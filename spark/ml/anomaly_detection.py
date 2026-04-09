"""
Anomaly Detection using hybrid Isolation Forest + LSTM-Autoencoder ensemble.
Detects heatwaves, cold snaps, and precipitation extremes from
multi-variate climate features with extreme-value-aware scoring.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, DoubleType,
    IntegerType, ArrayType
)
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, FEATURES_ROLLING_STATS, FEATURES_STL,
    OUTPUT_ANOMALIES, OUTPUT_TILES, OUTPUT_SUMMARIES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANOMALY_FEATURES = [
    "tmax_zscore_30d",
    "tmin_zscore_30d",
    "prcp_zscore_30d",
    "tmax_climatology_deviation",
    "tmin_climatology_deviation",
    "tmax_residual",
    "tmin_residual",
    "prcp_residual",
]

SEQUENCE_LENGTH = 30
LSTM_FEATURES = ["tmax_zscore_30d", "tmin_zscore_30d", "prcp_zscore_30d"]

ANOMALY_OUTPUT_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("obs_date", DateType(), False),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("geohash_prefix", StringType(), True),
    StructField("anomaly_type", StringType(), True),
    StructField("severity", DoubleType(), True),
    StructField("duration_days", IntegerType(), True),
    StructField("temp_deviation", DoubleType(), True),
    StructField("precip_deviation", DoubleType(), True),
    StructField("description", StringType(), True),
    StructField("year", IntegerType(), True),
    StructField("month", IntegerType(), True),
])


def _build_sequences(data, seq_len):
    """Build overlapping sequences for the LSTM autoencoder."""
    sequences = []
    for i in range(len(data) - seq_len + 1):
        sequences.append(data[i:i + seq_len])
    return np.array(sequences) if sequences else np.empty((0, seq_len, data.shape[1]))


def _lstm_autoencoder_scores(pdf, available_features):
    """
    Train a simple LSTM-Autoencoder and return reconstruction error scores.
    Uses Keras with a lightweight architecture optimized for per-station fitting.
    Falls back to zeros if TensorFlow is unavailable.
    """
    try:
        import tensorflow as tf
        from tensorflow import keras
    except ImportError:
        return np.zeros(len(pdf))

    lstm_feats = [f for f in LSTM_FEATURES if f in available_features]
    if len(lstm_feats) < 2:
        return np.zeros(len(pdf))

    data = pdf[lstm_feats].fillna(0).values
    if len(data) < SEQUENCE_LENGTH * 3:
        return np.zeros(len(pdf))

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data)

    sequences = _build_sequences(data_scaled, SEQUENCE_LENGTH)
    if len(sequences) < 50:
        return np.zeros(len(pdf))

    n_features = len(lstm_feats)
    model = keras.Sequential([
        keras.layers.LSTM(32, input_shape=(SEQUENCE_LENGTH, n_features), return_sequences=True),
        keras.layers.LSTM(16, return_sequences=False),
        keras.layers.RepeatVector(SEQUENCE_LENGTH),
        keras.layers.LSTM(16, return_sequences=True),
        keras.layers.LSTM(32, return_sequences=True),
        keras.layers.TimeDistributed(keras.layers.Dense(n_features)),
    ])
    model.compile(optimizer="adam", loss="mse")

    try:
        model.fit(sequences, sequences, epochs=10, batch_size=32, verbose=0, shuffle=True)
        reconstructed = model.predict(sequences, verbose=0)
        mse_per_seq = np.mean(np.square(sequences - reconstructed), axis=(1, 2))

        scores = np.zeros(len(pdf))
        for i, mse in enumerate(mse_per_seq):
            scores[i + SEQUENCE_LENGTH - 1] = mse

        for i in range(SEQUENCE_LENGTH - 1):
            scores[i] = scores[SEQUENCE_LENGTH - 1]

        return scores
    except Exception:
        return np.zeros(len(pdf))


def _extreme_value_weight(values, quantile=0.95):
    """
    Compute weights that up-weight extreme values (tail events).
    Inspired by MMWSTM-ADRAN+ extreme-value-aware scoring.
    """
    threshold = np.quantile(values[values > 0], quantile) if np.any(values > 0) else 1.0
    weights = np.ones_like(values)
    extreme_mask = values > threshold
    if extreme_mask.any():
        weights[extreme_mask] = 1.0 + np.log1p(values[extreme_mask] / threshold)
    return weights


def detect_anomalies_hybrid(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Hybrid anomaly detection combining Isolation Forest + LSTM-Autoencoder.
    Uses extreme-value-aware scoring to boost sensitivity to tail events.
    Parallelized across stations via applyInPandas.
    """
    from sklearn.ensemble import IsolationForest

    station_id = pdf["station_id"].iloc[0]
    lat = pdf["latitude"].iloc[0] if "latitude" in pdf.columns else 0
    lon = pdf["longitude"].iloc[0] if "longitude" in pdf.columns else 0
    geohash_prefix = pdf["geohash_prefix"].iloc[0] if "geohash_prefix" in pdf.columns else ""

    pdf = pdf.sort_values("obs_date").reset_index(drop=True)

    available_features = [f for f in ANOMALY_FEATURES if f in pdf.columns]
    if len(available_features) < 3:
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    X = pdf[available_features].copy()
    X = X.fillna(0)

    if len(X) < 365:
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    # --- Model 1: Isolation Forest ---
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.02,
        max_samples="auto",
        random_state=42,
        n_jobs=1,
    )

    try:
        iso_predictions = iso_forest.fit_predict(X)
        iso_scores = -iso_forest.score_samples(X)
    except Exception:
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    # --- Model 2: LSTM-Autoencoder (reconstruction error) ---
    lstm_scores = _lstm_autoencoder_scores(pdf, available_features)

    # --- Ensemble: weighted combination ---
    if iso_scores.std() > 0:
        iso_norm = (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min())
    else:
        iso_norm = np.full_like(iso_scores, 0.5)

    if lstm_scores.std() > 0:
        lstm_norm = (lstm_scores - lstm_scores.min()) / (lstm_scores.max() - lstm_scores.min())
    else:
        lstm_norm = np.zeros_like(lstm_scores)

    has_lstm = lstm_scores.sum() > 0
    if has_lstm:
        combined_scores = 0.6 * iso_norm + 0.4 * lstm_norm
    else:
        combined_scores = iso_norm

    ev_weights = _extreme_value_weight(combined_scores)
    weighted_scores = combined_scores * ev_weights

    threshold = np.percentile(weighted_scores, 98)
    anomaly_mask = (weighted_scores >= threshold) | (iso_predictions == -1)

    if not anomaly_mask.any():
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    anomaly_df = pdf[anomaly_mask].copy()
    anomaly_df["raw_score"] = weighted_scores[anomaly_mask]

    if anomaly_df["raw_score"].std() > 0:
        anomaly_df["severity"] = (
            (anomaly_df["raw_score"] - anomaly_df["raw_score"].min()) /
            (anomaly_df["raw_score"].max() - anomaly_df["raw_score"].min())
        ).clip(0.1, 1.0)
    else:
        anomaly_df["severity"] = 0.5

    def classify_anomaly(row):
        tmax_z = row.get("tmax_zscore_30d", 0) or 0
        tmin_z = row.get("tmin_zscore_30d", 0) or 0
        prcp_z = row.get("prcp_zscore_30d", 0) or 0
        tmax_clim = row.get("tmax_climatology_deviation", 0) or 0

        if tmax_z > 2 or tmax_clim > 2:
            return "heatwave"
        elif tmin_z < -2 or tmax_z < -2:
            return "cold_snap"
        elif prcp_z > 2:
            return "precip_extreme"
        elif tmax_z > 1.5:
            return "heatwave"
        elif tmin_z < -1.5:
            return "cold_snap"
        else:
            return "precip_extreme" if abs(prcp_z) > abs(tmax_z) else "heatwave"

    anomaly_df["anomaly_type"] = anomaly_df.apply(classify_anomaly, axis=1)

    anomaly_df["date_diff"] = anomaly_df["obs_date"].diff().dt.days
    anomaly_df["event_group"] = (anomaly_df["date_diff"] != 1).cumsum()
    duration_map = anomaly_df.groupby("event_group").size().to_dict()
    anomaly_df["duration_days"] = anomaly_df["event_group"].map(duration_map)

    anomaly_df["temp_deviation"] = anomaly_df.get("tmax_zscore_30d", 0)
    anomaly_df["precip_deviation"] = anomaly_df.get("prcp_zscore_30d", 0)

    method = "hybrid (IF+LSTM)" if has_lstm else "isolation_forest"

    def make_description(row):
        atype = row["anomaly_type"]
        sev = row["severity"]
        dur = row["duration_days"]
        if atype == "heatwave":
            return f"Heatwave event (severity: {sev:.2f}, {dur} days, +{row.get('temp_deviation', 0):.1f}σ) [{method}]"
        elif atype == "cold_snap":
            return f"Cold snap event (severity: {sev:.2f}, {dur} days, {row.get('temp_deviation', 0):.1f}σ) [{method}]"
        else:
            return f"Precipitation extreme (severity: {sev:.2f}, {dur} days, +{row.get('precip_deviation', 0):.1f}σ) [{method}]"

    anomaly_df["description"] = anomaly_df.apply(make_description, axis=1)

    result = pd.DataFrame({
        "station_id": anomaly_df["station_id"],
        "obs_date": anomaly_df["obs_date"],
        "latitude": lat,
        "longitude": lon,
        "geohash_prefix": geohash_prefix,
        "anomaly_type": anomaly_df["anomaly_type"],
        "severity": anomaly_df["severity"],
        "duration_days": anomaly_df["duration_days"].astype(int),
        "temp_deviation": anomaly_df["temp_deviation"],
        "precip_deviation": anomaly_df["precip_deviation"],
        "description": anomaly_df["description"],
        "year": anomaly_df["obs_date"].dt.year,
        "month": anomaly_df["obs_date"].dt.month,
    })

    return result


def run_anomaly_detection(spark: SparkSession):
    """Run distributed Isolation Forest anomaly detection across all stations."""
    logger.info("Loading feature data...")

    # Load rolling stats
    rolling = spark.read.parquet(FEATURES_ROLLING_STATS)

    # Try to load STL results and join
    try:
        stl = spark.read.parquet(FEATURES_STL).select(
            "station_id", "obs_date",
            "tmax_residual", "tmin_residual", "prcp_residual"
        )
        features = rolling.join(stl, on=["station_id", "obs_date"], how="left")
    except Exception:
        logger.warning("STL data not available, using rolling stats only")
        features = rolling.withColumn("tmax_residual", F.lit(None).cast("double")) \
            .withColumn("tmin_residual", F.lit(None).cast("double")) \
            .withColumn("prcp_residual", F.lit(None).cast("double"))

    # Select needed columns
    input_cols = [
        "station_id", "obs_date", "latitude", "longitude", "geohash_prefix",
        "year", "month", "tmax", "tmin", "prcp",
    ] + [f for f in ANOMALY_FEATURES if f in features.columns]

    input_df = features.select(*[c for c in input_cols if c in features.columns])

    logger.info("Running distributed hybrid anomaly detection (IF + LSTM-AE)...")
    anomalies = input_df.groupby("station_id").applyInPandas(
        detect_anomalies_hybrid, schema=ANOMALY_OUTPUT_SCHEMA
    )

    # Write anomalies
    logger.info(f"Writing detected anomalies to {OUTPUT_ANOMALIES}...")
    (
        anomalies
        .repartition("geohash_prefix", "year")
        .write
        .mode("overwrite")
        .partitionBy("year", "month")
        .parquet(OUTPUT_ANOMALIES)
    )

    anomaly_count = anomalies.count()
    logger.info(f"Anomaly detection complete: {anomaly_count:,} anomalies detected")

    # Generate summary statistics
    _generate_anomaly_summary(spark, anomalies)
    _generate_anomaly_tiles(spark, anomalies)

    return anomalies


def _generate_anomaly_summary(spark: SparkSession, anomalies):
    """Generate monthly anomaly summaries."""
    logger.info("Generating monthly anomaly summaries...")

    summary = anomalies.groupBy("year", "month").agg(
        F.count("*").alias("total_anomalies"),
        F.sum(F.when(F.col("anomaly_type") == "heatwave", 1).otherwise(0)).alias("heatwave_count"),
        F.sum(F.when(F.col("anomaly_type") == "cold_snap", 1).otherwise(0)).alias("cold_snap_count"),
        F.sum(F.when(F.col("anomaly_type") == "precip_extreme", 1).otherwise(0)).alias("precip_extreme_count"),
        F.avg("severity").alias("avg_severity"),
    )

    summary.write.mode("overwrite").parquet(OUTPUT_SUMMARIES)
    logger.info(f"Monthly summaries written to {OUTPUT_SUMMARIES}")


def _generate_anomaly_tiles(spark: SparkSession, anomalies):
    """Generate pre-aggregated anomaly tiles for heatmap display."""
    logger.info("Generating anomaly tiles for heatmap...")

    tiles = anomalies.groupBy("geohash_prefix", "year", "month").agg(
        F.count("*").alias("anomaly_count"),
        F.avg("severity").alias("avg_severity"),
        F.sum(F.when(F.col("anomaly_type") == "heatwave", 1).otherwise(0)).alias("heatwave_count"),
        F.sum(F.when(F.col("anomaly_type") == "cold_snap", 1).otherwise(0)).alias("cold_snap_count"),
        F.sum(F.when(F.col("anomaly_type") == "precip_extreme", 1).otherwise(0)).alias("precip_extreme_count"),
        F.avg("latitude").alias("center_lat"),
        F.avg("longitude").alias("center_lon"),
    )

    # Determine dominant type
    tiles = tiles.withColumn(
        "dominant_type",
        F.when(
            (F.col("heatwave_count") >= F.col("cold_snap_count")) &
            (F.col("heatwave_count") >= F.col("precip_extreme_count")),
            F.lit("heatwave")
        ).when(
            F.col("cold_snap_count") >= F.col("precip_extreme_count"),
            F.lit("cold_snap")
        ).otherwise(F.lit("precip_extreme"))
    )

    tiles.write.mode("overwrite").partitionBy("year").parquet(OUTPUT_TILES)
    logger.info(f"Anomaly tiles written to {OUTPUT_TILES}")


if __name__ == "__main__":
    spark = get_spark_session("Anomaly-Detection")
    run_anomaly_detection(spark)
    spark.stop()

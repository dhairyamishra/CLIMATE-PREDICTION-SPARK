"""
Anomaly Detection using Isolation Forest on Spark MLlib.
Detects heatwaves, cold snaps, and precipitation extremes from
multi-variate climate features.
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

# Features for anomaly detection
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


def detect_anomalies_isolation_forest(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Apply Isolation Forest anomaly detection per station.
    Uses sklearn IsolationForest for the actual detection,
    parallelized across stations via applyInPandas.
    """
    from sklearn.ensemble import IsolationForest

    station_id = pdf["station_id"].iloc[0]
    lat = pdf["latitude"].iloc[0] if "latitude" in pdf.columns else 0
    lon = pdf["longitude"].iloc[0] if "longitude" in pdf.columns else 0
    geohash_prefix = pdf["geohash_prefix"].iloc[0] if "geohash_prefix" in pdf.columns else ""

    pdf = pdf.sort_values("obs_date").reset_index(drop=True)

    # Extract feature matrix
    available_features = [f for f in ANOMALY_FEATURES if f in pdf.columns]
    if len(available_features) < 3:
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    X = pdf[available_features].copy()
    X = X.fillna(0)

    if len(X) < 365:
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    # Train Isolation Forest
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.02,  # expect ~2% anomalies
        max_samples="auto",
        random_state=42,
        n_jobs=1,
    )

    try:
        predictions = iso_forest.fit_predict(X)
        anomaly_scores = -iso_forest.score_samples(X)  # higher = more anomalous
    except Exception:
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    # Filter to anomalies (prediction == -1)
    anomaly_mask = predictions == -1
    if not anomaly_mask.any():
        return pd.DataFrame(columns=ANOMALY_OUTPUT_SCHEMA.fieldNames())

    anomaly_df = pdf[anomaly_mask].copy()
    anomaly_df["raw_score"] = anomaly_scores[anomaly_mask]

    # Normalize severity to 0-1 range
    if anomaly_df["raw_score"].std() > 0:
        anomaly_df["severity"] = (
            (anomaly_df["raw_score"] - anomaly_df["raw_score"].min()) /
            (anomaly_df["raw_score"].max() - anomaly_df["raw_score"].min())
        ).clip(0.1, 1.0)
    else:
        anomaly_df["severity"] = 0.5

    # Classify anomaly type based on feature values
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

    # Compute duration (consecutive anomaly days)
    anomaly_df["date_diff"] = anomaly_df["obs_date"].diff().dt.days
    anomaly_df["event_group"] = (anomaly_df["date_diff"] != 1).cumsum()
    duration_map = anomaly_df.groupby("event_group").size().to_dict()
    anomaly_df["duration_days"] = anomaly_df["event_group"].map(duration_map)

    # Compute deviations
    anomaly_df["temp_deviation"] = anomaly_df.get("tmax_zscore_30d", 0)
    anomaly_df["precip_deviation"] = anomaly_df.get("prcp_zscore_30d", 0)

    # Generate descriptions
    def make_description(row):
        atype = row["anomaly_type"]
        sev = row["severity"]
        dur = row["duration_days"]
        if atype == "heatwave":
            return f"Heatwave event (severity: {sev:.2f}, {dur} days, +{row.get('temp_deviation', 0):.1f}σ)"
        elif atype == "cold_snap":
            return f"Cold snap event (severity: {sev:.2f}, {dur} days, {row.get('temp_deviation', 0):.1f}σ)"
        else:
            return f"Precipitation extreme (severity: {sev:.2f}, {dur} days, +{row.get('precip_deviation', 0):.1f}σ)"

    anomaly_df["description"] = anomaly_df.apply(make_description, axis=1)

    # Build output
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

    logger.info("Running distributed Isolation Forest anomaly detection...")
    anomalies = input_df.groupby("station_id").applyInPandas(
        detect_anomalies_isolation_forest, schema=ANOMALY_OUTPUT_SCHEMA
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

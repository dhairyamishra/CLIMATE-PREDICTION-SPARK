"""
Unit tests for anomaly detection logic.
Uses local Spark session — no cluster required.
"""
import pytest
from datetime import date, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, DateType, IntegerType
)


def _create_features_df(spark, include_anomalies=True):
    """Create a synthetic features DataFrame with known anomalies."""
    schema = StructType([
        StructField("station_id", StringType(), False),
        StructField("obs_date", DateType(), False),
        StructField("tmax", FloatType()),
        StructField("tmin", FloatType()),
        StructField("prcp", FloatType()),
        StructField("tmax_zscore", FloatType()),
        StructField("tmin_zscore", FloatType()),
        StructField("prcp_zscore", FloatType()),
        StructField("latitude", FloatType()),
        StructField("longitude", FloatType()),
        StructField("geohash_prefix", StringType()),
        StructField("year", IntegerType()),
        StructField("month", IntegerType()),
    ])

    rows = []
    base = date(2020, 1, 1)
    for i in range(100):
        d = base + timedelta(days=i)
        # Normal data
        tmax_z = 0.3 if not include_anomalies else (0.3 if i < 90 else 4.0)
        tmin_z = 0.2 if not include_anomalies else (0.2 if i < 90 else -0.1)
        prcp_z = 0.1

        rows.append((
            "STATION_A", d,
            25.0 + tmax_z * 3, 15.0 + tmin_z * 2, 2.0 + prcp_z,
            tmax_z, tmin_z, prcp_z,
            40.7, -74.0, "dr5r",
            d.year, d.month,
        ))

    return spark.createDataFrame(rows, schema)


def test_anomaly_classification_heatwave(spark):
    """Test that high tmax z-scores are classified as heatwaves."""
    df = _create_features_df(spark, include_anomalies=True)

    # Apply classification logic (mirrors anomaly_detection.py)
    classified = df.withColumn(
        "anomaly_type",
        F.when(F.col("tmax_zscore") > 2.5, F.lit("heatwave"))
        .when(F.col("tmin_zscore") < -2.5, F.lit("cold_snap"))
        .when(F.col("prcp_zscore") > 3.0, F.lit("precip_extreme"))
        .otherwise(F.lit(None))
    ).filter(F.col("anomaly_type").isNotNull())

    results = classified.collect()
    assert len(results) > 0

    # Our injected anomalies (days 90-99) should be heatwaves
    for row in results:
        assert row["anomaly_type"] == "heatwave"
        assert row["tmax_zscore"] > 2.5


def test_no_anomalies_in_normal_data(spark):
    """Test that normal data produces no anomalies."""
    df = _create_features_df(spark, include_anomalies=False)

    classified = df.withColumn(
        "anomaly_type",
        F.when(F.col("tmax_zscore") > 2.5, F.lit("heatwave"))
        .when(F.col("tmin_zscore") < -2.5, F.lit("cold_snap"))
        .when(F.col("prcp_zscore") > 3.0, F.lit("precip_extreme"))
        .otherwise(F.lit(None))
    ).filter(F.col("anomaly_type").isNotNull())

    assert classified.count() == 0


def test_severity_calculation(spark):
    """Test that severity scales with z-score magnitude."""
    schema = StructType([
        StructField("station_id", StringType()),
        StructField("tmax_zscore", FloatType()),
    ])

    rows = [
        ("S1", 3.0),   # moderate
        ("S2", 5.0),   # severe
        ("S3", 8.0),   # extreme
    ]
    df = spark.createDataFrame(rows, schema)

    # Severity: normalize z-score to 0-1 range (clip at 10)
    result = df.withColumn(
        "severity",
        F.least(F.abs(F.col("tmax_zscore")) / 10.0, F.lit(1.0))
    )

    rows = result.orderBy("station_id").collect()
    assert rows[0]["severity"] == pytest.approx(0.3, abs=0.01)
    assert rows[1]["severity"] == pytest.approx(0.5, abs=0.01)
    assert rows[2]["severity"] == pytest.approx(0.8, abs=0.01)


def test_tile_aggregation(spark):
    """Test that anomaly tiles are aggregated by geohash + month."""
    schema = StructType([
        StructField("geohash_prefix", StringType()),
        StructField("year", IntegerType()),
        StructField("month", IntegerType()),
        StructField("anomaly_type", StringType()),
        StructField("severity", FloatType()),
        StructField("latitude", FloatType()),
        StructField("longitude", FloatType()),
    ])

    rows = [
        ("dr5r", 2020, 7, "heatwave", 0.8, 40.7, -74.0),
        ("dr5r", 2020, 7, "heatwave", 0.9, 40.8, -73.9),
        ("dr5r", 2020, 7, "cold_snap", 0.6, 40.7, -74.0),
        ("u33d", 2020, 7, "heatwave", 0.7, 48.8, 2.3),
    ]
    df = spark.createDataFrame(rows, schema)

    tiles = (
        df.groupBy("geohash_prefix", "year", "month")
        .agg(
            F.count("*").alias("anomaly_count"),
            F.avg("severity").alias("avg_severity"),
            F.avg("latitude").alias("center_lat"),
            F.avg("longitude").alias("center_lon"),
            F.sum(F.when(F.col("anomaly_type") == "heatwave", 1).otherwise(0)).alias("heatwave_count"),
            F.sum(F.when(F.col("anomaly_type") == "cold_snap", 1).otherwise(0)).alias("cold_snap_count"),
        )
    )

    result = tiles.orderBy("geohash_prefix").collect()
    assert len(result) == 2

    # dr5r tile
    dr5r = result[0]
    assert dr5r["geohash_prefix"] == "dr5r"
    assert dr5r["anomaly_count"] == 3
    assert dr5r["heatwave_count"] == 2
    assert dr5r["cold_snap_count"] == 1

    # u33d tile
    u33d = result[1]
    assert u33d["geohash_prefix"] == "u33d"
    assert u33d["anomaly_count"] == 1

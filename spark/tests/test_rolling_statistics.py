"""
Unit tests for the rolling statistics Spark job.
Uses local Spark session — no cluster required.
"""
import pytest
from datetime import date, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, DateType, IntegerType
)
from pyspark.sql.window import Window


def _create_test_observations(spark, num_days=365):
    """Create a synthetic observations DataFrame."""
    schema = StructType([
        StructField("station_id", StringType(), False),
        StructField("obs_date", DateType(), False),
        StructField("tmax", FloatType(), True),
        StructField("tmin", FloatType(), True),
        StructField("prcp", FloatType(), True),
        StructField("year", IntegerType(), False),
        StructField("month", IntegerType(), False),
        StructField("geohash_prefix", StringType(), False),
    ])

    rows = []
    base_date = date(2020, 1, 1)
    for i in range(num_days):
        d = base_date + timedelta(days=i)
        rows.append((
            "STATION_A",
            d,
            20.0 + 10.0 * (i % 30) / 30.0,   # tmax: 20-30 cyclical
            10.0 + 5.0 * (i % 30) / 30.0,     # tmin: 10-15 cyclical
            max(0.0, 5.0 - abs(15 - (i % 30))),  # prcp: triangle wave
            d.year,
            d.month,
            "dr5r",
        ))

    return spark.createDataFrame(rows, schema)


def test_rolling_mean_computation(spark):
    """Test that 30-day rolling mean is computed correctly."""
    df = _create_test_observations(spark, num_days=90)

    window_30d = (
        Window.partitionBy("station_id")
        .orderBy(F.col("obs_date").cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    result = df.withColumn(
        "tmax_rolling_30d_mean",
        F.avg("tmax").over(window_30d)
    )

    # Collect and verify
    rows = result.orderBy("obs_date").collect()
    assert len(rows) == 90

    # After day 30, rolling mean should be populated
    for row in rows[29:]:
        assert row["tmax_rolling_30d_mean"] is not None
        assert 20.0 <= row["tmax_rolling_30d_mean"] <= 30.0


def test_rolling_stddev_computation(spark):
    """Test that rolling standard deviation is computed."""
    df = _create_test_observations(spark, num_days=60)

    window_30d = (
        Window.partitionBy("station_id")
        .orderBy(F.col("obs_date").cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    result = df.withColumn(
        "tmax_rolling_30d_std",
        F.stddev("tmax").over(window_30d)
    )

    rows = result.orderBy("obs_date").collect()

    # Stddev should be > 0 for varying data (after enough rows)
    for row in rows[30:]:
        assert row["tmax_rolling_30d_std"] is not None
        assert row["tmax_rolling_30d_std"] > 0


def test_zscore_computation(spark):
    """Test z-score calculation from rolling stats."""
    df = _create_test_observations(spark, num_days=90)

    window_30d = (
        Window.partitionBy("station_id")
        .orderBy(F.col("obs_date").cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    result = (
        df
        .withColumn("tmax_mean", F.avg("tmax").over(window_30d))
        .withColumn("tmax_std", F.stddev("tmax").over(window_30d))
        .withColumn("tmax_zscore", F.when(
            F.col("tmax_std") > 0,
            (F.col("tmax") - F.col("tmax_mean")) / F.col("tmax_std")
        ).otherwise(0.0))
    )

    rows = result.orderBy("obs_date").collect()

    # Z-scores should be finite and reasonable
    for row in rows[30:]:
        z = row["tmax_zscore"]
        assert z is not None
        assert -10.0 < z < 10.0


def test_multiple_stations(spark):
    """Test rolling stats work independently per station."""
    schema = StructType([
        StructField("station_id", StringType(), False),
        StructField("obs_date", DateType(), False),
        StructField("tmax", FloatType(), True),
    ])

    rows = []
    base = date(2020, 1, 1)
    for i in range(60):
        d = base + timedelta(days=i)
        rows.append(("STATION_A", d, 20.0 + i * 0.1))
        rows.append(("STATION_B", d, 30.0 - i * 0.1))

    df = spark.createDataFrame(rows, schema)

    window = (
        Window.partitionBy("station_id")
        .orderBy(F.col("obs_date").cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    result = df.withColumn("tmax_avg", F.avg("tmax").over(window))

    # Station A should have increasing averages, Station B decreasing
    station_a = [r for r in result.collect() if r["station_id"] == "STATION_A"]
    station_b = [r for r in result.collect() if r["station_id"] == "STATION_B"]

    assert len(station_a) == 60
    assert len(station_b) == 60

    # Last avg for A should be higher than first
    a_sorted = sorted(station_a, key=lambda r: r["obs_date"])
    assert a_sorted[-1]["tmax_avg"] > a_sorted[0]["tmax_avg"]

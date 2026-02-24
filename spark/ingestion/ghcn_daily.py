"""
NOAA GHCN-Daily data ingestion pipeline.
Downloads station metadata and daily observations, converts to Parquet on HDFS.
"""
import os
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, IntegerType, DateType
)
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, RAW_GHCN_DAILY, RAW_STATION_METADATA,
    PROCESSED_OBSERVATIONS, PROCESSED_STATION_METADATA
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GHCN-Daily fixed-width format schema
STATION_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("latitude", FloatType(), False),
    StructField("longitude", FloatType(), False),
    StructField("elevation", FloatType(), True),
    StructField("state", StringType(), True),
    StructField("name", StringType(), True),
    StructField("gsn_flag", StringType(), True),
    StructField("hcn_flag", StringType(), True),
    StructField("wmo_id", StringType(), True),
])

DAILY_OBS_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("obs_date", StringType(), False),
    StructField("element", StringType(), False),
    StructField("value", FloatType(), True),
    StructField("m_flag", StringType(), True),
    StructField("q_flag", StringType(), True),
    StructField("s_flag", StringType(), True),
    StructField("obs_time", StringType(), True),
])


def ingest_station_metadata(spark: SparkSession, input_path: str):
    """Parse GHCN station inventory file into Parquet."""
    logger.info(f"Ingesting station metadata from {input_path}")

    df = spark.read.text(input_path)

    stations = df.select(
        F.trim(F.substring(F.col("value"), 1, 11)).alias("station_id"),
        F.substring(F.col("value"), 13, 8).cast(FloatType()).alias("latitude"),
        F.substring(F.col("value"), 22, 9).cast(FloatType()).alias("longitude"),
        F.substring(F.col("value"), 32, 6).cast(FloatType()).alias("elevation"),
        F.trim(F.substring(F.col("value"), 39, 2)).alias("state"),
        F.trim(F.substring(F.col("value"), 42, 30)).alias("name"),
        F.trim(F.substring(F.col("value"), 73, 3)).alias("gsn_flag"),
        F.trim(F.substring(F.col("value"), 77, 3)).alias("hcn_flag"),
        F.trim(F.substring(F.col("value"), 81, 5)).alias("wmo_id"),
    )

    # Extract country code from station_id (first 2 chars)
    stations = stations.withColumn("country", F.substring("station_id", 1, 2))

    # Add geohash
    stations = stations.withColumn(
        "geohash",
        F.udf(lambda lat, lon: _compute_geohash(lat, lon), StringType())(
            F.col("latitude"), F.col("longitude")
        )
    )

    stations.write.mode("overwrite").parquet(PROCESSED_STATION_METADATA)
    logger.info(f"Station metadata written to {PROCESSED_STATION_METADATA}")
    return stations


def ingest_daily_observations(spark: SparkSession, input_path: str):
    """Parse GHCN-Daily CSV observations into geo-partitioned Parquet."""
    logger.info(f"Ingesting daily observations from {input_path}")

    df = spark.read.csv(
        input_path,
        schema=DAILY_OBS_SCHEMA,
        header=False,
    )

    # Parse date and scale values (GHCN stores temps in tenths of degree C)
    observations = df.select(
        F.col("station_id"),
        F.to_date(F.col("obs_date"), "yyyyMMdd").alias("obs_date"),
        F.col("element"),
        F.when(
            F.col("element").isin("TMAX", "TMIN", "TAVG"),
            F.col("value") / 10.0
        ).otherwise(F.col("value")).alias("value"),
        F.col("q_flag"),
    )

    # Filter out quality-flagged observations
    observations = observations.filter(
        F.col("q_flag").isNull() | (F.col("q_flag") == "")
    )

    # Pivot elements to columns
    pivoted = (
        observations
        .groupBy("station_id", "obs_date")
        .pivot("element", ["TMAX", "TMIN", "TAVG", "PRCP", "SNOW", "SNWD"])
        .agg(F.first("value"))
    )

    # Rename pivoted columns to lowercase
    for col_name in ["TMAX", "TMIN", "TAVG", "PRCP", "SNOW", "SNWD"]:
        pivoted = pivoted.withColumnRenamed(col_name, col_name.lower())

    # Add partition columns
    pivoted = pivoted.withColumn("year", F.year("obs_date"))
    pivoted = pivoted.withColumn("month", F.month("obs_date"))

    # Join with station metadata to get geohash
    station_meta = spark.read.parquet(PROCESSED_STATION_METADATA).select(
        "station_id", "geohash"
    )
    pivoted = pivoted.join(
        F.broadcast(station_meta), on="station_id", how="left"
    )

    # Extract geohash prefix for partitioning (precision 4)
    pivoted = pivoted.withColumn(
        "geohash_prefix",
        F.substring("geohash", 1, 4)
    )

    # Write partitioned Parquet
    (
        pivoted
        .repartition("geohash_prefix", "year")
        .write
        .mode("overwrite")
        .partitionBy("geohash_prefix", "year", "month")
        .parquet(PROCESSED_OBSERVATIONS)
    )

    logger.info(f"Daily observations written to {PROCESSED_OBSERVATIONS}")
    return pivoted


def _compute_geohash(lat: float, lon: float, precision: int = 7) -> str:
    """Compute geohash from lat/lon coordinates."""
    try:
        import geohash as gh
        if lat is not None and lon is not None:
            return gh.encode(lat, lon, precision=precision)
    except ImportError:
        pass
    return ""


if __name__ == "__main__":
    spark = get_spark_session("GHCN-Daily-Ingestion")

    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "stations":
            input_path = sys.argv[2] if len(sys.argv) > 2 else f"{RAW_GHCN_DAILY}/ghcnd-stations.txt"
            ingest_station_metadata(spark, input_path)
        elif action == "observations":
            input_path = sys.argv[2] if len(sys.argv) > 2 else f"{RAW_GHCN_DAILY}/*.csv"
            ingest_daily_observations(spark, input_path)
        else:
            logger.error(f"Unknown action: {action}")
    else:
        logger.info("Usage: ghcn_daily.py [stations|observations] [input_path]")

    spark.stop()

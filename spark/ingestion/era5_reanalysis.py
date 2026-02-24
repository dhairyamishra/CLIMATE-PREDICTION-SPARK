"""
ERA5 Reanalysis data ingestion pipeline.
Converts NetCDF gridded data to geo-partitioned Parquet on HDFS.
"""
import os
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, IntegerType, DateType,
    DoubleType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import get_spark_session, RAW_ERA5, PROCESSED_ERA5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ERA5_SCHEMA = StructType([
    StructField("latitude", DoubleType(), False),
    StructField("longitude", DoubleType(), False),
    StructField("time", StringType(), False),
    StructField("t2m", DoubleType(), True),       # 2m temperature (K)
    StructField("tp", DoubleType(), True),         # total precipitation (m)
    StructField("sp", DoubleType(), True),         # surface pressure (Pa)
    StructField("u10", DoubleType(), True),        # 10m u-component of wind
    StructField("v10", DoubleType(), True),        # 10m v-component of wind
])


def ingest_era5_gridded(spark: SparkSession, input_path: str):
    """
    Ingest ERA5 reanalysis data (pre-converted from NetCDF to CSV/Parquet).
    Adds geohash and partitions by geohash prefix + year/month.
    """
    logger.info(f"Ingesting ERA5 reanalysis data from {input_path}")

    df = spark.read.csv(input_path, header=True, schema=ERA5_SCHEMA)

    # Convert units
    era5 = df.select(
        F.col("latitude"),
        F.col("longitude"),
        F.to_date(F.col("time")).alias("obs_date"),
        # Convert Kelvin to Celsius
        (F.col("t2m") - 273.15).alias("temp_2m_c"),
        # Convert m to mm
        (F.col("tp") * 1000.0).alias("precip_mm"),
        # Convert Pa to hPa
        (F.col("sp") / 100.0).alias("pressure_hpa"),
        # Wind speed from components
        F.sqrt(F.col("u10") ** 2 + F.col("v10") ** 2).alias("wind_speed_ms"),
    )

    # Add geohash for spatial indexing
    compute_geohash_udf = F.udf(
        lambda lat, lon: _compute_geohash(lat, lon, precision=5), StringType()
    )
    era5 = era5.withColumn("geohash", compute_geohash_udf("latitude", "longitude"))
    era5 = era5.withColumn("geohash_prefix", F.substring("geohash", 1, 4))
    era5 = era5.withColumn("year", F.year("obs_date"))
    era5 = era5.withColumn("month", F.month("obs_date"))

    # Write partitioned Parquet
    (
        era5
        .repartition("geohash_prefix", "year")
        .write
        .mode("overwrite")
        .partitionBy("geohash_prefix", "year", "month")
        .parquet(PROCESSED_ERA5)
    )

    logger.info(f"ERA5 data written to {PROCESSED_ERA5}")
    return era5


def _compute_geohash(lat: float, lon: float, precision: int = 5) -> str:
    """Compute geohash from lat/lon coordinates."""
    try:
        import geohash as gh
        if lat is not None and lon is not None:
            return gh.encode(lat, lon, precision=precision)
    except ImportError:
        pass
    return ""


if __name__ == "__main__":
    spark = get_spark_session("ERA5-Ingestion")
    input_path = sys.argv[1] if len(sys.argv) > 1 else f"{RAW_ERA5}/*.csv"
    ingest_era5_gridded(spark, input_path)
    spark.stop()

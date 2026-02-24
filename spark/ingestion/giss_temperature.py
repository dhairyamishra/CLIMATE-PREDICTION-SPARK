"""
NASA GISS Surface Temperature anomaly data ingestion.
Parses monthly anomaly grids into Parquet on HDFS.
"""
import os
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, IntegerType, DoubleType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import get_spark_session, RAW_GISS, PROCESSED_GISS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GISS_SCHEMA = StructType([
    StructField("year", IntegerType(), False),
    StructField("month", IntegerType(), False),
    StructField("latitude", DoubleType(), False),
    StructField("longitude", DoubleType(), False),
    StructField("temp_anomaly", DoubleType(), True),
])


def ingest_giss_anomalies(spark: SparkSession, input_path: str):
    """
    Ingest NASA GISS temperature anomaly grids.
    Expected input: CSV with year, month, lat, lon, temp_anomaly columns.
    """
    logger.info(f"Ingesting GISS temperature anomalies from {input_path}")

    df = spark.read.csv(input_path, header=True, schema=GISS_SCHEMA)

    # Build date column from year + month
    giss = df.withColumn(
        "obs_date",
        F.to_date(
            F.concat_ws("-", F.col("year"), F.lpad(F.col("month"), 2, "0"), F.lit("01")),
            "yyyy-MM-dd"
        )
    )

    # Add geohash
    compute_geohash_udf = F.udf(
        lambda lat, lon: _compute_geohash(lat, lon, precision=4), StringType()
    )
    giss = giss.withColumn("geohash", compute_geohash_udf("latitude", "longitude"))
    giss = giss.withColumn("geohash_prefix", F.substring("geohash", 1, 3))

    # Write partitioned
    (
        giss
        .repartition("year")
        .write
        .mode("overwrite")
        .partitionBy("year", "month")
        .parquet(PROCESSED_GISS)
    )

    logger.info(f"GISS anomalies written to {PROCESSED_GISS}")
    return giss


def _compute_geohash(lat: float, lon: float, precision: int = 4) -> str:
    """Compute geohash from lat/lon coordinates."""
    try:
        import geohash as gh
        if lat is not None and lon is not None:
            return gh.encode(lat, lon, precision=precision)
    except ImportError:
        pass
    return ""


if __name__ == "__main__":
    spark = get_spark_session("GISS-Ingestion")
    input_path = sys.argv[1] if len(sys.argv) > 1 else f"{RAW_GISS}/*.csv"
    ingest_giss_anomalies(spark, input_path)
    spark.stop()

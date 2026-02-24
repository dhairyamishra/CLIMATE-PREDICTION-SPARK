"""
Spark session configuration for climate data processing.
"""
import os
from pyspark.sql import SparkSession


def get_spark_session(app_name: str = "ClimateAnomalyEngine") -> SparkSession:
    """Create and return a configured SparkSession."""
    master_url = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
    hdfs_namenode = os.getenv("HDFS_NAMENODE_HOST", "namenode")
    hdfs_port = os.getenv("HDFS_NAMENODE_PORT", "9000")

    spark = (
        SparkSession.builder
        .appName(app_name)
        .master(master_url)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.shuffle.partitions", "200")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.hadoop.fs.defaultFS", f"hdfs://{hdfs_namenode}:{hdfs_port}")
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY", "2g"))
        .config("spark.executor.cores", os.getenv("SPARK_EXECUTOR_CORES", "2"))
        .enableHiveSupport()
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")
    return spark


# HDFS paths
HDFS_BASE = "/climate-data"
HDFS_RAW = f"{HDFS_BASE}/raw"
HDFS_PROCESSED = f"{HDFS_BASE}/processed"
HDFS_FEATURES = f"{HDFS_BASE}/features"
HDFS_MODELS = f"{HDFS_BASE}/models"
HDFS_OUTPUT = f"{HDFS_BASE}/output"

# Dataset paths
RAW_GHCN_DAILY = f"{HDFS_RAW}/ghcn-daily"
RAW_ERA5 = f"{HDFS_RAW}/era5"
RAW_GISS = f"{HDFS_RAW}/giss"
RAW_STATION_METADATA = f"{HDFS_RAW}/station-metadata"

PROCESSED_OBSERVATIONS = f"{HDFS_PROCESSED}/observations"
PROCESSED_STATION_METADATA = f"{HDFS_PROCESSED}/station-metadata"
PROCESSED_ERA5 = f"{HDFS_PROCESSED}/era5-gridded"
PROCESSED_GISS = f"{HDFS_PROCESSED}/giss-anomalies"

FEATURES_ROLLING_STATS = f"{HDFS_FEATURES}/rolling-stats"
FEATURES_STL = f"{HDFS_FEATURES}/stl-decomposition"
FEATURES_UNIFIED = f"{HDFS_FEATURES}/unified-climate"

OUTPUT_ANOMALIES = f"{HDFS_OUTPUT}/anomalies"
OUTPUT_FORECASTS = f"{HDFS_OUTPUT}/forecasts"
OUTPUT_TILES = f"{HDFS_OUTPUT}/tiles"
OUTPUT_SUMMARIES = f"{HDFS_OUTPUT}/summaries"

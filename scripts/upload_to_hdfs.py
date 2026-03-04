"""
Upload seed data from local filesystem to HDFS.
Run this after generate_seed_data.py and after HDFS is running.

Uses PySpark's Hadoop filesystem API so no external `hdfs` CLI is needed.
"""
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEED_DIR = os.getenv("SEED_OUTPUT_DIR", "/opt/data/seed" if os.path.isdir("/opt/data") else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "seed"
))
HDFS_BASE = "/climate-data/raw"


def get_hadoop_fs():
    """Get a Hadoop FileSystem instance via PySpark."""
    from pyspark.sql import SparkSession
    spark = SparkSession.builder \
        .appName("HDFS-Upload") \
        .config("spark.ui.showConsoleProgress", "false") \
        .getOrCreate()
    sc = spark.sparkContext
    jvm = sc._jvm
    conf = sc._jsc.hadoopConfiguration()
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(conf)
    Path = jvm.org.apache.hadoop.fs.Path
    return fs, Path, spark


def upload_directory(fs, Path, local_dir: str, hdfs_dir: str):
    """Upload a local directory to HDFS."""
    if not os.path.isdir(local_dir):
        logger.warning(f"Local directory not found: {local_dir}")
        return

    fs.mkdirs(Path(hdfs_dir))

    for fname in os.listdir(local_dir):
        local_path = os.path.join(local_dir, fname)
        if os.path.isfile(local_path):
            hdfs_path = f"{hdfs_dir}/{fname}"
            logger.info(f"Uploading {local_path} -> {hdfs_path}")
            fs.copyFromLocalFile(False, True, Path(local_path), Path(hdfs_path))


def main():
    logger.info("=" * 60)
    logger.info("Uploading seed data to HDFS (via PySpark Hadoop FS)")
    logger.info(f"Source: {SEED_DIR}")
    logger.info(f"Target: {HDFS_BASE}")
    logger.info("=" * 60)

    fs, Path, spark = get_hadoop_fs()

    for subdir in ["ghcn-daily", "station-metadata", "era5", "giss"]:
        fs.mkdirs(Path(f"{HDFS_BASE}/{subdir}"))

    upload_directory(fs, Path, os.path.join(SEED_DIR, "ghcn-daily"), f"{HDFS_BASE}/ghcn-daily")
    upload_directory(fs, Path, os.path.join(SEED_DIR, "station-metadata"), f"{HDFS_BASE}/station-metadata")
    upload_directory(fs, Path, os.path.join(SEED_DIR, "era5"), f"{HDFS_BASE}/era5")
    upload_directory(fs, Path, os.path.join(SEED_DIR, "giss"), f"{HDFS_BASE}/giss")

    logger.info("=" * 60)
    logger.info("HDFS upload complete!")

    status = fs.listStatus(Path(HDFS_BASE))
    for s in status:
        logger.info(f"  {s.getPath()}")

    logger.info("=" * 60)
    spark.stop()


if __name__ == "__main__":
    main()

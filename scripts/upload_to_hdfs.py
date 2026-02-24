"""
Upload seed data from local filesystem to HDFS.
Run this after generate_seed_data.py and after HDFS is running.
"""
import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEED_DIR = os.getenv("SEED_OUTPUT_DIR", "/opt/data/seed" if os.path.isdir("/opt/data") else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "seed"
))
HDFS_BASE = "/climate-data/raw"

HDFS_CMD = os.getenv("HDFS_CMD", "hdfs")


def run_hdfs(args: list):
    """Run an HDFS command."""
    cmd = [HDFS_CMD, "dfs"] + args
    logger.info(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"HDFS error: {result.stderr}")
        return False
    return True


def upload_directory(local_dir: str, hdfs_dir: str):
    """Upload a local directory to HDFS."""
    if not os.path.isdir(local_dir):
        logger.warning(f"Local directory not found: {local_dir}")
        return

    # Create HDFS directory
    run_hdfs(["-mkdir", "-p", hdfs_dir])

    # Upload files
    for fname in os.listdir(local_dir):
        local_path = os.path.join(local_dir, fname)
        if os.path.isfile(local_path):
            hdfs_path = f"{hdfs_dir}/{fname}"
            logger.info(f"Uploading {local_path} -> {hdfs_path}")
            run_hdfs(["-put", "-f", local_path, hdfs_path])


def main():
    logger.info("=" * 60)
    logger.info("Uploading seed data to HDFS")
    logger.info(f"Source: {SEED_DIR}")
    logger.info(f"Target: {HDFS_BASE}")
    logger.info("=" * 60)

    # Create base directories
    run_hdfs(["-mkdir", "-p", f"{HDFS_BASE}/ghcn-daily"])
    run_hdfs(["-mkdir", "-p", f"{HDFS_BASE}/station-metadata"])
    run_hdfs(["-mkdir", "-p", f"{HDFS_BASE}/era5"])
    run_hdfs(["-mkdir", "-p", f"{HDFS_BASE}/giss"])

    # Upload each dataset
    upload_directory(os.path.join(SEED_DIR, "ghcn-daily"), f"{HDFS_BASE}/ghcn-daily")
    upload_directory(os.path.join(SEED_DIR, "station-metadata"), f"{HDFS_BASE}/station-metadata")
    upload_directory(os.path.join(SEED_DIR, "era5"), f"{HDFS_BASE}/era5")
    upload_directory(os.path.join(SEED_DIR, "giss"), f"{HDFS_BASE}/giss")

    logger.info("=" * 60)
    logger.info("HDFS upload complete!")
    run_hdfs(["-ls", "-R", HDFS_BASE])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

"""
Shared fixtures for Spark unit tests.
Uses local Spark session (no cluster required).
"""
import os
import sys
import shutil
import tempfile
import pytest
from pyspark.sql import SparkSession

# Add parent dirs to path so we can import spark modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def spark():
    """Create a local SparkSession for testing."""
    session = (
        SparkSession.builder
        .master("local[2]")
        .appName("ClimateAnomalyTests")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.driver.memory", "1g")
        .config("spark.sql.warehouse.dir", tempfile.mkdtemp())
        .config("spark.driver.extraJavaOptions", "-Dderby.system.home=" + tempfile.mkdtemp())
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def tmp_path_spark():
    """Temporary directory for Spark output, cleaned up after test."""
    path = tempfile.mkdtemp(prefix="spark_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)

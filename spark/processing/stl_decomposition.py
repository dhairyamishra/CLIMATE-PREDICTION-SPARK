"""
Distributed STL (Seasonal-Trend decomposition using LOESS) per station.
Parallelized via Spark applyInPandas grouped by station_id.
"""
import os
import sys
import logging
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, DoubleType, IntegerType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, FEATURES_ROLLING_STATS, FEATURES_STL
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output schema for STL decomposition
STL_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("obs_date", DateType(), False),
    StructField("year", IntegerType(), True),
    StructField("month", IntegerType(), True),
    StructField("geohash_prefix", StringType(), True),
    StructField("tmax", DoubleType(), True),
    StructField("tmin", DoubleType(), True),
    StructField("prcp", DoubleType(), True),
    StructField("tmax_trend", DoubleType(), True),
    StructField("tmax_seasonal", DoubleType(), True),
    StructField("tmax_residual", DoubleType(), True),
    StructField("tmin_trend", DoubleType(), True),
    StructField("tmin_seasonal", DoubleType(), True),
    StructField("tmin_residual", DoubleType(), True),
    StructField("prcp_trend", DoubleType(), True),
    StructField("prcp_seasonal", DoubleType(), True),
    StructField("prcp_residual", DoubleType(), True),
])


def stl_decompose_station(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Apply STL decomposition to a single station's time series.
    Called via applyInPandas for distributed execution.
    """
    from statsmodels.tsa.seasonal import STL

    station_id = pdf["station_id"].iloc[0]
    geohash_prefix = pdf["geohash_prefix"].iloc[0] if "geohash_prefix" in pdf.columns else ""

    pdf = pdf.sort_values("obs_date").reset_index(drop=True)

    # Need at least 2 full years of data for STL
    if len(pdf) < 730:
        pdf["tmax_trend"] = np.nan
        pdf["tmax_seasonal"] = np.nan
        pdf["tmax_residual"] = np.nan
        pdf["tmin_trend"] = np.nan
        pdf["tmin_seasonal"] = np.nan
        pdf["tmin_residual"] = np.nan
        pdf["prcp_trend"] = np.nan
        pdf["prcp_seasonal"] = np.nan
        pdf["prcp_residual"] = np.nan
        return pdf[STL_SCHEMA.fieldNames()]

    # Set date as index for STL
    ts = pdf.set_index("obs_date")

    results = {}
    for variable in ["tmax", "tmin", "prcp"]:
        series = ts[variable].copy()

        # Fill missing values with interpolation for STL
        series = series.interpolate(method="linear", limit=30)
        series = series.fillna(method="bfill").fillna(method="ffill")

        if series.isna().all() or series.std() == 0:
            results[f"{variable}_trend"] = np.full(len(pdf), np.nan)
            results[f"{variable}_seasonal"] = np.full(len(pdf), np.nan)
            results[f"{variable}_residual"] = np.full(len(pdf), np.nan)
            continue

        try:
            stl = STL(
                series,
                period=365,
                seasonal=365,
                trend=731,
                robust=True,
            )
            decomposition = stl.fit()
            results[f"{variable}_trend"] = decomposition.trend.values
            results[f"{variable}_seasonal"] = decomposition.seasonal.values
            results[f"{variable}_residual"] = decomposition.resid.values
        except Exception:
            results[f"{variable}_trend"] = np.full(len(pdf), np.nan)
            results[f"{variable}_seasonal"] = np.full(len(pdf), np.nan)
            results[f"{variable}_residual"] = np.full(len(pdf), np.nan)

    for col, values in results.items():
        pdf[col] = values

    return pdf[STL_SCHEMA.fieldNames()]


def run_stl_decomposition(spark: SparkSession):
    """Run distributed STL decomposition across all stations."""
    logger.info("Loading rolling statistics data...")
    df = spark.read.parquet(FEATURES_ROLLING_STATS)

    # Select only needed columns to reduce shuffle
    input_df = df.select(
        "station_id", "obs_date", "year", "month", "geohash_prefix",
        "tmax", "tmin", "prcp"
    )

    logger.info("Running distributed STL decomposition...")
    stl_results = input_df.groupby("station_id").applyInPandas(
        stl_decompose_station, schema=STL_SCHEMA
    )

    logger.info(f"Writing STL decomposition results to {FEATURES_STL}...")
    (
        stl_results
        .repartition("geohash_prefix", "year")
        .write
        .mode("overwrite")
        .partitionBy("geohash_prefix", "year")
        .parquet(FEATURES_STL)
    )

    record_count = stl_results.count()
    logger.info(f"STL decomposition complete: {record_count:,} records")
    return stl_results


if __name__ == "__main__":
    spark = get_spark_session("STL-Decomposition")
    run_stl_decomposition(spark)
    spark.stop()

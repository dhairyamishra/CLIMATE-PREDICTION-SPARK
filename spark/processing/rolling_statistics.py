"""
Rolling statistics computation using Spark Window functions.
Computes 30-day, 90-day, and 365-day rolling mean, stddev, min, max
for TMAX, TMIN, PRCP across 100K+ stations.
"""
import os
import sys
import logging
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, FEATURES_UNIFIED, FEATURES_ROLLING_STATS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def compute_rolling_statistics(spark: SparkSession):
    """
    Compute multi-scale rolling statistics per station using Window functions.
    Windows: 30-day, 90-day, 365-day for TMAX, TMIN, PRCP.
    """
    logger.info("Loading unified climate observations...")
    df = spark.read.parquet(FEATURES_UNIFIED)

    logger.info("Computing rolling statistics over multiple windows...")

    # Define window specs partitioned by station_id, ordered by obs_date
    # rangeBetween uses days-in-seconds offset
    SECONDS_PER_DAY = 86400

    def days_window(station_col: str, date_col: str, days: int):
        return (
            Window
            .partitionBy(station_col)
            .orderBy(F.col(date_col).cast("timestamp").cast("long"))
            .rangeBetween(-days * SECONDS_PER_DAY, 0)
        )

    w30 = days_window("station_id", "obs_date", 30)
    w90 = days_window("station_id", "obs_date", 90)
    w365 = days_window("station_id", "obs_date", 365)

    # --- 30-day rolling statistics ---
    logger.info("  Computing 30-day rolling windows...")
    result = df.withColumn("tmax_rolling_30d_mean", F.avg("tmax").over(w30)) \
        .withColumn("tmax_rolling_30d_std", F.stddev("tmax").over(w30)) \
        .withColumn("tmax_rolling_30d_min", F.min("tmax").over(w30)) \
        .withColumn("tmax_rolling_30d_max", F.max("tmax").over(w30)) \
        .withColumn("tmin_rolling_30d_mean", F.avg("tmin").over(w30)) \
        .withColumn("tmin_rolling_30d_std", F.stddev("tmin").over(w30)) \
        .withColumn("tmin_rolling_30d_min", F.min("tmin").over(w30)) \
        .withColumn("tmin_rolling_30d_max", F.max("tmin").over(w30)) \
        .withColumn("prcp_rolling_30d_mean", F.avg("prcp").over(w30)) \
        .withColumn("prcp_rolling_30d_std", F.stddev("prcp").over(w30)) \
        .withColumn("prcp_rolling_30d_sum", F.sum("prcp").over(w30)) \
        .withColumn("prcp_rolling_30d_max", F.max("prcp").over(w30))

    # --- 90-day rolling statistics ---
    logger.info("  Computing 90-day rolling windows...")
    result = result \
        .withColumn("tmax_rolling_90d_mean", F.avg("tmax").over(w90)) \
        .withColumn("tmax_rolling_90d_std", F.stddev("tmax").over(w90)) \
        .withColumn("tmin_rolling_90d_mean", F.avg("tmin").over(w90)) \
        .withColumn("tmin_rolling_90d_std", F.stddev("tmin").over(w90)) \
        .withColumn("prcp_rolling_90d_mean", F.avg("prcp").over(w90)) \
        .withColumn("prcp_rolling_90d_sum", F.sum("prcp").over(w90))

    # --- 365-day rolling statistics ---
    logger.info("  Computing 365-day rolling windows...")
    result = result \
        .withColumn("tmax_rolling_365d_mean", F.avg("tmax").over(w365)) \
        .withColumn("tmax_rolling_365d_std", F.stddev("tmax").over(w365)) \
        .withColumn("tmin_rolling_365d_mean", F.avg("tmin").over(w365)) \
        .withColumn("tmin_rolling_365d_std", F.stddev("tmin").over(w365)) \
        .withColumn("prcp_rolling_365d_mean", F.avg("prcp").over(w365)) \
        .withColumn("prcp_rolling_365d_sum", F.sum("prcp").over(w365))

    # --- Z-scores (deviation from rolling mean, normalized by stddev) ---
    logger.info("  Computing z-scores...")
    result = result \
        .withColumn(
            "tmax_zscore_30d",
            F.when(
                F.col("tmax_rolling_30d_std") > 0,
                (F.col("tmax") - F.col("tmax_rolling_30d_mean")) / F.col("tmax_rolling_30d_std")
            ).otherwise(0)
        ) \
        .withColumn(
            "tmin_zscore_30d",
            F.when(
                F.col("tmin_rolling_30d_std") > 0,
                (F.col("tmin") - F.col("tmin_rolling_30d_mean")) / F.col("tmin_rolling_30d_std")
            ).otherwise(0)
        ) \
        .withColumn(
            "prcp_zscore_30d",
            F.when(
                F.col("prcp_rolling_30d_std") > 0,
                (F.col("prcp") - F.col("prcp_rolling_30d_mean")) / F.col("prcp_rolling_30d_std")
            ).otherwise(0)
        )

    # --- Day-of-year climatology deviation ---
    logger.info("  Computing day-of-year climatology...")
    result = result.withColumn("day_of_year", F.dayofyear("obs_date"))

    doy_window = Window.partitionBy("station_id", "day_of_year")
    result = result \
        .withColumn("tmax_doy_mean", F.avg("tmax").over(doy_window)) \
        .withColumn("tmax_doy_std", F.stddev("tmax").over(doy_window)) \
        .withColumn("tmin_doy_mean", F.avg("tmin").over(doy_window)) \
        .withColumn("tmin_doy_std", F.stddev("tmin").over(doy_window)) \
        .withColumn(
            "tmax_climatology_deviation",
            F.when(
                F.col("tmax_doy_std") > 0,
                (F.col("tmax") - F.col("tmax_doy_mean")) / F.col("tmax_doy_std")
            ).otherwise(0)
        ) \
        .withColumn(
            "tmin_climatology_deviation",
            F.when(
                F.col("tmin_doy_std") > 0,
                (F.col("tmin") - F.col("tmin_doy_mean")) / F.col("tmin_doy_std")
            ).otherwise(0)
        )

    # --- Write output ---
    logger.info(f"Writing rolling statistics to {FEATURES_ROLLING_STATS}...")
    (
        result
        .repartition("geohash_prefix", "year")
        .write
        .mode("overwrite")
        .partitionBy("geohash_prefix", "year")
        .parquet(FEATURES_ROLLING_STATS)
    )

    record_count = result.count()
    logger.info(f"Rolling statistics computed: {record_count:,} records")
    return result


if __name__ == "__main__":
    spark = get_spark_session("Rolling-Statistics")
    compute_rolling_statistics(spark)
    spark.stop()

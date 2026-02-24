"""
Spark SQL — Massive joins between station metadata, daily observations,
and gridded reanalysis data to create the unified climate_observations table.
"""
import os
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session,
    PROCESSED_OBSERVATIONS, PROCESSED_STATION_METADATA,
    PROCESSED_ERA5, PROCESSED_GISS, FEATURES_UNIFIED
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def join_all_datasets(spark: SparkSession):
    """
    Join station metadata, daily observations, ERA5 gridded reanalysis,
    and GISS monthly anomalies into a unified climate table.
    """
    logger.info("Loading processed datasets...")

    # --- Load station metadata (small, broadcast) ---
    stations = spark.read.parquet(PROCESSED_STATION_METADATA).select(
        "station_id", "name", "latitude", "longitude", "elevation",
        "country", "geohash"
    ).alias("s")

    # --- Load daily observations ---
    observations = spark.read.parquet(PROCESSED_OBSERVATIONS).select(
        "station_id", "obs_date", "tmax", "tmin", "tavg", "prcp", "snow", "snwd",
        "geohash", "geohash_prefix", "year", "month"
    ).alias("o")

    logger.info(f"Observations count: {observations.count():,}")
    logger.info(f"Stations count: {stations.count():,}")

    # --- Join observations with station metadata (broadcast join) ---
    logger.info("Joining observations with station metadata (broadcast)...")
    obs_with_meta = observations.join(
        F.broadcast(stations),
        on=(F.col("o.station_id") == F.col("s.station_id")),
        how="inner"
    ).select(
        F.col("o.station_id"),
        F.col("o.obs_date"),
        F.col("o.tmax"),
        F.col("o.tmin"),
        F.col("o.tavg"),
        F.col("o.prcp"),
        F.col("o.snow"),
        F.col("o.snwd"),
        F.col("s.name").alias("station_name"),
        F.col("s.latitude"),
        F.col("s.longitude"),
        F.col("s.elevation"),
        F.col("s.country"),
        F.col("o.geohash"),
        F.col("o.geohash_prefix"),
        F.col("o.year"),
        F.col("o.month"),
    )

    # --- Load ERA5 reanalysis (join by geohash prefix + date) ---
    try:
        era5 = spark.read.parquet(PROCESSED_ERA5).select(
            "geohash_prefix", "obs_date",
            F.col("temp_2m_c").alias("era5_temp_2m"),
            F.col("precip_mm").alias("era5_precip"),
            F.col("pressure_hpa").alias("era5_pressure"),
            F.col("wind_speed_ms").alias("era5_wind_speed"),
        ).alias("e")

        # Aggregate ERA5 to geohash_prefix + date level (may have multiple grid cells)
        era5_agg = era5.groupBy("geohash_prefix", "obs_date").agg(
            F.avg("era5_temp_2m").alias("era5_temp_2m"),
            F.avg("era5_precip").alias("era5_precip"),
            F.avg("era5_pressure").alias("era5_pressure"),
            F.avg("era5_wind_speed").alias("era5_wind_speed"),
        )

        logger.info("Joining with ERA5 reanalysis data...")
        obs_with_era5 = obs_with_meta.join(
            era5_agg,
            on=[
                obs_with_meta.geohash_prefix == era5_agg.geohash_prefix,
                F.trunc(obs_with_meta.obs_date, "month") == F.trunc(era5_agg.obs_date, "month"),
            ],
            how="left"
        ).drop(era5_agg.geohash_prefix).drop(era5_agg.obs_date)

    except Exception as e:
        logger.warning(f"ERA5 data not available, skipping: {e}")
        obs_with_era5 = obs_with_meta.withColumn("era5_temp_2m", F.lit(None).cast("double")) \
            .withColumn("era5_precip", F.lit(None).cast("double")) \
            .withColumn("era5_pressure", F.lit(None).cast("double")) \
            .withColumn("era5_wind_speed", F.lit(None).cast("double"))

    # --- Load GISS monthly anomalies (join by geohash prefix + year/month) ---
    try:
        giss = spark.read.parquet(PROCESSED_GISS).select(
            "year", "month", "geohash_prefix",
            F.col("temp_anomaly").alias("giss_temp_anomaly"),
        ).alias("g")

        giss_agg = giss.groupBy("year", "month", "geohash_prefix").agg(
            F.avg("giss_temp_anomaly").alias("giss_temp_anomaly"),
        )

        logger.info("Joining with GISS temperature anomalies...")
        unified = obs_with_era5.join(
            giss_agg,
            on=[
                obs_with_era5.year == giss_agg.year,
                obs_with_era5.month == giss_agg.month,
                F.substring(obs_with_era5.geohash_prefix, 1, 3) == giss_agg.geohash_prefix,
            ],
            how="left"
        ).drop(giss_agg.year).drop(giss_agg.month).drop(giss_agg.geohash_prefix)

    except Exception as e:
        logger.warning(f"GISS data not available, skipping: {e}")
        unified = obs_with_era5.withColumn("giss_temp_anomaly", F.lit(None).cast("double"))

    # --- Compute derived features ---
    logger.info("Computing derived features...")
    unified = unified.withColumn(
        "tavg_computed",
        F.coalesce(F.col("tavg"), (F.col("tmax") + F.col("tmin")) / 2)
    )

    # Temperature deviation from ERA5 (if available)
    unified = unified.withColumn(
        "temp_deviation_from_reanalysis",
        F.when(
            F.col("era5_temp_2m").isNotNull(),
            F.col("tavg_computed") - F.col("era5_temp_2m")
        )
    )

    # --- Write unified table ---
    logger.info(f"Writing unified climate observations to {FEATURES_UNIFIED}...")
    (
        unified
        .repartition("geohash_prefix", "year")
        .write
        .mode("overwrite")
        .partitionBy("geohash_prefix", "year", "month")
        .parquet(FEATURES_UNIFIED)
    )

    # Register as Spark SQL table
    spark.catalog.createTable(
        "climate_observations",
        path=FEATURES_UNIFIED,
        source="parquet"
    )

    record_count = unified.count()
    logger.info(f"Unified climate_observations table created: {record_count:,} records")
    return unified


if __name__ == "__main__":
    spark = get_spark_session("Dataset-Join")
    join_all_datasets(spark)
    spark.stop()

"""
Compute climate indices (ENSO/ONI, NAO, PDO, AMO, IOD) from ERA5 and GISS data.
Produces monthly index values stored in HDFS as Parquet.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, DoubleType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, PROCESSED_ERA5, PROCESSED_GISS, HDFS_OUTPUT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_INDICES = f"{HDFS_OUTPUT}/climate-indices"

INDEX_SCHEMA = StructType([
    StructField("index_date", DateType(), False),
    StructField("index_name", StringType(), False),
    StructField("value", DoubleType(), False),
    StructField("anomaly", DoubleType(), True),
    StructField("source", StringType(), True),
])

NINO34_LAT = (-5, 5)
NINO34_LON = (-170, -120)

NAO_AZORES_LAT = (36, 40)
NAO_AZORES_LON = (-30, -25)
NAO_ICELAND_LAT = (63, 66)
NAO_ICELAND_LON = (-25, -15)

PDO_LAT = (20, 60)
PDO_LON = (120, 260)

AMO_LAT = (0, 60)
AMO_LON = (-80, 0)

IOD_WEST_LAT = (-10, 10)
IOD_WEST_LON = (50, 70)
IOD_EAST_LAT = (-10, 0)
IOD_EAST_LON = (90, 110)


def _in_box(lat_col, lon_col, lat_range, lon_range):
    """Build a Spark SQL condition for a bounding box."""
    return (
        (F.col(lat_col) >= lat_range[0]) & (F.col(lat_col) <= lat_range[1]) &
        (F.col(lon_col) >= lon_range[0]) & (F.col(lon_col) <= lon_range[1])
    )


def compute_oni(era5_df):
    """
    Oceanic Nino Index — 3-month running mean of SST anomalies in the Nino 3.4 region.
    We approximate using 2m temperature from ERA5 over the equatorial Pacific.
    """
    logger.info("Computing ONI (Oceanic Nino Index)...")

    nino34 = era5_df.filter(_in_box("latitude", "longitude", NINO34_LAT, NINO34_LON))

    monthly = nino34.groupBy("year", "month").agg(
        F.avg("temp_2m_c").alias("sst_mean")
    )

    climatology = monthly.groupBy("month").agg(
        F.avg("sst_mean").alias("clim_mean")
    )

    with_anom = monthly.join(climatology, on="month", how="left")
    with_anom = with_anom.withColumn("anomaly", F.col("sst_mean") - F.col("clim_mean"))

    from pyspark.sql.window import Window
    w = Window.orderBy("year", "month").rowsBetween(-1, 1)
    with_anom = with_anom.withColumn("oni_value", F.avg("anomaly").over(w))

    result = with_anom.select(
        F.make_date("year", "month", F.lit(1)).alias("index_date"),
        F.lit("oni").alias("index_name"),
        F.round("oni_value", 4).alias("value"),
        F.round("anomaly", 4).alias("anomaly"),
        F.lit("ERA5-derived").alias("source"),
    )
    return result


def compute_nao(era5_df):
    """
    North Atlantic Oscillation — normalized pressure difference between Azores and Iceland.
    """
    logger.info("Computing NAO (North Atlantic Oscillation)...")

    azores = era5_df.filter(_in_box("latitude", "longitude", NAO_AZORES_LAT, NAO_AZORES_LON))
    iceland = era5_df.filter(_in_box("latitude", "longitude", NAO_ICELAND_LAT, NAO_ICELAND_LON))

    azores_monthly = azores.groupBy("year", "month").agg(
        F.avg("pressure_hpa").alias("azores_pressure")
    )
    iceland_monthly = iceland.groupBy("year", "month").agg(
        F.avg("pressure_hpa").alias("iceland_pressure")
    )

    combined = azores_monthly.join(iceland_monthly, on=["year", "month"], how="inner")
    combined = combined.withColumn(
        "pressure_diff",
        F.col("azores_pressure") - F.col("iceland_pressure")
    )

    stats = combined.agg(
        F.avg("pressure_diff").alias("mean_diff"),
        F.stddev("pressure_diff").alias("std_diff")
    ).collect()[0]

    mean_diff = stats["mean_diff"] or 0
    std_diff = stats["std_diff"] or 1

    result = combined.select(
        F.make_date("year", "month", F.lit(1)).alias("index_date"),
        F.lit("nao").alias("index_name"),
        F.round((F.col("pressure_diff") - F.lit(mean_diff)) / F.lit(std_diff), 4).alias("value"),
        F.round(F.col("pressure_diff") - F.lit(mean_diff), 4).alias("anomaly"),
        F.lit("ERA5-derived").alias("source"),
    )
    return result


def compute_pdo(era5_df):
    """
    Pacific Decadal Oscillation — leading mode of North Pacific SST variability.
    Approximated as the detrended SST anomaly averaged over the North Pacific.
    """
    logger.info("Computing PDO (Pacific Decadal Oscillation)...")

    adjusted_df = era5_df.withColumn(
        "adj_lon", F.when(F.col("longitude") < 0, F.col("longitude") + 360).otherwise(F.col("longitude"))
    )

    npac = adjusted_df.filter(
        (F.col("latitude") >= PDO_LAT[0]) & (F.col("latitude") <= PDO_LAT[1]) &
        (F.col("adj_lon") >= PDO_LON[0]) & (F.col("adj_lon") <= PDO_LON[1])
    )

    monthly = npac.groupBy("year", "month").agg(
        F.avg("temp_2m_c").alias("sst_mean")
    )

    climatology = monthly.groupBy("month").agg(F.avg("sst_mean").alias("clim_mean"))
    with_anom = monthly.join(climatology, on="month", how="left")
    with_anom = with_anom.withColumn("anomaly", F.col("sst_mean") - F.col("clim_mean"))

    global_mean = with_anom.agg(F.avg("anomaly").alias("global_mean")).collect()[0]["global_mean"] or 0
    with_anom = with_anom.withColumn("pdo_value", F.col("anomaly") - F.lit(global_mean))

    result = with_anom.select(
        F.make_date("year", "month", F.lit(1)).alias("index_date"),
        F.lit("pdo").alias("index_name"),
        F.round("pdo_value", 4).alias("value"),
        F.round("anomaly", 4).alias("anomaly"),
        F.lit("ERA5-derived").alias("source"),
    )
    return result


def compute_amo(era5_df):
    """
    Atlantic Multidecadal Oscillation — detrended North Atlantic SST anomalies.
    """
    logger.info("Computing AMO (Atlantic Multidecadal Oscillation)...")

    natl = era5_df.filter(_in_box("latitude", "longitude", AMO_LAT, AMO_LON))

    monthly = natl.groupBy("year", "month").agg(
        F.avg("temp_2m_c").alias("sst_mean")
    )
    climatology = monthly.groupBy("month").agg(F.avg("sst_mean").alias("clim_mean"))
    with_anom = monthly.join(climatology, on="month", how="left")
    with_anom = with_anom.withColumn("anomaly", F.col("sst_mean") - F.col("clim_mean"))

    from pyspark.sql.window import Window
    w = Window.orderBy("year", "month").rowsBetween(-5, 5)
    with_anom = with_anom.withColumn("amo_value", F.avg("anomaly").over(w))

    result = with_anom.select(
        F.make_date("year", "month", F.lit(1)).alias("index_date"),
        F.lit("amo").alias("index_name"),
        F.round("amo_value", 4).alias("value"),
        F.round("anomaly", 4).alias("anomaly"),
        F.lit("ERA5-derived").alias("source"),
    )
    return result


def compute_iod(era5_df):
    """
    Indian Ocean Dipole — SST gradient between western and eastern tropical Indian Ocean.
    """
    logger.info("Computing IOD (Indian Ocean Dipole)...")

    west = era5_df.filter(_in_box("latitude", "longitude", IOD_WEST_LAT, IOD_WEST_LON))
    east = era5_df.filter(_in_box("latitude", "longitude", IOD_EAST_LAT, IOD_EAST_LON))

    west_monthly = west.groupBy("year", "month").agg(
        F.avg("temp_2m_c").alias("west_sst")
    )
    east_monthly = east.groupBy("year", "month").agg(
        F.avg("temp_2m_c").alias("east_sst")
    )

    combined = west_monthly.join(east_monthly, on=["year", "month"], how="inner")
    combined = combined.withColumn("iod_value", F.col("west_sst") - F.col("east_sst"))

    climatology = combined.agg(F.avg("iod_value").alias("clim")).collect()[0]["clim"] or 0

    result = combined.select(
        F.make_date("year", "month", F.lit(1)).alias("index_date"),
        F.lit("iod").alias("index_name"),
        F.round(F.col("iod_value") - F.lit(climatology), 4).alias("value"),
        F.round(F.col("iod_value") - F.lit(climatology), 4).alias("anomaly"),
        F.lit("ERA5-derived").alias("source"),
    )
    return result


def run_climate_indices(spark: SparkSession):
    """Compute all climate indices and write to HDFS."""
    logger.info("=" * 60)
    logger.info("Computing climate indices...")
    logger.info("=" * 60)

    era5 = spark.read.parquet(PROCESSED_ERA5)

    all_indices = []
    for compute_fn in [compute_oni, compute_nao, compute_pdo, compute_amo, compute_iod]:
        try:
            idx = compute_fn(era5)
            all_indices.append(idx)
        except Exception as e:
            logger.warning(f"Failed to compute {compute_fn.__name__}: {e}")

    if not all_indices:
        logger.error("No indices computed successfully")
        return None

    from functools import reduce
    combined = reduce(lambda a, b: a.unionByName(b), all_indices)

    logger.info(f"Writing indices to {OUTPUT_INDICES}...")
    combined.write.mode("overwrite").partitionBy("index_name").parquet(OUTPUT_INDICES)

    count = combined.count()
    logger.info(f"Climate indices complete: {count:,} index records")
    return combined


if __name__ == "__main__":
    spark = get_spark_session("Climate-Indices")
    run_climate_indices(spark)
    spark.stop()

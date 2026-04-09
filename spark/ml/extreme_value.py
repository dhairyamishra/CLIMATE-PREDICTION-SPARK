"""
Extreme Value Analysis using GEV/GPD distributions.
Computes return periods (10yr, 25yr, 50yr, 100yr) for temperature
and precipitation extremes per station.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, FEATURES_ROLLING_STATS, HDFS_OUTPUT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_EVS = f"{HDFS_OUTPUT}/extreme-value-stats"

RETURN_PERIODS = [10, 25, 50, 100]

EVS_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("variable", StringType(), False),
    StructField("distribution", StringType(), False),
    StructField("return_period", IntegerType(), False),
    StructField("return_level", DoubleType(), False),
    StructField("lower_ci", DoubleType(), True),
    StructField("upper_ci", DoubleType(), True),
    StructField("shape_param", DoubleType(), True),
    StructField("location_param", DoubleType(), True),
    StructField("scale_param", DoubleType(), True),
    StructField("n_years", IntegerType(), True),
])


def fit_gev_per_station(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Fit GEV distribution to annual block maxima (for tmax, prcp)
    and annual block minima (for tmin) per station.
    """
    from scipy.stats import genextreme

    station_id = pdf["station_id"].iloc[0]
    pdf["obs_date"] = pd.to_datetime(pdf["obs_date"])
    pdf["year"] = pdf["obs_date"].dt.year

    results = []

    for variable in ["tmax", "tmin", "prcp"]:
        if variable not in pdf.columns:
            continue

        series = pdf[["year", variable]].dropna(subset=[variable])
        if len(series) < 365:
            continue

        if variable == "tmin":
            annual_extremes = series.groupby("year")[variable].min()
            annual_extremes = -annual_extremes
        else:
            annual_extremes = series.groupby("year")[variable].max()

        annual_extremes = annual_extremes.dropna()
        if len(annual_extremes) < 10:
            continue

        data = annual_extremes.values

        try:
            shape, loc, scale = genextreme.fit(data)

            for T in RETURN_PERIODS:
                p = 1.0 - 1.0 / T
                return_level = genextreme.ppf(p, shape, loc=loc, scale=scale)

                se = scale / np.sqrt(len(data))
                ci_lower = return_level - 1.96 * se * np.sqrt(np.log(T))
                ci_upper = return_level + 1.96 * se * np.sqrt(np.log(T))

                if variable == "tmin":
                    return_level = -return_level
                    ci_lower, ci_upper = -ci_upper, -ci_lower

                results.append({
                    "station_id": station_id,
                    "variable": variable,
                    "distribution": "gev",
                    "return_period": T,
                    "return_level": round(float(return_level), 2),
                    "lower_ci": round(float(ci_lower), 2),
                    "upper_ci": round(float(ci_upper), 2),
                    "shape_param": round(float(shape), 6),
                    "location_param": round(float(loc), 4),
                    "scale_param": round(float(scale), 4),
                    "n_years": int(len(annual_extremes)),
                })
        except Exception:
            continue

    if not results:
        return pd.DataFrame(columns=EVS_SCHEMA.fieldNames())

    return pd.DataFrame(results)


def run_extreme_value_analysis(spark: SparkSession):
    """Run distributed GEV fitting across all stations."""
    logger.info("=" * 60)
    logger.info("Running Extreme Value Analysis...")
    logger.info("=" * 60)

    df = spark.read.parquet(FEATURES_ROLLING_STATS)
    input_df = df.select("station_id", "obs_date", "tmax", "tmin", "prcp")

    logger.info("Fitting GEV distributions per station...")
    evs = input_df.groupby("station_id").applyInPandas(
        fit_gev_per_station, schema=EVS_SCHEMA
    )

    logger.info(f"Writing extreme value stats to {OUTPUT_EVS}...")
    evs.write.mode("overwrite").partitionBy("variable").parquet(OUTPUT_EVS)

    count = evs.count()
    logger.info(f"Extreme value analysis complete: {count:,} records")
    return evs


if __name__ == "__main__":
    spark = get_spark_session("Extreme-Value-Analysis")
    run_extreme_value_analysis(spark)
    spark.stop()

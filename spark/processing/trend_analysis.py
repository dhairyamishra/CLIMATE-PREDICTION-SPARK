"""
Mann-Kendall trend test and Sen's slope estimation per station per variable.
Tests for statistically significant monotonic trends in climate time series.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType, BooleanType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, FEATURES_ROLLING_STATS, HDFS_OUTPUT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_TRENDS = f"{HDFS_OUTPUT}/trend-analysis"

TREND_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("variable", StringType(), False),
    StructField("period_start", IntegerType(), False),
    StructField("period_end", IntegerType(), False),
    StructField("trend_direction", StringType(), False),
    StructField("sens_slope", DoubleType(), False),
    StructField("p_value", DoubleType(), False),
    StructField("z_statistic", DoubleType(), True),
    StructField("tau", DoubleType(), True),
    StructField("slope_per_decade", DoubleType(), True),
    StructField("ci_lower", DoubleType(), True),
    StructField("ci_upper", DoubleType(), True),
    StructField("significant", BooleanType(), True),
])


def _mann_kendall(x):
    """
    Mann-Kendall trend test. Returns (tau, p_value, z_statistic, S, var_S).
    """
    from scipy.stats import norm

    n = len(x)
    S = 0
    for k in range(n - 1):
        for j in range(k + 1, n):
            diff = x[j] - x[k]
            if diff > 0:
                S += 1
            elif diff < 0:
                S -= 1

    n_pairs = n * (n - 1) / 2
    tau = S / n_pairs if n_pairs > 0 else 0

    var_S = (n * (n - 1) * (2 * n + 5)) / 18.0

    unique, counts = np.unique(x, return_counts=True)
    for t in counts:
        if t > 1:
            var_S -= t * (t - 1) * (2 * t + 5) / 18.0

    if S > 0:
        z = (S - 1) / np.sqrt(var_S) if var_S > 0 else 0
    elif S < 0:
        z = (S + 1) / np.sqrt(var_S) if var_S > 0 else 0
    else:
        z = 0

    p_value = 2 * (1 - norm.cdf(abs(z)))

    return tau, p_value, z, S, var_S


def _sens_slope(x, t):
    """Compute Sen's slope estimator and confidence intervals."""
    from scipy.stats import norm

    n = len(x)
    slopes = []
    for i in range(n):
        for j in range(i + 1, n):
            dt = t[j] - t[i]
            if dt != 0:
                slopes.append((x[j] - x[i]) / dt)

    if not slopes:
        return 0, 0, 0

    slopes = np.array(slopes)
    median_slope = float(np.median(slopes))

    N = len(slopes)
    z_alpha = 1.96
    C_alpha = z_alpha * np.sqrt(N) / 2.0
    idx_lower = int(max(0, (N - C_alpha) / 2))
    idx_upper = int(min(N - 1, (N + C_alpha) / 2))
    sorted_slopes = np.sort(slopes)
    ci_lower = float(sorted_slopes[idx_lower]) if idx_lower < len(sorted_slopes) else median_slope
    ci_upper = float(sorted_slopes[idx_upper]) if idx_upper < len(sorted_slopes) else median_slope

    return median_slope, ci_lower, ci_upper


def compute_trends_per_station(pdf: pd.DataFrame) -> pd.DataFrame:
    """Compute Mann-Kendall + Sen's slope for a single station."""
    station_id = pdf["station_id"].iloc[0]
    pdf["obs_date"] = pd.to_datetime(pdf["obs_date"])
    pdf = pdf.sort_values("obs_date")
    pdf["year"] = pdf["obs_date"].dt.year

    results = []

    for variable in ["tmax", "tmin", "prcp"]:
        if variable not in pdf.columns:
            continue

        annual = pdf.groupby("year")[variable].mean().dropna()
        if len(annual) < 10:
            continue

        years = annual.index.values.astype(float)
        values = annual.values.astype(float)

        try:
            tau, p_value, z_stat, _, _ = _mann_kendall(values)
            sens, ci_lower, ci_upper = _sens_slope(values, years)

            slope_per_decade = sens * 10.0
            significant = p_value < 0.05

            if sens > 0:
                direction = "increasing"
            elif sens < 0:
                direction = "decreasing"
            else:
                direction = "no_trend"

            results.append({
                "station_id": station_id,
                "variable": variable,
                "period_start": int(years[0]),
                "period_end": int(years[-1]),
                "trend_direction": direction,
                "sens_slope": round(float(sens), 6),
                "p_value": round(float(p_value), 6),
                "z_statistic": round(float(z_stat), 4),
                "tau": round(float(tau), 4),
                "slope_per_decade": round(float(slope_per_decade), 4),
                "ci_lower": round(float(ci_lower), 6),
                "ci_upper": round(float(ci_upper), 6),
                "significant": bool(significant),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame(columns=TREND_SCHEMA.fieldNames())

    return pd.DataFrame(results)


def run_trend_analysis(spark: SparkSession):
    """Run distributed Mann-Kendall trend analysis across all stations."""
    logger.info("=" * 60)
    logger.info("Running Mann-Kendall Trend Analysis...")
    logger.info("=" * 60)

    df = spark.read.parquet(FEATURES_ROLLING_STATS)
    input_df = df.select("station_id", "obs_date", "tmax", "tmin", "prcp")

    logger.info("Computing trends per station...")
    trends = input_df.groupby("station_id").applyInPandas(
        compute_trends_per_station, schema=TREND_SCHEMA
    )

    logger.info(f"Writing trend analysis to {OUTPUT_TRENDS}...")
    trends.write.mode("overwrite").partitionBy("variable").parquet(OUTPUT_TRENDS)

    count = trends.count()
    sig_count = trends.filter(F.col("significant") == True).count()
    logger.info(f"Trend analysis complete: {count:,} records ({sig_count:,} significant)")
    return trends


if __name__ == "__main__":
    spark = get_spark_session("Trend-Analysis")
    run_trend_analysis(spark)
    spark.stop()

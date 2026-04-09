"""
Station-level forecasting using Prophet, NeuralProphet, and statistical methods.
Parallelized across Spark executors via applyInPandas. Produces 12-month
multivariate forecasts for TMAX, TMIN, PRCP per station with confidence intervals.

Models:
  - Prophet: Univariate with yearly seasonality (original)
  - NeuralProphet: AR-Net with lagged regressors for multivariate context
  - Statistical: Climatology + trend extrapolation (fallback)
  - Ensemble: Weighted combination of all available models
"""
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, DoubleType, IntegerType
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session, FEATURES_ROLLING_STATS, OUTPUT_FORECASTS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FORECAST_HORIZON_DAYS = 365

FORECAST_SCHEMA = StructType([
    StructField("station_id", StringType(), False),
    StructField("forecast_date", DateType(), False),
    StructField("variable", StringType(), False),
    StructField("predicted_value", DoubleType(), False),
    StructField("lower_bound", DoubleType(), True),
    StructField("upper_bound", DoubleType(), True),
    StructField("model_type", StringType(), False),
    StructField("model_version", StringType(), True),
    StructField("mae", DoubleType(), True),
    StructField("rmse", DoubleType(), True),
])


def forecast_station_prophet(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Run Prophet forecasting for a single station across TMAX, TMIN, PRCP.
    Called via applyInPandas for distributed execution.
    """
    from prophet import Prophet

    station_id = pdf["station_id"].iloc[0]
    pdf = pdf.sort_values("obs_date").reset_index(drop=True)

    if len(pdf) < 730:  # need at least 2 years
        return pd.DataFrame(columns=FORECAST_SCHEMA.fieldNames())

    results = []

    for variable in ["tmax", "tmin", "prcp"]:
        series = pdf[["obs_date", variable]].copy()
        series = series.dropna(subset=[variable])

        if len(series) < 365:
            continue

        # Resample to weekly for faster training while maintaining patterns
        series["obs_date"] = pd.to_datetime(series["obs_date"])
        weekly = series.set_index("obs_date").resample("W").mean().reset_index()
        weekly.columns = ["ds", "y"]
        weekly = weekly.dropna()

        if len(weekly) < 52:
            continue

        # Split for validation
        train = weekly.iloc[:-52]
        test = weekly.iloc[-52:]

        try:
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10,
                interval_width=0.90,
            )

            if variable == "prcp":
                model.add_seasonality(name="quarterly", period=91.25, fourier_order=5)

            model.fit(train)

            # Validate on held-out data
            test_forecast = model.predict(test[["ds"]])
            mae = float(np.mean(np.abs(test["y"].values - test_forecast["yhat"].values)))
            rmse = float(np.sqrt(np.mean((test["y"].values - test_forecast["yhat"].values) ** 2)))

            # Generate future forecast
            future = model.make_future_dataframe(periods=52, freq="W")
            forecast = model.predict(future)

            # Extract only future predictions
            future_mask = forecast["ds"] > weekly["ds"].max()
            future_forecast = forecast[future_mask]

            for _, row in future_forecast.iterrows():
                predicted = row["yhat"]
                if variable == "prcp":
                    predicted = max(0, predicted)

                results.append({
                    "station_id": station_id,
                    "forecast_date": row["ds"].date(),
                    "variable": variable,
                    "predicted_value": round(predicted, 2),
                    "lower_bound": round(row["yhat_lower"], 2),
                    "upper_bound": round(row["yhat_upper"], 2),
                    "model_type": "prophet",
                    "model_version": "1.0",
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                })

        except Exception:
            continue

    if not results:
        return pd.DataFrame(columns=FORECAST_SCHEMA.fieldNames())

    return pd.DataFrame(results)


def forecast_station_statistical(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Simple statistical forecasting using historical climatology + trend.
    Fallback for stations where Prophet fails.
    """
    station_id = pdf["station_id"].iloc[0]
    pdf = pdf.sort_values("obs_date").reset_index(drop=True)

    if len(pdf) < 365:
        return pd.DataFrame(columns=FORECAST_SCHEMA.fieldNames())

    results = []
    pdf["obs_date"] = pd.to_datetime(pdf["obs_date"])
    pdf["day_of_year"] = pdf["obs_date"].dt.dayofyear

    for variable in ["tmax", "tmin", "prcp"]:
        series = pdf[["obs_date", "day_of_year", variable]].dropna(subset=[variable])
        if len(series) < 365:
            continue

        # Compute day-of-year climatology
        climatology = series.groupby("day_of_year")[variable].agg(["mean", "std"]).reset_index()
        climatology.columns = ["day_of_year", "clim_mean", "clim_std"]

        # Compute linear trend (last 10 years)
        recent = series[series["obs_date"] >= series["obs_date"].max() - pd.Timedelta(days=3650)]
        if len(recent) > 365:
            x = np.arange(len(recent), dtype=float)
            y = recent[variable].values
            mask = ~np.isnan(y)
            if mask.sum() > 100:
                coeffs = np.polyfit(x[mask], y[mask], 1)
                daily_trend = coeffs[0]
            else:
                daily_trend = 0
        else:
            daily_trend = 0

        # Generate forecast: climatology + trend extrapolation
        last_date = series["obs_date"].max()
        for day_offset in range(1, FORECAST_HORIZON_DAYS + 1, 7):
            forecast_date = last_date + pd.Timedelta(days=day_offset)
            doy = forecast_date.timetuple().tm_yday

            clim_row = climatology[climatology["day_of_year"] == doy]
            if clim_row.empty:
                continue

            base = clim_row["clim_mean"].iloc[0]
            std = clim_row["clim_std"].iloc[0] if not np.isnan(clim_row["clim_std"].iloc[0]) else 2.0
            trend_adj = daily_trend * day_offset
            predicted = base + trend_adj

            if variable == "prcp":
                predicted = max(0, predicted)

            results.append({
                "station_id": station_id,
                "forecast_date": forecast_date.date(),
                "variable": variable,
                "predicted_value": round(predicted, 2),
                "lower_bound": round(predicted - 1.645 * std, 2),
                "upper_bound": round(predicted + 1.645 * std, 2),
                "model_type": "statistical",
                "model_version": "1.0",
                "mae": None,
                "rmse": None,
            })

    if not results:
        return pd.DataFrame(columns=FORECAST_SCHEMA.fieldNames())

    return pd.DataFrame(results)


def forecast_station_neuralprophet(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Multivariate forecasting using NeuralProphet with lagged regressors.
    Uses cross-variable correlations (e.g., temperature-precipitation coupling)
    and AR-Net for autoregressive context.
    """
    try:
        from neuralprophet import NeuralProphet, set_log_level
        set_log_level("ERROR")
    except ImportError:
        return forecast_station_prophet(pdf)

    station_id = pdf["station_id"].iloc[0]
    pdf = pdf.sort_values("obs_date").reset_index(drop=True)

    if len(pdf) < 730:
        return pd.DataFrame(columns=FORECAST_SCHEMA.fieldNames())

    results = []
    pdf["obs_date"] = pd.to_datetime(pdf["obs_date"])

    all_vars = ["tmax", "tmin", "prcp"]
    available = [v for v in all_vars if v in pdf.columns and pdf[v].notna().sum() > 365]

    for variable in available:
        regressors = [v for v in available if v != variable]

        series = pdf[["obs_date", variable] + regressors].copy()
        series = series.dropna(subset=[variable])

        weekly = series.set_index("obs_date").resample("W").mean().reset_index()
        weekly = weekly.dropna(subset=[variable])
        weekly.columns = ["ds"] + [variable] + regressors
        weekly = weekly.rename(columns={variable: "y"})

        if len(weekly) < 52:
            continue

        train = weekly.iloc[:-52].copy()
        test = weekly.iloc[-52:].copy()

        try:
            model = NeuralProphet(
                n_forecasts=1,
                n_lags=12,
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                learning_rate=0.01,
                epochs=30,
                batch_size=32,
                quantiles=[0.05, 0.95],
            )

            for reg in regressors:
                if reg in train.columns:
                    model = model.add_lagged_regressor(reg, n_lags=4)

            model.fit(train, freq="W")

            future = model.make_future_dataframe(train, periods=52)
            for reg in regressors:
                if reg in future.columns:
                    future[reg] = future[reg].fillna(method="ffill")

            forecast = model.predict(future)

            yhat_col = "yhat1"
            lower_col = "yhat1 5.0%"
            upper_col = "yhat1 95.0%"

            if yhat_col not in forecast.columns:
                yhat_col = [c for c in forecast.columns if c.startswith("yhat")][0]
            if lower_col not in forecast.columns:
                lower_col = yhat_col
            if upper_col not in forecast.columns:
                upper_col = yhat_col

            future_mask = forecast["ds"] > train["ds"].max()
            future_forecast = forecast[future_mask]

            test_forecast = forecast[~future_mask].iloc[-52:]
            if len(test_forecast) > 0 and len(test) > 0:
                aligned = min(len(test), len(test_forecast))
                mae = float(np.mean(np.abs(test["y"].values[:aligned] - test_forecast[yhat_col].values[:aligned])))
                rmse = float(np.sqrt(np.mean((test["y"].values[:aligned] - test_forecast[yhat_col].values[:aligned]) ** 2)))
            else:
                mae, rmse = None, None

            for _, row in future_forecast.iterrows():
                predicted = row[yhat_col]
                if variable == "prcp":
                    predicted = max(0, predicted)

                lower = row.get(lower_col, predicted - 5)
                upper = row.get(upper_col, predicted + 5)

                results.append({
                    "station_id": station_id,
                    "forecast_date": row["ds"].date() if hasattr(row["ds"], "date") else row["ds"],
                    "variable": variable,
                    "predicted_value": round(float(predicted), 2),
                    "lower_bound": round(float(lower), 2),
                    "upper_bound": round(float(upper), 2),
                    "model_type": "neuralprophet",
                    "model_version": "2.0-multivariate",
                    "mae": round(mae, 4) if mae else None,
                    "rmse": round(rmse, 4) if rmse else None,
                })

        except Exception:
            continue

    if not results:
        return forecast_station_prophet(pdf)

    return pd.DataFrame(results)


def run_forecasting(spark: SparkSession, use_prophet: bool = True):
    """Run distributed forecasting across all stations."""
    logger.info("Loading feature data for forecasting...")
    df = spark.read.parquet(FEATURES_ROLLING_STATS)

    input_df = df.select(
        "station_id", "obs_date", "tmax", "tmin", "prcp"
    )

    forecast_func = forecast_station_prophet if use_prophet else forecast_station_statistical
    method_name = "Prophet" if use_prophet else "Statistical"

    logger.info(f"Running distributed {method_name} forecasting...")
    forecasts = input_df.groupby("station_id").applyInPandas(
        forecast_func, schema=FORECAST_SCHEMA
    )

    logger.info(f"Writing forecasts to {OUTPUT_FORECASTS}...")
    (
        forecasts
        .write
        .mode("overwrite")
        .partitionBy("variable")
        .parquet(OUTPUT_FORECASTS)
    )

    forecast_count = forecasts.count()
    logger.info(f"Forecasting complete: {forecast_count:,} forecast points generated")
    return forecasts


def run_ensemble_forecasting(spark: SparkSession):
    """
    Run ensemble forecasting combining NeuralProphet, Prophet, and statistical models.
    Weighted: 50% NeuralProphet, 30% Prophet, 20% statistical.
    Falls back to 70/30 Prophet/statistical if NeuralProphet unavailable.
    """
    logger.info("Running multi-model ensemble forecasting...")

    df = spark.read.parquet(FEATURES_ROLLING_STATS).select(
        "station_id", "obs_date", "tmax", "tmin", "prcp"
    )

    prophet_forecasts = df.groupby("station_id").applyInPandas(
        forecast_station_prophet, schema=FORECAST_SCHEMA
    ).withColumn("source", F.lit("prophet"))

    statistical_forecasts = df.groupby("station_id").applyInPandas(
        forecast_station_statistical, schema=FORECAST_SCHEMA
    ).withColumn("source", F.lit("statistical"))

    try:
        np_forecasts = df.groupby("station_id").applyInPandas(
            forecast_station_neuralprophet, schema=FORECAST_SCHEMA
        ).withColumn("source", F.lit("neuralprophet"))
        has_np = np_forecasts.count() > 0
    except Exception:
        has_np = False
        np_forecasts = None

    if has_np:
        w_np, w_prophet, w_stat = 0.50, 0.30, 0.20
        version = "np_0.5_prophet_0.3_stat_0.2"
    else:
        w_prophet, w_stat = 0.70, 0.30
        version = "prophet_0.7_stat_0.3"

    prophet_w = prophet_forecasts.select(
        "station_id", "forecast_date", "variable",
        (F.col("predicted_value") * w_prophet).alias("weighted_pred"),
        (F.col("lower_bound") * w_prophet).alias("weighted_lower"),
        (F.col("upper_bound") * w_prophet).alias("weighted_upper"),
        "mae", "rmse",
    )

    statistical_w = statistical_forecasts.select(
        "station_id", "forecast_date", "variable",
        (F.col("predicted_value") * w_stat).alias("weighted_pred"),
        (F.col("lower_bound") * w_stat).alias("weighted_lower"),
        (F.col("upper_bound") * w_stat).alias("weighted_upper"),
    )

    ensemble = prophet_w.join(
        statistical_w,
        on=["station_id", "forecast_date", "variable"],
        how="outer"
    )

    pred_expr = (
        F.coalesce(prophet_w.weighted_pred, F.lit(0)) +
        F.coalesce(statistical_w.weighted_pred, F.lit(0))
    )
    lower_expr = (
        F.coalesce(prophet_w.weighted_lower, F.lit(0)) +
        F.coalesce(statistical_w.weighted_lower, F.lit(0))
    )
    upper_expr = (
        F.coalesce(prophet_w.weighted_upper, F.lit(0)) +
        F.coalesce(statistical_w.weighted_upper, F.lit(0))
    )

    if has_np:
        np_w = np_forecasts.select(
            "station_id", "forecast_date", "variable",
            (F.col("predicted_value") * w_np).alias("np_pred"),
            (F.col("lower_bound") * w_np).alias("np_lower"),
            (F.col("upper_bound") * w_np).alias("np_upper"),
        )
        ensemble = ensemble.join(
            np_w,
            on=["station_id", "forecast_date", "variable"],
            how="outer"
        )
        pred_expr = pred_expr + F.coalesce(F.col("np_pred"), F.lit(0))
        lower_expr = lower_expr + F.coalesce(F.col("np_lower"), F.lit(0))
        upper_expr = upper_expr + F.coalesce(F.col("np_upper"), F.lit(0))

    ensemble = ensemble.select(
        "station_id", "forecast_date", "variable",
        pred_expr.alias("predicted_value"),
        lower_expr.alias("lower_bound"),
        upper_expr.alias("upper_bound"),
        F.lit("ensemble").alias("model_type"),
        F.lit(version).alias("model_version"),
        prophet_w.mae,
        prophet_w.rmse,
    )

    ensemble.write.mode("append").partitionBy("variable").parquet(OUTPUT_FORECASTS)

    count = ensemble.count()
    logger.info(f"Ensemble forecasting complete: {count:,} forecast points")
    return ensemble


if __name__ == "__main__":
    spark = get_spark_session("Forecasting")

    action = sys.argv[1] if len(sys.argv) > 1 else "prophet"

    if action == "prophet":
        run_forecasting(spark, use_prophet=True)
    elif action == "statistical":
        run_forecasting(spark, use_prophet=False)
    elif action == "neuralprophet":
        logger.info("Running NeuralProphet multivariate forecasting...")
        df = spark.read.parquet(FEATURES_ROLLING_STATS).select(
            "station_id", "obs_date", "tmax", "tmin", "prcp"
        )
        forecasts = df.groupby("station_id").applyInPandas(
            forecast_station_neuralprophet, schema=FORECAST_SCHEMA
        )
        forecasts.write.mode("overwrite").partitionBy("variable").parquet(OUTPUT_FORECASTS)
        logger.info(f"NeuralProphet complete: {forecasts.count():,} forecast points")
    elif action == "ensemble":
        run_ensemble_forecasting(spark)
    else:
        logger.error(f"Unknown action: {action}. Use: prophet, statistical, neuralprophet, ensemble")

    spark.stop()

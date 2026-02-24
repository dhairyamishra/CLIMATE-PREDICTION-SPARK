"""
Export Spark processing results to PostGIS for the FastAPI backend.
Loads stations, observations (with rolling stats), anomalies, forecasts,
tiles, and monthly summaries into the PostgreSQL/PostGIS database.
"""
import os
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.spark_config import (
    get_spark_session,
    PROCESSED_STATION_METADATA, FEATURES_ROLLING_STATS,
    OUTPUT_ANOMALIES, OUTPUT_FORECASTS, OUTPUT_TILES, OUTPUT_SUMMARIES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JDBC_URL = "jdbc:postgresql://{host}:{port}/{db}".format(
    host=os.getenv("POSTGRES_HOST", "postgis"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    db=os.getenv("POSTGRES_DB", "climate_db"),
)
JDBC_PROPS = {
    "user": os.getenv("POSTGRES_USER", "climate"),
    "password": os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    "driver": "org.postgresql.Driver",
}


def export_stations(spark: SparkSession):
    """Export station metadata to PostGIS."""
    logger.info("Exporting station metadata to PostGIS...")

    stations = spark.read.parquet(PROCESSED_STATION_METADATA)

    # Add PostGIS geometry column as WKT
    stations_out = stations.select(
        F.col("station_id").alias("id"),
        "name", "latitude", "longitude", "elevation", "country", "state", "geohash",
        F.lit(None).cast("int").alias("first_year"),
        F.lit(None).cast("int").alias("last_year"),
        F.lit(0).cast("long").alias("record_count"),
        F.expr("ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)").alias("geom"),
    )

    # Use raw SQL insert since we need PostGIS geometry
    pdf = stations.toPandas()

    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgis"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "climate_db"),
        user=os.getenv("POSTGRES_USER", "climate"),
        password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    )
    cur = conn.cursor()

    # Truncate and reload
    cur.execute("TRUNCATE TABLE stations CASCADE")

    for _, row in pdf.iterrows():
        cur.execute("""
            INSERT INTO stations (id, name, latitude, longitude, elevation, country, state, geohash, geom, first_year, last_year, record_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, 0)
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude,
                elevation=EXCLUDED.elevation, country=EXCLUDED.country, geohash=EXCLUDED.geohash,
                geom=EXCLUDED.geom
        """, (
            row["station_id"], row.get("name", ""), row["latitude"], row["longitude"],
            row.get("elevation"), row.get("country", ""), row.get("state", ""),
            row["geohash"], row["longitude"], row["latitude"],
            row.get("first_year"), row.get("last_year"),
        ))

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Exported {len(pdf)} stations to PostGIS")


def export_observations_sample(spark: SparkSession, sample_fraction: float = 0.01):
    """Export a sample of observations with rolling stats to PostGIS."""
    logger.info(f"Exporting observations sample ({sample_fraction*100}%) to PostGIS...")

    df = spark.read.parquet(FEATURES_ROLLING_STATS)

    # Sample to keep PostGIS manageable
    sample = df.sample(fraction=sample_fraction, seed=42)

    pdf = sample.select(
        "station_id", "obs_date", "tmax", "tmin", "prcp",
        F.col("snow").alias("snow"),
        F.col("snwd").alias("snwd"),
        F.coalesce(F.col("tavg"), (F.col("tmax") + F.col("tmin")) / 2).alias("tavg"),
        F.col("tmax_rolling_30d_mean").alias("tmax_rolling_30d"),
        F.col("tmin_rolling_30d_mean").alias("tmin_rolling_30d"),
        F.col("prcp_rolling_30d_mean").alias("prcp_rolling_30d"),
        F.col("tmax_rolling_365d_mean").alias("tmax_rolling_365d"),
        F.col("tmin_rolling_365d_mean").alias("tmin_rolling_365d"),
        F.col("prcp_rolling_365d_mean").alias("prcp_rolling_365d"),
        F.col("tmax_rolling_30d_std").alias("tmax_stddev_30d"),
        F.col("tmin_rolling_30d_std").alias("tmin_stddev_30d"),
        F.col("prcp_rolling_30d_std").alias("prcp_stddev_30d"),
    ).toPandas()

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgis"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "climate_db"),
        user=os.getenv("POSTGRES_USER", "climate"),
        password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    )
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE observations")

    cols = [
        "station_id", "obs_date", "tmax", "tmin", "prcp", "snow", "snwd", "tavg",
        "tmax_rolling_30d", "tmin_rolling_30d", "prcp_rolling_30d",
        "tmax_rolling_365d", "tmin_rolling_365d", "prcp_rolling_365d",
        "tmax_stddev_30d", "tmin_stddev_30d", "prcp_stddev_30d",
    ]

    values = []
    for _, row in pdf.iterrows():
        values.append(tuple(
            None if (hasattr(v, '__float__') and (v != v)) else v
            for v in [row[c] for c in cols]
        ))

    if values:
        placeholders = ",".join(["%s"] * len(cols))
        col_names = ",".join(cols)
        execute_values(
            cur,
            f"INSERT INTO observations ({col_names}) VALUES %s",
            values,
            template=f"({placeholders})",
            page_size=5000,
        )

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Exported {len(values)} observation records to PostGIS")


def export_anomalies(spark: SparkSession):
    """Export detected anomalies to PostGIS."""
    logger.info("Exporting anomalies to PostGIS...")

    df = spark.read.parquet(OUTPUT_ANOMALIES)
    pdf = df.toPandas()

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgis"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "climate_db"),
        user=os.getenv("POSTGRES_USER", "climate"),
        password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    )
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE anomalies")

    values = []
    for _, row in pdf.iterrows():
        lat = row.get("latitude", 0) or 0
        lon = row.get("longitude", 0) or 0
        values.append((
            row["station_id"], row["obs_date"], row["anomaly_type"],
            row["severity"], row.get("duration_days", 1),
            row.get("temp_deviation"), row.get("precip_deviation"),
            row.get("description", ""), lon, lat,
        ))

    if values:
        execute_values(
            cur,
            """INSERT INTO anomalies
                (station_id, anomaly_date, anomaly_type, severity, duration_days,
                 temp_deviation, precip_deviation, description, geom)
               VALUES %s""",
            values,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
            page_size=5000,
        )

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Exported {len(values)} anomalies to PostGIS")


def export_forecasts(spark: SparkSession):
    """Export forecast results to PostGIS."""
    logger.info("Exporting forecasts to PostGIS...")

    df = spark.read.parquet(OUTPUT_FORECASTS)
    pdf = df.toPandas()

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgis"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "climate_db"),
        user=os.getenv("POSTGRES_USER", "climate"),
        password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    )
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE forecasts")

    values = []
    for _, row in pdf.iterrows():
        values.append((
            row["station_id"], row["forecast_date"], row["variable"],
            row["predicted_value"], row.get("lower_bound"), row.get("upper_bound"),
            row["model_type"], row.get("model_version"),
            row.get("mae"), row.get("rmse"),
        ))

    if values:
        execute_values(
            cur,
            """INSERT INTO forecasts
                (station_id, forecast_date, variable, predicted_value,
                 lower_bound, upper_bound, model_type, model_version, mae, rmse)
               VALUES %s""",
            values,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            page_size=5000,
        )

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Exported {len(values)} forecast records to PostGIS")


def export_tiles(spark: SparkSession):
    """Export pre-aggregated anomaly tiles to PostGIS."""
    logger.info("Exporting anomaly tiles to PostGIS...")

    df = spark.read.parquet(OUTPUT_TILES)
    pdf = df.toPandas()

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgis"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "climate_db"),
        user=os.getenv("POSTGRES_USER", "climate"),
        password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    )
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE anomaly_tiles")

    values = []
    for _, row in pdf.iterrows():
        lat = row.get("center_lat", 0) or 0
        lon = row.get("center_lon", 0) or 0
        # Construct tile_date from year + month
        tile_date = f"{int(row['year'])}-{int(row.get('month', 1)):02d}-01"
        values.append((
            row["geohash_prefix"], tile_date,
            int(row.get("anomaly_count", 0)),
            row.get("avg_severity", 0),
            row.get("dominant_type", ""),
            int(row.get("heatwave_count", 0)),
            int(row.get("cold_snap_count", 0)),
            int(row.get("precip_extreme_count", 0)),
            lat, lon, lon, lat,
        ))

    if values:
        execute_values(
            cur,
            """INSERT INTO anomaly_tiles
                (geohash, tile_date, anomaly_count, avg_severity, dominant_type,
                 heatwave_count, cold_snap_count, precip_extreme_count,
                 center_lat, center_lon, geom)
               VALUES %s""",
            values,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
            page_size=5000,
        )

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Exported {len(values)} tile records to PostGIS")


def export_monthly_summary(spark: SparkSession):
    """Export monthly anomaly summaries to PostGIS."""
    logger.info("Exporting monthly summaries to PostGIS...")

    df = spark.read.parquet(OUTPUT_SUMMARIES)
    pdf = df.toPandas()

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgis"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "climate_db"),
        user=os.getenv("POSTGRES_USER", "climate"),
        password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
    )
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE monthly_summary")

    values = []
    for _, row in pdf.iterrows():
        values.append((
            int(row["year"]), int(row["month"]),
            int(row.get("total_anomalies", 0)),
            int(row.get("heatwave_count", 0)),
            int(row.get("cold_snap_count", 0)),
            int(row.get("precip_extreme_count", 0)),
            row.get("avg_severity"),
            None,  # top_region
            None,  # global_temp_anomaly
        ))

    if values:
        execute_values(
            cur,
            """INSERT INTO monthly_summary
                (year, month, total_anomalies, heatwave_count, cold_snap_count,
                 precip_extreme_count, avg_severity, top_region, global_temp_anomaly)
               VALUES %s""",
            values,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            page_size=1000,
        )

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Exported {len(values)} monthly summary records to PostGIS")


def export_all(spark: SparkSession):
    """Run full export pipeline."""
    logger.info("=" * 60)
    logger.info("Starting full PostGIS export pipeline...")
    logger.info("=" * 60)

    export_stations(spark)
    export_observations_sample(spark, sample_fraction=0.02)
    export_anomalies(spark)
    export_tiles(spark)
    export_monthly_summary(spark)

    try:
        export_forecasts(spark)
    except Exception as e:
        logger.warning(f"Forecast export skipped: {e}")

    logger.info("=" * 60)
    logger.info("PostGIS export complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    spark = get_spark_session("PostGIS-Export")

    action = sys.argv[1] if len(sys.argv) > 1 else "all"
    actions = {
        "all": lambda: export_all(spark),
        "stations": lambda: export_stations(spark),
        "observations": lambda: export_observations_sample(spark),
        "anomalies": lambda: export_anomalies(spark),
        "forecasts": lambda: export_forecasts(spark),
        "tiles": lambda: export_tiles(spark),
        "summary": lambda: export_monthly_summary(spark),
    }

    if action in actions:
        actions[action]()
    else:
        logger.error(f"Unknown action: {action}. Use: {', '.join(actions.keys())}")

    spark.stop()

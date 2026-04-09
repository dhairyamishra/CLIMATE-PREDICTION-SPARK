"""
Real-time data ingestion pipeline for Climate Anomaly Engine.
Scheduled polling of NOAA CDO and Copernicus CDS APIs for new observations.

Run as a cron job or long-running process:
    python scripts/realtime_pipeline.py          # single run
    python scripts/realtime_pipeline.py --watch   # continuous polling
"""
import os
import sys
import time
import json
import logging
import hashlib
from datetime import date, datetime, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("realtime-pipeline")

DB_CONFIG = dict(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    dbname=os.getenv("POSTGRES_DB", "climate_db"),
    user=os.getenv("POSTGRES_USER", "climate"),
    password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
)

NOAA_API_TOKEN = os.getenv("NOAA_API_TOKEN", "")
NOAA_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2"

CDS_API_URL = os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api/v2")
CDS_API_KEY = os.getenv("CDS_API_KEY", "")

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL", "3600"))


def get_db_connection():
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def fetch_noaa_recent_observations(station_ids: list, start_date: str, end_date: str) -> list:
    """
    Fetch recent observations from the NOAA Climate Data Online API.
    Returns parsed observation records.
    """
    if not NOAA_API_TOKEN:
        logger.warning("NOAA_API_TOKEN not set, skipping NOAA ingestion")
        return []

    import httpx

    records = []
    headers = {"token": NOAA_API_TOKEN}

    for station_id in station_ids[:10]:
        try:
            response = httpx.get(
                f"{NOAA_BASE_URL}/data",
                params={
                    "datasetid": "GHCND",
                    "stationid": f"GHCND:{station_id}",
                    "startdate": start_date,
                    "enddate": end_date,
                    "datatypeid": "TMAX,TMIN,PRCP",
                    "units": "metric",
                    "limit": 1000,
                },
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                for result in data.get("results", []):
                    records.append({
                        "station_id": station_id,
                        "obs_date": result["date"][:10],
                        "element": result["datatype"],
                        "value": result["value"],
                    })
            elif response.status_code == 429:
                logger.warning("NOAA rate limit hit, pausing...")
                time.sleep(5)
            else:
                logger.debug(f"NOAA returned {response.status_code} for {station_id}")

        except Exception as e:
            logger.error(f"Error fetching NOAA data for {station_id}: {e}")

    return records


def pivot_observations(records: list) -> list:
    """Pivot NOAA long-format records to wide-format rows."""
    by_key = {}
    for r in records:
        key = (r["station_id"], r["obs_date"])
        if key not in by_key:
            by_key[key] = {"station_id": r["station_id"], "obs_date": r["obs_date"]}
        element = r["element"].lower()
        by_key[key][element] = r["value"]

    return list(by_key.values())


def insert_observations(conn, observations: list) -> int:
    """Insert new observations into PostGIS, skipping duplicates."""
    if not observations:
        return 0

    from psycopg2.extras import execute_values

    cur = conn.cursor()
    inserted = 0

    for obs in observations:
        try:
            cur.execute("""
                INSERT INTO observations (station_id, obs_date, tmax, tmin, prcp)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                obs["station_id"], obs["obs_date"],
                obs.get("tmax"), obs.get("tmin"), obs.get("prcp"),
            ))
            inserted += cur.rowcount
        except Exception as e:
            logger.warning(f"Failed to insert observation: {e}")
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    return inserted


def run_incremental_anomaly_detection(conn, station_ids: list):
    """
    Lightweight anomaly check on recent observations.
    Flags observations with extreme z-scores without full Spark pipeline.
    """
    cur = conn.cursor()

    for station_id in station_ids:
        try:
            cur.execute("""
                WITH recent AS (
                    SELECT obs_date, tmax, tmin, prcp
                    FROM observations
                    WHERE station_id = %s
                    ORDER BY obs_date DESC
                    LIMIT 365
                ),
                stats AS (
                    SELECT
                        AVG(tmax) as tmax_mean, STDDEV(tmax) as tmax_std,
                        AVG(tmin) as tmin_mean, STDDEV(tmin) as tmin_std,
                        AVG(prcp) as prcp_mean, STDDEV(prcp) as prcp_std
                    FROM recent
                )
                SELECT r.obs_date, r.tmax, r.tmin, r.prcp,
                       s.tmax_mean, s.tmax_std, s.tmin_mean, s.tmin_std,
                       s.prcp_mean, s.prcp_std
                FROM recent r, stats s
                WHERE r.obs_date = (SELECT MAX(obs_date) FROM recent)
            """, (station_id,))

            row = cur.fetchone()
            if not row:
                continue

            obs_date, tmax, tmin, prcp = row[0], row[1], row[2], row[3]
            tmax_mean, tmax_std = row[4], row[5]
            tmin_mean, tmin_std = row[6], row[7]
            prcp_mean, prcp_std = row[8], row[9]

            anomaly_type = None
            severity = 0
            temp_dev = 0

            if tmax and tmax_std and tmax_std > 0:
                z = (tmax - tmax_mean) / tmax_std
                if z > 2.5:
                    anomaly_type = "heatwave"
                    severity = min(1.0, z / 5.0)
                    temp_dev = z

            if not anomaly_type and tmin and tmin_std and tmin_std > 0:
                z = (tmin - tmin_mean) / tmin_std
                if z < -2.5:
                    anomaly_type = "cold_snap"
                    severity = min(1.0, abs(z) / 5.0)
                    temp_dev = z

            if not anomaly_type and prcp and prcp_std and prcp_std > 0:
                z = (prcp - prcp_mean) / prcp_std
                if z > 2.5:
                    anomaly_type = "precip_extreme"
                    severity = min(1.0, z / 5.0)

            if anomaly_type:
                cur.execute("""
                    SELECT latitude, longitude FROM stations WHERE id = %s
                """, (station_id,))
                loc = cur.fetchone()
                if loc:
                    cur.execute("""
                        INSERT INTO anomalies
                            (station_id, anomaly_date, anomaly_type, severity,
                             duration_days, temp_deviation, description, geom)
                        VALUES (%s, %s, %s, %s, 1, %s, %s,
                                ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        ON CONFLICT DO NOTHING
                    """, (
                        station_id, obs_date, anomaly_type, round(severity, 3),
                        round(temp_dev, 2) if temp_dev else None,
                        f"Real-time {anomaly_type} detection (z={abs(temp_dev):.1f}σ)",
                        loc[1], loc[0],
                    ))

        except Exception as e:
            logger.warning(f"Anomaly check failed for {station_id}: {e}")

    conn.commit()
    cur.close()


def get_active_stations(conn) -> list:
    """Get list of active station IDs from the database."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM stations ORDER BY id LIMIT 100")
    stations = [row[0] for row in cur.fetchall()]
    cur.close()
    return stations


def run_pipeline_cycle():
    """Execute one cycle of the real-time pipeline."""
    logger.info("=" * 50)
    logger.info("Starting real-time pipeline cycle")
    logger.info("=" * 50)

    conn = get_db_connection()

    try:
        stations = get_active_stations(conn)
        if not stations:
            logger.warning("No stations found in database")
            return

        logger.info(f"Processing {len(stations)} stations")

        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=7)).isoformat()

        records = fetch_noaa_recent_observations(stations, start_date, end_date)
        logger.info(f"Fetched {len(records)} raw records from NOAA")

        observations = pivot_observations(records)
        inserted = insert_observations(conn, observations)
        logger.info(f"Inserted {inserted} new observations")

        if inserted > 0:
            updated_stations = list(set(obs["station_id"] for obs in observations))
            run_incremental_anomaly_detection(conn, updated_stations)
            logger.info("Incremental anomaly detection complete")

    except Exception as e:
        logger.error(f"Pipeline cycle failed: {e}")
    finally:
        conn.close()

    logger.info("Pipeline cycle complete")


def main():
    watch = "--watch" in sys.argv

    if watch:
        logger.info(f"Starting continuous pipeline (interval: {POLL_INTERVAL_SECONDS}s)")
        while True:
            try:
                run_pipeline_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
            logger.info(f"Sleeping {POLL_INTERVAL_SECONDS}s until next cycle...")
            time.sleep(POLL_INTERVAL_SECONDS)
    else:
        run_pipeline_cycle()


if __name__ == "__main__":
    main()

"""
Lightweight database seeder for local development.
Inserts a small dataset directly into PostGIS — no Spark or HDFS required.

Usage:
    python scripts/seed_local_db.py                  # uses defaults
    POSTGRES_HOST=localhost python scripts/seed_local_db.py
"""

import hashlib
import math
import os
import random
import sys
from datetime import date, timedelta

DB_CONFIG = dict(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    dbname=os.getenv("POSTGRES_DB", "climate_db"),
    user=os.getenv("POSTGRES_USER", "climate"),
    password=os.getenv("POSTGRES_PASSWORD", "climate_secret"),
)

# ---------------------------------------------------------------------------
# Geohash (minimal pure-python impl so we don't need the C extension here)
# ---------------------------------------------------------------------------
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def _encode_geohash(lat: float, lon: float, precision: int = 7) -> str:
    lat_range, lon_range = (-90.0, 90.0), (-180.0, 180.0)
    bits = [16, 8, 4, 2, 1]
    ch, bit, is_lon = 0, 0, True
    geohash = []
    while len(geohash) < precision:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                ch |= bits[bit]
                lon_range = (mid, lon_range[1])
            else:
                lon_range = (lon_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                ch |= bits[bit]
                lat_range = (mid, lat_range[1])
            else:
                lat_range = (lat_range[0], mid)
        is_lon = not is_lon
        if bit < 4:
            bit += 1
        else:
            geohash.append(_BASE32[ch])
            ch, bit = 0, 0
    return "".join(geohash)


# ---------------------------------------------------------------------------
# Station data — 20 real-ish weather stations across the globe
# ---------------------------------------------------------------------------
STATIONS = [
    ("USW00094728", "NEW YORK CENTRAL PARK", 40.779, -73.969, 47.5, "US", "NY"),
    ("USW00023174", "LOS ANGELES INTL AP", 33.938, -118.389, 30.0, "US", "CA"),
    ("USW00014739", "CHICAGO OHARE INTL AP", 41.995, -87.934, 205.0, "US", "IL"),
    ("USW00012960", "MIAMI INTL AP", 25.791, -80.316, 4.0, "US", "FL"),
    ("USW00024233", "SEATTLE TACOMA INTL", 47.449, -122.314, 122.0, "US", "WA"),
    ("CA001108395", "TORONTO PEARSON", 43.677, -79.631, 173.0, "CA", "ON"),
    ("UKE00105620", "LONDON HEATHROW", 51.479, -0.449, 25.0, "GB", ""),
    ("FRE00104898", "PARIS ORLY", 48.716, 2.384, 89.0, "FR", ""),
    ("GME00111445", "BERLIN TEMPELHOF", 52.473, 13.402, 48.0, "DE", ""),
    ("JA000047662", "TOKYO", 35.694, 139.751, 6.0, "JP", ""),
    ("ASN00066062", "SYDNEY OBSERVATORY", -33.859, 151.205, 39.0, "AU", ""),
    ("IN021060100", "NEW DELHI SAFDARJUNG", 28.585, 77.206, 216.0, "IN", ""),
    ("BR000083743", "SAO PAULO", -23.617, -46.617, 802.0, "BR", ""),
    ("SF000688160", "CAPE TOWN", -33.964, 18.602, 42.0, "ZA", ""),
    ("RSM00027612", "MOSCOW", 55.834, 37.616, 156.0, "RU", ""),
    ("CHM00058362", "SHANGHAI", 31.398, 121.453, 4.0, "CN", ""),
    ("MXN00076680", "MEXICO CITY", 19.432, -99.133, 2240.0, "MX", ""),
    ("EGE00130520", "CAIRO", 30.082, 31.291, 74.0, "EG", ""),
    ("NGM00065201", "LAGOS", 6.577, 3.321, 11.0, "NG", ""),
    ("KEM00063740", "NAIROBI", -1.319, 36.928, 1624.0, "KE", ""),
]

ANOMALY_TYPES = ["heatwave", "cold_snap", "precip_extreme"]

ANOMALY_DESCRIPTIONS = {
    "heatwave": [
        "Prolonged extreme heat event",
        "Temperature exceeding 99th percentile",
        "Multi-day heat dome event",
    ],
    "cold_snap": [
        "Sudden temperature drop below 1st percentile",
        "Polar vortex intrusion",
        "Record-breaking cold outbreak",
    ],
    "precip_extreme": [
        "Heavy rainfall exceeding 95th percentile",
        "Flash flood conditions observed",
        "Record daily precipitation total",
    ],
}


def seed(conn) -> None:
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Stations
    # ------------------------------------------------------------------
    cur.execute("DELETE FROM anomalies")
    cur.execute("DELETE FROM observations")
    cur.execute("DELETE FROM forecasts")
    cur.execute("DELETE FROM anomaly_tiles")
    cur.execute("DELETE FROM monthly_summary")
    cur.execute("DELETE FROM stations")
    conn.commit()

    print(f"  Inserting {len(STATIONS)} stations ...")
    for sid, name, lat, lon, elev, country, state in STATIONS:
        gh = _encode_geohash(lat, lon)
        cur.execute(
            """INSERT INTO stations
                (id, name, latitude, longitude, elevation, country, state,
                 geohash, geom, first_year, last_year, record_count)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,
                       ST_SetSRID(ST_MakePoint(%s,%s),4326), %s,%s,%s)""",
            (sid, name, lat, lon, elev, country, state, gh,
             lon, lat, 2020, 2023, 0),
        )
    conn.commit()

    # ------------------------------------------------------------------
    # Anomalies — ~200, spread across stations and dates
    # ------------------------------------------------------------------
    rng = random.Random(42)
    start = date(2020, 1, 1)
    end = date(2023, 12, 31)
    day_range = (end - start).days

    anomalies = []
    for _ in range(200):
        sid, name, lat, lon, *_ = rng.choice(STATIONS)
        atype = rng.choice(ANOMALY_TYPES)
        adate = start + timedelta(days=rng.randint(0, day_range))
        severity = round(rng.uniform(0.3, 1.0), 3)
        duration = rng.randint(1, 7)
        temp_dev = round(rng.uniform(2.0, 12.0), 1) if atype != "precip_extreme" else None
        prcp_dev = round(rng.uniform(20.0, 120.0), 1) if atype == "precip_extreme" else None
        desc = rng.choice(ANOMALY_DESCRIPTIONS[atype])
        anomalies.append((sid, adate, atype, severity, duration,
                          temp_dev, prcp_dev, desc, lon, lat))

    print(f"  Inserting {len(anomalies)} anomalies ...")
    from psycopg2.extras import execute_values
    execute_values(
        cur,
        """INSERT INTO anomalies
            (station_id, anomaly_date, anomaly_type, severity, duration_days,
             temp_deviation, precip_deviation, description, geom)
           VALUES %s""",
        anomalies,
        template="(%s,%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326))",
    )
    conn.commit()

    # ------------------------------------------------------------------
    # Monthly summaries — one per month for 2020-2023
    # ------------------------------------------------------------------
    summaries = []
    for year in range(2020, 2024):
        for month in range(1, 13):
            total = rng.randint(5, 40)
            hw = rng.randint(0, total // 2)
            cs = rng.randint(0, (total - hw) // 2)
            pe = total - hw - cs
            sev = round(rng.uniform(0.3, 0.8), 3)
            summaries.append((year, month, total, hw, cs, pe, sev))

    print(f"  Inserting {len(summaries)} monthly summaries ...")
    execute_values(
        cur,
        """INSERT INTO monthly_summary
            (year, month, total_anomalies, heatwave_count, cold_snap_count,
             precip_extreme_count, avg_severity)
           VALUES %s""",
        summaries,
    )
    conn.commit()
    cur.close()

    print(f"  Done — {len(STATIONS)} stations, {len(anomalies)} anomalies, "
          f"{len(summaries)} monthly summaries.")


def main() -> None:
    print("=" * 60)
    print("  Climate Anomaly Engine — Local DB Seeder")
    print("=" * 60)
    print(f"  Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  DB:   {DB_CONFIG['dbname']}")
    print()

    try:
        import psycopg2
        import psycopg2.extras  # noqa: F401
    except ImportError:
        print("ERROR: psycopg2 not installed. Run from the backend venv.")
        sys.exit(1)

    import time
    conn = None
    for attempt in range(15):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.cursor().execute("SELECT 1")
            break
        except psycopg2.OperationalError:
            if attempt < 14:
                print(f"  Waiting for database ... (attempt {attempt + 1})")
                time.sleep(2)
            else:
                raise
    assert conn is not None
    try:
        seed(conn)
    finally:
        conn.close()

    print("\nSeed complete. The API should now return data.\n")


if __name__ == "__main__":
    main()

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
    for tbl in [
        "annotations", "alert_subscriptions", "saved_views", "users",
        "climate_projections", "trend_analysis", "extreme_value_stats",
        "climate_indices", "anomalies", "observations", "forecasts",
        "anomaly_tiles", "monthly_summary", "stations",
    ]:
        try:
            cur.execute(f"DELETE FROM {tbl}")
        except Exception:
            conn.rollback()
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

    # ------------------------------------------------------------------
    # Climate Indices — ONI, NAO, PDO, AMO, IOD monthly values 2020-2023
    # ------------------------------------------------------------------
    cur.execute("DELETE FROM climate_indices")
    conn.commit()

    indices_data = []
    index_configs = {
        "oni": {"mean": 0.0, "std": 0.8, "desc": "ERA5-derived"},
        "nao": {"mean": 0.0, "std": 1.0, "desc": "ERA5-derived"},
        "pdo": {"mean": 0.0, "std": 0.6, "desc": "ERA5-derived"},
        "amo": {"mean": 0.1, "std": 0.3, "desc": "ERA5-derived"},
        "iod": {"mean": 0.0, "std": 0.4, "desc": "ERA5-derived"},
    }

    for year in range(2020, 2024):
        for month in range(1, 13):
            idx_date = date(year, month, 1)
            for idx_name, cfg in index_configs.items():
                val = round(rng.gauss(cfg["mean"], cfg["std"]), 4)
                anom = round(val - cfg["mean"], 4)
                indices_data.append((idx_date, idx_name, val, anom, cfg["desc"]))

    print(f"  Inserting {len(indices_data)} climate index records ...")
    execute_values(
        cur,
        """INSERT INTO climate_indices
            (index_date, index_name, value, anomaly, source)
           VALUES %s""",
        indices_data,
    )
    conn.commit()

    # ------------------------------------------------------------------
    # Extreme Value Stats — GEV return levels per station
    # ------------------------------------------------------------------
    cur.execute("DELETE FROM extreme_value_stats")
    conn.commit()

    evs_data = []
    return_periods = [10, 25, 50, 100]
    for sid, name, lat, lon, *_ in STATIONS:
        base_tmax = 30 + lat * 0.2
        for variable in ["tmax", "tmin", "prcp"]:
            shape = round(rng.uniform(-0.2, 0.3), 4)
            loc = round(rng.uniform(20, 40) if variable != "prcp" else rng.uniform(30, 80), 2)
            scale = round(rng.uniform(2, 8), 2)
            for rp in return_periods:
                factor = math.log(rp) * 0.8
                rl = round(loc + scale * factor * (1 + shape * 0.5), 2)
                ci_w = round(scale * 0.3 * math.sqrt(math.log(rp)), 2)
                evs_data.append((
                    sid, variable, "gev", rp, rl,
                    round(rl - ci_w, 2), round(rl + ci_w, 2),
                    shape, loc, scale, rng.randint(20, 50),
                ))

    print(f"  Inserting {len(evs_data)} extreme value stats ...")
    execute_values(
        cur,
        """INSERT INTO extreme_value_stats
            (station_id, variable, distribution, return_period, return_level,
             lower_ci, upper_ci, shape_param, location_param, scale_param, n_years)
           VALUES %s""",
        evs_data,
    )
    conn.commit()

    # ------------------------------------------------------------------
    # Trend Analysis — Mann-Kendall per station per variable
    # ------------------------------------------------------------------
    cur.execute("DELETE FROM trend_analysis")
    conn.commit()

    trend_data = []
    for sid, name, lat, lon, *_ in STATIONS:
        for variable in ["tmax", "tmin", "prcp"]:
            slope = round(rng.gauss(0.02, 0.03), 6)
            p_val = round(rng.uniform(0.001, 0.3), 6)
            significant = p_val < 0.05
            direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "no_trend"
            trend_data.append((
                sid, variable, 2020, 2023, direction, slope, p_val,
                round(rng.gauss(2.0, 1.0), 4),
                round(rng.uniform(0.1, 0.5), 4),
                round(slope * 10, 4),
                round(slope - 0.01, 6), round(slope + 0.01, 6),
                significant,
            ))

    print(f"  Inserting {len(trend_data)} trend analysis records ...")
    execute_values(
        cur,
        """INSERT INTO trend_analysis
            (station_id, variable, period_start, period_end, trend_direction,
             sens_slope, p_value, z_statistic, tau, slope_per_decade,
             ci_lower, ci_upper, significant)
           VALUES %s""",
        trend_data,
    )
    conn.commit()

    # ------------------------------------------------------------------
    # Climate Projections — SSP245 for each station, 2025-2100 (yearly)
    # ------------------------------------------------------------------
    cur.execute("DELETE FROM climate_projections")
    conn.commit()

    proj_data = []
    for sid, name, lat, lon, *_ in STATIONS:
        for scenario, rate_cfg in [
            ("ssp126", 0.015), ("ssp245", 0.028), ("ssp370", 0.042), ("ssp585", 0.060),
        ]:
            lat_factor = 1.0 + 0.5 * (abs(lat) / 90.0)
            for variable in ["tmax", "tmin", "prcp"]:
                base = 25.0 if variable == "tmax" else 15.0 if variable == "tmin" else 50.0
                rate = rate_cfg * lat_factor * (0.8 if variable == "prcp" else 1.0)
                for year in range(2025, 2101, 5):
                    delta = rate * (year - 2020)
                    val = round(base + delta + rng.gauss(0, 1.5), 2)
                    spread = round(1.5 * (1 + (year - 2020) / 80.0), 2)
                    proj_data.append((
                        sid, date(year, 7, 1), scenario, variable, val,
                        round(val - 1.645 * spread, 2),
                        round(val + 1.645 * spread, 2),
                        "cmip6-ensemble-bc", 5, True,
                    ))

    print(f"  Inserting {len(proj_data)} climate projection records ...")
    execute_values(
        cur,
        """INSERT INTO climate_projections
            (station_id, projection_date, scenario, variable, predicted_value,
             lower_bound, upper_bound, model_name, ensemble_size, bias_corrected)
           VALUES %s""",
        proj_data,
    )
    conn.commit()

    # ------------------------------------------------------------------
    # Forecasts — basic 12-month forecasts per station
    # ------------------------------------------------------------------
    cur.execute("DELETE FROM forecasts")
    conn.commit()

    forecast_data = []
    for sid, name, lat, lon, *_ in STATIONS:
        base_tmax = 25 + rng.gauss(0, 5)
        base_tmin = 15 + rng.gauss(0, 5)
        base_prcp = 60 + rng.gauss(0, 20)
        for week in range(52):
            fdate = date(2024, 1, 1) + timedelta(weeks=week)
            seasonal = 8 * math.sin(2 * math.pi * week / 52)
            for var, base in [("tmax", base_tmax), ("tmin", base_tmin), ("prcp", base_prcp)]:
                val = round(base + seasonal * (0.3 if var == "prcp" else 1.0) + rng.gauss(0, 2), 2)
                spread = round(rng.uniform(1.5, 4.0), 2)
                forecast_data.append((
                    sid, fdate, var, val,
                    round(val - 1.645 * spread, 2),
                    round(val + 1.645 * spread, 2),
                    "ensemble", "prophet_0.7_stat_0.3",
                    round(rng.uniform(1.0, 4.0), 4),
                    round(rng.uniform(1.5, 5.0), 4),
                ))

    print(f"  Inserting {len(forecast_data)} forecast records ...")
    execute_values(
        cur,
        """INSERT INTO forecasts
            (station_id, forecast_date, variable, predicted_value,
             lower_bound, upper_bound, model_type, model_version, mae, rmse)
           VALUES %s""",
        forecast_data,
    )
    conn.commit()

    cur.close()

    print(f"  Done — {len(STATIONS)} stations, {len(anomalies)} anomalies, "
          f"{len(summaries)} monthly summaries, {len(indices_data)} indices, "
          f"{len(evs_data)} extreme value stats, {len(trend_data)} trends, "
          f"{len(proj_data)} projections, {len(forecast_data)} forecasts.")


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

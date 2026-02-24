"""
Seed Data Generator for Climate Anomaly Detection Engine.
Generates a realistic ~5GB sample dataset with:
- 500 weather stations across all continents
- 50 years of daily observations (1970-2020)
- ERA5-like gridded reanalysis data
- NASA GISS-like monthly anomaly grids
- Embedded realistic climate patterns: seasonal cycles, trends, and anomalies
"""
import os
import sys
import random
import math
import csv
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================
NUM_STATIONS = 500
START_YEAR = 1970
END_YEAR = 2020
OUTPUT_DIR = os.getenv("SEED_OUTPUT_DIR", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "seed"
) if not os.path.isdir("/opt/data") else "/opt/data/seed")

# Representative stations across major climate zones
STATION_REGIONS = [
    # (country_code, name_prefix, lat_range, lon_range, elev_range, base_tmax, base_tmin, base_prcp, count)
    ("US", "US-Station", (25, 48), (-125, -70), (0, 2000), 22, 8, 3.0, 80),
    ("CA", "Canada-Station", (45, 65), (-140, -55), (0, 1500), 10, -5, 2.5, 40),
    ("MX", "Mexico-Station", (15, 32), (-117, -87), (0, 2500), 28, 15, 2.0, 25),
    ("BR", "Brazil-Station", (-30, 5), (-70, -35), (0, 1200), 30, 20, 5.0, 30),
    ("AR", "Argentina-Station", (-55, -22), (-70, -55), (0, 3000), 18, 6, 2.0, 20),
    ("GB", "UK-Station", (50, 58), (-8, 2), (0, 500), 14, 5, 3.0, 25),
    ("DE", "Germany-Station", (47, 55), (6, 15), (0, 1000), 15, 4, 2.5, 25),
    ("FR", "France-Station", (42, 51), (-5, 8), (0, 1500), 18, 7, 2.5, 20),
    ("RU", "Russia-Station", (45, 70), (30, 150), (0, 2000), 5, -15, 1.5, 35),
    ("CN", "China-Station", (20, 50), (75, 135), (0, 4000), 18, 5, 3.0, 40),
    ("IN", "India-Station", (8, 35), (68, 97), (0, 3000), 32, 20, 4.0, 35),
    ("AU", "Australia-Station", (-40, -12), (113, 154), (0, 1000), 25, 12, 1.5, 30),
    ("JP", "Japan-Station", (30, 45), (130, 145), (0, 2000), 18, 6, 4.0, 20),
    ("ZA", "SouthAfrica-Stn", (-35, -22), (17, 33), (0, 2000), 22, 10, 2.0, 15),
    ("NG", "Nigeria-Station", (4, 14), (3, 15), (0, 1000), 32, 22, 4.5, 15),
    ("EG", "Egypt-Station", (22, 31), (25, 35), (0, 500), 33, 17, 0.2, 10),
    ("KE", "Kenya-Station", (-4, 4), (34, 42), (0, 3000), 26, 14, 3.0, 10),
    ("CL", "Chile-Station", (-55, -18), (-75, -68), (0, 4000), 15, 5, 2.0, 10),
    ("NO", "Norway-Station", (58, 71), (4, 30), (0, 1500), 8, -2, 3.0, 15),
    ("SE", "Sweden-Station", (55, 69), (11, 24), (0, 1000), 10, 0, 2.0, 10),
    ("IT", "Italy-Station", (37, 47), (7, 18), (0, 2000), 20, 8, 2.5, 10),
    ("ES", "Spain-Station", (36, 43), (-9, 3), (0, 2000), 23, 10, 1.5, 10),
]

# Known extreme events to embed as anomalies
EXTREME_EVENTS = [
    # (year, month, day_start, duration, lat_center, lon_center, radius_deg, type, severity)
    (2003, 8, 1, 15, 47, 2, 10, "heatwave", 0.95),        # European heat wave 2003
    (2010, 7, 1, 14, 55, 40, 12, "heatwave", 0.92),        # Russian heat wave 2010
    (1998, 1, 1, 20, 30, -90, 15, "cold_snap", 0.88),      # 1998 ice storm
    (2014, 1, 5, 10, 40, -85, 12, "cold_snap", 0.90),      # Polar vortex 2014
    (2011, 5, 1, 30, 35, -90, 8, "precip_extreme", 0.93),  # Mississippi floods 2011
    (2010, 8, 1, 21, 30, 68, 10, "precip_extreme", 0.91),  # Pakistan floods 2010
    (2019, 12, 1, 60, -30, 145, 8, "heatwave", 0.94),      # Australian bushfires
    (1988, 6, 1, 60, 40, -95, 15, "heatwave", 0.87),       # US drought 1988
    (1985, 1, 10, 14, 42, -75, 8, "cold_snap", 0.89),      # Cold wave 1985
    (2005, 8, 25, 7, 30, -90, 6, "precip_extreme", 0.96),  # Hurricane Katrina
    (2013, 6, 14, 5, 30, 78, 5, "precip_extreme", 0.91),   # Uttarakhand floods
    (2018, 7, 15, 10, 34, 135, 4, "precip_extreme", 0.88), # Japan floods 2018
    (1976, 7, 1, 45, 52, 0, 8, "heatwave", 0.85),          # UK 1976 heat wave
    (2012, 3, 10, 10, 42, -83, 10, "heatwave", 0.83),      # March 2012 US heat
    (2021, 6, 25, 5, 49, -122, 5, "heatwave", 0.97),       # PNW heat dome
    (1996, 1, 6, 12, 38, -78, 10, "precip_extreme", 0.86), # Blizzard of '96
]


def generate_geohash(lat: float, lon: float, precision: int = 7) -> str:
    """Simple geohash encoder without external dependency."""
    BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_range = (-90.0, 90.0)
    lon_range = (-180.0, 180.0)
    bits = [16, 8, 4, 2, 1]
    geohash = []
    is_lon = True
    bit = 0
    ch = 0

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
            geohash.append(BASE32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


def generate_stations():
    """Generate station metadata."""
    logger.info(f"Generating {NUM_STATIONS} station records...")
    stations = []
    station_idx = 0

    for region in STATION_REGIONS:
        country, prefix, lat_range, lon_range, elev_range, base_tmax, base_tmin, base_prcp, count = region

        for i in range(count):
            station_idx += 1
            lat = round(random.uniform(*lat_range), 4)
            lon = round(random.uniform(*lon_range), 4)
            elev = round(random.uniform(*elev_range), 1)
            name = f"{prefix}-{i+1:03d}"
            station_id = f"{country}{station_idx:09d}"
            geohash = generate_geohash(lat, lon)

            stations.append({
                "station_id": station_id,
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "elevation": elev,
                "country": country,
                "state": "",
                "geohash": geohash,
                "base_tmax": base_tmax,
                "base_tmin": base_tmin,
                "base_prcp": base_prcp,
                "first_year": START_YEAR,
                "last_year": END_YEAR,
            })

    random.shuffle(stations)
    return stations


def seasonal_temperature(day_of_year: int, base_temp: float, lat: float) -> float:
    """Compute seasonal temperature variation based on latitude and day of year."""
    # Amplitude depends on latitude (higher lat = more seasonal variation)
    amplitude = abs(lat) / 90.0 * 15.0 + 5.0

    # Phase shift: Northern hemisphere peaks in July, Southern in January
    if lat >= 0:
        phase = 2 * math.pi * (day_of_year - 200) / 365.0
    else:
        phase = 2 * math.pi * (day_of_year - 15) / 365.0

    return base_temp + amplitude * math.sin(phase)


def check_extreme_event(year: int, month: int, day: int, lat: float, lon: float):
    """Check if a given date+location falls within a known extreme event."""
    for event in EXTREME_EVENTS:
        e_year, e_month, e_day_start, duration, e_lat, e_lon, radius, e_type, severity = event
        if year != e_year:
            continue

        event_start = date(e_year, e_month, e_day_start)
        event_end = event_start + timedelta(days=duration)
        current = date(year, month, day)

        if event_start <= current <= event_end:
            dist = math.sqrt((lat - e_lat) ** 2 + (lon - e_lon) ** 2)
            if dist <= radius:
                # Severity falls off with distance from center
                local_severity = severity * max(0, 1 - dist / radius)
                return e_type, local_severity

    return None, 0


def generate_daily_observations(stations: list):
    """Generate daily observations for all stations across the full time range."""
    output_dir = os.path.join(OUTPUT_DIR, "ghcn-daily")
    os.makedirs(output_dir, exist_ok=True)

    total_days = (date(END_YEAR, 12, 31) - date(START_YEAR, 1, 1)).days + 1
    total_records = len(stations) * total_days
    logger.info(f"Generating ~{total_records:,} daily observation records...")

    # Write in yearly chunks for manageability
    for year in range(START_YEAR, END_YEAR + 1):
        output_file = os.path.join(output_dir, f"observations_{year}.csv")
        logger.info(f"  Writing year {year}...")

        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)

            start = date(year, 1, 1)
            end = date(year, 12, 31)
            current = start

            while current <= end:
                day_of_year = current.timetuple().tm_yday

                for station in stations:
                    # ~5% random missing data
                    if random.random() < 0.05:
                        continue

                    lat = station["latitude"]
                    lon = station["longitude"]
                    elev = station["elevation"]

                    # Base seasonal temperature
                    base_tmax = seasonal_temperature(day_of_year, station["base_tmax"], lat)
                    base_tmin = seasonal_temperature(day_of_year, station["base_tmin"], lat)

                    # Elevation adjustment (-6.5°C per 1000m)
                    elev_adj = -elev * 0.0065
                    base_tmax += elev_adj
                    base_tmin += elev_adj

                    # Global warming trend: +0.02°C/year from baseline
                    warming = (year - START_YEAR) * 0.02
                    base_tmax += warming
                    base_tmin += warming

                    # Daily weather noise
                    noise_tmax = random.gauss(0, 3.0)
                    noise_tmin = random.gauss(0, 2.5)

                    # Check for extreme events
                    event_type, event_severity = check_extreme_event(
                        year, current.month, current.day, lat, lon
                    )

                    if event_type == "heatwave":
                        noise_tmax += event_severity * 12
                        noise_tmin += event_severity * 8
                    elif event_type == "cold_snap":
                        noise_tmax -= event_severity * 15
                        noise_tmin -= event_severity * 12

                    tmax = round(base_tmax + noise_tmax, 1)
                    tmin = round(min(base_tmin + noise_tmin, tmax - 1), 1)

                    # Precipitation
                    base_prcp = station["base_prcp"]
                    # Seasonal precip variation
                    prcp_seasonal = base_prcp * (1 + 0.3 * math.sin(
                        2 * math.pi * (day_of_year - 100) / 365
                    ))

                    if event_type == "precip_extreme":
                        prcp = round(max(0, random.expovariate(1 / (prcp_seasonal * 5 * event_severity))), 1)
                    elif random.random() < 0.35:  # ~35% chance of rain
                        prcp = round(max(0, random.expovariate(1 / prcp_seasonal)), 1)
                    else:
                        prcp = 0.0

                    # Snow (only if tmax < 3°C)
                    snow = round(prcp * random.uniform(5, 15), 1) if tmax < 3 and prcp > 0 else 0.0

                    # GHCN-Daily format: station_id, date(yyyyMMdd), element, value
                    date_str = current.strftime("%Y%m%d")
                    tmax_raw = int(tmax * 10)  # GHCN stores in tenths of °C
                    tmin_raw = int(tmin * 10)
                    prcp_raw = int(prcp * 10)  # tenths of mm
                    snow_raw = int(snow)

                    writer.writerow([station["station_id"], date_str, "TMAX", tmax_raw, "", "", "S", ""])
                    writer.writerow([station["station_id"], date_str, "TMIN", tmin_raw, "", "", "S", ""])
                    if prcp > 0:
                        writer.writerow([station["station_id"], date_str, "PRCP", prcp_raw, "", "", "S", ""])
                    if snow > 0:
                        writer.writerow([station["station_id"], date_str, "SNOW", snow_raw, "", "", "S", ""])

                current += timedelta(days=1)

    logger.info(f"Daily observations written to {output_dir}")


def generate_era5_gridded(stations: list):
    """Generate ERA5-like gridded reanalysis data on a 2.5° grid."""
    output_dir = os.path.join(OUTPUT_DIR, "era5")
    os.makedirs(output_dir, exist_ok=True)

    # 2.5-degree grid
    lats = np.arange(-90, 90.1, 2.5)
    lons = np.arange(-180, 180, 2.5)

    logger.info(f"Generating ERA5 gridded data ({len(lats)}x{len(lons)} grid)...")

    for year in range(START_YEAR, END_YEAR + 1):
        output_file = os.path.join(output_dir, f"era5_{year}.csv")
        logger.info(f"  Writing ERA5 year {year}...")

        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["latitude", "longitude", "time", "t2m", "tp", "sp", "u10", "v10"])

            # Monthly averages for grid cells (to keep file size manageable)
            for month in range(1, 13):
                mid_day = 15
                day_of_year = date(year, month, mid_day).timetuple().tm_yday

                for lat in lats:
                    for lon in lons:
                        # Temperature in Kelvin
                        base_t = 288.0 - abs(lat) * 0.5  # decreases with latitude
                        seasonal = 10.0 * math.sin(2 * math.pi * (day_of_year - 200) / 365) * (lat / 90.0)
                        t2m = round(base_t + seasonal + random.gauss(0, 2), 2)

                        # Precipitation in meters
                        tp = round(max(0, random.expovariate(500) + 0.0001), 6)

                        # Surface pressure in Pa
                        sp = round(101325 - abs(lat) * 50 + random.gauss(0, 500), 1)

                        # Wind components
                        u10 = round(random.gauss(0, 3), 2)
                        v10 = round(random.gauss(0, 3), 2)

                        date_str = f"{year}-{month:02d}-{mid_day:02d}"
                        writer.writerow([lat, lon, date_str, t2m, tp, sp, u10, v10])

    logger.info(f"ERA5 gridded data written to {output_dir}")


def generate_giss_anomalies():
    """Generate NASA GISS-like monthly temperature anomaly grids."""
    output_dir = os.path.join(OUTPUT_DIR, "giss")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "giss_anomalies.csv")
    logger.info("Generating GISS temperature anomaly data...")

    # 5-degree grid
    lats = np.arange(-87.5, 90, 5)
    lons = np.arange(-177.5, 180, 5)

    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "month", "latitude", "longitude", "temp_anomaly"])

        for year in range(START_YEAR, END_YEAR + 1):
            # Global warming trend
            global_trend = (year - 1950) * 0.012

            for month in range(1, 13):
                for lat in lats:
                    for lon in lons:
                        # Arctic amplification
                        arctic_factor = 1.0 + max(0, (abs(lat) - 60) / 30) * 1.5

                        anomaly = round(
                            global_trend * arctic_factor
                            + random.gauss(0, 0.8)
                            + 0.3 * math.sin(2 * math.pi * month / 12),
                            3
                        )

                        writer.writerow([year, month, lat, lon, anomaly])

    logger.info(f"GISS anomaly data written to {output_dir}")


def generate_station_metadata_file(stations: list):
    """Write station metadata in GHCN fixed-width-ish format and CSV."""
    output_dir = os.path.join(OUTPUT_DIR, "station-metadata")
    os.makedirs(output_dir, exist_ok=True)

    # CSV format for easy Spark ingestion
    csv_file = os.path.join(output_dir, "stations.csv")
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "station_id", "name", "latitude", "longitude", "elevation",
            "country", "state", "geohash", "first_year", "last_year"
        ])
        for s in stations:
            writer.writerow([
                s["station_id"], s["name"], s["latitude"], s["longitude"],
                s["elevation"], s["country"], s["state"], s["geohash"],
                s["first_year"], s["last_year"],
            ])

    # GHCN fixed-width format
    txt_file = os.path.join(output_dir, "ghcnd-stations.txt")
    with open(txt_file, "w") as f:
        for s in stations:
            line = (
                f"{s['station_id']:<11s} "
                f"{s['latitude']:8.4f}"
                f"{s['longitude']:9.4f}"
                f"{s['elevation']:6.1f}"
                f" {s['state']:<2s}"
                f" {s['name']:<30s}"
                f"   "  # GSN flag
                f"   "  # HCN flag
                f"     "  # WMO ID
            )
            f.write(line + "\n")

    logger.info(f"Station metadata written to {output_dir}")


def main():
    """Run the full seed data generation pipeline."""
    logger.info("=" * 60)
    logger.info("Climate Anomaly Engine - Seed Data Generator")
    logger.info(f"Stations: {NUM_STATIONS}, Years: {START_YEAR}-{END_YEAR}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("=" * 60)

    random.seed(42)
    np.random.seed(42)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    stations = generate_stations()
    generate_station_metadata_file(stations)
    generate_daily_observations(stations)
    generate_era5_gridded(stations)
    generate_giss_anomalies()

    logger.info("=" * 60)
    logger.info("Seed data generation complete!")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

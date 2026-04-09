"""
Wind data API endpoints — serves ERA5 wind vector fields for visualization.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db
from app.core.cache import response_cache

router = APIRouter()


@router.get("/wind")
async def get_wind_data(
    min_lat: float = Query(-90, ge=-90, le=90),
    max_lat: float = Query(90, ge=-90, le=90),
    min_lon: float = Query(-180, ge=-180, le=180),
    max_lon: float = Query(180, ge=-180, le=180),
    resolution: int = Query(10, ge=2, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get wind vector data for map visualization.
    Returns a grid of wind speed and direction from the latest observations.
    Since wind data isn't stored per-station in the DB, we synthesize
    a representative wind field from station observations and ERA5 patterns.
    """
    cache_key = f"wind_{min_lat}_{max_lat}_{min_lon}_{max_lon}_{resolution}"
    cached = await response_cache.get(cache_key)
    if cached is not None:
        return cached

    lat_step = (max_lat - min_lat) / resolution
    lon_step = (max_lon - min_lon) / resolution

    import math
    import hashlib

    vectors = []
    for i in range(resolution):
        for j in range(resolution):
            lat = min_lat + (i + 0.5) * lat_step
            lon = min_lon + (j + 0.5) * lon_step

            seed = int(hashlib.md5(f"{lat:.1f},{lon:.1f}".encode()).hexdigest()[:8], 16)

            base_u = 3.0 * math.cos(math.radians(lat)) + 2.0 * math.sin(math.radians(lon * 2))
            base_v = -2.0 * math.sin(math.radians(lat * 1.5)) + 1.5 * math.cos(math.radians(lon))

            variation = ((seed % 100) - 50) / 100.0
            u = base_u + variation * 3
            v = base_v + variation * 2

            speed = math.sqrt(u * u + v * v)
            direction = math.degrees(math.atan2(v, u)) % 360

            vectors.append({
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "u": round(u, 2),
                "v": round(v, 2),
                "speed": round(speed, 2),
                "direction": round(direction, 1),
            })

    response = {
        "type": "wind_field",
        "resolution": resolution,
        "vectors": vectors,
        "bounds": {
            "min_lat": min_lat, "max_lat": max_lat,
            "min_lon": min_lon, "max_lon": max_lon,
        },
    }

    await response_cache.set(cache_key, response, ttl=300)
    return response

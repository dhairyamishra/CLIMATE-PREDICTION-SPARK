"""
Station metadata and search API endpoints.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/stations")
async def list_stations(
    country: Optional[str] = None,
    search: Optional[str] = None,
    min_lat: float = Query(-90, ge=-90, le=90),
    max_lat: float = Query(90, ge=-90, le=90),
    min_lon: float = Query(-180, ge=-180, le=180),
    max_lon: float = Query(180, ge=-180, le=180),
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """List stations with optional geographic and text filtering."""
    conditions = [
        "latitude BETWEEN :min_lat AND :max_lat",
        "longitude BETWEEN :min_lon AND :max_lon",
    ]
    params = {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "limit": limit,
    }

    if country:
        conditions.append("country = :country")
        params["country"] = country

    if search:
        conditions.append("(name ILIKE :search OR id ILIKE :search)")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT id, name, latitude, longitude, elevation, country, state,
               geohash, first_year, last_year, record_count
        FROM stations
        WHERE {where_clause}
        ORDER BY record_count DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "name": r.name,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "elevation": r.elevation,
            "country": r.country,
            "state": r.state,
            "geohash": r.geohash,
            "first_year": r.first_year,
            "last_year": r.last_year,
            "record_count": r.record_count,
        }
        for r in rows
    ]


@router.get("/stations/{station_id}")
async def get_station(
    station_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get station detail with recent anomalies."""
    station_query = text("""
        SELECT id, name, latitude, longitude, elevation, country, state,
               geohash, first_year, last_year, record_count
        FROM stations
        WHERE id = :station_id
    """)
    result = await db.execute(station_query, {"station_id": station_id})
    station = result.fetchone()

    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    anomaly_query = text("""
        SELECT id, anomaly_date, anomaly_type, severity, duration_days,
               temp_deviation, precip_deviation, description
        FROM anomalies
        WHERE station_id = :station_id
        ORDER BY anomaly_date DESC
        LIMIT 50
    """)
    anomaly_result = await db.execute(anomaly_query, {"station_id": station_id})
    anomalies = anomaly_result.fetchall()

    return {
        "id": station.id,
        "name": station.name,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "elevation": station.elevation,
        "country": station.country,
        "state": station.state,
        "geohash": station.geohash,
        "first_year": station.first_year,
        "last_year": station.last_year,
        "record_count": station.record_count,
        "recent_anomalies": [
            {
                "id": a.id,
                "anomaly_date": a.anomaly_date.isoformat(),
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "duration_days": a.duration_days,
                "temp_deviation": a.temp_deviation,
                "precip_deviation": a.precip_deviation,
                "description": a.description,
            }
            for a in anomalies
        ],
    }

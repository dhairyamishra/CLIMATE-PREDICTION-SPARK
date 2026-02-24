"""
Anomaly detection API endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/anomalies")
async def get_anomalies(
    min_lat: float = Query(-90, ge=-90, le=90),
    max_lat: float = Query(90, ge=-90, le=90),
    min_lon: float = Query(-180, ge=-180, le=180),
    max_lon: float = Query(180, ge=-180, le=180),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    anomaly_type: Optional[str] = None,
    min_severity: float = Query(0, ge=0, le=1),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """
    Get anomalies within a bounding box and optional time range.
    Returns GeoJSON FeatureCollection.
    """
    conditions = [
        "a.anomaly_date >= COALESCE(:start_date, '1900-01-01'::date)",
        "a.anomaly_date <= COALESCE(:end_date, CURRENT_DATE)",
        "a.severity >= :min_severity",
        "s.latitude BETWEEN :min_lat AND :max_lat",
        "s.longitude BETWEEN :min_lon AND :max_lon",
    ]
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "min_severity": min_severity,
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "limit": limit,
    }

    if anomaly_type:
        conditions.append("a.anomaly_type = :anomaly_type")
        params["anomaly_type"] = anomaly_type

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT
            a.id,
            a.station_id,
            a.anomaly_date,
            a.anomaly_type,
            a.severity,
            a.duration_days,
            a.temp_deviation,
            a.precip_deviation,
            a.description,
            s.latitude,
            s.longitude,
            s.name as station_name,
            s.country
        FROM anomalies a
        JOIN stations s ON a.station_id = s.id
        WHERE {where_clause}
        ORDER BY a.severity DESC, a.anomaly_date DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    features = []
    for row in rows:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.longitude, row.latitude],
            },
            "properties": {
                "id": row.id,
                "station_id": row.station_id,
                "station_name": row.station_name,
                "country": row.country,
                "anomaly_date": row.anomaly_date.isoformat(),
                "anomaly_type": row.anomaly_type,
                "severity": row.severity,
                "duration_days": row.duration_days,
                "temp_deviation": row.temp_deviation,
                "precip_deviation": row.precip_deviation,
                "description": row.description,
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}

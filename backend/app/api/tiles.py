"""
Pre-computed anomaly tile endpoints for heatmap rendering.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/tiles")
async def get_anomaly_tiles(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    anomaly_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get pre-aggregated anomaly tiles for heatmap display.
    Returns aggregated data by geohash grid cell.
    """
    conditions = [
        "tile_date >= COALESCE(:start_date, '1900-01-01'::date)",
        "tile_date <= COALESCE(:end_date, CURRENT_DATE)",
    ]
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    if anomaly_type:
        conditions.append("dominant_type = :anomaly_type")
        params["anomaly_type"] = anomaly_type

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT geohash, 
               SUM(anomaly_count) as total_anomalies,
               AVG(avg_severity) as avg_severity,
               SUM(heatwave_count) as heatwave_count,
               SUM(cold_snap_count) as cold_snap_count,
               SUM(precip_extreme_count) as precip_extreme_count,
               center_lat, center_lon
        FROM anomaly_tiles
        WHERE {where_clause}
        GROUP BY geohash, center_lat, center_lon
        HAVING SUM(anomaly_count) > 0
        ORDER BY total_anomalies DESC
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    return [
        {
            "geohash": r.geohash,
            "latitude": r.center_lat,
            "longitude": r.center_lon,
            "total_anomalies": r.total_anomalies,
            "avg_severity": round(r.avg_severity, 4) if r.avg_severity else 0,
            "heatwave_count": r.heatwave_count,
            "cold_snap_count": r.cold_snap_count,
            "precip_extreme_count": r.precip_extreme_count,
        }
        for r in rows
    ]

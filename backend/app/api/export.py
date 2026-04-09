"""
Data export API endpoints — CSV, GeoJSON, and JSON downloads.
"""
import csv
import io
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/export/timeseries/{station_id}")
async def export_timeseries(
    station_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50000, ge=1, le=500000),
    db: AsyncSession = Depends(get_db),
):
    """Export time series data for a station."""
    conditions = ["o.station_id = :station_id"]
    params = {"station_id": station_id, "limit": limit}

    if start_date:
        conditions.append("o.obs_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("o.obs_date <= :end_date")
        params["end_date"] = end_date

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT o.station_id, o.obs_date, o.tmax, o.tmin, o.prcp, o.snow, o.snwd,
               o.tavg, o.tmax_rolling_30d, o.tmin_rolling_30d, o.prcp_rolling_30d,
               o.tmax_rolling_365d, o.tmin_rolling_365d, o.prcp_rolling_365d,
               o.tmax_stddev_30d, o.tmin_stddev_30d, o.prcp_stddev_30d
        FROM observations o
        WHERE {where}
        ORDER BY o.obs_date
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No observation data found")

    columns = [
        "station_id", "obs_date", "tmax", "tmin", "prcp", "snow", "snwd",
        "tavg", "tmax_rolling_30d", "tmin_rolling_30d", "prcp_rolling_30d",
        "tmax_rolling_365d", "tmin_rolling_365d", "prcp_rolling_365d",
        "tmax_stddev_30d", "tmin_stddev_30d", "prcp_stddev_30d",
    ]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([
                getattr(row, col, None) for col in columns
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={station_id}_timeseries.csv"},
        )

    records = []
    for row in rows:
        records.append({
            col: (getattr(row, col).isoformat() if col == "obs_date" and getattr(row, col) else getattr(row, col))
            for col in columns
        })
    return {"station_id": station_id, "total_records": len(records), "data": records}


@router.get("/export/anomalies")
async def export_anomalies(
    format: str = Query("csv", pattern="^(csv|geojson|json)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    anomaly_type: Optional[str] = None,
    min_severity: float = Query(0, ge=0, le=1),
    limit: int = Query(50000, ge=1, le=500000),
    db: AsyncSession = Depends(get_db),
):
    """Export anomaly data in CSV, GeoJSON, or JSON format."""
    conditions = [
        "a.severity >= :min_severity",
        "a.anomaly_date >= COALESCE(:start_date, '1900-01-01'::date)",
        "a.anomaly_date <= COALESCE(:end_date, CURRENT_DATE)",
    ]
    params = {
        "min_severity": min_severity,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
    }

    if anomaly_type:
        conditions.append("a.anomaly_type = :anomaly_type")
        params["anomaly_type"] = anomaly_type

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT a.station_id, a.anomaly_date, a.anomaly_type, a.severity,
               a.duration_days, a.temp_deviation, a.precip_deviation,
               a.description, s.latitude, s.longitude, s.name as station_name,
               s.country
        FROM anomalies a
        JOIN stations s ON a.station_id = s.id
        WHERE {where}
        ORDER BY a.anomaly_date DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if format == "geojson":
        features = []
        for row in rows:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
                "properties": {
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
            })
        return {"type": "FeatureCollection", "features": features}

    columns = [
        "station_id", "station_name", "country", "latitude", "longitude",
        "anomaly_date", "anomaly_type", "severity", "duration_days",
        "temp_deviation", "precip_deviation", "description",
    ]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([getattr(row, col, None) for col in columns])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=anomalies_export.csv"},
        )

    records = []
    for row in rows:
        records.append({
            col: (getattr(row, col).isoformat() if col == "anomaly_date" and getattr(row, col) else getattr(row, col))
            for col in columns
        })
    return {"total_records": len(records), "data": records}

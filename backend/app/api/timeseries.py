"""
Time series data endpoints for station-level historical observations.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/timeseries/{station_id}")
async def get_station_timeseries(
    station_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    resolution: str = Query("daily", regex="^(daily|monthly|yearly)$"),
    limit: int = Query(3650, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
):
    """
    Get historical time-series observations for a station.
    Supports daily, monthly, or yearly resolution.
    """
    params = {
        "station_id": station_id,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
    }

    if resolution == "daily":
        query = text("""
            SELECT obs_date, tmax, tmin, prcp, tavg,
                   tmax_rolling_30d, tmin_rolling_30d, prcp_rolling_30d
            FROM observations
            WHERE station_id = :station_id
              AND obs_date >= COALESCE(:start_date, '1900-01-01'::date)
              AND obs_date <= COALESCE(:end_date, CURRENT_DATE)
            ORDER BY obs_date DESC
            LIMIT :limit
        """)
    elif resolution == "monthly":
        query = text("""
            SELECT DATE_TRUNC('month', obs_date)::date as obs_date,
                   AVG(tmax) as tmax, AVG(tmin) as tmin,
                   SUM(prcp) as prcp, AVG(tavg) as tavg,
                   AVG(tmax_rolling_30d) as tmax_rolling_30d,
                   AVG(tmin_rolling_30d) as tmin_rolling_30d,
                   AVG(prcp_rolling_30d) as prcp_rolling_30d
            FROM observations
            WHERE station_id = :station_id
              AND obs_date >= COALESCE(:start_date, '1900-01-01'::date)
              AND obs_date <= COALESCE(:end_date, CURRENT_DATE)
            GROUP BY DATE_TRUNC('month', obs_date)
            ORDER BY obs_date DESC
            LIMIT :limit
        """)
    else:  # yearly
        query = text("""
            SELECT DATE_TRUNC('year', obs_date)::date as obs_date,
                   AVG(tmax) as tmax, AVG(tmin) as tmin,
                   SUM(prcp) as prcp, AVG(tavg) as tavg,
                   AVG(tmax_rolling_30d) as tmax_rolling_30d,
                   AVG(tmin_rolling_30d) as tmin_rolling_30d,
                   AVG(prcp_rolling_30d) as prcp_rolling_30d
            FROM observations
            WHERE station_id = :station_id
              AND obs_date >= COALESCE(:start_date, '1900-01-01'::date)
              AND obs_date <= COALESCE(:end_date, CURRENT_DATE)
            GROUP BY DATE_TRUNC('year', obs_date)
            ORDER BY obs_date DESC
            LIMIT :limit
        """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found for this station")

    data = [
        {
            "obs_date": r.obs_date.isoformat(),
            "tmax": round(r.tmax, 2) if r.tmax is not None else None,
            "tmin": round(r.tmin, 2) if r.tmin is not None else None,
            "prcp": round(r.prcp, 2) if r.prcp is not None else None,
            "tavg": round(r.tavg, 2) if r.tavg is not None else None,
            "tmax_rolling_30d": round(r.tmax_rolling_30d, 2) if r.tmax_rolling_30d is not None else None,
            "tmin_rolling_30d": round(r.tmin_rolling_30d, 2) if r.tmin_rolling_30d is not None else None,
            "prcp_rolling_30d": round(r.prcp_rolling_30d, 2) if r.prcp_rolling_30d is not None else None,
        }
        for r in rows
    ]

    return {
        "station_id": station_id,
        "resolution": resolution,
        "total_records": len(data),
        "data": data,
    }

"""
Trend analysis API endpoints (Mann-Kendall, Sen's slope).
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/stations/{station_id}/trends")
async def get_station_trends(
    station_id: str,
    variable: Optional[str] = Query(None, pattern="^(tmax|tmin|prcp)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get trend analysis results for a station."""
    conditions = ["t.station_id = :station_id"]
    params = {"station_id": station_id}

    if variable:
        conditions.append("t.variable = :variable")
        params["variable"] = variable

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT t.variable, t.period_start, t.period_end, t.trend_direction,
               t.sens_slope, t.p_value, t.z_statistic, t.tau,
               t.slope_per_decade, t.ci_lower, t.ci_upper, t.significant
        FROM trend_analysis t
        WHERE {where}
        ORDER BY t.variable
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No trend data for this station")

    trends = [
        {
            "variable": r.variable,
            "period_start": r.period_start,
            "period_end": r.period_end,
            "trend_direction": r.trend_direction,
            "sens_slope": round(r.sens_slope, 6),
            "slope_per_decade": round(r.slope_per_decade, 4) if r.slope_per_decade else None,
            "p_value": round(r.p_value, 6),
            "z_statistic": round(r.z_statistic, 4) if r.z_statistic else None,
            "tau": round(r.tau, 4) if r.tau else None,
            "ci_lower": round(r.ci_lower, 4) if r.ci_lower else None,
            "ci_upper": round(r.ci_upper, 4) if r.ci_upper else None,
            "significant": r.significant,
        }
        for r in rows
    ]

    return {"station_id": station_id, "trends": trends}

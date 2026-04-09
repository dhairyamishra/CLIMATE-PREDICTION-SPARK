"""
Extreme value analysis API endpoints (GEV/GPD return periods).
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/stations/{station_id}/extremes")
async def get_station_extremes(
    station_id: str,
    variable: Optional[str] = Query(None, pattern="^(tmax|tmin|prcp)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get extreme value statistics and return periods for a station."""
    conditions = ["e.station_id = :station_id"]
    params = {"station_id": station_id}

    if variable:
        conditions.append("e.variable = :variable")
        params["variable"] = variable

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT e.variable, e.distribution, e.return_period, e.return_level,
               e.lower_ci, e.upper_ci, e.shape_param, e.location_param,
               e.scale_param, e.n_years
        FROM extreme_value_stats e
        WHERE {where}
        ORDER BY e.variable, e.return_period
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No extreme value data for this station")

    by_variable = {}
    for r in rows:
        var = r.variable
        if var not in by_variable:
            by_variable[var] = {
                "variable": var,
                "distribution": r.distribution,
                "shape": r.shape_param,
                "location": r.location_param,
                "scale": r.scale_param,
                "n_years": r.n_years,
                "return_levels": [],
            }
        by_variable[var]["return_levels"].append({
            "return_period": r.return_period,
            "return_level": round(r.return_level, 2),
            "lower_ci": round(r.lower_ci, 2) if r.lower_ci else None,
            "upper_ci": round(r.upper_ci, 2) if r.upper_ci else None,
        })

    return {"station_id": station_id, "extremes": list(by_variable.values())}

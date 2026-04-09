"""
Climate projection API endpoints (CMIP6 SSP scenarios).
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db

router = APIRouter()

VALID_SCENARIOS = ["ssp126", "ssp245", "ssp370", "ssp585"]


@router.get("/stations/{station_id}/projections")
async def get_station_projections(
    station_id: str,
    scenario: str = Query("ssp245", pattern="^(ssp126|ssp245|ssp370|ssp585)$"),
    variable: Optional[str] = Query(None, pattern="^(tmax|tmin|prcp)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get CMIP6 climate projections for a station under an SSP scenario."""
    conditions = [
        "p.station_id = :station_id",
        "p.scenario = :scenario",
    ]
    params = {"station_id": station_id, "scenario": scenario}

    if variable:
        conditions.append("p.variable = :variable")
        params["variable"] = variable

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT p.projection_date, p.variable, p.predicted_value,
               p.lower_bound, p.upper_bound, p.model_name, p.ensemble_size
        FROM climate_projections p
        WHERE {where}
        ORDER BY p.variable, p.projection_date
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No projection data for this station/scenario")

    by_variable = {}
    for r in rows:
        var = r.variable
        if var not in by_variable:
            by_variable[var] = []
        by_variable[var].append({
            "projection_date": r.projection_date.isoformat(),
            "predicted_value": r.predicted_value,
            "lower_bound": r.lower_bound,
            "upper_bound": r.upper_bound,
            "model_name": r.model_name,
        })

    return {
        "station_id": station_id,
        "scenario": scenario,
        "projections": by_variable,
    }


@router.get("/projections/scenarios")
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    """List available climate projection scenarios."""
    query = text("""
        SELECT scenario, COUNT(DISTINCT station_id) as station_count,
               COUNT(*) as total_points,
               MIN(projection_date) as start_date,
               MAX(projection_date) as end_date
        FROM climate_projections
        GROUP BY scenario
        ORDER BY scenario
    """)
    result = await db.execute(query)
    rows = result.fetchall()

    scenarios = [
        {
            "scenario": r.scenario,
            "station_count": r.station_count,
            "total_points": r.total_points,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
        }
        for r in rows
    ]

    descriptions = {
        "ssp126": "SSP1-2.6: Sustainability — low emissions, 1.8C by 2100",
        "ssp245": "SSP2-4.5: Middle of the road — moderate emissions, 2.7C by 2100",
        "ssp370": "SSP3-7.0: Regional rivalry — high emissions, 3.6C by 2100",
        "ssp585": "SSP5-8.5: Fossil-fueled development — very high emissions, 4.4C by 2100",
    }

    return {
        "available": VALID_SCENARIOS,
        "descriptions": descriptions,
        "data": scenarios,
    }

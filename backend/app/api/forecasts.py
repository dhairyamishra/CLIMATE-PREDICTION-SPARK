"""
Forecast API endpoints.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db

router = APIRouter()


@router.get("/stations/{station_id}/forecast")
async def get_station_forecast(
    station_id: str,
    variable: Optional[str] = Query(None, regex="^(tmax|tmin|prcp)$"),
    model_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get forecast data for a specific station."""
    conditions = ["f.station_id = :station_id"]
    params = {"station_id": station_id}

    if variable:
        conditions.append("f.variable = :variable")
        params["variable"] = variable

    if model_type:
        conditions.append("f.model_type = :model_type")
        params["model_type"] = model_type

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT f.forecast_date, f.variable, f.predicted_value,
               f.lower_bound, f.upper_bound, f.model_type,
               f.model_version, f.mae, f.rmse
        FROM forecasts f
        WHERE {where_clause}
        ORDER BY f.variable, f.forecast_date
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No forecasts found for this station")

    forecasts_by_var = {}
    for r in rows:
        var = r.variable
        if var not in forecasts_by_var:
            forecasts_by_var[var] = []
        forecasts_by_var[var].append({
            "forecast_date": r.forecast_date.isoformat(),
            "predicted_value": r.predicted_value,
            "lower_bound": r.lower_bound,
            "upper_bound": r.upper_bound,
            "model_type": r.model_type,
            "model_version": r.model_version,
        })

    return {
        "station_id": station_id,
        "forecasts": forecasts_by_var,
    }

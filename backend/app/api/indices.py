"""
Climate indices API endpoints (ENSO, NAO, PDO, AMO, IOD).
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.cache import response_cache

router = APIRouter()

INDEX_DESCRIPTIONS = {
    "oni": "Oceanic Nino Index — 3-month running mean of SST anomalies in Nino 3.4 region",
    "nao": "North Atlantic Oscillation — pressure difference between Azores High and Icelandic Low",
    "pdo": "Pacific Decadal Oscillation — leading PC of North Pacific monthly SST variability",
    "amo": "Atlantic Multidecadal Oscillation — detrended North Atlantic SST anomalies",
    "iod": "Indian Ocean Dipole — SST gradient across the tropical Indian Ocean",
}


@router.get("/indices")
async def list_indices(db: AsyncSession = Depends(get_db)):
    """List all available climate indices with their latest values."""
    cached = await response_cache.get("indices_list")
    if cached is not None:
        return cached

    query = text("""
        SELECT DISTINCT ON (index_name)
            index_name, value, index_date, source
        FROM climate_indices
        ORDER BY index_name, index_date DESC
    """)
    result = await db.execute(query)
    rows = result.fetchall()

    indices = []
    for r in rows:
        indices.append({
            "index_name": r.index_name,
            "latest_value": r.value,
            "latest_date": r.index_date.isoformat() if r.index_date else None,
            "source": r.source,
            "description": INDEX_DESCRIPTIONS.get(r.index_name.lower(), ""),
        })

    response = {"indices": indices, "available": list(INDEX_DESCRIPTIONS.keys())}
    await response_cache.set("indices_list", response, ttl=120)
    return response


@router.get("/indices/{index_name}")
async def get_index_series(
    index_name: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(600, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Get time series for a specific climate index."""
    index_lower = index_name.lower()
    if index_lower not in INDEX_DESCRIPTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown index: {index_name}")

    conditions = ["LOWER(index_name) = :index_name"]
    params = {"index_name": index_lower, "limit": limit}

    if start_date:
        conditions.append("index_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("index_date <= :end_date")
        params["end_date"] = end_date

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT index_date, index_name, value, anomaly, source
        FROM climate_indices
        WHERE {where}
        ORDER BY index_date DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    data = [
        {
            "index_date": r.index_date.isoformat(),
            "value": r.value,
            "anomaly": r.anomaly,
        }
        for r in rows
    ]

    return {
        "index_name": index_lower,
        "description": INDEX_DESCRIPTIONS[index_lower],
        "data": list(reversed(data)),
        "total_records": len(data),
    }

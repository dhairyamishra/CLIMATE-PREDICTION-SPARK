"""
Global summary and dashboard statistics endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter()


@router.get("/summary")
async def get_global_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get global dashboard statistics."""
    stats_query = text("""
        SELECT
            (SELECT COUNT(*) FROM stations) as total_stations,
            (SELECT COUNT(*) FROM anomalies) as total_anomalies,
            (SELECT COUNT(*) FROM anomalies WHERE anomaly_type = 'heatwave') as heatwave_count,
            (SELECT COUNT(*) FROM anomalies WHERE anomaly_type = 'cold_snap') as cold_snap_count,
            (SELECT COUNT(*) FROM anomalies WHERE anomaly_type = 'precip_extreme') as precip_extreme_count,
            (SELECT COALESCE(AVG(severity), 0) FROM anomalies) as avg_severity
    """)
    result = await db.execute(stats_query)
    stats = result.fetchone()

    top_regions_query = text("""
        SELECT s.country, COUNT(*) as anomaly_count,
               AVG(a.severity) as avg_severity
        FROM anomalies a
        JOIN stations s ON a.station_id = s.id
        WHERE s.country IS NOT NULL
        GROUP BY s.country
        ORDER BY anomaly_count DESC
        LIMIT 10
    """)
    regions_result = await db.execute(top_regions_query)
    regions = regions_result.fetchall()

    monthly_query = text("""
        SELECT year, month, total_anomalies, heatwave_count,
               cold_snap_count, precip_extreme_count, avg_severity,
               global_temp_anomaly
        FROM monthly_summary
        ORDER BY year DESC, month DESC
        LIMIT 120
    """)
    monthly_result = await db.execute(monthly_query)
    monthly = monthly_result.fetchall()

    return {
        "total_stations": stats.total_stations,
        "total_anomalies": stats.total_anomalies,
        "heatwave_count": stats.heatwave_count,
        "cold_snap_count": stats.cold_snap_count,
        "precip_extreme_count": stats.precip_extreme_count,
        "avg_severity": round(stats.avg_severity, 4) if stats.avg_severity else 0,
        "top_regions": [
            {
                "country": r.country,
                "anomaly_count": r.anomaly_count,
                "avg_severity": round(r.avg_severity, 4),
            }
            for r in regions
        ],
        "monthly_trend": [
            {
                "year": m.year,
                "month": m.month,
                "total_anomalies": m.total_anomalies,
                "heatwave_count": m.heatwave_count,
                "cold_snap_count": m.cold_snap_count,
                "precip_extreme_count": m.precip_extreme_count,
                "avg_severity": round(m.avg_severity, 4) if m.avg_severity else 0,
                "global_temp_anomaly": m.global_temp_anomaly,
            }
            for m in monthly
        ],
    }

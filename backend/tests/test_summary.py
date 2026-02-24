"""
Tests for the /api/summary endpoint.
Requires PostGIS — marked as integration tests.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_summary_data(db_session):
    """Insert monthly summary records for testing."""
    for month in range(1, 13):
        await db_session.execute(text(
            "INSERT INTO monthly_summary (year, month, total_anomalies, heatwave_count, "
            "cold_snap_count, precip_extreme_count, avg_severity) "
            "VALUES (:year, :month, :total, :hw, :cs, :pe, :sev)"
        ), {
            "year": 2020,
            "month": month,
            "total": 10 + month,
            "hw": 4 + (month % 3),
            "cs": 3 + (month % 2),
            "pe": 3,
            "sev": 0.5 + month * 0.02,
        })
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_summary_empty(client):
    """Returns summary even with no data."""
    response = await client.get("/api/summary")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_summary_with_data(client, db_session):
    """Returns summary statistics."""
    await _seed_summary_data(db_session)
    response = await client.get("/api/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_anomalies" in data or "monthly_trend" in data

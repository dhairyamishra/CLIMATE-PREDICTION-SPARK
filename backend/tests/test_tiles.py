"""
Tests for the /api/tiles endpoint.
Requires PostGIS — marked as integration tests.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_tile_data(db_session):
    """Insert anomaly tile records for testing."""
    for i in range(5):
        await db_session.execute(text(
            "INSERT INTO anomaly_tiles (geohash, tile_date, anomaly_count, avg_severity, "
            "dominant_type, heatwave_count, cold_snap_count, precip_extreme_count, "
            "center_lat, center_lon, geom) "
            "VALUES (:gh, :td, :ac, :sev, :dt, :hw, :cs, :pe, :lat, :lon, "
            "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))"
        ), {
            "gh": f"dr5r{i}",
            "td": f"2020-0{i+1}-01",
            "ac": 10 + i * 5,
            "sev": 0.4 + i * 0.1,
            "dt": "heatwave",
            "hw": 5 + i,
            "cs": 3,
            "pe": 2 + i,
            "lat": 40.0 + i * 0.5,
            "lon": -74.0 + i * 0.5,
        })
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_tiles_empty(client):
    """Returns result from tiles endpoint."""
    response = await client.get("/api/tiles")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_tiles_with_data(client, db_session):
    """Returns tile data."""
    await _seed_tile_data(db_session)
    response = await client.get("/api/tiles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5

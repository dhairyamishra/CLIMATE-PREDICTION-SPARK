"""
Tests for the /api/stations endpoints.
Requires PostGIS — marked as integration tests.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_stations(db_session, count=3):
    """Insert test stations into PostGIS."""
    for i in range(count):
        await db_session.execute(text(
            "INSERT INTO stations "
            "(id, name, latitude, longitude, elevation, country, state, geohash, geom, first_year, last_year, record_count) "
            "VALUES (:id, :name, :lat, :lon, :elev, :country, :state, :geohash, "
            "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :fy, :ly, :rc) "
            "ON CONFLICT (id) DO NOTHING"
        ), {
            "id": f"TEST{i:06d}",
            "name": f"Test Station {i}",
            "lat": 40.0 + i,
            "lon": -74.0 + i,
            "elev": 100.0 * i,
            "country": "US",
            "state": "NY",
            "geohash": f"dr5r{i}",
            "fy": 1970,
            "ly": 2020,
            "rc": 1000 * (i + 1),
        })
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_stations_empty(client):
    """Returns list (possibly empty) from stations endpoint."""
    response = await client.get("/api/stations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_stations_with_data(client, db_session):
    """Returns stations when data exists."""
    await _seed_stations(db_session, count=3)
    response = await client.get("/api/stations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    # Check structure
    station = data[0]
    assert "id" in station
    assert "name" in station
    assert "latitude" in station
    assert "longitude" in station


@pytest.mark.asyncio
async def test_get_stations_limit(client, db_session):
    """Respects limit parameter."""
    await _seed_stations(db_session, count=5)
    response = await client.get("/api/stations?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2


@pytest.mark.asyncio
async def test_get_station_detail(client, db_session):
    """Returns single station detail by ID."""
    await _seed_stations(db_session, count=1)
    response = await client.get("/api/stations/TEST000000")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "TEST000000"
    assert data["name"] == "Test Station 0"


@pytest.mark.asyncio
async def test_get_station_not_found(client):
    """Returns 404 for nonexistent station."""
    response = await client.get("/api/stations/NONEXISTENT_STATION_999")
    assert response.status_code == 404

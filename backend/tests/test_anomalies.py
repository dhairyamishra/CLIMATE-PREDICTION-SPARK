"""
Tests for the /api/anomalies endpoint.
Requires PostGIS — marked as integration tests.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_anomaly_data(db_session):
    """Insert stations and anomalies into PostGIS."""
    await db_session.execute(text(
        "INSERT INTO stations (id, name, latitude, longitude, elevation, country, state, geohash, geom, record_count) "
        "VALUES ('ANOM001', 'Anomaly Test Station', 40.7, -74.0, 10.0, 'US', 'NY', 'dr5ru', "
        "ST_SetSRID(ST_MakePoint(-74.0, 40.7), 4326), 5000) "
        "ON CONFLICT (id) DO NOTHING"
    ))

    for i in range(5):
        atype = ["heatwave", "cold_snap", "precip_extreme"][i % 3]
        await db_session.execute(text(
            "INSERT INTO anomalies (station_id, anomaly_date, anomaly_type, severity, duration_days, "
            "temp_deviation, precip_deviation, description, geom) "
            "VALUES (:sid, :adate, :atype, :sev, :dur, :td, :pd, :desc, "
            "ST_SetSRID(ST_MakePoint(-74.0, 40.7), 4326))"
        ), {
            "sid": "ANOM001",
            "adate": f"2020-07-{10 + i:02d}",
            "atype": atype,
            "sev": 0.5 + i * 0.1,
            "dur": i + 1,
            "td": 2.5 + i * 0.5 if atype != "precip_extreme" else None,
            "pd": 3.0 + i if atype == "precip_extreme" else None,
            "desc": f"Test anomaly {i}",
        })
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_anomalies_returns_geojson(client):
    """Returns GeoJSON FeatureCollection structure."""
    response = await client.get("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)


@pytest.mark.asyncio
async def test_get_anomalies_with_data(client, db_session):
    """Returns GeoJSON features with anomaly data."""
    await _seed_anomaly_data(db_session)
    response = await client.get("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 5


@pytest.mark.asyncio
async def test_get_anomalies_filter_type(client, db_session):
    """Filters by anomaly type."""
    await _seed_anomaly_data(db_session)
    response = await client.get("/api/anomalies?anomaly_type=heatwave")
    assert response.status_code == 200
    data = response.json()
    for f in data["features"]:
        assert f["properties"]["anomaly_type"] == "heatwave"


@pytest.mark.asyncio
async def test_get_anomalies_filter_severity(client, db_session):
    """Filters by minimum severity."""
    await _seed_anomaly_data(db_session)
    response = await client.get("/api/anomalies?min_severity=0.8")
    assert response.status_code == 200
    data = response.json()
    for f in data["features"]:
        assert f["properties"]["severity"] >= 0.8


@pytest.mark.asyncio
async def test_get_anomalies_filter_bbox(client, db_session):
    """Filters by bounding box."""
    await _seed_anomaly_data(db_session)
    response = await client.get("/api/anomalies?min_lat=40&max_lat=41&min_lon=-75&max_lon=-73")
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) >= 5

    response = await client.get("/api/anomalies?min_lat=0&max_lat=1&min_lon=0&max_lon=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) == 0


@pytest.mark.asyncio
async def test_get_anomalies_limit(client, db_session):
    """Respects limit parameter."""
    await _seed_anomaly_data(db_session)
    response = await client.get("/api/anomalies?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) <= 2


@pytest.mark.asyncio
async def test_get_anomalies_geojson_structure(client, db_session):
    """Validates GeoJSON feature structure."""
    await _seed_anomaly_data(db_session)
    response = await client.get("/api/anomalies?limit=1")
    data = response.json()
    assert len(data["features"]) >= 1
    feature = data["features"][0]

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert len(feature["geometry"]["coordinates"]) == 2
    props = feature["properties"]
    assert "station_id" in props
    assert "anomaly_type" in props
    assert "severity" in props
    assert "anomaly_date" in props

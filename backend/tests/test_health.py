"""
Tests for the health check endpoint.
No PostGIS required — uses clean_client fixture.
"""
import pytest


@pytest.mark.asyncio
async def test_health_endpoint(clean_client):
    """Health check returns 200 with service info."""
    response = await clean_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "climate-anomaly-engine"
    assert "database" in data


@pytest.mark.asyncio
async def test_openapi_docs(clean_client):
    """OpenAPI schema is accessible."""
    response = await clean_client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Climate Anomaly Detection & Forecasting Engine"
    assert "/api/anomalies" in data["paths"]
    assert "/api/stations" in data["paths"]
    assert "/api/tiles" in data["paths"]
    assert "/api/summary" in data["paths"]
    assert "/health" in data["paths"]

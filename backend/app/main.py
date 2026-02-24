"""
Climate Anomaly Detection & Forecasting Engine - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.api import anomalies, stations, forecasts, tiles, timeseries, summary

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Climate Anomaly Detection & Forecasting Engine",
    description=(
        "API for exploring 100+ years of global climate data, "
        "detecting anomalous events, and forecasting future conditions."
    ),
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(anomalies.router, prefix="/api", tags=["Anomalies"])
app.include_router(stations.router, prefix="/api", tags=["Stations"])
app.include_router(forecasts.router, prefix="/api", tags=["Forecasts"])
app.include_router(tiles.router, prefix="/api", tags=["Tiles"])
app.include_router(timeseries.router, prefix="/api", tags=["Time Series"])
app.include_router(summary.router, prefix="/api", tags=["Summary"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "climate-anomaly-engine"}

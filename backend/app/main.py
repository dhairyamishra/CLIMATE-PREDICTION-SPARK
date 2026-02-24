"""
Climate Anomaly Detection & Forecasting Engine - FastAPI Application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from sqlalchemy import text as sa_text

from app.core.config import get_settings
from app.core.database import engine, Base
from app.models import orm  # noqa: F401 — register ORM models with Base
from app.api import anomalies, stations, forecasts, tiles, timeseries, summary

logger = logging.getLogger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure DB tables exist. Shutdown: dispose engine."""
    logger.info("Starting Climate Anomaly Engine API...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created.")
    except Exception as e:
        logger.warning(f"DB init skipped (tables may already exist via init.sql): {e}")
    yield
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Climate Anomaly Detection & Forecasting Engine",
    description=(
        "API for exploring 100+ years of global climate data, "
        "detecting anomalous events, and forecasting future conditions."
    ),
    version="1.0.0",
    lifespan=lifespan,
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
    """Health check with DB connectivity test."""
    db_status = "unknown"
    try:
        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "service": "climate-anomaly-engine",
        "database": db_status,
    }

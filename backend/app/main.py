"""
Climate Anomaly Detection & Forecasting Engine - FastAPI Application
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

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

# --- Production middleware stack (order matters: last added = first executed) ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)

# GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured request logging with timing and request IDs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        start = time.perf_counter()

        response: Response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"

        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={"request_id": request_id},
        )
        return response


app.add_middleware(RequestLoggingMiddleware)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add Cache-Control headers based on endpoint."""

    CACHE_RULES = {
        "/api/summary": "public, max-age=60, stale-while-revalidate=120",
        "/api/tiles": "public, max-age=30, stale-while-revalidate=60",
        "/api/stations": "public, max-age=300, stale-while-revalidate=600",
        "/api/anomalies": "public, max-age=30, stale-while-revalidate=60",
    }

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.method == "GET" and response.status_code == 200:
            for prefix, directive in self.CACHE_RULES.items():
                if request.url.path.startswith(prefix):
                    response.headers["Cache-Control"] = directive
                    break
            else:
                response.headers["Cache-Control"] = "no-cache"
        return response


app.add_middleware(CacheControlMiddleware)

app.include_router(anomalies.router, prefix="/api", tags=["Anomalies"])
app.include_router(stations.router, prefix="/api", tags=["Stations"])
app.include_router(forecasts.router, prefix="/api", tags=["Forecasts"])
app.include_router(tiles.router, prefix="/api", tags=["Tiles"])
app.include_router(timeseries.router, prefix="/api", tags=["Time Series"])
app.include_router(summary.router, prefix="/api", tags=["Summary"])


_start_time = time.monotonic()


@app.get("/health")
async def health_check():
    """Health check with DB connectivity, pool stats, and uptime."""
    db_status = "unknown"
    db_latency_ms = None
    try:
        t0 = time.perf_counter()
        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
            db_status = "connected"
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:
        db_status = f"disconnected: {type(exc).__name__}"

    pool = engine.pool
    uptime_s = time.monotonic() - _start_time

    from app.core.cache import response_cache

    return {
        "status": "healthy",
        "service": "climate-anomaly-engine",
        "version": "1.0.0",
        "uptime_seconds": round(uptime_s),
        "database": db_status,
        "db_latency_ms": db_latency_ms,
        "pool": {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        },
        "cache_entries": response_cache.size,
    }

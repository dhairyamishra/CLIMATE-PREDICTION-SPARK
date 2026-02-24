"""
Test fixtures for the FastAPI backend.

Two modes:
  - Unit tests (default): Use httpx AsyncClient against the FastAPI app.
    DB calls hit real PostGIS if POSTGRES_TEST_URL is set, otherwise tests
    that require DB are skipped.
  - Integration tests (marked @pytest.mark.integration): Require a running
    PostGIS instance.

Run unit tests:      pytest backend/tests/ -m "not integration"
Run integration:     POSTGRES_TEST_URL=postgresql+asyncpg://... pytest backend/tests/ -m integration
Run all:             POSTGRES_TEST_URL=postgresql+asyncpg://... pytest backend/tests/
"""
import os
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.main import app

POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_URL",
    "postgresql+asyncpg://climate:climate_secret@localhost:5432/climate_db",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires running PostGIS")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def pg_engine():
    """Create a test engine connected to PostGIS."""
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(pg_engine):
    """DB session backed by real PostGIS."""
    session_factory = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(pg_engine):
    """Async test client with DB dependency overridden to use test PostGIS."""
    session_factory = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def clean_client():
    """Lightweight client that doesn't require PostGIS — for testing
    endpoints that don't hit the database (e.g. /health)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

from __future__ import annotations

"""Pytest configuration and fixtures for backend tests.

Important:
- Keep module import side-effects minimal so unit tests can run without
  requiring DB/env configuration.
- Integration fixtures lazily import app + DB config when actually used.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio


def _build_test_db_url() -> str:
    from app.core.config import settings

    if not getattr(settings, "database_url", None):
        raise RuntimeError("settings.database_url is not configured")

    return settings.database_url.replace("postgresql://", "postgresql+asyncpg://") + "_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator["AsyncSession", None]:
    """Create a fresh database session for each test."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
        from sqlalchemy.pool import NullPool
        from app.core.database import Base
    except Exception as e:
        pytest.skip(f"DB test dependencies not available: {e}")

    try:
        test_db_url = _build_test_db_url()
    except Exception as e:
        pytest.skip(f"Database not configured for tests: {e}")

    test_engine = create_async_engine(test_db_url, echo=False, poolclass=NullPool)
    TestAsyncSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: "AsyncSession") -> AsyncGenerator["AsyncClient", None]:
    """Create an async HTTP client for testing."""
    try:
        from httpx import AsyncClient
        from app.main import app
        from app.core.database import get_db
    except Exception as e:
        pytest.skip(f"App test dependencies not available: {e}")
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


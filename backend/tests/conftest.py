"""
Pytest configuration and fixtures for backend tests
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings


# Test database URL
TEST_DATABASE_URL = settings.database_url.replace("postgresql://", "postgresql+asyncpg://") + "_test"

# Create async engine for testing
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool
)

# Create async session factory
TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()
    
    async with test_engine.begin() as conn:
        # Drop all tables after test
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    
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

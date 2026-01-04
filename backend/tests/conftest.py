from __future__ import annotations

"""Pytest configuration and fixtures for backend tests.

Important:
- Keep module import side-effects minimal so unit tests can run without
  requiring DB/env configuration.
- Integration fixtures lazily import app + DB config when actually used.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio

# Add /app to Python path for imports to work in docker container
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

_ENSURED_TEST_DATABASES: set[str] = set()


def _sqlalchemy_url_to_asyncpg_dsn(url) -> str:
    """Render a SQLAlchemy URL into a DSN asyncpg can use.

    NOTE: str(URL) hides passwords (prints '***'), so always render with
    hide_password=False.
    """
    return url.render_as_string(hide_password=False)


def _load_test_env_from_dotenv() -> None:
    """Load backend/.env for pytest runs.

    Our app settings are environment-driven. When running pytest directly on a
    developer machine, the shell might not have DATABASE_URL exported.
    """
    dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    if not dotenv_path.exists():
        return

    try:
        from dotenv import dotenv_values
    except Exception:
        return

    # We intentionally override DB-related variables for pytest.
    # Reason: developers may have a lingering exported DATABASE_URL, and we want
    # tests to run against the repo's configured dev DB.
    values = dotenv_values(dotenv_path)

    raw_database_url = values.get("DATABASE_URL")
    if raw_database_url:
        # Normalize + optionally rewrite host for local (non-docker) runs.
        try:
            from sqlalchemy.engine import make_url
        except Exception:
            make_url = None

        normalized = raw_database_url
        if make_url is not None:
            try:
                url = make_url(raw_database_url)
                if url.drivername == "postgresql":
                    url = url.set(drivername="postgresql+asyncpg")

                running_in_docker = Path("/.dockerenv").exists()
                if not running_in_docker and url.host:
                    # In compose, the DB host is often the service name (e.g., postgres).
                    # When running pytest on the host machine, that name won't resolve;
                    # use localhost (port mapping) instead.
                    try:
                        import socket

                        socket.getaddrinfo(url.host, None)
                    except Exception:
                        if url.host == "postgres":
                            url = url.set(host="localhost")

                normalized = str(url)
                # IMPORTANT: str(URL) hides the password as '***'.
                # We must render with hide_password=False for an actual DSN.
                normalized = url.render_as_string(hide_password=False)
            except Exception:
                normalized = raw_database_url

        os.environ["DATABASE_URL"] = normalized

    # Also override legacy DB_* variables if present; some environments rely on them.
    for key in ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"):
        if values.get(key) is not None:
            os.environ[key] = str(values[key])

    # Optional: align POSTGRES_* env vars too (used by compose/init scripts).
    for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        if values.get(key) is not None:
            os.environ[key] = str(values[key])


_load_test_env_from_dotenv()


@pytest_asyncio.fixture(scope="function")
async def functional_client(tmp_path: Path) -> AsyncGenerator["AsyncClient", None]:
    """Async HTTP client for functional tests.

    Goal: run inside containers without requiring a dedicated test database.
    We override auth + DB dependencies so endpoint wiring can be validated even
    when DB/LLM are not configured.
    """

    # Ensure any import-time global services (like ChatAttachmentService) write
    # into a per-test, writable directory.
    chat_dir = str(tmp_path / "chat_attachments")
    # Always override (not setdefault): unit tests may have already imported settings.
    os.environ["CHAT_ATTACHMENT_DIR"] = chat_dir
    try:
        from app.core.config import settings

        settings.chat_attachment_dir = chat_dir
    except Exception:
        # If settings import fails, the subsequent imports will raise with context.
        pass

    try:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from app.api.v1.agent import router as agent_router
        from app.core.database import get_db
        from app.core.dependencies import get_current_user
    except Exception as e:
        raise RuntimeError(f"Functional test import failed: {e}") from e

    app = FastAPI()
    app.include_router(agent_router)

    class _DummyUser:
        emp_no = "000000"
        is_active = True
        is_admin = True
        username = "test"

    async def override_get_db():
        yield None

    async def override_get_current_user():
        return _DummyUser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def _build_test_db_url() -> str:
    from app.core.config import settings

    if not getattr(settings, "database_url", None):
        raise RuntimeError("settings.database_url is not configured")

    base_url = settings.database_url
    # Normalize to asyncpg driver URL for SQLAlchemy AsyncEngine.
    if base_url.startswith("postgresql://"):
        base_url = base_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return base_url + "_test"


async def _ensure_database_exists(database_url: str) -> None:
    """Ensure the target database exists.

    When DATABASE_URL points at a Postgres database that doesn't exist (common
    with *_test), asyncpg raises InvalidCatalogNameError. We create it by
    connecting to the server's default 'postgres' database.
    """
    if database_url in _ENSURED_TEST_DATABASES:
        return

    try:
        from sqlalchemy.engine import make_url
    except Exception as e:
        raise RuntimeError(f"SQLAlchemy URL parser not available: {e}") from e

    try:
        import asyncpg
    except Exception as e:
        raise RuntimeError(f"asyncpg not available: {e}") from e

    url = make_url(database_url)
    target_db = url.database
    if not target_db:
        raise RuntimeError("DATABASE_URL is missing database name")

    # asyncpg DSN must not include the '+asyncpg' dialect marker.
    admin_url = url.set(drivername="postgresql").set(database="postgres")
    target_db_ident = '"' + target_db.replace('"', '""') + '"'

    conn = await asyncpg.connect(_sqlalchemy_url_to_asyncpg_dsn(admin_url))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", target_db)
        if not exists:
            await conn.execute(f"CREATE DATABASE {target_db_ident}")
    finally:
        await conn.close()

    _ENSURED_TEST_DATABASES.add(database_url)


async def _ensure_schema_exists(database_url: str, schema_name: str) -> None:
    """Create an isolated schema in an existing database.

    This is a fallback when we cannot connect to the server's maintenance DB
    (often 'postgres') to create a dedicated *_test database.
    """
    try:
        from sqlalchemy.engine import make_url
        import asyncpg
    except Exception as e:
        raise RuntimeError(f"Dependencies not available for schema setup: {e}") from e

    url = make_url(database_url)
    if not url.database:
        raise RuntimeError("DATABASE_URL is missing database name")

    dsn_url = url.set(drivername="postgresql")
    conn = await asyncpg.connect(_sqlalchemy_url_to_asyncpg_dsn(dsn_url))
    try:
        schema_ident = '"' + schema_name.replace('"', '""') + '"'
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_ident}")
        # Install pgvector extension if needed (required for vector columns)
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()


async def _drop_schema(database_url: str, schema_name: str) -> None:
    try:
        from sqlalchemy.engine import make_url
        import asyncpg
    except Exception:
        return

    url = make_url(database_url)
    if not url.database:
        return

    dsn_url = url.set(drivername="postgresql")
    conn = await asyncpg.connect(_sqlalchemy_url_to_asyncpg_dsn(dsn_url))
    try:
        schema_ident = '"' + schema_name.replace('"', '""') + '"'
        await conn.execute(f"DROP SCHEMA IF EXISTS {schema_ident} CASCADE")
    finally:
        await conn.close()


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
        from sqlalchemy import text
        from app.core.database import Base
    except Exception as e:
        pytest.skip(f"DB test dependencies not available: {e}")

    from app.core.config import settings

    schema_name: str | None = None
    engine_db_url: str | None = None
    connect_args = None

    base_url = getattr(settings, "database_url", None)
    if not base_url:
        pytest.skip("settings.database_url is not configured")

    if base_url.startswith("postgresql://"):
        base_url = base_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Default: use schema-isolation in the configured DB (dev DB).
    # Opt-in to dedicated *_test DB creation by setting PYTEST_DB_MODE=testdb.
    db_mode = os.getenv("PYTEST_DB_MODE", "simple").lower().strip()
    if db_mode == "testdb":
        test_db_url = _build_test_db_url()
        try:
            await _ensure_database_exists(test_db_url)
        except Exception as e:
            pytest.skip(f"Test database could not be created/used: {e}")
        engine_db_url = test_db_url
    elif db_mode == "schema":
        # Create isolated schema per test
        schema_name = f"pytest_{uuid4().hex}"  # per-test schema
        try:
            await _ensure_schema_exists(base_url, schema_name)
        except Exception as schema_err:
            pytest.skip(f"Schema isolation failed: {schema_err}")

        engine_db_url = base_url
        connect_args = {"server_settings": {"search_path": schema_name}}
    else:
        # "simple" mode: use dev DB directly (no isolation, fastest)
        engine_db_url = base_url
        connect_args = {}

    test_engine = create_async_engine(
        engine_db_url,
        echo=False,
        poolclass=NullPool,
        connect_args=connect_args,
    )
    TestAsyncSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # Only create tables for isolated modes; simple mode uses existing dev DB tables
    if db_mode != "simple":
        async with test_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()

    await test_engine.dispose()

    if schema_name is not None and engine_db_url is not None:
        await _drop_schema(engine_db_url, schema_name)

    if schema_name is None:
        # Dedicated test DB mode: best-effort cleanup.
        try:
            test_engine_cleanup = create_async_engine(engine_db_url, echo=False, poolclass=NullPool)
            async with test_engine_cleanup.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await test_engine_cleanup.dispose()
        except Exception:
            pass


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: "AsyncSession") -> AsyncGenerator["AsyncClient", None]:
    """Create an async HTTP client for testing."""
    try:
        from httpx import ASGITransport, AsyncClient
        from app.main import app
        from app.core.database import get_db
    except Exception as e:
        pytest.skip(f"App test dependencies not available: {e}")
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client_with_admin(db_session: "AsyncSession") -> AsyncGenerator["AsyncClient", None]:
    """Create an async HTTP client for testing with admin user."""
    try:
        from httpx import AsyncClient
        from app.main import app
        from app.core.database import get_db
        from app.core.dependencies import get_current_user
    except Exception as e:
        pytest.skip(f"App test dependencies not available: {e}")
    
    class _AdminUser:
        emp_no = "admin001"
        is_active = True
        is_admin = True
        username = "admin"
    
    async def override_get_db():
        yield db_session
    
    async def override_get_current_user():
        return _AdminUser()
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


"""Shared LangGraph checkpointer selection for PPT flows.

Phase 2 requirement in 01.docs/13.2.PPT_Agent_LangGraph_Production_Upgrade.md:
- Prefer Postgres-based persistence for production (single DB).
- Keep SQLite fallback for local/dev if Postgres checkpointer isn't available.

Env vars:
- PPT_CHECKPOINTER_BACKEND: "postgres" | "sqlite" | "none" (default: "postgres")
- PPT_CHECKPOINTER_DB_URL: override Postgres URL (preferred, psycopg format)
- DATABASE_URL: fallback source (will be converted from postgresql+asyncpg)
- PPT_GRAPH_CHECKPOINT_DIR: sqlite fallback directory (default: /app/tmp)
- PPT_CHECKPOINTER_PG_POOL_MAX_SIZE: pool size (default: 5)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from loguru import logger

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except Exception:  # pragma: no cover
    PostgresSaver = None  # type: ignore

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except Exception:  # pragma: no cover
    AsyncPostgresSaver = None  # type: ignore

try:
    from psycopg_pool import ConnectionPool
except Exception:  # pragma: no cover
    ConnectionPool = None  # type: ignore

try:
    from psycopg_pool import AsyncConnectionPool
except Exception:  # pragma: no cover
    AsyncConnectionPool = None  # type: ignore

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except Exception:  # pragma: no cover
    SqliteSaver = None  # type: ignore

import sqlite3


_PG_POOL: Optional[Any] = None
_PG_SAVER: Optional[Any] = None
_PG_SETUP_STARTED: bool = False
_SQLITE_CONN: Optional[sqlite3.Connection] = None
_SQLITE_SAVER: Optional[Any] = None


def _ensure_async_setup_started(saver: Any) -> None:
    """Ensure async saver.setup() runs once.

    This module is imported during app startup (typically outside a running loop),
    but may also be imported lazily. We support both cases:
    - if a loop is running: schedule a background task
    - otherwise: run to completion synchronously
    """
    global _PG_SETUP_STARTED
    if _PG_SETUP_STARTED:
        return
    _PG_SETUP_STARTED = True

    setup_coro = getattr(saver, "setup", None)
    if setup_coro is None:
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(saver.setup())
        logger.info("✅ PPT checkpointer: Postgres async setup scheduled")
    except RuntimeError:
        # No running loop
        asyncio.run(saver.setup())
        logger.info("✅ PPT checkpointer: Postgres async setup completed")


def _normalize_pg_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u

    # SQLAlchemy async URL -> psycopg URL
    if u.startswith("postgresql+asyncpg://"):
        u = "postgresql://" + u[len("postgresql+asyncpg://") :]
    if u.startswith("postgresql+psycopg2://"):
        u = "postgresql://" + u[len("postgresql+psycopg2://") :]

    return u


def _get_pg_url() -> Optional[str]:
    url = os.getenv("PPT_CHECKPOINTER_DB_URL") or os.getenv("PPT_GRAPH_CHECKPOINT_DB_URL")
    if not url:
        url = os.getenv("DATABASE_URL")
    url = _normalize_pg_url(url or "")
    return url or None


def _get_sqlite_saver() -> Optional[Any]:
    if SqliteSaver is None:
        return None

    global _SQLITE_CONN, _SQLITE_SAVER
    if _SQLITE_SAVER is not None:
        return _SQLITE_SAVER

    tmp_dir = os.getenv("PPT_GRAPH_CHECKPOINT_DIR", "/app/tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    db_path = os.path.join(tmp_dir, "ppt_graph_checkpoints.sqlite")

    if _SQLITE_CONN is None:
        _SQLITE_CONN = sqlite3.connect(db_path, check_same_thread=False)

    saver = SqliteSaver(_SQLITE_CONN)
    try:
        saver.setup()
    except Exception:
        pass

    _SQLITE_SAVER = saver
    return saver


def _get_postgres_saver() -> Optional[Any]:
    # Prefer async Postgres saver when available (required for graphs executed via ainvoke).
    if AsyncPostgresSaver is None or AsyncConnectionPool is None:
        if PostgresSaver is None or ConnectionPool is None:
            return None
        logger.warning(
            "⚠️ PPT checkpointer: async Postgres saver unavailable; falling back to sync saver (may break async graphs)"
        )

    if PostgresSaver is None and AsyncPostgresSaver is None:
        return None

    global _PG_POOL, _PG_SAVER
    if _PG_SAVER is not None:
        return _PG_SAVER

    url = _get_pg_url()
    if not url:
        return None

    try:
        max_size = int(os.getenv("PPT_CHECKPOINTER_PG_POOL_MAX_SIZE", "5"))
    except Exception:
        max_size = 5

    try:
        # IMPORTANT: Postgres saver setup uses CREATE INDEX CONCURRENTLY which must run
        # outside a transaction. We enable autocommit at the pool/connection level.
        if AsyncPostgresSaver is not None and AsyncConnectionPool is not None:
            _PG_POOL = AsyncConnectionPool(
                conninfo=url,
                kwargs={"autocommit": True},
                min_size=1,
                max_size=max_size,
                open=True,
            )
            saver = AsyncPostgresSaver(_PG_POOL)
            _ensure_async_setup_started(saver)
            _PG_SAVER = saver
            logger.info("✅ PPT checkpointer: Postgres async enabled")
            return saver

        # Fallback: sync saver (not recommended for async graphs)
        _PG_POOL = ConnectionPool(
            conninfo=url,
            kwargs={"autocommit": True},
            min_size=1,
            max_size=max_size,
            open=True,
        )
        saver = PostgresSaver(_PG_POOL)  # type: ignore[operator]
        try:
            saver.setup()
        except Exception as e:
            logger.warning(
                f"⚠️ PPT checkpointer: Postgres setup() failed (will fallback to sqlite): {e}"
            )
            return None
        _PG_SAVER = saver
        logger.info("✅ PPT checkpointer: Postgres enabled (sync)")
        return saver
    except Exception as e:
        logger.warning(f"⚠️ PPT checkpointer: failed to init Postgres saver, falling back: {e}")
        return None


def get_checkpointer() -> Optional[Any]:
    """Return a checkpointer saver instance (Postgres preferred)."""

    backend = (os.getenv("PPT_CHECKPOINTER_BACKEND") or "postgres").strip().lower()
    if backend in {"none", "off", "disabled"}:
        return None

    if backend != "sqlite":
        saver = _get_postgres_saver()
        if saver is not None:
            return saver

    return _get_sqlite_saver()

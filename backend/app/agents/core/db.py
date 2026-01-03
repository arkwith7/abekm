from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import get_async_engine


@asynccontextmanager
async def get_db_session_context():
    """Async DB session context helper used by agents."""

    engine = get_async_engine()
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session

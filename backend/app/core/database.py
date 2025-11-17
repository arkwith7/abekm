from typing import AsyncGenerator, Generator, Optional
import time
import random
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session as SyncSession
from app.core.config import settings
from sqlalchemy import event

# 전역 엔진 변수들
_async_engine: Optional[AsyncEngine] = None
_sync_engine: Optional[Engine] = None
_async_session_local = None
_sync_session_local = None

# Base 클래스
Base = declarative_base()

def get_async_engine() -> AsyncEngine:
    """비동기 엔진 lazy loading with 성능 최적화"""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.database_url,
            echo=settings.sqlalchemy_echo,
            future=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=settings.db_pool_pre_ping,
            connect_args={
                "server_settings": {
                    "jit": "off",
                },
                # asyncpg connection timeout 설정 (초)
                "timeout": 60,  # 연결 타임아웃 (기본 60초)
                "command_timeout": 60,  # 명령 실행 타임아웃 (기본 60초)
            }
        )
        _attach_query_listeners(_async_engine.sync_engine)
    return _async_engine

def get_sync_engine() -> Engine:
    """동기 엔진 lazy loading with 성능 최적화"""
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.database_url
        if sync_url.startswith("postgresql+asyncpg://"):
            sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
        _sync_engine = create_engine(
            sync_url,
            echo=settings.sqlalchemy_echo,
            pool_size=settings.db_pool_size // 2,
            max_overflow=settings.db_max_overflow // 2,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=settings.db_pool_pre_ping
        )
        _attach_query_listeners(_sync_engine)
    return _sync_engine

def get_async_session_local():
    """비동기 세션 팩토리 lazy loading"""
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _async_session_local

def get_sync_session_local():
    """동기 세션 팩토리 lazy loading"""
    global _sync_session_local
    if _sync_session_local is None:
        _sync_session_local = sessionmaker(
            bind=get_sync_engine(),
            class_=SyncSession,
            expire_on_commit=False
        )
    return _sync_session_local

# --- SQL Logging (slow query & sampling) -----------------------------------
_SQL_LOGGER = logging.getLogger("app.sql")
_INSTRUMENTED_ENGINES = set()

def _attach_query_listeners(engine: Engine):
    """Attach timing listeners to an Engine (idempotent)."""
    if id(engine) in _INSTRUMENTED_ENGINES:
        return

    slow_threshold_ms = max(0, settings.sql_log_slow_threshold_ms)
    sample_rate = max(0.0, min(1.0, settings.sql_log_sample_rate))
    log_all = settings.sql_query_log_enabled and settings.sql_query_log_all
    if slow_threshold_ms <= 0 and sample_rate <= 0 and not settings.sqlalchemy_echo and not log_all:
        _INSTRUMENTED_ENGINES.add(id(engine))
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: D401
        context._wkms_query_start_time = time.perf_counter()
        if log_all:
            _SQL_LOGGER.info("EXEC %s", _compact_sql(statement))

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: D401
        start = getattr(context, "_wkms_query_start_time", None)
        if start is None:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_slow = slow_threshold_ms > 0 and elapsed_ms >= slow_threshold_ms
        log_sample = (not log_slow) and sample_rate > 0 and random.random() < sample_rate
        if log_slow or log_sample:
            tag = "SLOW" if log_slow else "SAMPLE"
            _SQL_LOGGER.info(
                "%s query %.1f ms | %s", tag, elapsed_ms, _compact_sql(statement)
            )

    _INSTRUMENTED_ENGINES.add(id(engine))

def _compact_sql(sql: str) -> str:
    return " ".join(sql.strip().split())[:1000]

# 비동기 데이터베이스 세션 의존성
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """향상된 비동기 데이터베이스 세션 관리"""
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

# 트랜잭션 관리가 포함된 세션 컨텍스트 매니저
async def get_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """트랜잭션 관리가 포함된 비동기 데이터베이스 세션"""
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        async with session.begin():
            try:
                yield session
            except Exception as e:
                await session.rollback()
                raise e

# 동기 데이터베이스 세션 의존성 (필요한 경우)
def get_sync_db() -> Generator[SyncSession, None, None]:
    sync_session_local = get_sync_session_local()
    db = sync_session_local()
    try:
        yield db
    finally:
        db.close()

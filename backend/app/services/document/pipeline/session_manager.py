"""세션/상태 관리 베이스 클래스 (멀티모달 추출/청킹용)

추후: Azure Document Intelligence / Textract / Legacy 추출 파이프라인이
공통으로 사용할 수 있는 헬퍼 로직을 제공.
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
import logging

from app.models.document.multimodal_models import (
    DocExtractionSession,
    DocChunkSession,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

class ExtractionSessionManager:
    async def start(self, db: AsyncSession, *, file_bss_info_sno: int, provider: str, model_profile: str, pipeline_type: Optional[str] = None) -> DocExtractionSession:
        effective_provider = provider or settings.get_current_llm_provider()
        effective_pipeline_type = pipeline_type or effective_provider or settings.default_llm_provider
        session = DocExtractionSession(
            file_bss_info_sno=file_bss_info_sno,
            provider=effective_provider,
            model_profile=model_profile,
            pipeline_type=effective_pipeline_type,
            status="running"
        )
        db.add(session)
        await db.flush()
        logger.info(f"[ExtractionSession] started id={session.extraction_session_id} file={file_bss_info_sno}")
        return session

    async def complete(self, db: AsyncSession, session_id: int, *, page_count: Optional[int] = None):
        q = select(DocExtractionSession).where(DocExtractionSession.extraction_session_id == session_id)
        res = await db.execute(q)
        sess = res.scalar_one_or_none()
        if not sess:
            logger.warning(f"[ExtractionSession] complete() session not found id={session_id}")
            return
        setattr(sess, "status", "success")
        setattr(sess, "completed_at", datetime.utcnow())
        if page_count is not None:
            setattr(sess, "page_count_detected", page_count)
        logger.info(f"[ExtractionSession] completed id={session_id} pages={page_count}")

    async def fail(self, db: AsyncSession, session_id: int, error_message: str):
        q = select(DocExtractionSession).where(DocExtractionSession.extraction_session_id == session_id)
        res = await db.execute(q)
        sess = res.scalar_one_or_none()
        if not sess:
            logger.warning(f"[ExtractionSession] fail() session not found id={session_id}")
            return
        setattr(sess, "status", "failed")
        setattr(sess, "error_message", error_message[:2000])
        setattr(sess, "completed_at", datetime.utcnow())
        logger.error(f"[ExtractionSession] failed id={session_id} error={error_message}")

class ChunkSessionManager:
    async def start(self, db: AsyncSession, *, file_bss_info_sno: int, extraction_session_id: int, strategy_name: str, params: Optional[Dict[str, Any]] = None) -> DocChunkSession:
        sess = DocChunkSession(
            file_bss_info_sno=file_bss_info_sno,
            extraction_session_id=extraction_session_id,
            strategy_name=strategy_name,
            params_json=params or {},
            status="running"
        )
        db.add(sess)
        await db.flush()
        logger.info(f"[ChunkSession] started id={sess.chunk_session_id} file={file_bss_info_sno} strategy={strategy_name}")
        return sess

    async def complete(self, db: AsyncSession, chunk_session_id: int, *, chunk_count: int):
        q = select(DocChunkSession).where(DocChunkSession.chunk_session_id == chunk_session_id)
        res = await db.execute(q)
        sess = res.scalar_one_or_none()
        if not sess:
            logger.warning(f"[ChunkSession] complete() not found id={chunk_session_id}")
            return
        setattr(sess, "status", "success")
        setattr(sess, "completed_at", datetime.utcnow())
        setattr(sess, "chunk_count", chunk_count)
        logger.info(f"[ChunkSession] completed id={chunk_session_id} chunks={chunk_count}")

    async def fail(self, db: AsyncSession, chunk_session_id: int, error_message: str):
        q = select(DocChunkSession).where(DocChunkSession.chunk_session_id == chunk_session_id)
        res = await db.execute(q)
        sess = res.scalar_one_or_none()
        if not sess:
            logger.warning(f"[ChunkSession] fail() not found id={chunk_session_id}")
            return
        setattr(sess, "status", "failed")
        setattr(sess, "completed_at", datetime.utcnow())
        logger.error(f"[ChunkSession] failed id={chunk_session_id} error={error_message}")

extraction_session_manager = ExtractionSessionManager()
chunk_session_manager = ChunkSessionManager()

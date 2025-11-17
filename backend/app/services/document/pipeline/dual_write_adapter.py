"""Dual Write Adapter

목표:
    - 기존 레거시 저장 (TbDocumentSearchIndex, VsDocContentsChunks)
    - 신규 멀티모달 스키마(doc_extraction_session, doc_chunk, doc_embedding 등) 동시 기록
    - 점진적 마이그레이션 동안 안전한 이중 기록

구현 상태:
    - start_extraction_session: 신규 세션 row 생성
    - write_legacy_file_index: 최소 필드로 tb_document_search_index upsert/insert
    - write_legacy_chunks: VsDocContentsChunks bulk insert (기존 벡터/메타 구조 유지)
    - write_new_objects_and_chunks: objects + chunk_session + chunks 트랜잭션 내 삽입
    - write_embeddings: doc_embedding bulk insert + (선택) 레거시 임베딩 업데이터 훅
    - finalize_file: tb_document_search_index 확장 컬럼 업데이트

주의:
    - 모든 연산은 best-effort. 실패 시 로깅 후 계속(마이그레이션 안정성 우선)
    - 호출 측에서 세션을 직접 주입하지 않고 내부 short-lived 세션을 사용 (경합 최소화)
    - 추후 성능 최적화를 위해 COPY 또는 execute_many로 개선 가능
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session_local
from app.core.config import settings
from app.models.document.multimodal_models import (
    DocExtractionSession, DocExtractedObject, DocChunkSession, DocChunk, DocEmbedding
)
from app.models.document.vector_models import VsDocContentsChunks
from app.models.document.unified_search_models import TbDocumentSearchIndex

logger = logging.getLogger(__name__)

def _safe_int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default

class DualWriteAdapter:
    async def start_extraction_session(self, file_id: str, user_emp_no: str, provider: Optional[str] = None, model_profile: str = "default") -> str:
        """신규 extraction session row 생성"""
        effective_provider = provider or settings.get_current_llm_provider()
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            try:
                sess = DocExtractionSession(
                    file_bss_info_sno=_safe_int(file_id),
                    provider=effective_provider,
                    model_profile=model_profile,
                    pipeline_type=effective_provider,
                    status="running"
                )
                session.add(sess)
                await session.flush()
                extraction_session_id = str(sess.extraction_session_id)
                await session.commit()
                logger.info(f"[DualWrite] extraction_session created id={extraction_session_id} file={file_id}")
                return extraction_session_id
            except Exception as e:
                await session.rollback()
                logger.error(f"[DualWrite] start_extraction_session 실패: {e}")
                return "0"

    async def write_legacy_file_index(self, file_meta: Dict[str, Any]):
        """레거시 tb_document_search_index 기록 (최소 필드)
        file_meta keys 예시: file_id, container_id, title, full_content
        """
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            try:
                file_id = _safe_int(file_meta.get('file_id'))
                if not file_id:
                    return
                stmt = select(TbDocumentSearchIndex).where(TbDocumentSearchIndex.file_bss_info_sno == file_id)
                res = await session.execute(stmt)
                row = res.scalar_one_or_none()
                if row:
                    # update basic fields only if empty (check underlying value via getattr)
                    changed = False
                    if (getattr(row, 'full_content', None) in (None, '')) and file_meta.get('full_content'):
                        setattr(row, 'full_content', file_meta['full_content'])
                        changed = True
                    if (getattr(row, 'document_title', None) in (None, '')) and file_meta.get('title'):
                        setattr(row, 'document_title', file_meta['title'])
                        changed = True
                    if changed:
                        await session.commit()
                else:
                    idx = TbDocumentSearchIndex(
                        file_bss_info_sno=file_id,
                        knowledge_container_id=file_meta.get('container_id') or 'default',
                        document_title=file_meta.get('title'),
                        full_content=file_meta.get('full_content') or '',
                        language_code=file_meta.get('language_code', 'ko'),
                        content_length=len(file_meta.get('full_content') or ''),
                        indexing_status='indexed'
                    )
                    session.add(idx)
                    await session.commit()
                logger.debug("[DualWrite] write_legacy_file_index 완료")
            except Exception as e:
                await session.rollback()
                logger.warning(f"[DualWrite] write_legacy_file_index 실패: {e}")

    async def write_legacy_chunks(self, file_id: str, chunks: List[Dict[str, Any]]):
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            try:
                if not chunks:
                    return
                objects = []
                for ch in chunks:
                    objects.append(VsDocContentsChunks(
                        file_bss_info_sno=_safe_int(file_id),
                        chunk_index=ch.get('chunk_index', 0),
                        chunk_text=ch.get('content_text') or ch.get('text') or '',
                        chunk_size=len(ch.get('content_text') or ch.get('text') or ''),
                        page_number=ch.get('page_no'),
                        section_title=ch.get('section_heading'),
                        knowledge_container_id=ch.get('container_id'),
                        metadata_json=None,
                    ))
                session.add_all(objects)
                await session.commit()
                logger.debug(f"[DualWrite] legacy chunks inserted count={len(objects)}")
            except Exception as e:
                await session.rollback()
                logger.warning(f"[DualWrite] write_legacy_chunks 실패: {e}")

    async def write_new_objects_and_chunks(
        self,
        extraction_session_id: str,
        objects: List[Dict[str, Any]],
        chunk_session_meta: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> str:
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            try:
                chunk_session = DocChunkSession(
                    file_bss_info_sno=_safe_int(chunk_session_meta.get('file_id')),
                    extraction_session_id=_safe_int(extraction_session_id),
                    strategy_name=chunk_session_meta.get('strategy_name', 'default'),
                    params_json=chunk_session_meta.get('params_json'),
                    status='running'
                )
                session.add(chunk_session)
                await session.flush()
                # objects
                obj_models = []
                for o in objects:
                    obj_models.append(DocExtractedObject(
                        extraction_session_id=_safe_int(extraction_session_id),
                        file_bss_info_sno=_safe_int(o.get('file_id')),
                        page_no=o.get('page_no'),
                        object_type=o.get('object_type', 'TEXT_BLOCK'),
                        sequence_in_page=o.get('sequence_in_page'),
                        bbox=o.get('bbox'),
                        content_text=o.get('content_text'),
                        structure_json=o.get('structure_json'),
                        lang_code=o.get('lang_code', 'ko'),
                        char_count=(len(o.get('content_text') or '') if o.get('content_text') else None),
                        token_estimate=o.get('token_estimate'),
                        confidence=o.get('confidence'),
                        hash_sha256=o.get('hash'),
                    ))
                if obj_models:
                    session.add_all(obj_models)
                await session.flush()
                # chunks
                chunk_models = []
                for idx, ch in enumerate(chunks):
                    chunk_models.append(DocChunk(
                        chunk_session_id=chunk_session.chunk_session_id,
                        file_bss_info_sno=_safe_int(ch.get('file_id')),
                        chunk_index=ch.get('chunk_index', idx),
                        source_object_ids=ch.get('source_object_ids') or [],
                        content_text=ch.get('content_text') or ch.get('text') or '',
                        token_count=ch.get('token_count'),
                        modality=ch.get('modality', 'text'),
                        section_heading=ch.get('section_heading'),
                        page_range=ch.get('page_range'),
                        quality_score=ch.get('quality_score'),
                    ))
                if chunk_models:
                    session.add_all(chunk_models)
                setattr(chunk_session, 'chunk_count', len(chunk_models))
                setattr(chunk_session, 'status', 'success')
                await session.commit()
                logger.info(f"[DualWrite] new objects={len(obj_models)} chunks={len(chunk_models)}")
                return str(chunk_session.chunk_session_id)
            except Exception as e:
                await session.rollback()
                logger.error(f"[DualWrite] write_new_objects_and_chunks 실패: {e}")
                return "0"

    async def write_embeddings(
        self,
        chunk_session_id: str,
        embeddings: List[Dict[str, Any]],
        model_name: str,
    ):
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            try:
                if not embeddings:
                    return
                emb_models = []
                for emb in embeddings:
                    # 벡터 및 차원 추출
                    vector = emb.get('vector')
                    dimension = emb.get('dimension', len(vector or []))
                    
                    # 벤더 판별 및 컬럼 할당
                    provider = None
                    azure_vec_1536 = None
                    azure_vec_3072 = None
                    aws_vec_1024 = None
                    aws_vec_256 = None
                    
                    if vector:
                        if dimension == 1536:
                            provider = 'azure'
                            azure_vec_1536 = vector
                        elif dimension == 3072:
                            provider = 'azure'
                            azure_vec_3072 = vector
                        elif dimension == 1024:
                            provider = 'aws'
                            aws_vec_1024 = vector
                        elif dimension == 256:
                            provider = 'aws'
                            aws_vec_256 = vector
                    
                    emb_models.append(DocEmbedding(
                        chunk_id=_safe_int(emb.get('chunk_id')),
                        file_bss_info_sno=_safe_int(emb.get('file_id')),
                        provider=provider,
                        model_name=model_name,
                        modality=emb.get('modality', 'text'),
                        dimension=dimension,
                        azure_vector_1536=azure_vec_1536,
                        azure_vector_3072=azure_vec_3072,
                        aws_vector_1024=aws_vec_1024,
                        aws_vector_256=aws_vec_256,
                        vector=vector,  # 레거시 호환
                        norm_l2=emb.get('norm_l2'),
                    ))
                session.add_all(emb_models)
                await session.commit()
                logger.info(f"[DualWrite] embeddings inserted count={len(emb_models)} model={model_name}")
            except Exception as e:
                await session.rollback()
                logger.error(f"[DualWrite] write_embeddings 실패: {e}")

    async def finalize_file(self, file_id: str, extraction_session_id: str, primary_chunk_session_id: Optional[str]):
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            try:
                file_id_int = _safe_int(file_id)
                if not file_id_int:
                    return
                stmt = select(TbDocumentSearchIndex).where(TbDocumentSearchIndex.file_bss_info_sno == file_id_int)
                res = await session.execute(stmt)
                idx = res.scalar_one_or_none()
                if idx:
                    if primary_chunk_session_id:
                        setattr(idx, 'primary_chunk_session_id', _safe_int(primary_chunk_session_id))
                    setattr(idx, 'extraction_session_id', _safe_int(extraction_session_id))
                    await session.commit()
                logger.info(
                    f"[DualWrite] finalize_file file={file_id} extraction_session={extraction_session_id} primary_chunk_session={primary_chunk_session_id}"
                )
            except Exception as e:
                await session.rollback()
                logger.error(f"[DualWrite] finalize_file 실패: {e}")


dual_write_adapter = DualWriteAdapter()

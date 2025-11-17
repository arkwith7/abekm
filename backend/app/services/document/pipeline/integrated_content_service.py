"""
🔄 통합 콘텐츠 서비스 (Integrated Content Service)
===============================================

🎯 목적: 문서 관리, 검색, RAG 시스템의 기능별 파이프라인 완성도 향상

📊 핵심 테이블별 역할 정의:
┌─────────────────────┬─────────────────────┬─────────────────────────────────┐
│ 테이블명              │ 주요 용도            │ 활용 기능                        │
├─────────────────────┼─────────────────────┼─────────────────────────────────┤
│ tb_file_bss_info    │ 문서 메타데이터      │ 문서 목록, 권한 검증, 파일 관리   │
│ tb_file_dtl_info    │ 파일 처리 상태       │ 업로드 진행률, 처리 결과         │
│ vs_doc_contents_index│ 문서 전문 + 임베딩   │ 키워드 검색, 문서 단위 표시      │
│ vs_doc_contents_chunks│ 청킹 단위 세부정보   │ 의미 검색, RAG 컨텍스트, 참조정보│
│ tb_chat_history     │ 채팅 세션 관리       │ 대화 기록, 컨텍스트 연속성       │
└─────────────────────┴─────────────────────┴─────────────────────────────────┘

🔗 기능별 파이프라인 아키텍처:
┌─ 📄 문서 관리 파이프라인 ─────────────────────────────────────────────────────┐
│ 업로드 → tb_file_bss_info 저장 → 전처리 → NLP 분석 → vs_doc_contents_index    │
│        ↓ tb_file_dtl_info 상태   ↓ 텍스트추출  ↓ 형태소분석 ↓ 문서전문+임베딩    │
│        → 청킹 → vs_doc_contents_chunks → 키워드/엔티티 추출 → 검색 준비 완료    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 🔍 검색 파이프라인 ──────────────────────────────────────────────────────────┐
│ [키워드 검색] vs_doc_contents_index 전문 → 문서 단위 결과 반환                │
│ [의미 검색]   vs_doc_contents_chunks 임베딩 → 청킹 단위 정확도 향상          │
│ [하이브리드]  두 방식 결합 → 스코어 가중 합산 → 최적 검색 결과               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 🤖 RAG 파이프라인 ──────────────────────────────────────────────────────────┐
│ 질문 → vs_doc_contents_chunks 의미 검색 → 컨텍스트 생성 → LLM 응답 생성      │
│      ↓ 청킹단위 정밀 검색           ↓ 참조정보 추출   ↓ tb_chat_history 저장  │
│      → 페이지번호, 키워드, 문서명 등 세부 참조정보 제공                      │
└─────────────────────────────────────────────────────────────────────────────┘
"""

import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_, func, desc
import numpy as np

from app.core.database import get_async_session_local
from app.services.core.embedding_service import EmbeddingService
from app.services.core.korean_nlp_service import korean_nlp_service
from app.services.auth.permission_service import PermissionService
from app.models import TbFileBssInfo, TbFileDtlInfo, TbDocumentSearchIndex
from app.models import VsDocContentsChunks
from app.models import TbChatHistory
from app.core.config import settings

logger = logging.getLogger(__name__)


class IntegratedContentService:
    """통합 콘텐츠 서비스 - 문서 관리, 검색, RAG 통합"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.async_session_local = get_async_session_local()
        
        # 검색 가중치 설정
        self.vector_weight = 0.7      # 벡터 검색 가중치 증가
        self.keyword_weight = 0.3     # 키워드 검색 가중치
        self.similarity_threshold = 0.5
        
        logger.info("🔄 통합 콘텐츠 서비스 초기화 완료")

    # =========================================================================
    # 📄 1. 문서 관리 파이프라인 (Document Management Pipeline)
    # =========================================================================
    
    async def complete_document_pipeline(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        file_metadata: Dict[str, Any],
        raw_content: str,
        user_emp_no: str
    ) -> Dict[str, Any]:
        """
        완전한 문서 처리 파이프라인
        
        파이프라인 단계:
        1. tb_file_bss_info 메타데이터 저장/업데이트
        2. tb_file_dtl_info 처리 상태 관리  
        3. 텍스트 전처리 및 청킹
        4. 형태소 분석 및 NLP 처리
        5. vs_doc_contents_index 문서 전문 + 임베딩 저장
        6. vs_doc_contents_chunks 청킹 단위 세부 정보 저장
        """
        try:
            pipeline_result = {
                "success": False,
                "pipeline_stages": {},
                "file_bss_info_sno": file_bss_info_sno,
                "container_id": container_id,
                "total_chunks": 0,
                "errors": []
            }
            
            # ===== 1단계: tb_file_bss_info 메타데이터 처리 =====
            stage1_result = await self._process_file_metadata(
                session, file_bss_info_sno, file_metadata, user_emp_no
            )
            pipeline_result["pipeline_stages"]["metadata_processing"] = stage1_result
            
            if not stage1_result["success"]:
                pipeline_result["errors"].append("메타데이터 처리 실패")
                return pipeline_result
            
            # ===== 2단계: tb_file_dtl_info 상태 관리 =====
            await self._update_processing_status(session, file_bss_info_sno, "PROCESSING")
            
            # ===== 3단계: 텍스트 전처리 및 청킹 =====
            stage3_result = await self._preprocess_and_chunk_content(raw_content)
            pipeline_result["pipeline_stages"]["text_processing"] = stage3_result
            
            if not stage3_result["success"]:
                await self._update_processing_status(session, file_bss_info_sno, "FAILED")
                pipeline_result["errors"].append("텍스트 처리 실패")
                return pipeline_result
            
            chunks = stage3_result["chunks"]
            pipeline_result["total_chunks"] = len(chunks)
            
            # ===== 4단계: 형태소 분석 및 NLP 처리 =====
            stage4_result = await self._perform_nlp_analysis(chunks)
            pipeline_result["pipeline_stages"]["nlp_analysis"] = stage4_result
            
            # ===== 5단계: vs_doc_contents_index 저장 (문서 전문 + 임베딩) =====
            stage5_result = await self._store_document_fulltext_vectors(
                session, file_bss_info_sno, container_id, chunks, stage4_result["nlp_results"], user_emp_no
            )
            pipeline_result["pipeline_stages"]["fulltext_vector_storage"] = stage5_result
            
            # ===== 6단계: vs_doc_contents_chunks 저장 (청킹 단위 세부정보) =====
            stage6_result = await self._store_chunk_detail_vectors(
                session, file_bss_info_sno, stage5_result["vector_ids"], chunks, stage4_result["nlp_results"]
            )
            pipeline_result["pipeline_stages"]["chunk_detail_storage"] = stage6_result
            
            # ===== 7단계: 최종 상태 업데이트 =====
            final_status = "COMPLETED" if stage5_result["success"] and stage6_result["success"] else "PARTIAL"
            await self._update_processing_status(session, file_bss_info_sno, final_status)
            
            pipeline_result["success"] = final_status == "COMPLETED"
            
            logger.info(f"🔄 문서 파이프라인 완료: {final_status}, 청크 {pipeline_result['total_chunks']}개")
            return pipeline_result
            
        except Exception as e:
            await self._update_processing_status(session, file_bss_info_sno, "ERROR")
            logger.error(f"문서 파이프라인 실패: {str(e)}")
            pipeline_result["errors"].append(str(e))
            return pipeline_result
    
    async def _process_file_metadata(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        metadata: Dict[str, Any],
        user_emp_no: str
    ) -> Dict[str, Any]:
        """tb_file_bss_info 메타데이터 처리"""
        try:
            # 한국어 형태소 분석 결과를 포함한 메타데이터 구성
            korean_metadata = {
                "file_size": metadata.get("file_size", 0),
                "content_type": metadata.get("content_type", ""),
                "page_count": metadata.get("page_count", 0),
                "language": "ko",
                "encoding": metadata.get("encoding", "utf-8"),
                "processor_version": "v1.0",
                "processed_by": user_emp_no,
                "processing_timestamp": datetime.now().isoformat()
            }
            
            query = text("""
                UPDATE tb_file_bss_info 
                SET 
                    korean_metadata = :korean_metadata,
                    updated_at = NOW(),
                    processing_status = 'ANALYZING'
                WHERE file_bss_info_sno = :file_id
            """)
            
            await session.execute(query, {
                "korean_metadata": json.dumps(korean_metadata),
                "file_id": file_bss_info_sno
            })
            
            return {"success": True, "metadata_updated": True}
            
        except Exception as e:
            logger.error(f"메타데이터 처리 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _update_processing_status(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        status: str
    ) -> bool:
        """tb_file_dtl_info 처리 상태 업데이트"""
        try:
            # tb_file_dtl_info에 처리 상태 기록
            query = text("""
                INSERT INTO tb_file_dtl_info (
                    file_bss_info_sno, processing_stage, status, 
                    started_at, updated_at, details
                ) VALUES (
                    :file_id, :stage, :status, NOW(), NOW(), :details
                )
                ON CONFLICT (file_bss_info_sno, processing_stage) 
                DO UPDATE SET 
                    status = :status,
                    updated_at = NOW(),
                    details = :details
            """)
            
            details = {
                "status_change": status,
                "timestamp": datetime.now().isoformat(),
                "pipeline_stage": self._get_pipeline_stage_from_status(status)
            }
            
            await session.execute(query, {
                "file_id": file_bss_info_sno,
                "stage": "document_processing",
                "status": status,
                "details": json.dumps(details)
            })
            
            return True
            
        except Exception as e:
            logger.error(f"처리 상태 업데이트 실패: {str(e)}")
            return False
    
    async def _preprocess_and_chunk_content(self, raw_content: str) -> Dict[str, Any]:
        """텍스트 전처리 및 청킹"""
        try:
            # 한국어 텍스트 정제
            cleaned_content = await korean_nlp_service.clean_korean_text(raw_content)
            
            # 의미 단위 청킹 (문장 경계, 단락 경계 고려)
            chunks = await korean_nlp_service.intelligent_chunking(
                cleaned_content,
                chunk_size=1000,
                overlap_size=200,
                preserve_sentences=True
            )
            
            return {
                "success": True,
                "chunks": chunks,
                "original_length": len(raw_content),
                "cleaned_length": len(cleaned_content),
                "chunk_count": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"텍스트 전처리 실패: {str(e)}")
            return {"success": False, "error": str(e), "chunks": []}
    
    async def _perform_nlp_analysis(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """형태소 분석 및 NLP 처리"""
        try:
            nlp_results = []
            
            for chunk in chunks:
                chunk_text = chunk.get("text", "")
                
                # 한국어 형태소 분석
                morpheme_result = await korean_nlp_service.analyze_morphemes(chunk_text)
                
                # 키워드 추출
                keywords = await korean_nlp_service.extract_keywords(
                    chunk_text, max_keywords=10
                )
                
                # 개체명 인식
                entities = await korean_nlp_service.extract_entities(chunk_text)
                
                # 문서 요약 (청킹 단위)
                summary = await korean_nlp_service.summarize_text(
                    chunk_text, max_length=100
                )
                
                nlp_results.append({
                    "morphemes": morpheme_result,
                    "keywords": keywords,
                    "entities": entities,
                    "summary": summary,
                    "text_stats": {
                        "char_count": len(chunk_text),
                        "word_count": len(chunk_text.split()),
                        "sentence_count": chunk_text.count('.')
                    }
                })
            
            return {
                "success": True,
                "nlp_results": nlp_results,
                "processed_chunks": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"NLP 분석 실패: {str(e)}")
            return {"success": False, "error": str(e), "nlp_results": []}
    
    def _get_pipeline_stage_from_status(self, status: str) -> str:
        """상태에서 파이프라인 단계 추출"""
        status_mapping = {
            "PROCESSING": "content_processing",
            "ANALYZING": "nlp_analysis", 
            "VECTORIZING": "embedding_generation",
            "COMPLETED": "storage_complete",
            "FAILED": "processing_failed",
            "ERROR": "system_error"
        }
        return status_mapping.get(status, "unknown")
    
    async def _store_document_fulltext_vectors(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunks: List[Dict[str, Any]],
        nlp_results: List[Dict[str, Any]],
        user_emp_no: str
    ) -> Dict[str, Any]:
        """vs_doc_contents_index에 문서 전문 + 임베딩 저장"""
        try:
            vector_ids = []
            failed_chunks = []
            
            await self._update_processing_status(session, file_bss_info_sno, "VECTORIZING")
            
            for i, (chunk, nlp_result) in enumerate(zip(chunks, nlp_results)):
                vector_result = await self._store_main_vector(
                    session, file_bss_info_sno, container_id, chunk, nlp_result, i, user_emp_no
                )
                
                if vector_result:
                    vector_ids.append(vector_result["vector_id"])
                else:
                    failed_chunks.append(i)
            
            return {
                "success": len(vector_ids) > 0,
                "vector_ids": vector_ids,
                "total_stored": len(vector_ids),
                "failed_chunks": failed_chunks,
                "success_rate": len(vector_ids) / len(chunks) if chunks else 0
            }
            
        except Exception as e:
            logger.error(f"문서 전문 벡터 저장 실패: {str(e)}")
            return {"success": False, "error": str(e), "vector_ids": []}
    
    async def _store_chunk_detail_vectors(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        vector_ids: List[int],
        chunks: List[Dict[str, Any]],
        nlp_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """vs_doc_contents_chunks에 청킹 단위 세부정보 저장"""
        try:
            stored_count = 0
            failed_details = []
            
            for i, (vector_id, chunk, nlp_result) in enumerate(zip(vector_ids, chunks, nlp_results)):
                success = await self._store_chunk_details(
                    session, file_bss_info_sno, vector_id, chunk, nlp_result, i
                )
                
                if success:
                    stored_count += 1
                else:
                    failed_details.append(i)
            
            return {
                "success": stored_count > 0,
                "total_stored": stored_count,
                "failed_details": failed_details,
                "success_rate": stored_count / len(vector_ids) if vector_ids else 0
            }
            
        except Exception as e:
            logger.error(f"청크 세부정보 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _store_main_vector(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int,
        user_emp_no: str
    ) -> Optional[Dict[str, Any]]:
        """vs_doc_contents_index에 메인 벡터 데이터 저장"""
        try:
            chunk_text = chunk.get('text', '')
            if not chunk_text.strip():
                return None
            
            # 임베딩 생성
            embedding = await self.embedding_service.get_embedding(chunk_text)
            if not embedding:
                return None
            
            # 메타데이터 구성
            metadata = {
                "chunk_index": chunk_index,
                "chunk_size": len(chunk_text),
                "page_number": chunk.get('page_number', 0),
                "section": chunk.get('section', ''),
                "nlp_keywords": nlp_result.get('keywords', []),
                "nlp_entities": nlp_result.get('entities', []),
                "created_by": user_emp_no,
                "created_at": datetime.now().isoformat()
            }
            
            # vs_doc_contents_index에 저장
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"
            
            query = text("""
                INSERT INTO vs_doc_contents_index (
                    file_bss_info_sno, knowledge_container_id, chunk_text, 
                    chunk_index, chunk_size, metadata_json, embedding, created_at
                ) 
                VALUES (
                    :file_bss_info_sno, :container_id, :chunk_text,
                    :chunk_index, :chunk_size, :metadata_json, :embedding::vector, NOW()
                )
                RETURNING id
            """)
            
            result = await session.execute(query, {
                "file_bss_info_sno": file_bss_info_sno,
                "container_id": container_id,
                "chunk_text": chunk_text,
                "chunk_index": chunk_index,
                "chunk_size": len(chunk_text),
                "metadata_json": json.dumps(metadata),
                "embedding": embedding_str
            })
            
            vector_id = result.scalar()
            
            logger.debug(f"벡터 저장 완료: ID {vector_id}, 청크 {chunk_index}")
            
            return {
                "vector_id": vector_id,
                "chunk_index": chunk_index,
                "embedding_dimension": len(embedding)
            }
            
        except Exception as e:
            logger.error(f"메인 벡터 저장 실패: {str(e)}")
            return None
    
    async def _store_chunk_details(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        vector_id: int,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int
    ) -> bool:
        """vs_doc_contents_chunks에 청크 상세 정보 저장"""
        try:
            query = text("""
                INSERT INTO vs_doc_contents_chunks (
                    vs_doc_contents_index_id, file_bss_info_sno, chunk_index,
                    page_number, section_title, subsection_title,
                    keywords_json, entities_json, summary_text, created_at
                ) 
                VALUES (
                    :vector_id, :file_bss_info_sno, :chunk_index,
                    :page_number, :section_title, :subsection_title,
                    :keywords_json, :entities_json, :summary_text, NOW()
                )
            """)
            
            await session.execute(query, {
                "vector_id": vector_id,
                "file_bss_info_sno": file_bss_info_sno,
                "chunk_index": chunk_index,
                "page_number": chunk.get('page_number', 0),
                "section_title": chunk.get('section', '')[:200] if chunk.get('section') else None,
                "subsection_title": chunk.get('subsection', '')[:200] if chunk.get('subsection') else None,
                "keywords_json": json.dumps(nlp_result.get('keywords', [])),
                "entities_json": json.dumps(nlp_result.get('entities', [])),
                "summary_text": nlp_result.get('summary', '')[:500] if nlp_result.get('summary') else None
            })
            
            return True
            
        except Exception as e:
            logger.error(f"청크 상세 정보 저장 실패: {str(e)}")
            return False
    
    async def _update_file_processing_status(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        status: str
    ) -> bool:
        """tb_file_bss_info 처리 상태 업데이트"""
        try:
            query = text("""
                UPDATE tb_file_bss_info 
                SET 
                    processing_status = :status,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE file_bss_info_sno = :file_id
            """)
            
            await session.execute(query, {
                "status": status,
                "file_id": file_bss_info_sno
            })
            
            return True
            
        except Exception as e:
            logger.error(f"파일 상태 업데이트 실패: {str(e)}")
            return False

    # =========================================================================
    # 🔍 2. 통합 검색 시스템 (Unified Search System)  
    # =========================================================================
    
    async def unified_search(
        self,
        query: str,
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_results: int = 10,
        search_type: str = "hybrid",
        similarity_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        통합 검색 시스템 - vs_doc_contents_index 중심
        
        Args:
            query: 검색 쿼리
            user_emp_no: 사용자 사번
            container_ids: 검색 대상 컨테이너
            max_results: 최대 결과 수
            search_type: 검색 타입 (vector, keyword, hybrid)
            similarity_threshold: 유사도 임계값
        """
        try:
            threshold = similarity_threshold or self.similarity_threshold
            
            # 권한 확인
            accessible_containers = await self._get_accessible_containers(user_emp_no, container_ids)
            if not accessible_containers:
                return {
                    "results": [],
                    "total_count": 0,
                    "message": "접근 권한이 있는 컨테이너가 없습니다"
                }
            
            # 쿼리 전처리
            processed_query = await self._process_search_query(query)
            
            # 검색 실행
            if search_type == "vector":
                results = await self._vector_search_unified(processed_query, accessible_containers, max_results, threshold)
            elif search_type == "keyword":
                results = await self._keyword_search_unified(processed_query, accessible_containers, max_results)
            else:  # hybrid
                results = await self._hybrid_search_unified(processed_query, accessible_containers, max_results, threshold)
            
            # 결과 포맷팅 및 메타데이터 추가
            formatted_results = await self._format_search_results_unified(results, user_emp_no)
            
            # 검색 로그 저장 (옵션)
            await self._log_search_activity(user_emp_no, query, len(formatted_results), search_type)
            
            return {
                "results": formatted_results,
                "total_count": len(formatted_results),
                "search_type": search_type,
                "query_processed": processed_query,
                "accessible_containers": accessible_containers,
                "execution_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"통합 검색 실패: {str(e)}")
            raise
    
    async def _vector_search_unified(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """통합 벡터 검색 - vs_doc_contents_index 직접 활용"""
        try:
            query_text = processed_query.get("optimized_text", processed_query["original_text"])
            
            # 쿼리 임베딩 생성
            query_embedding = await self.embedding_service.get_embedding(query_text)
            if not query_embedding:
                return []
            
            async with self.async_session_local() as session:
                container_filter = "', '".join(container_ids)
                embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
                
                # 🔷🟧 벤더별 벡터 컬럼 선택 (차원 기반 자동 판별)
                # vs_doc_contents_index는 레거시 테이블이므로 폴백 전략 사용
                embedding_dim = len(query_embedding)
                logger.info(f"[VECTOR-SEARCH-UNIFIED] 임베딩 차원: {embedding_dim}d (vs_doc_contents_index 테이블 사용)")
                
                query_sql = text(f"""
                    SELECT 
                        v.id as vector_id,
                        v.file_bss_info_sno,
                        v.chunk_text,
                        v.chunk_index,
                        v.chunk_size,
                        v.metadata_json,
                        v.knowledge_container_id,
                        f.file_lgc_nm,
                        f.file_psl_nm,
                        f.path,
                        f.korean_metadata,
                        f.created_at as file_created_at,
                        1 - (v.embedding <=> '{embedding_str}'::vector) as similarity_score
                    FROM vs_doc_contents_index v
                    JOIN tb_file_bss_info f ON v.file_bss_info_sno = f.file_bss_info_sno
                    WHERE v.knowledge_container_id IN ('{container_filter}')
                        AND f.del_yn = 'N'
                        AND v.embedding IS NOT NULL
                        AND 1 - (v.embedding <=> '{embedding_str}'::vector) >= {threshold}
                    ORDER BY similarity_score DESC
                    LIMIT {max_results}
                """)
                
                result = await session.execute(query_sql)
                
                results = []
                for row in result.fetchall():
                    # 메타데이터 파싱
                    metadata = {}
                    if row.metadata_json:
                        try:
                            metadata = json.loads(row.metadata_json)
                        except:
                            pass
                    
                    # 한국어 메타데이터 파싱
                    korean_metadata = {}
                    if row.korean_metadata:
                        try:
                            korean_metadata = json.loads(row.korean_metadata)
                        except:
                            pass
                    
                    results.append({
                        "vector_id": row.vector_id,
                        "file_bss_info_sno": row.file_bss_info_sno,
                        "document_id": f"doc_{row.file_bss_info_sno}_{row.chunk_index}",
                        "title": row.file_lgc_nm or row.file_psl_nm,
                        "content": row.chunk_text,
                        "chunk_index": row.chunk_index,
                        "chunk_size": row.chunk_size,
                        "similarity_score": float(row.similarity_score),
                        "container_id": row.knowledge_container_id,
                        "file_path": row.path,
                        "metadata": metadata,
                        "korean_metadata": korean_metadata,
                        "file_created_at": row.file_created_at.isoformat() if row.file_created_at else None,
                        "search_method": "vector"
                    })
                
                logger.info(f"벡터 검색 결과: {len(results)}개 (임계값: {threshold})")
                return results
                
        except Exception as e:
            logger.error(f"통합 벡터 검색 실패: {str(e)}")
            return []

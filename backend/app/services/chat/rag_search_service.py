"""
🔍 RAG 전용 검색 서비스
====================

RAG를 위한 컨텍스트 검색 및 최적화:
- 의도 기반 하이브리드 검색
- 시맨틱 유사도 + 키워드 매칭
- 컨텍스트 윈도우 최적화
- 검색 결과 리랭킹
- 멀티턴 대화 컨텍스트 활용
"""

import logging
import re
import json
import time
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import copy

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, and_, or_

# Multi-vendor AI services for embedding and reranking
from app.services.core.ai_service import ai_service
from app.services.core.korean_nlp_service import korean_nlp_service
from app.services.chat.conversation_context_service import conversation_context_service
from app.services.search.query_pipeline import process_user_query  # 통합 파이프라인
from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class RAGSearchParams:
    """RAG 검색 매개변수"""
    query: str
    container_ids: Optional[List[str]] = None
    document_ids: Optional[List[Any]] = None  # 특정 문서로 제한 (str/int 혼용 지원)
    limit: int = 10
    threshold: float = 0.2  # (legacy) – 사용 안함, similarity_threshold 사용
    max_chunks: int = 10
    similarity_threshold: float = 0.25  # 관련성 필터링 임계값 (0.4 → 0.25로 완화, recall 향상)
    keyword_boost: float = 0.5  # 키워드 검색 가중치 증가 (한국어에서 더 정확)
    semantic_boost: float = 0.4  # 벡터 검색 가중치 감소 (한국어 임베딩 한계 고려)
    use_reranking: bool = True
    reranking: bool = True
    context_window: int = 4000  # 토큰 수
    search_mode: str = "hybrid"  # "semantic", "keyword", "hybrid"
    original_query: Optional[str] = None  # 멀티턴 강화 전 사용자 원문 보존

@dataclass
class RAGSearchResult:
    """RAG 검색 결과"""
    # 최종 후보 청크(토큰 구성 전, 컷/리랭킹 이후 남은 전체 후보)
    chunks: List[Dict[str, Any]]
    # 실제 LLM 컨텍스트에 포함된 청크(토큰 제한 반영)
    used_chunks: List[Dict[str, Any]]
    context_text: str
    total_tokens: int
    search_stats: Dict[str, Any]
    reranking_applied: bool

class RAGSearchService:
    """RAG 전용 검색 서비스"""
    
    def __init__(self):
        self.ai_service = ai_service
        self.nlp_service = korean_nlp_service
        self.max_context_tokens = 4000
        self.chunk_overlap_ratio = 0.1
        # PPT 의도 감지용 키워드
        self._ppt_query_keywords = [
            "ppt", "pptx", "presentation", "슬라이드", "발표자료", "발표 자료", "프레젠테이션", "프리젠테이션", "제품소개", "소개서"
        ]
    
    def _detect_query_language(self, query: str) -> str:
        """
        쿼리의 주요 언어 감지 (한국어/영어/혼합)
        
        Returns:
            'ko': 한국어 위주
            'en': 영어 위주
            'mixed': 혼합
        """
        if not query:
            return 'ko'
        
        # 한글 문자 비율 계산
        korean_chars = len([c for c in query if '\uac00' <= c <= '\ud7a3'])
        english_chars = len([c for c in query if c.isalpha() and c.isascii()])
        total_chars = korean_chars + english_chars
        
        if total_chars == 0:
            return 'ko'  # 기본값
        
        korean_ratio = korean_chars / total_chars
        
        if korean_ratio > 0.6:
            return 'ko'
        elif korean_ratio < 0.2:
            return 'en'
        else:
            return 'mixed'
    
    async def search_for_rag_context(
        self,
        session: AsyncSession,
        search_params: RAGSearchParams,
        session_id: Optional[str] = None,
        enable_multiturn_context: bool = True
    ) -> RAGSearchResult:
        """
        RAG를 위한 컨텍스트 검색
        
        Args:
            session: 데이터베이스 세션
            search_params: 검색 매개변수
            
        Returns:
            RAG 검색 결과
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔍 RAG 검색 시작: '{search_params.query[:50]}...' "
                       f"(모드: {search_params.search_mode})")

            # --- 문서 ID 정합성 보정 (formatted/file_id → 실제 file_bss_info_sno 정규화) ---
            if search_params.document_ids:
                search_params.document_ids = self._normalize_document_ids(search_params.document_ids)

            # --- 멀티턴 대화 컨텍스트 활용 (Option B 개선: 원문 보존 + 필요시 2차 시도) ---
            if not search_params.original_query:
                search_params.original_query = search_params.query

            enhanced_query = search_params.query  # 기본값: 변경 없음
            context_metadata = {"context_used": False}

            if enable_multiturn_context and session_id:
                try:
                    enhanced_candidate, context_metadata = await conversation_context_service.enhance_query_with_context(
                        current_query=search_params.query,
                        session_id=session_id,
                        db_session=session
                    )
                    # 원문과 다르면 후보로만 보관 (1차 의미검색 실패 시 사용)
                    if context_metadata.get("context_used") and enhanced_candidate != search_params.query:
                        enhanced_query = enhanced_candidate
                        logger.info(f"🔗 컨텍스트 강화 후보 확보 (지연 적용): '{search_params.query[:60]}' → '{enhanced_query[:60]}'")
                except Exception as ctx_error:
                    logger.warning(f"⚠️ 멀티턴 컨텍스트 적용 실패, 원본 우선 사용: {ctx_error}")

            # --- Adaptive Threshold (관련성 없는 문서 필터링 강화) ---
            base_threshold = search_params.similarity_threshold
            qlen = len(search_params.query)
            # 짧은 쿼리일수록 더 엄격한 임계값 적용 (관련성 확보)
            # ⚠️ 2025-10-17: 임계값을 낮춰서 recall 향상 (0.268 정도의 유사도도 매칭되도록)
            if qlen < 15:
                adaptive = max(0.25, base_threshold - 0.10)  # 0.35 → 0.25로 추가 완화
            elif qlen < 40:
                adaptive = max(0.22, base_threshold - 0.15)  # 0.28 → 0.22로 추가 완화 (중요!)
            elif qlen > 200:
                adaptive = max(0.20, base_threshold - 0.15)  # 0.25 → 0.20로 추가 완화
            elif qlen > 120:
                adaptive = max(0.22, base_threshold - 0.15)  # 0.28 → 0.22로 추가 완화
            else:
                adaptive = max(0.22, base_threshold - 0.15)  # 0.28 → 0.22로 추가 완화
            # 필터 적용 상태에서도 높은 품질 유지
            # 기본 0.22, 컨테이너 필터 0.20, 문서 필터 0.18
            min_floor = 0.22  # 0.28 → 0.22로 완화 (중요!)
            if search_params.container_ids:
                min_floor = 0.20  # 0.25 → 0.20
            if search_params.document_ids:
                min_floor = 0.18  # 0.22 → 0.18로 완화 (0.268 매칭 가능)
            adaptive = max(min_floor, adaptive)
            if abs(adaptive - search_params.similarity_threshold) > 1e-6:
                logger.info(f"🎚️ Adaptive similarity threshold (revised): {search_params.similarity_threshold:.2f} -> {adaptive:.2f} (len={qlen})")
                search_params.similarity_threshold = adaptive
            
            # 1단계: 질의 분석 및 임베딩 생성
            query_analysis = await self._analyze_query(search_params.query)
            
            # 2단계: 하이브리드 검색 1차 (원문 기반)
            search_results = await self._execute_hybrid_search(
                session=session,
                search_params=search_params,
                query_analysis=query_analysis
            )

            def has_semantic(results: List[Dict[str, Any]]) -> bool:
                for r in results:
                    if r.get("search_type") in ("semantic", "hybrid") and r.get("semantic_score", 0) > 0:
                        return True
                return False

            # 2차: 의미 결과 전무 & 강화 쿼리 존재 시 강화 쿼리 재검색 (threshold 재설정)
            if not has_semantic(search_results) and enhanced_query != search_params.query:
                logger.info("🔁 1차 의미검색 실패 – 강화 쿼리로 재시도")
                sp2 = copy.deepcopy(search_params)
                sp2.query = enhanced_query
                # 길이 기반 재적용 (강화 쿼리도 품질 유지)
                qlen2 = len(sp2.query)
                if qlen2 > 120 and sp2.similarity_threshold > 0.35:
                    sp2.similarity_threshold = max(0.35, sp2.similarity_threshold - 0.03)
                query_analysis2 = await self._analyze_query(sp2.query)
                search_results2 = await self._execute_hybrid_search(
                    session=session,
                    search_params=sp2,
                    query_analysis=query_analysis2
                )
                if has_semantic(search_results2):
                    logger.info("✅ 강화 쿼리 재시도에서 의미 결과 확보 – 교체 적용")
                    search_results = search_results2
                    search_params.query = sp2.query  # 통계 일관성 위해 반영
                else:
                    logger.info("⚠️ 강화 쿼리 재시도도 의미결과 없음 – 1차 결과 유지")
            
            # 2.9단계: 하이브리드 분포 기반 컷라인 동적 적용 (과도한 저품질 제거)
            search_results = self._apply_dynamic_cutline(search_results, search_params)

            # 3단계: 중복 제거 (동일 파일의 동일 청크 제거)
            search_results = self._remove_duplicates(search_results)
            
            # 3.2단계: PPT 의도 감지 및 가중치 부여
            ppt_intent = self._detect_ppt_intent(search_params.query)
            if ppt_intent and search_results:
                search_results = self._boost_for_ppt_intent(search_results)

            # 3.5단계: 참고자료 품질 검증 (주제 일치도 확인)
            if search_results:
                search_results = await self._validate_reference_quality(
                    original_query=search_params.original_query or search_params.query,
                    current_query=search_params.query,
                    results=search_results,
                    relax_filter=bool(search_params.document_ids) or ppt_intent
                )
            
            # 4단계: 리랭킹 (필요시)
            if search_params.use_reranking and len(search_results) > search_params.max_chunks:
                search_results = await self._rerank_results(
                    query=search_params.query,
                    results=search_results,
                    target_count=search_params.max_chunks
                )
                reranking_applied = True
            else:
                search_results = search_results[:search_params.max_chunks]
                reranking_applied = False
            
            # 5단계: 컨텍스트 구성
            context_text, total_tokens, used_chunks = await self._build_context(
                chunks=search_results,
                max_tokens=search_params.context_window,
                ppt_mode=ppt_intent
            )
            
            # 6단계: 결과 통계 (멀티턴 컨텍스트 정보 포함)
            from app.core.config import settings
            search_stats = {
                "query_length": len(search_params.query),
                "total_candidates": len(search_results),
                "final_chunks": len(search_results),
                "avg_similarity": sum(chunk.get("similarity_score", 0) for chunk in search_results) / len(search_results) if search_results else 0,
                "search_time": time.time() - start_time,
                "search_mode": search_params.search_mode,
                "has_korean_keywords": len(query_analysis.get("korean_keywords", [])) > 0,
                "embedding_dimension": len(query_analysis.get("embedding", [])) if query_analysis.get("embedding") else 0,
                # 프로바이더 정보 추가
                "provider": settings.get_current_llm_provider(),
                "embedding_provider": settings.get_current_embedding_provider(),
                "llm_model": settings.get_current_llm_model(),
                "embedding_model": settings.get_current_embedding_model(),
                # 멀티턴 컨텍스트 정보
                "multiturn_context": context_metadata.get("context_used", False),
                "original_query": context_metadata.get("original_query", search_params.query),
                "enhanced_query": context_metadata.get("enhanced_query", search_params.query),
                "topic_continuity": context_metadata.get("topic_continuity", 0.0),
                "accumulated_keywords": context_metadata.get("accumulated_keywords", [])
            }
            
            logger.info(f"✅ RAG 검색 완료: {len(search_results)}개 청크, "
                       f"{total_tokens}토큰, {search_stats['search_time']:.2f}초")
            
            return RAGSearchResult(
                chunks=search_results,
                used_chunks=used_chunks,
                context_text=context_text,
                total_tokens=total_tokens,
                search_stats=search_stats,
                reranking_applied=reranking_applied
            )
            
        except Exception as e:
            logger.error(f"RAG 검색 실패: {str(e)}")
            return RAGSearchResult(
                chunks=[],
                used_chunks=[],
                context_text="",
                total_tokens=0,
                search_stats={"error": str(e), "search_time": time.time() - start_time},
                reranking_applied=False
            )

    def _detect_ppt_intent(self, query: str) -> bool:
        try:
            if not isinstance(query, str):
                return False
            q = query.lower()
            # PPT 키워드와 생성 의도 키워드 동시 포함 시 PPT 의도
            creation = any(k in q for k in ["만들", "작성", "생성", "제작"])
            has_ppt = any(k in q for k in self._ppt_query_keywords)
            return bool(creation and has_ppt)
        except Exception:
            return False

    def _boost_for_ppt_intent(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """PPT 의도일 때 템플릿/샘플/PPT 파일 및 헤더성 청크에 가중치 부여."""
        boosted: List[Dict[str, Any]] = []
        for r in results:
            score = self._score_of(r)
            fname = (r.get("file_name") or "").lower()
            sec = (r.get("section_title") or "").lower()
            content = (r.get("content") or "").lower()
            boost = 0.0
            # 파일명 기반 부스팅
            if any(k in fname for k in [".ppt", ".pptx", "template", "샘플", "sample", "템플릿", "소개서"]):
                boost += 0.15
            # 섹션/내용에 목차·개요·요약·슬라이드 등 키워드
            if any(k in sec for k in ["목차", "개요", "요약", "outline", "overview", "슬라이드", "title", "제목"]):
                boost += 0.08
            elif any(k in content for k in ["목차", "개요", "요약", "outline", "overview"]):
                boost += 0.05
            r2 = r.copy()
            # combined_score가 있으면 거기에, 없으면 similarity_score 기반으로 합산
            base = r2.get("combined_score", r2.get("similarity_score", score))
            r2["combined_score"] = base + boost
            boosted.append(r2)
        # 부스팅 반영하여 재정렬
        boosted_sorted = sorted(boosted, key=lambda x: x.get("combined_score", 0.0), reverse=True)
        logger.info(f"🎯 PPT 의도 부스팅 적용: 상위 점수 {boosted_sorted[0].get('combined_score', 0):.2f} (총 {len(boosted_sorted)})")
        return boosted_sorted
    
    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        질의 분석 - 통합 파이프라인 사용
        
        변경 사항 (2025-10-17):
        - 통합 파이프라인 (process_user_query) 사용
        - 일관된 불용어 제거 (UNIFIED_STOPWORDS)
        - RAG 전용 검색 전략 적용
        """
        try:
            # 통합 파이프라인으로 질의 처리 (RAG 모드)
            processed = await process_user_query(query, search_type="rag")
            
            logger.info(f"✅ RAG 파이프라인 처리 완료: {processed.processing_time_ms:.1f}ms")
            logger.info(f"  - 의도: {processed.intent} (confidence: {processed.intent_confidence:.2f})")
            logger.info(f"  - 키워드: {processed.keywords} → {processed.filtered_keywords}")
            logger.info(f"🔍 추출된 키워드: {processed.filtered_keywords} (총 {len(processed.filtered_keywords)}개)")
            
            # 기존 인터페이스 호환을 위한 변환
            return {
                "original_query": query,
                "korean_keywords": processed.filtered_keywords,  # 필터링된 키워드
                "named_entities": [],  # TODO: 개체명 인식 추가
                "pos_tags": [],  # TODO: 품사 태깅 추가
                "embedding": processed.vector_embedding,
                "query_type": self._classify_query_type_from_intent(processed.intent),
                "intent_keywords": processed.filtered_keywords
            }
            
        except Exception as e:
            logger.error(f"❌ RAG 파이프라인 처리 실패: {str(e)}")
            return {"original_query": query, "error": str(e)}
    
    def _classify_query_type_from_intent(self, intent: str) -> str:
        """의도를 RAG 질의 유형으로 변환"""
        intent_mapping = {
            "qa_question": "question",
            "document_search": "information",
            "comparison": "information",
            "summarization": "general",
            "keyword_search": "general"
        }
        return intent_mapping.get(intent, "general")
    
    def _classify_query_type(self, query: str, nlp_result: Dict[str, Any]) -> str:
        """질의 유형 분류"""
        keywords = nlp_result.get("keywords", [])  # 👈 keywords로 수정
        
        # 질문형 패턴
        question_patterns = ["무엇", "어떻게", "왜", "언제", "어디서", "누가", "?"]
        if any(pattern in query for pattern in question_patterns):
            return "question"
        
        # 정보 검색형
        info_patterns = ["설명", "정보", "내용", "자료", "문서"]
        if any(keyword in info_patterns for keyword in keywords):
            return "information"
        
        # 절차/방법 검색형
        procedure_patterns = ["방법", "절차", "과정", "단계", "프로세스"]
        if any(keyword in procedure_patterns for keyword in keywords):
            return "procedure"
        
        return "general"
    
    def _extract_intent_keywords(self, nlp_result: Dict[str, Any]) -> List[str]:
        """의도 키워드 추출"""
        keywords = nlp_result.get("keywords", [])  # 👈 keywords로 수정
        entities = nlp_result.get("proper_nouns", [])  # 👈 proper_nouns로 수정
        
        # 중요 명사 및 고유명사 추출
        intent_keywords = []
        for keyword in keywords:
            if len(keyword) > 1:  # 2글자 이상
                intent_keywords.append(keyword)
        
        for entity in entities:
            if entity not in intent_keywords:
                intent_keywords.append(entity)
        
        return intent_keywords[:10]  # 상위 10개만
        
        return intent_keywords[:10]  # 상위 10개만
    
    async def _execute_hybrid_search(
        self,
        session: AsyncSession,
        search_params: RAGSearchParams,
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """하이브리드 검색 실행"""
        try:
            if search_params.search_mode == "semantic":
                return await self._semantic_search(session, search_params, query_analysis)
            elif search_params.search_mode == "keyword":
                return await self._keyword_search(session, search_params, query_analysis)
            else:  # hybrid
                return await self._hybrid_search(session, search_params, query_analysis)
                
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {str(e)}")
            logger.error(f"검색 모드: {search_params.search_mode}, 쿼리: '{search_params.query[:100]}...'")
            # 빈 결과 반환하여 시스템이 계속 동작하도록 함
            return []
    
    async def _semantic_search(
        self,
        session: AsyncSession,
        search_params: RAGSearchParams,
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """의미적 유사도 검색 (Option B: 다단계 threshold 완화 재시도)"""
        if not query_analysis.get("embedding"):
            logger.warning("임베딩이 없어 의미적 검색 불가")
            return []

        embedding_vector = query_analysis["embedding"]

        # 컨텍스트/필터 상태 기반 하한값 보정
        # ⚠️ 2025-10-17: 하한값 대폭 완화 (recall 향상)
        min_floor = 0.22  # 0.28 → 0.22 (전체 검색 모드)
        if search_params.container_ids:
            min_floor = 0.20  # 0.25 → 0.20
        if search_params.document_ids:
            min_floor = 0.18  # 0.20 → 0.18 (0.268 매칭 가능)

        attempt_threshold = max(min_floor, search_params.similarity_threshold)
        attempts = 0
        all_results: List[Dict[str, Any]] = []

        # 🔷🟧 프로바이더별 벡터 컬럼 동적 선택
        provider = settings.get_current_embedding_provider()
        embedding_dim = len(embedding_vector)
        
        if provider == 'bedrock' or embedding_dim == 1024:
            # AWS Bedrock: Titan 1024d
            vector_column = "tdc.aws_embedding_1024"
            vector_not_null = "tdc.aws_embedding_1024 IS NOT NULL"
            logger.info(f"[RAG-SEARCH] 🟧 AWS Bedrock 벡터 검색 (aws_embedding_1024, {embedding_dim}d)")
        elif provider == 'azure_openai' or embedding_dim == 1536:
            # Azure OpenAI: text-embedding-3-small 1536d
            vector_column = "tdc.azure_embedding_1536"
            vector_not_null = "tdc.azure_embedding_1536 IS NOT NULL"
            logger.info(f"[RAG-SEARCH] 🔷 Azure OpenAI 벡터 검색 (azure_embedding_1536, {embedding_dim}d)")
        else:
            # 레거시 폴백
            vector_column = "tdc.chunk_embedding"
            vector_not_null = "tdc.chunk_embedding IS NOT NULL"
            logger.warning(f"[RAG-SEARCH] ⚠️ 레거시 벡터 컬럼 폴백 ({embedding_dim}d)")

        while attempts < 3:
            base_query = f"""
                SELECT 
                    tdc.file_bss_info_sno,
                    tdc.chunk_index,
                    tdc.chunk_text,
                    tdc.page_number,
                    tdc.section_title,
                    tdc.keywords,
                    tdc.named_entities,
                    tdc.knowledge_container_id,
                    1 - ({vector_column} <=> :embedding_vector) as similarity_score,
                    fbi.file_lgc_nm as file_name
                FROM vs_doc_contents_chunks tdc
                JOIN tb_file_bss_info fbi ON tdc.file_bss_info_sno = fbi.file_bss_info_sno
                WHERE {vector_not_null}
                AND tdc.del_yn = 'N'
                AND fbi.del_yn = 'N'
                AND 1 - ({vector_column} <=> :embedding_vector) > :threshold
            """

            conditions = []
            if search_params.container_ids:
                conditions.append("AND tdc.knowledge_container_id = ANY(:container_ids)")
            if search_params.document_ids:
                conditions.append("AND fbi.file_bss_info_sno = ANY(:document_ids)")
                logger.info(f"🔍 문서 ID 필터링 적용: {search_params.document_ids}")
            if conditions:
                base_query += " " + " ".join(conditions)
            base_query += " ORDER BY similarity_score DESC LIMIT :limit"

            query_sql = text(base_query)
            params = {
                "embedding_vector": f"[{','.join(map(str, embedding_vector))}]",
                "threshold": attempt_threshold,
                "limit": search_params.max_chunks * 2
            }
            if search_params.container_ids:
                params["container_ids"] = search_params.container_ids
            if search_params.document_ids:
                try:
                    params["document_ids"] = [int(doc_id) for doc_id in search_params.document_ids]
                except ValueError:
                    params["document_ids"] = search_params.document_ids

            result = await session.execute(query_sql, params)
            rows = result.fetchall()
            logger.info(f"🔍 의미적 검색 SQL 실행 결과 (attempt {attempts+1}, threshold={attempt_threshold:.2f}): {len(rows)}개 행")

            all_results = []
            for row in rows:
                similarity_score = float(row[8])
                
                # NaN 값 필터링
                import math
                if math.isnan(similarity_score) or math.isinf(similarity_score):
                    logger.warning(f"RAG 검색에서 잘못된 점수 발견 (NaN/Inf): file={row[9]}")
                    continue
                
                all_results.append({
                    "file_bss_info_sno": row[0],
                    "chunk_index": row[1],
                    "content": row[2],
                    "page_number": row[3] if row[3] else 1,
                    "section_title": row[4] if row[4] else "",
                    "keywords": row[5] if row[5] else "",
                    "named_entities": row[6] if row[6] else "",
                    "container_id": row[7],
                    "similarity_score": similarity_score,
                    "file_name": row[9],
                    "chunk_type": "content",
                    "search_type": "semantic",
                    "metadata": {
                        "page_number": row[3] if row[3] else 1,
                        "section_title": row[4] if row[4] else "",
                        "keywords": row[5].split(',') if row[5] else [],
                        "named_entities": row[6].split(',') if row[6] else []
                    }
                })

            if all_results:
                logger.info(f"🔮 의미적 검색 결과 확보 (attempt {attempts+1}): {len(all_results)}개")
                break

            # 다음 시도 – threshold 완화
            attempt_threshold = max(min_floor, attempt_threshold - 0.05)
            attempts += 1
            if attempts < 3:
                logger.info(f"🔄 의미적 검색 재시도 준비 (새 threshold={attempt_threshold:.2f})")

        return all_results

    async def _validate_reference_quality(
        self,
        original_query: str,
        current_query: str,
        results: List[Dict[str, Any]],
        relax_filter: bool = False
    ) -> List[Dict[str, Any]]:
        """참고자료 품질 검증 - 주제 불일치 필터링"""
        try:
            if not results:
                return results
            if relax_filter:
                logger.info("🧩 도메인 필터 완화: 사용자 선택 문서 또는 PPT 의도 감지")
                return results
            
            # 도메인 카테고리 정의
            domain_categories = {
                "medical": {"의료", "병원", "치료", "질병", "약물", "의사", "환자", "건강", "인슐린", "펌프", "혈당", "당뇨", "수술", "진료", "의료기기"},
                "travel": {"여행", "관광", "호텔", "항공", "비자", "일본", "도쿄", "교토", "오사카", "관광지", "숙소", "여행지", "패키지", "투어", "항공권"},
                "technology": {"IT", "컴퓨터", "소프트웨어", "프로그래밍", "개발", "시스템", "네트워크", "데이터베이스", "클라우드", "AI", "기술"},
                "business": {"사업", "회사", "경영", "마케팅", "영업", "제품", "서비스", "고객", "매출", "투자", "계약", "전략", "비즈니스"},
                "education": {"교육", "학교", "학습", "수업", "강의", "시험", "졸업", "입학", "과정", "커리큘럼", "학생", "교사", "연구"}
            }
            
            # 현재 질문의 도메인 감지
            current_domain = self._detect_query_domain(current_query.lower(), domain_categories)
            
            if current_domain == "general":
                logger.info("🔍 일반 질문으로 분류 - 참고자료 필터링 생략")
                return results
            
            # 각 참고자료의 도메인 관련성 검사
            validated_results = []
            filtered_count = 0
            
            for result in results:
                content = result.get("content", "").lower()
                file_name = result.get("file_name", "").lower()
                
                # 참고자료의 도메인 관련성 점수 계산
                relevance_score = 0
                content_domain_keywords = domain_categories.get(current_domain, set())
                
                # 내용에서 도메인 키워드 매칭 점수
                for keyword in content_domain_keywords:
                    if keyword in content:
                        relevance_score += 2
                    if keyword in file_name:
                        relevance_score += 1
                
                # 다른 도메인 키워드 존재 시 패널티
                for other_domain, other_keywords in domain_categories.items():
                    if other_domain != current_domain:
                        for keyword in other_keywords:
                            if keyword in content:
                                relevance_score -= 1
                
                # 임계값 기준으로 필터링 (현재 도메인 키워드가 최소 1개 이상 있어야 함)
                min_threshold = 1
                if relevance_score >= min_threshold:
                    result["domain_relevance_score"] = relevance_score
                    validated_results.append(result)
                else:
                    filtered_count += 1
                    logger.debug(f"🚫 도메인 불일치로 필터링: {result.get('file_name', 'Unknown')} (score: {relevance_score})")
            
            if filtered_count > 0:
                logger.info(f"🔍 도메인 관련성 필터링: {len(results)}개 → {len(validated_results)}개 (도메인: {current_domain}, 제외: {filtered_count}개)")
            
            # 필터링 후 결과가 너무 적으면 원본 유지 (over-filtering 방지)
            if len(validated_results) < max(1, len(results) * 0.3):
                logger.warning(f"⚠️ 과도한 필터링 감지 - 원본 결과 유지 ({len(validated_results)} < {len(results) * 0.3:.1f})")
                return results
            
            return validated_results
            
        except Exception as e:
            logger.error(f"❌ 참고자료 품질 검증 실패: {e}")
            return results
    
    def _detect_query_domain(self, query: str, domain_categories: dict) -> str:
        """질문에서 도메인 감지"""
        domain_scores = {}
        
        for domain, keywords in domain_categories.items():
            score = 0
            for keyword in keywords:
                if keyword in query:
                    score += 1
            domain_scores[domain] = score
        
        # 가장 높은 점수의 도메인 반환 (최소 임계값 이상)
        max_domain = max(domain_scores.items(), key=lambda x: x[1])
        if max_domain[1] >= 1:  # 최소 1개 키워드 매칭
            return max_domain[0]
        return "general"
    
    async def _keyword_search(
        self,
        session: AsyncSession,
        search_params: RAGSearchParams,
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """키워드 기반 검색 (Option A/B: 정규화 + 핵심어 AND + 가중 rank)"""
        raw_keywords = query_analysis.get("korean_keywords", []) or []
        if not raw_keywords:
            logger.warning("키워드가 없어 키워드 검색 불가")
            return []

        original_user_query = (search_params.original_query or search_params.query).strip()

        # Stopword / 일반어 (모두 lower)
        exclude_words = {
            '이전','user','사용자','질문','문의','답변','대화','채팅','현재','시스템','상태','확인','정보','내용','문서','자료','검색','결과',
            '일본','여행','도쿄','교토','오사카','후지산','관광','여행지','호텔','경치','호수','도시','아래','공존','방문','추천','각사','기온','센소지','사원','타워','금각사','은각사','거리','음식','나이트','등산','주변','비자','항공권','숙소','료칸','교통','패스','예절','언어','영어','표현','계획','목적지','요소','풍경','전통','명소','신주쿠','시부야','아사쿠사','도톤보리',
            '데이터','목록','리스트','항목','방법','관련','기능','설정','관리','서비스','요청','응답','처리','실행','로그','오류','문제','해결','방안','제안','의견','생각','하이브리드','의미적','키워드','검색어','결과물','토큰','청크','컨텍스트','세션'
        }

        # 핵심 도메인 키워드 추출 (원문 그대로 / 소문자)
        core_tokens = []
        for token in [t.strip() for t in re.split(r'[\s,/]+', original_user_query) if t.strip()]:
            lower = token.lower()
            # PPT 작성 의도 관련 핵심 보존 토큰
            if any(k in lower for k in ['ppt', '제품', '소개', '인슐린', '펌프', '슬라이드']):
                if token not in core_tokens:
                    core_tokens.append(token)

        # 복합어 분해 및 동의어 확장 포함 정규화
        normalized: List[str] = []
        for kw in raw_keywords:
            nk = kw.strip().lower()
            if len(nk) < 2:
                continue
            if nk in exclude_words:
                continue
            if nk.isdigit():
                continue
            # 복합어 분해 (예: '제품소개' → ['제품','소개'])
            parts = self._split_korean_compound(nk) or [nk]
            for p in parts:
                if p and p not in exclude_words:
                    normalized.append(p)
            # 동의어 확장 (과하지 않게 소수만)
            for syn in self._expand_synonyms(nk):
                if syn not in exclude_words:
                    normalized.append(syn)

        # 중복 제거 (순서 유지)
        seen = set()
        filtered_keywords = []
        for nk in normalized:
            if nk not in seen:
                seen.add(nk)
                filtered_keywords.append(nk)

        # 핵심 토큰이 필터링에서 빠졌다면 별도 보강
        core_keywords = []
        
        # PPT 관련 쿼리에서는 core 키워드를 사용하지 않음 (검색 범위를 넓히기 위해)
        is_ppt_related = search_params.query and any(term in search_params.query.lower() 
                                                    for term in ['ppt', 'powerpoint', '프레젠테이션', '발표자료', '제품소개서', '소개서'])
        
        if not is_ppt_related:
            for ct in core_tokens:
                cl = ct.lower()
                if cl not in exclude_words and cl not in filtered_keywords:
                    core_keywords.append(cl)

        if not filtered_keywords and not core_keywords:
            logger.info(f"⚠️ 키워드 필터 후 유효 키워드 없음: raw={raw_keywords}")
            return []

        # 최대 3개 일반 키워드만 사용
        main_keywords = filtered_keywords[:3]
        logger.info(f"🔍 키워드 검색 대상(main): {main_keywords}, core: {core_keywords} (PPT관련: {is_ppt_related})")
        logger.debug(f"🔍 키워드 검색 매개변수 - container_ids: {search_params.container_ids}, document_ids: {search_params.document_ids}")

        # rank_score 구성
        rank_parts = []
        for i, _ in enumerate(main_keywords):
            rank_parts.append(f"(CASE WHEN tdc.chunk_text ILIKE :kw_{i} THEN 1 ELSE 0 END)")
        core_weight = 2
        for j, _ in enumerate(core_keywords):
            rank_parts.append(f"(CASE WHEN tdc.chunk_text ILIKE :core_{j} THEN {core_weight} ELSE 0 END)")
        if not rank_parts:
            rank_expr = "1.0"  # fallback
        else:
            rank_expr = " + ".join(rank_parts)

        # WHERE 절 구성
        # 기본: ( (kw OR kw OR ...) AND (core OR core ...) )
        # 필터(컨테이너/문서)가 있는 경우: 느슨한 매칭으로 0건 방지 → (kw OR core) 만 요구
        kw_conditions = []
        for i, _ in enumerate(main_keywords):
            kw_conditions.append(f"tdc.chunk_text ILIKE :kw_{i}")
        kw_clause = " OR ".join(kw_conditions) if kw_conditions else ""

        core_conditions = []
        for j, _ in enumerate(core_keywords):
            core_conditions.append(f"tdc.chunk_text ILIKE :core_{j}")
        core_clause = " OR ".join(core_conditions)

        where_fragments = []
        loosen_match = bool(search_params.container_ids or search_params.document_ids)
        
        # PPT 관련 질문의 경우 core 키워드를 너무 엄격하게 적용하지 않음
        is_ppt_query = search_params.query and any(term in search_params.query.lower() 
                                                  for term in ['ppt', 'powerpoint', '프레젠테이션', '발표자료', '제품소개서'])
        
        if loosen_match or is_ppt_query:
            # 느슨: kw 또는 core 중 하나라도 매칭되면 후보로
            oc = []
            if kw_clause:
                oc.append(f"({kw_clause})")
            if core_clause:
                oc.append(f"({core_clause})")
            where_clause = " OR ".join(oc) if oc else "1=1"
        else:
            if kw_clause:
                where_fragments.append(f"({kw_clause})")
            if core_clause:
                # 핵심어가 있다면 반드시 하나는 매칭되도록 AND 그룹으로 추가
                where_fragments.append(f"({core_clause})")
            where_clause = " AND ".join(where_fragments) if where_fragments else "1=1"

        base_sql = f"""
            SELECT 
                tdc.file_bss_info_sno,
                tdc.chunk_index,
                tdc.chunk_text,
                tdc.page_number,
                tdc.section_title,
                tdc.keywords,
                tdc.named_entities,
                tdc.knowledge_container_id,
                {rank_expr} AS rank_score,
                fbi.file_lgc_nm AS file_name
            FROM vs_doc_contents_chunks tdc
            JOIN tb_file_bss_info fbi ON tdc.file_bss_info_sno = fbi.file_bss_info_sno
            WHERE {where_clause}
              AND tdc.del_yn = 'N'
              AND fbi.del_yn = 'N'
        """

        if search_params.container_ids and len(search_params.container_ids) > 0:
            base_sql += " AND tdc.knowledge_container_id = ANY(:container_ids)"
        if search_params.document_ids and len(search_params.document_ids) > 0:
            base_sql += " AND fbi.file_bss_info_sno = ANY(:document_ids)"

        base_sql += " ORDER BY rank_score DESC LIMIT :limit"

        query_sql = text(base_sql)
        params: Dict[str, Any] = {"limit": search_params.max_chunks * 2}
        for i, kw in enumerate(main_keywords):
            params[f"kw_{i}"] = f"%{kw}%"
        for j, ck in enumerate(core_keywords):
            params[f"core_{j}"] = f"%{ck}%"
        if search_params.container_ids:
            params["container_ids"] = search_params.container_ids
        if search_params.document_ids:
            params["document_ids"] = self._normalize_document_ids(search_params.document_ids)

        result = await session.execute(query_sql, params)
        rows = result.fetchall()
        
        logger.debug(f"🔍 키워드 검색 SQL 실행됨 - 매개변수: {params}")
        logger.info(f"🔤 키워드 검색 결과: {len(rows)}개 (raw rows from DB)")
        
        if len(rows) == 0:
            logger.warning(f"🔍 키워드 검색 결과 0개 - SQL 확인이 필요할 수 있음")
            logger.debug(f"🔍 실행된 SQL: {base_sql}")
            logger.debug(f"🔍 SQL 매개변수: {params}")

        search_results: List[Dict[str, Any]] = []
        for row in rows:
            rank_score = float(row[8]) if row[8] is not None else 0.0
            # 정규화: (최대 가능한 점수 대비) – 최대는 len(main)+core_weight*len(core)
            denom = max(1.0, len(main_keywords) + core_weight * len(core_keywords))
            similarity_score = rank_score / denom
            search_results.append({
                "file_bss_info_sno": row[0],
                "chunk_index": row[1],
                "content": row[2],
                "page_number": row[3] if row[3] else 1,
                "section_title": row[4] if row[4] else "",
                "keywords": row[5] if row[5] else "",
                "named_entities": row[6] if row[6] else "",
                "container_id": row[7],
                "similarity_score": similarity_score,
                "file_name": row[9],
                "chunk_type": "content",
                "search_type": "keyword",
                "metadata": {
                    "page_number": row[3] if row[3] else 1,
                    "section_title": row[4] if row[4] else "",
                    "keywords": row[5].split(',') if row[5] else [],
                    "named_entities": row[6].split(',') if row[6] else []
                }
            })

        logger.info(f"🔤 키워드 검색 결과: {len(search_results)}개 (core AND 적용 여부: {bool(core_keywords)})")
        return search_results
    
    async def _fulltext_search(
        self,
        session: AsyncSession,
        search_params: RAGSearchParams,
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        전문검색 (tsvector) - tb_document_search_index 활용
        
        다국어 지원:
        - 한국어: korean configuration (textsearch_ko 확장)
        - 영어: english configuration (stemming, stopwords)
        - 혼합: korean + english dual search
        
        예시:
        - '혁신' → 'innovation', 'innovative' 자동 매칭 (textsearch_ko)
        - 'Ambidextrous Leadership' → 'ambidextr', 'leadership' stemming 매칭
        """
        keywords = query_analysis.get("korean_keywords", [])
        if not keywords:
            logger.info("📚 전문검색: 키워드 없음 - 건너뛰기")
            return []
        
        # 조사 제거 및 불용어 필터링
        stopwords = {'뭐', '뭐라', '뭐라고', '하나요', '있나요', '있어요', '대해', '에서', '으로', '로서', '어떤', '어떻게', '무엇'}
        filtered_keywords = []
        for kw in keywords:
            # 조사 제거
            cleaned_kw = self._remove_korean_josa(kw)
            if cleaned_kw and cleaned_kw.lower() not in stopwords and len(cleaned_kw) > 1:
                filtered_keywords.append(cleaned_kw)
        
        if not filtered_keywords:
            logger.info("📚 전문검색: 조사 제거 후 키워드 없음 - 건너뛰기")
            return []
        
        # 언어 감지 (최적화된 FTS configuration 선택용)
        query_language = self._detect_query_language(search_params.query)
        logger.info(f"📚 전문검색 시작: 키워드 {keywords} → 필터링 후 {filtered_keywords}")
        logger.info(f"🌐 쿼리 언어 감지: {query_language} (ko=한국어, en=영어, mixed=혼합)")
        
        # 검색어 준비 (OR 검색)
        search_terms = ' | '.join(filtered_keywords)
        
        # SQL 쿼리 구성 (한국어 + 영어 + simple 멀티 언어 지원)
        base_sql = """
            WITH search_query AS (
                SELECT 
                    plainto_tsquery('korean', :search_terms) as query_korean,
                    plainto_tsquery('english', :search_terms) as query_english,
                    plainto_tsquery('simple', :search_terms) as query_simple
            )
            SELECT 
                dsi.file_bss_info_sno,
                dsi.search_doc_id,
                dsi.document_title as file_name,
                GREATEST(
                    ts_rank(dsi.content_tsvector, sq.query_korean),
                    ts_rank(dsi.content_tsvector_en, sq.query_english),
                    ts_rank(dsi.keyword_tsvector, sq.query_korean),
                    ts_rank(dsi.keyword_tsvector_en, sq.query_english),
                    ts_rank(dsi.content_tsvector, sq.query_simple)
                ) as rank,
                dsi.full_content,
                dsi.has_images,
                dsi.image_count,
                ts_headline('korean', 
                    COALESCE(substring(dsi.full_content, 1, 1000), ''), 
                    sq.query_korean,
                    'MaxWords=50, MinWords=20, ShortWord=3'
                ) as snippet
            FROM tb_document_search_index dsi
            CROSS JOIN search_query sq
            WHERE (
                dsi.content_tsvector @@ sq.query_korean 
                OR dsi.content_tsvector_en @@ sq.query_english
                OR dsi.keyword_tsvector @@ sq.query_korean
                OR dsi.keyword_tsvector_en @@ sq.query_english
                OR dsi.content_tsvector @@ sq.query_simple
            )
            AND dsi.file_bss_info_sno IS NOT NULL
        """
        
        # 문서 ID 필터링 추가
        conditions = []
        params = {"search_terms": search_terms}
        
        if search_params.document_ids:
            conditions.append("AND dsi.file_bss_info_sno = ANY(:document_ids)")
            params["document_ids"] = self._normalize_document_ids(search_params.document_ids)
        
        if search_params.container_ids:
            conditions.append("AND dsi.knowledge_container_id = ANY(:container_ids)")
            params["container_ids"] = search_params.container_ids
        
        # 조건 추가
        if conditions:
            base_sql += " " + " ".join(conditions)
        
        # 정렬 및 제한
        base_sql += """
            ORDER BY rank DESC
            LIMIT :limit
        """
        params["limit"] = 20  # 전문검색 결과 제한
        
        try:
            # SQL 실행
            result = await session.execute(text(base_sql), params)
            rows = result.fetchall()
            
            logger.info(f"📚 전문검색 SQL 실행 결과: {len(rows)}개 문서")
            
            if len(rows) == 0:
                logger.info(f"📚 전문검색 결과 없음 - 검색어: '{search_terms}'")
                return []
            
            # 문서별로 청크 조회
            search_results: List[Dict[str, Any]] = []
            
            for row in rows:
                # row[0]: file_bss_info_sno
                # row[1]: search_doc_id
                # row[2]: file_name
                # row[3]: rank (GREATEST 결과)
                # row[4]: full_text
                # row[5]: has_images
                # row[6]: image_count
                # row[7]: snippet
                file_bss_info_sno = row[0]
                rank_score = float(row[3]) if row[3] else 0.0
                snippet = row[7] if row[7] else ""
                
                # 해당 문서의 청크들을 조회 (상위 5개만)
                chunk_sql = """
                    SELECT 
                        tdc.file_bss_info_sno,
                        tdc.chunk_index,
                        tdc.chunk_text,
                        tdc.page_number,
                        tdc.section_title,
                        tdc.keywords,
                        tdc.named_entities,
                        tdc.knowledge_container_id,
                        fbi.file_lgc_nm as file_name
                    FROM vs_doc_contents_chunks tdc
                    JOIN tb_file_bss_info fbi ON tdc.file_bss_info_sno = fbi.file_bss_info_sno
                    WHERE tdc.file_bss_info_sno = :file_id
                      AND tdc.del_yn = 'N'
                      AND fbi.del_yn = 'N'
                """
                
                # 키워드로 청크 필터링 (청크 내용에 키워드가 있는 것만)
                chunk_conditions = []
                for i, kw in enumerate(filtered_keywords[:3]):  # 최대 3개 키워드만 사용
                    chunk_conditions.append(f"tdc.chunk_text ILIKE :kw_{i}")
                
                if chunk_conditions:
                    chunk_sql += " AND (" + " OR ".join(chunk_conditions) + ")"
                
                chunk_sql += " ORDER BY tdc.chunk_index LIMIT 5"
                
                chunk_params = {"file_id": file_bss_info_sno}
                for i, kw in enumerate(filtered_keywords[:3]):
                    chunk_params[f"kw_{i}"] = f"%{kw}%"
                
                chunk_result = await session.execute(text(chunk_sql), chunk_params)
                chunk_rows = chunk_result.fetchall()
                
                # 청크들을 결과에 추가
                for chunk_row in chunk_rows:
                    search_results.append({
                        "file_bss_info_sno": chunk_row[0],
                        "chunk_index": chunk_row[1],
                        "content": chunk_row[2],
                        "page_number": chunk_row[3] if chunk_row[3] else 1,
                        "section_title": chunk_row[4] if chunk_row[4] else "",
                        "keywords": chunk_row[5] if chunk_row[5] else "",
                        "named_entities": chunk_row[6] if chunk_row[6] else "",
                        "container_id": chunk_row[7],
                        "similarity_score": rank_score,  # 문서 rank 점수 사용
                        "file_name": chunk_row[8],
                        "chunk_type": "content",
                        "search_type": "fulltext",
                        "metadata": {
                            "page_number": chunk_row[3] if chunk_row[3] else 1,
                            "section_title": chunk_row[4] if chunk_row[4] else "",
                            "keywords": chunk_row[5].split(',') if chunk_row[5] else [],
                            "named_entities": chunk_row[6].split(',') if chunk_row[6] else [],
                            "snippet": snippet
                        }
                    })
            
            logger.info(f"📚 전문검색 완료: {len(search_results)}개 청크")
            return search_results
            
        except Exception as e:
            logger.error(f"❌ 전문검색 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _remove_korean_josa(self, word: str) -> str:
        """한국어 조사 제거"""
        josa_list = ['은', '는', '이', '가', '을', '를', '에', '의', '와', '과', '도', '로', '으로', '부터', '까지', '만', '에게', '한테', '에서', '으로서', '로서']
        for josa in josa_list:
            if word.endswith(josa) and len(word) > len(josa) + 1:
                return word[:-len(josa)]
        return word
    
    async def _hybrid_search(
        self,
        session: AsyncSession,
        search_params: RAGSearchParams,
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """하이브리드 검색 (의미적 + 키워드 + 전문검색)"""
        # 병렬로 세 가지 검색 실행
        semantic_results = await self._semantic_search(session, search_params, query_analysis)
        keyword_results = await self._keyword_search(session, search_params, query_analysis)
        fulltext_results = await self._fulltext_search(session, search_params, query_analysis)
        
        # 결과 통합 및 점수 조합
        combined_results = {}
        
        # 의미적 검색 결과 추가
        for result in semantic_results:
            key = f"{result['file_bss_info_sno']}_{result['chunk_index']}"
            combined_results[key] = {
                **result,
                "semantic_score": result["similarity_score"],
                "keyword_score": 0.0,
                "fulltext_score": 0.0,
                "combined_score": result["similarity_score"] * search_params.semantic_boost
            }
        
        # 키워드 검색 결과 통합
        for result in keyword_results:
            key = f"{result['file_bss_info_sno']}_{result['chunk_index']}"
            if key in combined_results:
                # 기존 결과에 키워드 점수 추가
                combined_results[key]["keyword_score"] = result["similarity_score"]
                combined_results[key]["combined_score"] = (
                    combined_results[key]["semantic_score"] * search_params.semantic_boost +
                    result["similarity_score"] * search_params.keyword_boost
                )
                combined_results[key]["search_type"] = "hybrid"
            else:
                # 새 결과 추가
                combined_results[key] = {
                    **result,
                    "semantic_score": 0.0,
                    "keyword_score": result["similarity_score"],
                    "fulltext_score": 0.0,
                    "combined_score": result["similarity_score"] * search_params.keyword_boost
                }
        
        # 전문검색 결과 통합 (가중치 0.6 - 키워드보다 높게 설정)
        fulltext_boost = 0.6
        for result in fulltext_results:
            key = f"{result['file_bss_info_sno']}_{result['chunk_index']}"
            if key in combined_results:
                # 기존 결과에 전문검색 점수 추가
                combined_results[key]["fulltext_score"] = result["similarity_score"]
                combined_results[key]["combined_score"] += result["similarity_score"] * fulltext_boost
                combined_results[key]["search_type"] = "hybrid"
            else:
                # 새 결과 추가
                combined_results[key] = {
                    **result,
                    "semantic_score": 0.0,
                    "keyword_score": 0.0,
                    "fulltext_score": result["similarity_score"],
                    "combined_score": result["similarity_score"] * fulltext_boost
                }
        
        # 통합 점수로 정렬
        final_results = sorted(
            combined_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        logger.info(f"🔄 하이브리드 검색 결과: {len(final_results)}개 "
                   f"(의미적: {len(semantic_results)}, 키워드: {len(keyword_results)}, 전문검색: {len(fulltext_results)})")
        
        # RAG 검색 품질 필터링 적용
        final_results = self._apply_rag_quality_filter(final_results, search_params, query_analysis)
        
        return final_results
    
    async def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        target_count: int
    ) -> List[Dict[str, Any]]:
        """검색 결과 리랭킹"""
        try:
            logger.info(f"🔄 리랭킹 시작: {len(results)}개 → {target_count}개")
            
            # 설정된 AI 서비스를 사용한 리랭킹
            rerank_prompt = f"""
다음 질문에 대해 제공된 문서 청크들을 관련성 순으로 정렬해주세요.

질문: {query}

문서 청크들:
"""
            
            for i, result in enumerate(results):
                content_preview = result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"]
                rerank_prompt += f"{i+1}. {content_preview}\n\n"
            
            rerank_prompt += """
위 청크들을 질문과의 관련성이 높은 순서대로 번호만 나열해주세요.
예: 3, 1, 7, 2, 5
"""
            
            # 설정된 AI 서비스에게 리랭킹 요청
            try:
                from app.services.core.ai_service import ai_service
                from app.core.config import settings
                from langchain_openai import AzureChatOpenAI
                from langchain.schema import HumanMessage
                
                # 리랭킹 전용 설정이 있으면 사용, 없으면 Settings 기반 기본값 사용
                rerank_endpoint = settings.rag_reranking_endpoint or settings.azure_openai_endpoint
                rerank_deployment = settings.rag_reranking_deployment or settings.azure_openai_llm_deployment
                rerank_api_key = settings.rag_reranking_api_key or settings.azure_openai_api_key
                rerank_api_version = settings.rag_reranking_api_version or settings.azure_openai_api_version

                if not (rerank_endpoint and rerank_deployment and rerank_api_key):
                    logger.info("⚠️ 리랭킹 전용 설정 없음 - 기본 Azure OpenAI 설정으로 fallback")
                    rerank_endpoint = settings.azure_openai_endpoint
                    rerank_deployment = settings.azure_openai_llm_deployment
                    rerank_api_key = settings.azure_openai_api_key
                    rerank_api_version = settings.azure_openai_api_version

                if not (rerank_endpoint and rerank_deployment and rerank_api_key):
                    raise ValueError("리랭킹에 사용할 Azure OpenAI 설정을 찾을 수 없습니다.")

                # Azure OpenAI 클라이언트 생성
                deployment_lower = rerank_deployment.lower()

                # gpt-5, nano, o1, o3 모델은 Reasoning 계열 → max_completion_tokens 사용
                if 'gpt-5' in deployment_lower or 'nano' in deployment_lower or 'o1' in deployment_lower or 'o3' in deployment_lower:
                    logger.info(f"🔧 리랭킹 모델: {rerank_deployment} (Reasoning 계열: max_completion_tokens 사용)")
                    rerank_max_completion_tokens = settings.rag_reranking_max_completion_tokens
                    rerank_reasoning_effort = settings.rag_reranking_reasoning_effort
                    model_kwargs: Dict[str, Any] = {"max_completion_tokens": rerank_max_completion_tokens}
                    if rerank_reasoning_effort:
                        model_kwargs["reasoning_effort"] = rerank_reasoning_effort
                    rerank_llm = AzureChatOpenAI(
                        azure_endpoint=rerank_endpoint,
                        api_key=rerank_api_key,
                        api_version=rerank_api_version,
                        deployment_name=rerank_deployment,
                        model_kwargs=model_kwargs
                    )
                else:
                    logger.info(f"🔧 리랭킹 모델: {rerank_deployment} (temperature 지원)")
                    rerank_temperature = settings.rag_reranking_temperature
                    rerank_max_tokens = settings.rag_reranking_max_tokens
                    rerank_llm = AzureChatOpenAI(
                        azure_endpoint=rerank_endpoint,
                        api_key=rerank_api_key,
                        api_version=rerank_api_version,
                        deployment_name=rerank_deployment,
                        temperature=rerank_temperature,
                        max_tokens=rerank_max_tokens  # 일반 모델은 max_tokens 사용
                    )
                
                # 리랭킹 실행
                response = await rerank_llm.ainvoke([HumanMessage(content=rerank_prompt)])
                rerank_response = response.content if hasattr(response, 'content') else str(response)
            except Exception as ai_error:
                logger.warning(f"AI 서비스 리랭킹 실패, 기본 순서 사용: {ai_error}")
                # 폴백: 기본 유사도 순서 사용
                reranked_results = results[:target_count]
                for i, result in enumerate(reranked_results):
                    result["rerank_score"] = (target_count - i) / target_count
                logger.info(f"✅ 리랭킹 완료: {len(reranked_results)}개 선택 (기본 순서)")
                return reranked_results
            
            # 응답에서 순서 추출
            reranked_order = self._parse_rerank_response(rerank_response, len(results))
            
            # 새로운 순서로 결과 재정렬
            reranked_results = []
            for idx in reranked_order[:target_count]:
                if 0 <= idx < len(results):
                    result = results[idx].copy()
                    result["rerank_score"] = (target_count - len(reranked_results)) / target_count
                    reranked_results.append(result)
            
            logger.info(f"✅ 리랭킹 완료: {len(reranked_results)}개 선택")
            return reranked_results
            
        except Exception as e:
            logger.error(f"리랭킹 실패: {str(e)}")
            # 리랭킹 실패시 원본 점수 순으로 반환
            return sorted(results, key=lambda x: x.get("combined_score", 0), reverse=True)[:target_count]
    
    def _parse_rerank_response(self, response: str, total_count: int) -> List[int]:
        """리랭킹 응답에서 순서 추출"""
        try:
            # 숫자만 추출
            import re
            numbers = re.findall(r'\d+', response)
            reranked_order = []
            
            for num_str in numbers:
                num = int(num_str) - 1  # 0-based index로 변환
                if 0 <= num < total_count and num not in reranked_order:
                    reranked_order.append(num)
            
            # 누락된 인덱스 추가
            for i in range(total_count):
                if i not in reranked_order:
                    reranked_order.append(i)
            
            return reranked_order
            
        except Exception as e:
            logger.error(f"리랭킹 응답 파싱 실패: {str(e)}")
            return list(range(total_count))  # 원본 순서 유지
    
    def _remove_duplicates(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 제거 (동일 파일의 동일 청크)"""
        seen = set()
        unique_results = []
        
        for result in search_results:
            # 파일ID와 청크 인덱스로 중복 확인
            key = (result.get("file_bss_info_sno"), result.get("chunk_index"))
            
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
                
        logger.info(f"🔄 중복 제거: {len(search_results)}개 → {len(unique_results)}개")
        return unique_results

    # ---------------------- 정책/유틸: 정규화·컷라인·동의어 ----------------------
    def _normalize_document_ids(self, raw_ids: List[Any]) -> List[int]:
        """문서 ID 입력을 file_bss_info_sno(int) 배열로 정규화.
        허용 형태: 123, "123", "doc_123_45", "DOC-123", "file-123" 등에서 123 추출."""
        normalized: List[int] = []
        for rid in raw_ids:
            if isinstance(rid, int):
                normalized.append(rid)
                continue
            try:
                # 순수 숫자 문자열
                normalized.append(int(str(rid)))
                continue
            except Exception:
                pass
            s = str(rid)
            m = re.search(r"(?i)(?:doc[_-]|file[_-])?(\d+)", s)
            if m:
                try:
                    normalized.append(int(m.group(1)))
                except Exception:
                    continue
        return normalized

    def _split_korean_compound(self, text: str) -> List[str]:
        """간단 복합어 분해: 자주 쓰이는 결합어를 어근으로 나눔 (예: 제품소개 → 제품, 소개)."""
        patterns = [
            ("제품소개", ["제품", "소개"]),
            ("회사소개", ["회사", "소개"]),
            ("제품설명", ["제품", "설명"]),
            ("기술문서", ["기술", "문서"]),
            ("요구사항정의", ["요구사항", "정의"]),
        ]
        for p, parts in patterns:
            if p in text:
                return parts
        # 공백/슬래시/쉼표 분리는 상위 로직에서 처리됨
        return []

    def _expand_synonyms(self, token: str) -> List[str]:
        """동의어/표기 변형 소량 확장."""
        synmap = {
            "소개": ["소개", "소개서", "소개자료", "overview", "introduction", "소개문"],
            "제품": ["제품", "상품", "product"],
            "ppt": ["ppt", "presentation", "슬라이드"],
            "문서": ["문서", "자료", "document"],
        }
        return synmap.get(token, [])

    def _score_of(self, item: Dict[str, Any]) -> float:
        return float(item.get("combined_score", item.get("similarity_score", 0.0)))

    def _apply_dynamic_cutline(self, results: List[Dict[str, Any]], params: RAGSearchParams) -> List[Dict[str, Any]]:
        """하이브리드 분포 기반 컷라인 적용.
        - 너무 많은 저점 결과 제거 (특히 필터 사용 시)
        - 최소 보존 개수는 max_chunks*2
        """
        if not results:
            return results
        keep_min = max(params.max_chunks * 2, 10)
        if len(results) <= keep_min:
            return results
        scores = [self._score_of(r) for r in results]
        scores_sorted = sorted(scores)
        median = scores_sorted[len(scores_sorted)//2]
        max_s = max(scores)
        # 컷라인: median과 0.9*max 중 더 낮은 값, 하지만 최소 하한 적용
        min_floor = 0.45
        if params.container_ids:
            min_floor = 0.40
        if params.document_ids:
            min_floor = 0.30
        cut = max(min_floor, min(0.9 * max_s, median))
        filtered = [r for r in results if self._score_of(r) >= cut]
        if len(filtered) < keep_min:
            return results  # 과도 필터 방지
        logger.info(f"✂️ 분포 컷라인 적용: {len(results)} → {len(filtered)} (cut={cut:.2f}, median={median:.2f}, max={max_s:.2f})")
        return filtered
    
    async def _build_context(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int,
        ppt_mode: bool = False
    ) -> Tuple[str, int, List[Dict[str, Any]]]:
        """RAG 컨텍스트 구성 - 토큰 제한 내에서 최대한 많은 청크 활용
        Returns: (context_text, total_tokens, used_chunks)
        """
        if not chunks:
            return "", 0, []
        
        context_parts = []
        current_tokens = 0
        used_chunks: List[Dict[str, Any]] = []
        
        # 청크별 토큰 수 미리 계산 (한국어 텍스트 기준으로 보정)
        chunk_tokens = []
        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue
            # 한국어 텍스트: 글자 수 / 3 정도가 토큰 수에 가까움
            estimated_tokens = len(content) // 3
            metadata_tokens = 50
            chunk_tokens.append({
                "chunk": chunk,
                "content": content,
                "tokens": estimated_tokens + metadata_tokens
            })

        # PPT 모드: 헤더/목차/요약 성격의 짧은 청크들을 우선 배치해 다양성 확보
        if ppt_mode and chunk_tokens:
            def _ppt_priority(ct: Dict[str, Any]) -> float:
                ch = ct["chunk"]
                fname = (ch.get("file_name") or "").lower()
                sec = (ch.get("section_title") or "").lower()
                txt = (ct.get("content") or "").lower()
                pri = 0.0
                # 파일 유형 우선 (템플릿/샘플/PPT)
                if any(k in fname for k in [".ppt", ".pptx", "template", "샘플", "sample", "템플릿", "소개서"]):
                    pri += 1.0
                # 헤더/목차/요약
                if any(k in sec for k in ["목차", "개요", "요약", "outline", "overview", "title", "제목"]):
                    pri += 0.6
                elif any(k in txt for k in ["목차", "개요", "요약", "outline", "overview"]):
                    pri += 0.3
                # 짧을수록 더 우선
                pri += max(0.0, 0.6 - (ct["tokens"] / max_tokens))
                # 기본 유사도 점수도 약간 반영
                pri += float(ch.get("combined_score", ch.get("similarity_score", 0.0))) * 0.3
                return pri
            chunk_tokens = sorted(chunk_tokens, key=_ppt_priority, reverse=True)
        
        # 첫 번째 청크가 너무 크면 잘라서 사용
        if chunk_tokens and chunk_tokens[0]["tokens"] > max_tokens * 0.8:
            first_chunk = chunk_tokens[0]
            # 첫 번째 청크를 최대 토큰의 60%까지만 사용 (나머지 청크들을 위해 여유 확보)
            max_first_tokens = int(max_tokens * 0.6)
            content_limit = int(max_first_tokens * 3)  # 토큰 -> 글자 수 변환 (한국어 기준)
            
            truncated_content = first_chunk["content"][:content_limit] + "..."
            chunk_info = f"[문서 1: {first_chunk['chunk'].get('file_name', 'Unknown')} - 유사도: {first_chunk['chunk'].get('combined_score', first_chunk['chunk'].get('similarity_score', 0)):.2f}] (일부 내용)"
            context_part = f"{chunk_info}\n{truncated_content}\n\n"
            
            context_parts.append(context_part)
            current_tokens = max_first_tokens
            used_chunks.append(first_chunk["chunk"])  # 실제 사용된 청크 기록
            
            logger.info(f"⚠️ 첫 번째 청크가 큼 (원본 {first_chunk['tokens']}토큰) → {max_first_tokens}토큰으로 축소")
            
            # 나머지 청크들도 추가
            for i, chunk_data in enumerate(chunk_tokens[1:], 2):
                if current_tokens + chunk_data["tokens"] > max_tokens:
                    logger.info(f"⚠️ 토큰 제한 도달: {current_tokens + chunk_data['tokens']} > {max_tokens}, 청크 {i}부터 생략")
                    break
                    
                chunk_info = f"[문서 {i}: {chunk_data['chunk'].get('file_name', 'Unknown')} - 유사도: {chunk_data['chunk'].get('combined_score', chunk_data['chunk'].get('similarity_score', 0)):.2f}]"
                context_part = f"{chunk_info}\n{chunk_data['content']}\n\n"
                
                context_parts.append(context_part)
                current_tokens += chunk_data["tokens"]
                used_chunks.append(chunk_data["chunk"])  # 실제 사용된 청크 기록
        else:
            # 일반적인 경우: 모든 청크를 순서대로 추가
            for i, chunk_data in enumerate(chunk_tokens):
                required_tokens = chunk_data["tokens"]
                if current_tokens + required_tokens > max_tokens and i > 0:
                    remaining = max_tokens - current_tokens
                    if remaining <= 80:
                        logger.info(f"⚠️ 토큰 제한 도달: {current_tokens + required_tokens} > {max_tokens}, 청크 {i+1}부터 생략")
                        break

                    logger.info(
                        f"✂️ 토큰 한도 초과로 청크 {i+1} 축소: 필요 {required_tokens}토큰 → 가용 {remaining}토큰"
                    )
                    content_limit = max(remaining * 3, 0)
                    truncated_content = chunk_data["content"][:content_limit] + "..."
                    chunk_info = f"[문서 {i+1}: {chunk_data['chunk'].get('file_name', 'Unknown')} - 유사도: {chunk_data['chunk'].get('combined_score', chunk_data['chunk'].get('similarity_score', 0)):.2f}] (일부 내용)"
                    context_part = f"{chunk_info}\n{truncated_content}\n\n"

                    context_parts.append(context_part)
                    current_tokens += remaining
                    used_chunks.append(chunk_data["chunk"])  # 실제 사용된 청크 기록
                    break
                
                chunk_info = f"[문서 {i+1}: {chunk_data['chunk'].get('file_name', 'Unknown')} - 유사도: {chunk_data['chunk'].get('combined_score', chunk_data['chunk'].get('similarity_score', 0)):.2f}]"
                context_part = f"{chunk_info}\n{chunk_data['content']}\n\n"
                
                context_parts.append(context_part)
                current_tokens += required_tokens
                used_chunks.append(chunk_data["chunk"])  # 실제 사용된 청크 기록
        
        context_text = "".join(context_parts)
        
        logger.info(f"📝 컨텍스트 구성 완료: {len(context_parts)}개 청크 (전체 {len(chunks)}개 중), 약 {current_tokens}토큰")
        
        return context_text, int(current_tokens), used_chunks
    
    async def search_with_rag(
        self,
        rag_params: RAGSearchParams,
        container_ids: Optional[List[str]] = None,
        db_session: Optional[AsyncSession] = None,
        attachments: Optional[List[Dict[str, Any]]] = None  # 🆕 이미지 첨부 정보
    ) -> Dict[str, Any]:
        """
        AI Agent를 위한 통합 RAG 검색
        
        Args:
            rag_params: RAG 검색 파라미터
            container_ids: 컨테이너 ID 목록
            db_session: 데이터베이스 세션 (선택적)
            attachments: 첨부된 이미지 메타데이터 (CLIP 기반 유사도 검색용)
            
        Returns:
            검색 결과 딕셔너리
        """
        from app.core.database import get_db
        
        try:
            # 🆕 이미지 첨부가 있고 문서가 선택된 경우 CLIP 기반 이미지 유사도 검색
            if attachments and rag_params.document_ids:
                image_attachments = [
                    att for att in attachments 
                    if att.get('mime_type', '').startswith('image/')
                ]
                
                if image_attachments:
                    logger.info(f"🖼️ 이미지 첨부 감지 - CLIP 기반 이미지 유사도 검색 시작 ({len(image_attachments)}개 이미지, {len(rag_params.document_ids)}개 문서)")
                    
                    # 데이터베이스 세션 확보
                    if db_session:
                        session = db_session
                    else:
                        async for session in get_db():
                            break
                    
                    # CLIP 기반 이미지 유사도 검색 수행
                    image_search_result = await self._search_by_image_similarity(
                        session=session,
                        image_attachments=image_attachments,
                        document_ids=rag_params.document_ids,
                        limit=rag_params.limit,
                        threshold=rag_params.similarity_threshold
                    )
                    
                    if image_search_result and len(image_search_result.get('references', [])) > 0:
                        logger.info(f"✅ 이미지 유사도 검색 성공 - {len(image_search_result['references'])}개 청크 반환")
                        return image_search_result
                    else:
                        logger.warning("⚠️ 이미지 유사도 검색 결과 없음 - 텍스트 기반 검색으로 폴백")
            
            # 컨테이너 ID 설정
            if container_ids:
                rag_params.container_ids = container_ids
            
            # 데이터베이스 세션 확보
            if db_session:
                session = db_session
                search_result = await self.search_for_rag_context(session, rag_params)
            else:
                async for session in get_db():
                    search_result = await self.search_for_rag_context(session, rag_params)
                    break
            
            # 결과를 딕셔너리 형태로 반환
            # references는 실제 컨텍스트에 포함된 used_chunks로 제한
            # all_references는 토큰 구성 전 최종 후보 전체(chunks)
            return {
                "references": search_result.used_chunks,
                "all_references": search_result.chunks,
                "context_text": search_result.context_text,
                "context_info": {
                    "total_chunks": len(search_result.chunks),
                    "used_chunks": len(search_result.used_chunks),
                    "context_tokens": search_result.total_tokens,
                    "search_mode": rag_params.search_mode,
                    "reranking_applied": search_result.reranking_applied,
                    "document_filtering": bool(rag_params.document_ids),
                    "filtered_document_count": len(rag_params.document_ids) if rag_params.document_ids else 0
                },
                "rag_stats": {
                    "query_length": len(rag_params.query),
                    "total_candidates": len(search_result.chunks),
                    "final_chunks": len(search_result.used_chunks),
                    "avg_similarity": search_result.search_stats.get("avg_similarity", 0),
                    "search_time": search_result.search_stats.get("search_time", 0),
                    "search_mode": rag_params.search_mode,
                    "has_korean_keywords": search_result.search_stats.get("has_korean_keywords", False),
                    "embedding_dimension": settings.get_current_embedding_dimension(),
                    "embedding_provider": settings.get_current_embedding_provider(),
                    "llm_provider": settings.get_current_llm_provider()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ RAG 검색 중 오류: {e}")
            # 오류 시 빈 결과 반환
            return {
                "references": [],
                "all_references": [],
                "context_text": "",
                "context_info": {
                    "total_chunks": 0,
                    "used_chunks": 0,
                    "context_tokens": 0,
                    "search_mode": rag_params.search_mode,
                    "reranking_applied": False,
                    "document_filtering": bool(rag_params.document_ids),
                    "filtered_document_count": 0,
                    "error": str(e)
                },
                "rag_stats": {
                    "query_length": len(rag_params.query),
                    "total_candidates": 0,
                    "final_chunks": 0,
                    "avg_similarity": 0,
                    "search_time": 0,
                    "search_mode": rag_params.search_mode,
                    "has_korean_keywords": False,
                    "embedding_dimension": settings.get_current_embedding_dimension(),
                    "embedding_provider": settings.get_current_embedding_provider(),
                    "llm_provider": settings.get_current_llm_provider()
                }
            }

    async def recommend_related_documents(
        self,
        query: str,
        exclude_document_ids: Optional[List[str]] = None,
        limit: int = 5,
        threshold: float = 0.2,
        db_session: Optional[AsyncSession] = None
    ) -> List[Dict[str, Any]]:
        """검색 실패 시 질의와 연관된 문서를 추천 (문서 전체 스코프).

        전략:
        1) 질의 임베딩 생성
        2) 낮은 threshold 로 전체 청크에서 후보 추출 (상한 넉넉히)
        3) 문서 단위로 max(similarity), 매칭 청크 수를 기준 정렬
        4) 상위 N개 반환
        """
        from app.core.database import get_db
        try:
            # 임베딩 생성 - 설정된 서비스 사용
            from app.services.core.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
            embedding_vector = await embedding_service.get_embedding(query)
            if not embedding_vector:
                return []

            # 세션 확보
            if db_session:
                session = db_session
                close_after = False
            else:
                # 비동기 제너레이터에서 하나 꺼냄
                session_gen = get_db()
                session = None
                async for s in session_gen:
                    session = s
                    break
                close_after = True

            if session is None:
                return []

            # 🔷🟧 프로바이더별 벡터 컬럼 동적 선택
            provider = settings.get_current_embedding_provider()
            embedding_dim = len(embedding_vector)
            
            if provider == 'bedrock' or embedding_dim == 1024:
                # AWS Bedrock: Titan 1024d
                vector_column = "tdc.aws_embedding_1024"
                vector_not_null = "tdc.aws_embedding_1024 IS NOT NULL"
                logger.info(f"[RAG-DOC-SEARCH] 🟧 AWS Bedrock 벡터 검색 (aws_embedding_1024, {embedding_dim}d)")
            elif provider == 'azure_openai' or embedding_dim == 1536:
                # Azure OpenAI: text-embedding-3-small 1536d
                vector_column = "tdc.azure_embedding_1536"
                vector_not_null = "tdc.azure_embedding_1536 IS NOT NULL"
                logger.info(f"[RAG-DOC-SEARCH] 🔷 Azure OpenAI 벡터 검색 (azure_embedding_1536, {embedding_dim}d)")
            else:
                # 레거시 폴백
                vector_column = "tdc.chunk_embedding"
                vector_not_null = "tdc.chunk_embedding IS NOT NULL"
                logger.warning(f"[RAG-DOC-SEARCH] ⚠️ 레거시 벡터 컬럼 폴백 ({embedding_dim}d)")

            # 후보 청크에서 문서 단위 집계
            base_sql = f"""
                SELECT 
                    fbi.file_bss_info_sno AS file_id,
                    fbi.file_lgc_nm AS file_name,
                    MAX(1 - ({vector_column} <=> :embedding_vector)) AS max_similarity,
                    COUNT(*) AS matched_chunks
                FROM vs_doc_contents_chunks tdc
                JOIN tb_file_bss_info fbi ON tdc.file_bss_info_sno = fbi.file_bss_info_sno
                WHERE {vector_not_null}
                  AND fbi.del_yn = 'N'
                  AND 1 - ({vector_column} <=> :embedding_vector) > :threshold
            """
            conditions = []
            params: Dict[str, Any] = {
                "embedding_vector": f"[{','.join(map(str, embedding_vector))}]",
                "threshold": threshold,
                "candidate_limit": max(limit * 5, 25)  # 충분한 후보 확보
            }
            if exclude_document_ids:
                try:
                    exclude_int = [int(x) for x in exclude_document_ids]
                except ValueError:
                    exclude_int = []
                if exclude_int:
                    conditions.append("AND NOT (fbi.file_bss_info_sno = ANY(:exclude_ids))")
                    params["exclude_ids"] = exclude_int

            if conditions:
                base_sql += " " + " ".join(conditions)

            # 그룹 & 정렬
            base_sql += """
                GROUP BY fbi.file_bss_info_sno, fbi.file_lgc_nm
                ORDER BY max_similarity DESC, matched_chunks DESC
                LIMIT :candidate_limit
            """
            from sqlalchemy import text
            result = await session.execute(text(base_sql), params)
            rows = result.fetchall()

            recommendations = []
            for row in rows[:limit]:
                import math
                max_sim = float(row.max_similarity)
                matched_count = int(row.matched_chunks)
                
                # NaN 값 필터링
                if math.isnan(max_sim) or math.isinf(max_sim):
                    logger.debug(f"연관 문서 추천에서 NaN 점수 스킵: {row.file_name}")
                    continue
                    
                recommendations.append({
                    "file_id": row.file_id,
                    "file_name": row.file_name,
                    "max_similarity": max_sim,
                    "matched_chunks": matched_count
                })

            logger.info(f"🔗 연관 문서 추천: {len(recommendations)}개 (limit={limit})")
            return recommendations
        except Exception as e:
            logger.warning(f"연관 문서 추천 실패: {e}")
            return []
    
    def _apply_rag_quality_filter(
        self, 
        results: List[Dict[str, Any]], 
        search_params: RAGSearchParams,
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        RAG 검색 결과 품질 필터링
        키워드 매치가 없고 낮은 벡터 점수만 있는 경우 관련성 검증
        
        개선 사항 (2025-10-16):
        - 키워드가 없을 때는 유사도만으로 필터링
        - 과도한 필터링 방지
        """
        try:
            query_keywords = query_analysis.get("korean_keywords", [])
            query_text = search_params.query.lower()
            
            # 쿼리 자체가 비어있으면 필터링 없이 반환
            if not query_keywords and not query_text:
                return results
            
            # 키워드가 없으면 유사도만으로 필터링
            if not query_keywords:
                logger.info("🔍 키워드 없음 - 유사도 기반 필터링만 적용")
                filtered_results = []
                for result in results:
                    similarity = result.get("similarity_score", 0.0)
                    # 낮은 유사도만 제외 (0.3 이하)
                    if similarity >= 0.3:
                        filtered_results.append(result)
                    else:
                        logger.info(f"RAG 품질 필터링으로 제외: {result.get('file_name', 'unknown')} "
                                  f"(낮은 유사도: {similarity:.3f})")
                logger.info(f"RAG 품질 필터링 (유사도 기반): {len(results)}개 -> {len(filtered_results)}개")
                return filtered_results
            
            filtered_results = []
            
            for result in results:
                search_type = result.get("search_type", "")
                
                # 키워드 검색 결과는 항상 통과
                if search_type == "keyword":
                    filtered_results.append(result)
                    continue
                
                # 벡터 검색 결과는 추가 검증
                if search_type == "semantic":
                    similarity = result.get("similarity_score", 0.0)
                    
                    # 매우 높은 유사도 점수 (0.6 이상)면 통과
                    if similarity >= 0.6:
                        filtered_results.append(result)
                        continue
                    
                    # 제목이나 내용에서 쿼리 키워드 부분 일치 확인
                    content = result.get("content", "").lower()
                    title = result.get("file_name", "").lower()
                    
                    # 쿼리 키워드와 부분적으로라도 일치하는지 확인
                    has_partial_match = False
                    for keyword in query_keywords:
                        keyword_lower = keyword.lower()
                        if len(keyword_lower) >= 2:  # 2글자 이상만 검사
                            if keyword_lower in content or keyword_lower in title:
                                has_partial_match = True
                                break
                    
                    # 쿼리 텍스트 전체와도 확인 (2글자 이상)
                    if not has_partial_match and len(query_text) >= 2:
                        if query_text in content or query_text in title:
                            has_partial_match = True
                    
                    if has_partial_match:
                        filtered_results.append(result)
                    else:
                        logger.info(f"RAG 품질 필터링으로 제외: {result.get('file_name', 'unknown')} "
                                  f"(키워드 불일치, 유사도: {similarity:.3f})")
                else:
                    # 알 수 없는 검색 타입은 통과
                    filtered_results.append(result)
            
            logger.info(f"RAG 품질 필터링: {len(results)}개 -> {len(filtered_results)}개")
            return filtered_results
            
        except Exception as e:
            logger.error(f"RAG 품질 필터링 오류: {e}")
            return results

    async def _search_by_image_similarity(
        self,
        session: AsyncSession,
        image_attachments: List[Dict[str, Any]],
        document_ids: List[str],
        limit: int = 10,
        threshold: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        """
        CLIP 기반 이미지 유사도 검색
        
        Args:
            session: 데이터베이스 세션
            image_attachments: 이미지 첨부 메타데이터 리스트
            document_ids: 검색 대상 문서 ID 리스트
            limit: 최대 반환 청크 수
            threshold: 유사도 임계값
            
        Returns:
            검색 결과 딕셔너리 (references, context_text, context_info, rag_stats)
        """
        from app.models.document_chunk import DocumentChunk
        from app.services.clip_embedding_service import clip_embedding_service
        from sqlalchemy import select, and_, or_, text
        import numpy as np
        import time
        
        try:
            start_time = time.time()
            
            # 첫 번째 이미지의 blob_url 가져오기
            first_image = image_attachments[0]
            image_blob_url = first_image.get('blob_url')
            
            if not image_blob_url:
                logger.warning("⚠️ 이미지 blob_url이 없음")
                return None
            
            logger.info(f"🖼️ 이미지 임베딩 생성 중: {image_blob_url}")
            
            # CLIP을 통해 이미지 임베딩 생성
            query_embedding = await clip_embedding_service.create_image_embedding(image_blob_url)
            
            if query_embedding is None:
                logger.error("❌ 이미지 임베딩 생성 실패")
                return None
            
            logger.info(f"✅ 이미지 임베딩 생성 완료 (dimension: {len(query_embedding)})")
            
            # pgvector를 사용한 이미지 청크 유사도 검색
            # document_id가 document_ids에 포함되고, image_embedding이 있는 청크만 검색
            query_text = text("""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.content,
                    dc.image_path,
                    dc.image_url,
                    d.file_name,
                    d.file_type,
                    d.container_id,
                    1 - (dc.image_embedding <=> :query_embedding) as similarity_score
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE 
                    dc.document_id = ANY(:document_ids)
                    AND dc.image_embedding IS NOT NULL
                    AND (1 - (dc.image_embedding <=> :query_embedding)) >= :threshold
                ORDER BY similarity_score DESC
                LIMIT :limit
            """)
            
            result = await session.execute(
                query_text,
                {
                    "query_embedding": str(query_embedding),
                    "document_ids": document_ids,
                    "threshold": threshold,
                    "limit": limit
                }
            )
            
            rows = result.fetchall()
            search_time = time.time() - start_time
            
            logger.info(f"🔍 이미지 유사도 검색 완료: {len(rows)}개 청크 발견 (소요시간: {search_time:.3f}초)")
            
            if not rows:
                return None
            
            # 결과를 딕셔너리 형태로 변환
            chunks = []
            for row in rows:
                chunk = {
                    "id": str(row[0]),
                    "document_id": str(row[1]),
                    "chunk_index": row[2],
                    "content": row[3] or "",
                    "image_path": row[4],
                    "image_url": row[5],
                    "file_name": row[6],
                    "file_type": row[7],
                    "container_id": str(row[8]) if row[8] else None,
                    "similarity_score": float(row[9]),
                    "search_type": "image_similarity"
                }
                chunks.append(chunk)
            
            # 컨텍스트 텍스트 생성
            context_parts = []
            for idx, chunk in enumerate(chunks, 1):
                context_parts.append(
                    f"[문서 {idx}: {chunk['file_name']} - 페이지 {chunk['chunk_index'] + 1}] "
                    f"(이미지 유사도: {chunk['similarity_score']:.3f})\n"
                    f"{chunk['content']}\n"
                )
            
            context_text = "\n".join(context_parts)
            
            # 결과 반환
            return {
                "references": chunks,
                "all_references": chunks,
                "context_text": context_text,
                "context_info": {
                    "total_chunks": len(chunks),
                    "used_chunks": len(chunks),
                    "context_tokens": len(context_text.split()),
                    "search_mode": "image_similarity",
                    "reranking_applied": False,
                    "document_filtering": True,
                    "filtered_document_count": len(document_ids),
                    "image_search": True
                },
                "rag_stats": {
                    "query_length": 0,
                    "total_candidates": len(chunks),
                    "final_chunks": len(chunks),
                    "avg_similarity": sum(c['similarity_score'] for c in chunks) / len(chunks),
                    "search_time": search_time,
                    "search_mode": "image_similarity",
                    "has_korean_keywords": False,
                    "embedding_dimension": len(query_embedding),
                    "embedding_provider": "clip",
                    "llm_provider": settings.get_current_llm_provider()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 이미지 유사도 검색 중 오류: {e}", exc_info=True)
            return None

# 전역 인스턴스
rag_search_service = RAGSearchService()

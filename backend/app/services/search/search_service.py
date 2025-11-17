"""
통합 검색 서비스
벡터 검색 + 키워드 검색 + 한국어 전문검색을 통합한 고성능 검색 엔진
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
import asyncio
import json
import math
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, text, desc, select
import numpy as np
from datetime import datetime

from app.core.database import get_async_session_local
from app.models import TbKnowledgeContainers, TbUserPermissions
from app.services.core.korean_nlp_service import korean_nlp_service
from app.services.core.embedding_service import EmbeddingService

try:
    # CLIP 기반 이미지/텍스트 임베딩 서비스 (멀티모달 검색용)
    from app.services.document.vision.image_embedding_service import image_embedding_service
except ImportError:  # pragma: no cover - 선택 구성 요소가 없을 때를 대비한 방어 코드
    image_embedding_service = None
from app.services.auth.permission_service import permission_service
from .natural_language_query_processor import natural_language_processor
from .query_pipeline import process_user_query  # 통합 파이프라인
from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    """통합 검색 서비스 - 하이브리드 검색 엔진"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_weight = 0.4  # 벡터 검색 가중치 (한국어 임베딩 한계 고려)
        self.keyword_weight = 0.5  # 키워드 검색 가중치 (한국어에서 더 정확함)
        self.fulltext_weight = 0.1  # 전문검색 가중치
        # 환경설정 기반 임계값 사용 (.env → settings.similarity_threshold)
        self.similarity_threshold = settings.similarity_threshold  # 기본값은 config.py의 기본값 사용
        self.async_session_local = get_async_session_local()
        self._container_details_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._all_container_name_cache: Tuple[float, Dict[str, str]] = (0.0, {})
        self._container_cache_ttl = getattr(settings, "container_cache_ttl_seconds", 300)
        
    async def hybrid_search(
        self,
        query: str,
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_results: int = 10,
        search_type: str = "hybrid",  # hybrid, vector_only, keyword_only
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        하이브리드 검색 수행
        
        Args:
            query: 검색 쿼리
            user_emp_no: 검색하는 사용자 사번
            container_ids: 검색 대상 컨테이너 목록 (None이면 권한 내 모든 컨테이너)
            max_results: 최대 결과 수
            search_type: 검색 타입
            filters: 추가 필터
            
        Returns:
            검색 결과
        """
        try:
            # 1. 사용자 권한 확인 및 검색 가능한 컨테이너 확인
            accessible_containers = await self._get_accessible_containers(
                user_emp_no, container_ids
            )
            
            if not accessible_containers:
                return {
                    "results": [],
                    "total_count": 0,
                    "search_type": search_type,
                    "message": "검색 권한이 있는 컨테이너가 없습니다."
                }
            
            # 2. 쿼리 전처리
            processed_query = await self._preprocess_query(query)
            
            # 3. 검색 타입에 따른 검색 수행
            if search_type == "vector_only":
                results = await self._vector_search(
                    processed_query, accessible_containers, max_results, filters
                )
            elif search_type == "keyword_only":
                results = await self._keyword_search(
                    processed_query, accessible_containers, max_results, filters
                )
            else:  # hybrid
                results = await self._hybrid_search_combined(
                    processed_query, accessible_containers, max_results, filters
                )
            
            # 4. 검색 기록 저장
            await self._save_search_history(
                user_emp_no, query, results, search_type, accessible_containers
            )
            
            # 5. 파일 단위로 그룹화 (검색 화면용)
            grouped_results = await self._group_results_by_file(results)
            
            # 6. 결과 후처리
            formatted_results = await self._format_search_results(grouped_results, user_emp_no, query)
            
            # 7. 컨테이너 이름 매핑
            accessible_container_names = await self._get_container_friendly_names(accessible_containers)
            
            return {
                "results": formatted_results,
                "total_count": len(formatted_results),
                "search_type": search_type,
                "accessible_containers": accessible_containers,
                "accessible_container_names": accessible_container_names,
                "query_processed": processed_query,
                "execution_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {str(e)}")
            raise
    
    async def _hybrid_search_combined(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        벡터 검색 + 키워드 검색 + 전문검색을 결합한 하이브리드 검색
        """
        # 병렬로 각 검색 방식 실행
        vector_results, keyword_results, fulltext_results = await asyncio.gather(
            self._vector_search(processed_query, container_ids, max_results * 2, filters),
            self._keyword_search(processed_query, container_ids, max_results * 2, filters),
            self._fulltext_search(processed_query, container_ids, max_results * 2, filters),
            return_exceptions=True
        )
        
        # 각 결과에 검색 방식별 가중치 적용
        all_results = {}
        
        # 벡터 검색 결과 처리
        if not isinstance(vector_results, Exception):
            logger.info(f"벡터 검색 결과 개수: {len(vector_results)}")
            for result in vector_results:
                doc_id = result.get("search_doc_id", result.get("document_id"))  # 두 가지 형태 모두 지원
                container_id = result.get("knowledge_container_id", "")
                logger.debug(f"벡터 검색 결과 - doc_id: {doc_id}, container_id: {container_id}")
                score = result.get("similarity_score", 0.0) * self.vector_weight
                if doc_id not in all_results:
                    all_results[doc_id] = result.copy()
                    all_results[doc_id]["combined_score"] = score
                    all_results[doc_id]["search_methods"] = ["vector"]
                else:
                    all_results[doc_id]["combined_score"] += score
                    all_results[doc_id]["search_methods"].append("vector")
        
        # 키워드 검색 결과 처리
        if not isinstance(keyword_results, Exception):
            logger.info(f"키워드 검색 결과 개수: {len(keyword_results)}")
            for result in keyword_results:
                doc_id = result["search_doc_id"]
                container_id = result.get("knowledge_container_id", "")
                logger.debug(f"키워드 검색 결과 - doc_id: {doc_id}, container_id: {container_id}")
                score = result.get("keyword_score", 0.0) * self.keyword_weight
                if doc_id not in all_results:
                    all_results[doc_id] = result.copy()
                    all_results[doc_id]["combined_score"] = score
                    all_results[doc_id]["search_methods"] = ["keyword"]
                else:
                    all_results[doc_id]["combined_score"] += score
                    all_results[doc_id]["search_methods"].append("keyword")
        
        # 전문검색 결과 처리
        if not isinstance(fulltext_results, Exception):
            logger.info(f"전문검색 결과 개수: {len(fulltext_results)}")
            for result in fulltext_results:
                doc_id = result["search_doc_id"]
                container_id = result.get("knowledge_container_id", "")
                logger.debug(f"전문검색 결과 - doc_id: {doc_id}, container_id: {container_id}")
                score = result.get("fulltext_score", 0.0) * self.fulltext_weight
                if doc_id not in all_results:
                    all_results[doc_id] = result.copy()
                    all_results[doc_id]["combined_score"] = score
                    all_results[doc_id]["search_methods"] = ["fulltext"]
                else:
                    all_results[doc_id]["combined_score"] += score
                    all_results[doc_id]["search_methods"].append("fulltext")
        
        # NaN 값 정리 및 결합된 점수로 정렬
        for result in all_results.values():
            # NaN 값을 0.0으로 교체
            if "combined_score" in result:
                import math
                if math.isnan(result["combined_score"]):
                    result["combined_score"] = 0.0
            
            # 개별 점수들도 NaN 체크
            for score_key in ["similarity_score", "keyword_score", "fulltext_score"]:
                if score_key in result:
                    if math.isnan(result[score_key]):
                        result[score_key] = 0.0
        
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x.get("combined_score", 0.0),
            reverse=True
        )
        
        # 검색 품질 필터링 적용
        sorted_results = self._apply_quality_filter(sorted_results, processed_query)
        
        # 최종 점수를 0-1 범위로 정규화
        if sorted_results:
            max_score = max(r.get("combined_score", 0.0) for r in sorted_results)
            min_score = min(r.get("combined_score", 0.0) for r in sorted_results)
            
            # 정규화 (0-1 범위)
            if max_score > min_score:
                for result in sorted_results:
                    original_score = result.get("combined_score", 0.0)
                    normalized_score = (original_score - min_score) / (max_score - min_score)
                    result["similarity_score"] = normalized_score
                    result["combined_score"] = normalized_score
                    logger.debug(f"점수 정규화: {original_score:.3f} -> {normalized_score:.3f}")
            else:
                # 모든 점수가 같은 경우
                for result in sorted_results:
                    result["similarity_score"] = 1.0
                    result["combined_score"] = 1.0
        
        return sorted_results[:max_results]
    
    async def _vector_search(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """벡터 유사도 검색 - 실제 테이블 구조 사용"""
        try:
            # 🚀 임베딩 입력은 자연어 문장 사용 (파이프 등 연산자 문자열 금지)
            original_text = processed_query.get("original_text", "")
            normalized_text = processed_query.get("normalized_text") or original_text
            # 검색 시스템 내부의 fulltext용 OR 문자열은 임베딩에 사용하지 않음
            optimized_text_for_fulltext = processed_query.get("search_query_string")
            if optimized_text_for_fulltext and optimized_text_for_fulltext != original_text:
                logger.info(
                    f"최적화된 검색어(전문/키워드용): '{original_text}' → '{optimized_text_for_fulltext}'"
                )
            query_text = normalized_text or original_text
            logger.info(f"임베딩 입력 문장: '{query_text}'")

            # 언어/길이 기반 동적 임계값 (한국어 단문 보호)
            language = processed_query.get("language", "mixed")
            dyn_threshold = self.similarity_threshold
            if language == "ko":
                try:
                    text_len = len(query_text)
                except Exception:
                    text_len = 0
                if text_len > 0 and text_len < 6:
                    # 짧은 한글 질의는 임계값 완화 (최소 0.3 보장)
                    dyn_threshold = max(0.3, self.similarity_threshold - 0.1)
            logger.info(
                f"벡터 검색 시작: '{query_text}', 임계값: {dyn_threshold} (기본: {self.similarity_threshold})"
            )
            
            query_embedding = await self.embedding_service.get_embedding(query_text)
            
            async with self.async_session_local() as db:
                # vs_doc_contents_chunks 테이블을 사용한 벡터 검색 (청킹된 임베딩)
                container_id_list = "', '".join(container_ids)
                
                # 임베딩을 문자열로 변환
                embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
                
                # 🔷🟧 벤더별 벡터 컬럼 선택 (차원 기반 자동 판별)
                embedding_dim = len(query_embedding)
                vector_column = None
                provider_filter = ""
                
                if embedding_dim == 1536:
                    vector_column = "c.azure_embedding_1536"
                    provider_filter = "AND c.embedding_provider = 'azure'"
                    logger.info(f"[VECTOR-SEARCH] 🔷 Azure 벡터 컬럼 사용 (1536d)")
                elif embedding_dim == 1024:
                    vector_column = "c.aws_embedding_1024"
                    provider_filter = "AND c.embedding_provider = 'aws'"
                    logger.info(f"[VECTOR-SEARCH] 🟧 AWS 벡터 컬럼 사용 (1024d)")
                else:
                    # 레거시 폴백 (동적 차원 컬럼)
                    vector_column = "c.chunk_embedding"
                    logger.warning(f"[VECTOR-SEARCH] ⚠️ 레거시 벡터 컬럼 폴백 ({embedding_dim}d)")
                
                query_sql = f"""
                    SELECT 
                        c.chunk_sno as id,
                        c.file_bss_info_sno,
                        c.chunk_text,
                        c.chunk_index,
                        c.chunk_size,
                        c.keywords as keywords_json,
                        c.knowledge_container_id,
                        c.metadata_json as metadata_json,
                        f.file_lgc_nm,
                        f.file_psl_nm,
                        f.path,
                        f.korean_metadata,
                        1 - ({vector_column} <=> '{embedding_str}'::vector) as similarity_score
                    FROM vs_doc_contents_chunks c
                    JOIN tb_file_bss_info f ON c.file_bss_info_sno = f.file_bss_info_sno
                    WHERE c.knowledge_container_id IS NOT NULL 
                        AND c.knowledge_container_id != '' 
                        AND c.knowledge_container_id NOT IN ('NONE', 'None', 'null', 'NULL')
                        AND (c.knowledge_container_id = 'DEFAULT_CONTAINER' OR c.knowledge_container_id IN ('{container_id_list}'))
                        AND f.del_yn = 'N'
                        AND {vector_column} IS NOT NULL
                        {provider_filter}
                        AND 1 - ({vector_column} <=> '{embedding_str}'::vector) >= {dyn_threshold}
                    ORDER BY similarity_score DESC
                    LIMIT {max_results * 2}
                """
                
                result = await db.execute(text(query_sql))
                
                results = []
                for row in result.fetchall():
                    similarity_score = float(row.similarity_score)
                    
                    # NaN 값 필터링
                    if math.isnan(similarity_score) or math.isinf(similarity_score):
                        logger.warning(f"벡터 검색에서 잘못된 점수 발견 (NaN/Inf): doc_id={getattr(row, 'id', 'unknown')}")
                        continue
                    
                    # 임계값 필터링 (동적 임계값 기준)
                    if similarity_score < dyn_threshold:
                        logger.debug(f"임계값 미달로 제외: {similarity_score:.3f} < {dyn_threshold}")
                        continue
                    
                    metadata = {}
                    modality = "text"  # 기본값
                    chunk_id = row.id
                    source_object_ids = []
                    page_number = None
                    
                    if row.metadata_json:
                        try:
                            metadata = json.loads(row.metadata_json)
                            # metadata_json에서 modality 추출
                            modality = metadata.get("modality", "text")
                            # doc_chunk 테이블의 실제 chunk_id 사용
                            chunk_id = metadata.get("chunk_id", row.id)
                            # source_object_ids 추출 (이미지 객체 ID)
                            source_object_ids = metadata.get("source_object_ids", [])
                            # page_number 추출 (이미지 페이지 번호)
                            page_number = metadata.get("page_number")
                        except:
                            metadata = {}
                    
                    korean_metadata = row.korean_metadata or {}
                    
                    results.append({
                        "search_doc_id": row.id,  # document_id 대신 search_doc_id 사용
                        "document_id": row.id,    # 호환성을 위해 둘 다 포함
                        "chunk_id": chunk_id,     # doc_chunk 테이블의 실제 chunk_id
                        "file_bss_info_sno": row.file_bss_info_sno,
                        "knowledge_container_id": row.knowledge_container_id,
                        "chunk_index": row.chunk_index,
                        "source_object_ids": source_object_ids,  # 이미지 객체 ID 배열
                        "page_number": page_number,  # 페이지 번호 (이미지용)
                        "content": row.chunk_text,
                        "chunk_size": row.chunk_size,
                        "file_name": row.file_lgc_nm,
                        "file_path": row.path,
                        # 혼동 방지를 위해 raw 유사도를 별도 보관
                        "similarity_score": similarity_score,  # 하이브리드 결합 전 raw vector sim
                        "search_method": "vector",
                        "modality": modality,     # modality 추가
                        "metadata": {**metadata, **korean_metadata},
                        # 분석/필터 일관성 유지를 위해 scores/raw_vector_similarity 추가
                        "scores": {"raw_vector_similarity": similarity_score},
                        "raw_vector_similarity": similarity_score
                    })
                
                logger.info(f"벡터 검색 완료: {len(results)}개 결과 발견 (임계값: {dyn_threshold})")
                
                if results:
                    max_score = max(r.get("raw_vector_similarity", r["similarity_score"]) for r in results)
                    min_score = min(r.get("raw_vector_similarity", r["similarity_score"]) for r in results)
                    avg_score = sum(r.get("raw_vector_similarity", r["similarity_score"]) for r in results) / max(len(results), 1)
                    logger.info(f"점수 범위(원시): {min_score:.3f} ~ {max_score:.3f}, 평균: {avg_score:.3f}")
                
                return results
                
        except Exception as e:
            logger.error(f"벡터 검색 실패: {str(e)}")
            return []
    
    async def _keyword_search(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        키워드 검색 (Multilingual textsearch 기반)
        
        변경 사항 (2025-10-24):
        - 한국어 + 영어 dual tsvector 검색 지원
        - language 감지하여 적절한 tsvector 컬럼 선택
        - ts_rank()로 정확한 순위 계산
        
        변경 사항 (2025-10-16):
        - kiwipiepy 제거
        - textsearch_ko를 키워드 검색에도 활용
        - ts_rank()로 정확한 순위 계산
        """
        try:
            query_text = processed_query["original_text"]
            language = processed_query.get("language", "mixed")  # 언어 정보 가져오기
            
            # textsearch 쿼리 생성
            # 예: "인슐린 펌프" → "인슐린 & 펌프"
            # 예: "Figure 1" → "Figure & 1"
            ts_query = query_text.replace(' ', ' & ')
            
            container_id_list = "', '".join(container_ids)
            
            logger.info(f"[KEYWORD-SEARCH] 쿼리: '{query_text}', 언어: {language}, 컨테이너: {len(container_ids)}개")
            
            async with self.async_session_local() as db:
                # 🌍 Multilingual textsearch 기반 키워드 검색
                # 한국어(korean) + 영어(english) dual configuration 지원
                
                # 언어별 검색 조건 구성
                if language == "en":
                    # 영어 전용 검색
                    tsvector_condition = """
                        s.content_tsvector_en @@ to_tsquery('english', :ts_query)
                        OR s.keyword_tsvector_en @@ to_tsquery('english', :ts_query)
                    """
                    rank_calculation = """
                        COALESCE(
                            ts_rank(
                                s.content_tsvector_en, 
                                to_tsquery('english', :ts_query)
                            ) * 2.0,
                            0.0
                        ) +
                        COALESCE(
                            ts_rank(
                                s.keyword_tsvector_en, 
                                to_tsquery('english', :ts_query)
                            ) * 3.0,
                            0.0
                        )
                    """
                elif language == "ko":
                    # 한국어 전용 검색
                    tsvector_condition = """
                        s.content_tsvector @@ to_tsquery('korean', :ts_query)
                        OR s.keyword_tsvector @@ to_tsquery('korean', :ts_query)
                    """
                    rank_calculation = """
                        COALESCE(
                            ts_rank(
                                s.content_tsvector, 
                                to_tsquery('korean', :ts_query)
                            ) * 2.0,
                            0.0
                        ) +
                        COALESCE(
                            ts_rank(
                                s.keyword_tsvector, 
                                to_tsquery('korean', :ts_query)
                            ) * 3.0,
                            0.0
                        )
                    """
                else:  # mixed 또는 language 정보 없음
                    # 한국어 + 영어 동시 검색 (OR 조건)
                    tsvector_condition = """
                        s.content_tsvector @@ to_tsquery('korean', :ts_query)
                        OR s.keyword_tsvector @@ to_tsquery('korean', :ts_query)
                        OR s.content_tsvector_en @@ to_tsquery('english', :ts_query)
                        OR s.keyword_tsvector_en @@ to_tsquery('english', :ts_query)
                    """
                    rank_calculation = """
                        GREATEST(
                            COALESCE(
                                ts_rank(s.content_tsvector, to_tsquery('korean', :ts_query)) * 2.0,
                                0.0
                            ) +
                            COALESCE(
                                ts_rank(s.keyword_tsvector, to_tsquery('korean', :ts_query)) * 3.0,
                                0.0
                            ),
                            COALESCE(
                                ts_rank(s.content_tsvector_en, to_tsquery('english', :ts_query)) * 2.0,
                                0.0
                            ) +
                            COALESCE(
                                ts_rank(s.keyword_tsvector_en, to_tsquery('english', :ts_query)) * 3.0,
                                0.0
                            )
                        )
                    """
                
                query_sql = f"""
                    SELECT 
                        s.search_doc_id,
                        s.file_bss_info_sno,
                        s.knowledge_container_id,
                        0 as chunk_index,
                        s.full_content as content,
                        s.content_summary as main_text,
                        s.document_title,
                        s.has_images,
                        s.image_count,
                        f.file_lgc_nm,
                        f.path,
                        -- ✅ 언어별 ts_rank() 계산
                        {rank_calculation} as keyword_score
                    FROM tb_document_search_index s
                    JOIN tb_file_bss_info f ON s.file_bss_info_sno = f.file_bss_info_sno
                    WHERE s.knowledge_container_id IS NOT NULL 
                        AND s.knowledge_container_id != '' 
                        AND s.knowledge_container_id NOT IN ('NONE', 'None', 'null', 'NULL')
                        AND (s.knowledge_container_id = 'DEFAULT_CONTAINER' OR s.knowledge_container_id IN ('{container_id_list}'))
                        AND f.del_yn = 'N'
                        AND s.indexing_status = 'indexed'
                        AND (
                            -- ✅ Multilingual textsearch 매칭 (메인)
                            {tsvector_condition}
                            OR 
                            -- ✅ 보조: 직접 문자열 매칭 (단순 키워드)
                            s.full_content ILIKE :like_pattern
                            OR s.document_title ILIKE :like_pattern
                        )
                    ORDER BY keyword_score DESC
                    LIMIT :max_results
                """
                
                like_pattern = f"%{query_text}%"
                
                result = await db.execute(
                    text(query_sql),
                    {
                        "ts_query": ts_query,
                        "like_pattern": like_pattern,
                        "max_results": max_results * 2
                    }
                )
                
                results = []
                for row in result.fetchall():
                    keyword_score = float(row.keyword_score) if row.keyword_score else 0.0
                    
                    # NaN 필터링
                    if math.isnan(keyword_score) or math.isinf(keyword_score):
                        keyword_score = 0.0
                    
                    results.append({
                        "search_doc_id": row.search_doc_id,
                        "file_bss_info_sno": row.file_bss_info_sno,
                        "knowledge_container_id": row.knowledge_container_id,
                        "chunk_index": row.chunk_index,
                        "content": row.content[:500] if row.content else "",  # 미리보기
                        "main_text": row.main_text,
                        "document_title": row.document_title,
                        "has_images": row.has_images,
                        "image_count": row.image_count,
                        "keyword_score": keyword_score,
                        "file_name": row.file_lgc_nm,
                        "file_path": row.path,
                        "search_method": "keyword_textsearch",
                        "modality": "text"  # 문서 레벨 검색
                    })
                
                logger.info(f"[KEYWORD-SEARCH] 문서 레벨 결과: {len(results)}개")
                
                # 🖼️ IMAGE chunk 검색 추가 (캡션 텍스트 매칭)
                image_chunk_results = await self._search_image_chunks_by_caption(
                    query_text, container_ids, db, language
                )
                
                if image_chunk_results:
                    logger.info(f"[KEYWORD-SEARCH] IMAGE chunk 결과: {len(image_chunk_results)}개")
                    results.extend(image_chunk_results)
                
                logger.info(f"[KEYWORD-SEARCH] 전체 결과: {len(results)}개 (문서 + IMAGE chunk)")
                return results[:max_results]
                
        except Exception as e:
            logger.error(f"키워드 검색 실패: {e}")
            return []
    
    async def _search_image_chunks_by_caption(
        self,
        query_text: str,
        container_ids: List[str],
        db: AsyncSession,
        language: str = "mixed"
    ) -> List[Dict[str, Any]]:
        """
        IMAGE chunk의 캡션 텍스트로 검색
        
        Args:
            query_text: 검색 쿼리 텍스트
            container_ids: 검색 대상 컨테이너 ID 목록
            db: 데이터베이스 세션
            language: 검색 언어 (en/ko/mixed)
        
        Returns:
            IMAGE chunk 검색 결과 리스트
        """
        try:
            from app.models.document.multimodal_models import DocChunk, DocChunkSession
            
            container_id_list = "', '".join(container_ids)
            
            # ILIKE 패턴 (대소문자 무시 검색)
            like_pattern = f"%{query_text}%"
            
            logger.info(f"[IMAGE-CHUNK-SEARCH] 캡션 검색: '{query_text}', 언어: {language}")
            
            # doc_chunk 테이블에서 modality='image'인 청크 검색
            # content_text에 캡션이 저장되어 있음
            query_sql = f"""
                SELECT 
                    c.chunk_id,
                    c.file_bss_info_sno,
                    c.chunk_index,
                    c.source_object_ids,
                    c.page_range,
                    c.blob_key,
                    c.content_text as caption,
                    c.modality,
                    c.section_heading,
                    f.knowledge_container_id,
                    f.file_lgc_nm,
                    f.path,
                    -- 캡션 텍스트 매칭 점수 (단순 ILIKE이므로 고정 점수)
                    0.8 as keyword_score
                FROM doc_chunk c
                JOIN doc_chunk_session s ON c.chunk_session_id = s.chunk_session_id
                JOIN tb_file_bss_info f ON c.file_bss_info_sno = f.file_bss_info_sno
                WHERE c.modality = 'image'
                    AND f.knowledge_container_id IS NOT NULL
                    AND f.knowledge_container_id != ''
                    AND f.knowledge_container_id NOT IN ('NONE', 'None', 'null', 'NULL')
                    AND (f.knowledge_container_id = 'DEFAULT_CONTAINER' OR f.knowledge_container_id IN ('{container_id_list}'))
                    AND f.del_yn = 'N'
                    AND c.content_text ILIKE :like_pattern
                ORDER BY c.chunk_index
                LIMIT 50
            """
            
            result = await db.execute(
                text(query_sql),
                {"like_pattern": like_pattern}
            )
            
            image_results = []
            for row in result.fetchall():
                # page_range에서 페이지 번호 추출
                page_number = None
                if row.page_range:
                    # PostgreSQL int4range는 문자열로 반환됨: "[5,6)"
                    try:
                        page_str = str(row.page_range).strip('[]()').split(',')[0]
                        page_number = int(page_str)
                    except (ValueError, IndexError):
                        page_number = None
                
                # blob_key 가져오기 (신규 데이터에만 존재)
                blob_key = getattr(row, 'blob_key', None)
                
                image_results.append({
                    "search_doc_id": row.chunk_id,  # IMAGE chunk의 ID
                    "chunk_id": row.chunk_id,
                    "file_bss_info_sno": row.file_bss_info_sno,
                    "knowledge_container_id": row.knowledge_container_id,
                    "chunk_index": row.chunk_index,
                    "source_object_ids": list(row.source_object_ids) if row.source_object_ids else [],  # 이미지 객체 ID 배열
                    "page_number": page_number,  # 페이지 번호
                    "blob_key": blob_key,  # Blob Storage 경로 (신규)
                    "content": row.caption or "",  # 캡션 텍스트
                    "main_text": row.caption or "",
                    "document_title": row.section_heading or "Image",
                    "has_images": True,
                    "image_count": 1,
                    "keyword_score": 0.8,  # IMAGE chunk 발견 시 높은 점수
                    "file_name": row.file_lgc_nm,
                    "file_path": row.path,
                    "search_method": "image_caption",
                    "modality": "image"  # IMAGE chunk임을 명시
                })
            
            logger.info(f"[IMAGE-CHUNK-SEARCH] {len(image_results)}개 IMAGE chunk 발견")
            return image_results
            
        except Exception as e:
            logger.error(f"IMAGE chunk 검색 실패: {e}", exc_info=True)
            return []
    
    async def _fulltext_search(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        PostgreSQL 전문검색 - Multilingual 통합 파이프라인 결과 사용
        
        변경 사항 (2025-10-24):
        - 한국어(korean) + 영어(english) dual tsvector 검색 추가
        """
        try:
            # 통합 파이프라인에서 이미 처리된 결과 사용
            fulltext_query = processed_query.get("fulltext_query", "")
            filtered_keywords = processed_query.get("filtered_keywords", [])
            language = processed_query.get("language", "mixed")
            
            if not fulltext_query and not filtered_keywords:
                return []
            
            # 검색어 준비
            search_terms = fulltext_query if fulltext_query else " ".join(filtered_keywords)
            
            logger.info(f"📚 전문검색 실행: '{search_terms}' (언어: {language}, 키워드: {filtered_keywords})")
            
            async with self.async_session_local() as db:
                # tb_document_search_index를 사용한 Multilingual 전문검색
                # korean: 한글 형태소 분석, english: 영어 검색
                container_id_list = "', '".join(container_ids)
                
                # 한글/영어 혼용 검색을 위한 쿼리 생성
                # OR 조건으로 korean 또는 english 구성에서 매칭되면 결과 반환
                query_sql = f"""
                    SELECT 
                        s.search_doc_id,
                        s.file_bss_info_sno,
                        s.knowledge_container_id,
                        0 as chunk_index,
                        s.full_content as content,
                        s.content_summary as main_text,
                        s.document_type as doc_type,
                        GREATEST(
                            ts_rank(s.content_tsvector, plainto_tsquery('korean', :search_terms)),
                            ts_rank(s.content_tsvector_en, plainto_tsquery('english', :search_terms))
                        ) as fulltext_score,
                        s.last_updated,
                        f.file_lgc_nm,
                        f.path
                    FROM tb_document_search_index s
                    JOIN tb_file_bss_info f ON s.file_bss_info_sno = f.file_bss_info_sno
                    WHERE s.knowledge_container_id IS NOT NULL 
                        AND s.knowledge_container_id != '' 
                        AND s.knowledge_container_id NOT IN ('NONE', 'None', 'null', 'NULL')
                        AND (s.knowledge_container_id = 'DEFAULT_CONTAINER' OR s.knowledge_container_id IN ('{container_id_list}'))
                        AND f.del_yn = 'N'
                        AND s.indexing_status = 'indexed'
                        AND (
                            s.content_tsvector @@ plainto_tsquery('korean', :search_terms)
                            OR s.content_tsvector_en @@ plainto_tsquery('english', :search_terms)
                        )
                    ORDER BY fulltext_score DESC
                    LIMIT :max_results
                """
                
                result = await db.execute(
                    text(query_sql),
                    {
                        "search_terms": search_terms,
                        "max_results": max_results
                    }
                )
                
                results = []
                for row in result.fetchall():
                    results.append({
                        "search_doc_id": row.search_doc_id,
                        "file_bss_info_sno": row.file_bss_info_sno,
                        "knowledge_container_id": row.knowledge_container_id,
                        "chunk_index": row.chunk_index,
                        "content": row.content,
                        "main_text": row.main_text,
                        "doc_type": row.doc_type,
                        "fulltext_score": float(row.fulltext_score),
                        "search_method": "fulltext",
                        "file_name": row.file_lgc_nm,
                        "file_path": row.path
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"전문검색 실패: {str(e)}")
            return []
    
    async def _preprocess_query(self, query: str) -> Dict[str, Any]:
        """
        🚀 통합 질의 처리 파이프라인 사용
        
        변경 사항 (2025-10-17):
        - 통합 파이프라인 (query_pipeline.process_user_query) 사용
        - 일관된 불용어 제거 (UNIFIED_STOPWORDS)
        - 의도 기반 검색 전략 적용
        """
        try:
            # 통합 파이프라인으로 질의 처리
            processed = await process_user_query(query, search_type="general")
            
            logger.info(f"✅ 통합 파이프라인 처리 완료: {processed.processing_time_ms:.1f}ms")
            logger.info(f"  - 의도: {processed.intent} (confidence: {processed.intent_confidence:.2f})")
            logger.info(f"  - 키워드: {processed.keywords} → {processed.filtered_keywords}")
            logger.info(f"  - 전문검색 쿼리: '{processed.fulltext_query}'")
            
            # 기존 인터페이스 호환을 위한 변환
            return {
                "original_text": processed.original_text,
                "normalized_text": processed.normalized_text,
                "language": processed.language,  # 언어 정보 추가 (ko/en/mixed)
                "intent": processed.intent,
                "main_keywords": processed.filtered_keywords,
                "keywords": processed.keywords,
                "filtered_keywords": processed.filtered_keywords,
                "fulltext_query": processed.fulltext_query,
                "keyword_query": processed.keyword_query,
                "search_operators": processed.filtered_keywords,
                "search_query_string": processed.fulltext_query,
                "weights": processed.weights,
                "similarity_threshold": processed.similarity_threshold,
                # 기존 필드 유지 (하위 호환성)
                "context_keywords": [],
                "optimized_keywords": processed.filtered_keywords,
                "expanded_keywords": processed.filtered_keywords
            }
            
        except Exception as e:
            logger.error(f"❌ 통합 파이프라인 처리 실패: {str(e)}")
            # Fallback: 최소 기능
            return {
                "original_text": query,
                "intent": "find_document",
                "main_keywords": query.split(),
                "keywords": query.split(),
                "filtered_keywords": query.split(),
                "fulltext_query": query,
                "search_operators": [query],
                "search_query_string": query,
                "context_keywords": [],
                "optimized_keywords": query.split(),
                "expanded_keywords": query.split()
            }

    
    async def _get_accessible_containers(
        self,
        user_emp_no: str,
        requested_containers: Optional[List[str]] = None
    ) -> List[str]:
        """사용자가 검색 가능한 컨테이너 목록 반환"""
        try:
            accessible = await permission_service.get_user_accessible_containers(
                user_emp_no, "VIEWER"
            )
            
            container_ids = [c["container_id"] for c in accessible]
            
            if requested_containers:
                # 요청된 컨테이너 중 권한이 있는 것만 필터링
                container_ids = [
                    cid for cid in requested_containers 
                    if cid in container_ids
                ]
            
            return container_ids
            
        except Exception as e:
            logger.error(f"접근 가능한 컨테이너 조회 실패: {str(e)}")
            return []
    
    async def _save_search_history(
        self,
        user_emp_no: str,
        query: str,
        results: List[Dict[str, Any]],
        search_type: str,
        container_ids: List[str]
    ):
        """검색 기록 저장 - 실제 테이블 스키마에 맞춤"""
        try:
            async with self.async_session_local() as db:
                # 실제 테이블 컬럼에 맞춰 검색 기록 저장
                await db.execute(
                    text("""
                        INSERT INTO tb_chat_history (
                            session_id, user_emp_no, user_message, assistant_response,
                            search_results, accessible_containers
                        ) VALUES (
                            :session_id, :user_emp_no, :user_message, :assistant_response,
                            :search_results, :accessible_containers
                        )
                    """),
                    {
                        "session_id": f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        "user_emp_no": user_emp_no,
                        "user_message": query,
                        "assistant_response": f"검색 결과 {len(results)}건 발견",
                        "search_results": json.dumps({
                            "search_type": search_type,
                            "result_count": len(results),
                            "container_ids": container_ids,
                            "results": self._clean_results_for_json(results[:5])  # 최대 5개 결과만 저장
                        }, default=str),  # NaN 등의 값을 문자열로 변환
                        "accessible_containers": container_ids
                    }
                )
                await db.commit()
                
        except Exception as e:
            logger.error(f"검색 기록 저장 실패: {str(e)}")
            # 검색 기록 저장 실패해도 검색 자체는 계속 진행
    
    async def _format_search_results(
        self,
        results: List[Dict[str, Any]],
        user_emp_no: str,
        query: str = ""
    ) -> List[Dict[str, Any]]:
        """검색 결과 포맷팅 - API 스키마에 맞게 포맷팅"""
        formatted = []
        
        # 컨테이너 상세 정보 가져오기 (데이터베이스에서 실제 이름과 경로 조회)
        container_ids = []
        for r in results:
            container_id = r.get("knowledge_container_id") or r.get("container_id")
            if container_id:
                container_ids.append(container_id)
                logger.info(f"🔍 FORMAT_SEARCH_RESULTS - 결과에서 발견된 container_id: {container_id}")
        
        logger.info(f"🔍 FORMAT_SEARCH_RESULTS - 수집된 container_ids: {container_ids}")
        container_details = await self._get_container_details(list(set(container_ids)))
        logger.info(f"🔍 FORMAT_SEARCH_RESULTS - 조회된 container_details: {container_details}")
        
        for result in results:
            # 검색 방법 결정
            search_methods = result.get("search_methods", [])
            if not search_methods:
                search_methods = [result.get("search_method", "unknown")]
            
            # match_type 결정 (primary search method)
            match_type = "hybrid"
            if len(search_methods) == 1:
                if "vector" in search_methods[0]:
                    match_type = "vector"
                elif "keyword" in search_methods[0]:
                    match_type = "keyword"
                elif "fulltext" in search_methods[0]:
                    match_type = "fulltext"
            
            # similarity_score 계산 및 추출
            similarity_score = 0.0
            scores = result.get("scores", {})
            
            # 먼저 combined_score 확인
            if result.get("combined_score"):
                similarity_score = result.get("combined_score", 0.0)
            elif isinstance(scores, dict) and scores.get("similarity_score"):
                similarity_score = scores.get("similarity_score", 0.0)
            elif result.get("similarity_score"):
                similarity_score = result.get("similarity_score", 0.0)
            else:
                # 개별 점수들을 조합하여 계산
                similarity_score = (
                    result.get("similarity_score", 0.0) * 0.6 +
                    result.get("keyword_score", 0.0) * 0.3 +
                    result.get("fulltext_score", 0.0) * 0.1
                )
            
            # NaN 체크
            if math.isnan(similarity_score):
                similarity_score = 0.0
            
            # ✅ 유사도 점수 정규화: 0.0-1.0 범위로 강제 조정
            similarity_score = self._normalize_similarity_score(similarity_score)
            
            # 백분율로 변환 (0-100%)
            similarity_percentage = similarity_score * 100
            
            # file_id를 문자열로 변환
            file_id = result.get("file_bss_info_sno") or result.get("file_id")
            if file_id is not None:
                file_id = str(file_id)
            else:
                file_id = ""
            
            # 제목 결정 - 파일 단위 결과에 맞게 개선
            title = result.get("file_name", "")
            if not title:
                # 파일명이 없는 경우 내용의 첫 부분을 제목으로 사용
                content = result.get("content", "")
                if content:
                    title = content[:50] + "..." if len(content) > 50 else content
                else:
                    title = "제목 없음"
            
            # 파일 확장자에 따른 제목 정리
            if title and "." in title:
                # 확장자가 있는 경우 확장자 제거하여 표시
                title_without_ext = title.rsplit(".", 1)[0]
                if len(title_without_ext) > 100:
                    title = title_without_ext[:100] + "..."
                else:
                    title = title_without_ext
            elif title and len(title) > 100:
                title = title[:100] + "..."
            
            # 내용 미리보기 - 파일 단위에 맞게 개선
            content = result.get("content", "")
            content_preview = content[:300] + "..." if len(content) > 300 else content
            
            # 검색 키워드 하이라이트 적용
            if content_preview and query:
                content_preview = self._highlight_keywords(content_preview, query)
            
            # 청크 정보 추가
            chunk_info = ""
            if result.get("file_level_result") and result.get("chunk_count", 0) > 1:
                chunk_info = f" (총 {result.get('chunk_count')}개 관련 섹션)"
            
            # 컨테이너 상세 정보 가져오기
            container_id = result.get("knowledge_container_id") or result.get("container_id", "")
            logger.info(f"🔍 하이브리드 검색 결과 처리: doc_id={result.get('search_doc_id')}, container_id={container_id}")
            logger.info(f"🔍 전체 result 키들: {list(result.keys())}")
            logger.info(f"🔍 사용 가능한 컨테이너 details: {list(container_details.keys())}")
            
            container_detail = container_details.get(container_id, {})
            logger.info(f"🔍 컨테이너 {container_id}에 대한 detail: {container_detail}")
            
            container_name = container_detail.get("container_name", container_id)
            
            # 계층 경로 구성 (org_path 우선 사용, 없으면 container_name)
            container_path = container_detail.get("full_path", "")
            if not container_path:
                # full_path가 없으면 container_name 사용
                container_path = container_name
            
            # 경로를 아이콘과 함께 구성
            container_path_with_icons = self._build_container_path_with_icons(container_path)
            
            logger.info(f"🔍 최종 컨테이너 정보: name={container_name}, path={container_path}, with_icons={container_path_with_icons}")
            
            # 디버깅 로그 추가
            logger.info(f"하이브리드 검색 - 컨테이너 정보 - ID: {container_id}, 이름: {container_name}, 경로: {container_path}")
            logger.info(f"하이브리드 검색 - 아이콘 포함 경로: {container_path_with_icons}")
            logger.info(f"하이브리드 검색 - container_detail 전체: {container_detail}")
            
            # 컨테이너 정보가 비어있는 경우 특별 처리
            if not container_id:
                logger.warning(f"컨테이너 ID가 없는 결과: {result}")
                container_path_with_icons = "📂 경로 없음"
            
            # 멀티모달 필드 추가
            modality = result.get("modality", "text")
            has_images = result.get("has_images", False)
            image_count = result.get("image_count", 0)
            clip_score = result.get("clip_score")
            
            # document_id 결정 (file_bss_info_sno 사용)
            document_id = result.get("file_bss_info_sno") or result.get("document_id") or file_id
            
            # API 스키마에 맞는 포맷
            formatted_result = {
                "file_id": file_id,
                "title": title + chunk_info,
                "content_preview": content_preview,
                "similarity_score": float(similarity_score),  # 0.0-1.0 범위의 정규화된 점수
                "match_type": match_type,
                "container_id": container_id,
                "container_name": container_name,  # 사용자 친화적인 컨테이너 이름
                "container_path": container_path_with_icons,  # 아이콘 포함 계층 경로
                "container_icon": "📂",  # 기본 폴더 아이콘
                "file_path": result.get("file_path"),
                "metadata": {
                    "document_id": str(document_id) if document_id else file_id,  # file_bss_info_sno를 document_id로 사용
                    "chunk_index": result.get("chunk_index"),
                    "chunk_count": result.get("chunk_count", 1),
                    "file_level_result": result.get("file_level_result", False),
                    "keywords": result.get("keywords", []),
                    "proper_nouns": result.get("proper_nouns", []),
                    "corp_names": result.get("corp_names", []),
                    "document_type": self._get_document_type(result),
                    "search_methods": search_methods,
                    "scores": scores,
                    "last_updated": result.get("last_updated"),
                    "file_name": result.get("file_name")
                },
                # 멀티모달 검색 추가 필드
                "has_images": has_images,
                "image_count": image_count,
                "modality": modality,
            }
            
            # CLIP 점수 추가 (있는 경우)
            if clip_score is not None:
                formatted_result["clip_score"] = float(clip_score)
            
            # 이미지 청크인 경우 이미지 URL 추가
            if modality == "image":
                chunk_id = result.get("chunk_id")
                blob_key = result.get("blob_key")  # 신규: blob_key 직접 사용
                
                if chunk_id:
                    formatted_result["chunk_id"] = chunk_id
                    
                    # blob_key가 있으면 직접 사용 (신규 방식)
                    if blob_key:
                        formatted_result["image_blob_key"] = blob_key
                    else:
                        # blob_key가 없으면 동적 생성 (구 데이터 호환성)
                        source_object_ids = result.get("source_object_ids", [])
                        page_number = result.get("page_number")
                        doc_id = result.get("file_bss_info_sno") or result.get("document_id")
                        
                        if doc_id and source_object_ids and len(source_object_ids) > 0:
                            # Azure Blob Storage 키 패턴: multimodal/{doc_id}/objects/image_{object_id}_{page_number}.png
                            object_id = source_object_ids[0]
                            page_num = page_number if page_number is not None else 1
                            formatted_result["image_blob_key"] = f"multimodal/{doc_id}/objects/image_{object_id}_{page_num}.png"

            # 파일 그룹화 단계에서 선정된 썸네일(있을 경우)을 그대로 노출
            thumb_blob = result.get("thumbnail_blob_key") or result.get("image_blob_key")
            thumb_chunk = result.get("thumbnail_chunk_id") or result.get("chunk_id")
            if thumb_blob:
                formatted_result["thumbnail_blob_key"] = thumb_blob
            if thumb_chunk:
                formatted_result["thumbnail_chunk_id"] = thumb_chunk
            
            logger.info(f"포맷된 결과: {formatted_result}")
            formatted.append(formatted_result)
        
        return formatted


    async def _get_search_suggestions(
        self,
        query: str,
        user_emp_no: str,
        limit: int = 10
    ) -> List[str]:
        """
        검색 자동완성 제안 - full_content와 document_title에서 추출
        
        변경 사항 (2025-10-16):
        - keywords 컬럼 제거로 인해 full_content와 document_title에서 직접 추출
        - pg_trgm 인덱스를 활용한 유사도 기반 제안
        """
        try:
            accessible_containers = await self._get_accessible_containers(user_emp_no)
            
            if not accessible_containers:
                return []
            
            async with self.async_session_local() as db:
                # full_content와 document_title에서 쿼리와 유사한 단어 추출
                container_id_list = "', '".join(accessible_containers)
                query_sql = f"""
                    SELECT DISTINCT 
                        s.document_title as suggestion
                    FROM tb_document_search_index s
                    JOIN tb_file_bss_info f ON s.file_bss_info_sno = f.file_bss_info_sno
                    WHERE s.knowledge_container_id IS NOT NULL 
                        AND s.knowledge_container_id != '' 
                        AND s.knowledge_container_id NOT IN ('NONE', 'None', 'null', 'NULL')
                        AND (s.knowledge_container_id = 'DEFAULT_CONTAINER' OR s.knowledge_container_id IN ('{container_id_list}'))
                        AND f.del_yn = 'N'
                        AND s.indexing_status = 'indexed'
                        AND s.document_title IS NOT NULL
                        AND s.document_title ILIKE :query_pattern
                    ORDER BY suggestion
                    LIMIT :limit_count
                """
                
                result = await db.execute(
                    text(query_sql),
                    {
                        "query_pattern": f"%{query}%",
                        "limit_count": limit
                    }
                )
                
                suggestions = [row.suggestion for row in result.fetchall() if row.suggestion]
                return suggestions
                
        except Exception as e:
            logger.error(f"검색 제안 실패: {str(e)}")
            return []
    
    async def _group_results_by_file(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색 결과를 파일 단위로 그룹화
        각 파일당 최고 점수의 청크만 선택하여 파일 단위 결과 생성
        """
        try:
            file_groups = {}
            
            for result in results:
                file_id = result.get("file_bss_info_sno")
                if not file_id:
                    continue
                
                # 점수 계산 (combined_score 또는 개별 점수 사용)
                score = 0.0
                if "combined_score" in result:
                    score = result["combined_score"]
                else:
                    # 개별 점수들을 조합
                    score = (
                        result.get("similarity_score", 0.0) * 0.6 +
                        result.get("keyword_score", 0.0) * 0.3 +
                        result.get("fulltext_score", 0.0) * 0.1
                    )
                
                # NaN 체크
                if math.isnan(score):
                    score = 0.0
                
                # 파일별로 최고 점수 청크만 유지
                if file_id not in file_groups or score > file_groups[file_id]["max_score"]:
                    # 대표 청크 내용 생성 (여러 청크의 내용을 합칠 수도 있음)
                    representative_content = result.get("content", "")
                    
                    file_groups[file_id] = {
                        "max_score": score,
                        "representative_result": {
                            **result,
                            "combined_score": score,
                            "content": representative_content,
                            "chunk_count": 1,  # 나중에 동일 파일의 청크 수를 카운트
                            "file_level_result": True  # 파일 레벨 결과임을 표시
                        }
                    }
            
            # 파일별 청크 개수 계산
            file_chunk_counts = {}
            for result in results:
                file_id = result.get("file_bss_info_sno")
                if file_id:
                    file_chunk_counts[file_id] = file_chunk_counts.get(file_id, 0) + 1
            
            # 청크 개수 정보 추가
            grouped_results = []
            for file_id, group_data in file_groups.items():
                result = group_data["representative_result"]
                result["chunk_count"] = file_chunk_counts.get(file_id, 1)

                # Thumbnail selection: prefer an image chunk within the same file group
                # Scan original results for same file_id and find an image modality chunk
                thumbnail_blob_key = None
                thumbnail_chunk_id = None
                for r in results:
                    if r.get("file_bss_info_sno") != file_id:
                        continue
                    # modality may be present or inside metadata_json
                    modality = r.get("modality")
                    if not modality and r.get("metadata"):
                        modality = r.get("metadata", {}).get("modality")
                    if modality == "image":
                        # prefer explicit chunk-level blob key if available
                        # check metadata for blob key/object id/page no
                        meta = r.get("metadata") or {}
                        obj_id = meta.get("object_id") or meta.get("objectIdx") or r.get("chunk_index")
                        page_no = meta.get("page_no", 1)
                        # common blob key patterns used by pipeline
                        if file_id:
                            thumbnail_blob_key = f"multimodal/{file_id}/objects/image_{obj_id}_{page_no}.png"
                            thumbnail_chunk_id = r.get("chunk_id") or r.get("search_doc_id") or r.get("document_id")
                            break

                if thumbnail_blob_key:
                    result["thumbnail_blob_key"] = thumbnail_blob_key
                    result["thumbnail_chunk_id"] = thumbnail_chunk_id

                grouped_results.append(result)
            
            # 점수순으로 정렬
            grouped_results.sort(key=lambda x: x.get("combined_score", 0.0), reverse=True)
            
            logger.info(f"파일 그룹화 완료: {len(results)}개 청크 -> {len(grouped_results)}개 파일")
            return grouped_results
            
        except Exception as e:
            logger.error(f"파일 그룹화 실패: {str(e)}")
            return results  # 실패시 원본 결과 반환
    
    async def _get_search_analytics(self, period: str = "7d") -> Dict[str, Any]:
        """검색 분석 정보"""
        try:
            days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}[period]
            
            async with self.async_session_local() as db:
                # 검색 통계 쿼리 - 실제 테이블 컬럼 사용
                analytics_sql = """
                    SELECT 
                        COUNT(*) as total_searches,
                        COUNT(DISTINCT user_emp_no) as unique_users,
                        0.1 as avg_response_time,
                        COUNT(CASE WHEN search_results IS NOT NULL 
                                   AND search_results::jsonb->>'result_count' != '0' 
                                   THEN 1 END) as successful_searches
                    FROM tb_chat_history 
                    WHERE user_message IS NOT NULL
                        AND search_results IS NOT NULL
                """
                
                result = await db.execute(text(analytics_sql))
                stats = result.fetchone()
                
                return {
                    "period": period,
                    "total_searches": stats.total_searches or 0,
                    "unique_users": stats.unique_users or 0,
                    "avg_response_time_ms": float(stats.avg_response_time or 0) * 1000,  # 초를 밀리초로 변환
                    "success_rate": (stats.successful_searches / max(stats.total_searches, 1)) * 100,
                    "generated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"검색 분석 실패: {str(e)}")
            return {
                "period": period,
                "total_searches": 0,
                "unique_users": 0,
                "avg_response_time_ms": 0.0,
                "success_rate": 0.0,
                "error": str(e)
            }


    async def vector_search_only(
        self,
        query: str,
        user_emp_no: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """벡터 검색 전용 메서드"""
        accessible_containers = await self._get_accessible_containers(user_emp_no)
        if not accessible_containers:
            return {"results": [], "total_count": 0, "message": "접근 가능한 컨테이너가 없습니다."}
        
        processed_query = await self._preprocess_query(query)
        results = await self._vector_search(processed_query, accessible_containers, limit * 2, None)  # 그룹화를 위해 더 많이 검색
        grouped_results = await self._group_results_by_file(results)
        formatted_results = await self._format_search_results(grouped_results[:limit], user_emp_no, query)
        
        return {
            "results": formatted_results,
            "total_count": len(formatted_results),
            "search_type": "vector_only"
        }
    
    async def keyword_search_only(
        self,
        query: str,
        user_emp_no: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """키워드 검색 전용 메서드"""
        accessible_containers = await self._get_accessible_containers(user_emp_no)
        if not accessible_containers:
            return {"results": [], "total_count": 0, "message": "접근 가능한 컨테이너가 없습니다."}
        
        processed_query = await self._preprocess_query(query)
        results = await self._keyword_search(processed_query, accessible_containers, limit * 2, None)  # 그룹화를 위해 더 많이 검색
        grouped_results = await self._group_results_by_file(results)
        formatted_results = await self._format_search_results(grouped_results[:limit], user_emp_no, query)
        
        return {
            "results": formatted_results,
            "total_count": len(formatted_results),
            "search_type": "keyword_only"
        }
    
    async def get_search_suggestions(
        self,
        partial_query: str,
        user_emp_no: str,
        limit: int = 10
    ) -> List[str]:
        """검색 제안 메서드"""
        return await self._get_search_suggestions(partial_query, user_emp_no, limit)
    
    async def get_search_analytics(
        self,
        user_emp_no: str,
        period: str = "7d"
    ) -> Dict[str, Any]:
        """검색 분석 메서드"""
        return await self._get_search_analytics(period)
    
    async def reindex_document(
        self,
        file_id: str,
        user_emp_no: str
    ) -> Dict[str, Any]:
        """문서 재인덱싱 메서드"""
        try:
            logger.info(f"문서 재인덱싱 시작: {file_id}, 사용자: {user_emp_no}")
            
            # 1. 파일 정보 조회
            async with self.async_session_local() as db:
                file_query = """
                    SELECT file_bss_info_sno, file_lgc_nm, path, knowledge_container_id
                    FROM tb_file_bss_info 
                    WHERE file_bss_info_sno = :file_id AND del_yn = 'N'
                """
                result = await db.execute(text(file_query), {"file_id": file_id})
                file_info = result.fetchone()
                
                if not file_info:
                    return {
                        "success": False,
                        "file_id": file_id,
                        "error": "파일을 찾을 수 없습니다."
                    }
                
                # 2. 기존 검색 인덱스 삭제
                await db.execute(
                    text("DELETE FROM tb_document_search_index WHERE file_bss_info_sno = :file_id"),
                    {"file_id": file_id}
                )
                
                # 3. 기존 벡터 청크 삭제
                await db.execute(
                    text("DELETE FROM vs_doc_contents_chunks WHERE file_bss_info_sno = :file_id"),
                    {"file_id": file_id}
                )
                
                await db.commit()
            
            # 4. 문서 처리 파이프라인 재실행
            from app.services.document.pipeline.integrated_document_pipeline_service import integrated_document_pipeline_service
            
            pipeline_result = await integrated_document_pipeline_service.process_document_for_rag(
                file_path=file_info.path,
                file_name=file_info.file_lgc_nm,
                container_id=file_info.knowledge_container_id,
                user_emp_no=user_emp_no
            )
            
            if pipeline_result.get("success"):
                logger.info(f"문서 재인덱싱 완료: {file_id}")
                return {
                    "success": True,
                    "file_id": file_id,
                    "message": "재인덱싱이 완료되었습니다.",
                    "status": "completed",
                    "pipeline_result": pipeline_result
                }
            else:
                return {
                    "success": False,
                    "file_id": file_id,
                    "error": f"파이프라인 처리 실패: {pipeline_result.get('error')}"
                }
            
        except Exception as e:
            logger.error(f"문서 재인덱싱 실패: {str(e)}")
            return {
                "success": False,
                "file_id": file_id,
                "error": str(e)
            }

    def _clean_results_for_json(self, results):
        """JSON 직렬화를 위해 결과를 정리하는 메서드"""
        cleaned_results = []
        for result in results:
            cleaned_result = {}
            for key, value in result.items():
                if isinstance(value, float):
                    if math.isnan(value) or math.isinf(value):
                        cleaned_result[key] = 0.0
                    else:
                        cleaned_result[key] = value
                else:
                    cleaned_result[key] = value
            cleaned_results.append(cleaned_result)
        return cleaned_results

    # 하위 호환성을 위한 기존 메서드들
    async def search_similar_documents(
        self,
        query: str,
        user_emp_no: str = "SYSTEM",
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        하위 호환성을 위한 레거시 메서드
        하이브리드 검색으로 리다이렉트
        """
        try:
            result = await self.hybrid_search(
                query=query,
                user_emp_no=user_emp_no,
                max_results=limit,
                search_type="hybrid"
            )
            return result.get("results", [])
        except Exception as e:
            logger.error(f"Legacy search method error: {str(e)}")
            return []

    async def unified_search(
        self,
        query: str,
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_results: int = 10,
        search_type: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        통합검색 - 파일 단위로 그룹화된 검색 결과
        화면 표시용 검색으로 동일 파일의 청크들을 하나로 합쳐서 표시
        """
        try:
            # 기본 하이브리드 검색 수행 (청크 단위)
            chunk_results = await self.hybrid_search(
                query=query,
                user_emp_no=user_emp_no,
                container_ids=container_ids,
                max_results=max_results * 3,  # 더 많은 청크를 가져와서 파일별로 그룹화
                search_type=search_type,
                filters=filters
            )
            
            # 파일별로 그룹화 및 대표 정보 생성
            file_groups = {}
            for result in chunk_results.get("results", []):
                file_id = result.get("file_id")
                if not file_id:
                    continue
                    
                if file_id not in file_groups:
                    # 파일의 첫 번째 청크를 대표로 설정
                    file_groups[file_id] = {
                        "file_id": file_id,
                        "title": result.get("metadata", {}).get("file_name", "제목 없음"),
                        "file_path": result.get("file_path"),
                        "container_id": result.get("container_id"),
                        "match_type": result.get("match_type"),
                        "max_similarity_score": result.get("similarity_score", 0.0),
                        "content_preview": result.get("content_preview", "")[:500],  # 파일 대표 내용
                        "chunk_count": 1,
                        "top_chunks": [result],  # 상위 청크 정보 보관
                        "metadata": {
                            "file_name": result.get("metadata", {}).get("file_name"),
                            "document_type": result.get("metadata", {}).get("document_type"),
                            "keywords": result.get("metadata", {}).get("keywords", []),
                            "search_methods": result.get("metadata", {}).get("search_methods", []),
                            "last_updated": result.get("metadata", {}).get("last_updated")
                        }
                    }
                else:
                    # 동일 파일의 추가 청크 처리
                    file_group = file_groups[file_id]
                    file_group["chunk_count"] += 1
                    
                    # 더 높은 점수가 있으면 업데이트
                    current_score = result.get("similarity_score", 0.0)
                    if current_score > file_group["max_similarity_score"]:
                        file_group["max_similarity_score"] = current_score
                        file_group["content_preview"] = result.get("content_preview", "")[:500]
                        file_group["match_type"] = result.get("match_type")
                    
                    # 상위 3개 청크만 보관
                    if len(file_group["top_chunks"]) < 3:
                        file_group["top_chunks"].append(result)
                    
                    # 키워드 통합
                    existing_keywords = set(file_group["metadata"].get("keywords", []))
                    new_keywords = set(result.get("metadata", {}).get("keywords", []))
                    file_group["metadata"]["keywords"] = list(existing_keywords | new_keywords)
            
            # 점수 순으로 정렬하고 제한
            sorted_files = sorted(
                file_groups.values(),
                key=lambda x: x["max_similarity_score"],
                reverse=True
            )[:max_results]
            
            return {
                "results": sorted_files,
                "total_count": len(sorted_files),
                "search_type": f"unified_{search_type}",
                "accessible_containers": chunk_results.get("accessible_containers", []),
                "query_processed": chunk_results.get("query_processed", {}),
                "execution_time": datetime.now().isoformat(),
                "message": f"{len(sorted_files)}개 파일에서 검색 결과를 찾았습니다."
            }
            
        except Exception as e:
            logger.error(f"통합검색 실패: {str(e)}")
            raise

    async def context_search(
        self,
        query: str,
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_results: int = 20,
        search_type: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None,
        include_references: bool = True
    ) -> Dict[str, Any]:
        """
        RAG 컨텍스트용 청크 단위 검색
        챗봇 응답 생성을 위한 정밀한 청크 단위 검색
        """
        try:
            # 기본 하이브리드 검색 수행 (청크 단위)
            chunk_results = await self.hybrid_search(
                query=query,
                user_emp_no=user_emp_no,
                container_ids=container_ids,
                max_results=max_results,
                search_type=search_type,
                filters=filters
            )
            
            # RAG용 상세 정보 추가
            enhanced_results = []
            for result in chunk_results.get("results", []):
                enhanced_result = {
                    "chunk_id": result.get("metadata", {}).get("document_id"),
                    "file_id": result.get("file_id"),
                    "content": result.get("content_preview"),  # 전체 청크 내용
                    "similarity_score": result.get("similarity_score"),
                    "match_type": result.get("match_type"),
                    "container_id": result.get("container_id"),
                    "chunk_info": {
                        "chunk_index": result.get("metadata", {}).get("chunk_index"),
                        "file_name": result.get("metadata", {}).get("file_name"),
                        "file_path": result.get("file_path"),
                        "page_number": self._extract_page_number(result),
                        "section_title": self._extract_section_title(result)
                    },
                    "reference_info": {
                        "title": result.get("title"),
                        "source": f"{result.get('metadata', {}).get('file_name', 'Unknown')}",
                        "page": self._extract_page_number(result),
                        "section": self._extract_section_title(result),
                        "chunk_position": f"청크 {result.get('metadata', {}).get('chunk_index', 0) + 1}"
                    } if include_references else None,
                    "metadata": {
                        "keywords": result.get("metadata", {}).get("keywords", []),
                        "proper_nouns": result.get("metadata", {}).get("proper_nouns", []),
                        "corp_names": result.get("metadata", {}).get("corp_names", []),
                        "search_methods": result.get("metadata", {}).get("search_methods", []),
                        "document_type": result.get("metadata", {}).get("document_type"),
                        "relevance_explanation": self._generate_relevance_explanation(result, query)
                    }
                }
                enhanced_results.append(enhanced_result)
            
            return {
                "results": enhanced_results,
                "total_count": len(enhanced_results),
                "search_type": f"context_{search_type}",
                "context_info": {
                    "total_chunks": len(enhanced_results),
                    "average_score": sum(r["similarity_score"] for r in enhanced_results) / max(len(enhanced_results), 1),
                    "score_distribution": self._calculate_score_distribution(enhanced_results),
                    "file_sources": list(set(r["chunk_info"]["file_name"] for r in enhanced_results if r["chunk_info"]["file_name"]))
                },
                "accessible_containers": chunk_results.get("accessible_containers", []),
                "query_processed": chunk_results.get("query_processed", {}),
                "execution_time": datetime.now().isoformat(),
                "message": f"RAG 컨텍스트용 {len(enhanced_results)}개 청크를 준비했습니다."
            }
            
        except Exception as e:
            logger.error(f"컨텍스트 검색 실패: {str(e)}")
            raise

    def _extract_page_number(self, result: Dict[str, Any]) -> Optional[int]:
        """청크에서 페이지 번호 추출"""
        try:
            metadata = result.get("metadata", {})
            # metadata에서 페이지 정보 찾기
            if "page" in metadata:
                return metadata["page"]
            if "page_number" in metadata:
                return metadata["page_number"]
            
            # 청크 인덱스를 기반으로 페이지 추정 (청크당 약 1/2 페이지로 가정)
            chunk_index = metadata.get("chunk_index", 0)
            return max(1, chunk_index // 2 + 1)
        except:
            return None

    def _extract_section_title(self, result: Dict[str, Any]) -> Optional[str]:
        """청크에서 섹션 제목 추출"""
        try:
            content = result.get("content_preview", "")
            # 내용의 첫 줄이 제목일 가능성이 높음
            lines = content.split('\n')
            if lines and len(lines[0]) < 100:  # 제목은 보통 짧음
                return lines[0].strip()
            return None
        except:
            return None

    def _generate_relevance_explanation(self, result: Dict[str, Any], query: str) -> str:
        """검색 결과의 관련성 설명 생성"""
        try:
            match_type = result.get("match_type", "unknown")
            score = result.get("similarity_score", 0.0)
            
            if match_type == "vector":
                return f"의미적 유사도 {score:.2f}로 매칭"
            elif match_type == "keyword":
                return f"키워드 매칭으로 발견"
            elif match_type == "fulltext":
                return f"전문검색으로 발견"
            elif match_type == "hybrid":
                return f"복합 검색 점수 {score:.2f}로 매칭"
            else:
                return f"검색 점수 {score:.2f}"
        except:
            return "관련 내용"

    async def _get_container_details(self, container_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        컨테이너 상세 정보 조회 - 사용자별 권한 정보와 계층 경로 포함
        """
        try:
            if not container_ids:
                logger.info("컨테이너 ID 목록이 비어있습니다.")
                return {}

            now = time.time()
            container_details: Dict[str, Dict[str, Any]] = {}
            uncached_ids: List[str] = []

            for container_id in container_ids:
                cache_entry = self._container_details_cache.get(container_id)
                if cache_entry and now - cache_entry[0] <= self._container_cache_ttl:
                    container_details[container_id] = cache_entry[1]
                else:
                    uncached_ids.append(container_id)

            if not uncached_ids:
                logger.info("컨테이너 정보 캐시 적중: %s", list(container_details.keys()))
                return container_details

            logger.info(f"컨테이너 정보 조회 시작(미캐시): {uncached_ids}")
            container_id_to_name = await self._get_all_container_names()

            async with self.async_session_local() as db:
                stmt = select(
                    TbKnowledgeContainers.container_id,
                    TbKnowledgeContainers.container_name,
                    TbKnowledgeContainers.parent_container_id,
                    TbKnowledgeContainers.org_level,
                    TbKnowledgeContainers.org_path,
                    TbKnowledgeContainers.container_type
                ).where(
                    TbKnowledgeContainers.is_active == True,
                    TbKnowledgeContainers.container_id.in_(uncached_ids)
                )

                result = await db.execute(stmt)
                rows = result.fetchall()

            fetched_ids = set()
            for row in rows:
                friendly_path = self._convert_path_ids_to_names(row.org_path, container_id_to_name)
                detail = {
                    "container_id": row.container_id,
                    "container_name": row.container_name,
                    "parent_container_id": row.parent_container_id,
                    "full_path": friendly_path or row.container_name,
                    "hierarchy_level": row.org_level or 1,
                    "container_type": row.container_type,
                }
                container_details[row.container_id] = detail
                self._container_details_cache[row.container_id] = (now, detail)
                fetched_ids.add(row.container_id)

            for container_id in uncached_ids:
                if container_id in fetched_ids:
                    continue
                logger.warning(f"컨테이너 {container_id}를 데이터베이스에서 찾을 수 없습니다.")
                detail = {
                    "container_id": container_id,
                    "container_name": container_id,
                    "parent_container_id": None,
                    "full_path": container_id,
                    "hierarchy_level": 1,
                    "container_type": "UNKNOWN"
                }
                container_details[container_id] = detail
                self._container_details_cache[container_id] = (now, detail)

            # 기본 컨테이너 정보 추가
            if "DEFAULT_CONTAINER" in container_ids and "DEFAULT_CONTAINER" not in container_details:
                default_detail = {
                    "container_id": "DEFAULT_CONTAINER",
                    "container_name": "기본 문서",
                    "parent_container_id": None,
                    "full_path": "기본 문서",
                    "hierarchy_level": 1,
                    "container_type": "DEFAULT"
                }
                container_details["DEFAULT_CONTAINER"] = default_detail
                self._container_details_cache["DEFAULT_CONTAINER"] = (now, default_detail)

            return container_details

        except Exception as e:
            logger.error(f"컨테이너 상세 정보 조회 실패: {str(e)}")
            fallback = {}
            for container_id in container_ids:
                fallback[container_id] = {
                    "container_id": container_id,
                    "container_name": container_id,
                    "parent_container_id": None,
                    "full_path": container_id,
                    "hierarchy_level": 1,
                    "container_type": "UNKNOWN"
                }
            return fallback

    async def _get_all_container_names(self) -> Dict[str, str]:
        """컨테이너 ID → 이름 매핑 (TTL 캐싱)"""
        cached_ts, cached_map = self._all_container_name_cache
        now = time.time()
        if cached_map and now - cached_ts <= self._container_cache_ttl:
            return cached_map

        async with self.async_session_local() as db:
            stmt = select(
                TbKnowledgeContainers.container_id,
                TbKnowledgeContainers.container_name
            ).where(TbKnowledgeContainers.is_active == True)
            result = await db.execute(stmt)
            mapping = {row.container_id: row.container_name for row in result.fetchall()}

        self._all_container_name_cache = (now, mapping)
        return mapping

    async def _get_container_friendly_names(self, container_ids: List[str]) -> List[str]:
        """컨테이너 ID들을 사용자 친화적인 이름으로 변환"""
        try:
            logger.info(f"컨테이너 친화적 이름 변환 시작: {container_ids}")
            container_details = await self._get_container_details(container_ids)
            friendly_names = []
            
            for container_id in container_ids:
                if container_id in container_details:
                    friendly_name = container_details[container_id]["container_name"]
                    friendly_names.append(friendly_name)
                    logger.info(f"컨테이너 {container_id} -> {friendly_name}")
                else:
                    # 데이터베이스에서 찾지 못한 경우 컨테이너 ID 그대로 사용
                    friendly_names.append(container_id)
                    logger.warning(f"컨테이너 {container_id}의 친화적 이름을 찾지 못해 ID를 그대로 사용")
            
            logger.info(f"컨테이너 친화적 이름 변환 완료: {friendly_names}")
            return friendly_names
            
        except Exception as e:
            logger.error(f"컨테이너 친화적 이름 변환 실패: {str(e)}")
            # 실패시 컨테이너 ID들을 그대로 반환
            return container_ids

    def _build_container_path(self, container_id: str, all_containers: Dict[str, Dict]) -> str:
        """컨테이너 ID로부터 전체 경로 구성"""
        try:
            path_parts = []
            current_id = container_id
            
            while current_id and current_id in all_containers:
                container = all_containers[current_id]
                path_parts.insert(0, current_id)  # 앞쪽에 삽입
                current_id = container.get("parent_container_id")
                
                # 무한 루프 방지
                if len(path_parts) > 10:
                    break
            
            return "/" + "/".join(path_parts)
            
        except Exception as e:
            logger.warning(f"컨테이너 경로 구성 실패: {e}")
            return f"/{container_id}"

    def _convert_path_to_display_names(self, org_path: str, all_containers: Dict[str, Dict]) -> str:
        """org_path를 사용자 친화적인 이름으로 변환"""
        try:
            if not org_path:
                return ""
                
            # org_path에서 컨테이너 ID들 추출 (예: /WJ_ROOT/WJ_CEO/WJ_HR)
            path_parts = [part for part in org_path.split("/") if part]
            display_parts = []
            
            for container_id in path_parts:
                if container_id in all_containers:
                    value = all_containers[container_id]
                    if isinstance(value, dict):
                        display_name = value.get("container_name", container_id)
                    else:
                        display_name = value
                    display_parts.append(display_name)
                else:
                    display_parts.append(container_id)
            
            return " > ".join(display_parts)
            
        except Exception as e:
            logger.warning(f"경로 표시명 변환 실패: {e}")
            return org_path

    def _get_container_icon(self, is_final: bool = True) -> str:
        """컨테이너 아이콘 반환"""
        if is_final:
            return "📂"  # 열린 폴더 아이콘 (최종 경로)
        else:
            return "📁"  # 닫힌 폴더 아이콘 (중간 경로)

    def _calculate_score_distribution(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """점수 분포 계산"""
        try:
            distribution = {"high": 0, "medium": 0, "low": 0}
            for result in results:
                score = result.get("similarity_score", 0.0)
                if score >= 0.8:
                    distribution["high"] += 1
                elif score >= 0.6:
                    distribution["medium"] += 1
                else:
                    distribution["low"] += 1
            return distribution
        except:
            return {"high": 0, "medium": 0, "low": 0}

    def _get_document_type(self, result: Dict[str, Any]) -> str:
        """파일 확장자 기반 문서 타입 반환"""
        try:
            # 기존 doc_type이 있고 'document'가 아니면 사용
            existing_type = result.get("document_type") or result.get("doc_type")
            if existing_type and existing_type != "document":
                return existing_type
            
            # 파일 경로나 이름에서 확장자 추출
            file_path = result.get("file_path") or result.get("path") or ""
            file_name = result.get("file_lgc_nm") or result.get("file_name") or ""
            
            # 확장자 기반 타입 매핑
            extension_map = {
                ".pdf": "PDF 문서",
                ".doc": "Word 문서", 
                ".docx": "Word 문서",
                ".xls": "Excel 문서",
                ".xlsx": "Excel 문서",
                ".ppt": "PowerPoint 문서",
                ".pptx": "PowerPoint 문서",
                ".txt": "텍스트 문서",
                ".hwp": "한글 문서",
                ".png": "이미지",
                ".jpg": "이미지",
                ".jpeg": "이미지",
                ".gif": "이미지",
                ".mp4": "동영상",
                ".avi": "동영상",
                ".zip": "압축 파일",
                ".rar": "압축 파일"
            }
            
            # 파일 경로에서 확장자 추출
            for ext, doc_type in extension_map.items():
                if file_path.lower().endswith(ext) or file_name.lower().endswith(ext):
                    return doc_type
            
            return "문서"  # 기본값
            
        except Exception as e:
            logger.warning(f"문서 타입 확인 실패: {e}")
            return "문서"

    def _calculate_similarity_percentage(self, similarity_score: float) -> float:
        """유사도 점수를 퍼센트로 변환"""
        try:
            if not similarity_score or math.isnan(similarity_score):
                return 0.0
            
            # 점수가 이미 퍼센트 형태(1보다 큰 값)인지 확인
            if similarity_score > 1.0:
                # 이미 퍼센트 형태인 경우 100을 초과하지 않도록 제한
                percentage = min(similarity_score, 100.0)
            else:
                # 0.0 ~ 1.0 범위의 점수를 0.0 ~ 100.0 범위로 변환
                percentage = similarity_score * 100.0
            
            # 소수점 첫째 자리까지만 표시
            return round(percentage, 1)
            
        except Exception as e:
            logger.warning(f"유사도 퍼센트 계산 실패: {e}")
            return 0.0
            return 0.0

    def _highlight_keywords(self, text: str, query: str, keywords: List[str] = None) -> str:
        """텍스트에서 검색 키워드를 하이라이트 처리"""
        try:
            if not text or not query:
                return text
            
            import re
            
            # 하이라이트할 키워드 목록 생성
            highlight_terms = set()
            
            # 1. 원본 쿼리 추가
            highlight_terms.add(query.strip().lower())
            
            # 2. 추가 키워드가 있으면 포함
            if keywords:
                for keyword in keywords:
                    if keyword and keyword.strip():
                        highlight_terms.add(keyword.strip().lower())
            
            # 3. 쿼리를 공백으로 분할한 개별 단어들 추가
            query_words = query.strip().split()
            for word in query_words:
                if len(word) >= 2:  # 2글자 이상만 하이라이트
                    highlight_terms.add(word.lower())
            
            # 4. 한국어 형태소 분석 결과가 있으면 활용
            try:
                morphemes = korean_nlp_service.extract_morphemes(query)
                for morpheme in morphemes:
                    if len(morpheme) >= 2:
                        highlight_terms.add(morpheme.lower())
            except:
                pass
            
            # 빈 문자열 제거
            highlight_terms = {term for term in highlight_terms if term}
            
            if not highlight_terms:
                return text
            
            # 정규식 패턴 생성 (대소문자 구분 안함)
            # 특수문자 이스케이프 처리
            escaped_terms = [re.escape(term) for term in highlight_terms]
            pattern = r'\b(' + '|'.join(escaped_terms) + r')\b'
            
            # 하이라이트 적용
            highlighted_text = re.sub(
                pattern, 
                r'<mark>\1</mark>', 
                text, 
                flags=re.IGNORECASE
            )
            
            return highlighted_text
            
        except Exception as e:
            logger.warning(f"키워드 하이라이트 처리 실패: {e}")
            return text

    def _normalize_similarity_score(self, score: float) -> float:
        """
        유사도 점수를 0.0-1.0 범위로 정규화
        
        Args:
            score: 원본 유사도 점수
            
        Returns:
            float: 0.0-1.0 범위로 정규화된 점수
        """
        try:
            # NaN 또는 None 체크
            if score is None or math.isnan(score):
                return 0.0
            
            # 이미 0.0-1.0 범위인 경우 그대로 반환
            if 0.0 <= score <= 1.0:
                return score
            
            # 1.0을 초과하는 경우 1.0으로 클램핑
            if score > 1.0:
                logger.warning(f"유사도 점수가 1.0을 초과합니다: {score:.3f} -> 1.0으로 조정")
                return 1.0
            
            # 0.0 미만인 경우 0.0으로 클램핑
            if score < 0.0:
                logger.warning(f"유사도 점수가 0.0 미만입니다: {score:.3f} -> 0.0으로 조정")
                return 0.0
                
            return score
            
        except Exception as e:
            logger.error(f"유사도 점수 정규화 오류: {e}")
            return 0.0

    def _build_container_path_with_icons(self, container_path: str) -> str:
        """
        컨테이너 경로에 아이콘을 추가하여 사용자 친화적인 경로 문자열 생성
        
        Args:
            container_path: 원본 컨테이너 경로 (예: "/웅진/CEO직속/인사전략팀")
            
        Returns:
            str: 아이콘이 포함된 경로 (예: "📁 웅진 📁 CEO직속 📂 인사전략팀")
        """
        try:
            if not container_path:
                return "📂 경로 없음"
            
            # 경로를 '/' 또는 ' > ' 기준으로 분할
            if '/' in container_path:
                path_parts = [part.strip() for part in container_path.split('/') if part.strip()]
            elif ' > ' in container_path:
                path_parts = [part.strip() for part in container_path.split(' > ') if part.strip()]
            else:
                # 단일 컨테이너인 경우
                return f"📂 {container_path}"
            
            if not path_parts:
                return "📂 경로 없음"
            
            # 각 경로 부분에 아이콘 추가
            icon_path_parts = []
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    # 마지막 (현재) 컨테이너는 열린 폴더 아이콘
                    icon_path_parts.append(f"📂 {part}")
                else:
                    # 상위 컨테이너들은 닫힌 폴더 아이콘
                    icon_path_parts.append(f"📁 {part}")
            
            return " ".join(icon_path_parts)
            
        except Exception as e:
            logger.error(f"컨테이너 경로 아이콘 구성 오류: {e}")
            return f"📂 {container_path}" if container_path else "📂 경로 없음"

    def _convert_path_ids_to_names(self, org_path: str, container_id_to_name: Dict[str, str]) -> str:
        """
        컨테이너 ID 경로를 사용자 친화적인 이름 경로로 변환
        
        Args:
            org_path: 컨테이너 ID 경로 (예: "/WJ_ROOT/WJ_CEO/WJ_HR")
            container_id_to_name: 컨테이너 ID -> 이름 매핑
            
        Returns:
            str: 변환된 경로 (예: "웅진/CEO직속/인사전략팀")
        """
        try:
            if not org_path:
                return ""
                
            # 경로 구분자로 분할
            if org_path.startswith('/'):
                org_path = org_path[1:]  # 맨 앞의 '/' 제거
                
            path_parts = [part.strip() for part in org_path.split('/') if part.strip()]
            
            # 각 컨테이너 ID를 이름으로 변환
            friendly_parts = []
            for container_id in path_parts:
                container_name = container_id_to_name.get(container_id, container_id)
                # 이모지 제거 (이미 이름에 포함되어 있으면)
                if container_name.startswith(('🏢', '📁', '📂')):
                    # 이모지와 공백 제거하여 순수한 이름만 추출
                    clean_name = container_name[2:].strip()
                    friendly_parts.append(clean_name)
                else:
                    friendly_parts.append(container_name)
            
            return "/".join(friendly_parts)
            
        except Exception as e:
            logger.error(f"컨테이너 경로 변환 오류: {e}")
            return org_path or ""
    
    def _apply_quality_filter(self, results: List[Dict[str, Any]], processed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        검색 결과 품질 필터링
        키워드 매치가 없고 벡터 점수만 있는 경우 관련성 검증
        
        개선사항:
        - 이미지/표 청크는 키워드 필터 완화 (내용 텍스트가 제한적)
        - 유사도 임계값 기반으로 필터링
        """
        try:
            query_keywords = processed_query.get("keywords", [])
            # 원문/정규화 텍스트 기반 부분일치 확인에 사용
            query_text = (processed_query.get("normalized_text") or processed_query.get("original_text") or "").lower()
            
            if not query_keywords and not query_text:
                return results
            
            filtered_results = []
            
            for result in results:
                search_methods = result.get("search_methods", [])
                modality = result.get("modality", "text")
                
                # 키워드나 전문검색 매치가 있으면 통과
                if any(method in search_methods for method in ["keyword", "fulltext"]):
                    filtered_results.append(result)
                    continue
                
                # 벡터 검색만 있는 경우 추가 검증
                if "vector" in search_methods:
                    # 정규화/가중치 이전의 원시 유사도 사용
                    similarity = result.get("raw_vector_similarity", result.get("similarity_score", 0.0))
                    
                    # 이미지/표 청크는 키워드 필터 완화 (유사도 임계값만 체크)
                    if modality in ['image', 'table']:
                        # 이미지/표는 유사도 임계값 이상이면 통과
                        if similarity >= self.similarity_threshold:
                            filtered_results.append(result)
                            logger.debug(f"이미지/표 청크 포함: {result.get('file_name', 'unknown')} (modality={modality}, score={similarity:.3f})")
                        else:
                            logger.info(f"품질 필터링으로 제외: {result.get('file_name', 'unknown')} (modality={modality}, 낮은 유사도(raw)={similarity:.3f})")
                        continue
                    
                    # 텍스트 청크는 기존 로직 유지
                    # 매우 높은 유사도 점수 (0.8 이상)면 통과
                    if similarity >= 0.8:
                        filtered_results.append(result)
                        continue
                    
                    # 제목이나 내용에서 쿼리 키워드 부분 일치 확인
                    content = result.get("content", "").lower()
                    title = result.get("file_name", "").lower()
                    
                    # 쿼리 키워드와 부분적으로라도 일치하는지 확인
                    has_partial_match = False
                    for keyword in query_keywords:
                        keyword_lower = keyword.lower()
                        if keyword_lower in content or keyword_lower in title:
                            has_partial_match = True
                            break
                    
                    # 쿼리 텍스트 전체와도 확인
                    if not has_partial_match and query_text:
                        if query_text in content or query_text in title:
                            has_partial_match = True
                    
                    if has_partial_match:
                        filtered_results.append(result)
                    else:
                        logger.info(f"품질 필터링으로 제외: {result.get('file_name', 'unknown')} (키워드 불일치, raw={similarity:.3f})")
                
            logger.info(f"품질 필터링: {len(results)}개 -> {len(filtered_results)}개")
            return filtered_results
            
        except Exception as e:
            logger.error(f"품질 필터링 오류: {e}")
            return results
    
    async def multimodal_search(
        self,
        query: str,
        user_emp_no: str,
        image_query: Optional[str] = None,  # Base64 인코딩된 이미지 (data:image/png;base64,...)
        container_ids: Optional[List[str]] = None,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        멀티모달 검색 수행 (텍스트 + 이미지)
        
        Args:
            query: 텍스트 검색 쿼리
            user_emp_no: 사용자 사원번호
            image_query: Base64 인코딩된 이미지 (data:image/png;base64,iVBOR...)
            container_ids: 검색할 컨테이너 ID 리스트
            max_results: 최대 결과 개수
            filters: 추가 필터 조건
        
        Returns:
            멀티모달 검색 결과 딕셔너리
        """
        try:
            import base64
            start_time = datetime.now()
            
            # Base64 이미지 디코딩
            image_bytes: Optional[bytes] = None
            if image_query:
                try:
                    # data:image/png;base64,iVBOR... → iVBOR... → bytes
                    if ',' in image_query:
                        image_query = image_query.split(',', 1)[1]
                    image_bytes = base64.b64decode(image_query)
                    logger.info(f"[MULTIMODAL_SEARCH] 이미지 디코딩 완료: {len(image_bytes)} bytes")
                except Exception as e:
                    logger.error(f"[MULTIMODAL_SEARCH] 이미지 디코딩 실패: {e}")
                    image_bytes = None
            
            # 1. 텍스트 검색 수행 (하이브리드) - 텍스트 쿼리가 있을 때만
            text_results: Dict[str, Any] = {"results": [], "total_count": 0, "search_metadata": {}, "filters_applied": {}}
            if query:
                text_results = await self.hybrid_search(
                    query=query,
                    user_emp_no=user_emp_no,
                    container_ids=container_ids,
                    max_results=max_results,
                    search_type="hybrid",
                    filters=filters
                )
            
            # 2. 이미지가 있는 문서 우선순위 부여
            if filters and filters.get('prefer_images', False):
                # 이미지가 있는 문서에 가중치 추가
                for result in text_results.get('results', []):
                    if result.get('has_images', False):
                        result['similarity_score'] = result.get('similarity_score', 0.0) * 1.2
                
                # 재정렬
                text_results['results'] = sorted(
                    text_results['results'],
                    key=lambda x: x.get('similarity_score', 0.0),
                    reverse=True
                )[:max_results]
            
            # 3. 이미지 검색 (CLIP 멀티모달)
            image_results: List[Dict[str, Any]] = []
            image_embedding: List[float] = []
            image_threshold = 0.8  # 유사도 임계값 (0.8 = 80% 유사도 이상만 반환)
            if filters and isinstance(filters.get("image_similarity_threshold"), (int, float)):
                candidate = float(filters["image_similarity_threshold"])  # type: ignore[index]
                if 0.0 <= candidate <= 1.0:
                    image_threshold = candidate

            if image_bytes:  # 디코딩된 바이트 데이터 사용
                logger.info(
                    "[MULTIMODAL_SEARCH] 이미지 검색 요청 수신 - payload %d bytes",
                    len(image_bytes)
                )

                image_embedding = await self._generate_image_embedding(image_bytes)
                if image_embedding:
                    image_results = await self._search_by_image_embedding(
                        image_embedding=image_embedding,
                        user_emp_no=user_emp_no,
                        container_ids=container_ids,
                        max_results=max_results,
                        similarity_threshold=image_threshold
                    )
                else:
                    logger.warning("[MULTIMODAL_SEARCH] 이미지 임베딩 생성 실패로 이미지 검색을 생략합니다.")
            
            # 4. 이미지 검색 결과 포맷팅 (container_path 추가)
            if image_results:
                # 컨테이너 정보 조회를 위한 container_id 수집
                container_ids_to_fetch = [
                    str(r["container_id"]) for r in image_results 
                    if r.get("container_id")
                ]
                
                # 컨테이너 정보 조회
                container_details = {}
                if container_ids_to_fetch:
                    container_details = await self._get_container_details(container_ids_to_fetch)
                
                # 각 이미지 결과에 container_path 추가
                for result in image_results:
                    container_id = result.get("container_id")
                    if container_id and container_id in container_details:
                        detail = container_details[container_id]
                        container_path = detail.get("full_path", "")
                        if not container_path:
                            container_path = detail.get("container_name", "")
                        
                        container_path_with_icons = self._build_container_path_with_icons(container_path)
                        
                        result["container_name"] = detail.get("container_name", "알 수 없음")
                        result["container_path"] = container_path_with_icons
                        result["container_icon"] = "📂"
                    else:
                        result["container_path"] = "📂 경로 없음"
                        result["container_icon"] = "📂"
                
                logger.info(f"[MULTIMODAL_SEARCH] 이미지 결과 포맷팅 완료: {len(image_results)}개")
            
            # 5. 결과 통합
            search_time = (datetime.now() - start_time).total_seconds()
            
            text_result_list = text_results.get('results') or []
            text_result_count = text_results.get('total_count', len(text_result_list))
            total_results = text_result_count + len(image_results)

            multimodal_results = {
                "success": True,
                "query": query or "[이미지 검색]",
                "has_image_query": image_bytes is not None,
                "total_results": total_results,
                "results": text_result_list,
                "image_results": image_results,  # 이미지 검색 결과 (청크 단위)
                "search_metadata": {
                    **text_results.get('search_metadata', {}),
                    "multimodal_enabled": True,
                    "image_search_ready": image_embedding_service is not None,
                    "search_time_seconds": search_time,
                    "image_results_count": len(image_results),
                    "image_similarity_threshold": image_threshold,
                    "image_embedding_dimension": len(image_embedding) if image_embedding else None
                },
                "filters_applied": {
                    **text_results.get('filters_applied', {}),
                    "prefer_images": filters.get('prefer_images', False) if filters else False,
                    "image_query_provided": image_bytes is not None,
                    "image_similarity_threshold": image_threshold
                }
            }
            
            logger.info(f"[MULTIMODAL_SEARCH] 검색 완료 - "
                       f"쿼리: '{query or '[이미지]'}', "
                       f"텍스트 결과: {text_result_count}개, 이미지 결과: {len(image_results)}개, "
                       f"시간: {search_time:.3f}초")
            
            return multimodal_results
            
        except Exception as e:
            logger.error(f"[MULTIMODAL_SEARCH] 검색 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "total_results": 0,
                "results": []
            }
    
    async def _generate_image_embedding(self, image_data: bytes) -> List[float]:
        """
        이미지 임베딩 생성 (CLIP 기반)

        Args:
            image_data: 이미지 바이트 데이터

        Returns:
            이미지 임베딩 벡터
        """
        if not image_data:
            logger.warning("[MULTIMODAL_SEARCH] 빈 이미지 데이터로 임베딩을 요청했습니다.")
            return []

        if image_embedding_service is None:
            logger.warning("[MULTIMODAL_SEARCH] CLIP 임베딩 서비스가 활성화되지 않았습니다.")
            return []

        try:
            embedding = await image_embedding_service.generate_image_embedding(image_bytes=image_data)
            if not embedding:
                logger.warning("[MULTIMODAL_SEARCH] 이미지 임베딩 생성 결과가 비어 있습니다.")
                return []

            # numpy.ndarray 등 리스트 호환 타입을 안전하게 변환
            embedding_values = embedding if isinstance(embedding, list) else list(embedding)
            embedding_list = [float(x) for x in embedding_values]
            target_dim = getattr(settings, "clip_embedding_dimension", 512) or len(embedding_list)

            # CLIP 임베딩은 512차원 기준으로 패딩/자르기 처리
            if len(embedding_list) < target_dim:
                embedding_list.extend([0.0] * (target_dim - len(embedding_list)))
            elif len(embedding_list) > target_dim:
                embedding_list = embedding_list[:target_dim]

            logger.info(f"[MULTIMODAL_SEARCH] 이미지 임베딩 생성 완료 ({len(embedding_list)}d)")
            return embedding_list

        except Exception as exc:  # pragma: no cover - 외부 서비스 오류 방어
            logger.error(f"[MULTIMODAL_SEARCH] 이미지 임베딩 생성 실패: {exc}")
            return []
    
    async def search_by_image_embedding(
        self,
        image_embedding: List[float],
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_results: int = 10,
        similarity_threshold: float = 0.25
    ) -> List[Dict[str, Any]]:
        """외부 서비스에서 호출 가능한 공개 메서드 래퍼."""
        return await self._search_by_image_embedding(
            image_embedding=image_embedding,
            user_emp_no=user_emp_no,
            container_ids=container_ids,
            max_results=max_results,
            similarity_threshold=similarity_threshold
        )

    async def _search_by_image_embedding(
        self,
        image_embedding: List[float],
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_results: int = 10,
        similarity_threshold: float = 0.25
    ) -> List[Dict[str, Any]]:
        """
        이미지 임베딩으로 doc_embedding.clip_vector 검색 수행

        Args:
            image_embedding: CLIP 이미지 임베딩 벡터
            user_emp_no: 사용자 사원번호
            container_ids: 필터링할 컨테이너 목록 (None이면 권한 내 전체)
            max_results: 반환할 최대 결과 수
            similarity_threshold: 최소 유사도 (0.0~1.0)

        Returns:
            이미지 검색 결과 리스트 (청크 단위)
        """
        if not image_embedding:
            logger.warning("[MULTIMODAL_SEARCH] 이미지 임베딩이 비어 있어 검색을 건너뜁니다.")
            return []

        accessible_containers = await self._get_accessible_containers(user_emp_no, container_ids)
        if not accessible_containers:
            logger.info("[MULTIMODAL_SEARCH] 접근 가능한 컨테이너가 없어 이미지 검색 결과가 없습니다.")
            return []

        # 벡터를 pgvector 포맷으로 직렬화
        safe_embedding = [float(x) for x in image_embedding]
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in safe_embedding) + "]"

        # 컨테이너 필터 문자열 구성 (단순 텍스트 필터이므로 기본적인 escaping 수행)
        container_filters = [cid.replace("'", "''") for cid in accessible_containers if cid]
        container_condition = ""
        if container_filters:
            joined = "','".join(container_filters)
            container_condition = f" AND fbf.knowledge_container_id IN ('{joined}')"

        query_sql = f"""
            SELECT
                de.embedding_id AS embedding_id,
                de.clip_vector <=> '{vector_literal}'::vector AS distance,
                1 - (de.clip_vector <=> '{vector_literal}'::vector) / 2 AS cosine_similarity,
                dc.chunk_id,
                dc.chunk_index,
                dc.content_text,
                dc.token_count,
                COALESCE(dc.modality, 'image') AS modality,
                fbf.file_bss_info_sno,
                fbf.file_lgc_nm AS file_name,
                fbf.path AS file_path,
                fbf.knowledge_container_id,
                kc.container_name,
                kc.org_path AS container_org_path
            FROM doc_embedding de
            JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
            JOIN tb_file_bss_info fbf ON dc.file_bss_info_sno = fbf.file_bss_info_sno
            LEFT JOIN tb_knowledge_containers kc ON fbf.knowledge_container_id = kc.container_id
            WHERE de.clip_vector IS NOT NULL
              AND fbf.del_yn = 'N'
              {container_condition}
            ORDER BY de.clip_vector <=> '{vector_literal}'::vector ASC
            LIMIT {max_results * 2}
        """

        try:
            async with self.async_session_local() as db:
                result = await db.execute(text(query_sql))
                rows = result.fetchall()

            image_results: List[Dict[str, Any]] = []
            similarity_scores = []  # 디버깅용
            for row in rows:
                # cosine distance를 similarity로 변환
                cosine_similarity = float(getattr(row, "cosine_similarity", 0.0))
                similarity_scores.append(cosine_similarity)  # 디버깅용

                if cosine_similarity < similarity_threshold:
                    continue

                distance_value = getattr(row, "distance", None)
                distance = float(distance_value) if distance_value is not None else None
                preview_text = row.content_text or "[이미지] 관련 텍스트가 없습니다."
                
                # 컨테이너 정보 구성
                container_id = row.knowledge_container_id
                container_name = getattr(row, "container_name", None) or container_id
                container_org_path = getattr(row, "container_org_path", None)
                container_path = container_org_path or container_name
                
                # 파일명 정보 (문서 제목)
                file_name = row.file_name or "알 수 없음"
                title = file_name  # 문서명을 제목으로 사용

                image_results.append({
                    "chunk_id": row.chunk_id,
                    "embedding_id": row.embedding_id,
                    "file_id": row.file_bss_info_sno,
                    "chunk_index": row.chunk_index,
                    "content": preview_text,
                    "token_count": row.token_count,
                    "modality": row.modality,
                    "file_name": file_name,
                    "title": title,  # 검색 결과 표시용 제목
                    "file_path": row.file_path,
                    "container_id": container_id,
                    "container_name": container_name,
                    "container_path": container_path,
                    "similarity_score": cosine_similarity,
                    "distance": distance,
                    "clip_score": cosine_similarity,
                    "has_images": True,
                    "image_count": 1,
                    "metadata": {
                        "file_name": file_name,
                        "document_id": str(row.file_bss_info_sno),
                        "chunk_index": row.chunk_index,
                    }
                })

            # 디버깅: 모든 유사도 점수 로그
            if similarity_scores:
                logger.info(
                    "[MULTIMODAL_SEARCH] 유사도 점수 분포 - "
                    f"최대: {max(similarity_scores):.4f}, "
                    f"최소: {min(similarity_scores):.4f}, "
                    f"평균: {sum(similarity_scores)/len(similarity_scores):.4f}, "
                    f"총 {len(similarity_scores)}건 비교"
                )

            logger.info(
                "[MULTIMODAL_SEARCH] 이미지 벡터 검색 완료 - 결과 %d건 (임계값 %.2f)",
                len(image_results),
                similarity_threshold
            )

            return image_results[:max_results]

        except Exception as exc:  # pragma: no cover - DB 오류 등 방어
            logger.error(f"[MULTIMODAL_SEARCH] 이미지 벡터 검색 실패: {exc}")
            return []


# 싱글톤 인스턴스
search_service = SearchService()

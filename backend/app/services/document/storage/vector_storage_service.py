"""
🔮 벡터 저장 서비스 - vs_ 중심 통합 아키텍처 (실제 스키마 맞춤)
================================================

최적 통합 방안 1: vs_ 중심 활용 ⭐ [권장]

🎯 역할 분담:
  Primary Vector Store: vs_doc_contents_index
    - 모든 문서 청크 벡터 저장 (vector(1024))
    - 빠른 벡터 검색 최적화
    - knowledge_container_id 컬럼으로 권한 관리
  
  Metadata & Reference: tb_document_chunks  
    - 상세 메타데이터 (페이지, 섹션) (vector(768))
    - 참조 추적 ("3페이지 2번째 단락")
    - 권한 및 컨테이너 정보
  
  Hybrid Search: tb_search_documents
    - 키워드 + 벡터 조합 검색
    - tsvector 최적화
    - 실시간 검색 성능

PostgreSQL + pgvector 활용, 실제 스키마 반영
"""

import json
import logging
from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime

# Database imports
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session_local
from app.core.config import settings
from app.services.core.korean_nlp_service import korean_nlp_service

logger = logging.getLogger(__name__)

class VectorStorageService:
    """
    🔮 vs_ 중심 통합 벡터 저장 서비스 (실제 스키마 맞춤)
    ===================================================
    
    Primary: vs_doc_contents_index (벡터 검색 - vector(1024))
    Metadata: tb_document_chunks (참조 추적 - vector(768))  
    Hybrid: tb_search_documents (키워드+벡터)
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStorageService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """벡터 저장 서비스 초기화"""
        # 이미 초기화되었으면 스킵
        if VectorStorageService._initialized:
            return
            
        # 동적 차원 설정 - 현재 설정된 임베딩 모델에 따라 결정
        self.embedding_dimension = settings.get_current_embedding_dimension()
        logger.info(f"🔮 vs_ 중심 벡터 저장 서비스 초기화 완료 - 임베딩 차원: {self.embedding_dimension}")
        logger.info(f"현재 임베딩 모델: {settings.get_current_embedding_model()}")
        print(f"✅ VectorStorageService 초기화 성공 - vs_ 중심 아키텍처, 차원: {self.embedding_dimension}")
        print(f"📊 현재 임베딩 모델: {settings.get_current_embedding_model()}")
        
        # 초기화 완료 플래그 설정
        VectorStorageService._initialized = True
    
    def get_dynamic_embedding_dimension(self) -> int:
        """실시간으로 현재 임베딩 차원 반환"""
        return settings.get_current_embedding_dimension()
    
    async def store_processed_document(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        preprocessed_data: Dict[str, Any],
        nlp_results: List[Dict[str, Any]],
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        🔮 vs_ 중심 통합 문서 벡터 저장 (실제 스키마 반영)
        
        Args:
            session: DB 세션
            file_bss_info_sno: 파일 기본 정보 ID
            container_id: 지식 컨테이너 ID (권한 관리용)
            preprocessed_data: 문서 전처리 결과
            nlp_results: 청크별 NLP 분석 결과
            user_info: 업로드 사용자 정보 (권한 설정용)
        """
        try:
            # 권한 정보 확인
            access_permissions = await self._get_container_permissions(
                session, container_id, user_info
            )
            
            result = {
                "success": False,  # 기본값을 False로 설정
                "primary_vectors": 0,      # vs_doc_contents_index 저장 수
                "metadata_chunks": 0,      # tb_document_chunks 저장 수
                "hybrid_records": 0,       # tb_search_documents 저장 수
                "errors": [],
                "container_id": container_id,
                "permissions": access_permissions,
                "architecture": "vs_primary"
            }
            
            chunks = preprocessed_data.get('chunks', [])
            
            for i, (chunk, nlp_result) in enumerate(zip(chunks, nlp_results)):
                try:
                    # 1단계: Primary Vector Store (vs_doc_contents_index)
                    primary_result = await self._store_primary_vector(
                        session, file_bss_info_sno, container_id, chunk, nlp_result, i
                    )
                    
                    if primary_result["success"]:
                        result["primary_vectors"] += 1
                    else:
                        result["errors"].append(f"청크 {i} 주요 벡터 저장 실패: {primary_result.get('error')}")
                    
                    # 2단계: Metadata & Reference (tb_document_chunks)
                    metadata_result = await self._store_metadata_chunk(
                        session, file_bss_info_sno, container_id, chunk, nlp_result, i
                    )
                    
                    if metadata_result["success"]:
                        result["metadata_chunks"] += 1
                    else:
                        result["errors"].append(f"청크 {i} 메타데이터 저장 실패: {metadata_result.get('error')}")
                    
                    # 3단계: Hybrid Search (tb_search_documents) - 선택적
                    hybrid_result = await self._store_hybrid_search(
                        session, file_bss_info_sno, container_id, chunk, nlp_result, i
                    )
                    
                    if hybrid_result["success"]:
                        result["hybrid_records"] += 1
                    else:
                        result["errors"].append(f"청크 {i} 하이브리드 저장 실패: {hybrid_result.get('error')}")
                    
                except Exception as e:
                    error_msg = f"청크 {i} 통합 저장 실패: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)
            
            # 파일 메타데이터 업데이트
            await self._update_file_metadata_integrated(
                session, file_bss_info_sno, len(chunks), preprocessed_data, access_permissions, result
            )
            
            # 성공 여부 판정: 주요 벡터 저장 성공 기준
            result["success"] = result["primary_vectors"] > 0
            
            logger.info(f"🔮 vs_ 중심 벡터 저장 완료 - 컨테이너: {container_id}, "
                       f"주요벡터: {result['primary_vectors']}, 메타데이터: {result['metadata_chunks']}, "
                       f"하이브리드: {result['hybrid_records']}")
            
            return result
            
        except Exception as e:
            logger.error(f"vs_ 중심 벡터 저장 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "primary_vectors": 0,
                "metadata_chunks": 0,
                "hybrid_records": 0,
                "container_id": container_id
            }
    
    async def _store_primary_vector(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int
    ) -> Dict[str, Any]:
        """vs_doc_contents_index에 주요 벡터 저장 (실제 스키마 맞춤)"""
        try:
            # 임베딩 벡터 준비 (동적 차원)
            embedding = nlp_result.get('embedding')
            current_dim = self.get_dynamic_embedding_dimension()
            
            # 차원 자동 조정 (필요시 스마트 축소 적용)
            if embedding and len(embedding) != current_dim:
                logger.info(f"임베딩 차원 조정: {len(embedding)} → {current_dim}")
                embedding = settings.apply_smart_dimension_reduction(embedding, current_dim)
            
            if not embedding or len(embedding) != current_dim:
                logger.warning(f"벡터 차원 문제: 예상 {current_dim}, 실제 {len(embedding) if embedding else 0}")
                return {"success": False, "error": "벡터 차원 문제"}
            
            embedding_str = f"[{','.join(map(str, embedding))}]"
            
            # vs_doc_contents_index 실제 스키마에 맞춘 INSERT
            query = text("""
                INSERT INTO vs_doc_contents_index (
                    id, file_bss_info_sno, knowledge_container_id, chunk_index,
                    chunk_text, embedding, chunk_size, metadata_json, created_date
                ) VALUES (
                    :id, :file_sno, :container_id, :chunk_index,
                    :chunk_text, CAST(:embedding AS vector), :chunk_size, :metadata_json, NOW()
                )
            """)
            
            # ID 생성 (파일SNO_청크인덱스_컨테이너ID 조합)
            doc_id = f"{file_bss_info_sno}_{chunk_index}_{container_id}"
            
            # 메타데이터 준비
            metadata = {
                "container_id": container_id,
                "chunk_type": chunk.get('chunk_type', 'content'),
                "page_number": chunk.get('page_number', 1),  # 페이지 번호 추가
                "keywords": nlp_result.get('korean_keywords', []),
                "named_entities": nlp_result.get('named_entities', [])
            }
            
            await session.execute(query, {
                "id": doc_id,
                "file_sno": file_bss_info_sno,
                "container_id": container_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk.get('content', ''),
                "embedding": embedding_str,
                "chunk_size": chunk.get('size', len(chunk.get('content', ''))),
                "metadata_json": json.dumps(metadata, ensure_ascii=False)
            })
            
            return {"success": True, "doc_id": doc_id}
            
        except Exception as e:
            logger.error(f"주요 벡터 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _store_metadata_chunk(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int
    ) -> Dict[str, Any]:
        """tb_document_chunks에 메타데이터 저장 (실제 스키마 맞춤)"""
        try:
            # 임베딩 벡터 정규화 (설정된 차원에 맞춤)
            original_embedding = nlp_result.get('embedding')
            embedding_str = None
            
            if original_embedding:
                expected_dimension = settings.vector_dimension
                if len(original_embedding) == expected_dimension:
                    # 차원이 일치하는 경우 그대로 사용
                    embedding_str = f"[{','.join(map(str, original_embedding))}]"
                elif len(original_embedding) > expected_dimension:
                    # 축소: 앞쪽 차원만 사용
                    reduced_embedding = original_embedding[:expected_dimension]
                    embedding_str = f"[{','.join(map(str, reduced_embedding))}]"
                    logger.debug(f"임베딩 차원 축소: {len(original_embedding)} -> {expected_dimension}")
                else:
                    # 확장: 0으로 패딩
                    padded_embedding = original_embedding + [0.0] * (expected_dimension - len(original_embedding))
                    embedding_str = f"[{','.join(map(str, padded_embedding))}]"
                    logger.debug(f"임베딩 차원 확장: {len(original_embedding)} -> {expected_dimension}")
            else:
                logger.warning(f"메타데이터 저장: 임베딩 벡터가 없음")
            
            # 참조 정보 생성 ("3페이지 2번째 단락" 형태)
            page_number = chunk.get('page_number', 1)
            paragraph_index = chunk_index + 1
            reference_info = f"{page_number}페이지 {paragraph_index}번째 단락"
            
            # tb_document_chunks 실제 스키마에 맞춘 INSERT
            if embedding_str:
                query = text("""
                    INSERT INTO tb_document_chunks (
                        "FILE_BSS_INFO_SNO", "CHUNK_INDEX", "CHUNK_TEXT", 
                        "CHUNK_SIZE", "CHUNK_EMBEDDING", "PAGE_NUMBER",
                        "SECTION_TITLE", "KNOWLEDGE_CONTAINER_ID",
                        "CREATED_BY", "LAST_MODIFIED_BY"
                    ) VALUES (
                        :file_sno, :chunk_index, :chunk_text,
                        :chunk_size, CAST(:embedding AS vector), :page_number,
                        :section_title, :container_id,
                        :created_by, :modified_by
                    )
                """)
                
                await session.execute(query, {
                    "file_sno": file_bss_info_sno,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk.get('content', ''),
                    "chunk_size": chunk.get('size', len(chunk.get('content', ''))),
                    "embedding": embedding_str,
                    "page_number": page_number,
                    "section_title": chunk.get('chunk_type', 'content'),
                    "container_id": container_id,
                    "created_by": "system",
                    "modified_by": "system"
                })
            else:
                # 벡터 없이 메타데이터만 저장
                query = text("""
                    INSERT INTO tb_document_chunks (
                        "FILE_BSS_INFO_SNO", "CHUNK_INDEX", "CHUNK_TEXT", 
                        "CHUNK_SIZE", "PAGE_NUMBER", "SECTION_TITLE", 
                        "KNOWLEDGE_CONTAINER_ID", "CREATED_BY", "LAST_MODIFIED_BY"
                    ) VALUES (
                        :file_sno, :chunk_index, :chunk_text,
                        :chunk_size, :page_number, :section_title,
                        :container_id, :created_by, :modified_by
                    )
                """)
                
                await session.execute(query, {
                    "file_sno": file_bss_info_sno,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk.get('content', ''),
                    "chunk_size": chunk.get('size', len(chunk.get('content', ''))),
                    "page_number": page_number,
                    "section_title": chunk.get('chunk_type', 'content'),
                    "container_id": container_id,
                    "created_by": "system",
                    "modified_by": "system"
                })
            
            return {"success": True, "reference": reference_info}
            
        except Exception as e:
            logger.error(f"메타데이터 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _store_hybrid_search(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int
    ) -> Dict[str, Any]:
        """tb_search_documents에 하이브리드 검색용 레코드 저장"""
        try:
            # 임베딩 벡터 준비
            embedding = nlp_result.get('embedding')
            if embedding and len(embedding) == self.embedding_dimension:
                embedding_str = f"[{','.join(map(str, embedding))}]"
            else:
                embedding_str = None
                if embedding:
                    logger.warning(f"하이브리드 검색 벡터 차원 불일치: 예상 {self.embedding_dimension}, 실제 {len(embedding)}")
            
            # 키워드, 고유명사 배열 준비
            keywords = nlp_result.get('korean_keywords', [])
            proper_nouns = nlp_result.get('named_entities', [])
            corp_names = []  # 추후 회사명 추출 로직 추가
            
            # PostgreSQL 배열 형태로 변환
            keywords_array = '{' + ','.join([f'"{k}"' for k in keywords if k]) + '}'
            proper_nouns_array = '{' + ','.join([f'"{p}"' for p in proper_nouns if p]) + '}'
            corp_names_array = '{}'
            
            content = chunk.get('content', '')
            
            # tb_search_documents에 저장
            if embedding_str:
                query = text("""
                    INSERT INTO tb_search_documents (
                        file_bss_info_sno, knowledge_container_id, chunk_index,
                        content, keywords, proper_nouns, corp_names,
                        content_vector, keyword_tsvector, content_tsvector
                    ) VALUES (
                        :file_sno, :container_id, :chunk_index,
                        :content, CAST(:keywords AS text[]), CAST(:proper_nouns AS text[]), CAST(:corp_names AS text[]),
                        CAST(:embedding AS vector), 
                        to_tsvector('korean', :content),
                        to_tsvector('korean', :content)
                    )
                """)
                
                await session.execute(query, {
                    "file_sno": file_bss_info_sno,
                    "container_id": container_id,
                    "chunk_index": chunk_index,
                    "content": content,
                    "keywords": keywords_array,
                    "proper_nouns": proper_nouns_array,
                    "corp_names": corp_names_array,
                    "embedding": embedding_str
                })
            else:
                # 벡터 없이 키워드 검색만 저장
                query = text("""
                    INSERT INTO tb_search_documents (
                        file_bss_info_sno, knowledge_container_id, chunk_index,
                        content, keywords, proper_nouns, corp_names,
                        keyword_tsvector, content_tsvector
                    ) VALUES (
                        :file_sno, :container_id, :chunk_index,
                        :content, CAST(:keywords AS text[]), CAST(:proper_nouns AS text[]), CAST(:corp_names AS text[]),
                        to_tsvector('korean', :content),
                        to_tsvector('korean', :content)
                    )
                """)
                
                await session.execute(query, {
                    "file_sno": file_bss_info_sno,
                    "container_id": container_id,
                    "chunk_index": chunk_index,
                    "content": content,
                    "keywords": keywords_array,
                    "proper_nouns": proper_nouns_array,
                    "corp_names": corp_names_array
                })
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"하이브리드 검색 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _get_container_permissions(
        self,
        session: AsyncSession,
        container_id: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """지식 컨테이너 권한 정보 조회"""
        try:
            # 기본 권한 정보
            permissions = {
                "container_id": container_id,
                "read_permission": True,
                "write_permission": True,
                "access_level": "full",
                "user_role": "system"
            }
            
            # 사용자 정보가 있으면 실제 권한 조회
            if user_info and user_info.get("user_id"):
                # TODO: 실제 권한 테이블에서 조회
                # 현재는 기본 권한 반환
                permissions.update({
                    "user_id": user_info.get("user_id"),
                    "user_role": user_info.get("role", "user")
                })
            
            return permissions
            
        except Exception as e:
            logger.error(f"컨테이너 권한 조회 실패: {str(e)}")
            return {
                "container_id": container_id,
                "read_permission": False,
                "write_permission": False,
                "access_level": "none",
                "error": str(e)
            }
    
    async def _update_file_metadata_integrated(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        chunk_count: int,
        preprocessed_data: Dict[str, Any],
        permissions: Dict[str, Any],
        storage_result: Dict[str, Any]
    ):
        """통합 파일 메타데이터 업데이트"""
        try:
            # 통합 메타데이터 준비
            integrated_metadata = {
                "vectorized": True,
                "architecture": "vs_primary",
                "chunk_count": chunk_count,
                "vector_dimension": self.embedding_dimension,
                "storage_summary": {
                    "primary_vectors": storage_result.get("primary_vectors", 0),
                    "metadata_chunks": storage_result.get("metadata_chunks", 0),
                    "hybrid_records": storage_result.get("hybrid_records", 0)
                },
                "access_permissions": permissions,
                "container_id": permissions.get("container_id"),
                "processing_status": "completed",
                "last_vectorized": datetime.now().isoformat()
            }
            
            # tb_file_bss_info 업데이트
            query = text("""
                UPDATE tb_file_bss_info 
                SET chunk_count = :chunk_count,
                    korean_metadata = COALESCE(korean_metadata, '{}') || CAST(:metadata AS json)
                WHERE file_bss_info_sno = :file_sno
            """)
            
            await session.execute(query, {
                "chunk_count": chunk_count,
                "metadata": json.dumps(integrated_metadata, ensure_ascii=False),
                "file_sno": file_bss_info_sno
            })
            
        except Exception as e:
            logger.error(f"통합 메타데이터 업데이트 실패: {str(e)}")

    async def search_hybrid(
        self,
        session: AsyncSession,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        container_ids: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        🔮 vs_ 중심 하이브리드 검색 (vs_doc_contents_index + tb_search_documents)
        
        Args:
            query_text: 검색 쿼리 텍스트
            query_embedding: 쿼리 임베딩 벡터
            container_ids: 검색할 컨테이너 ID 목록
            limit: 결과 개수 제한
            similarity_threshold: 유사도 임계값
        """
        try:
            # vs_doc_contents_index 기반 벡터 검색
            vector_results = []
            if query_embedding:
                vector_results = await self._search_primary_vectors(
                    session, query_embedding, container_ids, limit, similarity_threshold
                )
            
            # tb_search_documents 기반 키워드 검색
            keyword_results = await self._search_keywords(
                session, query_text, container_ids, limit
            )
            
            # 결과 통합 및 스코어링
            integrated_results = self._integrate_search_results(
                vector_results, keyword_results, limit
            )
            
            logger.info(f"vs_ 중심 하이브리드 검색 완료: 벡터 {len(vector_results)}개, 키워드 {len(keyword_results)}개, 통합 {len(integrated_results)}개")
            return integrated_results
            
        except Exception as e:
            logger.error(f"vs_ 중심 하이브리드 검색 실패: {str(e)}")
            return []

    async def _search_primary_vectors(
        self,
        session: AsyncSession,
        query_embedding: List[float],
        container_ids: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """vs_doc_contents_index에서 벡터 검색"""
        try:
            conditions = []
            params = {"query_embedding": f"[{','.join(map(str, query_embedding))}]", "limit": limit, "threshold": similarity_threshold}
            
            if container_ids:
                conditions.append("knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = container_ids
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = text(f"""
                SELECT 
                    id, file_bss_info_sno, knowledge_container_id, chunk_index,
                    chunk_text, metadata_json,
                    1 - (embedding <-> :query_embedding::vector) as similarity
                FROM vs_doc_contents_index
                WHERE {where_clause}
                    AND embedding <-> :query_embedding::vector < :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "chunk_index": row[3],
                    "content": row[4],
                    "metadata": json.loads(row[5]) if row[5] else {},
                    "similarity": float(row[6]),
                    "source": "vector"
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"주요 벡터 검색 실패: {str(e)}")
            return []

    async def _search_keywords(
        self,
        session: AsyncSession,
        query_text: str,
        container_ids: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """tb_search_documents에서 키워드 검색"""
        try:
            conditions = []
            params = {"query_text": query_text, "limit": limit}
            
            if container_ids:
                conditions.append("knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = container_ids
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = text(f"""
                SELECT 
                    search_doc_id, file_bss_info_sno, knowledge_container_id, chunk_index,
                    content, keywords, proper_nouns,
                    ts_rank(content_tsvector, plainto_tsquery('korean', :query_text)) as keyword_score
                FROM tb_search_documents
                WHERE {where_clause}
                    AND content_tsvector @@ plainto_tsquery('korean', :query_text)
                ORDER BY keyword_score DESC
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "chunk_index": row[3],
                    "content": row[4],
                    "keywords": row[5] if row[5] else [],
                    "proper_nouns": row[6] if row[6] else [],
                    "keyword_score": float(row[7]),
                    "source": "keyword"
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"키워드 검색 실패: {str(e)}")
            return []

    def _integrate_search_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """벡터 검색과 키워드 검색 결과 통합"""
        try:
            # 결과 통합 (file_bss_info_sno + chunk_index 기준)
            result_map = {}
            
            # 벡터 검색 결과 추가 (가중치 0.7)
            for result in vector_results:
                key = f"{result['file_bss_info_sno']}_{result['chunk_index']}"
                result["vector_score"] = result.get("similarity", 0) * 0.7
                result["keyword_score"] = 0
                result["hybrid_score"] = result["vector_score"]
                result_map[key] = result
            
            # 키워드 검색 결과 추가/병합 (가중치 0.3)
            for result in keyword_results:
                key = f"{result['file_bss_info_sno']}_{result['chunk_index']}"
                keyword_weighted = result.get("keyword_score", 0) * 0.3
                
                if key in result_map:
                    # 기존 결과에 키워드 점수 추가
                    result_map[key]["keyword_score"] = keyword_weighted
                    result_map[key]["hybrid_score"] += keyword_weighted
                    # 키워드 정보 병합
                    if "keywords" in result:
                        result_map[key]["keywords"] = result["keywords"]
                    if "proper_nouns" in result:
                        result_map[key]["proper_nouns"] = result["proper_nouns"]
                else:
                    # 키워드만 검색된 결과
                    result["vector_score"] = 0
                    result["keyword_score"] = keyword_weighted
                    result["hybrid_score"] = keyword_weighted
                    result_map[key] = result
            
            # 하이브리드 점수로 정렬
            integrated_results = sorted(
                result_map.values(),
                key=lambda x: x["hybrid_score"],
                reverse=True
            )
            
            return integrated_results[:limit]
            
        except Exception as e:
            logger.error(f"검색 결과 통합 실패: {str(e)}")
            return []


# 싱글톤 인스턴스 생성
vector_storage_service = VectorStorageService()

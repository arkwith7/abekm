"""
🔮 벡터 저장 서비스 - vs_ 중심 통합 아키텍처
================================================

최적 통합 방안 1: vs_ 중심 활용 ⭐ [권장]

🎯 역할 분담:
  Primary Vector Store: vs_doc_contents_index
    - 모든 문서 청크 벡터 저장
    - 빠른 벡터 검색 최적화
    - 권한 정보는 file_bss_info_sno로 연결
  
  Metadata & Reference: tb_document_chunks  
    - 상세 메타데이터 (페이지, 섹션)
    - 참조 추적 ("3페이지 2번째 단락")
    - 권한 및 컨테이너 정보
  
  Hybrid Search: tb_search_documents
    - 키워드 + 벡터 조합 검색
    - tsvector 최적화
    - 실시간 검색 성능

PostgreSQL + pgvector 활용
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
from app.services.korean_nlp_service import korean_nlp_service

logger = logging.getLogger(__name__)

class VectorStorageServiceIntegrated:
    """
    🔮 vs_ 중심 통합 벡터 저장 서비스
    ===============================
    
    Primary: vs_doc_contents_index (벡터 검색)
    Metadata: tb_document_chunks (참조 추적)  
    Hybrid: tb_search_documents (키워드+벡터)
    """
    
    def __init__(self):
        """벡터 저장 서비스 초기화"""
        self.embedding_dimension = settings.bedrock_embedding_dimension
        logger.info(f"🔮 vs_ 중심 벡터 저장 서비스 초기화 완료 - 임베딩 차원: {self.embedding_dimension}")
        print(f"✅ VectorStorageServiceIntegrated 초기화 성공 - vs_ 중심 아키텍처, 차원: {self.embedding_dimension}")
    
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
        🔮 vs_ 중심 문서 벡터 저장 통합 프로세스
        
        1. vs_doc_contents_index: 주요 벡터 저장
        2. tb_document_chunks: 메타데이터 및 참조 정보
        3. tb_search_documents: 하이브리드 검색용
        """
        try:
            # 권한 정보 확인
            access_permissions = await self._get_container_permissions(
                session, container_id, user_info
            )
            
            result = {
                "success": False,
                "primary_vectors": 0,     # vs_doc_contents_index 저장 수
                "metadata_chunks": 0,     # tb_document_chunks 저장 수
                "hybrid_records": 0,      # tb_search_documents 저장 수
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
                        session, file_bss_info_sno, container_id, chunk, nlp_result, i, access_permissions
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
                "container_id": container_id,
                "architecture": "vs_primary"
            }
    
    # ==============================================
    # 🔮 Primary Vector Store: vs_doc_contents_index
    # ==============================================
    
    async def _store_primary_vector(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int,
        permissions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """🔮 Primary Vector Store: vs_doc_contents_index에 주요 벡터 저장"""
        try:
            # 권한 확인
            if not permissions.get("write_permission", False):
                return {
                    "success": False,
                    "error": f"컨테이너 {container_id}에 대한 쓰기 권한이 없습니다."
                }
            
            # 임베딩 벡터 준비
            embedding = nlp_result.get('embedding')
            vector_dimension = self.embedding_dimension
            
            if not embedding or len(embedding) != vector_dimension:
                return {
                    "success": False,
                    "error": f"벡터 차원 불일치: 예상 {vector_dimension}, 실제 {len(embedding) if embedding else 0}"
                }
            
            embedding_str = f"[{','.join(map(str, embedding))}]"
            content = chunk.get('content', '')
            
            # vs_doc_contents_index에 저장
            query = text("""
                INSERT INTO vs_doc_contents_index (
                    file_bss_info_sno, knowledge_container_id, chunk_index,
                    content, content_vector, created_at, updated_at
                ) VALUES (
                    :file_sno, :container_id, :chunk_index,
                    :content, CAST(:embedding AS vector), NOW(), NOW()
                )
            """)
            
            await session.execute(query, {
                "file_sno": file_bss_info_sno,
                "container_id": container_id,
                "chunk_index": chunk_index,
                "content": content,
                "embedding": embedding_str
            })
            
            logger.debug(f"🔮 주요 벡터 저장 성공 - 파일: {file_bss_info_sno}, 청크: {chunk_index}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"주요 벡터 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}

    # ==============================================
    # 🔮 Metadata & Reference: tb_document_chunks
    # ==============================================

    async def _store_metadata_chunk(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int
    ) -> Dict[str, Any]:
        """🔮 Metadata & Reference: tb_document_chunks에 상세 메타데이터 저장"""
        try:
            # 참조 정보 추출
            page_info = chunk.get('page_number', 0)
            section_info = chunk.get('section_title', 'content')
            paragraph_info = chunk.get('paragraph_index', chunk_index)
            
            # 참조 문자열 생성 ("3페이지 2번째 단락")
            reference_info = f"{page_info}페이지 {paragraph_info}번째 단락" if page_info > 0 else f"{paragraph_info}번째 단락"
            
            # 키워드 정보
            keywords = nlp_result.get('korean_keywords', [])
            entities = nlp_result.get('named_entities', [])
            
            # tb_document_chunks에 저장 (벡터 없이 메타데이터만)
            query = text("""
                INSERT INTO tb_document_chunks (
                    "FILE_BSS_INFO_SNO", "CHUNK_INDEX", "CHUNK_TEXT", 
                    "CHUNK_SIZE", "SECTION_TITLE", "PAGE_NUMBER",
                    "PARAGRAPH_INDEX", "REFERENCE_INFO", "KEYWORDS",
                    "NAMED_ENTITIES", "KNOWLEDGE_CONTAINER_ID",
                    "CREATED_BY", "LAST_MODIFIED_BY"
                ) VALUES (
                    :file_sno, :chunk_index, :chunk_text,
                    :chunk_size, :section_title, :page_number,
                    :paragraph_index, :reference_info, :keywords,
                    :entities, :container_id,
                    :created_by, :modified_by
                )
            """)
            
            await session.execute(query, {
                "file_sno": file_bss_info_sno,
                "chunk_index": chunk_index,
                "chunk_text": chunk.get('content', ''),
                "chunk_size": chunk.get('size', len(chunk.get('content', ''))),
                "section_title": section_info,
                "page_number": page_info,
                "paragraph_index": paragraph_info,
                "reference_info": reference_info,
                "keywords": json.dumps(keywords),
                "entities": json.dumps(entities),
                "container_id": container_id,
                "created_by": "system",
                "modified_by": "system"
            })
            
            logger.debug(f"🔮 메타데이터 저장 성공 - 파일: {file_bss_info_sno}, 참조: {reference_info}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"메타데이터 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}

    # ==============================================
    # 🔮 Hybrid Search: tb_search_documents
    # ==============================================

    async def _store_hybrid_search(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        chunk: Dict[str, Any],
        nlp_result: Dict[str, Any],
        chunk_index: int
    ) -> Dict[str, Any]:
        """🔮 Hybrid Search: tb_search_documents에 하이브리드 검색용 저장"""
        try:
            # 임베딩 벡터 준비 (하이브리드 검색용)
            embedding = nlp_result.get('embedding')
            vector_dimension = self.embedding_dimension
            
            if embedding and len(embedding) == vector_dimension:
                embedding_str = f"[{','.join(map(str, embedding))}]"
            else:
                embedding_str = None
                if embedding:
                    logger.warning(f"하이브리드 검색 벡터 차원 불일치: 예상 {vector_dimension}, 실제 {len(embedding)}")
            
            # 키워드, 고유명사, 회사명 배열 준비
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
            
            logger.debug(f"🔮 하이브리드 검색 저장 성공 - 파일: {file_bss_info_sno}, 청크: {chunk_index}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"하이브리드 검색 저장 실패: {str(e)}")
            return {"success": False, "error": str(e)}

    # ==============================================
    # 🔮 검색 메서드들
    # ==============================================

    async def search_vector_primary(
        self,
        session: AsyncSession,
        query_embedding: List[float],
        container_ids: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """🔮 Primary Vector Search: vs_doc_contents_index 기반 고속 벡터 검색"""
        try:
            conditions = []
            params = {"query_embedding": f"[{','.join(map(str, query_embedding))}]", 
                     "threshold": similarity_threshold, "limit": limit}
            
            # 컨테이너 필터
            if container_ids:
                conditions.append("knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = container_ids
            
            # 유사도 임계값 필터
            conditions.append("content_vector <-> :query_embedding::vector < :threshold")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = text(f"""
                SELECT 
                    vs_doc_id,
                    file_bss_info_sno,
                    knowledge_container_id,
                    chunk_index,
                    content,
                    1 - (content_vector <-> :query_embedding::vector) as similarity,
                    created_at
                FROM vs_doc_contents_index
                WHERE {where_clause}
                ORDER BY content_vector <-> :query_embedding::vector
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            search_results = []
            for row in rows:
                search_results.append({
                    "vs_doc_id": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "chunk_index": row[3],
                    "content": row[4],
                    "similarity": float(row[5]),
                    "created_at": row[6],
                    "search_type": "vector_primary"
                })
            
            logger.info(f"🔮 주요 벡터 검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"주요 벡터 검색 실패: {str(e)}")
            return []

    async def search_with_reference(
        self,
        session: AsyncSession,
        query_text: str,
        container_ids: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """🔮 Reference Search: tb_document_chunks 기반 참조 정보 포함 검색"""
        try:
            conditions = []
            params = {"query_text": f"%{query_text}%", "limit": limit}
            
            # 컨테이너 필터
            if container_ids:
                conditions.append("\"KNOWLEDGE_CONTAINER_ID\" = ANY(:container_ids)")
                params["container_ids"] = container_ids
            
            # 텍스트 검색 조건
            conditions.append("\"CHUNK_TEXT\" ILIKE :query_text")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = text(f"""
                SELECT 
                    "CHUNK_SNO",
                    "FILE_BSS_INFO_SNO",
                    "KNOWLEDGE_CONTAINER_ID",
                    "CHUNK_INDEX",
                    "CHUNK_TEXT",
                    "SECTION_TITLE",
                    "PAGE_NUMBER",
                    "PARAGRAPH_INDEX",
                    "REFERENCE_INFO",
                    "KEYWORDS",
                    "NAMED_ENTITIES"
                FROM tb_document_chunks
                WHERE {where_clause}
                ORDER BY "CHUNK_INDEX"
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            search_results = []
            for row in rows:
                keywords = json.loads(row[9]) if row[9] else []
                entities = json.loads(row[10]) if row[10] else []
                
                search_results.append({
                    "chunk_sno": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "chunk_index": row[3],
                    "content": row[4],
                    "section_title": row[5],
                    "page_number": row[6],
                    "paragraph_index": row[7],
                    "reference_info": row[8],  # "3페이지 2번째 단락"
                    "keywords": keywords,
                    "named_entities": entities,
                    "search_type": "reference"
                })
            
            logger.info(f"🔮 참조 검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"참조 검색 실패: {str(e)}")
            return []

    async def search_hybrid(
        self,
        session: AsyncSession,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        container_ids: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """🔮 하이브리드 검색 (키워드 + 벡터 유사도) - tb_search_documents 활용"""
        try:
            # 키워드 검색과 벡터 검색을 결합한 쿼리
            conditions = []
            params = {"query_text": query_text, "limit": limit}
            
            # 컨테이너 필터
            if container_ids:
                conditions.append("knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = container_ids
            
            # 벡터 유사도 검색 추가
            vector_similarity_clause = "0"
            if query_embedding:
                embedding_str = f"[{','.join(map(str, query_embedding))}]"
                params["query_embedding"] = embedding_str
                params["threshold"] = similarity_threshold
                
                vector_similarity_clause = """
                    CASE 
                        WHEN content_vector IS NOT NULL
                        THEN 1 - (content_vector <-> :query_embedding::vector)
                        ELSE 0
                    END
                """
                
                conditions.append("content_vector <-> :query_embedding::vector < :threshold")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 하이브리드 스코어링 쿼리
            query = text(f"""
                SELECT 
                    search_doc_id,
                    file_bss_info_sno,
                    knowledge_container_id,
                    chunk_index,
                    content,
                    keywords,
                    proper_nouns,
                    -- 키워드 매칭 점수
                    ts_rank(content_tsvector, plainto_tsquery('korean', :query_text)) as keyword_score,
                    -- 벡터 유사도 점수
                    {vector_similarity_clause} as vector_similarity,
                    -- 하이브리드 점수 (키워드 30% + 벡터 70%)
                    (ts_rank(content_tsvector, plainto_tsquery('korean', :query_text)) * 0.3 +
                     {vector_similarity_clause} * 0.7) as hybrid_score
                FROM tb_search_documents
                WHERE {where_clause}
                ORDER BY hybrid_score DESC, keyword_score DESC
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            # 결과 포맷팅
            search_results = []
            for row in rows:
                search_results.append({
                    "search_doc_id": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "chunk_index": row[3],
                    "content": row[4],
                    "keywords": row[5] if row[5] else [],
                    "proper_nouns": row[6] if row[6] else [],
                    "keyword_score": float(row[7]) if row[7] else 0.0,
                    "vector_similarity": float(row[8]) if row[8] else 0.0,
                    "hybrid_score": float(row[9]) if row[9] else 0.0,
                    "search_type": "hybrid"
                })
            
            logger.info(f"🔮 하이브리드 검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {str(e)}")
            return []

    # ==============================================
    # 🔮 권한 관리 및 메타데이터 업데이트
    # ==============================================
    
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
        """🔮 통합 아키텍처 파일 메타데이터 업데이트"""
        try:
            # 권한 확인
            if not permissions.get("write_permission", False):
                logger.warning(f"파일 {file_bss_info_sno} 메타데이터 업데이트 권한 없음")
                return
            
            # 통합 메타데이터 생성
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
                "permissions": permissions,
                "container_id": permissions.get("container_id"),
                "processing_status": "completed",
                "last_vectorized": datetime.now().isoformat()
            }
            
            query = text("""
                UPDATE tb_file_bss_info 
                SET chunk_count = :chunk_count,
                    korean_metadata = COALESCE(korean_metadata, '{}') || CAST(:metadata AS json)
                WHERE file_bss_info_sno = :file_sno
            """)
            
            await session.execute(query, {
                "chunk_count": chunk_count,
                "metadata": json.dumps(integrated_metadata),
                "file_sno": file_bss_info_sno
            })
            
            logger.info(f"🔮 통합 메타데이터 업데이트 완료 - 파일: {file_bss_info_sno}")
            
        except Exception as e:
            logger.error(f"통합 메타데이터 업데이트 실패: {str(e)}")


# 통합 싱글톤 인스턴스 생성
vector_storage_service_integrated = VectorStorageServiceIntegrated()

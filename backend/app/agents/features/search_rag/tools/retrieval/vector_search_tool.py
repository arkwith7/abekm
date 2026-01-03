"""
Vector Search Tool - 벡터 유사도 검색 전용 도구
pgvector를 사용한 의미 기반 검색만 수행
"""
import asyncio
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.core.contracts import (
    SearchToolResult, SearchChunk, ToolMetrics
)
from app.services.core.embedding_service import embedding_service


class VectorSearchTool(BaseTool):
    """
    벡터 유사도 검색 도구
    
    책임:
    - 질의 임베딩 생성
    - pgvector <=> 연산으로 후보 검색
    - 유사도 threshold 필터링
    
    책임 없음:
    - 키워드 검색 (KeywordSearchTool)
    - 재랭킹 (RerankTool)
    - 중복 제거 (DeduplicateTool)
    - 컨텍스트 구성 (ContextBuilderTool)
    """
    name: str = "vector_search"
    description: str = """벡터 유사도 검색을 수행합니다. 질의의 의미를 임베딩으로 변환 후 
pgvector로 유사한 문서 청크를 찾습니다. 사실 확인 질문이나 의미 기반 검색에 적합합니다."""
    version: str = "1.0.0"
    
    async def _arun(
        self,
        query: str,
        db_session: AsyncSession,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 20,
        similarity_threshold: float = 0.2,  # 0.25 → 0.2로 낮춤 (일반 RAG adaptive 0.25와 유사)
        container_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        user_emp_no: Optional[str] = None,
        **kwargs
    ) -> SearchToolResult:
        """
        벡터 검색 실행
        
        Args:
            query: 검색 질의
            db_session: DB 세션
            query_embedding: 질의 임베딩 (None이면 자동 생성)
            top_k: 반환할 최대 결과 수
            similarity_threshold: 유사도 임계값 (0.0~1.0)
            container_ids: 검색 대상 컨테이너 ID 목록
            document_ids: 검색 대상 문서 ID 목록
            user_emp_no: 사용자 사번 (권한 확인용)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            # 1) 임베딩 생성 (제공되지 않은 경우)
            if query_embedding is None:
                embedding_start = datetime.utcnow()
                query_embedding = await embedding_service.get_embedding(query)
                embedding_ms = (datetime.utcnow() - embedding_start).total_seconds() * 1000
                logger.info(f"🔍 [VectorSearch] 임베딩 생성: {embedding_ms:.1f}ms")
            
            if not query_embedding:
                return SearchToolResult(
                    success=False,
                    data=[],
                    total_found=0,
                    filtered_count=0,
                    search_params={},
                    metrics=ToolMetrics(latency_ms=0, provider="internal", trace_id=trace_id),
                    errors=["임베딩 생성 실패"],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            # 2) SQL 쿼리 구성
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # 기본 쿼리
            # 3) 기본 쿼리
            sql_parts = [
                """
                SELECT 
                    dc.chunk_id,
                    dc.file_bss_info_sno as file_id,
                    dc.content_text as content,
                    dc.chunk_index,
                    dc.token_count,
                    1 - (de.vector <=> :embedding) as similarity_score,
                    fbi.file_lgc_nm as file_name,
                    fbi.path as file_path,
                    fbi.file_extsn as file_ext
                FROM doc_embedding de
                INNER JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
                LEFT JOIN tb_file_bss_info fbi ON dc.file_bss_info_sno = fbi.file_bss_info_sno
                WHERE de.modality = 'text'
                AND fbi.del_yn = 'N'
                """
            ]
            
            params: Dict[str, Any] = {"embedding": embedding_str}
            
            # 컨테이너 ID 필터
            if container_ids:
                # container_ids를 문자열 리스트로 변환 (knowledge_container_id는 String(50))
                normalized_container_ids = [str(c) for c in container_ids]
                sql_parts.append("AND fbi.knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = normalized_container_ids
            
            if document_ids:
                # 문서 ID가 str/int 혼용 가능하므로 정규화
                normalized_doc_ids = [
                    int(d) if isinstance(d, str) and d.isdigit() else d 
                    for d in document_ids
                ]
                sql_parts.append("AND dc.file_bss_info_sno = ANY(:document_ids)")
                params["document_ids"] = normalized_doc_ids
            
            # 권한 확인 (user_emp_no 제공 시)
            if user_emp_no:
                sql_parts.append("""
                    AND fbi.knowledge_container_id IN (
                        SELECT DISTINCT up.container_id
                        FROM tb_user_permissions up
                        WHERE up.user_emp_no = :emp_no
                        AND up.is_active = true
                        AND (up.expires_date IS NULL OR up.expires_date > NOW())
                    )
                """)
                params["emp_no"] = user_emp_no
            
            # 4) 유사도 필터 및 정렬
            sql_parts.append("""
                AND (1 - (de.vector <=> :embedding)) >= :threshold
                ORDER BY de.vector <=> :embedding
                LIMIT :limit
            """)
            params["threshold"] = similarity_threshold
            params["limit"] = top_k
            
            # 5) 쿼리 실행
            full_query = " ".join(sql_parts)
            result = await db_session.execute(text(full_query), params)
            rows = result.fetchall()
            
            # 6) 결과 변환
            chunks = []
            for row in rows:
                chunk = SearchChunk(
                    chunk_id=str(row.chunk_id),
                    content=row.content or "",
                    score=float(row.similarity_score),
                    file_id=str(row.file_id),
                    match_type="vector",
                    metadata={
                        "chunk_index": row.chunk_index,
                        "token_count": row.token_count,
                        "file_name": row.file_name,
                        "file_path": row.file_path,
                        "file_ext": row.file_ext,
                        "search_method": "pgvector_cosine"
                    }
                )
                chunks.append(chunk)
            
            # 7) 메트릭 수집
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"✅ [VectorSearch] 완료: {len(chunks)}개 발견, "
                f"threshold={similarity_threshold}, latency={latency_ms:.1f}ms"
            )
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=len(chunks),
                search_params={
                    "query": query[:100],
                    "top_k": top_k,
                    "threshold": similarity_threshold,
                    "container_ids": container_ids,
                    "document_ids": document_ids
                },
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    cache_hit=False,
                    retries=0
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [VectorSearch] 실패: {e}", exc_info=True)
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    cache_hit=False,
                    retries=0
                ),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    def _run(self, **kwargs) -> SearchToolResult:
        """동기 실행 (폴백)"""
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError as e:
            logger.error(f"❌ [VectorSearch] 동기 실행 실패: {e}")
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={},
                metrics=ToolMetrics(latency_ms=0, provider="internal"),
                errors=["RuntimeError: use _arun in async context"],
                trace_id=str(uuid.uuid4()),
                tool_name=self.name,
                tool_version=self.version
            )
    
    def validate_input(self, **kwargs) -> bool:
        """입력 검증"""
        if "query" not in kwargs or not kwargs["query"]:
            return False
        if "db_session" not in kwargs:
            return False
        return True


# 전역 인스턴스
vector_search_tool = VectorSearchTool()

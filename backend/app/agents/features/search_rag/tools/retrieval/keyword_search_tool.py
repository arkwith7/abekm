"""
Keyword Search Tool - 키워드 매칭 검색 전용 도구
ILIKE/regex 기반 키워드 검색만 수행
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

from app.core.contracts import SearchToolResult, SearchChunk, ToolMetrics


class KeywordSearchTool(BaseTool):
    """
    키워드 매칭 검색 도구
    
    책임:
    - 키워드 추출 (제공되지 않은 경우 공백 기준 분리)
    - ILIKE 기반 부분 매칭
    - 매칭 빈도 기반 점수 계산
    
    책임 없음:
    - 형태소 분석 (호출자가 제공)
    - 벡터 검색
    - 재랭킹
    """
    name: str = "keyword_search"
    description: str = """키워드 매칭 검색을 수행합니다. 질의에서 추출한 키워드를 문서 내용과 
직접 매칭합니다. 고유명사, 특정 용어 검색에 적합합니다."""
    version: str = "1.0.0"
    
    async def _arun(
        self,
        query: str,
        db_session: AsyncSession,
        keywords: Optional[List[str]] = None,
        top_k: int = 20,
        container_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        user_emp_no: Optional[str] = None,
        case_sensitive: bool = False,
        **kwargs
    ) -> SearchToolResult:
        """
        키워드 검색 실행
        
        Args:
            query: 검색 질의
            db_session: DB 세션
            keywords: 검색할 키워드 목록 (None이면 자동 추출)
            top_k: 반환할 최대 결과 수
            container_ids: 검색 대상 컨테이너
            document_ids: 검색 대상 문서
            user_emp_no: 사용자 사번
            case_sensitive: 대소문자 구분 여부
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            # 1) 키워드 추출 (제공되지 않은 경우 단순 분리)
            if keywords is None:
                keywords = [w.strip() for w in query.split() if len(w.strip()) >= 2]
            
            if not keywords:
                return SearchToolResult(
                    success=False,
                    data=[],
                    total_found=0,
                    filtered_count=0,
                    metrics=ToolMetrics(latency_ms=0, provider="internal"),
                    errors=["키워드가 없습니다"],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            logger.info(f"🔍 [KeywordSearch] 키워드: {keywords}")
            
            # 최소 매칭 개수 설정 (키워드가 2개 이상이면 최소 2개, 아니면 1개)
            min_match_count = 2 if len(keywords) >= 2 else 1
            logger.info(f"   - 최소 매칭 조건: {min_match_count}개 이상")
            
            # 2) SQL 쿼리 구성 (ILIKE 기반)
            # 각 키워드에 대해 매칭 점수 계산
            keyword_conditions = []
            for i, kw in enumerate(keywords[:10]):  # 최대 10개 키워드
                if case_sensitive:
                    keyword_conditions.append(
                        f"(CASE WHEN dc.content_text LIKE :kw{i} THEN 1 ELSE 0 END)"
                    )
                else:
                    keyword_conditions.append(
                        f"(CASE WHEN LOWER(dc.content_text) LIKE LOWER(:kw{i}) THEN 1 ELSE 0 END)"
                    )
            
            match_score_expr = " + ".join(keyword_conditions)
            
            sql_parts = [
                f"""
                SELECT 
                    dc.chunk_id,
                    dc.file_bss_info_sno as file_id,
                    dc.content_text as content,
                    dc.chunk_index,
                    dc.token_count,
                    ({match_score_expr})::float / :total_keywords as similarity_score,
                    fbi.file_lgc_nm as file_name,
                    fbi.path as file_path,
                    fbi.file_extsn as file_ext
                FROM doc_chunk dc
                LEFT JOIN tb_file_bss_info fbi ON dc.file_bss_info_sno = fbi.file_bss_info_sno
                WHERE ({match_score_expr}) >= :min_match_count
                AND fbi.del_yn = 'N'
                """
            ]
            
            params: Dict[str, Any] = {
                "total_keywords": len(keywords),
                "min_match_count": min_match_count
            }
            for i, kw in enumerate(keywords[:10]):
                params[f"kw{i}"] = f"%{kw}%"
            
            # 3) 필터 조건
            if container_ids:
                # container_ids를 문자열 리스트로 변환 (knowledge_container_id는 String(50))
                normalized_container_ids = [str(c) for c in container_ids]
                sql_parts.append("AND fbi.knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = normalized_container_ids
            
            if document_ids:
                normalized_doc_ids = [
                    int(d) if isinstance(d, str) and d.isdigit() else d 
                    for d in document_ids
                ]
                sql_parts.append("AND dc.file_bss_info_sno = ANY(:document_ids)")
                params["document_ids"] = normalized_doc_ids
            
            # 권한 확인
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
            
            # 4) 정렬 및 제한
            sql_parts.append(f"""
                ORDER BY ({match_score_expr}) DESC, dc.chunk_index
                LIMIT :limit
            """)
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
                    file_id=str(row.file_id),
                    content=row.content or "",
                    score=float(row.similarity_score),
                    match_type="keyword",
                    metadata={
                        "chunk_index": row.chunk_index,
                        "token_count": row.token_count,
                        "file_name": row.file_name,
                        "file_path": row.file_path,
                        "file_ext": row.file_ext,
                        "matched_keywords": keywords,
                        "search_method": "ilike_matching"
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"✅ [KeywordSearch] 완료: {len(chunks)}개 발견, "
                f"keywords={len(keywords)}, latency={latency_ms:.1f}ms"
            )
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=len(chunks),
                search_params={
                    "query": query[:100],
                    "keywords": keywords,
                    "top_k": top_k,
                    "case_sensitive": case_sensitive
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
            logger.error(f"❌ [KeywordSearch] 실패: {e}", exc_info=True)
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal"
                ),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    def _run(self, **kwargs) -> SearchToolResult:
        """동기 실행"""
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={},
                metrics=ToolMetrics(latency_ms=0, provider="internal"),
                errors=["use _arun in async context"],
                trace_id=str(uuid.uuid4()),
                tool_name=self.name,
                tool_version=self.version
            )
    
    def validate_input(self, **kwargs) -> bool:
        """입력 검증"""
        return "query" in kwargs and "db_session" in kwargs


# 전역 인스턴스
keyword_search_tool = KeywordSearchTool()

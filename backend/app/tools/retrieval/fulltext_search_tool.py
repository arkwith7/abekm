"""
Fulltext Search Tool - PostgreSQL tsvector 전문검색 전용 도구
"""
import asyncio
import uuid
from typing import List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.tools.contracts import SearchToolResult, SearchChunk, ToolMetrics


class FulltextSearchTool(BaseTool):
    """
    전문검색 도구 (PostgreSQL tsvector)
    
    책임:
    - tsquery 생성 및 실행
    - ts_rank 기반 점수 계산
    
    책임 없음:
    - 키워드 추출 (호출자)
    - 벡터 검색
    """
    name: str = "fulltext_search"
    description: str = """PostgreSQL tsvector를 사용한 전문검색을 수행합니다. 
형태소 기반 검색으로 한국어/영어 모두 지원하며 TS 랭킹 점수를 반환합니다."""
    version: str = "1.0.0"
    
    async def _arun(
        self,
        query: str,
        db_session: AsyncSession,
        tsquery_str: Optional[str] = None,
        language: str = "korean",
        top_k: int = 20,
        container_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        user_emp_no: Optional[str] = None,
        **kwargs
    ) -> SearchToolResult:
        """
        전문검색 실행
        
        Args:
            query: 검색 질의
            db_session: DB 세션
            tsquery_str: tsquery 문자열 (None이면 자동 생성)
            language: 언어 설정 (korean/english)
            top_k: 반환할 최대 결과 수
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            # 1) tsquery 생성
            if tsquery_str is None:
                # 단순 공백 분리 후 OR 조합
                keywords = [w.strip() for w in query.split() if len(w.strip()) >= 2]
                if not keywords:
                    raise ValueError("키워드 없음")
                tsquery_str = " | ".join(keywords)
            
            logger.info(f"🔍 [FulltextSearch] tsquery: {tsquery_str}")
            
            # 2) SQL 쿼리
            config = "korean" if language == "korean" else "english"
            
            sql_parts = [
                f"""
                SELECT 
                    dc.chunk_id,
                    dc.file_bss_info_sno as file_id,
                    dc.content_text as content,
                    dc.chunk_index,
                    dc.token_count,
                    ts_rank(dc.content_tsvector, to_tsquery(:config, :tsquery)) as similarity_score,
                    fbi.file_lgc_nm as file_name,
                    fbi.path as file_path,
                    fbi.file_extsn as file_ext
                FROM doc_chunk dc
                LEFT JOIN tb_file_bss_info fbi ON dc.file_bss_info_sno = fbi.file_bss_info_sno
                WHERE dc.content_tsvector @@ to_tsquery(:config, :tsquery)
                AND fbi.del_yn = 'N'
                """
            ]
            
            params = {
                "config": config,
                "tsquery": tsquery_str
            }
            
            # 3) 필터
            if container_ids:
                # container_ids를 문자열 리스트로 변환 (knowledge_container_id는 String(50))
                normalized_container_ids = [str(c) for c in container_ids]
                sql_parts.append("AND fbi.knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = normalized_container_ids
            
            if document_ids:
                normalized = [int(d) if isinstance(d, str) and d.isdigit() else d for d in document_ids]
                sql_parts.append("AND dc.file_bss_info_sno = ANY(:document_ids)")
                params["document_ids"] = normalized
            
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
            
            sql_parts.append("""
                ORDER BY ts_rank(dc.content_tsvector, to_tsquery(:config, :tsquery)) DESC
                LIMIT :limit
            """)
            params["limit"] = top_k
            
            # 4) 실행
            full_query = " ".join(sql_parts)
            result = await db_session.execute(text(full_query), params)
            rows = result.fetchall()
            
            # 5) 변환
            chunks = []
            for row in rows:
                chunk = SearchChunk(
                    chunk_id=str(row.chunk_id),
                    file_id=str(row.file_id),
                    content=row.content or "",
                    score=float(row.similarity_score) if row.similarity_score else 0.0,
                    match_type="fulltext",
                    metadata={
                        "chunk_index": row.chunk_index,
                        "token_count": row.token_count,
                        "file_name": row.file_name,
                        "file_path": row.file_path,
                        "tsquery": tsquery_str,
                        "language": language
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✅ [FulltextSearch] 완료: {len(chunks)}개, latency={latency_ms:.1f}ms")
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=len(chunks),
                search_params={"tsquery": tsquery_str, "language": language, "top_k": top_k},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internal"),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [FulltextSearch] 실패: {e}", exc_info=True)
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internal"),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    def _run(self, **kwargs) -> SearchToolResult:
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError:
            return SearchToolResult(
                success=False, data=[], total_found=0, filtered_count=0,
                search_params={}, metrics=ToolMetrics(latency_ms=0, provider="internal"),
                errors=["use _arun"], trace_id=str(uuid.uuid4()),
                tool_name=self.name, tool_version=self.version
            )
    
    def validate_input(self, **kwargs) -> bool:
        return "query" in kwargs and "db_session" in kwargs


# 전역 인스턴스
fulltext_search_tool = FulltextSearchTool()

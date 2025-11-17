"""
Document Loader Tool - 문서 전체 로드 도구
요약, 분석 등을 위해 특정 문서의 모든 청크를 로드
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.tools.contracts import (
    SearchToolResult, SearchChunk, ToolMetrics
)


class DocumentLoaderTool(BaseTool):
    """
    문서 로더 도구
    
    책임:
    - 특정 문서(들)의 모든 청크를 페이지/청크 순서대로 로드
    - 요약, 전체 내용 확인 등에 사용
    - 검색 없이 직접 로드 (빠른 응답)
    
    사용 케이스:
    - 사용자가 문서를 선택하고 "요약해줘" 요청
    - 문서 전체 내용 확인
    - 특정 문서 기반 분석
    
    책임 없음:
    - 검색 (VectorSearchTool, KeywordSearchTool)
    - 재랭킹 (RerankTool)
    - 중복 제거 (DeduplicateTool)
    """
    name: str = "document_loader"
    description: str = """선택된 문서의 전체 내용을 로드합니다. 
요약, 분석, 내용 확인 등 문서 전체가 필요한 작업에 사용됩니다."""
    version: str = "1.0.0"
    
    async def _arun(
        self,
        document_ids: List[int],
        db_session: AsyncSession,
        max_chunks: int = 50,
        user_emp_no: Optional[str] = None,
        **kwargs
    ) -> SearchToolResult:
        """
        문서 로드 실행
        
        Args:
            document_ids: 로드할 문서 ID 리스트
            db_session: DB 세션
            max_chunks: 반환할 최대 청크 수 (토큰 제한 방지)
            user_emp_no: 사용자 사번 (권한 확인용)
        
        Returns:
            SearchToolResult: 로드된 청크 리스트
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            if not document_ids:
                return SearchToolResult(
                    success=False,
                    data=[],
                    total_found=0,
                    filtered_count=0,
                    search_params={"document_ids": []},
                    metrics=ToolMetrics(
                        latency_ms=0,
                        provider="internal",
                        trace_id=trace_id
                    ),
                    errors=["문서 ID가 제공되지 않음"],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            logger.info(f"📚 [DocumentLoader] 문서 로드 시작: {len(document_ids)}개 문서")
            
            # SQL 쿼리: 페이지 번호와 청크 인덱스 순서로 정렬
            sql = text("""
                SELECT 
                    c.id,
                    c.file_id,
                    c.chunk_text,
                    c.page_number,
                    c.chunk_index,
                    c.metadata,
                    c.token_count,
                    c.created_at,
                    f.file_name,
                    f.file_type,
                    f.container_id,
                    con.name as container_name
                FROM tb_document_chunks c
                JOIN tb_files f ON c.file_id = f.id
                LEFT JOIN tb_containers con ON f.container_id = con.id
                WHERE c.file_id = ANY(:document_ids)
                ORDER BY c.file_id, c.page_number, c.chunk_index
                LIMIT :max_chunks
            """)
            
            result = await db_session.execute(
                sql,
                {
                    "document_ids": document_ids,
                    "max_chunks": max_chunks
                }
            )
            rows = result.fetchall()
            
            if not rows:
                logger.warning(f"⚠️ [DocumentLoader] 청크 없음: document_ids={document_ids}")
                return SearchToolResult(
                    success=True,
                    data=[],
                    total_found=0,
                    filtered_count=0,
                    search_params={"document_ids": document_ids, "max_chunks": max_chunks},
                    metrics=ToolMetrics(
                        latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                        provider="internal",
                        items_returned=0,
                        trace_id=trace_id
                    ),
                    errors=[],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            # 청크 변환
            chunks = []
            for row in rows:
                chunk = SearchChunk(
                    chunk_id=str(row.id),
                    file_id=str(row.file_id),
                    content=row.chunk_text or "",
                    score=1.0,  # 로드는 검색이 아니므로 1.0
                    match_type="document_load",
                    container_id=str(row.container_id) if row.container_id else None,
                    metadata={
                        "file_name": row.file_name,
                        "file_type": row.file_type,
                        "container_name": row.container_name,
                        "page_number": row.page_number,
                        "chunk_index": row.chunk_index,
                        "token_count": row.token_count,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "match_reason": "직접 로드",
                        **(row.metadata or {})
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"✅ [DocumentLoader] 완료: {len(chunks)}개 청크, "
                f"documents={len(set(c.file_id for c in chunks))}, "
                f"latency={latency_ms:.1f}ms"
            )
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=0,
                search_params={
                    "document_ids": document_ids,
                    "max_chunks": max_chunks,
                    "user_emp_no": user_emp_no
                },
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = f"문서 로드 실패: {str(e)}"
            logger.error(f"❌ [DocumentLoader] {error_msg}")
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"document_ids": document_ids},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    trace_id=trace_id
                ),
                errors=[error_msg],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    def _run(self, *args, **kwargs):
        """동기 실행은 지원하지 않음"""
        raise NotImplementedError("DocumentLoaderTool은 비동기 실행만 지원합니다. _arun()을 사용하세요.")


# 전역 인스턴스
document_loader_tool = DocumentLoaderTool()

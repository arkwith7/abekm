"""
단위 테스트 - 개별 도구 검증
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools import (
    vector_search_tool,
    keyword_search_tool,
    fulltext_search_tool,
    deduplicate_tool,
    context_builder_tool
)
from app.tools.contracts import SearchChunk


@pytest.mark.asyncio
async def test_vector_search_tool(db_session: AsyncSession):
    """벡터 검색 도구 테스트"""
    result = await vector_search_tool._arun(
        query="딥러닝 논문",
        db_session=db_session,
        top_k=5,
        similarity_threshold=0.5
    )
    
    assert result.success
    assert isinstance(result.data, list)
    assert result.metrics.latency_ms > 0
    assert result.metrics.trace_id


@pytest.mark.asyncio
async def test_keyword_search_tool(db_session: AsyncSession):
    """키워드 검색 도구 테스트"""
    result = await keyword_search_tool._arun(
        query="트랜스포머 아키텍처",
        db_session=db_session,
        keywords=["트랜스포머", "아키텍처"],
        top_k=5
    )
    
    assert result.success
    assert isinstance(result.data, list)


@pytest.mark.asyncio
async def test_fulltext_search_tool(db_session: AsyncSession):
    """전문검색 도구 테스트"""
    result = await fulltext_search_tool._arun(
        query="자연어 처리",
        db_session=db_session,
        tsquery_str="자연어 | 처리",
        top_k=5
    )
    
    assert result.success
    assert isinstance(result.data, list)


@pytest.mark.asyncio
async def test_deduplicate_tool():
    """중복 제거 도구 테스트"""
    chunks = [
        SearchChunk(
            chunk_id="chunk_1",
            content="딥러닝은 머신러닝의 한 분야입니다.",
            score=0.95,
            metadata={"doc_id": "doc_1"}
        ),
        SearchChunk(
            chunk_id="chunk_2",
            content="딥러닝은 머신러닝의 한 분야입니다.",  # 동일
            score=0.90,
            metadata={"doc_id": "doc_1"}
        ),
        SearchChunk(
            chunk_id="chunk_3",
            content="강화학습은 보상을 최대화합니다.",
            score=0.85,
            metadata={"doc_id": "doc_2"}
        )
    ]
    
    result = await deduplicate_tool._arun(chunks=chunks)
    
    assert result.success
    assert len(result.data) == 2  # chunk_2 제거


@pytest.mark.asyncio
async def test_context_builder_tool():
    """컨텍스트 구성 도구 테스트"""
    chunks = [
        SearchChunk(
            chunk_id="chunk_1",
            content="A" * 100,
            score=0.95,
            metadata={"doc_id": "doc_1", "title": "Title 1"}
        ),
        SearchChunk(
            chunk_id="chunk_2",
            content="B" * 200,
            score=0.90,
            metadata={"doc_id": "doc_2", "title": "Title 2"}
        )
    ]
    
    result = await context_builder_tool._arun(
        chunks=chunks,
        max_tokens=500,
        include_metadata=True,
        format_style="citation"
    )
    
    assert result.success
    assert isinstance(result.data, str)
    assert result.total_tokens <= 500
    assert len(result.used_chunks) <= len(chunks)


@pytest.mark.asyncio
async def test_tool_error_handling(db_session: AsyncSession):
    """도구 에러 핸들링 테스트"""
    # 잘못된 입력
    result = await vector_search_tool._arun(
        query="",  # 빈 쿼리
        db_session=db_session,
        top_k=5
    )
    
    # 실패해도 ToolResult 반환
    assert isinstance(result.success, bool)
    if not result.success:
        assert len(result.errors) > 0

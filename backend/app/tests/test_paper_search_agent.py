"""
통합 테스트 - PaperSearchAgent 엔드투엔드
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents import paper_search_agent
from app.tools.contracts import AgentConstraints, AgentIntent


@pytest.mark.asyncio
async def test_paper_search_agent_factual_qa(db_session: AsyncSession):
    """사실 확인 질문 테스트"""
    query = "딥러닝이란 무엇인가?"
    
    result = await paper_search_agent.execute(
        query=query,
        db_session=db_session,
        constraints=AgentConstraints(max_chunks=10),
        context={"user_emp_no": "test_user"}
    )
    
    assert result.success
    assert result.answer
    assert result.intent == AgentIntent.FACTUAL_QA
    assert "vector_search" in result.strategy_used
    assert "deduplicate" in result.strategy_used
    assert len(result.steps) > 0
    assert result.metrics["total_latency_ms"] > 0


@pytest.mark.asyncio
async def test_paper_search_agent_keyword_search(db_session: AsyncSession):
    """키워드 검색 테스트"""
    query = "트랜스포머 논문 찾기"
    
    result = await paper_search_agent.execute(
        query=query,
        db_session=db_session,
        constraints=AgentConstraints(max_chunks=5)
    )
    
    assert result.success
    assert result.intent == AgentIntent.KEYWORD_SEARCH
    assert "keyword_search" in result.strategy_used
    assert "fulltext_search" in result.strategy_used


@pytest.mark.asyncio
async def test_paper_search_agent_comparison(db_session: AsyncSession):
    """비교 질문 테스트"""
    query = "BERT와 GPT의 차이점은?"
    
    result = await paper_search_agent.execute(
        query=query,
        db_session=db_session
    )
    
    assert result.success
    assert result.intent == AgentIntent.COMPARISON
    # 비교는 하이브리드 전략 사용
    assert "vector_search" in result.strategy_used
    assert "keyword_search" in result.strategy_used


@pytest.mark.asyncio
async def test_paper_search_agent_with_constraints(db_session: AsyncSession):
    """제약 조건 적용 테스트"""
    query = "강화학습 알고리즘"
    
    constraints = AgentConstraints(
        max_chunks=3,
        max_tokens=500,
        container_ids=["container_123"],
        similarity_threshold=0.7
    )
    
    result = await paper_search_agent.execute(
        query=query,
        db_session=db_session,
        constraints=constraints
    )
    
    assert result.success
    assert result.metrics["chunks_used"] <= 3
    assert result.metrics["total_tokens"] <= 500


@pytest.mark.asyncio
async def test_paper_search_agent_observability(db_session: AsyncSession):
    """관찰 가능성 테스트 (steps, metrics 추적)"""
    query = "자연어 처리 기법"
    
    result = await paper_search_agent.execute(
        query=query,
        db_session=db_session
    )
    
    # Steps 검증
    assert len(result.steps) > 0
    for step in result.steps:
        assert step.tool_name
        assert step.tool_input
        assert step.tool_output
        assert step.reasoning
        assert hasattr(step.tool_output, "metrics")
        assert step.tool_output.metrics.trace_id
    
    # Metrics 검증
    assert "total_latency_ms" in result.metrics
    assert "tools_used" in result.metrics
    assert "chunks_found" in result.metrics
    assert "chunks_used" in result.metrics

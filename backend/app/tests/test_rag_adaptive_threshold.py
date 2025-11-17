import pytest
from app.services.chat.rag_search_service import RAGSearchParams, RAGSearchService

@pytest.mark.asyncio
async def test_adaptive_threshold_basic(monkeypatch):
    service = RAGSearchService()
    # monkeypatch internal methods to avoid DB/LLM
    async def fake_analyze(q):
        return {"embedding": [0.1]*1024, "korean_keywords": []}
    async def fake_exec(*args, **kwargs):
        return []
    async def fake_execute_hybrid(session, search_params, query_analysis):
        return []
    monkeypatch.setattr(service, '_analyze_query', fake_analyze)
    monkeypatch.setattr(service, '_execute_hybrid_search', fake_execute_hybrid)

    params_short = RAGSearchParams(query='인사', similarity_threshold=0.7)
    result = await service.search_for_rag_context(session=None, search_params=params_short)  # type: ignore
    assert result.search_stats['query_length'] == len('인사')
    # After adaptation threshold should be <= 0.7
    assert params_short.similarity_threshold <= 0.7

    params_long = RAGSearchParams(query='이것은 매우 긴 질의로서 세부 항목과 단계, 맥락을 모두 포함하여 모델이 보다 높은 정밀도를 갖도록 하는 테스트 문장입니다', similarity_threshold=0.7)
    result2 = await service.search_for_rag_context(session=None, search_params=params_long)  # type: ignore
    assert params_long.similarity_threshold >= 0.7

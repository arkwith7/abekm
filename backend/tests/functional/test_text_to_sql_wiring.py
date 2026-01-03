import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.functional
@pytest.mark.asyncio
async def test_agent_chat_tool_sql_routes_to_text_to_sql_worker_basic_wiring(functional_client, monkeypatch):
    """Test 1: Basic API wiring - LLM disabled to verify routing only."""
    import app.agents.features.text_to_sql.services.sql_generator as sql_generator

    # Force deterministic behavior even if the container has LLM credentials.
    monkeypatch.setattr(sql_generator, "_get_llm", lambda: None)

    resp = await functional_client.post(
        "/agent/chat",
        json={
            "message": "사용자 테이블에서 최근 10명 보여줘",
            "tool": "sql",
            "max_chunks": 3,
            "max_tokens": 500,
            "similarity_threshold": 0.25,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert body.get("intent") == "sql"

    # In test environments, LLM keys are commonly missing; we should fail gracefully.
    answer = body.get("answer") or ""
    assert ("설정" in answer) or ("OpenAI" in answer) or ("Azure" in answer)


@pytest.mark.functional
@pytest.mark.asyncio
async def test_agent_chat_tool_sql_with_mock_llm_full_flow(functional_client, monkeypatch):
    """Test 2: Full ReAct flow with Mock LLM - verify tool chain execution."""
    from pydantic import BaseModel, Field

    # Mock LLM response
    class MockSqlGeneration(BaseModel):
        sql: str = Field(default="SELECT emp_no, emp_name FROM users ORDER BY created_at DESC LIMIT 10")

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_llm)

    async def mock_ainvoke(*args, **kwargs):
        return MockSqlGeneration()

    mock_llm.ainvoke = mock_ainvoke

    # Patch LLM to return mock
    import app.agents.features.text_to_sql.services.sql_generator as sql_generator

    original_get_llm = sql_generator._get_llm

    def mock_get_llm():
        return mock_llm

    monkeypatch.setattr(sql_generator, "_get_llm", mock_get_llm)

    resp = await functional_client.post(
        "/agent/chat",
        json={
            "message": "사용자 테이블에서 최근 10명 보여줘",
            "tool": "sql",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert body.get("intent") == "sql"

    answer = body.get("answer") or ""

    # Should contain SQL execution result (even if empty due to test DB)
    assert "SELECT" in answer
    assert "users" in answer or "LIMIT" in answer

    # Should NOT contain error messages
    assert "❌" not in answer or "결과 없음" in answer  # Empty result is OK


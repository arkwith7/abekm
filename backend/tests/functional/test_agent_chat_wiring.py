import pytest


@pytest.mark.functional
@pytest.mark.asyncio
async def test_agent_chat_returns_fallback_message_when_llm_missing(functional_client):
    # Force fallback regardless of container env
    import app.agents.supervisor_agent as sup

    sup.supervisor_chain = None

    resp = await functional_client.post(
        "/agent/chat",
        json={
            "message": "안녕",
            "max_chunks": 3,
            "max_tokens": 500,
            "similarity_threshold": 0.25,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert "not configured" in (body.get("answer") or "")

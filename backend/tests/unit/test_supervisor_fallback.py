import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_supervisor_finishes_when_llm_missing():
    # Import module under test
    import app.agents.supervisor_agent as sup

    # Force misconfigured state regardless of container env
    sup.supervisor_chain = None

    initial_state = {"messages": [HumanMessage(content="안녕")], "next": "", "shared_context": {}}
    final_state = await sup.supervisor_agent.ainvoke(initial_state)

    assert final_state["messages"], "Supervisor should append a message on fallback"
    last = final_state["messages"][-1]
    assert "not configured" in (last.content or "")

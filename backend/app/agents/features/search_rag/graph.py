from __future__ import annotations

from typing import Any, Dict, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from loguru import logger


async def search_rag_worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Supervisor worker entrypoint for Search RAG.

    This is intentionally lightweight/import-safe: it imports heavier modules
    only when the node runs.
    """

    # Lazy imports to avoid side effects at module import time.
    from app.agents.features.search_rag.agent import paper_search_agent
    from app.agents.core.db import get_db_session_context

    messages: Sequence[BaseMessage] = state["messages"]
    last_message = messages[-1].content

    logger.info(f"Supervisor routing to SearchAgent: {str(last_message)[:50]}...")

    async with get_db_session_context() as db_session:
        history_dicts = []
        for msg in messages[:-1]:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            history_dicts.append({"role": role, "content": msg.content})

        result = await paper_search_agent.execute(
            query=last_message,
            db_session=db_session,
            history=history_dicts,
        )

    response_content = result.answer

    shared_context = dict(state.get("shared_context", {}))
    shared_context.update(
        {
            "search_result": response_content,
            "search_agent_result": result,
        }
    )

    return {
        "messages": [AIMessage(content=response_content, name="SearchAgent")],
        "shared_context": shared_context,
    }

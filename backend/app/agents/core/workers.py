from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Mapping, TypedDict, Any, Sequence

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from loguru import logger

from app.agents.core.db import get_db_session_context


class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next: str
    shared_context: Dict[str, Any]


NodeFunc = Callable[[AgentState], Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class WorkerSpec:
    """Supervisor가 호출할 Worker 정의."""

    name: str
    description: str
    node: NodeFunc


async def _search_node(state: AgentState) -> Dict[str, Any]:
    # Lazy import to avoid heavyweight initialization at module import time
    # (important for tests and misconfigured environments).
    from app.agents.paper_search_agent import paper_search_agent

    messages = state["messages"]
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


async def _presentation_node(state: AgentState) -> Dict[str, Any]:
    # Lazy import to avoid heavyweight initialization at module import time
    # (important for tests and misconfigured environments).
    from app.agents.presentation import presentation_agent_tool

    shared_context = state.get("shared_context", {})
    search_result = shared_context.get("search_result", "")

    logger.info(f"Supervisor routing to PresentationAgent. Context len: {len(search_result)}")

    context_text = search_result if search_result else "Create a presentation based on the conversation."

    try:
        tool_result = await presentation_agent_tool._arun(
            context_text=context_text,
            topic=None,
            documents=[],
            options={},
            template_style="business",
            presentation_type="general",
            quick_mode=False,
        )

        if tool_result.get("success"):
            file_name = tool_result.get("file_name", "presentation.pptx")
            file_path = tool_result.get("file_path", "")
            final_response = f"✅ PPT 생성 완료!\n\n📄 파일명: {file_name}\n💾 경로: {file_path}"
        else:
            error_msg = tool_result.get("error", "알 수 없는 오류")
            final_response = f"❌ PPT 생성 실패: {error_msg}"

    except Exception as e:
        logger.error(f"PresentationAgent Tool 실행 실패: {e}")
        final_response = f"❌ Presentation generation failed: {str(e)}"

    # shared_context는 유지(검색 결과 등)
    return {
        "messages": [AIMessage(content=final_response, name="PresentationAgent")],
        "shared_context": dict(shared_context),
    }


def get_default_workers() -> Mapping[str, WorkerSpec]:
    """현재 활성화된 기본 Worker 목록.

    향후에는 설정/레지스트리 기반으로 확장할 수 있도록 한 곳으로 모은다.
    """

    workers = {
        "SearchAgent": WorkerSpec(
            name="SearchAgent",
            description="논문/문서 검색 및 QA 수행",
            node=_search_node,
        ),
        "PresentationAgent": WorkerSpec(
            name="PresentationAgent",
            description="검색 결과 기반 PPT 생성",
            node=_presentation_node,
        ),
    }

    return workers

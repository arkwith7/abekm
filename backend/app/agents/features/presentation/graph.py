from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import AIMessage
from loguru import logger


async def presentation_worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Supervisor worker entrypoint for Presentation.

    This intentionally keeps imports lazy to avoid import-time side effects.
    """

    # Lazy import to avoid heavyweight initialization at module import time.
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

    return {
        "messages": [AIMessage(content=final_response, name="PresentationAgent")],
        "shared_context": dict(shared_context),
    }

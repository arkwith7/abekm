from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from loguru import logger


class SafeLogCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that logs minimal, non-sensitive run info.

    Notes:
    - Avoids logging prompts / full tool inputs by default.
    - Intended to complement LangSmith (UI) with terminal/file logs.
    """

    def __init__(self, *, redact: bool = True):
        super().__init__()
        self._redact = redact

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        model = (serialized or {}).get("name") or (serialized or {}).get("id") or "unknown"
        logger.info(
            "🔎 LangChain LLM start | run_id={} parent={} model={} tags={} meta_keys={}",
            run_id,
            parent_run_id,
            model,
            tags or [],
            sorted(list((metadata or {}).keys())),
        )

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        usage: Dict[str, Any] = {}
        llm_output = getattr(response, "llm_output", None)
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or llm_output.get("usage") or {}

        logger.info(
            "✅ LangChain LLM end | run_id={} parent={} tags={} usage={}",
            run_id,
            parent_run_id,
            tags or [],
            usage or {},
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        logger.error("❌ LangChain LLM error | run_id={} parent={} err={}", run_id, parent_run_id, error)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        tool = (serialized or {}).get("name") or "unknown_tool"
        logger.info(
            "🛠️ LangChain tool start | run_id={} parent={} tool={} tags={} meta_keys={}",
            run_id,
            parent_run_id,
            tool,
            tags or [],
            sorted(list((metadata or {}).keys())),
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        logger.info("🧩 LangChain tool end | run_id={} parent={}", run_id, parent_run_id)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        logger.error("❌ LangChain tool error | run_id={} parent={} err={}", run_id, parent_run_id, error)

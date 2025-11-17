"""Summary pipeline tool built on top of the existing document summarizer."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

try:  # pragma: no cover - optional dependency for LangChain compatibility
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:  # pragma: no cover
    from langchain.tools import BaseTool  # type: ignore

from app.core.database import get_async_session_local
from app.tools.contracts import ToolResult
from app.tools.document.document_summarizer_tool import document_summarizer_tool


class SummaryPipelineTool(BaseTool):
    """Wrapper around ``document_summarizer_tool`` that manages DB sessions.

    This tool is intended to be the single entry point for summarisation pipelines
    in the new agent architecture. It keeps the orchestration logic inside
    ``document_summarizer_tool`` while offering a clean interface for agents or
    orchestrators.
    """

    name: str = "summary_pipeline"
    description: str = (
        "Document summarisation pipeline that supports chat prompts, selected"
        " documents and uploaded files. Automatically acquires a database"
        " session when one is not provided."
    )

    async def _arun(
        self,
        *,
        request_type: Optional[str] = None,
        document_ids: Optional[List[int]] = None,
        attachment_paths: Optional[List[str]] = None,
        attachment_metadata: Optional[List[Dict[str, Any]]] = None,
        query_text: Optional[str] = None,
        summarization_type: str = "comprehensive",
        user_emp_no: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        search_document_ids: Optional[List[int]] = None,
        context_max_tokens: int = 4000,
        max_chunks: int = 50,
        db_session: Optional[AsyncSession] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the summarisation pipeline.

        Parameters mirror ``document_summarizer_tool`` with a couple of
        convenience defaults. Any additional keyword arguments are forwarded to
        the underlying tool for forward compatibility.
        """

        logger.info(
            "🚀 [SummaryPipeline] 실행: request_type=%s, docs=%s, attachments=%s, query=%s",
            request_type,
            len(document_ids or []),
            len(attachment_paths or []),
            bool(query_text and query_text.strip()),
        )

        async def _invoke(session: AsyncSession) -> ToolResult:
            return await document_summarizer_tool._arun(
                document_ids=document_ids,
                attachment_paths=attachment_paths,
                attachment_metadata=attachment_metadata,
                db_session=session,
                max_chunks=max_chunks,
                summarization_type=summarization_type,
                user_emp_no=user_emp_no,
                request_type=request_type,
                query_text=query_text,
                container_ids=container_ids,
                search_document_ids=search_document_ids,
                context_max_tokens=context_max_tokens,
                **kwargs,
            )

        if db_session is not None:
            logger.debug("[SummaryPipeline] 외부에서 제공된 세션 사용")
            return await _invoke(db_session)

        session_factory = get_async_session_local()
        async with session_factory() as session:
            logger.debug("[SummaryPipeline] 자체 세션 생성")
            return await _invoke(session)

    def _run(self, *args: Any, **kwargs: Any) -> ToolResult:
        """Synchronous execution wrapper required by :class:`BaseTool`."""

        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError as exc:
            raise RuntimeError(
                "SummaryPipelineTool synchronous execution requires an event loop."
                " Call `_arun` from an async context."
            ) from exc


summary_pipeline_tool = SummaryPipelineTool()

__all__ = ["SummaryPipelineTool", "summary_pipeline_tool"]

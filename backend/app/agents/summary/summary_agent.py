"""Summary agent implementation for the new agent architecture."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency for LangChain compatibility
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:  # pragma: no cover
    from langchain_core.tools import BaseTool  # type: ignore

from app.tools.summary import summary_pipeline_tool


class SummaryAgentInput(BaseModel):
    """Input schema for :class:`SummaryAgentTool`."""

    query: Optional[str] = Field(default=None, description="사용자 요약 요청 문장")
    documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="선택된 문서 목록 (각 항목은 최소한 id/fileName 정보 포함)",
    )
    attachment_paths: List[str] = Field(
        default_factory=list,
        description="요약 대상 첨부 파일 경로 목록",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="추가 옵션 (context_max_tokens, max_chunks 등)",
    )
    user_emp_no: Optional[str] = Field(default=None, description="요청자 사번")
    request_type: Optional[str] = Field(
        default=None,
        description="요청 유형 힌트(chat_prompt | selected_documents | uploaded_files)",
    )
    summarization_type: str = Field(
        default="comprehensive",
        description="요약 형식 (comprehensive | brief | bullet_points)",
    )


class SummaryAgentTool(BaseTool):
    """AI Agent interface that orchestrates the summarisation pipeline."""

    name: str = "summary_agent_tool"
    description: str = (
        "Summarises selected documents, uploaded files or chat prompts using"
        " the new summary pipeline tool."
    )
    args_schema: Type[BaseModel] = SummaryAgentInput

    async def _arun(
        self,
        query: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        attachment_paths: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
        user_emp_no: Optional[str] = None,
        request_type: Optional[str] = None,
        summarization_type: str = "comprehensive",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        docs = documents or []
        attachments = attachment_paths or []
        options = options or {}

        document_ids = self._extract_document_ids(docs)
        container_ids = self._extract_container_ids(docs)
        inferred_request_type = self._infer_request_type(
            request_type,
            document_ids,
            attachments,
            query,
        )

        context_max_tokens = int(options.get("context_max_tokens", options.get("max_context_tokens", 4000)))
        max_chunks = int(options.get("max_chunks", 50))

        logger.info(
            "🧠 [SummaryAgent] 실행: request_type=%s, docs=%s, attachments=%s",
            inferred_request_type,
            len(document_ids),
            len(attachments),
        )

        pipeline_result = await summary_pipeline_tool._arun(
            request_type=inferred_request_type,
            document_ids=document_ids or None,
            attachment_paths=attachments or None,
            query_text=query,
            summarization_type=summarization_type,
            user_emp_no=user_emp_no,
            container_ids=container_ids or None,
            search_document_ids=document_ids or None,
            context_max_tokens=context_max_tokens,
            max_chunks=max_chunks,
        )

        result_dict = pipeline_result.model_dump(mode="json")
        summary_text = (
            result_dict.get("data", {}).get("summary")
            if isinstance(result_dict.get("data"), dict)
            else ""
        )
        success = result_dict.get("success", False)
        errors = result_dict.get("errors", [])

        response_payload: Dict[str, Any] = {
            "success": success,
            "response": summary_text or "",
            "summary": summary_text or "",
            "source_info": result_dict.get("data", {}).get("source_info", {}),
            "trace_id": result_dict.get("trace_id"),
            "metrics": result_dict.get("metrics"),
            "raw_result": result_dict,
        }

        if not success and errors:
            response_payload["error"] = "; ".join(errors)

        return response_payload

    def _run(
        self,
        query: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        attachment_paths: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
        user_emp_no: Optional[str] = None,
        request_type: Optional[str] = None,
        summarization_type: str = "comprehensive",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Synchronous wrapper that delegates to the async implementation."""
        return asyncio.run(
            self._arun(
                query=query,
                documents=documents,
                attachment_paths=attachment_paths,
                options=options,
                user_emp_no=user_emp_no,
                request_type=request_type,
                summarization_type=summarization_type,
                **kwargs,
            )
        )

    def _extract_document_ids(self, documents: List[Dict[str, Any]]) -> List[int]:
        ids: List[int] = []
        for doc in documents:
            candidate = (
                doc.get("id")
                or doc.get("fileId")
                or doc.get("file_id")
                or doc.get("document_id")
            )
            if candidate is None:
                continue
            try:
                ids.append(int(str(candidate)))
            except (TypeError, ValueError):
                logger.debug("[SummaryAgent] 문서 ID 변환 실패: %s", candidate)
        return ids

    def _extract_container_ids(self, documents: List[Dict[str, Any]]) -> List[str]:
        container_ids: List[str] = []
        for doc in documents:
            metadata = doc.get("metadata") or {}
            candidate = (
                metadata.get("containerId")
                or metadata.get("container_id")
                or doc.get("container_id")
                or doc.get("containerId")
            )
            if not candidate:
                continue
            container_ids.append(str(candidate))
        return container_ids

    def _infer_request_type(
        self,
        explicit: Optional[str],
        document_ids: List[int],
        attachments: List[str],
        query: Optional[str],
    ) -> str:
        if explicit:
            return explicit
        if attachments:
            return "uploaded_files"
        if document_ids:
            return "selected_documents"
        if query and query.strip():
            return "chat_prompt"
        return "auto"


summary_agent_tool = SummaryAgentTool()

__all__ = ["SummaryAgentTool", "summary_agent_tool"]

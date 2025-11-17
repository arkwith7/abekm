"""Presentation agent implementation for the new agent architecture."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency for LangChain compatibility
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:  # pragma: no cover
    from langchain.tools import BaseTool  # type: ignore

from app.tools.presentation import presentation_pipeline_tool


class PresentationAgentInput(BaseModel):
    """Input schema for :class:`PresentationAgentTool`."""

    topic: Optional[str] = Field(default=None, description="프레젠테이션 제목/주제")
    context_text: str = Field(..., description="PPT 생성에 사용할 컨텍스트 텍스트 (요약문, 문서 내용 등)")
    documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="선택된 문서 목록 (메타데이터 참조용)",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="추가 옵션 (template_style, include_charts, max_slides 등)",
    )
    template_style: str = Field(
        default="business",
        description="템플릿 스타일 (business | modern | minimal | playful)",
    )
    presentation_type: str = Field(
        default="general",
        description="프레젠테이션 유형 (general | product_introduction)",
    )
    quick_mode: bool = Field(
        default=False,
        description="빠른 생성 모드 (LLM 없이 고정 구조 사용)",
    )


class PresentationAgentTool(BaseTool):
    """AI Agent interface that orchestrates the presentation generation pipeline."""

    name: str = "presentation_agent_tool"
    description: str = (
        "Generates professional presentations from document summaries or context text. "
        "Supports template customization, automatic chart generation, and multiple presentation types."
    )
    args_schema: Type[BaseModel] = PresentationAgentInput

    async def _arun(
        self,
        context_text: str,
        topic: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        template_style: str = "business",
        presentation_type: str = "general",
        quick_mode: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute presentation generation.

        Args:
            context_text: Source content for slides
            topic: Presentation title (auto-inferred if not provided)
            documents: Source document metadata
            options: Additional generation options
            template_style: Visual theme
            presentation_type: Content structure type
            quick_mode: Skip LLM for faster generation

        Returns:
            Dict with file path, metadata, and generation status
        """
        docs = documents or []
        options = options or {}

        # Extract document filename for title inference
        document_filename = None
        if docs:
            first_doc = docs[0]
            document_filename = (
                first_doc.get("fileName")
                or first_doc.get("file_name")
                or first_doc.get("name")
            )

        # Auto-infer topic if not provided
        inferred_topic = topic or self._infer_topic_from_context(context_text, document_filename)

        # Extract generation parameters
        provider = options.get("provider", options.get("llm_provider"))
        include_charts = options.get("include_charts", True)
        max_slides = int(options.get("max_slides", 8))
        user_template_id = options.get("user_template_id")

        logger.info(
            "🎨 [PresentationAgent] 실행: topic='%s', slides=%d, quick=%s, type=%s",
            inferred_topic[:50] if inferred_topic else "N/A",
            max_slides,
            quick_mode,
            presentation_type,
        )

        pipeline_result = await presentation_pipeline_tool._arun(
            topic=inferred_topic,
            context_text=context_text,
            provider=provider,
            template_style=template_style,
            include_charts=include_charts,
            max_slides=max_slides,
            document_filename=document_filename,
            presentation_type=presentation_type,
            quick_mode=quick_mode,
            user_template_id=user_template_id,
        )

        result_dict = pipeline_result.model_dump(mode="json")
        file_data = result_dict.get("data", {}) if isinstance(result_dict.get("data"), dict) else {}
        success = result_dict.get("success", False)
        errors = result_dict.get("errors", [])

        response_payload: Dict[str, Any] = {
            "success": success,
            "file_path": file_data.get("file_path", ""),
            "file_name": file_data.get("file_name", ""),
            "file_size_bytes": file_data.get("file_size_bytes", 0),
            "slide_count": file_data.get("slide_count", 0),
            "template_style": file_data.get("template_style", template_style),
            "presentation_type": file_data.get("presentation_type", presentation_type),
            "trace_id": result_dict.get("trace_id"),
            "metrics": result_dict.get("metrics"),
            "raw_result": result_dict,
        }

        if not success and errors:
            response_payload["error"] = "; ".join(errors)

        return response_payload

    def _run(
        self,
        context_text: str,
        topic: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        template_style: str = "business",
        presentation_type: str = "general",
        quick_mode: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Synchronous wrapper that delegates to the async implementation."""
        return asyncio.run(
            self._arun(
                context_text=context_text,
                topic=topic,
                documents=documents,
                options=options,
                template_style=template_style,
                presentation_type=presentation_type,
                quick_mode=quick_mode,
                **kwargs,
            )
        )

    def _infer_topic_from_context(
        self,
        context_text: str,
        document_filename: Optional[str] = None,
    ) -> str:
        """Infer presentation topic from context or document name."""
        if document_filename:
            # Use document name as fallback
            import re
            clean_name = re.sub(r'\.(docx?|pdf|txt|pptx?)$', '', document_filename, flags=re.IGNORECASE)
            return clean_name

        # Extract first meaningful line from context
        if context_text:
            lines = [ln.strip() for ln in context_text.split('\n') if ln.strip()]
            if lines:
                first_line = lines[0]
                # Clean markdown decorators
                import re
                cleaned = re.sub(r'^[#>*\s]*', '', first_line).strip()
                if cleaned and len(cleaned) <= 100:
                    return cleaned

        return "프레젠테이션"


presentation_agent_tool = PresentationAgentTool()

__all__ = ["PresentationAgentTool", "presentation_agent_tool"]

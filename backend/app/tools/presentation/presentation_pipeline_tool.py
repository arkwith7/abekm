"""Presentation pipeline tool that wraps the enhanced PPT generator service."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

try:  # pragma: no cover - optional dependency for LangChain compatibility
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:  # pragma: no cover
    from langchain.tools import BaseTool  # type: ignore

from app.services.presentation.enhanced_ppt_generator_service import (
    enhanced_ppt_generator_service,
)
from app.services.presentation.ppt_models import DeckSpec
from app.tools.contracts import ToolResult
from app.tools.presentation.pptxgenjs_tool import get_pptxgenjs_tool


class PresentationPipelineTool(BaseTool):
    """Wrapper around the enhanced PPT generator service for agent architecture.

    This tool provides a unified entry point for presentation generation, supporting:
    - Context-based PPT generation (from document summaries, text content)
    - Template selection and customization
    - Quick one-click PPT generation
    - Product introduction presentations

    The tool manages the orchestration of outline generation and PPTX building,
    keeping the agent interface clean while delegating heavy lifting to the
    presentation service.
    """

    name: str = "presentation_pipeline"
    description: str = (
        "Generate professional presentations from document content or context text. "
        "Supports multiple templates, automatic outline generation, and chart/diagram creation."
    )

    async def _arun(
        self,
        *,
        topic: str,
        context_text: str,
        provider: Optional[str] = None,
        template_style: str = "business",
        include_charts: bool = True,
        max_slides: int = 8,
        document_filename: Optional[str] = None,
        presentation_type: str = "general",
        quick_mode: bool = False,
        user_template_id: Optional[str] = None,
        generator: str = "legacy",  # NEW: legacy | pptxgenjs
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the presentation generation pipeline.

        Args:
            topic: Presentation title/topic
            context_text: Source content for generating slides
            provider: LLM provider (azure_openai | bedrock)
            template_style: Template theme (business | modern | minimal | playful)
            include_charts: Enable automatic chart generation from data
            max_slides: Maximum number of slides to generate
            document_filename: Original document filename for title extraction
            presentation_type: Type of presentation (general | product_introduction)
            quick_mode: Skip LLM outline generation, use fixed structure
            user_template_id: Custom user-uploaded template identifier
            generator: PPTX generator backend (legacy | pptxgenjs)

        Returns:
            ToolResult with file path and metadata
        """
        logger.info(
            "🎨 [PresentationPipeline] 실행: topic='%s', slides=%d, template=%s, quick=%s",
            topic[:50] if topic else "N/A",
            max_slides,
            template_style,
            quick_mode,
        )

        try:
            service = enhanced_ppt_generator_service

            # Quick mode: fixed outline without LLM
            if quick_mode:
                logger.info("⚡ Quick mode: 고정 구조 생성")
                deck_spec = service.generate_fixed_outline(
                    topic=topic,
                    context_text=context_text,
                    max_slides=max_slides,
                )
                pptx_path = service.build_quick_pptx(
                    spec=deck_spec,
                    file_basename=document_filename,
                )
            else:
                # Enhanced mode: LLM-driven outline generation
                logger.info("🧠 Enhanced mode: LLM 기반 아웃라인 생성")
                deck_spec = await service.generate_enhanced_outline(
                    topic=topic,
                    context_text=context_text,
                    provider=provider,
                    template_style=template_style,
                    include_charts=include_charts,
                    retries=2,
                    document_filename=document_filename,
                    presentation_type=presentation_type,
                    user_template_id=user_template_id,
                )

                # Build PPTX - route to selected generator
                if generator == "pptxgenjs":
                    logger.info("🚀 Using PptxGenJS (Node.js) generator")
                    pptx_path = await self._build_pptxgenjs(
                        deck_spec=deck_spec,
                        file_basename=document_filename,
                    )
                else:
                    logger.info("📄 Using legacy python-pptx generator")
                    pptx_path = service._build_legacy_pptx(
                        spec=deck_spec,
                        file_basename=document_filename,
                        template_style=template_style,
                        include_charts=include_charts,
                    )

            # Validate output
            output_file = Path(pptx_path)
            if not output_file.exists():
                raise FileNotFoundError(f"생성된 PPTX 파일을 찾을 수 없습니다: {pptx_path}")

            file_size = output_file.stat().st_size
            logger.info("✅ [PresentationPipeline] 성공: %s (%.2f KB)", output_file.name, file_size / 1024)

            from app.tools.contracts import ToolMetrics
            import uuid

            trace_id = str(uuid.uuid4())

            return ToolResult(
                success=True,
                data={
                    "file_path": str(pptx_path),
                    "file_name": output_file.name,
                    "file_size_bytes": file_size,
                    "slide_count": len(deck_spec.slides) if deck_spec else 0,
                    "template_style": template_style,
                    "presentation_type": presentation_type,
                },
                metrics=ToolMetrics(
                    latency_ms=0.0,
                    provider=provider or "internal",
                    items_returned=len(deck_spec.slides) if deck_spec else 0,
                ),
                trace_id=trace_id,
                tool_name=self.name,
            )

        except Exception as exc:
            logger.error("❌ [PresentationPipeline] 실패: %s", exc, exc_info=True)
            import uuid
            from app.tools.contracts import ToolMetrics

            return ToolResult(
                success=False,
                data={},
                metrics=ToolMetrics(latency_ms=0.0, provider="internal"),
                errors=[f"PPT 생성 실패: {str(exc)}"],
                trace_id=str(uuid.uuid4()),
                tool_name=self.name,
            )

    def _run(self, *args: Any, **kwargs: Any) -> ToolResult:
        """Synchronous execution wrapper required by BaseTool."""
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError as exc:
            raise RuntimeError(
                "PresentationPipelineTool synchronous execution requires an event loop. "
                "Call `_arun` from an async context."
            ) from exc


    async def _build_pptxgenjs(
        self,
        deck_spec: DeckSpec,
        file_basename: Optional[str] = None,
    ) -> str:
        """Build PPTX using Node.js PptxGenJS service.
        
        Args:
            deck_spec: DeckSpec with slides/content
            file_basename: Optional filename (without extension)
            
        Returns:
            Path to generated PPTX file
        """
        import tempfile
        import os
        from app.core.config import settings
        pptxgenjs_tool = get_pptxgenjs_tool()
        
        # Convert DeckSpec to dictionary
        deck_dict = deck_spec.model_dump() if hasattr(deck_spec, 'model_dump') else deck_spec.dict()
        
        # Call Node.js service
        pptx_content = await pptxgenjs_tool.generate_pptx(deck_dict)
        
        # Save to output directory
        output_dir = Path(getattr(settings, 'presentation_output_dir', tempfile.gettempdir()))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{file_basename or 'presentation'}.pptx"
        output_path = output_dir / filename
        
        output_path.write_bytes(pptx_content)
        
        logger.info(f"✅ PptxGenJS file saved: {output_path}")
        return str(output_path)


presentation_pipeline_tool = PresentationPipelineTool()

__all__ = ["PresentationPipelineTool", "presentation_pipeline_tool"]

"""Presentation pipeline tool that orchestrates the layered tool architecture."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.services.presentation.ppt_models import DeckSpec
from app.tools.contracts import ToolResult, ToolMetrics
from app.tools.presentation.pptxgenjs_tool import get_pptxgenjs_tool
from app.tools.presentation.content_planning_tools import OutlineGeneratorTool
from app.tools.presentation.assembly_tools import SlideAssemblerTool


class PresentationPipelineTool(BaseTool):
    """Orchestrator for presentation generation using layered tools."""

    name: str = "presentation_pipeline"
    description: str = (
        "Generate professional presentations from document content or context text. "
        "Supports multiple templates, automatic outline generation, and chart/diagram creation."
    )
    
    outline_generator: OutlineGeneratorTool = OutlineGeneratorTool()
    slide_assembler: SlideAssemblerTool = SlideAssemblerTool()

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
        generator: str = "legacy",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the presentation generation pipeline."""
        logger.info(
            "🎨 [PresentationPipeline] Start: topic='%s', slides=%d, template=%s, quick=%s",
            topic[:50] if topic else "N/A",
            max_slides,
            template_style,
            quick_mode,
        )

        try:
            # 1. Generate Outline (Content Planning Layer)
            if quick_mode:
                logger.info("⚡ Quick mode: Generating fixed outline")
                deck_spec = self.outline_generator.generate_fixed_outline(
                    topic=topic,
                    context_text=context_text,
                    max_slides=max_slides,
                )
            else:
                logger.info("🧠 Enhanced mode: Generating LLM-based outline")
                deck_spec = await self.outline_generator._arun(
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

            # 2. Build Presentation (Assembly Layer)
            if generator == "pptxgenjs":
                logger.info("�� Using PptxGenJS (Node.js) generator")
                pptx_path = await self._build_pptxgenjs(
                    deck_spec=deck_spec,
                    file_basename=document_filename,
                )
            else:
                logger.info("📄 Using legacy python-pptx generator (via SlideAssembler)")
                # For quick mode, we force standard build without charts if desired, 
                # but SlideAssembler handles it based on flags.
                # If quick_mode was requested, we might want to disable charts in build too?
                # The original code did include_charts=False for quick build.
                build_charts = False if quick_mode else include_charts
                
                pptx_path = self.slide_assembler._run(
                    spec=deck_spec,
                    file_basename=document_filename,
                    template_style=template_style,
                    include_charts=build_charts,
                    user_template_id=user_template_id if not quick_mode else None
                )

            # 3. Validate Output
            output_file = Path(pptx_path)
            if not output_file.exists():
                raise FileNotFoundError(f"Generated PPTX file not found: {pptx_path}")

            file_size = output_file.stat().st_size
            logger.info("✅ [PresentationPipeline] Success: %s (%.2f KB)", output_file.name, file_size / 1024)

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
            logger.error("❌ [PresentationPipeline] Failed: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data={},
                metrics=ToolMetrics(latency_ms=0.0, provider="internal"),
                errors=[f"PPT Generation Failed: {str(exc)}"],
                trace_id=str(uuid.uuid4()),
                tool_name=self.name,
            )

    def _run(self, *args: Any, **kwargs: Any) -> ToolResult:
        """Synchronous execution wrapper."""
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError as exc:
            raise RuntimeError(
                "PresentationPipelineTool synchronous execution requires an event loop."
            ) from exc

    async def _build_pptxgenjs(self, deck_spec: DeckSpec, file_basename: Optional[str] = None) -> str:
        """Build PPTX using Node.js PptxGenJS service."""
        import tempfile
        from app.core.config import settings
        
        pptxgenjs_tool = get_pptxgenjs_tool()
        deck_dict = deck_spec.model_dump() if hasattr(deck_spec, 'model_dump') else deck_spec.dict()
        pptx_content = await pptxgenjs_tool.generate_pptx(deck_dict)
        
        output_dir = Path(getattr(settings, 'presentation_output_dir', tempfile.gettempdir()))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{file_basename or 'presentation'}.pptx"
        output_path = output_dir / filename
        output_path.write_bytes(pptx_content)
        
        logger.info(f"✅ PptxGenJS file saved: {output_path}")
        return str(output_path)


presentation_pipeline_tool = PresentationPipelineTool()

__all__ = ["PresentationPipelineTool", "presentation_pipeline_tool"]

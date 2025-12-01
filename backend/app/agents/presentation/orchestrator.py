"""Presentation agent orchestrator.

This module centralizes the presentation generation strategies so that
both API endpoints and LangChain-based tools share the exact same
execution path. The orchestration logic was migrated here from the
legacy `backend/app/agents/presentation_agent.py` so we can keep a
single source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.tools.presentation.outline_generation_tool import outline_generation_tool
from app.tools.presentation.quick_pptx_builder_tool import quick_pptx_builder_tool
from app.tools.presentation.visualization_tool import visualization_tool
from app.tools.presentation.template_application_tool import template_application_tool
from app.tools.presentation.content_assembly_tool import content_assembly_tool
from app.tools.presentation.style_analysis_tool import style_analysis_tool


class PresentationAgent:
    """Presentation generation orchestrator."""

    name: str = "presentation_agent"
    description: str = "Orchestrates tool chains for PowerPoint generation"
    version: str = "2.1.0"

    def __init__(self) -> None:
        self.tools = {
            "outline_generation": outline_generation_tool,
            "quick_pptx_builder": quick_pptx_builder_tool,
            "visualization": visualization_tool,
            "template_application": template_application_tool,
            "content_assembly": content_assembly_tool,
            "style_analysis": style_analysis_tool,
        }
        self._execution_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._steps: List[Dict[str, Any]] = []

    async def execute(
        self,
        mode: str,
        topic: str,
        context_text: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the presentation agent workflow."""

        try:
            self._execution_id = str(uuid.uuid4())
            self._start_time = datetime.utcnow()
            self._steps = []
            options = options or {}

            logger.info(
                "🎬 [PresentationAgent] 시작: mode=%s, topic='%s'",
                mode,
                topic,
            )
            logger.info("📊 Execution ID: %s", self._execution_id)

            strategy = self._select_strategy(mode, options)
            logger.info("🎯 선택된 전략: %s", strategy)

            if strategy == "quick_generation":
                result = await self._execute_quick_strategy(topic, context_text, options)
            elif strategy == "enhanced_auto":
                result = await self._execute_enhanced_auto_strategy(topic, context_text, options)
            elif strategy == "enhanced_template":
                result = await self._execute_enhanced_template_strategy(topic, context_text, options)
            elif strategy == "style_transfer":
                result = await self._execute_style_transfer_strategy(topic, context_text, options)
            else:
                raise ValueError(f"알 수 없는 전략: {strategy}")

            execution_time = (datetime.utcnow() - self._start_time).total_seconds()
            result.update(
                {
                    "execution_id": self._execution_id,
                    "mode": mode,
                    "strategy": strategy,
                    "execution_time": execution_time,
                    "steps": self._steps,
                    "timestamp": self._start_time.isoformat(),
                }
            )

            logger.info("✅ [PresentationAgent] 완료: %.2f초", execution_time)
            return result

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ [PresentationAgent] 실패: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "execution_id": self._execution_id,
                "mode": mode,
                "steps": self._steps,
            }

    def _select_strategy(self, mode: str, options: Dict[str, Any]) -> str:
        """Select which generation strategy to execute."""

        if mode == "quick":
            return "quick_generation"
        if mode == "style_transfer" or options.get("style_reference_path"):
            return "style_transfer"
        if mode == "enhanced":
            if options.get("template_path"):
                return "enhanced_template"
            return "enhanced_auto"
        logger.warning("알 수 없는 mode=%s, quick_generation으로 폴백", mode)
        return "quick_generation"

    async def _execute_quick_strategy(
        self,
        topic: str,
        context_text: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("🚀 Quick 생성 전략 실행")
        max_slides = int(options.get("max_slides", 10))

        self._log_step("outline_generation", "시작")
        outline_result = await outline_generation_tool._arun(
            context_text=context_text,
            topic=topic,
            max_slides=max_slides,
        )
        if not outline_result["success"]:
            raise RuntimeError(f"Outline 생성 실패: {outline_result.get('error')}")
        self._log_step(
            "outline_generation",
            "완료",
            {"slide_count": outline_result["slide_count"]},
        )

        deck_spec = outline_result["deck"]

        if options.get("analyze_visualization", True):
            self._log_step("visualization", "시작")
            viz_results = []
            for idx, slide in enumerate(deck_spec["slides"]):
                if slide.get("slide_type") in ("title", "toc", "closing"):
                    continue
                viz_result = await visualization_tool._arun(
                    slide_title=slide["title"],
                    key_message=slide.get("key_message", ""),
                    bullets=slide.get("bullets", []),
                    slide_index=idx,
                )
                viz_results.append(viz_result)
            self._log_step(
                "visualization",
                "완료",
                {"analyzed_slides": len(viz_results)},
            )

        self._log_step("quick_pptx_builder", "시작")
        build_result = await quick_pptx_builder_tool._arun(
            deck_spec=deck_spec,
            file_basename=options.get("file_basename"),
        )
        if not build_result["success"]:
            raise RuntimeError(f"PPTX 빌드 실패: {build_result.get('error')}")
        self._log_step(
            "quick_pptx_builder",
            "완료",
            {
                "file_path": build_result["file_path"],
                "slide_count": build_result["slide_count"],
            },
        )
        return build_result

    async def _execute_enhanced_auto_strategy(
        self,
        topic: str,
        context_text: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("🚀 Enhanced 자동 생성 전략 실행")
        max_slides = int(options.get("max_slides", 10))
        content_segments = options.get("content_segments")

        if content_segments:
            self._log_step("content_assembly", "시작")
            assembly_result = await content_assembly_tool._arun(
                topic=topic,
                content_segments=content_segments,
                assembly_strategy=options.get("assembly_strategy", "sequential"),
                max_slides=max_slides,
                include_toc=options.get("include_toc", True),
            )
            if not assembly_result["success"]:
                raise RuntimeError(f"콘텐츠 조립 실패: {assembly_result.get('error')}")
            self._log_step(
                "content_assembly",
                "완료",
                {
                    "segments_used": assembly_result["segments_used"],
                    "slide_count": assembly_result["slide_count"],
                },
            )
            deck_spec = assembly_result["deck"]
        else:
            self._log_step("outline_generation", "시작")
            outline_result = await outline_generation_tool._arun(
                context_text=context_text,
                topic=topic,
                max_slides=max_slides,
            )
            if not outline_result["success"]:
                raise RuntimeError(f"Outline 생성 실패: {outline_result.get('error')}")
            self._log_step(
                "outline_generation",
                "완료",
                {"slide_count": outline_result["slide_count"]},
            )
            deck_spec = outline_result["deck"]

        self._log_step("quick_pptx_builder", "시작")
        build_result = await quick_pptx_builder_tool._arun(
            deck_spec=deck_spec,
            file_basename=options.get("file_basename"),
        )
        if not build_result["success"]:
            raise RuntimeError(f"PPTX 빌드 실패: {build_result.get('error')}")
        self._log_step(
            "quick_pptx_builder",
            "완료",
            {
                "file_path": build_result["file_path"],
                "slide_count": build_result["slide_count"],
            },
        )
        return build_result

    async def _execute_enhanced_template_strategy(
        self,
        topic: str,
        context_text: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("🚀 Enhanced 템플릿 적용 전략 실행")
        max_slides = int(options.get("max_slides", 10))
        template_path = options.get("template_path")
        if not template_path:
            raise ValueError("템플릿 경로가 필요합니다")

        content_segments = options.get("content_segments")

        if content_segments:
            self._log_step("content_assembly", "시작")
            assembly_result = await content_assembly_tool._arun(
                topic=topic,
                content_segments=content_segments,
                assembly_strategy=options.get("assembly_strategy", "sequential"),
                max_slides=max_slides,
                include_toc=options.get("include_toc", True),
            )
            if not assembly_result["success"]:
                raise RuntimeError(f"콘텐츠 조립 실패: {assembly_result.get('error')}")
            self._log_step(
                "content_assembly",
                "완료",
                {
                    "segments_used": assembly_result["segments_used"],
                    "slide_count": assembly_result["slide_count"],
                },
            )
            deck_spec = assembly_result["deck"]
        else:
            self._log_step("outline_generation", "시작")
            outline_result = await outline_generation_tool._arun(
                context_text=context_text,
                topic=topic,
                max_slides=max_slides,
            )
            if not outline_result["success"]:
                raise RuntimeError(f"Outline 생성 실패: {outline_result.get('error')}")
            self._log_step(
                "outline_generation",
                "완료",
                {"slide_count": outline_result["slide_count"]},
            )
            deck_spec = outline_result["deck"]

        self._log_step("template_application", "시작")
        template_result = await template_application_tool._arun(
            deck_spec=deck_spec,
            template_path=template_path,
            text_box_mappings=options.get("text_box_mappings"),
            file_basename=options.get("file_basename"),
        )
        if not template_result["success"]:
            raise RuntimeError(f"템플릿 적용 실패: {template_result.get('error')}")
        self._log_step(
            "template_application",
            "완료",
            {
                "file_path": template_result["file_path"],
                "slides_processed": template_result["slides_processed"],
                "mapping_mode": template_result["mapping_mode"],
            },
        )
        return template_result

    async def _execute_style_transfer_strategy(
        self,
        topic: str,
        context_text: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Style transfer strategy which references an existing PPT."""

        logger.info("🎨 Style Transfer 전략 실행")
        reference_path = options.get("style_reference_path") or options.get("template_path")
        if not reference_path:
            raise ValueError("style_reference_path 옵션이 필요합니다")

        self._log_step("style_analysis", "시작")
        style_result = await style_analysis_tool._arun(template_path=reference_path)
        if not style_result["success"]:
            raise RuntimeError(f"스타일 분석 실패: {style_result.get('error')}")
        self._log_step(
            "style_analysis",
            "완료",
            {
                "color_palette": style_result.get("color_palette"),
                "font_families": style_result.get("fonts"),
            },
        )

        max_slides = int(options.get("max_slides", 10))
        self._log_step("outline_generation", "시작")
        outline_result = await outline_generation_tool._arun(
            context_text=context_text,
            topic=topic,
            max_slides=max_slides,
        )
        if not outline_result["success"]:
            raise RuntimeError(f"Outline 생성 실패: {outline_result.get('error')}")
        self._log_step(
            "outline_generation",
            "완료",
            {"slide_count": outline_result["slide_count"]},
        )

        deck_spec = outline_result["deck"]
        self._log_step("template_application", "시작")
        template_result = await template_application_tool._arun(
            deck_spec=deck_spec,
            template_path=reference_path,
            text_box_mappings=options.get("text_box_mappings"),
            file_basename=options.get("file_basename"),
        )
        if not template_result["success"]:
            raise RuntimeError(f"템플릿 적용 실패: {template_result.get('error')}")
        template_result["style_metadata"] = style_result.get("style_metadata", style_result)
        self._log_step(
            "template_application",
            "완료",
            {
                "file_path": template_result["file_path"],
                "slides_processed": template_result["slides_processed"],
                "mapping_mode": template_result["mapping_mode"],
                "style_reference": reference_path,
            },
        )
        return template_result

    def _log_step(self, tool_name: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        step = {
            "tool": tool_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._steps.append(step)
        logger.debug("📝 Step: %s - %s", tool_name, status)


presentation_agent = PresentationAgent()

__all__ = ["PresentationAgent", "presentation_agent"]

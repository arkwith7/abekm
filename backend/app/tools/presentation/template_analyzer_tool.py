"""Template Analyzer Tool - Analyze PPT template structure and capabilities."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.services.presentation.ppt_template_manager import template_manager


class TemplateAnalyzerInput(BaseModel):
    """Input schema for TemplateAnalyzerTool."""

    template_id: str = Field(..., description="Template ID to analyze")


class TemplateAnalyzerTool(BaseTool):
    """
    Analyze PPT template structure.
    
    Extracts metadata including:
    - Available layouts and placeholders
    - Slide count and structure
    - Text boxes and their positions
    - Color scheme and fonts
    """

    name: str = "template_analyzer_tool"
    description: str = (
        "Analyzes a PPT template structure. Returns available layouts, "
        "placeholders, text boxes, and design elements that can be used "
        "for content mapping."
    )
    args_schema: Type[BaseModel] = TemplateAnalyzerInput

    async def _arun(
        self,
        template_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Analyze template asynchronously.

        Args:
            template_id: Template identifier

        Returns:
            Dict with template metadata and structure
        """
        logger.info(f"🔍 [TemplateAnalyzer] 시작: template_id='{template_id}'")

        try:
            # Get template details
            template_details = template_manager.get_template_details(template_id)
            
            if not template_details:
                logger.error(f"❌ 템플릿을 찾을 수 없음: {template_id}")
                return {
                    "success": False,
                    "error": f"Template not found: {template_id}",
                    "template_id": template_id,
                }

            # Get template metadata
            metadata = template_manager.get_template_metadata(template_id)
            
            # Extract key information
            template_path = template_details.get('path')
            slide_count = 0
            layouts = []
            text_boxes = []
            
            if metadata:
                slide_count = len(metadata.get('slides', []))
                
                # Extract layout information
                for idx, slide in enumerate(metadata.get('slides', [])):
                    layout_name = slide.get('layout_name', f'Layout_{idx}')
                    elements = slide.get('elements', [])
                    
                    layouts.append({
                        'index': idx,
                        'name': layout_name,
                        'element_count': len(elements),
                        'has_textboxes': any(e.get('type') == 'textbox' for e in elements)
                    })
                    
                    # Collect text box information
                    for element in elements:
                        if element.get('type') == 'textbox':
                            text_boxes.append({
                                'slide_index': idx,
                                'element_id': element.get('id'),
                                'content': element.get('content', '')[:50],  # Preview
                                'position': element.get('position', {})
                            })

            result = {
                "success": True,
                "template_id": template_id,
                "template_name": template_details.get('name', ''),
                "template_path": template_path,
                "template_structure": {
                    "slide_count": slide_count,
                    "layouts": layouts,
                    "text_boxes": text_boxes[:20],
                },
                "slide_count": slide_count,
                "layouts": layouts,
                "text_boxes": text_boxes[:20],  # Limit to first 20
                "total_textboxes": len(text_boxes),
                "has_metadata": metadata is not None,
                "message": "템플릿 분석 완료. 다음 단계로 content_mapping_tool을 호출하여 아웃라인과 템플릿을 매핑하세요."
            }

            logger.info(
                f"✅ [TemplateAnalyzer] 완료: {slide_count}개 슬라이드, "
                f"{len(layouts)}개 레이아웃, {len(text_boxes)}개 텍스트박스"
            )

            return result

        except Exception as e:
            logger.error(f"❌ [TemplateAnalyzer] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "template_id": template_id,
            }

    def _run(self, *args, **kwargs):
        """Synchronous wrapper for async _arun."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(*args, **kwargs))


# Singleton instance
template_analyzer_tool = TemplateAnalyzerTool()

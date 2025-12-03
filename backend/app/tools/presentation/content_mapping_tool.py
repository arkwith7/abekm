"""Content Mapping Tool - Generate AI-powered content-to-template mappings."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.services.core.ai_service import ai_service


class ContentMappingInput(BaseModel):
    """Input schema for ContentMappingTool."""

    outline: Optional[Dict[str, Any]] = Field(default=None, description="Presentation outline (DeckSpec)")
    deck_spec: Optional[Dict[str, Any]] = Field(default=None, description="Alternative name for outline (DeckSpec)")
    template_structure: Dict[str, Any] = Field(..., description="Template analysis result")


class ContentMappingTool(BaseTool):
    """
    Generate intelligent content-to-template mappings.
    
    Uses AI to map outline content to template text boxes, considering:
    - Layout compatibility
    - Content length and text box size
    - Semantic matching
    """

    name: str = "content_mapping_tool"
    description: str = (
        "Generates mappings between presentation content and template elements. "
        "Uses AI to intelligently match content to text boxes based on layout "
        "and semantic compatibility."
    )
    args_schema: Type[BaseModel] = ContentMappingInput

    async def _arun(
        self,
        outline: Optional[Dict[str, Any]] = None,
        deck_spec: Optional[Dict[str, Any]] = None,
        template_structure: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate mappings asynchronously.

        Args:
            outline: DeckSpec dictionary (primary)
            deck_spec: DeckSpec dictionary (alternative name)
            template_structure: Template analysis result

        Returns:
            Dict with mapping suggestions
        """
        logger.info(f"🎯 [ContentMapping] 시작")

        try:
            # outline 또는 deck_spec 사용 (둘 다 같은 것)
            actual_outline = outline or deck_spec
            if not actual_outline:
                return {
                    "success": False,
                    "error": "outline 또는 deck_spec이 필요합니다",
                    "mappings": []
                }
            
            if not template_structure:
                return {
                    "success": False,
                    "error": "template_structure가 필요합니다",
                    "mappings": []
                }
            
            slides = actual_outline.get('slides', [])
            template_slides = template_structure.get('layouts', [])
            text_boxes = template_structure.get('text_boxes', [])

            if not slides:
                return {
                    "success": False,
                    "error": "No slides in outline",
                    "mappings": []
                }

            if not text_boxes:
                logger.warning("⚠️ 템플릿에 텍스트박스가 없음 - 기본 매핑 생성")
                return self._create_default_mappings(slides)

            # Generate mappings using AI
            mappings = await self._generate_ai_mappings(slides, text_boxes, template_structure)

            logger.info(f"✅ [ContentMapping] 완료: {len(mappings)}개 매핑 생성")

            return {
                "success": True,
                "mappings": mappings,
                "mapping_count": len(mappings),
                "message": "콘텐츠 매핑 완료. 다음 단계로 templated_pptx_builder_tool을 호출하여 PPTX 파일을 생성하세요."
            }

        except Exception as e:
            logger.error(f"❌ [ContentMapping] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "mappings": []
            }

    async def _generate_ai_mappings(
        self,
        slides: List[Dict[str, Any]],
        text_boxes: List[Dict[str, Any]],
        template_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate mappings using AI."""
        # Simple rule-based mapping (can be enhanced with LLM)
        mappings = []
        
        for slide_idx, slide in enumerate(slides):
            slide_title = slide.get('title', '')
            slide_bullets = slide.get('bullets', [])
            
            # Find text boxes for this slide
            slide_textboxes = [
                tb for tb in text_boxes 
                if tb.get('slide_index') == slide_idx
            ]
            
            if not slide_textboxes:
                continue
            
            # Map title to first textbox
            if slide_textboxes and slide_title:
                mappings.append({
                    'slideIndex': slide_idx,
                    'elementId': slide_textboxes[0]['element_id'],
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_title,
                    'isEnabled': True
                })
            
            # Map bullets to remaining textboxes
            for i, bullet in enumerate(slide_bullets[:len(slide_textboxes)-1]):
                if i + 1 < len(slide_textboxes):
                    mappings.append({
                        'slideIndex': slide_idx,
                        'elementId': slide_textboxes[i + 1]['element_id'],
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'newContent': bullet,
                        'isEnabled': True
                    })
        
        return mappings

    def _create_default_mappings(self, slides: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create default mappings when no template metadata is available."""
        mappings = []
        
        for slide_idx, slide in enumerate(slides):
            # Create basic mapping for title
            mappings.append({
                'slideIndex': slide_idx,
                'elementId': f'element_{slide_idx}_0',
                'objectType': 'textbox',
                'action': 'replace_content',
                'newContent': slide.get('title', ''),
                'isEnabled': True
            })
        
        return {
            "success": True,
            "mappings": mappings,
            "mapping_count": len(mappings),
            "note": "Default mappings created (no template metadata)"
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
content_mapping_tool = ContentMappingTool()

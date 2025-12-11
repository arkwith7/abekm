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

from app.services.presentation.user_template_manager import user_template_manager


class TemplateAnalyzerInput(BaseModel):
    """Input schema for TemplateAnalyzerTool."""

    template_id: str = Field(..., description="Template ID to analyze")
    user_id: Optional[int] = Field(default=None, description="User ID for user-specific templates")


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
        user_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Analyze template asynchronously.

        Args:
            template_id: Template identifier
            user_id: User ID for user-specific templates

        Returns:
            Dict with template metadata and structure
        """
        # 템플릿 ID 정규화: 공백을 언더스코어로 변환, 소문자
        normalized_template_id = template_id.lower().replace(' ', '_')
        logger.info(f"🔍 [TemplateAnalyzer] 시작: template_id='{template_id}' → normalized='{normalized_template_id}', user_id={user_id}")

        try:
            template_details = None
            metadata = None
            
            # Strategy 1: user_id가 주어진 경우, 해당 사용자의 템플릿 확인
            if user_id:
                template_details = user_template_manager.get_template_details(str(user_id), normalized_template_id)
                metadata = user_template_manager.get_template_metadata(str(user_id), normalized_template_id)
                if template_details:
                    logger.info(f"🔍 [TemplateAnalyzer] Found template in user {user_id}'s directory")
            
            # Strategy 2: 못 찾으면 템플릿 소유자 검색 (다른 사용자 템플릿)
            if not template_details:
                owner_id = user_template_manager.find_template_owner(normalized_template_id)
                if owner_id:
                    template_details = user_template_manager.get_template_details(owner_id, normalized_template_id)
                    metadata = user_template_manager.get_template_metadata(owner_id, normalized_template_id)
                    if template_details:
                        logger.info(f"🔍 [TemplateAnalyzer] Found template owned by user {owner_id}")
            
            # Strategy 3: 시스템 템플릿 매니저에서 검색 (legacy)
            if not template_details:
                from app.services.presentation.ppt_template_manager import template_manager
                template_details = template_manager.get_template_details(normalized_template_id)
                metadata = template_manager.get_template_metadata(normalized_template_id)
                if template_details:
                    logger.info(f"🔍 [TemplateAnalyzer] Found template in system templates")
            
            if not template_details:
                logger.error(f"❌ 템플릿을 찾을 수 없음: {template_id}")
                return {
                    "success": False,
                    "error": f"Template not found: {template_id}",
                    "template_id": template_id,
                }
            
            # Extract key information
            template_path = template_details.get('path')
            slide_count = 0
            layouts = []
            text_boxes = []
            slides_with_roles = []  # 슬라이드 역할 정보 포함
            
            if metadata:
                slide_count = len(metadata.get('slides', []))
                
                # Extract layout and role information
                for idx, slide in enumerate(metadata.get('slides', [])):
                    layout_name = slide.get('layout_name', f'Layout_{idx}')
                    role = slide.get('role', 'content')  # title, toc, content, section, thanks
                    role_confidence = slide.get('role_confidence', 0.5)
                    shapes = slide.get('shapes', [])
                    elements = slide.get('elements', shapes)  # shapes가 없으면 elements 사용
                    
                    layouts.append({
                        'index': idx,
                        'name': layout_name,
                        'role': role,
                        'role_confidence': role_confidence,
                        'element_count': len(elements),
                        'has_textboxes': any(
                            e.get('type', '').upper() in ['TEXT_BOX', 'TEXTBOX'] or 
                            e.get('name', '').startswith('textbox-')
                            for e in elements
                        )
                    })
                    
                    # 슬라이드 역할 정보 저장 (slide_type_matcher용)
                    slides_with_roles.append({
                        'index': slide.get('index', idx + 1),
                        'layout_name': layout_name,
                        'role': role,
                        'role_confidence': role_confidence,
                        'shapes_count': len(shapes),
                        'shapes': shapes  # 전체 shapes 정보 포함
                    })
                    
                    # Collect text box information (including element_role from metadata v3.0)
                    for element in elements:
                        element_type = element.get('type', '').upper()
                        element_name = element.get('name', '')
                        element_id = element.get('id', '')
                        
                        # textbox 또는 shape-X-X 형식의 요소 수집 (AUTO_SHAPE 포함)
                        is_textbox = element_type in ['TEXT_BOX', 'TEXTBOX'] or element_name.startswith('textbox-') or element_id.startswith('textbox-')
                        is_shape = element_id.startswith('shape-')
                        
                        if is_textbox or is_shape:
                            # 콘텐츠 추출
                            content = ''
                            if element.get('content'):
                                content = element.get('content', '')[:50]
                            elif element.get('text', {}).get('raw'):
                                content = element.get('text', {}).get('raw', '')[:50]
                            
                            text_boxes.append({
                                'slide_index': idx,
                                'element_id': element_id or element_name or f'element_{idx}',
                                'original_name': element.get('original_name', ''),  # PPT 내부 shape.name
                                'element_role': element.get('element_role', 'unknown'),  # AI Agent용 역할 정보
                                'content': content,
                                'position': {
                                    'left_px': element.get('left_px') or element.get('position', {}).get('left'),
                                    'top_px': element.get('top_px') or element.get('position', {}).get('top'),
                                    'width_px': element.get('width_px') or element.get('position', {}).get('width'),
                                    'height_px': element.get('height_px') or element.get('position', {}).get('height'),
                                },
                                'slide_role': role,  # 슬라이드 역할 (title, toc, content, etc.)
                                'is_fixed': element.get('is_fixed', False),  # 고정 요소 여부
                                'style': element.get('style', {})  # 스타일 정보
                            })

            result = {
                "success": True,
                "template_id": template_id,
                "template_name": template_details.get('name', ''),
                "template_path": template_path,
                "template_structure": {
                    "slide_count": slide_count,
                    "layouts": layouts,
                    "text_boxes": text_boxes[:50],  # 더 많은 텍스트박스 정보
                    "slides": slides_with_roles,  # slide_type_matcher용 전체 슬라이드 정보
                },
                "template_metadata": {
                    "slides": slides_with_roles,  # 전체 슬라이드 역할 정보
                },
                "slide_count": slide_count,
                "layouts": layouts,
                "text_boxes": text_boxes[:50],
                "total_textboxes": len(text_boxes),
                "has_metadata": metadata is not None,
                "message": "템플릿 분석 완료. 다음 단계로 slide_type_matcher_tool을 호출하여 슬라이드 유형을 매칭하세요."
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

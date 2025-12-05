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
    slide_matches: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="Slide type matching results from slide_type_matcher_tool"
    )


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
        slide_matches: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate mappings asynchronously.

        Args:
            outline: DeckSpec dictionary (primary)
            deck_spec: DeckSpec dictionary (alternative name)
            template_structure: Template analysis result
            slide_matches: Slide type matching results from slide_type_matcher_tool

        Returns:
            Dict with mapping suggestions
        """
        logger.info(f"🎯 [ContentMapping] 시작: slide_matches={len(slide_matches) if slide_matches else 0}개")

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

            # slide_matches가 있으면 이를 활용하여 매핑 생성
            if slide_matches:
                logger.info(f"📋 slide_matches 활용하여 매핑 생성")
                mappings = await self._generate_matched_mappings(
                    slides, text_boxes, template_structure, slide_matches
                )
            else:
                # 기존 방식: AI로 매핑 생성
                logger.info(f"📋 기존 방식으로 매핑 생성 (slide_matches 없음)")
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
        """Generate mappings using AI - template의 실제 element_id를 사용."""
        mappings = []
        
        # 슬라이드별 텍스트박스 그룹화
        textboxes_by_slide: Dict[int, List[Dict[str, Any]]] = {}
        for tb in text_boxes:
            slide_idx = tb.get('slide_index', 0)
            if slide_idx not in textboxes_by_slide:
                textboxes_by_slide[slide_idx] = []
            textboxes_by_slide[slide_idx].append(tb)
        
        # 각 슬라이드별로 매핑 생성
        for slide_idx, slide in enumerate(slides):
            slide_title = slide.get('title', '')
            slide_key_message = slide.get('key_message', '')
            slide_bullets = slide.get('bullets', [])
            
            # 해당 슬라이드의 텍스트박스 가져오기
            # 템플릿 슬라이드 개수보다 outline 슬라이드가 많을 수 있으므로 순환 처리
            template_slide_count = len(textboxes_by_slide) if textboxes_by_slide else 1
            template_slide_idx = slide_idx % template_slide_count if template_slide_count > 0 else 0
            
            slide_textboxes = textboxes_by_slide.get(template_slide_idx, [])
            
            if not slide_textboxes:
                logger.warning(f"⚠️ 슬라이드 {slide_idx}에 매핑할 텍스트박스 없음")
                continue
            
            # 텍스트박스를 역할별로 분류 (title 역할이 있으면 분리)
            title_boxes = []
            content_boxes = []
            
            for tb in slide_textboxes:
                role = tb.get('role', '').lower()
                element_id = tb.get('element_id', '')
                
                # title 역할이거나, element_id에 title이 포함되어 있거나, 첫 번째 텍스트박스
                if role == 'title' or 'title' in element_id.lower():
                    title_boxes.append(tb)
                else:
                    content_boxes.append(tb)
            
            # title 박스가 없으면 첫 번째를 title로 사용
            if not title_boxes and slide_textboxes:
                title_boxes = [slide_textboxes[0]]
                content_boxes = slide_textboxes[1:]
            
            logger.info(f"📋 슬라이드 {slide_idx}: title_boxes={len(title_boxes)}, content_boxes={len(content_boxes)}")
            
            # 1. Title 매핑 (실제 element_id 사용)
            if title_boxes and slide_title:
                actual_element_id = title_boxes[0].get('element_id', f'textbox-{slide_idx}-0')
                mappings.append({
                    'slideIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_title,
                    'isEnabled': True
                })
                logger.info(f"✅ Title 매핑: slide={slide_idx}, elementId='{actual_element_id}', content='{slide_title[:30]}...'")
            
            # 2. Key Message 매핑 (첫 번째 content box에)
            if content_boxes and slide_key_message:
                actual_element_id = content_boxes[0].get('element_id', f'textbox-{slide_idx}-1')
                mappings.append({
                    'slideIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_key_message,
                    'isEnabled': True
                })
                logger.info(f"✅ KeyMessage 매핑: slide={slide_idx}, elementId='{actual_element_id}'")
            
            # 3. Bullets 매핑 (나머지 content boxes에)
            for i, bullet in enumerate(slide_bullets):
                # key_message가 있으면 1부터, 없으면 0부터
                box_idx = i + 1 if slide_key_message else i
                
                if box_idx < len(content_boxes):
                    actual_element_id = content_boxes[box_idx].get('element_id', f'textbox-{slide_idx}-{box_idx+1}')
                    mappings.append({
                        'slideIndex': slide_idx,
                        'elementId': actual_element_id,
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'newContent': bullet,
                        'isEnabled': True
                    })
                    logger.info(f"✅ Bullet 매핑: slide={slide_idx}, elementId='{actual_element_id}', content='{str(bullet)[:30]}...'")
        
        return mappings

    async def _generate_matched_mappings(
        self,
        slides: List[Dict[str, Any]],
        text_boxes: List[Dict[str, Any]],
        template_structure: Dict[str, Any],
        slide_matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        slide_type_matcher_tool의 결과를 활용하여 매핑 생성.
        
        slide_matches 구조:
        [
            {
                "outline_index": 0,
                "outline_title": "제목",
                "outline_role": "title",
                "template_index": 0,
                "template_role": "title",
                "match_reason": "제목 슬라이드 역할 매칭"
            },
            ...
        ]
        """
        mappings = []
        
        # 슬라이드별 텍스트박스 그룹화 (template_index 기준)
        textboxes_by_slide: Dict[int, List[Dict[str, Any]]] = {}
        for tb in text_boxes:
            slide_idx = tb.get('slide_index', 0)
            if slide_idx not in textboxes_by_slide:
                textboxes_by_slide[slide_idx] = []
            textboxes_by_slide[slide_idx].append(tb)
        
        logger.info(f"📋 텍스트박스 그룹화: {len(textboxes_by_slide)}개 슬라이드")
        
        # slide_matches를 딕셔너리로 변환 (outline_index -> template_index)
        outline_to_template: Dict[int, int] = {}
        for match in slide_matches:
            outline_idx = match.get('outline_index', 0)
            template_idx = match.get('template_index', 0)
            outline_to_template[outline_idx] = template_idx
            logger.info(f"  매칭: outline[{outline_idx}] -> template[{template_idx}] ({match.get('match_reason', '')})")
        
        # 각 outline 슬라이드별로 매핑 생성
        for slide_idx, slide in enumerate(slides):
            slide_title = slide.get('title', '')
            slide_key_message = slide.get('key_message', '')
            slide_bullets = slide.get('bullets', [])
            
            # slide_matches에서 해당 outline 슬라이드의 템플릿 슬라이드 인덱스 가져오기
            template_slide_idx = outline_to_template.get(slide_idx)
            
            if template_slide_idx is None:
                # 매칭이 없으면 순환 처리
                template_slide_count = len(textboxes_by_slide) if textboxes_by_slide else 1
                template_slide_idx = slide_idx % template_slide_count if template_slide_count > 0 else 0
                logger.warning(f"⚠️ outline[{slide_idx}]에 대한 매칭 없음, 순환 처리: template[{template_slide_idx}]")
            
            slide_textboxes = textboxes_by_slide.get(template_slide_idx, [])
            
            if not slide_textboxes:
                logger.warning(f"⚠️ template[{template_slide_idx}]에 텍스트박스 없음")
                continue
            
            # 텍스트박스를 역할별로 분류
            title_boxes = []
            content_boxes = []
            
            for tb in slide_textboxes:
                role = tb.get('role', '').lower()
                element_id = tb.get('element_id', '')
                
                if role == 'title' or 'title' in element_id.lower():
                    title_boxes.append(tb)
                else:
                    content_boxes.append(tb)
            
            # title 박스가 없으면 첫 번째를 title로 사용
            if not title_boxes and slide_textboxes:
                title_boxes = [slide_textboxes[0]]
                content_boxes = slide_textboxes[1:]
            
            logger.info(f"📋 outline[{slide_idx}] -> template[{template_slide_idx}]: title_boxes={len(title_boxes)}, content_boxes={len(content_boxes)}")
            
            # 1. Title 매핑
            if title_boxes and slide_title:
                actual_element_id = title_boxes[0].get('element_id', f'textbox-{template_slide_idx}-0')
                mappings.append({
                    'slideIndex': template_slide_idx,  # 템플릿 슬라이드 인덱스 사용!
                    'outlineIndex': slide_idx,  # 원본 outline 인덱스도 저장
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_title,
                    'isEnabled': True
                })
                logger.info(f"✅ Title 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
            
            # 2. Key Message 매핑
            if content_boxes and slide_key_message:
                actual_element_id = content_boxes[0].get('element_id', f'textbox-{template_slide_idx}-1')
                mappings.append({
                    'slideIndex': template_slide_idx,
                    'outlineIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_key_message,
                    'isEnabled': True
                })
                logger.info(f"✅ KeyMessage 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
            
            # 3. Bullets 매핑
            for i, bullet in enumerate(slide_bullets):
                box_idx = i + 1 if slide_key_message else i
                
                if box_idx < len(content_boxes):
                    actual_element_id = content_boxes[box_idx].get('element_id', f'textbox-{template_slide_idx}-{box_idx+1}')
                    mappings.append({
                        'slideIndex': template_slide_idx,
                        'outlineIndex': slide_idx,
                        'elementId': actual_element_id,
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'newContent': bullet,
                        'isEnabled': True
                    })
                    logger.info(f"✅ Bullet 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
        
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

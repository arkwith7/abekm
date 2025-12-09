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
        """Generate mappings using AI - element_role 기반 매핑 (v3.0)."""
        mappings = []
        
        # 슬라이드별 텍스트박스 그룹화 및 역할별 분류
        textboxes_by_slide: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
        for tb in text_boxes:
            slide_idx = tb.get('slide_index', 0)
            if slide_idx not in textboxes_by_slide:
                textboxes_by_slide[slide_idx] = {
                    'title': [],      # main_title, slide_title
                    'subtitle': [],   # subtitle, metadata
                    'key_message': [],  # key_message
                    'body': [],       # body_content, bullet_item, content_item
                    'toc': [],        # toc_item, toc_number
                    'other': []       # 그 외
                }
            
            # is_fixed가 True인 요소는 매핑 대상에서 제외
            if tb.get('is_fixed', False):
                continue
            
            element_role = tb.get('element_role', 'unknown')
            
            # element_role에 따라 분류
            if element_role in ['main_title', 'slide_title']:
                textboxes_by_slide[slide_idx]['title'].append(tb)
            elif element_role in ['subtitle', 'metadata']:
                textboxes_by_slide[slide_idx]['subtitle'].append(tb)
            elif element_role == 'key_message':
                textboxes_by_slide[slide_idx]['key_message'].append(tb)
            elif element_role in ['body_content', 'bullet_item', 'content_item', 'numbered_card']:
                textboxes_by_slide[slide_idx]['body'].append(tb)
            elif element_role in ['toc_item', 'toc_number']:
                textboxes_by_slide[slide_idx]['toc'].append(tb)
            else:
                textboxes_by_slide[slide_idx]['other'].append(tb)
        
        logger.info(f"📋 텍스트박스 역할별 분류 완료: {len(textboxes_by_slide)}개 슬라이드")
        
        # 각 슬라이드별로 매핑 생성
        for slide_idx, slide in enumerate(slides):
            slide_title = slide.get('title', '')
            slide_key_message = slide.get('key_message', '')
            slide_bullets = slide.get('bullets', [])
            slide_subtitle = slide.get('subtitle', '')
            
            # 템플릿 슬라이드 순환 처리
            template_slide_count = len(textboxes_by_slide) if textboxes_by_slide else 1
            template_slide_idx = slide_idx % template_slide_count if template_slide_count > 0 else 0
            
            slide_boxes = textboxes_by_slide.get(template_slide_idx, {})
            
            if not slide_boxes:
                logger.warning(f"⚠️ 슬라이드 {slide_idx}에 매핑할 텍스트박스 없음")
                continue
            
            logger.info(f"📋 슬라이드 {slide_idx}: title={len(slide_boxes.get('title', []))}, "
                       f"subtitle={len(slide_boxes.get('subtitle', []))}, "
                       f"key_message={len(slide_boxes.get('key_message', []))}, "
                       f"body={len(slide_boxes.get('body', []))}, "
                       f"toc={len(slide_boxes.get('toc', []))}")
            
            # 1. Title 매핑 (main_title, slide_title 역할)
            title_boxes = slide_boxes.get('title', [])
            if title_boxes and slide_title:
                actual_element_id = title_boxes[0].get('element_id', f'textbox-{slide_idx}-0')
                mappings.append({
                    'slideIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_title,
                    'isEnabled': True,
                    'target_role': 'title'
                })
                logger.info(f"✅ Title 매핑: slide={slide_idx}, elementId='{actual_element_id}'")
            
            # 2. Subtitle 매핑 (subtitle, metadata 역할)
            subtitle_boxes = slide_boxes.get('subtitle', [])
            if subtitle_boxes and slide_subtitle:
                actual_element_id = subtitle_boxes[0].get('element_id', f'textbox-{slide_idx}-1')
                mappings.append({
                    'slideIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_subtitle,
                    'isEnabled': True,
                    'target_role': 'subtitle'
                })
                logger.info(f"✅ Subtitle 매핑: slide={slide_idx}, elementId='{actual_element_id}'")
            
            # 3. Key Message 매핑 (key_message 역할)
            key_message_boxes = slide_boxes.get('key_message', [])
            if key_message_boxes and slide_key_message:
                actual_element_id = key_message_boxes[0].get('element_id', f'textbox-{slide_idx}-2')
                mappings.append({
                    'slideIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_key_message,
                    'isEnabled': True,
                    'target_role': 'key_message'
                })
                logger.info(f"✅ KeyMessage 매핑: slide={slide_idx}, elementId='{actual_element_id}'")
            elif slide_key_message:
                # key_message 역할 박스가 없으면 body 첫 번째에 매핑
                body_boxes = slide_boxes.get('body', [])
                if body_boxes:
                    actual_element_id = body_boxes[0].get('element_id', f'textbox-{slide_idx}-3')
                    mappings.append({
                        'slideIndex': slide_idx,
                        'elementId': actual_element_id,
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'newContent': slide_key_message,
                        'isEnabled': True,
                        'target_role': 'key_message_fallback'
                    })
                    logger.info(f"✅ KeyMessage (fallback to body): slide={slide_idx}, elementId='{actual_element_id}'")
            
            # 4. Bullets/Body 매핑 (body_content, bullet_item 역할)
            body_boxes = slide_boxes.get('body', [])
            # key_message가 body에 매핑되었으면 offset
            body_offset = 1 if (not key_message_boxes and slide_key_message) else 0
            
            for i, bullet in enumerate(slide_bullets):
                box_idx = i + body_offset
                if box_idx < len(body_boxes):
                    actual_element_id = body_boxes[box_idx].get('element_id', f'textbox-{slide_idx}-{box_idx+3}')
                    mappings.append({
                        'slideIndex': slide_idx,
                        'elementId': actual_element_id,
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'newContent': bullet,
                        'isEnabled': True,
                        'target_role': 'body'
                    })
                    logger.info(f"✅ Body 매핑: slide={slide_idx}, elementId='{actual_element_id}'")
        
        return mappings

    async def _generate_matched_mappings(
        self,
        slides: List[Dict[str, Any]],
        text_boxes: List[Dict[str, Any]],
        template_structure: Dict[str, Any],
        slide_matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        slide_type_matcher_tool의 결과를 활용하여 매핑 생성 (element_role 기반 v3.0).
        
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
        
        # 슬라이드별 텍스트박스를 element_role로 분류
        textboxes_by_slide: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
        for tb in text_boxes:
            slide_idx = tb.get('slide_index', 0)
            if slide_idx not in textboxes_by_slide:
                textboxes_by_slide[slide_idx] = {
                    'title': [],      # main_title, slide_title
                    'subtitle': [],   # subtitle, metadata
                    'key_message': [],  # key_message
                    'body': [],       # body_content, bullet_item, content_item, numbered_card
                    'toc': [],        # toc_item, toc_number
                    'other': []       # 그 외
                }
            
            # is_fixed가 True인 요소는 매핑 대상에서 제외
            if tb.get('is_fixed', False):
                continue
            
            element_role = tb.get('element_role', 'unknown')
            
            # element_role에 따라 분류
            if element_role in ['main_title', 'slide_title']:
                textboxes_by_slide[slide_idx]['title'].append(tb)
            elif element_role in ['subtitle', 'metadata']:
                textboxes_by_slide[slide_idx]['subtitle'].append(tb)
            elif element_role == 'key_message':
                textboxes_by_slide[slide_idx]['key_message'].append(tb)
            elif element_role in ['body_content', 'bullet_item', 'content_item', 'numbered_card']:
                textboxes_by_slide[slide_idx]['body'].append(tb)
            elif element_role in ['toc_item', 'toc_number']:
                textboxes_by_slide[slide_idx]['toc'].append(tb)
            else:
                textboxes_by_slide[slide_idx]['other'].append(tb)
        
        logger.info(f"📋 텍스트박스 역할별 분류: {len(textboxes_by_slide)}개 슬라이드")
        
        # slide_matches를 딕셔너리로 변환 (outline_index -> template_index)
        outline_to_template: Dict[int, int] = {}
        for match in slide_matches:
            outline_idx = match.get('outline_index', 0)
            template_idx = match.get('template_index', 0)
            outline_to_template[outline_idx] = template_idx
            logger.info(f"  매칭: outline[{outline_idx}] -> template[{template_idx}] ({match.get('match_reason', '')})")
        
        # 목차(TOC) 슬라이드가 아닌 슬라이드들의 제목 목록 수집 (목차 내용 생성용)
        non_toc_slides_titles = []
        for slide in slides:
            slide_role = slide.get('role', '').lower()
            slide_title = slide.get('title', '')
            if slide_role not in ['toc', 'title', 'closing', 'thank_you', 'qa']:
                if slide_title and '목차' not in slide_title:
                    non_toc_slides_titles.append(slide_title)
        
        logger.info(f"📋 목차용 슬라이드 제목 목록: {non_toc_slides_titles}")
        
        # 각 outline 슬라이드별로 매핑 생성
        for slide_idx, slide in enumerate(slides):
            slide_title = slide.get('title', '')
            slide_key_message = slide.get('key_message', '')
            slide_bullets = slide.get('bullets', [])
            slide_subtitle = slide.get('subtitle', '')
            slide_role = slide.get('role', '').lower()
            
            # 목차 슬라이드 감지
            is_toc_slide = (
                slide_role == 'toc' or 
                '목차' in slide_title or 
                'contents' in slide_title.lower() or
                'table of contents' in slide_title.lower()
            )
            
            if is_toc_slide:
                logger.info(f"📑 목차 슬라이드 감지: outline[{slide_idx}] '{slide_title}'")
                slide_bullets = [f"{i+1:02d}. {title}" for i, title in enumerate(non_toc_slides_titles)]
                logger.info(f"📑 목차 내용 생성: {slide_bullets}")
            
            # slide_matches에서 템플릿 슬라이드 인덱스 가져오기
            template_slide_idx = outline_to_template.get(slide_idx)
            if template_slide_idx is None:
                template_slide_count = len(textboxes_by_slide) if textboxes_by_slide else 1
                template_slide_idx = slide_idx % template_slide_count if template_slide_count > 0 else 0
                logger.warning(f"⚠️ outline[{slide_idx}]에 대한 매칭 없음, 순환 처리: template[{template_slide_idx}]")
            
            slide_boxes = textboxes_by_slide.get(template_slide_idx, {})
            if not slide_boxes:
                logger.warning(f"⚠️ template[{template_slide_idx}]에 텍스트박스 없음")
                continue
            
            logger.info(f"📋 outline[{slide_idx}] -> template[{template_slide_idx}]: "
                       f"title={len(slide_boxes.get('title', []))}, "
                       f"key_message={len(slide_boxes.get('key_message', []))}, "
                       f"body={len(slide_boxes.get('body', []))}")
            
            # 1. Title 매핑 (main_title, slide_title 역할)
            title_boxes = slide_boxes.get('title', [])
            if title_boxes and slide_title:
                actual_element_id = title_boxes[0].get('element_id', f'textbox-{template_slide_idx}-0')
                mappings.append({
                    'slideIndex': template_slide_idx,
                    'outlineIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_title,
                    'isEnabled': True,
                    'target_role': 'title'
                })
                logger.info(f"✅ Title 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
            
            # 2. Subtitle 매핑 (subtitle, metadata 역할)
            subtitle_boxes = slide_boxes.get('subtitle', [])
            if subtitle_boxes and slide_subtitle:
                actual_element_id = subtitle_boxes[0].get('element_id', f'textbox-{template_slide_idx}-1')
                mappings.append({
                    'slideIndex': template_slide_idx,
                    'outlineIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_subtitle,
                    'isEnabled': True,
                    'target_role': 'subtitle'
                })
                logger.info(f"✅ Subtitle 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
            
            # 3. Key Message 매핑 (key_message 역할)
            key_message_boxes = slide_boxes.get('key_message', [])
            if key_message_boxes and slide_key_message:
                actual_element_id = key_message_boxes[0].get('element_id', f'textbox-{template_slide_idx}-2')
                mappings.append({
                    'slideIndex': template_slide_idx,
                    'outlineIndex': slide_idx,
                    'elementId': actual_element_id,
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'newContent': slide_key_message,
                    'isEnabled': True,
                    'target_role': 'key_message'
                })
                logger.info(f"✅ KeyMessage 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
            elif slide_key_message:
                # key_message 역할 박스가 없으면 body 첫 번째에 매핑
                body_boxes = slide_boxes.get('body', [])
                if body_boxes:
                    actual_element_id = body_boxes[0].get('element_id', f'textbox-{template_slide_idx}-3')
                    mappings.append({
                        'slideIndex': template_slide_idx,
                        'outlineIndex': slide_idx,
                        'elementId': actual_element_id,
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'newContent': slide_key_message,
                        'isEnabled': True,
                        'target_role': 'key_message_fallback'
                    })
                    logger.info(f"✅ KeyMessage (fallback): outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
            
            # 4. TOC 항목 매핑 (목차 슬라이드인 경우)
            if is_toc_slide:
                toc_boxes = slide_boxes.get('toc', [])
                # toc_number와 toc_item 분리
                toc_numbers = [tb for tb in toc_boxes if tb.get('element_role') == 'toc_number']
                toc_items = [tb for tb in toc_boxes if tb.get('element_role') == 'toc_item']
                
                for i, bullet in enumerate(slide_bullets):
                    # 번호 부분과 텍스트 부분 분리
                    parts = bullet.split('. ', 1)
                    if len(parts) == 2:
                        num_part, text_part = parts
                        
                        # toc_number 매핑
                        if i < len(toc_numbers):
                            actual_element_id = toc_numbers[i].get('element_id')
                            mappings.append({
                                'slideIndex': template_slide_idx,
                                'outlineIndex': slide_idx,
                                'elementId': actual_element_id,
                                'objectType': 'textbox',
                                'action': 'replace_content',
                                'newContent': num_part,
                                'isEnabled': True,
                                'target_role': 'toc_number'
                            })
                        
                        # toc_item 매핑
                        if i < len(toc_items):
                            actual_element_id = toc_items[i].get('element_id')
                            mappings.append({
                                'slideIndex': template_slide_idx,
                                'outlineIndex': slide_idx,
                                'elementId': actual_element_id,
                                'objectType': 'textbox',
                                'action': 'replace_content',
                                'newContent': text_part,
                                'isEnabled': True,
                                'target_role': 'toc_item'
                            })
                            logger.info(f"✅ TOC 매핑: {num_part}. {text_part}")
            else:
                # 5. Body/Bullets 매핑 (일반 슬라이드)
                body_boxes = slide_boxes.get('body', [])
                body_offset = 1 if (not key_message_boxes and slide_key_message) else 0
                
                for i, bullet in enumerate(slide_bullets):
                    box_idx = i + body_offset
                    if box_idx < len(body_boxes):
                        actual_element_id = body_boxes[box_idx].get('element_id', f'textbox-{template_slide_idx}-{box_idx+3}')
                        mappings.append({
                            'slideIndex': template_slide_idx,
                            'outlineIndex': slide_idx,
                            'elementId': actual_element_id,
                            'objectType': 'textbox',
                            'action': 'replace_content',
                            'newContent': bullet,
                            'isEnabled': True,
                            'target_role': 'body'
                        })
                        logger.info(f"✅ Body 매핑: outline[{slide_idx}] -> template[{template_slide_idx}].{actual_element_id}")
        
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

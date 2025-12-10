"""Templated PPTX Builder Tool - Build PPTX using template with mappings."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.services.presentation.templated_ppt_generator_service import templated_ppt_service
from app.services.presentation.ppt_models import DeckSpec
from app.services.presentation.user_template_manager import user_template_manager


class TemplatedPPTXBuilderInput(BaseModel):
    """Input schema for TemplatedPPTXBuilderTool."""

    deck_spec: Dict[str, Any] = Field(..., description="DeckSpec dictionary")
    template_id: str = Field(..., description="Template ID to use")
    mappings: Optional[List[Dict[str, Any]]] = Field(default=None, description="Content mappings")
    slide_matches: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="Slide type matching results from slide_type_matcher_tool"
    )
    file_basename: Optional[str] = Field(default=None, description="Base filename")
    user_id: Optional[int] = Field(default=None, description="User ID for user-specific templates")


class TemplatedPPTXBuilderTool(BaseTool):
    """
    Build PPTX file using template with content mappings.
    
    Applies AI-generated outline to a pre-designed template while
    preserving the template's styling and layout.
    """

    name: str = "templated_pptx_builder_tool"
    description: str = (
        "Builds a PPTX file using a template with content mappings. "
        "Applies outline content to template elements while preserving "
        "template design and styling."
    )
    args_schema: Type[BaseModel] = TemplatedPPTXBuilderInput

    def _remap_element_ids(
        self,
        mappings: List[Dict[str, Any]],
        template_details: Dict[str, Any],
        deck_spec: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        AI가 생성한 generic element ID (title, content1 등)를 
        템플릿의 실제 element ID (textbox-0-0 등)로 재매핑.
        """
        # 템플릿 메타데이터에서 슬라이드별 텍스트박스 정보 가져오기
        metadata = template_details.get('metadata', {})
        slides_meta = metadata.get('slides', [])
        
        logger.info(f"📋 [TemplatedBuilder] 메타데이터 slides 수: {len(slides_meta)}")
        
        if not slides_meta:
            logger.warning("⚠️ [TemplatedBuilder] 템플릿 메타데이터 없음 - 매핑 재매핑 불가, 원본 매핑 사용")
            return mappings
        
        # 슬라이드별 텍스트박스 element_id 맵 구축
        # 메타데이터 구조: slides[].shapes[] 에서 type이 TEXT_BOX인 것들의 name
        slide_textboxes: Dict[int, List[str]] = {}
        for slide_meta in slides_meta:
            slide_idx = slide_meta.get('index', 1) - 1  # 1-based to 0-based
            shapes = slide_meta.get('shapes', [])
            
            # TEXT_BOX 타입의 shape들의 name을 element_id로 사용
            textbox_ids = []
            for shape in shapes:
                shape_type = shape.get('type', '').upper()  # 대소문자 무시
                shape_name = shape.get('name', '')
                # TEXT_BOX 타입이거나 textbox-로 시작하는 이름
                if shape_type == 'TEXT_BOX' or shape_type == 'TEXTBOX' or shape_name.startswith('textbox-'):
                    textbox_ids.append(shape_name)
            
            slide_textboxes[slide_idx] = textbox_ids
            if textbox_ids:
                logger.debug(f"  슬라이드 {slide_idx}: {len(textbox_ids)}개 텍스트박스 - {textbox_ids[:3]}...")
        
        textbox_summary = {k: len(v) for k, v in slide_textboxes.items()}
        logger.info(f"📋 [TemplatedBuilder] 슬라이드별 텍스트박스 수: {textbox_summary}")
        
        # 매핑이 이미 실제 element ID를 사용하는 경우 그대로 반환
        # (content_mapping_tool이 이미 올바른 ID를 생성한 경우)
        if mappings:
            first_element_id = mappings[0].get('elementId', '')
            logger.info(f"📋 [TemplatedBuilder] 첫 번째 매핑 elementId: '{first_element_id}'")
            if first_element_id.startswith('textbox-'):
                logger.info(f"✅ [TemplatedBuilder] 매핑이 이미 실제 element ID 사용 - 재매핑 불필요")
                return mappings
        
        # 매핑 재매핑
        remapped_mappings = []
        template_slide_count = len(slide_textboxes)
        
        for mapping in mappings:
            slide_idx = mapping.get('slideIndex', 0)
            element_id = mapping.get('elementId', '')
            new_content = mapping.get('newContent', '')
            
            if template_slide_count == 0:
                logger.warning(f"⚠️ 템플릿 슬라이드 없음 - 매핑 건너뜀")
                continue
            
            # 🆕 전략 C: 슬라이드 인덱스가 템플릿을 초과해도 그대로 유지
            # 서비스 레이어에서 슬라이드 복제를 처리함
            target_slide_idx = slide_idx
            
            # 단, element ID 매핑을 위해 참조할 템플릿 슬라이드 결정
            # 초과 슬라이드는 content 슬라이드의 element 구조를 참조
            reference_slide_idx = slide_idx if slide_idx < template_slide_count else self._find_content_slide_idx(slide_textboxes)
            available_ids = slide_textboxes.get(reference_slide_idx, [])
            
            if not available_ids:
                logger.warning(f"⚠️ 슬라이드 {slide_idx} (참조: {reference_slide_idx})에 사용 가능한 텍스트박스 없음")
                continue
            
            # Generic ID를 실제 ID로 매핑
            actual_element_id = element_id
            
            # 이미 실제 ID 형식인 경우 (textbox-0-0 등) 그대로 사용
            if element_id.startswith('textbox-') or element_id in available_ids:
                actual_element_id = element_id
            else:
                # title, subtitle, content1, content2 등의 generic ID 처리
                element_lower = element_id.lower()
                if element_lower == 'title':
                    actual_element_id = available_ids[0] if available_ids else element_id
                elif element_lower == 'subtitle':
                    actual_element_id = available_ids[1] if len(available_ids) > 1 else (available_ids[0] if available_ids else element_id)
                elif element_lower.startswith('content'):
                    # content1, content2, content3... -> 해당 인덱스의 텍스트박스
                    try:
                        content_num = int(element_lower.replace('content', ''))
                        idx = content_num  # content1 -> index 1, content2 -> index 2
                        if idx < len(available_ids):
                            actual_element_id = available_ids[idx]
                        elif available_ids:
                            # 범위 초과시 마지막 텍스트박스 사용
                            actual_element_id = available_ids[-1]
                    except ValueError:
                        pass
            
            if actual_element_id != element_id:
                logger.info(f"🔄 Element ID 재매핑: '{element_id}' -> '{actual_element_id}' (slide {slide_idx})")
            
            remapped_mappings.append({
                **mapping,
                'elementId': actual_element_id,
                'slideIndex': target_slide_idx  # 원본 슬라이드 인덱스 유지
            })
        
        return remapped_mappings

    def _find_content_slide_idx(self, slide_textboxes: Dict[int, List[str]]) -> int:
        """content 슬라이드 인덱스 찾기 (가장 많은 텍스트박스를 가진 중간 슬라이드)"""
        if not slide_textboxes:
            return 0
        
        max_count = 0
        best_idx = 1  # 기본값: 두 번째 슬라이드
        
        for idx, textboxes in slide_textboxes.items():
            # 첫 번째와 마지막 슬라이드 제외
            if idx == 0 or idx == max(slide_textboxes.keys()):
                continue
            
            if len(textboxes) > max_count:
                max_count = len(textboxes)
                best_idx = idx
        
        return best_idx

    async def _arun(
        self,
        deck_spec: Dict[str, Any],
        template_id: str,
        mappings: Optional[List[Dict[str, Any]]] = None,
        slide_matches: Optional[List[Dict[str, Any]]] = None,
        file_basename: Optional[str] = None,
        user_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build PPTX file asynchronously.

        Args:
            deck_spec: DeckSpec dictionary
            template_id: Template identifier
            mappings: Content-to-template mappings
            slide_matches: Slide type matching results (which template slides to use/skip)
            file_basename: Optional base filename
            user_id: User ID for user-specific templates

        Returns:
            Dict with file path and metadata
        """
        logger.info(
            f"🏗️ [TemplatedBuilder] 시작: template_id='{template_id}', "
            f"mappings={len(mappings) if mappings else 0}, "
            f"slide_matches={len(slide_matches) if slide_matches else 0}, user_id={user_id}"
        )

        try:
            # Parse DeckSpec
            spec = DeckSpec(**deck_spec)
            
            template_details = None
            
            # Strategy 1: user_id가 주어진 경우, 해당 사용자의 템플릿 확인
            if user_id:
                template_details = user_template_manager.get_template_details(str(user_id), template_id)
                if template_details:
                    logger.info(f"🏗️ [TemplatedBuilder] Found template in user {user_id}'s directory")
            
            # Strategy 2: 못 찾으면 템플릿 소유자 검색 (다른 사용자 템플릿)
            if not template_details:
                owner_id = user_template_manager.find_template_owner(template_id)
                if owner_id:
                    template_details = user_template_manager.get_template_details(owner_id, template_id)
                    if template_details:
                        logger.info(f"🏗️ [TemplatedBuilder] Found template owned by user {owner_id}")
            
            # Strategy 3: 시스템 템플릿 매니저에서 검색 (legacy)
            if not template_details:
                from app.services.presentation.ppt_template_manager import template_manager
                template_details = template_manager.get_template_details(template_id)
                if template_details:
                    logger.info(f"🏗️ [TemplatedBuilder] Found template in system templates")
            
            if not template_details:
                return {
                    "success": False,
                    "error": f"Template not found: {template_id}",
                    "file_path": None,
                }
            
            # Get template path
            template_path = template_details.get('cleaned_template_path') or template_details.get('path')
            
            if not template_path or not Path(template_path).exists():
                return {
                    "success": False,
                    "error": f"Template file not found: {template_path}",
                    "file_path": None,
                }
            
            # 🆕 매핑 element ID 재매핑 (generic ID -> 실제 템플릿 ID)
            if mappings:
                original_count = len(mappings)
                mappings = self._remap_element_ids(mappings, template_details, deck_spec)
                logger.info(f"🔄 [TemplatedBuilder] 매핑 재매핑 완료: {original_count}개 -> {len(mappings)}개")
            
            # 🆕 slide_matches에서 사용할 슬라이드 인덱스와 사용하지 않을 슬라이드 인덱스 추출
            used_template_indices = None
            unused_template_indices = None
            if slide_matches:
                used_template_indices = sorted(set(
                    m.get('template_index', 0) for m in slide_matches
                ))
                logger.info(f"📋 [TemplatedBuilder] 사용할 템플릿 슬라이드: {used_template_indices}")
            
            # 🆕 template_metadata 추출 (매핑되지 않은 요소 클리어용)
            template_metadata = template_details.get('metadata')
            
            # Build PPTX with mappings
            file_path = templated_ppt_service.build_enhanced_pptx_with_slide_management(
                spec=spec,
                file_basename=file_basename,
                custom_template_path=template_path,
                user_template_id=template_details.get('dynamic_template_id') or template_details.get('id'),
                text_box_mappings=mappings,
                content_segments=None,
                slide_management=None,
                used_template_indices=used_template_indices,
                template_metadata=template_metadata,  # 🆕 메타데이터 직접 전달
            )
            
            logger.info(f"✅ [TemplatedBuilder] 완료: {file_path}")
            
            return {
                "success": True,
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "slide_count": len(spec.slides),
                "template_used": template_id,
                "mappings_applied": len(mappings) if mappings else 0,
                "message": f"Template PPT generation complete. File saved at {file_path}. Please output Final Answer with this path."
            }

        except Exception as e:
            logger.error(f"❌ [TemplatedBuilder] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
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
templated_pptx_builder_tool = TemplatedPPTXBuilderTool()

"""
PPT 오브젝트 매핑을 위한 확장된 데이터 모델
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class PPTObjectType(str, Enum):
    """PPT 오브젝트 타입 정의"""
    TEXTBOX = "textbox"
    IMAGE = "image"
    SHAPE = "shape"
    CHART = "chart"
    TABLE = "table"
    DIAGRAM = "diagram"
    ICON = "icon"
    LOGO = "logo"
    BACKGROUND = "background"
    VIDEO = "video"
    AUDIO = "audio"


class ObjectAction(str, Enum):
    """오브젝트에 대한 액션 타입"""
    KEEP_ORIGINAL = "keep_original"      # 원본 유지
    REPLACE_CONTENT = "replace_content"   # 내용 교체
    HIDE_OBJECT = "hide_object"          # 오브젝트 제거
    RESIZE = "resize"                    # 크기 조정
    REPOSITION = "reposition"            # 위치 조정


class PPTObjectMapping(BaseModel):
    """통합된 PPT 오브젝트 매핑 모델"""
    slide_index: int
    element_id: str
    object_type: PPTObjectType
    action: ObjectAction = ObjectAction.KEEP_ORIGINAL
    
    # 원본 정보
    original_content: Optional[str] = None
    original_style: Optional[Dict[str, Any]] = None
    original_position: Optional[Dict[str, Any]] = None
    original_size: Optional[Dict[str, Any]] = None
    
    # 새로운 정보 (변경 시)
    new_content: Optional[str] = None
    new_image_url: Optional[str] = None
    new_style: Optional[Dict[str, Any]] = None
    new_position: Optional[Dict[str, Any]] = None
    new_size: Optional[Dict[str, Any]] = None
    
    # 사용 여부 (UI에서 체크박스로 제어)
    is_enabled: bool = True
    
    # 메타데이터
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# 특화된 오브젝트 매핑 모델들

class TextObjectMapping(PPTObjectMapping):
    """텍스트 오브젝트 매핑 (기존 TextBoxMapping 확장)"""
    object_type: PPTObjectType = PPTObjectType.TEXTBOX
    
    # 텍스트 특화 속성
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    font_color: Optional[str] = None
    font_bold: Optional[bool] = None
    font_italic: Optional[bool] = None
    text_alignment: Optional[str] = None


class ImageObjectMapping(PPTObjectMapping):
    """이미지 오브젝트 매핑"""
    object_type: PPTObjectType = PPTObjectType.IMAGE
    
    # 이미지 특화 속성
    image_type: Optional[str] = None  # jpeg, png, svg 등
    alt_text: Optional[str] = None
    crop_settings: Optional[Dict[str, Any]] = None
    transparency: Optional[float] = None
    effects: Optional[List[str]] = None  # shadow, reflection 등


class ShapeObjectMapping(PPTObjectMapping):
    """도형 오브젝트 매핑"""
    object_type: PPTObjectType = PPTObjectType.SHAPE
    
    # 도형 특화 속성
    shape_type: Optional[str] = None  # rectangle, circle, arrow 등
    fill_color: Optional[str] = None
    border_color: Optional[str] = None
    border_width: Optional[float] = None
    border_style: Optional[str] = None
    rotation: Optional[float] = None


class ChartObjectMapping(PPTObjectMapping):
    """차트 오브젝트 매핑"""
    object_type: PPTObjectType = PPTObjectType.CHART
    
    # 차트 특화 속성
    chart_type: Optional[str] = None  # bar, line, pie 등
    chart_data: Optional[Dict[str, Any]] = None
    chart_style: Optional[str] = None
    color_scheme: Optional[List[str]] = None


class TableObjectMapping(PPTObjectMapping):
    """테이블 오브젝트 매핑"""
    object_type: PPTObjectType = PPTObjectType.TABLE
    
    # 테이블 특화 속성
    table_data: Optional[List[List[str]]] = None
    header_style: Optional[Dict[str, Any]] = None
    cell_style: Optional[Dict[str, Any]] = None
    border_style: Optional[Dict[str, Any]] = None


# 매핑 컬렉션
class SlideObjectMappings(BaseModel):
    """슬라이드별 오브젝트 매핑 컬렉션"""
    slide_index: int
    mappings: List[PPTObjectMapping] = []
    
    def get_mappings_by_type(self, object_type: PPTObjectType) -> List[PPTObjectMapping]:
        """타입별 매핑 필터링"""
        return [m for m in self.mappings if m.object_type == object_type]
    
    def get_enabled_mappings(self) -> List[PPTObjectMapping]:
        """활성화된 매핑만 반환"""
        return [m for m in self.mappings if m.is_enabled]


class PresentationObjectMappings(BaseModel):
    """전체 프레젠테이션 오브젝트 매핑"""
    presentation_id: str
    slide_mappings: List[SlideObjectMappings] = []
    global_settings: Optional[Dict[str, Any]] = None
    
    def get_slide_mappings(self, slide_index: int) -> Optional[SlideObjectMappings]:
        """특정 슬라이드 매핑 반환"""
        for slide_mapping in self.slide_mappings:
            if slide_mapping.slide_index == slide_index:
                return slide_mapping
        return None

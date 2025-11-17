"""
Presentation Data Models - Pydantic models for presentation generation
"""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ========== Visual Elements Models ==========

class GridItem(BaseModel):
    """Grid item in a slide"""
    title: str = Field(..., description="Grid item title")
    description: str = Field(..., description="Grid item description")
    bg_color: str = Field(default="gray-50", description="Tailwind background color class")


class GridLayout(BaseModel):
    """Grid layout configuration"""
    cols: int = Field(ge=1, le=4, description="Number of columns (1-4)")
    items: List[GridItem] = Field(..., description="Grid items")


class ImageSpec(BaseModel):
    """Image specification"""
    url: str = Field(..., description="Image URL or placeholder")
    alt: str = Field(default="", description="Alt text")
    width: Optional[str] = Field(None, description="Width (e.g., '800px', '50%')")
    height: Optional[str] = Field(None, description="Height")


class VisualElements(BaseModel):
    """Visual elements for a slide"""
    icons: List[str] = Field(
        default_factory=list,
        description="Lucide icon names (e.g., ['trending-up', 'dollar-sign'])"
    )
    bullets: List[str] = Field(
        default_factory=list,
        description="Bullet point texts (max 8)"
    )
    grid: Optional[GridLayout] = Field(
        None,
        description="Grid layout for two-column or multi-column content"
    )
    image: Optional[ImageSpec] = Field(
        None,
        description="Image specification"
    )


# ========== Slide Models ==========

class StructuredSlide(BaseModel):
    """Structured slide with layout and visual elements"""
    title: str = Field(..., max_length=100, description="Slide title")
    content: str = Field(default="", max_length=500, description="Main content text")
    layout: Literal[
        "title",
        "title-and-bullets",
        "two-column-grid",
        "divider",
        "image-placeholder"
    ] = Field(
        default="title-and-bullets",
        description="Slide layout type"
    )
    visual_elements: Optional[VisualElements] = Field(
        None,
        description="Visual elements (icons, bullets, grid, image)"
    )


class StructuredOutline(BaseModel):
    """Complete presentation outline"""
    title: str = Field(..., max_length=200, description="Presentation title")
    theme: str = Field(
        default="business",
        description="Theme style: business|modern|playful|minimal|dark|vibrant"
    )
    slides: List[StructuredSlide] = Field(
        ...,
        description="Slide array (1-30 slides)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "2025 Q3 실적 분석",
                "theme": "business",
                "slides": [
                    {
                        "title": "매출 현황",
                        "content": "매출이 15% 증가했습니다.",
                        "layout": "title-and-bullets",
                        "visual_elements": {
                            "bullets": ["매출 15% 증가", "전년 대비 +2.3B"],
                            "icons": ["trending-up", "dollar-sign"]
                        }
                    }
                ]
            }
        }


# ========== Request/Response Models ==========

class PresentationRequest(BaseModel):
    """Presentation generation request"""
    session_id: str = Field(..., description="Chat session ID")
    message_id: str = Field(..., description="Source message ID (contains markdown)")
    style: Literal["business", "modern", "playful"] = Field(
        default="business",
        description="Presentation style"
    )
    title_override: Optional[str] = Field(
        default=None,
        description="Optional presentation title override"
    )
    markdown: Optional[str] = Field(
        default=None,
        description="Direct markdown content (bypass chat history lookup)"
    )
    output_format: Literal["html", "pptx", "both"] = Field(
        default="both",
        description="Output format: html (preview only), pptx (download only), both"
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional options"
    )


class PresentationMetadata(BaseModel):
    """Presentation metadata"""
    title: str
    created_at: datetime
    file_size_bytes: int = 0
    slide_count: int = 0
    theme: str = "business"
    html_filename: Optional[str] = None
    outline_filename: Optional[str] = None
    outline_file_size_bytes: int = 0


class PresentationResponse(BaseModel):
    """Presentation generation response"""
    success: bool = Field(..., description="Success flag")
    html_url: Optional[str] = Field(
        None,
        description="HTML preview URL (e.g., /api/v1/presentations/view/xxx.html)"
    )
    pptx_url: Optional[str] = Field(
        None,
        description="PPTX download URL (e.g., /api/v1/chat/presentation/download/xxx.pptx)"
    )
    preview_available: bool = Field(
        default=False,
        description="Whether HTML preview is available"
    )
    slide_count: int = Field(default=0, description="Number of slides")
    metadata: Optional[PresentationMetadata] = Field(
        None,
        description="Presentation metadata"
    )
    outline_url: Optional[str] = Field(
        None,
        description="Outline JSON URL"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if success=false"
    )
    error_code: Optional[str] = Field(
        None,
        description="Error code for client handling"
    )


# ========== Office Generator Models ==========

class OfficeGeneratorRequest(BaseModel):
    """Request to Office Generator Service"""
    slides: List[Dict[str, Any]] = Field(
        ...,
        description="Slide data array (StructuredSlide.dict() format)"
    )
    metadata: Dict[str, Any] = Field(
        ...,
        description="Metadata (title, author, theme)"
    )


class OfficeGeneratorResponse(BaseModel):
    """Response from Office Generator Service"""
    success: bool
    file_size_bytes: int = 0
    generation_time_ms: int = 0
    error: Optional[str] = None

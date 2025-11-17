"""Shared PPT model classes to avoid circular imports between generator and template manager."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class ChartData(BaseModel):
    type: str = Field("column")
    title: str = ""
    categories: List[str] = Field(default_factory=list)
    series: List[Dict[str, Any]] = Field(default_factory=list)


class DiagramData(BaseModel):
    type: str = Field("none")
    data: Optional[Any] = None  # can be dict/list/raw
    chart: Optional[ChartData] = None


class SlideSpec(BaseModel):
    title: str = ""
    key_message: str = ""
    bullets: List[str] = Field(default_factory=list)
    diagram: Optional[DiagramData] = None
    layout: str = Field("title-and-content")
    style: Optional[Dict[str, Any]] = None
    visual_suggestion: Optional[str] = None
    speaker_notes: Optional[str] = None

    @validator("bullets", pre=True, always=True)
    def normalize_bullets(cls, v):  # noqa: D401
        if not v:
            return []
        res: List[str] = []
        for b in v:
            if isinstance(b, str):
                b2 = b.strip()
                if b2:
                    res.append(b2[:140])
        return res[:8]


class DeckSpec(BaseModel):
    topic: str = "발표자료"
    max_slides: int = 1
    slides: List[SlideSpec] = Field(default_factory=list)
    theme: Optional[Dict[str, Any]] = None
    template_style: Optional[str] = "business"

    @validator("max_slides")
    def clamp(cls, v):  # noqa: D401
        return max(1, min(60, v))

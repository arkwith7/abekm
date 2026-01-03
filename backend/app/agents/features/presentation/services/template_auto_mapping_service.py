"""
Template Auto-Mapping Service
AI 아웃라인과 템플릿 슬라이드를 자동으로 매핑하는 서비스

v1.0 - 초기 구현
- AI가 생성한 아웃라인을 템플릿 슬라이드에 자동 매핑
- 슬라이드 역할 기반 매핑 (title, toc, content, thanks)
- 사용자 수정을 위한 매핑 결과 반환
"""
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from loguru import logger
from pathlib import Path


@dataclass
class SlideMapping:
    """슬라이드 매핑 정보"""
    template_slide_index: int  # 템플릿 슬라이드 인덱스 (1-based)
    outline_slide_index: int   # 아웃라인 슬라이드 인덱스 (0-based)
    action: str                # "ai_content" | "keep_original" | "skip"
    confidence: float          # 매핑 확신도 (0.0 ~ 1.0)
    ai_content: Dict[str, Any] = field(default_factory=dict)  # AI가 생성한 콘텐츠
    element_mappings: List[Dict[str, Any]] = field(default_factory=list)  # 요소별 매핑
    reason: str = ""           # 매핑 이유


@dataclass
class AutoMappingResult:
    """자동 매핑 결과"""
    template_id: str
    success: bool
    slide_mappings: List[SlideMapping]
    total_template_slides: int
    total_outline_slides: int
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


class TemplateAutoMappingService:
    """템플릿 자동 매핑 서비스"""
    
    def __init__(self):
        pass
    
    def auto_map_outline_to_template(
        self,
        template_id: str,
        template_metadata: Dict[str, Any],
        ai_outline: Dict[str, Any]
    ) -> AutoMappingResult:
        """
        AI 아웃라인을 템플릿에 자동으로 매핑합니다.
        
        Args:
            template_id: 템플릿 ID
            template_metadata: 템플릿 메타데이터 (extract_presentation 결과)
            ai_outline: AI가 생성한 아웃라인 (DeckSpec 형태)
        
        Returns:
            AutoMappingResult: 매핑 결과
        """
        try:
            template_slides = template_metadata.get("slides", [])
            outline_slides = ai_outline.get("slides", [])
            
            total_template = len(template_slides)
            total_outline = len(outline_slides)
            
            logger.info(f"🔄 자동 매핑 시작: template={template_id}, "
                       f"template_slides={total_template}, outline_slides={total_outline}")
            
            # 1. 템플릿 슬라이드 역할 분석
            template_roles = self._analyze_template_slide_roles(template_slides)
            
            # 2. 아웃라인 슬라이드 역할 추론
            outline_roles = self._infer_outline_slide_roles(outline_slides)
            
            # 3. 역할 기반 매핑 수행
            slide_mappings = self._perform_role_based_mapping(
                template_slides, template_roles,
                outline_slides, outline_roles
            )
            
            # 4. 요소별 상세 매핑
            slide_mappings = self._perform_element_mapping(
                slide_mappings, template_slides, outline_slides
            )
            
            # 5. 요약 정보 생성
            summary = self._generate_mapping_summary(slide_mappings)
            
            # 6. 경고 생성
            warnings = self._generate_warnings(
                slide_mappings, total_template, total_outline
            )
            
            logger.info(f"✅ 자동 매핑 완료: {summary}")
            
            return AutoMappingResult(
                template_id=template_id,
                success=True,
                slide_mappings=slide_mappings,
                total_template_slides=total_template,
                total_outline_slides=total_outline,
                summary=summary,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"❌ 자동 매핑 실패: {e}")
            return AutoMappingResult(
                template_id=template_id,
                success=False,
                slide_mappings=[],
                total_template_slides=0,
                total_outline_slides=0,
                error_message=str(e)
            )
    
    def _analyze_template_slide_roles(self, template_slides: List[Dict]) -> List[Dict[str, Any]]:
        """템플릿 슬라이드의 역할을 분석합니다."""
        roles = []
        total = len(template_slides)
        
        for idx, slide in enumerate(template_slides):
            slide_index = slide.get("index", idx + 1)
            
            # v2.0 메타데이터에 이미 역할 정보가 있으면 사용
            if slide.get("role"):
                roles.append({
                    "index": slide_index,
                    "role": slide.get("role"),
                    "confidence": slide.get("role_confidence", 0.9),
                    "editable_elements": slide.get("editable_elements", []),
                    "fixed_elements": slide.get("fixed_elements", [])
                })
                continue
            
            # 기존 방식: 위치와 레이아웃 기반 추론
            role, confidence = self._infer_slide_role_from_position(
                slide_index, total, slide.get("layout_name", "")
            )
            
            roles.append({
                "index": slide_index,
                "role": role,
                "confidence": confidence,
                "editable_elements": [],
                "fixed_elements": []
            })
        
        return roles
    
    def _infer_slide_role_from_position(
        self, slide_index: int, total_slides: int, layout_name: str
    ) -> Tuple[str, float]:
        """슬라이드 위치와 레이아웃으로 역할을 추론합니다."""
        layout_lower = layout_name.lower() if layout_name else ""
        
        # 첫 번째 슬라이드: title
        if slide_index == 1:
            if "제목" in layout_lower or "title" in layout_lower:
                return ("title", 0.95)
            return ("title", 0.85)
        
        # 두 번째 슬라이드: toc 후보
        if slide_index == 2:
            if "목차" in layout_lower or "content" in layout_lower:
                return ("toc", 0.90)
            return ("toc", 0.70)
        
        # 마지막 슬라이드: thanks
        if slide_index == total_slides:
            if "감사" in layout_lower or "thank" in layout_lower or "end" in layout_lower:
                return ("thanks", 0.95)
            return ("thanks", 0.75)
        
        # 나머지: content
        return ("content", 0.90)
    
    def _infer_outline_slide_roles(self, outline_slides: List[Dict]) -> List[Dict[str, Any]]:
        """아웃라인 슬라이드의 역할을 추론합니다."""
        roles = []
        total = len(outline_slides)
        
        for idx, slide in enumerate(outline_slides):
            title = slide.get("title", "").lower()
            
            # 키워드 기반 역할 추론
            if idx == 0:
                role = "title"
                confidence = 0.95
            elif any(kw in title for kw in ["목차", "contents", "agenda", "목록"]):
                role = "toc"
                confidence = 0.90
            elif any(kw in title for kw in ["감사", "thank", "q&a", "질문", "마무리"]):
                role = "thanks"
                confidence = 0.90
            elif idx == total - 1:
                # 마지막 슬라이드는 thanks 후보
                role = "thanks" if "감사" in title or "thank" in title else "content"
                confidence = 0.75
            else:
                role = "content"
                confidence = 0.90
            
            roles.append({
                "index": idx,
                "role": role,
                "confidence": confidence,
                "title": slide.get("title", ""),
                "bullets_count": len(slide.get("bullets", []))
            })
        
        return roles
    
    def _perform_role_based_mapping(
        self,
        template_slides: List[Dict],
        template_roles: List[Dict],
        outline_slides: List[Dict],
        outline_roles: List[Dict]
    ) -> List[SlideMapping]:
        """역할 기반으로 슬라이드를 매핑합니다."""
        mappings = []
        used_outline_indices = set()
        
        for t_role in template_roles:
            t_idx = t_role["index"]
            t_role_name = t_role["role"]
            
            # 같은 역할의 아웃라인 슬라이드 찾기
            best_match = None
            best_confidence = 0
            
            for o_role in outline_roles:
                o_idx = o_role["index"]
                if o_idx in used_outline_indices:
                    continue
                
                if o_role["role"] == t_role_name:
                    # 역할이 일치하면 높은 확신도
                    confidence = min(t_role["confidence"], o_role["confidence"])
                    if confidence > best_confidence:
                        best_match = o_idx
                        best_confidence = confidence
            
            if best_match is not None:
                # AI 콘텐츠로 매핑
                used_outline_indices.add(best_match)
                outline_slide = outline_slides[best_match]
                
                mappings.append(SlideMapping(
                    template_slide_index=t_idx,
                    outline_slide_index=best_match,
                    action="ai_content",
                    confidence=best_confidence,
                    ai_content={
                        "title": outline_slide.get("title", ""),
                        "key_message": outline_slide.get("key_message", ""),
                        "bullets": outline_slide.get("bullets", []),
                        "diagram": outline_slide.get("diagram"),
                        "visual_suggestion": outline_slide.get("visual_suggestion", "")
                    },
                    reason=f"Role match: {t_role_name}"
                ))
            else:
                # 매칭되는 아웃라인이 없으면 원본 유지
                mappings.append(SlideMapping(
                    template_slide_index=t_idx,
                    outline_slide_index=-1,
                    action="keep_original",
                    confidence=0.5,
                    reason=f"No matching outline for role: {t_role_name}"
                ))
        
        # 매핑되지 않은 아웃라인 슬라이드가 있으면 추가 매핑 시도
        remaining_outline = [i for i in range(len(outline_slides)) if i not in used_outline_indices]
        remaining_template = [m for m in mappings if m.action == "keep_original"]
        
        for o_idx in remaining_outline:
            if remaining_template:
                # 아직 매핑되지 않은 템플릿 슬라이드에 할당
                mapping = remaining_template.pop(0)
                outline_slide = outline_slides[o_idx]
                mapping.outline_slide_index = o_idx
                mapping.action = "ai_content"
                mapping.confidence = 0.6
                mapping.ai_content = {
                    "title": outline_slide.get("title", ""),
                    "key_message": outline_slide.get("key_message", ""),
                    "bullets": outline_slide.get("bullets", []),
                    "diagram": outline_slide.get("diagram"),
                    "visual_suggestion": outline_slide.get("visual_suggestion", "")
                }
                mapping.reason = "Fallback assignment"
        
        return mappings
    
    def _perform_element_mapping(
        self,
        slide_mappings: List[SlideMapping],
        template_slides: List[Dict],
        outline_slides: List[Dict]
    ) -> List[SlideMapping]:
        """슬라이드 내 요소별 상세 매핑을 수행합니다."""
        for mapping in slide_mappings:
            if mapping.action != "ai_content":
                continue
            
            # 템플릿 슬라이드의 편집 가능한 요소 찾기
            t_idx = mapping.template_slide_index - 1
            if t_idx < 0 or t_idx >= len(template_slides):
                continue
            
            template_slide = template_slides[t_idx]
            editable_elements = template_slide.get("editable_elements", [])
            elements = template_slide.get("elements", [])
            
            # 편집 가능한 요소만 필터링
            editable_element_ids = set(editable_elements)
            target_elements = [e for e in elements if e.get("id") in editable_element_ids]
            
            if not target_elements:
                # 편집 가능한 요소 정보가 없으면 모든 요소 사용
                target_elements = elements
            
            # AI 콘텐츠를 요소에 매핑
            ai_content = mapping.ai_content
            element_mappings = []
            
            for elem in target_elements:
                elem_id = elem.get("id", "")
                elem_role = elem.get("element_role", "")
                position = elem.get("position", {})
                
                # 요소 역할에 따라 AI 콘텐츠 할당
                content = ""
                if elem_role in ["main_title", "slide_title"]:
                    content = ai_content.get("title", "")
                elif elem_role == "subtitle":
                    content = ai_content.get("key_message", "")
                elif elem_role in ["body", "bullet"]:
                    bullets = ai_content.get("bullets", [])
                    content = "\n".join(f"• {b}" for b in bullets) if bullets else ""
                elif elem_role == "toc_item":
                    # 목차 항목은 별도 처리 필요
                    content = ai_content.get("title", "")
                else:
                    # 기본: 제목 또는 본문
                    if position.get("top", 0) < 100:  # 상단 = 제목
                        content = ai_content.get("title", "")
                    else:
                        bullets = ai_content.get("bullets", [])
                        content = "\n".join(f"• {b}" for b in bullets) if bullets else ""
                
                element_mappings.append({
                    "element_id": elem_id,
                    "element_role": elem_role,
                    "original_content": elem.get("content", ""),
                    "new_content": content,
                    "position": position,
                    "is_editable": elem_id in editable_element_ids
                })
            
            mapping.element_mappings = element_mappings
        
        return slide_mappings
    
    def _generate_mapping_summary(self, slide_mappings: List[SlideMapping]) -> Dict[str, Any]:
        """매핑 요약 정보를 생성합니다."""
        ai_content_count = sum(1 for m in slide_mappings if m.action == "ai_content")
        keep_original_count = sum(1 for m in slide_mappings if m.action == "keep_original")
        skip_count = sum(1 for m in slide_mappings if m.action == "skip")
        
        avg_confidence = 0.0
        if slide_mappings:
            avg_confidence = sum(m.confidence for m in slide_mappings) / len(slide_mappings)
        
        return {
            "total_mappings": len(slide_mappings),
            "ai_content_slides": ai_content_count,
            "keep_original_slides": keep_original_count,
            "skip_slides": skip_count,
            "average_confidence": round(avg_confidence, 2)
        }
    
    def _generate_warnings(
        self,
        slide_mappings: List[SlideMapping],
        total_template: int,
        total_outline: int
    ) -> List[str]:
        """매핑 경고를 생성합니다."""
        warnings = []
        
        # 슬라이드 수 불일치 경고
        if total_outline > total_template:
            warnings.append(
                f"아웃라인 슬라이드({total_outline}개)가 템플릿 슬라이드({total_template}개)보다 "
                f"많습니다. 일부 콘텐츠가 누락될 수 있습니다."
            )
        elif total_outline < total_template - 1:
            warnings.append(
                f"템플릿 슬라이드({total_template}개)가 아웃라인 슬라이드({total_outline}개)보다 "
                f"많습니다. 일부 슬라이드는 원본이 유지됩니다."
            )
        
        # 낮은 확신도 매핑 경고
        low_confidence = [m for m in slide_mappings if m.confidence < 0.6]
        if low_confidence:
            warnings.append(
                f"{len(low_confidence)}개 슬라이드의 매핑 확신도가 낮습니다. "
                f"수동 검토를 권장합니다."
            )
        
        return warnings
    
    def export_mapping_for_editor(self, result: AutoMappingResult) -> Dict[str, Any]:
        """편집기 UI용으로 매핑 결과를 내보냅니다."""
        return {
            "template_id": result.template_id,
            "success": result.success,
            "total_template_slides": result.total_template_slides,
            "total_outline_slides": result.total_outline_slides,
            "mappings": [
                {
                    "template_slide": m.template_slide_index,
                    "outline_slide": m.outline_slide_index,
                    "action": m.action,
                    "confidence": m.confidence,
                    "ai_content": m.ai_content,
                    "element_mappings": m.element_mappings,
                    "reason": m.reason
                }
                for m in result.slide_mappings
            ],
            "summary": result.summary,
            "warnings": result.warnings,
            "error": result.error_message
        }


# 전역 인스턴스
template_auto_mapping_service = TemplateAutoMappingService()

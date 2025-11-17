"""
동적 템플릿 관리자
사용자가 업로드한 PPTX 템플릿을 기반으로 AI 생성 시스템을 동적으로 조정
"""
import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from .pptx_template_analyzer import PPTXTemplateAnalyzer, PresentationTemplate, pptx_template_analyzer

logger = logging.getLogger(__name__)

class DynamicTemplateManager:
    """동적 템플릿 관리자"""
    
    def __init__(self):
        self.analyzer = pptx_template_analyzer
        self.template_cache: Dict[str, PresentationTemplate] = {}
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        # 템플릿 저장소 경로 - uploads/templates 디렉토리 사용
        base_dir = Path("uploads/templates")
        self.template_storage_path = base_dir / "user_templates"
        self.metadata_storage_path = base_dir / "metadata"
        
        # 디렉토리 생성
        self.template_storage_path.mkdir(parents=True, exist_ok=True)
        self.metadata_storage_path.mkdir(parents=True, exist_ok=True)
    
    def register_user_template(self, pptx_file_path: str, template_name: Optional[str] = None) -> str:
        """사용자 업로드 템플릿 등록"""
        try:
            logger.info(f"사용자 템플릿 등록 시작: {pptx_file_path}")
            
            # 1. PPTX 파일 분석
            template = self.analyzer.analyze_pptx_template(pptx_file_path)
            
            # 2. 템플릿 이름 설정
            if template_name:
                template.template_name = template_name
            
            template_id = f"user_{template.template_name}"
            
            # 3. 템플릿 파일 복사 (필요시)
            target_path = self.template_storage_path / f"{template_id}.pptx"
            if not target_path.exists():
                import shutil
                shutil.copy2(pptx_file_path, target_path)
            
            # 4. 메타데이터 저장
            metadata_file = self.analyzer.save_template_metadata(
                template, str(self.metadata_storage_path)
            )
            
            # 5. 캐시에 저장
            self.template_cache[template_id] = template
            self.metadata_cache[template_id] = self._create_ai_metadata(template)
            
            logger.info(f"사용자 템플릿 등록 완료: {template_id}")
            return template_id
            
        except Exception as e:
            logger.error(f"사용자 템플릿 등록 실패: {e}")
            raise
    
    def _create_ai_metadata(self, template: PresentationTemplate) -> Dict[str, Any]:
        """AI 생성 시스템용 메타데이터 생성"""
        
        # 1. 레이아웃 옵션 생성
        layout_options = []
        for slide_template in template.slide_templates:
            layout_info = {
                "name": slide_template.layout_type,
                "description": self._get_layout_description(slide_template.layout_type),
                "content_areas": len([box for box in slide_template.layout_boxes if box.type in ["content", "text"]]),
                "has_chart_area": any(box.type == "chart" for box in slide_template.layout_boxes),
                "has_table_area": any(box.type == "table" for box in slide_template.layout_boxes),
                "has_image_area": any(box.type == "image" for box in slide_template.layout_boxes),
                "suggested_for": slide_template.suggested_content_type
            }
            layout_options.append(layout_info)
        
        # 중복 제거
        layout_options = self._deduplicate_layouts(layout_options)
        
        # 2. 스타일 가이드 생성
        style_guide = {
            "color_scheme": template.color_scheme,
            "font_scheme": template.font_scheme,
            "text_constraints": {
                "title_max_length": 60,
                "key_message_max_length": 120,
                "bullet_max_length": 50
            }
        }
        
        # 3. 도식화 규칙 생성
        diagram_rules = self._generate_diagram_rules(template)
        
        # 4. 슬라이드 구조 템플릿
        slide_structure_template = []
        for slide_template in template.slide_templates:
            structure = {
                "slide_number": slide_template.slide_number,
                "title": slide_template.title,
                "role": self._infer_slide_role(slide_template, template.slide_templates),
                "layout": slide_template.layout_type,
                "content_guidance": self._generate_content_guidance(slide_template)
            }
            slide_structure_template.append(structure)
        
        return {
            "template_id": f"user_{template.template_name}",
            "template_name": template.template_name,
            "total_slides": template.total_slides,
            "layout_options": layout_options,
            "style_guide": style_guide,
            "diagram_rules": diagram_rules,
            "slide_structure_template": slide_structure_template,
            "ai_prompt_additions": self._generate_prompt_additions(template)
        }
    
    def _get_layout_description(self, layout_type: str) -> str:
        """레이아웃 타입별 설명"""
        descriptions = {
            "title-only": "제목만 있는 커버 슬라이드",
            "title-content": "제목과 본문 내용이 있는 기본 슬라이드",
            "two-column": "두 개의 콘텐츠 영역으로 나뉜 비교형 슬라이드",
            "chart-focus": "차트나 그래프가 중심인 데이터 시각화 슬라이드",
            "table-focus": "표가 중심인 정보 정리 슬라이드",
            "image-focus": "이미지가 중심인 시각적 슬라이드",
            "section-header": "섹션 구분용 헤더 슬라이드"
        }
        return descriptions.get(layout_type, "사용자 정의 레이아웃")
    
    def _deduplicate_layouts(self, layout_options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복된 레이아웃 제거"""
        seen = set()
        unique_layouts = []
        
        for layout in layout_options:
            key = (layout["name"], layout["content_areas"], layout["has_chart_area"], layout["has_table_area"])
            if key not in seen:
                seen.add(key)
                unique_layouts.append(layout)
        
        return unique_layouts
    
    def _generate_diagram_rules(self, template: PresentationTemplate) -> Dict[str, Any]:
        """도식화 규칙 생성"""
        rules = {
            "chart_layouts": [],
            "table_layouts": [],
            "image_layouts": [],
            "default_diagram_types": ["chart", "table", "flow", "timeline", "comparison"]
        }
        
        for slide_template in template.slide_templates:
            if any(box.type == "chart" for box in slide_template.layout_boxes):
                rules["chart_layouts"].append(slide_template.layout_type)
            if any(box.type == "table" for box in slide_template.layout_boxes):
                rules["table_layouts"].append(slide_template.layout_type)
            if any(box.type == "image" for box in slide_template.layout_boxes):
                rules["image_layouts"].append(slide_template.layout_type)
        
        return rules
    
    def _infer_slide_role(self, slide_template, all_slides: List) -> str:
        """슬라이드 역할 추론"""
        if slide_template.slide_number == 1:
            return "title"
        elif slide_template.slide_number == 2 and "목차" in slide_template.title:
            return "agenda"
        elif slide_template.slide_number == len(all_slides):
            return "summary"
        else:
            return "section"
    
    def _generate_content_guidance(self, slide_template) -> Dict[str, str]:
        """콘텐츠 가이던스 생성"""
        guidance = {}
        
        if slide_template.layout_type == "title-only":
            guidance["title"] = "주제명 또는 섹션 제목"
            guidance["content"] = "부제목이나 간단한 설명 (선택사항)"
        elif slide_template.layout_type == "chart-focus":
            guidance["title"] = "데이터 분석 제목"
            guidance["content"] = "차트 설명과 핵심 인사이트"
            guidance["diagram"] = "수치 데이터를 시각적 차트로 표현"
        elif slide_template.layout_type == "table-focus":
            guidance["title"] = "정보 정리 제목"
            guidance["content"] = "표 설명과 주요 포인트"
            guidance["diagram"] = "구조화된 정보를 표 형태로 정리"
        else:
            guidance["title"] = "섹션 제목"
            guidance["content"] = "핵심 내용을 불릿 포인트로 정리"
        
        return guidance
    
    def _generate_prompt_additions(self, template: PresentationTemplate) -> List[str]:
        """AI 프롬프트에 추가할 지침 생성"""
        additions = [
            f"- 이 템플릿은 총 {template.total_slides}개의 슬라이드 구조를 가지고 있습니다.",
            f"- 사용 가능한 레이아웃: {', '.join(template.layout_types)}",
            f"- 주 색상 스키마: {template.color_scheme.get('primary', '#1f4e79')}",
        ]
        
        # 특별한 레이아웃이 있는 경우 추가 지침
        if "chart-focus" in template.layout_types:
            additions.append("- 수치 데이터가 있을 때는 chart-focus 레이아웃을 적극 활용하세요.")
        if "table-focus" in template.layout_types:
            additions.append("- 구조화된 정보는 table-focus 레이아웃으로 표현하세요.")
        if "two-column" in template.layout_types:
            additions.append("- 비교나 대조가 필요한 내용은 two-column 레이아웃을 사용하세요.")
        
        return additions
    
    def get_template_for_ai(self, template_id: str) -> Optional[Dict[str, Any]]:
        """AI 생성 시스템용 템플릿 메타데이터 반환"""
        return self.metadata_cache.get(template_id)
    
    def get_outline_tab_structure(self, template_id: str) -> Optional[List[Dict[str, Any]]]:
        """아웃라인 에디터용 탭 구조 반환"""
        if template_id in self.template_cache:
            template = self.template_cache[template_id]
            return self.analyzer.generate_outline_tabs(template)
        return None
    
    def list_available_templates(self) -> List[Dict[str, str]]:
        """사용 가능한 템플릿 목록"""
        templates = []
        
        # 실제 등록된 템플릿만 반환 (가상 템플릿 제거)
        
        # 사용자 업로드 템플릿들
        for template_id, template in self.template_cache.items():
            templates.append({
                "id": template_id,
                "name": template.template_name,
                "type": "user-uploaded",
                "slides": template.total_slides
            })
        
        return templates
    
    def generate_dynamic_prompt(self, template_id: str, base_prompt: str) -> str:
        """템플릿 기반 동적 프롬프트 생성"""
        if template_id not in self.metadata_cache:
            return base_prompt
        
        metadata = self.metadata_cache[template_id]
        
        # 기본 프롬프트에 템플릿 특화 지침 추가
        template_additions = [
            f"\n================ 템플릿 특화 지침 ================",
            f"템플릿: {metadata['template_name']} ({metadata['total_slides']}개 슬라이드)",
            "",
            "사용 가능한 레이아웃:",
        ]
        
        for layout in metadata["layout_options"]:
            template_additions.append(f"- {layout['name']}: {layout['description']}")
        
        template_additions.extend([
            "",
            "추가 지침:",
        ])
        template_additions.extend(metadata["ai_prompt_additions"])
        
        # 슬라이드 구조 가이드
        template_additions.extend([
            "",
            "권장 슬라이드 구조:",
        ])
        
        for i, slide_structure in enumerate(metadata["slide_structure_template"][:6]):  # 최대 6개만 표시
            template_additions.append(
                f"{slide_structure['slide_number']}. {slide_structure['title']} "
                f"({slide_structure['layout']}, {slide_structure['role']})"
            )
        
        template_additions.append("=====================================\n")
        
        return base_prompt + "\n".join(template_additions)
    
    def apply_template_to_outline(self, template_id: str, ai_outline: Dict[str, Any]) -> Dict[str, Any]:
        """AI 생성 아웃라인에 템플릿 구조 적용"""
        if template_id not in self.metadata_cache:
            return ai_outline
        
        metadata = self.metadata_cache[template_id]
        enhanced_outline = ai_outline.copy()
        
        # 1. 테마 정보 업데이트
        enhanced_outline["theme"] = {
            **enhanced_outline.get("theme", {}),
            **metadata["style_guide"]["color_scheme"],
            "template_id": template_id,
            "template_name": metadata["template_name"]
        }
        
        # 2. 슬라이드별 레이아웃 최적화
        if "slides" in enhanced_outline:
            slides = enhanced_outline["slides"]
            structure_template = metadata["slide_structure_template"]
            
            for i, slide in enumerate(slides):
                if i < len(structure_template):
                    template_slide = structure_template[i]
                    
                    # 레이아웃 타입 적용
                    slide["layout"] = template_slide["layout"]
                    
                    # 역할 정보 추가
                    slide["role"] = template_slide["role"]
                    
                    # 템플릿별 스타일 힌트 추가
                    slide["template_hints"] = {
                        "layout_type": template_slide["layout"],
                        "content_guidance": template_slide["content_guidance"]
                    }
        
        return enhanced_outline


# 전역 인스턴스
dynamic_template_manager = DynamicTemplateManager()

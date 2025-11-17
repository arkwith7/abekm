"""
제품소개서 전용 템플릿 관리자
의료기기, 제품 소개서에 특화된 레이아웃과 구조를 제공
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

class ProductPageType(Enum):
    """제품소개서 페이지 타입"""
    TITLE = "title"              # 제목 페이지
    TABLE_OF_CONTENTS = "toc"    # 목차 페이지  
    PRODUCT_OVERVIEW = "overview" # 제품 개요
    FEATURES = "features"        # 제품 기능
    PERFORMANCE = "performance"  # 제품 성능
    SPECIFICATIONS = "specs"     # 기술 스펙
    SAFETY_CERTIFICATION = "safety" # 안전/인증
    BENEFITS = "benefits"        # 기대 효과

@dataclass
class ProductPageLayout:
    """제품소개서 페이지별 레이아웃 정의"""
    page_type: ProductPageType
    layout_name: str
    description: str
    
    # 레이아웃 특성
    has_title: bool = True
    has_content: bool = True
    has_image_area: bool = False
    has_chart_area: bool = False
    has_table_area: bool = False
    has_icon_area: bool = False
    
    # 스타일 가이드
    title_style: Dict[str, Any] = None
    content_style: Dict[str, Any] = None
    color_scheme: str = "medical_blue"
    
    # 자동 생성 규칙
    auto_content_rules: List[str] = None

class ProductTemplateManager:
    """제품소개서 템플릿 관리자"""
    
    def __init__(self):
        self.page_layouts = self._initialize_product_layouts()
        self.content_mapping_rules = self._initialize_content_rules()
        
    def _initialize_product_layouts(self) -> Dict[ProductPageType, ProductPageLayout]:
        """제품소개서 페이지별 레이아웃 초기화"""
        return {
            ProductPageType.TITLE: ProductPageLayout(
                page_type=ProductPageType.TITLE,
                layout_name="product-title",
                description="제품명과 회사 정보를 중앙에 배치",
                has_content=False,
                has_image_area=True,  # 제품 이미지/로고
                title_style={
                    "font_size": 32,
                    "font_weight": "bold",
                    "alignment": "center",
                    "color": "primary"
                },
                auto_content_rules=[
                    "extract_product_name",
                    "extract_company_name",
                    "extract_product_category"
                ]
            ),
            
            ProductPageType.TABLE_OF_CONTENTS: ProductPageLayout(
                page_type=ProductPageType.TABLE_OF_CONTENTS,
                layout_name="numbered-list",
                description="표준 제품소개서 목차 구조",
                content_style={
                    "list_type": "numbered",
                    "font_size": 18,
                    "line_spacing": 1.5
                },
                auto_content_rules=[
                    "generate_standard_toc"
                ]
            ),
            
            ProductPageType.PRODUCT_OVERVIEW: ProductPageLayout(
                page_type=ProductPageType.PRODUCT_OVERVIEW,
                layout_name="title-content-image",
                description="제품 개요 설명과 제품 이미지",
                has_image_area=True,
                auto_content_rules=[
                    "extract_product_purpose",
                    "extract_product_description",
                    "extract_target_users"
                ]
            ),
            
            ProductPageType.FEATURES: ProductPageLayout(
                page_type=ProductPageType.FEATURES,
                layout_name="icon-bullet-list",
                description="기능별 아이콘과 설명",
                has_icon_area=True,
                auto_content_rules=[
                    "extract_key_features",
                    "assign_feature_icons",
                    "limit_features_per_slide"
                ]
            ),
            
            ProductPageType.PERFORMANCE: ProductPageLayout(
                page_type=ProductPageType.PERFORMANCE,
                layout_name="chart-focus",
                description="성능 수치와 차트 중심",
                has_chart_area=True,
                auto_content_rules=[
                    "extract_performance_metrics",
                    "create_performance_charts",
                    "highlight_key_numbers"
                ]
            ),
            
            ProductPageType.SPECIFICATIONS: ProductPageLayout(
                page_type=ProductPageType.SPECIFICATIONS,
                layout_name="table-focus",
                description="기술 사양 테이블 중심",
                has_table_area=True,
                auto_content_rules=[
                    "extract_tech_specs",
                    "format_spec_table",
                    "categorize_specifications"
                ]
            ),
            
            ProductPageType.SAFETY_CERTIFICATION: ProductPageLayout(
                page_type=ProductPageType.SAFETY_CERTIFICATION,
                layout_name="badge-grid",
                description="인증 마크와 안전 규격",
                has_icon_area=True,
                auto_content_rules=[
                    "extract_certifications",
                    "extract_safety_standards",
                    "create_certification_badges"
                ]
            ),
            
            ProductPageType.BENEFITS: ProductPageLayout(
                page_type=ProductPageType.BENEFITS,
                layout_name="benefit-highlight",
                description="기대 효과와 장점 강조",
                has_icon_area=True,
                auto_content_rules=[
                    "extract_benefits",
                    "extract_advantages",
                    "create_impact_statements"
                ]
            )
        }
    
    def _initialize_content_rules(self) -> Dict[str, Any]:
        """AI 답변을 제품소개서 구조로 변환하는 규칙들"""
        return {
            "extract_product_name": {
                "patterns": [
                    r"제품명[:\s]*([^\n]+)",
                    r"모델명[:\s]*([^\n]+)",
                    r"^([A-Z][A-Z0-9\-]+)\s*(?:시리즈|모델)?",
                ],
                "fallback": "의료기기 제품"
            },
            
            "extract_key_features": {
                "patterns": [
                    r"(?:주요\s*)?기능[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"특징[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"장점[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)"
                ],
                "split_bullets": True,
                "max_features": 6
            },
            
            "extract_performance_metrics": {
                "patterns": [
                    r"성능[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"(?:측정|수치|결과)[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"(\d+(?:\.\d+)?)\s*([%℃㎝㎜㎏㎎㎎/㎗㎘㎰분초시간초당])"
                ],
                "extract_numbers": True,
                "create_charts": True
            },
            
            "extract_tech_specs": {
                "patterns": [
                    r"사양[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"스펙[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"규격[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)"
                ],
                "table_format": True,
                "key_value_pairs": True
            },
            
            "extract_certifications": {
                "patterns": [
                    r"인증[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"규격[:\s]*(.+?)(?:\n\n|\n[가-힣]+:|$)",
                    r"(FDA|CE|ISO\s*\d+|KS\s*[A-Z]\s*\d+|의료기기\s*허가)"
                ],
                "badge_icons": True
            }
        }
    
    def analyze_rag_content_for_product(self, content: str) -> Dict[ProductPageType, Dict[str, Any]]:
        """RAG 답변을 분석하여 제품소개서 페이지별 내용 추출"""
        import re
        
        extracted_content = {}
        
        for page_type, layout in self.page_layouts.items():
            page_content = {"title": "", "content": [], "metadata": {}}
            
            # 각 페이지 타입별 자동 콘텐츠 추출 규칙 적용
            if layout.auto_content_rules:
                for rule_name in layout.auto_content_rules:
                    if rule_name in self.content_mapping_rules:
                        rule = self.content_mapping_rules[rule_name]
                        
                        # 패턴 매칭으로 콘텐츠 추출
                        for pattern in rule.get("patterns", []):
                            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                            for match in matches:
                                if rule_name == "extract_product_name":
                                    page_content["title"] = match.group(1).strip()
                                elif rule.get("split_bullets"):
                                    # 불릿 포인트로 분할
                                    bullets = self._split_into_bullets(match.group(1))
                                    page_content["content"].extend(bullets[:rule.get("max_features", 10)])
                                elif rule.get("table_format"):
                                    # 테이블 형태로 변환
                                    table_data = self._extract_table_data(match.group(1))
                                    page_content["metadata"]["table"] = table_data
                                else:
                                    page_content["content"].append(match.group(1).strip())
            
            extracted_content[page_type] = page_content
        
        return extracted_content
    
    def _split_into_bullets(self, text: str) -> List[str]:
        """텍스트를 불릿 포인트로 분할"""
        import re
        
        # 기존 불릿 포인트나 번호 매기기 패턴 찾기
        bullets = re.split(r'[•\-\*]\s*|^\d+\.\s*', text, flags=re.MULTILINE)
        bullets = [b.strip() for b in bullets if b.strip()]
        
        # 긴 문장을 적절히 분할
        if len(bullets) == 1 and len(bullets[0]) > 200:
            sentences = re.split(r'[.。]\s*', bullets[0])
            bullets = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        return bullets[:6]  # 최대 6개까지
    
    def _extract_table_data(self, text: str) -> List[Dict[str, str]]:
        """텍스트에서 테이블 데이터 추출"""
        import re
        
        table_data = []
        
        # 키:값 패턴 찾기
        kv_patterns = re.finditer(r'([^:\n]{1,30}):\s*([^\n]{1,100})', text)
        for match in kv_patterns:
            table_data.append({
                "key": match.group(1).strip(),
                "value": match.group(2).strip()
            })
        
        return table_data
    
    def generate_product_outline(self, rag_content: str, product_type: str = "medical_device") -> Dict[str, Any]:
        """RAG 답변을 제품소개서 아웃라인으로 변환"""
        
        # 1. RAG 콘텐츠 분석
        extracted_pages = self.analyze_rag_content_for_product(rag_content)
        
        # 2. 제품소개서 표준 구조로 슬라이드 생성
        slides = []
        
        # 표준 페이지 순서
        page_order = [
            ProductPageType.TITLE,
            ProductPageType.TABLE_OF_CONTENTS,
            ProductPageType.PRODUCT_OVERVIEW,
            ProductPageType.FEATURES,
            ProductPageType.PERFORMANCE,
            ProductPageType.SPECIFICATIONS,
            ProductPageType.SAFETY_CERTIFICATION,
            ProductPageType.BENEFITS
        ]
        
        for page_type in page_order:
            if page_type in extracted_pages:
                layout = self.page_layouts[page_type]
                page_data = extracted_pages[page_type]
                
                slide = {
                    "title": self._generate_page_title(page_type, page_data),
                    "key_message": page_data.get("content", [""])[0] if page_data.get("content") else "",
                    "bullets": page_data.get("content", [])[:6],
                    "layout": layout.layout_name,
                    "style": {
                        "page_type": page_type.value,
                        "color_scheme": layout.color_scheme
                    },
                    "metadata": page_data.get("metadata", {})
                }
                
                # 페이지 타입별 특별 처리
                if page_type == ProductPageType.PERFORMANCE and page_data.get("metadata", {}).get("table"):
                    slide["diagram"] = {
                        "type": "chart",
                        "data": page_data["metadata"]["table"]
                    }
                elif page_type == ProductPageType.SPECIFICATIONS and page_data.get("metadata", {}).get("table"):
                    slide["diagram"] = {
                        "type": "table", 
                        "data": page_data["metadata"]["table"]
                    }
                
                slides.append(slide)
        
        return {
            "topic": extracted_pages.get(ProductPageType.TITLE, {}).get("title", "제품 소개서"),
            "max_slides": len(slides),
            "slides": slides,
            "theme": {
                "color_scheme": "medical_blue",
                "template_type": "product_introduction"
            }
        }
    
    def _generate_page_title(self, page_type: ProductPageType, page_data: Dict[str, Any]) -> str:
        """페이지 타입별 제목 생성"""
        title_map = {
            ProductPageType.TITLE: page_data.get("title", "제품명"),
            ProductPageType.TABLE_OF_CONTENTS: "목차",
            ProductPageType.PRODUCT_OVERVIEW: "제품 개요",
            ProductPageType.FEATURES: "주요 기능",
            ProductPageType.PERFORMANCE: "제품 성능",
            ProductPageType.SPECIFICATIONS: "기술 사양",
            ProductPageType.SAFETY_CERTIFICATION: "안전 규격 및 인증",
            ProductPageType.BENEFITS: "기대 효과"
        }
        
        return title_map.get(page_type, "제품 정보")


# 전역 인스턴스
product_template_manager = ProductTemplateManager()

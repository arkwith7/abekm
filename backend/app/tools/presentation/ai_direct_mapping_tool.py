"""
AI Direct Mapping Tool - AI-First Template PPT Generation

AI가 템플릿 메타데이터를 직접 분석하고 사용자 질의에 맞는 콘텐츠를
element_id 단위로 직접 매핑하는 단순화된 도구.

핵심 원칙:
1. AI가 모든 매핑 결정을 함 (코드는 단순 적용만)
2. 단일 프롬프트로 전체 PPT 콘텐츠 생성
3. element_id ↔ content 직접 매핑
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.core.ai_service import MultiVendorAIService as AIService

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "presentation"
AI_DIRECT_MAPPING_PROMPT_FILE = PROMPT_DIR / "ai_direct_mapping_system.prompt"


class AIDirectMappingInput(BaseModel):
    """AI Direct Mapping Tool 입력 스키마"""
    user_query: str = Field(description="사용자의 PPT 생성 요청 (주제, 내용 등)")
    template_metadata: Dict[str, Any] = Field(description="템플릿 메타데이터 (slides, elements 포함)")
    additional_context: Optional[str] = Field(default=None, description="추가 컨텍스트 (참고 자료 등)")


class AIDirectMappingTool(BaseTool):
    """
    AI가 템플릿 메타데이터를 보고 직접 매핑 JSON을 생성하는 도구.
    
    기존 파이프라인의 4개 Tool을 1개로 통합:
    - template_analyzer_tool (불필요: 메타데이터 직접 전달)
    - outline_generator_tool (통합: AI가 슬라이드 구조 결정)
    - slide_type_matcher_tool (불필요: AI가 직접 매칭)
    - content_mapping_tool (통합: AI가 직접 매핑)
    """
    
    name: str = "ai_direct_mapping_tool"
    description: str = """
    AI가 템플릿 메타데이터를 분석하고 사용자 요청에 맞는 PPT 콘텐츠를 직접 생성합니다.
    
    입력:
    - user_query: PPT 생성 요청 (예: "자동차 산업 특허분석 방법론 PPT 만들어줘")
    - template_metadata: 템플릿 메타데이터 JSON
    
    출력:
    - mappings: element_id와 content의 직접 매핑 리스트
    - 각 요소의 original_name도 포함 (PPT 빌드용)
    """
    args_schema: type[BaseModel] = AIDirectMappingInput
    
    _ai_service: Optional[AIService] = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ai_service = AIService()
    
    def _run(
        self,
        user_query: str,
        template_metadata: Dict[str, Any],
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """동기 실행"""
        import asyncio
        return asyncio.run(self._arun(user_query, template_metadata, additional_context))
    
    async def _arun(
        self,
        user_query: str,
        template_metadata: Dict[str, Any],
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """비동기 실행 - AI가 직접 매핑 생성"""
        
        logger.info(f"🎯 [AIDirectMapping] 시작: query='{user_query[:50]}...'")
        
        try:
            # 1. 템플릿 구조를 AI에게 전달할 형식으로 변환
            template_spec = self._create_template_spec(template_metadata)
            
            # 2. AI 프롬프트 생성
            prompt = self._create_prompt(user_query, template_spec, additional_context)
            
            # 3. AI 호출
            response = await self._call_llm(prompt)
            
            # 4. 응답 파싱 (매핑 + 슬라이드 대체 정보)
            parse_result = self._parse_response(response, template_metadata)
            mappings = parse_result.get('mappings', [])
            slide_replacements = parse_result.get('slide_replacements', [])
            
            logger.info(f"✅ [AIDirectMapping] 완료: {len(mappings)}개 매핑 생성")
            if slide_replacements:
                logger.info(f"🔄 [AIDirectMapping] 슬라이드 대체: {len(slide_replacements)}개")
            
            return {
                "success": True,
                "mappings": mappings,
                "mapping_count": len(mappings),
                "slide_replacements": slide_replacements,  # 🆕 v3.4
                "message": "AI 직접 매핑 완료. simple_ppt_builder로 PPT를 생성하세요."
            }
            
        except Exception as e:
            logger.error(f"❌ [AIDirectMapping] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "mappings": []
            }
    
    def _is_decoration_element(self, elem: Dict[str, Any]) -> bool:
        """장식용/아이콘/placeholder 요소인지 판단"""
        elem_role = elem.get('element_role', '')
        elem_type = elem.get('type', '')
        content = elem.get('content', '').strip()
        
        # 🆕 v3.3: 테이블은 항상 편집 대상
        if elem_type == 'table':
            return False  # 테이블은 장식 아님
        
        # 1. element_role 기반 판단
        # 🆕 v3.2: icon_card는 편집 대상 (장식 아님)
        # 🆕 v3.3: comparison_table, data_table 추가
        decoration_roles = {'icon_text', 'icon', 'decoration', 'arrow', 'bracket'}
        editable_roles = {'icon_card', 'numbered_card', 'body_content', 'key_message', 'bullet_item', 'comparison_table', 'data_table'}
        
        if elem_role in editable_roles:
            return False  # 편집 대상
        if elem_role in decoration_roles:
            return True  # 장식
        
        # 2. 콘텐츠 패턴 기반 판단 - 이모지/특수문자만 있는지 확인
        # 🔧 수정: 한글은 일반 텍스트로 취급 (한글 범위: 0xAC00-0xD7AF, 한글자모: 0x1100-0x11FF, 0x3130-0x318F)
        def is_emoji_or_special(c):
            """한글이 아닌 비-ASCII 문자 (이모지/특수문자)인지 판단"""
            if c in '→←↑↓↔':  # 화살표 문자
                return True
            code = ord(c)
            # 한글 완성형 범위
            if 0xAC00 <= code <= 0xD7AF:
                return False  # 한글은 일반 텍스트
            # 한글 자모 범위
            if 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F:
                return False  # 한글은 일반 텍스트
            # ASCII 범위 (일반 영문/숫자/기호)
            if code < 128:
                return False  # ASCII는 일반 텍스트
            # 그 외 비-ASCII는 이모지/특수문자로 간주
            return True
        
        # 모든 문자가 이모지/특수문자인 경우만 장식으로 판단
        non_space_content = content.replace(' ', '')
        if non_space_content and all(is_emoji_or_special(c) for c in non_space_content):
            return True
        
        # 화살표나 특수문자만 있는 경우
        if content in {'→', '←', '↑', '↓', '|', '/', '-', '•', '▶', '▷', '►'}:
            return True
        
        # 3. placeholder 텍스트 판단
        placeholder_patterns = {'제품 이미지', '이미지', 'image', 'placeholder', 'logo', 'Logo'}
        if content.lower() in {p.lower() for p in placeholder_patterns}:
            return True
        
        # 4. 매우 짧은 label (10자 이하이고 label role) - 단, icon_card는 제외
        if elem_role == 'label' and len(content) <= 10:
            # 도식 내 라벨은 보통 짧고 맥락 의존적이므로 유지
            return True
        
        return False
    
    def _analyze_slide_flexibility(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        🆕 v3.4: 슬라이드별 유연성 분석 및 대체 가능 슬라이드 매핑
        
        고정 요소가 많은 슬라이드(도식 등)는 주제와 맞지 않을 수 있으므로,
        같은 스타일의 더 유연한 슬라이드로 대체 가능한지 분석합니다.
        
        Returns:
            {
                'slide_flexibility': {slide_idx: {'fixed_ratio': 0.7, 'style': 'icon_boxes', ...}},
                'replacement_candidates': {6: [7], 7: [6]},  # 슬라이드 6은 7로 대체 가능
                'high_fixed_slides': [6],  # 고정 비율 50% 이상 슬라이드
            }
        """
        slide_flexibility = {}
        style_groups = {}  # 스타일별 슬라이드 그룹화
        
        for slide in metadata.get('slides', []):
            slide_idx = slide.get('index', 0)
            role = slide.get('role', 'unknown')
            viz_style = slide.get('visualization_style', {})
            style_name = viz_style.get('name', 'simple_text')
            
            elements = slide.get('elements', [])
            total_count = len(elements)
            
            # 🆕 v3.5: is_fixed 뿐만 아니라 장식 요소도 고정 요소로 간주
            fixed_count = 0
            for e in elements:
                if e.get('is_fixed', False) or self._is_decoration_element(e):
                    fixed_count += 1
            
            fixed_ratio = fixed_count / total_count if total_count > 0 else 0
            
            # 🆕 v3.5: 유연성 기준 강화 (40% 이상 고정이면 경직된 것으로 간주)
            is_flexible = fixed_ratio < 0.4
            
            slide_flexibility[slide_idx] = {
                'role': role,
                'style': style_name,
                'total_elements': total_count,
                'fixed_elements': fixed_count,
                'fixed_ratio': fixed_ratio,
                'is_flexible': is_flexible
            }
            
            # 스타일별 그룹화 (content/section 슬라이드만)
            if role in ['content', 'section']:
                if style_name not in style_groups:
                    style_groups[style_name] = []
                style_groups[style_name].append({
                    'index': slide_idx,
                    'fixed_ratio': fixed_ratio,
                    'is_flexible': is_flexible
                })
        
        # 대체 후보 계산: 같은 스타일 내에서 더 유연한 슬라이드 찾기
        replacement_candidates = {}
        high_fixed_slides = []
        
        for slide_idx, info in slide_flexibility.items():
            # 🆕 v3.5: 고정 비율 40% 이상이면 대체 고려
            if info['fixed_ratio'] >= 0.4:
                high_fixed_slides.append(slide_idx)
                
                # 같은 스타일의 더 유연한 슬라이드 찾기
                style_name = info['style']
                if style_name in style_groups:
                    candidates = [
                        s['index'] for s in style_groups[style_name]
                        if s['index'] != slide_idx and s['is_flexible']
                    ]
                    # 🆕 v3.5: 같은 스타일의 유연한 슬라이드가 없으면 'simple_text' 스타일에서도 찾기
                    if not candidates and style_name != 'simple_text':
                        if 'simple_text' in style_groups:
                            candidates = [
                                s['index'] for s in style_groups['simple_text']
                                if s['is_flexible']
                            ]
                            
                    if candidates:
                        replacement_candidates[slide_idx] = candidates
        
        return {
            'slide_flexibility': slide_flexibility,
            'replacement_candidates': replacement_candidates,
            'high_fixed_slides': high_fixed_slides,
            'style_groups': style_groups
        }
    
    def _create_template_spec(self, metadata: Dict[str, Any]) -> str:
        """템플릿 메타데이터를 AI가 이해하기 쉬운 형식으로 변환"""
        
        lines = []
        lines.append("=== 템플릿 구조 ===")
        total_slides = len(metadata.get('slides', []))
        lines.append(f"총 슬라이드: {total_slides}개")
        lines.append("")
        
        # 목차 슬라이드의 항목 수 파악 (슬라이드 수와 일치해야 함)
        toc_items_count = 0
        content_slides_count = 0
        editable_count = 0
        skipped_count = 0
        
        # 🆕 슬라이드 스타일 요약 수집
        slide_styles = []
        
        for slide in metadata.get('slides', []):
            slide_num = slide.get('index', 0)
            role = slide.get('role', 'unknown')
            
            # 🆕 시각화 스타일 정보 추출
            viz_style = slide.get('visualization_style', {})
            style_name = viz_style.get('name', 'simple_text')
            style_desc = viz_style.get('description', '')
            
            # 편집 가능 요소 수 미리 계산
            slide_editable_count = sum(
                1 for e in slide.get('elements', []) 
                if not e.get('is_fixed', False) and not self._is_decoration_element(e) and e.get('content', '').strip()
            )
            
            # 🆕 슬라이드 헤더에 스타일 정보 포함
            if role in ['content', 'section']:
                lines.append(f"## 슬라이드 {slide_num} ({role}) - 스타일: {style_name}")
                lines.append(f"   📊 레이아웃: {style_desc} (편집가능 요소: {slide_editable_count}개)")
                slide_styles.append({
                    'index': slide_num,
                    'style': style_name,
                    'editable_count': slide_editable_count
                })
            else:
                lines.append(f"## 슬라이드 {slide_num} ({role})")
            
            if role == 'toc':
                # 목차 항목 수 카운트
                for elem in slide.get('elements', []):
                    if elem.get('element_role') == 'toc_item':
                        toc_items_count += 1
            elif role in ['content', 'section']:
                content_slides_count += 1
            
            # 편집 가능한 요소만 표시
            for elem in slide.get('elements', []):
                # is_fixed=True인 요소 제외
                if elem.get('is_fixed', False):
                    skipped_count += 1
                    continue
                
                # 🆕 장식 요소 추가 필터링
                if self._is_decoration_element(elem):
                    skipped_count += 1
                    continue
                
                elem_id = elem.get('id', '')
                elem_type = elem.get('type', '')
                elem_role = elem.get('element_role', 'unknown')
                original_name = elem.get('original_name', '')
                current_content = elem.get('content', '')
                content_len = len(current_content)
                
                # 빈 콘텐츠는 이미 is_fixed로 처리되었지만, 혹시 모르니 추가 체크
                if not current_content.strip():
                    skipped_count += 1
                    continue
                
                editable_count += 1
                
                # 🆕 표(Table) 요소는 특별 처리
                if elem_type == 'table':
                    table_data = elem.get('table_data', {})
                    rows = table_data.get('rows', 0)
                    cols = table_data.get('cols', 0)
                    header_row = table_data.get('header_row', [])
                    header_texts = [cell.get('text', '') for cell in header_row]
                    
                    lines.append(f"  - {elem_id} | {elem_role} | 📊 TABLE ({rows}행 x {cols}열)")
                    lines.append(f"    헤더: {header_texts}")
                    lines.append(f"    ⚠️ 표 데이터는 JSON 2D 배열로 생성: [[\"헤더1\", \"헤더2\"], [\"데이터1\", \"데이터2\"], ...]")
                    
                    # 현재 테이블 내용 미리보기 (처음 3행만)
                    cells = table_data.get('cells', [])
                    if cells:
                        for row_idx, row in enumerate(cells[:3]):
                            row_texts = [c.get('text', '')[:15] for c in row]
                            lines.append(f"    현재 Row{row_idx}: {row_texts}")
                        if len(cells) > 3:
                            lines.append(f"    ... ({len(cells) - 3}행 더 있음)")
                else:
                    content_preview = current_content[:80].replace('\n', ' / ')
                    if len(current_content) > 80:
                        content_preview += "..."
                    
                    # 요소 크기 힌트 (shape_width, shape_height 가 있으면)
                    width = elem.get('width_px', 0)
                    height = elem.get('height_px', 0)
                    size_hint = ""
                    if width > 0 and height > 0:
                        if width < 100 or height < 50:
                            size_hint = " [작은 요소 - 짧게]"
                        elif width > 500:
                            size_hint = " [넓은 요소 - 상세히]"
                    
                    lines.append(f"  - {elem_id} | {elem_role} | len={content_len}{size_hint}")
                    lines.append(f"    현재: \"{content_preview}\"")
            
            lines.append("")
        
        # 🆕 슬라이드 스타일 매칭 가이드 추가
        style_guide = self._create_style_matching_guide(slide_styles)
        
        # 🆕 v3.4: 슬라이드 유연성 분석 추가
        flexibility_info = self._analyze_slide_flexibility(metadata)
        flexibility_guide = self._create_flexibility_guide(flexibility_info)
        
        # 구조 요약 추가
        lines.insert(2, f"목차 항목 수: {toc_items_count}개")
        lines.insert(3, f"본문 슬라이드 수: {content_slides_count}개")
        lines.insert(4, f"편집 대상 요소: {editable_count}개 (제외됨: {skipped_count}개)")
        lines.insert(5, "")
        lines.insert(6, style_guide)
        lines.insert(7, "")
        lines.insert(8, flexibility_guide)
        lines.insert(9, "")
        
        return "\n".join(lines)
    
    def _create_style_matching_guide(self, slide_styles: List[Dict]) -> str:
        """슬라이드 스타일별 최적 콘텐츠 유형 가이드 생성"""
        
        style_recommendations = {
            'simple_text': '개요, 요약, 단순 설명',
            'image_with_text': '제품/서비스 소개, 개념 설명, 비전 제시',
            'numbered_cards': '단계별 프로세스, 핵심 기능 목록, 주요 특징 나열',
            'table_style': '스펙 비교, 데이터 요약, 상세 정보',
            'icon_boxes': '카테고리별 설명, 시스템 구성요소, 기능 분류',
            'card_grid': '여러 항목 비교, 옵션 나열, 서비스 패키지',
            'timeline': '일정, 로드맵, 단계별 진행',
            'comparison': '비교 분석, 장단점, Before/After',
        }
        
        lines = ["=== 슬라이드 스타일 매칭 가이드 ==="]
        lines.append("각 본문 슬라이드의 레이아웃에 맞는 콘텐츠를 배치하세요:")
        lines.append("")
        
        for item in slide_styles:
            style = item['style']
            idx = item['index']
            recommendation = style_recommendations.get(style, '일반 콘텐츠')
            lines.append(f"  - 슬라이드 {idx} ({style}): {recommendation}")
        
        return "\n".join(lines)
    
    def _create_flexibility_guide(self, flexibility_info: Dict[str, Any]) -> str:
        """
        🆕 v3.4: 슬라이드 유연성 및 대체 가이드 생성
        
        고정 요소가 많은 슬라이드에 대한 안내와 대체 옵션을 AI에게 제공합니다.
        """
        high_fixed_slides = flexibility_info.get('high_fixed_slides', [])
        replacement_candidates = flexibility_info.get('replacement_candidates', {})
        slide_flexibility = flexibility_info.get('slide_flexibility', {})
        
        if not high_fixed_slides:
            return ""  # 고정 비율 높은 슬라이드 없으면 생략
        
        lines = ["=== 🚨 슬라이드 대체 필수 검토 ==="]
        lines.append("다음 슬라이드는 고정 요소(도식/아이콘)가 많아 주제와 맞지 않을 가능성이 높습니다.")
        lines.append("반드시 내용을 확인하고, 주제와 맞지 않으면 'slide_replacements'를 사용하여 대체하세요.")
        lines.append("")
        
        for slide_idx in high_fixed_slides:
            info = slide_flexibility.get(slide_idx, {})
            fixed_ratio = info.get('fixed_ratio', 0) * 100
            style = info.get('style', 'unknown')
            
            lines.append(f"  - 슬라이드 {slide_idx}: 고정 {fixed_ratio:.0f}% ({style})")
            
            # 대체 후보가 있으면 안내
            if slide_idx in replacement_candidates:
                candidates = replacement_candidates[slide_idx]
                lines.append(f"    💡 추천 대체안: 슬라이드 {candidates} (더 유연함)")
            else:
                lines.append(f"    ⚠️ 대체 후보 없음 (콘텐츠를 최대한 맞춰보세요)")
        
        lines.append("")
        lines.append("📌 대체 방법: JSON 응답에 'slide_replacements' 필드를 반드시 포함하세요.")
        lines.append("   예: \"slide_replacements\": [{\"original\": 6, \"replacement\": 7, \"reason\": \"도식이 주제와 무관\"}]")
        
        return "\n".join(lines)
    
    def _load_prompt_template(self) -> str:
        """프롬프트 템플릿 파일 로드"""
        try:
            if AI_DIRECT_MAPPING_PROMPT_FILE.exists():
                return AI_DIRECT_MAPPING_PROMPT_FILE.read_text(encoding='utf-8')
            else:
                logger.warning(f"프롬프트 파일 없음: {AI_DIRECT_MAPPING_PROMPT_FILE}, 기본 프롬프트 사용")
                return self._get_default_prompt_template()
        except Exception as e:
            logger.warning(f"프롬프트 파일 로드 실패: {e}, 기본 프롬프트 사용")
            return self._get_default_prompt_template()
    
    def _get_default_prompt_template(self) -> str:
        """기본 프롬프트 템플릿 (파일 로드 실패 시 사용)"""
        return """당신은 프레젠테이션 콘텐츠 전문가입니다.
사용자의 요청에 맞게 템플릿의 각 요소에 들어갈 콘텐츠를 생성해주세요.

## 사용자 요청
{user_query}

## 템플릿 구조
{template_spec}

{additional_context}

## 출력 형식 (JSON)
```json
{{
  "presentation_title": "프레젠테이션 제목",
  "mappings": [
    {{"element_id": "textbox-0-0", "content": "새 콘텐츠"}},
    ...
  ],
  "slide_replacements": [
    {{"original": 6, "replacement": 7, "reason": "도식이 주제와 무관"}}
  ]
}}
```

JSON만 출력하세요."""
    
    def _create_prompt(
        self, 
        user_query: str, 
        template_spec: str,
        additional_context: Optional[str]
    ) -> str:
        """AI 프롬프트 생성 - 프롬프트 파일에서 로드"""
        
        # 프롬프트 템플릿 로드
        prompt_template = self._load_prompt_template()
        
        # 추가 컨텍스트 포맷
        additional_section = ""
        if additional_context:
            additional_section = f"## 추가 참고 자료\n{additional_context}"
        
        # 템플릿 변수 치환
        prompt = prompt_template.format(
            user_query=user_query,
            template_spec=template_spec,
            additional_context=additional_section,
        )
        
        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """LLM 호출"""
        
        if not self._ai_service:
            self._ai_service = AIService()
        
        messages = [
            {"role": "system", "content": "You are a presentation content expert. Output only valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._ai_service.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.get('response', '')
    
    def _parse_response(
        self, 
        response: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        AI 응답 파싱 및 매핑 리스트 생성
        
        Returns:
            {
                'mappings': [...],
                'slide_replacements': [...]  # 🆕 v3.4
            }
        """
        
        # JSON 추출
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        
        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"응답: {response[:500]}")
            raise ValueError(f"AI 응답 JSON 파싱 실패: {e}")
        
        # 🆕 v3.4: 슬라이드 대체 정보 추출
        slide_replacements = data.get('slide_replacements', [])
        if slide_replacements:
            logger.info(f"📋 슬라이드 대체 요청: {slide_replacements}")
        
        # element_id → 상세 정보 매핑 테이블 생성
        id_to_info = {}
        editable_elements = []  # 🆕 편집 가능한 모든 요소 추적
        
        for slide in metadata.get('slides', []):
            slide_idx = slide.get('index', 1) - 1  # 1-based → 0-based
            for elem in slide.get('elements', []):
                elem_id = elem.get('id', '')
                is_fixed = elem.get('is_fixed', False)
                elem_type = elem.get('type', '')
                
                elem_info = {
                    'original_name': elem.get('original_name', ''),
                    'slide_index': slide_idx,
                    'element_role': elem.get('element_role', ''),
                    'is_fixed': is_fixed,
                    'type': elem_type
                }
                
                # 🆕 v3.3: 테이블 정보 저장 (미매핑 시 구조 활용)
                if elem_type == 'table':
                    table_data = elem.get('table_data', {})
                    elem_info['table_data'] = table_data
                    elem_info['rows'] = table_data.get('rows', 0)
                    elem_info['cols'] = table_data.get('cols', 0)
                
                id_to_info[elem_id] = elem_info
                
                # 🆕 편집 가능 요소 목록
                if not is_fixed:
                    editable_elements.append(elem_id)
        
        # AI가 매핑한 element_id 추적
        ai_mapped_ids = set()
        
        # 매핑 리스트 생성
        mappings = []
        for item in data.get('mappings', []):
            elem_id = item.get('element_id', '')
            content = item.get('content', '')
            
            info = id_to_info.get(elem_id, {})
            ai_mapped_ids.add(elem_id)
            
            # 🆕 is_fixed 요소는 비활성화 (AI가 잘못 매핑한 경우 방지)
            is_fixed = info.get('is_fixed', False)
            is_enabled = not is_fixed
            
            if is_fixed:
                logger.debug(f"⚠️ 고정 요소 매핑 비활성화: {elem_id}")
            
            # 🆕 표(Table) 요소인 경우 특별 처리
            if elem_id.startswith('table-') and isinstance(content, list):
                # 2D 배열을 tableData 형식으로 변환
                headers = content[0] if content else []
                rows = content[1:] if len(content) > 1 else []
                
                mappings.append({
                    'slideIndex': info.get('slide_index', 0),
                    'elementId': elem_id,
                    'originalName': info.get('original_name', ''),
                    'objectType': 'table',
                    'action': 'replace_content',
                    'generatedText': '',  # 표는 텍스트가 아닌 tableData 사용
                    'metadata': {
                        'tableData': {
                            'headers': headers,
                            'rows': rows
                        }
                    },
                    'isEnabled': is_enabled,
                    'elementRole': info.get('element_role', '')
                })
            else:
                mappings.append({
                    'slideIndex': info.get('slide_index', 0),
                    'elementId': elem_id,
                    'originalName': info.get('original_name', ''),
                    'objectType': 'textbox',
                    'action': 'replace_content',
                    'generatedText': content if isinstance(content, str) else str(content),
                    'isEnabled': is_enabled,
                    'elementRole': info.get('element_role', '')
                })
        
        # 🆕 AI가 매핑하지 않은 편집 가능 요소 → 빈 문자열로 추가
        unmapped_count = 0
        unmapped_tables = []
        
        for elem_id in editable_elements:
            if elem_id not in ai_mapped_ids:
                info = id_to_info.get(elem_id, {})
                elem_type = info.get('type', '')
                
                # 🆕 v3.3: 테이블 미매핑은 심각한 문제 - 명시적 경고
                if elem_type == 'table' or elem_id.startswith('table-'):
                    rows = info.get('rows', 0)
                    cols = info.get('cols', 0)
                    unmapped_tables.append(f"{elem_id} ({rows}x{cols})")
                    
                    # 🆕 미매핑 테이블은 비활성화하여 원본 유지
                    mappings.append({
                        'slideIndex': info.get('slide_index', 0),
                        'elementId': elem_id,
                        'originalName': info.get('original_name', ''),
                        'objectType': 'table',
                        'action': 'replace_content',
                        'generatedText': '',
                        'metadata': {
                            'tableData': {
                                'headers': [],
                                'rows': []
                            }
                        },
                        'isEnabled': False,  # 🆕 비활성화하여 원본 테이블 유지
                        'elementRole': info.get('element_role', ''),
                        'unmapped_reason': 'AI가 테이블 데이터를 생성하지 않음'
                    })
                else:
                    mappings.append({
                        'slideIndex': info.get('slide_index', 0),
                        'elementId': elem_id,
                        'originalName': info.get('original_name', ''),
                        'objectType': 'textbox',
                        'action': 'replace_content',
                        'generatedText': '',  # 빈 문자열로 설정
                        'isEnabled': True,
                        'elementRole': info.get('element_role', '')
                    })
                unmapped_count += 1
        
        if unmapped_count > 0:
            logger.warning(f"⚠️ AI 미매핑 요소 {unmapped_count}개 → 빈 문자열로 설정")
        
        # 🆕 v3.3: 테이블 미매핑 시 강력한 경고
        if unmapped_tables:
            logger.error(f"🚨 AI가 테이블 {len(unmapped_tables)}개를 매핑하지 않음 (원본 유지): {unmapped_tables}")
        
        # 🆕 v3.4: 매핑과 슬라이드 대체 정보 함께 반환
        return {
            'mappings': mappings,
            'slide_replacements': slide_replacements
        }


# 싱글톤 인스턴스
ai_direct_mapping_tool = AIDirectMappingTool()

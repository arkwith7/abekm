"""Slide Type Matcher Tool - AI-powered slide type matching between outline and template."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.services.core.ai_service import ai_service
from app.core.config import settings


class SlideTypeMatcherInput(BaseModel):
    """Input schema for SlideTypeMatcherTool."""

    outline: Optional[Dict[str, Any]] = Field(default=None, description="Presentation outline (DeckSpec)")
    deck_spec: Optional[Dict[str, Any]] = Field(default=None, description="Alternative name for outline (DeckSpec)")
    template_metadata: Dict[str, Any] = Field(..., description="Template metadata with slide roles")
    user_id: Optional[int] = Field(default=None, description="User ID for context")


class SlideTypeMatcherTool(BaseTool):
    """
    AI-powered slide type matching tool.
    
    Intelligently matches AI-generated outline slides to template slides based on:
    - Slide role (title, toc, content, section, thanks)
    - Content characteristics (bullet count, has table/chart, etc.)
    - Semantic similarity
    
    Returns an optimal mapping that considers:
    - Which template slides to use for each content slide
    - Which template slides to skip (not needed)
    - Which template slides to duplicate (if more content than templates)
    """

    name: str = "slide_type_matcher_tool"
    description: str = (
        "Matches AI-generated outline slides to template slides based on their types and roles. "
        "Uses AI to intelligently determine: "
        "1) Which template slide is best for each content slide (title→title, content→content, etc.) "
        "2) Which template slides to skip if content has fewer slides "
        "3) Which template slides to reuse if content has more slides. "
        "Call this AFTER template_analyzer_tool and outline generation, BEFORE content_mapping_tool."
    )
    args_schema: Type[BaseModel] = SlideTypeMatcherInput

    async def _arun(
        self,
        outline: Optional[Dict[str, Any]] = None,
        deck_spec: Optional[Dict[str, Any]] = None,
        template_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Match slide types using AI reasoning.

        Args:
            outline: DeckSpec dictionary (primary)
            deck_spec: DeckSpec dictionary (alternative name)
            template_metadata: Template metadata with slide roles
            user_id: User ID for context

        Returns:
            Dict with slide matching results
        """
        logger.info(f"🎯 [SlideTypeMatcher] 시작: user_id={user_id}")

        try:
            # outline 또는 deck_spec 사용
            actual_outline = outline or deck_spec
            if not actual_outline:
                return {
                    "success": False,
                    "error": "outline 또는 deck_spec이 필요합니다",
                    "slide_matches": []
                }
            
            if not template_metadata:
                return {
                    "success": False,
                    "error": "template_metadata가 필요합니다",
                    "slide_matches": []
                }
            
            outline_slides = actual_outline.get('slides', [])
            template_slides = template_metadata.get('slides', [])
            
            if not outline_slides:
                return {
                    "success": False,
                    "error": "outline에 슬라이드가 없습니다",
                    "slide_matches": []
                }
            
            if not template_slides:
                return {
                    "success": False,
                    "error": "template에 슬라이드가 없습니다",
                    "slide_matches": []
                }
            
            logger.info(f"📊 outline 슬라이드: {len(outline_slides)}개, template 슬라이드: {len(template_slides)}개")
            
            # AI를 사용한 슬라이드 타입 매칭
            slide_matches = await self._ai_match_slides(outline_slides, template_slides)
            
            # 🆕 used_template_indices 계산 (순서대로)
            used_template_indices = []
            for match in slide_matches:
                tmpl_idx = match.get('template_index')
                if tmpl_idx is not None and tmpl_idx >= 0:
                    used_template_indices.append(tmpl_idx)
            
            # 결과에 매핑된 슬라이드 정보 추가
            result = {
                "success": True,
                "slide_matches": slide_matches,
                "outline_slide_count": len(outline_slides),
                "template_slide_count": len(template_slides),
                "matched_count": len(slide_matches),
                "used_template_indices": used_template_indices,  # 🆕 추가
                "unused_template_slides": self._get_unused_template_slides(slide_matches, template_slides),
                "message": (
                    f"슬라이드 타입 매칭 완료: {len(outline_slides)}개 콘텐츠 슬라이드 → "
                    f"{len(template_slides)}개 템플릿 슬라이드 중 {len(slide_matches)}개 매칭. "
                    "다음 단계로 content_mapping_tool을 호출하세요."
                )
            }
            
            logger.info(f"✅ [SlideTypeMatcher] 완료: {len(slide_matches)}개 매칭")
            return result

        except Exception as e:
            logger.error(f"❌ [SlideTypeMatcher] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "slide_matches": []
            }

    async def _ai_match_slides(
        self,
        outline_slides: List[Dict[str, Any]],
        template_slides: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use AI to match outline slides to template slides."""
        
        # 1. outline 슬라이드 정보 추출
        outline_info = []
        for i, slide in enumerate(outline_slides):
            info = {
                "index": i,
                "title": slide.get('title', ''),
                "key_message": slide.get('key_message', ''),
                "bullet_count": len(slide.get('bullets', [])),
                "has_diagram": bool(slide.get('diagram')),
                "layout": slide.get('layout', ''),
                "inferred_role": self._infer_slide_role(slide, i, len(outline_slides))
            }
            outline_info.append(info)
        
        # 2. template 슬라이드 정보 추출
        template_info = []
        for slide in template_slides:
            # 템플릿 index는 이미 0-based이므로 그대로 사용
            # (template_analyzer_tool에서 0부터 시작하는 인덱스 사용)
            tmpl_idx = slide.get('index', 0)
            info = {
                "index": tmpl_idx,
                "layout_name": slide.get('layout_name', ''),
                "role": slide.get('role', 'content'),
                "role_confidence": slide.get('role_confidence', 0.5),
                "shapes_count": slide.get('shapes_count', 0),
                "textbox_count": self._count_textboxes(slide)
            }
            template_info.append(info)
        
        logger.info(f"📋 Outline 슬라이드 분석: {json.dumps(outline_info, ensure_ascii=False, indent=2)[:500]}...")
        logger.info(f"📋 Template 슬라이드 분석: {json.dumps(template_info, ensure_ascii=False, indent=2)[:500]}...")
        
        # 3. AI를 사용하여 최적 매칭 결정
        try:
            ai_matches = await self._call_ai_for_matching(outline_info, template_info)
            if ai_matches:
                return ai_matches
        except Exception as e:
            logger.warning(f"⚠️ AI 매칭 실패, 규칙 기반 폴백 사용: {e}")
        
        # 4. AI 실패 시 규칙 기반 매칭
        return self._rule_based_matching(outline_info, template_info)

    def _infer_slide_role(self, slide: Dict[str, Any], index: int, total: int) -> str:
        """Infer the role of an outline slide based on its content."""
        title = slide.get('title', '').lower()
        bullets = slide.get('bullets', [])
        
        # 첫 번째 슬라이드는 보통 표지
        if index == 0:
            return 'title'
        
        # 마지막 슬라이드 체크
        if index == total - 1:
            if any(kw in title for kw in ['감사', 'thank', 'q&a', '질문', 'q & a']):
                return 'thanks'
        
        # 목차 슬라이드 체크
        if any(kw in title for kw in ['목차', '순서', 'contents', 'agenda', 'table of contents']):
            return 'toc'
        
        # 섹션 헤더 체크 (번호로 시작하는 제목, 짧은 bullets)
        import re
        if re.match(r'^\d+\.?\s*\w', title) and len(bullets) <= 2:
            return 'section'
        
        # 기본은 content
        return 'content'

    def _count_textboxes(self, slide: Dict[str, Any]) -> int:
        """Count textboxes in a template slide."""
        shapes = slide.get('shapes', [])
        count = 0
        for shape in shapes:
            shape_type = shape.get('type', '').upper()
            if shape_type in ['TEXT_BOX', 'TEXTBOX']:
                count += 1
        return count

    async def _call_ai_for_matching(
        self,
        outline_info: List[Dict[str, Any]],
        template_info: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Call AI to determine optimal slide matching."""
        
        prompt = f"""당신은 PPT 슬라이드 매칭 전문가입니다.

## 작업
AI가 생성한 콘텐츠 슬라이드를 템플릿 슬라이드에 매칭해야 합니다.
각 콘텐츠 슬라이드에 가장 적합한 템플릿 슬라이드를 선택하세요.

## 콘텐츠 슬라이드 (AI 생성)
```json
{json.dumps(outline_info, ensure_ascii=False, indent=2)}
```

## 템플릿 슬라이드 (사용 가능)
```json
{json.dumps(template_info, ensure_ascii=False, indent=2)}
```

## 매칭 규칙
1. title 역할의 콘텐츠는 title 역할의 템플릿에 매칭
2. toc (목차) 콘텐츠는 toc 템플릿에 매칭
3. content/section 콘텐츠는 content/section 템플릿에 매칭
4. thanks 콘텐츠는 thanks 템플릿에 매칭
5. 템플릿 슬라이드는 재사용 가능 (여러 content 슬라이드가 같은 템플릿 사용 가능)
6. textbox 개수가 많은 템플릿이 bullet 개수가 많은 콘텐츠에 적합

## 출력 형식
JSON 배열로 응답하세요. 각 항목:
```json
[
  {{
    "outline_index": 0,
    "outline_title": "제목",
    "outline_role": "title",
    "template_index": 0,
    "template_role": "title",
    "match_reason": "제목 슬라이드 매칭"
  }},
  ...
]
```

JSON 배열만 출력하세요. 다른 설명은 불필요합니다."""

        try:
            provider = settings.get_current_llm_provider()
            response_text = ""
            
            async for chunk in ai_service.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                provider=provider
            ):
                if chunk:
                    if isinstance(chunk, str):
                        response_text += chunk
                    elif hasattr(chunk, 'text'):
                        response_text += str(chunk.text) if callable(chunk.text) else chunk.text
            
            # JSON 파싱
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                matches = json.loads(json_match.group())
                logger.info(f"✅ AI 매칭 결과: {len(matches)}개")
                return matches
            
        except Exception as e:
            logger.error(f"AI 매칭 호출 실패: {e}")
        
        return None

    def _rule_based_matching(
        self,
        outline_info: List[Dict[str, Any]],
        template_info: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rule-based slide matching as fallback."""
        matches = []
        
        # 역할별 템플릿 슬라이드 분류
        template_by_role: Dict[str, List[Dict[str, Any]]] = {
            'title': [],
            'toc': [],
            'content': [],
            'section': [],
            'thanks': []
        }
        
        for t in template_info:
            role = t.get('role', 'content')
            if role not in template_by_role:
                role = 'content'
            template_by_role[role].append(t)
        
        # content용 템플릿 풀 (content + section)
        content_pool = template_by_role['content'] + template_by_role['section']
        content_pool_idx = 0
        
        for outline in outline_info:
            o_idx = outline['index']
            o_role = outline['inferred_role']
            o_title = outline['title']
            
            matched_template = None
            match_reason = ""
            
            # 역할별 매칭
            if o_role == 'title' and template_by_role['title']:
                matched_template = template_by_role['title'][0]
                match_reason = "제목 슬라이드 역할 매칭"
            
            elif o_role == 'toc' and template_by_role['toc']:
                matched_template = template_by_role['toc'][0]
                match_reason = "목차 슬라이드 역할 매칭"
            
            elif o_role == 'thanks' and template_by_role['thanks']:
                matched_template = template_by_role['thanks'][0]
                match_reason = "감사 슬라이드 역할 매칭"
            
            elif o_role in ['content', 'section'] and content_pool:
                # content/section 슬라이드는 순환하며 할당
                matched_template = content_pool[content_pool_idx % len(content_pool)]
                content_pool_idx += 1
                match_reason = f"콘텐츠 슬라이드 순환 매칭 (pool index {content_pool_idx - 1})"
            
            # 폴백: 첫 번째 content 템플릿 사용
            if not matched_template and content_pool:
                matched_template = content_pool[0]
                match_reason = "폴백: 기본 콘텐츠 템플릿 사용"
            
            if matched_template:
                matches.append({
                    "outline_index": o_idx,
                    "outline_title": o_title,
                    "outline_role": o_role,
                    "template_index": matched_template['index'],
                    "template_role": matched_template.get('role', 'content'),
                    "match_reason": match_reason
                })
        
        logger.info(f"📋 규칙 기반 매칭 완료: {len(matches)}개")
        return matches

    def _get_unused_template_slides(
        self,
        matches: List[Dict[str, Any]],
        template_slides: List[Dict[str, Any]]
    ) -> List[int]:
        """Get list of unused template slide indices."""
        used_indices = set(m.get('template_index', -1) for m in matches)
        all_indices = set(s.get('index', 0) - 1 for s in template_slides)  # 0-based
        return sorted(all_indices - used_indices)

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
slide_type_matcher_tool = SlideTypeMatcherTool()

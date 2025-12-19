"""Outline Generation Tool - Extract structured outline from context text."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.services.presentation.ppt_models import DeckSpec, SlideSpec
from app.services.core.ai_service import ai_service


class OutlineGenerationInput(BaseModel):
    """Input schema for OutlineGenerationTool."""

    context_text: str = Field(..., description="AI 응답 또는 문서 내용 (마크다운 형식)")
    topic: str = Field(..., description="발표 주제/제목")
    max_slides: int = Field(default=8, description="최대 슬라이드 수")
    presentation_type: str = Field(default="general", description="프레젠테이션 유형")


class OutlineGenerationTool(BaseTool):
    """
    Generate structured presentation outline from context text.
    
    Parses markdown-formatted AI responses into a structured deck specification
    with title, sections, and bullet points for each slide.
    """

    name: str = "outline_generation_tool"
    description: str = (
        "Generates a structured presentation outline from context text. "
        "Parses markdown sections (##, ###) into slide specifications with "
        "titles, key messages, and bullet points."
    )
    args_schema: Type[BaseModel] = OutlineGenerationInput
    
    # 클래스 변수로 정의 (Pydantic 필드 검증 우회)
    max_sections: int = 20

    async def _arun(
        self,
        context_text: str,
        topic: str,
        max_slides: int = 8,
        presentation_type: str = "general",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate outline asynchronously.

        Args:
            context_text: Markdown formatted text
            topic: Presentation title
            max_slides: Maximum number of slides
            presentation_type: Type of presentation

        Returns:
            Dict with deck specification and metadata
        """
        logger.info(f"🚀 [OutlineTool] 시작: topic='{topic[:50]}', max_slides={max_slides}")
        
        # 🆕 topic 정제: 요청 표현 제거 및 명사형 변환
        refined_topic = await self._refine_topic(topic)
        if refined_topic and refined_topic != topic:
            logger.info(f"📝 제목 정제: '{topic[:50]}' → '{refined_topic[:50]}'")
            topic = refined_topic

        try:
            # Pre-sanitize markdown
            sanitized_text = self._sanitize_markdown(context_text)

            # Parse sections
            parsed_title, sections = self._parse_sections(sanitized_text, max_slides)

            # 🔍 [Smart Fallback] 섹션이 너무 적으면 LLM으로 재생성 시도
            if len(sections) < min(3, max_slides):
                logger.warning(f"⚠️ 파싱된 섹션이 너무 적음 ({len(sections)}개). LLM을 사용하여 아웃라인 재생성을 시도합니다.")
                try:
                    regenerated_text = await self._generate_outline_with_llm(topic, context_text, max_slides)
                    if regenerated_text:
                        logger.info("🔄 LLM 재생성 완료. 다시 파싱합니다.")
                        new_title, new_sections = self._parse_sections(self._sanitize_markdown(regenerated_text), max_slides)
                        if len(new_sections) > len(sections):
                            logger.info(f"✅ 재생성 성공: {len(sections)} -> {len(new_sections)}개 섹션")
                            sections = new_sections
                            if new_title:
                                parsed_title = new_title
                        else:
                            logger.warning("⚠️ 재생성된 텍스트에서도 섹션을 충분히 찾지 못했습니다.")
                except Exception as llm_err:
                    logger.error(f"❌ LLM 재생성 중 오류: {llm_err}")

            if not sections:
                logger.warning("⚠️ 섹션 파싱 실패 - 폴백 슬라이드 생성")
                sections = self._create_fallback_sections(topic)

            # Prefer the markdown-extracted title if available (so we don't end up with generic titles).
            effective_topic = (parsed_title or "").strip() or topic

            # Build deck specification
            deck = self._build_deck_spec(effective_topic, sections, max_slides)

            logger.info(f"✅ [OutlineTool] 완료: {len(deck.slides)}개 슬라이드 생성")

            return {
                "success": True,
                "deck_spec": deck.model_dump(),
                "deck": deck.model_dump(),  # 레거시 호환
                "slide_count": len(deck.slides),
                "topic": deck.topic,
                "outline_text": regenerated_text if 'regenerated_text' in locals() and regenerated_text else context_text,
                "message": "아웃라인 생성 완료. 다음 단계로 quick_pptx_builder_tool을 호출하여 PPT 파일을 생성하세요."
            }

        except Exception as e:
            logger.error(f"❌ [OutlineTool] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "deck": None,
            }

    async def _refine_topic(self, topic: str) -> str:
        """요청 표현을 제거하고 명사형 제목으로 정제."""
        if not topic:
            return topic
        
        original = topic
        
        # 1. 후위 요청 표현 패턴 (끝에서부터 제거) - 더 포괄적으로 개선
        suffix_patterns = [
            r'\s*(에 대해|에 대한|에 관한|에 관해|을 위한|를 위한)\s*(PPT|ppt|프레젠테이션|발표\s*자료|슬라이드).*$',
            r'\s*(PPT|ppt|프레젠테이션|발표\s*자료|슬라이드)\s*(작성|생성|만들|제작).*$',
            r'\s*(작성|생성|만들어|제작)\s*(해|좀)?\s*(주세요|줘|줘요|주십시오|부탁).*$',
            r'\s*(해|좀)?\s*(주세요|줘|줘요|주십시오|부탁).*$',
            r'\s+PPT\s*$',
            r'\s+ppt\s*$',
        ]
        
        for pattern in suffix_patterns:
            topic = re.sub(pattern, '', topic, flags=re.IGNORECASE).strip()
        
        # 2. 전위 요청 표현 패턴 (앞에서부터 제거)
        prefix_patterns = [
            r'^(다음|아래|위)\s*(내용|주제)(에 대해|으로|로)?\s*',
        ]
        
        for pattern in prefix_patterns:
            topic = re.sub(pattern, '', topic, flags=re.IGNORECASE).strip()
        
        # 3. 조사 정리 (끝에 '의', '에', '를' 등이 남으면 제거)
        topic = re.sub(r'[의에를을가이]$', '', topic).strip()
        
        # 결과가 너무 짧으면 원본 반환
        if len(topic) < 3:
            topic = original
        
        # 4. 정규식으로 처리 안 된 복잡한 경우 LLM 사용
        if topic == original and any(word in original.lower() for word in ['작성', '해줘', '부탁', '만들', '생성']):
            try:
                prompt = (
                    f"다음 요청문에서 핵심 주제만 추출하여 명사형 제목으로 변환하세요. "
                    f"'PPT 작성', '해줘요' 같은 요청 표현은 모두 제거하고, 순수한 주제만 반환하세요.\n\n"
                    f"요청문: \"{original}\"\n\n"
                    f"예시:\n"
                    f"- 입력: '자동차산업 특허분석 방법론 PPT작성 해줘요' → 출력: '자동차산업 특허분석 방법론'\n"
                    f"- 입력: 'AI 기술 트렌드 발표 자료 만들어줘' → 출력: 'AI 기술 트렌드'\n"
                    f"- 입력: '2024 마케팅 전략' → 출력: '2024 마케팅 전략' (이미 명사형)\n\n"
                    f"명사형 제목만 출력하세요 (설명 없이):"
                )
                
                response_data = await ai_service.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                refined = response_data.get("response", "").strip()
                
                # 결과 검증 (너무 길거나 짧으면 원본 반환)
                if refined and 3 <= len(refined) <= 100:
                    return refined
                    
            except Exception as e:
                logger.warning(f"제목 정제 LLM 호출 실패: {e}")
        
        return topic
    
    async def _generate_outline_with_llm(self, topic: str, context: str, max_slides: int) -> Optional[str]:
        """Generate a structured outline using LLM when parsing fails."""
        prompt = (
            f"당신은 전문 프레젠테이션 기획자입니다.\n"
            f"주제 '{topic}'에 대해 {max_slides}장 내외의 프레젠테이션 아웃라인을 작성해주세요.\n"
            f"제공된 컨텍스트를 바탕으로 내용을 구성해야 합니다.\n\n"
            f"## 필수 형식 (Markdown)\n"
            f"- 메인 제목은 '# 제목' 또는 '## 제목'으로 시작\n"
            f"- 각 슬라이드는 '### 제목 [Layout: ...]' 형식으로 작성 (제목에 '슬라이드 1' 같은 번호나 접두어는 절대 붙이지 마세요. 순수한 제목만 작성)\n"
            f"- 각 슬라이드 하위에 '- 내용' 형태로 불릿 포인트 작성\n"
            f"- '🔑 **키 메시지**: ...' 형식으로 핵심 메시지 포함\n\n"
            f"## 🔴 목차 슬라이드 필수 규칙 (매우 중요!)\n"
            f"- 목차 슬라이드의 항목들은 반드시 실제 슬라이드 제목들과 정확히 일치해야 합니다\n"
            f"- 예: 실제 슬라이드 제목이 '제품 개요', '주요 기능', '기술 사양'이라면\n"
            f"  목차에도 정확히 '제품 개요', '주요 기능', '기술 사양'으로 표시\n"
            f"- 목차에 '01. 제품 개요' 형식의 번호를 넣을 수 있지만, 제목 텍스트 자체는 동일해야 함\n"
            f"- 목차 항목 개수는 실제 본문 슬라이드 개수와 동일해야 함\n\n"
            f"## 사용 가능한 레이아웃 태그 (적극 활용)\n"
            f"- [Layout: 2-Column]: 비교/대조 (좌우 2단)\n"
            f"- [Layout: Process]: 단계/흐름 (화살표 프로세스)\n"
            f"- [Layout: Grid]: 4분면/SWOT (2x2 그리드)\n"
            f"- [Layout: Title-and-Content]: 일반 목록 (기본값)\n\n"
            f"## 컨텍스트\n"
            f"{context[:4000]}\n\n"
            f"위 형식을 엄격히 준수하여 아웃라인을 생성해주세요."
        )
        
        try:
            # Use chat_completion with temperature=0.0 for reproducibility
            response_data = await ai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            return response_data.get("response")
        except Exception as e:
            logger.error(f"LLM 아웃라인 생성 실패: {e}")
            return None

    def _run(self, *args, **kwargs):
        """Synchronous wrapper for async _arun."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(*args, **kwargs))

    def _sanitize_markdown(self, text: str) -> str:
        """Remove code fences and normalize whitespace."""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Remove code fences
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*$", "", text, flags=re.MULTILINE)
        # Remove generic headers
        text = re.sub(r"(?m)^##\s*제목\s*슬라이드\s*$", "", text)
        # Remove duplicate consecutive headings
        text = self._remove_duplicate_headings(text)
        # Ensure spacing after headers
        text = re.sub(r"(?m)^(#{2,6}\s+[^\n]+)\n(?=\S)", r"\1\n\n", text)
        # Reduce excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _remove_duplicate_headings(self, text: str) -> str:
        """Remove consecutive duplicate headings."""
        lines = text.split('\n')
        processed = []
        last_heading = None

        for line in lines:
            heading_match = re.match(r'^(#{3,6})\s+(.+)', line.strip())
            if heading_match:
                current = (heading_match.group(1), heading_match.group(2).strip())
                if current != last_heading:
                    processed.append(line)
                    last_heading = current
            else:
                processed.append(line)
                if line.strip():
                    last_heading = None

        return '\n'.join(processed)

    def _parse_sections(self, text: str, max_slides: int) -> tuple[str, List[Dict[str, Any]]]:
        """
        Parse markdown into sections.
        
        Supports:
        - ## Main title
        - ### Section titles (numbered or not)
        - 🔑 **키 메시지**: pattern
        - 📝 **상세 설명**: pattern
        - Bullet points (-, •, *)
        - Numbered lists (1990년대:, 1), 2), etc.)
        """
        lines = [ln.rstrip() for ln in text.splitlines() if ln is not None]
        total = len(lines)
        logger.info(f"📄 총 라인 수: {total}")
        
        # 디버그: 처음 10줄 출력
        if total > 0:
            preview = '\n'.join(lines[:min(10, total)])
            logger.debug(f"📝 입력 텍스트 미리보기:\n{preview}")

        sections: List[Dict[str, Any]] = []
        presentation_title = ""
        toc_content = []
        i = 0

        # Regex patterns
        h2_regex = re.compile(r'^##\s+(.+)$')
        h3_regex = re.compile(r'^###\s+(.+)$')
        slide_regex = re.compile(r'^\[슬라이드\s*\d+\.?\s*(.*)\]')  # [슬라이드 N. 제목] 패턴 추가
        km_regex = re.compile(r'^🔑\s*(?:\*\*)?([^\*:]+)(?:\*\*)?:?\s*(.*)$')
        detail_regex = re.compile(r'^📝\s*(?:\*\*)?([^\*:]+)(?:\*\*)?:?\s*(.*)$')
        overview_regex = re.compile(r'^###\s*📋\s*발표\s*개요')
        toc_regex = re.compile(r'^###\s*(?:📑\s*)?발표\s*목차')
        summary_regex = re.compile(r'^###\s*감사합니다\s*$')
        layout_regex = re.compile(r'\[Layout:\s*([\w-]+)\]', re.IGNORECASE)

        # 1. Extract main title (H2)
        while i < total:
            line = lines[i].strip()
            h2_match = h2_regex.match(line)
            if h2_match:
                presentation_title = h2_match.group(1).strip()
                logger.info(f"🎯 발표 제목: '{presentation_title}'")
                break
            i += 1

        # 2. Parse H3 sections
        i = 0
        while i < total:
            line = lines[i].strip()
            h3_match = h3_regex.match(line)
            slide_match = slide_regex.match(line)

            if h3_match or slide_match:
                if h3_match:
                    slide_title = h3_match.group(1).strip()
                else:
                    slide_title = slide_match.group(1).strip()
                    # [슬라이드 N. 제목] 패턴에서 제목이 비어있으면 다음 줄을 제목으로 사용
                    if not slide_title and i + 1 < total:
                        next_line = lines[i+1].strip()
                        if next_line and not any(r.match(next_line) for r in [h3_regex, slide_regex, km_regex, detail_regex]):
                            slide_title = next_line
                            i += 1  # 다음 줄 소비

                # Extract Layout tag
                layout_type = "title-and-content"
                layout_match = layout_regex.search(slide_title)
                if layout_match:
                    layout_type = layout_match.group(1).lower()
                    slide_title = layout_regex.sub("", slide_title).strip()
                    logger.info(f"🎨 레이아웃 감지: {layout_type}")

                # Skip special slides
                if overview_regex.match(line):
                    logger.info("🏷️ 발표 개요 슬라이드 - 건너뜀")
                    i += 1
                    continue
                elif toc_regex.match(line):
                    logger.info("📑 목차 슬라이드 - 별도 처리")
                    toc_content = self._extract_toc(lines, i)
                    i += 1
                    continue
                elif summary_regex.match(line):
                    logger.info(f"🏁 마무리 슬라이드: '{slide_title}'")

                # Normalize numbered section titles
                normalized_title = re.sub(r'^\d+\.\s*', '', slide_title).strip()
                # Remove [슬라이드 N] prefix if present in the title itself
                normalized_title = re.sub(r'^\[?슬라이드\s*\d+\.?\]?\s*[:.]?\s*', '', normalized_title).strip()
                normalized_title = re.sub(r'^Slide\s*\d+\s*[:.]?\s*', '', normalized_title, flags=re.IGNORECASE).strip()
                # Remove redundant numbers like "1: " or "1. " again just in case
                normalized_title = re.sub(r'^\d+\s*[:.]\s*', '', normalized_title).strip()
                
                if normalized_title != slide_title:
                    logger.info(f"🔢 제목 정규화: '{slide_title}' → '{normalized_title}'")

                # Collect section content
                key_message = ""
                detail_bullets = []
                content_lines = []
                j = i + 1

                while j < total:
                    current = lines[j].strip()

                    # Stop at next H3 or Slide pattern
                    if h3_regex.match(current) or slide_regex.match(current):
                        break

                    # Collect all non-empty lines
                    if current:
                        content_lines.append(current)

                    # Extract key message
                    km_match = km_regex.match(current)
                    if km_match:
                        # Group 1 is label, Group 2 is content
                        content = km_match.group(2).strip()
                        if content:
                            key_message = content
                            logger.info(f"🔑 키 메시지: '{key_message[:50]}...'")
                        else:
                            # If content is empty, maybe the label itself is the key message?
                            # Or it's just a header for bullets.
                            # Let's assume it's a header and try to use next lines as bullets.
                            pass

                    # Extract detail section
                    elif detail_regex.match(current):
                        detail_match = detail_regex.match(current)
                        # Group 1 is label, Group 2 is content
                        content = detail_match.group(2).strip()
                        if content:
                            detail_bullets.append(content)

                        k = j + 1
                        while k < total:
                            bullet_line = lines[k].strip()
                            if not bullet_line:
                                k += 1
                                continue
                            if h3_regex.match(bullet_line) or slide_regex.match(bullet_line) or km_regex.match(bullet_line) or detail_regex.match(bullet_line):
                                break
                            if bullet_line.startswith(('-', '•', '*')):
                                detail_bullets.append(bullet_line.lstrip('-•* ').strip()[:300])
                            elif len(bullet_line) > 3:
                                detail_bullets.append(bullet_line[:300])
                            k += 1
                        j = k - 1

                    # Direct bullet collection
                    elif current.startswith(('-', '•', '*')):
                        bullet_text = current.lstrip('-•* ').strip()
                        if bullet_text:
                            detail_bullets.append(bullet_text[:300])

                    # Year-based bullets (1990년대:, 2000년대:)
                    elif re.match(r'^\d{4}년대:', current) or re.match(r'^\d+\)', current):
                        detail_bullets.append(current[:300])

                    # Keyword-based bullets
                    elif len(current) > 10 and any(kw in current for kw in ["기능", "특징", "장점", "요구사항", "분석", "도입", "중심"]):
                        detail_bullets.append(current[:300])

                    # Catch-all for "Title: Description" style lines that look like bullets
                    elif ':' in current and not current.endswith(':') and len(current) < 200:
                        # Simple heuristic: if it has a colon and isn't a header, treat as bullet
                        detail_bullets.append(current[:300])

                    j += 1

                # Fallback: use content_lines if no bullets found
                if not detail_bullets and content_lines:
                    if not key_message and content_lines:
                        key_message = content_lines[0][:200]
                        detail_bullets = [line[:300] for line in content_lines[1:8] if len(line) > 5]
                    else:
                        detail_bullets = [line[:300] for line in content_lines[:8] if len(line) > 5]

                    if detail_bullets:
                        logger.info(f"🔄 폴백: {len(detail_bullets)}줄을 불릿으로 변환")

                # Add section if title exists (skip TOC-like titles since we generate TOC separately)
                if slide_title:
                    final_title = normalized_title if normalized_title != slide_title else slide_title
                    
                    # Skip if this looks like a TOC slide (we generate it separately in _build_deck_spec)
                    toc_title_pattern = re.compile(r'^(?:📑\s*)?발표\s*목차$|^목차$|^Table\s*of\s*Contents?$', re.IGNORECASE)
                    if toc_title_pattern.match(final_title.strip()):
                        logger.info(f"⏭️ 목차 슬라이드 건너뜀 (별도 생성): '{final_title}'")
                        i = j
                        continue
                    
                    sections.append({
                        'title': final_title,
                        'key_message': key_message or f"{final_title}의 핵심 내용입니다.",
                        'bullets': detail_bullets[:8] if detail_bullets else ["주요 내용을 여기에 작성합니다."],
                        'slide_type': 'summary' if summary_regex.match(line) else 'content',
                        'layout': layout_type
                    })
                    logger.info(f"📄 슬라이드 추가: '{final_title}' (layout: {layout_type})")

                    if len(sections) >= max_slides:
                        break

                i = j
                continue

            i += 1

        logger.info(f"✅ 섹션 파싱 완료: {len(sections)}개")
        return presentation_title.strip(), sections

    def _extract_toc(self, lines: List[str], start_idx: int) -> List[str]:
        """Extract table of contents items."""
        toc = []
        i = start_idx + 1
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('###'):
                break
            if line.startswith(('-', '•', '*', '1.', '2.', '3.')):
                item = line.lstrip('-•* ').strip()
                item = re.sub(r'^\d+\.\s*', '', item)
                if item:
                    toc.append(item)
            i += 1
        logger.info(f"📑 목차 항목 {len(toc)}개 추출")
        return toc

    def _create_fallback_sections(self, topic: str) -> List[Dict[str, Any]]:
        """Create fallback sections when parsing fails."""
        return [
            {
                'title': topic,
                'key_message': "발표의 핵심 내용을 한 문장으로 요약",
                'bullets': ["발표 목적 및 배경", "대상 청중", "예상 소요 시간: 10분"],
                'slide_type': 'title'
            },
            {
                'title': "주요 내용",
                'key_message': "핵심 주제에 대한 상세 내용",
                'bullets': ["주요 특징 및 장점", "실무 적용 방안", "기대 효과"],
                'slide_type': 'content'
            }
        ]

    def _build_deck_spec(self, topic: str, sections: List[Dict[str, Any]], max_slides: int) -> DeckSpec:
        """Build DeckSpec from parsed sections."""
        slides = []

        # Normalize topic (remove "PPT", redundant words)
        normalized_topic = re.sub(r'\s*PPT\s*$', '', topic, flags=re.IGNORECASE).strip()
        normalized_topic = re.sub(r'\s*(발표)?자료\s*$', '', normalized_topic).strip()

        # 1. Title slide
        title_info = sections[0] if sections and sections[0].get('slide_type') == 'title' else None
        if title_info:
            slides.append(SlideSpec(
                title=normalized_topic,
                key_message=title_info.get('key_message', ''),
                bullets=title_info.get('bullets', []),
                layout='title-slide'
            ))
            sections = sections[1:]
        else:
            slides.append(SlideSpec(
                title=normalized_topic,
                key_message="발표의 핵심 내용",
                bullets=[],
                layout='title-slide'
            ))

        # 2. TOC slide (if >= 5 total slides expected)
        total_expected = len(sections) + 2  # title + closing
        if total_expected >= 5:
            toc_items = [s['title'] for s in sections[:10]]
            slides.append(SlideSpec(
                title='📑 발표 목차',
                key_message='',
                bullets=toc_items,
                layout='title-and-content'
            ))
            logger.info("✅ 목차 슬라이드 생성")

        # 3. Content slides
        has_summary = any(s.get('slide_type') == 'summary' for s in sections)
        for section in sections:
            if section.get('slide_type') == 'summary':
                slides.append(SlideSpec(
                    title=section['title'],
                    key_message=section.get('key_message', ''),
                    bullets=section.get('bullets', []),
                    layout='title-slide'
                ))
            else:
                slides.append(SlideSpec(
                    title=section['title'],
                    key_message=section.get('key_message', ''),
                    bullets=section.get('bullets', []),
                    layout=section.get('layout', 'title-and-content')
                ))

        # 4. Closing slide (if no summary exists)
        if not has_summary:
            slides.append(SlideSpec(
                title='감사합니다',
                key_message='',
                bullets=[],
                layout='title-slide'
            ))
            logger.info("✅ 마무리 슬라이드 추가")

        deck = DeckSpec(topic=normalized_topic, slides=slides, max_slides=len(slides))
        logger.info(f"🎉 DeckSpec 생성: {len(slides)}개 슬라이드")
        return deck


# Singleton instance
outline_generation_tool = OutlineGenerationTool()

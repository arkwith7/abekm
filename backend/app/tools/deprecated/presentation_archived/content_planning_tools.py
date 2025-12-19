"""Content Planning Tools for Presentation Agent."""
from __future__ import annotations

import json
import re
import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.services.core.ai_service import ai_service
from app.services.presentation.ppt_models import DeckSpec, SlideSpec, DiagramData, ChartData
from app.services.presentation.product_template_manager import product_template_manager
from app.services.presentation.dynamic_template_manager import dynamic_template_manager


class ContextAnalyzerTool(BaseTool):
    """Tool for analyzing context and extracting structured information."""
    
    name: str = "context_analyzer"
    description: str = "Analyze text context to extract title, sections, and data patterns."

    def _run(self, context_text: str, document_filename: Optional[str] = None) -> Dict[str, Any]:
        """Analyze context text synchronously."""
        return {
            "title": self._extract_clean_title(context_text, document_filename),
            "sections": self._extract_structured_sections(context_text),
            "key_value_blocks": self._extract_keyvalue_blocks(context_text)
        }

    async def _arun(self, context_text: str, document_filename: Optional[str] = None) -> Dict[str, Any]:
        """Analyze context text asynchronously."""
        return self._run(context_text, document_filename)

    def _extract_clean_title(self, text: str, document_filename: Optional[str] = None) -> str:
        """Extract a clean title from text or filename."""
        if not text:
            return ""
        
        lines = text.strip().split('\n')
        title_candidates = []
        
        first_line = lines[0].strip() if lines else ""
        if first_line and not re.match(r'^\d+\.', first_line) and len(first_line) <= 50:
            if len(lines) > 1:
                second_line = lines[1].strip() if len(lines) > 1 else ""
                if not second_line or re.match(r'^\d+\.', second_line):
                    return first_line
        
        for i, line in enumerate(lines[:10]):
            clean_line = re.sub(r'^[#>*\s]*', '', line).strip()
            if not clean_line or len(clean_line) <= 5:
                continue
            
            score = self._title_score(clean_line)
            if i == 0 and not any(word in clean_line.lower() for word in ['질문', '문의', '해주세요', '알려주세요', '입니다', '합니다']):
                score += 50
            if not re.match(r'^\d+\.', clean_line.strip()) and not clean_line.lower().startswith('목차'):
                score += 10
            if 10 <= len(clean_line) <= 50:
                score += 20
            elif len(clean_line) > 100:
                score -= 30
                
            title_candidates.append((clean_line, score))
        
        if title_candidates:
            best_title = max(title_candidates, key=lambda x: x[1])[0]
            if document_filename:
                doc_title = re.sub(r'\.(docx?|pdf|txt)$', '', document_filename, flags=re.IGNORECASE)
                doc_score = self._title_score(doc_title)
                best_score = max(title_candidates, key=lambda x: x[1])[1]
                return doc_title if doc_score > best_score + 10 else best_title
            return best_title
            
        if document_filename:
            return re.sub(r'\.(docx?|pdf|txt)$', '', document_filename, flags=re.IGNORECASE)
        return ""

    def _title_score(self, title: str) -> int:
        if not title:
            return -100
        t = title.strip()
        score = 0
        ln = len(t)
        if 8 <= ln <= 40:
            score += 40
        else:
            score += max(0, 40 - abs(ln - 24))
        
        high_value_keywords = ['제품', '시스템', '서비스', '개발', '분석', '보고서', '계획', '전략', '가이드', '로드맵']
        for kw in high_value_keywords:
            if kw in t:
                score += 16
        
        if re.search(r"(해주세요|해줘|알려줘|알려주세요|소개해줘|설명해줘|요약해줘|정리해줘)$", t):
            score -= 45
        if t.endswith('?'):
            score -= 30
        if t in ["발표자료", "프레젠테이션", "슬라이드"]:
            score -= 50
        return score

    def _extract_structured_sections(self, text: str) -> List[Dict[str, Any]]:
        sections = []
        lines = text.strip().split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            section_match = re.match(r'^(\d+)\.\s*(.+)$', line.strip())
            if section_match:
                if current_section:
                    sections.append({
                        'number': current_section['number'],
                        'title': current_section['title'],
                        'content': '\n'.join(current_content).strip()
                    })
                current_section = {
                    'number': int(section_match.group(1)),
                    'title': section_match.group(2).strip()
                }
                current_content = []
            elif current_section and line.strip():
                current_content.append(line.strip())
        
        if current_section:
            sections.append({
                'number': current_section['number'],
                'title': current_section['title'],
                'content': '\n'.join(current_content).strip()
            })
        return sections

    def _extract_keyvalue_blocks(self, text: str) -> List[Dict[str, Any]]:
        blocks = []
        lines = text.split('\n')
        current_block = []
        
        for line in lines:
            kv_match = re.match(r'^([^:]{1,25}):\s*(.{1,100})$', line.strip())
            if kv_match:
                key, value = kv_match.groups()
                if len(key.strip()) <= 15 and len(value.strip()) <= 30:
                    current_block.append({"key": key.strip(), "value": value.strip()})
            else:
                if len(current_block) >= 3:
                    blocks.append({
                        "type": "keyvalue",
                        "items": current_block.copy(),
                        "is_chart_candidate": self._is_chart_candidate(current_block)
                    })
                current_block = []
        
        if len(current_block) >= 3:
            blocks.append({
                "type": "keyvalue", 
                "items": current_block.copy(),
                "is_chart_candidate": self._is_chart_candidate(current_block)
            })
        return blocks

    def _is_chart_candidate(self, items: List[Dict[str, str]]) -> bool:
        if len(items) < 3:
            return False
        numeric_count = 0
        units = set()
        for item in items:
            value = item["value"]
            numeric_match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z가-힣%]*)', value)
            if numeric_match:
                numeric_count += 1
                unit = numeric_match.group(2).strip()
                if unit:
                    units.add(unit)
        return numeric_count >= 3 and len(units) <= 2


class OutlineGeneratorTool(BaseTool):
    """Tool for generating presentation outlines using LLM."""
    
    name: str = "outline_generator"
    description: str = "Generate a structured presentation outline (DeckSpec) from topic and context."
    
    context_analyzer: ContextAnalyzerTool = Field(default_factory=ContextAnalyzerTool)

    def generate_fixed_outline(self, topic: str, context_text: str, max_slides: int = 8) -> DeckSpec:
        """Generate a fixed structure outline without LLM (Quick Mode)."""
        max_slides = max(3, min(max_slides, 20))
        lines = [ln.strip() for ln in (context_text or "").split("\n") if ln.strip()]
        
        # 1. Find Headings
        headings = []
        for ln in lines:
            if (ln.startswith(('#', '##', '###', '####')) or 
                ln.endswith(':') or 
                (len(ln) <= 50 and any(word in ln for word in ['배경', '목표', '현황', '과제', '방안', '결론', '요약']))):
                headings.append(ln)
        
        # 2. Fallback to sentences
        if len(headings) < 2:
            sentences = [s.strip() for s in context_text.split('.') if s.strip() and len(s.strip()) > 10]
            headings = []
            for sent in sentences[:max_slides-3]:
                if len(sent) <= 60:
                    headings.append(sent)
                else:
                    headings.append(' '.join(sent.split()[:6]) + '...')
        
        sections = []
        content_lines = [ln for ln in lines if ln not in headings]
        
        for i, h in enumerate(headings[:max(0, max_slides-3)]):
            title = h.lstrip('#').strip(':').strip()
            start_idx = i * 2
            bullets = []
            for j in range(start_idx, min(start_idx + 3, len(content_lines))):
                if j < len(content_lines) and content_lines[j]:
                    bullets.append(content_lines[j][:80])
            
            if not bullets:
                bullets = [f"{title} Details", "Key Points", "Action Items"]
            
            sections.append({
                "title": title or f"Section {i+1}", 
                "key_message": f"Key details about {title}", 
                "bullets": bullets[:3]
            })
        
        slides = []
        slides.append(SlideSpec(title=topic or "Presentation", key_message="", bullets=[], layout="title-only"))
        slides.append(SlideSpec(title="Agenda", key_message="", bullets=[s["title"] for s in sections], layout="title-and-content"))
        for s in sections:
            slides.append(SlideSpec(title=s["title"], key_message=s["key_message"], bullets=s["bullets"], layout="title-and-content"))
        slides.append(SlideSpec(title="Thank You", key_message="Thank you for listening.", bullets=[], layout="title-only"))
        
        return DeckSpec(topic=topic or "Presentation", slides=slides, max_slides=len(slides))

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use _arun for async execution")

    async def _arun(
        self, 
        topic: str, 
        context_text: str, 
        provider: Optional[str] = None,
        template_style: str = "business", 
        include_charts: bool = True,
        retries: int = 2, 
        document_filename: Optional[str] = None,
        presentation_type: str = "general",
        user_template_id: Optional[str] = None
    ) -> DeckSpec:
        
        # 1. User Template Mode
        if user_template_id and user_template_id.startswith("user_"):
            return await self._generate_user_template_outline(
                topic, context_text, provider, template_style,
                include_charts, retries, document_filename, user_template_id
            )
        
        # 2. Product Introduction Mode
        if presentation_type == "product_introduction":
            return await self._generate_product_introduction_outline(
                topic, context_text, provider, template_style, 
                include_charts, retries, document_filename
            )
        
        # 3. General Mode
        return await self._generate_general_outline(
            topic, context_text, provider, template_style, 
            include_charts, retries, document_filename
        )

    async def _generate_general_outline(self, topic: str, context_text: str, provider: Optional[str],
                                      template_style: str, include_charts: bool, retries: int,
                                      document_filename: Optional[str]) -> DeckSpec:
        
        analysis = await self.context_analyzer._arun(context_text, document_filename)
        extracted_topic = analysis["title"]
        structured_sections = analysis["sections"]
        
        # Topic selection logic
        improved_topic = self._select_best_topic(topic, extracted_topic)
        
        # Prepare prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(
            improved_topic, context_text, template_style, include_charts, 
            structured_sections, analysis["key_value_blocks"]
        )
        
        # LLM Call
        last_err = None
        for attempt in range(retries + 1):
            try:
                current_prompt = user_prompt if attempt == 0 else user_prompt + f"\nPrevious Error: {last_err}. Retry JSON."
                resp = await ai_service.chat_completion([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_prompt},
                ], provider=provider)
                
                raw = resp.get("response", "").strip()
                deck = self._parse_outline(raw, improved_topic)
                return self._post_process_deck(deck, improved_topic)
                
            except Exception as e:
                last_err = str(e)
                logger.warning(f"Outline generation attempt {attempt+1} failed: {e}")
                if attempt == retries:
                    return self._create_fallback_deck(improved_topic, structured_sections)
        
        return self._create_fallback_deck(improved_topic, structured_sections)

    async def _generate_user_template_outline(self, topic: str, context_text: str, provider: Optional[str],
                                            template_style: str, include_charts: bool, retries: int,
                                            document_filename: Optional[str], user_template_id: str) -> DeckSpec:
        try:
            template_metadata = dynamic_template_manager.get_template_for_ai(user_template_id)
            if not template_metadata:
                return await self._generate_general_outline(topic, context_text, provider, template_style, include_charts, retries, document_filename)
            
            base_prompt = self._get_system_prompt()
            dynamic_prompt = dynamic_template_manager.generate_dynamic_prompt(user_template_id, base_prompt)
            
            # Build template-specific prompt
            user_content = [
                f"Topic: {topic}",
                f"Context:\n{context_text[:8000]}",
                "Template Requirements:",
                f"- Total Slides: {template_metadata['total_slides']}",
                f"- Template Name: {template_metadata['template_name']}",
                "Follow this structure:",
            ]
            for slide_struct in template_metadata['slide_structure_template'][:8]:
                user_content.append(f"  {slide_struct['slide_number']}. {slide_struct['title']} (Layout: {slide_struct['layout']})")
            
            user_content.append("\nOutput JSON only.")
            user_prompt = '\n'.join(user_content)
            
            for attempt in range(retries + 1):
                try:
                    resp = await ai_service.chat_completion([
                        {"role": "system", "content": dynamic_prompt},
                        {"role": "user", "content": user_prompt},
                    ], provider=provider)
                    
                    raw = resp.get("response", "").strip()
                    deck = self._parse_outline(raw, topic)
                    enhanced_deck = dynamic_template_manager.apply_template_to_outline(user_template_id, deck.dict())
                    return DeckSpec(**enhanced_deck)
                except Exception as e:
                    if attempt == retries: raise
                    continue
                    
        except Exception as e:
            logger.error(f"User template generation failed: {e}")
            return await self._generate_general_outline(topic, context_text, provider, template_style, include_charts, retries, document_filename)

    async def _generate_product_introduction_outline(self, topic: str, context_text: str, provider: Optional[str],
                                                   template_style: str, include_charts: bool, retries: int,
                                                   document_filename: Optional[str]) -> DeckSpec:
        try:
            product_outline = product_template_manager.generate_product_outline(context_text, product_type="medical_device")
            
            slides = []
            for slide_data in product_outline.get("slides", []):
                diagram = None
                if slide_data.get("diagram"):
                    d_data = slide_data["diagram"]
                    diagram = DiagramData(type=d_data.get("type", "none"), data=d_data.get("data", {}), chart=None)
                
                slides.append(SlideSpec(
                    title=slide_data.get("title", ""),
                    key_message=slide_data.get("key_message", ""),
                    bullets=slide_data.get("bullets", []),
                    layout=slide_data.get("layout", "title-and-content"),
                    style=slide_data.get("style", {}),
                    diagram=diagram,
                    visual_suggestion=slide_data.get("visual_suggestion"),
                    speaker_notes=slide_data.get("speaker_notes")
                ))
            
            return DeckSpec(
                topic=product_outline.get("topic", topic),
                max_slides=len(slides),
                slides=slides,
                theme=product_outline.get("theme", {"color_scheme": "medical_blue"})
            )
        except Exception as e:
            logger.error(f"Product introduction generation failed: {e}")
            return await self._generate_general_outline(topic, context_text, provider, template_style, include_charts, retries, document_filename)

    def _select_best_topic(self, provided_topic: str, extracted_topic: str) -> str:
        provided_topic = (provided_topic or "").strip()
        if not provided_topic:
            return extracted_topic or "Presentation"
        
        # Simple heuristic: if provided topic looks like a query, prefer extracted
        if any(x in provided_topic for x in ["해주세요", "해줘", "create", "make"]):
            return extracted_topic or provided_topic
        return provided_topic

    def _get_system_prompt(self) -> str:
        return (
            "You are a professional presentation designer. Output JSON only. "
            "Fields: topic,max_slides,slides[].title,key_message,bullets,layout,diagram,visual_suggestion,speaker_notes"
        )

    def _build_user_prompt(self, topic: str, context: str, style: str, charts: bool, sections: List, kv_blocks: List) -> str:
        reqs = [
            f"Topic: {topic}",
            f"Context:\n{context[:8000]}",
            "Requirements:",
            "- Create separate slides for numbered sections",
            "- Use bullets for details",
            "- Include 'Agenda' as the second slide",
            f"- Include Charts: {charts}",
            f"- Style: {style}",
            "- JSON output only"
        ]
        if sections:
            reqs.append(f"Detected Sections: {json.dumps([{k:v for k,v in s.items() if k!='content'} for s in sections], ensure_ascii=False)}")
        return "\n".join(reqs)

    def _parse_outline(self, text: str, fallback_topic: str) -> DeckSpec:
        try:
            # Extract JSON block
            if "```" in text:
                text = re.search(r"```(?:json)?\n(.*)```", text, re.DOTALL).group(1)
            elif "{" in text:
                text = text[text.find("{"):text.rfind("}")+1]
            
            data = json.loads(text)
            slides = []
            for s in data.get("slides", []):
                diagram = DiagramData(type="none", data={}, chart=None)
                if s.get("diagram"):
                    d = s["diagram"]
                    chart = None
                    if d.get("chart"):
                        chart = ChartData(**d["chart"])
                    diagram = DiagramData(type=d.get("type", "none"), data=d.get("data", {}), chart=chart)
                
                slides.append(SlideSpec(
                    title=s.get("title", ""),
                    key_message=s.get("key_message", ""),
                    bullets=s.get("bullets", []),
                    diagram=diagram,
                    layout=s.get("layout", "title-and-content"),
                    visual_suggestion=s.get("visual_suggestion"),
                    speaker_notes=s.get("speaker_notes"),
                    style=s.get("style")
                ))
            
            return DeckSpec(
                topic=data.get("topic", fallback_topic),
                max_slides=len(slides),
                slides=slides,
                theme=data.get("theme", {})
            )
        except Exception as e:
            logger.error(f"JSON Parse Error: {e}")
            raise

    def _post_process_deck(self, deck: DeckSpec, topic: str) -> DeckSpec:
        # Ensure Title and Agenda
        if not deck.slides or deck.slides[0].layout != "title-only":
            deck.slides.insert(0, SlideSpec(title=topic, layout="title-only", style={"role": "title"}))
        
        has_agenda = any(s.style and s.style.get("role") == "agenda" for s in deck.slides)
        if not has_agenda and len(deck.slides) > 2:
            agenda_items = [s.title for s in deck.slides[1:] if not s.title.lower() in ["agenda", "목차"]]
            deck.slides.insert(1, SlideSpec(title="Agenda", bullets=agenda_items[:8], layout="title-and-content", style={"role": "agenda"}))
        
        return deck

    def _create_fallback_deck(self, topic: str, sections: List[Dict]) -> DeckSpec:
        slides = [SlideSpec(title=topic, layout="title-only")]
        if sections:
            slides.append(SlideSpec(title="Agenda", bullets=[s["title"] for s in sections], layout="title-and-content"))
            for s in sections[:8]:
                slides.append(SlideSpec(title=s["title"], bullets=[s["content"][:100]], layout="title-and-content"))
        else:
            slides.append(SlideSpec(title="Overview", bullets=["Key Point 1", "Key Point 2"], layout="title-and-content"))
        
        return DeckSpec(topic=topic, max_slides=len(slides), slides=slides)

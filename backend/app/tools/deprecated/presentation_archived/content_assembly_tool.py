"""
Content Assembly Tool for Enhanced PPT Generation

다양한 소스의 콘텐츠를 조립하여 최종 DeckSpec을 생성하는 도구

Author: Presentation System
Created: 2025-01-20
Phase: 2.2
"""

import logging
from typing import Any, Dict, List, Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.presentation.ppt_models import DeckSpec, SlideSpec

logger = logging.getLogger(__name__)


class ContentAssemblyInput(BaseModel):
    """Input schema for ContentAssemblyTool"""
    topic: str = Field(..., description="프레젠테이션 주제")
    content_segments: List[Dict[str, Any]] = Field(
        ...,
        description="콘텐츠 세그먼트 리스트"
    )
    assembly_strategy: str = Field(
        default="sequential",
        description="조립 전략: sequential, hierarchical, thematic"
    )
    max_slides: int = Field(default=10, description="최대 슬라이드 수")
    include_toc: bool = Field(default=True, description="목차 슬라이드 포함 여부")


class ContentAssemblyTool(BaseTool):
    """
    여러 콘텐츠 소스를 조립하여 통합 DeckSpec을 생성하는 도구
    
    기능:
    - 다양한 소스의 콘텐츠 세그먼트 병합
    - 중복 제거 및 정규화
    - 슬라이드 순서 최적화
    - 목차 자동 생성
    - 슬라이드 개수 조정
    
    콘텐츠 세그먼트 형식:
    {
        "source": "search" | "document" | "ai" | "user",
        "title": "섹션 제목",
        "content": "본문 텍스트",
        "bullets": ["불릿1", "불릿2"],
        "metadata": {"priority": 1, "category": "intro"}
    }
    
    조립 전략:
    - sequential: 세그먼트 순서대로 조립
    - hierarchical: 계층 구조 기반 조립 (카테고리별 그룹화)
    - thematic: 주제별 유사도 기반 재배치
    
    출력:
    {
        "success": True,
        "deck": DeckSpec,
        "slide_count": 8,
        "segments_used": 5,
        "assembly_strategy": "sequential"
    }
    """
    
    name: str = "content_assembly_tool"
    description: str = (
        "여러 콘텐츠 소스를 조립하여 통합 DeckSpec을 생성합니다. "
        "중복 제거, 순서 최적화, 목차 생성을 수행합니다."
    )
    args_schema: Type[BaseModel] = ContentAssemblyInput
    
    def _run(self, *args, **kwargs):
        """Synchronous wrapper for async _arun."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(*args, **kwargs))

    async def _arun(
        self,
        topic: str,
        content_segments: List[Dict[str, Any]],
        assembly_strategy: str = "sequential",
        max_slides: int = 10,
        include_toc: bool = True,
    ) -> Dict[str, Any]:
        """
        콘텐츠 조립 (비동기)
        
        Args:
            topic: 프레젠테이션 주제
            content_segments: 콘텐츠 세그먼트 리스트
            assembly_strategy: 조립 전략
            max_slides: 최대 슬라이드 수
            include_toc: 목차 포함 여부
        
        Returns:
            Dict with DeckSpec and metadata
        """
        try:
            logger.info(f"🔧 [ContentAssembly] 시작: {len(content_segments)}개 세그먼트")
            logger.info(f"📊 전략: {assembly_strategy}, 최대 슬라이드: {max_slides}")
            
            # 세그먼트 전처리
            processed_segments = self._preprocess_segments(content_segments)
            logger.info(f"✅ 전처리 완료: {len(processed_segments)}개")
            
            # 조립 전략에 따라 슬라이드 생성
            if assembly_strategy == "hierarchical":
                slides = self._assemble_hierarchical(processed_segments, max_slides)
            elif assembly_strategy == "thematic":
                slides = self._assemble_thematic(processed_segments, max_slides)
            else:  # sequential (기본)
                slides = self._assemble_sequential(processed_segments, max_slides)
            
            logger.info(f"🎯 조립 완료: {len(slides)}개 본문 슬라이드")
            
            # DeckSpec 구성
            deck_slides = []
            
            # 1. 제목 슬라이드
            title_slide = SlideSpec(
                title=topic,
                key_message=f"{topic}에 대한 종합 발표 자료입니다.",
                bullets=[],
                slide_type="title"
            )
            deck_slides.append(title_slide)
            
            # 2. 목차 슬라이드 (선택)
            if include_toc and len(slides) > 3:
                toc_slide = self._create_toc_slide(slides)
                deck_slides.append(toc_slide)
            
            # 3. 본문 슬라이드들
            deck_slides.extend(slides)
            
            # 4. 마무리 슬라이드
            closing_slide = SlideSpec(
                title="감사합니다",
                key_message="질문이 있으시면 말씀해 주세요.",
                bullets=[],
                slide_type="closing"
            )
            deck_slides.append(closing_slide)
            
            # DeckSpec 생성
            deck = DeckSpec(
                topic=topic,
                total_slides=len(deck_slides),
                slides=deck_slides
            )
            
            logger.info(f"✅ [ContentAssembly] 완료: {len(deck_slides)}개 슬라이드")
            
            return {
                "success": True,
                "deck": deck.dict(),
                "slide_count": len(deck_slides),
                "segments_used": len(processed_segments),
                "assembly_strategy": assembly_strategy,
                "included_toc": include_toc and len(slides) > 3
            }
            
        except Exception as e:
            logger.error(f"❌ [ContentAssembly] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "deck": None,
            }

    def _preprocess_segments(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        세그먼트 전처리
        
        - 중복 제거
        - 빈 세그먼트 제거
        - 메타데이터 정규화
        - 우선순위 정렬
        """
        try:
            processed = []
            seen_titles = set()
            
            for seg in segments:
                title = seg.get('title', '').strip()
                if not title:
                    continue
                
                # 중복 제거 (제목 기준)
                if title in seen_titles:
                    logger.debug(f"  중복 제목 건너뛰기: '{title}'")
                    continue
                seen_titles.add(title)
                
                # 메타데이터 정규화
                metadata = seg.get('metadata', {})
                priority = metadata.get('priority', 5)  # 기본 우선순위 5
                category = metadata.get('category', 'general')
                
                processed_seg = {
                    'title': title,
                    'content': seg.get('content', ''),
                    'bullets': seg.get('bullets', []),
                    'key_message': seg.get('key_message', ''),
                    'source': seg.get('source', 'unknown'),
                    'priority': priority,
                    'category': category
                }
                processed.append(processed_seg)
            
            # 우선순위 정렬 (높은 우선순위가 앞으로)
            processed.sort(key=lambda x: x['priority'])
            
            return processed
            
        except Exception as e:
            logger.error(f"세그먼트 전처리 실패: {e}")
            return segments

    def _assemble_sequential(
        self,
        segments: List[Dict[str, Any]],
        max_slides: int
    ) -> List[SlideSpec]:
        """순차 조립: 세그먼트 순서대로 슬라이드 생성"""
        slides = []
        
        for i, seg in enumerate(segments[:max_slides - 3]):  # 제목/목차/마무리 공간 확보
            slide = SlideSpec(
                title=seg['title'],
                key_message=seg.get('key_message') or self._extract_key_message(seg),
                bullets=seg['bullets'][:8] if seg['bullets'] else self._extract_bullets(seg),
                slide_type="content"
            )
            slides.append(slide)
            logger.debug(f"  슬라이드 {i+1}: '{seg['title']}'")
        
        return slides

    def _assemble_hierarchical(
        self,
        segments: List[Dict[str, Any]],
        max_slides: int
    ) -> List[SlideSpec]:
        """
        계층 조립: 카테고리별로 그룹화하여 슬라이드 생성
        
        카테고리 순서: intro → main → detail → conclusion
        """
        # 카테고리별 그룹화
        category_order = ['intro', 'main', 'detail', 'analysis', 'conclusion', 'general']
        grouped = {cat: [] for cat in category_order}
        
        for seg in segments:
            category = seg.get('category', 'general')
            if category in grouped:
                grouped[category].append(seg)
            else:
                grouped['general'].append(seg)
        
        # 카테고리 순서대로 슬라이드 생성
        slides = []
        remaining_slots = max_slides - 3
        
        for category in category_order:
            if not grouped[category] or remaining_slots <= 0:
                continue
            
            for seg in grouped[category]:
                if remaining_slots <= 0:
                    break
                
                slide = SlideSpec(
                    title=seg['title'],
                    key_message=seg.get('key_message') or self._extract_key_message(seg),
                    bullets=seg['bullets'][:8] if seg['bullets'] else self._extract_bullets(seg),
                    slide_type="content"
                )
                slides.append(slide)
                remaining_slots -= 1
                logger.debug(f"  [{category}] '{seg['title']}'")
        
        return slides

    def _assemble_thematic(
        self,
        segments: List[Dict[str, Any]],
        max_slides: int
    ) -> List[SlideSpec]:
        """
        주제별 조립: 유사한 주제끼리 그룹화 (간단한 키워드 기반)
        
        실제 구현에서는 임베딩 기반 유사도를 사용할 수 있음
        """
        # 간단한 키워드 기반 그룹화 (실제로는 더 정교한 방법 사용)
        # 현재는 sequential과 동일하게 처리
        logger.info("  주제별 조립은 현재 순차 조립과 동일하게 처리됩니다.")
        return self._assemble_sequential(segments, max_slides)

    def _create_toc_slide(self, slides: List[SlideSpec]) -> SlideSpec:
        """목차 슬라이드 생성"""
        toc_items = [f"{i+1}. {slide.title}" for i, slide in enumerate(slides[:10])]
        
        return SlideSpec(
            title="📑 발표 목차",
            key_message=f"총 {len(slides)}개 주제로 구성된 발표입니다.",
            bullets=toc_items,
            slide_type="toc"
        )

    def _extract_key_message(self, segment: Dict[str, Any]) -> str:
        """세그먼트에서 키 메시지 추출"""
        # 1. content의 첫 문장 사용
        content = segment.get('content', '')
        if content:
            sentences = content.split('.')
            if sentences:
                return sentences[0].strip()[:200] + '.'
        
        # 2. 폴백: 제목 기반 메시지
        title = segment.get('title', '')
        return f"{title}에 대한 핵심 내용입니다."

    def _extract_bullets(self, segment: Dict[str, Any]) -> List[str]:
        """세그먼트에서 불릿 포인트 추출"""
        content = segment.get('content', '')
        if not content:
            return []
        
        # 간단한 문장 분할 (실제로는 더 정교한 방법 사용)
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        
        # 길이 제한 적용
        bullets = []
        for sent in sentences[:8]:
            if len(sent) > 10:  # 너무 짧은 문장 제외
                bullets.append(sent[:200])  # 최대 200자
        
        return bullets


# 전역 인스턴스
content_assembly_tool = ContentAssemblyTool()

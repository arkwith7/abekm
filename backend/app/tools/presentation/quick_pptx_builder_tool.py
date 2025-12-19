"""Quick PPTX Builder Tool - 원클릭 PPT 생성 도구 (템플릿 미적용)

이 도구는 outline_generation_tool에서 생성된 deck_spec을 받아
템플릿 없이 고정 구조로 PPTX 파일을 생성합니다.

생성 히스토리:
- 생성일: 2025-12-09
- 생성자: AI Assistant  
- 사유: react_agent_system.prompt에서 참조하는 도구 구현
        (quick_pptx_builder_tool이 프롬프트에 명시되어 있으나 미구현 상태였음)
- 연결 서비스: quick_ppt_generator_service.py (복원됨)

도구 명명 규칙:
- 논리적 이름: quick_pptx_builder_tool (프롬프트에서 참조)
- 물리적 파일: quick_pptx_builder_tool.py (이 파일)
- 서비스 파일: quick_ppt_generator_service.py (실제 로직)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.services.presentation.quick_ppt_generator_service import quick_ppt_service
from app.services.presentation.ppt_models import DeckSpec


class QuickPPTXBuilderInput(BaseModel):
    """Input schema for QuickPPTXBuilderTool."""
    
    deck_spec: Dict[str, Any] = Field(
        ..., 
        description="DeckSpec dictionary from outline_generation_tool containing topic, max_slides, and slides array"
    )
    file_basename: Optional[str] = Field(
        default=None, 
        description="Optional base filename for the output PPTX (without extension)"
    )


class QuickPPTXBuilderTool(BaseTool):
    """
    원클릭 PPT 빌더 도구 - 템플릿 없이 고정 구조로 PPTX 생성.
    
    outline_generation_tool에서 생성된 deck_spec을 받아 PPTX 파일을 생성합니다.
    이 도구는 템플릿을 적용하지 않으며, 고정된 3단계 레이아웃 구조를 사용합니다:
    - 표지 슬라이드 (제목)
    - 목차 슬라이드
    - 내용 슬라이드들 (제목 + 키메시지 + 불릿포인트)
    - 종료 슬라이드 (감사합니다)
    
    사용 예시 (에이전트 프롬프트에서):
    ```
    **Action**: quick_pptx_builder_tool
    **Action Input**: {"deck_spec": {"topic": "주제", "max_slides": 6, "slides": [...]}}
    ```
    """

    name: str = "quick_pptx_builder_tool"
    description: str = (
        "Builds a PPTX file from deck_spec without using templates. "
        "Takes the deck_spec from outline_generation_tool and creates a presentation "
        "with fixed layout: title slide, table of contents, content slides, and ending slide. "
        "Returns the file path of the generated PPTX."
    )
    args_schema: Type[BaseModel] = QuickPPTXBuilderInput

    async def _arun(
        self,
        deck_spec: Dict[str, Any],
        file_basename: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build PPTX file asynchronously.

        Args:
            deck_spec: DeckSpec dictionary containing topic, max_slides, slides
            file_basename: Optional base filename

        Returns:
            Dict with file path and metadata
        """
        logger.info(
            f"🏗️ [QuickPPTXBuilder] 시작: "
            f"topic='{deck_spec.get('topic', 'Unknown')[:30]}', "
            f"slides={len(deck_spec.get('slides', []))}"
        )

        try:
            # Parse DeckSpec from dictionary
            spec = DeckSpec(**deck_spec)
            
            # Build PPTX using quick service
            file_path = quick_ppt_service.build_quick_pptx(
                spec=spec,
                file_basename=file_basename
            )
            
            logger.info(f"✅ [QuickPPTXBuilder] 완료: {file_path}")
            
            return {
                "success": True,
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "slide_count": len(spec.slides),
                "topic": spec.topic,
                "message": f"Quick PPT generation complete. File saved at {file_path}. Please output Final Answer with this path."
            }

        except Exception as e:
            logger.error(f"❌ [QuickPPTXBuilder] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
            }

    def _run(self, *args, **kwargs):
        """Synchronous wrapper for async _arun."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(*args, **kwargs))


# Singleton instance - 에이전트에서 이 인스턴스를 import하여 사용
quick_pptx_builder_tool = QuickPPTXBuilderTool()

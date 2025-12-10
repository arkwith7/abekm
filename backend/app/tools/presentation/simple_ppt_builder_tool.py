"""
Simple PPT Builder Tool - AI-First Template PPT Generation

AI 매핑 결과를 받아 PPT를 생성하는 Tool.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.presentation.simple_ppt_builder import SimplePPTBuilder

logger = logging.getLogger(__name__)


class SimplePPTBuilderInput(BaseModel):
    """Simple PPT Builder Tool 입력 스키마"""
    template_path: str = Field(description="템플릿 PPT 파일 경로")
    mappings: List[Dict[str, Any]] = Field(description="AI가 생성한 매핑 리스트")
    output_filename: Optional[str] = Field(default=None, description="출력 파일명")


class SimplePPTBuilderTool(BaseTool):
    """
    AI 매핑 결과를 받아 PPT를 생성하는 단순화된 빌더 Tool.
    """
    
    name: str = "simple_ppt_builder_tool"
    description: str = """
    AI가 생성한 매핑을 템플릿 PPT에 적용하여 새 PPT를 생성합니다.
    
    입력:
    - template_path: 템플릿 PPT 파일 경로
    - mappings: AI 매핑 리스트 [{'slideIndex': 0, 'originalName': 'TextBox 1', 'newContent': '...'}, ...]
    - output_filename: 출력 파일명 (선택)
    
    출력:
    - file_path: 생성된 PPT 파일 경로
    """
    args_schema: type[BaseModel] = SimplePPTBuilderInput
    
    def _run(
        self,
        template_path: str,
        mappings: List[Dict[str, Any]],
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """동기 실행"""
        
        logger.info(f"🔨 [SimplePPTBuilderTool] 시작: {len(mappings)}개 매핑")
        
        try:
            builder = SimplePPTBuilder(template_path)
            result = builder.build(mappings, output_filename)
            
            if result.get('success'):
                logger.info(f"✅ [SimplePPTBuilderTool] 완료: {result.get('file_path')}")
            else:
                logger.error(f"❌ [SimplePPTBuilderTool] 실패: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [SimplePPTBuilderTool] 예외: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(
        self,
        template_path: str,
        mappings: List[Dict[str, Any]],
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """비동기 실행 (동기 래핑)"""
        return self._run(template_path, mappings, output_filename)


# 싱글톤 인스턴스
simple_ppt_builder_tool = SimplePPTBuilderTool()

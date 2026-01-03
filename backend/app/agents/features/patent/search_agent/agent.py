"""
Patent Search Agent - 특허 검색 에이전트

키워드, 출원인, IPC 코드 기반 특허 검색 및 탐색을 위한 ReAct 에이전트.
간단한 검색 요청에 최적화되어 있습니다.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, Dict, Any, Sequence
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from app.services.core.ai_service import MultiVendorAIService
from app.agents.features.patent.tools.search import (
    UnifiedPatentSearchTool,
    PatentSimilaritySearchTool,
)
from app.agents.features.patent.tools.analysis import (
    PatentTrendAnalysisTool,
)


# =============================================================================
# Agent State & Config
# =============================================================================

class PatentSearchConfig(BaseModel):
    """검색 에이전트 설정"""
    max_iterations: int = Field(default=5, description="최대 반복 횟수")
    default_jurisdiction: str = Field(default="KR", description="기본 관할권")
    default_max_results: int = Field(default=30, description="기본 최대 결과 수")


SEARCH_AGENT_SYSTEM_PROMPT = """당신은 특허 검색 전문가입니다.

## 역할
사용자의 특허 검색 요청을 이해하고 적절한 도구를 사용하여 정확한 결과를 제공합니다.

## 사용 가능한 도구
1. **unified_patent_search**: 키워드, 출원인, IPC 코드로 특허 검색
2. **patent_similarity_search**: 참조 특허와 유사한 특허 검색
3. **patent_trend_analysis**: 특허 트렌드 분석 (간단한 통계)

## 검색 전략
1. 사용자 요청에서 핵심 키워드, 출원인, 기술 분야를 파악합니다.
2. 적절한 검색 도구를 선택합니다:
   - 일반 키워드 검색 → unified_patent_search
   - 특정 특허와 유사한 것 찾기 → patent_similarity_search
   - 기술 트렌드 파악 → patent_trend_analysis
3. 검색 결과를 명확하게 요약합니다.

## 응답 형식
- 검색 결과는 표 형식으로 정리
- 핵심 특허 3-5건 강조
- 관련 IPC 코드 설명 포함

## 주의사항
- 출원인 검색 시 회사명의 다양한 표기를 고려 (예: "삼성전자", "Samsung Electronics")
- IPC 코드가 언급되면 해당 코드로 필터링
- 날짜 범위가 주어지면 반드시 적용
"""


# =============================================================================
# Patent Search Agent
# =============================================================================

class PatentSearchAgent:
    """
    특허 검색 에이전트
    
    ReAct 패턴을 사용하여 특허 검색 요청을 처리합니다.
    """
    
    def __init__(
        self,
        config: Optional[PatentSearchConfig] = None,
        ai_service: Optional[MultiVendorAIService] = None,
    ):
        self.config = config or PatentSearchConfig()
        self._ai_service = ai_service
        self._agent = None
        self._tools: List[BaseTool] = []
    
    def _get_ai_service(self) -> MultiVendorAIService:
        """AI 서비스 지연 초기화"""
        if self._ai_service is None:
            self._ai_service = MultiVendorAIService()
        return self._ai_service
    
    def _get_tools(self) -> List[BaseTool]:
        """도구 목록 반환"""
        if not self._tools:
            self._tools = [
                UnifiedPatentSearchTool(),
                PatentSimilaritySearchTool(),
                PatentTrendAnalysisTool(),
            ]
        return self._tools
    
    def _get_agent(self):
        """ReAct 에이전트 생성"""
        if self._agent is None:
            ai_service = self._get_ai_service()
            llm = ai_service.get_chat_model()
            tools = self._get_tools()
            
            self._agent = create_react_agent(
                model=llm,
                tools=tools,
                state_modifier=SEARCH_AGENT_SYSTEM_PROMPT,
            )
        return self._agent
    
    async def search(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        특허 검색 실행
        
        Args:
            query: 사용자 검색 요청
            context: 추가 컨텍스트 (선택)
        
        Returns:
            검색 결과 및 에이전트 응답
        """
        start_time = datetime.now()
        
        try:
            agent = self._get_agent()
            
            # 메시지 구성
            messages = [HumanMessage(content=query)]
            
            # 컨텍스트가 있으면 추가
            if context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
                messages[0] = HumanMessage(
                    content=f"컨텍스트:\n{context_str}\n\n요청: {query}"
                )
            
            # 에이전트 실행
            result = await agent.ainvoke(
                {"messages": messages},
                config={"recursion_limit": self.config.max_iterations * 2}
            )
            
            # 결과 추출
            final_message = result["messages"][-1]
            response_content = (
                final_message.content 
                if hasattr(final_message, 'content') 
                else str(final_message)
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "response": response_content,
                "messages": [
                    {
                        "role": "assistant" if isinstance(m, AIMessage) else "user",
                        "content": m.content if hasattr(m, 'content') else str(m),
                    }
                    for m in result["messages"]
                ],
                "execution_time_seconds": execution_time,
            }
            
        except Exception as e:
            logger.error(f"검색 에이전트 실행 실패: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                "success": False,
                "error": str(e),
                "execution_time_seconds": execution_time,
            }
    
    def search_sync(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """동기 검색 (비동기 래핑)"""
        return asyncio.run(self.search(query, context))


# =============================================================================
# Factory Function
# =============================================================================

def create_patent_search_agent(
    config: Optional[PatentSearchConfig] = None,
) -> PatentSearchAgent:
    """검색 에이전트 팩토리"""
    return PatentSearchAgent(config=config)


# =============================================================================
# Module-level singleton
# =============================================================================

_default_agent: Optional[PatentSearchAgent] = None


def get_patent_search_agent() -> PatentSearchAgent:
    """기본 검색 에이전트 반환 (싱글톤)"""
    global _default_agent
    if _default_agent is None:
        _default_agent = PatentSearchAgent()
    return _default_agent

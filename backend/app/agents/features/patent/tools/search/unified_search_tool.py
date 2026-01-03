"""
Patent Unified Search Tool - 통합 특허 검색 도구

다중 데이터 소스를 통합하여 특허 검색을 수행합니다.
- KIPRIS (한국)
- Google Patents (글로벌) - 향후 확장
- USPTO, EPO, JPO, CNIPA - 향후 확장
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    AggregatedSearchResult,
    PatentJurisdiction,
)
from app.agents.features.patent.clients import (
    PatentSourceAggregator,
    KiprisPatentClient,
)
from app.core.contracts import ToolResult


# =============================================================================
# Input/Output Models
# =============================================================================

class UnifiedSearchInput(BaseModel):
    """통합 검색 입력"""
    query: Optional[str] = Field(default=None, description="검색 키워드 (발명의 명칭, 초록 등)")
    applicant: Optional[str] = Field(default=None, description="출원인 이름")
    ipc_code: Optional[str] = Field(default=None, description="IPC 분류 코드")
    date_from: Optional[str] = Field(default=None, description="출원일 시작 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(default=None, description="출원일 종료 (YYYY-MM-DD)")
    jurisdictions: List[str] = Field(
        default=["KR"],
        description="검색 대상 관할권 (KR, US, EP, WO, JP, CN)"
    )
    max_results: int = Field(default=50, ge=1, le=500, description="최대 결과 수")
    sources: Optional[List[str]] = Field(
        default=None, 
        description="사용할 데이터 소스 (kipris, google_patents 등). None이면 모두 사용"
    )


class UnifiedSearchOutput(ToolResult):
    """통합 검색 출력"""
    patents: List[PatentData] = Field(default_factory=list, description="검색된 특허 목록")
    total_count: int = Field(default=0, description="총 결과 수")
    sources_used: List[str] = Field(default_factory=list, description="사용된 데이터 소스")
    search_params: Dict[str, Any] = Field(default_factory=dict, description="검색 파라미터")
    execution_time_ms: float = Field(default=0.0, description="실행 시간 (밀리초)")


# =============================================================================
# Unified Search Tool
# =============================================================================

class UnifiedPatentSearchTool(BaseTool):
    """
    통합 특허 검색 도구
    
    여러 특허 데이터베이스를 통합하여 검색합니다.
    현재 지원: KIPRIS (한국)
    향후 확장: Google Patents, USPTO, EPO, JPO, CNIPA
    """
    
    name: str = "unified_patent_search"
    description: str = """
    다중 소스 통합 특허 검색 도구.
    키워드, 출원인, IPC 코드, 날짜 범위로 특허를 검색합니다.
    
    사용 예:
    - 키워드 검색: query="인공지능 반도체"
    - 출원인 검색: applicant="삼성전자"
    - 복합 검색: query="배터리", applicant="LG에너지솔루션", ipc_code="H01M"
    """
    args_schema: type[BaseModel] = UnifiedSearchInput
    return_direct: bool = False
    
    # Private attributes
    _aggregator: Optional[PatentSourceAggregator] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self._aggregator = None
    
    def _get_aggregator(self) -> PatentSourceAggregator:
        """지연 초기화된 aggregator 반환"""
        if self._aggregator is None:
            self._aggregator = PatentSourceAggregator()
            # KIPRIS 클라이언트 등록 (자동 등록이 실패한 경우 수동 등록)
            if not self._aggregator.list_clients():
                try:
                    kipris = KiprisPatentClient()
                    self._aggregator.register_client(kipris)
                except Exception as e:
                    logger.warning(f"KIPRIS 클라이언트 등록 실패: {e}")
        return self._aggregator
    
    def _run(
        self,
        query: Optional[str] = None,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        jurisdictions: List[str] = None,
        max_results: int = 50,
        sources: Optional[List[str]] = None,
    ) -> UnifiedSearchOutput:
        """동기 실행 (비동기 래핑)"""
        return asyncio.run(self._arun(
            query=query,
            applicant=applicant,
            ipc_code=ipc_code,
            date_from=date_from,
            date_to=date_to,
            jurisdictions=jurisdictions or ["KR"],
            max_results=max_results,
            sources=sources,
        ))
    
    async def _arun(
        self,
        query: Optional[str] = None,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        jurisdictions: List[str] = None,
        max_results: int = 50,
        sources: Optional[List[str]] = None,
    ) -> UnifiedSearchOutput:
        """비동기 실행"""
        start_time = datetime.now()
        
        if jurisdictions is None:
            jurisdictions = ["KR"]
        
        # 입력 검증
        if not query and not applicant:
            return UnifiedSearchOutput(
                success=False,
                error="검색어(query) 또는 출원인(applicant) 중 하나는 필수입니다.",
                patents=[],
                total_count=0,
                sources_used=[],
                search_params={
                    "query": query,
                    "applicant": applicant,
                }
            )
        
        try:
            aggregator = self._get_aggregator()
            
            # 검색 쿼리 생성
            search_query = PatentSearchQuery(
                keywords=[query] if query else [],
                applicant=applicant,
                ipc_codes=[ipc_code] if ipc_code else [],
                date_from=date_from,
                date_to=date_to,
                jurisdictions=[PatentJurisdiction(j) for j in jurisdictions if j in PatentJurisdiction.__members__],
                max_results=max_results,
            )
            
            # 통합 검색 실행
            result: AggregatedSearchResult = await aggregator.search(
                query=search_query,
                sources=sources,
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return UnifiedSearchOutput(
                success=True,
                patents=result.patents,
                total_count=result.total_count,
                sources_used=result.sources,
                search_params={
                    "query": query,
                    "applicant": applicant,
                    "ipc_code": ipc_code,
                    "date_from": date_from,
                    "date_to": date_to,
                    "jurisdictions": jurisdictions,
                    "max_results": max_results,
                },
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(f"통합 특허 검색 실패: {e}")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return UnifiedSearchOutput(
                success=False,
                error=str(e),
                patents=[],
                total_count=0,
                sources_used=[],
                search_params={
                    "query": query,
                    "applicant": applicant,
                },
                execution_time_ms=execution_time,
            )


# =============================================================================
# Functional Tool (LangChain @tool 호환)
# =============================================================================

async def unified_patent_search(
    query: Optional[str] = None,
    applicant: Optional[str] = None,
    ipc_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    jurisdictions: Optional[List[str]] = None,
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    통합 특허 검색 함수
    
    Args:
        query: 검색 키워드
        applicant: 출원인 이름
        ipc_code: IPC 분류 코드
        date_from: 출원일 시작 (YYYY-MM-DD)
        date_to: 출원일 종료 (YYYY-MM-DD)
        jurisdictions: 검색 대상 관할권 목록
        max_results: 최대 결과 수
    
    Returns:
        검색 결과 딕셔너리
    """
    tool = UnifiedPatentSearchTool()
    result = await tool._arun(
        query=query,
        applicant=applicant,
        ipc_code=ipc_code,
        date_from=date_from,
        date_to=date_to,
        jurisdictions=jurisdictions or ["KR"],
        max_results=max_results,
    )
    return result.model_dump()


# =============================================================================
# Singleton Instance
# =============================================================================

# 재사용 가능한 기본 인스턴스
unified_search_tool = UnifiedPatentSearchTool()

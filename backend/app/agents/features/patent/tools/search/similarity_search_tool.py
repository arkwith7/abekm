"""
Patent Similarity Search Tool - 유사 특허 검색 도구

특정 특허와 유사한 특허를 찾는 도구입니다.
키워드 추출 및 IPC 코드 기반 유사도 검색을 수행합니다.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    PatentJurisdiction,
)
from app.agents.features.patent.core.utils import (
    extract_keywords,
    parse_ipc_code,
)
from app.agents.features.patent.clients import PatentSourceAggregator
from app.core.contracts import ToolResult


# =============================================================================
# Input/Output Models
# =============================================================================

class SimilaritySearchInput(BaseModel):
    """유사 특허 검색 입력"""
    title: Optional[str] = Field(default=None, description="참조 특허 제목")
    abstract: Optional[str] = Field(default=None, description="참조 특허 초록")
    claims: Optional[List[str]] = Field(default=None, description="참조 특허 청구항")
    ipc_codes: Optional[List[str]] = Field(default=None, description="참조 특허 IPC 코드")
    patent_number: Optional[str] = Field(default=None, description="참조 특허 번호 (이미 검색된 특허 제외용)")
    jurisdictions: List[str] = Field(
        default=["KR"],
        description="검색 대상 관할권"
    )
    max_results: int = Field(default=20, ge=1, le=100, description="최대 결과 수")
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0, description="최소 유사도 점수")


class SimilarPatent(PatentData):
    """유사 특허 (유사도 점수 포함)"""
    similarity_score: float = Field(default=0.0, description="유사도 점수 (0-1)")
    matching_keywords: List[str] = Field(default_factory=list, description="매칭된 키워드")
    matching_ipc_codes: List[str] = Field(default_factory=list, description="매칭된 IPC 코드")


class SimilaritySearchOutput(ToolResult):
    """유사 특허 검색 출력"""
    similar_patents: List[SimilarPatent] = Field(default_factory=list, description="유사 특허 목록")
    reference_keywords: List[str] = Field(default_factory=list, description="참조 특허에서 추출된 키워드")
    total_count: int = Field(default=0, description="총 결과 수")
    execution_time_ms: float = Field(default=0.0, description="실행 시간 (밀리초)")


# =============================================================================
# Similarity Search Tool
# =============================================================================

class PatentSimilaritySearchTool(BaseTool):
    """
    유사 특허 검색 도구
    
    참조 특허의 제목, 초록, 청구항, IPC 코드를 분석하여
    유사한 특허를 검색합니다.
    """
    
    name: str = "patent_similarity_search"
    description: str = """
    참조 특허와 유사한 특허를 검색합니다.
    제목, 초록, 청구항, IPC 코드를 기반으로 유사도를 계산합니다.
    
    사용 예:
    - title="배터리 관리 시스템", abstract="리튬이온 배터리의..."
    - ipc_codes=["H01M10/42", "H02J7/00"]
    """
    args_schema: type[BaseModel] = SimilaritySearchInput
    return_direct: bool = False
    
    # Private
    _aggregator: Optional[PatentSourceAggregator] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self._aggregator = None
    
    def _get_aggregator(self) -> PatentSourceAggregator:
        if self._aggregator is None:
            self._aggregator = PatentSourceAggregator()
        return self._aggregator
    
    def _extract_reference_keywords(
        self,
        title: Optional[str],
        abstract: Optional[str],
        claims: Optional[List[str]],
    ) -> List[str]:
        """참조 특허에서 키워드 추출"""
        keywords = set()
        
        if title:
            keywords.update(extract_keywords(title, max_keywords=5))
        if abstract:
            keywords.update(extract_keywords(abstract, max_keywords=10))
        if claims:
            for claim in claims[:3]:  # 상위 3개 청구항만
                keywords.update(extract_keywords(claim, max_keywords=5))
        
        return list(keywords)[:15]  # 최대 15개
    
    def _calculate_similarity(
        self,
        patent: PatentData,
        ref_keywords: List[str],
        ref_ipc_codes: List[str],
    ) -> tuple[float, List[str], List[str]]:
        """유사도 계산"""
        matching_keywords = []
        matching_ipc = []
        
        # 키워드 매칭
        patent_text = f"{patent.title} {patent.abstract}".lower()
        for kw in ref_keywords:
            if kw.lower() in patent_text:
                matching_keywords.append(kw)
        
        # IPC 코드 매칭
        if ref_ipc_codes and patent.ipc_codes:
            for ref_ipc in ref_ipc_codes:
                ref_parsed = parse_ipc_code(ref_ipc)
                if not ref_parsed:
                    continue
                for pat_ipc in patent.ipc_codes:
                    pat_parsed = parse_ipc_code(pat_ipc)
                    if not pat_parsed:
                        continue
                    # 섹션+클래스+서브클래스 매칭
                    if (ref_parsed.get("section") == pat_parsed.get("section") and
                        ref_parsed.get("class") == pat_parsed.get("class")):
                        matching_ipc.append(pat_ipc)
                        break
        
        # 유사도 점수 계산 (키워드 60%, IPC 40%)
        kw_score = len(matching_keywords) / max(len(ref_keywords), 1) if ref_keywords else 0
        ipc_score = len(matching_ipc) / max(len(ref_ipc_codes), 1) if ref_ipc_codes else 0
        
        if ref_ipc_codes:
            similarity = 0.6 * kw_score + 0.4 * ipc_score
        else:
            similarity = kw_score
        
        return similarity, matching_keywords, matching_ipc
    
    def _run(self, **kwargs) -> SimilaritySearchOutput:
        return asyncio.run(self._arun(**kwargs))
    
    async def _arun(
        self,
        title: Optional[str] = None,
        abstract: Optional[str] = None,
        claims: Optional[List[str]] = None,
        ipc_codes: Optional[List[str]] = None,
        patent_number: Optional[str] = None,
        jurisdictions: List[str] = None,
        max_results: int = 20,
        min_similarity: float = 0.3,
    ) -> SimilaritySearchOutput:
        """비동기 실행"""
        start_time = datetime.now()
        
        if jurisdictions is None:
            jurisdictions = ["KR"]
        
        # 입력 검증
        if not title and not abstract and not claims and not ipc_codes:
            return SimilaritySearchOutput(
                success=False,
                error="제목, 초록, 청구항, IPC 코드 중 하나 이상 필요합니다.",
            )
        
        try:
            # 키워드 추출
            ref_keywords = self._extract_reference_keywords(title, abstract, claims)
            ref_ipc_codes = ipc_codes or []
            
            if not ref_keywords and not ref_ipc_codes:
                return SimilaritySearchOutput(
                    success=False,
                    error="참조 특허에서 검색 가능한 키워드를 추출할 수 없습니다.",
                )
            
            # 검색 쿼리 생성 (상위 키워드로 검색)
            search_query = PatentSearchQuery(
                keywords=ref_keywords[:5],  # 상위 5개 키워드
                ipc_codes=ref_ipc_codes[:2] if ref_ipc_codes else [],  # 상위 2개 IPC
                jurisdictions=[PatentJurisdiction(j) for j in jurisdictions if j in PatentJurisdiction.__members__],
                max_results=max_results * 2,  # 필터링 고려 2배 요청
            )
            
            # 검색 실행
            aggregator = self._get_aggregator()
            result = await aggregator.search(query=search_query)
            
            # 유사도 계산 및 정렬
            similar_patents = []
            for patent in result.patents:
                # 자기 자신 제외
                if patent_number and patent.patent_number == patent_number:
                    continue
                
                similarity, match_kw, match_ipc = self._calculate_similarity(
                    patent, ref_keywords, ref_ipc_codes
                )
                
                if similarity >= min_similarity:
                    similar = SimilarPatent(
                        **patent.model_dump(),
                        similarity_score=round(similarity, 3),
                        matching_keywords=match_kw,
                        matching_ipc_codes=match_ipc,
                    )
                    similar_patents.append(similar)
            
            # 유사도 순 정렬
            similar_patents.sort(key=lambda x: x.similarity_score, reverse=True)
            similar_patents = similar_patents[:max_results]
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return SimilaritySearchOutput(
                success=True,
                similar_patents=similar_patents,
                reference_keywords=ref_keywords,
                total_count=len(similar_patents),
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(f"유사 특허 검색 실패: {e}")
            return SimilaritySearchOutput(
                success=False,
                error=str(e),
            )


# =============================================================================
# Singleton Instance
# =============================================================================

similarity_search_tool = PatentSimilaritySearchTool()

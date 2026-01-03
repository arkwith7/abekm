"""
Patent Portfolio Analysis Tool - 특허 포트폴리오 분석 도구

특정 출원인(기업)의 특허 포트폴리오를 종합 분석합니다.
- 기술 분야 커버리지
- 시간별 출원 전략
- 강점/약점 분석
"""
from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
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
from app.agents.features.patent.core.utils import parse_ipc_code
from app.agents.features.patent.clients import PatentSourceAggregator
from app.core.contracts import ToolResult


# =============================================================================
# Input/Output Models
# =============================================================================

class PortfolioAnalysisInput(BaseModel):
    """포트폴리오 분석 입력"""
    applicant: str = Field(description="분석 대상 출원인 (기업명)")
    compare_with: Optional[List[str]] = Field(
        default=None, 
        description="비교 대상 출원인 목록 (최대 3개)"
    )
    date_from: Optional[str] = Field(default=None, description="분석 시작일")
    date_to: Optional[str] = Field(default=None, description="분석 종료일")
    jurisdictions: List[str] = Field(default=["KR"], description="분석 대상 관할권")
    max_patents: int = Field(default=300, ge=10, le=500, description="분석할 최대 특허 수")


class TechnologyArea(BaseModel):
    """기술 영역"""
    ipc_section: str
    ipc_class: str
    description: str
    patent_count: int
    percentage: float
    example_titles: List[str] = Field(default_factory=list)


class TemporalPattern(BaseModel):
    """시간별 출원 패턴"""
    period: str  # "2020-Q1", "2020"
    count: int
    main_technologies: List[str] = Field(default_factory=list)


class PortfolioStrength(BaseModel):
    """포트폴리오 강점/약점"""
    category: str  # "strength" | "weakness" | "opportunity"
    description: str
    evidence: List[str] = Field(default_factory=list)


class CompetitorComparison(BaseModel):
    """경쟁사 비교"""
    applicant: str
    total_patents: int
    main_technologies: List[str]
    overlap_areas: List[str] = Field(default_factory=list)


class PortfolioAnalysisOutput(ToolResult):
    """포트폴리오 분석 출력"""
    applicant: str = Field(description="분석 대상")
    total_patents: int = Field(default=0, description="총 특허 수")
    technology_areas: List[TechnologyArea] = Field(default_factory=list, description="기술 영역 분포")
    temporal_patterns: List[TemporalPattern] = Field(default_factory=list, description="시간별 패턴")
    strengths_weaknesses: List[PortfolioStrength] = Field(default_factory=list, description="강점/약점")
    competitor_comparison: List[CompetitorComparison] = Field(default_factory=list, description="경쟁사 비교")
    strategic_insights: List[str] = Field(default_factory=list, description="전략적 인사이트")
    execution_time_ms: float = Field(default=0.0, description="실행 시간")


# =============================================================================
# IPC Section Descriptions
# =============================================================================

IPC_SECTIONS = {
    "A": "생활필수품",
    "B": "처리조작; 운수",
    "C": "화학; 야금",
    "D": "섬유; 지류",
    "E": "고정구조물",
    "F": "기계공학; 조명; 가열",
    "G": "물리학",
    "H": "전기",
}


# =============================================================================
# Portfolio Analysis Tool
# =============================================================================

class PatentPortfolioAnalysisTool(BaseTool):
    """
    특허 포트폴리오 분석 도구
    
    특정 출원인의 특허 포트폴리오를 종합 분석합니다.
    - 기술 분야별 커버리지
    - 시간별 출원 전략
    - 강점/약점 식별
    - 경쟁사 비교 (선택)
    """
    
    name: str = "patent_portfolio_analysis"
    description: str = """
    출원인(기업)의 특허 포트폴리오 종합 분석 도구.
    
    사용 예:
    - applicant="삼성전자"로 삼성전자 포트폴리오 분석
    - compare_with=["LG전자", "SK하이닉스"]로 경쟁사 비교 포함
    """
    args_schema: type[BaseModel] = PortfolioAnalysisInput
    return_direct: bool = False
    
    _aggregator: Optional[PatentSourceAggregator] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self._aggregator = None
    
    def _get_aggregator(self) -> PatentSourceAggregator:
        if self._aggregator is None:
            self._aggregator = PatentSourceAggregator()
        return self._aggregator
    
    def _analyze_technology_areas(self, patents: List[PatentData]) -> List[TechnologyArea]:
        """기술 영역 분석"""
        ipc_data = defaultdict(lambda: {"count": 0, "titles": []})
        
        for patent in patents:
            for ipc in patent.ipc_codes[:2]:  # 상위 2개 IPC
                parsed = parse_ipc_code(ipc)
                if parsed:
                    key = f"{parsed['section']}{parsed['class']}"
                    ipc_data[key]["count"] += 1
                    if len(ipc_data[key]["titles"]) < 3:
                        ipc_data[key]["titles"].append(patent.title[:50])
        
        if not ipc_data:
            return []
        
        total = sum(d["count"] for d in ipc_data.values())
        areas = []
        
        for ipc_key, data in sorted(ipc_data.items(), key=lambda x: x[1]["count"], reverse=True)[:8]:
            section = ipc_key[0]
            areas.append(TechnologyArea(
                ipc_section=section,
                ipc_class=ipc_key,
                description=IPC_SECTIONS.get(section, "기타"),
                patent_count=data["count"],
                percentage=round(data["count"] / total * 100, 1),
                example_titles=data["titles"],
            ))
        
        return areas
    
    def _analyze_temporal_patterns(self, patents: List[PatentData]) -> List[TemporalPattern]:
        """시간별 출원 패턴 분석"""
        year_data = defaultdict(lambda: {"count": 0, "ipcs": Counter()})
        
        for patent in patents:
            if patent.application_date:
                try:
                    year = patent.application_date[:4]
                    year_data[year]["count"] += 1
                    for ipc in patent.ipc_codes[:1]:
                        parsed = parse_ipc_code(ipc)
                        if parsed:
                            year_data[year]["ipcs"][parsed["section"]] += 1
                except:
                    pass
        
        patterns = []
        for year in sorted(year_data.keys()):
            data = year_data[year]
            top_techs = [
                IPC_SECTIONS.get(ipc, ipc) 
                for ipc, _ in data["ipcs"].most_common(2)
            ]
            patterns.append(TemporalPattern(
                period=year,
                count=data["count"],
                main_technologies=top_techs,
            ))
        
        return patterns
    
    def _analyze_strengths_weaknesses(
        self,
        patents: List[PatentData],
        tech_areas: List[TechnologyArea],
    ) -> List[PortfolioStrength]:
        """강점/약점 분석"""
        items = []
        
        # 강점 분석
        if tech_areas:
            top_area = tech_areas[0]
            if top_area.percentage > 30:
                items.append(PortfolioStrength(
                    category="strength",
                    description=f"{top_area.description} 분야 집중 ({top_area.percentage}%)",
                    evidence=top_area.example_titles[:2],
                ))
        
        # 다양성 분석
        if len(tech_areas) >= 4:
            diverse_count = sum(1 for t in tech_areas if t.percentage >= 10)
            if diverse_count >= 3:
                items.append(PortfolioStrength(
                    category="strength",
                    description=f"{diverse_count}개 기술 분야에 고른 분포 (다각화 전략)",
                    evidence=[t.ipc_class for t in tech_areas[:3]],
                ))
        
        # 최근 활동성
        recent_patents = [
            p for p in patents 
            if p.application_date and p.application_date[:4] >= "2023"
        ]
        if len(recent_patents) > len(patents) * 0.3:
            items.append(PortfolioStrength(
                category="strength",
                description=f"최근 2년간 활발한 출원 활동 ({len(recent_patents)}건)",
                evidence=[],
            ))
        elif len(recent_patents) < len(patents) * 0.1:
            items.append(PortfolioStrength(
                category="weakness",
                description="최근 출원 활동 감소 추세",
                evidence=[],
            ))
        
        return items
    
    async def _compare_competitors(
        self,
        main_applicant: str,
        main_patents: List[PatentData],
        competitors: List[str],
        jurisdictions: List[PatentJurisdiction],
    ) -> List[CompetitorComparison]:
        """경쟁사 비교"""
        comparisons = []
        aggregator = self._get_aggregator()
        
        # 주 출원인의 주요 기술 분야
        main_ipcs = Counter()
        for p in main_patents:
            for ipc in p.ipc_codes[:1]:
                parsed = parse_ipc_code(ipc)
                if parsed:
                    main_ipcs[parsed["section"]] += 1
        
        for competitor in competitors[:3]:  # 최대 3개
            try:
                query = PatentSearchQuery(
                    applicant=competitor,
                    jurisdictions=jurisdictions,
                    max_results=100,
                )
                result = await aggregator.search(query=query)
                
                # 경쟁사 주요 기술 분야
                comp_ipcs = Counter()
                for p in result.patents:
                    for ipc in p.ipc_codes[:1]:
                        parsed = parse_ipc_code(ipc)
                        if parsed:
                            comp_ipcs[parsed["section"]] += 1
                
                main_techs = [IPC_SECTIONS.get(s, s) for s, _ in comp_ipcs.most_common(3)]
                
                # 중복 분야 찾기
                overlap = []
                for section in main_ipcs:
                    if section in comp_ipcs:
                        overlap.append(IPC_SECTIONS.get(section, section))
                
                comparisons.append(CompetitorComparison(
                    applicant=competitor,
                    total_patents=len(result.patents),
                    main_technologies=main_techs,
                    overlap_areas=overlap[:3],
                ))
                
            except Exception as e:
                logger.warning(f"경쟁사 {competitor} 분석 실패: {e}")
        
        return comparisons
    
    def _generate_strategic_insights(
        self,
        total_patents: int,
        tech_areas: List[TechnologyArea],
        temporal: List[TemporalPattern],
        strengths: List[PortfolioStrength],
        competitors: List[CompetitorComparison],
    ) -> List[str]:
        """전략적 인사이트 생성"""
        insights = []
        
        # 규모 평가
        if total_patents >= 100:
            insights.append(f"📊 총 {total_patents}건의 특허로 상당한 규모의 포트폴리오 보유")
        
        # 기술 집중도
        if tech_areas:
            top3_share = sum(t.percentage for t in tech_areas[:3])
            if top3_share > 70:
                insights.append(f"🎯 상위 3개 기술 분야가 {top3_share:.0f}%로 집중도 높음")
        
        # 성장 추세
        if len(temporal) >= 2:
            recent = temporal[-1].count if temporal else 0
            prev = temporal[-2].count if len(temporal) >= 2 else 0
            if recent > prev * 1.2:
                insights.append("📈 최근 출원량 증가 추세 - 적극적인 R&D 투자 시사")
        
        # 경쟁 분석
        if competitors:
            for comp in competitors:
                if comp.overlap_areas:
                    insights.append(
                        f"⚔️ {comp.applicant}와 {', '.join(comp.overlap_areas)} 분야에서 경쟁"
                    )
        
        return insights
    
    def _run(self, **kwargs) -> PortfolioAnalysisOutput:
        return asyncio.run(self._arun(**kwargs))
    
    async def _arun(
        self,
        applicant: str,
        compare_with: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        jurisdictions: List[str] = None,
        max_patents: int = 300,
    ) -> PortfolioAnalysisOutput:
        """비동기 실행"""
        start_time = datetime.now()
        
        if jurisdictions is None:
            jurisdictions = ["KR"]
        
        try:
            aggregator = self._get_aggregator()
            jur_enums = [PatentJurisdiction(j) for j in jurisdictions if j in PatentJurisdiction.__members__]
            
            # 주 출원인 특허 검색
            query = PatentSearchQuery(
                applicant=applicant,
                date_from=date_from,
                date_to=date_to,
                jurisdictions=jur_enums,
                max_results=max_patents,
            )
            result = await aggregator.search(query=query)
            patents = result.patents
            
            if not patents:
                return PortfolioAnalysisOutput(
                    success=True,
                    applicant=applicant,
                    total_patents=0,
                    strategic_insights=[f"'{applicant}'의 특허를 찾을 수 없습니다."],
                )
            
            # 분석 수행
            tech_areas = self._analyze_technology_areas(patents)
            temporal = self._analyze_temporal_patterns(patents)
            strengths = self._analyze_strengths_weaknesses(patents, tech_areas)
            
            # 경쟁사 비교
            competitors = []
            if compare_with:
                competitors = await self._compare_competitors(
                    applicant, patents, compare_with, jur_enums
                )
            
            # 전략적 인사이트
            insights = self._generate_strategic_insights(
                len(patents), tech_areas, temporal, strengths, competitors
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return PortfolioAnalysisOutput(
                success=True,
                applicant=applicant,
                total_patents=len(patents),
                technology_areas=tech_areas,
                temporal_patterns=temporal,
                strengths_weaknesses=strengths,
                competitor_comparison=competitors,
                strategic_insights=insights,
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(f"포트폴리오 분석 실패: {e}")
            return PortfolioAnalysisOutput(
                success=False,
                applicant=applicant,
                error=str(e),
            )


# =============================================================================
# Singleton Instance
# =============================================================================

portfolio_analysis_tool = PatentPortfolioAnalysisTool()

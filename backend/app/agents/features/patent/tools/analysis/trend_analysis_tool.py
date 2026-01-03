"""
Patent Trend Analysis Tool - 특허 트렌드 분석 도구

특허 데이터를 기반으로 기술 트렌드를 분석합니다.
- 연도별 출원 추이
- IPC 코드별 분포
- 주요 출원인 분석
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

class TrendAnalysisInput(BaseModel):
    """트렌드 분석 입력"""
    query: Optional[str] = Field(default=None, description="분석 대상 키워드")
    applicant: Optional[str] = Field(default=None, description="분석 대상 출원인")
    ipc_code: Optional[str] = Field(default=None, description="분석 대상 IPC 코드")
    date_from: Optional[str] = Field(default=None, description="분석 시작일 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(default=None, description="분석 종료일 (YYYY-MM-DD)")
    jurisdictions: List[str] = Field(default=["KR"], description="분석 대상 관할권")
    max_patents: int = Field(default=200, ge=10, le=500, description="분석할 최대 특허 수")


class YearlyTrend(BaseModel):
    """연도별 트렌드"""
    year: int
    count: int
    growth_rate: Optional[float] = None  # 전년 대비 성장률


class IPCDistribution(BaseModel):
    """IPC 코드 분포"""
    ipc_code: str
    section: str
    description: str
    count: int
    percentage: float


class ApplicantRanking(BaseModel):
    """출원인 순위"""
    rank: int
    applicant: str
    count: int
    percentage: float
    recent_patents: List[str] = Field(default_factory=list)  # 최근 특허 제목


class TrendAnalysisOutput(ToolResult):
    """트렌드 분석 출력"""
    yearly_trends: List[YearlyTrend] = Field(default_factory=list, description="연도별 출원 추이")
    ipc_distribution: List[IPCDistribution] = Field(default_factory=list, description="IPC 코드 분포")
    top_applicants: List[ApplicantRanking] = Field(default_factory=list, description="상위 출원인")
    total_patents_analyzed: int = Field(default=0, description="분석된 총 특허 수")
    date_range: Dict[str, str] = Field(default_factory=dict, description="분석 기간")
    key_findings: List[str] = Field(default_factory=list, description="주요 발견 사항")
    execution_time_ms: float = Field(default=0.0, description="실행 시간 (밀리초)")


# =============================================================================
# IPC Section Descriptions
# =============================================================================

IPC_SECTIONS = {
    "A": "생활필수품",
    "B": "처리조작; 운수",
    "C": "화학; 야금",
    "D": "섬유; 지류",
    "E": "고정구조물",
    "F": "기계공학; 조명; 가열; 무기; 폭파",
    "G": "물리학",
    "H": "전기",
}


# =============================================================================
# Trend Analysis Tool
# =============================================================================

class PatentTrendAnalysisTool(BaseTool):
    """
    특허 트렌드 분석 도구
    
    특허 데이터를 수집하여 기술 트렌드를 분석합니다.
    - 연도별 출원 추이 및 성장률
    - IPC 코드별 기술 분야 분포
    - 주요 출원인 및 점유율
    """
    
    name: str = "patent_trend_analysis"
    description: str = """
    특허 데이터 기반 기술 트렌드 분석 도구.
    연도별 추이, IPC 분포, 주요 출원인을 분석합니다.
    
    사용 예:
    - query="전기자동차 배터리"로 배터리 기술 트렌드 분석
    - applicant="삼성전자"로 삼성전자 특허 포트폴리오 분석
    """
    args_schema: type[BaseModel] = TrendAnalysisInput
    return_direct: bool = False
    
    _aggregator: Optional[PatentSourceAggregator] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self._aggregator = None
    
    def _get_aggregator(self) -> PatentSourceAggregator:
        if self._aggregator is None:
            self._aggregator = PatentSourceAggregator()
        return self._aggregator
    
    def _analyze_yearly_trends(self, patents: List[PatentData]) -> List[YearlyTrend]:
        """연도별 출원 추이 분석"""
        year_counts = Counter()
        
        for patent in patents:
            if patent.application_date:
                try:
                    year = int(patent.application_date[:4])
                    year_counts[year] += 1
                except (ValueError, IndexError):
                    pass
        
        if not year_counts:
            return []
        
        trends = []
        sorted_years = sorted(year_counts.keys())
        prev_count = None
        
        for year in sorted_years:
            count = year_counts[year]
            growth_rate = None
            if prev_count and prev_count > 0:
                growth_rate = round((count - prev_count) / prev_count * 100, 1)
            
            trends.append(YearlyTrend(
                year=year,
                count=count,
                growth_rate=growth_rate,
            ))
            prev_count = count
        
        return trends
    
    def _analyze_ipc_distribution(self, patents: List[PatentData]) -> List[IPCDistribution]:
        """IPC 코드 분포 분석"""
        ipc_counts = Counter()
        
        for patent in patents:
            for ipc in patent.ipc_codes[:3]:  # 특허당 상위 3개 IPC만
                parsed = parse_ipc_code(ipc)
                if parsed:
                    # 섹션+클래스 수준으로 집계
                    key = f"{parsed['section']}{parsed['class']}"
                    ipc_counts[key] += 1
        
        if not ipc_counts:
            return []
        
        total = sum(ipc_counts.values())
        distributions = []
        
        for ipc_code, count in ipc_counts.most_common(10):  # 상위 10개
            section = ipc_code[0] if ipc_code else "?"
            distributions.append(IPCDistribution(
                ipc_code=ipc_code,
                section=section,
                description=IPC_SECTIONS.get(section, "기타"),
                count=count,
                percentage=round(count / total * 100, 1),
            ))
        
        return distributions
    
    def _analyze_top_applicants(self, patents: List[PatentData]) -> List[ApplicantRanking]:
        """상위 출원인 분석"""
        applicant_data = defaultdict(lambda: {"count": 0, "patents": []})
        
        for patent in patents:
            if patent.applicant:
                # 법인명 정규화 (간단한 처리)
                applicant = patent.applicant.strip()
                applicant_data[applicant]["count"] += 1
                if len(applicant_data[applicant]["patents"]) < 3:
                    applicant_data[applicant]["patents"].append(patent.title)
        
        if not applicant_data:
            return []
        
        total = sum(d["count"] for d in applicant_data.values())
        rankings = []
        
        sorted_applicants = sorted(
            applicant_data.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:10]  # 상위 10명
        
        for rank, (applicant, data) in enumerate(sorted_applicants, 1):
            rankings.append(ApplicantRanking(
                rank=rank,
                applicant=applicant,
                count=data["count"],
                percentage=round(data["count"] / total * 100, 1),
                recent_patents=data["patents"],
            ))
        
        return rankings
    
    def _generate_key_findings(
        self,
        yearly_trends: List[YearlyTrend],
        ipc_distribution: List[IPCDistribution],
        top_applicants: List[ApplicantRanking],
        total_patents: int,
    ) -> List[str]:
        """주요 발견 사항 생성"""
        findings = []
        
        # 출원 추이 관련
        if yearly_trends:
            recent = yearly_trends[-1] if yearly_trends else None
            if recent and recent.growth_rate:
                if recent.growth_rate > 20:
                    findings.append(f"📈 {recent.year}년 출원이 전년 대비 {recent.growth_rate}% 급증하여 관심 증가 추세")
                elif recent.growth_rate < -20:
                    findings.append(f"📉 {recent.year}년 출원이 전년 대비 {abs(recent.growth_rate)}% 감소")
        
        # IPC 분포 관련
        if ipc_distribution:
            top_ipc = ipc_distribution[0]
            findings.append(f"🔬 주요 기술 분야: {top_ipc.description} ({top_ipc.ipc_code}, {top_ipc.percentage}%)")
        
        # 출원인 관련
        if top_applicants:
            top = top_applicants[0]
            findings.append(f"🏢 선두 출원인: {top.applicant} ({top.count}건, {top.percentage}%)")
            
            if len(top_applicants) >= 3:
                top3_share = sum(a.percentage for a in top_applicants[:3])
                if top3_share > 50:
                    findings.append(f"⚠️ 상위 3개 출원인이 전체의 {top3_share:.1f}%를 점유 (집중도 높음)")
        
        findings.append(f"📊 총 {total_patents}건의 특허 분석 완료")
        
        return findings
    
    def _run(self, **kwargs) -> TrendAnalysisOutput:
        return asyncio.run(self._arun(**kwargs))
    
    async def _arun(
        self,
        query: Optional[str] = None,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        jurisdictions: List[str] = None,
        max_patents: int = 200,
    ) -> TrendAnalysisOutput:
        """비동기 실행"""
        start_time = datetime.now()
        
        if jurisdictions is None:
            jurisdictions = ["KR"]
        
        if not query and not applicant and not ipc_code:
            return TrendAnalysisOutput(
                success=False,
                error="query, applicant, ipc_code 중 하나 이상 필요합니다.",
            )
        
        try:
            # 검색 쿼리 생성
            search_query = PatentSearchQuery(
                keywords=[query] if query else [],
                applicant=applicant,
                ipc_codes=[ipc_code] if ipc_code else [],
                date_from=date_from,
                date_to=date_to,
                jurisdictions=[PatentJurisdiction(j) for j in jurisdictions if j in PatentJurisdiction.__members__],
                max_results=max_patents,
            )
            
            # 데이터 수집
            aggregator = self._get_aggregator()
            result = await aggregator.search(query=search_query)
            patents = result.patents
            
            if not patents:
                return TrendAnalysisOutput(
                    success=True,
                    total_patents_analyzed=0,
                    key_findings=["검색 조건에 해당하는 특허가 없습니다."],
                )
            
            # 분석 수행
            yearly_trends = self._analyze_yearly_trends(patents)
            ipc_distribution = self._analyze_ipc_distribution(patents)
            top_applicants = self._analyze_top_applicants(patents)
            key_findings = self._generate_key_findings(
                yearly_trends, ipc_distribution, top_applicants, len(patents)
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return TrendAnalysisOutput(
                success=True,
                yearly_trends=yearly_trends,
                ipc_distribution=ipc_distribution,
                top_applicants=top_applicants,
                total_patents_analyzed=len(patents),
                date_range={
                    "from": date_from or "미지정",
                    "to": date_to or "미지정",
                },
                key_findings=key_findings,
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(f"트렌드 분석 실패: {e}")
            return TrendAnalysisOutput(
                success=False,
                error=str(e),
            )


# =============================================================================
# Singleton Instance
# =============================================================================

trend_analysis_tool = PatentTrendAnalysisTool()

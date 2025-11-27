"""
Patent Analysis Tool - 특허 분석 도구
특허 데이터 심층 분석 (기술 토픽, 인용, 시계열, 경쟁 비교)
"""
import asyncio
import uuid
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from enum import Enum
from collections import Counter, defaultdict
from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.tools.contracts import ToolResult, ToolMetrics
from app.tools.retrieval.patent_search_tool import PatentData, PatentJurisdiction, PatentStatus


# =============================================================================
# Analysis Types
# =============================================================================

class PatentAnalysisType(str, Enum):
    """특허 분석 유형"""
    TOPIC_EXTRACTION = "topic"           # 기술 토픽 추출
    TIMELINE_TREND = "timeline"          # 시계열 트렌드
    COMPETITOR_COMPARISON = "comparison" # 경쟁사 비교
    CITATION_NETWORK = "citation"        # 인용 네트워크
    WHITE_SPACE = "gap"                  # 기술 공백 분석
    PORTFOLIO_OVERVIEW = "portfolio"     # 포트폴리오 개요


# =============================================================================
# Analysis Result Models
# =============================================================================

class TechTopic(BaseModel):
    """기술 토픽"""
    name: str = Field(description="토픽 이름")
    keywords: List[str] = Field(description="관련 키워드")
    patent_count: int = Field(description="관련 특허 수")
    ipc_codes: List[str] = Field(description="관련 IPC 코드")
    representative_patents: List[str] = Field(description="대표 특허 번호")
    trend: str = Field(default="stable", description="트렌드 (growing/stable/declining)")


class TimelinePoint(BaseModel):
    """시계열 포인트"""
    year: int = Field(description="연도")
    patent_count: int = Field(description="특허 수")
    topics: List[str] = Field(default_factory=list, description="주요 토픽")
    notable_patents: List[str] = Field(default_factory=list, description="주목할 특허")


class CompetitorMetrics(BaseModel):
    """경쟁사 지표"""
    name: str = Field(description="회사명")
    total_patents: int = Field(description="총 특허 수")
    granted_patents: int = Field(description="등록 특허 수")
    pending_patents: int = Field(description="출원 중 특허 수")
    avg_citations: float = Field(default=0.0, description="평균 피인용 수")
    top_ipc_codes: List[str] = Field(default_factory=list, description="주요 IPC 코드")
    recent_growth_rate: float = Field(default=0.0, description="최근 성장률 (%)")
    key_technologies: List[str] = Field(default_factory=list, description="핵심 기술")


class GapAnalysisItem(BaseModel):
    """기술 공백 분석 항목"""
    ipc_code: str = Field(description="IPC 코드")
    technology_name: str = Field(description="기술 분야명")
    our_count: int = Field(description="우리 특허 수")
    competitor_count: int = Field(description="경쟁사 특허 수")
    gap_level: str = Field(description="공백 수준 (high/medium/low/advantage)")
    recommendation: str = Field(description="권고사항")


class PatentAnalysisResult(ToolResult):
    """특허 분석 결과"""
    analysis_type: PatentAnalysisType = Field(description="분석 유형")
    summary: str = Field(description="분석 요약")
    
    # 분석 유형별 결과
    topics: Optional[List[TechTopic]] = Field(default=None, description="기술 토픽 (TOPIC)")
    timeline: Optional[List[TimelinePoint]] = Field(default=None, description="시계열 (TIMELINE)")
    competitors: Optional[List[CompetitorMetrics]] = Field(default=None, description="경쟁사 비교 (COMPARISON)")
    gaps: Optional[List[GapAnalysisItem]] = Field(default=None, description="기술 공백 (GAP)")
    
    # 시각화 데이터
    visualization_data: Dict[str, Any] = Field(default_factory=dict, description="시각화용 데이터")
    
    # 인사이트
    key_insights: List[str] = Field(default_factory=list, description="핵심 인사이트")
    recommendations: List[str] = Field(default_factory=list, description="전략적 제언")


# =============================================================================
# IPC Code Mappings
# =============================================================================

IPC_CODE_NAMES = {
    "G06N": "AI/기계학습",
    "G06F": "컴퓨팅/데이터처리",
    "G06Q": "비즈니스 시스템",
    "G06T": "이미지 처리",
    "G06V": "패턴 인식",
    "G06K": "데이터 인식",
    "H01L": "반도체 소자",
    "H04L": "통신/네트워크",
    "H04N": "영상 통신",
    "H04W": "무선 통신",
    "B25J": "로보틱스",
    "G16H": "헬스케어 ICT",
    "G16B": "바이오인포매틱스",
    "G01N": "재료 분석",
    "G01R": "전기 측정",
}


def get_ipc_name(ipc_code: str) -> str:
    """IPC 코드에서 기술 분야명 반환"""
    prefix = ipc_code[:4] if len(ipc_code) >= 4 else ipc_code
    return IPC_CODE_NAMES.get(prefix, f"기타 ({prefix})")


# =============================================================================
# Patent Analysis Tool
# =============================================================================

class PatentAnalysisTool(BaseTool):
    """
    특허 분석 도구
    
    분석 기능:
    - 기술 토픽 추출 및 클러스터링
    - 시계열 트렌드 분석
    - 경쟁사 비교 분석
    - 인용 네트워크 분석
    - 기술 공백 분석
    """
    name: str = "patent_analysis"
    description: str = """특허 데이터 심층 분석 도구.

분석 유형:
- topic: 기술 토픽 추출 (핵심 기술 분야, 키워드)
- timeline: 시계열 트렌드 (연도별 출원 동향)
- comparison: 경쟁사 비교 (특허 포트폴리오 비교)
- gap: 기술 공백 분석 (경쟁사 대비 부족한 영역)
- portfolio: 포트폴리오 개요 (전체 현황)

사용 예:
- "삼성전자와 애플의 AI 특허 비교"
- "최근 5년간 반도체 특허 트렌드"
- "경쟁사 대비 기술 공백 분석"
"""
    version: str = "1.0.0"
    
    async def _arun(
        self,
        patents: List[PatentData],
        analysis_type: str = "portfolio",
        comparison_target: Optional[str] = None,
        our_company: Optional[str] = None,
        time_range_years: int = 5,
        **kwargs
    ) -> PatentAnalysisResult:
        """
        특허 분석 실행
        
        Args:
            patents: 분석할 특허 목록
            analysis_type: 분석 유형 (topic/timeline/comparison/gap/portfolio)
            comparison_target: 비교 대상 (경쟁사명, comparison/gap에 필요)
            our_company: 우리 회사명 (comparison/gap에 필요)
            time_range_years: 분석 기간 (년)
        
        Returns:
            PatentAnalysisResult: 분석 결과
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            analysis_type_enum = PatentAnalysisType(analysis_type)
        except ValueError:
            analysis_type_enum = PatentAnalysisType.PORTFOLIO_OVERVIEW
        
        logger.info(f"📊 [PatentAnalysis] 분석 시작: type={analysis_type}, patents={len(patents)}")
        
        try:
            if analysis_type_enum == PatentAnalysisType.TOPIC_EXTRACTION:
                result = await self._analyze_topics(patents)
            elif analysis_type_enum == PatentAnalysisType.TIMELINE_TREND:
                result = await self._analyze_timeline(patents, time_range_years)
            elif analysis_type_enum == PatentAnalysisType.COMPETITOR_COMPARISON:
                result = await self._analyze_competitors(patents, our_company, comparison_target)
            elif analysis_type_enum == PatentAnalysisType.WHITE_SPACE:
                result = await self._analyze_gaps(patents, our_company, comparison_target)
            else:  # PORTFOLIO_OVERVIEW
                result = await self._analyze_portfolio(patents)
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result.metrics = ToolMetrics(
                latency_ms=elapsed_ms,
                provider="patent_analysis",
                items_returned=len(patents),
                trace_id=trace_id
            )
            result.trace_id = trace_id
            result.tool_name = self.name
            result.tool_version = self.version
            result.success = True
            
            logger.info(f"✅ [PatentAnalysis] 완료: {elapsed_ms:.0f}ms")
            return result
            
        except Exception as e:
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [PatentAnalysis] 오류: {e}")
            
            return PatentAnalysisResult(
                success=False,
                data=None,
                analysis_type=analysis_type_enum,
                summary=f"분석 중 오류 발생: {str(e)}",
                metrics=ToolMetrics(
                    latency_ms=elapsed_ms,
                    provider="patent_analysis",
                    trace_id=trace_id
                ),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    async def _analyze_topics(self, patents: List[PatentData]) -> PatentAnalysisResult:
        """기술 토픽 추출"""
        # IPC 코드별 그룹화
        ipc_groups: Dict[str, List[PatentData]] = defaultdict(list)
        for patent in patents:
            for ipc in patent.ipc_codes:
                prefix = ipc[:4] if len(ipc) >= 4 else ipc
                ipc_groups[prefix].append(patent)
        
        topics = []
        for ipc_code, group_patents in sorted(ipc_groups.items(), key=lambda x: -len(x[1])):
            # 키워드 추출 (제목에서)
            words = []
            for p in group_patents:
                words.extend(p.title.split())
            
            word_counts = Counter(words)
            top_keywords = [w for w, _ in word_counts.most_common(5) if len(w) > 1]
            
            topic = TechTopic(
                name=get_ipc_name(ipc_code),
                keywords=top_keywords,
                patent_count=len(group_patents),
                ipc_codes=[ipc_code],
                representative_patents=[p.patent_number for p in group_patents[:3]],
                trend=self._calculate_trend(group_patents)
            )
            topics.append(topic)
        
        # 시각화 데이터
        viz_data = {
            "type": "pie_chart",
            "data": [{"name": t.name, "value": t.patent_count} for t in topics[:10]]
        }
        
        return PatentAnalysisResult(
            success=True,
            data=topics,
            analysis_type=PatentAnalysisType.TOPIC_EXTRACTION,
            summary=f"총 {len(patents)}건의 특허에서 {len(topics)}개의 기술 토픽 추출",
            topics=topics,
            visualization_data=viz_data,
            key_insights=[
                f"가장 많은 특허가 있는 분야: {topics[0].name} ({topics[0].patent_count}건)" if topics else "",
                f"총 {len(set(ipc for p in patents for ipc in p.ipc_codes))}개의 IPC 분류 커버"
            ],
            metrics=ToolMetrics(latency_ms=0, provider="patent_analysis"),
            errors=[],
            trace_id="",
            tool_name=self.name,
            tool_version=self.version
        )
    
    async def _analyze_timeline(
        self, 
        patents: List[PatentData], 
        years: int = 5
    ) -> PatentAnalysisResult:
        """시계열 트렌드 분석"""
        current_year = datetime.now().year
        
        # 연도별 그룹화
        year_groups: Dict[int, List[PatentData]] = defaultdict(list)
        for patent in patents:
            if patent.application_date:
                try:
                    year = int(patent.application_date[:4])
                    if year >= current_year - years:
                        year_groups[year].append(patent)
                except (ValueError, IndexError):
                    pass
        
        timeline = []
        for year in sorted(year_groups.keys()):
            year_patents = year_groups[year]
            
            # 해당 연도 주요 토픽
            ipc_counts = Counter()
            for p in year_patents:
                for ipc in p.ipc_codes:
                    ipc_counts[ipc[:4]] += 1
            
            top_topics = [get_ipc_name(ipc) for ipc, _ in ipc_counts.most_common(3)]
            
            point = TimelinePoint(
                year=year,
                patent_count=len(year_patents),
                topics=top_topics,
                notable_patents=[p.patent_number for p in year_patents[:2]]
            )
            timeline.append(point)
        
        # 트렌드 분석
        if len(timeline) >= 2:
            recent_avg = sum(t.patent_count for t in timeline[-2:]) / 2
            older_avg = sum(t.patent_count for t in timeline[:-2]) / max(len(timeline) - 2, 1)
            growth = ((recent_avg - older_avg) / max(older_avg, 1)) * 100
            trend_text = "증가" if growth > 10 else "감소" if growth < -10 else "유지"
        else:
            growth = 0
            trend_text = "데이터 부족"
        
        # 시각화 데이터
        viz_data = {
            "type": "line_chart",
            "data": [{"year": t.year, "count": t.patent_count} for t in timeline]
        }
        
        return PatentAnalysisResult(
            success=True,
            data=timeline,
            analysis_type=PatentAnalysisType.TIMELINE_TREND,
            summary=f"{years}년간 특허 출원 트렌드 분석 (총 {len(patents)}건)",
            timeline=timeline,
            visualization_data=viz_data,
            key_insights=[
                f"최근 트렌드: {trend_text} ({growth:+.1f}%)",
                f"가장 활발한 연도: {max(timeline, key=lambda x: x.patent_count).year if timeline else 'N/A'}",
                f"최근 주요 기술: {', '.join(timeline[-1].topics) if timeline else 'N/A'}"
            ],
            metrics=ToolMetrics(latency_ms=0, provider="patent_analysis"),
            errors=[],
            trace_id="",
            tool_name=self.name,
            tool_version=self.version
        )
    
    async def _analyze_competitors(
        self,
        patents: List[PatentData],
        our_company: Optional[str],
        competitor: Optional[str]
    ) -> PatentAnalysisResult:
        """경쟁사 비교 분석"""
        # 출원인별 그룹화
        applicant_groups: Dict[str, List[PatentData]] = defaultdict(list)
        for patent in patents:
            applicant_groups[patent.applicant].append(patent)
        
        competitors = []
        for applicant, group_patents in sorted(applicant_groups.items(), key=lambda x: -len(x[1])):
            granted = sum(1 for p in group_patents if p.status == PatentStatus.GRANTED)
            pending = sum(1 for p in group_patents if p.status in [PatentStatus.APPLICATION, PatentStatus.PUBLISHED])
            
            # IPC 분석
            ipc_counts = Counter()
            for p in group_patents:
                for ipc in p.ipc_codes:
                    ipc_counts[ipc[:4]] += 1
            
            top_ipcs = [ipc for ipc, _ in ipc_counts.most_common(5)]
            key_techs = [get_ipc_name(ipc) for ipc in top_ipcs[:3]]
            
            # 피인용 수 평균
            citations = [p.cited_by_count or 0 for p in group_patents]
            avg_citations = sum(citations) / max(len(citations), 1)
            
            metrics = CompetitorMetrics(
                name=applicant,
                total_patents=len(group_patents),
                granted_patents=granted,
                pending_patents=pending,
                avg_citations=avg_citations,
                top_ipc_codes=top_ipcs,
                key_technologies=key_techs,
                recent_growth_rate=self._calculate_growth_rate(group_patents)
            )
            competitors.append(metrics)
        
        # 시각화 데이터 (레이더 차트용)
        if len(competitors) >= 2:
            viz_data = {
                "type": "radar_chart",
                "data": [
                    {
                        "name": c.name,
                        "values": {
                            "출원량": min(c.total_patents / 100, 1),  # 정규화
                            "등록률": c.granted_patents / max(c.total_patents, 1),
                            "피인용수": min(c.avg_citations / 50, 1),
                            "기술다양성": len(c.top_ipc_codes) / 10,
                            "성장률": min(max(c.recent_growth_rate + 50, 0) / 100, 1)
                        }
                    }
                    for c in competitors[:5]
                ]
            }
        else:
            viz_data = {}
        
        return PatentAnalysisResult(
            success=True,
            data=competitors,
            analysis_type=PatentAnalysisType.COMPETITOR_COMPARISON,
            summary=f"{len(competitors)}개 출원인의 특허 포트폴리오 비교",
            competitors=competitors,
            visualization_data=viz_data,
            key_insights=[
                f"가장 많은 특허: {competitors[0].name} ({competitors[0].total_patents}건)" if competitors else "",
                f"가장 높은 등록률: {max(competitors, key=lambda x: x.granted_patents/max(x.total_patents,1)).name if competitors else 'N/A'}",
                f"가장 빠른 성장: {max(competitors, key=lambda x: x.recent_growth_rate).name if competitors else 'N/A'}"
            ],
            recommendations=[
                f"{our_company}의 특허 포트폴리오 강화 필요" if our_company else "경쟁사 동향 지속 모니터링 권고"
            ],
            metrics=ToolMetrics(latency_ms=0, provider="patent_analysis"),
            errors=[],
            trace_id="",
            tool_name=self.name,
            tool_version=self.version
        )
    
    async def _analyze_gaps(
        self,
        patents: List[PatentData],
        our_company: Optional[str],
        competitor: Optional[str]
    ) -> PatentAnalysisResult:
        """기술 공백 분석"""
        if not our_company or not competitor:
            return PatentAnalysisResult(
                success=False,
                data=None,
                analysis_type=PatentAnalysisType.WHITE_SPACE,
                summary="기술 공백 분석에는 our_company와 comparison_target이 필요합니다.",
                metrics=ToolMetrics(latency_ms=0, provider="patent_analysis"),
                errors=["our_company와 comparison_target 파라미터가 필요합니다."],
                trace_id="",
                tool_name=self.name,
                tool_version=self.version
            )
        
        # 회사별 IPC 분류
        our_ipcs: Dict[str, int] = defaultdict(int)
        competitor_ipcs: Dict[str, int] = defaultdict(int)
        
        for patent in patents:
            is_ours = our_company.lower() in patent.applicant.lower()
            is_competitor = competitor.lower() in patent.applicant.lower()
            
            for ipc in patent.ipc_codes:
                prefix = ipc[:4] if len(ipc) >= 4 else ipc
                if is_ours:
                    our_ipcs[prefix] += 1
                if is_competitor:
                    competitor_ipcs[prefix] += 1
        
        # 모든 IPC 코드 통합
        all_ipcs = set(our_ipcs.keys()) | set(competitor_ipcs.keys())
        
        gaps = []
        for ipc in all_ipcs:
            our_count = our_ipcs.get(ipc, 0)
            comp_count = competitor_ipcs.get(ipc, 0)
            
            # 공백 수준 계산
            if our_count == 0 and comp_count > 0:
                gap_level = "high"
                recommendation = f"{get_ipc_name(ipc)} 분야 R&D 투자 권고"
            elif comp_count > our_count * 2:
                gap_level = "medium"
                recommendation = f"{get_ipc_name(ipc)} 분야 특허 출원 강화 필요"
            elif our_count > comp_count * 2:
                gap_level = "advantage"
                recommendation = f"{get_ipc_name(ipc)} 분야 우위 유지"
            else:
                gap_level = "low"
                recommendation = "현 수준 유지"
            
            gap_item = GapAnalysisItem(
                ipc_code=ipc,
                technology_name=get_ipc_name(ipc),
                our_count=our_count,
                competitor_count=comp_count,
                gap_level=gap_level,
                recommendation=recommendation
            )
            gaps.append(gap_item)
        
        # 공백 수준별 정렬
        gap_priority = {"high": 0, "medium": 1, "low": 2, "advantage": 3}
        gaps.sort(key=lambda x: (gap_priority.get(x.gap_level, 9), -x.competitor_count))
        
        # 시각화 데이터
        viz_data = {
            "type": "gap_matrix",
            "data": [
                {
                    "ipc": g.ipc_code,
                    "name": g.technology_name,
                    "our": g.our_count,
                    "competitor": g.competitor_count,
                    "level": g.gap_level
                }
                for g in gaps
            ]
        }
        
        high_gaps = [g for g in gaps if g.gap_level == "high"]
        advantages = [g for g in gaps if g.gap_level == "advantage"]
        
        return PatentAnalysisResult(
            success=True,
            data=gaps,
            analysis_type=PatentAnalysisType.WHITE_SPACE,
            summary=f"{our_company} vs {competitor} 기술 공백 분석 ({len(gaps)}개 기술 분야)",
            gaps=gaps,
            visualization_data=viz_data,
            key_insights=[
                f"🔴 높은 공백: {len(high_gaps)}개 분야",
                f"🟢 우위 분야: {len(advantages)}개 분야",
                f"가장 큰 공백: {high_gaps[0].technology_name if high_gaps else 'N/A'}"
            ],
            recommendations=[g.recommendation for g in gaps if g.gap_level in ["high", "medium"]][:5],
            metrics=ToolMetrics(latency_ms=0, provider="patent_analysis"),
            errors=[],
            trace_id="",
            tool_name=self.name,
            tool_version=self.version
        )
    
    async def _analyze_portfolio(self, patents: List[PatentData]) -> PatentAnalysisResult:
        """포트폴리오 개요"""
        total = len(patents)
        granted = sum(1 for p in patents if p.status == PatentStatus.GRANTED)
        pending = sum(1 for p in patents if p.status in [PatentStatus.APPLICATION, PatentStatus.PUBLISHED])
        
        # 관할권별 분포
        jurisdiction_counts = Counter(p.jurisdiction.value for p in patents)
        
        # IPC 분포
        ipc_counts = Counter()
        for p in patents:
            for ipc in p.ipc_codes:
                ipc_counts[ipc[:4]] += 1
        
        top_ipcs = [f"{ipc} ({get_ipc_name(ipc)})" for ipc, _ in ipc_counts.most_common(5)]
        
        # 출원인 분포
        applicant_counts = Counter(p.applicant for p in patents)
        top_applicants = [name for name, _ in applicant_counts.most_common(5)]
        
        summary_data = {
            "total_patents": total,
            "granted": granted,
            "pending": pending,
            "grant_rate": granted / max(total, 1) * 100,
            "jurisdictions": dict(jurisdiction_counts),
            "top_ipc_codes": top_ipcs,
            "top_applicants": top_applicants
        }
        
        viz_data = {
            "type": "dashboard",
            "metrics": summary_data,
            "charts": {
                "jurisdiction_pie": [{"name": k, "value": v} for k, v in jurisdiction_counts.items()],
                "ipc_bar": [{"name": get_ipc_name(ipc), "value": cnt} for ipc, cnt in ipc_counts.most_common(10)]
            }
        }
        
        return PatentAnalysisResult(
            success=True,
            data=summary_data,
            analysis_type=PatentAnalysisType.PORTFOLIO_OVERVIEW,
            summary=f"특허 포트폴리오 개요: 총 {total}건 (등록 {granted}, 출원 {pending})",
            visualization_data=viz_data,
            key_insights=[
                f"등록률: {granted/max(total,1)*100:.1f}%",
                f"주요 기술 분야: {', '.join(top_ipcs[:3])}",
                f"주요 출원인: {', '.join(top_applicants[:3])}"
            ],
            metrics=ToolMetrics(latency_ms=0, provider="patent_analysis"),
            errors=[],
            trace_id="",
            tool_name=self.name,
            tool_version=self.version
        )
    
    def _calculate_trend(self, patents: List[PatentData]) -> str:
        """트렌드 계산"""
        current_year = datetime.now().year
        recent = sum(1 for p in patents if p.application_date and int(p.application_date[:4]) >= current_year - 2)
        older = sum(1 for p in patents if p.application_date and int(p.application_date[:4]) < current_year - 2)
        
        if recent > older * 1.5:
            return "growing"
        elif recent < older * 0.5:
            return "declining"
        return "stable"
    
    def _calculate_growth_rate(self, patents: List[PatentData]) -> float:
        """성장률 계산"""
        current_year = datetime.now().year
        recent = sum(1 for p in patents if p.application_date and int(p.application_date[:4]) >= current_year - 2)
        older = sum(1 for p in patents if p.application_date and current_year - 4 <= int(p.application_date[:4]) < current_year - 2)
        
        if older == 0:
            return 0.0
        return ((recent - older) / older) * 100
    
    def _run(self, patents: List[PatentData], **kwargs) -> PatentAnalysisResult:
        """동기 실행"""
        return asyncio.run(self._arun(patents, **kwargs))


# =============================================================================
# Factory Function & Singleton Instance
# =============================================================================

def get_patent_analysis_tool() -> PatentAnalysisTool:
    """PatentAnalysisTool 인스턴스 반환"""
    return PatentAnalysisTool()


# 싱글톤 인스턴스 (import 시 사용)
patent_analysis_tool = PatentAnalysisTool()

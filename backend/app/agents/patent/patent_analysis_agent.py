"""
Patent Analysis Agent - 특허 분석 전문 에이전트

엔터프라이즈 경쟁 인텔리전스를 위한 특허 데이터 검색, 분석, 시각화

주요 기능:
1. 특허 검색 (KIPRIS, Google Patents via SerpAPI)
2. 경쟁사 특허 비교 분석
3. 기술 트렌드 분석 (시계열)
4. 특허 포트폴리오 분석
5. 기술 공백(White Space) 분석
6. 시각화 데이터 생성 (차트, 그래프)
7. LLM 기반 심층 분석 및 인사이트 생성
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.tools.retrieval.patent_search_tool import (
    PatentSearchTool, 
    PatentData,
    PatentSearchResult,
    PatentJurisdiction,
    PatentStatus
)
from app.tools.retrieval.patent_functional_tools import (
    PatentDiscoveryTool,
    PatentDetailTool,
    PatentLegalTool
)
from app.tools.retrieval.patent_analysis_tool import (
    PatentAnalysisTool,
    PatentAnalysisType,
    PatentAnalysisResult
)
from app.services.core.ai_service import ai_service


# =============================================================================
# 시스템 프롬프트 로딩
# =============================================================================

def load_patent_analysis_prompt() -> str:
    """특허 분석 시스템 프롬프트 로딩"""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "patent-analysis.prompt"
    
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        logger.warning(f"⚠️ 특허 분석 프롬프트 파일을 찾을 수 없습니다: {prompt_path}")
        return DEFAULT_PATENT_ANALYSIS_PROMPT


DEFAULT_PATENT_ANALYSIS_PROMPT = """당신은 특허 분석 전문가입니다. 
제공된 특허 데이터를 분석하여 기술 트렌드, 경쟁력 분석, 시장 인사이트, 전략적 권고를 제공합니다.
분석은 한국어로 작성하고, 비전문가도 이해할 수 있도록 설명해 주세요."""


# =============================================================================
# Input/Output Models
# =============================================================================

class PatentAnalysisAgentInput(BaseModel):
    """특허 분석 에이전트 입력 스키마"""
    
    query: str = Field(
        ..., 
        description="검색 쿼리 또는 분석 요청 (예: '삼성전자 AI 반도체 특허')"
    )
    analysis_type: str = Field(
        default="search",
        description="분석 유형: search(검색), comparison(경쟁사비교), trend(트렌드), portfolio(포트폴리오), gap(기술공백)"
    )
    our_company: Optional[str] = Field(
        default=None,
        description="우리 회사명 (경쟁사 비교 시 필수)"
    )
    competitor: Optional[str] = Field(
        default=None,
        description="경쟁사명 (경쟁사 비교 시 필수)"
    )
    jurisdiction: str = Field(
        default="KR",
        description="관할권: KR(한국), US(미국), EP(유럽), ALL(전체)"
    )
    date_from: Optional[str] = Field(
        default=None,
        description="출원일 시작 (YYYY-MM-DD)"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="출원일 종료 (YYYY-MM-DD)"
    )
    ipc_codes: Optional[List[str]] = Field(
        default=None,
        description="IPC 분류 코드 필터 (예: ['G06N', 'H01L'])"
    )
    max_results: int = Field(
        default=50,
        description="최대 검색 결과 수"
    )
    include_visualization: bool = Field(
        default=True,
        description="시각화 데이터 포함 여부"
    )
    time_range_years: int = Field(
        default=5,
        description="트렌드 분석 시 기간 (년)"
    )


class VisualizationData(BaseModel):
    """시각화 데이터 모델"""
    
    chart_type: str = Field(description="차트 유형: bar, line, pie, radar, timeline, network")
    title: str = Field(description="차트 제목")
    data: Dict[str, Any] = Field(description="차트 데이터")
    options: Dict[str, Any] = Field(default_factory=dict, description="차트 옵션")


class PatentAnalysisAgentOutput(BaseModel):
    """특허 분석 에이전트 출력"""
    
    success: bool = Field(description="성공 여부")
    analysis_type: str = Field(description="수행된 분석 유형")
    summary: str = Field(description="분석 결과 요약 (자연어)")
    patents: List[Dict[str, Any]] = Field(default_factory=list, description="검색된 특허 목록")
    total_patents: int = Field(default=0, description="총 특허 수")
    analysis_result: Optional[Dict[str, Any]] = Field(default=None, description="상세 분석 결과")
    visualizations: List[VisualizationData] = Field(default_factory=list, description="시각화 데이터")
    insights: List[str] = Field(default_factory=list, description="핵심 인사이트")
    recommendations: List[str] = Field(default_factory=list, description="권장 사항")
    trace_id: str = Field(description="추적 ID")
    elapsed_ms: float = Field(description="처리 시간 (ms)")
    errors: List[str] = Field(default_factory=list, description="오류 목록")


# =============================================================================
# Patent Analysis Agent Tool
# =============================================================================

class PatentAnalysisAgentTool(BaseTool):
    """
    특허 분석 AI 에이전트
    
    LangChain Tool 인터페이스를 구현하여 SupervisorAgent에서 호출 가능
    
    지원 분석 유형:
    1. search: 특허 검색
    2. comparison: 경쟁사 특허 비교
    3. trend: 시계열 트렌드 분석
    4. portfolio: 포트폴리오 개요
    5. gap: 기술 공백 분석
    """
    
    name: str = "patent_analysis_agent"
    description: str = """특허 분석 전문 에이전트 - 엔터프라이즈 경쟁 인텔리전스.

기능:
- 특허 검색 (KIPRIS 한국, SerpAPI Google Patents 글로벌)
- 경쟁사 특허 비교 분석 ("삼성전자 vs LG전자 AI 특허 비교")
- 기술 트렌드 분석 (시계열 변화)
- 특허 포트폴리오 분석
- 기술 공백(White Space) 분석
- 시각화 데이터 생성 (차트, 그래프)

사용 시나리오:
- "삼성전자의 AI 반도체 관련 특허를 검색해줘"
- "우리회사와 삼성전자의 특허 포트폴리오를 비교해줘"
- "최근 5년간 AI 반도체 특허 트렌드를 분석해줘"
- "경쟁사 대비 우리가 부족한 기술 분야는?"
"""
    args_schema: Type[BaseModel] = PatentAnalysisAgentInput
    
    # 내부 도구 (PrivateAttr로 pydantic 호환)
    _search_tool: PatentSearchTool = PrivateAttr()
    _analysis_tool: PatentAnalysisTool = PrivateAttr()
    _discovery_tool: PatentDiscoveryTool = PrivateAttr()
    _detail_tool: PatentDetailTool = PrivateAttr()
    _legal_tool: PatentLegalTool = PrivateAttr()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._search_tool = PatentSearchTool()
        self._analysis_tool = PatentAnalysisTool()
        self._discovery_tool = PatentDiscoveryTool()
        self._detail_tool = PatentDetailTool()
        self._legal_tool = PatentLegalTool()
    
    def _map_discovery_to_patent_data(self, item: Dict[str, Any]) -> PatentData:
        """Discovery Tool 결과를 PatentData로 변환"""
        # 상태 매핑
        status_str = item.get("status", "")
        status = PatentStatus.APPLICATION
        if "등록" in status_str:
            status = PatentStatus.GRANTED
        elif "공개" in status_str:
            status = PatentStatus.PUBLISHED
        elif "취하" in status_str:
            status = PatentStatus.WITHDRAWN
        elif "소멸" in status_str or "만료" in status_str:
            status = PatentStatus.EXPIRED
            
        return PatentData(
            patent_number=item.get("application_number", ""),
            title=item.get("title", ""),
            abstract=item.get("abstract", ""),
            applicant=item.get("applicant", ""),
            inventors=[], # Discovery 결과에는 발명자가 없을 수 있음
            ipc_codes=item.get("ipc_all", []) or ([item.get("ipc_code")] if item.get("ipc_code") else []),
            application_date=item.get("application_date"),
            publication_date=item.get("open_date"),
            grant_date=item.get("register_date"),
            status=status,
            jurisdiction=PatentJurisdiction.KR,
            url=f"https://kpat.kipris.or.kr/kpat/biblioa.do?applno={item.get('application_number', '')}"
        )

    async def _analyze_query_with_llm(self, query: str) -> Dict[str, Any]:
        """LLM을 사용하여 쿼리 의도 및 파라미터 정밀 분석"""
        try:
            system_prompt = """당신은 특허 분석 요청을 구조화된 데이터로 변환하는 전문가입니다.
사용자의 자연어 질의를 분석하여 다음 JSON 형식으로 추출해주세요.

{
    "is_valid": true/false,
    "reason": "유효하지 않은 경우 이유",
    "analysis_type": "search" | "comparison" | "trend" | "portfolio" | "gap",
    "applicant": "주 출원인(회사명) 또는 null",
    "competitor": "비교 대상 경쟁사 또는 null",
    "keywords": "기술 키워드 (회사명, 불용어 제외) 또는 null",
    "date_from": "YYYY-MM-DD 또는 null",
    "date_to": "YYYY-MM-DD 또는 null",
    "jurisdiction": "KR" | "US" | "ALL"
}

분석 가이드:
1. **출원인(applicant)**: '삼성전자', 'LG에너지솔루션' 등 회사명을 정확히 추출하세요. (주), 주식회사 등은 제외하고 핵심 명칭만 추출.
2. **분석 유형(analysis_type)**:
   - 두 개 이상의 회사가 언급되고 비교/대조/차이 등의 단어가 있으면 "comparison"
   - '트렌드', '동향', '추이', '변화' 등이 있으면 "trend"
   - '포트폴리오', '현황', '보유 특허' 등이 있으면 "portfolio"
   - '공백', '빈틈', '기회' 등이 있으면 "gap"
   - 그 외에는 "search"
3. **키워드(keywords)**: '특허', '검색', '분석', '해줘' 등 불용어를 제외한 기술적 핵심 단어만 남기세요.
4. **유효성(is_valid)**: 특허 분석과 무관한 질의거나, 분석에 필요한 최소한의 정보(키워드 또는 출원인)가 없으면 false로 설정하세요.
"""
            
            response = await ai_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.0
            )
            
            import json
            content = response.get("response", "{}")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            result = json.loads(content)
            logger.info(f"🧠 [PatentAnalysisAgent] LLM 쿼리 분석 결과: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [PatentAnalysisAgent] LLM 쿼리 분석 실패: {e}")
            # 실패 시 기본값 반환
            return {
                "is_valid": True,
                "analysis_type": "search",
                "applicant": self._extract_applicant_from_query(query),
                "keywords": self._clean_query(query, None),
                "competitor": None,
                "date_from": None,
                "date_to": None,
                "jurisdiction": "KR"
            }

    async def _arun(
        self,
        query: str,
        analysis_type: str = "search",
        our_company: Optional[str] = None,
        competitor: Optional[str] = None,
        jurisdiction: str = "KR",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        ipc_codes: Optional[List[str]] = None,
        max_results: int = 50,
        include_visualization: bool = True,
        time_range_years: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        특허 분석 실행
        
        Args:
            query: 검색 쿼리 또는 분석 요청
            analysis_type: 분석 유형 (search/comparison/trend/portfolio/gap)
            our_company: 우리 회사명 (비교 분석 시)
            competitor: 경쟁사명 (비교 분석 시)
            jurisdiction: 관할권 (KR/US/EP/ALL)
            date_from: 출원일 시작
            date_to: 출원일 종료
            ipc_codes: IPC 필터
            max_results: 최대 결과 수
            include_visualization: 시각화 포함 여부
            time_range_years: 트렌드 분석 기간
        
        Returns:
            Dict: 분석 결과 (PatentAnalysisAgentOutput 형태)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        logger.info(
            f"🔬 [PatentAnalysisAgent] 분석 시작: type={analysis_type}, query='{query[:50]}...'"
        )
        
        try:
            # 1. LLM 기반 쿼리 정밀 분석 (입력 정보 강화)
            analyzed_query = await self._analyze_query_with_llm(query)
            
            if not analyzed_query.get("is_valid", True):
                return {
                    "success": False,
                    "analysis_type": analysis_type,
                    "summary": f"분석할 수 없는 질의입니다: {analyzed_query.get('reason', '정보 부족')}",
                    "patents": [],
                    "total_patents": 0,
                    "analysis_result": None,
                    "visualizations": [],
                    "insights": [],
                    "recommendations": ["더 구체적인 회사명이나 기술 키워드를 입력해주세요."],
                    "trace_id": trace_id,
                    "elapsed_ms": 0,
                    "errors": [analyzed_query.get("reason", "Invalid query")]
                }

            # 2. 파라미터 병합 (LLM 분석 결과 우선 적용)
            # analysis_type이 기본값('search')인 경우 LLM 분석 결과 사용
            if analysis_type == "search" and analyzed_query.get("analysis_type"):
                analysis_type = analyzed_query["analysis_type"]
            
            # 회사명/경쟁사 정보 보강
            if not our_company and analyzed_query.get("applicant"):
                our_company = analyzed_query["applicant"]
            if not competitor and analyzed_query.get("competitor"):
                competitor = analyzed_query["competitor"]
                
            # 날짜 정보 보강
            if not date_from and analyzed_query.get("date_from"):
                date_from = analyzed_query["date_from"]
            if not date_to and analyzed_query.get("date_to"):
                date_to = analyzed_query["date_to"]
                
            # 관할권 정보 보강
            if jurisdiction == "KR" and analyzed_query.get("jurisdiction"):
                jurisdiction = analyzed_query["jurisdiction"]

            # 검색용 키워드 (LLM이 추출한 키워드 사용)
            search_keywords = analyzed_query.get("keywords") or query
            
            logger.info(f"🔧 [PatentAnalysisAgent] 파라미터 확정: type={analysis_type}, applicant={our_company}, keywords={search_keywords}")

            # 분석 유형에 따라 처리
            if analysis_type == "search":
                result = await self._execute_search(
                    query=search_keywords,
                    applicant=our_company, # 추출된 출원인 전달
                    jurisdiction=jurisdiction,
                    date_from=date_from,
                    date_to=date_to,
                    ipc_codes=ipc_codes,
                    max_results=max_results,
                    include_visualization=include_visualization
                )
            elif analysis_type == "comparison":
                result = await self._execute_comparison(
                    query=search_keywords,
                    our_company=our_company,
                    competitor=competitor,
                    jurisdiction=jurisdiction,
                    date_from=date_from,
                    date_to=date_to,
                    max_results=max_results,
                    include_visualization=include_visualization
                )
            elif analysis_type == "trend":
                result = await self._execute_trend_analysis(
                    query=search_keywords,
                    jurisdiction=jurisdiction,
                    time_range_years=time_range_years,
                    max_results=max_results,
                    include_visualization=include_visualization
                )
            elif analysis_type == "portfolio":
                result = await self._execute_portfolio_analysis(
                    query=search_keywords,
                    company=our_company or competitor,
                    jurisdiction=jurisdiction,
                    max_results=max_results,
                    include_visualization=include_visualization
                )
            elif analysis_type == "gap":
                result = await self._execute_gap_analysis(
                    query=search_keywords,
                    our_company=our_company,
                    competitor=competitor,
                    jurisdiction=jurisdiction,
                    max_results=max_results,
                    include_visualization=include_visualization
                )
            else:
                # 기본: 검색
                result = await self._execute_search(
                    query=search_keywords,
                    applicant=our_company,
                    jurisdiction=jurisdiction,
                    max_results=max_results,
                    include_visualization=include_visualization
                )
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result["trace_id"] = trace_id
            result["elapsed_ms"] = elapsed_ms
            result["success"] = True
            
            logger.info(f"✅ [PatentAnalysisAgent] 완료: {elapsed_ms:.0f}ms")
            
            return result
            
        except Exception as e:
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [PatentAnalysisAgent] 오류: {e}")
            
            return {
                "success": False,
                "analysis_type": analysis_type,
                "summary": f"분석 중 오류가 발생했습니다: {str(e)}",
                "patents": [],
                "total_patents": 0,
                "analysis_result": None,
                "visualizations": [],
                "insights": [],
                "recommendations": [],
                "trace_id": trace_id,
                "elapsed_ms": elapsed_ms,
                "errors": [str(e)]
            }
    
    def _run(
        self,
        query: str,
        **kwargs
    ) -> Dict[str, Any]:
        """동기 실행 (폴백)"""
        return asyncio.run(self._arun(query, **kwargs))
    
    # =========================================================================
    # 분석 유형별 실행 메서드
    # =========================================================================
    
    async def _execute_search(
        self,
        query: str,
        applicant: Optional[str] = None,
        jurisdiction: str = "KR",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        ipc_codes: Optional[List[str]] = None,
        max_results: int = 50,
        include_visualization: bool = True
    ) -> Dict[str, Any]:
        """특허 검색 실행"""
        import re
        
        # 쿼리에서 출원인 추출 시도 (전달받지 못한 경우 폴백)
        if not applicant:
            applicant = self._extract_applicant_from_query(query)
        
        # 쿼리 정제
        # LLM이 이미 키워드를 추출했더라도, 추가적인 정제(조사 제거 등)를 위해 실행
        clean_query = self._clean_query(query, applicant)
        
        # 🔧 디버그: clean_query 값 확인
        logger.info(f"🔧 [PatentAnalysisAgent] 쿼리 정제: '{query}' → clean='{clean_query}', applicant='{applicant}'")
        
        # 🆕 쿼리에서 연도 정보 추출 (전달받지 못한 경우)
        if not date_from:
            year_match = re.search(r'(\d{4})년', query)
            if year_match:
                year = year_match.group(1)
                date_from = f"{year}-01-01"
                date_to = f"{year}-12-31"
                logger.info(f"📅 연도 필터 적용: {date_from} ~ {date_to}")
        
        patents: List[PatentData] = []
        errors: List[str] = []
        total_count = 0
        
        search_params = {
            "query": clean_query,
            "applicant": applicant,
            "jurisdiction": jurisdiction,
            "date_from": date_from,
            "date_to": date_to
        }
        
        # 1. KR 검색 (Discovery Tool 사용)
        if jurisdiction in ["KR", "ALL"]:
            try:
                discovery_results = await self._discovery_tool._arun(
                    query=clean_query,
                    applicant=applicant,
                    date_from=date_from,
                    date_to=date_to,
                    ipc_code=ipc_codes[0] if ipc_codes else None,
                    max_results=max_results
                )
                
                # Handle new dict return format with total_count
                kr_patents_list = []
                kr_total = 0
                
                if isinstance(discovery_results, dict) and "patents" in discovery_results:
                    kr_patents_list = discovery_results["patents"]
                    kr_total = discovery_results.get("total_count", 0)
                elif isinstance(discovery_results, list):
                    kr_patents_list = discovery_results
                    kr_total = len(discovery_results)
                
                for item in kr_patents_list:
                    patents.append(self._map_discovery_to_patent_data(item))
                
                # Update total count (use max of retrieved or reported total)
                total_count += max(kr_total, len(kr_patents_list))
                    
                logger.info(f"✅ [Discovery] KR 특허 {len(kr_patents_list)}건 검색 완료 (총 {kr_total}건)")
            except Exception as e:
                logger.error(f"❌ [Discovery] KR 검색 실패: {e}")
                errors.append(f"KR 검색 실패: {str(e)}")
        
        # 2. Global 검색 (Legacy Search Tool 사용)
        if jurisdiction != "KR":
            try:
                # KR이 아니거나 ALL인 경우 Global 검색
                # ALL인 경우 KR은 위에서 했으므로 Global만 추가
                target_jurisdiction = jurisdiction if jurisdiction != "ALL" else "US" # ALL일 때 Global 대표로 US 검색 (임시)
                
                global_result = await self._search_tool._arun(
                    query=clean_query,
                    applicant=applicant,
                    jurisdiction=target_jurisdiction,
                    date_from=date_from,
                    date_to=date_to,
                    ipc_codes=ipc_codes,
                    max_results=max_results,
                    include_global=True
                )
                
                if global_result.data:
                    patents.extend(global_result.data)
                    # Add global total count
                    total_count += global_result.total_found
                    logger.info(f"✅ [Global] {len(global_result.data)}건 검색 완료")
            except Exception as e:
                logger.error(f"❌ [Global] 검색 실패: {e}")
                errors.append(f"Global 검색 실패: {str(e)}")
        
        # 🆕 검색 결과가 없거나 출원인 매칭 실패 시 인터넷 검색 폴백
        if not patents and applicant:
            logger.warning(f"⚠️ [PatentAnalysisAgent] KIPRIS에서 '{applicant}' 특허를 찾을 수 없음 → 인터넷 검색 폴백")
            return await self._fallback_to_internet_search(query, applicant, date_from)
        
        # 🆕 연도 필터링 (검색 결과에서 추가 필터)
        if date_from and date_to:
            target_year = date_from[:4]
            filtered_patents = [
                p for p in patents 
                if p.application_date and p.application_date.startswith(target_year)
            ]
            if filtered_patents:
                patents = filtered_patents
                logger.info(f"📅 {target_year}년 특허 필터링: {len(patents)}건")
        
        # 시각화 데이터 생성
        visualizations = []
        if include_visualization and patents:
            visualizations = self._generate_search_visualizations(patents)
        
        # 🆕 상세 요약 생성 (원본 쿼리, 검색 맥락 포함)
        summary = await self._generate_search_summary(
            original_query=query,
            patents=patents,
            applicant=applicant,
            year_filter=date_from[:4] if date_from else None
        )
        
        # 🆕 상세 인사이트 추출
        insights = self._extract_search_insights(patents, applicant)
        
        return {
            "analysis_type": "search",
            "summary": summary,
            "patents": [p.model_dump() for p in patents],
            "total_patents": total_count if total_count > len(patents) else len(patents),
            "analysis_result": {
                "search_params": search_params,
                "source": "kipris_discovery" if jurisdiction == "KR" else "hybrid",
                "year_filter": date_from[:4] if date_from else None
            },
            "visualizations": [v.model_dump() for v in visualizations],
            "insights": insights,
            "recommendations": [],
            "errors": errors
        }
    
    async def _fallback_to_internet_search(
        self,
        query: str,
        applicant: str,
        date_from: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        KIPRIS 검색 실패 시 인터넷 검색으로 폴백
        
        정확한 출원인의 특허를 찾지 못하면, 잘못된 정보를 제공하는 것보다
        인터넷에서 관련 정보를 검색하여 제공하는 것이 더 낫습니다.
        """
        try:
            from app.tools.retrieval.internet_search_tool import internet_search_tool
            
            # 인터넷 검색 쿼리 구성
            year_str = date_from[:4] if date_from else ""
            search_query = f"{applicant} {year_str} 특허 출원 현황"
            
            logger.info(f"🌐 [PatentAnalysisAgent] 인터넷 검색: '{search_query}'")
            
            # 인터넷 검색 실행
            search_result = await internet_search_tool._arun(query=search_query)
            
            # 검색 결과에서 텍스트 추출
            internet_summary = ""
            if search_result.success and search_result.data:
                for item in search_result.data[:5]:  # 상위 5개만
                    # SearchChunk 객체에서 속성 추출
                    title = getattr(item, 'title', '') or ''
                    content = getattr(item, 'content', '') or ''
                    url = getattr(item, 'url', '') or getattr(item, 'source_url', '') or ''
                    if title:
                        internet_summary += f"- **{title}**\n"
                        if content:
                            internet_summary += f"  {content[:200]}...\n"
                        if url:
                            internet_summary += f"  [링크]({url})\n"
                        internet_summary += "\n"
            
            if not internet_summary:
                internet_summary = "관련 정보를 찾을 수 없습니다."
            
            # 검색 결과를 요약 형태로 반환
            summary = f"""## 📋 특허 검색 결과

### ⚠️ KIPRIS 검색 결과 없음

**'{applicant}'**의 특허를 KIPRIS(한국특허정보원)에서 직접 검색하였으나, 
정확히 일치하는 출원인의 특허를 찾지 못했습니다.

**가능한 원인:**
- 회사명이 KIPRIS에 등록된 정식 명칭과 다를 수 있습니다
- 해당 기간에 출원된 특허가 없을 수 있습니다
- 아직 공개되지 않은 특허일 수 있습니다 (출원 후 18개월 이내)

---

### 🌐 인터넷 검색 결과

다음은 인터넷에서 찾은 **'{applicant}'** 관련 특허 정보입니다:

{internet_summary}

---

### 💡 권장 사항

1. **정확한 회사명 확인**: KIPRIS에서 직접 '{applicant}' 검색하여 정식 출원인명 확인
2. **KIPRIS 직접 검색**: [KIPRIS](https://www.kipris.or.kr) 사이트에서 직접 검색
3. **기간 조정**: 더 넓은 기간으로 검색 시도
"""
            
            return {
                "analysis_type": "search",
                "summary": summary,
                "patents": [],
                "total_patents": 0,
                "analysis_result": {
                    "source": "internet_search_fallback",
                    "reason": "KIPRIS에서 정확한 출원인 매칭 실패",
                    "applicant": applicant
                },
                "visualizations": [],
                "insights": [
                    f"KIPRIS에서 '{applicant}'의 특허를 찾지 못함",
                    "인터넷 검색으로 대체 정보 제공",
                    "정확한 특허 정보는 KIPRIS 직접 검색 권장"
                ],
                "recommendations": [
                    f"KIPRIS에서 '{applicant}' 정식 출원인명 확인",
                    "특허청 특허로 사이트에서 직접 검색"
                ],
                "errors": []
            }
            
        except Exception as e:
            logger.error(f"❌ [PatentAnalysisAgent] 인터넷 검색 폴백 실패: {e}")
            return {
                "analysis_type": "search",
                "summary": f"## ⚠️ 검색 실패\n\n'{applicant}'의 특허 정보를 찾을 수 없습니다.\n\n**권장 사항:**\n- KIPRIS(https://www.kipris.or.kr)에서 직접 검색하세요\n- 정확한 출원인명을 확인해 주세요",
                "patents": [],
                "total_patents": 0,
                "analysis_result": {"source": "error", "error": str(e)},
                "visualizations": [],
                "insights": [],
                "recommendations": ["KIPRIS에서 직접 검색"],
                "errors": [str(e)]
            }

    async def _execute_comparison(
        self,
        query: str,
        our_company: Optional[str],
        competitor: Optional[str],
        jurisdiction: str = "KR",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
        include_visualization: bool = True
    ) -> Dict[str, Any]:
        """경쟁사 특허 비교 분석"""
        
        if not our_company or not competitor:
            return {
                "analysis_type": "comparison",
                "summary": "경쟁사 비교 분석을 위해서는 우리 회사명(our_company)과 경쟁사명(competitor)이 필요합니다.",
                "patents": [],
                "total_patents": 0,
                "analysis_result": None,
                "visualizations": [],
                "insights": [],
                "recommendations": ["our_company와 competitor 파라미터를 제공해주세요."],
                "errors": ["Missing required parameters: our_company, competitor"]
            }
        
        # 양측 특허 검색
        our_result = await self._search_tool._arun(
            query=query,
            applicant=our_company,
            jurisdiction=jurisdiction,
            date_from=date_from,
            date_to=date_to,
            max_results=max_results,
            include_global=(jurisdiction != "KR")
        )
        
        competitor_result = await self._search_tool._arun(
            query=query,
            applicant=competitor,
            jurisdiction=jurisdiction,
            date_from=date_from,
            date_to=date_to,
            max_results=max_results,
            include_global=(jurisdiction != "KR")
        )
        
        our_patents = our_result.data
        competitor_patents = competitor_result.data
        all_patents = our_patents + competitor_patents
        
        # 비교 분석 수행
        analysis_result = await self._analysis_tool._arun(
            patents=all_patents,
            analysis_type="comparison",
            our_company=our_company,
            comparison_target=competitor
        )
        
        # 시각화 데이터 생성
        visualizations = []
        if include_visualization:
            visualizations = self._generate_comparison_visualizations(
                our_patents, competitor_patents, our_company, competitor
            )
        
        # 요약 생성
        summary = await self._generate_comparison_summary(
            query, our_company, competitor, our_patents, competitor_patents, analysis_result
        )
        
        # 인사이트 및 권장사항
        insights = self._extract_comparison_insights(our_patents, competitor_patents, our_company, competitor)
        recommendations = self._generate_comparison_recommendations(analysis_result)
        
        return {
            "analysis_type": "comparison",
            "summary": summary,
            "patents": [p.model_dump() for p in all_patents],
            "total_patents": len(all_patents),
            "analysis_result": analysis_result.model_dump() if hasattr(analysis_result, 'model_dump') else analysis_result,
            "visualizations": [v.model_dump() for v in visualizations],
            "insights": insights,
            "recommendations": recommendations,
            "errors": our_result.errors + competitor_result.errors
        }
    
    async def _execute_trend_analysis(
        self,
        query: str,
        jurisdiction: str = "KR",
        time_range_years: int = 5,
        max_results: int = 100,
        include_visualization: bool = True
    ) -> Dict[str, Any]:
        """시계열 트렌드 분석"""
        
        # 기간 계산
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * time_range_years)
        
        date_from = start_date.strftime("%Y-%m-%d")
        date_to = end_date.strftime("%Y-%m-%d")
        
        # 특허 검색
        search_result = await self._search_tool._arun(
            query=query,
            jurisdiction=jurisdiction,
            date_from=date_from,
            date_to=date_to,
            max_results=max_results,
            include_global=(jurisdiction != "KR")
        )
        
        patents = search_result.data
        
        # 트렌드 분석 수행
        analysis_result = await self._analysis_tool._arun(
            patents=patents,
            analysis_type="timeline",
            time_range_years=time_range_years
        )
        
        # 시각화 데이터 생성
        visualizations = []
        if include_visualization and patents:
            visualizations = self._generate_trend_visualizations(patents, time_range_years)
        
        # 요약 생성
        summary = await self._generate_trend_summary(query, patents, time_range_years, analysis_result)
        
        # 인사이트 추출
        insights = self._extract_trend_insights(patents, time_range_years)
        
        return {
            "analysis_type": "trend",
            "summary": summary,
            "patents": [p.model_dump() for p in patents],
            "total_patents": len(patents),
            "analysis_result": analysis_result.model_dump() if hasattr(analysis_result, 'model_dump') else analysis_result,
            "visualizations": [v.model_dump() for v in visualizations],
            "insights": insights,
            "recommendations": [],
            "errors": search_result.errors
        }
    
    async def _execute_portfolio_analysis(
        self,
        query: str,
        company: Optional[str],
        jurisdiction: str = "KR",
        max_results: int = 100,
        include_visualization: bool = True
    ) -> Dict[str, Any]:
        """포트폴리오 분석"""
        
        # 특허 검색
        search_result = await self._search_tool._arun(
            query=query,
            applicant=company,
            jurisdiction=jurisdiction,
            max_results=max_results,
            include_global=(jurisdiction != "KR")
        )
        
        patents = search_result.data
        
        # 포트폴리오 분석 수행
        analysis_result = await self._analysis_tool._arun(
            patents=patents,
            analysis_type="portfolio"
        )
        
        # 토픽 분석도 수행
        topic_result = await self._analysis_tool._arun(
            patents=patents,
            analysis_type="topic"
        )
        
        # 시각화 데이터 생성
        visualizations = []
        if include_visualization and patents:
            visualizations = self._generate_portfolio_visualizations(patents, company)
        
        # 요약 생성
        summary = await self._generate_portfolio_summary(query, company, patents, analysis_result, topic_result)
        
        # 인사이트 추출
        insights = self._extract_portfolio_insights(patents, company)
        
        return {
            "analysis_type": "portfolio",
            "summary": summary,
            "patents": [p.model_dump() for p in patents],
            "total_patents": len(patents),
            "analysis_result": {
                "portfolio": analysis_result.model_dump() if hasattr(analysis_result, 'model_dump') else analysis_result,
                "topics": topic_result.model_dump() if hasattr(topic_result, 'model_dump') else topic_result
            },
            "visualizations": [v.model_dump() for v in visualizations],
            "insights": insights,
            "recommendations": [],
            "errors": search_result.errors
        }
    
    async def _execute_gap_analysis(
        self,
        query: str,
        our_company: Optional[str],
        competitor: Optional[str],
        jurisdiction: str = "KR",
        max_results: int = 100,
        include_visualization: bool = True
    ) -> Dict[str, Any]:
        """기술 공백 분석"""
        
        if not our_company or not competitor:
            return {
                "analysis_type": "gap",
                "summary": "기술 공백 분석을 위해서는 우리 회사명(our_company)과 경쟁사명(competitor)이 필요합니다.",
                "patents": [],
                "total_patents": 0,
                "analysis_result": None,
                "visualizations": [],
                "insights": [],
                "recommendations": ["our_company와 competitor 파라미터를 제공해주세요."],
                "errors": ["Missing required parameters"]
            }
        
        # 양측 특허 검색
        our_result = await self._search_tool._arun(
            query=query,
            applicant=our_company,
            jurisdiction=jurisdiction,
            max_results=max_results,
            include_global=(jurisdiction != "KR")
        )
        
        competitor_result = await self._search_tool._arun(
            query=query,
            applicant=competitor,
            jurisdiction=jurisdiction,
            max_results=max_results,
            include_global=(jurisdiction != "KR")
        )
        
        all_patents = our_result.data + competitor_result.data
        
        # 기술 공백 분석 수행
        analysis_result = await self._analysis_tool._arun(
            patents=all_patents,
            analysis_type="gap",
            our_company=our_company,
            comparison_target=competitor
        )
        
        # 시각화 데이터 생성
        visualizations = []
        if include_visualization:
            visualizations = self._generate_gap_visualizations(
                our_result.data, competitor_result.data, our_company, competitor
            )
        
        # 요약 생성
        summary = await self._generate_gap_summary(query, our_company, competitor, analysis_result)
        
        # 인사이트 및 권장사항
        insights = self._extract_gap_insights(analysis_result)
        recommendations = self._generate_gap_recommendations(analysis_result)
        
        return {
            "analysis_type": "gap",
            "summary": summary,
            "patents": [p.model_dump() for p in all_patents],
            "total_patents": len(all_patents),
            "analysis_result": analysis_result.model_dump() if hasattr(analysis_result, 'model_dump') else analysis_result,
            "visualizations": [v.model_dump() for v in visualizations],
            "insights": insights,
            "recommendations": recommendations,
            "errors": our_result.errors + competitor_result.errors
        }
    
    # =========================================================================
    # 헬퍼 메서드
    # =========================================================================
    
    def _extract_applicant_from_query(self, query: str) -> Optional[str]:
        """쿼리에서 출원인(회사명) 추출"""
        import re
        
        # 1. 알려진 한국 대기업 패턴 (정확한 매칭)
        korean_companies = [
            "삼성전자", "삼성SDI", "삼성디스플레이", "삼성바이오로직스", "삼성SDS",
            "LG전자", "LG화학", "LG에너지솔루션", "LG디스플레이", "LG이노텍",
            "SK하이닉스", "SK이노베이션", "SK텔레콤", "SKC",
            "현대자동차", "현대모비스", "기아", "현대건설",
            "네이버", "카카오", "쿠팡", "토스", "배달의민족",
            "포스코", "롯데케미칼", "한화솔루션", "두산에너빌리티", "CJ제일제당"
        ]
        
        for company in korean_companies:
            if company in query:
                logger.debug(f"📌 출원인 추출 (알려진 기업): {company}")
                return company
        
        # 2. "~의 특허", "~가 출원한", "~에서 개발한" 패턴
        patterns = [
            r'([가-힣A-Za-z0-9]+(?:전자|그룹|전기|통신|반도체|메디컬|바이오|테크|소프트|시스템즈?|솔루션|이노베이션|에너지))(?:의|가|에서|이|는)',
            r'([가-힣A-Za-z0-9]+(?:주식회사|㈜|\(주\)|Inc\.|Corp\.|Ltd\.?))(?:의|가|에서|이|는)?',
            r'([가-힣]{2,}(?:전자|화학|건설|제약|바이오|테크|메디컬))(?:의|가|에서)?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # 너무 짧거나 일반 명사는 제외
                if len(company) >= 3 and company not in ['특허', '출원', '분석', '검색']:
                    logger.debug(f"📌 출원인 추출 (패턴 매칭): {company}")
                    return company
        
        # 3. "회사명 + 연도 + 특허" 패턴 (예: "제이시스메디컬 2024년 출원 특허")
        match = re.search(r'([가-힣A-Za-z0-9]+)\s+\d{4}년\s*(?:출원|등록|공개)?\s*특허', query)
        if match:
            company = match.group(1).strip()
            if len(company) >= 2 and company not in ['특허', '출원', '분석', '검색', '년']:
                logger.debug(f"📌 출원인 추출 (연도+특허 패턴): {company}")
                return company
        
        # 4. 쿼리 시작 부분의 고유명사 추출 (마지막 수단)
        # "제이시스메디컬 특허 분석" → "제이시스메디컬"
        words = query.split()
        if words:
            first_word = words[0]
            # 첫 단어가 3글자 이상이고, 일반 명사가 아니면 회사명으로 추정
            if len(first_word) >= 3 and first_word not in ['특허', '출원', '분석', '검색', '최근', '올해', '작년']:
                # 한글+영문 조합이거나 특정 접미사가 있으면 회사명 가능성 높음
                if re.match(r'^[가-힣A-Za-z0-9]+$', first_word):
                    logger.debug(f"📌 출원인 추출 (첫 단어): {first_word}")
                    return first_word
        
        logger.debug(f"⚠️ 출원인 추출 실패: '{query}'")
        return None
    
    def _clean_query(self, query: str, applicant: Optional[str]) -> str:
        """쿼리에서 회사명과 요청문 제거하여 검색 키워드만 추출"""
        import re
        
        clean = query
        
        # 회사명 제거
        if applicant:
            clean = clean.replace(applicant, "").strip()
        
        # 요청문/명령어 패턴 제거 (더 포괄적)
        request_patterns = [
            r'분석\s*해\s*주\s*세\s*요', r'분석해주세요', r'분석해줘',
            r'검색\s*해\s*주\s*세\s*요', r'검색해주세요', r'검색해줘',
            r'해\s*주\s*세\s*요', r'해주세요', r'해\s*줘',
            r'알려\s*주\s*세\s*요', r'알려주세요', r'알려\s*줘',
            r'찾아\s*주\s*세\s*요', r'찾아주세요', r'찾아\s*줘',
            r'조사\s*해\s*주\s*세\s*요', r'조사해주세요',
            r'보여\s*주\s*세\s*요', r'보여주세요', r'보여\s*줘',
            r'확인\s*해\s*주\s*세\s*요', r'확인해주세요',
            r'\?$', r'\.$'
        ]
        for pattern in request_patterns:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        
        # "~의", "~가", "~에서" 등 조사 제거
        clean = re.sub(r'^[의가에서은는을를이]\s*', '', clean)
        clean = re.sub(r'[의가에서은는을를이]\s*$', '', clean)
        
        # "특허분석", "특허검색" 등 메타 단어는 유지하되 "특허" 단독은 제거
        clean = re.sub(r'\s+특허\s*$', '', clean)
        clean = re.sub(r'^특허\s+', '', clean)
        
        # "출원" 키워드가 있으면 연도 정보 추출 시도
        year_match = re.search(r'(\d{4})\s*년', clean)
        year_filter = year_match.group(1) if year_match else None
        
        # 연도 표현 정리 ("2024년 출원" → "2024"만 남기거나 제거)
        clean = re.sub(r'\d{4}\s*년\s*(출원|등록|공개)?', '', clean)
        
        # 불필요한 단어 제거 (더 포괄적)
        noise_words = [
            '출원', '등록', '공개', '분석', '검색', '관련', '대한', '에대한',
            '특허', '특허분석', '특허검색', '현황', '보고서', '자료',
            '주세요', '해줘', '주세', '해주',
            '건수', '개수', '몇개', '얼마나', '수량', '통계', '알수', '있나요', '있을까요', '건수를',
            '출원건수', '등록건수', '특허수', '특허건수'
        ]
        for word in noise_words:
            clean = clean.replace(word, ' ')
            
        # 특수문자 제거 (쉼표 등)
        clean = re.sub(r'[,;]', ' ', clean)
        
        # 연속 공백 정리
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        # 결과가 비어있으면 원본에서 핵심 키워드 추출 시도
        if not clean or len(clean) < 2:
            # 원본 쿼리에서 기술 관련 명사 추출 (간단한 패턴)
            tech_nouns = re.findall(r'[가-힣]{2,}(?:전자|기술|시스템|배터리|반도체|디스플레이|자동차|로봇|AI|인공지능)?', query)
            if tech_nouns:
                # 회사명과 일반 단어 제외
                exclude_words = [applicant, '특허', '출원', '분석', '검색', '해주세요', '주세요'] if applicant else ['특허', '출원', '분석', '검색', '해주세요', '주세요']
                tech_nouns = [n for n in tech_nouns if n not in exclude_words and len(n) >= 2]
                if tech_nouns:
                    clean = ' '.join(tech_nouns[:3])  # 상위 3개
        
        # 🆕 출원인만 검색하는 경우 (기술 키워드 없음) - 빈 문자열 반환
        # 이렇게 하면 KIPRIS/SerpAPI가 출원인 기반으로만 검색
        noise_check = ['특허', '분석', '검색', '현황', '자료', '보고서']
        if not clean or len(clean) < 2 or clean in noise_check or clean == applicant:
            logger.debug(f"🔍 출원인만 검색: '{applicant}', 원본 쿼리: '{query}'")
            return ""
        
        return clean.strip()
    
    # =========================================================================
    # 시각화 생성 메서드
    # =========================================================================
    
    def _generate_search_visualizations(self, patents: List[PatentData]) -> List[VisualizationData]:
        """검색 결과 시각화 생성"""
        visualizations = []
        
        # 1. 출원인별 특허 수 (파이 차트)
        applicant_counts = {}
        for p in patents:
            applicant = p.applicant or "Unknown"
            applicant_counts[applicant] = applicant_counts.get(applicant, 0) + 1
        
        visualizations.append(VisualizationData(
            chart_type="pie",
            title="출원인별 특허 분포",
            data={
                "labels": list(applicant_counts.keys()),
                "values": list(applicant_counts.values())
            },
            options={"showLegend": True}
        ))
        
        # 2. 연도별 출원 추이 (라인 차트)
        year_counts = {}
        for p in patents:
            if p.application_date:
                year = p.application_date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1
        
        sorted_years = sorted(year_counts.keys())
        visualizations.append(VisualizationData(
            chart_type="line",
            title="연도별 특허 출원 추이",
            data={
                "labels": sorted_years,
                "datasets": [{
                    "label": "특허 수",
                    "data": [year_counts[y] for y in sorted_years]
                }]
            },
            options={"xAxisLabel": "년도", "yAxisLabel": "특허 수"}
        ))
        
        # 3. IPC 분류별 분포 (바 차트)
        ipc_counts = {}
        for p in patents:
            for ipc in (p.ipc_codes or [])[:1]:  # 첫 번째 IPC만
                main_class = ipc[:4] if len(ipc) >= 4 else ipc
                ipc_counts[main_class] = ipc_counts.get(main_class, 0) + 1
        
        sorted_ipc = sorted(ipc_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        visualizations.append(VisualizationData(
            chart_type="bar",
            title="IPC 분류별 특허 분포 (Top 10)",
            data={
                "labels": [x[0] for x in sorted_ipc],
                "datasets": [{
                    "label": "특허 수",
                    "data": [x[1] for x in sorted_ipc]
                }]
            },
            options={"horizontal": True}
        ))
        
        return visualizations
    
    def _generate_comparison_visualizations(
        self,
        our_patents: List[PatentData],
        competitor_patents: List[PatentData],
        our_company: str,
        competitor: str
    ) -> List[VisualizationData]:
        """경쟁사 비교 시각화 생성"""
        visualizations = []
        
        # 1. 특허 수 비교 (바 차트)
        visualizations.append(VisualizationData(
            chart_type="bar",
            title="특허 수 비교",
            data={
                "labels": [our_company, competitor],
                "datasets": [{
                    "label": "특허 수",
                    "data": [len(our_patents), len(competitor_patents)]
                }]
            },
            options={"colors": ["#4CAF50", "#2196F3"]}
        ))
        
        # 2. 연도별 비교 (그룹 바 차트)
        our_years = {}
        comp_years = {}
        
        for p in our_patents:
            if p.application_date:
                year = p.application_date[:4]
                our_years[year] = our_years.get(year, 0) + 1
        
        for p in competitor_patents:
            if p.application_date:
                year = p.application_date[:4]
                comp_years[year] = comp_years.get(year, 0) + 1
        
        all_years = sorted(set(our_years.keys()) | set(comp_years.keys()))
        
        visualizations.append(VisualizationData(
            chart_type="bar",
            title="연도별 특허 출원 비교",
            data={
                "labels": all_years,
                "datasets": [
                    {
                        "label": our_company,
                        "data": [our_years.get(y, 0) for y in all_years]
                    },
                    {
                        "label": competitor,
                        "data": [comp_years.get(y, 0) for y in all_years]
                    }
                ]
            },
            options={"grouped": True}
        ))
        
        # 3. IPC 분류 비교 (레이더 차트)
        our_ipc = {}
        comp_ipc = {}
        
        for p in our_patents:
            for ipc in (p.ipc_codes or [])[:1]:
                main_class = ipc[:4] if len(ipc) >= 4 else ipc
                our_ipc[main_class] = our_ipc.get(main_class, 0) + 1
        
        for p in competitor_patents:
            for ipc in (p.ipc_codes or [])[:1]:
                main_class = ipc[:4] if len(ipc) >= 4 else ipc
                comp_ipc[main_class] = comp_ipc.get(main_class, 0) + 1
        
        all_ipc = list(set(our_ipc.keys()) | set(comp_ipc.keys()))[:8]
        
        visualizations.append(VisualizationData(
            chart_type="radar",
            title="기술 분야별 특허 비교",
            data={
                "labels": all_ipc,
                "datasets": [
                    {
                        "label": our_company,
                        "data": [our_ipc.get(ipc, 0) for ipc in all_ipc]
                    },
                    {
                        "label": competitor,
                        "data": [comp_ipc.get(ipc, 0) for ipc in all_ipc]
                    }
                ]
            },
            options={}
        ))
        
        return visualizations
    
    def _generate_trend_visualizations(
        self,
        patents: List[PatentData],
        time_range_years: int
    ) -> List[VisualizationData]:
        """트렌드 시각화 생성"""
        visualizations = []
        
        # 연도별 출원 추이
        year_counts = {}
        for p in patents:
            if p.application_date:
                year = p.application_date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1
        
        sorted_years = sorted(year_counts.keys())
        
        visualizations.append(VisualizationData(
            chart_type="line",
            title=f"최근 {time_range_years}년 특허 출원 트렌드",
            data={
                "labels": sorted_years,
                "datasets": [{
                    "label": "출원 수",
                    "data": [year_counts[y] for y in sorted_years],
                    "fill": True
                }]
            },
            options={"xAxisLabel": "년도", "yAxisLabel": "출원 수", "tension": 0.4}
        ))
        
        return visualizations
    
    def _generate_portfolio_visualizations(
        self,
        patents: List[PatentData],
        company: Optional[str]
    ) -> List[VisualizationData]:
        """포트폴리오 시각화 생성"""
        visualizations = []
        
        # 상태별 분포
        status_counts = {}
        for p in patents:
            status = p.status.value if p.status else "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        visualizations.append(VisualizationData(
            chart_type="pie",
            title=f"{company or '전체'} 특허 상태 분포",
            data={
                "labels": list(status_counts.keys()),
                "values": list(status_counts.values())
            },
            options={"showLegend": True}
        ))
        
        return visualizations
    
    def _generate_gap_visualizations(
        self,
        our_patents: List[PatentData],
        competitor_patents: List[PatentData],
        our_company: str,
        competitor: str
    ) -> List[VisualizationData]:
        """기술 공백 시각화 생성"""
        # 경쟁사 비교와 유사하지만 공백 강조
        return self._generate_comparison_visualizations(
            our_patents, competitor_patents, our_company, competitor
        )
    
    # =========================================================================
    # 요약 생성 메서드
    # =========================================================================
    
    async def _generate_search_summary(
        self,
        original_query: str,
        patents: List[PatentData],
        applicant: Optional[str],
        year_filter: Optional[str] = None
    ) -> str:
        """검색 결과 상세 요약 생성"""
        if not patents:
            no_result_msg = f"'{original_query}' 검색 결과, 관련 특허를 찾지 못했습니다."
            if applicant:
                no_result_msg += f"\n\n**참고:** {applicant}의 특허를 찾을 수 없습니다. 다른 검색어나 기간을 시도해 보세요."
            return no_result_msg
        
        # 기본 정보
        summary_parts = []
        
        # 헤더
        if applicant and year_filter:
            summary_parts.append(f"## 📊 {applicant} {year_filter}년 특허 분석 결과\n")
        elif applicant:
            summary_parts.append(f"## 📊 {applicant} 특허 분석 결과\n")
        else:
            summary_parts.append(f"## 📊 특허 검색 결과\n")
        
        # 검색 개요
        summary_parts.append(f"### 📋 검색 개요")
        summary_parts.append(f"- **총 검색 결과:** {len(patents)}건")
        if applicant:
            summary_parts.append(f"- **출원인:** {applicant}")
        if year_filter:
            summary_parts.append(f"- **분석 기간:** {year_filter}년")
        summary_parts.append("")
        
        # 연도별 분포 분석
        year_counts = {}
        for p in patents:
            if p.application_date:
                year = p.application_date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1
        
        if year_counts:
            summary_parts.append(f"### 📅 연도별 출원 현황")
            sorted_years = sorted(year_counts.items(), key=lambda x: x[0], reverse=True)
            for year, count in sorted_years[:5]:
                bar = "█" * min(count, 20)
                summary_parts.append(f"- **{year}년:** {count}건 {bar}")
            summary_parts.append("")
        
        # 기술 분류 (IPC) 분석
        ipc_counts = {}
        for p in patents:
            if p.ipc_codes:
                for ipc in p.ipc_codes[:2]:  # 상위 2개 IPC만
                    main_ipc = ipc[:4] if len(ipc) >= 4 else ipc
                    ipc_counts[main_ipc] = ipc_counts.get(main_ipc, 0) + 1
        
        if ipc_counts:
            summary_parts.append(f"### 🔬 주요 기술 분류 (IPC)")
            ipc_descriptions = self._get_ipc_descriptions()
            sorted_ipc = sorted(ipc_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            for ipc, count in sorted_ipc:
                desc = ipc_descriptions.get(ipc[:3], ipc_descriptions.get(ipc[:1], "기타"))
                summary_parts.append(f"- **{ipc}** ({desc}): {count}건")
            summary_parts.append("")
        
        # 대표 특허 목록
        summary_parts.append(f"### 📄 주요 특허 ({min(5, len(patents))}건)")
        for i, p in enumerate(patents[:5], 1):
            title = p.title[:60] + "..." if len(p.title) > 60 else p.title
            date_info = f", 출원일: {p.application_date}" if p.application_date else ""
            status = f" [{p.status}]" if p.status else ""
            summary_parts.append(f"{i}. **{title}**{status}")
            summary_parts.append(f"   - 출원번호: {p.patent_number}{date_info}")
        summary_parts.append("")
        
        # 분석 요약
        summary_parts.append(f"### 💡 분석 요약")
        
        # 출원 트렌드 분석
        if len(year_counts) >= 2:
            years = sorted(year_counts.keys())
            recent_years = years[-2:]
            if len(recent_years) == 2:
                older, newer = recent_years
                older_count = year_counts.get(older, 0)
                newer_count = year_counts.get(newer, 0)
                if newer_count > older_count:
                    growth = ((newer_count - older_count) / max(older_count, 1)) * 100
                    summary_parts.append(f"- 📈 **출원 증가 추세**: {older}년 대비 {newer}년 {growth:.0f}% 증가")
                elif newer_count < older_count:
                    decline = ((older_count - newer_count) / max(older_count, 1)) * 100
                    summary_parts.append(f"- 📉 **출원 감소 추세**: {older}년 대비 {newer}년 {decline:.0f}% 감소")
                else:
                    summary_parts.append(f"- ➡️ **출원 유지**: 안정적인 특허 출원 활동")
        
        # 기술 집중도
        if ipc_counts:
            top_ipc = sorted(ipc_counts.items(), key=lambda x: x[1], reverse=True)[0]
            concentration = (top_ipc[1] / len(patents)) * 100
            if concentration > 50:
                summary_parts.append(f"- 🎯 **기술 집중도 높음**: {top_ipc[0]} 분야에 {concentration:.0f}% 집중")
            else:
                summary_parts.append(f"- 🌐 **기술 다각화**: 다양한 기술 분야에 분산 출원")
        
        # 기본 요약 생성
        base_summary = "\n".join(summary_parts)
        
        # 🆕 LLM 기반 심층 분석 추가
        try:
            llm_analysis = await self._generate_llm_analysis(
                original_query=original_query,
                patents=patents,
                applicant=applicant,
                year_filter=year_filter,
                year_counts=year_counts,
                ipc_counts=ipc_counts
            )
            if llm_analysis:
                base_summary += f"\n\n{llm_analysis}"
        except Exception as e:
            logger.warning(f"⚠️ LLM 분석 생성 실패: {e}")
        
        return base_summary
    
    async def _generate_llm_analysis(
        self,
        original_query: str,
        patents: List[PatentData],
        applicant: Optional[str],
        year_filter: Optional[str],
        year_counts: Dict[str, int],
        ipc_counts: Dict[str, int]
    ) -> Optional[str]:
        """LLM을 사용한 심층 분석 생성"""
        if not patents or len(patents) < 3:
            return None
        
        try:
            # 시스템 프롬프트 로딩
            system_prompt = load_patent_analysis_prompt()
            
            # 특허 데이터 요약 (LLM 입력용)
            patent_summary = self._prepare_patents_for_llm(patents[:10])  # 상위 10건만
            
            # 분석 컨텍스트 구성
            context = f"""
## 분석 요청
{original_query}

## 특허 데이터 요약
- 총 특허 수: {len(patents)}건
- 출원인: {applicant or '전체'}
- 분석 기간: {year_filter or '전체 기간'}

## 연도별 출원 현황
{self._format_year_counts(year_counts)}

## 기술 분류 (IPC) 분포
{self._format_ipc_counts(ipc_counts)}

## 주요 특허 목록
{patent_summary}

위 데이터를 분석하여 다음을 제공해 주세요:
1. 기술 트렌드 분석 (2-3문장)
2. 핵심 인사이트 (3개)
3. 전략적 권고 (2-3개)
"""
            
            # LLM 호출
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
            
            response = await ai_service.chat_completion(
                messages=messages,
                max_tokens=1500,
                temperature=0.7
            )
            
            if response and response.get("response"):
                return f"### 🤖 AI 심층 분석\n\n{response['response']}"
            
        except Exception as e:
            logger.error(f"❌ LLM 분석 오류: {e}")
        
        return None
    
    def _prepare_patents_for_llm(self, patents: List[PatentData]) -> str:
        """LLM 입력용 특허 데이터 포맷팅"""
        lines = []
        for i, p in enumerate(patents, 1):
            title = p.title[:80] if p.title else "제목 없음"
            applicant = p.applicant or "출원인 미상"
            date = p.application_date or "날짜 미상"
            ipc = ", ".join(p.ipc_codes[:2]) if p.ipc_codes else "분류 미상"
            abstract = (p.abstract[:150] + "...") if p.abstract and len(p.abstract) > 150 else (p.abstract or "")
            
            lines.append(f"{i}. **{title}**")
            lines.append(f"   - 출원인: {applicant}, 출원일: {date}")
            lines.append(f"   - IPC: {ipc}")
            if abstract:
                lines.append(f"   - 요약: {abstract}")
        
        return "\n".join(lines)
    
    def _format_year_counts(self, year_counts: Dict[str, int]) -> str:
        """연도별 출원 수 포맷팅"""
        if not year_counts:
            return "데이터 없음"
        
        sorted_years = sorted(year_counts.items(), key=lambda x: x[0], reverse=True)
        return "\n".join([f"- {year}년: {count}건" for year, count in sorted_years[:5]])
    
    def _format_ipc_counts(self, ipc_counts: Dict[str, int]) -> str:
        """IPC 분포 포맷팅"""
        if not ipc_counts:
            return "데이터 없음"
        
        ipc_desc = self._get_ipc_descriptions()
        sorted_ipc = sorted(ipc_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        lines = []
        for ipc, count in sorted_ipc:
            desc = ipc_desc.get(ipc[:3], ipc_desc.get(ipc[:1], "기타"))
            lines.append(f"- {ipc} ({desc}): {count}건")
        return "\n".join(lines)
    
    def _get_ipc_descriptions(self) -> Dict[str, str]:
        """IPC 코드 설명"""
        return {
            "A": "생활필수품",
            "B": "처리조작/운수",
            "C": "화학/야금",
            "D": "섬유/제지",
            "E": "고정구조물",
            "F": "기계공학/조명/가열",
            "G": "물리학",
            "H": "전기",
            "G01": "측정/시험",
            "G02": "광학",
            "G06": "컴퓨팅/계산",
            "G09": "교육/암호",
            "H01": "전기소자",
            "H02": "전력생산/변환",
            "H04": "전기통신",
            "H05": "전기기술",
            "B60": "차량일반",
            "B62": "무궤도차량",
            "C07": "유기화학",
            "C08": "유기고분자화합물",
            "F16": "기계요소",
        }
    
    async def _generate_comparison_summary(
        self,
        query: str,
        our_company: str,
        competitor: str,
        our_patents: List[PatentData],
        competitor_patents: List[PatentData],
        analysis_result: Any
    ) -> str:
        """경쟁사 비교 요약 생성"""
        summary = f"**'{query}' 관련 특허 비교 분석**\n\n"
        summary += f"| 구분 | {our_company} | {competitor} |\n"
        summary += f"|------|--------|--------|\n"
        summary += f"| 특허 수 | {len(our_patents)}건 | {len(competitor_patents)}건 |\n"
        
        # 차이 분석
        diff = len(our_patents) - len(competitor_patents)
        if diff > 0:
            summary += f"\n✅ **{our_company}**가 {abs(diff)}건 더 많은 특허를 보유하고 있습니다.\n"
        elif diff < 0:
            summary += f"\n⚠️ **{competitor}**가 {abs(diff)}건 더 많은 특허를 보유하고 있습니다.\n"
        else:
            summary += f"\n🔄 양사의 특허 수가 동일합니다.\n"
        
        return summary
    
    async def _generate_trend_summary(
        self,
        query: str,
        patents: List[PatentData],
        time_range_years: int,
        analysis_result: Any
    ) -> str:
        """트렌드 분석 요약 생성"""
        summary = f"**'{query}' 최근 {time_range_years}년 특허 트렌드**\n\n"
        summary += f"- 분석 대상: **{len(patents)}건**\n"
        
        # 연도별 통계
        year_counts = {}
        for p in patents:
            if p.application_date:
                year = p.application_date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1
        
        if year_counts:
            max_year = max(year_counts.items(), key=lambda x: x[1])
            min_year = min(year_counts.items(), key=lambda x: x[1])
            summary += f"- 최다 출원 연도: {max_year[0]} ({max_year[1]}건)\n"
            summary += f"- 최소 출원 연도: {min_year[0]} ({min_year[1]}건)\n"
            
            # 트렌드 방향
            years = sorted(year_counts.keys())
            if len(years) >= 2:
                recent = year_counts.get(years[-1], 0)
                older = year_counts.get(years[-2], 0)
                if recent > older:
                    summary += f"\n📈 출원 트렌드: **상승세** (전년 대비 +{recent - older}건)\n"
                elif recent < older:
                    summary += f"\n📉 출원 트렌드: **하락세** (전년 대비 {recent - older}건)\n"
                else:
                    summary += f"\n➡️ 출원 트렌드: **유지**\n"
        
        return summary
    
    async def _generate_portfolio_summary(
        self,
        query: str,
        company: Optional[str],
        patents: List[PatentData],
        portfolio_result: Any,
        topic_result: Any
    ) -> str:
        """포트폴리오 분석 요약 생성"""
        summary = f"**{company or '전체'} 특허 포트폴리오 분석**\n\n"
        summary += f"- 총 특허: **{len(patents)}건**\n"
        
        # 상태별 분포
        status_counts = {}
        for p in patents:
            status = p.status.value if p.status else "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        summary += f"- 등록 특허: {status_counts.get('granted', 0)}건\n"
        summary += f"- 출원 중: {status_counts.get('application', 0)}건\n"
        summary += f"- 공개: {status_counts.get('published', 0)}건\n"
        
        return summary
    
    async def _generate_gap_summary(
        self,
        query: str,
        our_company: str,
        competitor: str,
        analysis_result: Any
    ) -> str:
        """기술 공백 분석 요약 생성"""
        summary = f"**'{query}' 기술 공백 분석**\n\n"
        summary += f"- 비교 대상: **{our_company}** vs **{competitor}**\n\n"
        
        if hasattr(analysis_result, 'data') and analysis_result.data:
            gaps = analysis_result.data.get('gaps', [])
            if gaps:
                summary += "**우리가 보완해야 할 기술 분야:**\n"
                for gap in gaps[:5]:
                    summary += f"- {gap.get('area', 'N/A')}: {gap.get('description', '')}\n"
        
        return summary
    
    # =========================================================================
    # 인사이트 추출 메서드
    # =========================================================================
    
    def _extract_search_insights(self, patents: List[PatentData], applicant: Optional[str] = None) -> List[str]:
        """검색 결과 인사이트 추출"""
        insights = []
        
        if not patents:
            return ["검색 결과가 없습니다. 다른 검색어나 기간을 시도해 보세요."]
        
        # 1. 출원 활동 분석
        year_counts = {}
        for p in patents:
            if p.application_date:
                year = p.application_date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1
        
        if year_counts:
            sorted_years = sorted(year_counts.keys())
            if len(sorted_years) >= 2:
                recent = sorted_years[-1]
                prev = sorted_years[-2]
                recent_count = year_counts[recent]
                prev_count = year_counts[prev]
                
                if recent_count > prev_count * 1.2:
                    insights.append(f"📈 {recent}년 출원이 전년 대비 증가하여 R&D 활동이 활발해지고 있습니다.")
                elif recent_count < prev_count * 0.8:
                    insights.append(f"📉 {recent}년 출원이 전년 대비 감소하여 해당 분야 투자가 줄어들 수 있습니다.")
        
        # 2. 기술 집중도 분석
        ipc_counts = {}
        for p in patents:
            if p.ipc_codes:
                for ipc in p.ipc_codes[:1]:
                    main_ipc = ipc[:4] if len(ipc) >= 4 else ipc
                    ipc_counts[main_ipc] = ipc_counts.get(main_ipc, 0) + 1
        
        if ipc_counts:
            top_ipc = max(ipc_counts.items(), key=lambda x: x[1])
            concentration = (top_ipc[1] / len(patents)) * 100
            ipc_desc = self._get_ipc_descriptions()
            desc = ipc_desc.get(top_ipc[0][:3], ipc_desc.get(top_ipc[0][:1], "기술"))
            
            if concentration > 50:
                insights.append(f"🎯 {desc} 분야({top_ipc[0]})에 {concentration:.0f}%가 집중되어 핵심 기술 영역으로 보입니다.")
            elif concentration > 30:
                insights.append(f"⚡ {desc} 분야({top_ipc[0]})가 주력이나, 다른 기술 분야로도 확장 중입니다.")
        
        # 3. 최근 특허 동향
        current_year = str(datetime.now().year)
        recent_patents = [p for p in patents if p.application_date and p.application_date[:4] >= str(int(current_year) - 1)]
        if recent_patents:
            insights.append(f"🔥 최근 2년 내 {len(recent_patents)}건의 활발한 출원으로 지속적인 기술 개발이 진행 중입니다.")
        
        # 4. 출원인 분석 (특정 출원인 검색이 아닌 경우)
        if not applicant:
            applicant_counts = {}
            for p in patents:
                app = p.applicant or "Unknown"
                applicant_counts[app] = applicant_counts.get(app, 0) + 1
            
            if applicant_counts:
                top_app = max(applicant_counts.items(), key=lambda x: x[1])
                if top_app[1] > len(patents) * 0.3:
                    insights.append(f"👑 {top_app[0]}이(가) 해당 분야에서 {top_app[1]}건({top_app[1]/len(patents)*100:.0f}%)으로 선도적 위치입니다.")
        
        # 5. 특허 상태 분석
        status_counts = {}
        for p in patents:
            status = p.status or "Unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if "등록" in status_counts:
            registered = status_counts["등록"]
            if registered > len(patents) * 0.5:
                insights.append(f"✅ 등록 특허가 {registered}건({registered/len(patents)*100:.0f}%)으로 기술력이 인정받고 있습니다.")
        
        if "공개" in status_counts:
            published = status_counts["공개"]
            if published > len(patents) * 0.3:
                insights.append(f"📝 공개 특허가 {published}건으로 향후 등록 가능성이 있는 기술들이 많습니다.")
        
        # 인사이트가 없으면 기본 메시지
        if not insights:
            insights.append(f"📊 총 {len(patents)}건의 특허가 검색되었습니다. 상세 분석이 필요합니다.")
        
        return insights
    
    def _extract_comparison_insights(
        self,
        our_patents: List[PatentData],
        competitor_patents: List[PatentData],
        our_company: str,
        competitor: str
    ) -> List[str]:
        """경쟁사 비교 인사이트 추출"""
        insights = []
        
        # 양적 비교
        if len(our_patents) > len(competitor_patents) * 1.5:
            insights.append(f"{our_company}가 양적으로 우위 (1.5배 이상)")
        elif len(competitor_patents) > len(our_patents) * 1.5:
            insights.append(f"{competitor}가 양적으로 우위 - 특허 확보 전략 검토 필요")
        
        # IPC 다양성
        our_ipc = set()
        comp_ipc = set()
        for p in our_patents:
            our_ipc.update(p.ipc_codes or [])
        for p in competitor_patents:
            comp_ipc.update(p.ipc_codes or [])
        
        if len(our_ipc) > len(comp_ipc) * 1.3:
            insights.append(f"{our_company}가 더 다양한 기술 분야에 진출")
        elif len(comp_ipc) > len(our_ipc) * 1.3:
            insights.append(f"{competitor}가 더 다양한 기술 분야 보유 - 기술 다각화 검토 필요")
        
        return insights
    
    def _extract_trend_insights(
        self,
        patents: List[PatentData],
        time_range_years: int
    ) -> List[str]:
        """트렌드 인사이트 추출"""
        insights = []
        
        year_counts = {}
        for p in patents:
            if p.application_date:
                year = p.application_date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1
        
        if year_counts:
            years = sorted(year_counts.keys())
            if len(years) >= 3:
                recent_avg = sum(year_counts.get(y, 0) for y in years[-2:]) / 2
                older_avg = sum(year_counts.get(y, 0) for y in years[:-2]) / max(len(years) - 2, 1)
                
                if recent_avg > older_avg * 1.5:
                    insights.append("최근 2년간 출원이 급증 - 해당 분야 기술 경쟁 심화")
                elif recent_avg < older_avg * 0.5:
                    insights.append("최근 출원 감소 - 기술 성숙기 또는 시장 침체 가능성")
        
        return insights
    
    def _extract_portfolio_insights(
        self,
        patents: List[PatentData],
        company: Optional[str]
    ) -> List[str]:
        """포트폴리오 인사이트 추출"""
        insights = []
        
        # 등록률
        granted = sum(1 for p in patents if p.status == PatentStatus.GRANTED)
        if patents:
            grant_rate = granted / len(patents) * 100
            if grant_rate > 70:
                insights.append(f"높은 등록률 ({grant_rate:.0f}%) - 우수한 특허 품질")
            elif grant_rate < 30:
                insights.append(f"낮은 등록률 ({grant_rate:.0f}%) - 특허 전략 재검토 필요")
        
        return insights
    
    def _extract_gap_insights(self, analysis_result: Any) -> List[str]:
        """기술 공백 인사이트 추출"""
        insights = []
        
        if hasattr(analysis_result, 'data') and analysis_result.data:
            gaps = analysis_result.data.get('gaps', [])
            if gaps:
                insights.append(f"총 {len(gaps)}개 기술 분야에서 공백 발견")
        
        return insights
    
    def _generate_comparison_recommendations(self, analysis_result: Any) -> List[str]:
        """경쟁사 비교 권장사항 생성"""
        recommendations = []
        recommendations.append("경쟁사 핵심 특허에 대한 회피 설계 검토")
        recommendations.append("특허 인용 네트워크 분석을 통한 핵심 기술 파악")
        return recommendations
    
    def _generate_gap_recommendations(self, analysis_result: Any) -> List[str]:
        """기술 공백 권장사항 생성"""
        recommendations = []
        recommendations.append("식별된 기술 공백 분야에 대한 R&D 투자 검토")
        recommendations.append("기술 라이선싱 또는 M&A를 통한 빠른 기술 확보 고려")
        return recommendations


# =============================================================================
# Singleton Instance
# =============================================================================

patent_analysis_agent_tool = PatentAnalysisAgentTool()


__all__ = ["PatentAnalysisAgentTool", "patent_analysis_agent_tool"]

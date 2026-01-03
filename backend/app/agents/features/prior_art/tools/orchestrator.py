"""Prior Art Orchestrator - 선행기술조사 전체 흐름 제어

책임:
- PatentAnalysisTool, PriorArtSearchTool, PriorArtReportTool 조율
- 단계별 실행 및 데이터 전달
- (API 라우터에서 호출하기 쉽도록 파사드 역할)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agents.features.prior_art.tools.patent_analysis_tool import patent_analysis_tool
from app.agents.features.prior_art.tools.search_tool import prior_art_search_tool
from app.agents.features.prior_art.tools.report_tool import prior_art_report_tool
from app.agents.features.prior_art.tools.screening_tool import prior_art_screening_tool


class PriorArtOrchestrator:
    """
    선행기술조사 오케스트레이터 (Facade)
    
    API 라우터는 이 클래스(또는 모듈 함수)를 통해
    각 단계(Analysis -> Search -> Report)를 순차적으로 호출하거나,
    필요한 경우 개별 Tool을 직접 호출할 수도 있음.
    """
    
    def __init__(self):
        self.analysis_tool = patent_analysis_tool
        self.search_tool = prior_art_search_tool
        self.screening_tool = prior_art_screening_tool
        self.report_tool = prior_art_report_tool

    # 각 단계별 메서드를 노출하여 API 라우터가 SSE 이벤트를 사이사이에 넣을 수 있게 함

    async def analyze_input(
        self,
        attached_document_context: Optional[str],
        rewritten_query: Optional[str],
        fallback_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """1단계: 입력 분석"""
        text_to_analyze = (attached_document_context or "").strip()
        fallback = (rewritten_query or "")
        if fallback_keywords:
            fallback += " " + " ".join(fallback_keywords)
            
        return await self.analysis_tool.analyze(
            text=text_to_analyze,
            fallback_query=fallback
        )

    def plan_search(
        self,
        analysis_result: Dict[str, Any],
        base_query: Optional[str] = None,
    ) -> List[Any]: # List[Tuple[str, str]]
        """2단계: 검색 전략 수립"""
        keywords = analysis_result.get("keywords", [])
        return self.search_tool.generate_queries(
            keywords=keywords,
            base_query=base_query
        )

    async def execute_search_step(
        self,
        label: str,
        query: str,
        *,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        max_results: int = 20,
    ) -> Dict[str, Any]:
        """3단계: 개별 검색 실행 (SSE 진행률 표시용)"""
        patents, total = await self.search_tool.execute_search(
            query=query,
            applicant=applicant,
            ipc_code=ipc_code,
            date_from=date_from,
            max_results=max_results,
        )
        return {
            "label": label,
            "query": query,
            "patents": patents,
            "total_found": total,
            "returned": len(patents)
        }

    def screen_results(
        self,
        all_results: List[Any],
        *,
        target_keywords: Optional[List[str]] = None,
        min_relevance_score: Optional[int] = None,
        max_candidates: Optional[int] = None,
    ) -> tuple[list[Any], dict[str, int]]:
        """4단계: 결과 스크리닝(중복 제거/컷오프/정렬)"""
        return self.screening_tool.screen_and_rank(
            candidates=all_results,
            target_keywords=target_keywords,
            min_relevance_score=min_relevance_score,
            max_candidates=max_candidates,
        )

    def create_report_content(
        self,
        session_id: Optional[str],
        user_message: str,
        document_ids: Optional[List[str]],
        analysis_result: Dict[str, Any],
        search_metadata: Dict[str, Any],
        unique_patents: List[Any],
    ) -> Dict[str, str]:
        """5단계: 리포트 생성"""
        return self.report_tool.build_report(
            session_id=session_id,
            user_message=user_message,
            document_ids=document_ids,
            analysis_result=analysis_result,
            search_metadata=search_metadata,
            unique_patents=unique_patents
        )

    async def save_final_report(
        self,
        chat_attachment_service,
        owner_emp_no: str,
        report_md: str,
        report_filename: str,
    ):
        """6단계: 리포트 저장"""
        return await self.report_tool.save_report(
            chat_attachment_service=chat_attachment_service,
            owner_emp_no=owner_emp_no,
            report_md=report_md,
            report_filename=report_filename
        )


prior_art_orchestrator = PriorArtOrchestrator()

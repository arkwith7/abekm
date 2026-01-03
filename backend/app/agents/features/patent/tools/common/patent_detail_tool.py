"""
Patent Detail Tool - 특허 상세 조회 도구

단일 특허의 상세 정보를 조회합니다.
출원번호/등록번호로 서지정보, 청구항, 발명자 등을 조회합니다.
"""
from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agents.features.patent.core import (
    PatentData,
    PatentJurisdiction,
)
from app.agents.features.patent.clients import PatentSourceAggregator
from app.core.contracts import ToolResult


# =============================================================================
# Input/Output Models
# =============================================================================

class PatentDetailInput(BaseModel):
    """특허 상세 조회 입력"""
    patent_number: str = Field(description="특허번호 (출원번호 또는 등록번호)")
    jurisdiction: str = Field(
        default="KR",
        description="관할권 (KR, US, EP, WO, JP, CN)"
    )
    include_claims: bool = Field(
        default=True,
        description="청구항 포함 여부"
    )
    include_citations: bool = Field(
        default=True,
        description="인용 정보 포함 여부"
    )


class PatentDetailOutput(ToolResult):
    """특허 상세 조회 출력"""
    patent: Optional[PatentData] = Field(default=None, description="특허 데이터")
    found: bool = Field(default=False, description="조회 성공 여부")


# =============================================================================
# Tool Implementation
# =============================================================================

class PatentDetailTool(BaseTool):
    """
    특허 상세 조회 도구
    
    특허번호로 상세 정보를 조회합니다.
    - 서지정보 (제목, 출원인, 발명자, 날짜)
    - IPC/CPC 분류
    - 청구항 (선택)
    - 인용 정보 (선택)
    """
    
    name: str = "patent_detail"
    description: str = """특허번호로 특허의 상세 정보를 조회합니다.

입력:
- patent_number: 특허번호 (출원번호 또는 등록번호)
- jurisdiction: 관할권 (기본: KR)
- include_claims: 청구항 포함 여부 (기본: true)
- include_citations: 인용 정보 포함 여부 (기본: true)

출력:
- 특허 서지정보, IPC 분류, 청구항, 인용 정보 등"""
    
    args_schema: type[BaseModel] = PatentDetailInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._aggregator = PatentSourceAggregator()
    
    @property
    def aggregator(self) -> PatentSourceAggregator:
        return self._aggregator
    
    def _run(
        self,
        patent_number: str,
        jurisdiction: str = "KR",
        include_claims: bool = True,
        include_citations: bool = True,
    ) -> str:
        """동기 실행"""
        return asyncio.run(
            self._arun(
                patent_number=patent_number,
                jurisdiction=jurisdiction,
                include_claims=include_claims,
                include_citations=include_citations,
            )
        )
    
    async def _arun(
        self,
        patent_number: str,
        jurisdiction: str = "KR",
        include_claims: bool = True,
        include_citations: bool = True,
    ) -> str:
        """비동기 실행"""
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"🔍 [PatentDetail] 조회 시작: {patent_number} ({jurisdiction})")
            
            # 관할권 결정
            try:
                patent_jurisdiction = PatentJurisdiction(jurisdiction.upper())
            except ValueError:
                patent_jurisdiction = PatentJurisdiction.KR
            
            # 적절한 클라이언트 선택
            client = self._select_client(patent_jurisdiction)
            
            if not client:
                return f"❌ {jurisdiction} 관할권을 지원하는 데이터 소스가 없습니다."
            
            # 특허 상세 조회
            patent = await client.get_detail(patent_number)
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if not patent:
                logger.warning(f"⚠️ [PatentDetail] 특허를 찾을 수 없음: {patent_number}")
                return f"특허 '{patent_number}'을(를) 찾을 수 없습니다."
            
            # 결과 포맷팅
            result = self._format_result(
                patent=patent,
                include_claims=include_claims,
                include_citations=include_citations,
                elapsed_ms=elapsed_ms,
            )
            
            logger.info(f"✅ [PatentDetail] 조회 완료: {patent_number}, time={elapsed_ms:.0f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [PatentDetail] 조회 실패: {e}")
            return f"조회 중 오류가 발생했습니다: {str(e)}"
    
    def _select_client(self, jurisdiction: PatentJurisdiction):
        """관할권에 맞는 클라이언트 선택"""
        for source_name in self.aggregator.list_available_sources():
            client = self.aggregator.get_client(source_name)
            if client and jurisdiction.value in client.supported_jurisdictions:
                return client
        return None
    
    def _format_result(
        self,
        patent: PatentData,
        include_claims: bool,
        include_citations: bool,
        elapsed_ms: float,
    ) -> str:
        """결과 포맷팅"""
        lines = [
            f"## 📄 {patent.title}",
            f"",
            f"### 기본 정보",
            f"- **특허번호**: {patent.patent_number}",
            f"- **출원인**: {patent.applicant}",
            f"- **발명자**: {', '.join(patent.inventors) if patent.inventors else 'N/A'}",
            f"- **출원일**: {patent.application_date or 'N/A'}",
            f"- **등록일**: {patent.grant_date or 'N/A'}",
            f"- **상태**: {patent.status.value}",
            f"- **관할권**: {patent.jurisdiction.value}",
        ]
        
        # IPC 코드
        if patent.ipc_codes:
            lines.append(f"")
            lines.append(f"### IPC 분류")
            for ipc in patent.ipc_codes[:5]:
                lines.append(f"- {ipc}")
        
        # 초록
        if patent.abstract:
            lines.append(f"")
            lines.append(f"### 초록")
            lines.append(patent.abstract[:500] + ("..." if len(patent.abstract) > 500 else ""))
        
        # 청구항
        if include_claims and patent.claims:
            lines.append(f"")
            lines.append(f"### 청구항 ({patent.claims_count or len(patent.claims)}건)")
            for i, claim in enumerate(patent.claims[:3], 1):
                claim_text = claim[:300] + ("..." if len(claim) > 300 else "")
                lines.append(f"**청구항 {i}**: {claim_text}")
        
        # 인용 정보
        if include_citations and patent.citations:
            lines.append(f"")
            lines.append(f"### 인용 특허 ({len(patent.citations)}건)")
            for citation in patent.citations[:5]:
                lines.append(f"- {citation}")
        
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"_조회 시간: {elapsed_ms:.0f}ms_")
        
        return "\n".join(lines)


# 도구 인스턴스
patent_detail_tool = PatentDetailTool()

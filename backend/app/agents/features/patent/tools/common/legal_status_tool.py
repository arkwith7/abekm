"""
Legal Status Tool - 특허 법적 상태 조회 도구

특허의 법적 상태(유효/만료/포기 등)를 조회합니다.
등록료 납부, 존속기간, 권리범위 변동 등을 확인합니다.
"""
from __future__ import annotations

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agents.features.patent.core import (
    PatentData,
    PatentJurisdiction,
    PatentStatus,
    LegalStatus,
)
from app.agents.features.patent.clients import PatentSourceAggregator
from app.core.contracts import ToolResult


# =============================================================================
# Input/Output Models
# =============================================================================

class LegalStatusInput(BaseModel):
    """법적 상태 조회 입력"""
    patent_number: str = Field(description="특허번호 (등록번호)")
    jurisdiction: str = Field(
        default="KR",
        description="관할권 (KR, US, EP, WO, JP, CN)"
    )


class LegalStatusOutput(ToolResult):
    """법적 상태 조회 출력"""
    status: Optional[LegalStatus] = Field(default=None, description="법적 상태")
    found: bool = Field(default=False, description="조회 성공 여부")


# =============================================================================
# Tool Implementation
# =============================================================================

class LegalStatusTool(BaseTool):
    """
    특허 법적 상태 조회 도구
    
    특허의 현재 법적 상태를 조회합니다:
    - 권리 상태 (유효/만료/포기/무효)
    - 존속기간 및 잔여 기간
    - 등록료 납부 상태
    - 최근 심판/심사 이력
    """
    
    name: str = "legal_status"
    description: str = """특허의 법적 상태를 조회합니다.

입력:
- patent_number: 특허번호 (등록번호)
- jurisdiction: 관할권 (기본: KR)

출력:
- 권리 상태 (유효/만료/포기/무효)
- 존속기간 정보
- 등록료 납부 상태
- 권리 변동 이력"""
    
    args_schema: type[BaseModel] = LegalStatusInput
    
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
    ) -> str:
        """동기 실행"""
        return asyncio.run(
            self._arun(
                patent_number=patent_number,
                jurisdiction=jurisdiction,
            )
        )
    
    async def _arun(
        self,
        patent_number: str,
        jurisdiction: str = "KR",
    ) -> str:
        """비동기 실행"""
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"📋 [LegalStatus] 조회 시작: {patent_number} ({jurisdiction})")
            
            # 관할권 결정
            try:
                patent_jurisdiction = PatentJurisdiction(jurisdiction.upper())
            except ValueError:
                patent_jurisdiction = PatentJurisdiction.KR
            
            # 적절한 클라이언트 선택
            client = self._select_client(patent_jurisdiction)
            
            if not client:
                return f"❌ {jurisdiction} 관할권을 지원하는 데이터 소스가 없습니다."
            
            # 법적 상태 조회
            legal_status = await client.get_legal_status(patent_number)
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if not legal_status:
                logger.warning(f"⚠️ [LegalStatus] 법적 상태를 찾을 수 없음: {patent_number}")
                return f"특허 '{patent_number}'의 법적 상태를 찾을 수 없습니다."
            
            # 결과 포맷팅
            result = self._format_result(
                legal_status=legal_status,
                patent_number=patent_number,
                jurisdiction=jurisdiction,
                elapsed_ms=elapsed_ms,
            )
            
            logger.info(f"✅ [LegalStatus] 조회 완료: {patent_number}, status={legal_status.current_status.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [LegalStatus] 조회 실패: {e}")
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
        legal_status: LegalStatus,
        patent_number: str,
        jurisdiction: str,
        elapsed_ms: float,
    ) -> str:
        """결과 포맷팅"""
        # 상태 이모지 결정
        status_emoji = {
            PatentStatus.GRANTED: "✅",
            PatentStatus.EXPIRED: "⏰",
            PatentStatus.WITHDRAWN: "❌",
            PatentStatus.APPLICATION: "📝",
            PatentStatus.PUBLISHED: "📄",
            PatentStatus.REJECTED: "🚫",
            PatentStatus.ABANDONED: "🗑️",
        }.get(legal_status.current_status, "❓")
        
        lines = [
            f"## {status_emoji} 특허 법적 상태: {patent_number}",
            f"",
            f"### 기본 정보",
            f"- **현재 상태**: {legal_status.current_status.value}",
            f"- **상태 기준일**: {legal_status.status_date or 'N/A'}",
            f"- **관할권**: {jurisdiction}",
        ]
        
        # 존속기간 정보
        if legal_status.remaining_term is not None:
            lines.append(f"")
            lines.append(f"### 존속기간")
            if legal_status.remaining_term > 0:
                lines.append(f"- **잔여 존속기간**: {legal_status.remaining_term}년")
                lines.append(f"- **만료 예정일**: {legal_status.expiration_date or 'N/A'}")
            else:
                lines.append(f"- ⚠️ **존속기간 만료**")
                lines.append(f"- **만료일**: {legal_status.expiration_date or 'N/A'}")
        
        # 등록료 정보
        if legal_status.fee_status:
            lines.append(f"")
            lines.append(f"### 등록료 상태")
            lines.append(f"- {legal_status.fee_status}")
        
        # 권리 변동 이력
        if legal_status.events and len(legal_status.events) > 0:
            lines.append(f"")
            lines.append(f"### 최근 권리 변동 ({len(legal_status.events)}건)")
            for event in legal_status.events[:5]:
                date = event.get("date", "")
                description = event.get("description", "")
                lines.append(f"- [{date}] {description}")
        
        # 권리 상태 요약
        lines.append(f"")
        lines.append(f"### 권리 상태 요약")
        if legal_status.current_status == PatentStatus.GRANTED:
            if legal_status.remaining_term and legal_status.remaining_term > 0:
                lines.append(f"✅ **유효한 권리**: 잔여 {legal_status.remaining_term}년")
            else:
                lines.append(f"⏰ **만료 임박 또는 만료**")
        elif legal_status.current_status == PatentStatus.EXPIRED:
            lines.append(f"⏰ **권리 만료**: 존속기간 종료")
        elif legal_status.current_status == PatentStatus.WITHDRAWN:
            lines.append(f"❌ **권리 포기**: 출원인 의사에 의한 포기")
        elif legal_status.current_status == PatentStatus.APPLICATION:
            lines.append(f"📝 **출원 중**: 심사 진행 중")
        else:
            lines.append(f"상태: {legal_status.current_status.value}")
        
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"_조회 시간: {elapsed_ms:.0f}ms_")
        
        return "\n".join(lines)


# 도구 인스턴스
legal_status_tool = LegalStatusTool()

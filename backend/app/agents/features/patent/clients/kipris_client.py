"""
KIPRIS Client Adapter - KIPRIS+ API 클라이언트

BasePatentClient 인터페이스를 구현하는 KIPRIS 어댑터.
기존 app.clients.kipris.KiprisClient를 래핑하여 통합 인터페이스 제공.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from ..core.interfaces import BasePatentClient
from ..core.models import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    LegalStatus,
    PatentCitation,
    PatentStatus,
    PatentJurisdiction,
)

# 기존 KIPRIS 클라이언트 import
from app.clients.kipris import (
    KiprisClient as LegacyKiprisClient,
    KiprisPatentBasic,
    KiprisPatentDetail,
    KiprisLegalStatus,
)
from app.core.config import settings


class KiprisPatentClient(BasePatentClient):
    """
    KIPRIS+ API 클라이언트
    
    한국특허정보원(KIPRIS) Open API를 통한 한국 특허 검색/조회.
    BasePatentClient 인터페이스를 구현하여 다른 데이터 소스와 통합 사용 가능.
    
    Features:
        - 특허/실용신안 검색
        - 서지 정보 조회
        - 청구항 조회
        - 법적 상태 조회
        - 패밀리 정보 조회
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: KIPRIS API 키 (None이면 설정에서 가져옴)
        """
        self._api_key = api_key or getattr(settings, 'kipris_api_key', None)
        self._legacy_client = LegacyKiprisClient(api_key=self._api_key)
    
    @property
    def source_name(self) -> str:
        return "KIPRIS"
    
    @property
    def supported_jurisdictions(self) -> List[str]:
        return ["KR"]
    
    @property
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    # =========================================================================
    # Search
    # =========================================================================
    
    async def search(self, query: PatentSearchQuery) -> SearchResult:
        """
        특허 검색
        
        Args:
            query: 검색 쿼리
            
        Returns:
            SearchResult: 검색 결과
        """
        start_time = datetime.utcnow()
        
        try:
            # Legacy 클라이언트 호출
            patents_basic, total_count = await self._legacy_client.search_patents(
                query=query.query,
                applicant=query.applicant,
                ipc_code=query.ipc_code,
                date_from=query.date_from,
                date_to=query.date_to,
                max_results=query.max_results,
            )
            
            # PatentData로 변환
            patents = [
                self._convert_basic_to_patent_data(p)
                for p in patents_basic
            ]
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"✅ [KIPRIS] 검색 완료: query='{query.query[:30]}...', "
                f"results={len(patents)}/{total_count}, time={elapsed_ms:.0f}ms"
            )
            
            return SearchResult(
                patents=patents,
                total_count=total_count,
                returned_count=len(patents),
                query=query,
                source=self.source_name,
                search_time_ms=elapsed_ms,
            )
            
        except Exception as e:
            logger.error(f"❌ [KIPRIS] 검색 실패: {e}")
            return SearchResult(
                patents=[],
                total_count=0,
                returned_count=0,
                query=query,
                source=self.source_name,
                search_time_ms=0,
            )
    
    # =========================================================================
    # Detail
    # =========================================================================
    
    async def get_detail(self, patent_number: str) -> Optional[PatentData]:
        """
        특허 상세 정보 조회
        
        Args:
            patent_number: 특허번호 (출원번호)
            
        Returns:
            Optional[PatentData]: 특허 상세 정보
        """
        try:
            detail = await self._legacy_client.get_biblio_detail(patent_number)
            
            if detail:
                return self._convert_detail_to_patent_data(detail)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ [KIPRIS] 상세 조회 실패: {patent_number}, {e}")
            return None
    
    # =========================================================================
    # Citations
    # =========================================================================
    
    async def get_citations(self, patent_number: str) -> List[PatentCitation]:
        """
        인용 특허 조회
        
        현재 KIPRIS API에서 직접 지원하지 않음.
        향후 구현 예정.
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[PatentCitation]: 인용 목록 (현재 빈 리스트)
        """
        # TODO: KIPRIS 인용 정보 API 확인 및 구현
        logger.warning(f"⚠️ [KIPRIS] 인용 조회 미구현: {patent_number}")
        return []
    
    # =========================================================================
    # Legal Status
    # =========================================================================
    
    async def get_legal_status(self, patent_number: str) -> Optional[LegalStatus]:
        """
        법적 상태 조회
        
        Args:
            patent_number: 특허번호
            
        Returns:
            Optional[LegalStatus]: 법적 상태 정보
        """
        try:
            status = await self._legacy_client.get_legal_status(patent_number)
            
            if status:
                return self._convert_legal_status(status)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ [KIPRIS] 법적 상태 조회 실패: {patent_number}, {e}")
            return None
    
    # =========================================================================
    # Additional KIPRIS-specific methods
    # =========================================================================
    
    async def search_by_applicant_code(
        self,
        applicant_name: str,
        max_results: int = 50,
    ) -> SearchResult:
        """
        출원인 코드를 이용한 정확한 검색
        
        KIPRIS는 출원인 코드(특허고객번호)를 사용하면 더 정확한 검색이 가능합니다.
        
        Args:
            applicant_name: 출원인명
            max_results: 최대 결과 수
            
        Returns:
            SearchResult: 검색 결과
        """
        # 먼저 출원인 코드 조회
        customer_no = await self._legacy_client.search_applicant_code(applicant_name)
        
        if customer_no:
            logger.info(f"🔍 [KIPRIS] 출원인 코드 발견: {applicant_name} -> {customer_no}")
        
        # 검색 실행
        patents_basic, total_count = await self._legacy_client.search_patents(
            query="",
            applicant=applicant_name,
            max_results=max_results,
            customer_no=customer_no,
        )
        
        patents = [
            self._convert_basic_to_patent_data(p)
            for p in patents_basic
        ]
        
        return SearchResult(
            patents=patents,
            total_count=total_count,
            returned_count=len(patents),
            source=self.source_name,
        )
    
    async def get_family_patents(self, patent_number: str) -> List[str]:
        """
        패밀리 특허 조회
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[str]: 패밀리 특허번호 목록
        """
        try:
            family_info = await self._legacy_client.get_family_info(patent_number)
            
            if family_info:
                return [
                    p.get("applicationNumber", "")
                    for p in family_info.family_patents
                    if p.get("applicationNumber")
                ]
            
            return []
            
        except Exception as e:
            logger.error(f"❌ [KIPRIS] 패밀리 조회 실패: {patent_number}, {e}")
            return []
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """API 상태 확인"""
        base_health = await super().health_check()
        
        # 간단한 테스트 검색으로 API 상태 확인
        if self.is_available:
            try:
                test_query = PatentSearchQuery(
                    query="AI",
                    max_results=1,
                )
                result = await self.search(test_query)
                base_health["api_responsive"] = result.total_count >= 0
            except Exception:
                base_health["api_responsive"] = False
        else:
            base_health["api_responsive"] = False
        
        return base_health
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    async def close(self):
        """클라이언트 리소스 정리"""
        await self._legacy_client.close()
    
    # =========================================================================
    # Converters
    # =========================================================================
    
    def _convert_basic_to_patent_data(self, basic: KiprisPatentBasic) -> PatentData:
        """KiprisPatentBasic -> PatentData 변환"""
        return PatentData(
            patent_number=basic.application_number,
            title=basic.title,
            abstract=basic.abstract,
            applicant=basic.applicant,
            ipc_codes=basic.ipc_all or ([basic.ipc_code] if basic.ipc_code else []),
            application_date=basic.application_date,
            publication_date=basic.open_date,
            grant_date=basic.register_date,
            status=self._map_status(basic.status),
            jurisdiction=PatentJurisdiction.KR,
            source=self.source_name,
            retrieved_at=datetime.utcnow(),
        )
    
    def _convert_detail_to_patent_data(self, detail: KiprisPatentDetail) -> PatentData:
        """KiprisPatentDetail -> PatentData 변환"""
        return PatentData(
            patent_number=detail.application_number,
            title=detail.title,
            abstract="",  # Detail에는 초록이 없을 수 있음
            applicant="",  # Detail에서 출원인 필드 확인 필요
            inventors=detail.inventors,
            claims=detail.claims,
            claims_count=len(detail.claims) if detail.claims else None,
            status=self._map_status(detail.legal_status or ""),
            jurisdiction=PatentJurisdiction.KR,
            source=self.source_name,
            retrieved_at=datetime.utcnow(),
        )
    
    def _convert_legal_status(self, status: KiprisLegalStatus) -> LegalStatus:
        """KiprisLegalStatus -> LegalStatus 변환"""
        return LegalStatus(
            patent_number=status.application_number,
            current_status=self._map_status(status.current_status),
            status_date=status.registration_date,
            status_history=status.history,
        )
    
    def _map_status(self, status_str: str) -> PatentStatus:
        """KIPRIS 상태 문자열 -> PatentStatus 변환"""
        status_lower = status_str.lower() if status_str else ""
        
        if "등록" in status_lower or "grant" in status_lower:
            return PatentStatus.GRANTED
        elif "공개" in status_lower or "publish" in status_lower:
            return PatentStatus.PUBLISHED
        elif "거절" in status_lower or "reject" in status_lower:
            return PatentStatus.REJECTED
        elif "포기" in status_lower or "abandon" in status_lower:
            return PatentStatus.ABANDONED
        elif "취하" in status_lower or "withdraw" in status_lower:
            return PatentStatus.WITHDRAWN
        elif "만료" in status_lower or "expir" in status_lower:
            return PatentStatus.EXPIRED
        else:
            return PatentStatus.APPLICATION


# 편의를 위한 팩토리 함수
def create_kipris_client(api_key: Optional[str] = None) -> KiprisPatentClient:
    """KIPRIS 클라이언트 생성"""
    return KiprisPatentClient(api_key=api_key)

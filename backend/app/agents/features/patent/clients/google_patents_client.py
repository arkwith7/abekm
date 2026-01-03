"""
Google Patents Client - SerpAPI 기반 Google Patents 클라이언트

BasePatentClient 인터페이스를 구현하여 Patent Feature-Pack에 통합.
"""
from __future__ import annotations

import asyncio
import aiohttp
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    PatentJurisdiction,
    PatentStatus,
    PatentCitation,
    LegalStatus,
    BasePatentClient,
)


class GooglePatentsClient(BasePatentClient):
    """
    Google Patents 클라이언트 (SerpAPI 사용)
    
    API 문서:
    - Google Patents Search: https://serpapi.com/google-patents-api
    - Google Patents Details: https://serpapi.com/google-patents-details-api
    
    주요 기능:
    - 특허 검색 (키워드, 출원인, IPC 등)
    - 특허 상세 정보 조회
    - 인용/피인용 정보
    - 법적 상태 정보
    
    지원 관할권:
    - US (미국), EP (유럽), WO (WIPO), CN (중국), JP (일본), KR (한국) 등
    """
    
    SERPAPI_BASE_URL = "https://serpapi.com/search"
    
    # 지원 관할권 (Google Patents가 지원하는 주요 국가)
    SUPPORTED_JURISDICTIONS = [
        PatentJurisdiction.US,
        PatentJurisdiction.EP,
        PatentJurisdiction.WO,
        PatentJurisdiction.CN,
        PatentJurisdiction.JP,
        PatentJurisdiction.KR,
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: SerpAPI API 키 (미제공시 settings에서 로드)
        """
        self.api_key = api_key or getattr(settings, 'serpapi_api_key', None)
        self._session: Optional[aiohttp.ClientSession] = None
    
    # =========================================================================
    # BasePatentClient 인터페이스 구현
    # =========================================================================
    
    @property
    def source_name(self) -> str:
        return "google_patents"
    
    @property
    def supported_jurisdictions(self) -> List[PatentJurisdiction]:
        return self.SUPPORTED_JURISDICTIONS
    
    def is_available(self) -> bool:
        """API 키가 설정되어 있으면 사용 가능"""
        return bool(self.api_key)
    
    async def search(self, query: PatentSearchQuery) -> SearchResult:
        """
        통합 검색 인터페이스 구현
        
        Args:
            query: 표준화된 검색 쿼리
        
        Returns:
            SearchResult: 검색 결과
        """
        patents = await self.search_patents(
            query=" ".join(query.keywords) if query.keywords else "",
            applicant=query.applicant,
            ipc_code=query.ipc_codes[0] if query.ipc_codes else None,
            jurisdictions=[j.value for j in query.jurisdictions] if query.jurisdictions else None,
            date_from=query.date_from,
            date_to=query.date_to,
            max_results=query.max_results,
        )
        
        return SearchResult(
            patents=patents,
            total_count=len(patents),
            source=self.source_name,
            query_used=query,
        )
    
    async def get_patent_by_number(self, patent_number: str) -> Optional[PatentData]:
        """특허 번호로 상세 조회"""
        return await self.get_patent_details(patent_number)
    
    # =========================================================================
    # HTTP 세션 관리
    # =========================================================================
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 획득 (재사용)"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # =========================================================================
    # 검색 API
    # =========================================================================
    
    async def search_patents(
        self,
        query: str = "",
        applicant: Optional[str] = None,
        inventor: Optional[str] = None,
        assignee: Optional[str] = None,
        ipc_code: Optional[str] = None,
        jurisdictions: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        patent_type: Optional[str] = None,  # patent, application, design
        sort_by: str = "relevance",
        language: str = "en",
        max_results: int = 50,
    ) -> List[PatentData]:
        """
        SerpAPI Google Patents 검색
        
        Args:
            query: 검색 키워드
            applicant: 출원인 필터
            inventor: 발명자 필터
            assignee: 양수인 필터
            ipc_code: IPC 분류 필터
            jurisdictions: 관할권 목록 (US, EP, WO 등)
            date_from: 출원일 시작 (YYYY-MM-DD)
            date_to: 출원일 종료
            patent_type: 특허 유형 (patent, application, design)
            sort_by: 정렬 기준 (relevance, new, old)
            language: 언어 코드
            max_results: 최대 결과 수
        
        Returns:
            List[PatentData]: 특허 목록
        """
        if not self.api_key:
            logger.warning("⚠️ [GooglePatents] SerpAPI 키가 설정되지 않았습니다.")
            return []
        
        try:
            session = await self._get_session()
            
            # 검색 쿼리 구성
            search_parts = []
            if query and query.strip():
                search_parts.append(query.strip())
            if applicant:
                search_parts.append(f"assignee:{applicant}")
            if inventor:
                search_parts.append(f"inventor:{inventor}")
            if assignee and assignee != applicant:
                search_parts.append(f"assignee:{assignee}")
            if ipc_code:
                search_parts.append(f"cpc:{ipc_code}")
            
            search_query = " ".join(search_parts)
            
            if not search_query.strip():
                logger.warning("⚠️ [GooglePatents] 검색어가 없습니다.")
                return []
            
            # SerpAPI 파라미터
            params = {
                "engine": "google_patents",
                "q": search_query,
                "api_key": self.api_key,
                "num": max(10, min(max_results, 100)),  # 10-100 범위
            }
            
            # 관할권 필터 (첫 번째 관할권 사용)
            if jurisdictions and len(jurisdictions) > 0:
                params["country"] = jurisdictions[0]
            
            # 추가 필터
            if patent_type:
                params["type"] = patent_type
            if language:
                params["hl"] = language
            if date_from:
                params["after"] = f"filing:{date_from}"
            if date_to:
                params["before"] = f"filing:{date_to}"
            
            logger.info(f"🌐 [GooglePatents] 검색: query='{search_query}', jurisdictions={jurisdictions}")
            
            async with session.get(self.SERPAPI_BASE_URL, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(f"⚠️ [GooglePatents] API 오류: {response.status} - {error_text[:200]}")
                    return []
                
                data = await response.json()
                
                if "error" in data:
                    logger.error(f"❌ [GooglePatents] 오류: {data['error']}")
                    return []
                
                patents = self._parse_search_response(data)
                
                # 출원인 필터링 (후처리)
                if applicant and patents:
                    filtered = [
                        p for p in patents 
                        if self._is_applicant_match(applicant, p.applicant or "")
                    ]
                    if filtered:
                        logger.info(f"📌 [GooglePatents] 출원인 필터링: {len(patents)}건 → {len(filtered)}건")
                        return filtered
                    else:
                        logger.warning(f"⚠️ [GooglePatents] 출원인 '{applicant}' 매칭 0건")
                        return []
                
                return patents
                
        except Exception as e:
            logger.error(f"❌ [GooglePatents] 검색 실패: {e}")
            return []
    
    # =========================================================================
    # 상세 조회 API
    # =========================================================================
    
    async def get_patent_details(
        self,
        patent_id: str,
        language: str = "en",
    ) -> Optional[PatentData]:
        """
        특허 상세 정보 조회 (SerpAPI Google Patents Details API)
        
        Args:
            patent_id: 특허 ID (예: "US11734097B1" 또는 "patent/US11734097B1/en")
            language: 언어 코드
        
        Returns:
            PatentData: 특허 상세 정보
        """
        if not self.api_key:
            logger.warning("⚠️ [GooglePatents] SerpAPI 키가 설정되지 않았습니다.")
            return None
        
        try:
            session = await self._get_session()
            
            # patent_id 형식 정규화
            if not patent_id.startswith("patent/"):
                patent_id = f"patent/{patent_id}"
            if "/" not in patent_id.split("/")[-1] or len(patent_id.split("/")) < 3:
                patent_id = f"{patent_id}/{language}"
            
            params = {
                "engine": "google_patents_details",
                "patent_id": patent_id,
                "api_key": self.api_key,
            }
            
            logger.info(f"🔍 [GooglePatents] 상세 조회: {patent_id}")
            
            async with session.get(self.SERPAPI_BASE_URL, params=params) as response:
                if response.status != 200:
                    logger.warning(f"⚠️ [GooglePatents] 상세 조회 실패: {response.status}")
                    return None
                
                data = await response.json()
                
                if "error" in data:
                    logger.error(f"❌ [GooglePatents] 오류: {data['error']}")
                    return None
                
                return self._parse_details_response(data)
                
        except Exception as e:
            logger.error(f"❌ [GooglePatents] 상세 조회 실패: {e}")
            return None
    
    # =========================================================================
    # 응답 파싱
    # =========================================================================
    
    def _parse_search_response(self, data: Dict[str, Any]) -> List[PatentData]:
        """검색 응답 파싱"""
        patents = []
        organic_results = data.get("organic_results", [])
        
        for idx, result in enumerate(organic_results):
            try:
                patent_id = result.get("patent_id", "")
                publication_number = result.get("publication_number", patent_id)
                
                # 관할권 추출
                jurisdiction = self._extract_jurisdiction(publication_number)
                
                # 출원인/발명자
                assignee = result.get("assignee", "")
                inventor = result.get("inventor", "")
                inventors = [inventor] if inventor else []
                
                # 날짜
                filing_date = result.get("filing_date", "")
                publication_date = result.get("publication_date", "")
                grant_date = result.get("grant_date", "")
                
                # 상태 결정
                status = PatentStatus.APPLICATION
                if grant_date:
                    status = PatentStatus.GRANTED
                elif publication_date:
                    status = PatentStatus.PUBLISHED
                
                # 피인용 수
                cited_by = result.get("cited_by", {})
                cited_by_count = cited_by.get("total", 0) if isinstance(cited_by, dict) else 0
                
                patent = PatentData(
                    patent_number=publication_number,
                    title=result.get("title", ""),
                    abstract=result.get("snippet", ""),
                    applicant=assignee,
                    inventors=inventors,
                    ipc_codes=[],  # 검색 결과에는 IPC 없음
                    application_date=filing_date,
                    publication_date=publication_date,
                    grant_date=grant_date,
                    status=status,
                    jurisdiction=jurisdiction,
                    cited_by_count=cited_by_count,
                    url=result.get("link", f"https://patents.google.com/patent/{publication_number}"),
                    relevance_score=max(0.5, 1.0 - (idx * 0.02)),
                    source="google_patents",
                )
                patents.append(patent)
                
            except Exception as e:
                logger.warning(f"⚠️ [GooglePatents] 결과 파싱 오류: {e}")
                continue
        
        logger.info(f"✅ [GooglePatents] {len(patents)}건 파싱 완료")
        return patents
    
    def _parse_details_response(self, data: Dict[str, Any]) -> PatentData:
        """상세 응답 파싱"""
        # 관할권
        country = data.get("country", "US")
        jurisdiction = self._extract_jurisdiction(country)
        
        # 발명자
        inventors = []
        for inv in data.get("inventors", []):
            if isinstance(inv, dict):
                inventors.append(inv.get("name", ""))
            elif isinstance(inv, str):
                inventors.append(inv)
        
        # IPC 분류
        ipc_codes = []
        for cls in data.get("classifications", []):
            if isinstance(cls, dict):
                code = cls.get("code", "")
                if code:
                    ipc_codes.append(code)
        
        # 청구항
        claims = data.get("claims", [])
        claims_count = len(claims) if claims else None
        
        # 인용 특허
        citations = []
        patent_citations = data.get("patent_citations", {})
        for cite in patent_citations.get("original", []):
            if isinstance(cite, dict):
                pub_num = cite.get("publication_number", "")
                if pub_num:
                    citations.append(pub_num)
        
        # 피인용 수
        cited_by = data.get("cited_by", {})
        cited_by_count = len(cited_by.get("original", [])) if isinstance(cited_by, dict) else 0
        
        # 패밀리 멤버
        family_members = []
        worldwide_apps = data.get("worldwide_applications", {})
        for year, apps in worldwide_apps.items():
            for app in apps:
                if isinstance(app, dict):
                    doc_id = app.get("document_id", "")
                    if doc_id:
                        family_members.append(doc_id)
        
        # 상태 결정
        status = self._determine_status(data)
        
        return PatentData(
            patent_number=data.get("publication_number", ""),
            title=data.get("title", ""),
            abstract=data.get("abstract", "") or data.get("abstract_original", ""),
            applicant=", ".join(data.get("assignees", [])),
            inventors=inventors,
            ipc_codes=ipc_codes,
            application_date=data.get("filing_date"),
            publication_date=data.get("publication_date"),
            grant_date=data.get("grant_date"),
            status=status,
            claims_count=claims_count,
            claims=claims if claims else None,
            citations=citations if citations else None,
            cited_by_count=cited_by_count,
            family_members=family_members if family_members else None,
            jurisdiction=jurisdiction,
            url=data.get("pdf") or data.get("full_view_url") or f"https://patents.google.com/patent/{data.get('publication_number', '')}",
            relevance_score=0.95,
            source="google_patents",
        )
    
    # =========================================================================
    # 유틸리티
    # =========================================================================
    
    def _extract_jurisdiction(self, identifier: str) -> PatentJurisdiction:
        """특허 번호/국가 코드에서 관할권 추출"""
        if not identifier:
            return PatentJurisdiction.US
        
        country_code = identifier[:2].upper()
        try:
            return PatentJurisdiction(country_code)
        except ValueError:
            return PatentJurisdiction.US
    
    def _determine_status(self, data: Dict[str, Any]) -> PatentStatus:
        """특허 상태 결정"""
        status = PatentStatus.APPLICATION
        
        if data.get("grant_date") or "granted" in str(data.get("legal_status", "")).lower():
            status = PatentStatus.GRANTED
        elif data.get("publication_date"):
            status = PatentStatus.PUBLISHED
        
        # 법적 이벤트에서 만료/취하 확인
        for event in data.get("legal_events", []):
            if isinstance(event, dict):
                title = event.get("title", "").lower()
                if "expired" in title or "lapsed" in title:
                    return PatentStatus.EXPIRED
                elif "withdrawn" in title:
                    return PatentStatus.WITHDRAWN
        
        return status
    
    def _is_applicant_match(self, search_applicant: str, patent_applicant: str) -> bool:
        """출원인 매칭 검증"""
        if not search_applicant or not patent_applicant:
            return False
        
        search_clean = search_applicant.strip().lower()
        patent_clean = patent_applicant.strip().lower()
        
        if len(search_clean) < 2:
            return False
        
        # 직접 매칭
        if search_clean in patent_clean or patent_clean in search_clean:
            return True
        
        # 영문/한글 변환 매칭
        name_mappings = {
            "sk": "에스케이", "lg": "엘지", "cj": "씨제이",
            "kt": "케이티", "gs": "지에스", "samsung": "삼성",
            "hyundai": "현대", "kia": "기아",
        }
        
        for eng, kor in name_mappings.items():
            if eng in search_clean and kor in patent_clean:
                return True
            if kor in search_clean and eng in patent_clean:
                return True
        
        # 법인명 제거 후 매칭
        import re
        legal_suffixes = r'(주식회사|㈜|\(주\)|inc\.?|corp\.?|ltd\.?|co\.?|llc)?'
        search_core = re.sub(legal_suffixes, '', search_clean, flags=re.IGNORECASE).strip()
        patent_core = re.sub(legal_suffixes, '', patent_clean, flags=re.IGNORECASE).strip()
        
        if search_core and patent_core:
            if search_core in patent_core or patent_core in search_core:
                return True
        
        return False
    
    # =========================================================================
    # BasePatentClient 추상 메서드 구현
    # =========================================================================
    
    async def get_detail(self, patent_number: str) -> Optional[PatentData]:
        """
        특허 상세 정보 조회 (BasePatentClient 추상 메서드)
        
        Args:
            patent_number: 특허번호
            
        Returns:
            Optional[PatentData]: 특허 상세 정보
        """
        return await self.get_patent_details(patent_number)
    
    async def get_citations(self, patent_number: str) -> List[PatentCitation]:
        """
        인용 특허 조회 (BasePatentClient 추상 메서드)
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[PatentCitation]: 인용 목록
        """
        detail = await self.get_patent_details(patent_number)
        if not detail or not detail.citations:
            return []
        
        # 단순 특허번호 목록을 PatentCitation으로 변환
        citations = []
        for citation_number in detail.citations:
            citations.append(PatentCitation(
                patent_number=citation_number,
                citation_type="backward",  # 이 특허가 인용함
                relevance_category=None,
            ))
        return citations
    
    async def get_legal_status(self, patent_number: str) -> Optional[LegalStatus]:
        """
        법적 상태 조회 (BasePatentClient 추상 메서드)
        
        Args:
            patent_number: 특허번호
            
        Returns:
            Optional[LegalStatus]: 법적 상태 정보
        """
        detail = await self.get_patent_details(patent_number)
        if not detail:
            return None
        
        return LegalStatus(
            patent_number=patent_number,
            status=detail.status,
            grant_date=detail.grant_date,
            expiration_date=None,  # Google Patents에서 직접 제공하지 않음
            is_in_force=detail.status == PatentStatus.GRANTED,
            events=[],  # 상세 이벤트는 별도 API 필요
        )


# =============================================================================
# Factory & Singleton
# =============================================================================

_default_client: Optional[GooglePatentsClient] = None


def get_google_patents_client() -> GooglePatentsClient:
    """기본 Google Patents 클라이언트 반환 (싱글톤)"""
    global _default_client
    if _default_client is None:
        _default_client = GooglePatentsClient()
    return _default_client

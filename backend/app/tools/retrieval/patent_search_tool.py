"""
Patent Search Tool - 특허 검색 도구
KIPRIS (한국) 및 Google Patents (글로벌) API 연동

엔터프라이즈 경쟁 인텔리전스를 위한 특허 데이터 검색 및 분석
"""
import asyncio
import uuid
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from enum import Enum
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.tools.contracts import (
    ToolResult, ToolMetrics, SearchChunk
)
from app.core.config import settings


# =============================================================================
# Patent Data Models
# =============================================================================

class PatentJurisdiction(str, Enum):
    """특허 관할권"""
    KR = "KR"      # 한국 (KIPRIS)
    US = "US"      # 미국 (USPTO)
    EP = "EP"      # 유럽 (EPO)
    WO = "WO"      # 국제 (WIPO PCT)
    CN = "CN"      # 중국
    JP = "JP"      # 일본
    ALL = "ALL"    # 모든 관할권


class PatentStatus(str, Enum):
    """특허 상태"""
    APPLICATION = "application"    # 출원
    PUBLISHED = "published"        # 공개
    GRANTED = "granted"           # 등록
    EXPIRED = "expired"           # 만료
    WITHDRAWN = "withdrawn"       # 취하


class PatentData(BaseModel):
    """특허 데이터 모델"""
    patent_number: str = Field(description="특허번호 (출원번호/등록번호)")
    title: str = Field(description="발명의 명칭")
    abstract: str = Field(default="", description="초록")
    applicant: str = Field(description="출원인")
    inventors: List[str] = Field(default_factory=list, description="발명자 목록")
    ipc_codes: List[str] = Field(default_factory=list, description="IPC 분류 코드")
    application_date: Optional[str] = Field(default=None, description="출원일 (YYYY-MM-DD)")
    publication_date: Optional[str] = Field(default=None, description="공개일")
    grant_date: Optional[str] = Field(default=None, description="등록일")
    status: PatentStatus = Field(default=PatentStatus.APPLICATION, description="특허 상태")
    claims_count: Optional[int] = Field(default=None, description="청구항 수")
    claims: Optional[List[str]] = Field(default=None, description="청구항 목록")
    citations: Optional[List[str]] = Field(default=None, description="인용 특허 번호")
    cited_by_count: Optional[int] = Field(default=None, description="피인용 횟수")
    family_members: Optional[List[str]] = Field(default=None, description="패밀리 특허")
    jurisdiction: PatentJurisdiction = Field(default=PatentJurisdiction.KR, description="관할권")
    url: Optional[str] = Field(default=None, description="특허 상세 URL")
    
    # 점수 (검색 관련성)
    relevance_score: float = Field(default=0.0, description="검색 관련성 점수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "patent_number": "10-2023-0123456",
                "title": "인공지능 기반 반도체 설계 방법",
                "applicant": "삼성전자",
                "inventors": ["홍길동", "김철수"],
                "ipc_codes": ["G06N3/08", "H01L21/00"],
                "application_date": "2023-05-15",
                "jurisdiction": "KR"
            }
        }


class PatentSearchResult(ToolResult):
    """특허 검색 결과"""
    data: List[PatentData] = Field(description="검색된 특허 목록")
    total_found: int = Field(description="총 발견된 특허 수")
    filtered_count: int = Field(description="필터링 후 특허 수")
    search_params: Dict[str, Any] = Field(default_factory=dict, description="검색 파라미터")
    source: str = Field(default="kipris", description="데이터 소스")


# =============================================================================
# KIPRIS API Client (한국특허정보원)
# =============================================================================

class KIPRISClient:
    """
    KIPRIS Open API 클라이언트
    
    API 문서: https://www.kipris.or.kr/khome/openapi/openApiIntro.do
    
    주요 엔드포인트:
    - 특허/실용신안 검색: /patUtiModInfoSearchSevice/
    - 출원인별 검색: /applicantInfoService/
    - 특허 상세 정보: /patentInfoService/
    
    API 문서 참조: https://plus.kipris.or.kr/portal/data/service/DBII_000000000000001/view.do
    """
    
    # 기본 REST API (구 버전)
    BASE_URL = "http://plus.kipris.or.kr/openapi/rest"
    # 새로운 KIPO API (권장)
    KIPO_API_URL = "http://plus.kipris.or.kr/kipo-api/kipi"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'kipris_api_key', None)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 획득"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _is_applicant_match(self, search_applicant: str, patent_applicant: str) -> bool:
        """
        출원인 엄격 매칭 검증
        
        검색한 회사명이 실제 특허 출원인에 포함되어 있는지 확인합니다.
        단순 부분 문자열 매칭이 아닌, 회사명 단위로 매칭합니다.
        
        예:
        - "제이시스메디컬" in "주식회사 제이시스메디컬" → True
        - "SK하이닉스" in "에스케이하이닉스 주식회사" → True (변환 후)
        - "삼성" in "삼성전자 주식회사" → True
        - "시스" in "제이시스메디컬" → False (너무 짧은 부분 매칭 방지)
        """
        if not search_applicant or not patent_applicant:
            return False
        
        search_clean = search_applicant.strip().lower()
        patent_clean = patent_applicant.strip().lower()
        
        # 최소 길이 체크 (너무 짧은 검색어는 오매칭 방지)
        if len(search_clean) < 2:
            return False
        
        # 1. 직접 매칭 (가장 정확)
        if search_clean in patent_clean:
            return True
        
        # 2. 영문/한글 변환 매칭
        # SK → 에스케이, LG → 엘지 등
        name_mappings = {
            "sk": "에스케이", "lg": "엘지", "cj": "씨제이",
            "kt": "케이티", "gs": "지에스", "ks": "케이에스",
            "ls": "엘에스", "hy": "에이치와이", "kcc": "케이씨씨"
        }
        
        for eng, kor in name_mappings.items():
            if eng in search_clean:
                converted = search_clean.replace(eng, kor)
                if converted in patent_clean:
                    return True
            if kor in search_clean:
                converted = search_clean.replace(kor, eng)
                if converted in patent_clean:
                    return True
        
        # 3. 법인명 표기 제거 후 매칭
        # "주식회사", "㈜", "(주)", "Inc.", "Corp." 등 제거
        import re
        legal_suffixes = r'(주식회사|㈜|\(주\)|유한회사|유한책임회사|inc\.?|corp\.?|ltd\.?|co\.?|llc)?'
        search_core = re.sub(legal_suffixes, '', search_clean, flags=re.IGNORECASE).strip()
        patent_core = re.sub(legal_suffixes, '', patent_clean, flags=re.IGNORECASE).strip()
        
        if search_core and search_core in patent_core:
            return True
        
        return False

    async def search_patents(
        self,
        query: str,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        patent_type: str = "patent",  # patent | utility
        max_results: int = 50,
        page: int = 1
    ) -> List[PatentData]:
        """
        KIPRIS 특허 검색 (새로운 KIPO API 사용)
        
        Args:
            query: 검색 키워드 (발명의 명칭, 초록 등)
            applicant: 출원인 필터
            ipc_code: IPC 분류 코드 필터
            date_from: 출원일 시작 (YYYYMMDD)
            date_to: 출원일 종료 (YYYYMMDD)
            patent_type: patent(특허) | utility(실용신안)
            max_results: 최대 결과 수
            page: 페이지 번호
        
        Returns:
            List[PatentData]: 특허 목록
        """
        if not self.api_key:
            logger.warning("⚠️ [KIPRIS] API 키가 설정되지 않았습니다.")
            return []  # API 키 없으면 빈 결과 반환
        
        # 🔧 출원인만 있고 쿼리가 없으면 출원인 검색 API 사용
        search_query = query.strip() if query else ""
        if applicant and not search_query:
            logger.info(f"🔍 [KIPRIS] 출원인 전용 검색: '{applicant}'")
            return await self._search_by_applicant(
                applicant=applicant,
                ipc_code=ipc_code,
                date_from=date_from,
                date_to=date_to,
                patent_type=patent_type,
                max_results=max_results,
                page=page
            )
        
        try:
            session = await self._get_session()
            
            # URL 인코딩
            import urllib.parse
            
            # 🔧 검색 쿼리와 출원인 분리 처리
            # - word: 키워드 검색 (발명의 명칭, 초록 등)
            # - applicant: 출원인 검색 (별도 파라미터)
            search_query = query.strip() if query else ""
            
            # 출원인만 있고 쿼리가 없으면 word는 비워두고 applicant만 사용
            encoded_query = urllib.parse.quote(search_query) if search_query else ""
            
            # 새로운 KIPO API 엔드포인트 (getAdvancedSearch)
            endpoint = f"{self.KIPO_API_URL}/patUtiModInfoSearchSevice/getAdvancedSearch"
            
            params = {
                "ServiceKey": self.api_key,
                "patent": "true" if patent_type == "patent" else "false",
                "utility": "true" if patent_type == "utility" else "false",
                "num_of_rows": str(min(max_results, 100)),
                "page_no": str(page),
                "desc_sort": "true",
                "sort_spec": "AD"  # 출원일 기준 정렬
            }
            
            # word 파라미터: 키워드가 있는 경우에만 추가
            if encoded_query:
                params["word"] = encoded_query
            
            # 🔧 출원인 필터: 항상 별도로 추가 (출원인 검색은 applicant 파라미터 사용)
            if applicant:
                params["applicant"] = urllib.parse.quote(applicant)
            if ipc_code:
                params["ipc_number"] = ipc_code
            if date_from:
                # KIPRIS 날짜 형식: YYYYMMDD
                params["application_date"] = date_from.replace("-", "")
            if date_to:
                # KIPRIS API는 단일 날짜 필터만 지원하는 경우가 있음
                pass
            
            logger.info(f"🔍 [KIPRIS] 검색 요청: endpoint={endpoint}, query='{search_query}', applicant='{applicant}'")
            logger.debug(f"[KIPRIS] 파라미터: {params}")
            
            async with session.get(endpoint, params=params) as response:
                if response.status != 200:
                    content = await response.text()
                    logger.error(f"❌ [KIPRIS] API 오류: {response.status}, 응답: {content[:200]}")
                    # 구 API로 폴백 시도
                    return await self._search_patents_legacy(query, applicant, ipc_code, date_from, date_to, patent_type, max_results, page)
                
                content = await response.text()
                patents = self._parse_kipris_response(content)
                
                # 🔧 출원인 엄격 필터링 (API 결과를 후처리)
                if applicant and patents:
                    original_count = len(patents)
                    # 출원인 엄격 매칭 적용
                    filtered = [p for p in patents if self._is_applicant_match(applicant, p.applicant or "")]
                    if filtered:
                        logger.info(f"📌 [KIPRIS] 출원인 필터링: {original_count}건 → {len(filtered)}건 ('{applicant}')")
                        patents = filtered
                    else:
                        # 매칭 실패 시 빈 결과 반환 (엉뚱한 특허 방지)
                        logger.warning(f"❌ [KIPRIS] 출원인 '{applicant}' 매칭 0건 → 빈 결과 반환")
                        return []
                
                # 새 API로 결과가 없으면 구 API로 폴백
                if not patents:
                    logger.info("🔄 [KIPRIS] 결과 없음, 구 API로 폴백 시도...")
                    return await self._search_patents_legacy(query, applicant, ipc_code, date_from, date_to, patent_type, max_results, page)
                
                return patents
                
        except Exception as e:
            logger.error(f"❌ [KIPRIS] 검색 실패: {e}")
            return await self._search_patents_legacy(query, applicant, ipc_code, date_from, date_to, patent_type, max_results, page)
    
    async def _search_by_applicant(
        self,
        applicant: str,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        patent_type: str = "patent",
        max_results: int = 50,
        page: int = 1
    ) -> List[PatentData]:
        """
        KIPRIS 출원인별 특허 검색
        
        출원인 이름으로 특허를 검색합니다. 키워드 검색이 아닌 출원인 필드에서 직접 검색합니다.
        """
        try:
            session = await self._get_session()
            import urllib.parse
            
            # 출원인 검색 전용 엔드포인트 (applicantInfoService)
            # 참고: https://plus.kipris.or.kr/portal/data/service/DBII_000000000000001/view.do
            endpoint = f"{self.KIPO_API_URL}/patUtiModInfoSearchSevice/getAdvancedSearch"
            
            # 출원인 검색용 파라미터 구성
            # KIPRIS API에서 출원인 검색은 'applicant' 파라미터 또는 특수 검색어 형식 사용
            params = {
                "ServiceKey": self.api_key,
                "applicant": urllib.parse.quote(applicant),  # 출원인 파라미터
                "patent": "true" if patent_type == "patent" else "false",
                "utility": "true" if patent_type == "utility" else "false",
                "num_of_rows": str(min(max_results, 100)),
                "page_no": str(page),
                "desc_sort": "true",
                "sort_spec": "AD"
            }
            
            if ipc_code:
                params["ipc_number"] = ipc_code
            if date_from:
                params["application_date"] = date_from.replace("-", "")
            
            logger.info(f"🔍 [KIPRIS Applicant] 출원인 검색: applicant='{applicant}'")
            logger.debug(f"[KIPRIS Applicant] 파라미터: {params}")
            
            async with session.get(endpoint, params=params) as response:
                if response.status != 200:
                    content = await response.text()
                    logger.error(f"❌ [KIPRIS Applicant] API 오류: {response.status}")
                    # 폴백: word 파라미터에 출원인을 넣고 결과 필터링
                    return await self._search_applicant_fallback(applicant, ipc_code, date_from, date_to, patent_type, max_results, page)
                
                content = await response.text()
                patents = self._parse_kipris_response(content)
                
                if patents:
                    # 결과에서 출원인 확인 로깅
                    unique_applicants = set(p.applicant for p in patents if p.applicant)
                    logger.info(f"✅ [KIPRIS Applicant] {len(patents)}건 검색됨, 출원인: {list(unique_applicants)[:5]}")
                    return patents
                else:
                    # 결과 없으면 폴백
                    logger.info("🔄 [KIPRIS Applicant] 결과 없음, word 검색으로 폴백")
                    return await self._search_applicant_fallback(applicant, ipc_code, date_from, date_to, patent_type, max_results, page)
                    
        except Exception as e:
            logger.error(f"❌ [KIPRIS Applicant] 검색 실패: {e}")
            return await self._search_applicant_fallback(applicant, ipc_code, date_from, date_to, patent_type, max_results, page)
    
    async def _search_applicant_fallback(
        self,
        applicant: str,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        patent_type: str = "patent",
        max_results: int = 50,
        page: int = 1
    ) -> List[PatentData]:
        """
        출원인 검색 폴백 - word 파라미터에 출원인을 넣고 결과 필터링
        """
        try:
            session = await self._get_session()
            import urllib.parse
            
            endpoint = f"{self.KIPO_API_URL}/patUtiModInfoSearchSevice/getAdvancedSearch"
            
            # word에 출원인 이름을 넣고 검색
            params = {
                "ServiceKey": self.api_key,
                "word": urllib.parse.quote(applicant),
                "patent": "true" if patent_type == "patent" else "false",
                "utility": "true" if patent_type == "utility" else "false",
                "num_of_rows": str(min(max_results * 3, 100)),  # 필터링 고려 더 많이 요청
                "page_no": str(page),
                "desc_sort": "true",
                "sort_spec": "AD"
            }
            
            if ipc_code:
                params["ipc_number"] = ipc_code
            if date_from:
                params["application_date"] = date_from.replace("-", "")
            
            logger.info(f"🔍 [KIPRIS Fallback] word 검색 + 필터링: '{applicant}'")
            
            async with session.get(endpoint, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ [KIPRIS Fallback] API 오류: {response.status}")
                    return []  # 오류 시 빈 결과 반환 (데모 데이터 제거)
                
                content = await response.text()
                patents = self._parse_kipris_response(content)
                
                # 🔧 출원인 엄격 필터링 (매칭 실패 시 빈 결과 반환)
                if patents:
                    original_count = len(patents)
                    # 출원인 이름에 검색어가 포함된 특허만 필터링 (엄격 모드)
                    filtered = [
                        p for p in patents 
                        if p.applicant and self._is_applicant_match(applicant, p.applicant)
                    ]
                    
                    if filtered:
                        logger.info(f"📌 [KIPRIS Fallback] 출원인 필터링: {original_count}건 → {len(filtered)}건")
                        return filtered[:max_results]
                    else:
                        # ❌ 출원인 매칭 실패 → 빈 결과 반환 (엉뚱한 특허 방지)
                        logger.warning(f"❌ [KIPRIS Fallback] 출원인 '{applicant}' 정확히 매칭되는 특허 없음 → 빈 결과 반환")
                        return []  # 매칭 실패 시 빈 리스트 반환
                
                return []  # 결과 없음
                
        except Exception as e:
            logger.error(f"❌ [KIPRIS Fallback] 검색 실패: {e}")
            return []  # 오류 시 빈 결과 반환 (데모 데이터 제거)

    async def _search_patents_legacy(
        self,
        query: str,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        patent_type: str = "patent",
        max_results: int = 50,
        page: int = 1
    ) -> List[PatentData]:
        """KIPRIS 구 API로 검색 (폴백용)"""
        try:
            session = await self._get_session()
            
            import urllib.parse
            
            # 🆕 검색 쿼리 구성 (출원인이 있으면 쿼리에 포함)
            search_query = query.strip() if query else ""
            if applicant and not search_query:
                # 쿼리가 비어있으면 출원인을 검색어로 사용
                search_query = applicant
            elif applicant and search_query:
                # 쿼리와 출원인 모두 있으면 조합
                search_query = f"{search_query} {applicant}"
            
            encoded_query = urllib.parse.quote(search_query) if search_query else ""
            
            # 구 API 엔드포인트 - freeSearchInfo (accessKey 사용)
            endpoint = f"{self.BASE_URL}/patUtiModInfoSearchSevice/freeSearchInfo"
            
            params = {
                "accessKey": self.api_key,  # 구 API는 accessKey 사용
                "word": encoded_query,
                "patent": "true" if patent_type == "patent" else "false",
                "utility": "true" if patent_type == "utility" else "false",
                "docs_count": str(min(max_results, 30)),
                "docs_start": str((page - 1) * min(max_results, 30) + 1),
                "desc_sort": "true",
                "sort_spec": "AD"
            }
            
            logger.info(f"🔍 [KIPRIS Legacy] 검색 요청: query='{search_query}', applicant='{applicant}'")
            
            async with session.get(endpoint, params=params) as response:
                if response.status != 200:
                    content = await response.text()
                    logger.error(f"❌ [KIPRIS Legacy] API 오류: {response.status}, 응답: {content[:200]}")
                    return []  # 오류 시 빈 결과 반환
                
                content = await response.text()
                patents = self._parse_kipris_response_legacy(content)
                
                # 🔒 출원인 엄격 필터링
                if applicant and patents:
                    original_count = len(patents)
                    filtered = [p for p in patents if self._is_applicant_match(applicant, p.applicant or "")]
                    if filtered:
                        patents = filtered
                        logger.info(f"📌 [KIPRIS Legacy] 출원인 필터링: {original_count}건 → {len(patents)}건 ('{applicant}')")
                    else:
                        logger.warning(f"❌ [KIPRIS Legacy] 출원인 '{applicant}' 매칭 0건 → 빈 결과 반환")
                        return []  # 매칭 실패 시 빈 결과
                
                return patents
                
        except Exception as e:
            logger.error(f"❌ [KIPRIS Legacy] 검색 실패: {e}")
            return []  # 오류 시 빈 결과 반환
    
    def _parse_kipris_response(self, xml_content: str) -> List[PatentData]:
        """KIPRIS XML 응답 파싱"""
        patents = []
        
        try:
            # KIPRIS API 응답이 잘못된 XML을 반환할 수 있으므로 전처리
            # HTML 엔티티나 잘못된 태그 처리
            import re
            # 잘못된 XML 문자 제거
            xml_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml_content)
            # 닫히지 않은 태그 처리를 위해 lxml 대신 기본 파서 사용
            
            # 에러 응답 체크 (KIPRIS는 에러 시 HTML을 반환할 수 있음)
            if '<html' in xml_content.lower() or '<!doctype' in xml_content.lower():
                logger.warning(f"⚠️ [KIPRIS] HTML 응답 수신 (API 오류일 수 있음)")
                return patents
            
            # 에러 코드 체크
            if '<errMsg>' in xml_content or '<returnAuthMsg>' in xml_content:
                logger.warning(f"⚠️ [KIPRIS] API 에러 응답: {xml_content[:500]}")
                return patents
            
            root = ET.fromstring(xml_content)
            items = root.findall(".//item")
            
            for item in items:
                patent = PatentData(
                    patent_number=self._get_text(item, "applicationNumber", ""),
                    title=self._get_text(item, "inventionTitle", ""),
                    abstract=self._get_text(item, "astrtCont", ""),
                    applicant=self._get_text(item, "applicantName", ""),
                    inventors=self._get_text(item, "inventorName", "").split("|"),
                    ipc_codes=self._get_text(item, "ipcNumber", "").split("|"),
                    application_date=self._format_date(self._get_text(item, "applicationDate", "")),
                    publication_date=self._format_date(self._get_text(item, "openDate", "")),
                    grant_date=self._format_date(self._get_text(item, "registerDate", "")),
                    status=self._parse_status(self._get_text(item, "registerStatus", "")),
                    jurisdiction=PatentJurisdiction.KR,
                    url=f"https://kpat.kipris.or.kr/kpat/biblioa.do?applno={self._get_text(item, 'applicationNumber', '')}"
                )
                patents.append(patent)
                
        except ET.ParseError as e:
            logger.error(f"❌ [KIPRIS] XML 파싱 오류: {e}")
            # 파싱 오류 시 XML 내용 일부 로깅 (디버깅용)
            logger.debug(f"[KIPRIS] 원본 XML (처음 500자): {xml_content[:500]}")
        except Exception as e:
            logger.error(f"❌ [KIPRIS] 파싱 중 예외: {e}")
        
        return patents
    
    def _parse_kipris_response_legacy(self, xml_content: str) -> List[PatentData]:
        """KIPRIS 구 API XML 응답 파싱 (freeSearchInfo 용)"""
        patents = []
        
        try:
            import re
            # 잘못된 XML 문자 제거
            xml_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml_content)
            
            # HTML 응답 체크
            if '<html' in xml_content.lower() or '<!doctype' in xml_content.lower():
                logger.warning(f"⚠️ [KIPRIS Legacy] HTML 응답 수신 (API 오류일 수 있음): {xml_content[:200]}")
                return patents
            
            # 에러 메시지 체크
            if '<errMsg>' in xml_content or '<returnAuthMsg>' in xml_content or 'SERVICE_ACCESS_DENIED' in xml_content:
                logger.warning(f"⚠️ [KIPRIS Legacy] API 에러 응답: {xml_content[:500]}")
                return patents
            
            root = ET.fromstring(xml_content)
            
            # response.body.items.item 경로 파싱 (langchain_kipris_tools 참조)
            body = root.find(".//body")
            if body is None:
                items = root.findall(".//item")
            else:
                items_container = body.find("items")
                if items_container is None:
                    items = root.findall(".//item")
                else:
                    items = items_container.findall("item")
            
            logger.info(f"✅ [KIPRIS Legacy] {len(items)}개 특허 파싱 중...")
            
            for item in items:
                # 구 API 필드명 (langchain_kipris_tools 참조)
                patent = PatentData(
                    patent_number=self._get_text(item, "applicationNumber", "") or self._get_text(item, "applicationnumber", ""),
                    title=self._get_text(item, "inventionTitle", "") or self._get_text(item, "inventionname", ""),
                    abstract=self._get_text(item, "astrtCont", "") or self._get_text(item, "abstractcont", ""),
                    applicant=self._get_text(item, "applicantName", "") or self._get_text(item, "applicantname", ""),
                    inventors=self._get_text(item, "inventorName", "").split("|") if self._get_text(item, "inventorName", "") else [],
                    ipc_codes=self._get_text(item, "ipcNumber", "").split("|") if self._get_text(item, "ipcNumber", "") else [],
                    application_date=self._format_date(self._get_text(item, "applicationDate", "") or self._get_text(item, "applicationdate", "")),
                    publication_date=self._format_date(self._get_text(item, "openDate", "") or self._get_text(item, "opendate", "")),
                    grant_date=self._format_date(self._get_text(item, "registerDate", "") or self._get_text(item, "registerdate", "")),
                    status=self._parse_status(self._get_text(item, "registerStatus", "") or self._get_text(item, "registerstatus", "")),
                    jurisdiction=PatentJurisdiction.KR,
                    url=f"https://kpat.kipris.or.kr/kpat/biblioa.do?applno={self._get_text(item, 'applicationNumber', '') or self._get_text(item, 'applicationnumber', '')}"
                )
                patents.append(patent)
                
        except ET.ParseError as e:
            logger.error(f"❌ [KIPRIS Legacy] XML 파싱 오류: {e}")
            logger.debug(f"[KIPRIS Legacy] 원본 XML (처음 500자): {xml_content[:500]}")
        except Exception as e:
            logger.error(f"❌ [KIPRIS Legacy] 파싱 중 예외: {e}")
        
        return patents
    
    def _get_text(self, element: ET.Element, tag: str, default: str = "") -> str:
        """XML 엘리먼트에서 텍스트 추출"""
        child = element.find(tag)
        return child.text if child is not None and child.text else default
    
    def _format_date(self, date_str: str) -> Optional[str]:
        """날짜 포맷 변환 (YYYYMMDD -> YYYY-MM-DD)"""
        if date_str and len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return None
    
    def _parse_status(self, status_str: str) -> PatentStatus:
        """특허 상태 파싱"""
        status_map = {
            "등록": PatentStatus.GRANTED,
            "공개": PatentStatus.PUBLISHED,
            "출원": PatentStatus.APPLICATION,
            "취하": PatentStatus.WITHDRAWN,
            "만료": PatentStatus.EXPIRED
        }
        return status_map.get(status_str, PatentStatus.APPLICATION)
    



# =============================================================================
# SerpAPI Google Patents Client
# =============================================================================

class SerpAPIGooglePatentsClient:
    """
    SerpAPI Google Patents 클라이언트
    
    API 문서: 
    - Google Patents Search: https://serpapi.com/google-patents-api
    - Google Patents Details: https://serpapi.com/google-patents-details-api
    
    주요 기능:
    - 특허 검색 (키워드, 출원인, IPC 등)
    - 특허 상세 정보 조회
    - 인용/피인용 정보
    - 법적 상태 정보
    """
    
    SERPAPI_BASE_URL = "https://serpapi.com/search"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: SerpAPI API 키
        """
        self.api_key = api_key or getattr(settings, 'serpapi_api_key', None)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 획득"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def search_patents(
        self,
        query: str,
        applicant: Optional[str] = None,
        inventor: Optional[str] = None,
        assignee: Optional[str] = None,
        ipc_code: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        patent_type: Optional[str] = None,  # patent, application, design
        sort_by: str = "relevance",  # relevance, new, old
        language: str = "en",
        max_results: int = 50
    ) -> List[PatentData]:
        """
        SerpAPI Google Patents 검색
        
        Args:
            query: 검색 키워드
            applicant: 출원인 필터
            inventor: 발명자 필터
            assignee: 양수인 필터
            ipc_code: IPC 분류 필터
            jurisdiction: 관할권 (US, EP, WO, CN, JP, KR 등)
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
            logger.warning("⚠️ [SerpAPI] API 키가 없습니다.")
            return []  # 데모 데이터 대신 빈 결과 반환
        
        try:
            session = await self._get_session()
            
            # 🆕 검색 쿼리 구성 (쿼리가 비어있으면 출원인만으로 검색)
            search_parts = []
            if query and query.strip():
                search_parts.append(query.strip())
            if applicant:
                search_parts.append(f"assignee:{applicant}")
            if inventor:
                search_parts.append(f"inventor:{inventor}")
            if assignee and assignee != applicant:
                search_parts.append(f"assignee:{assignee}")
            
            search_query = " ".join(search_parts)
            
            # 검색어가 없으면 빈 결과 반환
            if not search_query.strip():
                logger.warning("⚠️ [SerpAPI] 검색어가 없습니다.")
                return []  # 데모 데이터 대신 빈 결과 반환
            
            # SerpAPI 파라미터 (num은 10-100 범위여야 함)
            params = {
                "engine": "google_patents",
                "q": search_query,
                "api_key": self.api_key,
                "num": max(10, min(max_results, 100)),
            }
            
            # 필터 추가
            if jurisdiction:
                params["country"] = jurisdiction
            if patent_type:
                params["type"] = patent_type
            # sort_by 파라미터는 SerpAPI Google Patents에서 지원하지 않음
            # if sort_by:
            #     params["sort"] = sort_by
            if language:
                params["hl"] = language
            if date_from or date_to:
                # SerpAPI는 before/after 파라미터 사용
                if date_from:
                    params["after"] = f"filing:{date_from}"
                if date_to:
                    params["before"] = f"filing:{date_to}"
            
            logger.info(f"🌐 [SerpAPI] Google Patents 검색: query='{search_query}', jurisdiction={jurisdiction}")
            
            async with session.get(self.SERPAPI_BASE_URL, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(f"⚠️ [SerpAPI] API 응답 오류: {response.status} - {error_text[:200]}")
                    return []  # 오류 시 빈 결과 반환
                
                data = await response.json()
                
                # 에러 체크
                if "error" in data:
                    logger.error(f"❌ [SerpAPI] 오류: {data['error']}")
                    return []  # 오류 시 빈 결과 반환
                
                patents = self._parse_serpapi_search_response(data)
                
                # 🔧 출원인 엄격 필터링 (SerpAPI 결과도 검증)
                if applicant and patents:
                    from app.tools.retrieval.patent_search_tool import KIPRISClient
                    kipris_client = KIPRISClient()
                    filtered = [p for p in patents if kipris_client._is_applicant_match(applicant, p.applicant or "")]
                    if filtered:
                        logger.info(f"📌 [SerpAPI] 출원인 필터링: {len(patents)}건 → {len(filtered)}건")
                        return filtered
                    else:
                        logger.warning(f"⚠️ [SerpAPI] 출원인 '{applicant}' 매칭 0건 → 빈 결과 반환")
                        return []
                
                return patents
                
        except Exception as e:
            logger.error(f"❌ [SerpAPI] 검색 실패: {e}")
            return []  # 예외 시 빈 결과 반환
    
    async def get_patent_details(
        self,
        patent_id: str,
        language: str = "en"
    ) -> Optional[PatentData]:
        """
        특허 상세 정보 조회 (SerpAPI Google Patents Details API)
        
        Args:
            patent_id: 특허 ID (예: "patent/US11734097B1/en" 또는 "US11734097B1")
            language: 언어 코드
        
        Returns:
            PatentData: 특허 상세 정보
        """
        if not self.api_key:
            logger.warning("⚠️ [SerpAPI] API 키가 없습니다.")
            return None
        
        try:
            session = await self._get_session()
            
            # patent_id 형식 정규화
            if not patent_id.startswith("patent/"):
                patent_id = f"patent/{patent_id}"
            if not "/" in patent_id.split("/")[-1]:
                patent_id = f"{patent_id}/{language}"
            
            params = {
                "engine": "google_patents_details",
                "patent_id": patent_id,
                "api_key": self.api_key,
            }
            
            logger.info(f"🔍 [SerpAPI] 특허 상세 조회: {patent_id}")
            
            async with session.get(self.SERPAPI_BASE_URL, params=params) as response:
                if response.status != 200:
                    logger.warning(f"⚠️ [SerpAPI] 상세 조회 실패: {response.status}")
                    return None
                
                data = await response.json()
                
                if "error" in data:
                    logger.error(f"❌ [SerpAPI] 오류: {data['error']}")
                    return None
                
                return self._parse_patent_details(data)
                
        except Exception as e:
            logger.error(f"❌ [SerpAPI] 상세 조회 실패: {e}")
            return None
    
    def _parse_serpapi_search_response(self, data: Dict[str, Any]) -> List[PatentData]:
        """SerpAPI 검색 응답 파싱"""
        patents = []
        
        organic_results = data.get("organic_results", [])
        
        for idx, result in enumerate(organic_results):
            try:
                # 특허 번호 추출
                patent_id = result.get("patent_id", "")
                publication_number = result.get("publication_number", patent_id)
                
                # 관할권 추출 (특허 번호 앞 2자리)
                jurisdiction = PatentJurisdiction.US
                if publication_number:
                    country_code = publication_number[:2].upper()
                    if country_code in ["KR", "US", "EP", "WO", "CN", "JP"]:
                        try:
                            jurisdiction = PatentJurisdiction(country_code)
                        except ValueError:
                            pass
                
                # 출원인/양수인
                assignee = result.get("assignee", "")
                
                # 발명자
                inventor = result.get("inventor", "")
                inventors = [inventor] if inventor else []
                
                # 날짜 파싱
                filing_date = result.get("filing_date", "")
                publication_date = result.get("publication_date", "")
                grant_date = result.get("grant_date", "")
                
                # 상태 결정
                status = PatentStatus.APPLICATION
                if grant_date:
                    status = PatentStatus.GRANTED
                elif publication_date:
                    status = PatentStatus.PUBLISHED
                
                patent = PatentData(
                    patent_number=publication_number,
                    title=result.get("title", ""),
                    abstract=result.get("snippet", ""),
                    applicant=assignee,
                    inventors=inventors,
                    ipc_codes=[],  # 검색 결과에는 IPC 없음, 상세에서 가져와야 함
                    application_date=filing_date,
                    publication_date=publication_date,
                    grant_date=grant_date,
                    status=status,
                    jurisdiction=jurisdiction,
                    cited_by_count=result.get("cited_by", {}).get("total", 0) if isinstance(result.get("cited_by"), dict) else 0,
                    url=result.get("link", f"https://patents.google.com/patent/{publication_number}"),
                    relevance_score=max(0.5, 1.0 - (idx * 0.02))  # 순위 기반 점수
                )
                patents.append(patent)
                
            except Exception as e:
                logger.warning(f"⚠️ [SerpAPI] 결과 파싱 오류: {e}")
                continue
        
        logger.info(f"✅ [SerpAPI] {len(patents)}건 파싱 완료")
        return patents
    
    def _parse_patent_details(self, data: Dict[str, Any]) -> PatentData:
        """SerpAPI 특허 상세 응답 파싱"""
        # 관할권 추출
        country = data.get("country", "US")
        try:
            jurisdiction = PatentJurisdiction(country[:2].upper())
        except ValueError:
            jurisdiction = PatentJurisdiction.US
        
        # 발명자 파싱
        inventors = []
        for inv in data.get("inventors", []):
            if isinstance(inv, dict):
                inventors.append(inv.get("name", ""))
            elif isinstance(inv, str):
                inventors.append(inv)
        
        # IPC 분류 파싱
        ipc_codes = []
        for cls in data.get("classifications", []):
            if isinstance(cls, dict):
                ipc_codes.append(cls.get("code", ""))
        
        # 청구항 파싱
        claims = data.get("claims", [])
        claims_count = len(claims) if claims else None
        
        # 인용 특허 파싱
        citations = []
        patent_citations = data.get("patent_citations", {})
        for cite in patent_citations.get("original", []):
            if isinstance(cite, dict):
                citations.append(cite.get("publication_number", ""))
        
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
        status = PatentStatus.APPLICATION
        if data.get("grant_date") or "granted" in str(data.get("legal_status", "")).lower():
            status = PatentStatus.GRANTED
        elif data.get("publication_date"):
            status = PatentStatus.PUBLISHED
        
        # 법적 상태에서 만료/취하 확인
        for event in data.get("legal_events", []):
            if isinstance(event, dict):
                title = event.get("title", "").lower()
                if "expired" in title or "lapsed" in title:
                    status = PatentStatus.EXPIRED
                    break
                elif "withdrawn" in title:
                    status = PatentStatus.WITHDRAWN
                    break
        
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
            relevance_score=0.95  # 상세 조회는 높은 관련성
        )
    



# Alias for backward compatibility
GooglePatentsClient = SerpAPIGooglePatentsClient


# =============================================================================
# Patent Search Tool
# =============================================================================

class PatentSearchTool(BaseTool):
    """
    특허 검색 도구
    
    지원 API:
    - KIPRIS (한국 특허)
    - Google Patents / Lens.org (글로벌)
    
    사용 예:
    - 경쟁사 특허 포트폴리오 분석
    - 기술 동향 파악
    - 특허 침해 위험 분석
    """
    name: str = "patent_search"
    description: str = """특허 데이터베이스 검색 도구 (SerpAPI Google Patents + KIPRIS).
    
기능:
- 키워드/기술 분야별 특허 검색
- 출원인(회사)별 특허 검색  
- 발명자별 검색
- IPC 분류 코드별 검색
- 한국(KIPRIS) 및 글로벌(SerpAPI Google Patents) 특허 지원
- 특허 상세 정보 조회 (인용, 청구항, 법적 상태 등)

사용 시나리오:
- "삼성전자의 AI 관련 특허 검색"
- "최근 3년간 반도체 특허 동향"
- "경쟁사 A와 B의 특허 비교"
- "특정 특허의 인용/피인용 분석"
"""
    version: str = "1.1.0"
    
    # 클라이언트 (PrivateAttr로 pydantic 호환)
    _kipris_client: KIPRISClient = PrivateAttr()
    _google_client: GooglePatentsClient = PrivateAttr()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kipris_client = KIPRISClient()
        self._google_client = GooglePatentsClient()
    
    async def _arun(
        self,
        query: str,
        applicant: Optional[str] = None,
        ipc_codes: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        jurisdiction: str = "KR",
        max_results: int = 50,
        include_global: bool = False,
        **kwargs
    ) -> PatentSearchResult:
        """
        특허 검색 실행 (비동기)
        
        Args:
            query: 검색 키워드 (발명의 명칭, 기술 분야 등)
            applicant: 출원인 필터 (회사명, 예: "삼성전자")
            ipc_codes: IPC 분류 코드 필터 (예: ["G06N", "H01L"])
            date_from: 출원일 시작 (YYYY-MM-DD)
            date_to: 출원일 종료
            jurisdiction: 관할권 (KR, US, EP, WO, ALL)
            max_results: 최대 결과 수
            include_global: 글로벌 특허 포함 여부
        
        Returns:
            PatentSearchResult: 검색 결과
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        all_patents: List[PatentData] = []
        errors: List[str] = []
        
        search_params = {
            "query": query,
            "applicant": applicant,
            "ipc_codes": ipc_codes,
            "date_from": date_from,
            "date_to": date_to,
            "jurisdiction": jurisdiction,
            "max_results": max_results
        }
        
        logger.info(f"🔍 [PatentSearch] 검색 시작: {search_params}")
        
        try:
            # 한국 특허 검색 (KIPRIS) - 실패 시 SerpAPI fallback
            kipris_success = False
            if jurisdiction in ["KR", "ALL"]:
                try:
                    kr_patents = await self._kipris_client.search_patents(
                        query=query,
                        applicant=applicant,
                        ipc_code=ipc_codes[0] if ipc_codes else None,
                        date_from=date_from.replace("-", "") if date_from else None,
                        date_to=date_to.replace("-", "") if date_to else None,
                        max_results=max_results
                    )
                    if kr_patents:  # KIPRIS에서 결과가 있으면 성공
                        all_patents.extend(kr_patents)
                        kipris_success = True
                    logger.info(f"✅ [KIPRIS] {len(kr_patents)}건 검색됨")
                except Exception as e:
                    errors.append(f"KIPRIS 검색 오류: {str(e)}")
                    logger.error(f"❌ [KIPRIS] 오류: {e}")
            
            # 글로벌 특허 검색 (SerpAPI)
            # - jurisdiction이 KR이 아닌 경우
            # - include_global이 True인 경우
            # - KIPRIS 검색 결과가 없는 경우 (fallback)
            use_global = (jurisdiction not in ["KR"]) or include_global or (jurisdiction == "KR" and not kipris_success)
            
            if use_global:
                try:
                    # KR인데 KIPRIS 실패 시 SerpAPI로 KR 검색
                    jur_filter = jurisdiction if jurisdiction != "ALL" else None
                    if jurisdiction == "KR" and include_global and kipris_success:
                        jur_filter = "US"  # KIPRIS 성공 시 글로벌은 US
                    
                    global_patents = await self._google_client.search_patents(
                        query=query,
                        applicant=applicant,
                        ipc_code=ipc_codes[0] if ipc_codes else None,
                        jurisdiction=jur_filter,
                        date_from=date_from,
                        date_to=date_to,
                        max_results=max_results
                    )
                    all_patents.extend(global_patents)
                    logger.info(f"✅ [GlobalPatents] {len(global_patents)}건 검색됨 (jurisdiction={jur_filter})")
                except Exception as e:
                    errors.append(f"글로벌 특허 검색 오류: {str(e)}")
                    logger.error(f"❌ [GlobalPatents] 오류: {e}")
            
            # 관련성 점수 기반 정렬
            all_patents.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # 중복 제거 (특허번호 기준)
            seen_numbers = set()
            unique_patents = []
            for patent in all_patents:
                if patent.patent_number not in seen_numbers:
                    seen_numbers.add(patent.patent_number)
                    unique_patents.append(patent)
            
            # 최대 결과 수 제한
            final_patents = unique_patents[:max_results]
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ [PatentSearch] 완료: {len(final_patents)}건, {elapsed_ms:.0f}ms")
            
            return PatentSearchResult(
                success=True,
                data=final_patents,
                total_found=len(all_patents),
                filtered_count=len(final_patents),
                search_params=search_params,
                source="kipris+global" if include_global or jurisdiction == "ALL" else "kipris",
                metrics=ToolMetrics(
                    latency_ms=elapsed_ms,
                    provider="patent_api",
                    items_returned=len(final_patents),
                    trace_id=trace_id
                ),
                errors=errors,
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [PatentSearch] 오류: {e}")
            
            return PatentSearchResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params=search_params,
                source="error",
                metrics=ToolMetrics(
                    latency_ms=elapsed_ms,
                    provider="patent_api",
                    trace_id=trace_id
                ),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    def _run(
        self,
        query: str,
        **kwargs
    ) -> PatentSearchResult:
        """동기 실행 (폴백)"""
        return asyncio.run(self._arun(query, **kwargs))
    
    async def get_patent_details(
        self,
        patent_id: str,
        language: str = "en"
    ) -> Optional[PatentData]:
        """
        특허 상세 정보 조회 (SerpAPI Google Patents Details API)
        
        Args:
            patent_id: 특허 ID (예: "US11734097B1", "patent/US11734097B1/en")
            language: 언어 코드 (en, ko, ja 등)
        
        Returns:
            PatentData: 특허 상세 정보 (인용, 청구항, 법적 상태 포함)
        
        사용 예:
            details = await tool.get_patent_details("US11734097B1")
            print(f"제목: {details.title}")
            print(f"청구항 수: {details.claims_count}")
            print(f"인용 특허: {details.citations}")
        """
        return await self._google_client.get_patent_details(patent_id, language)
    
    def to_search_chunks(self, patents: List[PatentData]) -> List[SearchChunk]:
        """
        특허 데이터를 SearchChunk 형태로 변환
        (기존 검색 도구들과 호환성 유지)
        """
        chunks = []
        for patent in patents:
            content = f"""[{patent.jurisdiction.value}] {patent.title}

출원번호: {patent.patent_number}
출원인: {patent.applicant}
발명자: {', '.join(patent.inventors)}
출원일: {patent.application_date or 'N/A'}
IPC: {', '.join(patent.ipc_codes)}
상태: {patent.status.value}

초록:
{patent.abstract}
"""
            chunk = SearchChunk(
                chunk_id=f"patent_{patent.patent_number}",
                content=content,
                score=patent.relevance_score,
                file_id=patent.patent_number,
                match_type="patent",
                container_id=f"patent_{patent.jurisdiction.value}",
                metadata={
                    "patent_number": patent.patent_number,
                    "applicant": patent.applicant,
                    "ipc_codes": patent.ipc_codes,
                    "application_date": patent.application_date,
                    "jurisdiction": patent.jurisdiction.value,
                    "status": patent.status.value,
                    "url": patent.url
                }
            )
            chunks.append(chunk)
        
        return chunks


# =============================================================================
# Factory Function & Singleton Instance
# =============================================================================

def get_patent_search_tool() -> PatentSearchTool:
    """PatentSearchTool 인스턴스 반환"""
    return PatentSearchTool()


# 싱글톤 인스턴스 (import 시 사용)
patent_search_tool = PatentSearchTool()


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        tool = get_patent_search_tool()
        
        # 테스트 1: 기본 검색
        print("=" * 60)
        print("테스트 1: 기본 검색")
        print("=" * 60)
        result = await tool._arun(
            query="인공지능 반도체",
            max_results=5
        )
        print(f"검색 결과: {len(result.data)}건")
        for p in result.data:
            print(f"  - {p.title} ({p.applicant})")
        
        # 테스트 2: 출원인 필터
        print("\n" + "=" * 60)
        print("테스트 2: 출원인 필터 (삼성전자)")
        print("=" * 60)
        result2 = await tool._arun(
            query="AI",
            applicant="삼성전자",
            max_results=5
        )
        print(f"삼성전자 특허: {len(result2.data)}건")
        
        # 테스트 3: 글로벌 검색 (SerpAPI)
        print("\n" + "=" * 60)
        print("테스트 3: 글로벌 검색 (US)")
        print("=" * 60)
        result3 = await tool._arun(
            query="machine learning semiconductor",
            jurisdiction="US",
            max_results=5
        )
        print(f"미국 특허: {len(result3.data)}건")
        for p in result3.data:
            print(f"  - [{p.jurisdiction.value}] {p.title}")
            print(f"    출원인: {p.applicant}, 상태: {p.status.value}")
        
        # 테스트 4: 특허 상세 정보
        if result3.data:
            print("\n" + "=" * 60)
            print("테스트 4: 특허 상세 정보")
            print("=" * 60)
            patent_num = result3.data[0].patent_number
            details = await tool.get_patent_details(patent_num)
            if details:
                print(f"특허번호: {details.patent_number}")
                print(f"제목: {details.title}")
                print(f"청구항 수: {details.claims_count}")
                print(f"인용 특허: {len(details.citations or [])}건")
                print(f"피인용 수: {details.cited_by_count}")
                print(f"IPC 코드: {details.ipc_codes}")
    
    asyncio.run(test())

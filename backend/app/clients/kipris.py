"""
KIPRIS API Client
한국특허정보원(KIPRIS) Open API 연동 클라이언트

제공 기능:
1. 특허/실용신안 검색 (Search)
2. 서지 정보 조회 (Bibliography)
3. 전문 조회 (Full Text)
4. 행정/법적 상태 조회 (Legal Status)
"""
import aiohttp
import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings

# =============================================================================
# Data Models
# =============================================================================

class KiprisPatentBasic(BaseModel):
    """KIPRIS 특허 기본 정보 (검색 결과)"""
    application_number: str = Field(description="출원번호")
    title: str = Field(description="발명의 명칭")
    applicant: str = Field(description="출원인")
    application_date: str = Field(description="출원일")
    status: str = Field(description="상태")
    ipc_code: str = Field(description="IPC 코드 (대표)")
    ipc_all: List[str] = Field(default_factory=list, description="전체 IPC 코드")
    abstract: str = Field(description="초록")
    open_date: Optional[str] = Field(None, description="공개일")
    register_date: Optional[str] = Field(None, description="등록일")
    image_path: Optional[str] = Field(None, description="대표도면 경로")
    customer_no: Optional[str] = Field(None, description="특허고객번호")

class KiprisPatentDetail(BaseModel):
    """KIPRIS 특허 상세 정보 (서지+전문)"""
    application_number: str
    title: str
    claims: List[str] = Field(default_factory=list, description="청구항")
    description: str = Field(default="", description="상세설명")
    inventors: List[str] = Field(default_factory=list, description="발명자")
    agent: Optional[str] = Field(None, description="대리인")
    priority_info: Optional[str] = Field(None, description="우선권 정보")
    legal_status: Optional[str] = Field(None, description="법적 상태")
    image_path: Optional[str] = Field(None, description="대표도면 경로")

class KiprisLegalStatus(BaseModel):
    """KIPRIS 행정/법적 상태"""
    application_number: str
    current_status: str = Field(description="현재 상태 (등록/거절/포기/취하)")
    history: List[Dict[str, str]] = Field(default_factory=list, description="진행 이력")
    registration_date: Optional[str] = None
    expiration_date: Optional[str] = None

class KiprisFamilyInfo(BaseModel):
    """KIPRIS 패밀리 정보"""
    application_number: str
    family_patents: List[Dict[str, str]] = Field(default_factory=list, description="패밀리 특허 목록")

# =============================================================================
# KIPRIS Client
# =============================================================================

class KiprisClient:
    """
    KIPRIS API 클라이언트 (세분화된 기능 제공)
    """
    # KIPO API (REST)
    BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'kipris_api_key', None)
        self._session: Optional[aiohttp.ClientSession] = None
        
        if not self.api_key:
            logger.warning("⚠️ [KiprisClient] API Key가 설정되지 않았습니다.")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, service: str, operation: str, params: Dict[str, str]) -> Optional[str]:
        """공통 요청 메서드"""
        if not self.api_key:
            return None
            
        session = await self._get_session()
        endpoint = f"{self.BASE_URL}/{service}/{operation}"
        
        # 기본 파라미터 추가
        params["ServiceKey"] = self.api_key
        
        try:
            async with session.get(endpoint, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ [KIPRIS] API Error ({response.status}): {endpoint}")
                    return None
                return await response.text()
        except Exception as e:
            logger.error(f"❌ [KIPRIS] Request Failed: {e}")
            return None

    # -------------------------------------------------------------------------
    # 0. Applicant Info (출원인 정보)
    # -------------------------------------------------------------------------

    async def search_applicant_code(self, applicant_name: str) -> Optional[str]:
        """
        출원인 명칭으로 특허고객번호 조회
        """
        # TODO: KIPRIS에서 제공하는 출원인 검색 API가 명확하지 않으므로
        # 현재는 getAdvancedSearch 결과에서 customerNumber를 추출하는 방식으로 우회 구현 가능
        # 또는 별도의 출원인 코드 조회 API가 있다면 그것을 사용
        
        # 임시 구현: 검색을 통해 첫 번째 결과의 출원인 코드를 반환
        params = {
            "applicant": applicant_name,
            "numOfRows": "1",
            "pageNo": "1"
        }
        xml_response = await self._request("patUtiModInfoSearchSevice", "getAdvancedSearch", params)
        if not xml_response:
            return None
            
        try:
            root = ET.fromstring(xml_response)
            item = root.find(".//item")
            if item is not None:
                # XML 응답에 customerNumber 필드가 있는지 확인 필요
                # KIPRIS 문서에 따르면 applicantName만 있고 코드는 없을 수 있음
                # 이 경우 별도 로직 필요
                return self._get_text(item, "applicantCode") # 가상의 필드명
        except:
            pass
        return None

    # -------------------------------------------------------------------------
    # 1. Search (검색)
    # -------------------------------------------------------------------------
    
    async def search_patents(
        self,
        query: str,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 30,
        customer_no: Optional[str] = None
    ) -> Tuple[List[KiprisPatentBasic], int]:
        """
        특허 검색 (Advanced Search)
        Returns: (특허 목록, 총 검색 결과 수)
        """
        params = {
            "patent": "true",
            "utility": "true",
            "num_of_rows": str(min(max_results, 100)),
            "page_no": "1",
            "desc_sort": "true",
            "sort_spec": "AD"  # 출원일순
        }
        
        # 쿼리 구성
        if query:
            params["word"] = query
        
        # 출원인 검색: 고객번호가 있으면 우선 사용
        if customer_no:
            params["customer_no"] = customer_no # API 파라미터명 확인 필요
        elif applicant:
            params["applicant"] = applicant
            
        if ipc_code:
            params["ipc_number"] = ipc_code
        if date_from:
            params["application_date"] = date_from.replace("-", "")
            
        xml_response = await self._request("patUtiModInfoSearchSevice", "getAdvancedSearch", params)
        if not xml_response:
            return [], 0
            
        return self._parse_search_result(xml_response)

    def _parse_search_result(self, xml_content: str) -> Tuple[List[KiprisPatentBasic], int]:
        results = []
        total_count = 0
        try:
            root = ET.fromstring(xml_content)
            items = root.findall(".//item")
            
            # 총 개수 파싱
            count_tag = root.find(".//count/totalCount")
            if count_tag is not None and count_tag.text:
                try:
                    total_count = int(count_tag.text)
                except ValueError:
                    pass
            
            for item in items:
                try:
                    ipc_str = self._get_text(item, "ipcNumber")
                    ipc_list = [code.strip() for code in ipc_str.split("|")] if ipc_str else []
                    
                    patent = KiprisPatentBasic(
                        application_number=self._get_text(item, "applicationNumber"),
                        title=self._get_text(item, "inventionTitle"),
                        applicant=self._get_text(item, "applicantName"),
                        application_date=self._format_date(self._get_text(item, "applicationDate")),
                        status=self._get_text(item, "registerStatus"),
                        ipc_code=ipc_list[0] if ipc_list else "",
                        ipc_all=ipc_list,
                        abstract=self._get_text(item, "astrtCont"),
                        open_date=self._format_date(self._get_text(item, "openDate")),
                        register_date=self._format_date(self._get_text(item, "registerDate")),
                        image_path=self._get_text(item, "bigDrawing"),
                        customer_no=None  # 검색 결과에는 없을 수 있음
                    )
                    results.append(patent)
                except Exception as e:
                    logger.warning(f"⚠️ [KIPRIS] Item parsing error: {e}")
                    continue
        except Exception as e:
            logger.error(f"❌ [KIPRIS] XML Parsing Error: {e}")
            
        return results, total_count

    # -------------------------------------------------------------------------
    # 2. Bibliography & Detail (서지 정보 및 상세)
    # -------------------------------------------------------------------------

    async def get_biblio_detail(self, application_number: str) -> Optional[KiprisPatentDetail]:
        """
        문헌상세정보 조회 (청구항, 법적상태 포함)
        """
        app_no = application_number.replace("-", "")
        params = {"applicationNumber": app_no}
        
        # 문헌상세정보 서비스 (getBiblioInfoSearch)
        xml_response = await self._request("patUtiModInfoSearchSevice", "getBiblioDetailInfo", params)
        
        if not xml_response:
            logger.warning(f"⚠️ [KIPRIS] getBiblioDetailInfo returned no response for {app_no}")
            return None
            
        # logger.debug(f"🔍 [KIPRIS] Detail XML: {xml_response[:500]}...") # Debug log
            
        try:
            root = ET.fromstring(xml_response)
            item = root.find(".//item") # 상세 정보는 보통 단일 item
            
            if not item:
                # body/items/item 구조일 수도 있음
                item = root.find(".//body/items/item")
            
            if item:
                # 청구항 파싱 (claimText가 있다면)
                claim_text = self._get_text(item, "claimInfo") # 필드명 확인 필요
                claims = [c.strip() for c in claim_text.split("|")] if claim_text else []
                
                return KiprisPatentDetail(
                    application_number=self._get_text(item, "applicationNumber"),
                    title=self._get_text(item, "inventionTitle"),
                    claims=claims,
                    description="", # 상세설명은 별도 API일 수 있음
                    inventors=[self._get_text(item, "inventorName")],
                    agent=self._get_text(item, "agentName"),
                    priority_info=self._get_text(item, "priorityNumber"),
                    legal_status=self._get_text(item, "registerStatus"),
                    image_path=self._get_text(item, "pathImg")
                )
            else:
                logger.warning(f"⚠️ [KIPRIS] Item not found in Detail XML for {app_no}")
                # logger.debug(f"XML: {xml_response}")
        except Exception as e:
            logger.error(f"❌ [KIPRIS] Detail Parsing Error: {e}")
            
        return None

    async def get_bibliography(self, application_number: str) -> Optional[Dict[str, Any]]:
        """
        서지 정보 상세 조회 (Legacy Wrapper)
        """
        detail = await self.get_biblio_detail(application_number)
        return detail.model_dump() if detail else None

    # -------------------------------------------------------------------------
    # 3. Full Text (전문)
    # -------------------------------------------------------------------------

    async def get_full_text(self, application_number: str) -> Optional[KiprisPatentDetail]:
        """
        전문(청구항, 상세설명) 조회
        """
        app_no = application_number.replace("-", "")
        params = {"applicationNumber": app_no}
        
        # 전문 API 엔드포인트 (추정)
        # 실제로는 getFullTextInfo 등이 사용될 수 있음
        xml_response = await self._request("patUtiModInfoSearchSevice", "getFullTextInfo", params)
        
        if not xml_response:
            return None
            
        # TODO: XML 파싱하여 Claims, Description 추출
        return None

    # -------------------------------------------------------------------------
    # 4. Legal Status (행정 상태)
    # -------------------------------------------------------------------------

    async def get_legal_status(self, application_number: str) -> Optional[KiprisLegalStatus]:
        """
        행정/법적 상태 조회
        """
        app_no = application_number.replace("-", "")
        params = {"applicationNumber": app_no}
        
        # 행정정보 API
        xml_response = await self._request("patUtiModInfoSearchSevice", "getAdminInfo", params)
        
        if not xml_response:
            return None
            
        # TODO: XML 파싱하여 이력 추출
        return None

    # -------------------------------------------------------------------------
    # 5. Family Info (패밀리 정보)
    # -------------------------------------------------------------------------

    async def get_family_info(self, application_number: str) -> Optional[KiprisFamilyInfo]:
        """
        패밀리 특허 정보 조회
        """
        app_no = application_number.replace("-", "")
        params = {"applicationNumber": app_no}
        
        xml_response = await self._request("patUtiModInfoSearchSevice", "getFamilyPatentInfo", params)
        
        if not xml_response:
            return None
            
        # TODO: 파싱 로직 구현
        return KiprisFamilyInfo(
            application_number=application_number,
            family_patents=[]
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_text(self, element: ET.Element, tag: str, default: str = "") -> str:
        child = element.find(tag)
        return child.text if child is not None and child.text else default
    
    def _format_date(self, date_str: str) -> str:
        """YYYYMMDD -> YYYY-MM-DD"""
        if date_str and len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    def _is_applicant_match(self, search_applicant: str, patent_applicant: str) -> bool:
        """출원인 매칭 유틸리티"""
        if not search_applicant or not patent_applicant:
            return False
        
        search = search_applicant.strip().lower()
        target = patent_applicant.strip().lower()
        
        if len(search) < 2:
            return False
            
        if search in target:
            return True
            
        # 영문/한글 매핑 등 추가 로직
        return False


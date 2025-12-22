"""
KIPRIS API 클라이언트
한국 특허정보원(KIPRIS) Open API를 통한 특허 검색 및 조회
"""
from typing import List, Dict, Any, Optional
import httpx
from loguru import logger
from app.core.config import settings


class KIPRISClient:
    """KIPRIS API 클라이언트 (특허정보 검색)

    기본 경로는 KIPRIS Plus의 kipo-api 고급검색 엔드포인트로 설정한다.
    필요 시 환경설정에서 kipris_base_url / kipris_search_path로 덮어쓰기 가능.
    """
    
    DEFAULT_BASE_URL = "http://plus.kipris.or.kr/kipo-api"
    DEFAULT_SEARCH_PATH = "kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: KIPRIS API 키 (없으면 settings에서 가져옴)
        """
        self.api_key = api_key or getattr(settings, 'kipris_api_key', '')
        if not self.api_key:
            logger.warning("⚠️ KIPRIS API 키가 설정되지 않았습니다")

        self.base_url = getattr(settings, 'kipris_base_url', '') or self.DEFAULT_BASE_URL
        self.search_path = getattr(settings, 'kipris_search_path', '') or self.DEFAULT_SEARCH_PATH

        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    
    async def search_patents(
        self,
        ipc_codes: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        applicants: Optional[List[str]] = None,
        max_results: int = 100,
        sort: str = "application_date_desc"
    ) -> List[Dict[str, Any]]:
        """
        특허 검색
        
        Args:
            ipc_codes: IPC 분류 코드 리스트 (예: ["G06N", "G06F"])
            keywords: 키워드 리스트 (제목/요약 검색)
            applicants: 출원인 리스트
            max_results: 최대 결과 수 (KIPRIS API 제한: 100건/요청)
            sort: 정렬 (application_date_desc, publication_date_desc)
        
        Returns:
            특허 서지정보 리스트
        """
        try:
            # KIPRIS API는 한 번에 최대 100건까지만 조회 가능
            page_size = min(max_results, 100)

            # 검색 조건 구성 (KIPRIS 검색식). 기존 SearchService 형식과 동일하게 word 파라미터로 전달.
            query_parts = []

            if ipc_codes:
                ipc_query = " OR ".join([f"IPC:{code}" for code in ipc_codes])
                query_parts.append(f"({ipc_query})")

            if keywords:
                keyword_query = " OR ".join([f"TI:{kw}" for kw in keywords])
                query_parts.append(f"({keyword_query})")

            if applicants:
                applicant_query = " OR ".join([f"PA:{app}" for app in applicants])
                query_parts.append(f"({applicant_query})")

            if not query_parts:
                logger.warning("⚠️ 검색 조건이 없습니다")
                return []

            query_string = " AND ".join(query_parts)

            params = {
                "ServiceKey": self.api_key,
                "word": query_string,
                "patent": "true",
                "utility": "true",
                "numOfRows": str(page_size),
                "pageNo": "1",
            }

            url = f"{self.base_url.rstrip('/')}/{self.search_path.lstrip('/')}"

            logger.info(f"🔍 KIPRIS 검색 시작: url={url}, word={query_string}, max={max_results}")

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            # XML 응답 처리 (KIPRIS 기본 포맷)
            text = response.text or ""
            if "<item>" not in text:
                logger.warning("⚠️ KIPRIS 응답에 item이 없습니다")
                return []

            # 매우 단순한 XML 파싱 (필요한 필드만 추출)
            # 공식 스키마에 맞춰 body->items->item 파싱을 시도
            # 여기서는 httpx.Response.text를 활용, 후속 파이프라인에서 dict 형태 기대하므로 최소 필드만 채움
            # 추가 파싱 필요 시 xmltodict 등으로 교체 가능
            import xml.etree.ElementTree as ET

            root = ET.fromstring(text)
            items_el = root.find('.//items')
            results: List[Dict[str, Any]] = []
            if items_el is not None:
                for item_el in items_el.findall('item'):
                    def _get(tag: str) -> Optional[str]:
                        el = item_el.find(tag)
                        return el.text if el is not None else None

                    results.append({
                        "applicationNumber": _get('applicationNumber'),
                        "publicationNumber": _get('publicationNumber'),
                        "inventionTitle": _get('inventionTitle'),
                        "abstract": _get('abstract'),
                        "applicationDate": _get('applicationDate'),
                        "publicationDate": _get('publicationDate'),
                        "country": _get('countryCode'),
                        "office": _get('officeCode'),
                        "patentType": _get('patentType'),
                        "legalStatus": _get('legalStatus'),
                    })

            logger.info(f"✅ KIPRIS 검색 완료: {len(results)}건")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ KIPRIS API HTTP 오류: {e.response.status_code}, {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"❌ KIPRIS API 오류: {e}")
            return []
    
    async def get_patent_detail(self, application_number: str) -> Optional[Dict[str, Any]]:
        """
        특허 상세 정보 조회
        
        Args:
            application_number: 출원번호 (예: 1020210012345)
        
        Returns:
            특허 상세 서지정보 (dict) 또는 None
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/BibliographicService/detail",
                params={
                    "ServiceKey": self.api_key,
                    "applicationNumber": application_number
                }
            )
            response.raise_for_status()
            
            data = response.json()
            detail = data.get("response", {}).get("body", {}).get("item", {})
            
            logger.info(f"✅ 특허 상세 조회 완료: {application_number}")
            return detail
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ 특허 상세 조회 HTTP 오류: {application_number}, {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ 특허 상세 조회 실패: {application_number}, {e}")
            return None
    
    async def download_patent_pdf(
        self,
        application_number: str,
        save_path: str
    ) -> bool:
        """
        특허 PDF 다운로드
        
        Args:
            application_number: 출원번호
            save_path: 저장 경로 (예: /uploads/patents/1020210012345.pdf)
        
        Returns:
            다운로드 성공 여부
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/DocumentService/pdf",
                params={
                    "ServiceKey": self.api_key,
                    "applicationNumber": application_number
                },
                follow_redirects=True  # PDF 다운로드 리다이렉트 처리
            )
            response.raise_for_status()
            
            # 파일 저장
            from pathlib import Path
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"✅ PDF 다운로드 완료: {application_number} → {save_path}")
            return True
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ PDF 다운로드 HTTP 오류: {application_number}, {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"❌ PDF 다운로드 실패: {application_number}, {e}")
            return False
    
    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.client.aclose()
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()


# 싱글톤 인스턴스 (선택적)
_kipris_client: Optional[KIPRISClient] = None


def get_kipris_client() -> KIPRISClient:
    """
    KIPRIS 클라이언트 싱글톤 인스턴스 반환
    
    Usage:
        client = get_kipris_client()
        results = await client.search_patents(ipc_codes=["G06N"])
    """
    global _kipris_client
    if _kipris_client is None:
        _kipris_client = KIPRISClient()
    return _kipris_client

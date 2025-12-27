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
        invention_title: Optional[str] = None,
        abstract_text: Optional[str] = None,
        max_results: int = 100,
        sort: str = "application_date_desc"
    ) -> List[Dict[str, Any]]:
        """
        특허 검색 (KIPRIS Plus API - getAdvancedSearch)
        
        KIPRIS Plus API 파라미터:
            - word: 자유검색 (키워드)
            - inventionTitle: 발명의 명칭
            - astrtCont: 초록
            - ipcNumber: IPC 코드
            - applicant: 출원인명/특허고객번호
            - patent: 특허 포함 (true/false)
            - utility: 실용 포함 (true/false)
            - numOfRows: 페이지당 건수 (기본 30, 최대 500)
            - pageNo: 페이지 번호
            - sortSpec: 정렬기준 (PD-공고일자, AD-출원일자, GD-등록일자, OPD-공개일자)
            - descSort: 정렬방식 (asc: false, desc: true)
        
        Args:
            ipc_codes: IPC 분류 코드 리스트 (예: ["G06N", "G06F"])
            keywords: 키워드 리스트 (word 파라미터 - 자유검색)
            applicants: 출원인 리스트
            invention_title: 발명의 명칭 검색어
            abstract_text: 초록 검색어
            max_results: 최대 결과 수 (KIPRIS API 제한: 500건/요청)
            sort: 정렬 (application_date_desc, publication_date_desc)
        
        Returns:
            특허 서지정보 리스트
        """
        try:
            # KIPRIS API는 한 번에 최대 500건까지 조회 가능
            page_size = min(max_results, 500)

            # 정렬 설정
            sort_spec = "AD"  # 기본: 출원일자
            desc_sort = "true"  # 기본: 내림차순
            if sort == "publication_date_desc":
                sort_spec = "OPD"  # 공개일자
            elif sort == "registration_date_desc":
                sort_spec = "GD"  # 등록일자

            # API 파라미터 구성
            params = {
                "ServiceKey": self.api_key,
                "patent": "true",
                "utility": "true",
                "numOfRows": str(page_size),
                "pageNo": "1",
                "sortSpec": sort_spec,
                "descSort": desc_sort,
            }

            # 자유검색 (word) - 여러 키워드를 공백으로 연결
            if keywords:
                word_query = " ".join(keywords)
                params["word"] = word_query

            # 발명의 명칭 검색 (inventionTitle)
            if invention_title:
                params["inventionTitle"] = invention_title

            # 초록 검색 (astrtCont)
            if abstract_text:
                params["astrtCont"] = abstract_text

            # IPC 코드 검색 (ipcNumber)
            if ipc_codes:
                # IPC 코드가 여러 개면 공백으로 연결
                ipc_query = " ".join(ipc_codes)
                params["ipcNumber"] = ipc_query

            # 출원인 검색 (applicant)
            if applicants:
                # 출원인이 여러 명이면 첫 번째만 사용 (API 제한)
                params["applicant"] = applicants[0]

            # 검색 조건이 없으면 경고
            has_search_condition = any([
                params.get("word"),
                params.get("inventionTitle"),
                params.get("astrtCont"),
                params.get("ipcNumber"),
                params.get("applicant"),
            ])
            if not has_search_condition:
                logger.warning("⚠️ 검색 조건이 없습니다")
                return []

            url = f"{self.base_url.rstrip('/')}/{self.search_path.lstrip('/')}"

            # 로그에 검색 조건 상세 표시
            log_parts = []
            if params.get("word"):
                log_parts.append(f"word={params['word']}")
            if params.get("inventionTitle"):
                log_parts.append(f"inventionTitle={params['inventionTitle']}")
            if params.get("astrtCont"):
                log_parts.append(f"astrtCont={params['astrtCont']}")
            if params.get("ipcNumber"):
                log_parts.append(f"ipcNumber={params['ipcNumber']}")
            if params.get("applicant"):
                log_parts.append(f"applicant={params['applicant']}")
            logger.info(f"🔍 KIPRIS 검색 시작: {', '.join(log_parts)}, max={max_results}")

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
            
            # 응답 성공 여부 확인
            success_yn = root.find('.//successYN')
            if success_yn is None or success_yn.text != 'Y':
                result_msg = root.find('.//resultMsg')
                msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                logger.warning(f"⚠️ KIPRIS API 응답 오류: {msg}")
                return []
            
            items_el = root.find('.//items')
            results: List[Dict[str, Any]] = []
            if items_el is not None:
                for item_el in items_el.findall('item'):
                    def _get(tag: str) -> Optional[str]:
                        el = item_el.find(tag)
                        return el.text.strip() if el is not None and el.text else None

                    # KIPRIS API 응답 필드에 맞게 파싱
                    # applicantName, applicationDate, applicationNumber, astrtCont,
                    # bigDrawing, drawing, indexNo, inventionTitle, ipcNumber,
                    # openDate, openNumber, publicationDate, publicationNumber,
                    # registerDate, registerNumber, registerStatus
                    results.append({
                        "applicationNumber": _get('applicationNumber'),
                        "inventionTitle": _get('inventionTitle'),
                        "abstract": _get('astrtCont'),  # 초록은 astrtCont 필드
                        "applicantName": _get('applicantName'),
                        "applicationDate": _get('applicationDate'),
                        "openNumber": _get('openNumber'),
                        "openDate": _get('openDate'),
                        "publicationNumber": _get('publicationNumber'),
                        "publicationDate": _get('publicationDate'),
                        "registerNumber": _get('registerNumber'),
                        "registerDate": _get('registerDate'),
                        "registerStatus": _get('registerStatus'),
                        "ipcNumber": _get('ipcNumber'),
                        "bigDrawing": _get('bigDrawing'),
                        "drawing": _get('drawing'),
                    })

            # 전체 건수 확인
            total_count_el = root.find('.//totalCount')
            total_count = int(total_count_el.text) if total_count_el is not None and total_count_el.text else len(results)

            logger.info(f"✅ KIPRIS 검색 완료: {len(results)}건 (전체 {total_count}건)")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ KIPRIS API HTTP 오류: {e.response.status_code}, {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"❌ KIPRIS API 오류: {e}")
            return []
    
    async def get_patent_detail(self, application_number: str) -> Optional[Dict[str, Any]]:
        """
        특허 상세 정보 조회 (서지정보 상세)
        
        Args:
            application_number: 출원번호 (예: 1020210012345)
        
        Returns:
            특허 상세 서지정보 (dict) 또는 None
        """
        try:
            import xml.etree.ElementTree as ET
            
            url = f"{self.base_url}/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch"
            response = await self.client.get(
                url,
                params={
                    "ServiceKey": self.api_key,
                    "applicationNumber": application_number
                }
            )
            response.raise_for_status()
            
            text = response.text or ""
            if "<successYN>Y</successYN>" not in text:
                logger.warning(f"⚠️ 특허 상세 조회 실패: {application_number}")
                return None
            
            # XML 파싱
            root = ET.fromstring(text)
            item = root.find('.//item')
            if item is None:
                return None
            
            # 주요 필드 추출
            def _get(tag: str) -> Optional[str]:
                el = item.find(f'.//{tag}')
                return el.text if el is not None else None
            
            detail = {
                "applicationNumber": _get('applicationNumber'),
                "inventionTitle": _get('inventionTitle'),
                "inventionTitleEng": _get('inventionTitleEng'),
                "openNumber": _get('openNumber'),
                "openDate": _get('openDate'),
                "registerNumber": _get('registerNumber'),
                "registerDate": _get('registerDate'),
                "registerStatus": _get('registerStatus'),
                "abstract": _get('astrtCont'),
            }
            
            logger.info(f"✅ 특허 상세 조회 완료: {application_number}")
            return detail
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ 특허 상세 조회 HTTP 오류: {application_number}, {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ 특허 상세 조회 실패: {application_number}, {e}")
            return None
    
    async def get_full_text_pdf_url(self, application_number: str) -> Optional[Dict[str, str]]:
        """
        공개전문 PDF 다운로드 URL 조회
        
        Args:
            application_number: 출원번호 (예: 1020240027504)
        
        Returns:
            {"docName": "파일명", "path": "다운로드URL"} 또는 None
        """
        try:
            import xml.etree.ElementTree as ET
            
            url = f"{self.base_url}/kipi/patUtiModInfoSearchSevice/getPubFullTextInfoSearch"
            response = await self.client.get(
                url,
                params={
                    "ServiceKey": self.api_key,
                    "applicationNumber": application_number
                }
            )
            response.raise_for_status()
            
            text = response.text or ""
            if "<successYN>Y</successYN>" not in text:
                logger.warning(f"⚠️ 전문 PDF URL 조회 실패: {application_number}")
                return None
            
            # XML 파싱
            root = ET.fromstring(text)
            item = root.find('.//item')
            if item is None:
                logger.warning(f"⚠️ 전문 PDF 없음: {application_number}")
                return None
            
            doc_name = item.find('docName')
            path = item.find('path')
            
            if path is None or not path.text:
                logger.warning(f"⚠️ 전문 PDF URL 없음: {application_number}")
                return None
            
            result = {
                "docName": doc_name.text if doc_name is not None else f"{application_number}.pdf",
                "path": path.text
            }
            
            logger.info(f"✅ 전문 PDF URL 조회 완료: {application_number} → {result['docName']}")
            return result
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ 전문 PDF URL 조회 HTTP 오류: {application_number}, {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ 전문 PDF URL 조회 실패: {application_number}, {e}")
            return None
    
    async def download_full_text_pdf(
        self,
        application_number: str,
        save_path: str
    ) -> bool:
        """
        공개전문 PDF 다운로드
        
        1. getPubFullTextInfoSearch로 다운로드 URL 조회
        2. 해당 URL에서 PDF 다운로드
        3. save_path에 저장
        
        Args:
            application_number: 출원번호
            save_path: 저장 경로 (예: /uploads/patents/1020210012345.pdf)
        
        Returns:
            다운로드 성공 여부
        """
        try:
            from pathlib import Path
            
            # 1. PDF URL 조회
            pdf_info = await self.get_full_text_pdf_url(application_number)
            if not pdf_info:
                logger.warning(f"⚠️ PDF URL을 찾을 수 없음: {application_number}")
                return False
            
            pdf_url = pdf_info["path"]
            logger.info(f"📥 PDF 다운로드 시작: {application_number} from {pdf_url[:60]}...")
            
            # 2. PDF 다운로드
            response = await self.client.get(pdf_url, follow_redirects=True)
            response.raise_for_status()
            
            # PDF 유효성 확인
            if not response.content or response.content[:4] != b'%PDF':
                logger.error(f"❌ 유효하지 않은 PDF: {application_number}")
                return False
            
            # 3. 파일 저장
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, "wb") as f:
                f.write(response.content)
            
            file_size = len(response.content) / 1024  # KB
            logger.info(f"✅ PDF 다운로드 완료: {application_number} → {save_path} ({file_size:.1f} KB)")
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

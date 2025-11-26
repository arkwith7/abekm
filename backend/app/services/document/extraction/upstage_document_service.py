"""
Upstage Document Parse API 서비스

한국어 문서 처리에 최적화된 Upstage Document Parse API 통합
- Layout Analysis (레이아웃 분석)
- Table Detection & Extraction (테이블 추출)
- Figure Detection (이미지 추출)
- OCR (한국어 최적화)
- Azure Document Intelligence 대안

API Documentation: https://console.upstage.ai/docs
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any

import requests
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class UpstageResult:
    """Upstage Document Parse 결과를 담는 데이터 클래스"""
    
    def __init__(
        self,
        success: bool = True,
        text: str = "",
        markdown: str = "",  # 🆕 마크다운 추가
        html: str = "",      # 🆕 HTML 추가
        pages: Optional[List[Dict[str, Any]]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
        figures: Optional[List[Dict[str, Any]]] = None,
        elements: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        extraction_method: str = "upstage_document_parse"
    ):
        self.success = success
        self.text = text
        self.markdown = markdown  # 🆕
        self.html = html          # 🆕
        self.pages = pages or []
        self.tables = tables or []
        self.figures = figures or []
        self.elements = elements or []
        self.metadata = metadata or {}
        self.error = error
        self.extraction_method = extraction_method


class UpstageDocumentService:
    """Upstage Document Parse API 클라이언트"""
    
    def __init__(self):
        self.api_key = settings.upstage_api_key
        self.api_endpoint = settings.upstage_api_endpoint
        self.max_pages = settings.upstage_max_pages
        self.timeout_seconds = settings.upstage_timeout_seconds
        self.retry_max_attempts = settings.upstage_retry_max_attempts
        self.model = settings.upstage_model
        self.ocr_mode = settings.upstage_ocr_mode
        self.base64_categories = settings.upstage_base64_categories or []
        self.merge_multipage_tables = settings.upstage_merge_multipage_tables
        self.use_async_api = settings.upstage_use_async_api
        self.async_poll_interval = settings.upstage_async_poll_interval_seconds
        self.async_timeout_seconds = settings.upstage_async_timeout_seconds
        self.async_endpoint = settings.upstage_async_api_endpoint or self._infer_async_endpoint(self.api_endpoint)
        self.status_endpoint = settings.upstage_async_status_endpoint or self._infer_status_endpoint(self.api_endpoint)
        
        # 초기화 로그 (디버깅용)
        logger.info(f"[UPSTAGE] UpstageDocumentService 초기화")
        logger.info(f"[UPSTAGE] API Endpoint: {self.api_endpoint}")
        logger.info(f"[UPSTAGE] API Key 설정 여부: {bool(self.api_key)}")
        logger.info(f"[UPSTAGE] Max Pages: {self.max_pages}")
        logger.info(f"[UPSTAGE] Timeout: {self.timeout_seconds}s")
        logger.info(f"[UPSTAGE] Retry Attempts: {self.retry_max_attempts}")
        logger.info(f"[UPSTAGE] Model Alias: {self.model}")
        logger.info(f"[UPSTAGE] OCR Mode: {self.ocr_mode or 'auto'}")
        if self.base64_categories:
            logger.info(f"[UPSTAGE] Base64 Encoding Targets: {self.base64_categories}")
        logger.info(f"[UPSTAGE] Merge Multipage Tables: {self.merge_multipage_tables}")
        logger.info(
            f"[UPSTAGE] Async API Enabled: {self.use_async_api and self._supports_async_api()}"
        )
        
        if not self.api_key:
            logger.error("[UPSTAGE] ❌ API 키가 설정되지 않았습니다. UPSTAGE_API_KEY 환경 변수를 확인하세요.")
        else:
            logger.info(f"[UPSTAGE] ✅ API 키 설정 완료 (길이: {len(self.api_key)}자)")

    def _infer_async_endpoint(self, endpoint: Optional[str]) -> Optional[str]:
        if not endpoint:
            return None
        base = endpoint.rstrip('/')
        if base.endswith("/document-digitization"):
            return f"{base}/async"
        return None

    def _infer_status_endpoint(self, endpoint: Optional[str]) -> Optional[str]:
        if not endpoint:
            return None
        base = endpoint.rstrip('/')
        if base.endswith("/document-digitization"):
            return f"{base}/requests"
        return None

    def _supports_async_api(self) -> bool:
        return bool(self.async_endpoint and self.status_endpoint)

    def _build_request_payload(self) -> Dict[str, str]:
        payload: Dict[str, str] = {}
        if self.model:
            payload["model"] = self.model
        if self.ocr_mode:
            payload["ocr"] = self.ocr_mode
        # 🆕 마크다운 형식 요청 (섹션 구조 보존)
        payload["output_formats"] = "html,markdown,text"
        if self.base64_categories:
            try:
                payload["base64_encoding"] = json.dumps(self.base64_categories)
            except Exception:
                payload["base64_encoding"] = str(self.base64_categories)
        if self.merge_multipage_tables is not None:
            payload["merge_multipage_tables"] = str(self.merge_multipage_tables).lower()
        return payload
    
    async def parse_document(self, file_path: str) -> UpstageResult:
        """
        문서를 분석하여 텍스트, 테이블, 이미지를 추출합니다.
        
        Args:
            file_path: PDF 파일 경로
            
        Returns:
            UpstageResult: 추출 결과
        """
        if not self.api_key:
            logger.error("[UPSTAGE] ❌ API 키가 설정되지 않았습니다.")
            return UpstageResult(
                success=False,
                error="Upstage API 키가 설정되지 않았습니다."
            )
        
        if not Path(file_path).exists():
            logger.error(f"[UPSTAGE] ❌ 파일을 찾을 수 없습니다: {file_path}")
            return UpstageResult(
                success=False,
                error=f"파일을 찾을 수 없습니다: {file_path}"
            )
        
        file_size = Path(file_path).stat().st_size
        logger.info(f"[UPSTAGE] 🚀 문서 분석 시작")
        logger.info(f"[UPSTAGE]    📄 파일: {Path(file_path).name}")
        logger.info(f"[UPSTAGE]    📊 크기: {file_size / 1024:.2f} KB")
        logger.info(f"[UPSTAGE]    🔧 설정: max_pages={self.max_pages}, timeout={self.timeout_seconds}s, retry={self.retry_max_attempts}")
        
        start_time = time.time()
        
        try:
            # API 호출 (재시도 로직 포함)
            result = await self._call_api_with_retry(file_path)
            
            elapsed = time.time() - start_time
            
            if result.success:
                logger.info(f"[UPSTAGE] ✅ 문서 분석 완료: {elapsed:.2f}초")
                logger.info(f"[UPSTAGE]    📊 통계:")
                logger.info(f"[UPSTAGE]       - 페이지 수: {result.metadata.get('page_count', len(result.pages))}")
                logger.info(f"[UPSTAGE]       - 테이블 수: {result.metadata.get('table_count', len(result.tables))}")
                logger.info(f"[UPSTAGE]       - 이미지 수: {result.metadata.get('figure_count', len(result.figures))}")
                logger.info(f"[UPSTAGE]       - 텍스트 길이: {len(result.text)} 문자")
                logger.info(f"[UPSTAGE]       - 모델: {result.metadata.get('model', 'unknown')}")
            else:
                logger.error(f"[UPSTAGE] ❌ 문서 분석 실패: {elapsed:.2f}초, error={result.error}")
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[UPSTAGE] ❌ 문서 분석 예외 발생: {elapsed:.2f}초", exc_info=True)
            logger.error(f"[UPSTAGE]    오류: {type(e).__name__}: {str(e)}")
            return UpstageResult(
                success=False,
                error=str(e)
            )
    
    async def _call_api_with_retry(self, file_path: str) -> UpstageResult:
        """재시도 로직을 포함한 API 호출"""
        
        last_error = None
        retry_reasons = []
        
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                if attempt == 1:
                    logger.info(f"[UPSTAGE] 🔄 API 호출 시도 {attempt}/{self.retry_max_attempts}")
                else:
                    logger.warning(f"[UPSTAGE] 🔄 재시도 {attempt}/{self.retry_max_attempts} (이전 실패: {last_error})")
                
                call_start = time.time()
                
                # 비동기 HTTP 요청을 동기 방식으로 실행 (requests 사용)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._call_api_sync,
                    file_path
                )
                
                call_elapsed = time.time() - call_start
                
                if result.success:
                    logger.info(f"[UPSTAGE] ✅ API 호출 성공: {call_elapsed:.2f}초 (시도 {attempt}/{self.retry_max_attempts})")
                    return result
                else:
                    last_error = result.error
                    retry_reasons.append(f"Attempt {attempt}: {last_error}")
                    logger.warning(f"[UPSTAGE] ⚠️ API 호출 실패: {call_elapsed:.2f}초, error={last_error}")
                    
                    # 🆕 413 오류 시 즉시 중단 (재시도해도 해결 불가능)
                    if '413' in str(last_error) or 'too large' in str(last_error).lower():
                        logger.error(f"[UPSTAGE] 🚫 파일 크기 제한 초과 (HTTP 413) - 재시도 중단")
                        return result
                    
            except Exception as e:
                last_error = str(e)
                retry_reasons.append(f"Attempt {attempt}: {type(e).__name__}: {str(e)}")
                logger.warning(f"[UPSTAGE] ⚠️ API 호출 예외: 시도 {attempt}, error={e}")
                
                # 🆕 413 오류 시 즉시 중단
                if '413' in str(e):
                    logger.error(f"[UPSTAGE] 🚫 파일 크기 제한 초과 (HTTP 413) - 재시도 중단")
                    return UpstageResult(success=False, error=str(e))
            
            # 재시도 전 대기 (백오프)
            if attempt < self.retry_max_attempts:
                wait_time = attempt * 2  # 2초, 4초, 6초...
                logger.info(f"[UPSTAGE] ⏳ {wait_time}초 대기 후 재시도...")
                await asyncio.sleep(wait_time)
        
        logger.error(f"[UPSTAGE] ❌ 최대 재시도 횟수 초과 ({self.retry_max_attempts}회)")
        logger.error(f"[UPSTAGE]    재시도 히스토리: {retry_reasons}")
        
        return UpstageResult(
            success=False,
            error=f"최대 재시도 횟수 초과 ({self.retry_max_attempts}회): {last_error}"
        )
    
    def _call_api_sync(self, file_path: str) -> UpstageResult:
        """동기/비동기 API 호출 진입점"""
        if self.use_async_api and self._supports_async_api():
            logger.info("[UPSTAGE] 🌀 Async Document Digitization API 사용")
            return self._call_async_document_parse(file_path)
        return self._call_sync_document_parse(file_path)

    def _call_sync_document_parse(self, file_path: str) -> UpstageResult:
        """동기 방식 API 호출 (requests 사용)"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key[:20]}...",  # API 키 일부만 로깅
        }
        
        file_name = Path(file_path).name
        file_size = Path(file_path).stat().st_size
        
        logger.debug(f"[UPSTAGE] 📤 HTTP POST 요청 준비")
        logger.debug(f"[UPSTAGE]    Endpoint: {self.api_endpoint}")
        logger.debug(f"[UPSTAGE]    File: {file_name} ({file_size / 1024:.2f} KB)")
        
        try:
            request_start = time.time()
            
            with open(file_path, "rb") as f:
                files = {
                    "document": (file_name, f, "application/pdf")
                }
                
                logger.debug(f"[UPSTAGE] 📡 HTTP 요청 전송 중... (timeout={self.timeout_seconds}s)")
                
                response = requests.post(
                    self.api_endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},  # 실제 요청에는 전체 키 사용
                    data=self._build_request_payload(),
                    files=files,
                    timeout=self.timeout_seconds
                )
            
            request_elapsed = time.time() - request_start
            logger.info(f"[UPSTAGE] 📥 HTTP 응답 수신: {response.status_code} ({request_elapsed:.2f}초)")
            
            # HTTP 오류 체크
            response.raise_for_status()
            
            # JSON 응답 파싱
            response_size = len(response.content)
            logger.debug(f"[UPSTAGE] 📊 응답 크기: {response_size / 1024:.2f} KB")
            
            data = response.json()
            logger.debug(f"[UPSTAGE] 🔍 JSON 파싱 완료, 응답 파싱 시작...")
            
            # 결과 변환
            return self._parse_response(data)
            
        except requests.exceptions.Timeout:
            logger.error(f"[UPSTAGE] ⏱️ API 요청 타임아웃: {self.timeout_seconds}초 초과")
            return UpstageResult(
                success=False,
                error=f"API 요청 타임아웃 ({self.timeout_seconds}초 초과)"
            )
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text[:500] if e.response else "No response"
            logger.error(f"[UPSTAGE] 🚫 HTTP 오류: {e.response.status_code}")
            logger.error(f"[UPSTAGE]    응답: {error_text}")
            return UpstageResult(
                success=False,
                error=f"HTTP 오류: {e.response.status_code} - {error_text}"
            )
        except Exception as e:
            logger.error(f"[UPSTAGE] ❌ API 호출 예외: {type(e).__name__}: {str(e)}")
            return UpstageResult(
                success=False,
                error=f"API 호출 실패: {str(e)}"
            )

    def _call_async_document_parse(self, file_path: str) -> UpstageResult:
        if not self._supports_async_api():
            logger.warning("[UPSTAGE] ⚠️ Async API 정보가 없어 동기 API로 폴백합니다.")
            return self._call_sync_document_parse(file_path)

        file_name = Path(file_path).name
        logger.info(f"[UPSTAGE] 📨 Async 요청 전송: endpoint={self.async_endpoint}, file={file_name}")

        try:
            with open(file_path, "rb") as f:
                files = {"document": (file_name, f, "application/pdf")}
                response = requests.post(
                    self.async_endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=self._build_request_payload(),
                    files=files,
                    timeout=self.timeout_seconds
                )

            response.raise_for_status()
            submission = response.json()
            request_id = submission.get("request_id") or submission.get("id")
            if not request_id:
                logger.error(f"[UPSTAGE] ❌ Async 응답에 request_id가 없습니다: {submission}")
                return UpstageResult(success=False, error="Async 응답에 request_id가 없습니다")

            logger.info(f"[UPSTAGE] 🆔 Async request_id={request_id}")
            detail = self._poll_async_request(request_id)
            merged_payload = self._collect_async_batches(detail)
            # detail 메타데이터 보강
            merged_payload.setdefault("model", detail.get("model"))
            merged_payload.setdefault("usage", {"pages": detail.get("total_pages")})
            merged_payload.setdefault("api", detail.get("api"))
            return self._parse_response(merged_payload)

        except requests.exceptions.Timeout:
            logger.error("[UPSTAGE] ⏱️ Async API 요청 타임아웃")
            return UpstageResult(success=False, error="Async API 요청 타임아웃")
        except Exception as e:
            logger.error(f"[UPSTAGE] ❌ Async API 처리 중 오류: {type(e).__name__}: {str(e)}", exc_info=True)
            return UpstageResult(success=False, error=f"Async API 실패: {str(e)}")

    def _poll_async_request(self, request_id: str) -> Dict[str, Any]:
        status_url = f"{self.status_endpoint.rstrip('/')}/{request_id}"
        deadline = time.time() + self.async_timeout_seconds
        logger.info(f"[UPSTAGE] ⏳ Async 상태 조회 시작 (timeout={self.async_timeout_seconds}s)")

        while time.time() < deadline:
            resp = requests.get(
                status_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_seconds
            )
            resp.raise_for_status()
            detail = resp.json()
            status = (detail.get("status") or "").lower()
            logger.info(f"[UPSTAGE] 📡 Async status={status} completed_pages={detail.get('completed_pages')} / {detail.get('total_pages')}")

            if status == "completed":
                return detail
            if status in {"failed", "error"}:
                failure_message = detail.get("failure_message") or "알 수 없는 오류"
                raise RuntimeError(f"Async 작업 실패: {failure_message}")

            time.sleep(self.async_poll_interval)

        raise TimeoutError("Async 작업이 지정된 시간 내에 완료되지 않았습니다")

    def _collect_async_batches(self, request_detail: Dict[str, Any]) -> Dict[str, Any]:
        batches = request_detail.get("batches") or []
        if not batches:
            raise RuntimeError("Async 응답에 batch 정보가 없습니다")

        payloads: List[Dict[str, Any]] = []
        for batch in batches:
            if (batch.get("status") or "").lower() != "completed":
                logger.warning(f"[UPSTAGE] ⚠️ batch {batch.get('id')} 상태={batch.get('status')} - 건너뜀")
                continue
            download_url = batch.get("download_url")
            if not download_url:
                logger.warning(f"[UPSTAGE] ⚠️ batch {batch.get('id')} 다운로드 URL 없음")
                continue
            logger.info(f"[UPSTAGE] 📥 batch {batch.get('id')} 다운로드")
            resp = requests.get(download_url, timeout=self.timeout_seconds)
            resp.raise_for_status()
            payloads.append(resp.json())

        if not payloads:
            raise RuntimeError("다운로드한 batch 결과가 없습니다")

        if len(payloads) == 1:
            return payloads[0]
        return self._merge_batch_payloads(payloads)

    def _merge_batch_payloads(self, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        merged = payloads[0]
        merged_content = merged.setdefault("content", {})
        for batch in payloads[1:]:
            content = batch.get("content") or {}
            for key in ("pages", "tables", "figures", "elements"):
                if key in content:
                    merged_content.setdefault(key, [])
                    merged_content[key].extend(content.get(key) or [])
            for key in ("text", "html", "markdown"):
                value = content.get(key)
                if value:
                    existing = merged_content.get(key, "")
                    merged_content[key] = f"{existing}\n{value}".strip() if existing else value
        return merged

    def _build_pages(self, content: Dict[str, Any], elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pages: List[Dict[str, Any]] = []
        page_entries = content.get("pages") if isinstance(content, dict) else None
        if isinstance(page_entries, list) and page_entries:
            logger.info(f"[UPSTAGE] 📄 페이지 데이터 {len(page_entries)}건 파싱")
            for page in page_entries:
                if not isinstance(page, dict):
                    continue
                text_value = page.get("text") or page.get("html") or page.get("content") or ""
                pages.append({
                    "page_number": page.get("page") or page.get("page_number") or 0,
                    "text": text_value,
                    "width": page.get("width", 0),
                    "height": page.get("height", 0)
                })
            return pages

        # elements 기반 재구성
        text_by_page: Dict[int, List[str]] = defaultdict(list)
        for elem in elements:
            page_num = int(elem.get("page") or 0)
            elem_text = elem.get("text")
            if elem_text:
                text_by_page[page_num].append(elem_text)

        for page_num in sorted(text_by_page.keys()):
            combined_text = "\n".join(text_by_page[page_num]).strip()
            pages.append({
                "page_number": page_num,
                "text": combined_text,
                "width": 0,
                "height": 0
            })
        return pages

    def _compose_text_from_pages(self, pages: List[Dict[str, Any]]) -> str:
        segments = [p.get("text", "").strip() for p in pages if p.get("text")]
        return "\n\n".join(segments).strip()

    def _compose_text_from_elements(self, elements: List[Dict[str, Any]]) -> str:
        segments = [elem.get("text", "").strip() for elem in elements if elem.get("text")]
        return "\n".join(segments).strip()

    def _normalize_elements(self, raw_elements: Optional[List[Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        if not isinstance(raw_elements, list):
            return normalized
        for elem in raw_elements:
            if not isinstance(elem, dict):
                continue
            normalized.append({
                "id": elem.get("id"),
                "category": elem.get("category") or elem.get("type"),
                "page": elem.get("page") or elem.get("page_number") or elem.get("pageIndex") or 0,
                "text": self._resolve_content_field(elem, "text"),
                "markdown": self._resolve_content_field(elem, "markdown"),
                "html": self._resolve_content_field(elem, "html"),
                "coordinates": elem.get("coordinates") or elem.get("bbox"),
                "base64_encoding": elem.get("base64_encoding"),
                "confidence": elem.get("confidence")
            })
        return normalized

    def _resolve_content_field(self, elem: Dict[str, Any], field: str) -> str:
        value = elem.get(field)
        if isinstance(value, str):
            return value
        content_obj = elem.get("content")
        if isinstance(content_obj, dict):
            inner_val = content_obj.get(field)
            if isinstance(inner_val, str):
                return inner_val
        return ""

    def _extract_tables(self, content: Dict[str, Any], elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tables: List[Dict[str, Any]] = []
        
        # 🎯 우선순위: elements에서 추출 (페이지 정보 포함)
        table_categories = {"table", "table_continued", "table_header", "table_body"}
        elements_tables = []
        for elem in elements:
            category = (elem.get("category") or "").lower()
            if category in table_categories:
                elements_tables.append({
                    "table_index": len(elements_tables),
                    "page": elem.get("page", 0),
                    "bbox": elem.get("coordinates", []),
                    "html": elem.get("html", ""),
                    "markdown": elem.get("markdown", ""),
                    "text": elem.get("text", ""),
                    "element_id": elem.get("id"),
                    "base64": elem.get("base64_encoding")
                })
        
        # elements에서 테이블을 찾았으면 우선 사용
        if elements_tables:
            return elements_tables
        
        # Fallback: content["tables"] 사용 (페이지 정보 없을 수 있음)
        table_entries = content.get("tables") if isinstance(content, dict) else None
        if isinstance(table_entries, list):
            for idx, table in enumerate(table_entries):
                if not isinstance(table, dict):
                    continue
                tables.append({
                    "table_index": idx,
                    "page": table.get("page", 0),
                    "bbox": table.get("bbox", []),
                    "html": table.get("html", ""),
                    "markdown": table.get("markdown", ""),
                    "text": table.get("text")
                })
        return tables

    def _extract_figures(self, content: Dict[str, Any], elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        figures: List[Dict[str, Any]] = []
        
        # 🎯 우선순위: elements에서 추출 (페이지 정보 포함)
        figure_categories = {"figure", "chart", "image", "diagram"}
        elements_figures = []
        for elem in elements:
            category = (elem.get("category") or "").lower()
            if category in figure_categories:
                elements_figures.append({
                    "figure_index": len(elements_figures),
                    "page": elem.get("page", 0),
                    "bbox": elem.get("coordinates", []),
                    "caption": elem.get("text", ""),
                    "image": None,
                    "base64": elem.get("base64_encoding"),
                    "element_id": elem.get("id")
                })
        
        # elements에서 figure를 찾았으면 우선 사용
        if elements_figures:
            return elements_figures
        
        # Fallback: content["figures"] 사용 (페이지 정보 없을 수 있음)
        figure_entries = content.get("figures") if isinstance(content, dict) else None
        if isinstance(figure_entries, list):
            for idx, figure in enumerate(figure_entries):
                if not isinstance(figure, dict):
                    continue
                figures.append({
                    "figure_index": idx,
                    "page": figure.get("page", 0),
                    "bbox": figure.get("bbox", []),
                    "caption": figure.get("caption", ""),
                    "image": figure.get("image"),
                    "base64": figure.get("base64_encoding")
                })
        return figures
    
    def _parse_response(self, data: Dict[str, Any]) -> UpstageResult:
        """Upstage API 응답을 내부 형식으로 변환 (이미지 PDF, 일반 PDF 모두 지원)"""
        
        try:
            logger.info(f"[UPSTAGE] 📋 전체 응답 키: {list(data.keys())}")
            content = data.get("content") or data.get("data") or data.get("result") or {}
            if not isinstance(content, dict):
                logger.warning(f"[UPSTAGE] ⚠️ 예상치 못한 content 타입: {type(content)}")
                content = {}

            logger.info(f"[UPSTAGE] 📋 content 키: {list(content.keys())}")

            document_html = content.get("html")
            document_markdown = content.get("markdown")
            document_text = (content.get("text") or "").strip()

            raw_elements = content.get("elements") or data.get("elements")
            normalized_elements = self._normalize_elements(raw_elements)
            logger.info(f"[UPSTAGE] 📎 요소 수: {len(normalized_elements)}")

            pages = self._build_pages(content, normalized_elements)
            full_text = document_text or self._compose_text_from_pages(pages)
            if not full_text:
                full_text = self._compose_text_from_elements(normalized_elements)

            tables = self._extract_tables(content, normalized_elements)
            figures = self._extract_figures(content, normalized_elements)

            usage = data.get("usage", {})
            # 🎯 페이지 수: usage['pages'] 우선, 없으면 pages 리스트 길이
            page_count = usage.get("pages", len(pages)) if usage else len(pages)
            
            metadata = {
                "model": data.get("model", "unknown"),
                "usage": usage,
                "page_count": page_count,
                "table_count": len(tables),
                "figure_count": len(figures),
                "api_version": data.get("api", "unknown"),
                "html": document_html or "",      # 🆕 키 이름 단순화
                "markdown": document_markdown or "",  # 🆕 키 이름 단순화
                "element_count": len(normalized_elements)
            }

            if len(full_text) < 10 and not pages and not tables and not figures:
                logger.warning("[UPSTAGE] ⚠️ 추출된 정보가 거의 없습니다. 응답 구조를 확인하세요.")
                logger.warning(f"[UPSTAGE]    응답 샘플: {str(data)[:300]}...")

            logger.info("[UPSTAGE] ✅ 응답 파싱 완료")
            logger.info(f"[UPSTAGE]    📊 최종 통계: 페이지={page_count}, 테이블={len(tables)}, Figure={len(figures)}, 텍스트={len(full_text)}자")
            if usage:
                logger.info(f"[UPSTAGE]       - Usage: {usage}")

            return UpstageResult(
                success=True,
                text=full_text.strip(),
                markdown=document_markdown or "",  # 🆕 마크다운 전달
                html=document_html or "",          # 🆕 HTML 전달
                pages=pages,
                tables=tables,
                figures=figures,
                elements=normalized_elements,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"[UPSTAGE] ❌ 응답 파싱 실패: {type(e).__name__}: {str(e)}", exc_info=True)
            logger.error(f"[UPSTAGE]    응답 데이터 샘플: {str(data)[:500]}...")
            return UpstageResult(
                success=False,
                error=f"응답 파싱 실패: {str(e)}"
            )
    
    async def analyze_pdf(self, file_path: str) -> UpstageResult:
        """
        PDF 문서 분석 (Azure DI analyze_pdf와 동일한 인터페이스)
        
        Azure Document Intelligence Service의 analyze_pdf 메서드와
        완전히 동일한 시그니처를 제공하여 text_extractor_service.py에서
        투명하게 교체 가능하도록 합니다.
        
        Args:
            file_path: PDF 파일 경로
            
        Returns:
            UpstageResult: 추출 결과 (DocumentIntelligenceResult와 호환)
        """
        logger.info(f"[UPSTAGE] 🔄 analyze_pdf 호출됨 (Azure DI 호환 인터페이스)")
        return await self.parse_document(file_path)
    
    def create_internal_extraction_result(self, upstage_result: UpstageResult) -> Dict[str, Any]:
        """
        Upstage 결과를 내부 extraction result 형식으로 변환
        (text_extractor_service.py와 호환)
        
        Azure DI의 create_internal_extraction_result와 동일한 형식 반환
        """
        
        logger.debug(f"[UPSTAGE] 🔧 내부 extraction result 형식으로 변환 중...")
        
        if not upstage_result.success:
            logger.warning(f"[UPSTAGE] ⚠️ 실패한 결과를 변환: {upstage_result.error}")
            return {
                "text": "",
                "metadata": {},
                "success": False,
                "error": upstage_result.error,
                "text_length": 0,
                "extraction_method": "upstage_document_parse"
            }
        
        logger.info(f"[UPSTAGE] ✅ 성공한 결과를 변환:")
        logger.info(f"[UPSTAGE]    - 페이지: {len(upstage_result.pages)}")
        logger.info(f"[UPSTAGE]    - 테이블: {len(upstage_result.tables)}")
        logger.info(f"[UPSTAGE]    - Figure: {len(upstage_result.figures)}")
        logger.info(f"[UPSTAGE]    - 텍스트 길이: {len(upstage_result.text)}")
        
        return {
            "text": upstage_result.text,
            "metadata": {
                "provider": "upstage",  # 🎯 Provider 정보 추가 (multimodal_document_service에서 사용)
                "page_count": len(upstage_result.pages),
                "table_count": len(upstage_result.tables),
                "figure_count": len(upstage_result.figures),
                "extraction_method": "upstage_document_parse",
                "upstage_model": upstage_result.metadata.get("model", "unknown"),
                "pages": upstage_result.pages,
                "tables": upstage_result.tables,
                "figures": upstage_result.figures,
                "elements": upstage_result.elements
            },
            "success": True,
            "error": None,
            "text_length": len(upstage_result.text),
            "extraction_method": "upstage_document_parse"
        }


# 싱글톤 인스턴스
# 🎯 싱글톤 인스턴스 생성 (모듈 import 시 자동 초기화)
logger.info("[UPSTAGE] 🔷 upstage_document_service 싱글톤 인스턴스 생성 시작")
upstage_document_service = UpstageDocumentService()
logger.info("[UPSTAGE] 🔷 upstage_document_service 싱글톤 인스턴스 생성 완료")

"""
Azure Document Intelligence (DI) 서비스

SDK 4.x 마이그레이션 (2025-03-26 GA):
 - azure-ai-documentintelligence (4.x) 사용
 - DocumentIntelligenceClient로 변경 (기존 DocumentAnalysisClient 대체)
 - DocumentAnalysisFeature → DocumentContentElement 로 변경
 - FIGURES 기능 지원 (Layout v4.0+)
 - prebuilt-document (또는 설정된 기본 모델) 1차 호출로 페이지/라인 추출
 - 필요 시 prebuilt-layout 재호출하여 테이블 구조 및 Figure 추출 (2-pass)
 - 컬럼(다단) 문서 정렬: 좌표 기반 경량 1D k-means 휴리스틱 적용
 - 테이블 셀 그리드 재구성 및 페이지 번호 추정
 - 서비스 결과를 기존 통합 파이프라인에서 소비 가능한 구조(DocumentIntelligenceResult)로 유지
 - 404/모델 미지원/일시 오류 재시도 로직 단순화

주의:
 - settings.azure_document_intelligence_default_model 이 prebuilt-read 인 경우
     가급적 prebuilt-document 로 자동 폴백 시도 후 실패 시 입력값 사용
 - API 버전 2024-11-30 이상 권장 (FIGURES 지원)
 - analyze_pdf() 외부 시그니처는 유지 (기존 코드 호환)
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError
from azure.core.polling import LROPoller

from app.core.config import settings

logger = logging.getLogger(__name__)

# Azure Document Intelligence 4.x SDK (GA)
try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient  # type: ignore
    from azure.ai.documentintelligence.models import DocumentAnalysisFeature, AnalyzeOutputOption  # type: ignore
    SDK_VERSION = "4.x"
    logger.info("[AZURE-DI] azure-ai-documentintelligence 4.x SDK 로드 성공")
except Exception as e4x:
    logger.warning(f"[AZURE-DI] azure-ai-documentintelligence 4.x 로드 실패: {e4x}")
    # Fallback to 3.3.x (FormRecognizer)
    try:
        from azure.ai.formrecognizer import DocumentAnalysisClient as DocumentIntelligenceClient  # type: ignore
        DocumentAnalysisFeature = None  # type: ignore
        AnalyzeOutputOption = None  # type: ignore
        SDK_VERSION = "3.3.x"
        logger.warning("[AZURE-DI] Fallback to azure-ai-formrecognizer 3.3.x (FIGURES 미지원)")
    except Exception as e3x:
        logger.error(f"[AZURE-DI] 모든 SDK 로드 실패: {e3x}")
        DocumentIntelligenceClient = None  # type: ignore
        DocumentAnalysisFeature = None  # type: ignore
        AnalyzeOutputOption = None  # type: ignore
        SDK_VERSION = "none"


class DocumentIntelligenceResult:
    """Document Intelligence 결과를 담는 데이터 클래스"""
    
    def __init__(
        self,
        success: bool = True,
        text: str = "",
        pages: Optional[List[Dict[str, Any]]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
        figures: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        extraction_method: str = "azure_document_intelligence"
    ):
        self.success = success
        self.text = text
        self.pages = pages or []
        self.tables = tables or []
        self.figures = figures or []
        self.metadata = metadata or {}
        self.error = error
        self.extraction_method = extraction_method


class AzureDocumentIntelligenceService:
    """Azure Document Intelligence API 클라이언트 래퍼"""
    
    def __init__(self):
        # Azure SDK HTTP 로깅 최소화 (Document Intelligence 호출 시 request/response 로그 억제)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

        self.endpoint = settings.azure_document_intelligence_endpoint
        self.api_key = settings.azure_document_intelligence_api_key
        self.api_version = settings.azure_document_intelligence_api_version
        self.default_model = settings.azure_document_intelligence_default_model
        self.layout_model = settings.azure_document_intelligence_layout_model
        self.max_pages = settings.azure_document_intelligence_max_pages
        self.timeout_seconds = settings.azure_document_intelligence_timeout_seconds
        self.retry_max_attempts = settings.azure_document_intelligence_retry_max_attempts
        self.confidence_threshold = settings.azure_document_intelligence_confidence_threshold

        self.enabled_features = self._resolve_enabled_features()
        self.enabled_outputs = self._resolve_enabled_outputs()

        # 내부 클라이언트 초기화
        # NOTE: 일부 환경에서 클래스 내부 PEP526 주석 처리 문제가 되어 단순 할당 사용
        self._client = None  # type: ignore
        self._init_client()
    
    def _init_client(self):
        """Document Intelligence 4.x 클라이언트 초기화"""
        if not self.endpoint:
            logger.warning("Azure Document Intelligence endpoint 미설정")
            return
        if DocumentIntelligenceClient is None:
            logger.error("azure-ai-documentintelligence 패키지가 설치되지 않았습니다.")
            return
        try:
            if self.api_key:
                credential = AzureKeyCredential(self.api_key)
            else:
                raise RuntimeError("API Key가 설정되지 않았습니다. .env 확인")
            
            # 4.x SDK는 api_version을 초기화 시 전달할 수 없음 (요청 시 설정)
            self._client = DocumentIntelligenceClient(
                endpoint=self.endpoint.rstrip('/'), 
                credential=credential
            )
            logger.info(f"[AZURE-DI] Document Intelligence 클라이언트 초기화 완료: SDK={SDK_VERSION}, endpoint={self.endpoint}")
        except Exception as e:
            logger.error(f"클라이언트 초기화 실패: {e}")
            self._client = None

    def _resolve_enabled_features(self) -> List[Any]:
        """DI 4.x에서 기본 활성화할 분석 feature 목록 구성"""
        if DocumentAnalysisFeature is None:
            return []

        features: List[Any] = []
        for feature_name in ("STYLE_FONT", "LANGUAGES", "FORMULAS"):
            feature_value = getattr(DocumentAnalysisFeature, feature_name, None)
            if feature_value:
                features.append(feature_value)

        if features:
            logger.info("[AZURE-DI] 활성화된 features=%s", [getattr(f, "value", str(f)) for f in features])
        return features

    def _resolve_enabled_outputs(self) -> List[Any]:
        """DI 4.x analyze output 옵션 구성 (FIGURES 등)"""
        if 'AnalyzeOutputOption' not in globals() or AnalyzeOutputOption is None:
            return []

        outputs: List[Any] = []
        option_figures = getattr(AnalyzeOutputOption, "FIGURES", None)
        if option_figures:
            outputs.append(option_figures)

        if outputs:
            logger.info("[AZURE-DI] 활성화된 output 옵션=%s", [getattr(o, "value", str(o)) for o in outputs])
        return outputs
    
    def is_available(self) -> bool:
        """Document Intelligence 서비스 사용 가능 여부 확인"""
        return bool(self._client and settings.use_azure_document_intelligence_pdf and self.endpoint)
    
    async def analyze_pdf(
        self,
        file_path: str,
        model: Optional[str] = None,
        pages: Optional[List[int]] = None,
    ) -> DocumentIntelligenceResult:
        """
        PDF 파일을 Azure Document Intelligence로 분석
        
        Args:
            file_path: PDF 파일 경로
            model: 사용할 모델 (기본값: prebuilt-layout)
            pages: 분석할 페이지 리스트 (None이면 전체)
            
        Returns:
            DocumentIntelligenceResult: 분석 결과
        """
        if not self.is_available():
            return DocumentIntelligenceResult(
                success=False,
                error="Azure Document Intelligence 서비스를 사용할 수 없습니다.",
                extraction_method="azure_document_intelligence_unavailable"
            )
        
        # 페이지 수 제한 검사
        if await self._check_page_limit(file_path):
            return DocumentIntelligenceResult(
                success=False,
                error=f"PDF 페이지 수가 제한({self.max_pages})을 초과합니다.",
                extraction_method="azure_document_intelligence_page_limit_exceeded"
            )
        
        # SDK 4.x 모델 선택: 학술논문 처리는 prebuilt-layout 1회 호출로 충분
        # prebuilt-layout: 텍스트 + 문단 + 표 + 그림 + 섹션 헤더 모두 포함
        # 주의: SDK 4.x에서는 prebuilt-document 모델이 제거되었음
        configured_default = self.default_model or "prebuilt-layout"
        
        # SDK 4.x에서는 prebuilt-document가 없으므로 prebuilt-layout으로 변경
        if configured_default == "prebuilt-document":
            primary_model = "prebuilt-layout"
            logger.info("[AZURE-DI] SDK 4.x: prebuilt-document → prebuilt-layout 자동 변환")
        elif configured_default == "prebuilt-read":
            # prebuilt-read는 텍스트만 추출하므로 layout으로 업그레이드
            primary_model = "prebuilt-layout"
            logger.info("[AZURE-DI] SDK 4.x: prebuilt-read → prebuilt-layout 업그레이드 (표/그림 포함)")
        else:
            primary_model = configured_default
            
        if model:  # 호출자가 명시한 경우
            if model == "prebuilt-document":
                primary_model = "prebuilt-layout"
                logger.info("[AZURE-DI] SDK 4.x: prebuilt-document → prebuilt-layout 자동 변환 (caller override)")
            elif model == "prebuilt-read":
                primary_model = "prebuilt-layout"
                logger.info("[AZURE-DI] SDK 4.x: prebuilt-read → prebuilt-layout 업그레이드 (caller override)")
            else:
                primary_model = model

        # SDK 4.x에서는 layout 한 번만 호출하면 되므로 layout_model은 사용 안 함
        layout_model = None  # prebuilt-layout 1회 호출로 충분
        start_time = time.time()
        perf_start_total = time.perf_counter()

        logger.info(f"Azure DI 분석 시작: {file_path}, 모델(read)={primary_model} layout={layout_model}")

        # pdfplumber 한 번만 열기 (중복 호출 방지 - 성능 최적화)
        pdf_doc = None
        try:
            import pdfplumber  # type: ignore
            pdf_doc = pdfplumber.open(file_path)
            logger.debug(f"[PERF] pdfplumber.open() 완료: {len(pdf_doc.pages)} 페이지")
        except Exception as e:
            logger.warning(f"[PERF] pdfplumber.open() 실패: {e} - fallback 기능 일부 제한")

        try:
            # 파일 읽기
            with open(file_path, 'rb') as file:
                file_content = file.read()

            # 병렬 처리 및 캐싱 설정값 (존재하지 않으면 안전한 기본값)
            di_parallel_enabled: bool = bool(getattr(settings, "di_parallel_enabled", False))
            di_page_group_size: int = int(getattr(settings, "di_page_group_size", 3) or 3)
            di_max_concurrency: int = int(getattr(settings, "di_max_concurrency", 3) or 3)
            di_cache_enabled: bool = bool(getattr(settings, "di_cache_enabled", False))
            two_col_reorder_enabled: bool = bool(getattr(settings, "di_two_column_reorder_enabled", True))

            # 파일 해시 기반 간단 캐시 키 (로컬 임시 디스크 캐시)
            import hashlib, os, json as _json
            file_hash = hashlib.sha1(file_content).hexdigest()  # nosec - 캐시 키 용도
            cache_root = f"/tmp/di_cache/{file_hash}"
            if di_cache_enabled:
                os.makedirs(cache_root, exist_ok=True)

            # 병렬 페이지 그룹 처리 경로 (pages 인자가 None일 때만 전체 문서 대상으로 적용)
            total_pages = 0
            if pages is None and di_parallel_enabled:
                # 총 페이지 수 파악 (이미 열린 pdf_doc 재사용)
                total_pages = len(pdf_doc.pages) if pdf_doc else 0
                if total_pages <= 0:
                    logger.warning("PDF 페이지 수 확인 실패, 단일 호출로 폴백")
                    di_parallel_enabled = False

            if pages is None and di_parallel_enabled and (total_pages or 0) > di_page_group_size:
                logger.info(
                    f"[AZURE-DI] 병렬 페이지 그룹 처리 시작: total_pages={total_pages}, group_size={di_page_group_size}, max_concurrency={di_max_concurrency}"
                )

                # 그룹 분할 (1-indexed 페이지)
                page_numbers = list(range(1, total_pages + 1))
                groups: List[List[int]] = [
                    page_numbers[i : i + di_page_group_size] for i in range(0, len(page_numbers), di_page_group_size)
                ]

                # 세마포어로 동시성 제한
                import asyncio as _asyncio
                semaphore = _asyncio.Semaphore(di_max_concurrency)

                async def analyze_group(g: List[int]):
                    async with semaphore:
                        # 캐시 확인
                        cache_path = os.path.join(cache_root, f"group_{g[0]}_{g[-1]}.json") if di_cache_enabled else None
                        if di_cache_enabled and cache_path and os.path.exists(cache_path):
                            try:
                                with open(cache_path, "r", encoding="utf-8") as cf:
                                    cached = _json.load(cf)
                                return self._result_from_serialized(cached)
                            except Exception:
                                pass
                        # 호출
                        rr = await self._analyze_with_retry(file_content, primary_model, pages=g)
                        if rr and rr.success:
                            # 레이아웃(표/그림) 추가 패스
                            lr = await self._analyze_layout_with_retry(file_content, layout_model, pages=g)
                            if lr and lr.success:
                                rr.tables = lr.tables or rr.tables
                                rr.figures = lr.figures or []
                                rr.metadata.update({
                                    "layout_model_used": layout_model,
                                    "table_count": len(rr.tables or []),
                                    "figure_count": len(rr.figures or []),
                                })
                                self._merge_figures_into_pages(rr)
                            # 캐시 저장
                            if di_cache_enabled and cache_path:
                                try:
                                    with open(cache_path, "w", encoding="utf-8") as cf:
                                        _json.dump(self._serialize_result(rr), cf, ensure_ascii=False)
                                except Exception:
                                    pass
                        return rr

                tasks = [analyze_group(g) for g in groups]
                group_results: List[DocumentIntelligenceResult] = list(
                    await _asyncio.gather(*tasks, return_exceptions=False)
                )

                # 병합
                read_result = self._merge_group_results(group_results)
                if not read_result.success:
                    return read_result

                # 타이밍 기록
                group_read_secs = sum((gr.metadata or {}).get("timing", {}).get("read_seconds", 0) for gr in group_results if gr)
                group_layout_secs = sum((gr.metadata or {}).get("timing", {}).get("layout_seconds", 0) for gr in group_results if gr)
                read_result.metadata.setdefault("timing", {})
                read_result.metadata["timing"]["read_seconds"] = group_read_secs
                if group_layout_secs:
                    read_result.metadata["timing"]["layout_seconds"] = group_layout_secs
            else:
                # 단일 호출 경로: SDK 4.x prebuilt-layout은 1회 호출로 모든 것 추출
                perf_start = time.perf_counter()
                read_result = await self._analyze_with_retry(file_content, primary_model, pages=pages)
                elapsed = time.perf_counter() - perf_start
                logger.info(f"[AZURE-DI][TIMER] '{primary_model}' completed in {elapsed:.2f}s")
                
                if not read_result.success:
                    return read_result
                    
                if read_result.metadata is None:
                    read_result.metadata = {}
                read_result.metadata.setdefault("timing", {})
                read_result.metadata["timing"]["analysis_seconds"] = elapsed
                
                # SDK 4.x prebuilt-layout은 텍스트+표+그림을 한 번에 반환
                logger.info(f"[AZURE-DI][RESULT] SDK 4.x {primary_model} - "
                           f"pages: {len(read_result.pages)}, "
                           f"tables: {len(read_result.tables)}, "
                           f"figures: {len(read_result.figures)}")

            # pdfplumber fallback for figures (SDK 4.x에서도 figures가 없을 수 있음)
            if not read_result.figures:
                logger.info("[FIGURE-FALLBACK] Azure DI figures 없음 → pdfplumber fallback 시도")
                # 이미 열린 pdf_doc 재사용 (중복 open 방지)
                fallback_figures = self._extract_figures_with_pdfplumber_doc(pdf_doc) if pdf_doc else []
                if fallback_figures:
                    logger.info(f"[FIGURE-FALLBACK] ✅ {len(fallback_figures)}개 figure를 pdfplumber로 추출")
                    read_result.figures = fallback_figures
                    read_result.metadata.update({
                        "figure_count": len(read_result.figures),
                        "figure_extraction_fallback": "pdfplumber_images"
                    })
                    self._merge_figures_into_pages(read_result)
                else:
                    logger.warning("[FIGURE-FALLBACK] ❌ pdfplumber fallback도 figure 추출 실패")
            else:
                logger.info(f"[AZURE-DI][FIGURES] ✅ Azure DI로 {len(read_result.figures)}개 figure 추출 완료")

            result = read_result

            # 2열(dual-column) 레이아웃 재구성: 페이지 텍스트 순서 보정 (옵션)
            if two_col_reorder_enabled and pdf_doc:
                try:
                    # 이미 열린 pdf_doc 재사용 (중복 open 방지)
                    self._reorder_two_column_pages_doc(pdf_doc, result)
                except Exception as _e2:  # pragma: no cover - 실패해도 치명적 아님
                    logger.debug(f"dual-column 재구성 실패(무시): {_e2}")

            # 처리 시간 기록
            processing_time = time.time() - start_time
            result.metadata.update({
                'di_processing_time_seconds': round(processing_time, 2),
                'di_model_used': primary_model,
                'di_api_version': self.api_version,
                'di_endpoint': self.endpoint,
                'di_layout_model_used': layout_model
            })
            total_elapsed = time.perf_counter() - perf_start_total
            result.metadata.setdefault("timing", {})
            result.metadata["timing"]["total_seconds"] = total_elapsed
            logger.info(f"[AZURE-DI][TIMER] total analyze_pdf completed in {total_elapsed:.2f}s")

            logger.info(f"Azure DI 분석 완료: {processing_time:.2f}초, 성공: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"Azure DI 분석 중 예외 발생: {e}")
            return DocumentIntelligenceResult(
                success=False,
                error=f"Azure Document Intelligence 분석 실패: {str(e)}",
                extraction_method="azure_document_intelligence_error"
            )
        finally:
            # pdfplumber 리소스 정리 (중복 open 방지를 위해 한 번만 열고 사용 후 닫기)
            if pdf_doc:
                try:
                    pdf_doc.close()
                    logger.debug("[PERF] pdfplumber.close() 완료")
                except Exception:
                    pass
    
    async def _analyze_with_retry(self, file_content: bytes, model: str, pages: Optional[List[int]] = None) -> DocumentIntelligenceResult:
        """텍스트/레이아웃(라인 중심) 분석 재시도 (SDK 4.x 호환)"""
        last_error: Optional[str] = None
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                if not self._client:
                    raise RuntimeError("클라이언트 미초기화")
                logger.info(f"[read pass] 모델={model} SDK={SDK_VERSION} 시도 {attempt}/{self.retry_max_attempts}")
                
                if SDK_VERSION == "4.x":
                    # 4.x SDK: begin_analyze_document(model_id, body)
                    from io import BytesIO
                    body_params = {}
                    if pages:
                        body_params["pages"] = self._pages_to_range(pages)
                    if self.enabled_features:
                        body_params["features"] = list(self.enabled_features)
                    if self.enabled_outputs:
                        body_params["output"] = list(self.enabled_outputs)
                    
                    poller = self._client.begin_analyze_document(
                        model_id=model,
                        body=BytesIO(file_content),
                        **body_params
                    )
                else:
                    # 3.3.x Fallback
                    kwargs: Dict[str, Any] = {"logging_enable": False}
                    if pages:
                        kwargs["pages"] = self._pages_to_range(pages)
                    poller = self._client.begin_analyze_document(
                        model,
                        document=file_content,
                        **kwargs,
                    )
                
                analyze_result = await asyncio.wait_for(self._poll_result(poller), timeout=self.timeout_seconds)
                return self._convert_read_result(analyze_result, model)
            except ClientAuthenticationError as e:
                return DocumentIntelligenceResult(success=False, error=f"인증 실패: {e}", extraction_method="azure_document_intelligence_auth_error")
            except asyncio.TimeoutError:
                last_error = f"timeout {self.timeout_seconds}s"
                logger.warning(last_error)
            except HttpResponseError as e:
                if e.status_code in [429, 502, 503, 504]:
                    last_error = f"HTTP {e.status_code}: {e.message}"
                    if attempt < self.retry_max_attempts:
                        await asyncio.sleep(min(2 ** attempt, 30))
                else:
                    return DocumentIntelligenceResult(success=False, error=f"HTTP {e.status_code}: {e.message}", extraction_method="azure_document_intelligence_http_error")
            except Exception as e:  # pragma: no cover
                last_error = str(e)
                logger.warning(f"[read pass] 예외 발생: {e}")
                if attempt < self.retry_max_attempts:
                    await asyncio.sleep(min(2 ** attempt, 30))
        return DocumentIntelligenceResult(success=False, error=f"read pass 실패: {last_error}", extraction_method="azure_document_intelligence_retry_exhausted")

    async def _analyze_layout_with_retry(self, file_content: bytes, layout_model: str, pages: Optional[List[int]] = None) -> Optional[DocumentIntelligenceResult]:
        """표/그림 추출 재시도 (SDK 4.x FIGURES 지원)"""
        last_error: Optional[str] = None
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                if not self._client:
                    raise RuntimeError("클라이언트 미초기화")
                logger.info(f"[layout pass] 모델={layout_model} SDK={SDK_VERSION} 시도 {attempt}/{self.retry_max_attempts}")
                
                if SDK_VERSION == "4.x":
                    # 4.x SDK: FIGURES feature 지원
                    from io import BytesIO
                    body_params = {}
                    if pages:
                        body_params["pages"] = self._pages_to_range(pages)
                    
                    if self.enabled_features:
                        body_params["features"] = list(self.enabled_features)
                    if self.enabled_outputs:
                        body_params["output"] = list(self.enabled_outputs)
                    
                    poller = self._client.begin_analyze_document(
                        model_id=layout_model,
                        body=BytesIO(file_content),
                        **body_params
                    )
                else:
                    # 3.3.x Fallback (FIGURES 미지원)
                    logger.warning("[AZURE-DI][FIGURES] ⚠️ SDK 3.3.x - FIGURES 미지원, API 기본 동작만 사용")
                    kwargs_l: Dict[str, Any] = {"logging_enable": False}
                    if pages:
                        kwargs_l["pages"] = self._pages_to_range(pages)
                    poller = self._client.begin_analyze_document(
                        layout_model,
                        document=file_content,
                        **kwargs_l,
                    )
                
                analyze_result = await asyncio.wait_for(self._poll_result(poller), timeout=self.timeout_seconds)
                return self._convert_layout_result(analyze_result, layout_model)
            except (ClientAuthenticationError, asyncio.TimeoutError, HttpResponseError, Exception) as e:  # noqa: E722
                last_error = str(e)
                logger.warning(f"[layout pass] 예외 발생: {e}")
                if attempt < self.retry_max_attempts:
                    await asyncio.sleep(min(2 ** attempt, 20))
        logger.warning(f"layout pass 실패: {last_error}")
        return None

    async def _get_page_count(self, file_path: str) -> int:
        """PDF 총 페이지 수를 반환 (pdfplumber 경량 호출)"""
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception:
            return 0

    def _merge_group_results(self, results: List["DocumentIntelligenceResult"]) -> "DocumentIntelligenceResult":
        """여러 그룹 결과를 페이지 순서대로 병합"""
        merged = DocumentIntelligenceResult(success=True, text="", pages=[], tables=[], figures=[], metadata={})
        for r in results:
            if not r or not r.success:
                return DocumentIntelligenceResult(success=False, error=getattr(r, "error", "group analyze failed"))
            merged.pages.extend(r.pages or [])
            merged.tables.extend(r.tables or [])
            merged.figures.extend(r.figures or [])
        # 페이지 번호 기준 정렬 및 본문 텍스트 재구성
        try:
            merged.pages.sort(key=lambda p: p.get("page_no", 0))
        except Exception:
            pass
        merged.text = "".join([
            (f"\n[페이지 {p.get('page_no')}]\n" + (p.get("text", "") or "")) for p in (merged.pages or [])
        ])
        return merged

    def _reorder_two_column_pages_doc(self, pdf: Any, result: "DocumentIntelligenceResult") -> None:
        """
        2열 레이아웃 페이지의 텍스트 순서를 재구성 (이미 열린 pdfplumber 객체 재사용)
        
        Args:
            pdf: 이미 열린 pdfplumber.PDF 객체
            result: 수정할 DocumentIntelligenceResult
        """
        if not result.pages:
            return

        # 페이지별로 pdfplumber에서 단어 좌표를 가져와 2열 여부 판단 및 재구성
        new_pages = []
        for pg in result.pages:
            pno = int(pg.get("page_no", 0) or 0)
            if pno <= 0 or pno > len(pdf.pages):
                new_pages.append(pg)
                continue
            page = pdf.pages[pno - 1]
            words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False) or []
            if not words:
                new_pages.append(pg)
                continue
            W = float(page.width or 0)
            # 중앙 밴드 비움 여부와 좌우 분포로 2열 판단
            centers = [ (float(w.get("x0",0))+float(w.get("x1",0)))/2.0 for w in words ]
            left = [w for w,cx in zip(words, centers) if cx < W*0.47]
            right = [w for w,cx in zip(words, centers) if cx > W*0.53]
            mid_band = [w for w,cx in zip(words, centers) if W*0.47 <= cx <= W*0.53]
            is_dual = len(left) > 0 and len(right) > 0 and len(mid_band) < max(3, int(0.02*len(words)))
            if not is_dual:
                new_pages.append(pg)
                continue
            # 좌/우 컬럼 내에서 y, x 정렬
            def sort_key(w):
                return (float(w.get("top",0)), float(w.get("x0",0)))
            left_sorted = sorted(left, key=sort_key)
            right_sorted = sorted(right, key=sort_key)
            left_text = self._join_words(left_sorted)
            right_text = self._join_words(right_sorted)
            combined_text = (left_text + "\n" + right_text).strip()
            new_pg = dict(pg)
            # 메타에 dual column 플래그 기록
            meta = dict(new_pg.get("metadata", {}))
            meta.update({"dual_column": True})
            new_pg["metadata"] = meta
            new_pg["text"] = combined_text if combined_text else pg.get("text", "")
            new_pages.append(new_pg)

        result.pages = new_pages
        # result.text 재구성
        result.text = "".join([
            (f"\n[페이지 {p.get('page_no')}]\n" + (p.get("text", "") or "")) for p in (result.pages or [])
        ])
        
        # INFO 로그: 2열 재구성 적용 페이지 수 표시
        dual_count = sum(1 for pg in new_pages if pg.get("metadata", {}).get("dual_column"))
        if dual_count > 0:
            logger.info(f"[AZURE-DI] 2열 레이아웃 재구성 적용: {dual_count}/{len(new_pages)} 페이지")

    def _reorder_two_column_pages(self, file_path: str, result: "DocumentIntelligenceResult") -> None:
        """
        [DEPRECATED] 2열 레이아웃 페이지의 텍스트 순서를 재구성 (레거시)
        
        이 함수는 이제 _reorder_two_column_pages_doc()를 호출합니다.
        pdfplumber를 매번 여는 대신 재사용하는 것이 권장됩니다.
        """
        try:
            import pdfplumber  # type: ignore
        except Exception:
            logger.debug("pdfplumber 미설치 - dual-column 재구성 생략")
            return

        if not result.pages:
            return

        # 페이지별로 pdfplumber에서 단어 좌표를 가져와 2열 여부 판단 및 재구성
        new_pages = []
        with pdfplumber.open(file_path) as pdf:
            for pg in result.pages:
                pno = int(pg.get("page_no", 0) or 0)
                if pno <= 0 or pno > len(pdf.pages):
                    new_pages.append(pg)
                    continue
                page = pdf.pages[pno - 1]
                words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False) or []
                if not words:
                    new_pages.append(pg)
                    continue
                W = float(page.width or 0)
                # 중앙 밴드 비움 여부와 좌우 분포로 2열 판단
                centers = [ (float(w.get("x0",0))+float(w.get("x1",0)))/2.0 for w in words ]
                left = [w for w,cx in zip(words, centers) if cx < W*0.47]
                right = [w for w,cx in zip(words, centers) if cx > W*0.53]
                mid_band = [w for w,cx in zip(words, centers) if W*0.47 <= cx <= W*0.53]
                is_dual = len(left) > 0 and len(right) > 0 and len(mid_band) < max(3, int(0.02*len(words)))
                if not is_dual:
                    new_pages.append(pg)
                    continue
                # 좌/우 컬럼 내에서 y, x 정렬
                def sort_key(w):
                    return (float(w.get("top",0)), float(w.get("x0",0)))
                left_sorted = sorted(left, key=sort_key)
                right_sorted = sorted(right, key=sort_key)
                left_text = self._join_words(left_sorted)
                right_text = self._join_words(right_sorted)
                combined_text = (left_text + "\n" + right_text).strip()
                new_pg = dict(pg)
                # 메타에 dual column 플래그 기록
                meta = dict(new_pg.get("metadata", {}))
                meta.update({"dual_column": True})
                new_pg["metadata"] = meta
                new_pg["text"] = combined_text if combined_text else pg.get("text", "")
                new_pages.append(new_pg)

        result.pages = new_pages
        # result.text 재구성
        result.text = "".join([
            (f"\n[페이지 {p.get('page_no')}]\n" + (p.get("text", "") or "")) for p in (result.pages or [])
        ])
        
        # INFO 로그: 2열 재구성 적용 페이지 수 표시
        dual_count = sum(1 for pg in new_pages if pg.get("metadata", {}).get("dual_column"))
        if dual_count > 0:
            logger.info(f"[AZURE-DI] 2열 레이아웃 재구성 적용: {dual_count}/{len(new_pages)} 페이지")

    def _join_words(self, words: List[Dict[str, Any]]) -> str:
        # 간단한 줄 바꿈 힌트: y 차이가 클 때 줄바꿈
        if not words:
            return ""
        lines: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        last_top = None
        for w in words:
            top = float(w.get("top", 0))
            if last_top is None or abs(top - last_top) <= 3.0:
                current.append(w)
                last_top = top if last_top is None else (last_top*0.7 + top*0.3)
            else:
                lines.append(current)
                current = [w]
                last_top = top
        if current:
            lines.append(current)
        # 각 줄에서 x0 순 정렬 후 텍스트 결합
        def line_text(ws: List[Dict[str, Any]]) -> str:
            ws_sorted = sorted(ws, key=lambda w: float(w.get("x0", 0)))
            return " ".join([w.get("text", "") for w in ws_sorted]).strip()
        return "\n".join([line_text(ln) for ln in lines]).strip()

    def _pages_to_range(self, pages: List[int]) -> str:
        """페이지 리스트를 Azure DI pages 매개변수 형식으로 변환 (예: "1-3,5,7-9")"""
        if not pages:
            return ""
        ps = sorted(set(int(p) for p in pages if p and p > 0))
        ranges: List[str] = []
        start = ps[0]
        prev = ps[0]
        for p in ps[1:]:
            if p == prev + 1:
                prev = p
                continue
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{prev}")
            start = prev = p
        if start == prev:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{prev}")
        return ",".join(ranges)

    def _serialize_result(self, r: "DocumentIntelligenceResult") -> Dict[str, Any]:
        return {
            "success": r.success,
            "text": r.text,
            "pages": r.pages,
            "tables": r.tables,
            "figures": r.figures,
            "metadata": r.metadata,
            "error": r.error,
            "extraction_method": r.extraction_method,
        }

    def _result_from_serialized(self, d: Dict[str, Any]) -> "DocumentIntelligenceResult":
        return DocumentIntelligenceResult(
            success=bool(d.get("success", True)),
            text=d.get("text", "") or "",
            pages=d.get("pages") or [],
            tables=d.get("tables") or [],
            figures=d.get("figures") or [],
            metadata=d.get("metadata") or {},
            error=d.get("error"),
            extraction_method=d.get("extraction_method", "azure_document_intelligence"),
        )
    
    async def _poll_result(self, poller: LROPoller) -> Any:
        """비동기 폴링 결과 대기"""
        while not poller.done():
            await asyncio.sleep(1)  # 1초마다 상태 확인
        return poller.result()
    
    # ------------------ 변환 유틸 (Read Pass) ------------------
    def _convert_read_result(self, analyze_result: Any, model: str) -> DocumentIntelligenceResult:
        try:
            pages = getattr(analyze_result, "pages", []) or []
            logger.debug(f"[AZURE-DI][READ] analyze_result.pages - count={len(pages)}")
            
            # 🎯 SDK 4.x: analyze_result.paragraphs를 페이지별로 분배
            doc_paragraphs = list(getattr(analyze_result, "paragraphs", []) or [])
            logger.info(f"[AZURE-DI][READ] analyze_result.paragraphs - count={len(doc_paragraphs)}")
            
            # 페이지별 paragraphs 매핑 (bounding_regions로 페이지 번호 추출)
            paragraphs_by_page: Dict[int, List[Any]] = {}
            for para in doc_paragraphs:
                bounding_regions = getattr(para, 'bounding_regions', [])
                if bounding_regions:
                    page_no = getattr(bounding_regions[0], 'page_number', 1)
                    if page_no not in paragraphs_by_page:
                        paragraphs_by_page[page_no] = []
                    paragraphs_by_page[page_no].append(para)
            
            logger.info(f"[AZURE-DI][READ] paragraphs를 {len(paragraphs_by_page)}개 페이지로 분배 완료")
            
            all_pages: List[Dict[str, Any]] = []
            full_text_parts: List[str] = []
            total_section_headers = 0
            
            for idx, page in enumerate(pages, 1):
                try:
                    # 해당 페이지의 paragraphs 전달
                    page_paragraphs = paragraphs_by_page.get(idx, [])
                    page_dict = self._process_page(page, idx, page_paragraphs)
                    all_pages.append(page_dict)
                    total_section_headers += len(page_dict.get('section_headers', []))
                    if page_dict.get("text"):
                        full_text_parts.append(f"\n\n=== 페이지 {idx} ===\n" + page_dict["text"])
                except Exception as page_err:
                    logger.error(f"[AZURE-DI][READ] 페이지 {idx} 처리 실패: {page_err}", exc_info=True)
                    # 페이지 처리 실패해도 계속 진행
                    continue
            
            full_text = "\n".join(full_text_parts).strip()
            
            logger.info(f"[AZURE-DI][READ] ✅ {len(all_pages)}페이지 처리 완료 - 전체 section_headers: {total_section_headers}개")
            
            # 🎯 SDK 4.x prebuilt-layout: tables와 figures도 함께 추출
            tables: List[Dict[str, Any]] = []
            tables_raw = getattr(analyze_result, "tables", []) or []
            if tables_raw:
                logger.info(f"[AZURE-DI][READ] analyze_result에서 {len(tables_raw)}개 table 발견")
                tables = [self._process_table(table, idx) for idx, table in enumerate(tables_raw)]
            
            figures: List[Dict[str, Any]] = []
            doc_figs = getattr(analyze_result, "figures", None)
            if doc_figs:
                logger.info(f"[AZURE-DI][READ] analyze_result에서 {len(doc_figs)}개 figure 발견 (문서 레벨)")
                for idx, fig in enumerate(doc_figs, 1):
                    figures.append(self._process_figure(fig, idx))
            
            # 문서 레벨 figures가 없으면 페이지별 figures 확인
            if not figures and hasattr(analyze_result, "pages"):
                logger.info(f"[AZURE-DI][READ] 페이지별 figures 확인 중 (총 {len(analyze_result.pages)}페이지)")
                for page in analyze_result.pages:
                    page_figures = getattr(page, "figures", None)
                    if page_figures:
                        logger.info(f"[AZURE-DI][READ] 페이지 {getattr(page, 'page_number', '?')}에서 {len(page_figures)}개 figure 발견")
                        for fig in page_figures:
                            figures.append(self._process_figure(fig, len(figures) + 1))
            
            metadata = {
                "page_count": len(all_pages),
                "table_count": len(tables),
                "figure_count": len(figures),
                "char_count": len(full_text),
                "di_model": model,
                "extraction_method": "azure_document_intelligence",
            }
            
            logger.info(f"[AZURE-DI][READ] ✅ 추출 완료 - tables: {len(tables)}, figures: {len(figures)}")
            
            return DocumentIntelligenceResult(success=True, text=full_text, pages=all_pages, tables=tables, figures=figures, metadata=metadata)
        except Exception as e:  # pragma: no cover
            logger.error(f"[AZURE-DI][READ] read 변환 실패: {e}", exc_info=True)
            return DocumentIntelligenceResult(success=False, error=f"read 변환 실패: {e}")

    # ------------------ 변환 유틸 (Layout/Table Pass) ------------------
    def _convert_layout_result(self, analyze_result: Any, model: str) -> DocumentIntelligenceResult:
        try:
            tables_raw = getattr(analyze_result, "tables", []) or []
            tables = [self._process_table(table, idx) for idx, table in enumerate(tables_raw)]

            figures: List[Dict[str, Any]] = []
            doc_figs = getattr(analyze_result, "figures", None)
            logger.info(f"[AZURE-DI][FIGURES] 문서 레벨 figures 속성: {type(doc_figs)}, count={len(doc_figs) if doc_figs else 0}")
            if doc_figs:
                for idx, fig in enumerate(doc_figs, 1):
                    figures.append(self._process_figure(fig, idx))

            if not figures and hasattr(analyze_result, "pages"):
                logger.info(f"[AZURE-DI][FIGURES] 문서 레벨 figures 없음 → 페이지별 figures 확인 중 (총 {len(analyze_result.pages)}페이지)")
                for page in analyze_result.pages:
                    page_figures = getattr(page, "figures", None)
                    if not page_figures:
                        continue
                    logger.info(f"[AZURE-DI][FIGURES] 페이지 {getattr(page, 'page_number', '?')}에서 {len(page_figures)}개 figure 발견")
                    for fig in page_figures:
                        figures.append(self._process_figure(fig, len(figures) + 1))

            metadata = {
                "layout_model": model,
                "layout_tables": len(tables),
                "layout_figures": len(figures)
            }

            return DocumentIntelligenceResult(
                success=True,
                text="",
                tables=tables,
                figures=figures,
                pages=[],
                metadata=metadata
            )
        except Exception as e:  # pragma: no cover
            return DocumentIntelligenceResult(success=False, error=f"layout 변환 실패: {e}")
    
    # ------------------ 페이지 처리 & 컬럼 정렬 ------------------
    def _process_page(self, page: Any, page_no: int, page_paragraphs: List[Any] = None) -> Dict[str, Any]:
        """
        페이지 단위 처리
        
        Args:
            page: Azure DI page 객체
            page_no: 페이지 번호 (1-based)
            page_paragraphs: 해당 페이지의 paragraphs 리스트 (SDK 4.x는 문서 레벨에서 전달)
        """
        width = float(getattr(page, 'width', 0) or 0)
        height = float(getattr(page, 'height', 0) or 0)
        lines = list(getattr(page, 'lines', []) or [])
        processed_lines: List[Dict[str, Any]] = []
        raw_line_objs: List[Any] = []
        for ln in lines:
            content = getattr(ln, 'content', getattr(ln, 'text', '')) or ''
            if not content.strip():
                continue
            processed_lines.append({
                'content': content,
                'bbox': self._extract_bbox(ln),
                'confidence': getattr(ln, 'confidence', 1.0)
            })
            raw_line_objs.append(ln)

        # 🎯 Azure DI의 paragraphs와 role 정보 추출 (섹션 감지 활용)
        # SDK 4.x: paragraphs는 문서 레벨에서 페이지별로 분배됨
        paragraphs = page_paragraphs if page_paragraphs is not None else []
        section_headers: List[Dict[str, Any]] = []
        paragraph_blocks: List[Dict[str, Any]] = []
        
        logger.debug(f"[AZURE-DI][PAGE-{page_no}] paragraphs 전달 받음 - count={len(paragraphs)}")
        
        for para in paragraphs:
            content = getattr(para, 'content', '') or ''
            if not content.strip():
                continue
            
            role = getattr(para, 'role', None)
            bbox = self._extract_bbox(para)
            
            para_info = {
                'content': content,
                'role': role,
                'bbox': bbox,
                'confidence': getattr(para, 'confidence', 1.0)
            }
            
            # role 기반 섹션 헤더 식별
            if role and 'heading' in role.lower():
                section_headers.append(para_info)
                logger.debug(f"[AZURE-DI][ROLE] 섹션 헤더 감지 - page={page_no}, role={role}, content='{content[:50]}'")
            else:
                paragraph_blocks.append(para_info)
        
        if section_headers:
            logger.info(f"[AZURE-DI][PAGE-{page_no}] ✅ {len(section_headers)}개 섹션 헤더 감지 (role 기반)")
        else:
            logger.debug(f"[AZURE-DI][PAGE-{page_no}] 섹션 헤더 없음 (paragraphs={len(paragraph_blocks)})")


        # 컬럼 분할 (간단: 2열 시도 후 다단)
        groups = self._split_into_n_columns(raw_line_objs, width, height, max_cols=2, min_lines_per_col=3)
        if len(groups) <= 1:
            groups = [raw_line_objs]
        merged_text_parts: List[str] = []
        for g in groups:
            # 각 그룹 내 라인 y,x 정렬
            g_sorted = sorted(g, key=lambda obj: self._line_left_top_norm(obj, width, height))
            merged_text_parts.append('\n'.join([getattr(obj, 'content', getattr(obj, 'text', '')) for obj in g_sorted]).strip())
        merged_text = '\n\n'.join([p for p in merged_text_parts if p]).strip()

        page_result = {
            'page_no': page_no,
            'text': merged_text,
            'width': width,
            'height': height,
            'lines': processed_lines,
            'paragraphs': paragraph_blocks,  # 🎯 일반 문단 정보
            'section_headers': section_headers,  # 🎯 role 기반 섹션 헤더
            'figures': [],  # 향후 필요 시 확장
            'tables': [],
            'images_metadata': [],
            'columns_detected': len(groups)
        }
        
        logger.debug(f"[AZURE-DI][PAGE-{page_no}] 반환 - text_len={len(merged_text)}, lines={len(processed_lines)}, "
                    f"section_headers={len(section_headers)}, paragraphs={len(paragraph_blocks)}")
        
        return page_result
    
    def _process_table(self, table: Any, table_idx: int) -> Dict[str, Any]:
        cells = getattr(table, 'cells', []) or []
        processed_cells: List[Dict[str, Any]] = []
        for c in cells:
            if getattr(c, 'confidence', 1.0) < self.confidence_threshold:
                continue
            processed_cells.append({
                'row_index': getattr(c, 'row_index', 0),
                'column_index': getattr(c, 'column_index', 0),
                'row_span': getattr(c, 'row_span', 1),
                'column_span': getattr(c, 'column_span', 1),
                'content': getattr(c, 'content', getattr(c, 'text', '')) or '',
                'confidence': getattr(c, 'confidence', 1.0),
                'bbox': self._extract_bbox(c)
            })
        return {
            'table_index': table_idx + 1,
            'row_count': getattr(table, 'row_count', 0),
            'column_count': getattr(table, 'column_count', 0),
            'bbox': self._extract_bbox(table),
            'cells': processed_cells
        }

    def _process_figure(self, figure: Any, figure_idx: int) -> Dict[str, Any]:
        bbox = self._extract_bbox(figure)
        page_no = None
        if hasattr(figure, 'bounding_regions') and figure.bounding_regions:
            region = figure.bounding_regions[0]
            page_no = getattr(region, 'page_number', None) or getattr(region, 'page', None)
        
        # Caption 처리: DocumentCaption 객체인 경우 .content로 문자열 추출
        caption_obj = getattr(figure, 'caption', None)
        if caption_obj:
            # DocumentCaption 객체인 경우 .content 속성 사용
            caption_text = getattr(caption_obj, 'content', str(caption_obj)) if hasattr(caption_obj, 'content') else str(caption_obj)
        else:
            caption_text = ''
        
        return {
            'figure_index': figure_idx,
            'page_no': page_no,
            'bbox': bbox,
            'confidence': getattr(figure, 'confidence', None),
            'caption': caption_text,  # 문자열로 저장
            'extraction_source': 'azure_document_intelligence'
        }

    # ------------------ 좌표/컬럼 유틸 (노트북 휴리스틱 이식) ------------------
    def _line_left_top_norm(self, line: Any, page_w: float, page_h: float) -> Tuple[float, float]:
        """라인 객체에서 정규화된 좌상단 좌표 추출 (SDK 3.x & 4.x 호환)"""
        poly = getattr(line, 'polygon', None) or getattr(line, 'bounding_polygon', None)
        if poly:
            xs = []
            ys = []
            
            # SDK 4.x 확인: flat array [x1, y1, x2, y2, ...] 또는 Point 객체 리스트
            if poly and len(poly) > 0:
                first_elem = poly[0]
                
                # Case 1: SDK 4.x flat array (숫자 리스트)
                if isinstance(first_elem, (int, float)):
                    # [x1, y1, x2, y2, x3, y3, x4, y4] 형식
                    for i in range(0, len(poly), 2):
                        if i + 1 < len(poly):
                            xs.append(float(poly[i]))
                            ys.append(float(poly[i + 1]))
                
                # Case 2: Point 객체 리스트 또는 [x, y] 리스트
                else:
                    for p in poly:
                        try:
                            # SDK 4.x: Point 객체 (p.x, p.y)
                            if hasattr(p, 'x') and hasattr(p, 'y'):
                                xs.append(float(p.x))
                                ys.append(float(p.y))
                            # SDK 3.x 또는 리스트: [x, y]
                            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                                xs.append(float(p[0]))
                                ys.append(float(p[1]))
                        except (TypeError, ValueError, IndexError) as e:
                            logger.debug(f"[AZURE-DI][NORM] polygon point 파싱 실패: {e}, type={type(p)}")
                            continue
            
            if xs and ys:
                left = (min(xs) / (page_w or 1.0))
                top = (min(ys) / (page_h or 1.0))
            else:
                left, top = 0.0, 0.0
        else:
            left, top = 0.0, 0.0
        return left, top

    def _kmeans_1d(self, values: List[float], k: int, iters: int = 15) -> List[int]:
        if k <= 1 or len(values) <= k:
            return [0 for _ in values]
        sv = sorted(set(values))
        if len(sv) < k:
            k = len(sv)
        centers = [sv[max(0, min(len(sv)-1, round((i+0.5)*len(sv)/k)-1))] for i in range(k)]
        assign = [0]*len(values)
        for _ in range(iters):
            for i, v in enumerate(values):
                ci = min(range(k), key=lambda j: abs(v - centers[j]))
                assign[i] = ci
            new_centers = centers[:]
            for j in range(k):
                grp = [values[i] for i, a in enumerate(assign) if a == j]
                if grp:
                    new_centers[j] = sum(grp)/len(grp)
            if all(abs(new_centers[j]-centers[j]) < 1e-4 for j in range(k)):
                break
            centers = new_centers
        return assign

    def _split_into_n_columns(self, lines: List[Any], page_w: float, page_h: float, max_cols: int, min_lines_per_col: int):
        if not lines:
            return [lines]
        xs = [self._line_left_top_norm(l, page_w, page_h)[0] for l in lines]
        best = [lines]
        for k in range(2, max_cols+1):
            assign = self._kmeans_1d(xs, k)
            groups = [[] for _ in range(k)]
            for l, a in zip(lines, assign):
                groups[a].append(l)
            groups = [g for g in groups if len(g) >= min_lines_per_col]
            if len(groups) <= 1:
                continue
            def left_mean(g):
                vals = [self._line_left_top_norm(x, page_w, page_h)[0] for x in g]
                return sum(vals)/len(vals)
            groups.sort(key=left_mean)
            best = groups
        return best
    
    def _extract_bbox(self, element: Any) -> List[List[float]]:
        """요소에서 bounding box 추출 (SDK 3.x & 4.x 호환)"""
        # SDK 4.x: bounding_regions[].polygon
        if hasattr(element, 'bounding_regions') and element.bounding_regions:
            try:
                region = element.bounding_regions[0]
                if hasattr(region, 'polygon') and region.polygon:
                    poly = region.polygon
                    polygon = []
                    
                    # SDK 4.x 확인: flat array 또는 Point 객체 리스트
                    if poly and len(poly) > 0:
                        first_elem = poly[0]
                        
                        # Case 1: SDK 4.x flat array [x1, y1, x2, y2, ...]
                        if isinstance(first_elem, (int, float)):
                            for i in range(0, len(poly), 2):
                                if i + 1 < len(poly):
                                    polygon.append([float(poly[i]), float(poly[i + 1])])
                        
                        # Case 2: Point 객체 리스트 또는 [x, y] 리스트
                        else:
                            for i, point in enumerate(poly):
                                try:
                                    if hasattr(point, 'x') and hasattr(point, 'y'):
                                        # Point 객체
                                        polygon.append([float(point.x), float(point.y)])
                                    elif isinstance(point, (list, tuple)) and len(point) >= 2:
                                        # [x, y] 형식
                                        polygon.append([float(point[0]), float(point[1])])
                                except (TypeError, ValueError, IndexError, AttributeError) as e:
                                    logger.debug(f"[AZURE-DI][BBOX] polygon point[{i}] 변환 실패: {e}")
                                    continue
                    
                    if polygon:
                        return polygon
                    else:
                        logger.debug(f"[AZURE-DI][BBOX] polygon 파싱 결과가 비어있음 (region.polygon 길이: {len(poly)})")
            except Exception as e:
                logger.debug(f"[AZURE-DI][BBOX] bounding_regions 파싱 실패: {e}, element_type={type(element).__name__}")
        
        # SDK 3.x 호환: bounding_box 속성
        if hasattr(element, 'bounding_box') and element.bounding_box:
            try:
                bbox = element.bounding_box
                return [[bbox.x, bbox.y], [bbox.x + bbox.width, bbox.y], 
                       [bbox.x + bbox.width, bbox.y + bbox.height], [bbox.x, bbox.y + bbox.height]]
            except Exception as e:
                logger.warning(f"[AZURE-DI][BBOX] bounding_box 파싱 실패: {e}")
        
        return []  # 빈 bounding box

    def _merge_figures_into_pages(self, di_result: DocumentIntelligenceResult) -> None:
        """layout pass에서 추출한 figure를 페이지 메타에 반영"""
        if not di_result.figures or not di_result.pages:
            return
        figures_by_page: Dict[int, List[Dict[str, Any]]] = {}
        for fig in di_result.figures:
            page_no = fig.get('page_no')
            if page_no is None:
                continue
            figures_by_page.setdefault(page_no, []).append(fig)

        for page in di_result.pages:
            page_no = page.get('page_no')
            if not page_no or page_no not in figures_by_page:
                continue
            page.setdefault('figures', [])
            page.setdefault('images_metadata', [])
            existing_images = page['images_metadata']
            start_idx = len(existing_images) + 1
            for idx, fig in enumerate(figures_by_page[page_no], start=start_idx):
                page['figures'].append(fig)
                page['images_metadata'].append({
                    'image_index': idx,
                    'page_no': page_no,
                    'bbox': fig.get('bbox', []),
                    'width': 0,
                    'height': 0,
                    'extraction_source': fig.get('extraction_source', 'azure_document_intelligence')
                })

    def _extract_figures_with_pdfplumber_doc(self, pdf: Any) -> List[Dict[str, Any]]:
        """
        pdfplumber 이미지를 활용한 보조 figure 추출 (이미 열린 객체 재사용)
        
        Args:
            pdf: 이미 열린 pdfplumber.PDF 객체
            
        Returns:
            추출된 figure 목록
        """
        figures: List[Dict[str, Any]] = []
        try:
            logger.info(f"[FIGURE-FALLBACK] pdfplumber로 이미지 추출 시작 (재사용된 PDF 객체)")
            for page_idx, page in enumerate(pdf.pages, start=1):
                page_images = page.images or []
                logger.debug(f"[FIGURE-FALLBACK] 페이지 {page_idx}: {len(page_images)}개 이미지 발견")
                # Dedup and size filter within page
                seen: List[Tuple[float, float, float, float]] = []
                per_page_count = 0
                max_per_page = 50  # prevent runaway counts
                min_area = max(1000.0, (page.width or 0) * (page.height or 0) * 0.002)  # skip tiny marks
                for img_idx, img in enumerate(page_images, start=1):
                    x0, y0, x1, y1 = img.get('x0'), img.get('y0'), img.get('x1'), img.get('y1')
                    if any(v is None for v in (x0, y0, x1, y1)):
                        logger.debug(f"[FIGURE-FALLBACK] 페이지 {page_idx} 이미지 {img_idx}: bbox 불완전 → 스킵")
                        continue
                    try:
                        fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
                    except Exception:
                        # 좌표 캐스팅 실패 시 스킵
                        continue
                    w = fx1 - fx0
                    h = fy1 - fy0
                    if w <= 2 or h <= 2 or (w * h) < min_area:
                        # ignore too small images (likely artifacts)
                        continue
                    # dedup by IoU with seen bboxes
                    cand = (fx0, fy0, fx1, fy1)
                    is_dup = False
                    for (sx0, sy0, sx1, sy1) in seen:
                        ix0, iy0 = max(cand[0], sx0), max(cand[1], sy0)
                        ix1, iy1 = min(cand[2], sx1), min(cand[3], sy1)
                        inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
                        area_c = (cand[2] - cand[0]) * (cand[3] - cand[1])
                        area_s = (sx1 - sx0) * (sy1 - sy0)
                        union = area_c + area_s - inter if (area_c + area_s - inter) > 0 else 1.0
                        iou = inter / union
                        if iou > 0.9:
                            is_dup = True
                            break
                    if is_dup:
                        continue
                    seen.append(cand)
                    bbox = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                    figures.append({
                        'figure_index': len(figures) + 1,
                        'page_no': page_idx,
                        'bbox': bbox,
                        'confidence': None,
                        'caption': '',
                        'extraction_source': 'pdfplumber_image'
                    })
                    per_page_count += 1
                    if per_page_count >= max_per_page:
                        break
            logger.info(f"[FIGURE-FALLBACK] pdfplumber 이미지 추출 완료: 총 {len(figures)}개")
        except Exception as e:
            logger.error(f"[FIGURE-FALLBACK] pdfplumber 이미지 추출 중 오류: {e}")
        return figures

    def _extract_figures_with_pdfplumber(self, file_path: str) -> List[Dict[str, Any]]:
        """
        [DEPRECATED] pdfplumber 이미지를 활용한 보조 figure 추출 (레거시)
        
        이 함수는 이제 _extract_figures_with_pdfplumber_doc()를 호출합니다.
        pdfplumber를 매번 여는 대신 재사용하는 것이 권장됩니다.
        """
        try:
            import pdfplumber
        except Exception:
            logger.warning("[FIGURE-FALLBACK] pdfplumber 미설치로 figure fallback 불가")
            return []

        figures: List[Dict[str, Any]] = []
        try:
            logger.info(f"[FIGURE-FALLBACK] pdfplumber로 이미지 추출 시작: {file_path}")
            with pdfplumber.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages, start=1):
                    page_images = page.images or []
                    logger.debug(f"[FIGURE-FALLBACK] 페이지 {page_idx}: {len(page_images)}개 이미지 발견")
                    # Dedup and size filter within page
                    seen: List[Tuple[float, float, float, float]] = []
                    per_page_count = 0
                    max_per_page = 50  # prevent runaway counts
                    min_area = max(1000.0, (page.width or 0) * (page.height or 0) * 0.002)  # skip tiny marks
                    for img_idx, img in enumerate(page_images, start=1):
                        x0, y0, x1, y1 = img.get('x0'), img.get('y0'), img.get('x1'), img.get('y1')
                        if any(v is None for v in (x0, y0, x1, y1)):
                            logger.debug(f"[FIGURE-FALLBACK] 페이지 {page_idx} 이미지 {img_idx}: bbox 불완전 → 스킵")
                            continue
                        try:
                            fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
                        except Exception:
                            # 좌표 캐스팅 실패 시 스킵
                            continue
                        w = fx1 - fx0
                        h = fy1 - fy0
                        if w <= 2 or h <= 2 or (w * h) < min_area:
                            # ignore too small images (likely artifacts)
                            continue
                        # dedup by IoU with seen bboxes
                        cand = (fx0, fy0, fx1, fy1)
                        is_dup = False
                        for (sx0, sy0, sx1, sy1) in seen:
                            ix0, iy0 = max(cand[0], sx0), max(cand[1], sy0)
                            ix1, iy1 = min(cand[2], sx1), min(cand[3], sy1)
                            inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
                            area_c = (cand[2] - cand[0]) * (cand[3] - cand[1])
                            area_s = (sx1 - sx0) * (sy1 - sy0)
                            union = area_c + area_s - inter if (area_c + area_s - inter) > 0 else 1.0
                            iou = inter / union
                            if iou > 0.9:
                                is_dup = True
                                break
                        if is_dup:
                            continue
                        seen.append(cand)
                        bbox = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                        figures.append({
                            'figure_index': len(figures) + 1,
                            'page_no': page_idx,
                            'bbox': bbox,
                            'confidence': None,
                            'caption': '',
                            'extraction_source': 'pdfplumber_image'
                        })
                        per_page_count += 1
                        if per_page_count >= max_per_page:
                            logger.debug(f"[FIGURE-FALLBACK] 페이지 {page_idx} 최대 {max_per_page}개 도달, 이후 스킵")
                            break
            logger.info(f"[FIGURE-FALLBACK] ✅ pdfplumber로 {len(figures)}개 figure 추출 완료")
        except Exception as e:
            logger.warning(f"[FIGURE-FALLBACK] ❌ pdfplumber figure 추출 실패: {e}")
            return []

        return figures
    
    async def _check_page_limit(self, file_path: str) -> bool:
        """PDF 페이지 수가 제한을 초과하는지 확인"""
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                page_count = len(reader.pages)
                
                if page_count > self.max_pages:
                    logger.warning(f"PDF 페이지 수 초과: {page_count} > {self.max_pages}")
                    return True
                    
                logger.info(f"PDF 페이지 수 확인: {page_count} (제한: {self.max_pages})")
                return False
                
        except Exception as e:
            logger.warning(f"PDF 페이지 수 확인 실패: {e}")
            return False  # 확인 실패시 진행
    
    def create_internal_extraction_result(self, di_result: DocumentIntelligenceResult) -> Dict[str, Any]:
        """Document Intelligence 결과를 기존 추출 형식으로 변환"""
        if not di_result.success:
            return {
                'success': False,
                'error': di_result.error,
                'text': '',
                'metadata': {
                    'extraction_method': di_result.extraction_method,
                    'extraction_note': di_result.error
                }
            }
        
        # 기존 형식으로 변환
        result = {
            'success': True,
            'text': di_result.text,
            'metadata': {
                'provider': 'azure_di',  # 🎯 Provider 정보 추가 (multimodal_document_service에서 사용)
                **di_result.metadata,
                'pages': di_result.pages,
                'tables': di_result.tables,
                'figures': di_result.figures,  # ✅ figures 추가
                'images_metadata': []
            }
        }
        
        # 이미지 메타데이터 통합
        for page in di_result.pages:
            if 'images_metadata' in page:
                result['metadata']['images_metadata'].extend(page['images_metadata'])
        
        return result


# 전역 서비스 인스턴스
azure_document_intelligence_service = AzureDocumentIntelligenceService()
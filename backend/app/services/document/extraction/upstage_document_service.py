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
import logging
import time
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
        pages: Optional[List[Dict[str, Any]]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
        figures: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]]] = None,
        error: Optional[str] = None,
        extraction_method: str = "upstage_document_parse"
    ):
        self.success = success
        self.text = text
        self.pages = pages or []
        self.tables = tables or []
        self.figures = figures or []
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
        
        if not self.api_key:
            logger.warning("[UPSTAGE] API 키가 설정되지 않았습니다. UPSTAGE_API_KEY 환경 변수를 확인하세요.")
    
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
                logger.info(f"[UPSTAGE]       - 페이지 수: {len(result.pages)}")
                logger.info(f"[UPSTAGE]       - 테이블 수: {len(result.tables)}")
                logger.info(f"[UPSTAGE]       - 이미지 수: {len(result.figures)}")
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
                    
            except Exception as e:
                last_error = str(e)
                retry_reasons.append(f"Attempt {attempt}: {type(e).__name__}: {str(e)}")
                logger.warning(f"[UPSTAGE] ⚠️ API 호출 예외: 시도 {attempt}, error={e}")
            
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
    
    def _parse_response(self, data: Dict[str, Any]) -> UpstageResult:
        """Upstage API 응답을 내부 형식으로 변환"""
        
        try:
            logger.debug(f"[UPSTAGE] 📋 응답 데이터 구조: {list(data.keys())}")
            
            # Upstage API 응답 구조:
            # {
            #   "content": {...},
            #   "model": "document-parse-v1.0",
            #   "usage": {...}
            # }
            
            content = data.get("content", {})
            logger.debug(f"[UPSTAGE] 📋 content 구조: {list(content.keys())}")
            
            # 페이지별 텍스트 추출
            pages = []
            full_text = ""
            
            if "pages" in content:
                logger.info(f"[UPSTAGE] 📄 페이지 데이터 파싱 중: {len(content['pages'])}개 페이지")
                for page_data in content["pages"]:
                    page_num = page_data.get("page", 0)
                    page_text = page_data.get("text", "")
                    
                    pages.append({
                        "page_number": page_num,
                        "text": page_text,
                        "width": page_data.get("width", 0),
                        "height": page_data.get("height", 0)
                    })
                    
                    full_text += page_text + "\n\n"
                
                logger.debug(f"[UPSTAGE] 📄 페이지 파싱 완료: 총 {len(full_text)} 문자")
            
            # 테이블 추출
            tables = []
            if "tables" in content:
                logger.info(f"[UPSTAGE] 📊 테이블 데이터 파싱 중: {len(content['tables'])}개 테이블")
                for idx, table_data in enumerate(content["tables"]):
                    tables.append({
                        "table_index": idx,
                        "page": table_data.get("page", 0),
                        "bbox": table_data.get("bbox", []),
                        "html": table_data.get("html", ""),
                        "markdown": table_data.get("markdown", "")
                    })
                logger.debug(f"[UPSTAGE] 📊 테이블 파싱 완료")
            
            # Figure 추출
            figures = []
            if "figures" in content:
                logger.info(f"[UPSTAGE] 🖼️ Figure 데이터 파싱 중: {len(content['figures'])}개 Figure")
                for idx, figure_data in enumerate(content["figures"]):
                    caption = figure_data.get("caption", "")
                    image_data = figure_data.get("image", "")
                    
                    figures.append({
                        "figure_index": idx,
                        "page": figure_data.get("page", 0),
                        "bbox": figure_data.get("bbox", []),
                        "caption": caption,
                        "image": image_data  # base64 인코딩
                    })
                    
                    logger.debug(f"[UPSTAGE]    Figure {idx}: page={figure_data.get('page')}, "
                                f"caption_len={len(caption)}, image_size={len(image_data)} bytes")
                
                logger.debug(f"[UPSTAGE] 🖼️ Figure 파싱 완료")
            
            # 메타데이터
            usage = data.get("usage", {})
            metadata = {
                "model": data.get("model", "unknown"),
                "usage": usage,
                "page_count": len(pages),
                "table_count": len(tables),
                "figure_count": len(figures)
            }
            
            logger.info(f"[UPSTAGE] ✅ 응답 파싱 완료")
            logger.info(f"[UPSTAGE]    📊 최종 통계:")
            logger.info(f"[UPSTAGE]       - 페이지: {len(pages)}")
            logger.info(f"[UPSTAGE]       - 테이블: {len(tables)}")
            logger.info(f"[UPSTAGE]       - Figure: {len(figures)}")
            logger.info(f"[UPSTAGE]       - 텍스트: {len(full_text)} 문자")
            if usage:
                logger.info(f"[UPSTAGE]       - Usage: {usage}")
            
            return UpstageResult(
                success=True,
                text=full_text.strip(),
                pages=pages,
                tables=tables,
                figures=figures,
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
                "page_count": len(upstage_result.pages),
                "table_count": len(upstage_result.tables),
                "figure_count": len(upstage_result.figures),
                "extraction_method": "upstage_document_parse",
                "upstage_model": upstage_result.metadata.get("model", "unknown"),
                "pages": upstage_result.pages,
                "tables": upstage_result.tables,
                "figures": upstage_result.figures
            },
            "success": True,
            "error": None,
            "text_length": len(upstage_result.text),
            "extraction_method": "upstage_document_parse"
        }


# 싱글톤 인스턴스
upstage_document_service = UpstageDocumentService()

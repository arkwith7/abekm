"""
학술 논문 처리 파이프라인

학술 논문 특화 처리:
- 섹션 자동 감지 (Abstract, Introduction, Methods, Results, Discussion, Conclusion, References)
- Figure/Table 캡션 우선 추출
- Abstract, Conclusion 섹션 우선 처리
- References 섹션 파싱
- 수식 추출 (옵션)
"""
from typing import Dict, Any
import logging
import json
from datetime import datetime

from app.services.document.pipelines.general_pipeline import GeneralPipeline
from app.services.document.extraction.adaptive_section_detector import AdaptiveSectionDetector
from app.core.database import get_async_session_local
from app.services.document.processing.bibliography_service import BibliographyService

logger = logging.getLogger(__name__)


class AcademicPaperPipeline(GeneralPipeline):
    """
    학술 논문 처리 파이프라인
    
    현재는 GeneralPipeline을 상속받아 기본 기능 사용.
    향후 논문 특화 기능 추가 예정:
    - 섹션 기반 청킹 (Abstract, Introduction, Methodology, Results, Discussion, Conclusion)
    - Figure/Table 캡션 우선 처리
    - References 파싱
    - 수식(LaTeX) 추출
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 적응형 섹션 감지 서비스 초기화
        self.section_detector = AdaptiveSectionDetector()
        
        # 논문 특화 옵션
        self.extract_figures = self._get_option("extract_figures", True)
        self.parse_references = self._get_option("parse_references", True)
        self.extract_equations = self._get_option("extract_equations", False)
        self.priority_sections = self._get_option("priority_sections", ["abstract", "conclusion"])
        self.figure_caption_required = self._get_option("figure_caption_required", True)
        
        logger.info(f"📚 [AcademicPaperPipeline] 초기화 완료")
        logger.info(f"   🖼️ Figure 추출: {self.extract_figures}")
        logger.info(f"   📖 References 파싱: {self.parse_references}")
        logger.info(f"   🔢 수식 추출: {self.extract_equations}")
        logger.info(f"   ⭐ 우선 섹션: {self.priority_sections}")
    
    async def process(self) -> Dict[str, Any]:
        """멀티모달 파이프라인 + 학술논문 섹션 감지"""
        logger.info(f"🚀 [AcademicPaperPipeline] 파이프라인 시작: {self.file_name}")
        
        # 기본 멀티모달 파이프라인 실행
        result = await super().process()
        
        if not result.get("success"):
            return result
        
        statistics = result.get("statistics") or {}
        section_meta = statistics.get("section_chunking") if isinstance(statistics, dict) else None

        if section_meta and section_meta.get("stored_to_blob"):
            logger.info("[AcademicPaperPipeline] 섹션 감지가 청킹 단계에서 완료되어 재실행 생략")
            logger.info("[AcademicPaperPipeline] ⚠️ 서지정보 upsert는 청킹 단계에서 처리되지 않았으므로 여기서 실행 필요")
            # 청킹 단계에서 섹션은 감지했지만 서지정보는 저장 안 했으므로 여기서 처리
            try:
                await self._upsert_bibliography_only()
            except Exception as e:
                logger.error(f"⚠️ [AcademicPaperPipeline] 서지정보 upsert 실패 (계속 진행): {e}", exc_info=True)
        else:
            # 섹션 감지 추가 처리
            logger.info("[AcademicPaperPipeline] 섹션 감지 및 서지정보 upsert 시작")
            try:
                await self._detect_and_save_sections()
            except Exception as e:
                logger.error(f"⚠️ [AcademicPaperPipeline] 섹션 감지 실패 (계속 진행): {e}", exc_info=True)
        
        logger.info(f"✅ [AcademicPaperPipeline] 파이프라인 완료")
        return result
    
    async def _detect_and_save_sections(self):
        """추출된 텍스트에서 섹션 감지"""
        # Blob에서 전체 텍스트 로드
        try:
            from app.services.core.azure_blob_service import get_azure_blob_service
            blob_service = get_azure_blob_service()
            
            # extraction_full_text.txt 다운로드
            blob_path = f"multimodal/{self.document_id}/extraction_full_text.txt"
            full_text = blob_service.download_text(
                blob_path=blob_path,
                purpose='intermediate'
            )
            
            if not full_text:
                logger.warning("[SECTION-DETECT] 전체 텍스트를 찾을 수 없음")
                return
            
            # 섹션 감지
            sections = self.section_detector.detect_sections(full_text)
            
            if sections:
                # 섹션 요약 통계
                summary = self.section_detector.get_section_summary(sections)
                logger.info(
                    f"[SECTION-DETECT] {summary['total_sections']}개 섹션 감지: "
                    f"{', '.join(summary['sections_found'])}"
                )
                logger.info(
                    f"[SECTION-DETECT] Abstract: {summary['abstract_words']}단어, "
                    f"References 시작: {summary['references_start_page']}페이지"
                )
                
                # Blob에 섹션 정보 저장
                sections_blob_path = f"multimodal/{self.document_id}/sections.json"
                sections_data = {
                    "sections": sections,
                    "summary": summary,
                    "detected_at": datetime.now().isoformat()
                }
                blob_service.upload_bytes(
                    data=json.dumps(sections_data, ensure_ascii=False, indent=2).encode("utf-8"),
                    blob_path=sections_blob_path,
                    purpose='intermediate'
                )
                logger.info(f"[SECTION-DETECT] 섹션 정보 저장: {sections_blob_path}")

                # 학술 논문 서지정보 최소 upsert (제목/초록/DOI/연도)
                try:
                    async_session_local = get_async_session_local()
                    async with async_session_local() as session:
                        biblio = BibliographyService(session)
                        # 첫 페이지 텍스트(있다면) 추출
                        first_page_text = None
                        try:
                            pages = sections_data.get("summary", {}).get("pages", []) or []
                        except Exception:
                            pages = []
                        # 현재 저장 구조엔 페이지 원문이 요약에 없으므로 None 처리
                        upsert_res = await biblio.upsert_document_metadata(
                            file_bss_info_sno=self.document_id,
                            full_text=full_text,
                            sections_summary=sections_data,  # 전체 sections.json 데이터 전달
                            first_page_text=first_page_text,
                        )
                        if not upsert_res.get("success"):
                            logger.warning(f"[BIBLIO] Upsert failed (non-fatal): {upsert_res.get('error')}")
                        else:
                            logger.info(
                                f"[BIBLIO] Upsert success: doi={upsert_res.get('doi')}, year={upsert_res.get('year')}, title={upsert_res.get('title')}"
                            )
                except Exception as e:
                    logger.warning(f"[BIBLIO] Upsert exception (non-fatal): {e}")
            else:
                logger.warning("[SECTION-DETECT] 섹션을 감지하지 못함")
                
        except Exception as e:
            logger.error(f"[SECTION-DETECT] 섹션 감지 중 오류: {e}", exc_info=True)
            raise
    
    async def _upsert_bibliography_only(self):
        """
        섹션 감지가 이미 완료된 경우 서지정보만 upsert
        """
        try:
            from app.services.core.azure_blob_service import get_azure_blob_service
            blob_service = get_azure_blob_service()
            
            # 전체 텍스트 로드
            blob_path = f"multimodal/{self.document_id}/extraction_full_text.txt"
            full_text = blob_service.download_text(
                blob_path=blob_path,
                purpose='intermediate'
            )
            
            if not full_text:
                logger.warning("[BIBLIO-ONLY] 전체 텍스트를 찾을 수 없음")
                return
            
            # 섹션 정보 로드 (있다면)
            sections_blob_path = f"multimodal/{self.document_id}/sections.json"
            try:
                sections_json = blob_service.download_text(sections_blob_path, purpose='intermediate')
                sections_data = json.loads(sections_json) if sections_json else {}
                # 전체 sections_data를 전달 (sections 배열과 summary 모두 포함)
            except Exception as e:
                logger.warning(f"[BIBLIO-ONLY] 섹션 정보 로드 실패: {e}")
                sections_data = None
            
            # 서지정보 upsert
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                biblio = BibliographyService(session)
                upsert_res = await biblio.upsert_document_metadata(
                    file_bss_info_sno=self.document_id,
                    full_text=full_text,
                    sections_summary=sections_data,  # 전체 sections.json 데이터 전달
                    first_page_text=None,
                )
                if not upsert_res.get("success"):
                    logger.warning(f"[BIBLIO-ONLY] Upsert failed: {upsert_res.get('error')}")
                else:
                    title = upsert_res.get('title') or ''
                    logger.info(
                        f"[BIBLIO-ONLY] ✅ Upsert success: doi={upsert_res.get('doi')}, "
                        f"year={upsert_res.get('year')}, title={title[:50]}..."
                    )
        except Exception as e:
            logger.error(f"[BIBLIO-ONLY] 서지정보 upsert 중 오류: {e}", exc_info=True)
    
    # 🔜 향후 추가 메서드들 (placeholder)
    
    # def _filter_figures_with_caption(self, extracted_objects: List[Dict]) -> List[Dict]:
    #     """
    #     캡션이 있는 Figure만 필터링
    #     """
    #     filtered = []
    #     for obj in extracted_objects:
    #         if obj.get("object_type") == "image":
    #             if not self.figure_caption_required or obj.get("content_text"):
    #                 filtered.append(obj)
    #         else:
    #             filtered.append(obj)
    #     return filtered
    
    # def _apply_section_priority(self, chunks: List[Dict]) -> List[Dict]:
    #     """
    #     섹션 기반 우선순위 적용
    #     """
    #     for chunk in chunks:
    #         section = chunk.get("section", "").lower()
    #         if section in self.priority_sections:
    #             chunk["priority"] = "high"
    #         else:
    #             chunk["priority"] = "normal"
    #     return chunks

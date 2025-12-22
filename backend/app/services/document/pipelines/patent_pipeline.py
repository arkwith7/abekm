"""
특허 문서 처리 파이프라인

특허 문서 특화 처리:
- 정형화된 섹션 자동 감지 (청구항, 명세서, 도면 등)
- 청구항 우선 처리 (독립항/종속항 분리)
- 섹션별 청킹 및 메타데이터 저장
- 특허 서지정보 추출 (출원번호, 발명자, IPC 등)
"""
from typing import Dict, Any, Optional, Callable
import logging
import json
from datetime import datetime

from app.services.document.pipelines.general_pipeline import GeneralPipeline
from app.services.document.extraction.patent_section_detector import PatentSectionDetector, PatentSection
from app.core.database import get_async_session_local

logger = logging.getLogger(__name__)


class PatentPipeline(GeneralPipeline):
    """
    특허 문서 처리 파이프라인
    
    GeneralPipeline을 상속받아 기본 멀티모달 처리 수행 후
    특허 특화 기능 추가:
    - 특허 섹션 감지 (청구항, 배경, 상세설명 등)
    - 청구항 개별 항 분리 및 우선 처리
    - 섹션별 메타데이터 저장
    - 특허 서지정보 DB 저장
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 특허 섹션 감지 서비스 초기화
        self.section_detector = PatentSectionDetector()
        
        # 특허 특화 옵션
        self.extract_claims = self._get_option("extract_claims", True)
        self.parse_citations = self._get_option("parse_citations", False)
        self.technical_field_extraction = self._get_option("technical_field_extraction", True)
        self.priority_claims = self._get_option("priority_claims", True)
        
        logger.info(f"📜 [PatentPipeline] 초기화 완료")
        logger.info(f"   ⚖️ 청구항 추출: {self.extract_claims}")
        logger.info(f"   🔗 인용 특허 파싱: {self.parse_citations}")
        logger.info(f"   🔬 기술분야 추출: {self.technical_field_extraction}")
        logger.info(f"   ⭐ 청구항 우선 처리: {self.priority_claims}")

    def _get_storage_adapter(
        self,
    ) -> tuple[str, Optional[Callable[[str], str]], Optional[Callable[[str, bytes, str], None]]]:
        """스토리지 백엔드별 텍스트 다운로드/업로드 헬퍼"""
        from app.core.config import settings

        backend = getattr(settings, 'storage_backend', 's3').lower()

        if backend == 'azure_blob':
            from app.services.core.azure_blob_service import get_azure_blob_service

            blob_service = get_azure_blob_service()

            def download_text(key: str) -> str:
                return blob_service.download_text(key, purpose='intermediate')

            def upload_bytes(key: str, data: bytes, content_type: str = 'text/plain; charset=utf-8') -> None:
                blob_service.upload_bytes(data, key, purpose='intermediate')

            return backend, download_text, upload_bytes

        if backend == 's3':
            from app.services.core.aws_service import S3Service

            s3_service = S3Service()

            def download_text(key: str) -> str:
                # S3에서는 intermediate/ prefix가 자동으로 붙으므로 추가
                full_key = f"intermediate/{key}" if not key.startswith('intermediate/') else key
                return s3_service.download_text(full_key)

            def upload_bytes(key: str, data: bytes, content_type: str = 'text/plain; charset=utf-8') -> None:
                # upload_bytes는 이미 purpose='intermediate'로 호출되므로 prefix 자동 추가됨
                full_key = f"intermediate/{key}" if not key.startswith('intermediate/') else key
                put_params = {
                    'Bucket': s3_service.bucket_name,
                    'Key': full_key,
                    'Body': data
                }
                if content_type:
                    put_params['ContentType'] = content_type
                s3_service.s3_client.put_object(**put_params)

            return backend, download_text, upload_bytes

        return backend, None, None
    
    async def process(self) -> Dict[str, Any]:
        """멀티모달 파이프라인 + 특허 섹션 감지 (전처리)"""
        logger.info(f"🚀 [PatentPipeline] 파이프라인 시작: {self.file_name}")
        
        # 기본 멀티모달 파이프라인 실행 (추출, 청킹, 임베딩, 인덱싱)
        result = await super().process()
        
        if not result.get("success"):
            return result
        
        # 특허 섹션 감지 추가 처리 (후처리)
        # 청킹 단계에서 이미 extraction_full_text.txt가 저장되었으므로
        # 이를 로드하여 특허 섹션 감지 수행
        logger.info("[PatentPipeline] 특허 섹션 감지 시작")
        try:
            await self._detect_and_save_patent_sections()
        except Exception as e:
            logger.error(f"⚠️ [PatentPipeline] 특허 섹션 감지 실패 (계속 진행): {e}", exc_info=True)
        
        logger.info(f"✅ [PatentPipeline] 파이프라인 완료")
        return result
    
    async def _detect_and_save_patent_sections(self):
        """추출된 텍스트에서 특허 섹션 감지 (동적 스토리지 백엔드)"""
        # 스토리지 백엔드에서 전체 텍스트 로드
        try:
            storage_backend, download_text, upload_bytes = self._get_storage_adapter()
            blob_key = f"multimodal/{self.document_id}/extraction_full_text.txt"

            if not download_text:
                logger.warning(f"[PATENT-SECTION] 지원되지 않는 스토리지 백엔드: {storage_backend}")
                return

            try:
                full_text = download_text(blob_key)
            except Exception as exc:
                logger.error(f"[PATENT-SECTION] 전체 텍스트 다운로드 실패 ({storage_backend}): {exc}")
                return
            
            if not full_text:
                logger.warning("[PATENT-SECTION] 전체 텍스트를 찾을 수 없음")
                return
            
            # 특허 섹션 감지
            sections = self.section_detector.detect_sections(full_text)
            
            if sections:
                # 섹션 요약 통계
                summary = self.section_detector.get_section_summary(sections)
                logger.info(
                    f"[PATENT-SECTION] {summary['total_sections']}개 섹션 감지: "
                    f"{', '.join(summary['sections_found'])}"
                )
                logger.info(
                    f"[PATENT-SECTION] 청구항: {summary['claims_count']}개 항"
                )
                
                # 섹션 정보를 JSON으로 직렬화 (PatentSection → dict)
                sections_data = {
                    "sections": [self._section_to_dict(s) for s in sections],
                    "summary": summary,
                    "detected_at": datetime.now().isoformat()
                }
                
                # Blob에 섹션 정보 저장
                sections_blob_path = f"multimodal/{self.document_id}/patent_sections.json"
                if upload_bytes:
                    upload_bytes(
                        sections_blob_path,
                        json.dumps(sections_data, ensure_ascii=False, indent=2).encode("utf-8"),
                        content_type='application/json; charset=utf-8'
                    )
                    logger.info(f"[PATENT-SECTION] 섹션 정보 저장({storage_backend}): {sections_blob_path}")
                else:
                    logger.warning("[PATENT-SECTION] 업로드 헬퍼가 없어 섹션 정보를 저장하지 못함")

                # 특허 서지정보 저장 (향후 구현)
                # await self._save_patent_bibliographic_info(full_text, sections_data)
                
            else:
                logger.warning("[PATENT-SECTION] 특허 섹션을 감지하지 못함")
                
        except Exception as e:
            logger.error(f"[PATENT-SECTION] 섹션 감지 중 오류: {e}", exc_info=True)
            raise
    
    def _section_to_dict(self, section: PatentSection) -> Dict[str, Any]:
        """PatentSection 객체를 딕셔너리로 변환 (JSON 직렬화용)"""
        result = {
            "section_type": section.section_type,
            "title": section.title,
            "start_pos": section.start_pos,
            "end_pos": section.end_pos,
            "content": section.content[:500] + "..." if len(section.content) > 500 else section.content,  # 요약만 저장
            "content_length": len(section.content),
            "priority": section.priority
        }
        
        # 하위 섹션 (청구항의 경우 개별 항)
        if section.subsections:
            result["subsections"] = [self._section_to_dict(sub) for sub in section.subsections]
        
        return result
    
    async def _save_patent_bibliographic_info(self, full_text: str, sections_data: Dict):
        """
        특허 서지정보 DB 저장
        
        🔜 향후 구현:
        - 출원번호 추출 (정규식)
        - 발명자/출원인 추출 (첫 페이지 파싱)
        - IPC 분류 추출
        - 출원일/등록일 추출
        - TbPatentBibliographicInfo 테이블에 저장
        """
        try:
            logger.info("[PATENT-BIBLIO] 특허 서지정보 추출 시작")
            
            # 출원번호 패턴 (예: "출원번호: 10-2023-0012345")
            application_number = self._extract_application_number(full_text)
            if application_number:
                logger.info(f"[PATENT-BIBLIO] 출원번호 발견: {application_number}")
            
            # 향후 DB 저장 로직 추가
            # async_session_local = get_async_session_local()
            # async with async_session_local() as session:
            #     # TbPatentBibliographicInfo 생성/업데이트
            #     pass
            
            logger.info("[PATENT-BIBLIO] ✅ 서지정보 추출 완료")
        except Exception as e:
            logger.warning(f"[PATENT-BIBLIO] 서지정보 추출 실패 (non-fatal): {e}")
    
    def _extract_application_number(self, text: str) -> Optional[str]:
        """
        출원번호 추출
        
        한국 특허 출원번호 형식:
        - 10-2023-0012345
        - 10-2023-12345
        - KR 10-2023-0012345
        """
        import re
        pattern = r'(?:출원번호|Application\s+No\.?)\s*[:：]\s*((?:KR\s+)?10-\d{4}-\d+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    # 🔜 향후 추가 메서드들 (placeholder)
    
    # def _parse_patent_claims(self, claims_section: PatentSection) -> List[Dict]:
    #     """
    #     청구항 파싱 (독립항/종속항 구분)
    #     """
    #     pass
    
    # def _extract_technical_field(self, text: str) -> Optional[str]:
    #     """
    #     기술분야 추출
    #     """
    #     pass
    
    # def _parse_cited_patents(self, prior_art_section: PatentSection) -> List[Dict]:
    #     """
    #     인용 특허 파싱
    #     """
    #     pass

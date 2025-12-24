"""
특허 문서 처리 파이프라인

특허 문서 특화 처리:
- 정형화된 섹션 자동 감지 (청구항, 명세서, 도면 등)
- 청구항 우선 처리 (독립항/종속항 분리)
- 섹션별 청킹 및 메타데이터 저장
- 특허 서지정보 추출 (출원번호, 발명자, IPC 등)
"""
from typing import Dict, Any, Optional, Callable, Tuple
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
        """멀티모달 파이프라인 + 특허 섹션 감지 및 청킹 메타데이터 보강"""
        logger.info(f"🚀 [PatentPipeline] 파이프라인 시작: {self.file_name}")
        
        # 1. 기본 멀티모달 파이프라인 실행 (추출, 청킹, 임베딩, 인덱싱)
        result = await super().process()
        
        if not result.get("success"):
            return result
        
        # 2. 특허 섹션 감지 추가 처리 (후처리)
        logger.info("[PatentPipeline] 특허 섹션 감지 및 청킹 메타데이터 보강 시작")
        try:
            sections_data, full_text = await self._detect_and_save_patent_sections()
            
            # 3. 섹션 정보를 청크에 매핑 (section_heading 업데이트)
            if sections_data and sections_data.get("sections") and full_text:
                await self._enrich_chunks_with_sections(sections_data["sections"], full_text)
            
        except Exception as e:
            logger.error(f"⚠️ [PatentPipeline] 특허 섹션 감지 실패 (계속 진행): {e}", exc_info=True)
        
        logger.info(f"✅ [PatentPipeline] 파이프라인 완료")
        return result
    
    async def _detect_and_save_patent_sections(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """추출된 텍스트에서 특허 섹션 감지 및 저장 (동적 스토리지 백엔드)"""
        # 스토리지 백엔드에서 전체 텍스트 로드
        try:
            storage_backend, download_text, upload_bytes = self._get_storage_adapter()
            blob_key = f"multimodal/{self.document_id}/extraction_full_text.txt"

            if not download_text:
                logger.warning(f"[PATENT-SECTION] 지원되지 않는 스토리지 백엔드: {storage_backend}")
                return None

            try:
                full_text = download_text(blob_key)
            except Exception as exc:
                logger.error(f"[PATENT-SECTION] 전체 텍스트 다운로드 실패 ({storage_backend}): {exc}")
                return None
            
            if not full_text:
                logger.warning("[PATENT-SECTION] 전체 텍스트를 찾을 수 없음")
                return None
            
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
                
                # 선행기술문헌(인용문헌) 추출 (있으면 구조화해서 함께 저장)
                prior_art_citations: list[str] = []
                try:
                    for s in sections:
                        if s.section_type == "prior_art":
                            prior_art_citations = self.section_detector.extract_prior_art_citations(s.content)
                            break
                except Exception as exc:
                    logger.warning(f"[PATENT-SECTION] 선행기술문헌 인용 추출 실패 (non-fatal): {exc}")

                # 섹션 정보를 JSON으로 직렬화 (PatentSection → dict)
                sections_data = {
                    "sections": [self._section_to_dict(s) for s in sections],
                    "summary": summary,
                    "prior_art_citations": prior_art_citations,
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
                
                return sections_data, full_text
            else:
                logger.warning("[PATENT-SECTION] 특허 섹션을 감지하지 못함")
                return None, full_text
                
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
    
    async def _enrich_chunks_with_sections(self, sections: list[Dict[str, Any]], full_text: str):
        """
        청크에 섹션 정보 매핑 (section_heading 업데이트)
        
        각 청크의 텍스트 시작 위치를 특허 섹션 범위와 비교하여
        해당 섹션의 제목을 section_heading에 설정
        """
        try:
            from app.models.document.multimodal_models import DocChunk
            from sqlalchemy import select, update
            
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                # DB에서 해당 문서의 청크 조회
                stmt = select(DocChunk).where(DocChunk.file_bss_info_sno == self.document_id)
                result = await session.execute(stmt)
                chunks = list(result.scalars().all())
                
                if not chunks:
                    logger.warning(f"[PATENT-CHUNK-ENRICH] 문서 ID {self.document_id}에 대한 청크를 찾을 수 없음")
                    return

                # 청크를 인덱스 순으로 정렬 (순차적 처리를 위해)
                chunks.sort(key=lambda x: x.chunk_index)
                
                # 1. 각 청크의 위치 찾기 (Two-Pass Approach)
                chunk_positions = []  # (chunk, start_pos, end_pos)
                current_search_pos = 0
                
                for chunk in chunks:
                    # NOTE: table 청크에도 섹션 헤딩(예: (54) 발명의 명칭)이 포함될 수 있으므로
                    #       text/table 모두를 대상으로 위치 탐색 및 섹션 매핑을 수행한다.
                    if chunk.modality not in {"text", "table"}:
                        chunk_positions.append((chunk, -1, -1))
                        continue
                        
                    chunk_text = chunk.content_text
                    if not chunk_text:
                        chunk_positions.append((chunk, -1, -1))
                        continue
                        
                    # 위치 찾기 로직 (기존과 동일)
                    chunk_start_pos = -1
                    
                    # 1. 정확한 매칭
                    if len(chunk_text) > 10:
                        chunk_start_pos = full_text.find(chunk_text, current_search_pos)
                    
                    # 2. 앞부분 매칭 (50자)
                    if chunk_start_pos == -1 and len(chunk_text) >= 50:
                        chunk_start_pos = full_text.find(chunk_text[:50], current_search_pos)
                        
                    # 3. 중간부분 매칭
                    if chunk_start_pos == -1 and len(chunk_text) > 100:
                        mid_idx = len(chunk_text) // 2
                        mid_text = chunk_text[mid_idx : mid_idx + 50]
                        mid_pos = full_text.find(mid_text, current_search_pos)
                        if mid_pos != -1:
                            chunk_start_pos = max(current_search_pos, mid_pos - mid_idx)
                            
                    # 4. 공백 유연 매칭
                    if chunk_start_pos == -1:
                        try:
                            import re
                            clean_start = "".join(c for c in chunk_text[:30] if c.isalnum())
                            if clean_start:
                                pattern_str = r"\s*".join(list(map(re.escape, clean_start)))
                                match = re.search(pattern_str, full_text[current_search_pos:])
                                if match:
                                    chunk_start_pos = current_search_pos + match.start()
                        except Exception:
                            pass
                    
                    if chunk_start_pos != -1:
                        chunk_end_pos = chunk_start_pos + len(chunk_text)
                        chunk_positions.append((chunk, chunk_start_pos, chunk_end_pos))
                        # 다음 검색 위치 업데이트 (겹침 고려하여 절반만 전진)
                        current_search_pos = chunk_start_pos + (len(chunk_text) // 2)
                    else:
                        chunk_positions.append((chunk, -1, -1))
                
                # 2. 위치 보간 (Interpolation)
                last_valid_end = 0
                for i, (chunk, start, end) in enumerate(chunk_positions):
                    if start == -1:
                        # 위치를 못 찾은 경우: 이전 유효 위치 바로 뒤로 가정
                        if chunk.modality in {"text", "table"} and chunk.content_text:
                            interpolated_start = last_valid_end
                            interpolated_end = interpolated_start + len(chunk.content_text)
                            chunk_positions[i] = (chunk, interpolated_start, interpolated_end)
                            # 다음 청크를 위해 last_valid_end 업데이트
                            last_valid_end = interpolated_end
                    else:
                        last_valid_end = end
                
                # 3. 섹션 매핑
                update_count = 0
                for chunk, start, end in chunk_positions:
                    if start == -1:
                        continue

                    # 섹션 선택: 기본은 overlap 최대 (기존 품질 유지)
                    matching_section = None
                    best_overlap = 0

                    for section in sections:
                        s_start = int(section.get("start_pos", 0))
                        s_end = int(section.get("end_pos", 0))
                        overlap = min(end, s_end) - max(start, s_start)
                        if overlap > best_overlap:
                            best_overlap = overlap
                            matching_section = section

                    # overlap이 0이면 fallback: center/start 기준
                    if not matching_section:
                        center_pos = (start + end) // 2
                        for section in sections:
                            if section["start_pos"] <= center_pos < section["end_pos"]:
                                matching_section = section
                                break
                        if not matching_section:
                            for section in sections:
                                if section["start_pos"] <= start < section["end_pos"]:
                                    matching_section = section
                                    break

                    # 특정 섹션(짧거나 표/띄어쓰기 변형으로 chunk가 섞이는 경우) 보정
                    # - 발명의 명칭: 표(table) 청크에 포함되는 경우가 많음
                    # - 기술분야: '기 술 분 야' 처럼 띄어쓰기 변형이 흔함
                    try:
                        import re

                        chunk_text = chunk.content_text or ""

                        if chunk_text:
                            # '발명의 명칭'은 (54) 표기/테이블 파이프라인에서 자주 등장
                            if re.search(r"(?:^|\n|\|)\s*(?:\(54\)\s*)?발\s*명\s*의\s*명\s*칭", chunk_text):
                                forced = next((s for s in sections if s.get("title") == "발명의 명칭"), None)
                                if forced:
                                    matching_section = forced

                            # '기술분야'는 본문에도 '기술 분야에서 ...'로 흔히 등장하므로
                            # 헤딩 형태(라인 시작 + 뒤에 개행/대괄호 등)만 매칭
                            if re.search(r"(?:^|\n)\s*기\s*술\s*분\s*야\s*(?:\n|\[)", chunk_text):
                                forced = next((s for s in sections if s.get("title") == "기술분야"), None)
                                if forced:
                                    matching_section = forced
                    except Exception:
                        pass

                    if matching_section:
                        chunk.section_heading = matching_section["title"]
                        update_count += 1
                
                # DB 커밋
                await session.commit()
                
                logger.info(f"[PATENT-CHUNK-ENRICH] ✅ {update_count}개 청크에 섹션 정보 매핑 완료")
                
        except Exception as e:
            logger.error(f"[PATENT-CHUNK-ENRICH] 청크 보강 실패: {e}", exc_info=True)
    
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

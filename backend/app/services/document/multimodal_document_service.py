"""
🎨 멀티모달 문서 처리 서비스
============================

새로운 멀티모달 스키마를 활용한 문서 추출/청킹/임베딩 파이프라인
- DocExtractionSession: 추출 세션 관리
- DocExtractedObject: 페이지별 객체 추출 (텍스트, 표, 이미지)
- DocChunkSession: 청킹 세션 관리
- DocChunk: 청크 저장
- DocEmbedding: 임베딩 벡터 저장
- Azure Blob Storage: 추출 결과 및 처리 아티팩트 저장
"""

import logging
import hashlib
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, type_coerce
from sqlalchemy.dialects.postgresql import INT4RANGE

from app.models.document.multimodal_models import (
    DocExtractionSession,
    DocExtractedObject,
    DocChunkSession,
    DocChunk,
    DocEmbedding
)
from app.models import TbDocumentSearchIndex
from app.models.document.file_models import TbFileBssInfo
from app.models.document.vector_models import VsDocContentsChunks
from app.services.document.extraction.text_extractor_service import text_extractor_service
from app.services.core.korean_nlp_service import korean_nlp_service
from app.core.config import settings
from app.services.document.chunking.advanced_chunker import advanced_chunk_text
from app.services.document.extraction.adaptive_section_detector import AdaptiveSectionDetector
from app.services.document.storage.search_index_store import SearchIndexStoreService

# Azure Blob Storage 통합
try:
    from app.services.core.azure_blob_service import get_azure_blob_service
except ImportError:
    get_azure_blob_service = None

# 이미지 특징 추출 서비스
try:
    from app.services.document.vision.image_embedding_service import (
        image_embedding_service as default_image_embedding_service,
    )
except ImportError:
    default_image_embedding_service = None

logger = logging.getLogger(__name__)

class MultimodalDocumentService:
    """멀티모달 문서 처리 서비스"""
    
    def __init__(self, image_embedding_service: Optional[Any] = None):
        """서비스 초기화"""
        self.search_index_service = SearchIndexStoreService()
        # 인스턴스 주입이 없으면 기본 전역 서비스를 사용
        self.image_embedding_service = image_embedding_service or default_image_embedding_service
        # 적응형 섹션 감지 서비스 (모든 헤더 감지 + 의미 매핑)
        self.section_detector = AdaptiveSectionDetector()
    
    async def process_document_multimodal(
        self,
        file_path: str,
        file_bss_info_sno: int,
        container_id: str,
        user_emp_no: str,
        session: AsyncSession,
        provider: Optional[str] = None,
        model_profile: str = "default",
        processing_options: Optional[Dict[str, Any]] = None,
        document_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """멀티모달 파이프라인 (리팩터 버전)

        단계:
        1) 추출 세션 + 객체 저장
        2) 고급 청킹(문단/토큰 기반)
        3) 임베딩 생성 (제로 패딩)
        4) 검색 인덱스 보강
        5) 통계 반환
        """
        started = datetime.now()
        result: Dict[str, Any] = {
            "success": False,
            "extraction_session_id": None,
            "chunk_session_id": None,
            "objects_count": 0,
            "chunks_count": 0,
            "embeddings_count": 0,
            "stats": {},
            "error": None,
            "stages": []
        }
        stage_timers: Dict[str, float] = {}

        provider = provider or settings.get_current_llm_provider()
        processing_options = processing_options or {}
        pipeline_type = processing_options.get("pipeline_type") or provider or settings.default_llm_provider
        document_type_normalized = (document_type or processing_options.get("document_type") or "").lower()
        section_chunking_requested = processing_options.get("section_chunking_enabled", True)
        apply_section_chunking = document_type_normalized == "academic_paper" and section_chunking_requested
        section_chunking_meta: Dict[str, Any] = {
            "requested": bool(apply_section_chunking),
            "enabled": False,
            "detected_sections": [],
            "chunk_counts": {},
            "stored_to_blob": False,
        }
        precomputed_sections_info: List[Dict[str, Any]] = []
        precomputed_section_summary: Optional[Dict[str, Any]] = None
        visual_page_filter: Optional[Set[int]] = None
        section_combined_text: str = ""
        section_object_spans: List[Tuple[DocExtractedObject, int, int]] = []
        image_ids_with_binary: Set[int] = set()
        image_object_ids_seen: Set[int] = set()

        def _start_stage(name: str):
            stage_timers[name] = time.perf_counter()
            logger.info(f"[MULTIMODAL][TIMER] {name} stage started")

        def _stage(name: str, success: bool, **extra):
            elapsed = None
            if name in stage_timers:
                elapsed = time.perf_counter() - stage_timers.pop(name)
                extra.setdefault("elapsed_seconds", elapsed)
            result["stages"].append({"name": name, "success": success, **extra})
            if elapsed is not None:
                logger.info(f"[MULTIMODAL][TIMER] {name} stage completed in {elapsed:.2f}s (success={success})")
            else:
                logger.info(f"[MULTIMODAL][TIMER] {name} stage completed (success={success})")

        try:
            # -----------------------------
            # 1. Extraction
            # -----------------------------
            _start_stage("extraction_setup")
            extraction_session = DocExtractionSession(
                file_bss_info_sno=file_bss_info_sno,
                provider=provider,
                model_profile=model_profile,
                pipeline_type=pipeline_type,
                status="running",
                started_at=datetime.now()
            )
            session.add(extraction_session)
            await session.flush()
            result["extraction_session_id"] = extraction_session.extraction_session_id
            _stage("extraction_setup", True, extraction_session_id=extraction_session.extraction_session_id)
            logger.info(f"[MULTIMODAL] Extraction session started: {extraction_session.extraction_session_id}")

            _start_stage("extraction")
            extraction_result = await text_extractor_service.extract_text_from_file(file_path)
            if not extraction_result.get("success"):
                # 모델 필드에 직접 할당 시 정적 타입 경고 회피 위해 setattr 사용
                setattr(extraction_session, "status", "failed")
                setattr(extraction_session, "error_message", extraction_result.get("error"))
                setattr(extraction_session, "completed_at", datetime.now())
                await session.commit()
                _stage("extraction", False, error=extraction_result.get("error"))
                result["error"] = extraction_result.get("error")
                return result

            # 실제 파일 경로 확보 (이미지 추출용)
            actual_file_path = extraction_result.get("actual_file_path", file_path)
            is_temp_file = extraction_result.get("is_temp_file", False)
            
            metadata = extraction_result.get("metadata", {})
            extracted_objects: List[DocExtractedObject] = []
            
            def _add_text_obj(page_no: Optional[int], text_val: str):
                if not text_val or not text_val.strip():
                    return
                extracted_objects.append(
                    DocExtractedObject(
                        extraction_session_id=extraction_session.extraction_session_id,
                        file_bss_info_sno=file_bss_info_sno,
                        page_no=page_no,
                        object_type="TEXT_BLOCK",
                        sequence_in_page=0,
                        content_text=text_val,
                        char_count=len(text_val),
                        token_estimate=len(text_val.split()),
                        hash_sha256=hashlib.sha256(text_val.encode()).hexdigest(),
                    )
                )

            # 전체 텍스트 재조립 헬퍼 (fallback)
            def _assemble_full_text(objs: List[DocExtractedObject]) -> str:
                try:
                    return "\n\n".join([
                        (o.content_text or "").strip()
                        for o in objs
                        if getattr(o, 'object_type', None) == 'TEXT_BLOCK' and (o.content_text or '').strip()
                    ])
                except Exception as e:
                    logger.warning(f"[MULTIMODAL] _assemble_full_text 실패: {e}")
                    return ""

            # 매니페스트 엔트리 구성 헬퍼
            def _object_to_manifest_entry(idx: int, obj: DocExtractedObject, blob_key: str) -> Dict[str, Any]:
                return {
                    "object_index": idx,
                    "object_id": getattr(obj, 'object_id', None),
                    "object_type": getattr(obj, 'object_type', None),
                    "page_no": getattr(obj, 'page_no', None),
                    "sequence_in_page": getattr(obj, 'sequence_in_page', None),
                    "blob_key": blob_key,
                    "char_count": len(getattr(obj, 'content_text', '') or ''),
                    "has_structure": bool(getattr(obj, 'structure_json', None)),
                    "bbox": getattr(obj, 'bbox', None)
                }

            # PDF
            if "pages" in metadata:
                for p in metadata["pages"]:
                    page_no = p.get("page_no")
                    page_text = p.get("text", "")
                    
                    # 페이지 bbox 계산 (전체 페이지 크기)
                    page_width = p.get("width", 0)
                    page_height = p.get("height", 0)
                    page_bbox = None
                    if page_width and page_height:
                        # 전체 페이지를 TEXT_BLOCK의 bbox로 설정
                        page_bbox = [0, 0, int(page_width * 72), int(page_height * 72)]  # inch → points 변환
                    
                    # TEXT_BLOCK 객체 생성 (bbox 포함)
                    if page_text and page_text.strip():
                        extracted_objects.append(
                            DocExtractedObject(
                                extraction_session_id=extraction_session.extraction_session_id,
                                file_bss_info_sno=file_bss_info_sno,
                                page_no=page_no,
                                object_type="TEXT_BLOCK",
                                sequence_in_page=0,
                                content_text=page_text,
                                char_count=len(page_text),
                                token_estimate=len(page_text.split()),
                                hash_sha256=hashlib.sha256(page_text.encode()).hexdigest(),
                                bbox=page_bbox
                            )
                        )
                    # Persist DI figures (if any) as FIGURE objects alongside IMAGEs
                    for fig in p.get("figures", []) or []:
                        try:
                            # Convert polygon bbox to [x0,y0,x1,y1] if possible
                            bbox_poly = fig.get("bbox") or []
                            if isinstance(bbox_poly, list) and len(bbox_poly) >= 4:
                                xs = [pt[0] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) == 2]
                                ys = [pt[1] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) == 2]
                                if xs and ys:
                                    _bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
                                else:
                                    _bbox = [0, 0, 0, 0]
                            else:
                                _bbox = [0, 0, 0, 0]
                        except Exception:
                            _bbox = [0, 0, 0, 0]

                        caption_text = (fig.get("caption") or "").strip()
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=p.get("page_no"),
                            object_type="FIGURE",
                            sequence_in_page=fig.get("figure_index") or 0,
                            bbox=_bbox,
                            content_text=caption_text,
                            structure_json=fig
                        ))
                    # ❌ 페이지별 tables_count는 사용하지 않음 (문서 레벨에서 처리)
                    
                    for img_meta in p.get("images_metadata", []):
                        # DOCX/다른 형식의 경우 binary_data를 structure_json에서 제거
                        clean_img_meta = dict(img_meta)
                        if 'binary_data' in clean_img_meta:
                            clean_img_meta.pop('binary_data')
                        
                        # 🎯 Caption 추출 (Azure DI에서 제공)
                        caption = clean_img_meta.get('caption', '') or ''
                        if caption:
                            logger.info(f"[CAPTION] 📝 이미지 캡션 발견 - page={p.get('page_no')}, caption={caption[:100]}")
                        
                        # bbox 변환: polygon [[x,y], [x,y], ...] → [x0, y0, x1, y1]
                        _bbox = [0, 0, 0, 0]
                        try:
                            # Case 1: x0, y0, x1, y1 형식 (기존)
                            if 'x0' in img_meta and 'y0' in img_meta:
                                _bbox = [
                                    int(img_meta.get('x0', 0)),
                                    int(img_meta.get('y0', 0)),
                                    int(img_meta.get('x1', 0)),
                                    int(img_meta.get('y1', 0))
                                ]
                            # Case 2: bbox polygon 형식 (Azure DI)
                            elif 'bbox' in img_meta:
                                bbox_poly = img_meta.get('bbox')
                                if isinstance(bbox_poly, list) and len(bbox_poly) >= 4:
                                    # polygon: [[x,y], [x,y], ...] → [x0, y0, x1, y1]
                                    xs = [pt[0] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                                    ys = [pt[1] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                                    if xs and ys:
                                        _bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
                                        logger.debug(f"[BBOX] polygon → rect: {bbox_poly} → {_bbox}")
                        except Exception as e:
                            logger.warning(f"[BBOX] 변환 실패: {e}, img_meta={img_meta}")
                            _bbox = [0, 0, 0, 0]
                        
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=p.get("page_no"),
                            object_type="IMAGE",
                            sequence_in_page=img_meta.get("image_index"),
                            bbox=_bbox,
                            content_text=caption,  # 🎯 Caption을 content_text에 저장
                            structure_json=clean_img_meta
                        ))
                
                # 🎯 문서 레벨 테이블 처리 (Azure DI SDK 4.x)
                # Azure DI는 analyze_result.tables를 문서 레벨에서 추출하므로,
                # metadata["tables"] 배열을 순회하며 실제 TABLE 객체를 생성합니다.
                doc_tables = metadata.get("tables", [])
                if doc_tables:
                    logger.info(f"[MULTIMODAL-EXTRACT] 📊 문서 레벨 테이블 {len(doc_tables)}개 처리 시작")
                    for table in doc_tables:
                        try:
                            # bbox polygon → rectangle 변환
                            bbox_poly = table.get("bbox") or []
                            if isinstance(bbox_poly, list) and len(bbox_poly) >= 4:
                                xs = [pt[0] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) == 2]
                                ys = [pt[1] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) == 2]
                                _bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))] if xs and ys else [0, 0, 0, 0]
                            else:
                                _bbox = [0, 0, 0, 0]
                        except Exception:
                            _bbox = [0, 0, 0, 0]
                        
                        # 테이블 텍스트 추출 (cells에서 조합)
                        table_text = ""
                        cells = table.get("cells", [])
                        if cells:
                            # cells를 행/열 순서로 정렬하여 텍스트 추출
                            sorted_cells = sorted(cells, key=lambda c: (c.get("row_index", 0), c.get("column_index", 0)))
                            table_text = " | ".join([c.get("content", "") for c in sorted_cells if c.get("content", "").strip()])
                        
                        # 페이지 번호 추출 (Azure DI 테이블은 페이지 정보가 없을 수 있음)
                        # bounding_regions에서 페이지 번호를 찾거나, bbox 좌표로 페이지 매칭
                        table_page_no = None
                        
                        # 방법 1: table 자체에 page_no가 있는 경우
                        if "page_no" in table:
                            table_page_no = table.get("page_no")
                        
                        # 방법 2: bounding_regions에서 추출
                        elif "bounding_regions" in table and table["bounding_regions"]:
                            first_region = table["bounding_regions"][0]
                            table_page_no = first_region.get("page_number") or first_region.get("page")
                        
                        # 방법 3: bbox 좌표로 페이지 매칭 (폴백)
                        if not table_page_no and _bbox != [0, 0, 0, 0]:
                            # 각 페이지의 bbox와 비교하여 가장 많이 겹치는 페이지 찾기
                            for p in metadata.get("pages", []):
                                page_width = p.get("width", 0)
                                page_height = p.get("height", 0)
                                if page_width > 0 and page_height > 0:
                                    page_bbox = [0, 0, int(page_width * 72), int(page_height * 72)]
                                    # 간단한 포함 여부 확인
                                    if (_bbox[0] >= page_bbox[0] and _bbox[1] >= page_bbox[1] and
                                        _bbox[2] <= page_bbox[2] and _bbox[3] <= page_bbox[3]):
                                        table_page_no = p.get("page_no")
                                        break
                        
                        # 페이지 번호를 찾지 못한 경우 1로 설정
                        if not table_page_no:
                            table_page_no = 1
                            logger.warning(f"[MULTIMODAL-EXTRACT] ⚠️ 테이블 페이지 번호를 찾지 못함, 기본값 1로 설정")
                        
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=table_page_no,
                            object_type="TABLE",
                            sequence_in_page=table.get("table_index") or 0,
                            bbox=_bbox,
                            content_text=table_text[:5000],  # 최대 5000자로 제한
                            structure_json=table  # 전체 테이블 구조 (cells, row_count, column_count 포함)
                        ))
                    
                    logger.info(f"[MULTIMODAL-EXTRACT] ✅ 문서 레벨 테이블 {len(doc_tables)}개 처리 완료")
                
                # 🎯 문서 레벨 figures 처리 (Azure DI SDK 4.x)
                # Azure DI는 analyze_result.figures를 문서 레벨에서 추출하고,
                # _merge_figures_into_pages()로 페이지별 분배를 시도하지만,
                # 페이지별 분배에 실패한 경우를 대비하여 문서 레벨에서도 처리합니다.
                doc_figures = metadata.get("figures", [])
                if doc_figures:
                    logger.info(f"[MULTIMODAL-EXTRACT] 📊 문서 레벨 figure {len(doc_figures)}개 처리 시작")
                    for fig in doc_figures:
                        try:
                            # bbox polygon → rectangle 변환
                            bbox_poly = fig.get("bbox") or []
                            if isinstance(bbox_poly, list) and len(bbox_poly) >= 4:
                                xs = [pt[0] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) == 2]
                                ys = [pt[1] for pt in bbox_poly if isinstance(pt, (list, tuple)) and len(pt) == 2]
                                _bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))] if xs and ys else [0, 0, 0, 0]
                            else:
                                _bbox = [0, 0, 0, 0]
                        except Exception:
                            _bbox = [0, 0, 0, 0]
                        
                        # 페이지 번호 추출 (fig.page_no 또는 bbox 좌표 매칭)
                        fig_page_no = fig.get("page_no")
                        if not fig_page_no and _bbox != [0, 0, 0, 0]:
                            # bbox 좌표로 페이지 매칭
                            for p in metadata.get("pages", []):
                                page_width = p.get("width", 0)
                                page_height = p.get("height", 0)
                                if page_width > 0 and page_height > 0:
                                    page_bbox = [0, 0, int(page_width * 72), int(page_height * 72)]
                                    if (_bbox[0] >= page_bbox[0] and _bbox[1] >= page_bbox[1] and
                                        _bbox[2] <= page_bbox[2] and _bbox[3] <= page_bbox[3]):
                                        fig_page_no = p.get("page_no")
                                        break
                        
                        if not fig_page_no:
                            fig_page_no = 1
                            logger.warning(f"[MULTIMODAL-EXTRACT] ⚠️ Figure 페이지 번호를 찾지 못함, 기본값 1로 설정")
                        
                        caption_text = (fig.get("caption") or "").strip()
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=fig_page_no,
                            object_type="FIGURE",
                            sequence_in_page=fig.get("figure_index") or 0,
                            bbox=_bbox,
                            content_text=caption_text,
                            structure_json=fig
                        ))
                    
                    logger.info(f"[MULTIMODAL-EXTRACT] ✅ 문서 레벨 figure {len(doc_figures)}개 처리 완료")
            
            # PPT
            elif "slides" in metadata:
                for s in metadata["slides"]:
                    _add_text_obj(s.get("slide_no"), s.get("text", ""))
                    for idx in range(s.get("tables_count", 0)):
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=s.get("slide_no"),
                            object_type="TABLE",
                            sequence_in_page=idx + 1,
                            content_text=f"[표 {idx+1}]",
                            structure_json={"table_index": idx}
                        ))
                    for idx in range(s.get("charts_count", 0)):
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=s.get("slide_no"),
                            object_type="FIGURE",
                            sequence_in_page=idx + 100,
                            content_text=f"[차트 {idx+1}]",
                            structure_json={"chart_index": idx}
                        ))
                    for img_meta in s.get("images_metadata", []):
                        # PPT 이미지 메타데이터에서도 binary_data 제거
                        clean_img_meta = dict(img_meta)
                        if 'binary_data' in clean_img_meta:
                            clean_img_meta.pop('binary_data')
                        _bbox = [
                            int(img_meta.get('left', 0)),
                            int(img_meta.get('top', 0)),
                            int(img_meta.get('left', 0) + img_meta.get('width', 0)),
                            int(img_meta.get('top', 0) + img_meta.get('height', 0))
                        ]
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=s.get("slide_no"),
                            object_type="IMAGE",
                            sequence_in_page=img_meta.get("image_index"),
                            bbox=_bbox,
                            structure_json=clean_img_meta
                        ))
            # XLSX
            elif "sheets" in metadata:
                for sh in metadata["sheets"]:
                    text_val = sh.get("text", "")
                    if text_val.strip():
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=sh.get("sheet_no"),
                            object_type="TABLE",
                            sequence_in_page=0,
                            content_text=text_val,
                            char_count=len(text_val),
                            structure_json=sh
                        ))

            # Fallback: pages/slides/sheets 모두 없고 text만 존재하는 경우(예: direct_text_read)
            if not extracted_objects and extraction_result.get("text"):
                raw_text = extraction_result.get("text") or ""
                if raw_text.strip():
                    extracted_objects.append(
                        DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=None,
                            object_type="TEXT_BLOCK",
                            sequence_in_page=0,
                            content_text=raw_text,
                            char_count=len(raw_text),
                            token_estimate=len(raw_text.split()),
                            hash_sha256=hashlib.sha256(raw_text.encode()).hexdigest(),
                        )
                    )
                    logger.info("[MULTIMODAL] Fallback single TEXT_BLOCK object created from raw text")

            # 섹션 감지를 선행하여 이미지/표 필터링 범위 파악 (학술 논문 한정)
            if apply_section_chunking:
                text_objs_for_sections = [
                    obj for obj in extracted_objects
                    if getattr(obj, "object_type", None) == "TEXT_BLOCK"
                    and (getattr(obj, "content_text", "") or "").strip()
                ]
                if text_objs_for_sections:
                    separator = "\n\n"
                    combined_parts: List[str] = []
                    section_object_spans = []
                    current_pos = 0
                    for obj in text_objs_for_sections:
                        content = (getattr(obj, "content_text", "") or "").strip()
                        if not content:
                            continue
                        if combined_parts:
                            combined_parts.append(separator)
                            current_pos += len(separator)
                        start_pos = current_pos
                        combined_parts.append(content)
                        current_pos += len(content)
                        section_object_spans.append((obj, start_pos, current_pos))
                    section_combined_text = "".join(combined_parts)

                    if section_combined_text.strip():
                        # Pass DI pages so detector can leverage Azure paragraph roles
                        precomputed_sections_info = self.section_detector.detect_sections(
                            section_combined_text,
                            pages=metadata.get("pages") or None,
                        )
                        if precomputed_sections_info:
                            precomputed_section_summary = self.section_detector.get_section_summary(precomputed_sections_info)
                            section_chunking_meta["detected_sections"] = [s.get("type") for s in precomputed_sections_info]
                            if precomputed_section_summary:
                                section_chunking_meta.setdefault("summary", precomputed_section_summary)

                            visual_page_filter = self._derive_core_content_page_set(
                                precomputed_sections_info,
                                section_object_spans,
                            )

                            # Derive allowed pages; if too narrow or unavailable, widen using safe defaults
                            total_pages = len(metadata.get('pages', metadata.get('slides', metadata.get('sheets', []))))
                            if visual_page_filter:
                                counts_before = {
                                    "IMAGE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "IMAGE"),
                                    "TABLE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "TABLE"),
                                    "FIGURE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "FIGURE"),
                                }
                                filtered_objects: List[DocExtractedObject] = []
                                removed_counts = {"IMAGE": 0, "TABLE": 0, "FIGURE": 0}
                                for obj in extracted_objects:
                                    otype = getattr(obj, "object_type", None)
                                    if otype in removed_counts:
                                        page_no = getattr(obj, "page_no", None)
                                        if page_no is not None and page_no not in visual_page_filter:
                                            removed_counts[otype] += 1
                                            continue
                                    filtered_objects.append(obj)

                                if len(filtered_objects) != len(extracted_objects):
                                    extracted_objects = filtered_objects
                                    logger.info(
                                        "[MULTIMODAL] 섹션 범위 필터 적용 - 이미지 %s개, 표 %s개, 차트 %s개 제외",
                                        removed_counts["IMAGE"],
                                        removed_counts["TABLE"],
                                        removed_counts["FIGURE"],
                                    )

                                counts_after = {
                                    "IMAGE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "IMAGE"),
                                    "TABLE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "TABLE"),
                                    "FIGURE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "FIGURE"),
                                }
                                # widen if roles not used or filter too small
                                widened = False
                                reason = None
                                if (len(visual_page_filter) < 3) and total_pages:
                                    summary = section_chunking_meta.get("summary") or {}
                                    if not summary.get("azure_di_role_used"):
                                        # Use middle pages (2..N-1) as a safe default
                                        start = 2 if total_pages >= 3 else 1
                                        end = total_pages - 1 if total_pages >= 3 else total_pages
                                        widened_pages = set(range(start, end + 1))
                                        # reapply filter against widened set
                                        if widened_pages and widened_pages != visual_page_filter:
                                            visual_page_filter = widened_pages
                                            widened = True
                                            reason = "di_roles_unavailable_or_narrow"
                                            # re-run filtering with widened set
                                            filtered_objects = []
                                            removed_counts = {"IMAGE": 0, "TABLE": 0, "FIGURE": 0}
                                            for obj in extracted_objects:
                                                otype = getattr(obj, "object_type", None)
                                                if otype in removed_counts:
                                                    pno = getattr(obj, "page_no", None)
                                                    if pno is not None and pno not in visual_page_filter:
                                                        removed_counts[otype] += 1
                                                        continue
                                                filtered_objects.append(obj)
                                            extracted_objects = filtered_objects
                                            counts_after = {
                                                "IMAGE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "IMAGE"),
                                                "TABLE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "TABLE"),
                                                "FIGURE": sum(1 for obj in extracted_objects if getattr(obj, "object_type", None) == "FIGURE"),
                                            }
                                section_chunking_meta["figure_table_filter"] = {
                                    "enabled": True,
                                    "allowed_pages": sorted(visual_page_filter),
                                    "before": counts_before,
                                    "after": counts_after,
                                    "widened": widened,
                                    "widen_reason": reason,
                                }
                            else:
                                section_chunking_meta["figure_table_filter"] = {"enabled": False, "reason": "no_core_pages"}
                        else:
                            section_chunking_meta["figure_table_filter"] = {"enabled": False, "reason": "no_sections"}
                    else:
                        section_chunking_meta["figure_table_filter"] = {"enabled": False, "reason": "empty_combined_text"}
            
            for obj in extracted_objects:
                session.add(obj)
            await session.flush()
            setattr(extraction_session, "status", "success")
            setattr(extraction_session, "completed_at", datetime.now())
            setattr(extraction_session, "page_count_detected", len(metadata.get('pages', metadata.get('slides', metadata.get('sheets', [])))))
            result["objects_count"] = len(extracted_objects)
            _stage("extraction", True, objects=len(extracted_objects))

            # -----------------------------
            # 1.5. Azure Blob Storage - 중간 결과 저장
            # -----------------------------
            performed_blob_intermediate = False
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                    _start_stage("blob_intermediate_save")
                    performed_blob_intermediate = True
                    azure_factory = get_azure_blob_service if callable(get_azure_blob_service) else None
                    if not azure_factory:
                        raise RuntimeError("Azure Blob service factory not available")
                    azure = azure_factory()
                    
                    # 전체 추출 텍스트 저장 (intermediate 컨테이너)
                    full_text_key = f"multimodal/{file_bss_info_sno}/extraction_full_text.txt"
                    full_text_content = extraction_result.get("text", "") or ""
                    # 필요시 fallback 조립
                    if not full_text_content.strip():
                        full_text_content = _assemble_full_text(extracted_objects)
                    if full_text_content.strip():
                        azure.upload_bytes(
                            full_text_content.encode('utf-8'), 
                            full_text_key, 
                            purpose='intermediate'
                        )
                        logger.info(f"[MULTIMODAL-BLOB] 전체 텍스트 저장: {full_text_key} (len={len(full_text_content)})")
                    else:
                        logger.info("[MULTIMODAL-BLOB] 전체 텍스트 비어있어 저장 생략")
                    
                    # 추출 메타데이터 저장 (binary_data 제거)
                    metadata_key = f"multimodal/{file_bss_info_sno}/extraction_metadata.json"
                    
                    # metadata에서 binary_data 제거 (JSON 직렬화 오류 방지)  
                    clean_metadata = _clean_metadata_for_json(metadata)
                    
                    metadata_content = {
                        "extraction_session_id": extraction_session.extraction_session_id,
                        "provider": provider,
                        "pipeline_type": pipeline_type,
                        "extracted_objects_count": len(extracted_objects),
                        "pages_detected": extraction_session.page_count_detected,
                        "extraction_metadata": clean_metadata,
                        "has_full_text": bool(full_text_content.strip()),
                        "timestamp": datetime.now().isoformat()
                    }
                    azure.upload_bytes(
                        json.dumps(metadata_content, ensure_ascii=False).encode('utf-8'),
                        metadata_key,
                        purpose='intermediate'
                    )
                    logger.info(f"[MULTIMODAL-BLOB] 메타데이터 저장: {metadata_key}")
                    
                    # 객체별 세부 정보 저장 + 매니페스트 구성
                    objects_manifest: List[Dict[str, Any]] = []
                    saved_counts = {"TEXT_BLOCK": 0, "TABLE": 0, "IMAGE": 0, "FIGURE": 0}
                    # PDF 이미지 추출을 위한 사전 준비
                    pdf_pages = None
                    pdf_doc = None
                    is_pdf = False
                    # IMAGE 또는 FIGURE 객체가 있으면 pdfplumber 초기화
                    has_images_or_figures = any(getattr(o, 'object_type', None) in ['IMAGE', 'FIGURE'] for o in extracted_objects)
                    if file_path.lower().endswith('.pdf') and has_images_or_figures:
                        try:
                            import pdfplumber  # type: ignore
                            # 실제 파일 경로 사용 (Azure Blob 경로가 아닌 로컬 임시 파일)
                            pdf_doc = pdfplumber.open(actual_file_path)
                            pdf_pages = pdf_doc.pages
                            is_pdf = True
                            logger.info(f"[MULTIMODAL-BLOB] PDF 초기화 완료 - FIGURE/IMAGE 바이너리 추출 준비")
                        except Exception as e:
                            logger.warning(f"[MULTIMODAL-BLOB] PDF 이미지 초기화 실패 (이미지 바이너리 추출 생략): {e}")
                            pdf_pages = None
                            pdf_doc = None
                    object_save_errors: List[str] = []
                    for idx, obj in enumerate(extracted_objects):
                        try:
                            blob_key = None
                            if getattr(obj, 'object_type', None) == 'TEXT_BLOCK' and (obj.content_text or '').strip():
                                blob_key = f"multimodal/{file_bss_info_sno}/objects/text_block_{idx}_{obj.page_no or 0}.txt"
                                azure.upload_bytes(
                                    (obj.content_text or '').encode('utf-8'),
                                    blob_key,
                                    purpose='intermediate'
                                )
                            elif getattr(obj, 'object_type', None) in ['TABLE', 'IMAGE', 'FIGURE']:
                                blob_key = f"multimodal/{file_bss_info_sno}/objects/{obj.object_type.lower()}_{idx}_{obj.page_no or 0}.json"

                                if getattr(obj, 'object_type', None) in ['IMAGE', 'FIGURE']:
                                    obj_id_for_tracking = getattr(obj, 'object_id', idx)
                                    image_object_ids_seen.add(obj_id_for_tracking)

                                # structure_json 전체 재귀 정리 (binary_data/bytes 제거)
                                clean_structure_json = _clean_metadata_for_json(getattr(obj, 'structure_json', None))

                                obj_content = {
                                    "object_type": obj.object_type,
                                    "page_no": obj.page_no,
                                    "sequence_in_page": obj.sequence_in_page,
                                    # TABLE 은 placeholder 텍스트일 수 있음 → 구조 개선 TODO
                                    "content_text": obj.content_text,
                                    "structure_json": clean_structure_json,
                                    "bbox": obj.bbox
                                }
                                try:
                                    azure.upload_bytes(
                                        json.dumps(obj_content, ensure_ascii=False).encode('utf-8'),
                                        blob_key,
                                        purpose='intermediate'
                                    )
                                except TypeError as te:
                                    # 디버깅용 로그: 어떤 필드 때문에 실패했는지 확인
                                    logger.warning(f"[MULTIMODAL-BLOB] 객체 JSON 직렬화 실패 idx={idx}: {te}")
                                    # 강제 fallback: structure_json 제거 후 저장
                                    fallback_content = dict(obj_content)
                                    fallback_content.pop('structure_json', None)
                                    azure.upload_bytes(
                                        json.dumps(fallback_content, ensure_ascii=False).encode('utf-8'),
                                        blob_key,
                                        purpose='intermediate'
                                    )
                                # 이미지 또는 FIGURE인 경우 바이너리 저장 및 특징 추출
                                if getattr(obj, 'object_type', None) in ['IMAGE', 'FIGURE']:
                                    obj_type = getattr(obj, 'object_type', None)
                                    logger.info(f"[MULTIMODAL-BLOB] {obj_type} 객체 발견 idx={idx}, page={getattr(obj, 'page_no', None)}, obj_id={getattr(obj, 'object_id', None)}")
                                    img_bytes = None
                                    page_no_val = getattr(obj, 'page_no', None) or 1
                                    
                                    # 🎯 STEP 1: Azure DI가 이미 바이너리 데이터를 제공했는지 확인
                                    azure_binary = getattr(obj, 'binary_data', None)
                                    if azure_binary and len(azure_binary) > 0:
                                        img_bytes = azure_binary
                                        logger.info(f"[MULTIMODAL-BLOB] ✅ Azure DI 바이너리 사용 - idx={idx}, size={len(img_bytes)} bytes")
                                    
                                    # STEP 2: Azure DI 바이너리가 없으면 PDF에서 추출
                                    elif is_pdf and pdf_pages is not None:
                                        logger.info(f"[MULTIMODAL-BLOB] PDF 이미지 처리 시작 idx={idx}, page={page_no_val}, is_pdf={is_pdf}, pdf_pages={len(pdf_pages) if pdf_pages else 0}")
                                        
                                        # 🎯 Azure DI polygon bbox 추출 (정확한 좌표)
                                        structure_json = getattr(obj, 'structure_json', None)
                                        bbox_val = None
                                        
                                        if structure_json and isinstance(structure_json, dict):
                                            polygon = structure_json.get('bbox')
                                            if polygon and isinstance(polygon, list) and len(polygon) == 4:
                                                # polygon: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                                                # bounding box 계산: (min_x, min_y, max_x, max_y)
                                                x_coords = [pt[0] for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                                                y_coords = [pt[1] for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                                                
                                                if len(x_coords) == 4 and len(y_coords) == 4:
                                                    x0 = min(x_coords)
                                                    y0 = min(y_coords)
                                                    x1 = max(x_coords)
                                                    y1 = max(y_coords)
                                                    bbox_val = [x0, y0, x1, y1]
                                                    logger.info(f"[MULTIMODAL-BLOB] ✅ Azure DI polygon bbox 추출 - idx={idx}, polygon={polygon[:2]}..., bbox={bbox_val}, size={(x1-x0):.2f}x{(y1-y0):.2f}inch")
                                        
                                        # Fallback: obj.bbox 사용 (정수 반올림 버전)
                                        if not bbox_val:
                                            bbox_val = getattr(obj, 'bbox', None)
                                            logger.info(f"[MULTIMODAL-BLOB] bbox fallback (obj.bbox) - idx={idx}, bbox_val={bbox_val}, type={type(bbox_val)}, page_no_val={page_no_val}, type={type(page_no_val)}")
                                        
                                        # 🎯 bbox가 [0,0,0,0]인 경우 같은 페이지의 FIGURE bbox 찾아서 사용
                                        if bbox_val == [0, 0, 0, 0] or (isinstance(bbox_val, (list, tuple)) and all(v == 0 for v in bbox_val)):
                                            logger.warning(f"[MULTIMODAL-BLOB] ⚠️ IMAGE bbox 무효 (idx={idx}) → 같은 페이지의 FIGURE bbox 검색 중...")
                                            sequence_in_page = getattr(obj, 'sequence_in_page', None)
                                            
                                            # 같은 페이지에서 sequence가 비슷한 FIGURE 찾기
                                            for candidate_obj in extracted_objects:
                                                if (getattr(candidate_obj, 'object_type', None) == 'FIGURE' and
                                                    getattr(candidate_obj, 'page_no', None) == page_no_val):
                                                    
                                                    candidate_bbox = getattr(candidate_obj, 'bbox', None)
                                                    candidate_seq = getattr(candidate_obj, 'sequence_in_page', None)
                                                    
                                                    # bbox가 유효하고 sequence가 비슷하면 사용
                                                    if (candidate_bbox and 
                                                        isinstance(candidate_bbox, (list, tuple)) and 
                                                        len(candidate_bbox) == 4 and
                                                        not all(v == 0 for v in candidate_bbox)):
                                                        
                                                        # sequence가 같거나 ±1 차이면 매칭
                                                        if sequence_in_page is None or candidate_seq is None or abs(candidate_seq - sequence_in_page) <= 1:
                                                            bbox_val = candidate_bbox
                                                            logger.info(f"[MULTIMODAL-BLOB] ✅ FIGURE bbox 적용 성공 - FIGURE seq={candidate_seq}, IMAGE seq={sequence_in_page}, bbox={bbox_val}")
                                                            break
                                            
                                            if bbox_val == [0, 0, 0, 0] or (isinstance(bbox_val, (list, tuple)) and all(v == 0 for v in bbox_val)):
                                                logger.warning(f"[MULTIMODAL-BLOB] ❌ 매칭되는 FIGURE bbox를 찾지 못함 → pdfplumber fallback 시도")
                                        
                                        # bbox 유효성 검증
                                        is_valid_bbox = (
                                            isinstance(page_no_val, int) and 
                                            isinstance(bbox_val, (list, tuple)) and 
                                            len(bbox_val) == 4 and
                                            not all(v == 0 for v in bbox_val)  # [0,0,0,0] 제외
                                        )
                                        
                                        if is_valid_bbox:
                                            logger.info(f"[MULTIMODAL-BLOB] bbox 검증 통과 - idx={idx}, 크롭 시도 시작")
                                            try:
                                                page_index = page_no_val - 1
                                                if 0 <= page_index < len(pdf_pages):
                                                    page = pdf_pages[page_index]
                                                    x0, y0, x1, y1 = [float(v) for v in bbox_val]
                                                    
                                                    # 🎯 Azure DI bbox는 inch 단위 → 150 DPI로 픽셀 변환
                                                    # 최소 크기: 0.5 inch (75 픽셀 @ 150 DPI)
                                                    width_inch = x1 - x0
                                                    height_inch = y1 - y0
                                                    width_px = width_inch * 150
                                                    height_px = height_inch * 150
                                                    
                                                    logger.info(f"[MULTIMODAL-BLOB] bbox 크기 - idx={idx}, inch=({width_inch:.2f}x{height_inch:.2f}), pixels=({width_px:.0f}x{height_px:.0f})")
                                                    
                                                    page_image = page.to_image(resolution=150)
                                                    
                                                    # 최소 크기 검증: 0.3 inch (45 픽셀) 이상
                                                    if width_inch > 0.3 and height_inch > 0.3:
                                                        import io
                                                        from PIL import Image  # type: ignore
                                                        
                                                        # 🎯 좌표 변환: Azure DI bbox (inch) → pdfplumber image (픽셀)
                                                        # PDF 기본 해상도: 72 DPI
                                                        # to_image(resolution=150) 스케일 팩터: 150/72 = 2.083333
                                                        render_dpi = 150
                                                        pdf_dpi = 72
                                                        scale_factor = render_dpi / pdf_dpi
                                                        
                                                        # inch → points (72 DPI) → scaled pixels (150 DPI)
                                                        x0_px = x0 * pdf_dpi * scale_factor  # inch * 72 * 2.083 = inch * 150
                                                        y0_px = y0 * pdf_dpi * scale_factor
                                                        x1_px = x1 * pdf_dpi * scale_factor
                                                        y1_px = y1 * pdf_dpi * scale_factor
                                                        
                                                        logger.info(f"[MULTIMODAL-BLOB] 좌표 변환 - inch=({x0:.2f},{y0:.2f},{x1:.2f},{y1:.2f}) → pixels@150dpi=({x0_px:.1f},{y0_px:.1f},{x1_px:.1f},{y1_px:.1f}), scale={scale_factor:.3f}")
                                                        
                                                        cropped = page_image.original.crop((x0_px, y0_px, x1_px, y1_px))
                                                        buf = io.BytesIO()
                                                        cropped.save(buf, format='PNG')
                                                        buf.seek(0)
                                                        img_bytes = buf.getvalue()
                                                        logger.info(f"[MULTIMODAL-BLOB] ✅ PDF 이미지 추출 성공 (Azure DI polygon bbox) idx={idx}, page={page_no_val}, size={len(img_bytes)} bytes, dimensions={cropped.size}")
                                                    else:
                                                        logger.warning(f"[MULTIMODAL-BLOB] 이미지 크기 부족 - idx={idx}, inch=({width_inch:.2f}x{height_inch:.2f}), pixels=({width_px:.0f}x{height_px:.0f})")
                                            except Exception as img_err:
                                                logger.warning(f"[MULTIMODAL-BLOB] PDF 이미지 크롭 실패 idx={idx}, page={page_no_val}, bbox={bbox_val}, error={img_err}")
                                        elif bbox_val == [0, 0, 0, 0] or (isinstance(bbox_val, (list, tuple)) and all(v == 0 for v in bbox_val)):
                                            logger.warning(f"[MULTIMODAL-BLOB] ⚠️ 무효한 bbox 감지 - idx={idx}, bbox={bbox_val} → pdfplumber 직접 추출 시도")
                                            # Fallback: pdfplumber의 이미지 객체 직접 추출
                                            try:
                                                page_index = page_no_val - 1
                                                if 0 <= page_index < len(pdf_pages):
                                                    page = pdf_pages[page_index]
                                                    images = page.images
                                                    logger.info(f"[MULTIMODAL-BLOB] pdfplumber 감지 이미지 수: {len(images)} on page {page_no_val}")
                                                    
                                                    # 페이지 내 이미지 시퀀스 추정 (Azure DI: 1-based → pdfplumber: 0-based 변환)
                                                    sequence_in_page = getattr(obj, 'sequence_in_page', 1)  # Azure DI default: 1
                                                    image_index = sequence_in_page - 1  # 0-based 인덱스로 변환
                                                    logger.info(f"[MULTIMODAL-BLOB] 이미지 인덱싱 변환 - Azure DI sequence={sequence_in_page} → pdfplumber index={image_index}")
                                                    
                                                    # 🎯 모든 이미지를 크기순으로 정렬하여 가장 큰 것 선택
                                                    if images:
                                                        # 이미지 크기 계산 및 정렬
                                                        sized_images = []
                                                        for i, img_obj in enumerate(images):
                                                            x0, top, x1, bottom = img_obj['x0'], img_obj['top'], img_obj['x1'], img_obj['bottom']
                                                            width = x1 - x0
                                                            height = bottom - top
                                                            area = width * height
                                                            
                                                            # 최소 크기 필터 (50x50 이상)
                                                            if width >= 50 and height >= 50:
                                                                sized_images.append({
                                                                    'index': i,
                                                                    'obj': img_obj,
                                                                    'width': width,
                                                                    'height': height,
                                                                    'area': area,
                                                                    'x0': x0,
                                                                    'top': top,
                                                                    'x1': x1,
                                                                    'bottom': bottom
                                                                })
                                                        
                                                        # 면적 기준 내림차순 정렬
                                                        sized_images.sort(key=lambda x: x['area'], reverse=True)
                                                        
                                                        logger.info(f"[MULTIMODAL-BLOB] 유효 이미지 {len(sized_images)}개 (최소 50x50 이상)")
                                                        
                                                        # sequence에 해당하는 이미지 또는 가장 큰 이미지 선택
                                                        target_img = None
                                                        if 0 <= image_index < len(sized_images):
                                                            target_img = sized_images[image_index]
                                                            logger.info(f"[MULTIMODAL-BLOB] sequence={image_index} 이미지 선택")
                                                        elif sized_images:
                                                            target_img = sized_images[0]
                                                            logger.info(f"[MULTIMODAL-BLOB] sequence 범위 초과, 가장 큰 이미지 선택 (area={target_img['area']:.0f})")
                                                        
                                                        if target_img:
                                                            import io
                                                            from PIL import Image  # type: ignore
                                                            
                                                            page_image = page.to_image(resolution=150)
                                                            cropped = page_image.original.crop((
                                                                target_img['x0'],
                                                                target_img['top'],
                                                                target_img['x1'],
                                                                target_img['bottom']
                                                            ))
                                                            
                                                            # 🔍 이미지 품질 검증 (너무 단순한 이미지 제외)
                                                            import numpy as np
                                                            img_array = np.array(cropped)
                                                            
                                                            # 색상 분산 계산 (단색 이미지 제외)
                                                            if len(img_array.shape) >= 3:
                                                                color_variance = np.var(img_array)
                                                                unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
                                                                logger.info(f"[MULTIMODAL-BLOB] 이미지 품질 - variance={color_variance:.1f}, unique_colors={unique_colors}")
                                                                
                                                                # 너무 단순한 이미지 제외 (순백색, 순흑색 등)
                                                                if color_variance < 10 and unique_colors < 5:
                                                                    logger.warning(f"[MULTIMODAL-BLOB] ❌ 단순 이미지 제외 (variance={color_variance:.1f}, colors={unique_colors})")
                                                                    target_img = None
                                                            
                                                            if target_img:
                                                                buf = io.BytesIO()
                                                                cropped.save(buf, format='PNG')
                                                                buf.seek(0)
                                                                img_bytes = buf.getvalue()
                                                                logger.info(f"[MULTIMODAL-BLOB] ✅ pdfplumber 직접 추출 성공 idx={idx}, page={page_no_val}, size={len(img_bytes)} bytes, "
                                                                          f"dimensions={target_img['width']:.0f}x{target_img['height']:.0f}, "
                                                                          f"bbox=({target_img['x0']:.1f},{target_img['top']:.1f},{target_img['x1']:.1f},{target_img['bottom']:.1f})")
                                                        else:
                                                            logger.warning(f"[MULTIMODAL-BLOB] ❌ 유효한 이미지를 찾지 못함")
                                                    else:
                                                        logger.warning(f"[MULTIMODAL-BLOB] pdfplumber 이미지 인덱스 범위 초과 - Azure DI sequence={sequence_in_page}, pdfplumber index={image_index}, available={len(images)}")
                                            except Exception as fallback_err:
                                                logger.warning(f"[MULTIMODAL-BLOB] pdfplumber 직접 추출 실패 idx={idx}, page={page_no_val}, error={fallback_err}")
                                                import traceback
                                                logger.debug(traceback.format_exc())
                                        else:
                                            logger.warning(f"[MULTIMODAL-BLOB] bbox 검증 실패 - idx={idx}, page_no_val={page_no_val} (type={type(page_no_val)}), bbox_val={bbox_val} (type={type(bbox_val)}, len={len(bbox_val) if bbox_val and hasattr(bbox_val, '__len__') else 'N/A'})")
                                    
                                    # DOCX 이미지 처리 (Azure DI 바이너리가 없는 경우만)
                                    elif not img_bytes and file_path.lower().endswith('.docx'):
                                        try:
                                            # 원본 메타데이터에서 이미지 바이너리 찾기
                                            image_index = getattr(obj, 'sequence_in_page', None)
                                            page_no_val = getattr(obj, 'page_no', 1)
                                            
                                            # pages 메타데이터에서 해당 이미지 찾기
                                            if "pages" in metadata:
                                                for page in metadata["pages"]:
                                                    if page.get("page_no") == page_no_val:
                                                        for img_meta in page.get("images_metadata", []):
                                                            if img_meta.get("image_index") == image_index and 'binary_data' in img_meta:
                                                                img_bytes = img_meta['binary_data']
                                                                logger.debug(f"[MULTIMODAL-BLOB] DOCX 이미지 바이너리 발견 idx={idx}, size={len(img_bytes)}")
                                                                break
                                        except Exception as docx_err:
                                            logger.debug(f"[MULTIMODAL-BLOB] DOCX 이미지 처리 실패 idx={idx}: {docx_err}")
                                    # PPTX 이미지 처리 (Azure DI 바이너리가 없는 경우만)
                                    elif not img_bytes and file_path.lower().endswith('.pptx'):
                                        try:
                                            image_index = getattr(obj, 'sequence_in_page', None)
                                            slide_no_val = getattr(obj, 'page_no', 1)
                                            if "slides" in metadata:
                                                for slide in metadata["slides"]:
                                                    if slide.get("slide_no") == slide_no_val:
                                                        for img_meta in slide.get("images_metadata", []):
                                                            if img_meta.get("image_index") == image_index and 'binary_data' in img_meta:
                                                                img_bytes = img_meta['binary_data']
                                                                logger.debug(f"[MULTIMODAL-BLOB] PPTX 이미지 바이너리 발견 idx={idx}, size={len(img_bytes)}")
                                                                break
                                        except Exception as pptx_err:
                                            logger.debug(f"[MULTIMODAL-BLOB] PPTX 이미지 처리 실패 idx={idx}: {pptx_err}")
                                    
                                    # STEP 3: 이미지 바이너리 검증 및 저장
                                    if img_bytes:
                                        logger.info(f"[MULTIMODAL-BLOB] ✅ 이미지 바이너리 최종 확보 idx={idx}, size={len(img_bytes)} bytes, page={page_no_val}")
                                        try:
                                            # object_id를 사용하여 일관된 blob 키 생성
                                            obj_id = getattr(obj, 'object_id', idx)
                                            img_blob_key = f"multimodal/{file_bss_info_sno}/objects/image_{obj_id}_{page_no_val}.png"
                                            azure.upload_bytes(img_bytes, img_blob_key, purpose='intermediate')
                                            image_ids_with_binary.add(obj_id)
                                            
                                            # B/C. Extract image features (pHash, dimensions)
                                            enhanced_features = {}
                                            if self.image_embedding_service:
                                                try:
                                                    features = await self.image_embedding_service.extract_features(img_bytes)
                                                    enhanced_features = {
                                                        "phash": features.get("phash"),
                                                        "width": features.get("width"),
                                                        "height": features.get("height"),
                                                        "aspect_ratio": features.get("aspect_ratio")
                                                    }
                                                    
                                                    # D. Update database object with extracted features
                                                    setattr(obj, 'phash', features.get("phash"))
                                                    setattr(obj, 'image_width', features.get("width"))
                                                    setattr(obj, 'image_height', features.get("height"))
                                                    
                                                    # C. Save enhanced feature JSON
                                                    feature_key = f"multimodal/{file_bss_info_sno}/objects/image_{obj_id}_{page_no_val}_features.json"
                                                    azure.upload_bytes(
                                                        json.dumps(features, ensure_ascii=False, indent=2).encode('utf-8'),
                                                        feature_key,
                                                        purpose='intermediate'
                                                    )
                                                except Exception as feat_err:
                                                    logger.debug(f"[MULTIMODAL-BLOB] 이미지 특징 추출 실패 obj_id={obj_id}: {feat_err}")
                                            
                                            objects_manifest.append({
                                                **_object_to_manifest_entry(idx, obj, blob_key),
                                                "binary_image_key": img_blob_key,
                                                "has_binary": True,
                                                **enhanced_features
                                            })
                                            saved_counts['IMAGE'] += 1
                                            continue
                                            
                                        except Exception as save_err:
                                            logger.warning(f"[MULTIMODAL-BLOB] 이미지 저장 실패 obj_id={obj_id}, page={page_no_val}: {save_err}")
                                    else:
                                        # 이미지 바이너리를 확보하지 못한 경우
                                        obj_id = getattr(obj, 'object_id', None)
                                        has_azure_binary = getattr(obj, 'binary_data', None) is not None
                                        bbox_val = getattr(obj, 'bbox', None)
                                        logger.warning(
                                            f"[MULTIMODAL-BLOB] ❌ 이미지 바이너리 없음 - "
                                            f"idx={idx}, obj_id={obj_id}, page={page_no_val}, "
                                            f"Azure_DI_binary={'있음' if has_azure_binary else '없음'}, "
                                            f"bbox={bbox_val}, "
                                            f"file_type={file_path.split('.')[-1] if file_path else 'unknown'}"
                                        )
                            if blob_key:
                                objects_manifest.append({**_object_to_manifest_entry(idx, obj, blob_key), "has_binary": False})
                                otype = getattr(obj, 'object_type', None)
                                if isinstance(otype, str) and otype in saved_counts:
                                    saved_counts[otype] += 1
                        except Exception as oe:
                            msg = f"idx={idx} type={getattr(obj,'object_type',None)} err={oe}"
                            object_save_errors.append(msg)
                            logger.warning(f"[MULTIMODAL-BLOB] 객체 저장 오류: {msg}")
                    # PDF 문서 핸들 닫기
                    try:
                        if pdf_doc:
                            pdf_doc.close()
                    except Exception:
                        pass
                    
                    # 객체 매니페스트 저장
                    manifest_key = f"multimodal/{file_bss_info_sno}/objects_manifest.json"
                    azure.upload_bytes(
                        json.dumps(objects_manifest, ensure_ascii=False, indent=2).encode('utf-8'),
                        manifest_key,
                        purpose='intermediate'
                    )
                    logger.info(f"[MULTIMODAL-BLOB] objects_manifest 저장: {manifest_key} ({len(objects_manifest)} entries)")
                    
                    # Ensure database objects are updated with extracted features
                    await session.flush()

                    logger.info(
                        f"[MULTIMODAL-BLOB] 객체 저장 완료 text={saved_counts['TEXT_BLOCK']} table={saved_counts['TABLE']} "
                        f"image={saved_counts['IMAGE']} figure={saved_counts['FIGURE']} errors={len(object_save_errors)}"
                    )
                    _stage(
                        "blob_intermediate_save", True,
                        objects_saved=len(objects_manifest),
                        text_blocks=saved_counts['TEXT_BLOCK'],
                        tables=saved_counts['TABLE'],
                        images=saved_counts['IMAGE'],
                        figures=saved_counts['FIGURE'],
                        object_save_errors=object_save_errors[:5]
                    )
            except Exception as blob_err:
                logger.warning(f"[MULTIMODAL-BLOB] 중간 결과 저장 실패 (무시하고 계속): {blob_err}")
                if performed_blob_intermediate:
                    _stage("blob_intermediate_save", False, error=str(blob_err))
            finally:
                if not performed_blob_intermediate:
                    _stage("blob_intermediate_save", False, skipped=True)

            # -----------------------------
            # 2. Chunking (advanced)
            # -----------------------------
            _start_stage("chunking")
            # SQLAlchemy 컬럼 속성 대신 안전하게 getattr 사용
            text_objs = [o for o in extracted_objects if getattr(o, 'object_type', None) == "TEXT_BLOCK"]
            raw_image_objs = [o for o in extracted_objects if getattr(o, 'object_type', None) in ["IMAGE", "FIGURE"]]
            if image_object_ids_seen:
                image_objs = [
                    o for o in raw_image_objs
                    if getattr(o, 'object_id', None) in image_ids_with_binary
                ]
                skipped_images = len(raw_image_objs) - len(image_objs)
                if skipped_images > 0:
                    logger.info(
                        "[MULTIMODAL] 바이너리 누락으로 이미지 청크 %s개 제외 (object_ids=%s)",
                        skipped_images,
                        [getattr(o, 'object_id', None) for o in raw_image_objs if getattr(o, 'object_id', None) not in image_ids_with_binary],
                    )
            else:
                image_objs = raw_image_objs
            table_objs = [o for o in extracted_objects if getattr(o, 'object_type', None) == "TABLE"]
            text_objs = [o for o in text_objs if (getattr(o, 'content_text', '') or '').strip()]

            chunk_params: Dict[str, Any] = {
                "min_tokens": 80,
                "target_tokens": 280,
                "max_tokens": 420,
                "overlap_tokens": 40,
            }

            sections_info: List[Dict[str, Any]] = list(precomputed_sections_info) if precomputed_sections_info else []
            section_summary: Optional[Dict[str, Any]] = precomputed_section_summary
            # 섹션 순서 보존: (type, index, title) 튜플과 객체 리스트 쌍
            section_groups: List[Tuple[Optional[Tuple[str, int, str]], List[DocExtractedObject]]] = []
            object_spans: List[Tuple[DocExtractedObject, int, int]] = list(section_object_spans)

            if apply_section_chunking and text_objs:
                try:
                    separator = "\n\n"
                    if section_combined_text and section_object_spans:
                        combined_text = section_combined_text
                        object_spans_local = list(section_object_spans)
                    else:
                        combined_parts: List[str] = []
                        object_spans_local = []
                        current_pos = 0
                        for obj in text_objs:
                            content = (getattr(obj, 'content_text', '') or '').strip()
                            if not content:
                                continue
                            if combined_parts:
                                combined_parts.append(separator)
                                current_pos += len(separator)
                            start_pos = current_pos
                            combined_parts.append(content)
                            current_pos += len(content)
                            object_spans_local.append((obj, start_pos, current_pos))

                        combined_text = "".join(combined_parts)
                        section_combined_text = combined_text
                        section_object_spans = list(object_spans_local)

                    if combined_text.strip() and not sections_info:
                        sections_info = self.section_detector.detect_sections(
                            combined_text,
                            pages=metadata.get("pages") or None,
                        )
                        section_summary = self.section_detector.get_section_summary(sections_info)

                    if sections_info:
                        if not section_chunking_meta.get("detected_sections"):
                            section_chunking_meta["detected_sections"] = [s.get("type") for s in sections_info]
                        if section_summary and not section_chunking_meta.get("summary"):
                            section_chunking_meta["summary"] = section_summary
                        object_spans = list(object_spans_local)

                        # 섹션 순서 보존: (type, index, original_title) 튜플로 매핑
                        object_section_map: Dict[DocExtractedObject, Optional[Tuple[str, int, str]]] = {}
                        for section in sections_info:
                            s_type = section.get("type")
                            s_index = section.get("index")  # 순서 인덱스
                            s_title = section.get("original_title")  # 원본 제목
                            s_start = section.get("start_pos", 0)
                            s_end = section.get("end_pos", 0)
                            for obj, span_start, span_end in object_spans:
                                if span_end <= s_start or span_start >= s_end:
                                    continue
                                # (type, index, title) 튜플로 저장하여 순서 보존
                                object_section_map[obj] = (s_type, s_index, s_title)

                        current_group: List[DocExtractedObject] = []
                        current_label: Optional[Tuple[str, int, str]] = None
                        for obj in text_objs:
                            content = (getattr(obj, 'content_text', '') or '').strip()
                            if not content:
                                continue
                            label = object_section_map.get(obj)
                            if current_label is None:
                                current_label = label
                                current_group.append(obj)
                                continue
                            if label != current_label:
                                if current_group:
                                    section_groups.append((current_label, current_group))
                                current_group = [obj]
                                current_label = label
                            else:
                                current_group.append(obj)
                        if current_group:
                            section_groups.append((current_label, current_group))

                        chunk_params["section_chunking"] = {
                            "detected_sections": section_chunking_meta["detected_sections"],
                            "total_detected": len(section_chunking_meta["detected_sections"]),
                        }

                        if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                            try:
                                azure_factory2 = get_azure_blob_service if callable(get_azure_blob_service) else None
                                if not azure_factory2:
                                    raise RuntimeError("Azure Blob service factory not available")
                                azure_sections_service = azure_factory2()
                                sections_blob_path = f"multimodal/{file_bss_info_sno}/sections.json"
                                sections_payload = {
                                    "sections": sections_info,
                                    "summary": section_summary,
                                    "detected_at": datetime.now().isoformat(),
                                }
                                azure_sections_service.upload_bytes(
                                    json.dumps(sections_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                                    sections_blob_path,
                                    purpose='intermediate'
                                )
                                section_chunking_meta["stored_to_blob"] = True
                                logger.info(f"[SECTION-DETECT] 섹션 정보 저장: {sections_blob_path}")
                            except Exception as section_blob_err:
                                logger.warning(f"[SECTION-DETECT] 섹션 정보 저장 실패 (기본 청킹 계속): {section_blob_err}")
                    else:
                        logger.info("[SECTION-DETECT] 섹션 감지 결과가 없어 기본 청킹 적용")
                except Exception as sec_err:
                    logger.warning(f"[SECTION-DETECT] 섹션 감지 중 예외 발생 (기본 청킹으로 진행): {sec_err}")

            section_chunk_counts: Dict[str, int] = {}
            adv_chunks: List[Dict[str, Any]] = []
            if section_groups:
                section_chunking_meta["enabled"] = True
                # 섹션 순서 보존: label은 (type, index, title) 튜플
                for label, group in section_groups:
                    iterable = (
                        (
                            (getattr(o, 'content_text', '') or ''),
                            getattr(o, 'page_no', None),
                            getattr(o, 'object_id', None) or 0
                        ) for o in group
                    )
                    section_chunks = advanced_chunk_text(iterable)
                    
                    # 순서 보존을 위한 메타데이터 추가
                    if label:
                        section_type, section_index, section_title = label
                        for chunk_dict in section_chunks:
                            chunk_dict['section'] = section_type  # 섹션 타입 (other, methods 등)
                            chunk_dict['section_title'] = section_title  # 원본 제목 (Related Work 등)
                            chunk_dict['section_index'] = section_index  # 순서 인덱스
                    else:
                        for chunk_dict in section_chunks:
                            chunk_dict['section'] = None
                            chunk_dict['section_title'] = None
                            chunk_dict['section_index'] = None
                    
                    adv_chunks.extend(section_chunks)
                    key = label[0] if label else "unassigned"  # section_type 사용
                    section_chunk_counts[key] = section_chunk_counts.get(key, 0) + len(section_chunks)
            else:
                adv_chunks = advanced_chunk_text(
                    (
                        (
                            (getattr(o, 'content_text', '') or ''),
                            getattr(o, 'page_no', None),
                            getattr(o, 'object_id', None) or 0
                        ) for o in text_objs
                    )
                )
                section_chunking_meta["enabled"] = False

            if section_chunk_counts:
                section_chunking_meta["chunk_counts"] = section_chunk_counts
            
            chunk_session = DocChunkSession(
                file_bss_info_sno=file_bss_info_sno,
                extraction_session_id=extraction_session.extraction_session_id,
                strategy_name="advanced_paragraph_token",
                params_json=chunk_params,
                status="running",
                started_at=datetime.now()
            )
            session.add(chunk_session)
            await session.flush()
            result["chunk_session_id"] = chunk_session.chunk_session_id

            doc_chunks: List[DocChunk] = []
            for idx, cdict in enumerate(adv_chunks):
                # 섹션 순서 정보를 로그로 기록 (디버깅용)
                if cdict.get('section_index') is not None:
                    logger.debug(
                        f"[SECTION-ORDER] 청크 {idx}: section_index={cdict['section_index']}, "
                        f"type={cdict.get('section')}, title={cdict.get('section_title')}"
                    )
                
                # page_range 생성: page_numbers에서 최소/최대 페이지 추출
                page_range_value = None
                page_numbers = cdict.get('page_numbers', [])
                if page_numbers:
                    min_page = min(page_numbers)
                    max_page = max(page_numbers)
                    # PostgreSQL int4range: [lower, upper) 형식
                    # SQLAlchemy type_coerce를 사용하여 문자열을 int4range로 변환
                    page_range_str = f"[{min_page},{max_page + 1})"
                    page_range_value = type_coerce(text(f"'{page_range_str}'"), INT4RANGE)
                
                doc_chunk = DocChunk(
                    chunk_session_id=chunk_session.chunk_session_id,
                    file_bss_info_sno=file_bss_info_sno,
                    chunk_index=idx,
                    source_object_ids=cdict.get('source_object_ids', []),
                    content_text=cdict['content_text'],
                    token_count=cdict['token_count'],
                    modality="text",
                    section_heading=cdict.get('section'),  # 섹션 타입 (other, methods 등)
                    page_range=page_range_value  # 페이지 범위 추가
                )
                session.add(doc_chunk)
                doc_chunks.append(doc_chunk)
            
            # 이미지 청크 생성 (각 이미지를 독립적인 청크로)
            image_chunk_start_idx = len(doc_chunks)
            for img_idx, img_obj in enumerate(image_objs):
                object_id = getattr(img_obj, 'object_id', None)
                page_no = getattr(img_obj, 'page_no', None)
                
                # 이미지 캡션/설명 추출 (있으면)
                img_text = getattr(img_obj, 'content_text', '') or f"Image on page {page_no}"
                
                # page_range 생성: PostgreSQL int4range 타입 '[start, end)' 형식
                page_range_value = None
                if page_no is not None:
                    # SQLAlchemy type_coerce를 사용하여 문자열을 int4range로 변환
                    page_range_str = f"[{page_no},{page_no + 1})"
                    page_range_value = type_coerce(text(f"'{page_range_str}'"), INT4RANGE)
                    logger.info(f"[IMAGE_CHUNK_CREATE] object_id={object_id}, page_no={page_no}, page_range={page_range_str}")
                
                # blob_key 생성: Blob Storage 파일 경로
                blob_key_value = None
                if object_id and page_no is not None:
                    blob_key_value = f"multimodal/{file_bss_info_sno}/objects/image_{object_id}_{page_no}.png"
                    logger.info(f"[IMAGE_CHUNK_CREATE] blob_key={blob_key_value}")
                
                img_chunk = DocChunk(
                    chunk_session_id=chunk_session.chunk_session_id,
                    file_bss_info_sno=file_bss_info_sno,
                    chunk_index=image_chunk_start_idx + img_idx,
                    source_object_ids=[object_id] if object_id else [],
                    content_text=img_text,
                    token_count=0,  # 이미지는 토큰 카운트 0
                    modality="image",
                    page_range=page_range_value,  # 페이지 범위
                    blob_key=blob_key_value  # Blob Storage 파일 경로
                )
                session.add(img_chunk)
                doc_chunks.append(img_chunk)
            
            # 표 청크 생성 (각 표를 독립적인 청크로)
            table_chunk_start_idx = len(doc_chunks)
            for tbl_idx, tbl_obj in enumerate(table_objs):
                object_id = getattr(tbl_obj, 'object_id', None)
                page_no = getattr(tbl_obj, 'page_no', None)
                
                # 표를 텍스트로 변환 (마크다운 또는 CSV 형식)
                table_text = _serialize_table_to_text(tbl_obj)
                
                # 토큰 수 추정 (공백 기준 단순 계산)
                token_count = len(table_text.split()) if table_text else 0
                
                # page_range 생성: PostgreSQL int4range 타입
                page_range_value = None
                if page_no is not None:
                    # SQLAlchemy type_coerce를 사용하여 문자열을 int4range로 변환
                    page_range_str = f"[{page_no},{page_no + 1})"
                    page_range_value = type_coerce(text(f"'{page_range_str}'"), INT4RANGE)
                
                # blob_key 생성: Blob Storage 파일 경로 (테이블은 JSON)
                blob_key_value = None
                if object_id and page_no is not None:
                    blob_key_value = f"multimodal/{file_bss_info_sno}/objects/table_{object_id}_{page_no}.json"
                
                tbl_chunk = DocChunk(
                    chunk_session_id=chunk_session.chunk_session_id,
                    file_bss_info_sno=file_bss_info_sno,
                    chunk_index=table_chunk_start_idx + tbl_idx,
                    source_object_ids=[object_id] if object_id else [],
                    content_text=table_text,
                    token_count=token_count,
                    modality="table",
                    page_range=page_range_value,  # 페이지 범위
                    blob_key=blob_key_value  # Blob Storage 파일 경로
                )
                session.add(tbl_chunk)
                doc_chunks.append(tbl_chunk)
            
            await session.flush()
            setattr(chunk_session, "status", "success")
            setattr(chunk_session, "completed_at", datetime.now())
            setattr(chunk_session, "chunk_count", len(doc_chunks))
            result["chunks_count"] = len(doc_chunks)
            logger.info(f"[MULTIMODAL] 청킹 완료 - 텍스트: {len(adv_chunks)}개, 이미지: {len(image_objs)}개, 표: {len(table_objs)}개, 전체: {len(doc_chunks)}개")
            if section_chunking_meta.get("enabled"):
                logger.info(f"[SECTION-DETECT] 섹션 기반 청킹 적용 - chunk_counts={section_chunking_meta.get('chunk_counts')}")

            chunk_stage_payload = {
                "chunks": len(doc_chunks),
                "text_chunks": len(adv_chunks),
                "image_chunks": len(image_objs),
                "table_chunks": len(table_objs),
            }
            if section_chunking_meta.get("requested"):
                chunk_stage_payload["section_chunking"] = section_chunking_meta
            _stage("chunking", True, **chunk_stage_payload)

            # -----------------------------
            # 2.4. vs_doc_contents_chunks 테이블에 청크 저장 (RAG 기능 지원)
            # -----------------------------
            try:
                logger.info(f"[MULTIMODAL][RAG] vs_doc_contents_chunks 저장 시작 - {len(doc_chunks)}개 청크")
                
                for chunk in doc_chunks:
                    # 청크 텍스트 및 메타데이터
                    chunk_text = getattr(chunk, 'content_text', '') or ''
                    chunk_size = len(chunk_text)
                    chunk_idx = getattr(chunk, 'chunk_index', 0)
                    chunk_modality = getattr(chunk, 'modality', 'text')  # 실제 modality 사용
                    
                    # 페이지 번호 추정 (source_object_ids에서 추출)
                    page_number = None
                    source_object_ids = getattr(chunk, 'source_object_ids', [])
                    if source_object_ids and extracted_objects:
                        # 첫 번째 소스 객체의 페이지 번호 사용
                        for obj in extracted_objects:
                            if getattr(obj, 'object_id', None) == source_object_ids[0]:
                                page_number = getattr(obj, 'page_number', None)
                                break
                    
                    # VsDocContentsChunks 레코드 생성
                    vs_chunk = VsDocContentsChunks(
                        file_bss_info_sno=file_bss_info_sno,
                        chunk_index=chunk_idx,
                        chunk_text=chunk_text,
                        chunk_size=chunk_size,
                        chunk_embedding=None,  # 임베딩은 나중에 업데이트
                        page_number=page_number,
                        section_title=None,  # TODO: 섹션 제목 추출 로직 추가
                        keywords=None,  # TODO: 청크별 키워드 추출 추가
                        named_entities=None,  # TODO: 청크별 개체명 추출 추가
                        knowledge_container_id=container_id,
                        metadata_json=json.dumps({
                            'chunk_id': getattr(chunk, 'chunk_id', None),
                            'token_count': getattr(chunk, 'token_count', 0),
                            'modality': chunk_modality,  # 실제 modality 반영 (text/image/table)
                            'source_object_ids': source_object_ids,
                            'chunk_session_id': chunk_session.chunk_session_id
                        }, ensure_ascii=False),
                        created_by=user_emp_no,
                        del_yn='N'
                    )
                    session.add(vs_chunk)
                
                await session.flush()
                logger.info(f"[MULTIMODAL][RAG] ✅ vs_doc_contents_chunks 저장 완료 - {len(doc_chunks)}개")
                
            except Exception as vs_err:
                logger.error(f"[MULTIMODAL][RAG] ❌ vs_doc_contents_chunks 저장 실패: {vs_err}")
                # 실패해도 계속 진행 (검색 인덱스는 별도)

            # -----------------------------
            # 2.5. Azure Blob Storage - 청킹 결과 저장 (derived)
            # -----------------------------
            performed_blob_derived = False
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                    _start_stage("blob_derived_save")
                    performed_blob_derived = True
                    azure_factory3 = get_azure_blob_service if callable(get_azure_blob_service) else None
                    if not azure_factory3:
                        raise RuntimeError("Azure Blob service factory not available")
                    azure = azure_factory3()
                    
                    # 청킹 메타데이터 저장
                    chunk_metadata_key = f"multimodal/{file_bss_info_sno}/chunking_metadata.json"
                    chunk_metadata = {
                        "chunk_session_id": chunk_session.chunk_session_id,
                        "strategy_name": "advanced_paragraph_token",
                        "chunk_count": len(doc_chunks),
                        "params": {
                            "min_tokens": 80,
                            "target_tokens": 280,
                            "max_tokens": 420,
                            "overlap_tokens": 40
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    azure.upload_bytes(
                        json.dumps(chunk_metadata, ensure_ascii=False).encode('utf-8'),
                        chunk_metadata_key,
                        purpose='derived'
                    )
                    
                    # 개별 청크 저장
                    chunk_manifest = []
                    for idx, chunk in enumerate(doc_chunks):
                        chunk_modality = getattr(chunk, 'modality', 'text')
                        chunk_key = f"multimodal/{file_bss_info_sno}/chunks/chunk_{idx:04d}_{chunk_modality}.json"
                        chunk_content = {
                            "chunk_id": getattr(chunk, 'chunk_id', None),
                            "chunk_index": idx,
                            "content_text": getattr(chunk, 'content_text', ''),
                            "token_count": getattr(chunk, 'token_count', 0),
                            "modality": chunk_modality,
                            "source_object_ids": getattr(chunk, 'source_object_ids', [])
                        }
                        azure.upload_bytes(
                            json.dumps(chunk_content, ensure_ascii=False).encode('utf-8'),
                            chunk_key,
                            purpose='derived'
                        )
                        chunk_manifest.append({
                            "chunk_index": idx,
                            "key": chunk_key,
                            "modality": chunk_modality,
                            "char_count": len(chunk_content["content_text"]),
                            "token_count": chunk_content["token_count"]
                        })
                    
                    # 청크 매니페스트 저장
                    manifest_key = f"multimodal/{file_bss_info_sno}/chunks_manifest.json"
                    azure.upload_bytes(
                        json.dumps(chunk_manifest, ensure_ascii=False).encode('utf-8'),
                        manifest_key,
                        purpose='derived'
                    )
                    
                    logger.info(f"[MULTIMODAL-BLOB] {len(doc_chunks)}개 청크 및 매니페스트 저장 완료")
                    _stage("blob_derived_save", True, chunks_saved=len(doc_chunks))
                    
            except Exception as blob_err:
                logger.warning(f"[MULTIMODAL-BLOB] 청킹 결과 저장 실패 (무시하고 계속): {blob_err}")
                if performed_blob_derived:
                    _stage("blob_derived_save", False, error=str(blob_err))
            finally:
                if not performed_blob_derived:
                    _stage("blob_derived_save", False, skipped=True)

            # -----------------------------
            # 3. Embeddings (텍스트 + CLIP 멀티모달)
            # -----------------------------
            _start_stage("embedding")
            current_embedding_model = settings.get_current_embedding_model()
            max_dim = settings.vector_dimension
            clip_dim = 512  # CLIP 임베딩 차원
            embed_success = 0
            clip_embed_success = 0
            chunk_embeddings = {}  # chunk_index -> vector 매핑
            
            # 🚀 배치 임베딩 최적화: 텍스트 청크 + 이미지 캡션을 한 번에 처리
            text_chunks_list = []
            text_chunk_indices = []
            for idx, ch in enumerate(doc_chunks):
                modality = getattr(ch, 'modality', 'text')
                content = (getattr(ch, 'content_text', '') or '').strip()
                
                # 텍스트 청크 또는 의미 있는 캡션이 있는 이미지 청크 포함
                if modality == 'text' and content:
                    text_chunks_list.append(content)
                    text_chunk_indices.append(idx)
                elif modality == 'image' and content:
                    # 이미지 캡션도 텍스트 임베딩 생성 (일반 검색에서도 찾을 수 있도록)
                    text_chunks_list.append(content)
                    text_chunk_indices.append(idx)
                    logger.debug(f"[MULTIMODAL][IMAGE-CAPTION] 이미지 캡션 배치 추가: idx={idx}, caption='{content[:60]}'")
            
            # 배치 임베딩 생성 (한 번의 API 호출로 여러 텍스트 처리)
            text_embeddings_batch = []
            if text_chunks_list:
                logger.info(f"[MULTIMODAL][BATCH-EMB] 텍스트 배치 임베딩 시작: {len(text_chunks_list)}개")
                try:
                    from app.services.core.embedding_service import EmbeddingService
                    emb_service = EmbeddingService()
                    text_embeddings_batch = await emb_service.get_embeddings_batch(text_chunks_list, batch_size=100)
                    logger.info(f"[MULTIMODAL][BATCH-EMB] ✅ 텍스트 배치 임베딩 완료: {len(text_embeddings_batch)}개")
                except Exception as batch_err:
                    logger.error(f"[MULTIMODAL][BATCH-EMB] ❌ 배치 임베딩 실패 (폴백 처리): {batch_err}")
                    # 실패 시 개별 처리로 폴백
                    text_embeddings_batch = []
            
            # 배치 결과를 청크 인덱스에 매핑
            text_embedding_map = {}
            for idx, vec in zip(text_chunk_indices, text_embeddings_batch):
                text_embedding_map[idx] = vec
            
            # 청크별로 임베딩 저장 (배치 결과 + CLIP 이미지 임베딩)
            for idx, ch in enumerate(doc_chunks):
                try:
                    modality = getattr(ch, 'modality', 'text')
                    vec = None
                    clip_vec = None
                    
                    # 텍스트 임베딩: 배치 결과에서 가져오기 (텍스트 청크 + 이미지 캡션)
                    if idx in text_embedding_map:
                        vec = text_embedding_map[idx]
                        if modality == 'image':
                            logger.info(f"[MULTIMODAL][IMAGE-CAPTION] ✅ 이미지 캡션 텍스트 임베딩 적용: chunk={ch.chunk_id}")
                        else:
                            logger.debug(f"[MULTIMODAL][BATCH-EMB] 텍스트 임베딩 매핑: chunk={ch.chunk_id}, idx={idx}")
                    elif modality == 'text':
                        # TEXT 청크가 배치에서 누락된 경우에만 개별 생성 (폴백)
                        content = getattr(ch, 'content_text', '') or ''
                        if content.strip():
                            vec = await korean_nlp_service.generate_korean_embedding(content)
                            logger.warning(f"[MULTIMODAL][BATCH-EMB] 배치 누락 - 개별 임베딩 생성: chunk={ch.chunk_id}")
                    
                    # 이미지 청크인 경우 CLIP 임베딩 생성 (개별 처리 유지)
                    if modality == 'image' and self.image_embedding_service:
                        try:
                            # 이미지 객체 조회
                            source_object_ids = getattr(ch, 'source_object_ids', [])
                            if source_object_ids:
                                # 첫 번째 이미지 객체에서 CLIP 임베딩 생성
                                img_obj_result = await session.execute(
                                    select(DocExtractedObject)
                                    .where(DocExtractedObject.object_id == source_object_ids[0])
                                )
                                img_obj = img_obj_result.scalar_one_or_none()
                                
                                if img_obj and settings.storage_backend == 'azure_blob':
                                    # Azure Blob에서 이미지 다운로드
                                    azure_factory4 = get_azure_blob_service if callable(get_azure_blob_service) else None
                                    if not azure_factory4:
                                        raise RuntimeError("Azure Blob service factory not available")
                                    azure = azure_factory4()
                                    page_no_val = getattr(img_obj, 'page_no', 0) or 0
                                    img_blob_key = f"multimodal/{file_bss_info_sno}/objects/image_{img_obj.object_id}_{page_no_val}.png"
                                    img_bytes = azure.download_blob_to_bytes(img_blob_key, purpose='intermediate')
                                    
                                    if img_bytes:
                                        # CLIP 이미지 임베딩 생성
                                        clip_vec = await self.image_embedding_service.generate_image_embedding(
                                            image_bytes=img_bytes
                                        )
                                        if clip_vec:
                                            clip_embed_success += 1
                                            logger.info(f"[MULTIMODAL][CLIP] ✅ 이미지 CLIP 임베딩 생성: chunk={ch.chunk_id}, dim={len(clip_vec)}")
                        except Exception as clip_err:
                            logger.warning(f"[MULTIMODAL][CLIP] CLIP 임베딩 생성 실패 chunk={ch.chunk_id}: {clip_err}")
                    
                    # 텍스트 청크의 경우에도 CLIP 텍스트 임베딩 생성 가능 (선택적)
                    elif modality == 'text' and self.image_embedding_service and getattr(settings, 'enable_text_clip_embedding', False):
                        try:
                            content_text = getattr(ch, 'content_text', '') or ''
                            if content_text.strip():
                                clip_vec = await self.image_embedding_service.generate_text_embedding(content_text)
                                if clip_vec:
                                    clip_embed_success += 1
                                    logger.info(f"[MULTIMODAL][CLIP] ✅ 텍스트 CLIP 임베딩 생성: chunk={ch.chunk_id}, dim={len(clip_vec)}")
                        except Exception as clip_err:
                            logger.warning(f"[MULTIMODAL][CLIP] 텍스트 CLIP 임베딩 생성 실패 chunk={ch.chunk_id}: {clip_err}")
                    
                    # 임베딩 벡터 저장 (텍스트 임베딩 또는 CLIP 임베딩 중 하나라도 있으면 저장)
                    if vec or clip_vec:
                        # 텍스트 벡터 패딩 (있는 경우만)
                        if vec:
                            if len(vec) < max_dim:
                                vec = vec + [0.0] * (max_dim - len(vec))
                            elif len(vec) > max_dim:
                                vec = vec[:max_dim]
                        
                        # CLIP 벡터 패딩 (있는 경우만)
                        if clip_vec:
                            if len(clip_vec) < clip_dim:
                                clip_vec = clip_vec + [0.0] * (clip_dim - len(clip_vec))
                            elif len(clip_vec) > clip_dim:
                                clip_vec = clip_vec[:clip_dim]
                        
                        # 벤더별 벡터 컬럼 할당
                        provider = None
                        azure_vec_1536 = None
                        azure_vec_3072 = None
                        azure_clip_vec = None
                        aws_vec_1024 = None
                        aws_vec_256 = None
                        
                        if vec:
                            if max_dim == 1536:
                                provider = 'azure'
                                azure_vec_1536 = vec
                            elif max_dim == 3072:
                                provider = 'azure'
                                azure_vec_3072 = vec
                            elif max_dim == 1024:
                                provider = 'aws'
                                aws_vec_1024 = vec
                            elif max_dim == 256:
                                provider = 'aws'
                                aws_vec_256 = vec
                        
                        if clip_vec:
                            azure_clip_vec = clip_vec  # CLIP은 Azure 전용
                            if not provider:
                                provider = 'azure'
                        
                        emb = DocEmbedding(
                            chunk_id=ch.chunk_id,
                            file_bss_info_sno=file_bss_info_sno,
                            provider=provider,
                            model_name=current_embedding_model,
                            modality=modality,
                            dimension=max_dim,
                            azure_vector_1536=azure_vec_1536,
                            azure_vector_3072=azure_vec_3072,
                            azure_clip_vector=azure_clip_vec,
                            aws_vector_1024=aws_vec_1024,
                            aws_vector_256=aws_vec_256,
                            vector=vec,  # 레거시 호환
                            clip_vector=clip_vec  # 레거시 호환
                        )
                        session.add(emb)
                        embed_success += 1
                        
                        # 청크 인덱스 매핑 저장 (vs_doc_contents_chunks 업데이트용, 텍스트 벡터가 있는 경우만)
                        if vec:
                            chunk_idx = getattr(ch, 'chunk_index', None)
                            if chunk_idx is not None:
                                chunk_embeddings[chunk_idx] = vec
                            
                except Exception as ee:
                    logger.warning(f"[MULTIMODAL] Embedding 실패 chunk={ch.chunk_id}: {ee}")
            await session.flush()
            result["embeddings_count"] = embed_success
            result["clip_embeddings_count"] = clip_embed_success
            _stage("embedding", True, embeddings=embed_success, clip_embeddings=clip_embed_success)

            # -----------------------------
            # 3.1. vs_doc_contents_chunks 임베딩 업데이트 (RAG 기능 지원)
            # -----------------------------
            try:
                logger.info(f"[MULTIMODAL][RAG] vs_doc_contents_chunks 임베딩 업데이트 시작 - {len(chunk_embeddings)}개")
                
                # vs_doc_contents_chunks 레코드 조회 및 업데이트
                from sqlalchemy import update
                
                for chunk_idx, vec in chunk_embeddings.items():
                    stmt = (
                        update(VsDocContentsChunks)
                        .where(VsDocContentsChunks.file_bss_info_sno == file_bss_info_sno)
                        .where(VsDocContentsChunks.chunk_index == chunk_idx)
                        .values(chunk_embedding=vec)
                    )
                    await session.execute(stmt)
                
                await session.flush()
                logger.info(f"[MULTIMODAL][RAG] ✅ vs_doc_contents_chunks 임베딩 업데이트 완료 - {len(chunk_embeddings)}개")
                
            except Exception as emb_err:
                logger.error(f"[MULTIMODAL][RAG] ❌ vs_doc_contents_chunks 임베딩 업데이트 실패: {emb_err}")
                # 실패해도 계속 진행

            # -----------------------------
            # 3.5. Azure Blob Storage - 임베딩 결과 저장 (derived)
            # -----------------------------
            performed_blob_embedding = False
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                    _start_stage("blob_embedding_save")
                    performed_blob_embedding = True
                    azure_factory5 = get_azure_blob_service if callable(get_azure_blob_service) else None
                    if not azure_factory5:
                        raise RuntimeError("Azure Blob service factory not available")
                    azure = azure_factory5()
                    
                    # 임베딩 메타데이터 저장
                    embedding_metadata_key = f"multimodal/{file_bss_info_sno}/embedding_metadata.json"
                    embedding_metadata = {
                        "model_name": current_embedding_model,
                        "vector_dimension": max_dim,
                        "embeddings_generated": embed_success,
                        "total_chunks": len(doc_chunks),
                        "timestamp": datetime.now().isoformat()
                    }
                    azure.upload_bytes(
                        json.dumps(embedding_metadata, ensure_ascii=False).encode('utf-8'),
                        embedding_metadata_key,
                        purpose='derived'
                    )
                    
                    logger.info(f"[MULTIMODAL-BLOB] 임베딩 메타데이터 저장 완료 - {embed_success}/{len(doc_chunks)} 임베딩")
                    _stage("blob_embedding_save", True, embeddings_saved=embed_success)
                    
            except Exception as blob_err:
                logger.warning(f"[MULTIMODAL-BLOB] 임베딩 결과 저장 실패 (무시하고 계속): {blob_err}")
                if performed_blob_embedding:
                    _stage("blob_embedding_save", False, error=str(blob_err))
            finally:
                if not performed_blob_embedding:
                    _stage("blob_embedding_save", False, skipped=True)

            # -----------------------------
            # 4. Search Index Creation (통합 검색 인덱스 생성)
            # -----------------------------
            _start_stage("search_index_creation")
            try:
                # 4.1. 파일 정보 조회
                stmt_file = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == file_bss_info_sno)
                file_result = await session.execute(stmt_file)
                file_info = file_result.scalar_one_or_none()
                
                if not file_info:
                    logger.warning(f"[MULTIMODAL] 파일 정보를 찾을 수 없음: {file_bss_info_sno}")
                    _stage("search_index_creation", False, error="File info not found")
                else:
                    # 4.2. 전체 텍스트 수집 (모든 청크 통합)
                    full_text_parts = []
                    image_count = 0
                    table_count = 0
                    
                    for chunk in doc_chunks:
                        content = getattr(chunk, 'content_text', '') or ''
                        if content:
                            full_text_parts.append(content)
                    
                    # 추출된 객체에서 이미지/테이블 개수 확인
                    for obj in extracted_objects:
                        obj_type = getattr(obj, 'object_type', '')
                        if obj_type == 'IMAGE':
                            image_count += 1
                        elif obj_type == 'TABLE':
                            table_count += 1
                    
                    full_content = '\n\n'.join(full_text_parts)
                    
                    logger.info(f"[MULTIMODAL] 검색 인덱스 데이터 수집 완료 - "
                               f"텍스트 청크: {len(doc_chunks)}개, "
                               f"이미지: {image_count}개, "
                               f"테이블: {table_count}개, "
                               f"전체 텍스트 길이: {len(full_content)}")
                    
                    # 4.3. NLP 분석 (전체 문서 레벨)
                    # textsearch_ko가 자동으로 형태소 분석을 하므로, 간소화된 분석만 수행
                    logger.info(f"[MULTIMODAL] 검색 인덱스를 위한 텍스트 준비 - 텍스트 길이: {len(full_content)}")
                    nlp_result = await korean_nlp_service.analyze_text_for_search(full_content[:10000])  # 처음 10,000자만 분석
                    
                    # 4.4. 검색 메타데이터 구성 (textsearch_ko가 tsvector 생성 시 자동 처리)
                    search_metadata = {
                        'keywords': nlp_result.get('keywords', [])[:30],  # 빈 리스트 (textsearch_ko가 자동 처리)
                        'proper_nouns': nlp_result.get('proper_nouns', [])[:30],  # 빈 리스트
                        'corp_names': nlp_result.get('entities', {}).get('ORG', [])[:20] if isinstance(nlp_result.get('entities'), dict) else [],
                        'main_topics': nlp_result.get('keywords', [])[:10],  # 빈 리스트
                    }
                    
                    logger.info(f"[MULTIMODAL] 텍스트 분석 완료 - textsearch_ko가 tsvector 생성 시 자동으로 형태소 분석 수행")
                    
                    # 4.5. 이미지 정보 수집 (멀티모달 검색용)
                    image_metadata = []
                    for obj in extracted_objects:
                        if getattr(obj, 'object_type', '') == 'IMAGE':
                            # 🎯 Caption 우선 추출 (content_text에 저장됨)
                            caption = getattr(obj, 'content_text', '') or ''
                            structure_json = getattr(obj, 'structure_json', {}) or {}
                            
                            # Fallback: structure_json에서도 확인
                            if not caption and isinstance(structure_json, dict):
                                caption = structure_json.get('caption', '')
                            
                            img_meta = {
                                'object_id': getattr(obj, 'object_id', None),
                                'page_number': getattr(obj, 'page_no', None),
                                'caption': caption,  # 🎯 Azure DI에서 추출한 Figure caption
                                'bounding_box': getattr(obj, 'bbox', None),
                                'has_caption': bool(caption),  # 🎯 Caption 유무 플래그
                            }
                            image_metadata.append(img_meta)
                            
                            # 🎯 Caption 발견 시 로그 출력
                            if caption:
                                logger.info(f"[CAPTION] ✅ 이미지 캡션 수집 완료 - obj_id={img_meta['object_id']}, page={img_meta['page_number']}, caption='{caption[:80]}...'")
                    
                    captions_found = sum(1 for img in image_metadata if img.get('has_caption'))
                    logger.info(f"[MULTIMODAL] 이미지 메타데이터 수집 완료 - {len(image_metadata)}개 (캡션 있음: {captions_found}개)")
                    
                    # 4.6. 문서 데이터 준비 (멀티모달 검색 지원)
                    document_data = {
                        'title': getattr(file_info, 'file_lgc_nm', 'Untitled'),
                        'file_name': getattr(file_info, 'file_lgc_nm', ''),
                        'file_type': getattr(file_info, 'file_extsn', 'unknown'),
                        'full_content': full_content,  # 전체 텍스트 (중요!)
                        'page_count': len(set(getattr(obj, 'page_number', 1) for obj in extracted_objects)) if extracted_objects else 1,
                        'language': 'mixed',  # 한국어/영어 혼합
                        'has_images': image_count > 0,
                        'has_tables': table_count > 0,
                        'image_count': image_count,
                        'table_count': table_count,
                        'images': image_metadata,  # 이미지 메타데이터 (멀티모달 검색용)
                    }
                    
                    logger.info(f"[MULTIMODAL] 문서 데이터 준비 완료 - "
                               f"제목: {document_data['title']}, "
                               f"텍스트 길이: {len(full_content)}, "
                               f"이미지: {image_count}개, "
                               f"테이블: {table_count}개")
                    
                    # 4.6. 검색 인덱스 생성
                    search_result = await self.search_index_service.store_document_for_search(
                        session=session,
                        file_bss_info_sno=file_bss_info_sno,
                        container_id=container_id,
                        document_data=document_data,
                        nlp_analysis=search_metadata,
                        user_info={'emp_no': user_emp_no} if user_emp_no else None
                    )
                    
                    if search_result.get('success'):
                        logger.info(f"[MULTIMODAL] 검색 인덱스 생성 완료 - search_doc_id: {search_result.get('search_doc_id')}")
                        _stage("search_index_creation", True, 
                              search_doc_id=search_result.get('search_doc_id'),
                              keywords_count=len(search_metadata.get('keywords', [])),
                              content_length=len(full_content))
                    else:
                        logger.warning(f"[MULTIMODAL] 검색 인덱스 생성 실패: {search_result.get('error')}")
                        _stage("search_index_creation", False, error=search_result.get('error'))
                        
            except Exception as idx_err:
                logger.error(f"[MULTIMODAL] 검색 인덱스 생성 중 오류: {idx_err}")
                _stage("search_index_creation", False, error=str(idx_err))
            
            # 4.7. 기존 검색 인덱스 메타데이터 업데이트 (있는 경우)
            _start_stage("index_metadata_update")
            try:
                stmt = select(TbDocumentSearchIndex).where(TbDocumentSearchIndex.file_bss_info_sno == file_bss_info_sno)
                sr = await session.execute(stmt)
                search_index = sr.scalar_one_or_none()
                if search_index:
                    search_index.extraction_session_id = extraction_session.extraction_session_id
                    search_index.primary_chunk_session_id = chunk_session.chunk_session_id
                    search_index.last_embedding_model = current_embedding_model
                    search_index.has_table = any(o.object_type == "TABLE" for o in extracted_objects)
                    search_index.has_image = any(o.object_type == "IMAGE" for o in extracted_objects)
                    logger.info(f"[MULTIMODAL] 검색 인덱스 메타데이터 업데이트 완료")
                _stage("index_metadata_update", True)
            except Exception as meta_err:
                logger.warning(f"[MULTIMODAL] 검색 인덱스 메타데이터 업데이트 실패 (무시): {meta_err}")
                _stage("index_metadata_update", False, error=str(meta_err))

            await session.commit()

            elapsed = (datetime.now() - started).total_seconds()
            # 통계 계산 (SQLAlchemy 객체 속성 안전하게 접근)
            tables_count = sum(1 for o in extracted_objects if getattr(o, 'object_type', '') == "TABLE")
            images_count = sum(1 for o in extracted_objects if getattr(o, 'object_type', '') == "IMAGE")  
            figures_count = sum(1 for o in extracted_objects if getattr(o, 'object_type', '') == "FIGURE")
            
            # 청크별 통계
            text_chunks_count = sum(1 for c in doc_chunks if getattr(c, 'modality', 'text') == 'text')
            image_chunks_count = sum(1 for c in doc_chunks if getattr(c, 'modality', 'text') == 'image')
            table_chunks_count = sum(1 for c in doc_chunks if getattr(c, 'modality', 'text') == 'table')
            
            total_tokens = sum(getattr(c, 'token_count', 0) or 0 for c in doc_chunks)
            avg_tokens = (total_tokens / len(doc_chunks)) if doc_chunks else 0
            
            result["stats"] = {
                "elapsed_seconds": elapsed,
                "avg_chunk_tokens": avg_tokens,
                "vector_dimension": max_dim,
                "tables": tables_count,
                "images": images_count,
                "figures": figures_count,
                "text_chunks": text_chunks_count,
                "image_chunks": image_chunks_count,
                "table_chunks": table_chunks_count,
            }
            if section_chunking_meta.get("requested"):
                result["stats"]["section_chunking_enabled"] = section_chunking_meta.get("enabled")
                result["stats"]["section_chunking_detected_sections"] = section_chunking_meta.get("detected_sections", [])
                result["section_chunking"] = section_chunking_meta
            result["success"] = True
            logger.info(f"[MULTIMODAL] Pipeline success in {elapsed:.2f}s | "
                       f"chunks={result['chunks_count']} (text={text_chunks_count}, image={image_chunks_count}, table={table_chunks_count}) "
                       f"embeddings={result['embeddings_count']}")
            return result
        except Exception as e:
            logger.error(f"[MULTIMODAL] 파이프라인 오류: {e}")
            await session.rollback()
            result["error"] = str(e)
            _stage("fatal", False, error=str(e))
            return result
        finally:
            # 임시 파일 정리
            if is_temp_file and actual_file_path and os.path.exists(actual_file_path):
                try:
                    os.remove(actual_file_path)
                    logger.debug(f"[MULTIMODAL] 임시 파일 삭제 완료: {actual_file_path}")
                except Exception as cleanup_err:
                    logger.warning(f"[MULTIMODAL] 임시 파일 삭제 실패: {cleanup_err}")

    def _derive_core_content_page_set(
        self,
        sections: List[Dict[str, Any]],
        object_spans: List[Tuple[DocExtractedObject, int, int]],
    ) -> Optional[Set[int]]:
        """
        섹션 순서를 기반으로 핵심 본문 구간에 해당하는 페이지 집합 계산
        
        학술논문의 경우:
        - References 섹션 이후는 제외 (저자 프로필 사진 등 논문 내용과 무관)
        - Introduction부터 Conclusion까지가 핵심 본문
        
        개선사항:
        - bbox 기반으로 실제 페이지 번호 추출
        - References 섹션 감지 실패 시 전체 페이지의 80% 이후를 References로 간주
        """
        if not sections or not object_spans:
            return None

        # 1. 전체 객체에서 페이지 번호 추출 (bbox 기반)
        all_pages: Set[int] = set()
        for obj, _, _ in object_spans:
            page_no = self._extract_page_from_bbox(obj)
            if page_no and page_no > 0:
                all_pages.add(page_no)
        
        if not all_pages:
            logger.warning("[FIGURE-FILTER] 페이지 번호를 추출할 수 없음")
            return None
        
        max_page = max(all_pages)
        logger.info(f"[FIGURE-FILTER] 전체 페이지 범위: 1~{max_page}")

        # 2. References 섹션 감지
        intro_idx: Optional[int] = None
        conclusion_idx: Optional[int] = None
        references_idx: Optional[int] = None
        references_start_page: Optional[int] = None
        
        for section in sections:
            idx = section.get("index")
            if idx is None:
                continue
            section_type = (section.get("type") or "").lower()
            
            if intro_idx is None and section_type == "introduction":
                intro_idx = idx
            if section_type == "conclusion":
                conclusion_idx = idx
            if section_type == "references":
                references_idx = idx
                # References 섹션의 시작 페이지 저장 (섹션 정보에서)
                references_start_page = section.get("start_page")

        # 3. References 시작 페이지 결정 (섹션 감지 실패 시 bbox 기반 추정)
        if references_idx is not None and not references_start_page:
            # 섹션은 있지만 start_page가 None인 경우 → bbox로 추정
            references_start_page = self._estimate_references_page_from_objects(
                sections, object_spans, references_idx
            )
        
        if not references_start_page:
            # References 섹션 자체가 없거나 추정 실패 → 전체 페이지의 80% 이후를 References로 간주
            references_start_page = max(1, int(max_page * 0.8))
            logger.info(f"[FIGURE-FILTER] References 섹션 미감지 → 페이지 {references_start_page}부터를 후반부로 간주 (80% 기준)")
        else:
            logger.info(f"[FIGURE-FILTER] References 섹션 감지 - idx={references_idx}, start_page={references_start_page}")

        # 4. References 이전의 모든 페이지를 허용 (섹션 범위 무시)
        # 학술논문의 TABLE/FIGURE는 본문 전체에 분산되어 있으므로
        # 섹션 텍스트 위치(span)와 매칭하지 말고 단순히 페이지 번호만으로 필터링
        allowed_pages: Set[int] = {p for p in all_pages if p < references_start_page}
        
        # References 섹션 정보 로깅 (디버깅용)
        if intro_idx is not None and conclusion_idx is not None:
            logger.info(f"[FIGURE-FILTER] 섹션 인덱스: Introduction({intro_idx})~Conclusion({conclusion_idx}), References({references_idx})")
        
        logger.info(f"[FIGURE-FILTER] References({references_start_page}p) 이후 제외 → 허용 페이지: {sorted(allowed_pages)}")
        
        return allowed_pages or None
    
    def _extract_page_from_bbox(self, obj: DocExtractedObject) -> Optional[int]:
        """
        객체의 bbox 또는 structure_json에서 페이지 번호 추출
        
        우선순위:
        1. obj.page_no (이미 설정되어 있으면 사용)
        2. structure_json의 bbox 좌표에서 추출
        3. structure_json의 page_number 필드
        """
        # 1. 기존 page_no 사용
        page_no = getattr(obj, "page_no", None)
        if isinstance(page_no, int) and page_no > 0:
            return page_no
        
        # 2. structure_json에서 추출
        structure_json = getattr(obj, "structure_json", None)
        if structure_json and isinstance(structure_json, dict):
            # Azure DI bbox 구조: [{"polygon": [...], "page_number": 5}]
            bboxes = structure_json.get("bounding_regions", [])
            if bboxes and isinstance(bboxes, list) and len(bboxes) > 0:
                first_bbox = bboxes[0]
                if isinstance(first_bbox, dict):
                    bbox_page = first_bbox.get("page_number")
                    if isinstance(bbox_page, int) and bbox_page > 0:
                        return bbox_page
            
            # 직접 page_number 필드
            direct_page = structure_json.get("page_number")
            if isinstance(direct_page, int) and direct_page > 0:
                return direct_page
        
        return None
    
    def _estimate_references_page_from_objects(
        self,
        sections: List[Dict[str, Any]],
        object_spans: List[Tuple[DocExtractedObject, int, int]],
        references_idx: int
    ) -> Optional[int]:
        """
        References 섹션에 속한 객체들의 bbox에서 페이지 번호 추정
        """
        references_section = None
        for section in sections:
            if section.get("index") == references_idx:
                references_section = section
                break
        
        if not references_section:
            return None
        
        s_start = references_section.get("start_pos", 0)
        s_end = references_section.get("end_pos", 0)
        if s_end < s_start:
            s_start, s_end = s_end, s_start
        
        ref_pages: List[int] = []
        for obj, span_start, span_end in object_spans:
            # 섹션 범위와 겹치는지 확인
            if span_end <= s_start or span_start >= s_end:
                continue
            page_no = self._extract_page_from_bbox(obj)
            if page_no and page_no > 0:
                ref_pages.append(page_no)
        
        if ref_pages:
            min_page = min(ref_pages)
            logger.info(f"[FIGURE-FILTER] References 섹션 bbox 분석 → 시작 페이지: {min_page}")
            return min_page
        
        return None

def _serialize_table_to_text(table_obj: DocExtractedObject) -> str:
    """
    TABLE 객체를 검색 가능한 텍스트로 변환
    
    우선순위:
    1. content_text가 있으면 그대로 사용
    2. structure_json에 표 데이터가 있으면 마크다운 표로 변환
    3. 없으면 플레이스홀더 텍스트 반환
    """
    # 1. 기존 content_text가 있으면 사용
    content_text = getattr(table_obj, 'content_text', '') or ''
    if content_text and content_text.strip() and not content_text.startswith('[표 '):
        return content_text.strip()
    
    # 2. structure_json에서 표 데이터 추출
    structure_json = getattr(table_obj, 'structure_json', None)
    if structure_json and isinstance(structure_json, dict):
        # XLSX 시트 데이터 (전체 시트가 TABLE로 저장됨)
        if 'text' in structure_json and structure_json.get('text', '').strip():
            return structure_json['text'].strip()
        
        # Azure DI 표 구조 (cells, rows, columns 등)
        if 'cells' in structure_json or 'rows' in structure_json:
            try:
                return _convert_azure_table_to_markdown(structure_json)
            except Exception as e:
                logger.debug(f"[TABLE] Azure 표 변환 실패: {e}")
        
        # PDF/PPT 표 인덱스만 있는 경우 (실제 데이터 없음)
        if 'table_index' in structure_json:
            table_idx = structure_json.get('table_index', 0)
            page_no = getattr(table_obj, 'page_no', None)
            return f"[표 {table_idx + 1} - 페이지 {page_no}]"
    
    # 3. 플레이스홀더
    page_no = getattr(table_obj, 'page_no', None)
    seq = getattr(table_obj, 'sequence_in_page', None)
    return f"[표 - 페이지 {page_no}, 순서 {seq}]"


def _convert_azure_table_to_markdown(structure: Dict[str, Any]) -> str:
    """
    Azure Document Intelligence 표 구조를 마크다운 표로 변환
    
    structure 예시:
    {
        "rowCount": 3,
        "columnCount": 2,
        "cells": [
            {"rowIndex": 0, "columnIndex": 0, "content": "Header1"},
            {"rowIndex": 0, "columnIndex": 1, "content": "Header2"},
            ...
        ]
    }
    """
    if not structure:
        return ""
    
    # 셀 데이터 추출
    cells = structure.get('cells', [])
    if not cells:
        # rows 형태로 제공된 경우
        rows = structure.get('rows', [])
        if rows:
            lines = []
            for row_data in rows:
                if isinstance(row_data, dict) and 'cells' in row_data:
                    row_cells = [str(c.get('content', '')).strip() for c in row_data['cells']]
                    lines.append(' | '.join(row_cells))
                elif isinstance(row_data, list):
                    lines.append(' | '.join(str(c).strip() for c in row_data))
            return '\n'.join(lines)
        return ""
    
    # 행/열 크기 확인
    row_count = structure.get('rowCount', max((c.get('rowIndex', 0) for c in cells), default=0) + 1)
    col_count = structure.get('columnCount', max((c.get('columnIndex', 0) for c in cells), default=0) + 1)
    
    # 2D 배열 초기화
    table_grid = [['' for _ in range(col_count)] for _ in range(row_count)]
    
    # 셀 데이터 채우기
    for cell in cells:
        row_idx = cell.get('rowIndex', 0)
        col_idx = cell.get('columnIndex', 0)
        content = str(cell.get('content', '')).strip()
        
        # 병합된 셀 처리
        row_span = cell.get('rowSpan', 1)
        col_span = cell.get('columnSpan', 1)
        
        if 0 <= row_idx < row_count and 0 <= col_idx < col_count:
            table_grid[row_idx][col_idx] = content
            
            # 병합된 셀 영역 표시
            for r in range(row_idx, min(row_idx + row_span, row_count)):
                for c in range(col_idx, min(col_idx + col_span, col_count)):
                    if r != row_idx or c != col_idx:
                        table_grid[r][c] = ''  # 병합된 셀은 빈 문자열
    
    # 마크다운 표 생성
    lines = []
    for idx, row in enumerate(table_grid):
        lines.append('| ' + ' | '.join(row) + ' |')
        # 첫 번째 행 후 구분선 추가 (헤더로 간주)
        if idx == 0 and row_count > 1:
            lines.append('| ' + ' | '.join(['---'] * col_count) + ' |')
    
    return '\n'.join(lines)


def _clean_metadata_for_json(metadata: Any) -> Any:
    """
    메타데이터에서 JSON 직렬화할 수 없는 binary_data 등을 재귀적으로 제거
    """
    if isinstance(metadata, dict):
        result = {}
        for key, value in metadata.items():
            if key == 'binary_data':
                # binary_data는 제거하고 대신 참조 정보만 저장
                result['binary_data_info'] = {
                    'removed': True,
                    'type': type(value).__name__,
                    'size_bytes': len(value) if isinstance(value, bytes) else None
                }
            else:
                result[key] = _clean_metadata_for_json(value)
        return result
    elif isinstance(metadata, list):
        return [_clean_metadata_for_json(item) for item in metadata]
    elif isinstance(metadata, bytes):
        # bytes 타입은 정보만 저장
        return {
            'binary_data_info': {
                'removed': True,
                'type': 'bytes',
                'size_bytes': len(metadata)
            }
        }
    else:
        return metadata


# 전역 인스턴스
multimodal_document_service = MultimodalDocumentService()

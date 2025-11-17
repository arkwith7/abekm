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
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document.multimodal_models import (
    DocExtractionSession,
    DocExtractedObject,
    DocChunkSession,
    DocChunk,
    DocEmbedding
)
from app.models import TbDocumentSearchIndex
from app.services.document.extraction.text_extractor_service import text_extractor_service
from app.services.core.korean_nlp_service import korean_nlp_service
from app.core.config import settings
from app.services.document.chunking.advanced_chunker import advanced_chunk_text

# Azure Blob Storage 통합
try:
    from app.services.core.azure_blob_service import get_azure_blob_service
except ImportError:
    get_azure_blob_service = None

logger = logging.getLogger(__name__)

class MultimodalDocumentService:
    """멀티모달 문서 처리 서비스"""
    
    async def process_document_multimodal(
        self,
        file_path: str,
        file_bss_info_sno: int,
        container_id: str,
        user_emp_no: str,
        session: AsyncSession,
        provider: str = "azure",
        model_profile: str = "default"
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

        def _stage(name: str, success: bool, **extra):
            result["stages"].append({"name": name, "success": success, **extra})

        try:
            # -----------------------------
            # 1. Extraction
            # -----------------------------
            extraction_session = DocExtractionSession(
                file_bss_info_sno=file_bss_info_sno,
                provider=provider,
                model_profile=model_profile,
                pipeline_type="azure",
                status="running",
                started_at=datetime.now()
            )
            session.add(extraction_session)
            await session.flush()
            result["extraction_session_id"] = extraction_session.extraction_session_id
            logger.info(f"[MULTIMODAL] Extraction session started: {extraction_session.extraction_session_id}")

            extraction_result = await text_extractor_service.extract_text_from_file(file_path)
            if not extraction_result.get("success"):
                extraction_session.status = "failed"
                extraction_session.error_message = extraction_result.get("error")
                extraction_session.completed_at = datetime.now()
                await session.commit()
                _stage("extraction", False, error=extraction_result.get("error"))
                result["error"] = extraction_result.get("error")
                return result

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

            # PDF
            if "pages" in metadata:
                for p in metadata["pages"]:
                    _add_text_obj(p.get("page_no"), p.get("text", ""))
                    for idx in range(p.get("tables_count", 0)):
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=p.get("page_no"),
                            object_type="TABLE",
                            sequence_in_page=idx + 1,
                            content_text=f"[표 {idx+1}]",
                            structure_json={"table_index": idx}
                        ))
                    for img_meta in p.get("images_metadata", []):
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=p.get("page_no"),
                            object_type="IMAGE",
                            sequence_in_page=img_meta.get("image_index"),
                            bbox=[img_meta.get('x0',0), img_meta.get('y0',0), img_meta.get('x1',0), img_meta.get('y1',0)],
                            structure_json=img_meta
                        ))
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
                        extracted_objects.append(DocExtractedObject(
                            extraction_session_id=extraction_session.extraction_session_id,
                            file_bss_info_sno=file_bss_info_sno,
                            page_no=s.get("slide_no"),
                            object_type="IMAGE",
                            sequence_in_page=img_meta.get("image_index"),
                            bbox=[img_meta.get('left',0), img_meta.get('top',0), img_meta.get('left',0)+img_meta.get('width',0), img_meta.get('top',0)+img_meta.get('height',0)],
                            structure_json=img_meta
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

            for obj in extracted_objects:
                session.add(obj)
            await session.flush()
            extraction_session.status = "success"
            extraction_session.completed_at = datetime.now()
            extraction_session.page_count_detected = len(metadata.get('pages', metadata.get('slides', metadata.get('sheets', []))))
            result["objects_count"] = len(extracted_objects)
            _stage("extraction", True, objects=len(extracted_objects))

            # -----------------------------
            # 1.5. Azure Blob Storage - 중간 결과 저장
            # -----------------------------
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                    azure = get_azure_blob_service()
                    
                    # 전체 추출 텍스트 저장 (intermediate 컨테이너)
                    full_text_key = f"multimodal/{file_bss_info_sno}/extraction_full_text.txt"
                    full_text_content = extraction_result.get("text", "")
                    if full_text_content:
                        azure.upload_bytes(
                            full_text_content.encode('utf-8'), 
                            full_text_key, 
                            purpose='intermediate'
                        )
                        logger.info(f"[MULTIMODAL-BLOB] 전체 텍스트 저장: {full_text_key}")
                    
                    # 추출 메타데이터 저장
                    metadata_key = f"multimodal/{file_bss_info_sno}/extraction_metadata.json"
                    metadata_content = {
                        "extraction_session_id": extraction_session.extraction_session_id,
                        "provider": provider,
                        "pipeline_type": "azure",
                        "extracted_objects_count": len(extracted_objects),
                        "pages_detected": extraction_session.page_count_detected,
                        "extraction_metadata": metadata,
                        "timestamp": datetime.now().isoformat()
                    }
                    azure.upload_bytes(
                        json.dumps(metadata_content, ensure_ascii=False).encode('utf-8'),
                        metadata_key,
                        purpose='intermediate'
                    )
                    logger.info(f"[MULTIMODAL-BLOB] 메타데이터 저장: {metadata_key}")
                    
                    # 객체별 세부 정보 저장
                    for idx, obj in enumerate(extracted_objects):
                        if obj.content_text and obj.object_type == "TEXT_BLOCK":
                            obj_key = f"multimodal/{file_bss_info_sno}/objects/text_block_{idx}_{obj.page_no or 0}.txt"
                            azure.upload_bytes(
                                obj.content_text.encode('utf-8'),
                                obj_key,
                                purpose='intermediate'
                            )
                        elif obj.object_type in ["TABLE", "IMAGE"]:
                            obj_key = f"multimodal/{file_bss_info_sno}/objects/{obj.object_type.lower()}_{idx}_{obj.page_no or 0}.json"
                            obj_content = {
                                "object_type": obj.object_type,
                                "page_no": obj.page_no,
                                "sequence_in_page": obj.sequence_in_page,
                                "content_text": obj.content_text,
                                "structure_json": obj.structure_json,
                                "bbox": obj.bbox
                            }
                            azure.upload_bytes(
                                json.dumps(obj_content, ensure_ascii=False).encode('utf-8'),
                                obj_key,
                                purpose='intermediate'
                            )
                    
                    logger.info(f"[MULTIMODAL-BLOB] {len(extracted_objects)}개 객체 저장 완료")
                    _stage("blob_intermediate_save", True, objects_saved=len(extracted_objects))
                    
            except Exception as blob_err:
                logger.warning(f"[MULTIMODAL-BLOB] 중간 결과 저장 실패 (무시하고 계속): {blob_err}")
                _stage("blob_intermediate_save", False, error=str(blob_err))

            # -----------------------------
            # 2. Chunking (advanced)
            # -----------------------------
            text_objs = [o for o in extracted_objects if o.object_type == "TEXT_BLOCK"]
            chunk_session = DocChunkSession(
                file_bss_info_sno=file_bss_info_sno,
                extraction_session_id=extraction_session.extraction_session_id,
                strategy_name="advanced_paragraph_token",
                params_json={
                    "min_tokens": 80,
                    "target_tokens": 280,
                    "max_tokens": 420,
                    "overlap_tokens": 40
                },
                status="running",
                started_at=datetime.now()
            )
            session.add(chunk_session)
            await session.flush()
            result["chunk_session_id"] = chunk_session.chunk_session_id

            iterable = ((o.content_text or "", o.page_no, o.object_id) for o in text_objs)
            adv_chunks = advanced_chunk_text(iterable)
            doc_chunks: List[DocChunk] = []
            for idx, cdict in enumerate(adv_chunks):
                doc_chunk = DocChunk(
                    chunk_session_id=chunk_session.chunk_session_id,
                    file_bss_info_sno=file_bss_info_sno,
                    chunk_index=idx,
                    source_object_ids=cdict.get('source_object_ids', []),
                    content_text=cdict['content_text'],
                    token_count=cdict['token_count'],
                    modality="text"
                )
                session.add(doc_chunk)
                doc_chunks.append(doc_chunk)
            await session.flush()
            chunk_session.status = "success"
            chunk_session.completed_at = datetime.now()
            chunk_session.chunk_count = len(doc_chunks)
            result["chunks_count"] = len(doc_chunks)
            _stage("chunking", True, chunks=len(doc_chunks))

            # -----------------------------
            # 2.5. Azure Blob Storage - 청킹 결과 저장 (derived)
            # -----------------------------
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                    azure = get_azure_blob_service()
                    
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
                        chunk_key = f"multimodal/{file_bss_info_sno}/chunks/chunk_{idx:04d}.json"
                        chunk_content = {
                            "chunk_id": getattr(chunk, 'chunk_id', None),
                            "chunk_index": idx,
                            "content_text": getattr(chunk, 'content_text', ''),
                            "token_count": getattr(chunk, 'token_count', 0),
                            "modality": "text",
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
                _stage("blob_derived_save", False, error=str(blob_err))

            # -----------------------------
            # 3. Embeddings
            # -----------------------------
            current_embedding_model = settings.get_current_embedding_model()
            max_dim = settings.vector_dimension
            embed_success = 0
            for ch in doc_chunks:
                try:
                    vec = await korean_nlp_service.generate_korean_embedding(ch.content_text)
                    if vec:
                        if len(vec) < max_dim:
                            vec = vec + [0.0] * (max_dim - len(vec))
                        elif len(vec) > max_dim:
                            vec = vec[:max_dim]
                        emb = DocEmbedding(
                            chunk_id=ch.chunk_id,
                            file_bss_info_sno=file_bss_info_sno,
                            model_name=current_embedding_model,
                            modality="text",
                            dimension=max_dim,
                            vector=vec
                        )
                        session.add(emb)
                        embed_success += 1
                except Exception as ee:
                    logger.warning(f"[MULTIMODAL] Embedding 실패 chunk={ch.chunk_id}: {ee}")
            await session.flush()
            result["embeddings_count"] = embed_success
            _stage("embedding", True, embeddings=embed_success)

            # -----------------------------
            # 3.5. Azure Blob Storage - 임베딩 결과 저장 (derived)
            # -----------------------------
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and file_bss_info_sno:
                    azure = get_azure_blob_service()
                    
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
                _stage("blob_embedding_save", False, error=str(blob_err))

            # -----------------------------
            # 4. Search Index Update
            # -----------------------------
            stmt = select(TbDocumentSearchIndex).where(TbDocumentSearchIndex.file_bss_info_sno == file_bss_info_sno)
            sr = await session.execute(stmt)
            search_index = sr.scalar_one_or_none()
            if search_index:
                search_index.extraction_session_id = extraction_session.extraction_session_id
                search_index.primary_chunk_session_id = chunk_session.chunk_session_id
                search_index.last_embedding_model = current_embedding_model
                search_index.has_table = any(o.object_type == "TABLE" for o in extracted_objects)
                search_index.has_image = any(o.object_type == "IMAGE" for o in extracted_objects)
            _stage("index_update", True)

            await session.commit()

            elapsed = (datetime.now() - started).total_seconds()
            # 통계 계산 (SQLAlchemy 객체 속성 안전하게 접근)
            tables_count = sum(1 for o in extracted_objects if getattr(o, 'object_type', '') == "TABLE")
            images_count = sum(1 for o in extracted_objects if getattr(o, 'object_type', '') == "IMAGE")  
            figures_count = sum(1 for o in extracted_objects if getattr(o, 'object_type', '') == "FIGURE")
            
            total_tokens = sum(getattr(c, 'token_count', 0) or 0 for c in doc_chunks)
            avg_tokens = (total_tokens / len(doc_chunks)) if doc_chunks else 0
            
            result["stats"] = {
                "elapsed_seconds": elapsed,
                "avg_chunk_tokens": avg_tokens,
                "vector_dimension": max_dim,
                "tables": tables_count,
                "images": images_count,
                "figures": figures_count,
            }
            result["success"] = True
            logger.info(f"[MULTIMODAL] Pipeline success in {elapsed:.2f}s | chunks={result['chunks_count']} embeddings={result['embeddings_count']}")
            return result
        except Exception as e:
            logger.error(f"[MULTIMODAL] 파이프라인 오류: {e}")
            await session.rollback()
            result["error"] = str(e)
            _stage("fatal", False, error=str(e))
            return result

# 전역 인스턴스
multimodal_document_service = MultimodalDocumentService()

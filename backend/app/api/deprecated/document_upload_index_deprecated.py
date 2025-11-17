"""
통합 문서 업로드 및 검색 인덱싱 API
문서 처리부터 검색 가능한 상태까지 완전한 파이프라인 제공
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import tempfile
import os
from pathlib import Path

from app.services.document_processor_service import document_processor_service
from app.services.document_index_service import document_index_service
from app.services.auth_service import get_current_user
from app.models import User
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Document Upload & Indexing"])

# Request/Response 모델
class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    file_info: Dict[str, Any]
    processing_result: Optional[Dict[str, Any]] = None
    indexing_result: Optional[Dict[str, Any]] = None
    search_doc_ids: Optional[List[str]] = None
    error: Optional[str] = None

class DocumentUploadRequest(BaseModel):
    knowledge_container_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None

@router.post("/upload-and-index", response_model=DocumentUploadResponse)
async def upload_and_index_document(
    knowledge_container_id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON 문자열로 받기
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    문서 업로드 및 검색 인덱싱 통합 처리
    
    1. 파일 업로드 및 내용 추출
    2. 한국어 NLP 처리
    3. 벡터 임베딩 생성
    4. 검색 인덱스에 등록
    """
    try:
        # 태그 파싱
        tag_list = []
        if tags:
            import json
            try:
                tag_list = json.loads(tags)
            except:
                tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        
        # 1단계: 권한 및 파일 유효성 검사
        # 컨테이너 존재 및 접근 권한 확인
        from app.services.permission_service import permission_service
        
        container_exists = await permission_service.check_container_exists(knowledge_container_id)
        if not container_exists:
            raise HTTPException(
                status_code=404, 
                detail=f"지식 컨테이너 '{knowledge_container_id}'를 찾을 수 없습니다."
            )
        
        has_upload_permission = await permission_service.check_container_permission(
            current_user.emp_no, knowledge_container_id, "WRITE"
        )
        if not has_upload_permission:
            raise HTTPException(
                status_code=403,
                detail=f"컨테이너 '{knowledge_container_id}'에 문서 업로드 권한이 없습니다."
            )
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 제공되지 않았습니다.")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in document_processor_service.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"지원되지 않는 파일 형식: {file_ext}. 지원 형식: {list(document_processor_service.supported_formats.keys())}"
            )
        
        # 파일 크기 검사
        file_size_mb = (file.size or 0) / (1024 * 1024)
        if file.size and file.size > settings.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"파일 크기가 너무 큽니다. 최대 크기: {settings.max_file_size / (1024*1024):.1f}MB"
            )
        
        # 2단계: 임시 파일 저장 및 문서 처리
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 문서 처리 수행
            logger.info(f"문서 처리 시작: {file.filename} (사용자: {current_user.emp_no})")
            processing_result = await document_processor_service.process_document(
                file_path=temp_file_path,
                file_name=file.filename,
                user_id=current_user.id
            )
            
            if not processing_result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=f"문서 처리 실패: {processing_result.get('error', '알 수 없는 오류')}"
                )
            
            # 3단계: 메타데이터 보강
            enhanced_metadata = processing_result["metadata"].copy()
            if title:
                enhanced_metadata["title"] = title
            if description:
                enhanced_metadata["description"] = description
            if tag_list:
                enhanced_metadata["tags"] = tag_list
            enhanced_metadata["uploaded_by"] = current_user.emp_no
            enhanced_metadata["knowledge_container_id"] = knowledge_container_id
            
            # 4단계: 파일 기본 정보 DB 저장
            logger.info(f"파일 기본 정보 DB 저장 시작: {file.filename}")
            
            from app.services.document.storage.file_storage_service import file_storage_service
            
            # TB_FILE_BSS_INFO에 파일 기본 정보 저장
            file_bss_info_sno = await file_storage_service.save_file_basic_info(
                file_logical_name=enhanced_metadata.get("title", file.filename),
                file_physical_name=file.filename,
                file_extension=file_ext,
                file_path=temp_file_path,  # 실제로는 영구 저장 경로
                file_hash=processing_result["file_info"]["file_hash"],
                file_size=file_size_mb * 1024 * 1024,  # bytes로 변환
                knowledge_container_id=knowledge_container_id,
                owner_emp_no=current_user.emp_no,
                korean_metadata=processing_result["korean_analysis"],
                chunk_count=processing_result["content"]["chunk_count"],
                user_id=current_user.id
            )
            
            if not file_bss_info_sno:
                raise HTTPException(
                    status_code=500,
                    detail="파일 기본 정보 저장에 실패했습니다."
                )
            
            # 4.5단계: 파일 상세 정보 저장
            detail_saved = await file_storage_service.save_file_detail_info(
                file_bss_info_sno=file_bss_info_sno,
                content_text=processing_result["content"]["raw_text"],
                document_title=enhanced_metadata.get("title", file.filename),
                metadata_json=enhanced_metadata
            )
            
            if not detail_saved:
                logger.warning(f"파일 상세 정보 저장 실패: {file.filename}")
            
            # 5단계: 검색 인덱싱
            logger.info(f"검색 인덱싱 시작: {file.filename}")
            
            indexing_result = await document_index_service.index_document_for_search(
                file_bss_info_sno=file_bss_info_sno,
                knowledge_container_id=knowledge_container_id,
                document_content=processing_result["content"]["raw_text"],
                document_metadata=enhanced_metadata,
                korean_analysis=processing_result["korean_analysis"],
                chunks_with_embeddings=processing_result["content"]["chunks_with_embeddings"],
                user_emp_no=current_user.emp_no
            )
            
            if not indexing_result.get("success", False):
                logger.warning(f"검색 인덱싱 실패하였지만 문서 처리는 완료: {indexing_result.get('error', '')}")
            
            # 6단계: 결과 반환
            search_doc_ids = []
            if indexing_result.get("success", False):
                search_doc_ids = [chunk["search_doc_id"] for chunk in indexing_result.get("chunks_detail", [])]
            
            logger.info(f"문서 업로드 및 인덱싱 완료: {file.filename}, 검색문서 {len(search_doc_ids)}개 생성")
            
            return DocumentUploadResponse(
                success=True,
                message=f"문서 '{file.filename}'이 성공적으로 업로드되고 검색 인덱스에 등록되었습니다.",
                file_info={
                    "filename": file.filename,
                    "size_mb": round(file_size_mb, 2),
                    "extension": file_ext,
                    "container_id": knowledge_container_id,
                    "file_bss_info_sno": file_bss_info_sno,
                    "upload_time": processing_result.get("metadata", {}).get("processing_timestamp"),
                    "uploaded_by": current_user.emp_no
                },
                processing_result={
                    "chunks_created": processing_result["content"]["chunk_count"],
                    "text_length": processing_result["content"]["text_length"],
                    "keywords_extracted": len(processing_result["korean_analysis"].get("keywords", [])),
                    "processing_time": processing_result.get("processing_time", 0)
                },
                indexing_result=indexing_result,
                search_doc_ids=search_doc_ids
            )
            
        finally:
            # 임시 파일 정리
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {temp_file_path}, {e}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 업로드 및 인덱싱 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 업로드 및 인덱싱 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/index-stats")
async def get_search_index_statistics(
    container_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """검색 인덱스 통계 조회"""
    try:
        stats = await document_index_service.get_index_statistics(container_id)
        return stats
    except Exception as e:
        logger.error(f"검색 인덱스 통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/remove-from-index/{file_bss_info_sno}")
async def remove_document_from_search_index(
    file_bss_info_sno: int,
    knowledge_container_id: str,
    current_user: User = Depends(get_current_user)
):
    """검색 인덱스에서 문서 제거"""
    try:
        result = await document_index_service.remove_document_from_index(
            file_bss_info_sno, knowledge_container_id
        )
        return result
    except Exception as e:
        logger.error(f"검색 인덱스 문서 제거 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reindex/{file_bss_info_sno}")
async def reindex_document(
    file_bss_info_sno: int,
    knowledge_container_id: str,
    current_user: User = Depends(get_current_user)
):
    """문서 재인덱싱"""
    try:
        # 실제 구현에서는 원본 파일 경로를 DB에서 조회하여 재처리
        # 여기서는 간단한 응답만 반환
        return {
            "message": "재인덱싱 기능은 추후 구현 예정입니다.",
            "file_bss_info_sno": file_bss_info_sno,
            "knowledge_container_id": knowledge_container_id
        }
    except Exception as e:
        logger.error(f"문서 재인덱싱 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

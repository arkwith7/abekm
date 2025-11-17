"""
문서 처리 API 엔드포인트
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import tempfile
import os
import asyncio
from pathlib import Path

from app.services.document_processor_service import document_processor_service
from app.core.config import settings

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Document Processing"])

# Request/Response 모델
class DocumentProcessingResponse(BaseModel):
    success: bool
    file_info: Dict[str, Any]
    content: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    korean_analysis: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None

class SupportedFormatsResponse(BaseModel):
    supported_formats: List[str]
    descriptions: Dict[str, str]

class BatchUploadResponse(BaseModel):
    success: bool
    total_files: int
    processed_files: int
    failed_files: int
    results: List[DocumentProcessingResponse]
    processing_summary: Dict[str, Any]
    processing_time: Optional[float] = None

class FileProcessingStatus(BaseModel):
    filename: str
    status: str  # "processing", "completed", "failed"
    progress: float  # 0.0 to 1.0
    result: Optional[DocumentProcessingResponse] = None
    error: Optional[str] = None

@router.get("/supported-formats", response_model=SupportedFormatsResponse)
async def get_supported_formats():
    """지원되는 문서 형식 조회"""
    formats = {
        ".pdf": "PDF 문서",
        ".docx": "Microsoft Word 문서 (최신)",
        ".doc": "Microsoft Word 문서 (레거시)",
        ".xlsx": "Microsoft Excel 스프레드시트 (최신)",
        ".xls": "Microsoft Excel 스프레드시트 (레거시)",
        ".pptx": "Microsoft PowerPoint 프레젠테이션 (최신)",
        ".ppt": "Microsoft PowerPoint 프레젠테이션 (레거시)",
        ".hwp": "아래아한글 문서",
        ".txt": "텍스트 파일",
        ".md": "Markdown 파일"
    }
    
    return SupportedFormatsResponse(
        supported_formats=list(formats.keys()),
        descriptions=formats
    )

@router.post("/upload", response_model=DocumentProcessingResponse)
async def upload_and_process_document(file: UploadFile = File(...)):
    """문서 업로드 및 처리"""
    try:
        # 파일 유효성 검사
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 제공되지 않았습니다.")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in document_processor_service.supported_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"지원되지 않는 파일 형식입니다: {file_ext}. 지원 형식: {list(document_processor_service.supported_formats.keys())}"
            )
        
        # 파일 크기 검사 및 대용량 파일 처리 안내
        file_size_mb = (file.size or 0) / (1024 * 1024)
        if file.size and file.size > settings.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"파일 크기가 너무 큽니다. 최대 크기: {settings.max_file_size / (1024*1024):.1f}MB"
            )
        
        # 대용량 파일 경고 (20MB 이상)
        if file_size_mb > 20:
            logger.warning(f"대용량 파일 감지: {file.filename} ({file_size_mb:.1f}MB)")
            logger.info("대용량 파일은 /api/documents/large-file-upload 엔드포인트 사용을 권장합니다.")
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 문서 처리
            result = await document_processor_service.process_document(
                file_path=temp_file_path,
                file_name=file.filename
            )
            
            return DocumentProcessingResponse(**result)
            
        finally:
            # 임시 파일 정리
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {e}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload and processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-file")
async def process_existing_file(file_path: str, file_name: str):
    """기존 파일 처리"""
    try:
        # 파일 경로 유효성 검사
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        # 보안: 허용된 디렉토리 내의 파일만 처리
        allowed_dirs = [settings.upload_dir]
        file_abs_path = os.path.abspath(file_path)
        
        is_allowed = any(
            file_abs_path.startswith(os.path.abspath(allowed_dir))
            for allowed_dir in allowed_dirs
        )
        
        if not is_allowed:
            raise HTTPException(status_code=403, detail="허용되지 않은 파일 경로입니다.")
        
        # 문서 처리
        result = await document_processor_service.process_document(
            file_path=file_path,
            file_name=file_name
        )
        
        return DocumentProcessingResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract-text")
async def extract_text_only(file: UploadFile = File(...)):
    """텍스트 추출만 수행 (한국어 분석 제외)"""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 제공되지 않았습니다.")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in document_processor_service.supported_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"지원되지 않는 파일 형식입니다: {file_ext}"
            )
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 문서에서 텍스트만 추출
            file_ext = Path(file.filename).suffix.lower()
            processor = document_processor_service.supported_formats[file_ext]
            extraction_result = await processor(temp_file_path)
            
            if extraction_result["success"]:
                return {
                    "success": True,
                    "file_name": file.filename,
                    "text": extraction_result["text"],
                    "text_length": len(extraction_result["text"]),
                    "metadata": extraction_result.get("metadata", {})
                }
            else:
                raise HTTPException(status_code=400, detail=extraction_result["error"])
                
        finally:
            # 임시 파일 정리
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {e}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def document_processor_health():
    """문서 처리 서비스 상태 확인"""
    try:
        components = {
            "docx": "ok" if hasattr(document_processor_service, '_process_docx') else "not_available",
            "xlsx": "ok" if hasattr(document_processor_service, '_process_xlsx') else "not_available", 
            "pptx": "ok" if hasattr(document_processor_service, '_process_pptx') else "not_available",
            "pdf": "ok" if hasattr(document_processor_service, '_process_pdf') else "not_available",
            "hwp": "ok" if hasattr(document_processor_service, '_process_hwp') else "not_available",
            "txt": "ok" if hasattr(document_processor_service, '_process_txt') else "not_available"
        }
        
        return {
            "status": "healthy",
            "service": "document_processor",
            "supported_formats": list(document_processor_service.supported_formats.keys()),
            "components": components
        }
        
    except Exception as e:
        logger.error(f"Document processor health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# 멀티 파일 업로드를 위한 전역 상태 관리 (실제 환경에서는 Redis나 DB 사용 권장)
batch_processing_status: Dict[str, Dict[str, FileProcessingStatus]] = {}


async def process_single_file_async(file: UploadFile, batch_id: str) -> DocumentProcessingResponse:
    """단일 파일 비동기 처리"""
    filename = file.filename or "unknown"
    
    # 상태 업데이트
    if batch_id in batch_processing_status:
        batch_processing_status[batch_id][filename].status = "processing"
        batch_processing_status[batch_id][filename].progress = 0.1
    
    try:
        # 파일 유효성 검사
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 제공되지 않았습니다.")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in document_processor_service.supported_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"지원되지 않는 파일 형식입니다: {file_ext}"
            )
        
        # 파일 크기 검사
        if file.size and file.size > settings.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"파일 크기가 너무 큽니다. 최대 크기: {settings.max_file_size / (1024*1024):.1f}MB"
            )
        
        # 상태 업데이트
        if batch_id in batch_processing_status:
            batch_processing_status[batch_id][filename].progress = 0.3
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 상태 업데이트
            if batch_id in batch_processing_status:
                batch_processing_status[batch_id][filename].progress = 0.6
            
            # 문서 처리
            result = await document_processor_service.process_document(
                temp_file_path,
                file_name=file.filename
            )
            
            # 상태 업데이트
            if batch_id in batch_processing_status:
                batch_processing_status[batch_id][filename].progress = 1.0
                batch_processing_status[batch_id][filename].status = "completed"
            
            response = DocumentProcessingResponse(
                success=True,
                file_info={
                    "filename": file.filename,
                    "size": file.size,
                    "content_type": file.content_type,
                    "extension": file_ext
                },
                content=result.get("content"),
                metadata=result.get("metadata"),
                korean_analysis=result.get("korean_analysis"),
                processing_time=result.get("processing_time")
            )
            
            # 최종 상태 업데이트
            if batch_id in batch_processing_status:
                batch_processing_status[batch_id][filename].result = response
            
            return response
            
        finally:
            # 임시 파일 정리
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        # 오류 상태 업데이트
        if batch_id in batch_processing_status:
            batch_processing_status[batch_id][filename].status = "failed"
            batch_processing_status[batch_id][filename].error = str(e)
        
        logger.error(f"Error processing file {filename}: {e}")
        return DocumentProcessingResponse(
            success=False,
            file_info={
                "filename": filename,
                "size": file.size if file.size else 0,
                "content_type": file.content_type,
                "extension": Path(filename).suffix.lower() if filename else ""
            },
            error=str(e)
        )


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    여러 문서 동시 업로드 및 처리
    
    - 최대 10개 파일까지 동시 업로드 가능
    - 각 파일은 병렬로 처리됨
    - 실시간 진행 상황 추적 가능
    """
    import time
    import uuid
    
    start_time = time.time()
    
    # 파일 개수 제한
    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="한 번에 최대 10개 파일까지만 업로드할 수 있습니다."
        )
    
    # 빈 파일 제거
    valid_files = [f for f in files if f.filename and f.filename.strip()]
    if not valid_files:
        raise HTTPException(status_code=400, detail="유효한 파일이 없습니다.")
    
    # 배치 ID 생성
    batch_id = str(uuid.uuid4())
    
    # 배치 상태 초기화
    batch_processing_status[batch_id] = {}
    for file in valid_files:
        batch_processing_status[batch_id][file.filename] = FileProcessingStatus(
            filename=file.filename,
            status="pending",
            progress=0.0
        )
    
    try:
        # 병렬 처리를 위한 세마포어 (동시 처리 수 제한)
        semaphore = asyncio.Semaphore(8)  # 최대 8개 파일 동시 처리 (개선됨)
        
        async def process_with_semaphore(file: UploadFile) -> DocumentProcessingResponse:
            async with semaphore:
                return await process_single_file_async(file, batch_id)
        
        # 모든 파일 병렬 처리
        logger.info(f"Starting batch processing for {len(valid_files)} files (batch_id: {batch_id})")
        
        results = await asyncio.gather(
            *[process_with_semaphore(file) for file in valid_files],
            return_exceptions=True
        )
        
        # 결과 분석
        successful_results = []
        failed_results = []
        
        for result in results:
            if isinstance(result, Exception):
                failed_results.append(DocumentProcessingResponse(
                    success=False,
                    file_info={"filename": "unknown", "size": 0, "content_type": "", "extension": ""},
                    error=str(result)
                ))
            elif result.success:
                successful_results.append(result)
            else:
                failed_results.append(result)
        
        processing_time = time.time() - start_time
        
        # 처리 요약
        processing_summary = {
            "batch_id": batch_id,
            "start_time": start_time,
            "end_time": time.time(),
            "total_processing_time": processing_time,
            "average_time_per_file": processing_time / len(valid_files) if valid_files else 0,
            "success_rate": len(successful_results) / len(valid_files) * 100,
            "file_types": list(set(Path(f.filename).suffix.lower() for f in valid_files if f.filename)),
            "total_size_mb": sum(f.size or 0 for f in valid_files) / (1024 * 1024)
        }
        
        logger.info(f"Batch processing completed: {len(successful_results)}/{len(valid_files)} files processed successfully")
        
        return BatchUploadResponse(
            success=len(failed_results) == 0,
            total_files=len(valid_files),
            processed_files=len(successful_results),
            failed_files=len(failed_results),
            results=successful_results + failed_results,
            processing_summary=processing_summary,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"배치 업로드 중 오류가 발생했습니다: {str(e)}")
    
    finally:
        # 메모리 정리 (옵션: 나중에 상태 조회를 위해 일정 시간 보관할 수도 있음)
        # del batch_processing_status[batch_id]
        pass


@router.get("/batch-status/{batch_id}")
async def get_batch_processing_status(batch_id: str):
    """배치 처리 상태 조회"""
    if batch_id not in batch_processing_status:
        raise HTTPException(status_code=404, detail="배치 ID를 찾을 수 없습니다.")
    
    status_info = batch_processing_status[batch_id]
    
    # 전체 진행률 계산
    total_progress = sum(file_status.progress for file_status in status_info.values())
    average_progress = total_progress / len(status_info) if status_info else 0
    
    # 상태별 카운트
    status_counts = {
        "pending": sum(1 for s in status_info.values() if s.status == "pending"),
        "processing": sum(1 for s in status_info.values() if s.status == "processing"),
        "completed": sum(1 for s in status_info.values() if s.status == "completed"),
        "failed": sum(1 for s in status_info.values() if s.status == "failed")
    }
    
    return {
        "batch_id": batch_id,
        "overall_progress": average_progress,
        "status_counts": status_counts,
        "files": {filename: {
            "status": file_status.status,
            "progress": file_status.progress,
            "error": file_status.error
        } for filename, file_status in status_info.items()},
        "is_completed": all(s.status in ["completed", "failed"] for s in status_info.values())
    }

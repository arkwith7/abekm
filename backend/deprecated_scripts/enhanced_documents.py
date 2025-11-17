"""
개선된 문서 업로드 API - 조직 기반 컨테이너 지원
/backend/app/api/v1/enhanced_documents.py
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.core.database import get_db
from app.services.auth_service import get_current_user
from app.models.file_models import User
from app.schemas.enhanced_document import (
    ContainerListResponse,
    ContainerInfo,
    DocumentUploadRequest,
    DocumentUploadResponse,
    UploadProgress
)

# 새로운 서비스들
from app.services.permission_service import PermissionService
from app.services.document_processor_service import DocumentProcessorService

# 서비스 인스턴스 생성
permission_service = PermissionService()
document_processor = DocumentProcessorService()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/enhanced-documents", tags=["Enhanced Documents"])

@router.get("/containers", response_model=ContainerListResponse)
async def get_user_containers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    사용자가 접근 가능한 조직 컨테이너 목록 조회
    - 사용자 소속 조직 기반 권한 계산
    - 계층적 트리 구조로 반환
    - 각 컨테이너별 권한 정보 포함
    """
    try:
        # 1. 사용자 조직 정보 확인
        user_org_info = await container_permission_service.get_user_organization(
            user_id=current_user.id,
            session=session
        )
        
        if not user_org_info:
            raise HTTPException(
                status_code=400,
                detail="사용자 조직 정보를 찾을 수 없습니다."
            )
        
        # 2. 접근 가능한 컨테이너 목록 조회
        containers = await container_permission_service.get_accessible_containers(
            user_id=current_user.id,
            user_org_code=user_org_info["sap_org_code"],
            session=session
        )
        
        # 3. 컨테이너별 권한 계산
        container_list = []
        for container in containers:
            permission_info = await container_permission_service.calculate_container_permission(
                user_id=current_user.id,
                container_id=container.container_id,
                user_org_code=user_org_info["sap_org_code"],
                session=session
            )
            
            container_info = ContainerInfo(
                container_id=container.container_id,
                container_name=container.container_name,
                container_type=container.container_type,
                hierarchy_level=container.hierarchy_level,
                hierarchy_path=container.hierarchy_path,
                access_level=container.access_level,
                parent_container_id=container.parent_container_id,
                display_order=container.display_order,
                can_upload=permission_info["can_upload"],
                user_permission=permission_info["permission_level"]
            )
            container_list.append(container_info)
        
        return ContainerListResponse(
            success=True,
            containers=container_list,
            user_organization=user_org_info
        )
        
    except Exception as e:
        logger.error(f"컨테이너 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document_to_container(
    container_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    조직 컨테이너에 문서 업로드
    - 컨테이너 업로드 권한 검증
    - 파일 저장 및 메타데이터 생성
    - 벡터 임베딩 및 컨테이너 할당
    - 실시간 진행 상황 업데이트
    """
    try:
        # 1. 컨테이너 존재 및 권한 확인
        container_info = await container_permission_service.validate_upload_permission(
            user_id=current_user.id,
            container_id=container_id,
            session=session
        )
        
        if not container_info["can_upload"]:
            raise HTTPException(
                status_code=403,
                detail=f"컨테이너 '{container_info['container_name']}'에 업로드 권한이 없습니다."
            )
        
        # 2. 파일 검증
        file_validation = await enhanced_document_processor.validate_upload_file(
            file=file,
            container_limits=container_info["upload_limits"]
        )
        
        if not file_validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=file_validation["error"]
            )
        
        # 3. 문서 처리 파이프라인 실행 (컨테이너 정보 포함)
        processing_result = await enhanced_document_processor.process_document_with_container(
            file=file,
            container_id=container_id,
            container_info=container_info,
            user_id=current_user.id,
            session=session
        )
        
        if not processing_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"문서 처리 실패: {processing_result['error']}"
            )
        
        # 4. 컨테이너 할당 및 권한 설정
        assignment_result = await container_assignment_service.assign_document_to_container(
            document_id=processing_result["document_id"],
            container_id=container_id,
            user_id=current_user.id,
            session=session
        )
        
        if not assignment_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"컨테이너 할당 실패: {assignment_result['error']}"
            )
        
        # 5. 성공 응답 구성
        return DocumentUploadResponse(
            success=True,
            message="문서가 성공적으로 업로드되었습니다.",
            document_id=processing_result["document_id"],
            container_info={
                "container_id": container_id,
                "container_name": container_info["container_name"],
                "hierarchy_path": container_info["hierarchy_path"]
            },
            file_info={
                "original_name": file.filename,
                "file_size": processing_result["file_info"]["file_size"],
                "file_type": processing_result["file_info"]["file_extension"],
                "file_hash": processing_result["file_info"]["file_hash"]
            },
            processing_stats={
                "text_length": processing_result["content"]["text_length"],
                "chunk_count": processing_result["content"]["chunk_count"],
                "processing_time": processing_result["processing_time"],
                "quality_score": processing_result["quality_metrics"]["overall_score"],
                "korean_ratio": processing_result["quality_metrics"]["korean_ratio"]
            },
            vector_info={
                "content_vectors": processing_result["vectors"]["content_count"],
                "metadata_vector": processing_result["vectors"]["metadata_created"],
                "preprocessing_vector": processing_result["vectors"]["preprocessing_created"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload-progress/{upload_id}")
async def get_upload_progress(
    upload_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    실시간 업로드 진행 상황 조회 (WebSocket 대신 폴링 방식)
    """
    try:
        progress = await enhanced_document_processor.get_upload_progress(
            upload_id=upload_id,
            user_id=current_user.id
        )
        
        return progress
        
    except Exception as e:
        logger.error(f"업로드 진행 상황 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/validate")
async def validate_container_access(
    container_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    특정 컨테이너에 대한 접근 권한 검증
    """
    try:
        validation_result = await container_permission_service.validate_upload_permission(
            user_id=current_user.id,
            container_id=container_id,
            session=session
        )
        
        return JSONResponse(content={
            "valid": validation_result["can_upload"],
            "container_name": validation_result["container_name"],
            "permission_level": validation_result["permission_level"],
            "upload_limits": validation_result["upload_limits"],
            "access_level": validation_result["access_level"]
        })
        
    except Exception as e:
        logger.error(f"컨테이너 권한 검증 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_id}/stats")
async def get_container_statistics(
    container_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    컨테이너 통계 정보 조회 (문서 수, 용량 등)
    """
    try:
        # 권한 확인
        has_access = await container_permission_service.check_container_access(
            user_id=current_user.id,
            container_id=container_id,
            required_permission="VIEWER",
            session=session
        )
        
        if not has_access:
            raise HTTPException(status_code=403, detail="컨테이너 접근 권한이 없습니다.")
        
        # 통계 조회
        stats = await container_assignment_service.get_container_statistics(
            container_id=container_id,
            session=session
        )
        
        return JSONResponse(content=stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"컨테이너 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

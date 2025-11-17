"""
문서 접근 제어 API
Phase 2: 문서 접근 관리 기능

엔드포인트:
- POST   /api/v1/documents/{id}/access-rules     문서 접근 규칙 생성
- GET    /api/v1/documents/{id}/access-rules     문서 접근 규칙 조회
- PUT    /api/v1/documents/access-rules/{rule_id} 문서 접근 규칙 수정
- DELETE /api/v1/documents/access-rules/{rule_id} 문서 접근 규칙 삭제
- GET    /api/v1/documents/{id}/check-access      사용자 접근 권한 확인
- GET    /api/v1/documents/accessible             접근 가능한 문서 목록
"""
from typing import List, Optional, Dict, Any, cast
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.document.document_access_service import DocumentAccessService
from app.models.document.document_access import AccessLevel, RuleType, PermissionLevel
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["📄 Document Access Control"])


# ========== Pydantic 모델 ==========

class AccessRuleCreateRequest(BaseModel):
    """접근 규칙 생성 요청"""
    access_level: AccessLevel = Field(..., description="접근 레벨 (public/restricted/private)")
    rule_type: Optional[RuleType] = Field(None, description="규칙 타입 (user/department)")
    target_id: Optional[str] = Field(None, description="대상 ID (사번 또는 부서명)")
    permission_level: Optional[PermissionLevel] = Field(None, description="권한 레벨 (view/download/edit)")
    is_inherited: str = Field('N', description="컨테이너 권한 상속 여부")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_level": "restricted",
                "rule_type": "department",
                "target_id": "HR부서",
                "permission_level": "download",
                "is_inherited": "N",
                "metadata": {
                    "description": "HR 부서 전용 문서"
                }
            }
        }


class AccessRuleUpdateRequest(BaseModel):
    """접근 규칙 수정 요청"""
    access_level: Optional[AccessLevel] = None
    rule_type: Optional[RuleType] = None
    target_id: Optional[str] = None
    permission_level: Optional[PermissionLevel] = None
    is_inherited: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AccessRuleResponse(BaseModel):
    """접근 규칙 응답"""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    rule_id: int
    file_bss_info_sno: int
    access_level: AccessLevel
    rule_type: Optional[RuleType]
    target_id: Optional[str]
    permission_level: Optional[PermissionLevel]
    is_inherited: str
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        alias='rule_metadata',
        serialization_alias='metadata'
    )
    created_by: str
    created_date: datetime
    last_modified_by: Optional[str]
    last_modified_date: Optional[datetime]


class AccessCheckResponse(BaseModel):
    """접근 권한 확인 응답"""
    file_bss_info_sno: int
    user_emp_no: str
    has_access: bool
    access_level: Optional[AccessLevel]
    permission_level: Optional[PermissionLevel]
    message: str


class AccessibleDocumentResponse(BaseModel):
    """접근 가능한 문서 응답"""
    file_bss_info_sno: int
    file_lgc_nm: str
    file_psl_nm: str
    file_extsn: str
    knowledge_container_id: Optional[str]
    created_date: datetime
    access_level: AccessLevel
    permission_level: PermissionLevel
    is_inherited: str


# ========== API 엔드포인트 ==========

@router.post(
    "/documents/{file_bss_info_sno}/access-rules",
    response_model=AccessRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="문서 접근 규칙 생성",
    description="""
    문서에 대한 접근 규칙을 생성합니다.
    
    **접근 레벨:**
    - `public`: 모든 사용자 접근 가능
    - `restricted`: 특정 사용자/부서만 접근 가능
    - `private`: 관리자만 접근 가능
    
    **규칙 타입 (RESTRICTED일 때 필수):**
    - `user`: 개별 사용자 (target_id = 사번)
    - `department`: 부서 단위 (target_id = 부서명)
    
    **권한 레벨 (RESTRICTED일 때 필수):**
    - `view`: 조회만 가능
    - `download`: 조회 + 다운로드 가능
    - `edit`: 조회 + 다운로드 + 편집 가능
    """
)
async def create_document_access_rule(
    file_bss_info_sno: int,
    request: AccessRuleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """문서 접근 규칙 생성"""
    try:
        service = DocumentAccessService(db)
        created_by = str(current_user.emp_no)
        if not created_by:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user context")
        
        access_rule = await service.create_access_rule(
            file_bss_info_sno=file_bss_info_sno,
            access_level=request.access_level,
            created_by=created_by,
            rule_type=request.rule_type,
            target_id=request.target_id,
            permission_level=request.permission_level,
            is_inherited=request.is_inherited,
            metadata=request.metadata
        )
        
        return AccessRuleResponse.from_orm(access_rule)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create access rule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create access rule: {str(e)}"
        )


@router.get(
    "/documents/{file_bss_info_sno}/access-rules",
    response_model=List[AccessRuleResponse],
    summary="문서 접근 규칙 조회",
    description="특정 문서의 모든 접근 규칙을 조회합니다."
)
async def get_document_access_rules(
    file_bss_info_sno: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """문서 접근 규칙 조회"""
    try:
        service = DocumentAccessService(db)
        
        rules = await service.get_document_access_rules(file_bss_info_sno)
        
        return [AccessRuleResponse.from_orm(rule) for rule in rules]
        
    except Exception as e:
        logger.error(f"Failed to get access rules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get access rules: {str(e)}"
        )


@router.put(
    "/documents/access-rules/{rule_id}",
    response_model=AccessRuleResponse,
    summary="문서 접근 규칙 수정",
    description="기존 접근 규칙을 수정합니다."
)
async def update_document_access_rule(
    rule_id: int,
    request: AccessRuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """문서 접근 규칙 수정"""
    try:
        service = DocumentAccessService(db)
        modified_by = str(current_user.emp_no)
        if not modified_by:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user context")
        
        updated_rule = await service.update_access_rule(
            rule_id=rule_id,
            access_level=request.access_level,
            rule_type=request.rule_type,
            target_id=request.target_id,
            permission_level=request.permission_level,
            is_inherited=request.is_inherited,
            metadata=request.metadata,
            modified_by=modified_by
        )
        
        if not updated_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Access rule {rule_id} not found"
            )
        
        return AccessRuleResponse.from_orm(updated_rule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update access rule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update access rule: {str(e)}"
        )


@router.delete(
    "/documents/access-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="문서 접근 규칙 삭제",
    description="접근 규칙을 삭제합니다."
)
async def delete_document_access_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """문서 접근 규칙 삭제"""
    try:
        service = DocumentAccessService(db)
        
        deleted = await service.delete_access_rule(rule_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Access rule {rule_id} not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete access rule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete access rule: {str(e)}"
        )


@router.get(
    "/documents/{file_bss_info_sno}/check-access",
    response_model=AccessCheckResponse,
    summary="문서 접근 권한 확인",
    description="""
    사용자가 특정 문서에 접근 가능한지 확인합니다.
    
    **required_permission 파라미터:**
    - `view`: 조회 권한 확인
    - `download`: 다운로드 권한 확인
    - `edit`: 편집 권한 확인
    """
)
async def check_document_access(
    file_bss_info_sno: int,
    required_permission: PermissionLevel = Query(PermissionLevel.VIEW, description="확인할 권한 레벨"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """문서 접근 권한 확인"""
    try:
        service = DocumentAccessService(db)
        user_emp_no = str(current_user.emp_no)
        if not user_emp_no:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user context")
        
        has_access = await service.check_user_document_access(
            file_bss_info_sno=file_bss_info_sno,
            user_emp_no=user_emp_no,
            required_permission=required_permission
        )
        
        # 접근 가능한 경우 상세 정보 조회
        access_level = None
        permission_level = None
        
        if has_access:
            rules = await service.get_document_access_rules(file_bss_info_sno)
            if rules:
                # 첫 번째 규칙의 정보 반환 (여러 규칙이 있을 수 있음)
                access_level = cast(Optional[AccessLevel], rules[0].access_level)
                permission_level = cast(Optional[PermissionLevel], rules[0].permission_level)
        
        message = "Access granted" if has_access else "Access denied"
        
        # 접근 로그 기록
        await service.log_document_access(
            file_bss_info_sno=file_bss_info_sno,
            user_emp_no=user_emp_no,
            access_type=required_permission.value,
            access_granted=has_access,
            denial_reason=None if has_access else "Insufficient permissions"
        )
        
        return AccessCheckResponse(
            file_bss_info_sno=file_bss_info_sno,
            user_emp_no=user_emp_no,
            has_access=has_access,
            access_level=access_level,
            permission_level=permission_level,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Failed to check document access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check document access: {str(e)}"
        )


@router.get(
    "/documents/accessible",
    response_model=List[AccessibleDocumentResponse],
    summary="접근 가능한 문서 목록",
    description="""
    현재 사용자가 접근 가능한 문서 목록을 조회합니다.
    
    **필터링 옵션:**
    - `access_level`: 접근 레벨 필터 (public/restricted/private)
    - `container_id`: 컨테이너 ID 필터
    - `limit`: 결과 개수 제한 (기본: 100)
    - `offset`: 페이지네이션 오프셋 (기본: 0)
    """
)
async def get_accessible_documents(
    access_level: Optional[AccessLevel] = Query(None, description="접근 레벨 필터"),
    container_id: Optional[str] = Query(None, description="컨테이너 ID 필터"),
    limit: int = Query(100, ge=1, le=1000, description="결과 개수 제한"),
    offset: int = Query(0, ge=0, description="페이지네이션 오프셋"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """접근 가능한 문서 목록 조회"""
    try:
        service = DocumentAccessService(db)
        user_emp_no = str(current_user.emp_no)
        if not user_emp_no:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user context")
        
        documents = await service.get_accessible_documents(
            user_emp_no=user_emp_no,
            access_level_filter=access_level,
            container_id=container_id,
            limit=limit,
            offset=offset
        )
        
        return [
            AccessibleDocumentResponse(
                file_bss_info_sno=doc['file_bss_info_sno'],
                file_lgc_nm=doc['file_lgc_nm'],
                file_psl_nm=doc['file_psl_nm'],
                file_extsn=doc['file_extsn'],
                knowledge_container_id=doc['knowledge_container_id'],
                created_date=doc['created_date'],
                access_level=doc['access_level'],
                permission_level=doc['permission_level'],
                is_inherited=doc['is_inherited']
            )
            for doc in documents
        ]
        
    except Exception as e:
        logger.error(f"Failed to get accessible documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get accessible documents: {str(e)}"
        )


@router.post(
    "/documents/{file_bss_info_sno}/inherit-container-access",
    response_model=AccessRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="컨테이너 권한 상속",
    description="문서가 속한 컨테이너의 권한을 상속받아 접근 규칙을 자동 설정합니다."
)
async def inherit_container_access(
    file_bss_info_sno: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """컨테이너 권한 상속하여 접근 규칙 설정"""
    try:
        service = DocumentAccessService(db)
        created_by = str(current_user.emp_no)
        if not created_by:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user context")
        
        access_rule = await service.set_document_access_from_container(
            file_bss_info_sno=file_bss_info_sno,
            created_by=created_by
        )
        
        if not access_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {file_bss_info_sno} not found"
            )
        
        return AccessRuleResponse.from_orm(access_rule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to inherit container access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inherit container access: {str(e)}"
        )

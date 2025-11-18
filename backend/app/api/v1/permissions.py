"""
WKMS 권한 관리 통합 API
======================

🎯 목적:
- 권한 확인, 부여, 취소 등 권한 관리 기능
- 권한 요청, 승인, 거부 등 워크플로우 관리
- 통합된 권한 관리 시스템 제공

📋 주요 기능:
1. 🔍 권한 확인 및 조회
2. ⚡ 권한 부여 및 취소
3. 📝 권한 요청 생성 및 관리
4. ✅ 권한 요청 승인/거부
5. 📊 권한 통계 및 모니터링

🔗 통합된 기능:
- permissions.py: 권한 관리 핵심 기능
- permission_requests.py: 권한 요청 워크플로우
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.auth.permission_service import PermissionService
from app.services.auth.permission_request_service import PermissionRequestService
from app.services.auth.container_service import ContainerService
from app.core.dependencies import get_current_user
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# 통합된 라우터 설정
router = APIRouter(tags=["🔐 Permission Management"])
permission_requests_router = APIRouter(tags=["📋 Permission Requests"])
security = HTTPBearer()

# =============================================================================
# 📋 Pydantic 모델들 (통합)
# =============================================================================

class PermissionLevelResponse(BaseModel):
    user_emp_no: str
    container_id: str
    permission_level: Optional[str]
    has_permission: bool

class AccessibleContainerResponse(BaseModel):
    container_id: str
    container_name: str
    permission_level: str
    permission_source: str
    container_type: str
    access_level: str

class GrantPermissionRequest(BaseModel):
    user_emp_no: str = Field(..., description="권한을 부여받을 사용자 사번")
    container_id: str = Field(..., description="대상 컨테이너 ID")
    permission_level: str = Field(..., description="권한 레벨 (ADMIN/MANAGER/EDITOR/VIEWER)")
    valid_until: Optional[datetime] = Field(None, description="권한 유효 기간")

# 권한 요청 관련 모델들
class CreatePermissionRequestModel(BaseModel):
    container_id: str = Field(..., description="요청 대상 컨테이너 ID")
    requested_permission_level: str = Field(..., description="요청 권한 레벨 (ADMIN/MANAGER/EDITOR/VIEWER)")
    request_reason: str = Field(..., description="요청 사유")
    business_justification: Optional[str] = Field(None, description="업무 타당성")
    expected_usage_period: Optional[str] = Field(None, description="예상 사용 기간")
    priority_level: str = Field("normal", description="우선순위 (urgent/high/normal/low)")

class ApprovalActionModel(BaseModel):
    action: str = Field(..., description="승인 액션 (approve/reject)")
    reason: Optional[str] = Field(None, description="승인/거부 사유")

class RequestStatusUpdateModel(BaseModel):
    status: str = Field(..., description="요청 상태 (pending/approved/rejected/cancelled)")
    reason: Optional[str] = Field(None, description="상태 변경 사유")

# =============================================================================
# 🔍 권한 확인 및 조회 API
# =============================================================================

@router.get("/check/{user_emp_no}/{container_id}")
async def check_user_permission(
    user_emp_no: str,
    container_id: str,
    session: AsyncSession = Depends(get_db)
):
    """특정 사용자의 컨테이너 권한 확인"""
    try:
        permission_service = PermissionService(session)
        permission_level = await permission_service.get_user_permission_level(
            user_emp_no=user_emp_no,
            container_id=container_id
        )
        
        return PermissionLevelResponse(
            user_emp_no=user_emp_no,
            container_id=container_id,
            permission_level=permission_level,
            has_permission=permission_level is not None
        )
    except Exception as e:
        logger.error(f"권한 확인 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accessible-containers/{user_emp_no}")
async def get_accessible_containers(
    user_emp_no: str,
    session: AsyncSession = Depends(get_db)
):
    """사용자가 접근 가능한 컨테이너 목록 조회"""
    try:
        logger.info(f"🔍 접근 가능한 컨테이너 조회 요청 - 사용자: '{user_emp_no}' (타입: {type(user_emp_no)})")
        
        # URL 디코딩된 사용자 정보 로깅
        import urllib.parse
        decoded_user_emp_no = urllib.parse.unquote(user_emp_no)
        logger.info(f"🔍 URL 디코딩된 사용자: '{decoded_user_emp_no}'")
        
        # sample-shop.com이 포함된 경우 경고
        if 'sample-shop.com' in user_emp_no or 'sample-shop.com' in decoded_user_emp_no:
            logger.warning(f"⚠️  잘못된 사용자 정보 감지: '{user_emp_no}' - 이는 웅진 WKMS와 관련없는 정보입니다!")
            raise HTTPException(status_code=400, detail="유효하지 않은 사용자 정보입니다.")
        
        permission_service = PermissionService(session)
        containers = await permission_service.get_accessible_containers(decoded_user_emp_no)
        
        logger.info(f"✅ 사용자 '{decoded_user_emp_no}'의 접근 가능한 컨테이너 {len(containers)}개 조회 완료")
        
        return {
            "user_emp_no": decoded_user_emp_no,
            "containers": containers,
            "total_count": len(containers)
        }
    except Exception as e:
        logger.error(f"❌ 접근 가능한 컨테이너 조회 실패 (사용자: '{user_emp_no}'): {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# ⚡ 권한 부여 및 취소 API
# =============================================================================

@router.post("/grant")
async def grant_permission(
    request: GrantPermissionRequest,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """권한 부여"""
    try:
        permission_service = PermissionService(session)
        
        # 권한 부여 권한 확인 (관리자만 가능)
        if not await permission_service.check_admin_permission(current_user.emp_no):
            raise HTTPException(status_code=403, detail="권한 부여 권한이 없습니다.")
        
        success = await permission_service.grant_permission(
            user_emp_no=request.user_emp_no,
            container_id=request.container_id,
            permission_level=request.permission_level,
            granted_by=current_user.emp_no,
            valid_until=request.valid_until
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="권한 부여에 실패했습니다.")
        
        logger.info(f"권한 부여 완료: {request.user_emp_no} -> {request.container_id} ({request.permission_level})")
        
        return {
            "message": "권한이 성공적으로 부여되었습니다.",
            "granted_to": request.user_emp_no,
            "container_id": request.container_id,
            "permission_level": request.permission_level
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 부여 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/revoke/{user_emp_no}/{container_id}")
async def revoke_permission(
    user_emp_no: str,
    container_id: str,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """권한 취소"""
    try:
        permission_service = PermissionService(session)
        
        # 권한 취소 권한 확인 (관리자만 가능)
        if not await permission_service.check_admin_permission(current_user.emp_no):
            raise HTTPException(status_code=403, detail="권한 취소 권한이 없습니다.")
        
        result = await permission_service.revoke_permission(
            user_emp_no=user_emp_no,
            container_id=container_id,
            revoked_by=current_user.emp_no
        )
        
        logger.info(f"권한 취소 완료: {user_emp_no} -> {container_id}")
        
        return {
            "message": "권한이 성공적으로 취소되었습니다.",
            "revoked_from": user_emp_no,
            "container_id": container_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 취소 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-user-permissions")
async def get_all_user_permissions(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    container_id: Optional[str] = Query(None, description="특정 컨테이너 필터링"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """전체 사용자 권한 목록 조회 (관리자용)
    
    - 시스템 관리자: 모든 권한 조회
    - 지식관리자: 403 Forbidden (managed-scope-permissions 사용)
    """
    try:
        permission_service = PermissionService(session)
        
        # 시스템 관리자만 허용
        if not await permission_service.is_system_admin(current_user.emp_no):
            raise HTTPException(
                status_code=403, 
                detail="시스템 관리자만 전체 권한을 조회할 수 있습니다. 지식관리자는 /permissions/managed-scope-permissions를 사용하세요."
            )
        
        # 전체 권한 목록 조회
        permissions = await permission_service.list_all_permissions(
            container_id=container_id,
            skip=skip,
            limit=limit,
            manager_emp_no=None  # 시스템 관리자는 필터링 없음
        )
        
        return {
            "success": True,
            "permissions": permissions,
            "total_count": len(permissions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/managed-scope-permissions")
async def get_managed_scope_permissions(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    container_id: Optional[str] = Query(None, description="특정 컨테이너 필터링"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """관리 범위 내 권한 목록 조회 (지식관리자용)
    
    - 시스템 관리자: 모든 권한 조회
    - 지식관리자: 관리하는 컨테이너 범위 내 권한만 조회
    """
    try:
        permission_service = PermissionService(session)
        
        # 시스템 관리자 또는 지식관리자 권한 확인
        is_system_admin = await permission_service.is_system_admin(current_user.emp_no)
        managed_containers = await permission_service.get_managed_container_ids(current_user.emp_no)
        
        if not is_system_admin and not managed_containers:
            raise HTTPException(
                status_code=403, 
                detail="권한 조회 권한이 없습니다. 지식관리자 역할이 필요합니다."
            )
        
        # 관리 범위 내 권한 목록 조회
        permissions = await permission_service.list_all_permissions(
            container_id=container_id,
            skip=skip,
            limit=limit,
            manager_emp_no=current_user.emp_no  # 지식관리자 범위 필터링
        )
        
        return {
            "success": True,
            "permissions": permissions,
            "total_count": len(permissions),
            "is_system_admin": is_system_admin,
            "managed_container_count": 0 if is_system_admin else len(managed_containers)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관리 범위 권한 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# 📝 권한 요청 생성 및 관리 API
# =============================================================================

@permission_requests_router.post("/create")
async def create_permission_request(
    request: CreatePermissionRequestModel,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """권한 요청 생성"""
    try:
        request_service = PermissionRequestService(session)
        
        # 중복 요청 확인
        existing_request = await request_service.check_existing_request(
            user_emp_no=current_user.emp_no,
            container_id=request.container_id
        )
        
        if existing_request:
            raise HTTPException(
                status_code=400, 
                detail="해당 컨테이너에 대한 처리 중인 요청이 이미 존재합니다."
            )
        
        result = await request_service.create_permission_request(
            user_emp_no=current_user.emp_no,
            container_id=request.container_id,
            requested_permission_level=request.requested_permission_level,
            request_reason=request.request_reason,
            business_justification=request.business_justification,
            expected_usage_period=request.expected_usage_period,
            priority_level=request.priority_level
        )
        
        logger.info(f"권한 요청 생성: {current_user.emp_no} -> {request.container_id}")
        
        return {
            "message": "권한 요청이 성공적으로 생성되었습니다.",
            "request_id": result.get("request_id"),
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 요청 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@permission_requests_router.get("/my-requests")
async def get_my_permission_requests(
    status: Optional[str] = Query(None, description="요청 상태 필터"),
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """내 권한 요청 목록 조회"""
    try:
        request_service = PermissionRequestService(session)
        requests = await request_service.get_user_requests(
            user_emp_no=current_user.emp_no,
            status_filter=status
        )
        
        return {
            "requests": requests,
            "total_count": len(requests),
            "user_emp_no": current_user.emp_no
        }
        
    except Exception as e:
        logger.error(f"권한 요청 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@permission_requests_router.get("/pending")
async def get_pending_requests(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """대기 중인 권한 요청 목록 (관리자용)"""
    try:
        permission_service = PermissionService(session)
        
        # 관리자 권한 확인
        if not await permission_service.check_admin_permission(current_user.emp_no):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        
        request_service = PermissionRequestService(session)
        requests = await request_service.get_pending_requests()
        
        return {
            "pending_requests": requests,
            "total_count": len(requests)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"대기 중인 요청 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# ✅ 권한 요청 승인/거부 API
# =============================================================================

@permission_requests_router.post("/{request_id}/approve")
async def approve_permission_request(
    request_id: str,
    approval: ApprovalActionModel,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """권한 요청 승인/거부"""
    try:
        permission_service = PermissionService(session)
        
        # 관리자 권한 확인
        if not await permission_service.check_admin_permission(current_user.emp_no):
            raise HTTPException(status_code=403, detail="권한 요청 처리 권한이 없습니다.")
        
        request_service = PermissionRequestService(session)
        
        if approval.action == "approve":
            result = await request_service.approve_request(
                request_id=request_id,
                approved_by=current_user.emp_no,
                approval_reason=approval.reason
            )
            message = "권한 요청이 승인되었습니다."
        elif approval.action == "reject":
            result = await request_service.reject_request(
                request_id=request_id,
                rejected_by=current_user.emp_no,
                rejection_reason=approval.reason
            )
            message = "권한 요청이 거부되었습니다."
        else:
            raise HTTPException(status_code=400, detail="유효하지 않은 액션입니다.")
        
        logger.info(f"권한 요청 처리: {request_id} -> {approval.action} by {current_user.emp_no}")
        
        return {
            "message": message,
            "request_id": request_id,
            "action": approval.action,
            "processed_by": current_user.emp_no
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 요청 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# 📊 권한 통계 및 모니터링 API
# =============================================================================

@router.get("/statistics")
async def get_permission_statistics(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """권한 통계 조회"""
    try:
        permission_service = PermissionService(session)
        
        # 관리자 권한 확인
        if not await permission_service.check_admin_permission(current_user.emp_no):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        
        stats = await permission_service.get_permission_statistics()
        
        return {
            "statistics": stats,
            "generated_at": datetime.now(),
            "generated_by": current_user.emp_no
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@permission_requests_router.get("/statistics")
async def get_request_statistics(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """권한 요청 통계 조회"""
    try:
        permission_service = PermissionService(session)
        
        # 관리자 권한 확인
        if not await permission_service.check_admin_permission(current_user.emp_no):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        
        request_service = PermissionRequestService(session)
        stats = await request_service.get_request_statistics()
        
        return {
            "request_statistics": stats,
            "generated_at": datetime.now(),
            "generated_by": current_user.emp_no
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"권한 요청 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

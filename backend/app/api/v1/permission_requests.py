"""
권한 요청 API - 사용자 권한 요청 및 승인 워크플로우
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.models.auth.permission_models import TbPermissionRequests
from app.services.auth.permission_request_service import PermissionRequestService
from app.schemas.permission_request import (
    PermissionRequestCreate,
    PermissionRequestResponse,
    PermissionRequestListResponse,
    PermissionRequestCreateResponse,
    PermissionRequestActionResponse,
    PermissionRequestApprove,
    PermissionRequestReject,
    PermissionRequestStatistics,
    BatchApprovalRequest,
    BatchRejectionRequest,
    BatchActionResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["📋 Permission Requests"])


# ==================== 권한 요청 생성 및 조회 ====================

@router.post("", response_model=PermissionRequestCreateResponse)
async def create_permission_request(
    request_data: PermissionRequestCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 생성
    
    - 사용자가 특정 컨테이너에 대한 권한을 요청합니다
    - 자동 승인 규칙에 따라 즉시 승인될 수 있습니다
    """
    try:
        # 🔍 디버그 로그 추가
        logger.info(f"권한 요청 데이터 수신: container_id={request_data.container_id}, "
                   f"requested_permission_level={request_data.requested_permission_level}, "
                   f"request_reason={request_data.request_reason[:50]}...")
        
        service = PermissionRequestService(session)
        
        request_id = await service.create_request(
            requester_emp_no=str(current_user.emp_no),
            container_id=request_data.container_id,
            requested_permission=request_data.requested_permission_level,  # ✅ 서비스 파라미터명에 맞춤
            justification=request_data.request_reason,                     # ✅ 서비스 파라미터명에 맞춤
            business_need=request_data.business_justification,             # ✅ 서비스 파라미터명에 맞춤
            requested_duration=request_data.expected_usage_period,         # ✅ 서비스 파라미터명에 맞춤
            priority_level=request_data.urgency_level or 'normal'          # ✅ 서비스 파라미터명에 맞춤
        )
        
        if not request_id:
            raise ValueError("권한 요청 생성에 실패했습니다. 중복 요청이거나 유효하지 않은 컨테이너입니다.")
        
        # 생성된 요청 조회
        result = await session.execute(
            select(TbPermissionRequests).where(TbPermissionRequests.request_id == request_id)
        )
        request = result.scalar_one_or_none()
        
        if not request:
            raise ValueError("권한 요청을 찾을 수 없습니다.")
        
        # 응답 메시지 생성
        if str(request.request_status) == 'approved':
            message = "권한이 자동 승인되어 즉시 사용 가능합니다."
        else:
            message = f"권한 요청이 접수되었습니다. 컨테이너 관리자의 승인이 필요합니다. (요청 ID: {request_id})"
        
        return PermissionRequestCreateResponse(
            success=True,
            message=message,
            request_id=str(request.request_id),
            auto_approved=bool(request.auto_approved) if request.auto_approved else False
        )
        
    except ValueError as e:
        logger.error(f"권한 요청 검증 실패: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"권한 요청 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"권한 요청 생성 중 오류가 발생했습니다: {str(e)}")


@router.get("/my-requests", response_model=PermissionRequestListResponse)
async def get_my_permission_requests(
    status: Optional[str] = Query(None, description="상태 필터 (pending, approved, rejected, cancelled)"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    내 권한 요청 목록 조회
    
    - 본인이 요청한 권한 요청 목록을 조회합니다
    """
    try:
        user_name = getattr(current_user, "username", None) or getattr(current_user, "emp_no", "unknown")
        logger.info(f"🔍 [DEBUG] get_my_permission_requests called by user: {current_user.emp_no} ({user_name})")
        logger.info(f"🔍 [DEBUG] Filter - status: {status}, limit: {limit}")
        
        service = PermissionRequestService(session)
        
        result = await service.get_my_requests(
            requester_emp_no=current_user.emp_no,
            status=status,
            limit=limit
        )
        
        logger.info(f"✅ [DEBUG] Service returned: total={result.get('total', 0)}, requests count={len(result.get('requests', []))}")

        # result는 Dict[str, Any] 형태: {'total': int, 'requests': List[TbPermissionRequests], ...}
        requests_data = result.get('requests', [])
        total_count = result.get('total', 0)

        logger.info(f"✅ [DEBUG] Processing {len(requests_data)} requests")

        requests_list: List[PermissionRequestResponse] = []
        for idx, item in enumerate(requests_data, start=1):
            try:
                logger.debug("Processing request item %s: %s", idx, item)
                requests_list.append(PermissionRequestResponse(**item))
            except Exception as req_error:
                logger.error(f"권한 요청 변환 실패 (index={idx}): {req_error}")
                import traceback
                logger.error(traceback.format_exc())
                continue

        logger.info(f"✅ [DEBUG] Successfully processed {len(requests_list)} requests")

        return PermissionRequestListResponse(
            requests=requests_list,
            total_count=total_count
        )
        
    except Exception as e:
        logger.exception("내 요청 조회 실패")
        raise HTTPException(status_code=500, detail=f"요청 목록 조회 중 오류가 발생했습니다: {e}")


@router.get("/pending", response_model=PermissionRequestListResponse)
async def get_pending_permission_requests(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    대기 중인 권한 요청 목록 조회 (관리자용)
    
    - 승인 대기 중인 권한 요청 목록을 조회합니다
    - 관리자 권한이 필요합니다
    - 지식관리자는 관리 범위 내 요청만 조회됩니다
    """
    try:
        service = PermissionRequestService(session)
        
        # 지식관리자 범위 필터링 적용
        result = await service.get_pending_requests(
            container_id=None,
            limit=limit,
            manager_emp_no=current_user.emp_no  # 지식관리자 범위 제한
        )
        
        # result는 Dict[str, Any] 형태: {'total': int, 'requests': List[TbPermissionRequests], ...}
        requests_data = result.get('requests', [])
        total_count = result.get('total', 0)

        # SQLAlchemy 모델을 스키마로 변환
        requests_list = []
        for req in requests_data:
            # Use eagerly loaded relationships
            requester_name = req.requester.emp_nm if req.requester else None
            requester_department = req.requester.dept_nm if req.requester else None
            container_name = req.knowledge_container.container_name if req.knowledge_container else None
            approver_name = req.approver.emp_nm if req.approver else None
            
            requests_list.append(PermissionRequestResponse(
                id=req.request_id,
                request_id=str(req.request_id),
                requester_emp_no=req.requester_emp_no,
                requester_name=requester_name,
                requester_department=requester_department,
                container_id=req.container_id,
                container_name=container_name,
                current_permission_level=req.current_permission,
                requested_permission_level=req.requested_permission,
                request_reason=req.justification or "",
                business_justification=req.business_need,
                expected_usage_period=req.requested_duration,
                urgency_level=req.priority_level,
                status=req.request_status,
                approver_emp_no=req.approver_emp_no,
                approver_name=approver_name,
                approval_comment=req.approval_comment,
                rejection_reason=req.rejection_reason,
                auto_approved=req.auto_approved,
                requested_at=req.created_date.isoformat() if req.created_date else None,
                processed_at=req.approval_date.isoformat() if req.approval_date else None,
                expires_at=req.temp_end_date.isoformat() if req.temp_end_date else None
            ))

        return PermissionRequestListResponse(
            requests=requests_list,
            total_count=total_count,
            pending_count=total_count
        )
        
    except Exception as e:
        logger.error(f"대기 요청 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="대기 요청 조회 중 오류가 발생했습니다.")


@router.get("/{request_id}", response_model=PermissionRequestResponse)
async def get_permission_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 상세 정보 조회
    """
    try:
        service = PermissionRequestService(session)
        
        request = await service.get_request_by_id(request_id)
        
        if not request:
            raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
        
        # 본인의 요청이거나 관리자인지 확인
        if request['requester_emp_no'] != current_user.emp_no:
            # TODO: 관리자 권한 확인 추가
            pass
        
        return PermissionRequestResponse(**request)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"요청 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="요청 조회 중 오류가 발생했습니다.")


# ==================== 권한 요청 승인/거부 ====================

@router.post("/{request_id}/approve", response_model=PermissionRequestActionResponse)
async def approve_permission_request(
    request_id: str,
    approval_data: PermissionRequestApprove,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 승인
    
    - 대기 중인 권한 요청을 승인하고 권한을 부여합니다
    - 관리자 권한이 필요합니다
    """
    try:
        service = PermissionRequestService(session)
        
        # TODO: 승인 권한 확인 추가
        
        success = await service.approve_request(
            request_id=int(request_id),  # Convert string to int
            approver_emp_no=current_user.emp_no,
            approval_comment=approval_data.approval_comment
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="권한 요청 승인에 실패했습니다.")
        
        return PermissionRequestActionResponse(
            success=True,
            message="권한 요청이 승인되었습니다.",
            request_id=request_id
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"권한 승인 실패: {e}")
        raise HTTPException(status_code=500, detail="권한 승인 중 오류가 발생했습니다.")


@router.post("/{request_id}/reject", response_model=PermissionRequestActionResponse)
async def reject_permission_request(
    request_id: str,
    rejection_data: PermissionRequestReject,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 거부
    
    - 대기 중인 권한 요청을 거부합니다
    - 관리자 권한이 필요합니다
    """
    try:
        service = PermissionRequestService(session)
        
        # TODO: 거부 권한 확인 추가
        
        success = await service.reject_request(
            request_id=int(request_id),  # Convert string to int
            approver_emp_no=current_user.emp_no,  # Fixed parameter name
            rejection_reason=rejection_data.rejection_reason
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="권한 요청 거부에 실패했습니다.")
        
        return PermissionRequestActionResponse(
            success=True,
            message="권한 요청이 거부되었습니다.",
            request_id=request_id
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"권한 거부 실패: {e}")
        raise HTTPException(status_code=500, detail="권한 거부 중 오류가 발생했습니다.")


@router.delete("/{request_id}", response_model=PermissionRequestActionResponse)
async def cancel_permission_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 취소
    
    - 본인의 대기 중인 권한 요청을 취소합니다
    """
    try:
        service = PermissionRequestService(session)
        
        success = await service.cancel_request(
            request_id=int(request_id),  # Convert string to int
            requester_emp_no=current_user.emp_no
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="권한 요청 취소에 실패했습니다.")
        
        return PermissionRequestActionResponse(
            success=True,
            message="권한 요청이 취소되었습니다.",
            request_id=request_id
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"권한 취소 실패: {e}")
        raise HTTPException(status_code=500, detail="권한 취소 중 오류가 발생했습니다.")


# ==================== 일괄 작업 ====================

@router.post("/batch-approve", response_model=BatchActionResponse)
async def batch_approve_requests(
    batch_data: BatchApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 일괄 승인
    
    - 여러 권한 요청을 한 번에 승인합니다
    - 관리자 권한이 필요합니다
    """
    try:
        service = PermissionRequestService(session)
        
        processed_count = 0
        failed_requests = []
        
        for request_id in batch_data.request_ids:
            try:
                await service.approve_request(
                    request_id=int(request_id),  # Convert string to int
                    approver_emp_no=current_user.emp_no,
                    approval_comment=batch_data.approval_comment
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"일괄 승인 실패 ({request_id}): {e}")
                failed_requests.append(request_id)
        
        await session.commit()
        
        return BatchActionResponse(
            success=True,
            message=f"{processed_count}개 요청이 승인되었습니다.",
            processed_count=processed_count,
            failed_requests=failed_requests if failed_requests else None
        )
        
    except Exception as e:
        await session.rollback()
        logger.error(f"일괄 승인 실패: {e}")
        raise HTTPException(status_code=500, detail="일괄 승인 중 오류가 발생했습니다.")


@router.post("/batch-reject", response_model=BatchActionResponse)
async def batch_reject_requests(
    batch_data: BatchRejectionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 일괄 거부
    
    - 여러 권한 요청을 한 번에 거부합니다
    - 관리자 권한이 필요합니다
    """
    try:
        service = PermissionRequestService(session)
        
        processed_count = 0
        failed_requests = []
        
        for request_id in batch_data.request_ids:
            try:
                await service.reject_request(
                    request_id=int(request_id),  # Convert string to int
                    approver_emp_no=current_user.emp_no,  # Fixed parameter name
                    rejection_reason=batch_data.rejection_reason
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"일괄 거부 실패 ({request_id}): {e}")
                failed_requests.append(request_id)
        
        await session.commit()
        
        return BatchActionResponse(
            success=True,
            message=f"{processed_count}개 요청이 거부되었습니다.",
            processed_count=processed_count,
            failed_requests=failed_requests if failed_requests else None
        )
        
    except Exception as e:
        await session.rollback()
        logger.error(f"일괄 거부 실패: {e}")
        raise HTTPException(status_code=500, detail="일괄 거부 중 오류가 발생했습니다.")


# ==================== 통계 및 모니터링 ====================

@router.get("/statistics/summary", response_model=PermissionRequestStatistics)
async def get_permission_request_statistics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    권한 요청 통계 조회
    
    - 권한 요청 현황 및 통계를 조회합니다
    - 관리자 권한이 필요합니다
    """
    try:
        service = PermissionRequestService(session)
        
        # TODO: 관리자 권한 확인 추가
        
        stats = await service.get_statistics()
        
        return PermissionRequestStatistics(**stats)
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="통계 조회 중 오류가 발생했습니다.")

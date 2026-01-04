"""
IPC 권한 관리 Admin API
시스템 관리자가 사용자별 IPC 권한을 직접 할당/관리하는 엔드포인트
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, delete as sql_delete
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models import User
from app.models.patent.ipc_models import TbIpcPermissions, TbIpcCode
from app.services.auth.ipc_permission_service import IpcPermissionService

router = APIRouter(
    prefix="/api/v1/admin/ipc-permissions",
    tags=["🔐 Admin - IPC Permission Management"]
)


# === Pydantic Schemas ===

class IpcPermissionCreate(BaseModel):
    """IPC 권한 생성 요청"""
    user_emp_no: str = Field(..., description="사용자 사번")
    ipc_code: str = Field(..., description="IPC 코드 (예: H04W, G06N)")
    role_id: str = Field(..., description="권한 레벨 (VIEWER/EDITOR/ADMIN)")
    access_scope: str = Field(default="FULL", description="접근 범위 (FULL/READ_ONLY/WRITE_ONLY)")
    include_children: bool = Field(default=True, description="하위 IPC 코드 포함 여부")
    valid_until: Optional[datetime] = Field(None, description="만료일 (없으면 무기한)")


class IpcPermissionUpdate(BaseModel):
    """IPC 권한 수정 요청"""
    role_id: Optional[str] = Field(None, description="권한 레벨")
    access_scope: Optional[str] = Field(None, description="접근 범위")
    include_children: Optional[bool] = Field(None, description="하위 코드 포함")
    valid_until: Optional[datetime] = Field(None, description="만료일")
    is_active: Optional[bool] = Field(None, description="활성화 여부")


class IpcPermissionBulkCreate(BaseModel):
    """일괄 권한 부여 요청"""
    permissions: List[IpcPermissionCreate]


class IpcPermissionResponse(BaseModel):
    """IPC 권한 응답"""
    permission_id: int
    user_emp_no: str
    user_name: Optional[str] = None
    ipc_code: str
    ipc_description_kr: Optional[str] = None
    role_id: str
    access_scope: str
    include_children: bool
    valid_from: datetime
    valid_until: Optional[datetime]
    is_active: bool
    created_by: Optional[str]
    created_date: datetime


class IpcPermissionListResponse(BaseModel):
    """IPC 권한 목록 응답"""
    permissions: List[IpcPermissionResponse]
    total: int
    page: int
    page_size: int


# === API Endpoints ===

@router.get("", response_model=IpcPermissionListResponse)
async def list_ipc_permissions(
    user_emp_no: Optional[str] = Query(None, description="사용자 사번 필터"),
    ipc_code: Optional[str] = Query(None, description="IPC 코드 필터"),
    role_id: Optional[str] = Query(None, description="권한 레벨 필터"),
    is_active: Optional[bool] = Query(None, description="활성화 여부 필터"),
    search: Optional[str] = Query(None, description="검색어 (사용자명, 사번, IPC)"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 권한 목록 조회 (시스템 관리자 전용)
    
    - 필터링: 사용자, IPC 코드, 권한 레벨, 활성화 여부
    - 검색: 사용자명, 사번, IPC 코드로 검색
    - 페이징: page, page_size
    """
    # 쿼리 빌딩
    query = select(TbIpcPermissions).join(
        TbIpcCode, TbIpcPermissions.ipc_code == TbIpcCode.code, isouter=True
    )
    
    filters = []
    
    if user_emp_no:
        filters.append(TbIpcPermissions.user_emp_no == user_emp_no)
    
    if ipc_code:
        # 하위 코드도 검색
        filters.append(or_(
            TbIpcPermissions.ipc_code == ipc_code,
            TbIpcPermissions.ipc_code.like(f"{ipc_code}%")
        ))
    
    if role_id:
        filters.append(TbIpcPermissions.role_id == role_id)
    
    if is_active is not None:
        filters.append(TbIpcPermissions.is_active == is_active)
    
    if search:
        # 사용자명, 사번, IPC 코드로 검색
        search_filter = or_(
            TbIpcPermissions.user_emp_no.ilike(f"%{search}%"),
            TbIpcPermissions.ipc_code.ilike(f"%{search}%"),
            TbIpcCode.description_ko.ilike(f"%{search}%")
        )
        filters.append(search_filter)
    
    if filters:
        query = query.where(and_(*filters))
    
    # 총 개수 조회
    count_query = select(func.count()).select_from(TbIpcPermissions)
    if filters:
        count_query = count_query.where(and_(*filters))
    
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # 페이징 조회
    query = query.order_by(
        TbIpcPermissions.created_date.desc()
    ).offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    permissions = result.scalars().all()
    
    # IPC 설명 조회
    ipc_codes = list(set([p.ipc_code for p in permissions]))
    ipc_query = select(TbIpcCode).where(TbIpcCode.code.in_(ipc_codes))
    ipc_result = await db.execute(ipc_query)
    ipc_dict = {ipc.code: ipc.description_ko for ipc in ipc_result.scalars().all()}
    
    # 응답 생성
    permission_list = [
        IpcPermissionResponse(
            permission_id=p.permission_id,
            user_emp_no=p.user_emp_no,
            user_name=None,  # TODO: 사용자 정보 조인
            ipc_code=p.ipc_code,
            ipc_description_kr=ipc_dict.get(p.ipc_code),
            role_id=p.role_id,
            access_scope=p.access_scope,
            include_children=p.include_children,
            valid_from=p.valid_from,
            valid_until=p.valid_until,
            is_active=p.is_active,
            created_by=p.created_by,
            created_date=p.created_date
        )
        for p in permissions
    ]
    
    return IpcPermissionListResponse(
        permissions=permission_list,
        total=total_count,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=IpcPermissionResponse)
async def create_ipc_permission(
    request: IpcPermissionCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 권한 부여 (시스템 관리자 전용)
    
    - 사용자에게 특정 IPC 코드 권한 직접 할당
    - 중복 체크: 동일 사용자+IPC 조합이 이미 존재하면 에러
    """
    # 1. IPC 코드 존재 여부 확인
    ipc_query = select(TbIpcCode).where(TbIpcCode.code == request.ipc_code)
    ipc_result = await db.execute(ipc_query)
    ipc_code = ipc_result.scalar_one_or_none()
    
    if not ipc_code:
        raise HTTPException(
            status_code=404,
            detail=f"IPC 코드 '{request.ipc_code}'를 찾을 수 없습니다."
        )
    
    # 2. 중복 체크
    existing_query = select(TbIpcPermissions).where(
        and_(
            TbIpcPermissions.user_emp_no == request.user_emp_no,
            TbIpcPermissions.ipc_code == request.ipc_code
        )
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"사용자 {request.user_emp_no}에게 이미 IPC {request.ipc_code} 권한이 존재합니다."
        )
    
    # 3. 권한 생성
    new_permission = TbIpcPermissions(
        user_emp_no=request.user_emp_no,
        ipc_code=request.ipc_code,
        role_id=request.role_id,
        access_scope=request.access_scope,
        include_children=request.include_children,
        valid_until=request.valid_until,
        is_active=True,
        created_by=str(current_user.emp_no)
    )
    
    db.add(new_permission)
    await db.commit()
    await db.refresh(new_permission)
    
    return IpcPermissionResponse(
        permission_id=new_permission.permission_id,
        user_emp_no=new_permission.user_emp_no,
        user_name=None,
        ipc_code=new_permission.ipc_code,
        ipc_description_kr=ipc_code.description_ko,
        role_id=new_permission.role_id,
        access_scope=new_permission.access_scope,
        include_children=new_permission.include_children,
        valid_from=new_permission.valid_from,
        valid_until=new_permission.valid_until,
        is_active=new_permission.is_active,
        created_by=new_permission.created_by,
        created_date=new_permission.created_date
    )


@router.put("/{permission_id}", response_model=IpcPermissionResponse)
async def update_ipc_permission(
    permission_id: int,
    request: IpcPermissionUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 권한 수정 (시스템 관리자 전용)
    
    - 권한 레벨, 접근 범위, 하위 코드 포함, 만료일, 활성화 여부 수정 가능
    """
    # 권한 조회
    query = select(TbIpcPermissions).where(TbIpcPermissions.permission_id == permission_id)
    result = await db.execute(query)
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=404, detail="권한을 찾을 수 없습니다.")
    
    # 수정 가능한 필드만 업데이트
    if request.role_id is not None:
        permission.role_id = request.role_id
    if request.access_scope is not None:
        permission.access_scope = request.access_scope
    if request.include_children is not None:
        permission.include_children = request.include_children
    if request.valid_until is not None:
        permission.valid_until = request.valid_until
    if request.is_active is not None:
        permission.is_active = request.is_active
    
    permission.last_modified_date = datetime.utcnow()
    permission.last_modified_by = str(current_user.emp_no)
    
    await db.commit()
    await db.refresh(permission)
    
    # IPC 설명 조회
    ipc_query = select(TbIpcCode).where(TbIpcCode.code == permission.ipc_code)
    ipc_result = await db.execute(ipc_query)
    ipc_code = ipc_result.scalar_one_or_none()
    
    return IpcPermissionResponse(
        permission_id=permission.permission_id,
        user_emp_no=permission.user_emp_no,
        user_name=None,
        ipc_code=permission.ipc_code,
        ipc_description_kr=ipc_code.description_ko if ipc_code else None,
        role_id=permission.role_id,
        access_scope=permission.access_scope,
        include_children=permission.include_children,
        valid_from=permission.valid_from,
        valid_until=permission.valid_until,
        is_active=permission.is_active,
        created_by=permission.created_by,
        created_date=permission.created_date
    )


@router.delete("/{permission_id}")
async def delete_ipc_permission(
    permission_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 권한 삭제 (시스템 관리자 전용)
    
    - 물리적 삭제 (DB에서 완전히 제거)
    """
    delete_query = sql_delete(TbIpcPermissions).where(
        TbIpcPermissions.permission_id == permission_id
    )
    
    result = await db.execute(delete_query)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="권한을 찾을 수 없습니다.")
    
    return {"success": True, "message": f"권한 ID {permission_id} 삭제 완료"}


@router.get("/user/{emp_no}", response_model=List[IpcPermissionResponse])
async def get_user_ipc_permissions(
    emp_no: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 사용자의 IPC 권한 목록 조회 (시스템 관리자 전용)
    
    - 사용자에게 할당된 모든 IPC 권한 조회
    """
    query = select(TbIpcPermissions).where(
        TbIpcPermissions.user_emp_no == emp_no
    ).order_by(TbIpcPermissions.created_date.desc())
    
    result = await db.execute(query)
    permissions = result.scalars().all()
    
    # IPC 설명 조회
    ipc_codes = list(set([p.ipc_code for p in permissions]))
    if ipc_codes:
        ipc_query = select(TbIpcCode).where(TbIpcCode.code.in_(ipc_codes))
        ipc_result = await db.execute(ipc_query)
        ipc_dict = {ipc.code: ipc.description_ko for ipc in ipc_result.scalars().all()}
    else:
        ipc_dict = {}
    
    return [
        IpcPermissionResponse(
            permission_id=p.permission_id,
            user_emp_no=p.user_emp_no,
            user_name=None,
            ipc_code=p.ipc_code,
            ipc_description_kr=ipc_dict.get(p.ipc_code),
            role_id=p.role_id,
            access_scope=p.access_scope,
            include_children=p.include_children,
            valid_from=p.valid_from,
            valid_until=p.valid_until,
            is_active=p.is_active,
            created_by=p.created_by,
            created_date=p.created_date
        )
        for p in permissions
    ]


@router.post("/bulk", response_model=dict)
async def bulk_create_ipc_permissions(
    request: IpcPermissionBulkCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 권한 일괄 부여 (시스템 관리자 전용)
    
    - CSV 업로드 등을 통한 대량 권한 할당
    - 중복은 건너뛰고 계속 진행
    """
    success_count = 0
    error_count = 0
    errors = []
    
    for perm in request.permissions:
        try:
            # IPC 코드 확인
            ipc_query = select(TbIpcCode).where(TbIpcCode.code == perm.ipc_code)
            ipc_result = await db.execute(ipc_query)
            ipc_code = ipc_result.scalar_one_or_none()
            
            if not ipc_code:
                errors.append(f"IPC 코드 {perm.ipc_code} 없음")
                error_count += 1
                continue
            
            # 중복 체크
            existing_query = select(TbIpcPermissions).where(
                and_(
                    TbIpcPermissions.user_emp_no == perm.user_emp_no,
                    TbIpcPermissions.ipc_code == perm.ipc_code
                )
            )
            existing_result = await db.execute(existing_query)
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                errors.append(f"중복: {perm.user_emp_no} - {perm.ipc_code}")
                error_count += 1
                continue
            
            # 권한 생성
            new_permission = TbIpcPermissions(
                user_emp_no=perm.user_emp_no,
                ipc_code=perm.ipc_code,
                role_id=perm.role_id,
                access_scope=perm.access_scope,
                include_children=perm.include_children,
                valid_until=perm.valid_until,
                is_active=True,
                created_by=str(current_user.emp_no)
            )
            
            db.add(new_permission)
            success_count += 1
            
        except Exception as e:
            errors.append(f"에러: {perm.user_emp_no} - {perm.ipc_code}: {str(e)}")
            error_count += 1
    
    await db.commit()
    
    return {
        "success": True,
        "total": len(request.permissions),
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors[:10]  # 처음 10개 에러만 반환
    }

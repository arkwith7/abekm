"""
사용자 인증 및 관리 API 엔드포인트

# pyright: reportGeneralTypeIssues=false
"""
from datetime import timedelta, datetime, timezone
# pyright: reportGeneralTypeIssues=false
from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, Cookie, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import AuthUtils, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES
from app.core.dependencies import get_current_user, get_current_admin_user
from app.models import User
from app.models.auth import RefreshToken
from sqlalchemy import select
from app.schemas.user_schemas import (
    UserLogin, Token, UserCreate, UserUpdate, UserPasswordChange,
    UserResponse, UserListResponse, UserSearchParams, PaginatedUserResponse,
    SapHrInfoCreate, SapHrInfoUpdate, SapHrInfoResponse,
    SapSyncRequest, SapSyncResponse,
    BulkDeleteRequest, BulkUpdateRoleRequest, BulkOperationResponse
)
from pydantic import BaseModel
from typing import Optional

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None

from app.services.auth.async_user_service import AsyncUserService, AsyncSapHrService
from app.services.auth.container_service import ContainerService


class UserQuickSearchItem(BaseModel):
    emp_no: str
    username: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None


class UserQuickSearchResponse(BaseModel):
    success: bool
    users: List[UserQuickSearchItem]
    total: int
    page: int
    size: int

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
user_router = APIRouter(prefix="/api/v1/users", tags=["User Management"])
sap_router = APIRouter(prefix="/api/v1/sap", tags=["SAP HR Management"])

# ==================== 인증 관련 엔드포인트 ====================

def _build_user_info(user: User, sap_hr_info) -> UserListResponse:
    """SQLAlchemy 모델에서 Pydantic DTO로 안전 변환 (type checker 억제)"""
    return UserListResponse(
        id=int(user.id),  # type: ignore[arg-type]
        username=str(user.username),  # type: ignore[arg-type]
        email=str(user.email),  # type: ignore[arg-type]
        emp_no=str(user.emp_no),  # type: ignore[arg-type]
        is_active=bool(user.is_active),  # type: ignore[arg-type]
        is_admin=bool(user.is_admin),  # type: ignore[arg-type]
        last_login=user.last_login,  # datetime | None
        emp_name=sap_hr_info.emp_nm if sap_hr_info else None,  # type: ignore[arg-type]
        dept_name=sap_hr_info.dept_nm if sap_hr_info else None,  # type: ignore[arg-type]
        position_name=sap_hr_info.postn_nm if sap_hr_info else None,  # type: ignore[arg-type]
        role=""  # placeholder, caller sets
    )


def _generate_csrf_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)


@router.post("/login")
async def login(
    user_credentials: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 로그인 - 사번과 비밀번호로 로그인 (JWT 토큰 + 쿠키 설정)
    """
    user_service = AsyncUserService(db)
    user = await user_service.authenticate_user(
        user_credentials.emp_no, 
        user_credentials.password,
        options=[selectinload(User.sap_hr_info)]
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자명 또는 비밀번호가 올바르지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # JWT 토큰 생성
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = AuthUtils.create_access_token(
        data={
            "sub": user.emp_no,  # 사번을 주 식별자로 사용
            "user_id": user.id,
            "username": user.username,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )

    # Refresh 토큰 생성 (더 긴 만료기간)
    refresh_token_expires = timedelta(minutes=int(REFRESH_TOKEN_EXPIRE_MINUTES))
    refresh_token_raw, jti = AuthUtils.create_refresh_token(
        data={
            "sub": user.emp_no,
            "user_id": user.id,
            "username": user.username,
            "is_admin": user.is_admin
        },
        expires_delta=refresh_token_expires
    )
    # 새 토큰 저장
    token_hash = AuthUtils.hash_refresh_token(refresh_token_raw)
    refresh_record = RefreshToken(
        user_id=user.id,
        emp_no=user.emp_no,
        jti=jti,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires,
        is_active=True
    )
    db.add(refresh_record)
    await db.commit()
    
    # 쿠키에 토큰 설정 (HttpOnly, Secure, SameSite 설정)
    response.set_cookie(
        key="access_token",
        value=access_token,
    max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60,  # 초 단위
        httponly=True,  # XSS 방지
        secure=False,   # HTTPS에서만 전송 (개발환경에서는 False)
        samesite="lax"  # CSRF 방지
    )

    # refresh 토큰 HttpOnly 쿠키 설정
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_raw,
    max_age=int(REFRESH_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )
    
    # 사용자의 SAP HR 정보 조회
    sap_hr_info = await user_service.get_sap_hr_info_by_emp_no(user.emp_no)
    
    # 사용자 역할 확인 (ADMIN, MANAGER, USER)
    # NOTE: 2025-09-30 정책 수정
    # 기존: role_level <= 3 이면 MANAGER 간주 → 'EDITOR' 와 같은 비관리 직책도 MANAGER 로 오분류됨
    # 변경: 활성 역할 중 role_name='MANAGER' 가 존재할 때만 MANAGER 승격
    # 추가 개선 여지: container 별 scoped role / 다중 역할 우선순위 매핑 테이블 도입
    user_role = "ADMIN" if user.is_admin else "USER"
    if user_role == "USER":
        from sqlalchemy import text
        # 이전 로직: role_level <= 3 이면 모두 MANAGER 처리 → EDITOR(77107791) 가 의도치 않게 MANAGER 분류됨
        # 수정: 명시적으로 role_name='MANAGER' 인 활성 역할만 관리자로 승격
        role_result = await db.execute(
            text("""
                SELECT role_level
                FROM tb_user_roles
                WHERE user_emp_no = :emp_no
                  AND is_active = true
                  AND role_name = 'MANAGER'
                  AND role_level <= 3
                ORDER BY role_level ASC
                LIMIT 1
            """),
            {"emp_no": user.emp_no}
        )
        role_level = role_result.scalar()
        if role_level is not None:
            user_role = "MANAGER"

    user_info = _build_user_info(user, sap_hr_info)
    user_info.role = user_role  # type: ignore[attr-defined]

    # CSRF 토큰 생성 및 쿠키 (HttpOnly 아님) 설정
    csrf_token = _generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
    max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=False,
        secure=False,
        samesite="lax"
    )
    
    return {
        "access_token": access_token,
    "refresh_token": refresh_token_raw,
    "refresh_token_expires_in": int(REFRESH_TOKEN_EXPIRE_MINUTES) * 60,
        "token_type": "bearer",
    "expires_in": int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
    "user_info": user_info,
    "csrf_token": csrf_token
    }

@router.post("/refresh")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token")
):
    """리프레시 토큰으로 액세스/리프레시 토큰 재발급 (쿠키 우선, Body fallback)"""
    
    # JSON body에서 refresh_token 추출
    refresh_token_from_body = None
    try:
        body = await request.json()
        refresh_token_from_body = body.get('refresh_token')
        logger.info(f"🔍 JSON body: {body}")
    except Exception as e:
        logger.info(f"🔍 JSON body 파싱 실패 또는 비어있음: {e}")
    
    # 디버깅을 위한 상세 로그
    logger.info(f"🔍 받은 파라미터들:")
    logger.info(f"  - refresh_token_from_body: {refresh_token_from_body}")
    logger.info(f"  - refresh_cookie: {refresh_cookie}")
    logger.info(f"  - csrf_header: {csrf_header is not None}")
    logger.info(f"  - csrf_cookie: {csrf_cookie is not None}")
        
    # CSRF 검증 (쿠키 vs 헤더 일치) - 디버깅 로그 추가
    logger.info(f"🔍 CSRF 검증: cookie={csrf_cookie is not None}, header={csrf_header is not None}")
    
    # 쿠키 또는 헤더 중 하나라도 있으면 통과 (완화된 검증)
    if not csrf_cookie and not csrf_header:
        logger.warning(f"🚫 CSRF 토큰 완전 누락: cookie={csrf_cookie is not None}, header={csrf_header is not None}")
        raise HTTPException(
            status_code=403, 
            detail=f"CSRF token completely missing (cookie: {csrf_cookie is not None}, header: {csrf_header is not None})"
        )
    
    # 둘 다 있는 경우에만 일치 검사
    if csrf_cookie and csrf_header and csrf_cookie != csrf_header:
        logger.warning(f"🚫 CSRF 토큰 불일치: cookie length={len(csrf_cookie)}, header length={len(csrf_header)}")
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
        
    logger.info(f"✅ CSRF 검증 통과: cookie={bool(csrf_cookie)}, header={bool(csrf_header)}")

    # refresh token을 body 또는 cookie에서 가져오기 (이미 위에서 추출함)
    provided_token = refresh_cookie or refresh_token_from_body
    logger.info(f"🔍 Refresh 토큰 확인: cookie={bool(refresh_cookie)}, body={bool(refresh_token_from_body)}")
    if provided_token is None:
        logger.warning(f"🚫 Refresh 토큰 없음: cookie={refresh_cookie}, body={refresh_token_from_body}")
        raise HTTPException(status_code=400, detail="refresh_token 이 필요합니다")

    token_data = AuthUtils.verify_refresh_token(provided_token)

    # DB에서 활성 해시 존재 확인
    from sqlalchemy import select, update
    token_hash = AuthUtils.hash_refresh_token(provided_token)
    existing_q = await db.execute(
        select(RefreshToken).where(
            RefreshToken.emp_no == token_data.emp_no,
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_active == True,
            RefreshToken.revoked_at.is_(None)
        )
    )
    refresh_row: RefreshToken | None = existing_q.scalar_one_or_none()
    if not refresh_row:
        raise HTTPException(status_code=401, detail="유효하지 않은 refresh 토큰")

    # Rotation: 현재 토큰 비활성화 & 새 토큰 발급
    refresh_row.is_active = False  # type: ignore[assignment]
    refresh_row.rotated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

    # 새 access / refresh 생성
    new_access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    new_access_token = AuthUtils.create_access_token(
        data={
            "sub": token_data.emp_no,
            "user_id": token_data.user_id,
            "username": token_data.username,
            "is_admin": token_data.is_admin
        },
        expires_delta=new_access_token_expires
    )
    new_refresh_token_expires = timedelta(minutes=int(REFRESH_TOKEN_EXPIRE_MINUTES))
    new_refresh_token_raw, new_jti = AuthUtils.create_refresh_token(
        data={
            "sub": token_data.emp_no,
            "user_id": token_data.user_id,
            "username": token_data.username,
            "is_admin": token_data.is_admin
        },
        expires_delta=new_refresh_token_expires
    )
    # 새 refresh 토큰 저장
    new_hash = AuthUtils.hash_refresh_token(new_refresh_token_raw)
    new_record = RefreshToken(
        user_id=refresh_row.user_id,
        emp_no=token_data.emp_no,
        jti=new_jti,
        token_hash=new_hash,
        expires_at=datetime.now(timezone.utc) + new_refresh_token_expires,
        is_active=True,
        user_agent=request.headers.get('user-agent'),
        ip_address=request.client.host if request.client else None
    )
    db.add(new_record)
    await db.commit()

    # 쿠키 갱신
    response.set_cookie(
        key="access_token",
        value=new_access_token,
    max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token_raw,
    max_age=int(REFRESH_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )
    
    # 새 CSRF 토큰 생성 및 쿠키 설정
    new_csrf_token = _generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=new_csrf_token,
        max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=False,
        secure=False,
        samesite="lax"
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token_raw,
        "token_type": "bearer",
    "expires_in": int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
    "refresh_token_expires_in": int(REFRESH_TOKEN_EXPIRE_MINUTES) * 60,
        "csrf_token": new_csrf_token
    }

@router.post("/logout")
async def logout(response: Response, refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"), db: AsyncSession = Depends(get_db)):
    """
    사용자 로그아웃 - 쿠키에서 토큰 삭제
    """
    # 가능한 경우 refresh 해시 찾아서 revoke
    if refresh_cookie:
        token_hash = AuthUtils.hash_refresh_token(refresh_cookie)
        q = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_active == True,
                RefreshToken.revoked_at.is_(None)
            )
        )
        row = q.scalar_one_or_none()
        if row:
            row.is_active = False  # type: ignore[assignment]
            row.revoked_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            row.revoke_reason = "logout"  # type: ignore[assignment]
            await db.commit()
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    response.delete_cookie(key="csrf_token")
    return {"message": "성공적으로 로그아웃되었습니다"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    현재 로그인한 사용자 정보 조회
    """
    return current_user

@router.post("/change-password")
async def change_password(
    password_data: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    비밀번호 변경
    """
    user_service = AsyncUserService(db)
    success = await user_service.change_password(
        current_user.id, 
        password_data, 
        updated_by=current_user.username
    )
    
    if success:
        return {"message": "비밀번호가 성공적으로 변경되었습니다"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비밀번호 변경에 실패했습니다"
        )

# ==================== 사용자 관리 엔드포인트 ====================

@user_router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    새 사용자 생성 (관리자 전용)
    """
    user_service = AsyncUserService(db)
    user = await user_service.create_user(user_data, created_by=current_admin.username)
    return user

@user_router.get("/", response_model=PaginatedUserResponse)
async def search_users(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    search: str = Query(None, description="검색어 (이름, 이메일, 사번)"),
    dept_cd: str = Query(None, description="부서 코드"),
    dept_nm: str = Query(None, description="부서명"),
    postn_cd: str = Query(None, description="직급 코드"),
    postn_nm: str = Query(None, description="직급명"),
    is_active: bool = Query(None, description="활성화 상태"),
    is_admin: bool = Query(None, description="관리자 여부"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 검색 및 목록 조회
    """
    search_params = UserSearchParams(
        page=page,
        size=size,
        search=search,
        dept_cd=dept_cd,
        dept_nm=dept_nm,
        postn_cd=postn_cd,
        postn_nm=postn_nm,
        is_active=is_active,
        is_admin=is_admin
    )
    
    user_service = AsyncUserService(db)
    users, total = await user_service.search_users(search_params)
    
    pages = (total + size - 1) // size
    
    return PaginatedUserResponse(
        items=users,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@user_router.get("/search", response_model=UserQuickSearchResponse)
async def quick_search_users(
    q: Optional[str] = Query(None, description="검색어 (이름, 이메일, 사번)", alias="q"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=50, description="페이지 크기"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """권한 관리용 경량 사용자 검색"""
    search_params = UserSearchParams(
        page=page,
        size=size,
        search=q
    )

    user_service = AsyncUserService(db)
    users, total = await user_service.search_users(search_params)

    results: List[UserQuickSearchItem] = []
    for user_item in users:
        results.append(
            UserQuickSearchItem(
                emp_no=user_item.emp_no,
                username=user_item.username,
                name=user_item.emp_name or user_item.username,
                department=user_item.dept_name,
                position=user_item.position_name,
                email=user_item.email
            )
        )

    return UserQuickSearchResponse(
        success=True,
        users=results,
        total=total,
        page=page,
        size=size
    )

@user_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 사용자 정보 조회
    """
    # 관리자가 아닌 경우 자신의 정보만 조회 가능
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="다른 사용자의 정보를 조회할 권한이 없습니다"
        )
    
    user_service = AsyncUserService(db)
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )
    
    return user

@user_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 정보 수정
    """
    # 관리자가 아닌 경우 자신의 정보만 수정 가능 (단, 관리자 권한 변경 불가)
    if not current_user.is_admin:
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="다른 사용자의 정보를 수정할 권한이 없습니다"
            )
        
        # 일반 사용자는 관리자 권한 변경 불가
        if user_data.is_admin is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 권한을 변경할 수 없습니다"
            )
    
    user_service = AsyncUserService(db)
    user = await user_service.update_user(user_id, user_data, updated_by=current_user.username)
    return user

@user_router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    new_password: str = None,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 비밀번호 리셋 (관리자 전용)
    """
    user_service = AsyncUserService(db)
    temp_password = await user_service.reset_password(
        user_id, 
        new_password, 
        updated_by=current_admin.username
    )
    
    return {
        "message": "비밀번호가 성공적으로 리셋되었습니다",
        "temporary_password": temp_password if not new_password else None
    }

@user_router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 삭제 (비활성화) (관리자 전용)
    """
    user_service = AsyncUserService(db)
    success = await user_service.delete_user(user_id, deleted_by=current_admin.username)
    
    if success:
        return {"message": "사용자가 성공적으로 비활성화되었습니다"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="사용자 삭제에 실패했습니다"
        )

@user_router.post("/bulk-delete", response_model=BulkOperationResponse)
async def bulk_delete_users(
    request: BulkDeleteRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    일괄 사용자 삭제 (비활성화) (관리자 전용)
    """
    user_service = AsyncUserService(db)
    processed, failed, errors = await user_service.bulk_delete_users(request.user_ids)
    
    return BulkOperationResponse(
        success=failed == 0,
        message=f"{processed}명 처리 완료, {failed}명 실패",
        processed_count=processed,
        failed_count=failed,
        errors=errors
    )

@user_router.post("/bulk-update-role", response_model=BulkOperationResponse)
async def bulk_update_role(
    request: BulkUpdateRoleRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    일괄 사용자 권한 변경 (관리자 전용)
    """
    user_service = AsyncUserService(db)
    processed, failed, errors = await user_service.bulk_update_role(request.user_ids, request.is_admin)
    
    return BulkOperationResponse(
        success=failed == 0,
        message=f"{processed}명 권한 변경 완료, {failed}명 실패",
        processed_count=processed,
        failed_count=failed,
        errors=errors
    )

@user_router.get("/filters/departments")
async def get_departments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    부서 목록 조회 (필터용)
    """
    user_service = AsyncUserService(db)
    departments = await user_service.get_all_departments()
    
    return {"departments": departments}

@user_router.get("/filters/positions")
async def get_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    직급 목록 조회 (필터용)
    """
    user_service = AsyncUserService(db)
    positions = await user_service.get_all_positions()
    
    return {"positions": positions}

# ==================== SAP 인사 정보 관리 엔드포인트 ====================

@sap_router.get("/{emp_no}", response_model=SapHrInfoResponse)
async def get_sap_hr_info(
    emp_no: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    SAP 인사 정보 조회
    """
    # 관리자가 아닌 경우 자신의 정보만 조회 가능
    if not current_user.is_admin and current_user.emp_no != emp_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="다른 사용자의 SAP 인사 정보를 조회할 권한이 없습니다"
        )
    
    sap_service = AsyncSapHrService(db)
    sap_info = await sap_service.get_sap_hr_info(emp_no)
    
    if not sap_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SAP 인사 정보를 찾을 수 없습니다"
        )
    
    return sap_info

@sap_router.post("/", response_model=SapHrInfoResponse)
async def create_sap_hr_info(
    sap_data: SapHrInfoCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    SAP 인사 정보 생성 (관리자 전용)
    """
    sap_service = AsyncSapHrService(db)
    sap_info = await sap_service.create_sap_hr_info(sap_data, created_by=current_admin.username)
    return sap_info

@sap_router.put("/{emp_no}", response_model=SapHrInfoResponse)
async def update_sap_hr_info(
    emp_no: str,
    sap_data: SapHrInfoUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    SAP 인사 정보 수정 (관리자 전용)
    """
    sap_service = AsyncSapHrService(db)
    sap_info = await sap_service.update_sap_hr_info(emp_no, sap_data, updated_by=current_admin.username)
    return sap_info

@sap_router.post("/sync", response_model=SapSyncResponse)
async def sync_sap_with_users(
    sync_request: SapSyncRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    SAP 인사 정보와 User 테이블 동기화 (관리자 전용)
    """
    sap_service = AsyncSapHrService(db)
    result = await sap_service.sync_with_users(sync_request, synced_by=current_admin.username)
    return result

# ==================== 사용자 지식 컨테이너 관련 엔드포인트 ====================

@user_router.get("/me/knowledge-containers")
async def get_user_knowledge_containers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    현재 사용자가 접근 가능한 지식 컨테이너 목록 조회
    """
    container_service = ContainerService(db)
    
    # 사용자의 권한이 있는 컨테이너 목록 조회
    containers = await container_service.get_user_accessible_containers(current_user.emp_no, db)
    
    return {
        "containers": containers,
        "user_info": {
            "emp_no": current_user.emp_no,
            "username": current_user.username,
            "is_admin": current_user.is_admin
        }
    }

@user_router.get("/me/container-permission/{container_id}")
async def get_user_container_permission(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 컨테이너에 대한 사용자 권한 조회
    """
    container_service = ContainerService(db)
    
    # 사용자의 컨테이너별 권한 조회
    permission = await container_service.permission_service.get_user_permission_level(current_user.emp_no, container_id)
    
    user_info = {
        "emp_no": current_user.emp_no,
        "username": current_user.username,
        "is_admin": current_user.is_admin
    }

    if permission is None:
        return {
            "container_id": container_id,
            "permission_level": "NONE",
            "has_access": False,
            "user_info": user_info
        }
    
    return {
        "container_id": container_id,
        "permission_level": permission,
        "has_access": permission != "NONE",
        "user_info": user_info
    }

# ==================== 대시보드 관련 엔드포인트 ====================

@user_router.get("/me/dashboard-summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 대시보드 요약 정보 조회
    - 내 문서 수
    - AI 대화 세션 수
    - 대기중인 권한 요청 수
    """
    try:
        from app.models import TbFileBssInfo, TbChatSession, TbPermissionRequest
        from sqlalchemy import func, and_
        
        # 1. 내가 업로드한 문서 수
        my_documents_result = await db.execute(
            select(func.count(TbFileBssInfo.file_bss_info_sno))
            .where(TbFileBssInfo.created_by == current_user.emp_no)
        )
        my_documents_count = my_documents_result.scalar() or 0
        
        # 2. 내 AI 대화 세션 수
        chat_sessions_result = await db.execute(
            select(func.count(TbChatSession.session_id))
            .where(TbChatSession.user_id == current_user.emp_no)
        )
        chat_sessions_count = chat_sessions_result.scalar() or 0
        
        # 3. 내가 요청한 권한 중 대기중인 것
        pending_requests_result = await db.execute(
            select(func.count(TbPermissionRequest.request_id))
            .where(
                and_(
                    TbPermissionRequest.requester_emp_no == current_user.emp_no,
                    TbPermissionRequest.status == 'PENDING'
                )
            )
        )
        pending_requests_count = pending_requests_result.scalar() or 0
        
        return {
            "success": True,
            "data": {
                "my_documents_count": int(my_documents_count),
                "chat_sessions_count": int(chat_sessions_count),
                "pending_requests_count": int(pending_requests_count),
                "user_info": {
                    "emp_no": current_user.emp_no,
                    "username": current_user.username,
                    "is_admin": current_user.is_admin
                }
            }
        }
    except Exception as e:
        logger.error(f"대시보드 요약 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대시보드 요약 조회 실패: {str(e)}"
        )

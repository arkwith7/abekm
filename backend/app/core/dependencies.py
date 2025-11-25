"""
FastAPI 의존성 주입용 인증 함수들
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthUtils
from app.models import User
from app.schemas.user_schemas import TokenData
from app.services.auth.async_user_service import AsyncUserService

# HTTP Bearer 토큰 스킴
security = HTTPBearer()

async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    현재 사용자의 토큰 데이터 추출
    """
    token = credentials.credentials
    token_data = AuthUtils.verify_token(token)
    return token_data

async def get_current_user(
    token_data: TokenData = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    현재 로그인한 사용자 정보 조회 - 사번 기반
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_service = AsyncUserService(db)
    user = await user_service.get_user_by_emp_no(token_data.emp_no)
    
    if user is None:
        logger.warning(f"🔍 사용자를 찾을 수 없음: emp_no={token_data.emp_no}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        logger.warning(f"🚫 비활성 계정: emp_no={user.emp_no}, username={user.username}, is_active={user.is_active}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다"
        )
    
    logger.info(f"✅ 사용자 인증 성공: emp_no={user.emp_no}, username={user.username}")
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    현재 활성화된 사용자 조회 (별칭)
    """
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    현재 관리자 사용자 조회
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    return current_user

async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    선택적 현재 사용자 조회 (인증이 선택사항인 경우)
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        token_data = AuthUtils.verify_token(token)
        
        user_service = AsyncUserService(db)
        user = await user_service.get_user_by_username(token_data.username)
        
        if user and user.is_active:
            return user
        
    except Exception:
        # 토큰이 유효하지 않아도 None 반환 (선택사항이므로)
        pass
    
    return None

def require_permissions(*required_roles: str):
    """
    특정 권한이 필요한 데코레이터 팩토리
    
    Args:
        required_roles: 필요한 역할들 ('admin', 'user' 등)
    """
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = []
        if current_user.is_admin:
            user_roles.append('admin')
        user_roles.append('user')
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"필요한 권한: {', '.join(required_roles)}"
            )
        
        return current_user
    
    return permission_checker

# 자주 사용되는 권한 체크 함수들
require_admin = require_permissions('admin')
require_user = require_permissions('user', 'admin')

"""
인증 서비스
JWT 토큰 기반 사용자 인증 및 권한 관리
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
from app.core.security import AuthUtils
import logging

from app.core.database import get_db
from app.models import User, TbSapHrInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

# JWT 설정
ALGORITHM = "HS256"

security = HTTPBearer()


class AuthService:
    """인증 서비스"""
    
    def __init__(self):
        self.secret_key = getattr(settings, 'secret_key', 'your-secret-key-here')
        self.access_token_expire_minutes = getattr(settings, 'access_token_expire_minutes', 30)
        
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """JWT 액세스 토큰 생성"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """JWT 토큰 검증"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None
    
    def hash_password(self, password: str) -> str:
        """비밀번호 해시화 (passlib CryptContext 사용)"""
        return AuthUtils.get_password_hash(password)

    def verify_password(self, plain_password: str, hashed_password: Any) -> bool:  # hashed_password는 런타임에 str
        """비밀번호 검증 (passlib CryptContext 사용)

        SQLAlchemy 모델 속성 타입 추론 문제로 Any 허용 후 str 변환.
        """
        return AuthUtils.verify_password(plain_password, str(hashed_password))
    
    async def authenticate_user(self, username: str, password: str, db: AsyncSession) -> Optional[User]:
        """사용자 인증"""
        try:
            result = await db.execute(select(User).where(User.username == username))
            user = result.scalars().first()
            if not user:
                return None
            
            if not self.verify_password(password, user.password_hash):
                return None
                
            # 마지막 로그인 시간 업데이트
            user.last_login = datetime.utcnow()
            user.failed_login_attempts = 0
            await db.commit()
            
            return user
            
        except Exception as e:
            logger.error(f"사용자 인증 오류: {e}")
            return None
    
    async def get_user_by_token(self, token: str, db: AsyncSession) -> Optional[User]:
        """토큰으로 사용자 정보 조회"""
        try:
            payload = self.verify_token(token)
            if not payload:
                return None
                
            emp_no = payload.get("sub")  # emp_no로 변경
            if not emp_no:
                return None
                
            result = await db.execute(select(User).where(User.emp_no == emp_no))
            user = result.scalars().first()
            return user
            
        except Exception as e:
            logger.error(f"토큰으로 사용자 조회 오류: {e}")
            return None


# 싱글톤 인스턴스
auth_service = AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """현재 인증된 사용자 조회 (의존성 주입용)"""
    try:
        token = credentials.credentials
        user = await auth_service.get_user_by_token(token, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 인증 정보입니다",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 계정입니다"
            )
            
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 인증 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 처리 중 오류가 발생했습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_info(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """현재 사용자의 상세 정보 조회"""
    return {
        "user_id": current_user.id,
        "emp_no": current_user.emp_no,
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login
    }


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 필요 (의존성 주입용)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user

"""JWT 인증 및 보안 관련 유틸리티

passlib 1.7.x 는 bcrypt 핸들러 초기화 시 bcrypt.__about__.__version__ 접근을 시도한다.
일부 bcrypt 4.x 배포본에서 __about__ 모듈이 누락되어 경고 로그가 발생하므로, passlib import 이전에
shim을 삽입해 경고를 제거한다.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
import secrets
import hashlib

# ---- bcrypt shim (passlib 경고 방지) MUST appear before passlib.context import ----
try:  # pragma: no cover
    import bcrypt as _bcrypt  # type: ignore
    if not hasattr(_bcrypt, "__about__"):
        class _BcryptAbout:  # minimal object with version attr
            __version__ = getattr(_bcrypt, "__version__", "unknown")
        _bcrypt.__about__ = _BcryptAbout()  # type: ignore[attr-defined]
except Exception:
    # 경고 억제 목적이므로 실패해도 치명적이지 않다
    pass

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.schemas.user_schemas import TokenData
from app.core.config import settings

# JWT 설정을 config.py와 통일
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_MINUTES = settings.refresh_token_expire_minutes

# 비밀번호 해싱 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthUtils:
    """인증 관련 유틸리티 클래스"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """비밀번호 검증"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """비밀번호 해싱"""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """액세스 토큰 생성"""
        to_encode = data.copy()
        
        # 만료 시간 설정
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        
        # JWT 토큰 인코딩
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, str]:
        """리프레시 토큰 생성 (보다 긴 만료)

        Returns:
            tuple[token, jti]
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
        jti = secrets.token_hex(16)
        to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), jti

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        """Refresh 토큰 원문은 저장하지 않고 해시만 저장 (유출 대비)"""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_refresh_token(token: str) -> TokenData:
        """리프레시 토큰 검증 (type=refresh)"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰을 검증할 수 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "refresh":
                raise credentials_exception
            emp_no = payload.get("sub")  # type: ignore
            username = payload.get("username")  # type: ignore
            user_id = payload.get("user_id")  # type: ignore
            is_admin: bool = payload.get("is_admin", False)
            if emp_no is None:
                raise credentials_exception
            return TokenData(emp_no=emp_no, username=username, user_id=user_id, is_admin=is_admin)
        except JWTError:
            raise credentials_exception
    
    @staticmethod
    def verify_token(token: str) -> TokenData:
        """토큰 검증 및 데이터 추출"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰을 검증할 수 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # JWT 토큰 디코딩
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            emp_no = payload.get("sub")  # type: ignore  # sub에서 emp_no 추출
            username = payload.get("username")  # type: ignore
            user_id = payload.get("user_id")  # type: ignore
            is_admin: bool = payload.get("is_admin", False)
            
            if emp_no is None:
                raise credentials_exception
                
            token_data = TokenData(
                emp_no=emp_no,
                username=username,
                user_id=user_id,
                is_admin=is_admin
            )
            return token_data
            
        except JWTError:
            raise credentials_exception
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """토큰 만료 여부 확인"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            exp = payload.get("exp")
            if exp is None:
                return True
            
            # 현재 시간과 비교
            current_time = datetime.now(timezone.utc).timestamp()
            return current_time > exp
            
        except JWTError:
            return True
    
    @staticmethod
    def get_token_remaining_time(token: str) -> Optional[timedelta]:
        """토큰 남은 시간 반환"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            exp = payload.get("exp")
            if exp is None:
                return None
            
            # 현재 시간과 비교하여 남은 시간 계산
            current_time = datetime.now(timezone.utc).timestamp()
            remaining_seconds = exp - current_time
            
            if remaining_seconds <= 0:
                return timedelta(0)
            
            return timedelta(seconds=remaining_seconds)
            
        except JWTError:
            return None

class PasswordPolicy:
    """비밀번호 정책 관리 클래스"""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = False
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    @classmethod
    def validate_password(cls, password: str) -> tuple[bool, list[str]]:
        """
        비밀번호 정책 검증
        
        Returns:
            tuple: (유효성 여부, 오류 메시지 리스트)
        """
        errors = []
        
        # 길이 검증
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"비밀번호는 최소 {cls.MIN_LENGTH}자 이상이어야 합니다")
        
        if len(password) > cls.MAX_LENGTH:
            errors.append(f"비밀번호는 최대 {cls.MAX_LENGTH}자 이하여야 합니다")
        
        # 대문자 검증
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("비밀번호에는 최소 1개의 대문자가 포함되어야 합니다")
        
        # 소문자 검증
        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("비밀번호에는 최소 1개의 소문자가 포함되어야 합니다")
        
        # 숫자 검증
        if cls.REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            errors.append("비밀번호에는 최소 1개의 숫자가 포함되어야 합니다")
        
        # 특수문자 검증
        if cls.REQUIRE_SPECIAL_CHARS and not any(c in cls.SPECIAL_CHARS for c in password):
            errors.append(f"비밀번호에는 특수문자({cls.SPECIAL_CHARS})가 포함되어야 합니다")
        
        return len(errors) == 0, errors
    
    @classmethod
    def generate_temporary_password(cls, length: int = 12) -> str:
        """임시 비밀번호 생성"""
        import secrets
        import string
        
        # 각 요구사항별로 최소 1개씩 포함
        chars = ""
        password = ""
        
        if cls.REQUIRE_UPPERCASE:
            chars += string.ascii_uppercase
            password += secrets.choice(string.ascii_uppercase)
        
        if cls.REQUIRE_LOWERCASE:
            chars += string.ascii_lowercase
            password += secrets.choice(string.ascii_lowercase)
        
        if cls.REQUIRE_DIGITS:
            chars += string.digits
            password += secrets.choice(string.digits)
        
        if cls.REQUIRE_SPECIAL_CHARS:
            chars += cls.SPECIAL_CHARS
            password += secrets.choice(cls.SPECIAL_CHARS)
        
        # 나머지 길이만큼 랜덤 문자 추가
        for _ in range(length - len(password)):
            password += secrets.choice(chars)
        
        # 문자열 셔플
        password_list = list(password)
        secrets.SystemRandom().shuffle(password_list)
        
        return ''.join(password_list)

class SecurityUtils:
    """보안 관련 유틸리티"""
    
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    @staticmethod
    def is_account_locked(failed_attempts: int, locked_until: Optional[datetime]) -> bool:
        """계정 잠금 상태 확인"""
        if failed_attempts >= SecurityUtils.MAX_LOGIN_ATTEMPTS:
            if locked_until and locked_until > datetime.now(timezone.utc):
                return True
        return False
    
    @staticmethod
    def get_lockout_time() -> datetime:
        """계정 잠금 해제 시간 계산"""
        return datetime.now(timezone.utc) + timedelta(minutes=SecurityUtils.LOCKOUT_DURATION_MINUTES)
    
    @staticmethod
    def should_reset_failed_attempts(last_failed_attempt: Optional[datetime]) -> bool:
        """실패 횟수 리셋 여부 판단 (24시간 후)"""
        if not last_failed_attempt:
            return True
        
        reset_time = last_failed_attempt + timedelta(hours=24)
        return datetime.now(timezone.utc) > reset_time

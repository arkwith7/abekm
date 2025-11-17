"""
사용자 인증 및 관리를 위한 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, validator
from enum import Enum

class UserRole(str, Enum):
    """사용자 역할"""
    USER = "user"
    ADMIN = "admin"

class UserStatus(str, Enum):
    """사용자 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"

# === SAP HR Info 스키마 ===
class SapHrInfoBase(BaseModel):
    """SAP 인사 정보 기본 스키마"""
    emp_no: str
    emp_nm: str
    dept_cd: Optional[str] = None
    dept_nm: Optional[str] = None
    postn_cd: Optional[str] = None
    postn_nm: Optional[str] = None
    email: Optional[str] = None
    telno: Optional[str] = None
    mbtlno: Optional[str] = None
    entrps_de: Optional[str] = None
    rsgntn_de: Optional[str] = None
    emp_stats_cd: Optional[str] = None

class SapHrInfoCreate(SapHrInfoBase):
    """SAP 인사 정보 생성 스키마"""
    pass

class SapHrInfoUpdate(BaseModel):
    """SAP 인사 정보 수정 스키마"""
    emp_nm: Optional[str] = None
    dept_cd: Optional[str] = None
    dept_nm: Optional[str] = None
    postn_cd: Optional[str] = None
    postn_nm: Optional[str] = None
    email: Optional[str] = None
    telno: Optional[str] = None
    mbtlno: Optional[str] = None
    entrps_de: Optional[str] = None
    rsgntn_de: Optional[str] = None
    emp_stats_cd: Optional[str] = None

class SapHrInfoResponse(SapHrInfoBase):
    """SAP 인사 정보 응답 스키마"""
    del_yn: str
    created_date: datetime
    last_modified_date: datetime
    
    class Config:
        from_attributes = True

# === User 스키마 ===
class UserBase(BaseModel):
    """사용자 기본 스키마"""
    username: str
    email: EmailStr
    emp_no: str

class UserCreate(UserBase):
    """사용자 생성 스키마"""
    password: str
    is_admin: bool = False
    
    @validator('password')
    def validate_password(cls, v):
        """비밀번호 검증"""
        if len(v) < 8:
            raise ValueError('비밀번호는 최소 8자 이상이어야 합니다')
        if not any(c.isdigit() for c in v):
            raise ValueError('비밀번호에는 최소 1개의 숫자가 포함되어야 합니다')
        if not any(c.isupper() for c in v):
            raise ValueError('비밀번호에는 최소 1개의 대문자가 포함되어야 합니다')
        if not any(c.islower() for c in v):
            raise ValueError('비밀번호에는 최소 1개의 소문자가 포함되어야 합니다')
        return v

class UserUpdate(BaseModel):
    """사용자 정보 수정 스키마"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserPasswordChange(BaseModel):
    """비밀번호 변경 스키마"""
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """새 비밀번호 검증"""
        if len(v) < 8:
            raise ValueError('비밀번호는 최소 8자 이상이어야 합니다')
        if not any(c.isdigit() for c in v):
            raise ValueError('비밀번호에는 최소 1개의 숫자가 포함되어야 합니다')
        if not any(c.isupper() for c in v):
            raise ValueError('비밀번호에는 최소 1개의 대문자가 포함되어야 합니다')
        if not any(c.islower() for c in v):
            raise ValueError('비밀번호에는 최소 1개의 소문자가 포함되어야 합니다')
        return v

class UserResponse(UserBase):
    """사용자 응답 스키마"""
    id: int
    is_active: bool
    is_admin: bool
    last_login: Optional[datetime] = None
    failed_login_attempts: int
    account_locked_until: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    created_date: datetime
    last_modified_date: datetime
    
    # SAP 인사 정보 포함
    # sap_hr_info: Optional[SapHrInfoResponse] = None
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    """사용자 목록 응답 스키마"""
    id: int
    username: str
    email: str
    emp_no: str
    is_active: bool
    is_admin: bool
    last_login: Optional[datetime] = None
    
    # SAP 인사 정보에서 주요 정보만
    emp_name: Optional[str] = None
    dept_name: Optional[str] = None
    position_name: Optional[str] = None
    
    # 사용자 역할 정보 (ADMIN, MANAGER, USER)
    role: str = "USER"
    
    class Config:
        from_attributes = True

# === 인증 관련 스키마 ===
class UserLogin(BaseModel):
    """로그인 스키마 - 사번과 비밀번호로 로그인"""
    emp_no: str  # 사번으로 로그인
    password: str

class Token(BaseModel):
    """토큰 응답 스키마"""
    access_token: str
    token_type: str
    expires_in: int
    user_info: UserListResponse

class TokenData(BaseModel):
    """토큰 데이터 스키마"""
    emp_no: Optional[str] = None  # 사번을 주 식별자로 사용
    username: Optional[str] = None
    user_id: Optional[int] = None
    is_admin: Optional[bool] = False

# === SAP 동기화 스키마 ===
class SapSyncRequest(BaseModel):
    """SAP 동기화 요청 스키마"""
    force_sync: bool = False  # 강제 동기화 여부
    sync_inactive: bool = False  # 비활성 사용자도 동기화할지 여부

class SapSyncResponse(BaseModel):
    """SAP 동기화 응답 스키마"""
    success: bool
    message: str
    synced_count: int
    created_users: int
    updated_users: int
    deactivated_users: int
    errors: list[str] = []

# === 페이징 스키마 ===
class UserSearchParams(BaseModel):
    """사용자 검색 파라미터"""
    page: int = 1
    size: int = 20
    search: Optional[str] = None  # 이름, 이메일, 사번으로 검색
    dept_cd: Optional[str] = None  # 부서 코드로 필터
    dept_nm: Optional[str] = None  # 부서명으로 필터
    postn_cd: Optional[str] = None  # 직급 코드로 필터
    postn_nm: Optional[str] = None  # 직급명으로 필터
    is_active: Optional[bool] = None  # 활성화 상태로 필터
    is_admin: Optional[bool] = None  # 관리자 여부로 필터

class PaginatedUserResponse(BaseModel):
    """페이징된 사용자 응답"""
    items: list[UserListResponse]
    total: int
    page: int
    size: int
    pages: int

# === 일괄 작업 스키마 ===
class BulkDeleteRequest(BaseModel):
    """일괄 삭제 요청"""
    user_ids: list[int]

class BulkUpdateRoleRequest(BaseModel):
    """일괄 권한 변경 요청"""
    user_ids: list[int]
    is_admin: bool

class BulkOperationResponse(BaseModel):
    """일괄 작업 응답"""
    success: bool
    message: str
    processed_count: int
    failed_count: int
    errors: list[str] = []

# === 엑셀 임포트 스키마 ===
class UserImportData(BaseModel):
    """엑셀에서 가져온 사용자 데이터"""
    username: str
    email: str
    emp_no: str
    is_admin: bool = False

class UserImportResponse(BaseModel):
    """사용자 임포트 응답"""
    success: bool
    message: str
    total_rows: int
    success_count: int
    failed_count: int
    errors: list[str] = []

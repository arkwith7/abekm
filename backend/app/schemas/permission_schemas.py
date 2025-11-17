"""
Permission Management Schemas
권한 관리 시스템을 위한 Pydantic 스키마 정의
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PermissionLevel(str, Enum):
    """권한 레벨 열거형"""
    VIEWER = "VIEWER"
    EDITOR = "EDITOR"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class RequestStatus(str, Enum):
    """권한 요청 상태 열거형"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# === 권한 관련 스키마 ===

class PermissionCheckRequest(BaseModel):
    """권한 확인 요청"""
    container_id: int = Field(..., description="컨테이너 ID")
    action: str = Field(default="read", description="수행할 작업")
    resource_type: str = Field(default="file", description="리소스 타입")


class PermissionCheckResponse(BaseModel):
    """권한 확인 응답"""
    has_permission: bool = Field(..., description="권한 보유 여부")
    permission_level: Optional[PermissionLevel] = Field(None, description="권한 레벨")
    container_id: int = Field(..., description="컨테이너 ID")
    user_emp_no: str = Field(..., description="사용자 사번")


class PermissionLevelResponse(BaseModel):
    """권한 레벨 조회 응답"""
    user_emp_no: str = Field(..., description="사용자 사번")
    container_id: str = Field(..., description="컨테이너 ID")
    permission_level: Optional[PermissionLevel] = Field(None, description="권한 레벨")
    has_permission: bool = Field(..., description="권한 보유 여부")


class GrantPermissionRequest(BaseModel):
    """권한 부여 요청"""
    user_emp_no: str = Field(..., description="대상 사용자 사번")
    container_id: int = Field(..., description="컨테이너 ID")
    permission_level: PermissionLevel = Field(..., description="부여할 권한 레벨")
    valid_until: Optional[datetime] = Field(None, description="권한 만료일")


class BulkPermissionRequest(BaseModel):
    """일괄 권한 부여 요청"""
    user_emp_nos: List[str] = Field(..., description="대상 사용자 사번 목록")
    container_id: int = Field(..., description="컨테이너 ID")
    permission_level: PermissionLevel = Field(..., description="부여할 권한 레벨")


class AccessibleContainerResponse(BaseModel):
    """접근 가능한 컨테이너 응답"""
    container_id: int = Field(..., description="컨테이너 ID")
    container_name: str = Field(..., description="컨테이너 이름")
    container_path: str = Field(..., description="컨테이너 경로")
    permission_level: PermissionLevel = Field(..., description="권한 레벨")
    is_inherited: bool = Field(..., description="상속된 권한 여부")
    granted_by: Optional[str] = Field(None, description="권한 부여자")
    granted_date: Optional[datetime] = Field(None, description="권한 부여일")


# === 권한 요청 관련 스키마 ===

class CreatePermissionRequestSchema(BaseModel):
    """권한 요청 생성"""
    container_id: int = Field(..., description="컨테이너 ID")
    requested_permission_level: PermissionLevel = Field(..., description="요청할 권한 레벨")
    request_reason: Optional[str] = Field(None, description="요청 사유")


class PermissionRequestResponse(BaseModel):
    """권한 요청 응답"""
    id: int = Field(..., description="요청 ID")
    requester_emp_no: str = Field(..., description="요청자 사번")
    container_id: int = Field(..., description="컨테이너 ID")
    requested_permission_level: PermissionLevel = Field(..., description="요청한 권한 레벨")
    request_reason: Optional[str] = Field(None, description="요청 사유")
    status: RequestStatus = Field(..., description="요청 상태")
    requested_date: datetime = Field(..., description="요청일시")
    reviewed_date: Optional[datetime] = Field(None, description="검토일시")
    reviewer_emp_no: Optional[str] = Field(None, description="검토자 사번")
    review_comment: Optional[str] = Field(None, description="검토 의견")


class ApprovePermissionRequestSchema(BaseModel):
    """권한 요청 승인"""
    comment: Optional[str] = Field(None, description="승인 의견")


class RejectPermissionRequestSchema(BaseModel):
    """권한 요청 거절"""
    comment: str = Field(..., description="거절 사유")


class PermissionRequestStatsResponse(BaseModel):
    """권한 요청 통계 응답"""
    pending_count: int = Field(..., description="대기중인 요청 수")
    approved_count: int = Field(..., description="승인된 요청 수")
    rejected_count: int = Field(..., description="거절된 요청 수")
    my_pending_count: int = Field(..., description="내가 처리해야 할 요청 수")


# === 컨테이너 관련 스키마 ===

class CreateContainerRequest(BaseModel):
    """컨테이너 생성 요청"""
    container_name: str = Field(..., max_length=200, description="컨테이너 이름")
    container_path: str = Field(..., max_length=1000, description="컨테이너 경로")
    description: Optional[str] = Field(None, description="컨테이너 설명")
    parent_container_id: Optional[int] = Field(None, description="상위 컨테이너 ID")


class UpdateContainerRequest(BaseModel):
    """컨테이너 수정 요청"""
    container_name: Optional[str] = Field(None, max_length=200, description="컨테이너 이름")
    description: Optional[str] = Field(None, description="컨테이너 설명")
    is_active: Optional[bool] = Field(None, description="활성화 상태")


class ContainerResponse(BaseModel):
    """컨테이너 응답"""
    id: int = Field(..., description="컨테이너 ID")
    container_name: str = Field(..., description="컨테이너 이름")
    container_path: str = Field(..., description="컨테이너 경로")
    description: Optional[str] = Field(None, description="컨테이너 설명")
    parent_container_id: Optional[int] = Field(None, description="상위 컨테이너 ID")
    is_active: bool = Field(..., description="활성화 상태")
    created_by: str = Field(..., description="생성자")
    created_date: datetime = Field(..., description="생성일시")
    total_files: Optional[int] = Field(None, description="총 파일 수")
    total_size: Optional[int] = Field(None, description="총 파일 크기")


class ContainerHierarchyResponse(BaseModel):
    """컨테이너 계층 응답"""
    id: int = Field(..., description="컨테이너 ID")
    container_name: str = Field(..., description="컨테이너 이름")
    container_path: str = Field(..., description="컨테이너 경로")
    level: int = Field(..., description="계층 레벨")
    children: List['ContainerHierarchyResponse'] = Field(default=[], description="하위 컨테이너")


class ContainerPermissionResponse(BaseModel):
    """컨테이너 권한 응답"""
    container_id: int = Field(..., description="컨테이너 ID")
    user_emp_no: str = Field(..., description="사용자 사번")
    user_name: str = Field(..., description="사용자 이름")
    permission_level: PermissionLevel = Field(..., description="권한 레벨")
    is_inherited: bool = Field(..., description="상속된 권한 여부")
    granted_by: Optional[str] = Field(None, description="권한 부여자")
    granted_date: Optional[datetime] = Field(None, description="권한 부여일")


class ContainerSearchRequest(BaseModel):
    """컨테이너 검색 요청"""
    query: Optional[str] = Field(None, description="검색어")
    include_inactive: bool = Field(default=False, description="비활성 컨테이너 포함 여부")
    parent_container_id: Optional[int] = Field(None, description="상위 컨테이너 ID로 필터링")


# === 감사 로그 관련 스키마 ===

class AuditLogResponse(BaseModel):
    """감사 로그 응답"""
    id: int = Field(..., description="로그 ID")
    user_emp_no: str = Field(..., description="사용자 사번")
    target_user_emp_no: Optional[str] = Field(None, description="대상 사용자 사번")
    container_id: Optional[int] = Field(None, description="컨테이너 ID")
    action_type: str = Field(..., description="작업 유형")
    resource_type: str = Field(..., description="리소스 유형")
    action_result: str = Field(..., description="작업 결과")
    action_details: Optional[Dict[str, Any]] = Field(None, description="작업 세부사항")
    client_ip: Optional[str] = Field(None, description="클라이언트 IP")
    user_agent: Optional[str] = Field(None, description="사용자 에이전트")
    created_date: datetime = Field(..., description="생성일시")


# Forward reference 처리
ContainerHierarchyResponse.model_rebuild()

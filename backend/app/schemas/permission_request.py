"""
권한 요청 관련 Pydantic 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== Request Schemas ====================

class PermissionRequestCreate(BaseModel):
    """권한 요청 생성"""
    container_id: str = Field(..., description="컨테이너 ID")
    requested_permission_level: str = Field(..., description="요청 권한 레벨 (ADMIN, MANAGER, EDITOR, VIEWER)")
    request_reason: str = Field(..., min_length=10, max_length=500, description="요청 사유")
    business_justification: Optional[str] = Field(None, max_length=1000, description="업무 근거")
    expected_usage_period: Optional[str] = Field(None, max_length=100, description="사용 예정 기간")
    urgency_level: Optional[str] = Field('normal', description="긴급도 (urgent, high, normal, low)")


class PermissionRequestApprove(BaseModel):
    """권한 요청 승인"""
    approval_comment: Optional[str] = Field(None, max_length=500, description="승인 코멘트")


class PermissionRequestReject(BaseModel):
    """권한 요청 거부"""
    rejection_reason: str = Field(..., min_length=10, max_length=500, description="거부 사유")


class BatchApprovalRequest(BaseModel):
    """일괄 승인 요청"""
    request_ids: List[str] = Field(..., min_items=1, description="요청 ID 목록")
    approval_comment: Optional[str] = Field(None, max_length=500, description="승인 코멘트")


class BatchRejectionRequest(BaseModel):
    """일괄 거부 요청"""
    request_ids: List[str] = Field(..., min_items=1, description="요청 ID 목록")
    rejection_reason: str = Field(..., min_length=10, max_length=500, description="거부 사유")


# ==================== Response Schemas ====================

class PermissionRequestResponse(BaseModel):
    """권한 요청 응답"""
    id: int
    request_id: str
    requester_emp_no: str
    requester_name: Optional[str]
    requester_department: Optional[str]
    container_id: str
    container_name: Optional[str]
    current_permission_level: Optional[str]
    requested_permission_level: str
    request_reason: str
    business_justification: Optional[str]
    expected_usage_period: Optional[str]
    urgency_level: str
    status: str
    approver_emp_no: Optional[str]
    approver_name: Optional[str]
    approval_comment: Optional[str]
    rejection_reason: Optional[str]
    auto_approved: Optional[bool]
    requested_at: Optional[str]
    processed_at: Optional[str]
    expires_at: Optional[str]

    class Config:
        from_attributes = True


class PermissionRequestListResponse(BaseModel):
    """권한 요청 목록 응답"""
    requests: List[PermissionRequestResponse]
    total_count: int
    pending_count: Optional[int] = None


class PermissionRequestStatistics(BaseModel):
    """권한 요청 통계"""
    total_requests: int
    pending: int
    approved: int
    rejected: int
    cancelled: int
    avg_processing_hours: float


class PermissionRequestCreateResponse(BaseModel):
    """권한 요청 생성 응답"""
    success: bool
    message: str
    request_id: str
    auto_approved: bool = False


class PermissionRequestActionResponse(BaseModel):
    """권한 요청 작업 응답 (승인/거부/취소)"""
    success: bool
    message: str
    request_id: str


class BatchActionResponse(BaseModel):
    """일괄 작업 응답"""
    success: bool
    message: str
    processed_count: int
    failed_requests: Optional[List[str]] = None


# ==================== Auto Approval Rule Schemas ====================

class AutoApprovalRuleCreate(BaseModel):
    """자동 승인 규칙 생성"""
    rule_name: str = Field(..., max_length=200, description="규칙 이름")
    description: Optional[str] = Field(None, description="규칙 설명")
    priority: int = Field(0, description="우선순위 (높을수록 먼저 적용)")
    conditions: dict = Field(..., description="승인 조건 (JSON)")
    action: str = Field('auto_approve', description="작업 (auto_approve, require_approval)")


class AutoApprovalRuleUpdate(BaseModel):
    """자동 승인 규칙 수정"""
    rule_name: Optional[str] = Field(None, max_length=200, description="규칙 이름")
    description: Optional[str] = Field(None, description="규칙 설명")
    is_active: Optional[bool] = Field(None, description="활성 상태")
    priority: Optional[int] = Field(None, description="우선순위")
    conditions: Optional[dict] = Field(None, description="승인 조건")
    action: Optional[str] = Field(None, description="작업")


class AutoApprovalRuleResponse(BaseModel):
    """자동 승인 규칙 응답"""
    id: int
    rule_id: str
    rule_name: str
    description: Optional[str]
    is_active: bool
    priority: int
    conditions: dict
    action: str
    created_by: Optional[str]
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True

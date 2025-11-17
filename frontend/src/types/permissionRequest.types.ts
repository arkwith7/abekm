// 권한 요청 관련 타입 정의

export type PermissionRequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED' | 'EXPIRED';
export type PermissionLevel = 'VIEWER' | 'EDITOR' | 'MANAGER' | 'ADMIN';

export interface PermissionRequest {
  request_id: string;
  user_id: string;
  user_emp_no: string;
  user_name?: string;
  user_department?: string;
  // Backend response fields (새 스키마)
  requester_emp_no?: string;
  requester_name?: string;
  requester_department?: string;
  container_id: string;
  container_name?: string;
  requested_role_id: string;
  requested_role_name?: string;
  requested_permission_level?: string;  // 백엔드 새 필드
  reason: string;
  request_reason?: string;  // 백엔드 새 필드
  status: PermissionRequestStatus;
  requested_at: string;
  processed_at?: string;
  processed_by?: string;
  processor_name?: string;
  rejection_reason?: string;
  auto_approved: boolean;
  expires_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PermissionRequestCreate {
  container_id: string;
  requested_permission_level: string;  // ✅ 백엔드 스키마와 일치
  request_reason: string;              // ✅ 백엔드 스키마와 일치
  business_justification?: string;     // 선택적 필드
  expected_usage_period?: string;      // 선택적 필드
  urgency_level?: string;              // 선택적 필드
}

export interface PermissionRequestApprove {
  approver_comment?: string;
}

export interface PermissionRequestReject {
  rejection_reason: string;
}

export interface BatchApprovalRequest {
  request_ids: string[];
  approver_comment?: string;
}

export interface BatchRejectionRequest {
  request_ids: string[];
  rejection_reason: string;
}

export interface PermissionRequestStatistics {
  total_requests: number;
  pending_requests: number;
  approved_requests: number;
  rejected_requests: number;
  auto_approved_requests: number;
  avg_processing_time_hours?: number;
  requests_by_status: {
    status: PermissionRequestStatus;
    count: number;
  }[];
  requests_by_container: {
    container_id: string;
    container_name: string;
    count: number;
  }[];
}

export interface PermissionRequestListResponse {
  success: boolean;
  requests: PermissionRequest[];
  total: number;
  page: number;
  size: number;
}

export interface PermissionRequestResponse {
  success: boolean;
  request: PermissionRequest;
  message?: string;
}

export interface PermissionRequestFilter {
  status?: PermissionRequestStatus;
  container_id?: string;
  user_emp_no?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  size?: number;
}

// 자동 승인 규칙
export interface AutoApprovalRule {
  rule_id: string;
  rule_name: string;
  role_id: string;
  role_name?: string;
  conditions: Record<string, any>;
  priority: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 권한 감사 로그
export interface PermissionAuditLog {
  log_id: string;
  request_id: string;
  action: 'CREATE' | 'APPROVE' | 'REJECT' | 'CANCEL' | 'EXPIRE' | 'AUTO_APPROVE';
  performed_by: string;
  performer_name?: string;
  details?: Record<string, any>;
  created_at: string;
}

// 지식관리자 관련 타입 정의


export interface Container {
  id: string;
  name: string;
  description: string;
  parent_id?: string;
  manager_id: string;
  manager_name: string;
  document_count: number;
  user_count: number;
  view_count: number;
  permissions: ContainerPermission[];
  created_at: string;
  updated_at: string;
}

export interface ContainerPermission {
  id: string;
  container_id: string;
  user_id: string;
  user_name: string;
  permission_type: 'read' | 'write' | 'admin';
  granted_by: string;
  granted_at: string;
}

export interface PermissionRequest {
  id: string;
  user_id: string;
  user_name: string;
  user_department: string;
  container_id: string;
  container_name: string;
  permission_type: 'read' | 'write';
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_at: string;
  processed_at?: string;
  processed_by?: string;
  processing_note?: string;
}

export interface QualityMetric {
  document_id: string;
  document_title: string;
  author_name: string;
  average_rating: number;
  rating_count: number;
  view_count: number;
  feedback_count: number;
  quality_score: number;
  issues: QualityIssue[];
  last_reviewed: string;
}

export interface QualityIssue {
  type: 'low_rating' | 'outdated' | 'incomplete' | 'duplicate';
  severity: 'low' | 'medium' | 'high';
  description: string;
  suggestion: string;
}

export interface UserSupport {
  id: string;
  user_id: string;
  user_name: string;
  user_department: string;
  category: 'upload' | 'search' | 'permission' | 'technical' | 'other';
  title: string;
  description: string;
  status: 'new' | 'in_progress' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  assigned_to?: string;
  resolution?: string;
  created_at: string;
  updated_at: string;
}

export interface ManagementStats {
  container_count: number;
  pending_requests: number;
  quality_issues: number;
  active_users: number;
  monthly_uploads: number;
  monthly_approvals: number;
  user_inquiries: number;
}

export interface ContainerTree {
  id: string;
  name: string;
  children: ContainerTree[];
  document_count: number;
  user_count: number;
  is_managed: boolean;
}

// 팀 멤버 정보
export interface TeamMember {
  user_id: string;
  name: string;
  employee_id: string;
  department: string;
  position: string;
  email: string;
}

// 사용자 권한 정보
export interface UserPermission {
  id: string;
  user_id: string;
  user_name?: string;
  department?: string;
  container_id: string;
  container_name?: string;
  permission: 'read' | 'write' | 'admin' | 'none';
  granted_at: string;
  granted_by: string;
  valid_until?: string;
}

// 문서 분석 데이터
export interface DocumentAnalytics {
  total_documents: number;
  pending_documents: number;
  monthly_views: number;
  average_rating: number;
  popular_documents: Array<{
    title: string;
    views: number;
  }>;
}

// 지식관리자용 Document 타입 (user.types의 Document와 별도)
export interface ManagerDocument {
  id: string;
  title: string;
  description?: string;
  uploaded_by: string;
  uploaded_at: string;
  status: 'active' | 'pending' | 'rejected' | 'archived';
  container_path?: string;
  view_count: number;
  rating: number;
  file_size: number;
  file_type: string;
  rejection_reason?: string;
}

// ========== Phase 2: 문서 접근 제어 ==========

/**
 * 문서 접근 레벨
 */
export type AccessLevel = 'public' | 'restricted' | 'private';

/**
 * 접근 규칙 타입
 */
export type RuleType = 'user' | 'department';

/**
 * 권한 레벨 (계층 구조: view < download < edit)
 */
export type PermissionLevel = 'view' | 'download' | 'edit';

/**
 * 문서 접근 규칙
 */
export interface DocumentAccessRule {
  rule_id: number;
  file_bss_info_sno: number;
  access_level: AccessLevel;
  rule_type?: RuleType;
  target_id?: string;  // 사번 또는 부서명
  permission_level?: PermissionLevel;
  is_inherited: 'Y' | 'N';
  metadata?: {
    description?: string;
    source?: 'container' | 'manual';
    container_permission_level?: string;
    [key: string]: any;
  };
  created_by: string;
  created_date: string;
  last_modified_by?: string;
  last_modified_date?: string;
}

/**
 * 접근 규칙 생성 요청
 */
export interface AccessRuleCreateRequest {
  access_level: AccessLevel;
  rule_type?: RuleType;
  target_id?: string;
  permission_level?: PermissionLevel;
  is_inherited?: 'Y' | 'N';
  metadata?: Record<string, any>;
}

/**
 * 접근 규칙 수정 요청
 */
export interface AccessRuleUpdateRequest {
  access_level?: AccessLevel;
  rule_type?: RuleType;
  target_id?: string;
  permission_level?: PermissionLevel;
  is_inherited?: 'Y' | 'N';
  metadata?: Record<string, any>;
}

/**
 * 접근 가능한 문서 정보
 */
export interface AccessibleDocument {
  file_bss_info_sno: number;
  file_lgc_nm: string;
  file_psl_nm: string;
  file_extsn: string;
  knowledge_container_id?: string;
  created_date: string;
  access_level: AccessLevel;
  permission_level: PermissionLevel;
  is_inherited: 'Y' | 'N';
}

/**
 * 접근 권한 확인 응답
 */
export interface AccessCheckResponse {
  file_bss_info_sno: number;
  user_emp_no: string;
  has_access: boolean;
  access_level?: AccessLevel;
  permission_level?: PermissionLevel;
  message: string;
}

/**
 * 문서 접근 관리 필터
 */
export interface DocumentAccessFilter {
  access_level?: AccessLevel;
  container_id?: string;
  search_query?: string;
  limit?: number;
  offset?: number;
}

/**
 * 접근 레벨 통계
 */
export interface AccessLevelStats {
  public_count: number;
  restricted_count: number;
  private_count: number;
  total_count: number;
}


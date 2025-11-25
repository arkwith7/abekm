// 지식관리자 관련 API 서비스

import axios from 'axios';
import type {
  AccessCheckResponse,
  AccessibleDocument,
  AccessLevelStats,
  AccessRuleCreateRequest,
  AccessRuleUpdateRequest,
  Container,
  ContainerTree,
  DocumentAccessFilter,
  DocumentAccessRule,
  DocumentAnalytics,
  ManagementStats,
  ManagerDocument,
  PermissionRequest as ManagerPermissionRequest,
  QualityMetric,
  TeamMember,
  UserPermission,
  UserSupport
} from '../types/manager.types';
import type {
  PermissionRequest as PermissionRequestDTO,
  PermissionRequestFilter,
  PermissionRequestStatus
} from '../types/permissionRequest.types';
import { getAuthHeader } from './authService';
import {
  approvePermissionRequest as approvePermissionRequestApi,
  batchApprovePermissionRequests as batchApprovePermissionRequestsApi,
  batchRejectPermissionRequests as batchRejectPermissionRequestsApi,
  getPendingPermissionRequests as fetchPendingPermissionRequests,
  rejectPermissionRequest as rejectPermissionRequestApi
} from './permissionRequestService';

const API_BASE_URL = '/api/v1';

const mapPermissionRequestDto = (dto: PermissionRequestDTO): ManagerPermissionRequest => {
  // Backend의 새 스키마 필드 우선 사용
  const empNo = dto.requester_emp_no || dto.user_emp_no || dto.user_id;
  const userName = dto.requester_name || dto.user_name || empNo || '알 수 없음';
  const department = dto.requester_department || dto.user_department || '';
  const requestReason = dto.request_reason || dto.reason || '';
  const permissionLevel = dto.requested_permission_level || dto.requested_role_id || '';

  const roleId = permissionLevel.toUpperCase();
  const permission_type: 'read' | 'write' =
    roleId.includes('WRITE') || roleId.includes('EDITOR') || roleId.includes('MANAGER') || roleId.includes('ADMIN')
      ? 'write'
      : 'read';

  const mapStatus = (status: string | undefined): ManagerPermissionRequest['status'] => {
    const statusUpper = status?.toUpperCase();
    switch (statusUpper) {
      case 'APPROVED':
        return 'approved';
      case 'REJECTED':
        return 'rejected';
      case 'PENDING':
      default:
        return 'pending';
    }
  };

  return {
    id: dto.request_id,
    user_id: empNo,
    user_name: userName,
    user_department: department,
    container_id: dto.container_id,
    container_name: dto.container_name || dto.container_id,
    permission_type,
    reason: requestReason,
    status: mapStatus(dto.status),
    requested_at: dto.requested_at,
    processed_at: dto.processed_at,
    processed_by: dto.processor_name || dto.processed_by,
    processing_note: dto.rejection_reason
  };
};

interface ContainerPermissionItem {
  user_emp_no: string;
  user_name?: string;
  department?: string;
  position?: string;
  role_id: string;
  role_name: string;
  granted_date?: string;
}

interface ContainerPermissionResponse {
  success: boolean;
  permissions: ContainerPermissionItem[];
  total_count: number;
}

interface UserQuickSearchItem {
  emp_no: string;
  username?: string;
  name?: string;
  department?: string;
  position?: string;
  email?: string;
}

interface UserQuickSearchResponse {
  success: boolean;
  users: UserQuickSearchItem[];
  total: number;
  page: number;
  size: number;
}

export interface UserContainerPermission {
  success: boolean;
  container_id: string;
  user_emp_no: string;
  has_access: boolean;
  role_id: string | null;
  role_name: string | null;
  permission_level: 'ADMIN' | 'MANAGER' | 'EDITOR' | 'VIEWER' | 'NONE';
  can_read: boolean;
  can_write: boolean;
  can_delete: boolean;
  can_manage_permissions: boolean;
  can_create_subcontainer: boolean;
}


// 관리 통계
export const getManagementStats = async (): Promise<ManagementStats> => {
  // TODO: 백엔드 API 구현 필요
  // const response = await axios.get(`/api/manager/stats`);
  // return response.data;

  // 임시 Mock 데이터
  return {
    container_count: 0,
    pending_requests: 0,
    quality_issues: 0,
    active_users: 0,
    monthly_uploads: 0,
    monthly_approvals: 0,
    user_inquiries: 0
  };
};

// 컨테이너 관련 API
export const getContainers = async (): Promise<Container[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/containers/`, {
      headers: getAuthHeader()
    });

    if (response.data.success && response.data.containers) {
      return response.data.containers.map((container: any) => ({
        id: container.container_id,
        name: container.container_name,
        description: container.description || '',
        parent_id: undefined,
        manager_id: '',
        manager_name: '',
        document_count: container.document_count || 0,
        user_count: 0,
        view_count: 0,
        permissions: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }));
    }
    return [];
  } catch (error) {
    console.error('Failed to fetch containers:', error);
    throw error;
  }
};

export const getContainerTree = async (): Promise<ContainerTree[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/containers/hierarchy`, {
      headers: getAuthHeader()
    });

    if (response.data.success && response.data.containers) {
      return response.data.containers.map((container: any) => convertToTreeNode(container));
    }
    return [];
  } catch (error) {
    console.error('Failed to fetch container tree:', error);
    throw error;
  }
};

// Helper function to convert backend response to ContainerTree
const convertToTreeNode = (node: any): ContainerTree => {
  return {
    id: node.container_id,
    name: node.container_name,
    children: node.children ? node.children.map((child: any) => convertToTreeNode(child)) : [],
    document_count: node.document_count || 0,
    user_count: node.user_count || 0,
    is_managed: true
  };
};

// Resolve a container subtree by root name and return all IDs (root + descendants)
export const getContainerSubtreeIdsByName = async (
  targetRootName: string
): Promise<{ rootId: string | null; ids: string[] }> => {
  try {
    const tree = await getContainerTree();

    const findNode = (nodes: ContainerTree[], name: string): ContainerTree | null => {
      for (const n of nodes) {
        if (n.name === name) return n;
        const child = n.children && n.children.length ? findNode(n.children, name) : null;
        if (child) return child;
      }
      return null;
    };

    const collectIds = (node: ContainerTree | null, acc: string[]) => {
      if (!node) return;
      acc.push(node.id);
      if (node.children) node.children.forEach((c) => collectIds(c, acc));
    };

    const root = findNode(tree, targetRootName);
    const ids: string[] = [];
    collectIds(root, ids);
    return { rootId: root ? root.id : null, ids };
  } catch (err) {
    console.error('Failed to resolve container subtree by name:', err);
    return { rootId: null, ids: [] };
  }
};

export const createContainer = async (containerData: {
  name: string;
  description: string;
  parent_id?: string;
}): Promise<Container> => {
  try {
    // Generate unique container ID
    const containerId = `CON_${Date.now().toString(36).toUpperCase()}`;

    const response = await axios.post(
      `${API_BASE_URL}/containers/`,
      {
        container_id: containerId,
        container_name: containerData.name,
        description: containerData.description,
        parent_container_id: containerData.parent_id || null,
        container_type: 'custom',
        access_level: 'internal'
      },
      {
        headers: getAuthHeader()
      }
    );

    if (response.data.success) {
      return {
        id: response.data.container_id,
        name: containerData.name,
        description: containerData.description,
        parent_id: containerData.parent_id,
        manager_id: 'current-user',
        manager_name: '현재사용자',
        document_count: 0,
        user_count: 0,
        view_count: 0,
        permissions: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
    }
    throw new Error('Failed to create container');
  } catch (error) {
    console.error('Failed to create container:', error);
    throw error;
  }
};

export const updateContainer = async (
  containerId: string,
  updates: { name?: string; description?: string }
): Promise<void> => {
  try {
    await axios.put(
      `${API_BASE_URL}/containers/${containerId}`,
      {
        container_name: updates.name,
        description: updates.description
      },
      {
        headers: getAuthHeader()
      }
    );
  } catch (error) {
    console.error('Failed to update container:', error);
    throw error;
  }
};

export const deleteContainer = async (containerId: string): Promise<void> => {
  try {
    await axios.delete(`${API_BASE_URL}/containers/${containerId}`, {
      headers: getAuthHeader()
    });
  } catch (error) {
    console.error('Failed to delete container:', error);
    throw error;
  }
};

export const fetchContainerPermissions = async (containerId: string): Promise<ContainerPermissionItem[]> => {
  try {
    const response = await axios.get<ContainerPermissionResponse>(
      `${API_BASE_URL}/containers/${containerId}/permissions`,
      { headers: getAuthHeader() }
    );
    return response.data.permissions || [];
  } catch (error) {
    console.error('Failed to fetch container permissions:', error);
    throw error;
  }
};

export const getMyContainerPermission = async (containerId: string): Promise<UserContainerPermission> => {
  try {
    const response = await axios.get<UserContainerPermission>(
      `${API_BASE_URL}/containers/${containerId}/my-permission`,
      { headers: getAuthHeader() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to fetch my container permission:', error);
    throw error;
  }
};

export const addContainerPermission = async (
  containerId: string,
  payload: { user_emp_no: string; role_id: string; valid_until?: string | null }
): Promise<void> => {
  try {
    await axios.post(
      `${API_BASE_URL}/containers/${containerId}/permissions`,
      payload,
      { headers: getAuthHeader() }
    );
  } catch (error) {
    console.error('Failed to create container permission:', error);
    throw error;
  }
};

export const updateContainerPermission = async (
  containerId: string,
  userEmpNo: string,
  payload: { role_id: string; valid_until?: string | null }
): Promise<void> => {
  try {
    await axios.put(
      `${API_BASE_URL}/containers/${containerId}/permissions/${userEmpNo}`,
      payload,
      { headers: getAuthHeader() }
    );
  } catch (error) {
    console.error('Failed to update container permission:', error);
    throw error;
  }
};

export const deleteContainerPermission = async (
  containerId: string,
  userEmpNo: string
): Promise<void> => {
  try {
    await axios.delete(
      `${API_BASE_URL}/containers/${containerId}/permissions/${userEmpNo}`,
      { headers: getAuthHeader() }
    );
  } catch (error) {
    console.error('Failed to delete container permission:', error);
    throw error;
  }
};

export const searchUsersForPermissions = async (
  query: string,
  page: number = 1,
  size: number = 10
): Promise<UserQuickSearchResponse> => {
  try {
    const response = await axios.get<UserQuickSearchResponse>(
      `${API_BASE_URL}/users/search`,
      {
        headers: getAuthHeader(),
        params: {
          q: query,
          page,
          size
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to search users:', error);
    throw error;
  }
};

// 사용자 권한 관리 API
export const getUserPermissions = async (containerId?: string): Promise<UserPermission[]> => {
  try {
    // 관리 범위 내 권한 조회 (지식관리자/시스템관리자 공통)
    const response = await axios.get(`${API_BASE_URL}/permissions/managed-scope-permissions`, {
      headers: getAuthHeader(),
      params: containerId ? { container_id: containerId } : {}
    });

    if (response.data.success && response.data.permissions) {
      return response.data.permissions.map((perm: any) => ({
        id: perm.id,
        user_id: perm.user_emp_no,
        user_name: perm.user_name,
        department: perm.department,
        container_id: perm.container_id,
        container_name: perm.container_name,
        permission: perm.permission_type,
        granted_at: perm.granted_at || '',
        granted_by: perm.granted_by || '',
        valid_until: perm.valid_until || undefined
      }));
    }
    return [];
  } catch (error) {
    console.error('Failed to get user permissions:', error);
    return [];
  }
};

export const getTeamMembers = async (): Promise<TeamMember[]> => {
  // TODO: 백엔드에 팀원 목록 API 구현 필요
  // 임시로 빈 배열 반환
  // console.warn('getTeamMembers API not implemented yet');
  return [];
};

export const updateUserPermissions = async (
  userId: string,
  containerId: string,
  permission: string
): Promise<void> => {
  try {
    // 'none'인 경우 권한 삭제
    if (permission === 'none') {
      const response = await axios.delete(
        `${API_BASE_URL}/permissions/revoke/${userId}/${containerId}`,
        { headers: getAuthHeader() }
      );

      if (!response.data) {
        throw new Error('권한 삭제에 실패했습니다.');
      }

      console.log('권한 삭제 성공:', response.data);
      return;
    }

    // 권한 레벨 매핑 (read/write/admin -> VIEWER/EDITOR/ADMIN)
    const permissionLevelMap: { [key: string]: string } = {
      'read': 'VIEWER',
      'write': 'EDITOR',
      'admin': 'ADMIN'
    };

    const permissionLevel = permissionLevelMap[permission] || 'VIEWER';

    const response = await axios.post(
      `${API_BASE_URL}/permissions/grant`,
      {
        user_emp_no: userId,
        container_id: containerId,
        permission_level: permissionLevel,
        valid_until: null
      },
      { headers: getAuthHeader() }
    );

    if (!response.data) {
      throw new Error('권한 부여에 실패했습니다.');
    }

    console.log('권한 부여 성공:', response.data);
  } catch (error) {
    console.error('Failed to update user permissions:', error);
    throw error;
  }
};

export const grantPermission = async (
  userId: string,
  containerId: string,
  permission: string
): Promise<void> => {
  return updateUserPermissions(userId, containerId, permission);
};

// 문서 관리 API
export const getManagedDocuments = async (): Promise<ManagerDocument[]> => {
  // TODO: 실제 API 호출로 교체
  return [
    {
      id: '1',
      title: '신입사원 교육 매뉴얼',
      description: '신입사원을 위한 회사 소개 및 교육 자료',
      uploaded_by: '박인사',
      uploaded_at: '2025-01-20T09:30:00Z',
      status: 'pending',
      container_path: '인사팀 문서/교육 자료',
      view_count: 5,
      rating: 4.2,
      file_size: 2048000,
      file_type: 'pdf'
    },
    {
      id: '2',
      title: 'AWS 보안 가이드라인',
      description: 'AWS 클라우드 환경의 보안 설정 가이드',
      uploaded_by: '김클라우드',
      uploaded_at: '2025-01-19T14:20:00Z',
      status: 'active',
      container_path: '클라우드팀 기술문서/AWS 가이드',
      view_count: 23,
      rating: 4.8,
      file_size: 1536000,
      file_type: 'pdf'
    },
    {
      id: '3',
      title: '채용 프로세스 개선안',
      description: '2025년 채용 프로세스 개선 방안',
      uploaded_by: '최인사',
      uploaded_at: '2025-01-18T16:45:00Z',
      status: 'rejected',
      container_path: '인사팀 문서/채용 절차',
      view_count: 12,
      rating: 3.5,
      file_size: 1024000,
      file_type: 'docx',
      rejection_reason: '내용이 부족하고 구체적인 실행 방안이 필요합니다.'
    }
  ];
};

export const approveDocument = async (documentId: string): Promise<void> => {
  // TODO: 실제 API 호출로 교체
  console.log('Approving document:', documentId);
};

export const rejectDocument = async (documentId: string, reason: string): Promise<void> => {
  // TODO: 실제 API 호출로 교체
  console.log('Rejecting document:', documentId, 'Reason:', reason);
};

export const getDocumentAnalytics = async (): Promise<DocumentAnalytics> => {
  // TODO: 실제 API 호출로 교체
  return {
    total_documents: 156,
    pending_documents: 8,
    monthly_views: 2341,
    average_rating: 4.3,
    popular_documents: [
      { title: 'AWS 보안 가이드라인', views: 156 },
      { title: '신입사원 오리엔테이션', views: 89 },
      { title: '재택근무 정책', views: 67 }
    ]
  };
};

// 권한 승인 관리 - permissionRequestService 연동
export const getPendingPermissionRequests = async (
  filter?: PermissionRequestFilter
): Promise<ManagerPermissionRequest[]> => {
  const response = await fetchPendingPermissionRequests(filter);
  return (response.requests ?? []).map(mapPermissionRequestDto);
};

export const getPermissionRequests = async (
  status?: PermissionRequestStatus,
  filter?: PermissionRequestFilter
): Promise<ManagerPermissionRequest[]> => {
  if (!status || status === 'PENDING') {
    return getPendingPermissionRequests(filter);
  }

  console.warn('getPermissionRequests: 현재 상태 필터는 PENDING만 지원됩니다.', status);
  return [];
};

export const approvePermissionRequest = async (
  requestId: string,
  note?: string
): Promise<void> => {
  await approvePermissionRequestApi(
    requestId,
    note ? { approver_comment: note } : undefined
  );
};

export const rejectPermissionRequest = async (
  requestId: string,
  reason: string
): Promise<void> => {
  await rejectPermissionRequestApi(requestId, { rejection_reason: reason });
};

export const batchProcessPermissionRequests = async (
  requestIds: string[],
  action: 'approve' | 'reject',
  note?: string
): Promise<void> => {
  if (action === 'approve') {
    await batchApprovePermissionRequestsApi({
      request_ids: requestIds,
      approver_comment: note
    });
  } else {
    await batchRejectPermissionRequestsApi({
      request_ids: requestIds,
      rejection_reason: note || '일괄 거부'
    });
  }
};

// 품질 관리
export const getQualityMetrics = async (): Promise<QualityMetric[]> => {
  // TODO: 백엔드 API 구현 필요
  // const response = await axios.get(`/api/manager/quality/metrics`);
  // return response.data;
  return [];
};

export const getDocumentsNeedingReview = async (): Promise<QualityMetric[]> => {
  // TODO: 백엔드 API 구현 필요
  // const response = await axios.get(`/api/manager/quality/review-needed`);
  // return response.data;
  return [];
};

export const updateDocumentQuality = async (documentId: string, qualityData: any): Promise<void> => {
  // TODO: 백엔드 API 구현 필요
  // await axios.put(`/api/manager/quality/documents/${documentId}`, qualityData);
};

export const archiveDocument = async (documentId: string, reason: string): Promise<void> => {
  // TODO: 백엔드 API 구현 필요
  // await axios.post(`/api/manager/quality/documents/${documentId}/archive`, { reason });
};

// 사용자 지원
export const getUserSupportTickets = async (status?: string): Promise<UserSupport[]> => {
  const params = status ? { status } : {};
  const response = await axios.get(`/api/manager/support/tickets`, { params });
  return response.data;
};

export const getNewSupportTickets = async (): Promise<UserSupport[]> => {
  const response = await axios.get(`/api/manager/support/tickets?status=new`);
  return response.data;
};

export const assignSupportTicket = async (ticketId: string, assigneeId: string): Promise<void> => {
  await axios.post(`/api/manager/support/tickets/${ticketId}/assign`, {
    assigned_to: assigneeId
  });
};

export const updateSupportTicketStatus = async (
  ticketId: string,
  status: string,
  resolution?: string
): Promise<void> => {
  await axios.put(`/api/manager/support/tickets/${ticketId}`, {
    status,
    resolution
  });
};

export const addSupportTicketComment = async (ticketId: string, comment: string): Promise<void> => {
  await axios.post(`/api/manager/support/tickets/${ticketId}/comments`, {
    comment
  });
};

// FAQ 관리
export const getFAQs = async (): Promise<any[]> => {
  const response = await axios.get(`/api/manager/support/faqs`);
  return response.data;
};

export const createFAQ = async (faqData: any): Promise<any> => {
  const response = await axios.post(`/api/manager/support/faqs`, faqData);
  return response.data;
};

export const updateFAQ = async (faqId: string, faqData: any): Promise<any> => {
  const response = await axios.put(`/api/manager/support/faqs/${faqId}`, faqData);
  return response.data;
};

// 분석 및 리포트
export const getContainerAnalytics = async (containerId: string): Promise<any> => {
  const response = await axios.get(`/api/manager/analytics/containers/${containerId}`);
  return response.data;
};

export const getQualityReport = async (period: string = '30d'): Promise<any> => {
  const response = await axios.get(`/api/manager/analytics/quality`, {
    params: { period }
  });
  return response.data;
};

export const getUserActivityReport = async (period: string = '30d'): Promise<any> => {
  const response = await axios.get(`/api/manager/analytics/user-activity`, {
    params: { period }
  });
  return response.data;
};

// ========== Phase 2: 문서 접근 제어 API ==========

/**
 * 문서 접근 규칙 생성
 */
export const createDocumentAccessRule = async (
  fileBssInfoSno: number,
  ruleData: AccessRuleCreateRequest
): Promise<DocumentAccessRule> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/documents/${fileBssInfoSno}/access-rules`,
      ruleData,
      { headers: getAuthHeader() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to create document access rule:', error);
    throw error;
  }
};

/**
 * 문서 접근 규칙 조회
 */
export const getDocumentAccessRules = async (
  fileBssInfoSno: number
): Promise<DocumentAccessRule[]> => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/documents/${fileBssInfoSno}/access-rules`,
      { headers: getAuthHeader() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to get document access rules:', error);
    throw error;
  }
};

/**
 * 문서 접근 규칙 수정
 */
export const updateDocumentAccessRule = async (
  ruleId: number,
  ruleData: AccessRuleUpdateRequest
): Promise<DocumentAccessRule> => {
  try {
    const response = await axios.put(
      `${API_BASE_URL}/documents/access-rules/${ruleId}`,
      ruleData,
      { headers: getAuthHeader() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to update document access rule:', error);
    throw error;
  }
};

/**
 * 문서 접근 규칙 삭제
 */
export const deleteDocumentAccessRule = async (ruleId: number): Promise<void> => {
  try {
    await axios.delete(
      `${API_BASE_URL}/documents/access-rules/${ruleId}`,
      { headers: getAuthHeader() }
    );
  } catch (error) {
    console.error('Failed to delete document access rule:', error);
    throw error;
  }
};

/**
 * 사용자의 문서 접근 권한 확인
 */
export const checkDocumentAccess = async (
  fileBssInfoSno: number,
  requiredPermission: 'view' | 'download' | 'edit' = 'view'
): Promise<AccessCheckResponse> => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/documents/${fileBssInfoSno}/check-access`,
      {
        headers: getAuthHeader(),
        params: { required_permission: requiredPermission }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to check document access:', error);
    throw error;
  }
};

/**
 * 접근 가능한 문서 목록 조회
 */
export const getAccessibleDocuments = async (
  filter?: DocumentAccessFilter
): Promise<AccessibleDocument[]> => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/documents/accessible`,
      {
        headers: getAuthHeader(),
        params: {
          access_level: filter?.access_level,
          container_id: filter?.container_id,
          limit: filter?.limit || 100,
          offset: filter?.offset || 0
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to get accessible documents:', error);
    throw error;
  }
};

/**
 * 컨테이너 권한 상속하여 문서 접근 규칙 설정
 */
export const inheritContainerAccess = async (
  fileBssInfoSno: number
): Promise<DocumentAccessRule> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/documents/${fileBssInfoSno}/inherit-container-access`,
      {},
      { headers: getAuthHeader() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to inherit container access:', error);
    throw error;
  }
};

/**
 * 접근 레벨별 문서 통계 조회 (클라이언트 측 계산)
 */
export const getAccessLevelStats = async (
  containerId?: string
): Promise<AccessLevelStats> => {
  try {
    const documents = await getAccessibleDocuments({ container_id: containerId });

    const stats: AccessLevelStats = {
      public_count: 0,
      restricted_count: 0,
      private_count: 0,
      total_count: documents.length
    };

    documents.forEach(doc => {
      switch (doc.access_level) {
        case 'public':
          stats.public_count++;
          break;
        case 'restricted':
          stats.restricted_count++;
          break;
        case 'private':
          stats.private_count++;
          break;
      }
    });

    return stats;
  } catch (error) {
    console.error('Failed to get access level stats:', error);
    return {
      public_count: 0,
      restricted_count: 0,
      private_count: 0,
      total_count: 0
    };
  }
};

/**
 * 문서 검색 (접근 권한 고려)
 */
export const searchAccessibleDocuments = async (
  query: string,
  filter?: DocumentAccessFilter
): Promise<AccessibleDocument[]> => {
  try {
    const documents = await getAccessibleDocuments(filter);

    if (!query) {
      return documents;
    }

    // 클라이언트 측 검색 (백엔드에 검색 API 없는 경우)
    const lowerQuery = query.toLowerCase();
    return documents.filter(doc =>
      doc.file_lgc_nm.toLowerCase().includes(lowerQuery) ||
      doc.file_psl_nm.toLowerCase().includes(lowerQuery)
    );
  } catch (error) {
    console.error('Failed to search accessible documents:', error);
    return [];
  }
};

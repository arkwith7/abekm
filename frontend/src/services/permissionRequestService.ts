// 권한 요청 관련 API 서비스

import axios from 'axios';
import {
  BatchApprovalRequest,
  BatchRejectionRequest,
  PermissionRequest,
  PermissionRequestApprove,
  PermissionRequestCreate,
  PermissionRequestFilter,
  PermissionRequestListResponse,
  PermissionRequestReject,
  PermissionRequestResponse,
  PermissionRequestStatistics,
  PermissionRequestStatus
} from '../types/permissionRequest.types';
import { getAuthHeader } from './authService';
import { getApiUrl } from '../utils/apiConfig';

const getApiBaseUrl = () => {
  const apiUrl = getApiUrl();
  return apiUrl ? `${apiUrl}/api/v1/permission-requests` : '/api/v1/permission-requests';
};
const API_BASE_URL = getApiBaseUrl();

/**
 * 권한 요청 생성
 */
export const createPermissionRequest = async (
  data: PermissionRequestCreate
): Promise<PermissionRequestResponse> => {
  try {
    console.log('🔍 [DEBUG] Permission Request Data:', JSON.stringify(data, null, 2));
    const response = await axios.post(API_BASE_URL, data, {
      headers: getAuthHeader()
    });
    console.log('✅ [DEBUG] Permission Request Response:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('❌ [DEBUG] Failed to create permission request:', error);
    console.error('❌ [DEBUG] Error response:', error.response?.data);
    throw error;
  }
};

/**
 * 내 권한 요청 목록 조회
 */
export const getMyPermissionRequests = async (
  filter?: PermissionRequestFilter
): Promise<PermissionRequest[]> => {
  try {
    const params = new URLSearchParams();
    if (filter?.status) params.append('status', filter.status);
    if (filter?.container_id) params.append('container_id', filter.container_id);
    if (filter?.from_date) params.append('from_date', filter.from_date);
    if (filter?.to_date) params.append('to_date', filter.to_date);
    if (filter?.page) params.append('page', filter.page.toString());
    if (filter?.size) params.append('size', filter.size.toString());

    console.log('🔍 [DEBUG] Fetching my permission requests from:', `${API_BASE_URL}/my-requests?${params.toString()}`);

    const response = await axios.get(`${API_BASE_URL}/my-requests?${params.toString()}`, {
      headers: getAuthHeader()
    });

    console.log('✅ [DEBUG] API Response:', response.data);
    console.log('✅ [DEBUG] Requests array:', response.data.requests);

    const items = response.data.requests || [];

    // 백엔드 응답을 프런트에서 사용하는 PermissionRequest 형태로 변환
    const mapped: PermissionRequest[] = items.map((item: any) => ({
      request_id: item.request_id,
      user_id: '',
      user_emp_no: item.requester_emp_no || '',
      user_name: item.requester_name,
      user_department: item.requester_department,
      requester_emp_no: item.requester_emp_no,
      requester_name: item.requester_name,
      requester_department: item.requester_department,
      container_id: item.container_id,
      container_name: item.container_name,
      requested_role_id: item.requested_permission_level || item.requested_role_id || '',
      requested_role_name: item.requested_permission_level,
      requested_permission_level: item.requested_permission_level,
      reason: item.request_reason || item.reason || '',
      request_reason: item.request_reason || item.reason || '',
      status: (item.status || 'PENDING') as PermissionRequestStatus,
      requested_at: item.requested_at,
      processed_at: item.processed_at,
      processed_by: item.approver_emp_no,
      processor_name: item.approver_name,
      rejection_reason: item.rejection_reason,
      auto_approved: Boolean(item.auto_approved),
      expires_at: item.expires_at,
      created_at: item.requested_at,
      updated_at: item.processed_at || item.requested_at,
    }));

    return mapped;
  } catch (error: any) {
    console.error('❌ [DEBUG] Failed to fetch my permission requests:', error);
    console.error('❌ [DEBUG] Error response:', error.response?.data);
    return [];
  }
};

/**
 * 대기 중인 권한 요청 목록 조회 (관리자용)
 */
export const getPendingPermissionRequests = async (
  filter?: PermissionRequestFilter
): Promise<PermissionRequestListResponse> => {
  try {
    const params = new URLSearchParams();
    if (filter?.container_id) params.append('container_id', filter.container_id);
    if (filter?.user_emp_no) params.append('user_emp_no', filter.user_emp_no);
    if (filter?.from_date) params.append('from_date', filter.from_date);
    if (filter?.to_date) params.append('to_date', filter.to_date);
    if (filter?.page) params.append('page', filter.page.toString());
    if (filter?.size) params.append('size', filter.size.toString());

    const response = await axios.get(`${API_BASE_URL}/pending?${params.toString()}`, {
      headers: getAuthHeader()
    });
    return response.data;
  } catch (error: any) {
    console.error('Failed to fetch pending permission requests:', error);
    throw error;
  }
};

/**
 * 권한 요청 상세 조회
 */
export const getPermissionRequestById = async (
  requestId: string
): Promise<PermissionRequestResponse> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/${requestId}`, {
      headers: getAuthHeader()
    });
    return response.data;
  } catch (error: any) {
    console.error('Failed to fetch permission request:', error);
    throw error;
  }
};

/**
 * 권한 요청 승인
 */
export const approvePermissionRequest = async (
  requestId: string,
  data?: PermissionRequestApprove
): Promise<PermissionRequestResponse> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/${requestId}/approve`,
      data || {},
      {
        headers: getAuthHeader()
      }
    );
    return response.data;
  } catch (error: any) {
    console.error('Failed to approve permission request:', error);
    throw error;
  }
};

/**
 * 권한 요청 거부
 */
export const rejectPermissionRequest = async (
  requestId: string,
  data: PermissionRequestReject
): Promise<PermissionRequestResponse> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/${requestId}/reject`,
      data,
      {
        headers: getAuthHeader()
      }
    );
    return response.data;
  } catch (error: any) {
    console.error('Failed to reject permission request:', error);
    throw error;
  }
};

/**
 * 권한 요청 취소
 */
export const cancelPermissionRequest = async (
  requestId: string
): Promise<PermissionRequestResponse> => {
  try {
    const response = await axios.delete(`${API_BASE_URL}/${requestId}`, {
      headers: getAuthHeader()
    });
    return response.data;
  } catch (error: any) {
    console.error('Failed to cancel permission request:', error);
    throw error;
  }
};

/**
 * 일괄 승인
 */
export const batchApprovePermissionRequests = async (
  data: BatchApprovalRequest
): Promise<PermissionRequestResponse> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/batch-approve`,
      data,
      {
        headers: getAuthHeader()
      }
    );
    return response.data;
  } catch (error: any) {
    console.error('Failed to batch approve permission requests:', error);
    throw error;
  }
};

/**
 * 일괄 거부
 */
export const batchRejectPermissionRequests = async (
  data: BatchRejectionRequest
): Promise<PermissionRequestResponse> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/batch-reject`,
      data,
      {
        headers: getAuthHeader()
      }
    );
    return response.data;
  } catch (error: any) {
    console.error('Failed to batch reject permission requests:', error);
    throw error;
  }
};

/**
 * 권한 요청 통계 조회
 */
export const getPermissionRequestStatistics = async (): Promise<{
  success: boolean;
  statistics: PermissionRequestStatistics;
}> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/statistics/summary`, {
      headers: getAuthHeader()
    });
    return response.data;
  } catch (error: any) {
    console.error('Failed to fetch permission request statistics:', error);
    throw error;
  }
};

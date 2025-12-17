// 시스템 관리자 관련 API 서비스

import axios from 'axios';
import {
  BackupInfo,
  ResourceUsage,
  SecurityAudit,
  SystemConfig,
  SystemMetrics,
  UserRole
} from '../types/admin.types';
import {
  PaginatedUsers,
  PasswordResetResponse,
  UserCreateRequest,
  UserSearchParams,
  User as UserType,
  UserUpdateRequest
} from '../types/user';
import { getApiUrl } from '../utils/apiConfig';

// axios 인스턴스 생성
const api = axios.create({
  baseURL: getApiUrl(),
});

// 시스템 모니터링
export const getSystemMetrics = async (): Promise<SystemMetrics> => {
  const response = await api.get(`/api/admin/system/metrics`);
  return response.data;
};

export const getResourceUsage = async (period: string = '1h'): Promise<ResourceUsage[]> => {
  const response = await api.get(`/api/admin/system/resources`, {
    params: { period }
  });
  return response.data;
};

export const getSystemHealth = async (): Promise<any> => {
  const response = await api.get(`/api/admin/system/health`);
  return response.data;
};

// 사용자 관리
export const userManagementAPI = {
  /**
   * 사용자 목록 조회 (페이징, 검색, 필터 지원)
   */
  getUsers: async (params?: UserSearchParams): Promise<PaginatedUsers> => {
    const response = await api.get(`/api/v1/users/`, { params });
    return response.data;
  },

  /**
   * 특정 사용자 조회
   */
  getUser: async (userId: number): Promise<UserType> => {
    const response = await api.get(`/api/v1/users/${userId}`);
    return response.data;
  },

  /**
   * 사용자 생성
   */
  createUser: async (userData: UserCreateRequest): Promise<UserType> => {
    const response = await api.post(`/api/v1/users/`, userData);
    return response.data;
  },

  /**
   * 사용자 정보 수정
   */
  updateUser: async (userId: number, userData: UserUpdateRequest): Promise<UserType> => {
    const response = await api.put(`/api/v1/users/${userId}`, userData);
    return response.data;
  },

  /**
   * 사용자 삭제 (비활성화)
   */
  deleteUser: async (userId: number): Promise<{ message: string }> => {
    const response = await api.delete(`/api/v1/users/${userId}`);
    return response.data;
  },

  /**
   * 비밀번호 리셋
   */
  resetPassword: async (userId: number, newPassword?: string): Promise<PasswordResetResponse> => {
    const response = await api.post(`/api/v1/users/${userId}/reset-password`, {
      new_password: newPassword
    });
    return response.data;
  },

  /**
   * 사용자 통계 조회
   */
  getUserStats: async (): Promise<{
    total: number;
    active: number;
    inactive: number;
    admin: number;
    departments: number;
  }> => {
    // 전체 사용자 조회 (최대 100개씩, 통계 계산용)
    const response = await api.get(`/api/v1/users/`, { params: { page: 1, size: 100 } });
    const data: PaginatedUsers = response.data;
    const users = data.items;

    // 활성/비활성 사용자 수 계산
    const active = users.filter(u => u.is_active).length;
    const inactive = users.filter(u => !u.is_active).length;

    // 관리자 수 계산
    const admin = users.filter(u => u.is_admin || u.role === 'ADMIN').length;

    // 부서 수 계산 (중복 제거)
    const departments = new Set(users.map(u => u.dept_name).filter(Boolean)).size;

    return {
      total: data.total,  // 백엔드에서 제공하는 전체 사용자 수 사용
      active: active,
      inactive: inactive,
      admin: admin,
      departments: departments
    };
  },

  /**
   * 일괄 사용자 삭제
   */
  bulkDeleteUsers: async (userIds: number[]): Promise<{
    success: boolean;
    message: string;
    processed_count: number;
    failed_count: number;
    errors: string[];
  }> => {
    const response = await api.post(`/api/v1/users/bulk-delete`, { user_ids: userIds });
    return response.data;
  },

  /**
   * 일괄 권한 변경
   */
  bulkUpdateRole: async (userIds: number[], isAdmin: boolean): Promise<{
    success: boolean;
    message: string;
    processed_count: number;
    failed_count: number;
    errors: string[];
  }> => {
    const response = await api.post(`/api/v1/users/bulk-update-role`, {
      user_ids: userIds,
      is_admin: isAdmin
    });
    return response.data;
  },

  /**
   * 부서 목록 조회 (필터용)
   */
  getDepartments: async (): Promise<{ code: string; name: string }[]> => {
    const response = await api.get(`/api/v1/users/filters/departments`);
    return response.data.departments;
  },

  /**
   * 직급 목록 조회 (필터용)
   */
  getPositions: async (): Promise<{ code: string; name: string }[]> => {
    const response = await api.get(`/api/v1/users/filters/positions`);
    return response.data.positions;
  }
};

// 기존 함수들 (하위 호환성 유지)
export const getAllUsers = async (): Promise<UserType[]> => {
  const response = await userManagementAPI.getUsers({ page: 1, size: 1000 });
  return response.items;
};

export const getUserById = async (userId: string): Promise<UserType> => {
  return userManagementAPI.getUser(parseInt(userId));
};

export const createUser = async (userData: Partial<UserType>): Promise<UserType> => {
  return userManagementAPI.createUser(userData as UserCreateRequest);
};

export const updateUser = async (userId: string, userData: Partial<UserType>): Promise<UserType> => {
  return userManagementAPI.updateUser(parseInt(userId), userData as UserUpdateRequest);
};

export const deleteUser = async (userId: string): Promise<void> => {
  await userManagementAPI.deleteUser(parseInt(userId));
};

export const deactivateUser = async (userId: string): Promise<void> => {
  await userManagementAPI.updateUser(parseInt(userId), { is_active: false });
};

export const activateUser = async (userId: string): Promise<void> => {
  await userManagementAPI.updateUser(parseInt(userId), { is_active: true });
};

export const resetUserPassword = async (userId: string): Promise<{ temporary_password: string }> => {
  const response = await userManagementAPI.resetPassword(parseInt(userId));
  return { temporary_password: response.temporary_password || '' };
};

// 역할 및 권한 관리
export const getUserRoles = async (): Promise<UserRole[]> => {
  const response = await api.get(`/api/admin/roles`);
  return response.data;
};

export const createUserRole = async (roleData: Partial<UserRole>): Promise<UserRole> => {
  const response = await api.post(`/api/admin/roles`, roleData);
  return response.data;
};

export const updateUserRole = async (roleId: string, roleData: Partial<UserRole>): Promise<UserRole> => {
  const response = await api.put(`/api/admin/roles/${roleId}`, roleData);
  return response.data;
};

export const deleteUserRole = async (roleId: string): Promise<void> => {
  await api.delete(`/api/admin/roles/${roleId}`);
};

export const assignUserRole = async (userId: string, roleId: string): Promise<void> => {
  await api.post(`/api/admin/users/${userId}/roles`, { role_id: roleId });
};

export const removeUserRole = async (userId: string, roleId: string): Promise<void> => {
  await api.delete(`/api/admin/users/${userId}/roles/${roleId}`);
};

// 시스템 설정
export const getSystemConfig = async (): Promise<SystemConfig> => {
  const response = await api.get(`/api/admin/system/config`);
  return response.data;
};

export const updateSystemConfig = async (configData: Partial<SystemConfig>): Promise<SystemConfig> => {
  const response = await api.put(`/api/admin/system/config`, configData);
  return response.data;
};

export const getAIModelConfig = async (): Promise<any> => {
  const response = await api.get(`/api/admin/system/ai-config`);
  return response.data;
};

export const updateAIModelConfig = async (configData: any): Promise<any> => {
  const response = await api.put(`/api/admin/system/ai-config`, configData);
  return response.data;
};

// 보안 감사
export const getSecurityAuditLogs = async (days: number = 30): Promise<SecurityAudit[]> => {
  const response = await api.get(`/api/admin/security/audit`, {
    params: { days }
  });
  return response.data;
};

export const getFailedLoginAttempts = async (): Promise<SecurityAudit[]> => {
  const response = await api.get(`/api/admin/security/failed-logins`);
  return response.data;
};

export const getSecurityEvents = async (eventType?: string): Promise<SecurityAudit[]> => {
  const params = eventType ? { event_type: eventType } : {};
  const response = await api.get(`/api/admin/security/events`, { params });
  return response.data;
};

export const blockIPAddress = async (ipAddress: string, reason: string): Promise<void> => {
  await api.post(`/api/admin/security/block-ip`, {
    ip_address: ipAddress,
    reason
  });
};

export const unblockIPAddress = async (ipAddress: string): Promise<void> => {
  await api.delete(`/api/admin/security/block-ip/${ipAddress}`);
};

// 백업 관리
export const getBackupList = async (): Promise<BackupInfo[]> => {
  const response = await api.get(`/api/admin/backup/list`);
  return response.data;
};

export const createBackup = async (backupType: string, description?: string): Promise<BackupInfo> => {
  const response = await api.post(`/api/admin/backup/create`, {
    backup_type: backupType,
    description
  });
  return response.data;
};

export const restoreBackup = async (backupId: string): Promise<void> => {
  await api.post(`/api/admin/backup/restore/${backupId}`);
};

export const deleteBackup = async (backupId: string): Promise<void> => {
  await api.delete(`/api/admin/backup/${backupId}`);
};

export const downloadBackup = async (backupId: string): Promise<void> => {
  const response = await api.get(`/api/admin/backup/download/${backupId}`, {
    responseType: 'blob'
  });

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `backup_${backupId}.zip`);
  document.body.appendChild(link);
  link.click();
  link.remove();
};

// 데이터베이스 관리
export const getDatabaseStatus = async (): Promise<any> => {
  const response = await api.get(`/api/admin/database/status`);
  return response.data;
};

export const optimizeDatabase = async (): Promise<void> => {
  await api.post(`/api/admin/database/optimize`);
};

export const reindexDatabase = async (): Promise<void> => {
  await api.post(`/api/admin/database/reindex`);
};

export const getDatabaseStatistics = async (): Promise<any> => {
  const response = await api.get(`/api/admin/database/statistics`);
  return response.data;
};

// 로그 관리
export const getSystemLogs = async (level?: string, limit: number = 100): Promise<any[]> => {
  const params = { limit, ...(level && { level }) };
  const response = await api.get(`/api/admin/logs/system`, { params });
  return response.data;
};

export const getErrorLogs = async (limit: number = 100): Promise<any[]> => {
  const response = await api.get(`/api/admin/logs/errors`, {
    params: { limit }
  });
  return response.data;
};

export const clearLogs = async (logType: string): Promise<void> => {
  await api.delete(`/api/admin/logs/${logType}`);
};

// 통계 및 분석
export const getUsageStatistics = async (period: string = '30d'): Promise<any> => {
  const response = await api.get(`/api/admin/analytics/usage`, {
    params: { period }
  });
  return response.data;
};

export const getPerformanceReport = async (period: string = '30d'): Promise<any> => {
  const response = await api.get(`/api/admin/analytics/performance`, {
    params: { period }
  });
  return response.data;
};

export const getStorageAnalytics = async (): Promise<any> => {
  const response = await api.get(`/api/admin/analytics/storage`);
  return response.data;
};

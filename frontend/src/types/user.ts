/**
 * 사용자 관리 타입 정의
 */

export type UserRole = 'USER' | 'MANAGER' | 'ADMIN';
export type UserStatus = 'active' | 'inactive' | 'suspended';

export interface User {
  id: number;
  username: string;
  emp_no: string;
  emp_name: string | null;
  email: string;
  mbtlno: string | null;      // 휴대폰번호
  dept_name: string | null;
  position_name: string | null;
  role: UserRole;
  is_active: boolean;
  is_admin: boolean;
  last_login: string | null;
  created_date: string;
  last_modified_date: string;
  failed_login_attempts?: number;
  account_locked_until?: string | null;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface UserCreateRequest {
  username: string;
  email: string;
  emp_no: string;
  password: string;
  is_admin?: boolean;
}

export interface UserUpdateRequest {
  username?: string;
  email?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

export interface UserSearchParams {
  page?: number;
  size?: number;
  search?: string;
  dept_cd?: string;
  dept_nm?: string;
  postn_cd?: string;
  postn_nm?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

export interface PasswordResetResponse {
  message: string;
  temporary_password?: string;
}

/**
 * User 객체의 상태를 계산하는 유틸리티 함수
 */
export function getUserStatus(user: User): UserStatus {
  if (user.account_locked_until) {
    const lockedUntil = new Date(user.account_locked_until);
    if (lockedUntil > new Date()) {
      return 'suspended';
    }
  }
  return user.is_active ? 'active' : 'inactive';
}

/**
 * 역할을 한글로 변환
 */
export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    'ADMIN': '관리자',
    'MANAGER': '매니저',
    'USER': '사용자'
  };
  return labels[role] || '사용자';
}

/**
 * 상태를 한글로 변환
 */
export function getStatusLabel(status: UserStatus): string {
  const labels: Record<UserStatus, string> = {
    'active': '활성',
    'inactive': '비활성',
    'suspended': '정지'
  };
  return labels[status] || '알 수 없음';
}

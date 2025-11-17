/**
 * 인증 관련 유틸리티 함수들
 */

import { clearAllAuthStorage, getAccessToken } from './tokenStorage';

/**
 * 401 Unauthorized 응답 처리
 * 토큰 제거, 세션 무효화 이벤트 발송, 로그인 페이지로 리다이렉트
 */
export const handleUnauthorized = (): void => {
  console.warn('🔐 인증 실패 - 로그인 페이지로 리다이렉트');

  // 모든 토큰 제거
  clearAllAuthStorage();
  localStorage.removeItem('csrf_token');

  // 세션 무효화 이벤트 발송
  window.dispatchEvent(new CustomEvent('session:invalid', { detail: { status: 401 } }));

  // 로그인 페이지로 리다이렉트
  window.location.href = '/login';
};

/**
 * fetch 응답에서 401 상태 체크 및 처리
 * @param response fetch Response 객체
 * @returns 401인 경우 true, 그렇지 않으면 false
 */
export const checkAndHandleUnauthorized = (response: Response): boolean => {
  if (response.status === 401) {
    handleUnauthorized();
    return true;
  }
  return false;
};

/**
 * 인증 헤더 생성 유틸리티
 * @returns Authorization 헤더가 포함된 객체
 */
export const getAuthHeaders = (): { [key: string]: string } => {
  const headers: { [key: string]: string } = {
    'Content-Type': 'application/json'
  };
  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

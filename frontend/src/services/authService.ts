import axios from 'axios';
import {
  clearAllLocalStorage,
  getAccessToken,
  getAccessTokenExpiry,
  getRefreshToken,
  getRefreshTokenExpiry,
  getUserInfo,
  setAccessToken,
  setAccessTokenExpiry,
  setRefreshToken,
  setRefreshTokenExpiry,
  setUserInfo
} from '../utils/tokenStorage';
import { resetSessionState } from './userService';
import { getApiUrl } from '../utils/apiConfig';

export interface LoginRequest {
  employeeId: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  refresh_token_expires_in?: number;
  user_info: {
    id: number;
    username: string;
    email: string;
    emp_no: string;
    is_active: boolean;
    is_admin: boolean;
    last_login: string | null;
    emp_name: string | null;
    dept_name: string | null;
    position_name: string | null;
    role: string;
  };
}

export const authService = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    try {
      // 백엔드 API 형식에 맞게 변환 (emp_no 필드 사용)
      const loginData = {
        emp_no: credentials.employeeId,  // 백엔드가 기대하는 emp_no 필드명 사용
        password: credentials.password
      };

      const apiBaseUrl = getApiUrl();
      const response = await axios.post(`${apiBaseUrl}/api/v1/auth/login`, loginData, {
        headers: {
          'Content-Type': 'application/json'
        },
        withCredentials: true
      });

      // 성공적으로 응답받으면 토큰 저장
      if (response.data.access_token) {
        // 세션 상태 초기화 (이전 세션 만료 상태 클리어)
        resetSessionState();

        const expirationTime = Date.now() + (response.data.expires_in * 1000);
        setAccessToken(response.data.access_token);
        setAccessTokenExpiry(expirationTime.toString());
        setUserInfo(JSON.stringify(response.data.user_info));
        if (response.data.refresh_token) {
          const refreshExpiry = response.data.refresh_token_expires_in
            ? Date.now() + (response.data.refresh_token_expires_in * 1000)
            : expirationTime;
          setRefreshToken(response.data.refresh_token);
          setRefreshTokenExpiry(refreshExpiry.toString());
        }
        // CSRF 토큰 저장 (백엔드에서 응답으로 제공)
        if (response.data.csrf_token) {
          localStorage.setItem('csrf_token', response.data.csrf_token);
          // 쿠키로도 설정하여 백엔드 검증 통과
          document.cookie = `csrf_token=${response.data.csrf_token}; path=/; SameSite=lax`;
        }
        console.log('🔐 로그인 성공 - 토큰 만료 시간:', new Date(expirationTime).toLocaleString());
        console.log('🔄 세션 상태 초기화 완료');
      }

      return response.data;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  },

  logout(clearDocumentsCallback?: () => void): void {
    // 🔒 보안 강화: 로그아웃 시 모든 localStorage/sessionStorage 초기화
    // 이전 세션의 데이터가 남아있지 않도록 완전히 삭제
    clearAllLocalStorage();

    // CSRF 쿠키도 삭제
    document.cookie = 'csrf_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';

    // 선택된 문서 클리어 (제공된 콜백이 있는 경우)
    // Note: localStorage가 이미 초기화되었으므로 메모리 상태만 클리어
    if (clearDocumentsCallback) {
      clearDocumentsCallback();
    }

    console.log('🚪 로그아웃 처리 완료 (전체 localStorage 초기화 포함)');
  },

  getToken(): string | null {
    return getAccessToken();
  },

  getUser(): any {
    const userStr = getUserInfo();
    return userStr ? JSON.parse(userStr) : null;
  },

  isAuthenticated(): boolean {
    const token = this.getToken();
    const expiryTime = getAccessTokenExpiry();

    if (!token) {
      console.log('🔍 토큰이 없음');
      return false;
    }

    // 만료 시간 확인
    if (expiryTime) {
      const currentTime = Date.now();
      const expiry = parseInt(expiryTime);

      if (currentTime >= expiry) {
        console.log('⏰ 토큰 만료 시간 도달:', new Date(expiry).toLocaleString());
        this.logout();
        return false;
      }
    }

    try {
      // JWT 토큰 페이로드 파싱해서 만료 시간 확인 (이중 체크)
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;

      if (payload.exp && payload.exp < currentTime) {
        console.log('⏰ JWT 토큰 만료:', new Date(payload.exp * 1000).toLocaleString());
        this.logout();
        return false;
      }

      return true;
    } catch (error) {
      // 토큰이 유효하지 않은 경우
      console.error('🚫 토큰 파싱 오류:', error);
      this.logout();
      return false;
    }
  },

  // 토큰 만료까지 남은 시간 반환 (분 단위)
  getTimeUntilExpiry(): number | null {
    const expiryTime = getAccessTokenExpiry();
    if (!expiryTime) return null;

    const currentTime = Date.now();
    const expiry = parseInt(expiryTime);
    const remainingTime = expiry - currentTime;

    return Math.max(0, Math.floor(remainingTime / (1000 * 60))); // 분 단위로 반환
  },

  // 남은 시간(초) 계산 (정밀 카운트다운용)
  getTimeUntilExpirySeconds(): number | null {
    const expiryTime = getAccessTokenExpiry();
    if (!expiryTime) return null;
    const currentTime = Date.now();
    const expiry = parseInt(expiryTime);
    const remaining = Math.max(0, Math.floor((expiry - currentTime) / 1000));
    return remaining;
  },

  // (미구현) 서버 세션 연장/토큰 재발급 추상화 - refresh 엔드포인트 도입시 구현
  async attemptSilentRefresh(): Promise<boolean> {
    const token = this.getToken();
    const expiryTime = getAccessTokenExpiry();
    if (token && expiryTime) {
      const remainingMs = parseInt(expiryTime) - Date.now();
      // 만료 2분 이내면 미리 갱신 시도
      if (remainingMs < 2 * 60 * 1000) {
        const result = await this.refreshAccessToken();
        return result === true || result === 'no_refresh_needed';
      }
      return true;
    }
    const result = await this.refreshAccessToken();
    return result === true || result === 'no_refresh_needed';
  },

  async refreshAccessToken(): Promise<boolean | 'no_refresh_needed'> {
    const refreshToken = getRefreshToken();
    const refreshTokenExpiry = getRefreshTokenExpiry();

    // 쿠키에서도 refresh token 확인
    const refreshTokenFromCookie = document.cookie
      .split('; ')
      .find(row => row.startsWith('refresh_token='))
      ?.split('=')[1];

    console.log('🔍 Refresh token 상태 점검:', {
      fromLocalStorage: !!refreshToken,
      fromCookie: !!refreshTokenFromCookie,
      expiryTime: refreshTokenExpiry ? new Date(parseInt(refreshTokenExpiry)).toLocaleString() : null,
      isExpired: refreshTokenExpiry ? Date.now() >= parseInt(refreshTokenExpiry) : null
    });

    // 현재 access token이 아직 충분히 유효한지 확인 (5분 이상 남음)
    const currentTokenExpiry = getAccessTokenExpiry();
    if (currentTokenExpiry) {
      const remainingMs = parseInt(currentTokenExpiry) - Date.now();
      if (remainingMs > 5 * 60 * 1000) { // 5분 이상 남았으면
        console.log('🔍 액세스 토큰이 아직 충분히 유효함 (5분+ 남음) - refresh 건너뛰기');
        return 'no_refresh_needed'; // 갱신 불필요를 명시적으로 표시
      }
    }

    // refresh token이 없거나 만료된 경우
    if (!refreshToken || (refreshTokenExpiry && Date.now() >= parseInt(refreshTokenExpiry))) {
      console.log('🚫 refresh token 없거나 만료됨 - 로그아웃 처리');
      this.logout();
      return false;
    }

    try {
      const payload = refreshToken ? { refresh_token: refreshToken } : {};
      const csrfToken = this.getCsrfToken();

      console.log('🔍 Refresh token 요청 준비:', {
        hasRefreshToken: !!refreshToken,
        refreshTokenLength: refreshToken?.length || 0,
        hasCsrfToken: !!csrfToken,
        csrfTokenLength: csrfToken?.length || 0,
        currentCookies: document.cookie,
        payloadHasToken: !!(payload as any).refresh_token,
        actualPayload: payload
      });

      if (!csrfToken) {
        console.warn('⚠️ CSRF 토큰이 없음 - 세션 연장 실패하지만 로그아웃하지 않음');
        return false;
      }

      console.log('🚀 실제 전송할 데이터:', JSON.stringify(payload));

      const res = await axios.post(`/api/v1/auth/refresh`, payload, {
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken || ''
        },
        withCredentials: true
      });

      if (res.data?.access_token) {
        const expirationTime = Date.now() + (res.data.expires_in * 1000);
        setAccessToken(res.data.access_token);
        setAccessTokenExpiry(expirationTime.toString());
        if (res.data.refresh_token) {
          const refreshExpiry = res.data.refresh_token_expires_in
            ? Date.now() + (res.data.refresh_token_expires_in * 1000)
            : expirationTime;
          setRefreshToken(res.data.refresh_token);
          setRefreshTokenExpiry(refreshExpiry.toString());
        }
        // CSRF 토큰도 갱신
        if (res.data.csrf_token) {
          localStorage.setItem('csrf_token', res.data.csrf_token);
          // 쿠키로도 설정하여 백엔드 검증 통과
          document.cookie = `csrf_token=${res.data.csrf_token}; path=/; SameSite=lax`;
        }

        // 토큰 갱신 이벤트 발생 (다른 서비스들이 새 토큰을 사용하도록)
        const tokenUpdatedEvent = new CustomEvent('token:updated', {
          detail: {
            access_token: res.data.access_token,
            expires_in: res.data.expires_in
          }
        });
        window.dispatchEvent(tokenUpdatedEvent);

        console.log('🔄 액세스 토큰 갱신 완료');
        return true;
      }
    } catch (e: any) {
      console.error('🚨 리프레시 토큰 갱신 실패:', {
        status: e?.response?.status,
        message: e?.message,
        data: e?.response?.data,
        hasRefreshToken: !!refreshToken,
        hasCsrfToken: !!this.getCsrfToken(),
        url: e?.config?.url
      });

      // 401, 403 오류만 refresh token이 무효함을 의미 - 로그아웃 처리
      if (e?.response?.status === 401 || e?.response?.status === 403) {
        console.log('🚫 refresh token 무효 - 자동 로그아웃');
        this.logout();
      } else {
        // 다른 에러 (400, 500 등)는 일시적 문제일 수 있으므로 로그아웃하지 않음
        console.warn('⚠️ 리프레시 토큰 갱신 일시적 실패 - 로그아웃하지 않음:', e?.response?.status);
      }
    }
    return false;
  },  // CSRF 토큰 관리
  getCsrfToken(): string | null {
    // 먼저 쿠키에서 확인
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrf_token='))
      ?.split('=')[1];

    // 쿠키에 없으면 localStorage에서 확인
    const localStorageValue = localStorage.getItem('csrf_token');

    console.log('🔍 CSRF 토큰 조회:', {
      fromCookie: !!cookieValue,
      fromLocalStorage: !!localStorageValue,
      allCookies: document.cookie
    });

    return cookieValue || localStorageValue;
  },

  // 토큰 자동 갱신을 위한 응답 인터셉터 설정
  setupResponseInterceptor(axiosInstance: any): void {
    axiosInstance.interceptors.response.use(
      (response: any) => response,
      async (error: any) => {
        const status = error.response?.status;
        const original = error.config;

        // 401: 인증 실패 - 토큰 갱신 시도
        if (status === 401 && !original._retry) {
          original._retry = true;
          const refreshed = await this.refreshAccessToken();
          if (refreshed) {
            const newToken = this.getToken();
            if (newToken) original.headers['Authorization'] = `Bearer ${newToken}`;
            return axiosInstance(original);
          }
          const evt = new CustomEvent('session:invalid', { detail: { status } });
          window.dispatchEvent(evt);
          this.logout();
          import('../utils/navigation').then(({ redirectToLogin }) => redirectToLogin());
        }

        // 403: 권한 없음 - 토큰 갱신 없이 바로 에러 반환
        if (status === 403) {
          console.log('🚫 권한 없음 (403) - 토큰 갱신 시도 안 함');
          // 403은 권한 문제이므로 조용히 에러만 반환
          return Promise.reject(error);
        }

        return Promise.reject(error);
      }
    );
  }
};

// Helper function to get authorization header
export const getAuthHeader = (): Record<string, string> => {
  const token = getAccessToken();
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

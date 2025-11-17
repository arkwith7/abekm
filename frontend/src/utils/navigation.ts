// 전역 네비게이션 유틸리티
// React Router의 navigate 함수를 axios 인터셉터에서 사용할 수 있도록 하는 헬퍼

let globalNavigate: ((path: string, options?: any) => void) | null = null;

export const setGlobalNavigate = (navigate: (path: string, options?: any) => void) => {
  globalNavigate = navigate;
};

export const getGlobalNavigate = () => globalNavigate;

// 인증 실패 시 자동 로그인 페이지로 리다이렉트
export const redirectToLogin = () => {
  if (globalNavigate) {
    console.log('🔀 React Router로 로그인 페이지 이동');
    globalNavigate('/login', { replace: true });
  } else {
    console.log('🔀 window.location으로 로그인 페이지 이동');
    window.location.href = '/login';
  }
};

/**
 * API URL 설정 유틸리티
 * setupProxy.js를 통한 프록시 경로 사용 (개발환경)
 * 또는 직접 환경변수 사용 (프로덕션환경)
 */

export const getApiBaseUrl = (): string => {
  // Docker 환경에서는 REACT_APP_API_URL 환경변수 사용
  // 환경변수가 설정되어 있으면 사용, 없으면 프록시 경로 사용
  const apiUrl = process.env.REACT_APP_API_URL;

  if (apiUrl) {
    // 환경변수가 설정된 경우 (Docker 배포 환경)
    return apiUrl;
  }

  // 로컬 개발 환경: setupProxy.js 프록시 사용
  return '';
};

// 싱글톤으로 API URL 관리
let apiBaseUrl: string | null = null;

export const getApiUrl = (): string => {
  if (!apiBaseUrl) {
    apiBaseUrl = getApiBaseUrl();
    // 필요시 주석 해제하여 디버깅
    // const hasApiUrl = !!process.env.REACT_APP_API_URL;
    // console.log('🔗 API Base URL 설정:', {
    //   mode: hasApiUrl ? 'DOCKER (환경변수 사용)' : 'LOCAL (프록시 사용)',
    //   apiBaseUrl: hasApiUrl ? apiBaseUrl : '(프록시: /api → localhost)',
    //   actualRequests: hasApiUrl ? (apiBaseUrl + '/v1/...') : '/api/v1/...'
    // });
  }
  return apiBaseUrl;
};

// 개발 환경에서 디버깅용 (필요시 주석 해제)
// console.log('🔧 API 설정:', {
//   nodeEnv: process.env.NODE_ENV,
//   reactAppApiUrl: process.env.REACT_APP_API_URL,
//   computed_api_url: getApiBaseUrl(),
//   proxy_path: '/api'
// });

// 일반 사용자 관련 API 서비스

import axios from 'axios';
import { KnowledgeContainer } from '../pages/user/my-knowledge/components/KnowledgeContainerTree';
import { AIChat, Document, Recommendation, SearchResult, UploadProgress, UserActivity } from '../types/user.types';
import { redirectToLogin } from '../utils/navigation';
import { clearAllLocalStorage, getAccessToken } from '../utils/tokenStorage';
import { getApiUrl } from '../utils/apiConfig';

// axios 인스턴스 생성 (baseURL 설정)
export const api = axios.create({
  baseURL: getApiUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// api 인스턴스에 인증 토큰 인터셉터 추가
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 세션 만료 상태 추적 (중복 처리 방지)
let isLoggingOut = false;
let sessionExpiredAt: number | null = null;

// 진행 중인 요청들을 추적하기 위한 AbortController
const pendingRequests = new Set<AbortController>();

// ----------------------------
// 검색 요청 디바운스/캐싱 설정
// ----------------------------
const SEARCH_CACHE_TTL_MS = 5_000; // 동일 파라미터 5초 캐싱
type CachedResponse<T> = { timestamp: number; data: T };

const hybridSearchCache = new Map<string, CachedResponse<any>>();
const hybridSearchInflight = new Map<string, Promise<any>>();
const documentSearchCache = new Map<string, CachedResponse<SearchResult>>();
const documentSearchInflight = new Map<string, Promise<SearchResult>>();

const buildCacheKey = (path: string, payload: unknown) =>
  `${path}:${JSON.stringify(payload)}`;

const setCachedResponse = <T>(
  cache: Map<string, CachedResponse<T>>,
  key: string,
  data: T
) => {
  cache.set(key, { timestamp: Date.now(), data });
};

const tryGetCachedResponse = <T>(
  cache: Map<string, CachedResponse<T>>,
  key: string
): T | null => {
  const cached = cache.get(key);
  if (!cached) {
    return null;
  }
  if (Date.now() - cached.timestamp > SEARCH_CACHE_TTL_MS) {
    cache.delete(key);
    return null;
  }
  return cached.data;
};

// 요청 취소 함수
const cancelAllPendingRequests = () => {
  console.log(`🛑 ${pendingRequests.size}개의 진행 중인 요청을 취소합니다`);
  pendingRequests.forEach(controller => {
    try {
      controller.abort();
    } catch (error) {
      // 이미 완료된 요청은 무시
    }
  });
  pendingRequests.clear();
};

// 세션 만료 처리 (한 번만 실행되도록)
const handleSessionExpiry = () => {
  if (isLoggingOut) {
    console.log('🔄 이미 로그아웃 처리 중...');
    return;
  }

  isLoggingOut = true;
  sessionExpiredAt = Date.now();

  console.log('🚪 세션 만료 - 즉시 로그아웃 처리 시작');

  // 1. 모든 진행 중인 요청 취소
  cancelAllPendingRequests();

  // 2. 🔒 보안 강화: 전체 localStorage/sessionStorage 초기화
  clearAllLocalStorage();

  // 3. 글로벌 이벤트 발생 (다른 컴포넌트들이 상태를 정리할 수 있도록)
  window.dispatchEvent(new CustomEvent('session:expired'));

  // 4. 즉시 로그인 페이지로 리다이렉트
  setTimeout(() => {
    redirectToLogin();
    // 상태 초기화 (리다이렉트 후 즉시)
    setTimeout(() => {
      isLoggingOut = false;
      sessionExpiredAt = null;
      console.log('🔄 세션 상태 초기화 완료');
    }, 1000); // 5초에서 1초로 단축
  }, 100);
};

// 세션 상태 초기화 함수 (외부에서 호출 가능)
export const resetSessionState = () => {
  isLoggingOut = false;
  sessionExpiredAt = null;
  console.log('🔄 세션 상태 초기화 완료');
};

// 현재 세션 상태 확인 함수
export const getSessionState = () => ({
  isLoggingOut,
  sessionExpiredAt,
  pendingRequestsCount: pendingRequests.size
});

// Axios 인터셉터로 인증 토큰 자동 추가
axios.interceptors.request.use((config) => {
  // 로그인 요청과 refresh 요청은 세션 만료 차단에서 예외 처리
  const isAuthRequest = config.url?.includes('/auth/login') || config.url?.includes('/auth/refresh');

  // 세션이 만료되었으면 새로운 요청을 차단 (인증 요청 제외)
  if (!isAuthRequest && isLoggingOut && sessionExpiredAt && Date.now() - sessionExpiredAt < 5000) {
    console.log('🛑 세션 만료로 인해 새 요청 차단:', config.url);
    const error = new Error('Session expired - blocking new requests');
    error.name = 'SessionExpiredError';
    throw error;
  }

  const token = getAccessToken();
  if (token && !isAuthRequest) { // 인증 요청에는 토큰을 추가하지 않음
    config.headers.Authorization = `Bearer ${token}`;
  }

  // AbortController 추가하여 요청 추적
  if (!config.signal) {
    const controller = new AbortController();
    config.signal = controller.signal;
    pendingRequests.add(controller);

    // 요청 완료 시 추적에서 제거 (안전한 타입 체크)
    const signal = config.signal;
    if (signal && typeof signal.addEventListener === 'function') {
      signal.addEventListener('abort', () => {
        pendingRequests.delete(controller);
      });
    }
  }

  return config;
});

// Axios 응답 인터셉터로 401 오류 자동 처리 (개선된 버전)
axios.interceptors.response.use(
  (response) => {
    // 정상 응답시 요청을 추적에서 제거
    const controller = Array.from(pendingRequests).find(c =>
      c.signal === response.config.signal
    );
    if (controller) {
      pendingRequests.delete(controller);
    }
    return response;
  },
  async (error) => {
    const status = error.response?.status;

    console.log('🔍 API 응답 오류:', status, error.config?.url);

    // 요청을 추적에서 제거
    if (error.config?.signal) {
      const controller = Array.from(pendingRequests).find(c =>
        c.signal === error.config.signal
      );
      if (controller) {
        pendingRequests.delete(controller);
      }
    }

    // 이미 로그아웃 처리 중이면 추가 처리하지 않음
    if (isLoggingOut) {
      console.log('🔄 이미 로그아웃 처리 중이므로 오류 무시');
      return Promise.reject(error);
    }

    // 401 오류만 세션 만료 처리 (403은 권한 문제이므로 무시)
    if (status === 401) {
      const isRefreshRequest = error.config?.url?.includes('/auth/refresh');
      const isLoginRequest = error.config?.url?.includes('/auth/login');

      // 로그인 요청의 401은 정상적인 인증 실패이므로 세션 만료 처리하지 않음
      if (isLoginRequest) {
        console.log('🔐 로그인 실패 - 정상적인 인증 오류');
        return Promise.reject(error);
      }

      console.log(`🚨 ${status} 오류 감지 - ${isRefreshRequest ? 'refresh token 만료' : '액세스 토큰 만료'}`);

      // 세션 만료 처리
      handleSessionExpiry();

      // 세션 만료 오류로 즉시 반환 (재시도 없음)
      const sessionError = new Error('Session expired');
      sessionError.name = 'SessionExpiredError';
      return Promise.reject(sessionError);
    }

    // 403은 권한 문제이므로 그냥 에러 반환 (세션 만료 아님)
    if (status === 403) {
      console.log('🚫 권한 없음 (403) - 세션은 유효함');
      return Promise.reject(error);
    }

    // 기타 오류는 그대로 반환
    return Promise.reject(error);
  }
);

// 검색 관련
export const searchDocuments = async (query: string, filters?: any): Promise<SearchResult> => {
  try {
    console.log('🔍 검색 요청:', { query, filters });

    const payload = {
      query,
      limit: filters?.limit || 10,
      threshold: filters?.threshold || 0.7
    };
    const cacheKey = buildCacheKey('/api/v1/search', payload);

    const cached = tryGetCachedResponse(documentSearchCache, cacheKey);
    if (cached) {
      console.log('🔁 검색 캐시 적중');
      return cached;
    }

    const inflight = documentSearchInflight.get(cacheKey);
    if (inflight) {
      console.log('⏳ 동일 검색 요청 진행 중 - 기존 Promise 반환');
      return inflight;
    }

    const requestPromise = api.post(`/api/v1/search`, payload)
      .then((response) => {
        setCachedResponse(documentSearchCache, cacheKey, response.data);
        return response.data;
      })
      .finally(() => {
        documentSearchInflight.delete(cacheKey);
      });

    documentSearchInflight.set(cacheKey, requestPromise);

    const data = await requestPromise;
    console.log('🔍 검색 응답:', data);
    return data;

  } catch (error) {
    console.error('🔍 검색 오류:', error);
    throw error;
  }
};

// 하이브리드 검색 (새로운 고급 검색 API)
export const hybridSearch = async (
  query: string,
  options?: {
    container_ids?: string[];
    search_type?: 'hybrid' | 'vector_only' | 'keyword_only';
    max_results?: number;
    filters?: any;
  }
): Promise<any> => {
  try {
    console.log('🔍 하이브리드 검색 요청:', { query, options });

    const payload = {
      query: query,
      container_ids: options?.container_ids || null,
      search_type: options?.search_type || 'hybrid',
      max_results: options?.max_results || 10,
      filters: options?.filters || null
    };
    const cacheKey = buildCacheKey('/api/v1/search/hybrid', payload);

    const cached = tryGetCachedResponse(hybridSearchCache, cacheKey);
    if (cached) {
      console.log('🔁 하이브리드 검색 캐시 적중');
      return cached;
    }

    const inflight = hybridSearchInflight.get(cacheKey);
    if (inflight) {
      console.log('⏳ 동일 하이브리드 검색 요청 진행 중 - 기존 Promise 사용');
      return inflight;
    }

    const requestPromise = api.post(`/api/v1/search/hybrid`, payload)
      .then((response) => {
        setCachedResponse(hybridSearchCache, cacheKey, response.data);
        return response.data;
      })
      .finally(() => {
        hybridSearchInflight.delete(cacheKey);
      });

    hybridSearchInflight.set(cacheKey, requestPromise);

    const data = await requestPromise;
    console.log('🔍 하이브리드 검색 응답:', data);
    return data;

  } catch (error) {
    console.error('🔍 하이브리드 검색 오류:', error);
    throw error;
  }
};

// 검색 제안 (자동완성)
export const getSearchSuggestions = async (partialQuery: string): Promise<string[]> => {
  try {
    const response = await api.get(`/api/v1/search/suggestions`, {
      params: { partial_query: partialQuery }
    });
    return response.data.suggestions || [];
  } catch (error) {
    console.error('🔍 검색 제안 오류:', error);
    return [];
  }
};

// 문서 관련
export const getDocument = async (id: string): Promise<Document> => {
  const response = await api.get(`/api/v1/documents/${id}`);
  return response.data;
};

// 문서 청크 조회
export const getDocumentChunks = async (
  fileBssInfoSno: number,
  chunkIndex?: number
): Promise<{
  success: boolean;
  document_info: {
    file_bss_info_sno: number;
    file_name: string;
    container_id: string;
  };
  chunks: Array<{
    chunk_sno: number;
    chunk_index: number;
    chunk_text: string;
    chunk_size: number;
    page_number?: number;
    section_title?: string;
    keywords: string[];
    named_entities: string[];
    created_dt?: string;
    last_modified_dt?: string;
  }>;
  total_chunks: number;
  requested_chunk_index?: number;
}> => {
  try {
    const params = new URLSearchParams();
    if (chunkIndex !== undefined) {
      params.append('chunk_index', chunkIndex.toString());
    }

    const url = `/api/v1/documents/${fileBssInfoSno}/chunks${params.toString() ? `?${params.toString()}` : ''}`;
    const response = await api.get(url);
    return response.data;
  } catch (error) {
    console.error('📋 문서 청크 조회 실패:', error);
    throw error;
  }
};

export const getMyDocuments = async (options?: {
  skip?: number;
  limit?: number;
  container_id?: string;
}): Promise<{
  documents: Document[];
  total: number;
  current_page_count: number;
  skip: number;
  limit: number;
  has_next: boolean;
  has_previous: boolean;
}> => {
  try {
    const params = new URLSearchParams();
    if (options?.skip !== undefined) params.append('skip', options.skip.toString());
    if (options?.limit !== undefined) params.append('limit', options.limit.toString());
    if (options?.container_id) params.append('container_id', options.container_id);

    const response = await api.get(`/api/v1/documents?${params.toString()}`);
    console.log('📄 getMyDocuments API 응답:', response.data);

    // API 응답 구조 확인
    const responseData = response.data;
    let documentsData = responseData.documents || [];

    // 배열이 아닌 경우 빈 배열 반환
    if (!Array.isArray(documentsData)) {
      console.warn('Documents data is not an array:', documentsData);
      return {
        documents: [],
        total: 0,
        current_page_count: 0,
        skip: options?.skip || 0,
        limit: options?.limit || 100,
        has_next: false,
        has_previous: false
      };
    }

    // 백엔드 응답을 프론트엔드 형식으로 변환
    const transformedDocuments = documentsData.map((doc: any) => {
      console.log('📄 Raw document data:', doc);

      return {
        id: doc.file_bss_info_sno?.toString() || doc.id?.toString() || 'unknown',
        title: doc.file_lgc_nm || doc.title || doc.sj || 'Untitled',
        file_name: doc.file_lgc_nm || doc.file_name || 'unknown',
        file_size: doc.file_sz || doc.file_size || 0,
        file_extension: doc.file_extsn || doc.file_extension || '',
        container_path: doc.knowledge_container_id || doc.container_path || doc.container_id || '',
        created_at: doc.created_date || doc.created_at || new Date().toISOString(),
        uploaded_by: doc.created_by || doc.uploaded_by || doc.owner_emp_no || 'unknown',
        // 추가 필드들
        description: doc.cn || doc.description || '',
        keywords: doc.kwrd || doc.keywords || '',
        author: doc.authr || doc.author || '',
        category: doc.ctgry_nm || doc.category || '',
        permission_level: doc.permission_level || 'INTERNAL',
        access_count: doc.access_count || 0,
        last_accessed_date: doc.last_accessed_date || null,
      };
    });

    console.log('✅ 변환된 문서 목록:', transformedDocuments);

    return {
      documents: transformedDocuments,
      total: responseData.total || transformedDocuments.length,
      current_page_count: responseData.current_page_count || transformedDocuments.length,
      skip: responseData.skip || options?.skip || 0,
      limit: responseData.limit || options?.limit || 100,
      has_next: responseData.has_next || false,
      has_previous: responseData.has_previous || false
    };

  } catch (error) {
    console.error('❌ getMyDocuments 실패:', error);
    return {
      documents: [],
      total: 0,
      current_page_count: 0,
      skip: options?.skip || 0,
      limit: options?.limit || 100,
      has_next: false,
      has_previous: false
    };
  }
};

// 지식 컨테이너 가져오기
export const getMyContainers = async (): Promise<KnowledgeContainer[]> => {
  try {
    const response = await api.get(`/api/v1/documents/containers`);
    let containersData = response.data?.containers ?? response.data;
    if (!Array.isArray(containersData)) {
      console.warn('Containers data is not an array:', containersData);
      return [];
    }

    const transformedData = containersData.map((item: any) => {
      const permissionFields = [
        'user_permission',
        'permission_level',
        'role_id',
        'role_name',
        'permission_type',
        'access_scope',
        'access_level',
        'default_permission',
        'effective_permission'
      ];

      const normalized = permissionFields
        .map((field) => (item[field] ? item[field].toString().toUpperCase() : ''))
        .filter(Boolean);

      const includesAny = (keyword: string) => normalized.some((value) => value.includes(keyword));

      let permission: KnowledgeContainer['permission'] = 'VIEWER';
      if (includesAny('ADMIN') || includesAny('OWNER') || includesAny('FULL')) {
        permission = 'OWNER';
      } else if (
        includesAny('MANAGER') ||
        includesAny('EDITOR') ||
        includesAny('WRITE') ||
        includesAny('WRITER') ||
        includesAny('CONTRIBUTOR')
      ) {
        permission = 'EDITOR';
      } else if (includesAny('VIEWER') || includesAny('READ')) {
        permission = 'VIEWER';
      }

      const canUpload = Boolean(
        item.can_upload ||
        includesAny('ADMIN') ||
        includesAny('OWNER') ||
        includesAny('MANAGER') ||
        includesAny('EDITOR') ||
        includesAny('WRITE') ||
        includesAny('WRITER') ||
        includesAny('CONTRIBUTOR')
      );

      if (canUpload && permission === 'VIEWER') {
        permission = 'EDITOR';
      }

      const hierarchyPath = item.hierarchy_path || item.org_path || item.path || '';

      return {
        id: item.container_id,
        name: item.container_name || item.name || 'Unknown Container',
        path: hierarchyPath,
        parent_id: item.parent_container_id,
        permission,
        can_upload: canUpload,
        document_count: item.document_count || 0,
        children: [],
      };
    });

    const tree = [];
    const map: { [key: string]: any } = {};

    for (const item of transformedData) {
      map[item.id] = item;
    }

    for (const item of transformedData) {
      if (item.parent_id && map[item.parent_id]) {
        map[item.parent_id].children.push(item);
      } else {
        tree.push(item);
      }
    }

    return tree;

  } catch (error) {
    console.error('Failed to fetch containers:', error);
    // API 실패 시 빈 배열 반환 (하드코딩된 fallback 데이터 제거)
    return [];
  }
};

export const uploadDocument = async (
  file: File,
  container_id: string,
  metadata?: any,
  onProgress?: (progress: UploadProgress) => void
): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('container_id', container_id);

  // 메타데이터 추가
  if (metadata) {
    formData.append('title', metadata.title || file.name);
    formData.append('description', metadata.description || '');
    formData.append('keywords', JSON.stringify(metadata.keywords || []));

    // ✅ 문서 유형 및 처리 옵션 추가
    if (metadata.document_type) {
      formData.append('document_type', metadata.document_type);
    }
    if (metadata.processing_options) {
      formData.append('processing_options', JSON.stringify(metadata.processing_options));
    }

    // category는 하위 호환성을 위해 유지 (옵션)
    if (metadata.category) {
      formData.append('category', metadata.category);
    }

    formData.append('author', metadata.author || '');
    formData.append('language', metadata.language || 'ko');
    formData.append('security_level', metadata.security_level || 'PUBLIC');
    formData.append('tags', JSON.stringify(metadata.tags || []));
  }

  const response = await api.post(`/api/v1/documents/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress({
          file_name: file.name,
          progress,
          status: 'uploading'
        });
      }
    },
  });
  return response.data;
};

export const downloadDocument = async (documentId: string, documentTitle?: string, documentExtension?: string): Promise<void> => {
  console.info('📥 [downloadDocument] 시작 - documentId:', documentId, 'title:', documentTitle, 'ext:', documentExtension);
  const response = await api.get(`/api/v1/documents/${documentId}/download`, {
    responseType: 'blob',
  });

  // 서버가 노출한 헤더에서 파일명/타입 확보 (CORS expose_headers 필요)
  const contentDisposition = response.headers['content-disposition'] || '';
  const contentType = response.headers['content-type'] || response.data?.type || 'application/octet-stream';
  const serverFileNameHeader = response.headers['x-filename'];
  console.info('📥 [downloadDocument] 응답 헤더:', response.headers);

  // 1) 파일명 파싱 (filename* 우선 → filename → X-Filename → document title → 기본값)
  let fileName: string | undefined;
  let match = contentDisposition.match(/filename\*=(?:UTF-8'')?([^;\n]+)/i);
  if (match && match[1]) {
    try { fileName = decodeURIComponent(match[1].trim().replace(/"/g, '')); } catch { /* ignore */ }
  }
  if (!fileName) {
    match = contentDisposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) fileName = match[1];
  }
  if (!fileName && serverFileNameHeader) fileName = serverFileNameHeader;
  // Use document title from the UI as fallback
  if (!fileName && documentTitle) fileName = documentTitle;
  if (!fileName) fileName = `document_${documentId}`;

  console.info('📥 [downloadDocument] 파싱된 기본 파일명:', fileName);

  // 2) 확장자 보정: 파일명이 확장자가 없으면 MIME 또는 document extension 기반으로 추정
  const mimeToExt: Record<string, string> = {
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'application/vnd.ms-powerpoint': 'ppt',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-excel': 'xls',
    'application/pdf': 'pdf',
    'text/plain': 'txt',
  };
  const hasExt = /\.[^./\\]+$/.test(fileName);
  let guessedExt = mimeToExt[contentType.toLowerCase()] || '';

  // Prefer document extension from UI if available and no extension in filename
  if (!hasExt && documentExtension) {
    guessedExt = documentExtension.startsWith('.') ? documentExtension.slice(1) : documentExtension;
  }

  if (!hasExt && guessedExt) {
    fileName = `${fileName}.${guessedExt}`;
  }
  console.info('📥 [downloadDocument] 결정된 파일명/타입:', { fileName, contentType, hasExt, guessedExt });

  // 3) Blob 생성 시 타입 유지 → 브라우저 저장 대화상자에서 형식 인식
  const blob = new Blob([response.data], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', fileName);
  console.info('📥 [downloadDocument] 다운로드 트리거 - 최종 파일명:', fileName);

  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
};

export const deleteDocument = async (documentId: string): Promise<void> => {
  await api.delete(`/api/v1/documents/${documentId}`);
};

// Generic downloader by URL (e.g., chat-generated PPT). Mirrors downloadDocument logic.
export const downloadByUrl = async (url: string, fallbackTitle?: string, fallbackExtension?: string): Promise<void> => {
  console.info('📥 [downloadByUrl] 시작 - url:', url, 'title:', fallbackTitle, 'ext:', fallbackExtension);

  // 상대 경로를 절대 URL로 변환 (프록시 경로 사용)
  let fullUrl = url;
  if (url.startsWith('/api')) {
    fullUrl = url; // 이미 프록시 경로
  } else if (url.startsWith('/')) {
    fullUrl = url; // 프록시를 통해 처리됨
    console.info('📥 [downloadByUrl] 프록시 경로 사용:', fullUrl);
  }

  // 토큰이 필요하지만 포함되지 않았다면 자동으로 추가
  if (fullUrl.startsWith('/api') && !fullUrl.includes('token=')) {
    const token = localStorage.getItem('ABEKM_token');
    if (token) {
      const separator = fullUrl.includes('?') ? '&' : '?';
      fullUrl = `${fullUrl}${separator}token=${encodeURIComponent(token)}`;
      console.info('📥 [downloadByUrl] 토큰 자동 부착:', fullUrl);
    }
  }

  const authToken = localStorage.getItem('ABEKM_token');
  const response = await api.get(fullUrl, {
    responseType: 'blob',
    headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined
  });

  const headers = response.headers || {} as any;
  const contentDisposition = headers['content-disposition'] || '';
  const contentType = headers['content-type'] || response.data?.type || 'application/octet-stream';
  const serverFileNameHeader = headers['x-filename'];
  console.info('📥 [downloadByUrl] 응답 헤더:', headers);

  // Parse filename
  let fileName: string | undefined;
  let match = contentDisposition.match(/filename\*=(?:UTF-8'')?([^;\n]+)/i);
  if (match && match[1]) {
    try { fileName = decodeURIComponent(match[1].trim().replace(/"/g, '')); } catch { /* ignore */ }
  }
  if (!fileName) {
    match = contentDisposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) fileName = match[1];
  }
  if (!fileName && serverFileNameHeader) fileName = serverFileNameHeader;
  if (!fileName && fallbackTitle) fileName = fallbackTitle;
  if (!fileName) {
    // Try to infer from URL path
    try { fileName = decodeURIComponent(url.split('/').pop() || 'download'); } catch { fileName = 'download'; }
  }

  console.info('📥 [downloadByUrl] 파싱된 기본 파일명:', fileName);

  // Extension inference
  const mimeToExt: Record<string, string> = {
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'application/vnd.ms-powerpoint': 'ppt',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-excel': 'xls',
    'application/pdf': 'pdf',
    'text/plain': 'txt',
  };
  const hasExt = /\.[^./\\]+$/.test(fileName);
  let guessedExt = mimeToExt[String(contentType).toLowerCase()] || '';
  if (!hasExt && fallbackExtension) {
    guessedExt = fallbackExtension.startsWith('.') ? fallbackExtension.slice(1) : fallbackExtension;
  }
  if (!hasExt && guessedExt) {
    fileName = `${fileName}.${guessedExt}`;
  }
  console.info('📥 [downloadByUrl] 결정된 파일명/타입:', { fileName, contentType, hasExt, guessedExt });

  const blob = new Blob([response.data], { type: contentType });
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.setAttribute('download', fileName);
  console.info('📥 [downloadByUrl] 다운로드 트리거 - 최종 파일명:', fileName);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(objectUrl);
};

// AI 채팅 관련
export const sendChatMessage = async (question: string): Promise<AIChat> => {
  const response = await api.post(`/api/v1/chat`, {
    question
  });
  return response.data;
};

export interface UploadedChatAsset {
  assetId: string;
  fileName: string;
  mimeType: string;
  size: number;
  category: 'image' | 'document' | 'audio';
  previewUrl?: string;
  downloadUrl?: string;
}

export const uploadChatAttachments = async (files: File[]): Promise<UploadedChatAsset[]> => {
  if (!files.length) {
    return [];
  }

  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file, file.name);
  });

  // ✅ Agent API로 통합 (2025-12-09)
  const response = await api.post(`/api/v1/agent/chat/assets`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });

  return (response.data?.assets || []).map((asset: any) => ({
    assetId: asset.asset_id,
    fileName: asset.file_name,
    mimeType: asset.mime_type,
    size: asset.size,
    category: asset.category,
    previewUrl: asset.preview_url,
    downloadUrl: asset.download_url
  }));
};

export const transcribeChatAudio = async (blob: Blob, language: string = 'ko-KR'): Promise<{ transcript: string }> => {
  const formData = new FormData();
  formData.append('file', blob, `voice-${Date.now()}.webm`);
  formData.append('language', language);

  // ✅ Agent API로 통합 (2025-12-09)
  const response = await api.post(`/api/v1/agent/chat/transcribe`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });

  return response.data;
};

/**
 * @deprecated 사용하지 마세요. useAgentChat 훅의 /api/v1/agent/chat/stream 사용
 * RAG 기반 채팅 (사용 중단 - 2025-12-09)
 */
export const sendRagChatMessage = async (
  message: string,
  options: {
    provider?: string | null;
    container_ids?: number[];
    session_id?: string;
    max_tokens?: number;
    temperature?: number;
    include_references?: boolean;
    attachments?: Array<{ asset_id: string; category: string }>;
    voice_asset_id?: string;
  } = {}
) => {
  console.warn('⚠️ sendRagChatMessage is deprecated. Use useAgentChat hook instead.');
  const response = await api.post(`/api/v1/agent/chat`, {
    message,
    ...options
  });
  return response.data;
};

/**
 * @deprecated 사용하지 마세요. useAgentChat 훅의 /api/v1/agent/chat/stream 사용
 * 스트리밍 RAG 기반 채팅 (사용 중단 - 2025-12-09)
 */
export const sendRagChatMessageStream = async (
  message: string,
  options: {
    provider?: string | null;
    container_ids?: number[];
    session_id?: string;
    max_tokens?: number;
    temperature?: number;
    include_references?: boolean;
    onChunk?: (chunk: any) => void;
    onComplete?: (metadata: any) => void;
    onError?: (error: any) => void;
    attachments?: Array<{ asset_id: string; category: string }>;
    voice_asset_id?: string;
  } = {}
) => {
  try {
    console.warn('⚠️ sendRagChatMessageStream is deprecated. Use useAgentChat hook instead.');
    const authToken = getAccessToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const apiBaseUrl = getApiUrl();
    // ✅ Agent API로 통합 (2025-12-09)
    const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/agent/chat/stream` : '/api/v1/agent/chat/stream';
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        ...options
      })
    });

    if (!response.ok) {
      // 401 Unauthorized 처리 - 세션 만료 시 로그인 페이지로 리다이렉트
      if (response.status === 401) {
        clearAllLocalStorage();
        window.dispatchEvent(new Event('session:invalid'));
        window.location.href = '/login';
        return;
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is null');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'content' && options.onChunk) {
              options.onChunk(data.content);
            } else if (data.type === 'complete' && options.onComplete) {
              options.onComplete(data);
            } else if (data.type === 'error' && options.onError) {
              options.onError(new Error(data.message));
            }
          } catch (parseError) {
            console.warn('SSE 데이터 파싱 오류:', parseError);
          }
        }
      }
    }
  } catch (error) {
    if (options.onError) {
      options.onError(error);
    } else {
      throw error;
    }
  }
};

/**
 * @deprecated 사용하지 마세요. Agent API에서는 attachments로 이미지 처리
 * 이미지 포함 RAG 채팅 (Vision API) (사용 중단 - 2025-12-09)
 */
export const sendRagChatMessageWithImages = async (
  message: string,
  images: File[],
  options: {
    provider?: string | null;
    container_ids?: number[];
    session_id?: string;
    use_rag?: boolean;
  } = {}
) => {
  try {
    const authToken = getAccessToken();

    // FormData 생성
    const formData = new FormData();
    formData.append('message', message);

    // 이미지 파일 추가
    images.forEach((image, index) => {
      formData.append('images', image);
    });

    // 옵션 추가 (FormData는 문자열로만 전송 가능)
    // provider는 백엔드 .env 설정 사용 (전송하지 않음)
    if (options.session_id) {
      formData.append('session_id', options.session_id);
    }
    if (options.container_ids && options.container_ids.length > 0) {
      formData.append('container_ids', options.container_ids.join(','));
    }
    if (options.use_rag !== undefined) {
      formData.append('use_rag', String(options.use_rag));
    }

    const headers: Record<string, string> = {};
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }
    // Content-Type은 브라우저가 자동으로 설정 (multipart/form-data with boundary)

    const apiBaseUrl = getApiUrl();
    // ⚠️ Deprecated: Vision API는 Agent attachments로 대체 권장
    const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/chat/vision` : '/api/v1/chat/vision';
    console.warn('⚠️ sendRagChatMessageWithImages is deprecated. Use useAgentChat with attachments instead.');
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers,
      body: formData
    });

    if (!response.ok) {
      // 401 Unauthorized 처리
      if (response.status === 401) {
        clearAllLocalStorage();
        window.dispatchEvent(new Event('session:invalid'));
        window.location.href = '/login';
        return;
      }

      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('🖼️ 이미지 채팅 오류:', error);
    throw error;
  }
};

export const getChatHistory = async (): Promise<AIChat[]> => {
  const response = await api.get(`/api/v1/users/me/chat-history`);
  return response.data;
};

/**
 * @deprecated 사용하지 마세요. Agent API에서는 피드백 기능 미지원
 * 채팅 피드백 제출 (사용 중단 - 2025-12-09)
 */
export const submitChatFeedback = async (chatId: string, feedback: 'positive' | 'negative'): Promise<void> => {
  console.warn('⚠️ submitChatFeedback is deprecated.');
  await api.post(`/api/v1/chat/${chatId}/feedback`, {
    feedback
  });
};

// 사용자 활동 통계
export const getUserActivity = async (): Promise<UserActivity> => {
  const response = await api.get(`/api/v1/users/me/activity`);
  return response.data;
};

// 추천 시스템
export const getRecommendations = async (): Promise<Recommendation[]> => {
  const response = await api.get(`/api/v1/users/me/recommendations`);
  return response.data;
};

// 최근 문서
export const getRecentDocuments = async (limit: number = 10): Promise<Document[]> => {
  const response = await api.get(`/api/v1/documents/recent`, {
    params: { limit }
  });
  return response.data;
};

// 인기 문서
export const getPopularDocuments = async (limit: number = 10): Promise<Document[]> => {
  const response = await api.get(`/api/v1/documents/popular`, {
    params: { limit }
  });
  return response.data;
};

// 문서 좋아요
export const likeDocument = async (documentId: string): Promise<void> => {
  await api.post(`/api/v1/documents/${documentId}/like`);
};

export const unlikeDocument = async (documentId: string): Promise<void> => {
  await api.delete(`/api/v1/documents/${documentId}/like`);
};

// 컨테이너 관련
export const getUserAccessibleContainers = async (): Promise<any> => {
  const response = await api.get(`/api/v1/containers/user-accessible`);
  return response.data;
};

// 전체 컨테이너 트리 조회 (권한 정보 포함)
export const getFullContainerHierarchy = async (): Promise<any> => {
  const response = await api.get(`/api/v1/containers/full-hierarchy`);
  return response.data;
};

export const getContainerPermissions = async (containerId: string): Promise<any> => {
  const response = await api.get(`/api/v1/containers/${containerId}/permissions`);
  return response.data;
};

// 사용자별 권한이 있는 지식컨테이너 트리 구조 가져오기
export const getUserKnowledgeContainers = async (): Promise<any> => {
  const response = await api.get(`/api/v1/documents/containers`);
  return response.data;
};

// 특정 컨테이너의 권한 정보 가져오기
export const getContainerUserPermission = async (containerId: string): Promise<any> => {
  const response = await api.get(`/api/v1/user/containers/${containerId}/permission`);
  return response.data;
};

// 🎯 사용자 컨테이너 생성
export const createUserContainer = async (data: {
  container_name: string;
  parent_container_id?: string;
  description?: string;
}): Promise<any> => {
  const response = await api.post(`/api/v1/containers/user/create`, data);
  return response.data;
};

// 🗑️ 사용자 컨테이너 삭제
export const deleteUserContainer = async (containerId: string): Promise<any> => {
  const response = await api.delete(`/api/v1/containers/user/${containerId}`);
  return response.data;
};

// -----------------------------
// 특허 수집 API
// -----------------------------
export interface PatentCollectionSettingPayload {
  container_id: string;
  search_config: {
    ipc_codes?: string[];
    keywords?: string[];
    applicants?: string[];
  };
  max_results?: number;
  auto_download_pdf?: boolean;
  auto_generate_embeddings?: boolean;
  schedule_type?: string;
  schedule_config?: Record<string, unknown> | null;
}

export interface PatentCollectionSettingResponse {
  setting_id: number;
  user_emp_no: string;
  container_id: string;
  search_config: Record<string, any>;
  max_results: number;
  auto_download_pdf: boolean;
  auto_generate_embeddings: boolean;
  schedule_type: string;
  schedule_config?: Record<string, unknown> | null;
  is_active: boolean;
  last_collection_date?: string | null;
}

export interface PatentCollectionTaskStartResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface PatentCollectionStatusResponse {
  task_id: string;
  status: string;
  progress_current: number;
  progress_total: number;
  collected_count: number;
  error_count: number;
}

export const getPatentCollectionSettings = async (): Promise<PatentCollectionSettingResponse[]> => {
  const response = await api.get(`/api/v1/patent-collection/settings`);
  return response.data;
};

export const createPatentCollectionSetting = async (
  payload: PatentCollectionSettingPayload
): Promise<PatentCollectionSettingResponse> => {
  const response = await api.post(`/api/v1/patent-collection/settings`, payload);
  return response.data;
};

export const updatePatentCollectionSetting = async (
  settingId: number,
  payload: Partial<PatentCollectionSettingPayload>
): Promise<PatentCollectionSettingResponse> => {
  const response = await api.put(`/api/v1/patent-collection/settings/${settingId}`, payload);
  return response.data;
};

export const deletePatentCollectionSetting = async (settingId: number): Promise<{ success: boolean }> => {
  const response = await api.delete(`/api/v1/patent-collection/settings/${settingId}`);
  return response.data;
};

export const startPatentCollection = async (
  payload: { setting_id: number }
): Promise<PatentCollectionTaskStartResponse> => {
  const response = await api.post(`/api/v1/patent-collection/start`, payload);
  return response.data;
};

export const getPatentCollectionStatus = async (
  taskId: string
): Promise<PatentCollectionStatusResponse> => {
  const response = await api.get(`/api/v1/patent-collection/status/${taskId}`);
  return response.data;
};


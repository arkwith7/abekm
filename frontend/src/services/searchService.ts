import { api } from './userService';

// 검색 결과 타입 정의
export interface SearchResult {
  file_id: string;
  title: string;
  content_preview: string;
  similarity_score: number;
  match_type: string;
  container_id: string;
  container_name?: string; // 사용자 친화적인 컨테이너 이름
  container_path?: string; // 전체 경로
  container_icon?: string; // 폴더 아이콘
  file_path: string;
  metadata: {
    document_id?: string;
    chunk_index?: number;
    keywords?: string[];
    proper_nouns?: string[];
    corp_names?: string[];
    document_type?: string;
    search_methods?: string[];
    scores?: any;
    last_updated?: string;
    file_name?: string;
  };
}

export interface SearchResponse {
  results: SearchResult[];
  total_count: number;
  search_time: number;
  search_type: string;
  message?: string;
}

export interface SearchFilters {
  container_ids?: string[];
  document_types?: string[];
  score_threshold?: number;
  max_results?: number;
  date_range?: {
    start?: string;
    end?: string;
  };
  prefer_images?: boolean;  // 멀티모달: 이미지 우선 검색
}

// 멀티모달 검색 결과 타입
export interface MultimodalSearchResult extends SearchResult {
  has_images?: boolean;
  image_count?: number;
  clip_score?: number;
  modality?: 'text' | 'image';
}

export interface MultimodalSearchResponse {
  success: boolean;
  query: string;
  has_image_query: boolean;
  results: MultimodalSearchResult[];
  total_found: number;
  search_metadata: any;
}

// 검색 서비스 함수들

/**
 * 하이브리드 검색 (벡터 + 키워드 검색 통합)
 */
export const hybridSearch = async (query: string, filters: SearchFilters & { search_type?: string } = {}): Promise<SearchResponse> => {
  try {
    console.log('🔍 하이브리드 검색 API 호출:', { query, filters });

    const response = await api.post(`/api/v1/search/hybrid`, {
      query,
      search_type: filters.search_type || 'hybrid',
      container_ids: filters.container_ids || null,
      max_results: filters.max_results || 20,
      filters: {
        document_types: filters.document_types || [],
        score_threshold: filters.score_threshold || 0.1,
        date_range: filters.date_range || {}
      }
    });

    console.log('✅ 하이브리드 검색 응답:', response.data);

    // 백엔드 응답을 프론트엔드 형식으로 변환
    return {
      results: response.data.results || [],
      total_count: response.data.total_count || 0,
      search_time: 0, // 실제 시간은 execution_time에서 계산 가능
      search_type: response.data.search_type || 'hybrid',
      message: response.data.message
    };
  } catch (error: any) {
    console.error('❌ 하이브리드 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      results: [],
      total_count: 0,
      search_time: 0,
      search_type: 'hybrid',
      message: '검색 중 오류가 발생했습니다.'
    };
  }
};

/**
 * 벡터 검색 전용 (의미 검색)
 */
export const vectorSearch = async (query: string, filters: SearchFilters = {}): Promise<SearchResponse> => {
  try {
    console.log('🧠 벡터 검색 API 호출:', { query, filters });

    const response = await api.get(`/api/v1/search/vector`, {
      params: {
        query,
        limit: filters.max_results || 20
      }
    });

    console.log('✅ 벡터 검색 응답:', response.data);

    // 백엔드 응답을 프론트엔드 형식으로 변환
    return {
      results: response.data.results || [],
      total_count: response.data.total_count || 0,
      search_time: 0,
      search_type: response.data.search_type || 'vector_only',
      message: response.data.message
    };
  } catch (error: any) {
    console.error('❌ 벡터 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      results: [],
      total_count: 0,
      search_time: 0,
      search_type: 'vector_only',
      message: '검색 중 오류가 발생했습니다.'
    };
  }
};

/**
 * 키워드 검색 전용
 */
export const keywordSearch = async (query: string, filters: SearchFilters = {}): Promise<SearchResponse> => {
  try {
    console.log('🔤 키워드 검색 API 호출:', { query, filters });

    const response = await api.get(`/api/v1/search/keyword`, {
      params: {
        query,
        limit: filters.max_results || 20
      }
    });

    console.log('✅ 키워드 검색 응답:', response.data);

    // 백엔드 응답을 프론트엔드 형식으로 변환
    return {
      results: response.data.results || [],
      total_count: response.data.total_count || 0,
      search_time: 0,
      search_type: response.data.search_type || 'keyword_only',
      message: response.data.message
    };
  } catch (error: any) {
    console.error('❌ 키워드 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      results: [],
      total_count: 0,
      search_time: 0,
      search_type: 'keyword_only',
      message: '검색 중 오류가 발생했습니다.'
    };
  }
};

/**
 * 검색 제안 가져오기
 */
export const getSearchSuggestions = async (query: string): Promise<string[]> => {
  try {
    console.log('💡 검색 제안 API 호출:', { query });

    const response = await api.get(`/api/v1/search/suggestions`, {
      params: { query, limit: 5 }
    });

    console.log('✅ 검색 제안 응답:', response.data);
    return response.data.suggestions || [];
  } catch (error: any) {
    console.error('❌ 검색 제안 오류:', error.response?.data || error.message);
    // API 오류 시 빈 배열 반환 (mock 데이터 제거)
    return [];
  }
};

/**
 * 기본 문서 검색 (통합 검색 사용)
 * 백엔드의 /api/v1/search 엔드포인트 사용
 */
export const searchDocuments = async (query: string, limit: number = 10): Promise<SearchResponse> => {
  try {
    console.log('📋 기본 문서 검색 API 호출:', { query, limit });

    const response = await api.post(`/api/v1/search`, {
      query,
      limit
    });

    console.log('✅ 기본 문서 검색 응답:', response.data);

    // 백엔드의 레거시 응답 형식을 프론트엔드 형식으로 변환
    const results = (response.data.results || []).map((result: any) => ({
      file_id: result.metadata?.file_id || result.id,
      title: result.metadata?.title || '제목 없음',
      content_preview: result.content || '',
      similarity_score: result.similarity_score || 0,
      match_type: 'hybrid',
      container_id: result.metadata?.container_id || '',
      file_path: result.metadata?.file_path || '',
      metadata: result.metadata || {}
    }));

    return {
      results,
      total_count: response.data.total_count || 0,
      search_time: 0,
      search_type: 'hybrid',
      message: response.data.search_metadata?.message
    };
  } catch (error: any) {
    console.error('❌ 기본 문서 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      results: [],
      total_count: 0,
      search_time: 0,
      search_type: 'hybrid',
      message: '검색 중 오류가 발생했습니다.'
    };
  }
};

/**
 * 검색 분석 데이터 가져오기 (향후 구현)
 */
export const getSearchAnalytics = async (): Promise<any> => {
  try {
    const response = await api.get(`/api/v1/search/analytics`);
    return response.data;
  } catch (error: any) {
    console.error('❌ 검색 분석 오류:', error.response?.data || error.message);
    // API 오류 시 빈 데이터 반환 (mock 데이터 제거)
    return {
      total_searches: 0,
      popular_queries: [],
      search_trends: []
    };
  }
};

/**
 * 멀티모달 검색 (텍스트 + 이미지 메타데이터)
 */
export const multimodalSearch = async (
  query: string,
  filters: SearchFilters & { search_type?: string } = {}
): Promise<MultimodalSearchResponse> => {
  try {
    console.log('🎨 멀티모달 검색 API 호출:', { query, filters });

    const response = await api.post(`/api/v1/search/multimodal`, {
      query,
      top_k: filters.max_results || 20,
      container_ids: filters.container_ids || null,
      similarity_threshold: filters.score_threshold || 0.3,
      prefer_images: filters.prefer_images || false,
      search_type: filters.search_type || 'hybrid'
    });

    console.log('✅ 멀티모달 검색 응답:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('❌ 멀티모달 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      success: false,
      query,
      has_image_query: false,
      results: [],
      total_found: 0,
      search_metadata: { error: '검색 중 오류가 발생했습니다.' }
    };
  }
};

/**
 * CLIP 기반 이미지 검색 (이미지 업로드 + 텍스트)
 */
export const clipSearch = async (
  query: string,
  imageFile: File | null,
  filters: SearchFilters = {}
): Promise<MultimodalSearchResponse> => {
  try {
    console.log('🖼️ CLIP 검색 API 호출:', { query, hasImage: !!imageFile, filters });

    const formData = new FormData();
    formData.append('query', query);
    if (imageFile) {
      formData.append('image', imageFile);
    }
    formData.append('top_k', String(filters.max_results || 20));
    if (filters.container_ids && filters.container_ids.length > 0) {
      formData.append('container_ids', filters.container_ids.join(','));
    }

    const response = await api.post(`/api/v1/search/clip`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });

    console.log('✅ CLIP 검색 응답:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('❌ CLIP 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      success: false,
      query,
      has_image_query: !!imageFile,
      results: [],
      total_found: 0,
      search_metadata: { error: '검색 중 오류가 발생했습니다.' }
    };
  }
};

/**
 * Base64 이미지를 사용한 이미지 검색 (클립보드 붙여넣기용)
 * @param imageBase64 - Base64 인코딩된 이미지 데이터 (data:image/png;base64,... 형식)
 * @param query - 선택적 텍스트 쿼리 (하이브리드 검색용)
 * @param filters - 검색 필터
 */
export const imageSearchWithBase64 = async (
  imageBase64: string,
  query: string = '',
  filters: SearchFilters = {}
): Promise<MultimodalSearchResponse> => {
  try {
    console.log('📷 Base64 이미지 검색 시작:', {
      hasImage: !!imageBase64,
      hasQuery: !!query,
      searchType: query ? 'hybrid' : 'image'
    });

    const requestBody = {
      image: imageBase64,  // Base64 이미지 전송
      query: query || undefined,  // 빈 문자열이면 undefined로 전송
      top_k: filters.max_results || 20,
      search_type: query ? 'hybrid' : 'image',
      prefer_images: filters.prefer_images !== undefined ? filters.prefer_images : true,
      container_ids: filters.container_ids || []
    };

    const response = await api.post(`/api/v1/search/multimodal`, requestBody);

    console.log('✅ Base64 이미지 검색 응답:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('❌ Base64 이미지 검색 오류:', error.response?.data || error.message);
    // API 오류 시 빈 결과 반환 (mock 데이터 제거)
    return {
      success: false,
      query: query || '이미지 검색',
      has_image_query: true,
      results: [],
      total_found: 0,
      search_metadata: { error: '검색 중 오류가 발생했습니다.' }
    };
  }
};

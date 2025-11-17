import axios from 'axios';

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

    const response = await axios.post(`/api/v1/search/hybrid`, {
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

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: 목업 데이터 반환');
      return generateMockSearchResponse(query, 'hybrid');
    }

    throw error;
  }
};

/**
 * 벡터 검색 전용 (의미 검색)
 */
export const vectorSearch = async (query: string, filters: SearchFilters = {}): Promise<SearchResponse> => {
  try {
    console.log('🧠 벡터 검색 API 호출:', { query, filters });

    const response = await axios.get(`/api/v1/search/vector`, {
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

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: 목업 데이터 반환');
      return generateMockSearchResponse(query, 'vector_only');
    }

    throw error;
  }
};

/**
 * 키워드 검색 전용
 */
export const keywordSearch = async (query: string, filters: SearchFilters = {}): Promise<SearchResponse> => {
  try {
    console.log('🔤 키워드 검색 API 호출:', { query, filters });

    const response = await axios.get(`/api/v1/search/keyword`, {
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

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: 목업 데이터 반환');
      return generateMockSearchResponse(query, 'keyword_only');
    }

    throw error;
  }
};

/**
 * 검색 제안 가져오기
 */
export const getSearchSuggestions = async (query: string): Promise<string[]> => {
  try {
    console.log('💡 검색 제안 API 호출:', { query });

    const response = await axios.get(`/api/v1/search/suggestions`, {
      params: { query, limit: 5 }
    });

    console.log('✅ 검색 제안 응답:', response.data);
    return response.data.suggestions || [];
  } catch (error: any) {
    console.error('❌ 검색 제안 오류:', error.response?.data || error.message);

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      return generateMockSuggestions(query);
    }

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

    const response = await axios.post(`/api/v1/search`, {
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

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: 목업 데이터 반환');
      return generateMockSearchResponse(query, 'hybrid');
    }

    throw error;
  }
};

/**
 * 검색 분석 데이터 가져오기 (향후 구현)
 */
export const getSearchAnalytics = async (): Promise<any> => {
  try {
    const response = await axios.get(`/api/v1/search/analytics`);
    return response.data;
  } catch (error: any) {
    console.error('❌ 검색 분석 오류:', error.response?.data || error.message);

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      return {
        total_searches: 1234,
        popular_queries: ['인사평가', '교육프로그램', '복리후생'],
        search_trends: []
      };
    }

    throw error;
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

    const response = await axios.post(`/api/v1/search/multimodal`, {
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

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: 멀티모달 목업 데이터 반환');
      return generateMockMultimodalResponse(query);
    }

    throw error;
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

    const response = await axios.post(`/api/v1/search/clip`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });

    console.log('✅ CLIP 검색 응답:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('❌ CLIP 검색 오류:', error.response?.data || error.message);

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: CLIP 목업 데이터 반환');
      return generateMockMultimodalResponse(query, !!imageFile);
    }

    throw error;
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

    const response = await axios.post(`/api/v1/search/multimodal`, requestBody);

    console.log('✅ Base64 이미지 검색 응답:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('❌ Base64 이미지 검색 오류:', error.response?.data || error.message);

    // 개발 중 목업 데이터 반환
    if (process.env.NODE_ENV === 'development') {
      console.warn('🚧 개발 모드: 이미지 검색 목업 데이터 반환');
      return generateMockMultimodalResponse(query || '이미지 검색', true);
    }

    throw error;
  }
};

/**
 * 개발용 멀티모달 목업 검색 결과 생성
 */
const generateMockMultimodalResponse = (query: string, hasImage: boolean = false): MultimodalSearchResponse => {
  const mockResults: MultimodalSearchResult[] = [
    {
      file_id: 'mm_doc1',
      title: `${query}와 관련된 이미지 포함 문서`,
      content_preview: `이 문서는 "${query}"에 대한 비주얼 자료를 포함하고 있습니다. 차트와 그래프가 포함되어 있습니다.`,
      similarity_score: 0.95,
      match_type: 'multimodal',
      container_id: 'woongjin_hr',
      file_path: '/documents/mm_doc1.pdf',
      has_images: true,
      image_count: 5,
      clip_score: 0.92,
      modality: 'text',
      metadata: {
        document_id: 'mm_doc1',
        document_type: 'pdf',
        search_methods: ['vector', 'clip'],
        file_name: `${query}_비주얼_자료.pdf`
      }
    },
    {
      file_id: 'mm_doc2',
      title: `${query} 프레젠테이션`,
      content_preview: `${query} 관련 프레젠테이션 자료입니다. 다수의 이미지와 차트가 포함되어 있습니다.`,
      similarity_score: 0.88,
      match_type: 'multimodal',
      container_id: 'woongjin_edu',
      file_path: '/documents/presentation.pptx',
      has_images: true,
      image_count: 12,
      clip_score: 0.87,
      modality: 'image',
      metadata: {
        document_id: 'mm_doc2',
        document_type: 'pptx',
        search_methods: ['clip', 'vector'],
        file_name: '프레젠테이션.pptx'
      }
    }
  ];

  return {
    success: true,
    query,
    has_image_query: hasImage,
    results: mockResults,
    total_found: mockResults.length,
    search_metadata: {
      search_type: 'multimodal',
      note: '개발 모드 목업 데이터'
    }
  };
};

/**
 * 개발용 목업 검색 결과 생성
 */
const generateMockSearchResponse = (query: string, searchType: string): SearchResponse => {
  const mockResults: SearchResult[] = [
    {
      file_id: 'doc1',
      title: `${query}와 관련된 첫 번째 문서`,
      content_preview: `이 문서는 "${query}"에 대한 상세한 정보를 포함하고 있습니다. 하이브리드 검색을 통해 찾아낸 관련성 높은 문서입니다.`,
      similarity_score: 0.95,
      match_type: searchType === 'hybrid' ? 'hybrid' : searchType.replace('_only', ''),
      container_id: 'woongjin_hr',
      file_path: '/documents/doc1.pdf',
      metadata: {
        document_id: 'doc1',
        document_type: 'pdf',
        search_methods: searchType === 'hybrid' ? ['vector', 'keyword'] : [searchType.replace('_only', '')],
        file_name: `${query}_관련_문서.pdf`
      }
    },
    {
      file_id: 'doc2',
      title: `${query} 관련 정책 문서`,
      content_preview: `회사의 ${query} 관련 정책과 절차에 대해 설명하는 공식 문서입니다. 모든 직원이 숙지해야 할 중요한 내용입니다.`,
      similarity_score: 0.87,
      match_type: searchType === 'hybrid' ? 'hybrid' : searchType.replace('_only', ''),
      container_id: 'woongjin_edu',
      file_path: '/documents/policy.docx',
      metadata: {
        document_id: 'doc2',
        document_type: 'docx',
        search_methods: searchType === 'hybrid' ? ['vector', 'keyword'] : [searchType.replace('_only', '')],
        file_name: '정책_문서.docx'
      }
    },
    {
      file_id: 'doc3',
      title: `${query} 실무 가이드라인`,
      content_preview: `실무진을 위한 ${query} 처리 가이드라인입니다. 단계별 절차와 주의사항을 포함하고 있습니다.`,
      similarity_score: 0.78,
      match_type: searchType === 'hybrid' ? 'hybrid' : searchType.replace('_only', ''),
      container_id: 'woongjin_eval',
      file_path: '/documents/guidelines.md',
      metadata: {
        document_id: 'doc3',
        document_type: 'md',
        search_methods: searchType === 'hybrid' ? ['vector'] : [searchType.replace('_only', '')],
        file_name: '실무_가이드라인.md'
      }
    }
  ];

  return {
    results: mockResults,
    total_count: mockResults.length,
    search_time: Math.floor(Math.random() * 500) + 100, // 100-600ms
    search_type: searchType,
    message: '개발 모드에서 목업 데이터를 반환합니다.'
  };
};

/**
 * 개발용 목업 검색 제안 생성
 */
const generateMockSuggestions = (query: string): string[] => {
  const commonSuggestions = [
    '인사 평가',
    '교육 프로그램',
    '복리후생',
    '업무 매뉴얼',
    '보안 정책',
    '회계 규정'
  ];

  return commonSuggestions
    .filter(suggestion =>
      suggestion.toLowerCase().includes(query.toLowerCase()) ||
      query.toLowerCase().includes(suggestion.toLowerCase())
    )
    .slice(0, 5);
};

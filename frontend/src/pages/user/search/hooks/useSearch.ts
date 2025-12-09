import { useCallback, useEffect, useRef, useState } from 'react';
import { useGlobalApp } from '../../../../contexts/GlobalAppContext';
import { clipSearch, hybridSearch, imageSearchWithBase64, keywordSearch, multimodalSearch, vectorSearch } from '../../../../services/searchService';
import { SearchFilters, SearchResult } from '../types';

export const useSearch = () => {
  const { state: globalState, actions } = useGlobalApp();
  const savedSearchState = globalState.pageStates?.search;

  const [state, setState] = useState({
    query: savedSearchState?.query || '',
    isSearching: false,
    // ⚠️ searchResults는 localStorage에서 복원하지 않음 (DB 결과 우선)
    searchResults: [] as SearchResult[],
    totalCount: 0,
    searchTime: null as number | null,
    error: null as string | null,
    currentPage: savedSearchState?.currentPage || 1,
  });

  const [filters, setFilters] = useState<SearchFilters>(() => {
    const defaultFilters: SearchFilters = {
      searchType: 'hybrid',
      containerIds: [],
      includeSubContainers: true,
      documentTypes: [],
      dateRange: {},
      scoreThreshold: 0.1
    };
    // savedSearchState?.filters와 병합하여 누락된 필드 방지
    return savedSearchState?.filters
      ? { ...defaultFilters, ...savedSearchState.filters }
      : defaultFilters;
  });

  const [selectedResults, setSelectedResults] = useState<Set<string>>(
    new Set(savedSearchState?.selectedResults || [])
  );
  const [viewMode, setViewMode] = useState<'list' | 'grid'>(
    savedSearchState?.viewMode || 'list'
  );

  const abortControllerRef = useRef<AbortController | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const filtersRef = useRef(filters);

  // filters 변경 감지 및 ref 업데이트
  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  // 상태 변경 시 pageStates에 저장 (디바운스 적용)
  // ⚠️ searchResults는 저장하지 않음 (DB 결과 우선)
  useEffect(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    const payload = {
      query: state.query,
      filters: filtersRef.current,
      // results는 저장하지 않음 - 항상 API에서 최신 데이터 로드
      selectedResults: Array.from(selectedResults),
      viewMode,
      currentPage: state.currentPage,
      // NOTE: selectedDocuments는 다른 훅(SearchPage)에서 관리 → 여기서 덮어쓰지 않음
    };

    saveTimeoutRef.current = setTimeout(() => {
      actions.savePageState('search', payload);
    }, 250); // 약간 더 빠른 저장

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.query, selectedResults, viewMode, state.currentPage]);

  const buildSearchParams = useCallback((query: string, page: number = 1) => {
    const currentFilters = filtersRef.current || {
      searchType: 'hybrid',
      containerIds: [],
      includeSubContainers: true,
      documentTypes: [],
      dateRange: {},
      scoreThreshold: 0.1
    };
    return {
      container_ids: currentFilters.containerIds?.length > 0 ? currentFilters.containerIds : undefined,
      include_sub_containers: currentFilters.includeSubContainers,
      document_types: currentFilters.documentTypes,
      score_threshold: currentFilters.scoreThreshold,
      max_results: 20,
      page,
      date_range: currentFilters.dateRange,
    };
  }, []);

  const executeSearch = useCallback(async (searchQuery?: string, page: number = 1, imageFile?: File | null) => {
    console.log('🔍 [useSearch] executeSearch 호출:', { searchQuery, imageFile: imageFile?.name, page });

    // searchQuery가 제공되지 않으면 빈 문자열 사용 (이미지만 검색 가능)
    const currentQuery = searchQuery !== undefined ? searchQuery : '';

    // 텍스트 쿼리와 이미지가 모두 없으면 검색 안 함
    if (!currentQuery.trim() && !imageFile) {
      console.log('⚠️ [useSearch] 검색 중단: 쿼리와 이미지 모두 없음');
      return;
    }

    console.log('✅ [useSearch] 검색 진행:', { currentQuery, hasImage: !!imageFile });

    // 이전 검색 요청 취소
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    const startTime = Date.now();

    console.log('✅ [useSearch] 검색 시작:', { currentQuery, hasImage: !!imageFile, page });

    setState(prev => ({
      ...prev,
      isSearching: true,
      error: null,
      query: currentQuery,
      currentPage: page
    }));

    try {
      const commonParams = buildSearchParams(currentQuery, page);
      let searchResponse: any;

      // 이미지 파일이 있으면 Base64로 변환
      let imageBase64: string | undefined;
      if (imageFile) {
        console.log('📷 [useSearch] 이미지 파일 변환 시작:', imageFile.name);
        imageBase64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result as string);
          reader.onerror = reject;
          reader.readAsDataURL(imageFile);
        });
        console.log('✅ [useSearch] 이미지 Base64 변환 완료');
      }

      // 이미지가 있을 때는 imageSearchWithBase64 사용
      if (imageBase64) {
        console.log('🚀 [useSearch] imageSearchWithBase64 호출');
        searchResponse = await imageSearchWithBase64(
          imageBase64,
          currentQuery,  // 텍스트 쿼리 (있으면 하이브리드, 없으면 이미지만)
          commonParams
        );
        console.log('✅ [useSearch] 검색 응답:', searchResponse);
        // 응답을 SearchResponse 형식으로 변환
        searchResponse = {
          results: searchResponse.results || [],
          total_count: searchResponse.total_found || 0,
          search_time: 0,
          search_type: currentQuery ? 'hybrid' : 'image'
        };
      } else {
        // 이미지가 없을 때는 기존 검색 타입 사용
        const currentSearchType = filtersRef.current?.searchType || 'hybrid';
        switch (currentSearchType) {
          case 'vector_only':
            searchResponse = await vectorSearch(currentQuery, commonParams);
            break;
          case 'keyword_only':
            searchResponse = await keywordSearch(currentQuery, commonParams);
            break;
          case 'multimodal':
            searchResponse = await multimodalSearch(currentQuery, {
              ...commonParams,
              prefer_images: true
            });
            // 멀티모달 응답을 SearchResponse 형식으로 변환
            searchResponse = {
              results: searchResponse.results || [],
              total_count: searchResponse.total_found || 0,
              search_time: 0,
              search_type: 'multimodal'
            };
            break;
          case 'clip':
            searchResponse = await clipSearch(currentQuery, imageFile || null, commonParams);
            // CLIP 응답을 SearchResponse 형식으로 변환
            searchResponse = {
              results: searchResponse.results || [],
              total_count: searchResponse.total_found || 0,
              search_time: 0,
              search_type: 'clip'
            };
            break;
          default:
            searchResponse = await hybridSearch(currentQuery, {
              ...commonParams,
              search_type: 'hybrid'
            });
        }
      }

      const endTime = Date.now();

      setState(prev => ({
        ...prev,
        searchResults: page === 1 ? searchResponse.results || [] : [...prev.searchResults, ...(searchResponse.results || [])],
        totalCount: searchResponse.total_count || 0,
        searchTime: endTime - startTime,
        isSearching: false
      }));

    } catch (error: any) {
      console.error('❌ [useSearch] 검색 에러:', error);
      if (error.name !== 'AbortError') {
        const errorMessage = error.response?.data?.detail || '검색 중 오류가 발생했습니다.';
        console.error('❌ [useSearch] 에러 메시지:', errorMessage);
        setState(prev => ({
          ...prev,
          error: errorMessage,
          searchResults: [],
          totalCount: 0,
          isSearching: false
        }));
      }
    }
  }, [buildSearchParams]); // state.query와 filters 제거 (함수 내에서 직접 참조)

  const updateFilters = useCallback((newFilters: Partial<SearchFilters>) => {
    setFilters((prev: SearchFilters) => ({ ...prev, ...newFilters }));
    // 필터가 변경되면 기존 검색 결과 초기화
    setState(prev => ({ ...prev, searchResults: [], totalCount: 0, currentPage: 1 }));
  }, []);

  const handleResultSelect = useCallback((resultId: string) => {
    setSelectedResults(prev => {
      const newSet = new Set(prev);
      if (newSet.has(resultId)) newSet.delete(resultId);
      else newSet.add(resultId);
      return newSet;
    });
  }, []);

  // 외부(글로벌 선택 패널)에서 개별 제거/전체 제거 시 검색 결과 체크박스와 동기화하기 위한 헬퍼
  const syncSelectedResults = useCallback((fileIds: string[]) => {
    setSelectedResults(new Set(fileIds));
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selectedResults.size === state.searchResults.length) {
      setSelectedResults(new Set());
    } else {
      setSelectedResults(new Set(state.searchResults.map(r => r.file_id)));
    }
  }, [selectedResults.size, state.searchResults]);

  const loadMore = useCallback(() => {
    if (state.isSearching || state.searchResults.length >= state.totalCount) return;
    executeSearch(state.query, state.currentPage + 1);
  }, [state.isSearching, state.searchResults.length, state.totalCount, state.query, state.currentPage, executeSearch]);

  const clearResults = useCallback(() => {
    setState(prev => ({
      ...prev,
      query: '',
      searchResults: [],
      totalCount: 0,
      error: null,
      currentPage: 1
    }));
    setSelectedResults(new Set());
  }, []);

  return {
    // State
    ...state,
    filters,
    selectedResults,
    viewMode,

    // Actions
    executeSearch,
    updateFilters,
    handleResultSelect,
    syncSelectedResults,
    handleSelectAll,
    loadMore,
    clearResults,
    setViewMode,
    setQuery: (query: string) => setState(prev => ({ ...prev, query })),

    // Computed
    hasMore: state.searchResults.length < state.totalCount,
    isAllSelected: selectedResults.size === state.searchResults.length && state.searchResults.length > 0,
  };
};

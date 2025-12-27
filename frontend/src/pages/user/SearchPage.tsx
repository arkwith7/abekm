import { ArrowRight, MessageCircle } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SelectedDocumentsDisplay } from '../../components/chat/SelectedDocumentsDisplay';
import FileViewer from '../../components/common/FileViewer';
import { useSelectedDocuments, useUnifiedSelectedDocuments, useWorkContext } from '../../contexts/GlobalAppContext';
import { Document as GlobalDocument } from '../../contexts/types';
import { useGlobalAppStore } from '../../store/globalAppStore';
import { downloadDocument as downloadDocumentApi } from '../../services/userService';
import { Document } from '../../types/user.types';
import {
  EmptyState,
  FloatingSearchBar,
  LoadMoreButton,
  ResultList,
  useSearch
} from './search';
import { SearchResult } from './search/types';

const SearchPage: React.FC = () => {
  // FileViewer state
  const [isFileViewerOpen, setIsFileViewerOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);

  // 글로벌 상태 hooks
  const {
    selectedDocuments,
    setSelectedDocuments,
    hasSelectedDocuments
  } = useSelectedDocuments();
  const {
    selectedDocuments: unifiedSelectedDocuments,
    setSelectedDocuments: setUnifiedSelectedDocuments,
    removeSelectedDocument: removeUnifiedSelectedDocument,
    clearSelectedDocuments: clearUnifiedSelectedDocuments,
  } = useUnifiedSelectedDocuments();
  const { navigateWithContext, workContext, updateWorkContext } = useWorkContext();

  const {
    // State
    query,
    isSearching,
    searchResults,
    totalCount,
    error,
    filters,
    selectedResults,
    viewMode,

    // Actions
    executeSearch,
    updateFilters,
    handleResultSelect,
    handleSelectAll,
    loadMore,
    clearResults,
    setViewMode,
    setQuery,
    syncSelectedResults,

    // Computed
    hasMore,
    isAllSelected,
  } = useSearch();

  const navigate = useNavigate();

  // 페이지 진입 시 workContext.sourcePageType 보정
  const hasInitializedContext = useRef(false);

  useEffect(() => {
    if (!hasInitializedContext.current) {
      hasInitializedContext.current = true;
      if (workContext.sourcePageType !== 'search') {
        updateWorkContext({ sourcePageType: 'search' });
      }
      return;
    }

    if (workContext.sourcePageType !== 'search') {
      updateWorkContext({ sourcePageType: 'search' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workContext.sourcePageType]);

  // 대시보드나 다른 페이지에서 전달받은 검색 쿼리로 자동 검색 실행
  useEffect(() => {
    if (workContext.sourcePageState && (workContext.sourcePageState.query || workContext.sourcePageState.hasImage)) {
      const incomingQuery = workContext.sourcePageState.query;
      const hasImage = workContext.sourcePageState.hasImage;

      console.log('🔍 다른 페이지에서 전달받은 검색 요청:', { query: incomingQuery, hasImage });

      // ✅ 이미 동일 쿼리의 결과가 화면/스토어에 캐시되어 있으면 불필요한 재검색을 방지
      // (메뉴 이동 시 "즉시 복원" UX를 우선)
      if (!hasImage && incomingQuery && incomingQuery === query && searchResults.length > 0) {
        updateWorkContext({ sourcePageState: null });
        return;
      }

      // sessionStorage에서 이미지 복원
      let imageFile: File | null = null;
      if (hasImage) {
        try {
          const stored = sessionStorage.getItem('pendingSearchImage');
          if (stored) {
            const imageData = JSON.parse(stored);
            // base64 데이터를 Blob으로 변환
            const byteString = atob(imageData.data.split(',')[1]);
            const ab = new ArrayBuffer(byteString.length);
            const ia = new Uint8Array(ab);
            for (let i = 0; i < byteString.length; i++) {
              ia[i] = byteString.charCodeAt(i);
            }
            const blob = new Blob([ab], { type: imageData.type });
            imageFile = new File([blob], imageData.name, { type: imageData.type });

            console.log('✅ 이미지 복원 성공:', imageFile.name, imageFile.size);

            // 사용 후 삭제
            sessionStorage.removeItem('pendingSearchImage');
          }
        } catch (error) {
          console.error('❌ 이미지 복원 실패:', error);
        }
      }

      // 쿼리 설정 후 검색 실행
      if (incomingQuery) {
        setQuery(incomingQuery);
      }
      executeSearch(incomingQuery || '', 1, imageFile);

      // 사용한 상태 정리 (중복 실행 방지)
      updateWorkContext({ sourcePageState: null });
    }
  }, [workContext.sourcePageState, setQuery, executeSearch, updateWorkContext, query, searchResults.length]);

  // 선택된 검색 결과를 글로벌 페이지 상태에 병합 (기존 문서 + 새 선택 문서)
  // 🆕 검색 결과가 있을 때만 동기화 (다른 페이지의 선택 문서 보존)
  useEffect(() => {
    // 검색 결과가 없으면 동기화하지 않음 (초기 상태 또는 다른 페이지에서 온 경우)
    if (searchResults.length === 0 && selectedResults.size === 0) {
      console.log('🔍 검색 결과 없음 - 기존 선택 문서 보존');
      return;
    }

    // 검색 페이지에서 새로 선택한 문서들
    const newDocs: GlobalDocument[] = [];
    selectedResults.forEach(resultId => {
      const result = searchResults.find(r => r.file_id === resultId);
      if (result) {
        // metadata가 없거나 undefined일 경우를 대비한 안전한 처리
        const metadata = result.metadata || {};
        // 파일명 우선순위: metadata.file_name > file_path의 마지막 부분 > title
        const fileName = metadata.file_name ||
          (result.file_path ? result.file_path.split('/').pop() : null) ||
          result.title ||
          '알 수 없음';

        newDocs.push({
          fileId: result.file_id,
          fileName: fileName,
          originalName: result.title || fileName,
          fileSize: 0,
          fileType: fileName && fileName.includes('.') ? fileName.split('.').pop() || '' : '',
          uploadDate: metadata.last_updated || '',
          containerName: result.container_path || result.file_path || '',
          containerId: result.container_id || '',
          content: result.content_preview || '',
          summary: undefined,
          keywords: metadata.keywords || [],
          isSelected: true
        });
      }
    });

    // 🆕 기존 선택 문서와 병합 (중복 제거)
    if (newDocs.length > 0) {
      // 기존 문서 중 검색 결과에 없는 문서들 (다른 페이지에서 선택한 문서들)
      const existingDocs = unifiedSelectedDocuments.filter(doc =>
        !newDocs.some(newDoc => newDoc.fileId === doc.fileId)
      );

      // 기존 문서 + 새 문서 병합
      const mergedDocs = [...existingDocs, ...newDocs];

      console.log('🔍 검색 페이지 선택 문서 병합:', {
        기존: existingDocs.length,
        새로선택: newDocs.length,
        최종: mergedDocs.length
      });

      setSelectedDocuments(mergedDocs);
      // ✅ 통합 선택(전역)도 함께 업데이트
      setUnifiedSelectedDocuments(mergedDocs as any);
    } else if (selectedResults.size === 0 && searchResults.length > 0) {
      // 검색 결과는 있지만 아무것도 선택하지 않은 경우 - 기존 문서 유지
      console.log('🔍 검색 페이지에서 선택 해제 - 기존 문서 유지');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedResults, searchResults]); // setSelectedDocuments는 안정적인 함수

  // AI 채팅으로 이동하는 함수
  const handleGoToChat = useCallback(() => {
    console.log('🚀 AI 채팅으로 이동 버튼 클릭됨');
    console.log('📊 selectedResults:', selectedResults);
    console.log('📊 searchResults 개수:', searchResults.length);

    // 현재 검색 상태 저장
    // 선택 문서 스냅샷 생성 (채팅 진입 시 정확한 개수 보장을 위해)
    const selectedDocsSnapshot: GlobalDocument[] = [];
    selectedResults.forEach(resultId => {
      const result = searchResults.find(r => r.file_id === resultId);
      if (result) {
        // metadata가 없거나 undefined일 경우를 대비한 안전한 처리
        const metadata = result.metadata || {};
        // 파일명 우선순위: metadata.file_name > file_path의 마지막 부분 > title
        const fileName = metadata.file_name ||
          (result.file_path ? result.file_path.split('/').pop() : null) ||
          result.title ||
          '알 수 없음';

        selectedDocsSnapshot.push({
          fileId: result.file_id,
          fileName: fileName,
          originalName: result.title || fileName,
          fileSize: 0,
          fileType: fileName && fileName.includes('.') ? fileName.split('.').pop() || '' : '',
          uploadDate: metadata.last_updated || '',
          containerName: result.container_path || result.file_path || '',
          containerId: result.container_id || '',
          content: result.content_preview || '',
          summary: undefined,
          keywords: metadata.keywords || [],
          isSelected: true
        });
      }
    });

    const currentState = {
      query,
      filters,
      viewMode,
      selectedResults: Array.from(selectedResults),
      searchResults,
      selectedDocsSnapshot
    };

    console.log('💾 현재 검색 상태 저장:', currentState);
    console.log('📄 선택된 문서 스냅샷:', selectedDocsSnapshot);
    console.log('🔗 navigateWithContext 함수 존재 여부:', typeof navigateWithContext);

    // ✅ 이동 직전에 agent-chat 쪽 선택 문서를 미리 세팅 (fallback navigate 케이스에서도 유지)
    try {
      // 현재 페이지(search)의 선택 문서 가져오기
      const currentPageSelectedDocs = useGlobalAppStore.getState().pageStates.search?.selectedDocuments || [];
      const unifiedDocs = useGlobalAppStore.getState().selectedDocuments || [];
      
      // 우선순위: 스냅샷(현재 선택) > 현재 페이지 선택 문서 > 통합 선택 문서
      const docsToCarry = selectedDocsSnapshot.length > 0 
        ? selectedDocsSnapshot 
        : (currentPageSelectedDocs.length > 0 ? currentPageSelectedDocs : unifiedDocs);
      
      // agentChat으로 선택 문서 전달
      if (docsToCarry.length > 0) {
        useGlobalAppStore.getState().actions.setSelectedDocuments(docsToCarry);
        useGlobalAppStore.getState().actions.setPageSelectedDocuments('agentChat', docsToCarry);
        console.log('✅ AI Agents로 문서 전달:', docsToCarry.length, '개');
      } else {
        console.warn('⚠️ 선택된 문서가 없습니다.');
      }
    } catch (e) {
      console.error('❌ agentChat 선택 문서 사전 세팅 실패:', e);
    }

    const targetRoute = '/user/agent-chat';
    let navigated = false;

    try {
      if (typeof navigateWithContext === 'function') {
        navigated = navigateWithContext(
          'agent-chat',
          currentState,
          { ragMode: true }
        ) || false;
        console.log('✅ navigateWithContext 호출 성공, navigated:', navigated);
      } else {
        console.warn('⚠️ navigateWithContext 함수가 정의되지 않았습니다.');
      }
    } catch (error) {
      console.error('❌ navigateWithContext 호출 실패:', error);
    }

    if (!navigated) {
      console.log('🔁 navigateWithContext가 이동을 수행하지 않아 useNavigate로 직접 이동합니다.');
      navigate(targetRoute);
    }
  }, [navigateWithContext, query, filters, viewMode, selectedResults, searchResults, navigate]);

  // FileViewer handlers
  const convertSearchResultToDocument = (result: SearchResult): Document => {
    // metadata가 없거나 undefined일 경우를 대비한 안전한 처리
    const metadata = result.metadata || {};
    // 파일명 우선순위:
    // - 검색 결과에서는 metadata.file_name이 "제목"만 오는 경우가 많아(확장자 없음) file_path를 참고해야 함
    const fileNameFromPath = result.file_path ? result.file_path.split('/').pop() : null;
    const fileName = (metadata.file_name && metadata.file_name.includes('.'))
      ? metadata.file_name
      : (fileNameFromPath || metadata.file_name || result.title || '알 수 없음');

    // 파일 확장자 추출 (file_name에 없으면 file_path에서 유추)
    let fileExtension = fileName && fileName.includes('.') ? (fileName.split('.').pop() || '') : '';
    if (!fileExtension && result.file_path) {
      const lowerPath = String(result.file_path).toLowerCase();
      if (lowerPath.includes('patents.google.com')) {
        fileExtension = 'url';
      } else if (lowerPath.endsWith('.pdf')) {
        fileExtension = 'pdf';
      } else if (lowerPath.endsWith('.url')) {
        fileExtension = 'url';
      }
    }

    // 문서 타입 결정 (특허 URL인 경우 FileViewer 특허 UI로 유도)
    const looksLikePatentUrl =
      fileExtension === 'url' ||
      (typeof result.file_path === 'string' && result.file_path.includes('patents.google.com'));
    const documentType = looksLikePatentUrl ? 'patent' : (metadata.document_type || 'Unknown');

    return {
      id: result.file_id,
      document_id: metadata.document_id || result.file_id,
      title: result.title || fileName,
      file_name: fileName,
      file_size: 0, // Not available in SearchResult
      file_extension: fileExtension,
      document_type: documentType,
      quality_score: 0, // Not available in SearchResult
      korean_ratio: 0, // Not available in SearchResult
      keywords: metadata.keywords || [],
      container_path: result.container_path || result.file_path || '',
      description: result.content_preview || '',
      tags: [],
      is_public: false,
      view_count: 0,
      download_count: 0,
      created_at: metadata.last_updated || new Date().toISOString(),
      updated_at: metadata.last_updated || new Date().toISOString(),
      uploaded_by: 'Unknown', // Not available in SearchResult
      path: result.file_path, // 파일 경로 (S3 URL 또는 외부 URL)
    };
  };

  const handleFileView = (result: SearchResult) => {
    const document = convertSearchResultToDocument(result);
    setSelectedDocument(document);
    setIsFileViewerOpen(true);
  };

  const handleFileDownload = (result: SearchResult) => {
    const document = convertSearchResultToDocument(result);

    // 특허(URL 타입)도 백엔드에서 .url 바로가기 파일로 내려주므로 동일 다운로드 로직 사용
    downloadDocumentApi(String(document.document_id || document.id), document.title, document.file_extension);
  };

  const handleCloseFileViewer = () => {
    setIsFileViewerOpen(false);
    setSelectedDocument(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 relative">
      {/* 메인 컨텐츠 영역 - 검색 결과만 표시 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4" role="alert">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-red-400 mr-3 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.728-.833-2.498 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <div>
                <h3 className="text-sm font-medium text-red-800">검색 오류</h3>
                <p className="text-red-700 mt-1">{error}</p>
                <button
                  onClick={() => executeSearch()}
                  className="mt-2 text-sm text-red-600 hover:text-red-500 underline focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 rounded"
                >
                  다시 시도
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="pb-56"> {/* 플로팅 검색창 + 선택된 문서 패널 공간 확보 (224px) */}
            {/* Results Controls */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center space-x-4">
                <button
                  onClick={handleSelectAll}
                  className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded"
                  aria-label={isAllSelected ? '전체 선택 해제' : '전체 선택'}
                >
                  {isAllSelected ? '전체 해제' : '전체 선택'}
                </button>

                {selectedResults.size > 0 && (
                  <>
                    <span className="text-sm text-gray-600">
                      {selectedResults.size}개 선택됨
                    </span>
                    <button
                      className="text-sm text-green-600 hover:text-green-800 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 rounded"
                      onClick={() => {
                        // TODO: 선택된 항목들 다운로드 기능 구현
                        console.log('선택된 항목들:', Array.from(selectedResults));
                      }}
                    >
                      선택 항목 다운로드
                    </button>
                  </>
                )}
              </div>

              <div className="flex items-center space-x-4">
                <div className="text-sm text-gray-500">
                  {searchResults.length}개 / 총 {totalCount}개
                </div>

                {/* 뷰 모드 변경 버튼 */}
                <div className="flex border border-gray-300 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode('list')}
                    className={`px-3 py-2 text-sm font-medium transition-colors ${viewMode === 'list'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-50'
                      }`}
                  >
                    목록
                  </button>
                  <button
                    onClick={() => setViewMode('grid')}
                    className={`px-3 py-2 text-sm font-medium transition-colors ${viewMode === 'grid'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-50'
                      }`}
                  >
                    그리드
                  </button>
                </div>
              </div>
            </div>

            {/* Results List */}
            <ResultList
              results={searchResults}
              viewMode={viewMode}
              selectedResults={selectedResults}
              onResultSelect={handleResultSelect}
              onFileView={handleFileView}
              onFileDownload={handleFileDownload}
            />

            {/* Load More Button */}
            {hasMore && (
              <LoadMoreButton
                isLoading={isSearching}
                onClick={loadMore}
                remainingCount={totalCount - searchResults.length}
              />
            )}
          </div>
        )}

        {/* Empty States */}
        <EmptyState
          query={query}
          hasSearched={!!query}
          isSearching={isSearching}
          hasError={!!error}
          hasResults={searchResults.length > 0}
          onRetry={() => executeSearch()}
          onClear={clearResults}
          isImageSearch={filters.searchType === 'multimodal' || filters.searchType === 'clip'}
        />
      </main>

      {/* 플로팅 검색창 */}
      <FloatingSearchBar
        query={query}
        setQuery={setQuery}
        isSearching={isSearching}
        onSearch={(searchQuery, imageFile) => executeSearch(searchQuery, 1, imageFile)}
        onClear={clearResults}
        filters={filters}
        updateFilters={updateFilters}
        totalCount={totalCount}
      />

      {/* 플로팅 선택된 문서 패널 */}
      {hasSelectedDocuments && (
        <div className="fixed bottom-44 right-6 w-96 z-40"> {/* 플로팅 검색창보다 위쪽에 배치 (176px) */}
          <div className="bg-white rounded-lg shadow-lg border border-gray-200">
            <SelectedDocumentsDisplay
              maxDisplay={3}
              compact={true}
              showActions={true}
              className="mb-0"
              onClearAll={() => {
                // ✅ 통합 선택 비우기 + 체크박스 해제
                setSelectedDocuments([]);
                clearUnifiedSelectedDocuments();
                syncSelectedResults([]);
              }}
              onRemove={(fileId: string) => {
                // ✅ 통합 선택에서 제거 + (현재 검색 결과에 있으면) 체크박스 해제
                removeUnifiedSelectedDocument(fileId);
                const after = Array.from(selectedResults).filter(id => id !== fileId);
                syncSelectedResults(after);
              }}
              onViewDocument={(doc: GlobalDocument) => {
                // GlobalDocument를 Document로 변환
                const viewerDoc: Document = {
                  id: doc.fileId,
                  title: doc.fileName,
                  file_name: doc.fileName,
                  file_extension: doc.fileType || '',
                  container_path: doc.containerName || '',
                  created_at: new Date().toISOString(),
                  uploaded_by: '',
                  file_size: doc.fileSize || 0
                };
                setSelectedDocument(viewerDoc);
                setIsFileViewerOpen(true);
              }}
            />

            {/* AI 채팅으로 이동 버튼 */}
            <div className="p-3 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              <button
                onClick={handleGoToChat}
                className="w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md transition-colors font-medium"
              >
                <MessageCircle className="w-4 h-4" />
                <span>AI 채팅으로 이동</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <p className="text-xs text-gray-600 text-center mt-1">
                선택된 문서로 RAG 기반 AI 채팅을 시작합니다
              </p>
              <p className="text-xs text-blue-600 text-center mt-1 font-medium">
                💾 현재 검색 상태가 자동 저장됩니다
              </p>
            </div>
          </div>
        </div>
      )}

      {/* FileViewer Modal */}
      <FileViewer
        isOpen={isFileViewerOpen}
        onClose={handleCloseFileViewer}
        document={selectedDocument}
        onDownload={(document) => {
          if (!document) return;
          downloadDocumentApi(String(document.document_id || document.id), document.title, document.file_extension);
        }}
      />
    </div>
  );
};

export default SearchPage;

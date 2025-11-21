import {
  AlertCircle,
  CheckCircle,
  Clock,
  Download,
  Eye,
  Filter,
  Grid,
  List,
  Search,
  Shield,
  Trash2,
  Upload
} from 'lucide-react';
import React, { useState } from 'react';
import { Document } from '../../../../types/user.types';
import { KnowledgeContainer } from './KnowledgeContainerTree';

// 문서 상태 타입
type DocumentStatus = 'uploading' | 'processing' | 'completed' | 'error';

// 뷰 모드 타입
type ViewMode = 'grid' | 'list';

// 확장된 문서 타입 (업로드 진행 상태 포함)
interface ExtendedDocument extends Document {
  status?: DocumentStatus;
  uploadProgress?: number;
  errorMessage?: string;
}

interface KnowledgeListProps {
  documents: ExtendedDocument[];
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  selectedDocuments: Set<string>;
  onDocumentSelect: (documentId: string, selected: boolean) => void;
  onSelectAll: () => void;
  onDownload: (document: ExtendedDocument) => void;
  onEdit: (document: ExtendedDocument) => void;
  onDelete: (documentId: string) => void;
  onView: (document: ExtendedDocument) => void;
  onFileView?: (document: ExtendedDocument) => void;
  onBulkDelete: () => void;
  onUploadClick?: () => void;
  onAccessControl?: (document: ExtendedDocument) => void;
  searchTerm: string;
  onSearchChange: (term: string) => void;
  filterStatus: DocumentStatus | 'all';
  onFilterStatusChange: (status: DocumentStatus | 'all') => void;
  sortBy: 'date' | 'name' | 'size';
  onSortByChange: (sort: 'date' | 'name' | 'size') => void;
  sortOrder: 'asc' | 'desc';
  onSortOrderChange: (order: 'asc' | 'desc') => void;
  isLoading?: boolean;
  selectedContainer?: KnowledgeContainer | null;
  canUpload?: boolean;
  // 선택 상태일 때 우측의 기본 일괄 삭제 버튼을 커스터마이즈할 수 있는 액션
  selectedAction?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
    className?: string;
  };
  // 페이지네이션 관련 props 추가
  currentPage?: number;
  totalItems?: number;
  itemsPerPage?: number;
  hasNext?: boolean;
  hasPrevious?: boolean;
  onPageChange?: (page: number) => void;
  onItemsPerPageChange?: (itemsPerPage: number) => void;
  isLoadingDocuments?: boolean;
  // 🆕 컨테이너 관리 버튼
  containerActions?: React.ReactNode;
}

const KnowledgeList: React.FC<KnowledgeListProps> = ({
  documents,
  viewMode,
  onViewModeChange,
  selectedDocuments,
  onDocumentSelect,
  onSelectAll,
  onDownload,
  onEdit,
  onDelete,
  onView,
  onFileView,
  onBulkDelete,
  onUploadClick,
  onAccessControl,
  searchTerm,
  onSearchChange,
  filterStatus,
  onFilterStatusChange,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
  isLoading = false,
  selectedContainer,
  canUpload = false,
  selectedAction,
  // 페이지네이션 관련
  currentPage = 1,
  totalItems = 0,
  itemsPerPage = 20,
  hasNext = false,
  hasPrevious = false,
  onPageChange,
  onItemsPerPageChange,
  isLoadingDocuments = false,
  containerActions
}) => {
  const [showFilters, setShowFilters] = useState(false);
  const hasSelection = selectedDocuments.size > 0;

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // 제목 글자 수 제한 (한글 40자, 영문 80자)
  const truncateTitle = (text: string, maxKorean: number = 40, maxEnglish: number = 80): string => {
    if (!text) return '';

    // 한글/영문 글자 수 계산
    let koreanCount = 0;
    let englishCount = 0;
    let truncated = '';

    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      const isKorean = /[\u3131-\u314e|\u314f-\u3163|\uac00-\ud7a3]/.test(char);

      if (isKorean) {
        if (koreanCount >= maxKorean) {
          return truncated + '...';
        }
        koreanCount++;
      } else {
        if (englishCount >= maxEnglish) {
          return truncated + '...';
        }
        englishCount++;
      }

      truncated += char;
    }

    return truncated;
  };

  const getFileIcon = (fileType: string): string => {
    switch (fileType.toLowerCase()) {
      case 'pdf': return '📄';
      case 'doc':
      case 'docx': return '📝';
      case 'xls':
      case 'xlsx': return '📊';
      case 'ppt':
      case 'pptx': return '📈';
      case 'txt': return '📃';
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif': return '🖼️';
      default: return '📄';
    }
  };

  // 백엔드 processing_status를 프론트엔드 DocumentStatus로 매핑
  const mapProcessingStatus = (backendStatus?: string): DocumentStatus => {
    if (!backendStatus) return 'completed';

    switch (backendStatus) {
      case 'pending': return 'uploading';
      case 'processing': return 'processing';
      case 'completed': return 'completed';
      case 'failed': return 'error';
      default: return 'completed';
    }
  };

  const getStatusIcon = (status: DocumentStatus) => {
    switch (status) {
      case 'uploading': return <Clock className="w-4 h-4 text-blue-500" />;
      case 'processing': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getStatusText = (status: DocumentStatus) => {
    switch (status) {
      case 'uploading': return '업로드 중';
      case 'processing': return '처리 중';
      case 'completed': return '완료';
      case 'error': return '오류';
    }
  };

  const getStatusColor = (status: DocumentStatus) => {
    switch (status) {
      case 'uploading': return 'bg-blue-100 text-blue-800';
      case 'processing': return 'bg-yellow-100 text-yellow-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'error': return 'bg-red-100 text-red-800';
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">지식을 불러오는 중...</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white border border-gray-200 rounded-lg">
      {/* 헤더 */}
      <div className="flex-shrink-0 p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            <h3 className="text-lg font-medium text-gray-900">지식 목록</h3>
            {/* 선택 개수 표시 (선택 시에만) */}
            {hasSelection && (
              <span className="text-sm text-gray-600">{selectedDocuments.size}개 선택됨</span>
            )}

            {/* 선택 액션 버튼 */}
            {selectedAction ? (
              <button
                onClick={hasSelection ? selectedAction.onClick : undefined}
                disabled={!hasSelection}
                className={
                  (!hasSelection)
                    ? 'inline-flex items-center px-3 py-1 rounded text-sm font-medium border border-blue-300 bg-blue-300 text-white opacity-60 cursor-not-allowed'
                    : (selectedAction.className || 'inline-flex items-center px-3 py-1 rounded text-sm font-medium border border-blue-600 bg-blue-600 text-white hover:bg-blue-700')
                }
                title={hasSelection ? '선택한 문서로 AI 채팅 시작' : '문서를 선택하면 AI 채팅을 시작할 수 있습니다'}
              >
                {selectedAction.icon}
                {selectedAction.label}
              </button>
            ) : (
              // 기본 동작: 커스텀 액션이 없으면 선택 시 삭제 버튼 표시
              hasSelection && (
                <button
                  onClick={onBulkDelete}
                  className="inline-flex items-center px-3 py-1 border border-red-300 rounded text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100"
                >
                  <Trash2 className="w-4 h-4 mr-1" />
                  삭제
                </button>
              )
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* 🆕 컨테이너 관리 버튼 (지식 등록 버튼 앞에 배치) */}
            {containerActions}

            {/* 지식 등록 버튼 */}
            {onUploadClick && (
              <div className="relative">
                <button
                  onClick={canUpload ? onUploadClick : undefined}
                  disabled={!canUpload}
                  className={`inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium ${canUpload
                    ? 'text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                    : 'text-gray-400 bg-gray-200 cursor-not-allowed'
                    }`}
                  title={
                    !canUpload
                      ? selectedContainer
                        ? `선택된 컨테이너 "${selectedContainer.name}"에 업로드 권한이 없습니다`
                        : '업로드할 지식 컨테이너를 먼저 선택해주세요'
                      : '새 문서를 업로드합니다'
                  }
                >
                  <Upload className="w-4 h-4 mr-2" />
                  지식 등록
                </button>
                {!canUpload && (
                  <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 text-xs text-gray-500 whitespace-nowrap">
                    {selectedContainer ? '권한 없음' : '컨테이너 선택 필요'}
                  </div>
                )}
              </div>
            )}

            {/* 필터 토글 */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-md border ${showFilters ? 'bg-blue-50 border-blue-300' : 'border-gray-300'}`}
            >
              <Filter className="w-4 h-4" />
            </button>

            {/* 뷰 모드 토글 */}
            <div className="flex rounded-lg border border-gray-300 overflow-hidden">
              <button
                onClick={() => onViewModeChange('list')}
                className={`p-2 ${viewMode === 'list' ? 'bg-blue-500 text-white' : 'bg-white text-gray-700'}`}
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={() => onViewModeChange('grid')}
                className={`p-2 ${viewMode === 'grid' ? 'bg-blue-500 text-white' : 'bg-white text-gray-700'}`}
              >
                <Grid className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* 검색 및 필터 */}
        <div className="flex items-center space-x-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="지식 검색..."
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {showFilters && (
            <div className="flex items-center space-x-2">
              <select
                value={filterStatus}
                onChange={(e) => onFilterStatusChange(e.target.value as DocumentStatus | 'all')}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="all">모든 상태</option>
                <option value="completed">완료</option>
                <option value="uploading">업로드 중</option>
                <option value="processing">처리 중</option>
                <option value="error">오류</option>
              </select>

              <select
                value={sortBy}
                onChange={(e) => onSortByChange(e.target.value as 'date' | 'name' | 'size')}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="date">등록일순</option>
                <option value="name">이름순</option>
                <option value="size">크기순</option>
              </select>

              <button
                onClick={() => onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                {sortOrder === 'asc' ? '↑' : '↓'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 컨텐츠 영역 */}
      <div className="flex-1 overflow-hidden">
        {documents.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">📚</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">지식이 없습니다</h3>
              <p className="text-gray-600 mb-4">이 컨테이너에는 등록된 지식이 없습니다.</p>
            </div>
          </div>
        ) : viewMode === 'list' ? (
          <div className="h-full overflow-auto">
            <table className="w-full table-fixed divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0 z-10">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                    <input
                      type="checkbox"
                      checked={selectedDocuments.size === documents.length && documents.length > 0}
                      onChange={onSelectAll}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider">
                    제목
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-24">
                    크기
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-28">
                    등록자
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-40">
                    등록 날짜
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-24">
                    상태
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-32">
                    작업
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {documents.map((document) => (
                  <tr key={document.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedDocuments.has(document.id)}
                        onChange={(e) => {
                          e.stopPropagation();
                          onDocumentSelect(document.id, e.target.checked);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 overflow-hidden">
                        <div className="text-xl flex-shrink-0">
                          {getFileIcon(document.file_extension || '')}
                        </div>
                        <div className="min-w-0 flex-1 overflow-hidden">
                          <div
                            className="text-sm font-medium text-gray-900 cursor-help"
                            title={document.title}
                          >
                            {truncateTitle(document.title)}
                          </div>
                          {document.title !== document.file_name && (
                            <div
                              className="text-sm text-gray-500 cursor-help"
                              title={document.file_name}
                            >
                              {truncateTitle(document.file_name)}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                      {formatFileSize(document.file_size || 0)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600 truncate" title={document.uploaded_by || '알 수 없음'}>
                      {document.uploaded_by || '알 수 없음'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                      {formatDate(document.created_at || '')}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        {getStatusIcon(mapProcessingStatus(document.processing_status))}
                        <span className={`text-sm px-2 py-1 rounded-full ${getStatusColor(mapProcessingStatus(document.processing_status))}`}>
                          {getStatusText(mapProcessingStatus(document.processing_status))}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium">
                      <div className="flex space-x-2">
                        {(mapProcessingStatus(document.processing_status) === 'completed') && (
                          <>
                            <button
                              onClick={() => onFileView ? onFileView(document) : onView(document)}
                              className="text-blue-600 hover:text-blue-900 transition-colors"
                              title="파일 뷰어"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                            {/* 편집 기능 비활성화 (백엔드 미구현)
                            <button
                              onClick={() => onEdit(document)}
                              className="text-blue-600 hover:text-blue-900 transition-colors"
                              title="편집"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            */}
                            <button
                              onClick={() => onDownload(document)}
                              className="text-green-600 hover:text-green-900 transition-colors"
                              title="다운로드"
                            >
                              <Download className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => onAccessControl?.(document)}
                              className="text-blue-600 hover:text-blue-900 transition-colors"
                              title="접근 권한 설정"
                            >
                              <Shield className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => onDelete(document.id)}
                              className="text-red-600 hover:text-red-900 transition-colors"
                              title="삭제"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {(mapProcessingStatus(document.processing_status) === 'error') && (
                          <button
                            onClick={() => onDelete(document.id)}
                            className="text-red-600 hover:text-red-900 transition-colors"
                            title="삭제"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          // 그리드 뷰
          <div className="h-full overflow-auto p-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {documents.map((document) => (
                <div key={document.id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow text-left">
                  <div className="flex items-start justify-between mb-3">
                    <div className="text-3xl">
                      {getFileIcon(document.file_extension || '')}
                    </div>
                    <input
                      type="checkbox"
                      checked={selectedDocuments.has(document.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        onDocumentSelect(document.id, e.target.checked);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </div>

                  <h3
                    className="text-sm font-medium text-gray-900 mb-1 line-clamp-2 text-left cursor-help"
                    title={document.title}
                  >
                    {document.title}
                  </h3>
                  <p
                    className="text-sm text-gray-500 mb-2 line-clamp-1 text-left cursor-help"
                    title={document.file_name}
                  >
                    {document.file_name}
                  </p>

                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm text-gray-500">
                      {formatFileSize(document.file_size || 0)}
                    </span>
                    <div className="flex items-center">
                      {getStatusIcon(mapProcessingStatus(document.processing_status))}
                      <span className={`ml-1 text-sm px-2 py-1 rounded-full ${getStatusColor(mapProcessingStatus(document.processing_status))}`}>
                        {getStatusText(mapProcessingStatus(document.processing_status))}
                      </span>
                    </div>
                  </div>

                  {(mapProcessingStatus(document.processing_status) === 'uploading' || mapProcessingStatus(document.processing_status) === 'processing') && (
                    <div className="mb-3">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300 animate-pulse"
                          style={{ width: '100%' }}
                        ></div>
                      </div>
                      <p className="text-sm text-gray-500 mt-1 text-center">
                        {mapProcessingStatus(document.processing_status) === 'processing' ? '백그라운드에서 처리 중...' : '업로드 중...'}
                      </p>
                    </div>
                  )}

                  {mapProcessingStatus(document.processing_status) === 'error' && document.processing_error && (
                    <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded">
                      <p className="text-sm text-red-600 line-clamp-2">{document.processing_error}</p>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">
                      {formatDate(document.created_at || '')}
                    </span>
                    <div className="flex space-x-1">
                      {onAccessControl && mapProcessingStatus(document.processing_status) === 'completed' && (
                        <button
                          onClick={() => onAccessControl(document)}
                          className="text-blue-600 hover:text-blue-900 transition-colors"
                          title="접근 권한 설정"
                        >
                          <Shield className="w-4 h-4" />
                        </button>
                      )}
                      {mapProcessingStatus(document.processing_status) === 'completed' && (
                        <>
                          <button
                            onClick={() => onFileView ? onFileView(document) : onView(document)}
                            className="p-1 text-blue-600 hover:text-blue-900 transition-colors"
                            title="파일 뷰어"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          {/* 편집 기능 비활성화 (백엔드 미구현)
                          <button
                            onClick={() => onEdit(document)}
                            className="p-1 text-blue-600 hover:text-blue-900 transition-colors"
                            title="편집"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          */}
                          <button
                            onClick={() => onDownload(document)}
                            className="p-1 text-green-600 hover:text-green-900 transition-colors"
                            title="다운로드"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => onDelete(document.id)}
                            className="p-1 text-red-600 hover:text-red-900 transition-colors"
                            title="삭제"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      {mapProcessingStatus(document.processing_status) === 'error' && (
                        <button
                          onClick={() => onDelete(document.id)}
                          className="p-1 text-red-600 hover:text-red-900 transition-colors"
                          title="삭제"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 페이지네이션 */}
      {totalItems > 0 && onPageChange && (
        <div className="border-t bg-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center text-sm text-gray-700">
            <span>
              전체 {totalItems.toLocaleString()}개 중 {((currentPage - 1) * itemsPerPage + 1).toLocaleString()}
              -
              {Math.min(currentPage * itemsPerPage, totalItems).toLocaleString()}개 표시
            </span>
            {onItemsPerPageChange && (
              <div className="ml-4 flex items-center">
                <label className="mr-2">페이지당:</label>
                <select
                  value={itemsPerPage}
                  onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={!hasPrevious || isLoadingDocuments}
              className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              이전
            </button>

            <div className="flex items-center space-x-1">
              {/* 페이지 번호 표시 로직 */}
              {Array.from({ length: Math.min(5, Math.ceil(totalItems / itemsPerPage)) }, (_, i) => {
                const totalPages = Math.ceil(totalItems / itemsPerPage);
                let pageNumber: number;

                if (totalPages <= 5) {
                  pageNumber = i + 1;
                } else {
                  // 현재 페이지 기준으로 앞뒤 2페이지씩 표시
                  const start = Math.max(1, currentPage - 2);
                  const end = Math.min(totalPages, start + 4);
                  pageNumber = start + i;

                  if (pageNumber > end) return null;
                }

                return (
                  <button
                    key={pageNumber}
                    onClick={() => onPageChange(pageNumber)}
                    disabled={isLoadingDocuments}
                    className={`px-3 py-1 text-sm border rounded ${currentPage === pageNumber
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-300 hover:bg-gray-50'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {pageNumber}
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={!hasNext || isLoadingDocuments}
              className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              다음
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default KnowledgeList;

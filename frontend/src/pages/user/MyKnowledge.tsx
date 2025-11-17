import { Lock, MessageCircle, ShieldQuestion } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import FileViewer from '../../components/common/FileViewer';
import SessionWarning from '../../components/common/SessionWarning';
import { useSelectedDocuments, useWorkContext } from '../../contexts/GlobalAppContext';
import { Document } from '../../contexts/types';
import { createPermissionRequest } from '../../services/permissionRequestService';
import ContainerCreateModal from './my-knowledge/components/ContainerCreateModal';
import KnowledgeContainerTree from './my-knowledge/components/KnowledgeContainerTree';
import KnowledgeEditModal from './my-knowledge/components/KnowledgeEditModal';
import KnowledgeList from './my-knowledge/components/KnowledgeList';
import KnowledgeUploadModal from './my-knowledge/components/KnowledgeUploadModal';
import KnowledgeViewModal from './my-knowledge/components/KnowledgeViewModal';
import { useMyKnowledge } from './my-knowledge/hooks/useMyKnowledge';

const MyKnowledge: React.FC = () => {
  // 권한 요청 모달 상태
  const [showAccessRequestModal, setShowAccessRequestModal] = useState(false);
  const [requestReason, setRequestReason] = useState('');
  const [requestRole, setRequestRole] = useState('VIEWER');
  const isReasonValid = requestReason.trim().length >= 10; // 최소 10자 요구사항

  // 🆕 컨테이너 생성/삭제 모달 상태
  const [showContainerCreateModal, setShowContainerCreateModal] = useState(false);
  const [deleteMode, setDeleteMode] = useState(false);

  // 글로벌 상태 hooks
  const {
    selectedDocuments: globalSelectedDocuments,
    addSelectedDocument,
    removeSelectedDocument
  } = useSelectedDocuments();
  const { navigateWithContext, updateWorkContext } = useWorkContext();

  const {
    isLoading,
    isLoadingDocuments,
    viewMode, setViewMode,
    containers,
    selectedContainer,
    expandedContainers,
    handleSelectContainer,
    handleToggleExpand,
    filteredDocuments,
    searchTerm, setSearchTerm,
    filterStatus, setFilterStatus,
    sortBy, setSortBy,
    sortOrder, setSortOrder,
    selectedDocuments,
    handleDocumentSelect,
    handleSelectAll,
    handleDownload,
    handleEdit,
    handleDelete,
    handleView,
    handleBulkDelete,
    // 페이지네이션 관련
    currentPage,
    itemsPerPage,
    totalItems,
    hasNext,
    hasPrevious,
    handlePageChange,
    handleItemsPerPageChange,
    // 모달 관련
    showUploadModal, setShowUploadModal,
    showEditModal, setShowEditModal,
    showViewModal, setShowViewModal,
    showFileViewer, setShowFileViewer,
    editingDocument,
    viewingDocument,
    selectedFiles, setSelectedFiles,
    handleUpload,
    handleSaveEdit,
    handleFileView,
    canUploadToContainer,
    canEditContainer,
    // 🆕 컨테이너 관리 함수들
    handleCreateContainer,
    handleDeleteContainer,
    canDeleteContainer,
    // 새 동기화 헬퍼
    syncSelectedDocuments,
  } = useMyKnowledge();

  // 페이지 진입 시 소스 페이지 타입 설정 (선택 패널 표시 및 전역 상태 동작 일관성)
  useEffect(() => {
    updateWorkContext({ sourcePageType: 'my-knowledge' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 문서 선택 핸들러 - 로컬과 글로벌 상태 모두 업데이트
  const isLocalSelectionRef = useRef(false);

  const handleDocumentSelectWithGlobal = useCallback((documentId: string, selected: boolean) => {
    // 로컬 선택 중임을 표시
    isLocalSelectionRef.current = true;

    // 1. 로컬 상태 업데이트 (useMyKnowledge의 handleDocumentSelect 호출)
    handleDocumentSelect(documentId, selected);

    // 2. 글로벌 상태 업데이트
    const document = filteredDocuments.find(doc => doc.id === documentId);
    if (document) {
      const globalDoc: Document = {
        fileId: document.id,
        fileName: document.file_name,
        originalName: document.title,
        fileSize: document.file_size,
        fileType: document.file_extension || '',
        uploadDate: document.created_at || '',
        containerName: document.container_path,
        containerId: typeof selectedContainer === 'string' ? selectedContainer : selectedContainer?.id || '',
        content: undefined,
        summary: undefined,
        keywords: document.keywords,
        isSelected: selected
      };

      if (selected) {
        addSelectedDocument(globalDoc);
      } else {
        removeSelectedDocument(globalDoc.fileId);
      }
    }

    // 로컬 선택 완료 후 플래그 리셋
    setTimeout(() => { isLocalSelectionRef.current = false; }, 100);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleDocumentSelect, filteredDocuments, selectedContainer]); // addSelectedDocument, removeSelectedDocument는 안정적인 함수들

  // 글로벌(페이지) 선택 문서가 변경되면 로컬 체크박스와 동기화 (채팅 → 내지식 복귀 시 등)
  useEffect(() => {
    // 로컬 선택 중에는 동기화하지 않음
    if (isLocalSelectionRef.current) return;

    const ids = (globalSelectedDocuments || []).map((d: Document) => d.fileId);
    // 현재 로컬 Set과 다른 경우에만 동기화하여 재렌더 루프 방지
    const localIds = Array.from(selectedDocuments);
    const isSame = ids.length === localIds.length && ids.every((id: string) => selectedDocuments.has(id));

    if (!isSame) {
      syncSelectedDocuments(ids);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globalSelectedDocuments]);

  // 권한 요청 핸들러
  const handleAccessRequest = async () => {
    if (!selectedContainer || !requestReason.trim()) {
      alert('요청 사유를 입력해주세요.');
      return;
    }

    try {
      const response = await createPermissionRequest({
        container_id: selectedContainer.id,
        requested_permission_level: requestRole,  // ✅ 올바른 필드명으로 수정
        request_reason: requestReason             // ✅ 올바른 필드명으로 수정
      });

      // 서버 응답 메시지 표시
      const message = response?.message || '권한 요청이 접수되었습니다. 컨테이너 관리자의 승인을 기다려주세요.';
      alert(message);

      setShowAccessRequestModal(false);
      setRequestReason('');
      setRequestRole('VIEWER');
    } catch (error: any) {
      console.error('권한 요청 실패:', error);
      const detail = error?.response?.data?.detail;
      if (Array.isArray(detail) && detail[0]?.msg) {
        alert(`요청이 거부되었습니다: ${detail[0].msg}`);
      } else if (typeof detail === 'string') {
        alert(`요청이 거부되었습니다: ${detail}`);
      } else {
        alert('권한 요청에 실패했습니다. 다시 시도해주세요.');
      }
    }
  };

  // 🆕 컨테이너 생성 핸들러
  const handleContainerCreate = async (data: { container_name: string; description?: string }) => {
    try {
      // 선택된 컨테이너를 부모로 설정
      const createData = {
        ...data,
        parent_container_id: selectedContainer?.id  // 🔗 현재 선택된 컨테이너를 부모로 설정
      };

      await handleCreateContainer(createData);
      alert('컨테이너가 성공적으로 생성되었습니다.');
      setShowContainerCreateModal(false);
    } catch (error: any) {
      console.error('컨테이너 생성 실패:', error);
      throw error; // 모달에서 에러 메시지 표시하도록 재throw
    }
  };

  // 🗑️ 컨테이너 삭제 핸들러
  const handleContainerDeleteClick = async (containerId: string, containerName: string) => {
    if (!window.confirm(`정말로 "${containerName}" 컨테이너를 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.`)) {
      return;
    }

    try {
      await handleDeleteContainer(containerId);
      alert('컨테이너가 성공적으로 삭제되었습니다.');
      setDeleteMode(false);
    } catch (error: any) {
      console.error('컨테이너 삭제 실패:', error);
      const errorMessage = error.response?.data?.detail || '컨테이너 삭제에 실패했습니다.';
      alert(errorMessage);
    }
  };

  const handleGoToChat = useCallback(() => {
    // 현재 상태 저장 (확장된 컨테이너 정보 포함)
    const currentState = {
      selectedContainer: selectedContainer?.id || null,
      expandedContainers: Array.from(expandedContainers), // Set을 Array로 변환
      searchTerm,
      filterStatus,
      sortBy,
      sortOrder,
      currentPage,
      viewMode
    };

    navigateWithContext(
      'agent-chat',
      currentState,
      { ragMode: true }
    );
  }, [navigateWithContext, selectedContainer, expandedContainers, searchTerm, filterStatus, sortBy, sortOrder, currentPage, viewMode]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">내 지식을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  const canUploadToSelectedContainer = canUploadToContainer(selectedContainer);

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* 세션 만료 경고 */}
      <SessionWarning warningMinutes={5} />

      <div className="flex-1 flex overflow-hidden">
        <div className="w-96 flex-shrink-0 p-6 pr-3">
          <div className="h-full overflow-y-auto">
            <KnowledgeContainerTree
              containers={containers}
              selectedContainer={selectedContainer}
              onSelectContainer={handleSelectContainer}
              expandedContainers={expandedContainers}
              onToggleExpand={handleToggleExpand}
              deleteMode={deleteMode}
              onDeleteContainer={handleContainerDeleteClick}
              canDeleteContainer={canDeleteContainer}
            />
          </div>
        </div>

        <div className="flex-1 p-6 pl-3 overflow-hidden relative">
          <div className="h-full">
            {selectedContainer && selectedContainer.permission === 'NONE' ? (
              <div className="h-full flex items-center justify-center bg-white rounded-lg border border-gray-200">
                <div className="text-center max-w-md p-8">
                  <Lock className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    접근 권한이 필요합니다
                  </h3>
                  <p className="text-gray-600 mb-6">
                    <strong>{selectedContainer.name}</strong> 컨테이너에 접근하려면 권한이 필요합니다.
                  </p>
                  <button
                    onClick={() => setShowAccessRequestModal(true)}
                    className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <ShieldQuestion className="w-5 h-5 mr-2" />
                    권한 요청하기
                  </button>
                </div>
              </div>
            ) : (
              <KnowledgeList
                documents={filteredDocuments}
                viewMode={viewMode}
                onViewModeChange={setViewMode}
                selectedDocuments={selectedDocuments}
                onDocumentSelect={handleDocumentSelectWithGlobal}
                onSelectAll={handleSelectAll}
                onDownload={handleDownload}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onView={handleView}
                onFileView={handleFileView}
                onBulkDelete={handleBulkDelete}
                onUploadClick={() => setShowUploadModal(true)}
                searchTerm={searchTerm}
                onSearchChange={setSearchTerm}
                filterStatus={filterStatus}
                onFilterStatusChange={setFilterStatus}
                sortBy={sortBy}
                onSortByChange={setSortBy}
                sortOrder={sortOrder}
                onSortOrderChange={setSortOrder}
                isLoading={isLoading}
                selectedContainer={selectedContainer}
                canUpload={canUploadToSelectedContainer || false}
                containerActions={
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setShowContainerCreateModal(true)}
                      className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 transition-colors"
                      title="새 개인 컨테이너 추가"
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      컨테이너 추가
                    </button>
                    <button
                      onClick={() => {
                        if (canDeleteContainer(selectedContainer)) {
                          handleContainerDeleteClick(selectedContainer!.id, selectedContainer!.name);
                        }
                      }}
                      disabled={!canDeleteContainer(selectedContainer)}
                      className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${!canDeleteContainer(selectedContainer)
                        ? 'text-gray-400 bg-gray-100 border border-gray-200 cursor-not-allowed'
                        : 'text-red-600 bg-red-50 border border-red-200 hover:bg-red-100'
                        }`}
                      title={
                        !selectedContainer
                          ? '삭제할 컨테이너를 먼저 선택해주세요'
                          : !canDeleteContainer(selectedContainer)
                            ? '자신이 생성한 빈 컨테이너만 삭제할 수 있습니다'
                            : `"${selectedContainer.name}" 컨테이너 삭제`
                      }
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      컨테이너 삭제
                    </button>
                  </div>
                }
                selectedAction={{
                  label: ' AI 에이전트',
                  onClick: handleGoToChat,
                  icon: <MessageCircle className="w-4 h-4 mr-1" />,
                  className: 'inline-flex items-center px-3 py-1 border border-blue-600 rounded text-sm font-medium text-white bg-blue-600 hover:bg-blue-700'
                }}
                // 페이지네이션 관련 props 추가
                currentPage={currentPage}
                totalItems={totalItems}
                itemsPerPage={itemsPerPage}
                hasNext={hasNext}
                hasPrevious={hasPrevious}
                onPageChange={handlePageChange}
                onItemsPerPageChange={handleItemsPerPageChange}
                isLoadingDocuments={isLoadingDocuments}
              />
            )}
          </div>
          {/* 플로팅 선택된 문서 패널 제거: 헤더의 'AI 에이전트' 버튼으로 대체 */}
        </div>
      </div>

      <KnowledgeUploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUpload={handleUpload}
        containers={containers}
        selectedContainer={selectedContainer}
        selectedFiles={selectedFiles}
        onFileSelect={setSelectedFiles}
      />

      <KnowledgeEditModal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        onSave={handleSaveEdit}
        document={editingDocument}
        containers={containers}
      />

      <KnowledgeViewModal
        isOpen={showViewModal}
        onClose={() => setShowViewModal(false)}
        document={viewingDocument}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onDownload={handleDownload}
        canEdit={selectedContainer ? canEditContainer(selectedContainer) : false}
      />

      <FileViewer
        isOpen={showFileViewer}
        onClose={() => setShowFileViewer(false)}
        document={viewingDocument}
        onDownload={handleDownload}
      />

      {/* 권한 요청 모달 */}
      {showAccessRequestModal && selectedContainer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              컨테이너 접근 권한 요청
            </h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                컨테이너
              </label>
              <div className="text-sm text-gray-900 bg-gray-50 p-3 rounded">
                {selectedContainer.name}
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                요청 권한
              </label>
              <select
                value={requestRole}
                onChange={(e) => setRequestRole(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              >
                <option value="VIEWER">조회 권한 (VIEWER)</option>
                <option value="EDITOR">편집 권한 (EDITOR)</option>
                <option value="MANAGER">관리 권한 (MANAGER)</option>
              </select>
            </div>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                요청 사유 <span className="text-red-500">*</span>
              </label>
              <textarea
                value={requestReason}
                onChange={(e) => setRequestReason(e.target.value)}
                placeholder="예) 프로젝트 A 문서 열람 필요 (업무 협업 목적)"
                className={`w-full border rounded-md px-3 py-2 h-24 resize-none ${isReasonValid ? 'border-gray-300' : 'border-red-300'}`}
                aria-invalid={!isReasonValid}
              />
              <div className="mt-1 text-xs flex justify-between">
                <span className={isReasonValid ? 'text-gray-500' : 'text-red-600'}>
                  {isReasonValid ? '충분한 사유가 입력되었습니다.' : '요청 사유는 최소 10자 이상 입력해주세요.'}
                </span>
                <span className="text-gray-400">{requestReason.trim().length}/10</span>
              </div>
            </div>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowAccessRequestModal(false);
                  setRequestReason('');
                  setRequestRole('VIEWER');
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                취소
              </button>
              <button
                onClick={handleAccessRequest}
                disabled={!isReasonValid}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                요청하기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 🆕 컨테이너 생성 모달 */}
      <ContainerCreateModal
        isOpen={showContainerCreateModal}
        onClose={() => setShowContainerCreateModal(false)}
        onSubmit={handleContainerCreate}
        parentContainerName={selectedContainer?.name}
      />
    </div>
  );
};

export default MyKnowledge;

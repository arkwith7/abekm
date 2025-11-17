import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useGlobalApp } from '../../../../contexts/GlobalAppContext';
import { useAuth } from '../../../../hooks/useAuth';
import {
  createUserContainer,
  deleteDocument,
  deleteUserContainer,
  downloadDocument,
  getFullContainerHierarchy,
  getMyDocuments,
  uploadDocument
} from '../../../../services/userService';
import { Document } from '../../../../types/user.types';
import { KnowledgeContainer } from '../components/KnowledgeContainerTree';

// 확장된 문서 타입 (업로드 진행 상태 포함)
export interface ExtendedDocument extends Document {
  status?: 'uploading' | 'processing' | 'completed' | 'error';
  uploadProgress?: number;
  errorMessage?: string;
}

export type DocumentStatus = 'uploading' | 'processing' | 'completed' | 'error';
export type ViewMode = 'grid' | 'list';
export type SortBy = 'date' | 'name' | 'size';
export type SortOrder = 'asc' | 'desc';

export const useMyKnowledge = () => {
  const { user } = useAuth();
  const { state: globalState, actions } = useGlobalApp();
  const savedMyKnowledgeState = globalState.pageStates?.myKnowledge;

  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>(
    savedMyKnowledgeState?.viewMode || 'list'
  );

  // 컨테이너 관련
  const [containers, setContainers] = useState<KnowledgeContainer[]>(
    savedMyKnowledgeState?.containers || []
  );
  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(
    savedMyKnowledgeState?.selectedContainer || null
  );
  const [expandedContainers, setExpandedContainers] = useState<Set<string>>(
    new Set(savedMyKnowledgeState?.expandedContainers || [])
  );

  // 문서 관련
  const [documents, setDocuments] = useState<ExtendedDocument[]>(
    savedMyKnowledgeState?.documents || []
  );

  // 페이지네이션 관련
  const [currentPage, setCurrentPage] = useState(
    savedMyKnowledgeState?.currentPage || 1
  );
  const [itemsPerPage, setItemsPerPage] = useState(5);
  const [totalItems, setTotalItems] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);

  // 검색 및 필터링
  const [searchTerm, setSearchTerm] = useState(
    savedMyKnowledgeState?.searchTerm || ''
  );
  const [filterStatus, setFilterStatus] = useState<DocumentStatus | 'all'>(
    (savedMyKnowledgeState?.filterStatus as DocumentStatus | 'all') || 'all'
  );
  const [sortBy, setSortBy] = useState<SortBy>(
    (savedMyKnowledgeState?.sortBy as SortBy) || 'date'
  );
  const [sortOrder, setSortOrder] = useState<SortOrder>(
    (savedMyKnowledgeState?.sortOrder as SortOrder) || 'desc'
  );

  // 모달 관련
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showFileViewer, setShowFileViewer] = useState(false);
  const [editingDocument, setEditingDocument] = useState<Document | null>(null);
  const [viewingDocument, setViewingDocument] = useState<Document | null>(null);

  // 업로드 관련
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  // 선택 관련
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const expandedContainersRef = useRef(expandedContainers);

  // expandedContainers 변경 감지 및 ref 업데이트
  useEffect(() => {
    expandedContainersRef.current = expandedContainers;
  }, [expandedContainers]);

  // 상태 변경 시 pageStates에 저장 (디바운스 적용)
  useEffect(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      actions.savePageState('myKnowledge', {
        containers, // 컨테이너 목록 저장
        documents, // 문서 목록 저장
        selectedContainer: selectedContainerId,
        expandedContainers: Array.from(expandedContainersRef.current),
        searchTerm,
        filterStatus,
        sortBy,
        sortOrder,
        selectedDocuments: globalState.pageStates?.myKnowledge?.selectedDocuments || [],
        currentPage,
        viewMode
      });
    }, 500); // 500ms 디바운스

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedContainerId, searchTerm, filterStatus, sortBy, sortOrder, currentPage, viewMode, containers, documents]);

  const findContainerById = useCallback((id: string, searchContainers: KnowledgeContainer[]): KnowledgeContainer | null => {
    const search = (items: KnowledgeContainer[]): KnowledgeContainer | null => {
      for (const container of items) {
        if (container.id === id) return container;
        if (container.children) {
          const found = search(container.children);
          if (found) return found;
        }
      }
      return null;
    };
    return search(searchContainers);
  }, []);

  // 🔍 컨테이너까지의 전체 경로(조상 ID들) 찾기
  const findPathToContainer = useCallback((targetId: string): string[] => {
    const path: string[] = [];

    const search = (items: KnowledgeContainer[], currentPath: string[]): boolean => {
      for (const container of items) {
        if (container.id === targetId) {
          path.push(...currentPath);
          return true;
        }
        if (container.children && container.children.length > 0) {
          if (search(container.children, [...currentPath, container.id])) {
            return true;
          }
        }
      }
      return false;
    };

    search(containers, []);
    return path;
  }, [containers]);

  const selectedContainer = useMemo(() => {
    if (!selectedContainerId) return null;
    return findContainerById(selectedContainerId, containers);
  }, [selectedContainerId, findContainerById, containers]);

  // 권한 확인 헬퍼 함수들
  const canUploadToContainer = useCallback((container: KnowledgeContainer | null): boolean => {
    if (!container) return false;
    return container.permission === 'OWNER' || container.permission === 'EDITOR';
  }, []);

  const canEditContainer = useCallback((container: KnowledgeContainer | null): boolean => {
    if (!container) return false;
    return container.permission === 'OWNER' || container.permission === 'EDITOR';
  }, []);

  const canViewContainer = useCallback((container: KnowledgeContainer | null): boolean => {
    if (!container) return false;
    return ['OWNER', 'EDITOR', 'VIEWER'].includes(container.permission);
  }, []);

  // 🆕 컨테이너 생성 함수
  const handleCreateContainer = useCallback(async (data: {
    container_name: string;
    description?: string;
    parent_container_id?: string;
  }) => {
    try {
      console.log('📁 컨테이너 생성 시작:', data);

      const response = await createUserContainer(data);

      if (response.success) {
        console.log('✅ 컨테이너 생성 성공:', response.container_id);

        // 컨테이너 목록 새로고침
        await loadInitialData();

        // 🎯 생성된 컨테이너로 자동 이동
        setSelectedContainerId(response.container_id);

        // 📂 생성된 컨테이너까지의 전체 경로를 확장 (부모, 조상 모두)
        if (data.parent_container_id) {
          // 부모 컨테이너까지의 전체 경로 찾기
          const pathToParent = findPathToContainer(data.parent_container_id);
          console.log('📍 확장할 경로:', pathToParent);

          setExpandedContainers(prev => {
            const newSet = new Set(prev);
            // 부모 컨테이너 추가
            newSet.add(data.parent_container_id!);
            // 조상 컨테이너들 모두 추가
            pathToParent.forEach(ancestorId => newSet.add(ancestorId));
            return newSet;
          });
        }

        return response;
      } else {
        throw new Error(response.message || '컨테이너 생성 실패');
      }
    } catch (error: any) {
      console.error('❌ 컨테이너 생성 실패:', error);
      throw error;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findPathToContainer]);

  // 🗑️ 컨테이너 삭제 함수
  const handleDeleteContainer = useCallback(async (containerId: string) => {
    try {
      console.log('🗑️ 컨테이너 삭제 시작:', containerId);

      // 🔍 삭제 전에 부모 컨테이너 ID 저장
      const containerToDelete = findContainerById(containerId, containers);
      const parentContainerId = containerToDelete?.parent_id || null;

      console.log('📁 삭제할 컨테이너의 부모:', parentContainerId);

      const response = await deleteUserContainer(containerId);

      if (response.success) {
        console.log('✅ 컨테이너 삭제 성공');

        // 컨테이너 목록 새로고침
        await loadInitialData();

        // 🎯 삭제된 컨테이너가 선택된 상태라면 부모 컨테이너로 이동
        if (selectedContainerId === containerId && parentContainerId) {
          setSelectedContainerId(parentContainerId);
          console.log('📍 포커스 이동:', parentContainerId);

          // 📂 부모 컨테이너까지의 전체 경로를 확장
          const pathToParent = findPathToContainer(parentContainerId);
          console.log('📍 확장할 경로:', pathToParent);

          setExpandedContainers(prev => {
            const newSet = new Set(prev);
            // 부모 컨테이너 추가
            newSet.add(parentContainerId);
            // 조상 컨테이너들 모두 추가
            pathToParent.forEach(ancestorId => newSet.add(ancestorId));
            return newSet;
          });
        } else if (selectedContainerId === containerId && !parentContainerId) {
          // 최상위 컨테이너 삭제 시 선택 해제
          setSelectedContainerId(null);
        }

        return response;
      } else {
        throw new Error(response.message || '컨테이너 삭제 실패');
      }
    } catch (error: any) {
      console.error('❌ 컨테이너 삭제 실패:', error);
      throw error;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedContainerId, findContainerById, findPathToContainer]);

  // 🔍 삭제 가능한 컨테이너 확인
  const canDeleteContainer = useCallback((container: KnowledgeContainer | null) => {
    if (!container) return false;

    // OWNER 권한이고 USER_ prefix가 있는 컨테이너만 삭제 가능
    const isUserContainer = container.id.startsWith('USER_');
    const hasOwnerPermission = container.permission === 'OWNER';
    const hasNoDocuments = (container.document_count || 0) === 0;

    return isUserContainer && hasOwnerPermission && hasNoDocuments;
  }, []);

  const filteredDocuments = useMemo(() => {
    console.log('🔍 필터링 시작:', {
      totalDocuments: documents.length,
      selectedContainerId,
      searchTerm,
      filterStatus,
      sortBy,
      sortOrder
    });

    let filtered = documents.filter(doc => {
      const matchesSearch = !searchTerm ||
        doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.file_name?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = filterStatus === 'all' || doc.status === filterStatus;
      const matchesContainer = !selectedContainerId || doc.container_path === selectedContainerId;

      console.log(`📄 문서 "${doc.title}" 필터링:`, {
        container_path: doc.container_path,
        selectedContainerId,
        matchesContainer,
        matchesSearch,
        matchesStatus,
        included: matchesSearch && matchesStatus && matchesContainer
      });

      return matchesSearch && matchesStatus && matchesContainer;
    });

    console.log('📊 필터링 결과:', {
      filteredCount: filtered.length,
      selectedContainer: selectedContainerId
    });

    filtered.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'name':
          comparison = a.title.localeCompare(b.title);
          break;
        case 'size':
          comparison = (a.file_size || 0) - (b.file_size || 0);
          break;
        default:
          const aDate = new Date(a.created_at || 0).getTime();
          const bDate = new Date(b.created_at || 0).getTime();
          comparison = aDate - bDate;
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [documents, selectedContainerId, searchTerm, filterStatus, sortBy, sortOrder]);

  const loadDocuments = useCallback(async (page: number = 1, containerId?: string) => {
    if (loadingDocsRef.current) {
      console.log('SKIP: Document loading in progress');
      return;
    }
    loadingDocsRef.current = true;

    setIsLoadingDocuments(true);
    try {
      const skip = (page - 1) * itemsPerPage;
      console.log(`API_CALL: Loading documents (page: ${page}, container: ${containerId})`);
      const docs = await getMyDocuments({
        skip,
        limit: itemsPerPage,
        container_id: containerId || undefined
      });

      const documentsWithStatus = docs.documents.map((doc: Document) => ({
        ...doc,
        status: (doc.processing_status === 'pending' ? 'uploading' :
          doc.processing_status === 'processing' ? 'processing' :
            doc.processing_status === 'failed' ? 'error' :
              'completed') as 'uploading' | 'processing' | 'completed' | 'error'
      }));

      setDocuments(documentsWithStatus);
      setTotalItems(docs.total);
      setHasNext(docs.has_next);
      setHasPrevious(docs.has_previous);
      setCurrentPage(page);

      console.log('SUCCESS: Documents loaded', {
        page,
        total: docs.total,
        count: docs.current_page_count,
        processing: documentsWithStatus.filter((d: any) =>
          d.status === 'processing' || d.status === 'uploading'
        ).length
      });

      const hasProcessing = documentsWithStatus.some((d: any) =>
        d.status === 'processing' || d.status === 'uploading'
      );

      if (hasProcessing) {
        console.log('REFRESH: Processing documents detected, auto-refresh in 5s');
        setTimeout(() => {
          loadingDocsRef.current = false;
          loadDocuments(page, containerId);
        }, 5000);
      }

    } catch (error: any) {
      console.error('ERROR: Document load failed:', error);

      if (error?.response?.status === 403) {
        console.log('PERMISSION_ERROR: No document access');
        setDocuments([]);
        setTotalItems(0);
        setHasNext(false);
        setHasPrevious(false);
        setIsLoadingDocuments(false);
        loadingDocsRef.current = false;
        return;
      }

      setDocuments([]);
      setTotalItems(0);
      setHasNext(false);
      setHasPrevious(false);
    } finally {
      setIsLoadingDocuments(false);
      loadingDocsRef.current = false;
    }
  }, [itemsPerPage]);

  const loadingRef = useRef(false);
  const mountedRef = useRef(false);
  const initialLoadDoneRef = useRef(false);

  const loadInitialData = useCallback(async (force = false) => {
    if (loadingRef.current && !force) {
      console.log('SKIP: Loading already in progress');
      return;
    }

    if (initialLoadDoneRef.current && !force) {
      console.log('SKIP: Initial load already done');
      return;
    }

    // 강제 새로고침이 아니고, 저장된 상태가 있다면 복원 시도
    if (!force && savedMyKnowledgeState?.containers && savedMyKnowledgeState.containers.length > 0) {
      console.log('🔄 Restoring from saved state...');
      setContainers(savedMyKnowledgeState.containers as KnowledgeContainer[]);
      setDocuments(savedMyKnowledgeState.documents as ExtendedDocument[] || []);
      setSelectedContainerId(savedMyKnowledgeState.selectedContainer || null);
      setExpandedContainers(new Set(savedMyKnowledgeState.expandedContainers || []));
      setCurrentPage(savedMyKnowledgeState.currentPage || 1);
      setSearchTerm(savedMyKnowledgeState.searchTerm || '');
      setViewMode(savedMyKnowledgeState.viewMode || 'list');

      setIsLoading(false);
      initialLoadDoneRef.current = true;
      console.log('✅ Restored from saved state successfully.');
      return;
    }

    loadingRef.current = true;
    setIsLoading(true);
    try {
      if (!user) {
        console.log('SKIP: No user authentication');
        loadingRef.current = false;
        setIsLoading(false);
        return;
      }

      console.log('🚀 Fetching initial data from backend...');

      const containerResponse = await getFullContainerHierarchy();
      if (!containerResponse?.success || !containerResponse.containers) {
        throw new Error('Failed to load container hierarchy');
      }

      const mapToKnowledgeContainer = (node: any): KnowledgeContainer => ({
        id: node.id,
        name: node.name,
        path: node.org_path || `/${node.id}`,
        parent_id: node.parent_id,
        permission: node.permission || 'NONE',
        document_count: node.document_count || 0,
        children: node.children ? node.children.map(mapToKnowledgeContainer) : [],
      });

      const conts = containerResponse.containers.map(mapToKnowledgeContainer);
      setContainers(conts);

      const findFirstAccessible = (items: KnowledgeContainer[]): KnowledgeContainer | null => {
        for (const item of items) {
          if (item.permission !== 'NONE') return item;
          if (item.children) {
            const found = findFirstAccessible(item.children);
            if (found) return found;
          }
        }
        return null;
      };

      const containerToSelect = findContainerById(savedMyKnowledgeState?.selectedContainer || '', conts) || findFirstAccessible(conts);

      if (containerToSelect) {
        setSelectedContainerId(containerToSelect.id);

        const docs = await getMyDocuments({ skip: 0, limit: itemsPerPage, container_id: containerToSelect.id });
        const documentsWithStatus = docs.documents.map((doc: Document) => ({ ...doc, status: 'completed' as const }));
        setDocuments(documentsWithStatus);
        setTotalItems(docs.total);
        setHasNext(docs.has_next);
        setHasPrevious(docs.has_previous);
        setCurrentPage(1);
      }

      initialLoadDoneRef.current = true;
      console.log('✅ Initial data fetched successfully.');

    } catch (error) {
      console.error('❌ Failed to load initial data:', error);
    } finally {
      setIsLoading(false);
      loadingRef.current = false;
    }
  }, [user, itemsPerPage, savedMyKnowledgeState, findContainerById]);

  useEffect(() => {
    if (mountedRef.current) {
      console.log('SKIP: Already mounted (Strict Mode)');
      return;
    }
    mountedRef.current = true;

    if (user) {
      loadInitialData();
    }

    return () => {
      console.log('CLEANUP: Component unmounting');
      // ✅ initialLoadDoneRef는 리셋하지 않음 - 세션 동안 유지
      loadingRef.current = false;
      mountedRef.current = false;
    };
  }, [user, loadInitialData]);

  const handleSelectContainer = (container: KnowledgeContainer) => {
    setSelectedContainerId(container.id);
    setSelectedDocuments(new Set());
  };

  const handleToggleExpand = (containerId: string) => {
    setExpandedContainers(prev => {
      const newSet = new Set(prev);
      if (newSet.has(containerId)) newSet.delete(containerId);
      else newSet.add(containerId);
      return newSet;
    });
  };

  const handleUpload = async (files: File[], containerId: string, metadataArray: any[]) => {
    const container = findContainerById(containerId, containers);
    if (!container) return;

    const uploadPromises = files.map(async (file, index) => {
      const tempId = `temp_${Date.now()}_${Math.random()}`;
      const metadata = metadataArray[index];

      const tempDoc: ExtendedDocument = {
        id: tempId,
        title: metadata.title || file.name,
        file_name: file.name,
        file_size: file.size,
        file_extension: file.name.split('.').pop() || '',
        container_path: container.id,
        created_at: new Date().toISOString(),
        uploaded_by: user?.username || 'unknown',
        status: 'uploading',
        uploadProgress: 0,
      };

      setDocuments(prev => [tempDoc, ...prev]);

      try {
        const result = await uploadDocument(file, container.id, metadata, (progress) => {
          setDocuments(prev => prev.map(doc =>
            doc.id === tempId ? { ...doc, uploadProgress: progress.progress } : doc
          ));
        });

        setDocuments(prev => prev.map(doc =>
          doc.id === tempId ? { ...result.document, status: 'completed' } : doc
        ));
      } catch (error: any) {
        setDocuments(prev => prev.map(doc =>
          doc.id === tempId ? { ...doc, status: 'error', errorMessage: error?.message || 'Upload failed' } : doc
        ));
      }
    });

    await Promise.all(uploadPromises);

    // 업로드 완료 후 실제 문서 목록을 API에서 새로고침
    try {
      console.log('🔄 업로드 완료 후 문서 목록 새로고침...');
      await loadInitialData(true); // 강제 새로고침
    } catch (error: any) {
      console.error('❌ 문서 목록 새로고침 실패:', error);

      // 403 권한 오류인 경우 조용히 처리
      if (error?.response?.status === 403) {
        console.log('🚫 문서 목록 새로고침 권한 없음');
        return;
      }
    }

    setSelectedFiles([]);
    setShowUploadModal(false);
  };

  const handleDocumentSelect = (documentId: string, selected: boolean) => {
    setSelectedDocuments(prev => {
      const newSet = new Set(prev);
      if (selected) newSet.add(documentId);
      else newSet.delete(documentId);
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (selectedDocuments.size === filteredDocuments.length) {
      setSelectedDocuments(new Set());
    } else {
      setSelectedDocuments(new Set(filteredDocuments.map(doc => doc.id)));
    }
  };

  const handleDownload = async (document: ExtendedDocument) => {
    try {
      // Pass document title and extension to download function
      await downloadDocument(document.id, document.title || document.file_name, document.file_extension);
    } catch (error) {
      console.error('Download failed:', error);
      alert('다운로드에 실패했습니다.');
    }
  };

  const handleEdit = (document: ExtendedDocument) => {
    setEditingDocument(document);
    setShowEditModal(true);
  };

  const handleSaveEdit = async (documentId: string, updates: Partial<Document>) => {
    // This should be replaced with an actual API call
    setDocuments(prev => prev.map(doc =>
      doc.id === documentId ? { ...doc, ...updates } : doc
    ));
    setShowEditModal(false);
  };

  const handleView = (document: ExtendedDocument) => {
    setViewingDocument(document);
    setShowViewModal(true);
  };

  // 파일 뷰어 핸들러 추가
  const handleFileView = (document: ExtendedDocument) => {
    setViewingDocument(document);
    setShowFileViewer(true);
  };

  const handleDelete = async (documentId: string) => {
    if (!window.confirm('정말로 이 지식을 삭제하시겠습니까?')) return;
    try {
      await deleteDocument(documentId);
      setDocuments(prev => prev.filter(doc => doc.id !== documentId));
      setSelectedDocuments(prev => {
        const newSet = new Set(prev);
        newSet.delete(documentId);
        return newSet;
      });
    } catch (error) {
      console.error('Delete failed:', error);
      alert('삭제에 실패했습니다.');
    }
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`선택한 ${selectedDocuments.size}개 지식을 삭제하시겠습니까?`)) return;
    try {
      await Promise.all(Array.from(selectedDocuments).map(id => deleteDocument(id)));
      setDocuments(prev => prev.filter(doc => !selectedDocuments.has(doc.id)));
      setSelectedDocuments(new Set());
    } catch (error) {
      console.error('Bulk delete failed:', error);
      alert('일괄 삭제에 실패했습니다.');
    }
  };

  // 페이지네이션 핸들러
  const handlePageChange = useCallback((page: number) => {
    loadDocuments(page, selectedContainerId || undefined);
  }, [loadDocuments, selectedContainerId]);

  const handleItemsPerPageChange = useCallback((newItemsPerPage: number) => {
    setItemsPerPage(newItemsPerPage);
    setCurrentPage(1);
    loadDocuments(1, selectedContainerId || undefined);
  }, [loadDocuments, selectedContainerId]); // itemsPerPage 제거

  const loadingDocsRef = useRef(false);
  const lastLoadedContainerRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selectedContainerId) {
      return;
    }

    if (lastLoadedContainerRef.current === selectedContainerId) {
      console.log(`SKIP: Documents already loaded for ${selectedContainerId}`);
      return;
    }

    if (loadingDocsRef.current) {
      console.log('SKIP: Documents loading in progress');
      return;
    }

    console.log(`LOAD: Fetching documents for ${selectedContainerId}`);
    lastLoadedContainerRef.current = selectedContainerId;
    setCurrentPage(1);
    loadDocuments(1, selectedContainerId);
  }, [selectedContainerId, loadDocuments]);

  return {
    isLoading,
    isLoadingDocuments,
    viewMode, setViewMode,
    containers,
    documents,
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
    loadDocuments,
    // 모달 관련
    showUploadModal, setShowUploadModal,
    showEditModal, setShowEditModal,
    showViewModal, setShowViewModal,
    showFileViewer, setShowFileViewer,
    editingDocument, setEditingDocument,
    viewingDocument, setViewingDocument,
    selectedFiles, setSelectedFiles,
    handleUpload,
    handleSaveEdit,
    handleFileView,
    // 권한 관련 함수들
    canUploadToContainer,
    canEditContainer,
    canViewContainer,
    // 🆕 컨테이너 관리 함수들
    handleCreateContainer,
    handleDeleteContainer,
    canDeleteContainer,
    // 외부(선택 패널 등)에서 체크박스 상태 동기화를 위한 헬퍼
    syncSelectedDocuments: (ids: string[]) => {
      setSelectedDocuments((prev) => {
        // 동일한 집합이면 상태 변경하지 않음
        if (prev.size === ids.length) {
          let allMatch = true;
          for (const id of ids) {
            if (!prev.has(id)) { allMatch = false; break; }
          }
          if (allMatch) return prev; // no-op
        }
        return new Set(ids);
      });
    },
  };
};

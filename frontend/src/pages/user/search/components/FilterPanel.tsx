import React, { useState, useEffect } from 'react';
import { SearchFilters, ContainerNode, SearchType } from '../types/index';
import { authService } from '../../../../services/authService';

// 백엔드 API에서 사용자별 접근 가능한 컨테이너 목록 조회
const getUserAccessibleContainers = async (): Promise<ContainerNode[]> => {
  try {
    // 1. 인증 상태 확인
    if (!authService.isAuthenticated()) {
      throw new Error('인증이 필요합니다. 다시 로그인해주세요.');
    }

    // 2. 토큰 가져오기
    const token = authService.getToken();
    if (!token) {
      throw new Error('인증 토큰을 찾을 수 없습니다.');
    }

    // 3. 사용자 정보 가져오기
    const userInfo = authService.getUser();
    if (!userInfo || !userInfo.emp_no) {
      throw new Error('사용자 정보를 찾을 수 없습니다.');
    }

    console.log(`✅ 인증된 사용자: ${userInfo.emp_no} (${userInfo.emp_name})`);

    // 4. API 호출
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };
    
    const apiUrl = `/api/v1/users/me/knowledge-containers`;
    console.log(`🌐 API 호출: ${apiUrl}`);
    
    const containersResponse = await fetch(apiUrl, { headers });

    if (!containersResponse.ok) {
      const errorText = await containersResponse.text();
      console.error('❌ API 응답 오류:', {
        status: containersResponse.status,
        statusText: containersResponse.statusText,
        errorText
      });
      
      // 401 에러인 경우 자동 로그아웃
      if (containersResponse.status === 401) {
        authService.logout();
        throw new Error('인증이 만료되었습니다. 다시 로그인해주세요.');
      }
      
      throw new Error(`컨테이너 목록 조회 실패: ${containersResponse.status} - ${errorText}`);
    }

    const containersData = await containersResponse.json();
    console.log('✅ 백엔드에서 받은 컨테이너 데이터:', containersData);

    // 5. 백엔드 응답을 프론트엔드 ContainerNode 형식으로 변환
    const transformedContainers = transformBackendContainersToNodes(containersData.containers || []);
    console.log(`✅ 변환된 컨테이너 트리: ${transformedContainers.length}개`, transformedContainers);
    
    return transformedContainers;

  } catch (error) {
    console.error('❌ 컨테이너 목록 조회 중 전체 오류:', error);
    throw error;
  }
};

// 백엔드 컨테이너 데이터를 프론트엔드 형식으로 변환
const transformBackendContainersToNodes = (backendContainers: any[]): ContainerNode[] => {
  if (!backendContainers || !Array.isArray(backendContainers)) {
    console.warn('유효하지 않은 컨테이너 데이터:', backendContainers);
    return [];
  }

  const containerMap = new Map<string, ContainerNode>();
  const rootContainers: ContainerNode[] = [];

  // 1차: 모든 컨테이너를 맵에 추가
  backendContainers.forEach((container) => {
    const node: ContainerNode = {
      id: container.container_id,
      name: container.container_name || container.container_id,
      children: [],
      permissionLevel: container.user_permission, // knowledge-containers API 응답 형식
      containerType: container.container_type,
      accessLevel: container.access_level,
      permissionSource: 'direct', // 기본값 설정
      hierarchyPath: container.hierarchy_path, // 계층 경로 추가
    };
    containerMap.set(container.container_id, node);
  });

  // 2차: 계층 구조 구성
  backendContainers.forEach((container) => {
    const node = containerMap.get(container.container_id);
    if (!node) return;

    // 1) 명시적 parent_id가 있는 경우
    if (container.parent_container_id && containerMap.has(container.parent_container_id)) {
      const parent = containerMap.get(container.parent_container_id);
      if (parent && parent.id !== node.id) {
        parent.children = parent.children || [];
        parent.children.push(node);
        return;
      }
    }

    // 2) container_id 패턴으로 계층 구조 판단 (예: "woongjin_hr"의 부모는 "woongjin")
    const parts = container.container_id.split('_');
    if (parts.length > 1) {
      const parentId = parts[0];
      const parent = containerMap.get(parentId);
      
      if (parent && parent.id !== node.id) {
        parent.children = parent.children || [];
        parent.children.push(node);
        return;
      }
    }

    // 3) 기타 조건에 해당하지 않으면 루트 레벨에 추가
    rootContainers.push(node);
  });

  // 자식 컨테이너를 이름순으로 정렬
  const sortContainerChildren = (containers: ContainerNode[]) => {
    containers.forEach(container => {
      if (container.children && container.children.length > 0) {
        container.children.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
        sortContainerChildren(container.children);
      }
    });
  };

  // 루트 컨테이너도 이름순으로 정렬
  rootContainers.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  sortContainerChildren(rootContainers);

  return rootContainers;
};

interface FilterPanelProps {
  filters: SearchFilters;
  updateFilters: (newFilters: Partial<SearchFilters>) => void;
  resultsCount?: number;
}

const documentTypeOptions = [
  { value: 'pdf', label: 'PDF' },
  { value: 'hwpx', label: '아래한글' },
  { value: 'docx', label: 'Word' },
  { value: 'pptx', label: 'PowerPoint' },
  { value: 'xlsx', label: 'Excel' },
  { value: 'txt', label: 'Text' },
  { value: 'md', label: 'Markdown' },
];

const ContainerTree: React.FC<{
  nodes: ContainerNode[];
  selectedIds: string[];
  onSelectionChange: (id: string) => void;
}> = ({ nodes, selectedIds, onSelectionChange }) => {
  
  // 권한 레벨에 따른 표시 아이콘 및 색상
  const getPermissionIcon = (permissionLevel?: string) => {
    switch (permissionLevel) {
      case 'FULL_ACCESS':
        return { icon: '🔧', color: 'text-red-600', label: '전체 관리' };
      case 'ADMIN':
        return { icon: '👑', color: 'text-purple-600', label: '관리자' };
      case 'MANAGER':
        return { icon: '📝', color: 'text-blue-600', label: '매니저' };
      case 'EDITOR':
        return { icon: '✏️', color: 'text-green-600', label: '편집자' };
      case 'VIEWER':
        return { icon: '👁️', color: 'text-gray-600', label: '열람자' };
      default:
        return { icon: '📁', color: 'text-gray-500', label: '기본' };
    }
  };

  return (
    <div className="space-y-2">
      {nodes.map((node) => {
        const permission = getPermissionIcon(node.permissionLevel);
        return (
          <div key={node.id}>
            <label className="flex items-center group hover:bg-gray-50 p-1 rounded">
              <input
                type="checkbox"
                checked={selectedIds.includes(node.id)}
                onChange={() => onSelectionChange(node.id)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="ml-2 flex-1 text-sm text-gray-900 flex items-center">
                <span className="mr-1">{permission.icon}</span>
                {node.name}
                {node.permissionLevel && (
                  <span className={`ml-2 text-xs ${permission.color} opacity-75`} title={permission.label}>
                    ({permission.label})
                  </span>
                )}
              </span>
            </label>
            {node.children && node.children.length > 0 && (
              <div className="ml-6 mt-1 space-y-1 border-l border-gray-200 pl-4">
                <ContainerTree 
                  nodes={node.children} 
                  selectedIds={selectedIds} 
                  onSelectionChange={onSelectionChange} 
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const FilterPanel: React.FC<FilterPanelProps> = ({ filters, updateFilters, resultsCount }) => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [containerOptions, setContainerOptions] = useState<ContainerNode[]>([]);
  const [isLoadingContainers, setIsLoadingContainers] = useState(false);
  const [containerError, setContainerError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUserContainers = async () => {
      setIsLoadingContainers(true);
      setContainerError(null);
      
      try {
        // 사용자별 접근 가능한 컨테이너 목록을 동적으로 조회
        const userContainers = await getUserAccessibleContainers();
        setContainerOptions(userContainers);
        
        if (userContainers.length === 0) {
          setContainerError('접근 가능한 컨테이너가 없습니다. 관리자에게 권한을 요청해주세요.');
        }
      } catch (error) {
        console.error('컨테이너 목록 조회 실패:', error);
        
        // 구체적인 오류 메시지 설정
        let errorMessage = '컨테이너 목록을 불러올 수 없습니다.';
        if (error instanceof Error) {
          if (error.message.includes('인증 토큰이 없습니다')) {
            errorMessage = '로그인이 필요합니다. 다시 로그인해주세요.';
          } else if (error.message.includes('401')) {
            errorMessage = '인증이 만료되었습니다. 다시 로그인해주세요.';
          } else if (error.message.includes('403')) {
            errorMessage = '접근 권한이 없습니다. 관리자에게 문의해주세요.';
          } else if (error.message.includes('404')) {
            errorMessage = 'API 엔드포인트를 찾을 수 없습니다. 시스템 관리자에게 문의해주세요.';
          } else if (error.message.includes('500')) {
            errorMessage = '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
          } else if (error.message.includes('사번')) {
            errorMessage = '사용자 정보를 확인할 수 없습니다. 관리자에게 문의해주세요.';
          }
        }
        
        setContainerError(errorMessage);
        // 오류 시 기본 컨테이너 표시하지 않음 (권한 없는 컨테이너 노출 방지)
        setContainerOptions([]);
      } finally {
        setIsLoadingContainers(false);
      }
    };

    fetchUserContainers();
  }, []);

  const handleContainerChange = (id: string) => {
    const newContainerIds = filters.containerIds.includes(id)
      ? filters.containerIds.filter((cid: string) => cid !== id)
      : [...filters.containerIds, id];
    updateFilters({ containerIds: newContainerIds });
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-gray-700">검색 방식:</label>
          <select
            value={filters.searchType}
            onChange={(e) => updateFilters({ searchType: e.target.value as SearchType })}
            className="px-3 py-1 pr-8 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="hybrid">🔄 하이브리드 (추천)</option>
            <option value="vector_only">🧠 의미 검색</option>
            <option value="keyword_only">🔤 키워드 검색</option>
          </select>
        </div>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="inline-flex items-center px-3 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4" />
          </svg>
          고급 필터 {showAdvanced ? '▲' : '▼'}
        </button>

        {/* 활성 필터 표시 */}
        {filters.containerIds.length > 0 && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            📁 컨테이너 {filters.containerIds.length}개
          </span>
        )}
        {filters.documentTypes.length > 0 && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            📄 파일타입 {filters.documentTypes.length}개
          </span>
        )}
        {resultsCount !== undefined && resultsCount > 0 && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            📊 결과 {resultsCount}건
          </span>
        )}
      </div>

      {showAdvanced && (
        <div className="bg-gray-50 rounded-lg p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* 검색 범위 (컨테이너) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                검색 범위
                {isLoadingContainers && <span className="text-xs text-gray-500 ml-2">로딩 중...</span>}
              </label>
              
              {containerError && (
                <div className="text-xs text-red-600 mb-2 p-2 bg-red-50 rounded">
                  {containerError}
                </div>
              )}
              
              <div className="space-y-2 max-h-48 overflow-y-auto p-2 border rounded bg-white">
                {isLoadingContainers ? (
                  <div className="flex items-center justify-center py-4">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                    <span className="ml-2 text-sm text-gray-600">사용자 권한 조회 중...</span>
                  </div>
                ) : containerOptions.length > 0 ? (
                  <ContainerTree
                    nodes={containerOptions}
                    selectedIds={filters.containerIds}
                    onSelectionChange={handleContainerChange}
                  />
                ) : (
                  <div className="text-sm text-gray-500 py-2">
                    접근 가능한 컨테이너가 없습니다.
                  </div>
                )}
              </div>
              
              <label className="flex items-center mt-2">
                <input
                  type="checkbox"
                  checked={filters.includeSubContainers}
                  onChange={(e) => updateFilters({ includeSubContainers: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  disabled={isLoadingContainers}
                />
                <span className="ml-2 text-sm text-gray-800">하위 컨테이너 포함</span>
              </label>
            </div>

            {/* 파일 형식 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">파일 형식</label>
              <div className="space-y-2">
                {documentTypeOptions.map((type) => (
                  <label key={type.value} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={filters.documentTypes.includes(type.value)}
                      onChange={(e) => {
                        const newTypes = e.target.checked
                          ? [...filters.documentTypes, type.value]
                          : filters.documentTypes.filter((t: string) => t !== type.value);
                        updateFilters({ documentTypes: newTypes });
                      }}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <span className="ml-2 text-sm text-gray-900">{type.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* 유사도 임계값 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                유사도: {(filters.scoreThreshold * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={filters.scoreThreshold}
                onChange={(e) => updateFilters({ scoreThreshold: parseFloat(e.target.value) })}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FilterPanel;

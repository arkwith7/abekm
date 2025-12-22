import {
  ChevronDown,
  ChevronRight,
  Crown,
  Edit3,
  Eye,
  Folder,
  FolderOpen,
  Lock
} from 'lucide-react';
import React from 'react';

// 지식컨테이너 트리 구조 타입
export interface KnowledgeContainer {
  id: string;
  name: string;
  path: string;
  parent_id?: string;
  children?: KnowledgeContainer[];
  permission: 'OWNER' | 'EDITOR' | 'VIEWER' | 'NONE';
  can_upload?: boolean;
  document_count?: number;
}

interface KnowledgeContainerTreeProps {
  containers: KnowledgeContainer[];
  selectedContainer: KnowledgeContainer | null;
  onSelectContainer: (container: KnowledgeContainer) => void;
  expandedContainers: Set<string>;
  onToggleExpand: (containerId: string) => void;
  // 🆕 삭제 모드 및 핸들러
  deleteMode?: boolean;
  onDeleteContainer?: (containerId: string, containerName: string) => void;
  canDeleteContainer?: (container: KnowledgeContainer) => boolean;
}

const KnowledgeContainerTree: React.FC<KnowledgeContainerTreeProps> = ({
  containers,
  selectedContainer,
  onSelectContainer,
  expandedContainers,
  onToggleExpand,
  deleteMode = false,
  onDeleteContainer,
  canDeleteContainer
}) => {
  // 컨테이너 이름에서 이모티콘과 특수 문자 제거하는 함수
  const cleanContainerName = (name: string): string => {
    if (typeof name !== 'string') {
      return '';
    }
    return name
      // 폴더 관련 이모티콘 제거
      .replace(/[📁🏢📂🗂️📊📈📉📋📌📍📎📏📐📑📒📓📔📕📖📗📘📙📚]/g, '')
      // 일반적인 이모티콘 범위 제거 (ES5 호환)
      .replace(/[\uD83C-\uDBFF\uDC00-\uDFFF]+/g, '')
      .replace(/[\u2600-\u27BF]/g, '')
      .replace(/^\s+/, '') // 앞의 공백 제거
      .replace(/\s+$/, '') // 뒤의 공백 제거
      .trim(); // 양쪽 공백 제거
  };

  const renderContainer = (container: KnowledgeContainer, level: number = 0) => {
    const hasChildren = container.children && container.children.length > 0;
    const isExpanded = expandedContainers.has(container.id);
    const isSelected = selectedContainer?.id === container.id;

    return (
      <div key={container.id}>
        <div
          className={`flex items-center p-2 rounded-md cursor-pointer transition-colors ${isSelected
            ? 'bg-blue-100 text-blue-800 border border-blue-200'
            : container.permission === 'NONE'
              ? 'hover:bg-red-50'
              : 'hover:bg-gray-100'
            }`}
          style={{ paddingLeft: `${level * 20 + 8}px` }}
          onClick={() => onSelectContainer(container)}
        >
          <div className="flex items-center flex-1">
            {/* 확장/축소 버튼 */}
            <div className="w-6 mr-2 flex justify-center">
              {hasChildren ? (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleExpand(container.id);
                  }}
                  className="p-1 hover:bg-gray-200 rounded transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-600" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-600" />
                  )}
                </button>
              ) : (
                <div className="w-6" />
              )}
            </div>

            {/* 폴더 아이콘 */}
            <div className="mr-3">
              {hasChildren && isExpanded ? (
                <FolderOpen className="w-5 h-5 text-blue-600" />
              ) : (
                <Folder className="w-5 h-5 text-gray-600" />
              )}
            </div>

            {/* 컨테이너 정보 */}
            <div className="flex-1 text-left">
              <div className={`text-sm font-medium ${container.permission === 'NONE' ? 'text-gray-400' : 'text-gray-900'
                }`}>
                {cleanContainerName(container.name)}
              </div>
              {container.document_count !== undefined && (
                <div className={`text-xs ${container.permission === 'NONE' ? 'text-gray-300' : 'text-gray-500'
                  }`}>
                  {container.document_count}개 문서
                </div>
              )}
            </div>

            {/* 권한 표시 아이콘 */}
            <div className="flex items-center ml-2 space-x-2">
              {/* 삭제 버튼 (삭제 모드 시에만 표시) */}
              {deleteMode && canDeleteContainer && canDeleteContainer(container) && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onDeleteContainer) {
                      onDeleteContainer(container.id, container.name);
                    }
                  }}
                  className="p-1 text-red-600 hover:bg-red-100 rounded transition-colors"
                  title="컨테이너 삭제 (문서가 없는 자신의 컨테이너만 삭제 가능)"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}

              {/* 권한 아이콘 */}
              <div title={`권한: ${container.permission}`}>
                {container.permission === 'OWNER' && (
                  <Crown className="w-4 h-4 text-yellow-600" />
                )}
                {container.permission === 'EDITOR' && (
                  <Edit3 className="w-4 h-4 text-blue-600" />
                )}
                {container.permission === 'VIEWER' && (
                  <Eye className="w-4 h-4 text-gray-600" />
                )}
                {container.permission === 'NONE' && (
                  <Lock className="w-4 h-4 text-gray-400" />
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 자식 컨테이너들 */}
        {hasChildren && isExpanded && (
          <div>
            {container.children!.map(child => renderContainer(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-white border border-gray-200 rounded-lg">
      <div className="flex-shrink-0 p-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">지식 컨테이너</h3>
      </div>

      <div className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-1">
          {containers.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Folder className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm">접근 가능한 컨테이너가 없습니다</p>
            </div>
          ) : (
            containers.map(container => renderContainer(container))
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeContainerTree;

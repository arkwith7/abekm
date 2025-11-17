import { ChevronDown, ChevronRight, Edit2, Folder, FolderOpen, Plus, Trash2 } from 'lucide-react';
import React from 'react';
import { Container, ContainerTree } from '../../../../types/manager.types';

interface ContainerTreeViewProps {
    nodes: ContainerTree[];
    containers: Container[];
    expandedNodes: Set<string>;
    onToggleNode: (nodeId: string) => void;
    onEdit: (container: Container) => void;
    onDelete: (containerId: string, containerName: string) => void;
    onAddChild: (parentContainer: Container) => void;
    onSelect?: (container: { id: string; name: string }) => void;
    selectedId?: string;
}

export const ContainerTreeView: React.FC<ContainerTreeViewProps> = ({
    nodes,
    containers,
    expandedNodes,
    onToggleNode,
    onEdit,
    onDelete,
    onAddChild,
    onSelect,
    selectedId
}) => {
    const renderTree = (treeNodes: ContainerTree[], level = 0): React.ReactNode => {
        return treeNodes.map((node) => {
            const isExpanded = expandedNodes.has(node.id);
            const hasChildren = node.children && node.children.length > 0;
            const isSelected = selectedId === node.id;

            return (
                <div key={node.id} className="select-none">
                    <div
                        onClick={() => onSelect?.({ id: node.id, name: node.name })}
                        className={`flex items-center py-2.5 px-2 rounded-lg transition-all group cursor-pointer ${isSelected ? 'bg-blue-100 border-l-4 border-blue-600' : 'hover:bg-blue-50'
                            }`}
                        style={{ paddingLeft: level > 0 ? `${8 + level * 16}px` : '8px' }}
                    >
                        {/* Expand/Collapse Button */}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                if (hasChildren) onToggleNode(node.id);
                            }}
                            className={`mr-0.5 p-0.5 flex-shrink-0 ${hasChildren ? 'text-gray-600 hover:text-gray-900' : 'text-transparent'}`}
                        >
                            {hasChildren ? (
                                isExpanded ? (
                                    <ChevronDown className="w-4 h-4" />
                                ) : (
                                    <ChevronRight className="w-4 h-4" />
                                )
                            ) : (
                                <div className="w-4 h-4" />
                            )}
                        </button>

                        {/* Folder Icon - 좌측 정렬, 간격 최소화 */}
                        <div
                            className="flex-shrink-0 cursor-pointer"
                            onClick={() => hasChildren && onToggleNode(node.id)}
                        >
                            {isExpanded ? (
                                <FolderOpen className="w-5 h-5 text-blue-600" />
                            ) : (
                                <Folder className="w-5 h-5 text-blue-500" />
                            )}
                        </div>

                        {/* Container Info - 좌측 정렬 */}
                        <div className="flex items-center justify-between flex-1 min-w-0 ml-1.5">
                            <div
                                className="flex-shrink-0 cursor-pointer"
                                onClick={() => hasChildren && onToggleNode(node.id)}
                            >
                                <div className="font-medium text-gray-900 text-sm">{node.name}</div>
                                <div className="text-xs text-gray-500 mt-0.5 whitespace-nowrap">
                                    📄 {node.document_count}개 · 👥 {node.user_count}명
                                </div>
                            </div>

                            {/* Action Buttons - 호버 시 표시 */}
                            {node.is_managed && (
                                <div className="flex items-center space-x-0.5 ml-2 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            const container = containers.find(c => c.id === node.id);
                                            if (container) onAddChild(container);
                                        }}
                                        className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                                        title="하위 컨테이너 추가"
                                    >
                                        <Plus className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            const container = containers.find(c => c.id === node.id);
                                            if (container) onEdit(container);
                                        }}
                                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors"
                                        title="수정"
                                    >
                                        <Edit2 className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onDelete(node.id, node.name);
                                        }}
                                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-100 rounded transition-colors"
                                        title="삭제"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Children */}
                    {hasChildren && isExpanded && (
                        <div className="mt-0.5">
                            {renderTree(node.children, level + 1)}
                        </div>
                    )}
                </div>
            );
        });
    };

    return <div className="space-y-0.5">{renderTree(nodes)}</div>;
};

import { Plus } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import {
    addContainerPermission,
    createContainer,
    deleteContainer,
    deleteContainerPermission as deleteContainerPermissionApi,
    fetchContainerPermissions,
    getContainers,
    getContainerTree,
    getMyContainerPermission,
    updateContainer,
    updateContainerPermission as updateContainerPermissionApi,
    UserContainerPermission
} from '../../../services/managerService';
import { Container, ContainerTree } from '../../../types/manager.types';
import { ContainerFormModal } from './components/ContainerFormModal';
import { ContainerPermissionPanel } from './components/ContainerPermissionPanel';
import { ContainerTreeView } from './components/ContainerTreeView';
import { ErrorAlert } from './components/ErrorAlert';
import { StatsGrid } from './components/StatsGrid';

export const ContainerManagement: React.FC = () => {
    const [containers, setContainers] = useState<Container[]>([]);
    const [containerTree, setContainerTree] = useState<ContainerTree[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [editingContainer, setEditingContainer] = useState<Container | null>(null);
    const [selectedContainer, setSelectedContainer] = useState<{ id: string; name: string } | null>(null);
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [permissions, setPermissions] = useState<any[]>([]);
    const [myPermission, setMyPermission] = useState<UserContainerPermission | null>(null);
    const [newContainer, setNewContainer] = useState({
        name: '',
        description: '',
        parent_id: ''
    });

    useEffect(() => {
        loadContainers();
    }, []);

    const loadContainers = async () => {
        try {
            setIsLoading(true);
            setError(null);
            const [containersData, treeData] = await Promise.all([
                getContainers(),
                getContainerTree()
            ]);
            setContainers(containersData);
            setContainerTree(treeData);

            // Auto-expand first level
            const firstLevelIds = treeData.map(node => node.id);
            setExpandedNodes(new Set(firstLevelIds));
        } catch (error: any) {
            console.error('Failed to load containers:', error);
            setError(error.response?.data?.detail || '컨테이너 목록을 불러오는데 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    };

    const loadContainerPermissionList = async (containerId: string) => {
        try {
            setError(null);
            const items = await fetchContainerPermissions(containerId);
            const mapped = items.map(item => ({
                user_emp_no: item.user_emp_no,
                user_name: item.user_name || item.user_emp_no,
                department: item.department || '',
                role_id: item.role_id,
                role_name: item.role_name || item.role_id,
                granted_date: item.granted_date || new Date().toISOString()
            }));
            setPermissions(mapped);
        } catch (error: any) {
            console.error('Failed to load container permissions:', error);
            const message = error.response?.data?.detail || '컨테이너 권한을 불러오는데 실패했습니다.';
            setError(message);
            setPermissions([]);
        }
    };

    const handleCreateContainer = async () => {
        if (!newContainer.name.trim()) {
            alert('컨테이너 이름을 입력해주세요.');
            return;
        }

        try {
            await createContainer(newContainer);
            setShowCreateModal(false);
            setNewContainer({ name: '', description: '', parent_id: '' });
            await loadContainers();
        } catch (error: any) {
            console.error('Failed to create container:', error);
            const errorMessage = error.response?.data?.detail || '컨테이너 생성에 실패했습니다.';
            alert(errorMessage);
        }
    };

    const handleUpdateContainer = async () => {
        if (!editingContainer) return;

        if (!editingContainer.name.trim()) {
            alert('컨테이너 이름을 입력해주세요.');
            return;
        }

        try {
            await updateContainer(editingContainer.id, {
                name: editingContainer.name,
                description: editingContainer.description
            });
            setEditingContainer(null);
            await loadContainers();
        } catch (error: any) {
            console.error('Failed to update container:', error);
            const errorMessage = error.response?.data?.detail || '컨테이너 수정에 실패했습니다.';
            alert(errorMessage);
        }
    };

    const handleDeleteContainer = async (containerId: string, containerName: string) => {
        if (!window.confirm(`'${containerName}' 컨테이너를 정말 삭제하시겠습니까?\n\n⚠️ 주의: 하위 컨테이너가 있으면 삭제할 수 없습니다.`)) return;

        try {
            await deleteContainer(containerId);
            await loadContainers();
        } catch (error: any) {
            console.error('Failed to delete container:', error);
            const errorMessage = error.response?.data?.detail || '컨테이너 삭제에 실패했습니다.';
            alert(errorMessage);
        }
    };

    const handleAddChild = (parentContainer: Container) => {
        // 부모 컨테이너 정보를 설정하고 생성 모달 열기
        setNewContainer({
            name: '',
            description: '',
            parent_id: parentContainer.id
        });
        setShowCreateModal(true);

        // 부모 노드 자동 확장
        const newExpanded = new Set(expandedNodes);
        newExpanded.add(parentContainer.id);
        setExpandedNodes(newExpanded);
    };

    const handleSelectContainer = (container: { id: string; name: string }) => {
        setSelectedContainer(container);
        setPermissions([]);
        setMyPermission(null);
        loadContainerPermissionList(container.id);
        loadMyPermission(container.id);
    };

    const loadMyPermission = async (containerId: string) => {
        try {
            const permission = await getMyContainerPermission(containerId);
            setMyPermission(permission);
        } catch (error: any) {
            console.error('Failed to load my permission:', error);
            setMyPermission(null);
        }
    };

    const handleAddPermission = async (empNo: string, roleId: string) => {
        if (!selectedContainer) {
            throw new Error('컨테이너가 선택되지 않았습니다.');
        }
        try {
            await addContainerPermission(selectedContainer.id, {
                user_emp_no: empNo,
                role_id: roleId
            });
            await loadContainerPermissionList(selectedContainer.id);
        } catch (error: any) {
            console.error('Failed to add permission:', error);
            const message = error.response?.data?.detail || '권한 부여에 실패했습니다.';
            throw new Error(message);
        }
    };

    const handleUpdatePermission = async (empNo: string, roleId: string) => {
        if (!selectedContainer) {
            throw new Error('컨테이너가 선택되지 않았습니다.');
        }
        try {
            await updateContainerPermissionApi(selectedContainer.id, empNo, {
                role_id: roleId
            });
            await loadContainerPermissionList(selectedContainer.id);
        } catch (error: any) {
            console.error('Failed to update permission:', error);
            const message = error.response?.data?.detail || '권한 변경에 실패했습니다.';
            throw new Error(message);
        }
    };

    const handleRemovePermission = async (empNo: string) => {
        if (!selectedContainer) {
            throw new Error('컨테이너가 선택되지 않았습니다.');
        }
        try {
            await deleteContainerPermissionApi(selectedContainer.id, empNo);
            await loadContainerPermissionList(selectedContainer.id);
        } catch (error: any) {
            console.error('Failed to remove permission:', error);
            const message = error.response?.data?.detail || '권한 제거에 실패했습니다.';
            throw new Error(message);
        }
    };

    const toggleNode = (nodeId: string) => {
        const newExpanded = new Set(expandedNodes);
        if (newExpanded.has(nodeId)) {
            newExpanded.delete(nodeId);
        } else {
            newExpanded.add(nodeId);
        }
        setExpandedNodes(newExpanded);
    };

    const expandAll = () => {
        const getAllIds = (nodes: ContainerTree[]): string[] => {
            return nodes.reduce((acc: string[], node) => {
                acc.push(node.id);
                if (node.children && node.children.length > 0) {
                    acc.push(...getAllIds(node.children));
                }
                return acc;
            }, []);
        };
        setExpandedNodes(new Set(getAllIds(containerTree)));
    };

    // Calculate statistics
    const totalDocuments = containers.reduce((sum, c) => sum + c.document_count, 0);
    const totalUsers = containers.reduce((sum, c) => sum + (c.user_count || 0), 0);
    const totalViews = containers.reduce((sum, c) => sum + (c.view_count || 0), 0);

    if (isLoading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-4 text-gray-600">컨테이너를 불러오는 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-4 px-4 sm:px-6 lg:px-8">
            <div className="max-w-7xl mx-auto">
                {/* 헤더 */}
                <div className="mb-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">지식컨테이너 관리</h1>
                        <p className="mt-2 text-sm text-gray-600">
                            지식 컨테이너를 생성하고 관리합니다.
                        </p>
                    </div>
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
                    >
                        <Plus className="w-5 h-5 mr-2" />
                        새 컨테이너
                    </button>
                </div>

                {/* Error Message */}
                {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

                {/* 통계 카드 */}
                <StatsGrid
                    totalContainers={containers.length}
                    totalDocuments={totalDocuments}
                    totalUsers={totalUsers}
                    totalViews={totalViews}
                />

                {/* 2칼럼 레이아웃: 컨테이너 구조 (좌) + 권한 관리 (우) */}
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                    {/* 컨테이너 트리 - 40% */}
                    <div className="lg:col-span-2 bg-white rounded-lg shadow-sm border border-gray-200">
                        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-gray-900">컨테이너 구조</h3>
                                <p className="text-sm text-gray-500 mt-1">
                                    💡 컨테이너를 클릭하여 권한을 관리하세요
                                </p>
                            </div>
                            <button
                                onClick={expandAll}
                                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                            >
                                모두 펼치기
                            </button>
                        </div>
                        <div className="p-6">{containerTree.length === 0 ? (
                            <div className="text-center py-12">
                                <div className="text-6xl mb-4">📂</div>
                                <p className="text-lg text-gray-600 mb-2">생성된 컨테이너가 없습니다</p>
                                <p className="text-sm text-gray-500 mb-4">첫 번째 컨테이너를 생성하여 시작하세요</p>
                                <button
                                    onClick={() => setShowCreateModal(true)}
                                    className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                                >
                                    <Plus className="w-5 h-5 mr-2" />
                                    컨테이너 만들기
                                </button>
                            </div>
                        ) : (
                            <ContainerTreeView
                                nodes={containerTree}
                                containers={containers}
                                expandedNodes={expandedNodes}
                                onToggleNode={toggleNode}
                                onEdit={setEditingContainer}
                                onDelete={handleDeleteContainer}
                                onAddChild={handleAddChild}
                                onSelect={handleSelectContainer}
                                selectedId={selectedContainer?.id}
                            />
                        )}
                        </div>
                    </div>

                    {/* 권한 관리 패널 - 60% */}
                    <div className="lg:col-span-3 bg-white rounded-lg shadow-sm border border-gray-200">
                        <ContainerPermissionPanel
                            selectedContainer={selectedContainer}
                            permissions={permissions}
                            myPermission={myPermission}
                            onAddPermission={handleAddPermission}
                            onUpdatePermission={handleUpdatePermission}
                            onRemovePermission={handleRemovePermission}
                        />
                    </div>
                </div>

                {/* 컨테이너 생성 모달 */}
                <ContainerFormModal
                    isOpen={showCreateModal}
                    mode="create"
                    container={newContainer}
                    containers={containers}
                    onClose={() => {
                        setShowCreateModal(false);
                        setNewContainer({ name: '', description: '', parent_id: '' });
                    }}
                    onChange={(updates) => setNewContainer(prev => ({ ...prev, ...updates }))}
                    onSubmit={handleCreateContainer}
                />

                {/* 컨테이너 수정 모달 */}
                {editingContainer && (
                    <ContainerFormModal
                        isOpen={true}
                        mode="edit"
                        container={{
                            name: editingContainer.name,
                            description: editingContainer.description,
                            parent_id: editingContainer.parent_id || ''
                        }}
                        containers={containers}
                        onClose={() => setEditingContainer(null)}
                        onChange={(updates) => setEditingContainer(prev => prev ? { ...prev, ...updates } : null)}
                        onSubmit={handleUpdateContainer}
                    />
                )}
            </div>
        </div>
    );
};

export default ContainerManagement;

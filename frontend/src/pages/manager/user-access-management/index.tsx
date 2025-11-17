import { AlertCircle, CheckCircle, UserPlus } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import {
    getContainerSubtreeIdsByName,
    getContainers,
    getTeamMembers,
    getUserPermissions,
    updateUserPermissions
} from '../../../services/managerService';
import { Container, TeamMember, UserPermission } from '../../../types/manager.types';
import { AddPermissionModal } from './components/AddPermissionModal';
import { PendingApprovals } from './components/PendingApprovals';
import { PermissionFilters } from './components/PermissionFilters';
import { PermissionInfoPanel } from './components/PermissionInfoPanel';
import { PermissionStats } from './components/PermissionStats';
import { PermissionTable } from './components/PermissionTable';

export const PermissionManagement: React.FC = () => {
    const [userPermissions, setUserPermissions] = useState<UserPermission[]>([]);
    const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
    const [containers, setContainers] = useState<Container[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedDepartment, setSelectedDepartment] = useState('');
    const [selectedContainer, setSelectedContainer] = useState('');
    const [editingPermission, setEditingPermission] = useState<string | null>(null);
    const [tempPermissions, setTempPermissions] = useState<{ [key: string]: string }>({});
    const [activeTab, setActiveTab] = useState<'pending' | 'permissions'>('pending');
    const [allowedContainerIds, setAllowedContainerIds] = useState<string[]>([]);
    const [managedRootName] = useState<string>('MS서비스팀');
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);

    useEffect(() => {
        const resolveScope = async () => {
            const { ids } = await getContainerSubtreeIdsByName(managedRootName);
            if (ids.length) setAllowedContainerIds(ids);
        };
        resolveScope();
    }, [managedRootName]);

    const loadData = React.useCallback(async () => {
        try {
            setIsLoading(true);
            const [permissionsData, membersData, containersData] = await Promise.all([
                getUserPermissions(),
                getTeamMembers(),
                getContainers()
            ]);

            setUserPermissions(permissionsData);

            if (membersData.length > 0) {
                setTeamMembers(membersData);
            } else {
                const derivedMembersMap = new Map<string, TeamMember>();
                permissionsData.forEach((permission) => {
                    if (!derivedMembersMap.has(permission.user_id)) {
                        derivedMembersMap.set(permission.user_id, {
                            user_id: permission.user_id,
                            name: permission.user_name || permission.user_id,
                            employee_id: permission.user_id,
                            department: permission.department || '',
                            position: '',
                            email: ''
                        });
                    }
                });
                setTeamMembers(Array.from(derivedMembersMap.values()));
            }

            // Limit visible containers to allowed scope if available
            setContainers(
                allowedContainerIds.length ? containersData.filter((c) => allowedContainerIds.includes(c.id)) : containersData
            );
        } catch (error) {
            console.error('Failed to load data:', error);
        } finally {
            setIsLoading(false);
        }
    }, [allowedContainerIds]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleUpdatePermission = async (userId: string, containerId: string, permission: string) => {
        try {
            await updateUserPermissions(userId, containerId, permission);
            await loadData();
            setEditingPermission(null);
            setTempPermissions({});
        } catch (error) {
            console.error('Failed to update permission:', error);
            alert('권한 수정에 실패했습니다.');
        }
    };

    const handleAddPermission = async (userId: string, containerId: string, permission: string) => {
        try {
            await updateUserPermissions(userId, containerId, permission);
            await loadData();
            alert('권한이 성공적으로 추가되었습니다.');
        } catch (error) {
            console.error('Failed to add permission:', error);
            throw error;
        }
    };

    const filteredPermissions = useMemo(() => {
        return userPermissions.filter((permission) => {
            // 관리 범위 필터링
            if (allowedContainerIds.length && !allowedContainerIds.includes(permission.container_id)) {
                return false;
            }

            // 시스템 관리자 제외 (ADMIN001, admin, SYSTEM 등)
            const systemAdminIds = ['ADMIN001', 'admin', 'SYSTEM'];
            if (systemAdminIds.includes(permission.user_id)) {
                return false;
            }

            const user = teamMembers.find((member) => member.user_id === permission.user_id);
            const userName = (user?.name || permission.user_name || '').toLowerCase();
            const employeeId = (user?.employee_id || permission.user_id || '').toLowerCase();
            const department = user?.department || permission.department || '';

            const searchLower = searchTerm.toLowerCase();
            const matchesSearch = !searchTerm || userName.includes(searchLower) || employeeId.includes(searchLower);
            const matchesDepartment = !selectedDepartment || department === selectedDepartment;
            const matchesContainer = !selectedContainer || permission.container_id === selectedContainer;

            return matchesSearch && matchesDepartment && matchesContainer;
        });
    }, [userPermissions, teamMembers, searchTerm, selectedDepartment, selectedContainer, allowedContainerIds]);

    const departments = Array.from(
        new Set([
            ...teamMembers.map((member) => member.department).filter((dept): dept is string => Boolean(dept)),
            ...userPermissions.map((permission) => permission.department).filter((dept): dept is string => Boolean(dept))
        ])
    );

    const uniqueUserCount = new Set(filteredPermissions.map((permission) => permission.user_id)).size;

    if (isLoading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-4 text-gray-600">사용자 권한을 불러오는 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-4 px-4 sm:px-6 lg:px-8">
            <div className="max-w-7xl mx-auto">
                {/* 헤더 */}
                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">사용자 권한 관리</h1>
                        <p className="mt-2 text-sm text-gray-600">
                            {activeTab === 'pending' && '권한 요청을 검토하고 승인/거부합니다.'}
                            {activeTab === 'permissions' && '팀원들의 지식 컨테이너 접근 권한을 관리합니다.'}
                        </p>
                    </div>
                    {activeTab === 'permissions' && (
                        <button
                            onClick={() => setIsAddModalOpen(true)}
                            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                            <UserPlus className="w-5 h-5 mr-2" />
                            권한 추가
                        </button>
                    )}
                </div>

                {/* 탭 네비게이션 */}
                <div className="mb-6">
                    <div className="border-b border-gray-200">
                        <nav className="-mb-px flex space-x-8">
                            <button
                                onClick={() => setActiveTab('pending')}
                                className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'pending'
                                    ? 'border-orange-500 text-orange-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                <div className="flex items-center">
                                    <AlertCircle className="w-4 h-4 mr-2" />
                                    승인 대기
                                </div>
                            </button>
                            <button
                                onClick={() => setActiveTab('permissions')}
                                className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'permissions'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                <div className="flex items-center">
                                    <CheckCircle className="w-4 h-4 mr-2" />
                                    권한 현황
                                </div>
                            </button>
                        </nav>
                    </div>
                </div>

                {/* 탭 컨텐츠 */}
                {activeTab === 'pending' && <PendingApprovals />}

                {activeTab === 'permissions' && (
                    <>
                        <PermissionFilters
                            searchTerm={searchTerm}
                            setSearchTerm={setSearchTerm}
                            selectedDepartment={selectedDepartment}
                            setSelectedDepartment={setSelectedDepartment}
                            selectedContainer={selectedContainer}
                            setSelectedContainer={setSelectedContainer}
                            departments={departments}
                            containers={containers}
                        />

                        <PermissionStats
                            uniqueUserCount={uniqueUserCount}
                            containerCount={containers.length}
                            totalPermissions={userPermissions.length}
                        />

                        <PermissionTable
                            permissions={filteredPermissions}
                            teamMembers={teamMembers}
                            containers={containers}
                            editingPermission={editingPermission}
                            setEditingPermission={setEditingPermission}
                            tempPermissions={tempPermissions}
                            setTempPermissions={setTempPermissions}
                            onUpdatePermission={handleUpdatePermission}
                        />

                        <PermissionInfoPanel />
                    </>
                )}

                {/* 권한 추가 모달 */}
                <AddPermissionModal
                    isOpen={isAddModalOpen}
                    onClose={() => setIsAddModalOpen(false)}
                    containers={containers}
                    onAddPermission={handleAddPermission}
                />
            </div>
        </div>
    );
};

export default PermissionManagement;

import { Loader2, Plus, Search, Shield, Trash2, UserPlus, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { searchUsersForPermissions, UserContainerPermission } from '../../../../services/managerService';

interface User {
    emp_no: string;
    name?: string;
    username?: string;
    department?: string;
    position?: string;
    email?: string;
}

interface Permission {
    user_emp_no: string;
    user_name: string;
    department: string;
    role_id: string;
    role_name: string;
    granted_date: string;
}

interface ContainerPermissionPanelProps {
    selectedContainer: {
        id: string;
        name: string;
    } | null;
    permissions: Permission[];
    myPermission: UserContainerPermission | null;
    onAddPermission: (empNo: string, roleId: string) => void;
    onUpdatePermission: (empNo: string, roleId: string) => void;
    onRemovePermission: (empNo: string) => void;
}

const ROLES = [
    { id: 'ADMIN', name: '관리자', description: '모든 권한 + 컨테이너 관리', color: 'red' },
    { id: 'EDITOR', name: '편집자', description: '읽기 + 문서 업로드/수정/삭제', color: 'blue' },
    { id: 'WRITER', name: '작성자', description: '읽기 + 문서 업로드', color: 'green' },
    { id: 'READER', name: '읽기전용', description: '문서 조회만 가능', color: 'gray' }
];

// 권한 레벨 계산 함수
const getPermissionLevel = (roleId: string): number => {
    const hierarchy: { [key: string]: number } = {
        'ADMIN': 1,
        'ADMIN_DEPARTMENT': 1,
        'OWNER_DEPT': 1,
        'OWNER_DIVISION': 1,
        'OWNER': 1,
        'FULL_ACCESS': 1,
        'MANAGER': 2,
        'MANAGER_DEPT': 2,
        'MANAGER_DIVISION': 2,
        'EDITOR': 3,
        'MEMBER_DEPT': 3,
        'CONTRIBUTOR': 3,
        'WRITER': 3,
        'VIEWER': 4,
        'MEMBER_DIVISION': 4,
        'READER': 4
    };
    return hierarchy[roleId.toUpperCase()] || 999;
};

export const ContainerPermissionPanel: React.FC<ContainerPermissionPanelProps> = ({
    selectedContainer,
    permissions,
    myPermission,
    onAddPermission,
    onUpdatePermission,
    onRemovePermission
}) => {
    const [showAddModal, setShowAddModal] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedUser, setSelectedUser] = useState<User | null>(null);

    // 권한 확인
    const canManagePermissions = myPermission?.can_manage_permissions ?? false;
    const myPermissionLevel = myPermission ? getPermissionLevel(myPermission.permission_level) : 999;

    // 특정 사용자의 권한을 수정/삭제할 수 있는지 확인
    const canModifyUserPermission = (userRoleId: string): boolean => {
        if (!canManagePermissions) return false;
        const userLevel = getPermissionLevel(userRoleId);
        // 자신보다 낮은 레벨의 권한만 수정/삭제 가능 (같은 레벨도 불가)
        return myPermissionLevel < userLevel;
    };

    const [selectedRole, setSelectedRole] = useState('READER');
    const [editingPermission, setEditingPermission] = useState<string | null>(null);
    const [searchResults, setSearchResults] = useState<User[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [searchError, setSearchError] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        if (!showAddModal) {
            setSearchQuery('');
            setSearchResults([]);
            setSelectedUser(null);
            setSearchError(null);
            return;
        }

        if (!searchQuery.trim()) {
            setSearchResults([]);
            setSearchError(null);
            return;
        }

        let isSubscribed = true;
        setIsSearching(true);
        setSearchError(null);

        const handler = setTimeout(async () => {
            try {
                const response = await searchUsersForPermissions(searchQuery.trim(), 1, 10);
                if (!isSubscribed) {
                    return;
                }

                const mapped = response.users.map(user => ({
                    emp_no: user.emp_no,
                    name: user.name || user.username || user.emp_no,
                    username: user.username,
                    department: user.department,
                    position: user.position,
                    email: user.email
                }));

                setSearchResults(mapped);
                setSearchError(null);
            } catch (error: any) {
                if (!isSubscribed) {
                    return;
                }
                console.error('Failed to search users:', error);
                const message = error?.response?.data?.detail || '사용자 검색 중 오류가 발생했습니다.';
                setSearchError(message);
                setSearchResults([]);
            } finally {
                if (isSubscribed) {
                    setIsSearching(false);
                }
            }
        }, 400);

        return () => {
            isSubscribed = false;
            clearTimeout(handler);
        };
    }, [searchQuery, showAddModal]);

    useEffect(() => {
        setShowAddModal(false);
        setSelectedUser(null);
        setSearchQuery('');
        setSearchResults([]);
        setEditingPermission(null);
    }, [selectedContainer?.id]);

    useEffect(() => {
        if (selectedUser && !searchResults.some(user => user.emp_no === selectedUser.emp_no)) {
            setSelectedUser(null);
        }
    }, [searchResults, selectedUser]);

    useEffect(() => {
        if (showAddModal) {
            setSelectedRole('READER');
        }
    }, [showAddModal]);

    const getRoleColor = (roleId: string) => {
        const role = ROLES.find(r => r.id === roleId);
        return role?.color || 'gray';
    };

    const getRoleBadgeClass = (roleId: string) => {
        const colorMap: Record<string, string> = {
            red: 'bg-red-100 text-red-700 border-red-300',
            blue: 'bg-blue-100 text-blue-700 border-blue-300',
            green: 'bg-green-100 text-green-700 border-green-300',
            gray: 'bg-gray-100 text-gray-700 border-gray-300'
        };
        const color = getRoleColor(roleId);
        return colorMap[color] || colorMap.gray;
    };

    if (!selectedContainer) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <Shield className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                    <p className="text-lg text-gray-500 font-medium">컨테이너를 선택하세요</p>
                    <p className="text-sm text-gray-400 mt-2">
                        좌측에서 컨테이너를 클릭하면<br />권한을 관리할 수 있습니다
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            {/* 헤더 */}
            <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        <Shield className="w-6 h-6 text-blue-600" />
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900">권한 관리</h3>
                            <p className="text-sm text-gray-600 mt-0.5">
                                📁 {selectedContainer.name}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => setShowAddModal(true)}
                        disabled={!canManagePermissions}
                        className={`flex items-center px-4 py-2 rounded-lg transition-colors text-sm font-medium shadow-sm ${canManagePermissions
                            ? 'bg-blue-600 text-white hover:bg-blue-700'
                            : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            }`}
                        title={canManagePermissions ? undefined : '권한 관리 권한이 없습니다'}
                    >
                        <UserPlus className="w-4 h-4 mr-2" />
                        사용자 추가
                    </button>
                </div>
            </div>

            {/* 권한 목록 */}
            <div className="flex-1 overflow-y-auto p-6">
                {permissions.length === 0 ? (
                    <div className="text-center py-12">
                        <UserPlus className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                        <p className="text-gray-500 mb-2">권한이 부여된 사용자가 없습니다</p>
                        <p className="text-sm text-gray-400 mb-4">
                            사용자에게 컨테이너 접근 권한을 부여하세요
                        </p>
                        <button
                            onClick={() => setShowAddModal(true)}
                            disabled={!canManagePermissions}
                            className={`inline-flex items-center px-4 py-2 rounded-lg transition-colors text-sm ${canManagePermissions
                                ? 'bg-blue-600 text-white hover:bg-blue-700'
                                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                }`}
                            title={canManagePermissions ? undefined : '권한 관리 권한이 없습니다'}
                        >
                            <Plus className="w-4 h-4 mr-2" />
                            첫 번째 사용자 추가
                        </button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        <div className="flex items-center justify-between mb-4">
                            <p className="text-sm text-gray-600">
                                총 <span className="font-semibold text-blue-600">{permissions.length}명</span>의 사용자
                            </p>
                        </div>

                        {permissions.map((permission) => (
                            <div
                                key={permission.user_emp_no}
                                className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center space-x-3">
                                            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-semibold">
                                                {permission.user_name.charAt(0)}
                                            </div>
                                            <div>
                                                <div className="font-medium text-gray-900">
                                                    {permission.user_name}
                                                    <span className="text-sm text-gray-500 ml-2">
                                                        ({permission.user_emp_no})
                                                    </span>
                                                </div>
                                                <div className="text-sm text-gray-500">
                                                    {permission.department}
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center space-x-2">
                                        {editingPermission === permission.user_emp_no ? (
                                            <>
                                                <select
                                                    value={selectedRole}
                                                    onChange={(e) => setSelectedRole(e.target.value)}
                                                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                >
                                                    {ROLES.map((role) => (
                                                        <option key={role.id} value={role.id}>
                                                            {role.name}
                                                        </option>
                                                    ))}
                                                </select>
                                                <button
                                                    onClick={() => {
                                                        setIsSaving(true);
                                                        Promise.resolve(onUpdatePermission(permission.user_emp_no, selectedRole))
                                                            .then(() => {
                                                                setEditingPermission(null);
                                                            })
                                                            .catch((error) => {
                                                                const message = error?.message || '권한 변경에 실패했습니다.';
                                                                alert(message);
                                                            })
                                                            .finally(() => setIsSaving(false));
                                                    }}
                                                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                                                    disabled={isSaving}
                                                >
                                                    저장
                                                </button>
                                                <button
                                                    onClick={() => setEditingPermission(null)}
                                                    className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300"
                                                >
                                                    취소
                                                </button>
                                            </>
                                        ) : (
                                            <>
                                                <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getRoleBadgeClass(permission.role_id)}`}>
                                                    {permission.role_name}
                                                </span>
                                                <button
                                                    onClick={() => {
                                                        setSelectedRole(permission.role_id);
                                                        setEditingPermission(permission.user_emp_no);
                                                    }}
                                                    disabled={!canModifyUserPermission(permission.role_id)}
                                                    className={`p-2 rounded-lg transition-colors ${canModifyUserPermission(permission.role_id)
                                                            ? 'text-gray-400 hover:text-blue-600 hover:bg-blue-50'
                                                            : 'text-gray-300 cursor-not-allowed'
                                                        }`}
                                                    title={
                                                        !canManagePermissions
                                                            ? '권한 관리 권한이 없습니다'
                                                            : !canModifyUserPermission(permission.role_id)
                                                                ? '자신과 같거나 높은 권한을 가진 사용자의 권한은 변경할 수 없습니다'
                                                                : '권한 변경'
                                                    }
                                                >
                                                    <Shield className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        if (window.confirm(`${permission.user_name}님의 권한을 제거하시겠습니까?`)) {
                                                            onRemovePermission(permission.user_emp_no);
                                                        }
                                                    }}
                                                    disabled={!canModifyUserPermission(permission.role_id)}
                                                    className={`p-2 rounded-lg transition-colors ${canModifyUserPermission(permission.role_id)
                                                            ? 'text-gray-400 hover:text-red-600 hover:bg-red-50'
                                                            : 'text-gray-300 cursor-not-allowed'
                                                        }`}
                                                    title={
                                                        !canManagePermissions
                                                            ? '권한 관리 권한이 없습니다'
                                                            : !canModifyUserPermission(permission.role_id)
                                                                ? '자신과 같거나 높은 권한을 가진 사용자의 권한은 제거할 수 없습니다'
                                                                : '권한 제거'
                                                    }
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>

                                <div className="mt-3 pt-3 border-t border-gray-100">
                                    <p className="text-xs text-gray-500">
                                        부여일: {new Date(permission.granted_date).toLocaleDateString('ko-KR')}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* 역할 가이드 */}
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
                <p className="text-xs font-semibold text-gray-700 mb-2">📌 역할별 권한</p>
                <div className="grid grid-cols-2 gap-2">
                    {ROLES.map((role) => (
                        <div key={role.id} className="text-xs">
                            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium mr-2 ${getRoleBadgeClass(role.id)}`}>
                                {role.name}
                            </span>
                            <span className="text-gray-600">{role.description}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* 사용자 추가 모달 */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
                        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-gray-900">사용자 권한 추가</h3>
                            <button
                                onClick={() => setShowAddModal(false)}
                                className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                <X className="w-5 h-5 text-gray-500" />
                            </button>
                        </div>

                        <div className="p-6 flex-1 overflow-y-auto">
                            {/* 검색 */}
                            <div className="mb-4">
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    사용자 검색
                                </label>
                                <div className="relative">
                                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <input
                                        type="text"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="이름, 사번, 부서로 검색..."
                                    />
                                </div>
                            </div>

                            {/* 역할 선택 */}
                            <div className="mb-4">
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    부여할 역할
                                </label>
                                <div className="grid grid-cols-2 gap-3">
                                    {ROLES.map((role) => (
                                        <div
                                            key={role.id}
                                            onClick={() => setSelectedRole(role.id)}
                                            className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${selectedRole === role.id
                                                ? 'border-blue-500 bg-blue-50'
                                                : 'border-gray-200 hover:border-gray-300'
                                                }`}
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <span className={`px-2 py-1 rounded text-xs font-medium ${getRoleBadgeClass(role.id)}`}>
                                                    {role.name}
                                                </span>
                                                {selectedRole === role.id && (
                                                    <div className="w-5 h-5 bg-blue-600 rounded-full flex items-center justify-center">
                                                        <span className="text-white text-xs">✓</span>
                                                    </div>
                                                )}
                                            </div>
                                            <p className="text-xs text-gray-600">{role.description}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* 사용자 목록 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    사용자 선택
                                </label>
                                <div className="border border-gray-200 rounded-lg max-h-64 overflow-y-auto">
                                    {isSearching && (
                                        <div className="flex items-center justify-center py-6 text-sm text-gray-500">
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" /> 검색 중...
                                        </div>
                                    )}

                                    {!isSearching && searchError && searchResults.length === 0 && (
                                        <p className="p-4 text-sm text-red-500 text-center">{searchError}</p>
                                    )}

                                    {!isSearching && !searchError && searchResults.length === 0 && searchQuery.trim() !== '' && (
                                        <p className="p-4 text-sm text-gray-500 text-center">검색 결과가 없습니다.</p>
                                    )}

                                    {!isSearching && searchResults.length === 0 && searchQuery.trim() === '' && (
                                        <p className="p-4 text-sm text-gray-500 text-center">🔍 이름, 사번 또는 부서로 검색하세요.</p>
                                    )}

                                    {searchResults.map(user => {
                                        const isSelected = selectedUser?.emp_no === user.emp_no;
                                        return (
                                            <button
                                                key={user.emp_no}
                                                type="button"
                                                onClick={() => setSelectedUser(user)}
                                                className={`w-full text-left px-4 py-3 flex items-center justify-between transition-colors ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : 'hover:bg-gray-50'
                                                    }`}
                                            >
                                                <div>
                                                    <p className="text-sm font-medium text-gray-900">
                                                        {user.name || user.username || user.emp_no}
                                                        <span className="text-xs text-gray-500 ml-2">({user.emp_no})</span>
                                                    </p>
                                                    <p className="text-xs text-gray-500 mt-1">
                                                        {user.department || '부서 정보 없음'} · {user.position || '직책 정보 없음'}
                                                    </p>
                                                </div>
                                                {isSelected && <span className="text-blue-600 text-xs font-semibold">선택됨</span>}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
                            <button
                                onClick={() => setShowAddModal(false)}
                                className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                                취소
                            </button>
                            <button
                                onClick={async () => {
                                    if (!selectedUser || !selectedContainer) {
                                        return;
                                    }
                                    setIsSaving(true);
                                    try {
                                        await onAddPermission(selectedUser.emp_no, selectedRole);
                                        setShowAddModal(false);
                                        setSelectedUser(null);
                                        setSearchQuery('');
                                        setSearchResults([]);
                                    } catch (error: any) {
                                        const message = error?.message || '권한 부여에 실패했습니다.';
                                        alert(message);
                                    } finally {
                                        setIsSaving(false);
                                    }
                                }}
                                disabled={!selectedUser || isSaving}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                권한 부여
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

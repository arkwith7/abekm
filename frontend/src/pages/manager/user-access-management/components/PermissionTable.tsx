import { Edit2, Save, User, X } from 'lucide-react';
import React from 'react';
import { TeamMember, UserPermission } from '../../../../types/manager.types';

interface PermissionTableProps {
    permissions: UserPermission[];
    teamMembers: TeamMember[];
    containers: Array<{ id: string; name: string }>;
    editingPermission: string | null;
    setEditingPermission: (key: string | null) => void;
    tempPermissions: { [key: string]: string };
    setTempPermissions: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
    onUpdatePermission: (userId: string, containerId: string, permission: string) => Promise<void>;
}

export const PermissionTable: React.FC<PermissionTableProps> = ({
    permissions,
    teamMembers,
    containers,
    editingPermission,
    setEditingPermission,
    tempPermissions,
    setTempPermissions,
    onUpdatePermission
}) => {
    const getPermissionColor = (permission: string) => {
        switch (permission) {
            case 'read':
                return 'bg-green-100 text-green-800';
            case 'write':
                return 'bg-blue-100 text-blue-800';
            case 'admin':
                return 'bg-purple-100 text-purple-800';
            default:
                return 'bg-gray-100 text-gray-800';
        }
    };

    const getPermissionLabel = (permission: string) => {
        switch (permission) {
            case 'read':
                return '읽기';
            case 'write':
                return '읽기/쓰기';
            case 'admin':
                return '관리자';
            default:
                return '권한없음';
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">사용자별 권한 현황</h3>
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                지식컨테이너
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                부서
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                사용자
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                권한
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                작업
                            </th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {permissions.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                                    <div className="text-4xl mb-2">🔍</div>
                                    <p>검색 결과가 없습니다.</p>
                                </td>
                            </tr>
                        ) : (
                            permissions.map((permission, index) => {
                                const user = teamMembers.find((member) => member.user_id === permission.user_id);
                                const container = containers.find((c) => c.id === permission.container_id);
                                const editKey = `${permission.user_id}-${permission.container_id}`;
                                const isEditing = editingPermission === editKey;

                                const userName = user?.name || permission.user_name || permission.user_id;
                                const employeeId = user?.employee_id || permission.user_id;
                                const department = user?.department || permission.department || '-';
                                const containerName = container?.name || permission.container_name || permission.container_id;

                                return (
                                    <tr key={index} className="hover:bg-gray-50">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                            📁 {containerName}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{department}</td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className="flex-shrink-0 h-10 w-10">
                                                    <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                                                        <User className="h-5 w-5 text-blue-600" />
                                                    </div>
                                                </div>
                                                <div className="ml-4">
                                                    <div className="text-sm font-medium text-gray-900">{userName}</div>
                                                    <div className="text-sm text-gray-500">{employeeId}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {isEditing ? (
                                                <select
                                                    value={tempPermissions[editKey] || permission.permission}
                                                    onChange={(e) =>
                                                        setTempPermissions((prev) => ({
                                                            ...prev,
                                                            [editKey]: e.target.value
                                                        }))
                                                    }
                                                    className="text-sm border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                >
                                                    <option value="read">읽기</option>
                                                    <option value="write">읽기/쓰기</option>
                                                    <option value="admin">관리자</option>
                                                    <option value="none">권한없음</option>
                                                </select>
                                            ) : (
                                                <span
                                                    className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getPermissionColor(
                                                        permission.permission
                                                    )}`}
                                                >
                                                    {getPermissionLabel(permission.permission)}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                            {isEditing ? (
                                                <div className="flex space-x-2">
                                                    <button
                                                        onClick={() =>
                                                            onUpdatePermission(
                                                                permission.user_id,
                                                                permission.container_id,
                                                                tempPermissions[editKey] || permission.permission
                                                            )
                                                        }
                                                        className="text-green-600 hover:text-green-900"
                                                    >
                                                        <Save className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            setEditingPermission(null);
                                                            setTempPermissions({});
                                                        }}
                                                        className="text-gray-600 hover:text-gray-900"
                                                    >
                                                        <X className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            ) : (
                                                <button onClick={() => setEditingPermission(editKey)} className="text-blue-600 hover:text-blue-900">
                                                    <Edit2 className="w-4 h-4" />
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

import {
  AlertCircle,
  Building,
  CheckCircle,
  Clock,
  Edit2,
  Filter,
  Key,
  Mail,
  Phone,
  Plus,
  Search,
  Shield,
  Trash2,
  Users,
  X,
  XCircle
} from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import { userManagementAPI } from '../../services/adminService';
import { getRoleLabel, getStatusLabel, getUserStatus, User, UserCreateRequest, UserStatus, UserUpdateRequest } from '../../types/user';

// Toast 알림 컴포넌트
interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info';
  onClose: () => void;
}

const Toast: React.FC<ToastProps> = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';

  return (
    <div className={`fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2`}>
      {type === 'success' && <CheckCircle className="w-5 h-5" />}
      {type === 'error' && <XCircle className="w-5 h-5" />}
      {type === 'info' && <AlertCircle className="w-5 h-5" />}
      <span>{message}</span>
      <button onClick={onClose} className="ml-4"><X className="w-4 h-4" /></button>
    </div>
  );
};

export const UserManagement: React.FC = () => {
  // 상태 관리
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRole, setSelectedRole] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [pageSize] = useState(5); // 한 화면에 5개씩 표시

  // 고급 필터 상태
  const [selectedDepartment, setSelectedDepartment] = useState('all');
  const [selectedPosition, setSelectedPosition] = useState('all');
  const [departments, setDepartments] = useState<{ code: string; name: string }[]>([]);
  const [positions, setPositions] = useState<{ code: string; name: string }[]>([]);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // 일괄 작업 상태
  const [selectedUsers, setSelectedUsers] = useState<Set<number>>(new Set());
  const [showBulkActions, setShowBulkActions] = useState(false);

  // 통계
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    admin: 0,
    departments: 0
  });

  // 모달 상태
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showPasswordResetDialog, setShowPasswordResetDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  // Toast 상태
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // 사용자 목록 로드
  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        page: currentPage,
        size: pageSize,
      };

      if (searchTerm) params.search = searchTerm;
      if (selectedRole !== 'all') params.is_admin = selectedRole === 'ADMIN';
      if (selectedStatus !== 'all') params.is_active = selectedStatus === 'active';
      if (selectedDepartment !== 'all') params.dept_nm = selectedDepartment;
      if (selectedPosition !== 'all') params.postn_nm = selectedPosition;

      const response = await userManagementAPI.getUsers(params);
      setUsers(response.items);
      setTotalPages(response.pages);
      setTotalUsers(response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '사용자 목록을 불러오는데 실패했습니다');
      showToast('사용자 목록을 불러오는데 실패했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, searchTerm, selectedRole, selectedStatus, selectedDepartment, selectedPosition]);

  // 통계 로드
  const loadStats = useCallback(async () => {
    try {
      const stats = await userManagementAPI.getUserStats();
      setStats(stats);
    } catch (err) {
      console.error('통계 로드 실패:', err);
    }
  }, []);

  // 부서 목록 로드
  const loadDepartments = useCallback(async () => {
    try {
      const depts = await userManagementAPI.getDepartments();
      setDepartments(depts);
    } catch (err) {
      console.error('부서 목록 로드 실패:', err);
    }
  }, []);

  // 직급 목록 로드
  const loadPositions = useCallback(async () => {
    try {
      const posts = await userManagementAPI.getPositions();
      setPositions(posts);
    } catch (err) {
      console.error('직급 목록 로드 실패:', err);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    loadStats();
    loadDepartments();
    loadPositions();
  }, [loadStats, loadDepartments, loadPositions]);

  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    setToast({ message, type });
  };

  // 사용자 추가
  const handleAddUser = async (userData: UserCreateRequest) => {
    try {
      await userManagementAPI.createUser(userData);
      showToast('사용자가 성공적으로 추가되었습니다', 'success');
      setShowAddModal(false);
      loadUsers();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || '사용자 추가에 실패했습니다', 'error');
    }
  };

  // 사용자 수정
  const handleUpdateUser = async (userId: number, userData: UserUpdateRequest) => {
    try {
      await userManagementAPI.updateUser(userId, userData);
      showToast('사용자 정보가 성공적으로 수정되었습니다', 'success');
      setShowEditModal(false);
      setSelectedUser(null);
      loadUsers();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || '사용자 수정에 실패했습니다', 'error');
    }
  };

  // 사용자 삭제
  const handleDeleteUser = async () => {
    if (!selectedUser) return;

    try {
      await userManagementAPI.deleteUser(selectedUser.id);
      showToast('사용자가 성공적으로 비활성화되었습니다', 'success');
      setShowDeleteDialog(false);
      setSelectedUser(null);
      loadUsers();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || '사용자 삭제에 실패했습니다', 'error');
    }
  };

  // 체크박스 토글
  const handleToggleSelect = (userId: number) => {
    const newSelected = new Set(selectedUsers);
    if (newSelected.has(userId)) {
      newSelected.delete(userId);
    } else {
      newSelected.add(userId);
    }
    setSelectedUsers(newSelected);
    setShowBulkActions(newSelected.size > 0);
  };

  // 전체 선택/해제
  const handleToggleSelectAll = () => {
    if (selectedUsers.size === users.length) {
      setSelectedUsers(new Set());
      setShowBulkActions(false);
    } else {
      setSelectedUsers(new Set(users.map(u => u.id)));
      setShowBulkActions(true);
    }
  };

  // 일괄 삭제
  const handleBulkDelete = async () => {
    if (selectedUsers.size === 0) return;

    if (!window.confirm(`${selectedUsers.size}명의 사용자를 비활성화하시겠습니까?`)) {
      return;
    }

    try {
      const result = await userManagementAPI.bulkDeleteUsers(Array.from(selectedUsers));
      if (result.success) {
        showToast(`${result.processed_count}명 비활성화 완료`, 'success');
      } else {
        showToast(`${result.processed_count}명 처리, ${result.failed_count}명 실패`, 'error');
      }
      setSelectedUsers(new Set());
      setShowBulkActions(false);
      loadUsers();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || '일괄 삭제에 실패했습니다', 'error');
    }
  };

  // 일괄 권한 변경
  const handleBulkRoleChange = async (isAdmin: boolean) => {
    if (selectedUsers.size === 0) return;

    const roleText = isAdmin ? '관리자' : '일반 사용자';
    if (!window.confirm(`${selectedUsers.size}명의 권한을 ${roleText}로 변경하시겠습니까?`)) {
      return;
    }

    try {
      const result = await userManagementAPI.bulkUpdateRole(Array.from(selectedUsers), isAdmin);
      if (result.success) {
        showToast(`${result.processed_count}명 권한 변경 완료`, 'success');
      } else {
        showToast(`${result.processed_count}명 처리, ${result.failed_count}명 실패`, 'error');
      }
      setSelectedUsers(new Set());
      setShowBulkActions(false);
      loadUsers();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || '일괄 권한 변경에 실패했습니다', 'error');
    }
  };

  // 비밀번호 리셋
  const handlePasswordReset = async () => {
    if (!selectedUser) return;

    try {
      const response = await userManagementAPI.resetPassword(selectedUser.id);
      if (response.temporary_password) {
        showToast(`임시 비밀번호: ${response.temporary_password}`, 'success');
      } else {
        showToast('비밀번호가 성공적으로 리셋되었습니다', 'success');
      }
      setShowPasswordResetDialog(false);
      setSelectedUser(null);
    } catch (err: any) {
      showToast(err.response?.data?.detail || '비밀번호 리셋에 실패했습니다', 'error');
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'ADMIN':
        return 'bg-red-100 text-red-800';
      case 'MANAGER':
        return 'bg-blue-100 text-blue-800';
      case 'USER':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status: UserStatus) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'inactive':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'suspended':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: UserStatus) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'inactive':
        return 'bg-yellow-100 text-yellow-800';
      case 'suspended':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Toast 알림 */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">사용자 관리</h1>
          <p className="text-gray-600">시스템 사용자를 관리하고 권한을 설정하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>사용자 추가</span>
          </button>
        </div>
      </div>

      {/* 필터 및 검색 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col space-y-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0 md:space-x-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="이름, 이메일, 사번으로 검색..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <Filter className="w-4 h-4 text-gray-500" />
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="all">모든 역할</option>
                  <option value="ADMIN">관리자</option>
                  <option value="MANAGER">매니저</option>
                  <option value="USER">사용자</option>
                </select>
              </div>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="all">모든 상태</option>
                <option value="active">활성</option>
                <option value="inactive">비활성</option>
              </select>
              <button
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
              >
                {showAdvancedFilters ? '간단히' : '고급 필터'}
              </button>
            </div>
          </div>

          {/* 고급 필터 */}
          {showAdvancedFilters && (
            <div className="flex items-center space-x-3 pt-2 border-t border-gray-200">
              <select
                value={selectedDepartment}
                onChange={(e) => setSelectedDepartment(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="all">모든 부서</option>
                {departments.map(dept => (
                  <option key={dept.code} value={dept.name}>{dept.name}</option>
                ))}
              </select>
              <select
                value={selectedPosition}
                onChange={(e) => setSelectedPosition(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="all">모든 직급</option>
                {positions.map(pos => (
                  <option key={pos.code} value={pos.name}>{pos.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Users className="w-6 h-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">전체 사용자</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">활성 사용자</p>
              <p className="text-2xl font-bold text-gray-900">{stats.active}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-red-100 rounded-lg">
              <Shield className="w-6 h-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">관리자</p>
              <p className="text-2xl font-bold text-gray-900">{stats.admin}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Building className="w-6 h-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">부서 수</p>
              <p className="text-2xl font-bold text-gray-900">{stats.departments}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <span className="text-red-800">{error}</span>
        </div>
      )}

      {/* 사용자 테이블 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">사용자 목록</h2>
            <span className="text-sm text-gray-500">{totalUsers}명</span>
          </div>
        </div>

        {/* 일괄 작업 툴바 */}
        {showBulkActions && (
          <div className="p-4 bg-blue-50 border-b border-blue-200 flex items-center justify-between">
            <span className="text-sm font-medium text-blue-900">
              {selectedUsers.size}명 선택됨
            </span>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleBulkRoleChange(true)}
                className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                관리자로 변경
              </button>
              <button
                onClick={() => handleBulkRoleChange(false)}
                className="px-3 py-1.5 bg-gray-600 text-white rounded text-sm hover:bg-gray-700"
              >
                일반 사용자로 변경
              </button>
              <button
                onClick={handleBulkDelete}
                className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700"
              >
                선택 삭제
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={selectedUsers.size === users.length && users.length > 0}
                        onChange={handleToggleSelectAll}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">사용자</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">연락처</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">부서/직급</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">역할</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">상태</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">마지막 로그인</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">작업</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((user) => {
                    const status = getUserStatus(user);
                    return (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4">
                          <input
                            type="checkbox"
                            checked={selectedUsers.has(user.id)}
                            onChange={() => handleToggleSelect(user.id)}
                            className="rounded border-gray-300"
                          />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div className="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center">
                              <span className="text-sm font-medium text-gray-700">
                                {user.emp_name?.charAt(0) || user.username.charAt(0)}
                              </span>
                            </div>
                            <div className="ml-4">
                              <div className="text-sm font-medium text-gray-900">
                                {user.emp_name || user.username}
                              </div>
                              <div className="text-sm text-gray-500">{user.emp_no}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex flex-col space-y-1">
                            <div className="flex items-center text-sm text-gray-900">
                              <Mail className="w-4 h-4 mr-2 text-gray-400" />
                              {user.email}
                            </div>
                            {user.mbtlno && (
                              <div className="flex items-center text-sm text-gray-500">
                                <Phone className="w-4 h-4 mr-2 text-gray-400" />
                                {user.mbtlno}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">{user.dept_name || '-'}</div>
                          <div className="text-sm text-gray-500">{user.position_name || '-'}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getRoleColor(user.role)}`}>
                            {getRoleLabel(user.role)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            {getStatusIcon(status)}
                            <span className={`ml-2 inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(status)}`}>
                              {getStatusLabel(status)}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.last_login ? new Date(user.last_login).toLocaleString('ko-KR') : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => {
                                setSelectedUser(user);
                                setShowEditModal(true);
                              }}
                              className="text-green-600 hover:text-green-900"
                              title="수정"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => {
                                setSelectedUser(user);
                                setShowPasswordResetDialog(true);
                              }}
                              className="text-blue-600 hover:text-blue-900"
                              title="비밀번호 리셋"
                            >
                              <Key className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => {
                                setSelectedUser(user);
                                setShowDeleteDialog(true);
                              }}
                              className="text-red-600 hover:text-red-900"
                              title="삭제"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {users.length === 0 && !loading && (
              <div className="text-center py-12">
                <Users className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">사용자가 없습니다</h3>
                <p className="mt-1 text-sm text-gray-500">검색 조건을 변경하거나 새 사용자를 추가해보세요.</p>
              </div>
            )}

            {/* 페이지네이션 */}
            {users.length > 0 && (
              <div className="px-6 py-4 border-t border-gray-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm text-gray-700">
                    전체 {totalUsers.toLocaleString()}명 중 {((currentPage - 1) * pageSize + 1).toLocaleString()}-
                    {Math.min(currentPage * pageSize, totalUsers).toLocaleString()}명 표시
                  </div>
                  <div className="text-sm text-gray-500">
                    페이지 {currentPage} / {totalPages}
                  </div>
                </div>
                <div className="flex items-center justify-center space-x-2">
                  <button
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    title="첫 페이지"
                  >
                    ««
                  </button>
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    ‹ 이전
                  </button>

                  {/* 페이지 번호 버튼들 */}
                  <div className="flex items-center space-x-1">
                    {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                      let pageNum: number;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (currentPage <= 3) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = currentPage - 2 + i;
                      }

                      return (
                        <button
                          key={pageNum}
                          onClick={() => setCurrentPage(pageNum)}
                          className={`px-3 py-2 text-sm rounded-lg transition-colors ${currentPage === pageNum
                              ? 'bg-blue-600 text-white font-medium'
                              : 'border border-gray-300 hover:bg-gray-50'
                            }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    다음 ›
                  </button>
                  <button
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    title="마지막 페이지"
                  >
                    »»
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* 사용자 추가 모달 */}
      <UserAddModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSubmit={handleAddUser}
      />

      {/* 사용자 수정 모달 */}
      <UserEditModal
        isOpen={showEditModal}
        user={selectedUser}
        onClose={() => {
          setShowEditModal(false);
          setSelectedUser(null);
        }}
        onSubmit={handleUpdateUser}
      />

      {/* 삭제 확인 다이얼로그 */}
      <ConfirmDialog
        isOpen={showDeleteDialog}
        title="사용자 삭제"
        message={`정말로 ${selectedUser?.emp_name || selectedUser?.username} 사용자를 비활성화하시겠습니까?`}
        confirmLabel="삭제"
        onConfirm={handleDeleteUser}
        onCancel={() => {
          setShowDeleteDialog(false);
          setSelectedUser(null);
        }}
      />

      {/* 비밀번호 리셋 확인 다이얼로그 */}
      <ConfirmDialog
        isOpen={showPasswordResetDialog}
        title="비밀번호 리셋"
        message={`${selectedUser?.emp_name || selectedUser?.username} 사용자의 비밀번호를 리셋하시겠습니까?`}
        confirmLabel="리셋"
        onConfirm={handlePasswordReset}
        onCancel={() => {
          setShowPasswordResetDialog(false);
          setSelectedUser(null);
        }}
      />
    </div>
  );
};

// 사용자 추가 모달 컴포넌트
interface UserAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (userData: UserCreateRequest) => void;
}

const UserAddModal: React.FC<UserAddModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [formData, setFormData] = useState<UserCreateRequest>({
    username: '',
    email: '',
    emp_no: '',
    password: '',
    is_admin: false
  });
  const [validationError, setValidationError] = useState<string>('');

  if (!isOpen) return null;

  const validatePassword = (password: string): boolean => {
    setValidationError('');

    if (password.length < 8) {
      setValidationError('비밀번호는 최소 8자 이상이어야 합니다');
      return false;
    }
    if (!/[0-9]/.test(password)) {
      setValidationError('비밀번호에는 최소 1개의 숫자가 포함되어야 합니다');
      return false;
    }
    if (!/[A-Z]/.test(password)) {
      setValidationError('비밀번호에는 최소 1개의 대문자가 포함되어야 합니다');
      return false;
    }
    if (!/[a-z]/.test(password)) {
      setValidationError('비밀번호에는 최소 1개의 소문자가 포함되어야 합니다');
      return false;
    }
    return true;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validatePassword(formData.password)) {
      return;
    }

    onSubmit(formData);
    setFormData({ username: '', email: '', emp_no: '', password: '', is_admin: false });
    setValidationError('');
  };

  const handleClose = () => {
    setFormData({ username: '', email: '', emp_no: '', password: '', is_admin: false });
    setValidationError('');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-medium text-gray-900 mb-4">새 사용자 추가</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">사용자명</label>
            <input
              type="text"
              required
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="예: user001"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">이메일</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="user@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              사번
              <span className="ml-1 text-xs text-gray-500">
                * 신규 사번은 자동으로 SAP 인사 정보에 등록됩니다
              </span>
            </label>
            <input
              type="text"
              required
              value={formData.emp_no}
              onChange={(e) => setFormData({ ...formData, emp_no: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="예: USER001, EMP001"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">비밀번호</label>
            <input
              type="password"
              required
              value={formData.password}
              onChange={(e) => {
                setFormData({ ...formData, password: e.target.value });
                setValidationError('');
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              최소 8자, 대소문자, 숫자 포함 필수
            </p>
            {validationError && (
              <p className="mt-1 text-xs text-red-600">{validationError}</p>
            )}
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_admin"
              checked={formData.is_admin}
              onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="is_admin" className="ml-2 text-sm text-gray-700">
              관리자 권한 부여
            </label>
          </div>
          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              취소
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              추가
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// 사용자 수정 모달 컴포넌트
interface UserEditModalProps {
  isOpen: boolean;
  user: User | null;
  onClose: () => void;
  onSubmit: (userId: number, userData: UserUpdateRequest) => void;
}

const UserEditModal: React.FC<UserEditModalProps> = ({ isOpen, user, onClose, onSubmit }) => {
  const [formData, setFormData] = useState<UserUpdateRequest>({
    username: '',
    email: '',
    is_active: true,
    is_admin: false
  });

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username,
        email: user.email,
        is_active: user.is_active,
        is_admin: user.is_admin
      });
    }
  }, [user]);

  if (!isOpen || !user) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(user.id, formData);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-medium text-gray-900 mb-4">사용자 정보 수정</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">사번</label>
            <input
              type="text"
              value={user.emp_no}
              disabled
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">사용자명</label>
            <input
              type="text"
              required
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">이메일</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_active_edit"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="is_active_edit" className="ml-2 text-sm text-gray-700">
              활성 상태
            </label>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_admin_edit"
              checked={formData.is_admin}
              onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="is_admin_edit" className="ml-2 text-sm text-gray-700">
              관리자 권한
            </label>
          </div>
          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              취소
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              저장
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// 확인 다이얼로그 컴포넌트
interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-medium text-gray-900 mb-4">{title}</h3>
        <p className="text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end space-x-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default UserManagement;

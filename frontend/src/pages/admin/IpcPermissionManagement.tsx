import {
  AlertCircle,
  CheckCircle,
  Filter,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UserPlus,
  XCircle
} from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import {
  bulkCreateIpcPermissions,
  createIpcPermission,
  deleteIpcPermission,
  IpcPermission,
  IpcPermissionCreate,
  IpcPermissionListParams,
  IpcPermissionUpdate,
  listIpcPermissions,
  updateIpcPermission
} from '../../services/adminService';

// 상수 정의
const ROLE_OPTIONS = [
  { value: 'ADMIN', label: '관리자 (ADMIN)', color: 'text-red-600' },
  { value: 'MANAGER', label: '매니저 (MANAGER)', color: 'text-orange-600' },
  { value: 'EDITOR', label: '편집자 (EDITOR)', color: 'text-blue-600' },
  { value: 'VIEWER', label: '조회자 (VIEWER)', color: 'text-green-600' }
];

const ACCESS_SCOPE_OPTIONS = [
  { value: 'FULL', label: '전체' },
  { value: 'READ_ONLY', label: '읽기 전용' },
  { value: 'WRITE_ONLY', label: '쓰기 전용' }
];

const IpcPermissionManagement: React.FC = () => {
  console.log('🔍 IpcPermissionManagement component rendered');
  
  const [permissions, setPermissions] = useState<IpcPermission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // 페이징
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  
  // 필터
  const [filters, setFilters] = useState<IpcPermissionListParams>({
    page: 1,
    page_size: 10,
    is_active: true
  });
  
  // 모달 상태
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedPermission, setSelectedPermission] = useState<IpcPermission | null>(null);
  
  // 폼 데이터
  const [formData, setFormData] = useState<IpcPermissionCreate>({
    user_emp_no: '',
    ipc_code: '',
    role_id: 'VIEWER',
    access_scope: 'FULL',
    include_children: true
  });

  // 권한 목록 조회
  const loadPermissions = useCallback(async () => {
    console.log('📋 Loading IPC permissions...', { filters, page, pageSize });
    setLoading(true);
    setError(null);
    try {
      const response = await listIpcPermissions({
        ...filters,
        page,
        page_size: pageSize
      });
      console.log('✅ IPC permissions loaded:', response);
      setPermissions(response.permissions);
      setTotal(response.total);
    } catch (err: any) {
      console.error('❌ Failed to load IPC permissions:', err);
      setError(err.response?.data?.detail || '권한 목록 조회에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize]);

  useEffect(() => {
    loadPermissions();
  }, [loadPermissions]);

  // 권한 생성
  const handleCreate = async () => {
    if (!formData.user_emp_no || !formData.ipc_code) {
      setError('사번과 IPC 코드는 필수입니다.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await createIpcPermission(formData);
      setSuccess('권한이 생성되었습니다.');
      setShowCreateModal(false);
      setFormData({
        user_emp_no: '',
        ipc_code: '',
        role_id: 'VIEWER',
        access_scope: 'FULL',
        include_children: true
      });
      await loadPermissions();
    } catch (err: any) {
      setError(err.response?.data?.detail || '권한 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 권한 수정
  const handleUpdate = async () => {
    if (!selectedPermission) return;

    setLoading(true);
    setError(null);
    try {
      const updateData: IpcPermissionUpdate = {
        role_id: formData.role_id,
        access_scope: formData.access_scope,
        include_children: formData.include_children,
        valid_until: formData.valid_until
      };
      await updateIpcPermission(selectedPermission.permission_id, updateData);
      setSuccess('권한이 수정되었습니다.');
      setShowEditModal(false);
      setSelectedPermission(null);
      await loadPermissions();
    } catch (err: any) {
      setError(err.response?.data?.detail || '권한 수정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 권한 삭제
  const handleDelete = async (permissionId: number) => {
    if (!window.confirm('정말로 이 권한을 삭제하시겠습니까?')) return;

    setLoading(true);
    setError(null);
    try {
      await deleteIpcPermission(permissionId);
      setSuccess('권한이 삭제되었습니다.');
      await loadPermissions();
    } catch (err: any) {
      setError(err.response?.data?.detail || '권한 삭제에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 수정 모달 열기
  const openEditModal = (permission: IpcPermission) => {
    setSelectedPermission(permission);
    setFormData({
      user_emp_no: permission.user_emp_no,
      ipc_code: permission.ipc_code,
      role_id: permission.role_id,
      access_scope: permission.access_scope,
      include_children: permission.include_children,
      valid_until: permission.valid_until
    });
    setShowEditModal(true);
  };

  // 필터 적용
  const applyFilters = () => {
    setPage(1);
    loadPermissions();
  };

  // 필터 초기화
  const resetFilters = () => {
    setFilters({
      page: 1,
      page_size: 20,
      is_active: true
    });
    setPage(1);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* 헤더 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">IPC 권한 관리</h1>
        <p className="text-gray-600">IPC 코드별 사용자 권한을 관리합니다.</p>
      </div>

      {/* 알림 메시지 */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
          <XCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{error}</span>
        </div>
      )}
      {success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <span className="text-green-700">{success}</span>
        </div>
      )}

      {/* 필터 및 액션 바 */}
      <div className="mb-6 bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            type="text"
            placeholder="사번 검색"
            value={filters.user_emp_no || ''}
            onChange={(e) => setFilters({ ...filters, user_emp_no: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="IPC 코드 검색"
            value={filters.ipc_code || ''}
            onChange={(e) => setFilters({ ...filters, ipc_code: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={filters.role_id || ''}
            onChange={(e) => setFilters({ ...filters, role_id: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">모든 역할</option>
            {ROLE_OPTIONS.map(role => (
              <option key={role.value} value={role.value}>{role.label}</option>
            ))}
          </select>
          <select
            value={filters.is_active === undefined ? '' : filters.is_active.toString()}
            onChange={(e) => setFilters({ ...filters, is_active: e.target.value === '' ? undefined : e.target.value === 'true' })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">모든 상태</option>
            <option value="true">활성</option>
            <option value="false">비활성</option>
          </select>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={applyFilters}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Search className="w-4 h-4" />
            검색
          </button>
          <button
            onClick={resetFilters}
            className="flex items-center gap-2 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
          >
            <RefreshCw className="w-4 h-4" />
            초기화
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 ml-auto"
          >
            <Plus className="w-4 h-4" />
            권한 생성
          </button>
        </div>
      </div>

      {/* 권한 목록 테이블 */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">사번</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">이름</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">부서</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IPC 코드</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">역할</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">범위</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">하위포함</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">상태</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">생성일</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">액션</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-6 py-4 text-center text-gray-500">
                    로딩 중...
                  </td>
                </tr>
              ) : permissions.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-4 text-center text-gray-500">
                    권한이 없습니다.
                  </td>
                </tr>
              ) : (
                permissions.map((permission) => (
                  <tr key={permission.permission_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-900">{permission.user_emp_no}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{permission.user_name || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{permission.department_name || '-'}</td>
                    <td className="px-6 py-4 text-sm font-mono text-blue-600">{permission.ipc_code}</td>
                    <td className="px-6 py-4 text-sm">
                      <span className={`font-medium ${ROLE_OPTIONS.find(r => r.value === permission.role_id)?.color || 'text-gray-600'}`}>
                        {permission.role_id}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{permission.access_scope}</td>
                    <td className="px-6 py-4 text-sm">
                      {permission.include_children ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-gray-400" />
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      {permission.is_active ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">활성</span>
                      ) : (
                        <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs">비활성</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {new Date(permission.created_date).toLocaleDateString('ko-KR')}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <div className="flex gap-2">
                        <button
                          onClick={() => openEditModal(permission)}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          수정
                        </button>
                        <button
                          onClick={() => handleDelete(permission.permission_id)}
                          className="text-red-600 hover:text-red-800"
                        >
                          삭제
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이징 */}
        <div className="px-6 py-4 border-t flex items-center justify-between">
          <div className="text-sm text-gray-600">
            총 {total}개 중 {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)}번째 표시
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              이전
            </button>
            <span className="px-3 py-1">
              {page} / {Math.ceil(total / pageSize)}
            </span>
            <button
              onClick={() => setPage(Math.min(Math.ceil(total / pageSize), page + 1))}
              disabled={page >= Math.ceil(total / pageSize)}
              className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              다음
            </button>
          </div>
        </div>
      </div>

      {/* 생성 모달 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">IPC 권한 생성</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  사번 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.user_emp_no}
                  onChange={(e) => setFormData({ ...formData, user_emp_no: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="예: A12345"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  IPC 코드 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.ipc_code}
                  onChange={(e) => setFormData({ ...formData, ipc_code: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="예: H04W"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">역할</label>
                <select
                  value={formData.role_id}
                  onChange={(e) => setFormData({ ...formData, role_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {ROLE_OPTIONS.map(role => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">접근 범위</label>
                <select
                  value={formData.access_scope}
                  onChange={(e) => setFormData({ ...formData, access_scope: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {ACCESS_SCOPE_OPTIONS.map(scope => (
                    <option key={scope.value} value={scope.value}>{scope.label}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.include_children}
                  onChange={(e) => setFormData({ ...formData, include_children: e.target.checked })}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded"
                />
                <label className="ml-2 text-sm text-gray-700">하위 IPC 코드 포함</label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">유효 기간 (선택)</label>
                <input
                  type="datetime-local"
                  value={formData.valid_until || ''}
                  onChange={(e) => setFormData({ ...formData, valid_until: e.target.value || undefined })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="mt-6 flex gap-2 justify-end">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleCreate}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? '생성 중...' : '생성'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 수정 모달 */}
      {showEditModal && selectedPermission && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">IPC 권한 수정</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">사번</label>
                <input
                  type="text"
                  value={formData.user_emp_no}
                  disabled
                  className="w-full px-3 py-2 border rounded-lg bg-gray-100 text-gray-600"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">IPC 코드</label>
                <input
                  type="text"
                  value={formData.ipc_code}
                  disabled
                  className="w-full px-3 py-2 border rounded-lg bg-gray-100 text-gray-600"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">역할</label>
                <select
                  value={formData.role_id}
                  onChange={(e) => setFormData({ ...formData, role_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {ROLE_OPTIONS.map(role => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">접근 범위</label>
                <select
                  value={formData.access_scope}
                  onChange={(e) => setFormData({ ...formData, access_scope: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {ACCESS_SCOPE_OPTIONS.map(scope => (
                    <option key={scope.value} value={scope.value}>{scope.label}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.include_children}
                  onChange={(e) => setFormData({ ...formData, include_children: e.target.checked })}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded"
                />
                <label className="ml-2 text-sm text-gray-700">하위 IPC 코드 포함</label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">유효 기간 (선택)</label>
                <input
                  type="datetime-local"
                  value={formData.valid_until || ''}
                  onChange={(e) => setFormData({ ...formData, valid_until: e.target.value || undefined })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="mt-6 flex gap-2 justify-end">
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setSelectedPermission(null);
                }}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleUpdate}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? '수정 중...' : '수정'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IpcPermissionManagement;

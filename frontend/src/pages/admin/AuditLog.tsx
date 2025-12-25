import React, { useState, useEffect, useCallback } from 'react';
import { 
  Database, 
  Search, 
  Filter, 
  Download, 
  Eye, 
  Calendar,
  User,
  Activity,
  Shield,
  FileText,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Loader2,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { adminDashboardAPI, AuditLogItem, AuditLogStats } from '../../services/adminService';

const AuditLogComponent: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedResult, setSelectedResult] = useState('all');
  const [showDetails, setShowDetails] = useState<number | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [stats, setStats] = useState<AuditLogStats>({ total: 0, success: 0, failure: 0, warning: 0 });
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    pageSize: 20,
    totalPages: 0
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAuditLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await adminDashboardAPI.getAuditLogs({
        page: pagination.page,
        page_size: pagination.pageSize,
        category: selectedCategory !== 'all' ? selectedCategory : undefined,
        result: selectedResult !== 'all' ? selectedResult : undefined,
        search: searchTerm || undefined,
        days: 30
      });
      
      setAuditLogs(response.logs);
      setPagination(prev => ({
        ...prev,
        total: response.total,
        totalPages: response.total_pages
      }));
    } catch (err) {
      console.error('감사 로그 조회 실패:', err);
      setError('감사 로그를 불러오는데 실패했습니다. 관리자 권한이 필요합니다.');
      setAuditLogs([]);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.page, pagination.pageSize, selectedCategory, selectedResult, searchTerm]);

  const fetchStats = useCallback(async () => {
    try {
      const statsData = await adminDashboardAPI.getAuditLogStats(30);
      setStats(statsData);
    } catch (err) {
      console.error('감사 로그 통계 조회 실패:', err);
    }
  }, []);

  useEffect(() => {
    fetchAuditLogs();
    fetchStats();
  }, [fetchAuditLogs, fetchStats]);

  const handleRefresh = async () => {
    await fetchAuditLogs();
    await fetchStats();
  };

  const handleSearch = () => {
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handlePageChange = (newPage: number) => {
    setPagination(prev => ({ ...prev, page: newPage }));
  };

  const getResultIcon = (result: string) => {
    switch (result) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failure':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getResultColor = (result: string) => {
    switch (result) {
      case 'success':
        return 'bg-green-100 text-green-800';
      case 'failure':
        return 'bg-red-100 text-red-800';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'authentication':
        return <User className="w-4 h-4" />;
      case 'authorization':
      case 'permission':
        return <Shield className="w-4 h-4" />;
      case 'data_access':
        return <FileText className="w-4 h-4" />;
      case 'configuration':
        return <Activity className="w-4 h-4" />;
      case 'system':
        return <Database className="w-4 h-4" />;
      default:
        return <Activity className="w-4 h-4" />;
    }
  };

  const getActionTypeName = (actionType: string) => {
    const actionMap: Record<string, string> = {
      'grant': '권한 부여',
      'revoke': '권한 취소',
      'modify': '권한 변경',
      'access': '접근',
      'approve': '승인',
      'reject': '거부',
      'login': '로그인',
      'logout': '로그아웃'
    };
    return actionMap[actionType] || actionType;
  };

  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return '-';
    try {
      return new Date(timestamp).toLocaleString('ko-KR');
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">감사 로그</h1>
          <p className="text-gray-600">시스템 활동과 보안 이벤트를 추적하고 분석하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <button 
            disabled
            className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-400 cursor-not-allowed"
          >
            <Download className="w-4 h-4" />
            <span>로그 내보내기</span>
          </button>
          <button 
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>새로고침</span>
          </button>
        </div>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{error}</span>
        </div>
      )}

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Database className="w-6 h-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">전체 로그</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">성공</p>
              <p className="text-2xl font-bold text-gray-900">{stats.success.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-red-100 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">실패</p>
              <p className="text-2xl font-bold text-gray-900">{stats.failure.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">경고</p>
              <p className="text-2xl font-bold text-gray-900">{stats.warning.toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 필터 및 검색 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0 md:space-x-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="사용자, 컨테이너로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <select 
                value={selectedCategory}
                onChange={(e) => {
                  setSelectedCategory(e.target.value);
                  setPagination(prev => ({ ...prev, page: 1 }));
                }}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="all">모든 카테고리</option>
                <option value="permission">권한</option>
                <option value="access">접근</option>
                <option value="system">시스템</option>
              </select>
            </div>
            <select 
              value={selectedResult}
              onChange={(e) => {
                setSelectedResult(e.target.value);
                setPagination(prev => ({ ...prev, page: 1 }));
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="all">모든 결과</option>
              <option value="success">성공</option>
              <option value="failure">실패</option>
            </select>
            <button
              onClick={handleSearch}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm"
            >
              검색
            </button>
          </div>
        </div>
      </div>

      {/* 감사 로그 테이블 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">감사 로그 목록</h2>
            <span className="text-sm text-gray-500">{pagination.total.toLocaleString()}개 항목</span>
          </div>
        </div>
        
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
          </div>
        ) : auditLogs.length === 0 ? (
          <div className="text-center py-12">
            <Database className="mx-auto h-12 w-12 text-gray-300" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">로그가 없습니다</h3>
            <p className="mt-1 text-sm text-gray-500">
              {error ? '감사 로그를 불러올 수 없습니다.' : '조회 조건에 맞는 로그가 없습니다.'}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">시간</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">사용자</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">작업</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">대상</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">결과</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">상세</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {auditLogs.map((log) => (
                    <React.Fragment key={log.audit_id}>
                      <tr className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          <div className="flex items-center space-x-2">
                            <Calendar className="w-4 h-4 text-gray-400" />
                            <span>{formatTimestamp(log.timestamp)}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">
                            {log.user_name || log.user_emp_no}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center space-x-2">
                            {getCategoryIcon(log.resource_type)}
                            <span className="text-sm text-gray-900">
                              {getActionTypeName(log.action_type)}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {log.container_name || log.target_user_emp_no || '-'}
                          </div>
                          {log.old_permission && log.new_permission && (
                            <div className="text-xs text-gray-500">
                              {log.old_permission} → {log.new_permission}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-2">
                            {getResultIcon(log.action_result)}
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getResultColor(log.action_result)}`}>
                              {log.action_result === 'success' ? '성공' : log.action_result === 'failure' ? '실패' : '경고'}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {log.ip_address || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <button
                            onClick={() => setShowDetails(showDetails === log.audit_id ? null : log.audit_id)}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                      {showDetails === log.audit_id && (
                        <tr>
                          <td colSpan={7} className="px-6 py-4 bg-gray-50">
                            <div className="space-y-2 text-sm">
                              <div><strong>리소스 유형:</strong> {log.resource_type}</div>
                              <div><strong>대상 사용자:</strong> {log.target_user_emp_no || '-'}</div>
                              <div><strong>컨테이너 ID:</strong> {log.container_id || '-'}</div>
                              {log.failure_reason && (
                                <div><strong>실패 사유:</strong> {log.failure_reason}</div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* 페이지네이션 */}
            {pagination.totalPages > 1 && (
              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
                <div className="text-sm text-gray-500">
                  {((pagination.page - 1) * pagination.pageSize) + 1} - {Math.min(pagination.page * pagination.pageSize, pagination.total)} / {pagination.total}건
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handlePageChange(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <span className="px-3 py-1 text-sm">
                    {pagination.page} / {pagination.totalPages}
                  </span>
                  <button
                    onClick={() => handlePageChange(pagination.page + 1)}
                    disabled={pagination.page >= pagination.totalPages}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export { AuditLogComponent as AuditLog };
export default AuditLogComponent;

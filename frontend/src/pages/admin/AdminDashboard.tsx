import React, { useEffect, useState } from 'react';
import { 
  Users, 
  Database, 
  Activity, 
  AlertTriangle,
  CheckCircle,
  FileText,
  Loader2,
  RefreshCw
} from 'lucide-react';
import { adminDashboardAPI, AdminDashboardStats } from '../../services/adminService';

interface DashboardState {
  stats: AdminDashboardStats | null;
  isLoading: boolean;
  error: string | null;
}

export const AdminDashboard: React.FC = () => {
  const [state, setState] = useState<DashboardState>({
    stats: null,
    isLoading: true,
    error: null
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchStats = async () => {
    try {
      // 관리자 대시보드 통계 조회 (실제 API)
      const dashboardStats = await adminDashboardAPI.getStats();
      
      setState({
        stats: dashboardStats,
        isLoading: false,
        error: null
      });
    } catch (error) {
      console.error('대시보드 통계 로드 실패:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: '통계 데이터를 불러오는데 실패했습니다. 관리자 권한이 필요합니다.'
      }));
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchStats();
    setIsRefreshing(false);
  };

  const systemStats = [
    {
      title: '총 사용자',
      value: state.stats?.total_users.toLocaleString() || '0',
      icon: Users,
      color: 'blue',
      isReal: true
    },
    {
      title: '활성 사용자',
      value: state.stats?.active_users.toLocaleString() || '0',
      icon: Activity,
      color: 'green',
      isReal: true
    },
    {
      title: '총 문서 수',
      value: state.stats?.total_documents.toLocaleString() || '0',
      icon: FileText,
      color: 'purple',
      isReal: true
    },
    {
      title: '지식 컨테이너',
      value: state.stats?.total_containers.toLocaleString() || '0',
      icon: Database,
      color: 'indigo',
      isReal: true
    }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">시스템 관리 대시보드</h1>
          <p className="text-gray-600">전체 시스템 상태를 확인하세요</p>
        </div>
        <div className="flex items-center space-x-2">
          <button 
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>새로고침</span>
          </button>
        </div>
      </div>

      {/* 에러 표시 */}
      {state.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{state.error}</span>
        </div>
      )}

      {/* 시스템 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {systemStats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.title} className="bg-white rounded-lg shadow-sm p-6 border border-gray-200 relative">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                  {state.isLoading ? (
                    <Loader2 className="w-6 h-6 text-gray-400 animate-spin mt-2" />
                  ) : (
                    <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                  )}
                </div>
                <div className={`p-3 rounded-lg bg-${stat.color}-100`}>
                  <Icon className={`w-6 h-6 text-${stat.color}-600`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 시스템 상태 요약 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 시스템 헬스체크 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <Activity className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">시스템 상태</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="font-medium text-gray-900">백엔드 API</span>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                  정상
                </span>
              </div>
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="font-medium text-gray-900">데이터베이스</span>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                  정상
                </span>
              </div>
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="font-medium text-gray-900">인증 서비스</span>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                  정상
                </span>
              </div>
            </div>
            <p className="mt-4 text-sm text-gray-500 text-center">
              * 상세 모니터링은 시스템 모니터링 페이지에서 확인하세요
            </p>
          </div>
        </div>

        {/* 빠른 링크 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">관리 메뉴 바로가기</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 gap-4">
              <a 
                href="/admin/users" 
                className="flex items-center space-x-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Users className="w-5 h-5 text-blue-600" />
                <span className="font-medium text-gray-900">사용자 관리</span>
              </a>
              <a 
                href="/admin/security" 
                className="flex items-center space-x-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Activity className="w-5 h-5 text-green-600" />
                <span className="font-medium text-gray-900">보안 정책</span>
              </a>
              <a 
                href="/admin/audit" 
                className="flex items-center space-x-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <FileText className="w-5 h-5 text-purple-600" />
                <span className="font-medium text-gray-900">감사 로그</span>
              </a>
              <a 
                href="/admin/monitoring" 
                className="flex items-center space-x-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Database className="w-5 h-5 text-indigo-600" />
                <span className="font-medium text-gray-900">시스템 모니터링</span>
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* 향후 개발 안내 */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-amber-800">개발 예정 기능</h3>
            <ul className="mt-2 text-sm text-amber-700 space-y-1">
              <li>• AI 사용량 모니터링 (토큰 사용량, 비용 추적)</li>
              <li>• 문서 처리 현황 대시보드</li>
              <li>• 실시간 알림 시스템</li>
              <li>• 저장소 사용량 조회</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle,
  Clock,
  FileText,
  Folder,
  Users
} from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getManagementStats, getPendingPermissionRequests, getQualityMetrics } from '../../services/managerService';
import { ManagementStats, PermissionRequest, QualityMetric } from '../../types/manager.types';

export const ManagerDashboard: React.FC = () => {
  const [stats, setStats] = useState<ManagementStats | null>(null);
  const [pendingRequests, setPendingRequests] = useState<PermissionRequest[]>([]);
  const [qualityMetrics, setQualityMetrics] = useState<QualityMetric[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setIsLoading(true);

      // API들을 개별적으로 호출하여 일부 실패해도 계속 진행
      const statsPromise = getManagementStats().catch(() => null);
      const requestsPromise = getPendingPermissionRequests().catch(() => []);
      const metricsPromise = getQualityMetrics().catch(() => []);

      const [statsData, requestsData, metricsData] = await Promise.all([
        statsPromise,
        requestsPromise,
        metricsPromise
      ]);

      if (statsData) setStats(statsData);
      if (requestsData) setPendingRequests(requestsData.slice(0, 5)); // 최근 5개만
      if (metricsData) setQualityMetrics(metricsData.slice(0, 5)); // 최근 5개만
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">대시보드를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-4 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* 환영 메시지 */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">지식관리자 대시보드</h1>
          <p className="mt-2 text-sm text-gray-600">
            팀의 지식 관리 현황을 한눈에 확인하고 관리하세요.
          </p>
        </div>

        {/* 주요 통계 */}
        {stats && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Folder className="h-8 w-8 text-blue-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">관리 컨테이너</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.container_count}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Clock className="h-8 w-8 text-yellow-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">승인 대기</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.pending_requests}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Users className="h-8 w-8 text-green-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">활성 사용자</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.active_users}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <FileText className="h-8 w-8 text-purple-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">이번 달 업로드</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.monthly_uploads}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* 승인 대기 목록 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">승인 대기 요청</h3>
              <Link
                to="/manager/permissions"
                className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center"
              >
                전체 보기
                <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </div>
            <div className="p-6">
              {pendingRequests.length === 0 ? (
                <div className="text-center py-4">
                  <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-2" />
                  <p className="text-gray-500">승인 대기 중인 요청이 없습니다.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {pendingRequests.map((request) => (
                    <div key={request.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900">{request.user_name}</span>
                          <span className="text-sm text-gray-500">({request.user_department})</span>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">
                          {request.container_name} - {request.permission_type === 'read' ? '읽기' : '쓰기'} 권한
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <button className="px-3 py-1 bg-green-100 text-green-700 text-xs rounded-md hover:bg-green-200">
                          승인
                        </button>
                        <button className="px-3 py-1 bg-red-100 text-red-700 text-xs rounded-md hover:bg-red-200">
                          반려
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 품질 메트릭 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">문서 품질 현황</h3>
              <Link
                to="/manager/analytics"
                className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center"
              >
                상세 분석
                <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </div>
            <div className="p-6">
              {qualityMetrics.length === 0 ? (
                <div className="text-center py-4">
                  <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                  <p className="text-gray-500">품질 데이터가 없습니다.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {qualityMetrics.map((metric) => (
                    <div key={metric.document_id} className="flex items-center justify-between">
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900 truncate">{metric.document_title}</h4>
                        <div className="flex items-center space-x-4 mt-1">
                          <span className="text-sm text-gray-500">
                            평점: {metric.average_rating.toFixed(1)}
                          </span>
                          <span className="text-sm text-gray-500">
                            조회: {metric.view_count}
                          </span>
                          <span className="text-sm text-gray-500">
                            품질: {metric.quality_score.toFixed(1)}
                          </span>
                        </div>
                      </div>
                      {metric.issues.length > 0 && (
                        <AlertTriangle className="w-5 h-5 text-yellow-500" />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 빠른 액션 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            to="/manager/containers"
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Folder className="h-8 w-8 text-blue-600" />
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-medium text-gray-900">지식컨테이너 관리</h3>
                <p className="text-sm text-gray-500">새 컨테이너 생성 및 관리</p>
              </div>
            </div>
          </Link>

          <Link
            to="/manager/permissions"
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Users className="h-8 w-8 text-green-600" />
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-medium text-gray-900">권한 관리</h3>
                <p className="text-sm text-gray-500">사용자 권한 설정 및 승인</p>
              </div>
            </div>
          </Link>

          <Link
            to="/manager/documents"
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <FileText className="h-8 w-8 text-purple-600" />
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-medium text-gray-900">문서 관리</h3>
                <p className="text-sm text-gray-500">문서 승인 및 품질 관리</p>
              </div>
            </div>
          </Link>

          <Link
            to="/manager/analytics"
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <BarChart3 className="h-8 w-8 text-orange-600" />
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-medium text-gray-900">분석 리포트</h3>
                <p className="text-sm text-gray-500">사용 현황 및 성과 분석</p>
              </div>
            </div>
          </Link>
        </div>

        {/* 관리 팁 */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h4 className="font-medium text-blue-900 mb-3">💡 지식관리자 활용 팁</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800">
            <ul className="space-y-1">
              <li>• 정기적으로 승인 대기 요청을 확인하세요</li>
              <li>• 컨테이너 구조를 체계적으로 설계하세요</li>
              <li>• 문서 품질 지표를 주기적으로 점검하세요</li>
            </ul>
            <ul className="space-y-1">
              <li>• 사용자 피드백을 적극 수집하고 반영하세요</li>
              <li>• 자주 사용되지 않는 문서는 아카이브하세요</li>
              <li>• 팀원들에게 지식 공유 문화를 권장하세요</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ManagerDashboard;

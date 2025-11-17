import React, { useEffect, useState } from 'react';
import { getContainers, getManagementStats, getPendingPermissionRequests } from '../../services/managerService';
import { Container, ManagementStats, PermissionRequest } from '../../types/manager.types';

export const ManagerDashboard: React.FC = () => {
  const [stats, setStats] = useState<ManagementStats | null>(null);
  const [pendingRequests, setPendingRequests] = useState<PermissionRequest[]>([]);
  const [containers, setContainers] = useState<Container[]>([]);
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
      const containersPromise = getContainers().catch(() => []);

      const [statsData, requestsData, containersData] = await Promise.all([
        statsPromise,
        requestsPromise,
        containersPromise
      ]);

      if (statsData) setStats(statsData);
      if (requestsData) setPendingRequests(requestsData);
      if (containersData) setContainers(containersData);
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
        {/* 헤더 */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">지식관리자 대시보드</h1>
          <p className="mt-2 text-sm text-gray-600">
            지식컨테이너 관리, 권한 승인, 품질 관리 현황을 확인하세요.
          </p>
        </div>

        {/* 통계 카드 */}
        {stats && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">📊</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">월간 업로드</p>
                  <p className="text-lg font-semibold text-gray-900">{stats.monthly_uploads}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">📁</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">관리 컨테이너</p>
                  <p className="text-lg font-semibold text-gray-900">{stats.container_count}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">⏳</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">대기 요청</p>
                  <p className="text-lg font-semibold text-yellow-600">{stats.pending_requests}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">👥</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">활성 사용자</p>
                  <p className="text-lg font-semibold text-gray-900">{stats.active_users}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 대기 중인 권한 요청 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">대기 중인 권한 요청</h3>
            </div>
            <div className="p-6">
              {pendingRequests.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-2">✅</div>
                  <p className="text-gray-500">대기 중인 요청이 없습니다.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingRequests.slice(0, 5).map((request) => (
                    <div key={request.id} className="flex items-center justify-between py-2 border-b border-gray-100">
                      <div className="flex-1">
                        <div className="font-medium text-sm text-gray-900">{request.user_name}</div>
                        <div className="text-xs text-gray-500">{request.container_name} 접근 요청</div>
                      </div>
                      <div className="flex space-x-2">
                        <button className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded hover:bg-green-200">
                          승인
                        </button>
                        <button className="text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200">
                          거부
                        </button>
                      </div>
                    </div>
                  ))}
                  {pendingRequests.length > 5 && (
                    <div className="text-center pt-2">
                      <a href="/manager/permissions" className="text-blue-600 text-sm hover:text-blue-800">
                        더 보기 ({pendingRequests.length - 5}개 추가)
                      </a>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 최근 컨테이너 활동 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">컨테이너 현황</h3>
            </div>
            <div className="p-6">
              {containers.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-2">📁</div>
                  <p className="text-gray-500">관리 중인 컨테이너가 없습니다.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {containers.slice(0, 5).map((container) => (
                    <div key={container.id} className="flex items-center justify-between py-2 border-b border-gray-100">
                      <div className="flex-1">
                        <div className="font-medium text-sm text-gray-900">{container.name}</div>
                        <div className="text-xs text-gray-500">{container.document_count}개 문서</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-gray-900">{container.document_count}</div>
                        <div className="text-xs text-gray-500">문서</div>
                      </div>
                    </div>
                  ))}
                  {containers.length > 5 && (
                    <div className="text-center pt-2">
                      <a href="/manager/containers" className="text-blue-600 text-sm hover:text-blue-800">
                        모든 컨테이너 보기
                      </a>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 빠른 작업 */}
        <div className="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">빠른 작업</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <a
              href="/manager/containers"
              className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="text-2xl mr-3">📁</div>
              <div>
                <div className="font-medium text-gray-900">지식컨테이너 관리</div>
                <div className="text-sm text-gray-500">새 컨테이너 생성</div>
              </div>
            </a>
            <a
              href="/manager/permissions"
              className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="text-2xl mr-3">✅</div>
              <div>
                <div className="font-medium text-gray-900">권한 승인</div>
                <div className="text-sm text-gray-500">대기 중인 요청 처리</div>
              </div>
            </a>
            <a
              href="/manager/quality"
              className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="text-2xl mr-3">⭐</div>
              <div>
                <div className="font-medium text-gray-900">품질 관리</div>
                <div className="text-sm text-gray-500">문서 품질 검토</div>
              </div>
            </a>
            <a
              href="/manager/support"
              className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="text-2xl mr-3">🎧</div>
              <div>
                <div className="font-medium text-gray-900">사용자 지원</div>
                <div className="text-sm text-gray-500">지원 티켓 관리</div>
              </div>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ManagerDashboard;

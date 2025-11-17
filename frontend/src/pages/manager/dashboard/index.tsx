import { Lightbulb } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import { getManagementStats, getPendingPermissionRequests, getQualityMetrics } from '../../../services/managerService';
import { ManagementStats, PermissionRequest, QualityMetric } from '../../../types/manager.types';
import { PendingRequests, QualityMetrics, QuickActions, StatsCards } from './components';

const Dashboard: React.FC = () => {
    const [stats, setStats] = useState<ManagementStats | null>(null);
    const [pendingRequests, setPendingRequests] = useState<PermissionRequest[]>([]);
    const [qualityMetrics, setQualityMetrics] = useState<QualityMetric[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const loadDashboardData = useCallback(async () => {
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
    }, []);

    useEffect(() => {
        loadDashboardData();
    }, [loadDashboardData]);

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

                {/* 주요 통계 카드 */}
                {stats && <StatsCards stats={stats} />}

                {/* 승인 대기 및 품질 현황 */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    <PendingRequests requests={pendingRequests} onUpdate={loadDashboardData} />
                    <QualityMetrics metrics={qualityMetrics} />
                </div>

                {/* 빠른 작업 */}
                <div className="mb-6">
                    <QuickActions />
                </div>

                {/* 관리 팁 */}
                <div className="bg-blue-50 rounded-lg border border-blue-200 p-6">
                    <div className="flex items-start">
                        <Lightbulb className="w-6 h-6 text-blue-600 mt-1" />
                        <div className="ml-3">
                            <h3 className="text-lg font-medium text-blue-900">관리 팁</h3>
                            <ul className="mt-2 space-y-2 text-sm text-blue-800">
                                <li>• 승인 대기 중인 요청은 가능한 빠르게 처리해 주세요.</li>
                                <li>• 컨테이너 구조는 정기적으로 검토하여 최적화하세요.</li>
                                <li>• 품질 점수가 낮은 문서는 개선이 필요합니다.</li>
                                <li>• 사용자 피드백을 활용하여 지식 관리를 개선하세요.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;

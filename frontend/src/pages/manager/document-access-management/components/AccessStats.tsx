import { BarChart3, Globe, Lock, Users } from 'lucide-react';
import React from 'react';
import type { AccessLevelStats } from '../../../../types/manager.types';

interface AccessStatsProps {
    stats: AccessLevelStats;
}

export const AccessStats: React.FC<AccessStatsProps> = ({ stats }) => {
    const getPercentage = (count: number) => {
        if (stats.total_count === 0) return 0;
        return Math.round((count / stats.total_count) * 100);
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-medium text-gray-900">접근 레벨 통계</h3>
                <BarChart3 className="w-5 h-5 text-gray-400" />
            </div>

            <div className="space-y-4">
                {/* 공개 */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center">
                        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mr-3">
                            <Globe className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                            <div className="text-sm font-medium text-gray-900">공개</div>
                            <div className="text-xs text-gray-500">모든 사용자 접근 가능</div>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-lg font-semibold text-gray-900">
                            {stats.public_count}
                        </div>
                        <div className="text-xs text-gray-500">
                            {getPercentage(stats.public_count)}%
                        </div>
                    </div>
                </div>

                {/* 제한 */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center">
                        <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center mr-3">
                            <Users className="w-5 h-5 text-yellow-600" />
                        </div>
                        <div>
                            <div className="text-sm font-medium text-gray-900">제한</div>
                            <div className="text-xs text-gray-500">특정 사용자/부서만</div>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-lg font-semibold text-gray-900">
                            {stats.restricted_count}
                        </div>
                        <div className="text-xs text-gray-500">
                            {getPercentage(stats.restricted_count)}%
                        </div>
                    </div>
                </div>

                {/* 비공개 */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center">
                        <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center mr-3">
                            <Lock className="w-5 h-5 text-red-600" />
                        </div>
                        <div>
                            <div className="text-sm font-medium text-gray-900">비공개</div>
                            <div className="text-xs text-gray-500">관리자만 접근</div>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-lg font-semibold text-gray-900">
                            {stats.private_count}
                        </div>
                        <div className="text-xs text-gray-500">
                            {getPercentage(stats.private_count)}%
                        </div>
                    </div>
                </div>
            </div>

            {/* 총계 */}
            <div className="mt-6 pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">총 문서 수</span>
                    <span className="text-lg font-semibold text-gray-900">{stats.total_count}</span>
                </div>
            </div>

            {/* 시각화 바 */}
            <div className="mt-4">
                <div className="h-4 bg-gray-200 rounded-full overflow-hidden flex">
                    {stats.public_count > 0 && (
                        <div
                            className="bg-green-500 h-full"
                            style={{ width: `${getPercentage(stats.public_count)}%` }}
                            title={`공개: ${stats.public_count}개 (${getPercentage(stats.public_count)}%)`}
                        />
                    )}
                    {stats.restricted_count > 0 && (
                        <div
                            className="bg-yellow-500 h-full"
                            style={{ width: `${getPercentage(stats.restricted_count)}%` }}
                            title={`제한: ${stats.restricted_count}개 (${getPercentage(stats.restricted_count)}%)`}
                        />
                    )}
                    {stats.private_count > 0 && (
                        <div
                            className="bg-red-500 h-full"
                            style={{ width: `${getPercentage(stats.private_count)}%` }}
                            title={`비공개: ${stats.private_count}개 (${getPercentage(stats.private_count)}%)`}
                        />
                    )}
                </div>
            </div>
        </div>
    );
};

import { Clock, FileText, Folder, Users } from 'lucide-react';
import React from 'react';
import { ManagementStats } from '../../../../types/manager.types';

interface StatsCardsProps {
    stats: ManagementStats | null;
}

export const StatsCards: React.FC<StatsCardsProps> = ({ stats }) => {
    if (!stats) return null;

    return (
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
    );
};

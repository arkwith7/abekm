import React from 'react';

interface PermissionStatsProps {
    uniqueUserCount: number;
    containerCount: number;
    totalPermissions: number;
}

export const PermissionStats: React.FC<PermissionStatsProps> = ({
    uniqueUserCount,
    containerCount,
    totalPermissions
}) => {
    return (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div className="flex items-center">
                    <div className="flex-shrink-0 text-2xl">👥</div>
                    <div className="ml-3">
                        <p className="text-sm font-medium text-gray-500">팀원 수</p>
                        <p className="text-lg font-semibold text-gray-900">{uniqueUserCount}</p>
                    </div>
                </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div className="flex items-center">
                    <div className="flex-shrink-0 text-2xl">📁</div>
                    <div className="ml-3">
                        <p className="text-sm font-medium text-gray-500">관리 컨테이너</p>
                        <p className="text-lg font-semibold text-gray-900">{containerCount}</p>
                    </div>
                </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div className="flex items-center">
                    <div className="flex-shrink-0 text-2xl">🔐</div>
                    <div className="ml-3">
                        <p className="text-sm font-medium text-gray-500">설정된 권한</p>
                        <p className="text-lg font-semibold text-gray-900">{totalPermissions}</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

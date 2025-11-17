import React from 'react';

interface StatCardProps {
    icon: string;
    label: string;
    value: number;
}

export const StatCard: React.FC<StatCardProps> = ({ icon, label, value }) => {
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
            <div className="flex items-center">
                <div className="flex-shrink-0 text-3xl">{icon}</div>
                <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500">{label}</p>
                    <p className="text-2xl font-bold text-gray-900">{value.toLocaleString()}</p>
                </div>
            </div>
        </div>
    );
};

interface StatsGridProps {
    totalContainers: number;
    totalDocuments: number;
    totalUsers: number;
    totalViews: number;
}

export const StatsGrid: React.FC<StatsGridProps> = ({
    totalContainers,
    totalDocuments,
    totalUsers,
    totalViews
}) => {
    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard icon="📁" label="전체 컨테이너" value={totalContainers} />
            <StatCard icon="📄" label="총 문서 수" value={totalDocuments} />
            <StatCard icon="👥" label="접근 사용자" value={totalUsers} />
            <StatCard icon="👁️" label="총 조회수" value={totalViews} />
        </div>
    );
};

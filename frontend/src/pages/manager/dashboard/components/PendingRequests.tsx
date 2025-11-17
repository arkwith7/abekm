import { ArrowRight, CheckCircle } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { PermissionRequest } from '../../../../types/manager.types';

interface PendingRequestsProps {
    requests: PermissionRequest[];
    onUpdate?: () => void;
}

export const PendingRequests: React.FC<PendingRequestsProps> = ({ requests, onUpdate }) => {
    return (
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
                {requests.length === 0 ? (
                    <div className="text-center py-4">
                        <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-2" />
                        <p className="text-gray-500">승인 대기 중인 요청이 없습니다.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {requests.map((request) => (
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
    );
};

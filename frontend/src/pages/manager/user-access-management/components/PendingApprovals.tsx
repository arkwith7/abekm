import { Check, Clock, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { approvePermissionRequest, getPendingPermissionRequests, rejectPermissionRequest } from '../../../../services/managerService';
import type { PermissionRequest } from '../../../../types/manager.types';

export const PendingApprovals: React.FC = () => {
    const [requests, setRequests] = useState<PermissionRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [processingId, setProcessingId] = useState<string | null>(null);

    useEffect(() => {
        loadPendingRequests();
    }, []);

    const loadPendingRequests = async () => {
        try {
            setIsLoading(true);
            const data = await getPendingPermissionRequests();
            setRequests(data);
        } catch (error) {
            console.error('Failed to load pending requests:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleApprove = async (requestId: string) => {
        if (!window.confirm('이 권한 요청을 승인하시겠습니까?')) return;

        try {
            setProcessingId(requestId);
            await approvePermissionRequest(requestId, '승인되었습니다.');
            alert('권한 요청이 승인되었습니다.');
            await loadPendingRequests();
        } catch (error) {
            console.error('Failed to approve request:', error);
            alert('승인 처리에 실패했습니다.');
        } finally {
            setProcessingId(null);
        }
    };

    const handleReject = async (requestId: string) => {
        const reason = window.prompt('거부 사유를 입력해주세요:');
        if (!reason) return;

        try {
            setProcessingId(requestId);
            await rejectPermissionRequest(requestId, reason);
            alert('권한 요청이 거부되었습니다.');
            await loadPendingRequests();
        } catch (error) {
            console.error('Failed to reject request:', error);
            alert('거부 처리에 실패했습니다.');
        } finally {
            setProcessingId(null);
        }
    };

    const getPermissionBadge = (permissionType: string) => {
        const badges = {
            read: { label: '읽기', color: 'bg-green-100 text-green-800' },
            write: { label: '읽기/쓰기', color: 'bg-blue-100 text-blue-800' },
            admin: { label: '관리자', color: 'bg-purple-100 text-purple-800' }
        };
        const badge = badges[permissionType as keyof typeof badges] || { label: permissionType, color: 'bg-gray-100 text-gray-800' };
        return (
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${badge.color}`}>
                {badge.label}
            </span>
        );
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    if (requests.length === 0) {
        return (
            <div className="bg-white rounded-lg shadow-sm p-12 text-center">
                <Clock className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">승인 대기 중인 요청이 없습니다</h3>
                <p className="text-gray-500">새로운 권한 요청이 들어오면 여기에 표시됩니다.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* 통계 */}
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <div className="flex items-center">
                    <Clock className="w-5 h-5 text-orange-600 mr-2" />
                    <span className="font-medium text-orange-900">
                        승인 대기: <span className="text-2xl ml-2">{requests.length}</span>건
                    </span>
                </div>
            </div>

            {/* 요청 목록 */}
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    요청일시
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    요청자
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    부서
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    지식컨테이너
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    요청권한
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    요청사유
                                </th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    작업
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {requests.map((request) => (
                                <tr key={request.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                        {request.requested_at ? new Date(request.requested_at).toLocaleString('ko-KR') : '-'}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="text-sm font-medium text-gray-900">{request.user_name}</div>
                                        <div className="text-sm text-gray-500">{request.user_id}</div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {request.user_department || '-'}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="text-sm font-medium text-gray-900">{request.container_name}</div>
                                        <div className="text-sm text-gray-500">{request.container_id}</div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        {getPermissionBadge(request.permission_type)}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                                        {request.reason || '-'}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        <div className="flex items-center justify-center space-x-2">
                                            <button
                                                onClick={() => handleApprove(request.id)}
                                                disabled={processingId === request.id}
                                                className="inline-flex items-center px-3 py-1.5 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                                title="승인"
                                            >
                                                <Check className="w-4 h-4 mr-1" />
                                                승인
                                            </button>
                                            <button
                                                onClick={() => handleReject(request.id)}
                                                disabled={processingId === request.id}
                                                className="inline-flex items-center px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                                title="거부"
                                            >
                                                <X className="w-4 h-4 mr-1" />
                                                거부
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* 안내 메시지 */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex">
                    <div className="flex-shrink-0">
                        <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                        </svg>
                    </div>
                    <div className="ml-3">
                        <h3 className="text-sm font-medium text-blue-800">승인 안내</h3>
                        <div className="mt-2 text-sm text-blue-700">
                            <ul className="list-disc list-inside space-y-1">
                                <li>관리 중인 지식컨테이너에 대한 권한 요청만 표시됩니다.</li>
                                <li>승인 시 즉시 해당 사용자에게 권한이 부여됩니다.</li>
                                <li>거부 시 사유를 입력해주세요. 요청자에게 전달됩니다.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

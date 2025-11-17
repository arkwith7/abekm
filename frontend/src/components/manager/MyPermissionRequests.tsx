import { AlertCircle, Calendar, CheckCircle, Clock, FileText, Loader2, RefreshCw, X, XCircle } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import { cancelPermissionRequest, getMyPermissionRequests } from '../../services/permissionRequestService';
import { PermissionRequest, PermissionRequestStatus } from '../../types/permissionRequest.types';

export const MyPermissionRequests: React.FC = () => {
    const [requests, setRequests] = useState<PermissionRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedStatus, setSelectedStatus] = useState<PermissionRequestStatus | 'ALL'>('ALL');
    const [error, setError] = useState<string | null>(null);

    const loadRequests = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);
            const requests = await getMyPermissionRequests(
                selectedStatus === 'ALL' ? {} : { status: selectedStatus }
            );
            setRequests(requests);
        } catch (error) {
            console.error('Failed to load permission requests:', error);
            setError('요청 목록을 불러오는데 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    }, [selectedStatus]);

    useEffect(() => {
        loadRequests();
    }, [loadRequests]);

    const handleCancel = async (requestId: string) => {
        // eslint-disable-next-line no-restricted-globals
        if (!window.confirm('이 권한 요청을 취소하시겠습니까?')) {
            return;
        }

        try {
            await cancelPermissionRequest(requestId);
            await loadRequests(); // 목록 새로고침
        } catch (error: any) {
            console.error('Failed to cancel request:', error);
            // eslint-disable-next-line no-alert
            window.alert(error.response?.data?.detail || '요청 취소에 실패했습니다.');
        }
    };

    const getStatusBadge = (status: PermissionRequestStatus, autoApproved: boolean) => {
        const badges = {
            PENDING: {
                icon: Clock,
                label: '대기중',
                className: 'bg-yellow-100 text-yellow-800 border-yellow-300'
            },
            APPROVED: {
                icon: CheckCircle,
                label: autoApproved ? '자동승인' : '승인',
                className: 'bg-green-100 text-green-800 border-green-300'
            },
            REJECTED: {
                icon: XCircle,
                label: '거부',
                className: 'bg-red-100 text-red-800 border-red-300'
            },
            CANCELLED: {
                icon: X,
                label: '취소',
                className: 'bg-gray-100 text-gray-800 border-gray-300'
            },
            EXPIRED: {
                icon: AlertCircle,
                label: '만료',
                className: 'bg-orange-100 text-orange-800 border-orange-300'
            }
        };

        const badge = badges[status];
        const Icon = badge.icon;

        return (
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${badge.className}`}>
                <Icon className="w-3 h-3 mr-1" />
                {badge.label}
            </span>
        );
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getStatusCounts = () => {
        return {
            all: requests.length,
            pending: requests.filter(r => r.status === 'PENDING').length,
            approved: requests.filter(r => r.status === 'APPROVED').length,
            rejected: requests.filter(r => r.status === 'REJECTED').length
        };
    };

    const counts = getStatusCounts();

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
                    <p className="text-gray-600">권한 요청 목록을 불러오는 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-900">내 권한 요청</h2>
                <button
                    onClick={loadRequests}
                    className="flex items-center px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    disabled={isLoading}
                >
                    <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                    새로고침
                </button>
            </div>

            {/* 통계 카드 */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <button
                    onClick={() => setSelectedStatus('ALL')}
                    className={`p-4 rounded-lg border-2 transition-all ${selectedStatus === 'ALL'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                        }`}
                >
                    <div className="text-2xl font-bold text-gray-900">{counts.all}</div>
                    <div className="text-sm text-gray-600">전체</div>
                </button>
                <button
                    onClick={() => setSelectedStatus('PENDING')}
                    className={`p-4 rounded-lg border-2 transition-all ${selectedStatus === 'PENDING'
                        ? 'border-yellow-500 bg-yellow-50'
                        : 'border-gray-200 hover:border-gray-300'
                        }`}
                >
                    <div className="text-2xl font-bold text-yellow-600">{counts.pending}</div>
                    <div className="text-sm text-gray-600">대기중</div>
                </button>
                <button
                    onClick={() => setSelectedStatus('APPROVED')}
                    className={`p-4 rounded-lg border-2 transition-all ${selectedStatus === 'APPROVED'
                        ? 'border-green-500 bg-green-50'
                        : 'border-gray-200 hover:border-gray-300'
                        }`}
                >
                    <div className="text-2xl font-bold text-green-600">{counts.approved}</div>
                    <div className="text-sm text-gray-600">승인</div>
                </button>
                <button
                    onClick={() => setSelectedStatus('REJECTED')}
                    className={`p-4 rounded-lg border-2 transition-all ${selectedStatus === 'REJECTED'
                        ? 'border-red-500 bg-red-50'
                        : 'border-gray-200 hover:border-gray-300'
                        }`}
                >
                    <div className="text-2xl font-bold text-red-600">{counts.rejected}</div>
                    <div className="text-sm text-gray-600">거부</div>
                </button>
            </div>

            {/* 에러 메시지 */}
            {error && (
                <div className="flex items-center space-x-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    <p className="text-sm text-red-800">{error}</p>
                </div>
            )}

            {/* 요청 목록 */}
            <div className="space-y-4">
                {requests.length === 0 ? (
                    <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
                        <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                        <p className="text-gray-600">권한 요청 내역이 없습니다.</p>
                    </div>
                ) : (
                    requests.map((request) => (
                        <div
                            key={request.request_id}
                            className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow"
                        >
                            <div className="flex items-start justify-between mb-4">
                                <div className="flex-1">
                                    <div className="flex items-center space-x-3 mb-2">
                                        <h3 className="text-lg font-medium text-gray-900">
                                            {request.container_name || request.container_id}
                                        </h3>
                                        {getStatusBadge(request.status, request.auto_approved)}
                                    </div>
                                    <div className="flex items-center space-x-4 text-sm text-gray-600">
                                        <span className="flex items-center">
                                            <Calendar className="w-4 h-4 mr-1" />
                                            {formatDate(request.requested_at)}
                                        </span>
                                        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded">
                                            {request.requested_role_name || request.requested_role_id}
                                        </span>
                                    </div>
                                </div>
                                {request.status === 'PENDING' && (
                                    <button
                                        onClick={() => handleCancel(request.request_id)}
                                        className="ml-4 px-3 py-1 text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded-md transition-colors"
                                    >
                                        취소
                                    </button>
                                )}
                            </div>

                            {/* 요청 사유 */}
                            <div className="mb-4 p-3 bg-gray-50 rounded-md">
                                <p className="text-sm font-medium text-gray-700 mb-1">요청 사유</p>
                                <p className="text-sm text-gray-600">{request.reason}</p>
                            </div>

                            {/* 처리 정보 */}
                            {request.processed_at && (
                                <div className="border-t border-gray-200 pt-4">
                                    <div className="flex items-start justify-between text-sm">
                                        <div>
                                            <p className="text-gray-600 mb-1">
                                                처리일: {formatDate(request.processed_at)}
                                            </p>
                                            {request.processor_name && (
                                                <p className="text-gray-600">
                                                    처리자: {request.processor_name}
                                                </p>
                                            )}
                                        </div>
                                        {request.rejection_reason && (
                                            <div className="ml-4 flex-1 max-w-md">
                                                <p className="text-sm font-medium text-red-700 mb-1">거부 사유</p>
                                                <p className="text-sm text-red-600 bg-red-50 p-2 rounded">
                                                    {request.rejection_reason}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* 만료 정보 */}
                            {request.expires_at && request.status === 'APPROVED' && (
                                <div className="mt-4 flex items-center text-sm text-gray-600">
                                    <Clock className="w-4 h-4 mr-1" />
                                    만료일: {formatDate(request.expires_at)}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default MyPermissionRequests;

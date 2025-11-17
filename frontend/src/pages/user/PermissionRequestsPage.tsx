import { AlertCircle, Calendar, CheckCircle, Clock, FileText, XCircle } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { getMyPermissionRequests } from '../../services/permissionRequestService';
import type { PermissionRequest } from '../../types/permissionRequest.types';

export const PermissionRequestsPage: React.FC = () => {
    const [requests, setRequests] = useState<PermissionRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all');

    useEffect(() => {
        loadMyRequests();
    }, []);

    const loadMyRequests = async () => {
        try {
            setIsLoading(true);
            const data = await getMyPermissionRequests();
            console.log('🔍 [UI DEBUG] 사용자 권한 신청 데이터 로드:', data);
            setRequests(data);
        } catch (error) {
            console.error('Failed to load permission requests:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const getStatusBadge = (status: string) => {
        const statusMap = {
            PENDING: {
                icon: Clock,
                text: '승인 대기',
                className: 'bg-yellow-100 text-yellow-800 border-yellow-200'
            },
            APPROVED: {
                icon: CheckCircle,
                text: '승인됨',
                className: 'bg-green-100 text-green-800 border-green-200'
            },
            REJECTED: {
                icon: XCircle,
                text: '거부됨',
                className: 'bg-red-100 text-red-800 border-red-200'
            },
            CANCELLED: {
                icon: XCircle,
                text: '취소됨',
                className: 'bg-gray-100 text-gray-800 border-gray-200'
            }
        };

        const config = statusMap[status as keyof typeof statusMap] || statusMap.PENDING;
        const Icon = config.icon;

        return (
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${config.className}`}>
                <Icon className="w-4 h-4 mr-1" />
                {config.text}
            </span>
        );
    };

    const getPermissionLevelBadge = (level: string) => {
        const levelMap: Record<string, { text: string; className: string }> = {
            VIEWER: { text: '읽기', className: 'bg-blue-100 text-blue-800' },
            EDITOR: { text: '편집', className: 'bg-purple-100 text-purple-800' },
            MANAGER: { text: '관리', className: 'bg-indigo-100 text-indigo-800' },
            ADMIN: { text: '관리자', className: 'bg-red-100 text-red-800' },
            OWNER: { text: '소유자', className: 'bg-pink-100 text-pink-800' }
        };

        const config = levelMap[level] || { text: level, className: 'bg-gray-100 text-gray-800' };

        return (
            <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${config.className}`}>
                {config.text}
            </span>
        );
    };

    const filteredRequests = requests.filter(req => {
        if (filter === 'all') return true;
        return req.status?.toLowerCase() === filter.toLowerCase();
    });

    const stats = {
        total: requests.length,
        pending: requests.filter(r => r.status === 'PENDING').length,
        approved: requests.filter(r => r.status === 'APPROVED').length,
        rejected: requests.filter(r => r.status === 'REJECTED').length
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* 페이지 헤더 */}
                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900">권한 신청 현황</h1>
                    <p className="mt-2 text-gray-600">지식 컨테이너 접근 권한 신청 내역을 확인할 수 있습니다.</p>
                </div>

                {/* 통계 카드 */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-600">전체 신청</p>
                                <p className="text-2xl font-bold text-gray-900 mt-1">{stats.total}</p>
                            </div>
                            <FileText className="w-10 h-10 text-gray-400" />
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow-sm p-6 border border-yellow-200 bg-yellow-50">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-yellow-800">승인 대기</p>
                                <p className="text-2xl font-bold text-yellow-900 mt-1">{stats.pending}</p>
                            </div>
                            <Clock className="w-10 h-10 text-yellow-400" />
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow-sm p-6 border border-green-200 bg-green-50">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-green-800">승인 완료</p>
                                <p className="text-2xl font-bold text-green-900 mt-1">{stats.approved}</p>
                            </div>
                            <CheckCircle className="w-10 h-10 text-green-400" />
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow-sm p-6 border border-red-200 bg-red-50">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-red-800">거부됨</p>
                                <p className="text-2xl font-bold text-red-900 mt-1">{stats.rejected}</p>
                            </div>
                            <XCircle className="w-10 h-10 text-red-400" />
                        </div>
                    </div>
                </div>

                {/* 필터 버튼 */}
                <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
                    <div className="flex items-center space-x-2">
                        <span className="text-sm font-medium text-gray-700">필터:</span>
                        <button
                            onClick={() => setFilter('all')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${filter === 'all'
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            전체
                        </button>
                        <button
                            onClick={() => setFilter('pending')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${filter === 'pending'
                                ? 'bg-yellow-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            승인 대기
                        </button>
                        <button
                            onClick={() => setFilter('approved')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${filter === 'approved'
                                ? 'bg-green-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            승인됨
                        </button>
                        <button
                            onClick={() => setFilter('rejected')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${filter === 'rejected'
                                ? 'bg-red-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            거부됨
                        </button>
                    </div>
                </div>

                {/* 신청 목록 */}
                {filteredRequests.length === 0 ? (
                    <div className="bg-white rounded-lg shadow-sm p-12 text-center">
                        <AlertCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <h3 className="text-lg font-medium text-gray-900 mb-2">신청 내역이 없습니다</h3>
                        <p className="text-gray-500">
                            {filter === 'all'
                                ? '아직 권한을 신청한 내역이 없습니다.'
                                : `${filter === 'pending' ? '승인 대기 중인' : filter === 'approved' ? '승인된' : '거부된'} 신청이 없습니다.`
                            }
                        </p>
                    </div>
                ) : (
                    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            신청일시
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            컨테이너
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            요청 권한
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            신청 사유
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            상태
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            처리일시
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            처리 사유
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {filteredRequests.map((request) => (
                                        <tr key={request.request_id} className="hover:bg-gray-50">
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                <div className="flex items-center">
                                                    <Calendar className="w-4 h-4 text-gray-400 mr-2" />
                                                    {new Date(request.requested_at).toLocaleString('ko-KR')}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-sm">
                                                <div className="font-medium text-gray-900">
                                                    {request.container_name || request.container_id}
                                                </div>
                                                <div className="text-gray-500 text-xs">{request.container_id}</div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                {getPermissionLevelBadge(request.requested_permission_level || request.requested_role_id)}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-gray-700 max-w-xs">
                                                <div className="truncate" title={request.request_reason || request.reason}>
                                                    {request.request_reason || request.reason || '-'}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                {getStatusBadge(request.status)}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                {request.processed_at ? (
                                                    <div className="flex items-center">
                                                        <Calendar className="w-4 h-4 text-gray-400 mr-2" />
                                                        {new Date(request.processed_at).toLocaleString('ko-KR')}
                                                    </div>
                                                ) : (
                                                    '-'
                                                )}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-gray-700 max-w-xs">
                                                <div className="truncate" title={request.rejection_reason || ''}>
                                                    {request.rejection_reason || '-'}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* 안내 메시지 */}
                <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <AlertCircle className="h-5 w-5 text-blue-400" />
                        </div>
                        <div className="ml-3">
                            <h3 className="text-sm font-medium text-blue-800">권한 신청 안내</h3>
                            <div className="mt-2 text-sm text-blue-700">
                                <ul className="list-disc list-inside space-y-1">
                                    <li>승인 대기 중인 신청은 해당 컨테이너의 관리자가 검토합니다.</li>
                                    <li>승인 완료된 권한은 즉시 사용 가능합니다.</li>
                                    <li>거부된 신청의 경우 거부 사유를 확인하고 필요시 재신청할 수 있습니다.</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PermissionRequestsPage;

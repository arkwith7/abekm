import {
    AlertCircle,
    CheckCircle,
    CheckSquare,
    Clock,
    Loader2,
    RefreshCw,
    Search,
    Shield,
    Square,
    ThumbsDown,
    ThumbsUp,
    User,
    XCircle
} from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { getContainerSubtreeIdsByName, getUserPermissions } from '../../services/managerService';
import {
    approvePermissionRequest,
    batchApprovePermissionRequests,
    batchRejectPermissionRequests,
    getPendingPermissionRequests,
    getPermissionRequestStatistics,
    rejectPermissionRequest
} from '../../services/permissionRequestService';
import type { UserPermission } from '../../types/manager.types';
import {
    PermissionRequest,
    PermissionRequestStatistics
} from '../../types/permissionRequest.types';

export const PermissionApprovalManagement: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'requests' | 'permissions'>('requests');
    const [requests, setRequests] = useState<PermissionRequest[]>([]);
    const [userPermissions, setUserPermissions] = useState<UserPermission[]>([]);
    const [statistics, setStatistics] = useState<PermissionRequestStatistics | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedContainerId, setSelectedContainerId] = useState('');
    const [allowedContainerIds, setAllowedContainerIds] = useState<string[]>([]);
    const [managedRootName] = useState<string>('MS서비스팀');
    const [selectedRequests, setSelectedRequests] = useState<Set<string>>(new Set());
    const [showRejectModal, setShowRejectModal] = useState(false);
    const [rejectingRequestId, setRejectingRequestId] = useState<string | null>(null);
    const [rejectionReason, setRejectionReason] = useState('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Determine manager scope once (default to 'MS서비스팀')
        const resolveScope = async () => {
            const { rootId, ids } = await getContainerSubtreeIdsByName(managedRootName);
            if (ids.length) setAllowedContainerIds(ids);
            if (rootId) setSelectedContainerId(rootId);
        };
        resolveScope();
    }, [managedRootName]);

    useEffect(() => {
        loadData();
    }, [activeTab]);

    const loadData = async () => {
        try {
            setIsLoading(true);
            setError(null);

            if (activeTab === 'requests') {
                const [requestsResponse, statsResponse] = await Promise.all([
                    getPendingPermissionRequests(),
                    getPermissionRequestStatistics()
                ]);
                setRequests(requestsResponse.requests);
                setStatistics(statsResponse.statistics);
            } else {
                const permissions = await getUserPermissions();
                setUserPermissions(permissions);
            }
        } catch (error) {
            console.error('Failed to load data:', error);
            setError('데이터를 불러오는데 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleApprove = async (requestId: string) => {
        if (!confirm('이 권한 요청을 승인하시겠습니까?')) {
            return;
        }

        try {
            await approvePermissionRequest(requestId);
            await loadData();
            setSelectedRequests(new Set());
        } catch (error: any) {
            console.error('Failed to approve request:', error);
            alert(error.response?.data?.detail || '승인에 실패했습니다.');
        }
    };

    const handleReject = async (requestId: string) => {
        setRejectingRequestId(requestId);
        setShowRejectModal(true);
    };

    const confirmReject = async () => {
        if (!rejectionReason.trim()) {
            alert('거부 사유를 입력해주세요.');
            return;
        }

        if (!rejectingRequestId) return;

        try {
            await rejectPermissionRequest(rejectingRequestId, {
                rejection_reason: rejectionReason.trim()
            });
            await loadData();
            setShowRejectModal(false);
            setRejectingRequestId(null);
            setRejectionReason('');
            setSelectedRequests(new Set());
        } catch (error: any) {
            console.error('Failed to reject request:', error);
            alert(error.response?.data?.detail || '거부에 실패했습니다.');
        }
    };

    const handleBatchApprove = async () => {
        if (selectedRequests.size === 0) {
            alert('승인할 요청을 선택해주세요.');
            return;
        }

        if (!confirm(`선택한 ${selectedRequests.size}개의 요청을 일괄 승인하시겠습니까?`)) {
            return;
        }

        try {
            await batchApprovePermissionRequests({
                request_ids: Array.from(selectedRequests)
            });
            await loadData();
            setSelectedRequests(new Set());
        } catch (error: any) {
            console.error('Failed to batch approve:', error);
            alert(error.response?.data?.detail || '일괄 승인에 실패했습니다.');
        }
    };

    const handleBatchReject = async () => {
        if (selectedRequests.size === 0) {
            alert('거부할 요청을 선택해주세요.');
            return;
        }

        setRejectingRequestId('batch');
        setShowRejectModal(true);
    };

    const confirmBatchReject = async () => {
        if (!rejectionReason.trim()) {
            alert('거부 사유를 입력해주세요.');
            return;
        }

        try {
            await batchRejectPermissionRequests({
                request_ids: Array.from(selectedRequests),
                rejection_reason: rejectionReason.trim()
            });
            await loadData();
            setShowRejectModal(false);
            setRejectingRequestId(null);
            setRejectionReason('');
            setSelectedRequests(new Set());
        } catch (error: any) {
            console.error('Failed to batch reject:', error);
            alert(error.response?.data?.detail || '일괄 거부에 실패했습니다.');
        }
    };

    const toggleSelectRequest = (requestId: string) => {
        const newSelected = new Set(selectedRequests);
        if (newSelected.has(requestId)) {
            newSelected.delete(requestId);
        } else {
            newSelected.add(requestId);
        }
        setSelectedRequests(newSelected);
    };

    const toggleSelectAll = () => {
        if (selectedRequests.size === filteredRequests.length) {
            setSelectedRequests(new Set());
        } else {
            setSelectedRequests(new Set(filteredRequests.map(r => r.request_id)));
        }
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

    const filteredRequests = requests.filter(request => {
        const matchesSearch =
            request.user_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            request.user_emp_no?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            request.container_name?.toLowerCase().includes(searchTerm.toLowerCase());

        const inAllowedScope =
            allowedContainerIds.length === 0 || allowedContainerIds.includes(request.container_id);

        const matchesContainer = !selectedContainerId || request.container_id === selectedContainerId;

        return matchesSearch && inAllowedScope && matchesContainer;
    });

    const containers = useMemo(() => {
        const fromRequests = Array.from(
            new Set(requests.map(r => JSON.stringify({ id: r.container_id, name: r.container_name })))
        ).map(str => JSON.parse(str));
        const fromPermissions = Array.from(
            new Set(
                userPermissions.map(p => JSON.stringify({ id: p.container_id, name: p.container_name }))
            )
        ).map(str => JSON.parse(str));
        const map = new Map<string, any>();
        [...fromRequests, ...fromPermissions].forEach((c: any) => map.set(c.id, c));
        const raw = Array.from(map.values());
        if (allowedContainerIds.length === 0) return raw;
        return raw.filter((c: any) => allowedContainerIds.includes(c.id));
    }, [requests, userPermissions, allowedContainerIds]);

    const filteredPermissions = useMemo(() => {
        if (allowedContainerIds.length === 0) return userPermissions;
        return userPermissions.filter((p) => allowedContainerIds.includes(p.container_id));
    }, [userPermissions, allowedContainerIds]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto mb-4" />
                    <p className="text-gray-600">데이터를 불러오는 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-6 px-4 sm:px-6 lg:px-8">
            <div className="max-w-7xl mx-auto">
                {/* 헤더 */}
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900">권한 승인 관리</h1>
                        <p className="mt-2 text-sm text-gray-600">
                            팀원들의 지식 컨테이너 접근 권한을 관리합니다.
                        </p>
                    </div>
                    <button
                        onClick={loadData}
                        className="flex items-center px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                        disabled={isLoading}
                    >
                        <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                        새로고침
                    </button>
                </div>

                {/* 탭 네비게이션 */}
                <div className="mb-6 border-b border-gray-200">
                    <nav className="-mb-px flex space-x-8">
                        <button
                            onClick={() => setActiveTab('requests')}
                            className={`${activeTab === 'requests'
                                ? 'border-blue-500 text-blue-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                        >
                            <Clock className="w-5 h-5 mr-2" />
                            권한 요청 목록
                            {requests.length > 0 && (
                                <span className="ml-2 bg-red-100 text-red-800 py-0.5 px-2 rounded-full text-xs font-medium">
                                    {requests.length}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={() => setActiveTab('permissions')}
                            className={`${activeTab === 'permissions'
                                ? 'border-blue-500 text-blue-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                        >
                            <Shield className="w-5 h-5 mr-2" />
                            사용자별 권한 현황
                        </button>
                    </nav>
                </div>

                {/* 통계 (권한 요청 탭에만 표시) */}
                {activeTab === 'requests' && statistics && (
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
                        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                            <div className="flex items-center">
                                <div className="flex-shrink-0 text-2xl">📋</div>
                                <div className="ml-3">
                                    <p className="text-sm font-medium text-gray-500">총 요청</p>
                                    <p className="text-lg font-semibold text-gray-900">{statistics.total_requests}</p>
                                </div>
                            </div>
                        </div>
                        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                            <div className="flex items-center">
                                <div className="flex-shrink-0 text-2xl">⏰</div>
                                <div className="ml-3">
                                    <p className="text-sm font-medium text-gray-500">대기중</p>
                                    <p className="text-lg font-semibold text-yellow-600">{statistics.pending_requests}</p>
                                </div>
                            </div>
                        </div>
                        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                            <div className="flex items-center">
                                <div className="flex-shrink-0 text-2xl">✅</div>
                                <div className="ml-3">
                                    <p className="text-sm font-medium text-gray-500">승인됨</p>
                                    <p className="text-lg font-semibold text-green-600">{statistics.approved_requests}</p>
                                </div>
                            </div>
                        </div>
                        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                            <div className="flex items-center">
                                <div className="flex-shrink-0 text-2xl">🤖</div>
                                <div className="ml-3">
                                    <p className="text-sm font-medium text-gray-500">자동승인</p>
                                    <p className="text-lg font-semibold text-blue-600">{statistics.auto_approved_requests}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* 권한 요청 탭 */}
                {activeTab === 'requests' && (
                    <>
                        {/* 필터 및 검색 */}
                        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
                            <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
                                <div className="flex-1">
                                    <div className="relative">
                                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                                        <input
                                            type="text"
                                            placeholder="이름 또는 사번으로 검색"
                                            value={searchTerm}
                                            onChange={(e) => setSearchTerm(e.target.value)}
                                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    </div>
                                </div>
                                <div className="sm:w-64">
                                    <select
                                        value={selectedContainerId}
                                        onChange={(e) => setSelectedContainerId(e.target.value)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="">모든 컨테이너</option>
                                        {containers.map((container) => (
                                            <option key={container.id} value={container.id}>
                                                {container.name || container.id}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* 일괄 처리 버튼 */}
                        {selectedRequests.size > 0 && (
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium text-blue-900">
                                        {selectedRequests.size}개 선택됨
                                    </span>
                                    <div className="flex space-x-3">
                                        <button
                                            onClick={handleBatchApprove}
                                            className="flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                                        >
                                            <ThumbsUp className="w-4 h-4 mr-2" />
                                            일괄 승인
                                        </button>
                                        <button
                                            onClick={handleBatchReject}
                                            className="flex items-center px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                                        >
                                            <ThumbsDown className="w-4 h-4 mr-2" />
                                            일괄 거부
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* 에러 메시지 */}
                        {error && (
                            <div className="flex items-center space-x-2 p-4 bg-red-50 border border-red-200 rounded-lg mb-6">
                                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                                <p className="text-sm text-red-800">{error}</p>
                            </div>
                        )}

                        {/* 요청 목록 */}
                        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
                            <div className="px-6 py-4 border-b border-gray-200">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-medium text-gray-900">권한 요청 목록</h3>
                                    <button
                                        onClick={toggleSelectAll}
                                        className="flex items-center text-sm text-blue-600 hover:text-blue-800"
                                    >
                                        {selectedRequests.size === filteredRequests.length ? (
                                            <>
                                                <CheckSquare className="w-4 h-4 mr-1" />
                                                전체 해제
                                            </>
                                        ) : (
                                            <>
                                                <Square className="w-4 h-4 mr-1" />
                                                전체 선택
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                선택
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                사용자
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                부서
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                컨테이너
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                권한
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                요청일
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                작업
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {filteredRequests.length === 0 ? (
                                            <tr>
                                                <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                                                    <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                                                    <p>대기 중인 권한 요청이 없습니다.</p>
                                                </td>
                                            </tr>
                                        ) : (
                                            filteredRequests.map((request) => (
                                                <tr key={request.request_id} className="hover:bg-gray-50">
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedRequests.has(request.request_id)}
                                                            onChange={() => toggleSelectRequest(request.request_id)}
                                                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                                        />
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="flex items-center">
                                                            <div className="flex-shrink-0 h-10 w-10">
                                                                <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                                                                    <User className="h-5 w-5 text-blue-600" />
                                                                </div>
                                                            </div>
                                                            <div className="ml-4">
                                                                <div className="text-sm font-medium text-gray-900">
                                                                    {request.user_name || request.user_emp_no}
                                                                </div>
                                                                <div className="text-sm text-gray-500">{request.user_emp_no}</div>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                        {request.user_department || '-'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="text-sm text-gray-900">
                                                            {request.container_name || request.container_id}
                                                        </div>
                                                        <div className="text-xs text-gray-500 mt-1 max-w-xs truncate">
                                                            {request.reason}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                                                            {request.requested_role_name || request.requested_role_id}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {formatDate(request.requested_at)}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                                        <div className="flex space-x-2">
                                                            <button
                                                                onClick={() => handleApprove(request.request_id)}
                                                                className="text-green-600 hover:text-green-900 p-1 hover:bg-green-50 rounded"
                                                                title="승인"
                                                            >
                                                                <CheckCircle className="w-5 h-5" />
                                                            </button>
                                                            <button
                                                                onClick={() => handleReject(request.request_id)}
                                                                className="text-red-600 hover:text-red-900 p-1 hover:bg-red-50 rounded"
                                                                title="거부"
                                                            >
                                                                <XCircle className="w-5 h-5" />
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* 거부 모달 */}
                        {showRejectModal && (
                            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                                <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        {rejectingRequestId === 'batch' ? '일괄 거부' : '권한 요청 거부'}
                                    </h3>
                                    <p className="text-sm text-gray-600 mb-4">
                                        거부 사유를 입력해주세요. 사용자에게 전달됩니다.
                                    </p>
                                    <textarea
                                        value={rejectionReason}
                                        onChange={(e) => setRejectionReason(e.target.value)}
                                        rows={4}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
                                        placeholder="예: 해당 컨테이너에 대한 접근 권한이 필요하지 않음"
                                    />
                                    <div className="flex space-x-3">
                                        <button
                                            onClick={() => {
                                                setShowRejectModal(false);
                                                setRejectingRequestId(null);
                                                setRejectionReason('');
                                            }}
                                            className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                                        >
                                            취소
                                        </button>
                                        <button
                                            onClick={rejectingRequestId === 'batch' ? confirmBatchReject : confirmReject}
                                            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                                        >
                                            거부
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* 사용자별 권한 현황 탭 */}
                {activeTab === 'permissions' && (
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                                <h3 className="text-lg font-medium text-gray-900">부여된 권한 목록</h3>
                                <div className="flex items-center space-x-2">
                                    <span className="text-xs text-gray-500 hidden sm:inline">관리 범위</span>
                                    <select
                                        value={selectedContainerId}
                                        onChange={(e) => setSelectedContainerId(e.target.value)}
                                        className="px-2 py-1 border border-gray-300 rounded-md text-sm"
                                    >
                                        {containers.map((c: any) => (
                                            <option key={c.id} value={c.id}>{c.name || c.id}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            사용자
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            부서
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            컨테이너
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            권한
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            부여일
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            부여자
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {filteredPermissions.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                                                <User className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                                                <p className="text-lg font-medium">부여된 권한이 없습니다</p>
                                            </td>
                                        </tr>
                                    ) : (
                                        filteredPermissions
                                            .filter((p) => !selectedContainerId || p.container_id === selectedContainerId)
                                            .map((permission) => (
                                                <tr key={permission.id} className="hover:bg-gray-50">
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="flex items-center">
                                                            <div>
                                                                <div className="text-sm font-medium text-gray-900">
                                                                    {permission.user_name}
                                                                </div>
                                                                <div className="text-sm text-gray-500">
                                                                    {permission.user_id}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="text-sm text-gray-900">{permission.department || '-'}</div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="text-sm font-medium text-gray-900">
                                                            {permission.container_name}
                                                        </div>
                                                        <div className="text-xs text-gray-500">
                                                            {permission.container_id}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${permission.permission === 'write'
                                                            ? 'bg-green-100 text-green-800'
                                                            : 'bg-blue-100 text-blue-800'
                                                            }`}>
                                                            {permission.permission === 'write' ? '쓰기' : '읽기'}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {permission.granted_at ? formatDate(permission.granted_at) : '-'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {permission.granted_by || '-'}
                                                    </td>
                                                </tr>
                                            ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PermissionApprovalManagement;

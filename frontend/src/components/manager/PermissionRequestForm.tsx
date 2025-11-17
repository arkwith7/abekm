import { AlertCircle, CheckCircle, Loader2, Send, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { getContainers } from '../../services/managerService';
import { createPermissionRequest } from '../../services/permissionRequestService';
import { Container } from '../../types/manager.types';

interface PermissionRequestFormProps {
    onSuccess?: () => void;
    onCancel?: () => void;
    preselectedContainerId?: string;
}

const PERMISSION_ROLES = [
    { id: 'VIEWER', name: '조회자', description: '문서 조회, 검색, 다운로드' },
    { id: 'EDITOR', name: '편집자', description: '조회 + 문서 업로드, 수정' },
    { id: 'MANAGER', name: '관리자', description: '편집 + 지식컨테이너 관리' },
    { id: 'ADMIN', name: '최고관리자', description: '모든 권한 + 권한 관리' }
];

export const PermissionRequestForm: React.FC<PermissionRequestFormProps> = ({
    onSuccess,
    onCancel,
    preselectedContainerId
}) => {
    const [containers, setContainers] = useState<Container[]>([]);
    const [selectedContainerId, setSelectedContainerId] = useState(preselectedContainerId || '');
    const [selectedRoleId, setSelectedRoleId] = useState('VIEWER');
    const [reason, setReason] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingContainers, setIsLoadingContainers] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        loadContainers();
    }, []);

    const loadContainers = async () => {
        try {
            setIsLoadingContainers(true);
            const data = await getContainers();
            setContainers(data);
        } catch (error) {
            console.error('Failed to load containers:', error);
            setError('컨테이너 목록을 불러오는데 실패했습니다.');
        } finally {
            setIsLoadingContainers(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (!selectedContainerId) {
            setError('컨테이너를 선택해주세요.');
            return;
        }

        if (!reason.trim()) {
            setError('요청 사유를 입력해주세요.');
            return;
        }

        if (reason.trim().length < 10) {
            setError('요청 사유는 최소 10자 이상 입력해주세요.');
            return;
        }

        try {
            setIsLoading(true);
            await createPermissionRequest({
                container_id: selectedContainerId,
                requested_permission_level: selectedRoleId,  // ✅ 올바른 필드명으로 수정
                request_reason: reason.trim()                // ✅ 올바른 필드명으로 수정
            });

            setSuccess(true);

            // 성공 메시지 표시 후 콜백 실행
            setTimeout(() => {
                if (onSuccess) {
                    onSuccess();
                }
            }, 1500);
        } catch (error: any) {
            console.error('Failed to create permission request:', error);

            // 에러 메시지 파싱
            if (error.response?.data?.detail) {
                setError(error.response.data.detail);
            } else if (error.response?.status === 409) {
                setError('이미 동일한 권한 요청이 존재합니다.');
            } else {
                setError('권한 요청 생성에 실패했습니다. 다시 시도해주세요.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    if (success) {
        return (
            <div className="bg-white rounded-lg shadow-lg p-8 max-w-md mx-auto">
                <div className="text-center">
                    <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
                        <CheckCircle className="h-8 w-8 text-green-600" />
                    </div>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">
                        권한 요청이 완료되었습니다
                    </h3>
                    <p className="text-sm text-gray-500">
                        관리자가 승인하면 알림을 받으실 수 있습니다.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-lg shadow-lg p-6 max-w-2xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900">권한 요청</h2>
                {onCancel && (
                    <button
                        onClick={onCancel}
                        className="text-gray-400 hover:text-gray-600"
                        disabled={isLoading}
                    >
                        <X className="w-5 h-5" />
                    </button>
                )}
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* 컨테이너 선택 */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        지식 컨테이너 <span className="text-red-500">*</span>
                    </label>
                    {isLoadingContainers ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                        </div>
                    ) : (
                        <select
                            value={selectedContainerId}
                            onChange={(e) => setSelectedContainerId(e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            disabled={isLoading || !!preselectedContainerId}
                            required
                        >
                            <option value="">컨테이너를 선택하세요</option>
                            {containers.map((container) => (
                                <option key={container.id} value={container.id}>
                                    {container.name}
                                </option>
                            ))}
                        </select>
                    )}
                </div>

                {/* 권한 레벨 선택 */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-3">
                        요청 권한 <span className="text-red-500">*</span>
                    </label>
                    <div className="space-y-3">
                        {PERMISSION_ROLES.map((role) => (
                            <label
                                key={role.id}
                                className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-all ${selectedRoleId === role.id
                                    ? 'border-blue-500 bg-blue-50'
                                    : 'border-gray-200 hover:border-gray-300'
                                    }`}
                            >
                                <input
                                    type="radio"
                                    name="role"
                                    value={role.id}
                                    checked={selectedRoleId === role.id}
                                    onChange={(e) => setSelectedRoleId(e.target.value)}
                                    className="mt-1 mr-3"
                                    disabled={isLoading}
                                />
                                <div className="flex-1">
                                    <div className="font-medium text-gray-900">{role.name}</div>
                                    <div className="text-sm text-gray-500 mt-1">{role.description}</div>
                                </div>
                            </label>
                        ))}
                    </div>
                </div>

                {/* 요청 사유 */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        요청 사유 <span className="text-red-500">*</span>
                    </label>
                    <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        rows={4}
                        className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="권한이 필요한 사유를 상세히 작성해주세요. (최소 10자)"
                        disabled={isLoading}
                        required
                    />
                    <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
                        <span>최소 10자 이상 입력해주세요</span>
                        <span>{reason.length} / 500</span>
                    </div>
                </div>

                {/* 에러 메시지 */}
                {error && (
                    <div className="flex items-start space-x-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-red-800">{error}</p>
                    </div>
                )}

                {/* 안내 메시지 */}
                <div className="flex items-start space-x-2 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-blue-800">
                        <p className="font-medium mb-1">권한 요청 안내</p>
                        <ul className="list-disc list-inside space-y-1 text-xs">
                            <li>요청 사유는 관리자가 검토합니다</li>
                            <li>일부 권한은 자동으로 승인될 수 있습니다</li>
                            <li>승인된 권한은 30일간 유효합니다</li>
                        </ul>
                    </div>
                </div>

                {/* 버튼 */}
                <div className="flex space-x-3">
                    {onCancel && (
                        <button
                            type="button"
                            onClick={onCancel}
                            className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
                            disabled={isLoading}
                        >
                            취소
                        </button>
                    )}
                    <button
                        type="submit"
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center"
                        disabled={isLoading || isLoadingContainers}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                요청 중...
                            </>
                        ) : (
                            <>
                                <Send className="w-4 h-4 mr-2" />
                                권한 요청
                            </>
                        )}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default PermissionRequestForm;

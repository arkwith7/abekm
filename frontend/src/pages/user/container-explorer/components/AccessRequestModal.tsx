import { X } from 'lucide-react';
import React, { useState } from 'react';

interface AccessRequestModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: { reason: string; roleId: string; expiresAt?: string }) => Promise<void>;
    containerName: string;
}

const AccessRequestModal: React.FC<AccessRequestModalProps> = ({
    isOpen,
    onClose,
    onSubmit,
    containerName
}) => {
    const [reason, setReason] = useState('업무 수행을 위한 열람 권한 요청');
    const [roleId, setRoleId] = useState('VIEWER');
    const [expiresAt, setExpiresAt] = useState('');
    const [submitting, setSubmitting] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!reason.trim()) {
            alert('요청 사유를 입력해주세요.');
            return;
        }

        setSubmitting(true);
        try {
            await onSubmit({
                reason,
                roleId,
                expiresAt: expiresAt || undefined
            });
            onClose();
            // 리셋
            setReason('업무 수행을 위한 열람 권한 요청');
            setRoleId('VIEWER');
            setExpiresAt('');
        } catch (error) {
            console.error('권한 요청 실패:', error);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
                {/* 헤더 */}
                <div className="flex items-center justify-between p-6 border-b">
                    <h3 className="text-lg font-semibold text-gray-900">권한 요청</h3>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600"
                        disabled={submitting}
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* 본문 */}
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    {/* 컨테이너 정보 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            컨테이너
                        </label>
                        <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-700">
                            {containerName}
                        </div>
                    </div>

                    {/* 요청 권한 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            요청 권한 <span className="text-red-500">*</span>
                        </label>
                        <select
                            value={roleId}
                            onChange={(e) => setRoleId(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            required
                        >
                            <option value="VIEWER">열람 (VIEWER)</option>
                            <option value="EDITOR">편집 (EDITOR)</option>
                            <option value="MANAGER">관리 (MANAGER)</option>
                        </select>
                        <p className="mt-1 text-xs text-gray-500">
                            열람: 문서 조회 / 편집: 문서 추가 및 수정 / 관리: 권한 관리 포함
                        </p>
                    </div>

                    {/* 요청 사유 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            요청 사유 <span className="text-red-500">*</span>
                        </label>
                        <textarea
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            rows={4}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="권한이 필요한 구체적인 사유를 입력해주세요..."
                            required
                        />
                    </div>

                    {/* 유효기간 (선택) */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            유효기간 (선택)
                        </label>
                        <input
                            type="date"
                            value={expiresAt}
                            onChange={(e) => setExpiresAt(e.target.value)}
                            min={new Date().toISOString().split('T')[0]}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                            지정하지 않으면 무기한으로 요청됩니다
                        </p>
                    </div>

                    {/* 버튼 */}
                    <div className="flex justify-end space-x-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                            disabled={submitting}
                        >
                            취소
                        </button>
                        <button
                            type="submit"
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                            disabled={submitting}
                        >
                            {submitting ? '요청 중...' : '요청 제출'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default AccessRequestModal;

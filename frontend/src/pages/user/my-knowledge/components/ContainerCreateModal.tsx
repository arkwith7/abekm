import { AlertCircle, FolderPlus, X } from 'lucide-react';
import React, { useState } from 'react';

interface ContainerCreateModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: { container_name: string; description?: string }) => Promise<void>;
    parentContainerName?: string;  // 🆕 부모 컨테이너 이름 (선택사항)
}

const ContainerCreateModal: React.FC<ContainerCreateModalProps> = ({
    isOpen,
    onClose,
    onSubmit,
    parentContainerName  // 🆕 부모 컨테이너 이름
}) => {
    const [containerName, setContainerName] = useState('');
    const [description, setDescription] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!containerName.trim()) {
            setError('컨테이너 이름을 입력해주세요.');
            return;
        }

        setIsSubmitting(true);
        setError('');

        try {
            await onSubmit({
                container_name: containerName.trim(),
                description: description.trim() || undefined
            });

            // 성공 시 폼 초기화 및 닫기
            setContainerName('');
            setDescription('');
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || '컨테이너 생성에 실패했습니다.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            setContainerName('');
            setDescription('');
            setError('');
            onClose();
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
                {/* 헤더 */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-2">
                        <FolderPlus className="w-6 h-6 text-blue-600" />
                        <h2 className="text-xl font-bold text-gray-900">새 컨테이너 추가</h2>
                    </div>
                    <button
                        onClick={handleClose}
                        disabled={isSubmitting}
                        className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                {/* 에러 메시지 */}
                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start space-x-2">
                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-red-800">{error}</p>
                    </div>
                )}

                {/* 폼 */}
                <form onSubmit={handleSubmit}>
                    {/* 컨테이너 이름 */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            컨테이너 이름 <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={containerName}
                            onChange={(e) => setContainerName(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="예: 내 프로젝트 문서"
                            disabled={isSubmitting}
                            maxLength={100}
                        />
                        <p className="mt-1 text-xs text-gray-500">
                            최대 100자까지 입력 가능합니다.
                        </p>
                    </div>

                    {/* 설명 */}
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            설명 (선택사항)
                        </label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                            rows={3}
                            placeholder="컨테이너에 대한 간단한 설명을 입력하세요."
                            disabled={isSubmitting}
                            maxLength={500}
                        />
                        <p className="mt-1 text-xs text-gray-500">
                            최대 500자까지 입력 가능합니다.
                        </p>
                    </div>

                    {/* 안내 메시지 */}
                    <div className="mb-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        {parentContainerName ? (
                            <p className="text-sm text-blue-800">
                                📁 <strong>"{parentContainerName}"</strong>의 하위 컨테이너로 생성됩니다.
                                <br />
                                💡 생성된 컨테이너는 <strong>개인 컨테이너</strong>로 설정되며, 기본적으로 본인만 접근할 수 있습니다.
                            </p>
                        ) : (
                            <p className="text-sm text-blue-800">
                                💡 생성된 컨테이너는 <strong>개인 컨테이너</strong>로 설정되며,
                                기본적으로 본인만 접근할 수 있습니다.
                            </p>
                        )}
                    </div>

                    {/* 버튼 */}
                    <div className="flex space-x-3">
                        <button
                            type="button"
                            onClick={handleClose}
                            disabled={isSubmitting}
                            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            취소
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || !containerName.trim()}
                            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                        >
                            {isSubmitting ? (
                                <>
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                    <span>생성 중...</span>
                                </>
                            ) : (
                                <>
                                    <FolderPlus className="w-4 h-4" />
                                    <span>컨테이너 추가</span>
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ContainerCreateModal;

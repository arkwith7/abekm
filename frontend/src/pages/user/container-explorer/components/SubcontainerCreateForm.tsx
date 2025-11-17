import { X } from 'lucide-react';
import React, { useState } from 'react';

interface SubcontainerCreateFormProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: { name: string; description: string; inheritPermissions: boolean }) => Promise<void>;
    parentContainerName: string;
}

const SubcontainerCreateForm: React.FC<SubcontainerCreateFormProps> = ({
    isOpen,
    onClose,
    onSubmit,
    parentContainerName
}) => {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [inheritPermissions, setInheritPermissions] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim()) {
            alert('컨테이너 이름을 입력해주세요.');
            return;
        }

        setSubmitting(true);
        try {
            await onSubmit({
                name: name.trim(),
                description: description.trim(),
                inheritPermissions
            });
            onClose();
            // 리셋
            setName('');
            setDescription('');
            setInheritPermissions(true);
        } catch (error) {
            console.error('하위 컨테이너 생성 실패:', error);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
                {/* 헤더 */}
                <div className="flex items-center justify-between p-6 border-b">
                    <h3 className="text-lg font-semibold text-gray-900">하위 컨테이너 생성</h3>
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
                    {/* 부모 컨테이너 정보 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            부모 컨테이너
                        </label>
                        <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-700">
                            {parentContainerName}
                        </div>
                    </div>

                    {/* 컨테이너 이름 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            컨테이너 이름 <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="예: 프로젝트 문서"
                            required
                            maxLength={100}
                        />
                    </div>

                    {/* 설명 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            설명
                        </label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            rows={3}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="컨테이너에 대한 설명을 입력해주세요..."
                            maxLength={500}
                        />
                        <p className="mt-1 text-xs text-gray-500">
                            {description.length}/500
                        </p>
                    </div>

                    {/* 권한 상속 */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <label className="flex items-start cursor-pointer">
                            <input
                                type="checkbox"
                                checked={inheritPermissions}
                                onChange={(e) => setInheritPermissions(e.target.checked)}
                                className="mt-1 mr-3 w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            />
                            <div>
                                <div className="text-sm font-medium text-gray-900">
                                    부모 컨테이너 권한 상속 (권장)
                                </div>
                                <div className="text-xs text-gray-600 mt-1">
                                    부모 컨테이너의 접근 권한 설정을 그대로 상속받습니다.
                                    이 옵션을 해제하면 별도의 권한 설정이 필요합니다.
                                </div>
                            </div>
                        </label>
                    </div>

                    {/* 안내 메시지 */}
                    {!inheritPermissions && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                            <p className="text-xs text-yellow-800">
                                ⚠️ 권한 상속을 해제하면 컨테이너 생성 후 별도로 권한 설정이 필요합니다.
                            </p>
                        </div>
                    )}

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
                            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
                            disabled={submitting}
                        >
                            {submitting ? '생성 중...' : '생성'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default SubcontainerCreateForm;

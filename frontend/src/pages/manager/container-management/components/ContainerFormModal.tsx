import React from 'react';
import { Container } from '../../../../types/manager.types';

interface ContainerFormModalProps {
    isOpen: boolean;
    mode: 'create' | 'edit';
    container: {
        name: string;
        description: string;
        parent_id: string;
    };
    containers: Container[];
    onClose: () => void;
    onChange: (updates: Partial<{ name: string; description: string; parent_id: string }>) => void;
    onSubmit: () => void;
}

export const ContainerFormModal: React.FC<ContainerFormModalProps> = ({
    isOpen,
    mode,
    container,
    containers,
    onClose,
    onChange,
    onSubmit
}) => {
    if (!isOpen) return null;

    const title = mode === 'create' ? '새 컨테이너 생성' : '컨테이너 수정';
    const submitLabel = mode === 'create' ? '생성' : '수정';

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
                <h3 className="text-xl font-semibold text-gray-900 mb-4">{title}</h3>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            컨테이너 이름 <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={container.name}
                            onChange={(e) => onChange({ name: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            placeholder="예: 마케팅 자료"
                            autoFocus
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">설명</label>
                        <textarea
                            value={container.description}
                            onChange={(e) => onChange({ description: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                            rows={3}
                            placeholder="컨테이너에 대한 간단한 설명을 입력하세요"
                        />
                    </div>
                    {mode === 'create' && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                상위 컨테이너
                                {container.parent_id && (
                                    <span className="ml-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                                        하위 컨테이너로 생성됩니다
                                    </span>
                                )}
                            </label>
                            <select
                                value={container.parent_id}
                                onChange={(e) => onChange({ parent_id: e.target.value })}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            >
                                <option value="">최상위 컨테이너로 생성</option>
                                {containers.map((c) => (
                                    <option key={c.id} value={c.id}>
                                        📁 {c.name}
                                    </option>
                                ))}
                            </select>
                            {container.parent_id && (
                                <p className="mt-2 text-xs text-gray-500">
                                    💡 '{containers.find(c => c.id === container.parent_id)?.name}'의 하위 컨테이너로 생성됩니다.
                                </p>
                            )}
                        </div>
                    )}
                </div>
                <div className="flex space-x-3 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        취소
                    </button>
                    <button
                        onClick={onSubmit}
                        disabled={!container.name.trim()}
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {submitLabel}
                    </button>
                </div>
            </div>
        </div>
    );
};

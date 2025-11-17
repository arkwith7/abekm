import { Edit2, Trash2 } from 'lucide-react';
import React from 'react';
import { Container } from '../../../../types/manager.types';

interface ContainerSidebarProps {
    containers: Container[];
    onEdit: (container: Container) => void;
    onDelete: (containerId: string, containerName: string) => void;
}

export const ContainerSidebar: React.FC<ContainerSidebarProps> = ({
    containers,
    onEdit,
    onDelete
}) => {
    return (
        <div className="space-y-6">
            {/* 빠른 통계 */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
                <div className="px-6 py-4 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">관리 중인 컨테이너</h3>
                </div>
                <div className="p-4">
                    <div className="space-y-2">
                        {containers.slice(0, 5).map((container) => (
                            <div
                                key={container.id}
                                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="font-medium text-sm text-gray-900 truncate">{container.name}</div>
                                    <div className="text-xs text-gray-500 mt-1">
                                        📄 {container.document_count}개 문서
                                    </div>
                                </div>
                                <div className="flex space-x-1 ml-2">
                                    <button
                                        onClick={() => onEdit(container)}
                                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                                        title="수정"
                                    >
                                        <Edit2 className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                        onClick={() => onDelete(container.id, container.name)}
                                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                        title="삭제"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        ))}
                        {containers.length === 0 && (
                            <p className="text-sm text-gray-500 text-center py-4">컨테이너가 없습니다</p>
                        )}
                    </div>
                </div>
            </div>

            {/* 도움말 */}
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
                <h4 className="font-semibold text-blue-900 mb-3 flex items-center">
                    <span className="text-xl mr-2">💡</span>
                    지식컨테이너 관리 팁
                </h4>
                <ul className="text-sm text-blue-800 space-y-2">
                    <li className="flex items-start">
                        <span className="mr-2">•</span>
                        <span>주제별로 컨테이너를 구성하세요</span>
                    </li>
                    <li className="flex items-start">
                        <span className="mr-2">•</span>
                        <span>하위 컨테이너로 세분화 가능합니다</span>
                    </li>
                    <li className="flex items-start">
                        <span className="mr-2">•</span>
                        <span>사용자 권한을 세밀하게 설정하세요</span>
                    </li>
                    <li className="flex items-start">
                        <span className="mr-2">•</span>
                        <span>정기적으로 사용 현황을 점검하세요</span>
                    </li>
                </ul>
            </div>
        </div>
    );
};

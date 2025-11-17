import { FileText, FolderTree, Settings, Users } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';

export const QuickActions: React.FC = () => {
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">빠른 작업</h3>
            </div>
            <div className="p-6">
                <div className="grid grid-cols-2 gap-4">
                    <Link
                        to="/manager/container-management"
                        className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        <FolderTree className="w-8 h-8 text-blue-500" />
                        <div className="ml-3">
                            <h4 className="font-medium text-gray-900">컨테이너 관리</h4>
                            <p className="text-sm text-gray-500">구조 및 설정</p>
                        </div>
                    </Link>
                    <Link
                        to="/manager/user-access-management"
                        className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        <Users className="w-8 h-8 text-green-500" />
                        <div className="ml-3">
                            <h4 className="font-medium text-gray-900">사용자 권한 관리</h4>
                            <p className="text-sm text-gray-500">권한 승인 및 관리</p>
                        </div>
                    </Link>
                    <Link
                        to="/manager/document-access-management"
                        className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        <FileText className="w-8 h-8 text-purple-500" />
                        <div className="ml-3">
                            <h4 className="font-medium text-gray-900">문서 접근 관리</h4>
                            <p className="text-sm text-gray-500">문서 권한 설정</p>
                        </div>
                    </Link>
                    <Link
                        to="/manager/settings"
                        className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        <Settings className="w-8 h-8 text-gray-500" />
                        <div className="ml-3">
                            <h4 className="font-medium text-gray-900">시스템 설정</h4>
                            <p className="text-sm text-gray-500">전역 설정 관리</p>
                        </div>
                    </Link>
                </div>
            </div>
        </div>
    );
};

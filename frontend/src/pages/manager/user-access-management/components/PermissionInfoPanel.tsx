import React from 'react';

export const PermissionInfoPanel: React.FC = () => {
    return (
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-medium text-blue-900 mb-2">🔐 권한 설명</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm text-blue-800">
                <div>
                    <span className="font-medium">읽기:</span> 문서 조회, 검색, 다운로드
                </div>
                <div>
                    <span className="font-medium">읽기/쓰기:</span> 읽기 + 문서 업로드, 수정
                </div>
                <div>
                    <span className="font-medium">관리자:</span> 모든 권한 + 지식컨테이너 관리
                </div>
            </div>
        </div>
    );
};

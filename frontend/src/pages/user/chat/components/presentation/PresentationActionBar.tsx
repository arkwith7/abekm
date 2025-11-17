import React from 'react';

interface Props {
    sourceMessageId: string;
    sessionId: string;
    onBuildOneClick: (sourceMessageId: string, presentationType?: string) => void;
    onOpenOutline: (sourceMessageId: string, presentationType?: string) => void;
}

const PresentationActionBar: React.FC<Props> = ({ sourceMessageId, sessionId, onBuildOneClick, onOpenOutline }) => {
    return (
        <div className="flex items-center gap-2">
            <button
                className="px-2 py-1 text-xs rounded-md bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100"
                onClick={() => onBuildOneClick(sourceMessageId, "general")}
                title="일반 PPT로 바로 생성"
            >
                📊 PPT로 만들기
            </button>
            <button
                className="px-2 py-1 text-xs rounded-md bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100"
                onClick={() => onOpenOutline(sourceMessageId, "general")}
                title="PPT 생성 설정 및 템플릿 선택"
            >
                📝 PPT 생성 설정
            </button>
        </div>
    );
};

export default PresentationActionBar;

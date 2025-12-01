import React from 'react';

interface Props {
    sourceMessageId: string;
    sessionId: string;
    onOpenOutline: (sourceMessageId: string, presentationType?: string) => void;
    // 🆕 하이브리드 모드: PPT가 이미 생성된 상태
    isPPTGenerated?: boolean;
}

const PresentationActionBar: React.FC<Props> = ({
    sourceMessageId,
    sessionId,
    onOpenOutline,
    isPPTGenerated = false
}) => {
    return (
        <div className="flex items-center gap-2">
            {/* 하이브리드 모드: PPT 이미 생성됨 → "구조 확인 및 재생성" 버튼만 표시 */}
            <button
                className="px-3 py-1.5 text-xs rounded-md bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors"
                onClick={() => onOpenOutline(sourceMessageId, "general")}
                title="생성된 PPT의 구조를 확인하고 템플릿을 변경하여 재생성할 수 있습니다"
            >
                📝 {isPPTGenerated ? '구조 확인 및 재생성' : 'PPT 생성 설정'}
            </button>
        </div>
    );
};

export default PresentationActionBar;

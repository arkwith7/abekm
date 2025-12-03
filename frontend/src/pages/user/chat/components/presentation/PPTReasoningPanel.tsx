import { Brain, Check, ChevronDown, ChevronRight, FileText, Loader2, XCircle } from 'lucide-react';
import React, { useEffect, useState } from 'react';

export interface PPTProgressStep {
    message: string;
    status: 'in_progress' | 'completed' | 'error';
    timestamp?: string;
}

export interface PPTReasoningData {
    steps: PPTProgressStep[];
    isComplete: boolean;
    hasError: boolean;
    resultFileName?: string;
    resultFileUrl?: string;
}

interface PPTReasoningPanelProps {
    data: PPTReasoningData;
    isLoading?: boolean;
    mode?: 'quick' | 'template';  // PPT 생성 모드
}

/**
 * PPT 생성 과정 표시 컴포넌트 (ReasoningPanel 스타일)
 * - 생성 중: 자동으로 펼쳐짐
 * - 완료 시: 자동으로 접힘
 */
const PPTReasoningPanel: React.FC<PPTReasoningPanelProps> = ({
    data,
    isLoading = false,
    mode = 'quick'
}) => {
    // 로딩 중에는 자동으로 펼치고, 완료되면 자동으로 닫기
    const [isExpanded, setIsExpanded] = useState(isLoading);

    // 로딩 상태 변경 시 자동 토글
    useEffect(() => {
        if (isLoading) {
            setIsExpanded(true);  // 생성 중에는 펼치기
        } else if (data.isComplete || data.hasError) {
            // 완료 또는 에러 시 자동으로 닫기 (약간의 딜레이 후)
            const timer = setTimeout(() => {
                setIsExpanded(false);
            }, 1500);
            return () => clearTimeout(timer);
        }
    }, [isLoading, data.isComplete, data.hasError]);

    const modeLabel = mode === 'template' ? 'Template PPT' : 'Quick PPT';
    const modeIcon = mode === 'template' ? '🎨' : '📊';
    const headerBgColor = mode === 'template' ? 'bg-purple-50 hover:bg-purple-100' : 'bg-blue-50 hover:bg-blue-100';
    const headerIconColor = mode === 'template' ? 'text-purple-600' : 'text-blue-600';

    return (
        <div className="my-4 bg-white rounded-lg border border-gray-100 shadow-sm overflow-hidden">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={`w-full flex items-center justify-between p-4 ${headerBgColor} transition-colors`}
            >
                <div className="flex items-center gap-2 text-gray-800 font-bold">
                    <Brain className={`w-5 h-5 ${headerIconColor}`} />
                    <span>{modeIcon} {modeLabel} 생성</span>
                    {data.isComplete && !data.hasError && (
                        <span className="ml-2 text-xs text-green-600 font-normal">✓ 완료</span>
                    )}
                    {data.hasError && (
                        <span className="ml-2 text-xs text-red-600 font-normal">❌ 오류</span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {isLoading && (
                        <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                    )}
                    {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-gray-500" />
                    ) : (
                        <ChevronRight className="w-5 h-5 text-gray-500" />
                    )}
                </div>
            </button>

            {isExpanded && (
                <div className="p-4 border-t border-gray-100">
                    <ul className="space-y-2">
                        {data.steps.map((step, idx) => {
                            const isLast = idx === data.steps.length - 1;
                            const isActive = isLast && isLoading && step.status === 'in_progress';
                            const isError = step.status === 'error';

                            return (
                                <li
                                    key={idx}
                                    className={`flex items-start gap-3 text-sm animate-fadeIn ${isError ? 'text-red-600' : 'text-gray-600'
                                        }`}
                                >
                                    <div className="mt-0.5 flex-shrink-0">
                                        {isActive ? (
                                            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                                        ) : isError ? (
                                            <XCircle className="w-4 h-4 text-red-500" />
                                        ) : (
                                            <Check className="w-4 h-4 text-green-500" />
                                        )}
                                    </div>
                                    <span className={`${isActive ? 'text-blue-600 font-medium' : ''}`}>
                                        {step.message}
                                    </span>
                                </li>
                            );
                        })}
                    </ul>

                    {/* 결과 파일 링크 (완료 시) */}
                    {data.isComplete && data.resultFileUrl && data.resultFileName && (
                        <div className="mt-4 pt-3 border-t border-gray-100">
                            <a
                                href={data.resultFileUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                            >
                                <FileText className="w-4 h-4" />
                                <span>{data.resultFileName}</span>
                            </a>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default PPTReasoningPanel;

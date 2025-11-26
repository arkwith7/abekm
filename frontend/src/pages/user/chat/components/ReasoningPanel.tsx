import { Brain, Check, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import React, { useState } from 'react';

export interface ReasoningStep {
    stage: string;
    status: 'started' | 'completed' | 'error';
    tool?: string;
    message: string;
    result?: any;
    duration_ms?: number;
    timestamp?: string;
}

export interface SearchProgress {
    tool: string;
    chunks_found: number;
    total_chunks: number;
    avg_similarity?: number;
}

export interface ReasoningData {
    steps: ReasoningStep[];
    searchProgress: SearchProgress[];
    totalDuration?: number;
    intent?: string;
    keywords?: string[];
    strategy?: string[];
    searchStats?: Record<string, any>;
}

interface ReasoningPanelProps {
    reasoning: ReasoningData;
    isLoading?: boolean;
}

const ReasoningPanel: React.FC<ReasoningPanelProps> = ({ reasoning, isLoading = false }) => {
    // 🆕 로딩 중에는 자동으로 펼치고, 완료되면 자동으로 닫기
    const [isExpanded, setIsExpanded] = useState(isLoading);

    // 🆕 로딩 상태 변경 시 자동 토글
    React.useEffect(() => {
        if (isLoading) {
            setIsExpanded(true);  // 생성 중에는 펼치기
        } else if (reasoning.steps.length > 0) {
            // 답변 완료 시 자동으로 닫기 (약간의 딜레이 후)
            const timer = setTimeout(() => {
                setIsExpanded(false);
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [isLoading, reasoning.steps.length]);

    // 사용자 친화적인 메시지 매핑
    const getDisplayMessage = (step: ReasoningStep, index: number, allSteps: ReasoningStep[]) => {
        const { stage, status, tool } = step;

        if (stage === 'query_analysis') {
            return status === 'started'
                ? "질의어를 기반으로 Task를 만들고 있습니다..."
                : "질의어를 재구성했습니다.";
        }

        if (stage === 'strategy_selection') {
            return "질의어를 기반으로 검색 전략을 수립했습니다.";
        }

        if (stage === 'search') {
            // 검색 단계는 여러 번 발생할 수 있으므로 첫 번째만 표시하거나 도구별로 표시
            // 여기서는 단순화를 위해 첫 번째 검색 시작만 "검색합니다"로 표시하고 나머지는 생략하거나 상세 표시
            // 하지만 리스트 형태 유지를 위해 도구 실행도 표시하되 메시지 순화
            if (status === 'started') {
                // 이미 "질의어를 기반으로 검색합니다"가 있는지 확인 (중복 방지)
                const hasGenericSearchMsg = allSteps.slice(0, index).some(s => s.stage === 'search' && s.status === 'started');
                if (!hasGenericSearchMsg) return "질의어를 기반으로 검색합니다.";
                return null; // 중복 검색 메시지 숨김
            }
            return null;
        }

        if (stage === 'postprocess') {
            if (status === 'started') {
                // 검색 완료 후 후처리 시작 시점
                const hasSearchCompletedMsg = allSteps.slice(0, index).some(s => s.stage === 'postprocess' && s.status === 'started');
                if (!hasSearchCompletedMsg) return "검색이 완료되었습니다.";
                return null;
            }
            if (status === 'completed') {
                // 후처리 완료 시점
                if (tool === 'deduplicate') return null; // 개별 도구 완료는 숨김
                if (tool === 'rerank') return "입력을 확인중입니다...";
            }
            return null;
        }

        if (stage === 'context_building') {
            return status === 'started'
                ? "컨텍스트를 구성하고 있습니다..."
                : "에이전트가 생성중입니다...";
        }

        if (stage === 'answer_generation') {
            return "에이전트가 답변을 준비중입니다...";
        }

        return step.message; // 기본 메시지 (매핑되지 않은 경우)
    };

    // 표시할 스텝 필터링 및 매핑
    const displaySteps = reasoning.steps
        .map((step, index) => ({
            original: step,
            message: getDisplayMessage(step, index, reasoning.steps)
        }))
        .filter(item => item.message !== null); // null 메시지 제외

    return (
        <div className="my-4 bg-white rounded-lg border border-gray-100 shadow-sm overflow-hidden">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
            >
                <div className="flex items-center gap-2 text-gray-800 font-bold">
                    <Brain className="w-5 h-5 text-purple-600" />
                    <span>AI 사고 과정</span>
                </div>
                {isExpanded ? (
                    <ChevronDown className="w-5 h-5 text-gray-500" />
                ) : (
                    <ChevronRight className="w-5 h-5 text-gray-500" />
                )}
            </button>

            {isExpanded && (
                <div className="p-4 border-t border-gray-100">
                    <ul className="space-y-3">
                        {displaySteps.map((item, idx) => {
                            // 마지막 항목이고 로딩 중이면 스피너, 아니면 체크
                            // 또는 status가 started이면 스피너?
                            // 보통 started 상태로 남아있다가 다음 단계로 넘어가면 completed가 됨.
                            // 하지만 여기서는 로그처럼 쌓이는 구조.
                            // started 메시지가 나오고, 나중에 completed 메시지가 나옴.
                            // 따라서 모든 항목은 '완료된 로그'로 취급하되, 
                            // 가장 마지막 항목이면서 status가 'started'인 경우에만 진행 중 표시를 하는 것이 자연스러움.

                            const isLast = idx === displaySteps.length - 1;
                            const isActive = isLast && isLoading;
                            // 주의: isLoading은 전체 채팅 로딩 상태. 
                            // 개별 스텝의 status가 'started'라고 해서 무조건 로딩은 아님 (이미 지나간 started일 수 있음)
                            // 하지만 displaySteps는 순차적으로 쌓이므로, 마지막 항목이 started라면 현재 진행 중일 가능성이 높음.

                            return (
                                <li key={idx} className="flex items-start gap-3 text-sm text-gray-600 animate-fadeIn">
                                    <div className="mt-0.5 flex-shrink-0">
                                        {isActive ? (
                                            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                                        ) : (
                                            <Check className="w-4 h-4 text-green-500" />
                                        )}
                                    </div>
                                    <span className={`${isActive ? 'text-blue-600 font-medium' : ''}`}>
                                        {item.message}
                                    </span>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default ReasoningPanel;



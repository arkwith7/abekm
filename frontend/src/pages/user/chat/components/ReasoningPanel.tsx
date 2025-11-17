/**
 * ReasoningPanel - AI 사고 과정 표시 컴포넌트
 * 
 * 접이식 패널로 AI의 단계별 사고 과정을 시각화:
 * - 질의 분석 (의도, 키워드)
 * - 검색 전략 선택
 * - 하이브리드 검색 (벡터 + 키워드)
 * - 후처리 (중복 제거, 리랭킹)
 * - 컨텍스트 구성
 * - 답변 생성
 */

import { AlertCircle, CheckCircle, ChevronDown, ChevronRight, Clock, Loader } from 'lucide-react';
import React, { useState } from 'react';

export interface ReasoningStep {
    stage: string;  // 'query_analysis', 'search', 'postprocess', 'context_building', 'answer_generation'
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
    const [isExpanded, setIsExpanded] = useState(false);

    // 단계별 아이콘 매핑
    const getStageIcon = (stage: string, status: string) => {
        if (status === 'started') return <Loader className="w-4 h-4 animate-spin text-blue-500" />;
        if (status === 'error') return <AlertCircle className="w-4 h-4 text-red-500" />;
        if (status === 'completed') return <CheckCircle className="w-4 h-4 text-green-500" />;
        return <Clock className="w-4 h-4 text-gray-400" />;
    };

    // 단계 이름 한글화
    const getStageName = (stage: string) => {
        const stageNames: Record<string, string> = {
            query_analysis: '🔍 질의 분석',
            strategy_selection: '🎯 전략 선택',
            search: '📚 검색 실행',
            postprocess: '⚡ 후처리',
            context_building: '🏗️ 컨텍스트 구성',
            answer_generation: '✍️ 답변 생성'
        };
        return stageNames[stage] || stage;
    };

    // 진행률 계산
    const calculateProgress = () => {
        if (!reasoning.steps.length) return 0;
        const completedSteps = reasoning.steps.filter(s => s.status === 'completed').length;
        return Math.round((completedSteps / reasoning.steps.length) * 100);
    };

    const progress = calculateProgress();

    return (
        <div className="my-4 border border-gray-200 rounded-lg bg-gray-50 overflow-hidden">
            {/* 헤더 (항상 표시) */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-100 transition-colors"
            >
                <div className="flex items-center gap-3">
                    {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-gray-600" />
                    ) : (
                        <ChevronRight className="w-5 h-5 text-gray-600" />
                    )}
                    <span className="font-medium text-gray-700">💭 AI 사고 과정</span>

                    {/* 진행률 표시 */}
                    {isLoading && (
                        <span className="text-xs text-blue-600 flex items-center gap-1">
                            <Loader className="w-3 h-3 animate-spin" />
                            진행 중... {progress}%
                        </span>
                    )}

                    {!isLoading && reasoning.steps.length > 0 && (
                        <span className="text-xs text-green-600 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" />
                            완료
                        </span>
                    )}
                </div>

                {/* 요약 정보 (접혔을 때) */}
                {!isExpanded && reasoning.steps.length > 0 && (
                    <div className="flex items-center gap-4 text-xs text-gray-600">
                        {reasoning.intent && (
                            <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded">
                                {reasoning.intent}
                            </span>
                        )}
                        {reasoning.searchStats && (
                            <span>
                                {Object.keys(reasoning.searchStats).length}가지 검색 방식
                            </span>
                        )}
                    </div>
                )}
            </button>

            {/* 펼쳐진 내용 */}
            {isExpanded && (
                <div className="px-4 pb-4 space-y-3">
                    {/* 진행률 바 */}
                    {isLoading && (
                        <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    )}

                    {/* 단계별 상세 정보 */}
                    <div className="space-y-2">
                        {reasoning.steps.map((step, idx) => (
                            <div
                                key={idx}
                                className={`p-3 rounded-lg border ${step.status === 'completed'
                                        ? 'bg-white border-green-200'
                                        : step.status === 'error'
                                            ? 'bg-red-50 border-red-200'
                                            : 'bg-blue-50 border-blue-200'
                                    }`}
                            >
                                <div className="flex items-start gap-3">
                                    {getStageIcon(step.stage, step.status)}
                                    <div className="flex-1">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="font-medium text-sm text-gray-800">
                                                {getStageName(step.stage)}
                                                {step.tool && ` (${step.tool})`}
                                            </span>
                                            {step.duration_ms && (
                                                <span className="text-xs text-gray-500">
                                                    {step.duration_ms.toFixed(0)}ms
                                                </span>
                                            )}
                                        </div>

                                        <p className="text-sm text-gray-600">{step.message}</p>

                                        {/* 결과 상세 정보 */}
                                        {step.result && (
                                            <div className="mt-2 text-xs space-y-1">
                                                {step.result.intent && (
                                                    <div className="flex gap-2">
                                                        <span className="text-gray-500">의도:</span>
                                                        <span className="font-medium text-gray-700">{step.result.intent}</span>
                                                    </div>
                                                )}
                                                {step.result.keywords && step.result.keywords.length > 0 && (
                                                    <div className="flex gap-2">
                                                        <span className="text-gray-500">키워드:</span>
                                                        <span className="font-medium text-gray-700">
                                                            {step.result.keywords.join(', ')}
                                                        </span>
                                                    </div>
                                                )}
                                                {step.result.strategy && (
                                                    <div className="flex gap-2">
                                                        <span className="text-gray-500">전략:</span>
                                                        <span className="font-medium text-gray-700">
                                                            {step.result.strategy.join(' → ')}
                                                        </span>
                                                    </div>
                                                )}
                                                {typeof step.result.tokens === 'number' && (
                                                    <div className="flex gap-2">
                                                        <span className="text-gray-500">토큰:</span>
                                                        <span className="font-medium text-gray-700">
                                                            {step.result.tokens} / {step.result.max_tokens || 4000}
                                                        </span>
                                                    </div>
                                                )}
                                                {typeof step.result.chunks_used === 'number' && (
                                                    <div className="flex gap-2">
                                                        <span className="text-gray-500">사용 청크:</span>
                                                        <span className="font-medium text-gray-700">
                                                            {step.result.chunks_used}개
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* 검색 진행 상황 */}
                    {reasoning.searchProgress && reasoning.searchProgress.length > 0 && (
                        <div className="mt-4 p-3 bg-white rounded-lg border border-gray-200">
                            <h4 className="text-sm font-medium text-gray-700 mb-2">📊 검색 결과 통계</h4>
                            <div className="space-y-2">
                                {reasoning.searchProgress.map((progress, idx) => (
                                    <div key={idx} className="flex items-center justify-between text-xs">
                                        <span className="text-gray-600">{progress.tool}</span>
                                        <div className="flex items-center gap-3">
                                            <span className="font-medium text-gray-800">
                                                {progress.chunks_found}개 청크
                                            </span>
                                            {progress.avg_similarity && (
                                                <span className="text-gray-500">
                                                    평균 유사도: {(progress.avg_similarity * 100).toFixed(1)}%
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {reasoning.searchProgress.length > 0 && (
                                    <div className="pt-2 border-t border-gray-200 flex justify-between font-medium text-sm">
                                        <span className="text-gray-700">총합</span>
                                        <span className="text-blue-600">
                                            {reasoning.searchProgress.reduce((sum, p) => sum + p.total_chunks, 0)}개 청크
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* 최종 통계 */}
                    {reasoning.totalDuration && (
                        <div className="text-xs text-gray-500 text-right">
                            총 소요 시간: {(reasoning.totalDuration / 1000).toFixed(2)}초
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ReasoningPanel;

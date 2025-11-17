/**
 * AgentStepsTimeline Component
 * 
 * Agent 도구 실행 단계를 시각적으로 표시하는 타임라인 컴포넌트
 */

import {
    BeakerIcon,
    CheckCircleIcon,
    ClockIcon,
    XCircleIcon
} from '@heroicons/react/24/outline';
import React from 'react';
import { AgentStep, TOOL_COLORS, TOOL_LABELS } from '../types/agent.types';

interface AgentStepsTimelineProps {
    steps: AgentStep[];
    isLoading?: boolean;
    className?: string;
}

export const AgentStepsTimeline: React.FC<AgentStepsTimelineProps> = ({
    steps,
    isLoading = false,
    className = ''
}) => {
    if (!steps || steps.length === 0) {
        return null;
    }

    return (
        <div className={`bg-white rounded-lg shadow-sm border border-gray-200 p-4 ${className}`}>
            {/* 헤더 */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <BeakerIcon className="w-5 h-5 text-indigo-600" />
                    <h3 className="text-sm font-semibold text-gray-900">
                        실행 단계
                    </h3>
                    <span className="text-xs text-gray-500">
                        ({steps.length}개 도구)
                    </span>
                </div>
                {isLoading && (
                    <div className="flex items-center gap-2 text-xs text-blue-600">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
                        실행 중...
                    </div>
                )}
            </div>

            {/* 타임라인 */}
            <div className="space-y-3">
                {steps.map((step, index) => {
                    const colors = TOOL_COLORS[step.tool_name as keyof typeof TOOL_COLORS] || {
                        bg: 'bg-gray-50',
                        text: 'text-gray-700',
                        border: 'border-gray-200'
                    };

                    const toolLabel = TOOL_LABELS[step.tool_name as keyof typeof TOOL_LABELS] || step.tool_name;

                    return (
                        <div key={step.step_number} className="relative">
                            {/* 연결선 */}
                            {index < steps.length - 1 && (
                                <div className="absolute left-4 top-8 bottom-0 w-0.5 bg-gray-200" />
                            )}

                            {/* 단계 카드 */}
                            <div className={`relative flex gap-3 ${colors.bg} ${colors.border} border rounded-lg p-3 hover:shadow-sm transition-shadow`}>
                                {/* 단계 번호 + 성공/실패 아이콘 */}
                                <div className="flex-shrink-0">
                                    <div className={`w-8 h-8 rounded-full ${colors.bg} ${colors.border} border-2 flex items-center justify-center font-semibold ${colors.text}`}>
                                        {step.success ? (
                                            <CheckCircleIcon className="w-5 h-5 text-green-600" />
                                        ) : (
                                            <XCircleIcon className="w-5 h-5 text-red-600" />
                                        )}
                                    </div>
                                </div>

                                {/* 내용 */}
                                <div className="flex-1 min-w-0">
                                    {/* 도구 이름 + 실행 시간 */}
                                    <div className="flex items-start justify-between gap-2 mb-1">
                                        <div className="flex items-center gap-2">
                                            <span className={`text-sm font-semibold ${colors.text}`}>
                                                {step.step_number}. {toolLabel}
                                            </span>
                                            {step.items_returned !== undefined && (
                                                <span className="text-xs text-gray-500 bg-white px-2 py-0.5 rounded-full">
                                                    {step.items_returned}개
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-1 text-xs text-gray-500">
                                            <ClockIcon className="w-3.5 h-3.5" />
                                            {step.latency_ms < 1000
                                                ? `${Math.round(step.latency_ms)}ms`
                                                : `${(step.latency_ms / 1000).toFixed(1)}s`
                                            }
                                        </div>
                                    </div>

                                    {/* 추론 (Reasoning) */}
                                    {step.reasoning && (
                                        <p className="text-xs text-gray-600 leading-relaxed">
                                            {step.reasoning}
                                        </p>
                                    )}

                                    {/* 실패 시 에러 표시 */}
                                    {!step.success && (
                                        <div className="mt-2 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                                            ❌ 실행 실패
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* 전체 요약 */}
            <div className="mt-4 pt-3 border-t border-gray-200">
                <div className="flex items-center justify-between text-xs text-gray-600">
                    <div className="flex items-center gap-4">
                        <span>
                            성공: <strong className="text-green-600">{steps.filter(s => s.success).length}</strong>
                        </span>
                        <span>
                            실패: <strong className="text-red-600">{steps.filter(s => !s.success).length}</strong>
                        </span>
                    </div>
                    <span>
                        총 실행시간: <strong className="text-gray-900">
                            {(steps.reduce((sum, s) => sum + s.latency_ms, 0) / 1000).toFixed(2)}s
                        </strong>
                    </span>
                </div>
            </div>
        </div>
    );
};

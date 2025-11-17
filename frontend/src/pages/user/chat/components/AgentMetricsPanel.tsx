/**
 * AgentMetricsPanel Component
 * 
 * Agent 실행 지표를 표시하는 패널
 * - Intent (의도)
 * - Strategy (전략)
 * - Performance Metrics (성능 지표)
 */

import {
    BoltIcon,
    ChartBarIcon,
    ClockIcon,
    CubeTransparentIcon,
    DocumentTextIcon,
    SparklesIcon
} from '@heroicons/react/24/outline';
import React from 'react';
import { AgentIntent, AgentMetrics, INTENT_LABELS } from '../types/agent.types';

interface AgentMetricsPanelProps {
    intent?: AgentIntent;
    strategy?: string[];
    metrics?: AgentMetrics;
    className?: string;
}

export const AgentMetricsPanel: React.FC<AgentMetricsPanelProps> = ({
    intent,
    strategy,
    metrics,
    className = ''
}) => {
    if (!intent && !strategy && !metrics) {
        return null;
    }

    // Intent 색상 매핑
    const intentColors: Record<string, { bg: string; text: string; border: string }> = {
        FACTUAL_QA: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
        KEYWORD_SEARCH: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
        DOCUMENT_ANALYSIS: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
        GENERAL_CHAT: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
        UNKNOWN: { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200' }
    };

    const defaultColors = { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200' };
    const currentIntentColors = intent && intentColors[intent]
        ? intentColors[intent]
        : defaultColors;

    return (
        <div className={`bg-gradient-to-br from-indigo-50 to-purple-50 rounded-lg shadow-sm border border-indigo-200 p-4 ${className}`}>
            {/* 헤더 */}
            <div className="flex items-center gap-2 mb-4">
                <ChartBarIcon className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-semibold text-gray-900">
                    Agent 분석
                </h3>
            </div>

            <div className="space-y-4">
                {/* Intent */}
                {intent && (
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <SparklesIcon className="w-4 h-4 text-indigo-500" />
                            <span className="text-xs font-medium text-gray-700">의도 (Intent)</span>
                        </div>
                        <div className={`${currentIntentColors.bg} ${currentIntentColors.border} border rounded-md px-3 py-2`}>
                            <span className={`text-sm font-semibold ${currentIntentColors.text}`}>
                                {INTENT_LABELS[intent] || intent}
                            </span>
                        </div>
                    </div>
                )}

                {/* Strategy */}
                {strategy && strategy.length > 0 && (
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <BoltIcon className="w-4 h-4 text-indigo-500" />
                            <span className="text-xs font-medium text-gray-700">실행 전략</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                            {strategy.map((tool, index) => (
                                <span
                                    key={index}
                                    className="text-xs bg-white text-indigo-700 px-2.5 py-1 rounded-full border border-indigo-200 font-medium"
                                >
                                    {tool}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Performance Metrics */}
                {metrics && (
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <CubeTransparentIcon className="w-4 h-4 text-indigo-500" />
                            <span className="text-xs font-medium text-gray-700">성능 지표</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            {/* 전체 실행시간 */}
                            <MetricCard
                                icon={<ClockIcon className="w-4 h-4" />}
                                label="실행시간"
                                value={
                                    metrics.total_latency_ms < 1000
                                        ? `${Math.round(metrics.total_latency_ms)}ms`
                                        : `${(metrics.total_latency_ms / 1000).toFixed(2)}s`
                                }
                                color="blue"
                            />

                            {/* 검색된 청크 수 */}
                            <MetricCard
                                icon={<DocumentTextIcon className="w-4 h-4" />}
                                label="검색 청크"
                                value={`${metrics.total_chunks_found}개`}
                                color="green"
                            />

                            {/* 사용된 토큰 수 */}
                            {metrics.total_tokens_used !== undefined && (
                                <MetricCard
                                    icon={<CubeTransparentIcon className="w-4 h-4" />}
                                    label="토큰 사용"
                                    value={`${metrics.total_tokens_used}`}
                                    color="purple"
                                />
                            )}

                            {/* 중복 제거율 */}
                            {metrics.deduplication_rate !== undefined && (
                                <MetricCard
                                    icon={<SparklesIcon className="w-4 h-4" />}
                                    label="중복 제거"
                                    value={`${(metrics.deduplication_rate * 100).toFixed(0)}%`}
                                    color="orange"
                                />
                            )}
                        </div>

                        {/* 추가 상세 지표 (접기/펼치기) */}
                        {(metrics.search_time_ms || metrics.rerank_time_ms || metrics.context_build_time_ms) && (
                            <details className="mt-2">
                                <summary className="text-xs text-indigo-600 cursor-pointer hover:text-indigo-800 font-medium">
                                    상세 지표 보기
                                </summary>
                                <div className="mt-2 space-y-1 text-xs text-gray-600 bg-white rounded p-2">
                                    {metrics.search_time_ms && (
                                        <div className="flex justify-between">
                                            <span>검색 시간:</span>
                                            <span className="font-mono">{metrics.search_time_ms.toFixed(1)}ms</span>
                                        </div>
                                    )}
                                    {metrics.rerank_time_ms && (
                                        <div className="flex justify-between">
                                            <span>리랭킹 시간:</span>
                                            <span className="font-mono">{metrics.rerank_time_ms.toFixed(1)}ms</span>
                                        </div>
                                    )}
                                    {metrics.context_build_time_ms && (
                                        <div className="flex justify-between">
                                            <span>컨텍스트 구성:</span>
                                            <span className="font-mono">{metrics.context_build_time_ms.toFixed(1)}ms</span>
                                        </div>
                                    )}
                                    {metrics.llm_time_ms && (
                                        <div className="flex justify-between">
                                            <span>LLM 추론:</span>
                                            <span className="font-mono">{metrics.llm_time_ms.toFixed(1)}ms</span>
                                        </div>
                                    )}
                                </div>
                            </details>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

// 지표 카드 서브컴포넌트
interface MetricCardProps {
    icon: React.ReactNode;
    label: string;
    value: string;
    color: 'blue' | 'green' | 'purple' | 'orange';
}

const MetricCard: React.FC<MetricCardProps> = ({ icon, label, value, color }) => {
    const colorClasses = {
        blue: 'bg-blue-50 text-blue-700 border-blue-200',
        green: 'bg-green-50 text-green-700 border-green-200',
        purple: 'bg-purple-50 text-purple-700 border-purple-200',
        orange: 'bg-orange-50 text-orange-700 border-orange-200'
    };

    return (
        <div className={`${colorClasses[color]} border rounded-md p-2`}>
            <div className="flex items-center gap-1.5 mb-1">
                {icon}
                <span className="text-[10px] font-medium uppercase tracking-wide">
                    {label}
                </span>
            </div>
            <div className="text-base font-bold">
                {value}
            </div>
        </div>
    );
};

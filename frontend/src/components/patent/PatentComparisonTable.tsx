/**
 * PatentComparisonTable - 특허 비교 테이블 컴포넌트
 * 기업별/기술별 특허 비교 분석 시각화
 */
import {
    Equal,
    TrendingDown,
    TrendingUp
} from 'lucide-react';
import React from 'react';

export interface ComparisonItem {
    name: string;
    metrics: {
        [key: string]: {
            value: number | string;
            trend?: 'up' | 'down' | 'stable';
            changePercent?: number;
        };
    };
    totalScore?: number;
    rank?: number;
}

export interface ComparisonMetric {
    key: string;
    label: string;
    unit?: string;
    higherIsBetter?: boolean;
}

interface PatentComparisonTableProps {
    items: ComparisonItem[];
    metrics: ComparisonMetric[];
    title?: string;
    showRank?: boolean;
    highlightTop?: number;
}

const PatentComparisonTable: React.FC<PatentComparisonTableProps> = ({
    items,
    metrics,
    title = '특허 비교 분석',
    showRank = true,
    highlightTop = 3,
}) => {
    const getTrendIcon = (trend?: 'up' | 'down' | 'stable') => {
        switch (trend) {
            case 'up':
                return <TrendingUp className="w-4 h-4 text-green-500" />;
            case 'down':
                return <TrendingDown className="w-4 h-4 text-red-500" />;
            case 'stable':
                return <Equal className="w-4 h-4 text-gray-400" />;
            default:
                return null;
        }
    };

    const formatValue = (value: number | string, unit?: string) => {
        if (typeof value === 'number') {
            return `${value.toLocaleString()}${unit ? ` ${unit}` : ''}`;
        }
        return value;
    };

    const getRankBadge = (rank?: number) => {
        if (!rank) return null;

        const colors = {
            1: 'bg-yellow-400 text-yellow-900',
            2: 'bg-gray-300 text-gray-800',
            3: 'bg-amber-600 text-amber-100',
        };

        const colorClass = colors[rank as keyof typeof colors] || 'bg-gray-100 text-gray-600';

        return (
            <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${colorClass}`}>
                {rank}
            </span>
        );
    };

    // 순위별 정렬
    const sortedItems = [...items].sort((a, b) => (a.rank || 999) - (b.rank || 999));

    if (!items.length) {
        return (
            <div className="text-center py-8 text-gray-500">
                비교할 데이터가 없습니다
            </div>
        );
    }

    return (
        <div className="w-full">
            {title && (
                <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
            )}

            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            {showRank && (
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    순위
                                </th>
                            )}
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                기업/기술
                            </th>
                            {metrics.map((metric) => (
                                <th
                                    key={metric.key}
                                    className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
                                >
                                    {metric.label}
                                </th>
                            ))}
                            {items.some(item => item.totalScore !== undefined) && (
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    종합점수
                                </th>
                            )}
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {sortedItems.map((item, index) => {
                            const isHighlighted = item.rank && item.rank <= highlightTop;

                            return (
                                <tr
                                    key={item.name}
                                    className={`
                    ${isHighlighted ? 'bg-teal-50' : index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                    hover:bg-gray-100 transition-colors
                  `}
                                >
                                    {showRank && (
                                        <td className="px-3 py-4 whitespace-nowrap">
                                            {getRankBadge(item.rank)}
                                        </td>
                                    )}
                                    <td className="px-4 py-4 whitespace-nowrap">
                                        <span className={`font-medium ${isHighlighted ? 'text-teal-700' : 'text-gray-900'}`}>
                                            {item.name}
                                        </span>
                                    </td>
                                    {metrics.map((metric) => {
                                        const data = item.metrics[metric.key];
                                        if (!data) {
                                            return (
                                                <td key={metric.key} className="px-4 py-4 whitespace-nowrap text-right text-gray-400">
                                                    -
                                                </td>
                                            );
                                        }

                                        return (
                                            <td key={metric.key} className="px-4 py-4 whitespace-nowrap text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    <span className="text-gray-900">
                                                        {formatValue(data.value, metric.unit)}
                                                    </span>
                                                    {getTrendIcon(data.trend)}
                                                    {data.changePercent !== undefined && (
                                                        <span className={`text-xs ${data.changePercent > 0
                                                                ? 'text-green-600'
                                                                : data.changePercent < 0
                                                                    ? 'text-red-600'
                                                                    : 'text-gray-500'
                                                            }`}>
                                                            {data.changePercent > 0 ? '+' : ''}{data.changePercent}%
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                        );
                                    })}
                                    {item.totalScore !== undefined && (
                                        <td className="px-4 py-4 whitespace-nowrap text-right">
                                            <span className={`font-semibold ${isHighlighted ? 'text-teal-700' : 'text-gray-900'}`}>
                                                {item.totalScore.toFixed(1)}
                                            </span>
                                        </td>
                                    )}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default PatentComparisonTable;

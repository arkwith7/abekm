/**
 * PatentGapMatrix - 특허 갭 분석 매트릭스 컴포넌트
 * 기술 영역별 특허 보유 현황 및 갭 시각화
 */
import {
    AlertTriangle,
    CheckCircle,
    Lightbulb,
    Target,
    XCircle,
} from 'lucide-react';
import React from 'react';

export interface GapMatrixCell {
    value: number | 'strong' | 'moderate' | 'weak' | 'none';
    patentCount?: number;
    opportunity?: 'high' | 'medium' | 'low';
    competitors?: string[];
}

export interface GapMatrixData {
    technologies: string[];
    companies: string[];
    matrix: GapMatrixCell[][];  // [company][technology]
    targetCompany?: string;
}

interface PatentGapMatrixProps {
    data: GapMatrixData;
    title?: string;
    showOpportunities?: boolean;
    onCellClick?: (company: string, technology: string, cell: GapMatrixCell) => void;
}

const PatentGapMatrix: React.FC<PatentGapMatrixProps> = ({
    data,
    title = '기술 갭 분석',
    showOpportunities = true,
    onCellClick,
}) => {
    const getCellColor = (cell: GapMatrixCell, isTarget: boolean) => {
        const value = typeof cell.value === 'number' ?
            (cell.value > 10 ? 'strong' : cell.value > 3 ? 'moderate' : cell.value > 0 ? 'weak' : 'none')
            : cell.value;

        const colors = {
            strong: isTarget ? 'bg-teal-500 text-white' : 'bg-green-500 text-white',
            moderate: isTarget ? 'bg-teal-300 text-teal-900' : 'bg-yellow-400 text-yellow-900',
            weak: isTarget ? 'bg-teal-100 text-teal-700' : 'bg-orange-200 text-orange-800',
            none: 'bg-gray-100 text-gray-400',
        };

        return colors[value] || colors.none;
    };

    const getCellIcon = (cell: GapMatrixCell) => {
        const value = typeof cell.value === 'number' ?
            (cell.value > 10 ? 'strong' : cell.value > 3 ? 'moderate' : cell.value > 0 ? 'weak' : 'none')
            : cell.value;

        switch (value) {
            case 'strong':
                return <CheckCircle className="w-4 h-4" />;
            case 'moderate':
                return <AlertTriangle className="w-4 h-4" />;
            case 'weak':
                return <Target className="w-4 h-4" />;
            case 'none':
                return <XCircle className="w-4 h-4" />;
            default:
                return null;
        }
    };

    const getOpportunityBadge = (opportunity?: 'high' | 'medium' | 'low') => {
        if (!opportunity) return null;

        const styles = {
            high: 'bg-red-100 text-red-700 border-red-200',
            medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
            low: 'bg-gray-100 text-gray-600 border-gray-200',
        };

        const labels = {
            high: '높음',
            medium: '보통',
            low: '낮음',
        };

        return (
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-xs rounded border ${styles[opportunity]}`}>
                <Lightbulb className="w-3 h-3" />
                {labels[opportunity]}
            </span>
        );
    };

    // 기회 영역 찾기 (자사가 약하고 경쟁사가 강한 영역)
    const opportunities = data.targetCompany ?
        data.technologies.map((tech, techIndex) => {
            const targetIndex = data.companies.indexOf(data.targetCompany!);
            if (targetIndex === -1) return null;

            const targetCell = data.matrix[targetIndex][techIndex];
            const targetStrength = typeof targetCell.value === 'number' ? targetCell.value :
                (targetCell.value === 'strong' ? 10 : targetCell.value === 'moderate' ? 5 : 1);

            // 경쟁사 중 강한 기업 찾기
            const strongCompetitors = data.companies
                .filter((_, i) => i !== targetIndex)
                .filter((_, i) => {
                    const cell = data.matrix[i][techIndex];
                    const strength = typeof cell.value === 'number' ? cell.value :
                        (cell.value === 'strong' ? 10 : cell.value === 'moderate' ? 5 : 1);
                    return strength > targetStrength;
                });

            if (strongCompetitors.length > 0 && targetStrength < 5) {
                return {
                    technology: tech,
                    competitors: strongCompetitors,
                    priority: strongCompetitors.length,
                };
            }
            return null;
        }).filter(Boolean) : [];

    if (!data.technologies.length || !data.companies.length) {
        return (
            <div className="text-center py-8 text-gray-500">
                분석할 데이터가 없습니다
            </div>
        );
    }

    return (
        <div className="w-full">
            {title && (
                <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
            )}

            {/* 범례 */}
            <div className="flex flex-wrap gap-4 mb-4 text-sm">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-green-500" />
                    <span className="text-gray-600">강함 (10+건)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-yellow-400" />
                    <span className="text-gray-600">보통 (4-10건)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-orange-200" />
                    <span className="text-gray-600">약함 (1-3건)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gray-100 border border-gray-300" />
                    <span className="text-gray-600">없음</span>
                </div>
                {data.targetCompany && (
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded bg-teal-500" />
                        <span className="text-gray-600">{data.targetCompany} (자사)</span>
                    </div>
                )}
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                    <thead>
                        <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200">
                                기업 / 기술
                            </th>
                            {data.technologies.map((tech) => (
                                <th
                                    key={tech}
                                    className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200 min-w-[100px]"
                                >
                                    {tech}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.companies.map((company, companyIndex) => {
                            const isTarget = company === data.targetCompany;

                            return (
                                <tr
                                    key={company}
                                    className={isTarget ? 'bg-teal-50' : ''}
                                >
                                    <td className={`px-3 py-3 whitespace-nowrap font-medium border-b border-gray-100 ${isTarget ? 'text-teal-700' : 'text-gray-900'
                                        }`}>
                                        {company}
                                        {isTarget && (
                                            <span className="ml-2 text-xs text-teal-600">(자사)</span>
                                        )}
                                    </td>
                                    {data.technologies.map((tech, techIndex) => {
                                        const cell = data.matrix[companyIndex][techIndex];

                                        return (
                                            <td
                                                key={tech}
                                                className="px-3 py-3 text-center border-b border-gray-100"
                                                onClick={() => onCellClick?.(company, tech, cell)}
                                            >
                                                <div
                                                    className={`
                            inline-flex items-center justify-center gap-1
                            px-2 py-1 rounded-md text-sm font-medium
                            ${getCellColor(cell, isTarget)}
                            ${onCellClick ? 'cursor-pointer hover:opacity-80' : ''}
                          `}
                                                >
                                                    {getCellIcon(cell)}
                                                    <span>
                                                        {typeof cell.value === 'number'
                                                            ? cell.value
                                                            : cell.patentCount ?? '-'}
                                                    </span>
                                                </div>
                                            </td>
                                        );
                                    })}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* 기회 영역 */}
            {showOpportunities && opportunities.length > 0 && (
                <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <h4 className="font-semibold text-amber-800 mb-3 flex items-center gap-2">
                        <Lightbulb className="w-5 h-5" />
                        특허 확보 기회 영역
                    </h4>
                    <ul className="space-y-2">
                        {(opportunities as any[]).slice(0, 5).map((opp, index) => (
                            <li key={index} className="flex items-start gap-2 text-sm text-amber-900">
                                <Target className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <span>
                                    <strong>{opp.technology}</strong>: 경쟁사({opp.competitors.slice(0, 2).join(', ')})
                                    대비 특허 확보 필요
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default PatentGapMatrix;

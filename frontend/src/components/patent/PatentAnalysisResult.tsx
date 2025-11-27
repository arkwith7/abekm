/**
 * PatentAnalysisResult - 특허 분석 결과 통합 컴포넌트
 * 분석 유형에 따라 적절한 시각화 컴포넌트 렌더링
 */
import {
    Activity,
    Briefcase,
    FileText,
    GitCompare,
    Search,
    Target,
    TrendingUp
} from 'lucide-react';
import React from 'react';

import {
    BarChartDataItem,
    BarConfig,
    LineChartDataItem,
    LineConfig,
    NetworkGraphData,
    PatentBarChart,
    PatentLineChart,
    PatentNetworkGraph,
    PatentPieChart,
    PatentRadarChart,
    PieChartData,
    RadarChartDataItem,
    RadarConfig,
} from '../charts';
import PatentComparisonTable, { ComparisonItem, ComparisonMetric } from './PatentComparisonTable';
import PatentGapMatrix, { GapMatrixData } from './PatentGapMatrix';
import PatentSearchResults, { PatentResult } from './PatentSearchResults';

export type AnalysisType = 'search' | 'comparison' | 'trend' | 'portfolio' | 'gap';

export interface PatentAnalysisData {
    type: AnalysisType;
    summary?: string;
    insights?: string[];

    // 검색 결과
    searchResults?: PatentResult[];

    // 비교 분석
    comparisonItems?: ComparisonItem[];
    comparisonMetrics?: ComparisonMetric[];

    // 트렌드 분석
    trendData?: LineChartDataItem[];
    trendLines?: LineConfig[];

    // 포트폴리오 분석
    portfolioDistribution?: PieChartData[];
    portfolioByYear?: BarChartDataItem[];
    portfolioBars?: BarConfig[];
    portfolioStrength?: RadarChartDataItem[];
    portfolioRadars?: RadarConfig[];

    // 갭 분석
    gapMatrix?: GapMatrixData;

    // 네트워크 그래프
    networkData?: NetworkGraphData;

    // 추가 차트 데이터
    charts?: {
        pie?: { data: PieChartData[]; title?: string };
        bar?: { data: BarChartDataItem[]; bars: BarConfig[]; title?: string };
        line?: { data: LineChartDataItem[]; lines: LineConfig[]; title?: string };
        radar?: { data: RadarChartDataItem[]; radars: RadarConfig[]; title?: string };
        network?: { data: NetworkGraphData; title?: string };
    };
}

interface PatentAnalysisResultProps {
    data: PatentAnalysisData;
    title?: string;
    onPatentClick?: (patent: PatentResult) => void;
}

const PatentAnalysisResult: React.FC<PatentAnalysisResultProps> = ({
    data,
    title,
    onPatentClick,
}) => {
    const getTypeInfo = (type: AnalysisType) => {
        const typeMap = {
            search: {
                icon: Search,
                label: '특허 검색',
                color: 'text-blue-600 bg-blue-50',
            },
            comparison: {
                icon: GitCompare,
                label: '경쟁사 비교 분석',
                color: 'text-purple-600 bg-purple-50',
            },
            trend: {
                icon: TrendingUp,
                label: '기술 트렌드 분석',
                color: 'text-green-600 bg-green-50',
            },
            portfolio: {
                icon: Briefcase,
                label: '포트폴리오 분석',
                color: 'text-teal-600 bg-teal-50',
            },
            gap: {
                icon: Target,
                label: '갭 분석',
                color: 'text-orange-600 bg-orange-50',
            },
        };
        return typeMap[type] || typeMap.search;
    };

    const typeInfo = getTypeInfo(data.type);
    const TypeIcon = typeInfo.icon;

    return (
        <div className="space-y-6">
            {/* 헤더 */}
            <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${typeInfo.color}`}>
                    <TypeIcon className="w-5 h-5" />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-gray-900">
                        {title || typeInfo.label}
                    </h2>
                    <p className="text-sm text-gray-500">{typeInfo.label}</p>
                </div>
            </div>

            {/* 요약 */}
            {data.summary && (
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <h3 className="font-semibold text-gray-700 mb-2 flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        분석 요약
                    </h3>
                    <p className="text-gray-700 whitespace-pre-wrap">{data.summary}</p>
                </div>
            )}

            {/* 인사이트 */}
            {data.insights && data.insights.length > 0 && (
                <div className="p-4 bg-teal-50 rounded-lg border border-teal-200">
                    <h3 className="font-semibold text-teal-700 mb-3 flex items-center gap-2">
                        <Activity className="w-4 h-4" />
                        주요 인사이트
                    </h3>
                    <ul className="space-y-2">
                        {data.insights.map((insight, index) => (
                            <li key={index} className="flex items-start gap-2 text-teal-800">
                                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-teal-200 text-teal-700 text-xs flex items-center justify-center font-medium">
                                    {index + 1}
                                </span>
                                <span>{insight}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* 분석 유형별 시각화 */}
            <div className="space-y-6">
                {/* 검색 결과 */}
                {data.type === 'search' && data.searchResults && (
                    <PatentSearchResults
                        results={data.searchResults}
                        onPatentClick={onPatentClick}
                    />
                )}

                {/* 비교 분석 */}
                {data.type === 'comparison' && data.comparisonItems && data.comparisonMetrics && (
                    <PatentComparisonTable
                        items={data.comparisonItems}
                        metrics={data.comparisonMetrics}
                    />
                )}

                {/* 트렌드 분석 */}
                {data.type === 'trend' && data.trendData && data.trendLines && (
                    <div className="bg-white p-4 rounded-lg border border-gray-200">
                        <PatentLineChart
                            data={data.trendData}
                            lines={data.trendLines}
                            title="기술 트렌드"
                            height={350}
                        />
                    </div>
                )}

                {/* 포트폴리오 분석 */}
                {data.type === 'portfolio' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {data.portfolioDistribution && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200">
                                <PatentPieChart
                                    data={data.portfolioDistribution}
                                    title="기술분야별 분포"
                                    height={280}
                                />
                            </div>
                        )}
                        {data.portfolioByYear && data.portfolioBars && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200">
                                <PatentBarChart
                                    data={data.portfolioByYear}
                                    bars={data.portfolioBars}
                                    title="연도별 출원 현황"
                                    height={280}
                                />
                            </div>
                        )}
                        {data.portfolioStrength && data.portfolioRadars && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200 md:col-span-2">
                                <PatentRadarChart
                                    data={data.portfolioStrength}
                                    radars={data.portfolioRadars}
                                    title="기술역량 분석"
                                    height={350}
                                />
                            </div>
                        )}
                    </div>
                )}

                {/* 갭 분석 */}
                {data.type === 'gap' && data.gapMatrix && (
                    <PatentGapMatrix data={data.gapMatrix} />
                )}

                {/* 네트워크 그래프 */}
                {data.networkData && (
                    <div className="bg-white p-4 rounded-lg border border-gray-200">
                        <PatentNetworkGraph
                            data={data.networkData}
                            title="특허 인용 네트워크"
                            height={400}
                        />
                    </div>
                )}

                {/* 추가 차트 */}
                {data.charts && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {data.charts.pie && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200">
                                <PatentPieChart
                                    data={data.charts.pie.data}
                                    title={data.charts.pie.title}
                                    height={280}
                                />
                            </div>
                        )}
                        {data.charts.bar && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200">
                                <PatentBarChart
                                    data={data.charts.bar.data}
                                    bars={data.charts.bar.bars}
                                    title={data.charts.bar.title}
                                    height={280}
                                />
                            </div>
                        )}
                        {data.charts.line && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200 md:col-span-2">
                                <PatentLineChart
                                    data={data.charts.line.data}
                                    lines={data.charts.line.lines}
                                    title={data.charts.line.title}
                                    height={300}
                                />
                            </div>
                        )}
                        {data.charts.radar && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200">
                                <PatentRadarChart
                                    data={data.charts.radar.data}
                                    radars={data.charts.radar.radars}
                                    title={data.charts.radar.title}
                                    height={320}
                                />
                            </div>
                        )}
                        {data.charts.network && (
                            <div className="bg-white p-4 rounded-lg border border-gray-200">
                                <PatentNetworkGraph
                                    data={data.charts.network.data}
                                    title={data.charts.network.title}
                                    height={350}
                                />
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default PatentAnalysisResult;

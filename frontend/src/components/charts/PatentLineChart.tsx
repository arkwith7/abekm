/**
 * PatentLineChart - 특허 분석용 라인 차트 컴포넌트
 * 트렌드 분석, 시계열 데이터 시각화
 */
import React from 'react';
import {
    Area,
    CartesianGrid,
    ComposedChart,
    Legend,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

export interface LineChartDataItem {
    name: string;
    [key: string]: string | number;
}

export interface LineConfig {
    dataKey: string;
    name: string;
    color: string;
    strokeWidth?: number;
    dashed?: boolean;
    showArea?: boolean;
}

interface PatentLineChartProps {
    data: LineChartDataItem[];
    lines: LineConfig[];
    title?: string;
    height?: number;
    showGrid?: boolean;
    showLegend?: boolean;
    showDots?: boolean;
    xAxisLabel?: string;
    yAxisLabel?: string;
}

const PatentLineChart: React.FC<PatentLineChartProps> = ({
    data,
    lines,
    title,
    height = 300,
    showGrid = true,
    showLegend = true,
    showDots = true,
    xAxisLabel,
    yAxisLabel,
}) => {
    const CustomTooltip = ({ active, payload, label }: any) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-white px-3 py-2 shadow-lg rounded-lg border border-gray-200">
                    <p className="font-medium text-gray-900 mb-1">{label}</p>
                    {payload.map((entry: any, index: number) => (
                        <p key={index} className="text-sm" style={{ color: entry.color }}>
                            {entry.name}: <span className="font-semibold">{entry.value?.toLocaleString() ?? 'N/A'}</span>
                        </p>
                    ))}
                </div>
            );
        }
        return null;
    };

    const hasArea = lines.some(line => line.showArea);

    return (
        <div className="w-full">
            {title && (
                <h3 className="text-sm font-semibold text-gray-700 mb-2 text-center">
                    {title}
                </h3>
            )}
            <ResponsiveContainer width="100%" height={height}>
                {hasArea ? (
                    <ComposedChart
                        data={data}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                    >
                        {showGrid && (
                            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                        )}
                        <XAxis
                            dataKey="name"
                            tick={{ fontSize: 12 }}
                            label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 0 } : undefined}
                        />
                        <YAxis
                            label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft' } : undefined}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        {showLegend && (
                            <Legend
                                layout="horizontal"
                                verticalAlign="top"
                                align="right"
                                wrapperStyle={{ paddingBottom: 10 }}
                            />
                        )}
                        {lines.map((line) => (
                            line.showArea ? (
                                <Area
                                    key={line.dataKey}
                                    type="monotone"
                                    dataKey={line.dataKey}
                                    name={line.name}
                                    stroke={line.color}
                                    fill={line.color}
                                    fillOpacity={0.1}
                                    strokeWidth={line.strokeWidth || 2}
                                />
                            ) : (
                                <Line
                                    key={line.dataKey}
                                    type="monotone"
                                    dataKey={line.dataKey}
                                    name={line.name}
                                    stroke={line.color}
                                    strokeWidth={line.strokeWidth || 2}
                                    strokeDasharray={line.dashed ? '5 5' : undefined}
                                    dot={showDots}
                                    activeDot={{ r: 6 }}
                                />
                            )
                        ))}
                    </ComposedChart>
                ) : (
                    <LineChart
                        data={data}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                    >
                        {showGrid && (
                            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                        )}
                        <XAxis
                            dataKey="name"
                            tick={{ fontSize: 12 }}
                            label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 0 } : undefined}
                        />
                        <YAxis
                            label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft' } : undefined}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        {showLegend && (
                            <Legend
                                layout="horizontal"
                                verticalAlign="top"
                                align="right"
                                wrapperStyle={{ paddingBottom: 10 }}
                            />
                        )}
                        {lines.map((line) => (
                            <Line
                                key={line.dataKey}
                                type="monotone"
                                dataKey={line.dataKey}
                                name={line.name}
                                stroke={line.color}
                                strokeWidth={line.strokeWidth || 2}
                                strokeDasharray={line.dashed ? '5 5' : undefined}
                                dot={showDots}
                                activeDot={{ r: 6 }}
                            />
                        ))}
                    </LineChart>
                )}
            </ResponsiveContainer>
        </div>
    );
};

export default PatentLineChart;

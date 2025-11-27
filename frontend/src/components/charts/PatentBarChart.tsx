/**
 * PatentBarChart - 특허 분석용 바 차트 컴포넌트
 * 연도별 출원 추이, 기업별 특허 수 비교 등 시각화
 */
import React from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts';

export interface BarChartDataItem {
    name: string;
    [key: string]: string | number;
}

export interface BarConfig {
    dataKey: string;
    name: string;
    color: string;
    stackId?: string;
}

interface PatentBarChartProps {
    data: BarChartDataItem[];
    bars: BarConfig[];
    title?: string;
    height?: number;
    showGrid?: boolean;
    showLegend?: boolean;
    layout?: 'horizontal' | 'vertical';
    xAxisLabel?: string;
    yAxisLabel?: string;
}

const PatentBarChart: React.FC<PatentBarChartProps> = ({
    data,
    bars,
    title,
    height = 300,
    showGrid = true,
    showLegend = true,
    layout = 'horizontal',
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
                            {entry.name}: <span className="font-semibold">{entry.value.toLocaleString()}</span>
                        </p>
                    ))}
                </div>
            );
        }
        return null;
    };

    const isVertical = layout === 'vertical';

    return (
        <div className="w-full">
            {title && (
                <h3 className="text-sm font-semibold text-gray-700 mb-2 text-center">
                    {title}
                </h3>
            )}
            <ResponsiveContainer width="100%" height={height}>
                <BarChart
                    data={data}
                    layout={layout}
                    margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                >
                    {showGrid && (
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    )}
                    {isVertical ? (
                        <>
                            <XAxis type="number" />
                            <YAxis
                                type="category"
                                dataKey="name"
                                width={100}
                                tick={{ fontSize: 12 }}
                            />
                        </>
                    ) : (
                        <>
                            <XAxis
                                dataKey="name"
                                tick={{ fontSize: 12 }}
                                label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 0 } : undefined}
                            />
                            <YAxis
                                label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft' } : undefined}
                            />
                        </>
                    )}
                    <Tooltip content={<CustomTooltip />} />
                    {showLegend && bars.length > 1 && (
                        <Legend
                            layout="horizontal"
                            verticalAlign="top"
                            align="right"
                            wrapperStyle={{ paddingBottom: 10 }}
                        />
                    )}
                    {bars.map((bar, index) => (
                        <Bar
                            key={bar.dataKey}
                            dataKey={bar.dataKey}
                            name={bar.name}
                            fill={bar.color}
                            stackId={bar.stackId}
                            radius={[4, 4, 0, 0]}
                        />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default PatentBarChart;

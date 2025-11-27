/**
 * PatentRadarChart - 특허 분석용 레이더 차트 컴포넌트
 * 기술역량 비교, 다차원 분석 시각화
 */
import React from 'react';
import {
    Legend,
    PolarAngleAxis,
    PolarGrid,
    PolarRadiusAxis,
    Radar,
    RadarChart,
    ResponsiveContainer,
    Tooltip,
} from 'recharts';

// Recharts React 18 타입 호환성
const RPolarAngleAxis = PolarAngleAxis as unknown as React.FC<any>;
const RPolarRadiusAxis = PolarRadiusAxis as unknown as React.FC<any>;

export interface RadarChartDataItem {
    subject: string;
    fullMark?: number;
    [key: string]: string | number | undefined;
}

export interface RadarConfig {
    dataKey: string;
    name: string;
    color: string;
    fillOpacity?: number;
}

interface PatentRadarChartProps {
    data: RadarChartDataItem[];
    radars: RadarConfig[];
    title?: string;
    height?: number;
    showLegend?: boolean;
    maxValue?: number;
}

const PatentRadarChart: React.FC<PatentRadarChartProps> = ({
    data,
    radars,
    title,
    height = 350,
    showLegend = true,
    maxValue,
}) => {
    // 최대값 자동 계산
    const calculatedMax = maxValue || Math.max(
        ...data.flatMap(item =>
            radars.map(radar => Number(item[radar.dataKey]) || 0)
        )
    ) * 1.1;

    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            const subject = payload[0]?.payload?.subject;
            return (
                <div className="bg-white px-3 py-2 shadow-lg rounded-lg border border-gray-200">
                    <p className="font-medium text-gray-900 mb-1">{subject}</p>
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

    return (
        <div className="w-full">
            {title && (
                <h3 className="text-sm font-semibold text-gray-700 mb-2 text-center">
                    {title}
                </h3>
            )}
            <ResponsiveContainer width="100%" height={height}>
                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
                    <PolarGrid stroke="#E5E7EB" />
                    <RPolarAngleAxis
                        dataKey="subject"
                        tick={{ fontSize: 11, fill: '#4B5563' }}
                    />
                    <RPolarRadiusAxis
                        angle={30}
                        domain={[0, calculatedMax]}
                        tick={{ fontSize: 10 }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    {radars.map((radar) => (
                        <Radar
                            key={radar.dataKey}
                            name={radar.name}
                            dataKey={radar.dataKey}
                            stroke={radar.color}
                            fill={radar.color}
                            fillOpacity={radar.fillOpacity ?? 0.3}
                            strokeWidth={2}
                        />
                    ))}
                    {showLegend && (
                        <Legend
                            layout="horizontal"
                            verticalAlign="bottom"
                            align="center"
                            wrapperStyle={{ paddingTop: 20 }}
                        />
                    )}
                </RadarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default PatentRadarChart;

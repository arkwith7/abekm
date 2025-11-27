/**
 * PatentPieChart - 특허 분석용 파이 차트 컴포넌트
 * 출원인별 점유율, 기술분야별 분포 등 시각화
 */
import React from 'react';
import {
    Cell,
    Legend,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
} from 'recharts';

export interface PieChartData {
    name: string;
    value: number;
    color?: string;
}

interface PatentPieChartProps {
    data: PieChartData[];
    title?: string;
    height?: number;
    showLegend?: boolean;
    showLabels?: boolean;
    innerRadius?: number;
    outerRadius?: number;
}

// 기본 색상 팔레트
const DEFAULT_COLORS = [
    '#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8',
    '#82CA9D', '#FFC658', '#8DD1E1', '#A4DE6C', '#D0ED57',
];

const PatentPieChart: React.FC<PatentPieChartProps> = ({
    data,
    title,
    height = 300,
    showLegend = true,
    showLabels = true,
    innerRadius = 0,
    outerRadius = 80,
}) => {
    // 데이터에 색상이 없으면 기본 색상 할당
    const chartData = data.map((item, index) => ({
        ...item,
        color: item.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length],
    }));

    const renderCustomizedLabel = ({
        cx,
        cy,
        midAngle,
        innerRadius,
        outerRadius,
        percent,
        name,
    }: any) => {
        if (!showLabels || percent < 0.05) return null;

        const RADIAN = Math.PI / 180;
        const radius = innerRadius + (outerRadius - innerRadius) * 1.4;
        const x = cx + radius * Math.cos(-midAngle * RADIAN);
        const y = cy + radius * Math.sin(-midAngle * RADIAN);

        return (
            <text
                x={x}
                y={y}
                fill="#374151"
                textAnchor={x > cx ? 'start' : 'end'}
                dominantBaseline="central"
                className="text-xs"
            >
                {`${name} (${(percent * 100).toFixed(0)}%)`}
            </text>
        );
    };

    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            const data = payload[0].payload;
            return (
                <div className="bg-white px-3 py-2 shadow-lg rounded-lg border border-gray-200">
                    <p className="font-medium text-gray-900">{data.name}</p>
                    <p className="text-sm text-gray-600">
                        건수: <span className="font-semibold">{data.value.toLocaleString()}</span>
                    </p>
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
                <PieChart>
                    <Pie
                        data={chartData}
                        cx="50%"
                        cy="50%"
                        labelLine={showLabels}
                        label={renderCustomizedLabel}
                        innerRadius={innerRadius}
                        outerRadius={outerRadius}
                        paddingAngle={2}
                        dataKey="value"
                    >
                        {chartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    {showLegend && (
                        <Legend
                            layout="horizontal"
                            verticalAlign="bottom"
                            align="center"
                            wrapperStyle={{ paddingTop: 20 }}
                        />
                    )}
                </PieChart>
            </ResponsiveContainer>
        </div>
    );
};

export default PatentPieChart;

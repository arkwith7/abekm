/**
 * PatentNetworkGraph - 특허 인용관계 네트워크 그래프 컴포넌트
 * 특허 간 인용 관계, 기술 연관성 시각화
 */
import React, { useCallback, useEffect, useRef } from 'react';
import ForceGraph2D, { ForceGraphMethods, NodeObject } from 'react-force-graph-2d';

export interface NetworkNode {
    id: string;
    name: string;
    group?: string;
    value?: number;
    color?: string;
}

export interface NetworkLink {
    source: string;
    target: string;
    value?: number;
}

export interface NetworkGraphData {
    nodes: NetworkNode[];
    links: NetworkLink[];
}

interface PatentNetworkGraphProps {
    data: NetworkGraphData;
    title?: string;
    width?: number;
    height?: number;
    nodeSize?: number;
    showLabels?: boolean;
    onNodeClick?: (node: NetworkNode) => void;
}

// 그룹별 색상
const GROUP_COLORS: Record<string, string> = {
    'company': '#0088FE',
    'patent': '#00C49F',
    'technology': '#FFBB28',
    'applicant': '#FF8042',
    'citation': '#8884D8',
    'default': '#6B7280',
};

const PatentNetworkGraph: React.FC<PatentNetworkGraphProps> = ({
    data,
    title,
    width,
    height = 400,
    nodeSize = 8,
    showLabels = true,
    onNodeClick,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const graphRef = useRef<ForceGraphMethods>();
    const [dimensions, setDimensions] = React.useState({ width: 600, height: 400 });

    // 컨테이너 크기 감지
    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                setDimensions({
                    width: width || containerRef.current.offsetWidth,
                    height: height,
                });
            }
        };

        updateDimensions();
        window.addEventListener('resize', updateDimensions);
        return () => window.removeEventListener('resize', updateDimensions);
    }, [width, height]);

    // 초기 줌 레벨 설정
    useEffect(() => {
        if (graphRef.current) {
            graphRef.current.zoomToFit(400, 50);
        }
    }, [data]);

    const getNodeColor = useCallback((node: NodeObject) => {
        const n = node as unknown as NetworkNode;
        if (n.color) return n.color;
        return GROUP_COLORS[n.group || 'default'] || GROUP_COLORS.default;
    }, []);

    const getNodeSize = useCallback((node: NodeObject) => {
        const n = node as unknown as NetworkNode;
        return n.value ? Math.sqrt(n.value) * 2 + nodeSize : nodeSize;
    }, [nodeSize]);

    const handleNodeClick = useCallback((node: NodeObject) => {
        if (onNodeClick) {
            onNodeClick(node as unknown as NetworkNode);
        }
    }, [onNodeClick]);

    const nodeCanvasObject = useCallback((
        node: NodeObject,
        ctx: CanvasRenderingContext2D,
        globalScale: number
    ) => {
        const n = node as unknown as NetworkNode;
        const label = n.name;
        const fontSize = 12 / globalScale;
        const size = getNodeSize(node);
        const color = getNodeColor(node);

        // 노드 그리기
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5 / globalScale;
        ctx.stroke();

        // 라벨 그리기
        if (showLabels && globalScale > 0.5) {
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#374151';
            ctx.fillText(label, node.x!, node.y! + size + fontSize);
        }
    }, [getNodeColor, getNodeSize, showLabels]);

    if (!data.nodes.length) {
        return (
            <div className="w-full flex items-center justify-center" style={{ height }}>
                <p className="text-gray-500">네트워크 데이터가 없습니다</p>
            </div>
        );
    }

    return (
        <div className="w-full" ref={containerRef}>
            {title && (
                <h3 className="text-sm font-semibold text-gray-700 mb-2 text-center">
                    {title}
                </h3>
            )}
            <div className="border border-gray-200 rounded-lg overflow-hidden bg-gray-50">
                <ForceGraph2D
                    ref={graphRef}
                    graphData={data}
                    width={dimensions.width}
                    height={dimensions.height}
                    nodeCanvasObject={nodeCanvasObject}
                    nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                        const size = getNodeSize(node);
                        ctx.beginPath();
                        ctx.arc(node.x!, node.y!, size + 2, 0, 2 * Math.PI);
                        ctx.fillStyle = color;
                        ctx.fill();
                    }}
                    linkColor={() => '#CBD5E1'}
                    linkWidth={(link: any) => Math.sqrt((link as unknown as NetworkLink).value || 1)}
                    linkDirectionalArrowLength={4}
                    linkDirectionalArrowRelPos={1}
                    onNodeClick={handleNodeClick}
                    cooldownTicks={100}
                    d3AlphaDecay={0.02}
                    d3VelocityDecay={0.3}
                />
            </div>
            {/* 범례 */}
            <div className="flex flex-wrap gap-3 mt-3 justify-center">
                {Object.entries(GROUP_COLORS)
                    .filter(([key]) => key !== 'default')
                    .map(([key, color]) => (
                        <div key={key} className="flex items-center gap-1.5">
                            <div
                                className="w-3 h-3 rounded-full"
                                style={{ backgroundColor: color }}
                            />
                            <span className="text-xs text-gray-600 capitalize">{key}</span>
                        </div>
                    ))}
            </div>
        </div>
    );
};

export default PatentNetworkGraph;

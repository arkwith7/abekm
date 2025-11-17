import React, { useCallback, useEffect, useState } from 'react';
import { ContentSegment } from '../../../../../types/presentation';

interface Props {
    content: string;
    onSegmentChange: (segments: ContentSegment[]) => void;
    className?: string;
    // 클릭 모드 관련 props (다중 선택 지원)
    selectedSegments?: ContentSegment[];
    onSegmentClick?: (segment: ContentSegment) => void;
    useClickMode?: boolean;
}

const ContentSegmentationPanel: React.FC<Props> = ({
    content,
    onSegmentChange,
    className = '',
    selectedSegments = [],
    onSegmentClick,
    useClickMode = false
}) => {
    const [segments, setSegments] = useState<ContentSegment[]>([]);
    const [isAutoMode, setIsAutoMode] = useState(true);

    // 위치 제안 함수
    const suggestPosition = useCallback((type: string, priority: number): string => {
        switch (type) {
            case 'title':
                return priority > 8 ? 'top-center-header' : 'top-left-header';
            case 'bullet':
                return 'center';
            case 'table_data':
                return 'center';
            case 'paragraph':
                return priority > 6 ? 'middle-left-main' : 'middle-left-sub';
            default:
                return 'center';
        }
    }, []);

    // 자동 분할 함수
    const autoSegment = useCallback((text: string): ContentSegment[] => {
        if (!text.trim()) return [];

        const segments: ContentSegment[] = [];
        let segmentId = 1;

        // 줄바꿈으로 분할
        const lines = text.split('\n').filter(line => line.trim());

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            let type: 'paragraph' | 'title' | 'bullet' | 'table_data' = 'paragraph';
            let priority = 5; // 기본 우선도

            // 타입 분석
            if (trimmed.startsWith('#')) {
                type = 'title';
                priority = 9;
            } else if (trimmed.startsWith('-') || trimmed.startsWith('*') || trimmed.startsWith('•')) {
                type = 'bullet';
                priority = 6;
            } else if (trimmed.includes('|') || trimmed.includes('\t')) {
                type = 'table_data';
                priority = 7;
            } else if (trimmed.length < 50) {
                type = 'title';
                priority = 8;
            }

            segments.push({
                id: segmentId.toString(),
                content: trimmed,
                type,
                priority,
                suggestedPosition: suggestPosition(type, priority)
            });
            segmentId++;
        }

        return segments;
    }, [suggestPosition]);

    // content가 변경될 때 자동 분할
    useEffect(() => {
        if (isAutoMode && content) {
            const newSegments = autoSegment(content);
            setSegments(newSegments);
            onSegmentChange(newSegments);
        }
    }, [content, isAutoMode, autoSegment, onSegmentChange]);

    // 세그먼트 업데이트
    const updateSegment = (id: string, updates: Partial<ContentSegment>) => {
        const newSegments = segments.map(segment =>
            segment.id === id ? { ...segment, ...updates } : segment
        );
        setSegments(newSegments);
        onSegmentChange(newSegments);
    };

    // 세그먼트 삭제
    const removeSegment = (id: string) => {
        const newSegments = segments.filter(segment => segment.id !== id);
        setSegments(newSegments);
        onSegmentChange(newSegments);
    };

    // 우선도 변경
    const changePriority = (id: string, delta: number) => {
        updateSegment(id, {
            priority: Math.max(1, Math.min(10, (segments.find(s => s.id === id)?.priority || 5) + delta))
        });
    };

    const getTypeColor = (type: string) => {
        switch (type) {
            case 'title': return 'border-blue-300 bg-blue-50 text-blue-700';
            case 'bullet': return 'border-green-300 bg-green-50 text-green-700';
            case 'table_data': return 'border-purple-300 bg-purple-50 text-purple-700';
            default: return 'border-gray-300 bg-gray-50 text-gray-700';
        }
    };

    const getPriorityColor = (priority: number) => {
        if (priority >= 8) return 'bg-red-500';
        if (priority >= 6) return 'bg-orange-500';
        if (priority >= 4) return 'bg-yellow-500';
        return 'bg-gray-400';
    };

    return (
        <div className={`space-y-4 ${className}`}>
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">콘텐츠 분할</h3>
                <div className="flex items-center space-x-2">
                    <label className="flex items-center space-x-2">
                        <input
                            type="checkbox"
                            checked={isAutoMode}
                            onChange={(e) => setIsAutoMode(e.target.checked)}
                            className="rounded border-gray-300"
                        />
                        <span className="text-sm text-gray-600">자동 분할</span>
                    </label>
                </div>
            </div>

            {/* 클릭 모드 안내 */}
            {useClickMode && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <p className="text-sm text-green-800">
                        💡 <strong>세그먼트를 클릭</strong>하여 선택하세요. 선택된 세그먼트는 파란색으로 표시됩니다.
                    </p>
                </div>
            )}

            {/* 클릭 가능한 세그먼트 목록 */}
            <div className="space-y-3 max-h-96 overflow-y-auto">
                {segments.map((segment, index) => {
                    const isSelected = useClickMode && selectedSegments.some(s => s.id === segment.id);
                    return (
                        <div
                            key={segment.id}
                            onClick={() => useClickMode && onSegmentClick?.(segment)}
                            className={`border rounded-lg p-4 transition-all duration-200 ${useClickMode ? 'cursor-pointer' : ''
                                } ${isSelected
                                    ? 'border-blue-500 bg-blue-50 shadow-md ring-2 ring-blue-200'
                                    : 'border-gray-200 bg-white hover:shadow-sm hover:border-gray-300'
                                }`}
                        >
                            {/* 선택 표시 및 헤더 */}
                            <div className="flex items-center mb-2">
                                {useClickMode && (
                                    <div className={`w-3 h-3 rounded-full mr-3 ${isSelected ? 'bg-blue-500' : 'bg-gray-300'
                                        }`}></div>
                                )}

                                {/* 세그먼트 헤더 정보 */}
                                <div className="flex items-center space-x-2 flex-1">
                                    <span className="text-sm font-medium text-gray-500">
                                        #{index + 1}
                                    </span>
                                    <span className={`px-2 py-1 text-xs rounded border ${getTypeColor(segment.type)}`}>
                                        {segment.type}
                                    </span>
                                    <div className="flex items-center space-x-1">
                                        <span className="text-xs text-gray-500">우선도:</span>
                                        <div className="flex items-center space-x-1">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    changePriority(segment.id, -1);
                                                }}
                                                className="w-6 h-6 text-xs bg-gray-200 hover:bg-gray-300 rounded"
                                            >
                                                -
                                            </button>
                                            <div className="flex items-center space-x-1">
                                                <div
                                                    className={`w-3 h-3 rounded-full ${getPriorityColor(segment.priority)}`}
                                                />
                                                <span className="text-xs font-medium">{segment.priority}</span>
                                            </div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    changePriority(segment.id, 1);
                                                }}
                                                className="w-6 h-6 text-xs bg-gray-200 hover:bg-gray-300 rounded"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeSegment(segment.id);
                                    }}
                                    className="text-red-600 hover:text-red-800 text-sm"
                                >
                                    삭제
                                </button>
                            </div>

                            {/* 콘텐츠 편집 */}
                            <textarea
                                value={segment.content}
                                onChange={(e) => updateSegment(segment.id, { content: e.target.value })}
                                onClick={(e) => e.stopPropagation()}
                                className="w-full p-2 text-sm border border-gray-300 rounded resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                rows={3}
                                placeholder="세그먼트 내용을 입력하세요"
                            />

                            {/* 타입 및 위치 선택 */}
                            <div className="mt-2 flex items-center space-x-4">
                                <div className="flex items-center space-x-2">
                                    <label className="text-xs text-gray-600">타입:</label>
                                    <select
                                        value={segment.type}
                                        onChange={(e) => updateSegment(segment.id, {
                                            type: e.target.value as ContentSegment['type'],
                                            suggestedPosition: suggestPosition(e.target.value, segment.priority)
                                        })}
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-xs border border-gray-300 rounded px-2 py-1"
                                    >
                                        <option value="title">제목</option>
                                        <option value="paragraph">문단</option>
                                        <option value="bullet">불릿</option>
                                        <option value="table_data">표 데이터</option>
                                    </select>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <label className="text-xs text-gray-600">위치:</label>
                                    <select
                                        value={segment.suggestedPosition || 'center'}
                                        onChange={(e) => updateSegment(segment.id, { suggestedPosition: e.target.value })}
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-xs border border-gray-300 rounded px-2 py-1"
                                    >
                                        <option value="top-center-header">상단 중앙 헤더</option>
                                        <option value="top-left-header">상단 좌측 헤더</option>
                                        <option value="center">중앙</option>
                                        <option value="middle-left-main">중간 좌측 메인</option>
                                        <option value="middle-left-sub">중간 좌측 서브</option>
                                        <option value="bottom-center">하단 중앙</option>
                                    </select>
                                </div>
                            </div>

                            {/* 선택된 표시 */}
                            {isSelected && (
                                <div className="mt-2 text-xs text-blue-600 font-medium">
                                    ✓ 선택됨 - 텍스트박스를 클릭하여 매핑하세요
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {segments.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                    <p>분할할 콘텐츠가 없습니다.</p>
                    <p className="text-sm">AI 답변을 입력하면 자동으로 분할됩니다.</p>
                </div>
            )}
        </div>
    );
};

export default ContentSegmentationPanel;

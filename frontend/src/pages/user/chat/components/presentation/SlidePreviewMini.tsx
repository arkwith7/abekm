import React, { useState } from 'react';
import {
    ContentSegment,
    SimpleElement,
    SimpleSlide,
    TextBoxMapping
} from '../../../../../types/presentation';

// SVG 아이콘들
const ZoomInIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
    </svg>
);

const EditIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
);

const EyeIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
);

interface SlidePreviewMiniProps {
    slide: SimpleSlide;
    mappings: TextBoxMapping[];
    contentSegments: ContentSegment[];
    onElementClick?: (elementId: string) => void;
    className?: string;
    showControls?: boolean;
    isSelected?: boolean;
}

const SlidePreviewMini: React.FC<SlidePreviewMiniProps> = ({
    slide,
    mappings,
    contentSegments,
    onElementClick,
    className = '',
    showControls = true,
    isSelected = false
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [hoveredElementId, setHoveredElementId] = useState<string | null>(null);

    // 매핑된 콘텐츠 가져오기
    const getMappedContent = (elementId: string): string => {
        const mapping = mappings.find(m =>
            m.elementId === elementId && m.slideIndex === slide.pageNumber - 1
        );

        if (!mapping?.assignedContent) return '';

        const segment = contentSegments.find(s => s.id === mapping.assignedContent);
        return segment?.content || '';
    };

    // 요소별 위치 스타일 계산
    const getElementPositionStyle = (element: SimpleElement): React.CSSProperties => {
        const baseStyles: React.CSSProperties = {
            position: 'absolute',
            fontSize: '6px', // 미니 버전용 작은 폰트
            lineHeight: '1.2',
            overflow: 'hidden',
            wordBreak: 'break-word',
            borderRadius: '2px',
            cursor: onElementClick ? 'pointer' : 'default'
        };

        // 위치별 스타일 매핑 (슬라이드 비율 16:9 기준)
        switch (element.position) {
            case 'center':
                return {
                    ...baseStyles,
                    top: '30%',
                    left: '10%',
                    width: '80%',
                    height: '40%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    fontWeight: 'bold'
                };

            case 'top-center-header':
                return {
                    ...baseStyles,
                    top: '5%',
                    left: '10%',
                    width: '80%',
                    height: '20%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    fontWeight: 'bold',
                    fontSize: '8px'
                };

            case 'top-center-subtitle':
                return {
                    ...baseStyles,
                    top: '25%',
                    left: '15%',
                    width: '70%',
                    height: '15%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center'
                };

            case 'top-left-header':
                return {
                    ...baseStyles,
                    top: '5%',
                    left: '5%',
                    width: '40%',
                    height: '20%',
                    fontWeight: 'bold',
                    fontSize: '7px'
                };

            case 'middle-left-main':
                return {
                    ...baseStyles,
                    top: '30%',
                    left: '5%',
                    width: '50%',
                    height: '40%'
                };

            case 'middle-left-sub':
                return {
                    ...baseStyles,
                    top: '50%',
                    left: '5%',
                    width: '50%',
                    height: '25%',
                    fontSize: '5px'
                };

            case 'right-half':
                return {
                    ...baseStyles,
                    top: '20%',
                    left: '55%',
                    width: '40%',
                    height: '60%',
                    border: '1px dashed #ccc',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '5px',
                    color: '#666'
                };

            case 'bottom-center':
                return {
                    ...baseStyles,
                    top: '80%',
                    left: '20%',
                    width: '60%',
                    height: '15%',
                    textAlign: 'center',
                    fontSize: '5px'
                };

            case 'bottom-left':
                return {
                    ...baseStyles,
                    top: '85%',
                    left: '5%',
                    width: '30%',
                    height: '10%',
                    fontSize: '4px'
                };

            case 'bottom-right':
                return {
                    ...baseStyles,
                    top: '85%',
                    left: '65%',
                    width: '30%',
                    height: '10%',
                    textAlign: 'right',
                    fontSize: '4px'
                };

            default:
                return {
                    ...baseStyles,
                    top: '10%',
                    left: '10%',
                    width: '80%',
                    height: '20%'
                };
        }
    };

    // 요소별 배경색 결정 (매핑 상태에 따라)
    const getElementBackgroundColor = (elementId: string): string => {
        const mapping = mappings.find(m =>
            m.elementId === elementId && m.slideIndex === slide.pageNumber - 1
        );

        if (mapping?.assignedContent) {
            return hoveredElementId === elementId ? '#dcfce7' : '#f0fdf4'; // 연한 녹색
        }

        return hoveredElementId === elementId ? '#fef3c7' : '#fffbeb'; // 연한 노랑
    };

    // 콘텐츠 미리보기 (짧게 자르기)
    const getPreviewContent = (element: SimpleElement): string => {
        const mappedContent = getMappedContent(element.id);
        const content = mappedContent || element.content || '';

        if (!content) {
            if (element.type === 'image') return '[이미지]';
            if (element.type === 'table') return '[표]';
            if (element.type === 'chart') return '[차트]';
            return '[빈 텍스트박스]';
        }

        // 미니 프리뷰용으로 짧게 자르기
        const maxLength = isExpanded ? 50 : 20;
        return content.length > maxLength
            ? content.substring(0, maxLength) + '...'
            : content;
    };

    return (
        <div className={`
      relative bg-white border rounded-lg overflow-hidden transition-all duration-200
      ${isSelected ? 'border-blue-400 ring-2 ring-blue-100' : 'border-gray-200 hover:border-gray-300'}
      ${className}
    `}>
            {/* 슬라이드 헤더 */}
            <div className="flex items-center justify-between p-2 bg-gray-50 border-b">
                <div className="flex items-center space-x-2">
                    <span className="text-xs font-medium text-gray-700">
                        슬라이드 {slide.pageNumber}
                    </span>
                    <span className="text-xs text-gray-500">
                        {slide.layout}
                    </span>
                </div>

                {showControls && (
                    <div className="flex items-center space-x-1">
                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="p-1 text-gray-500 hover:text-gray-700 hover:bg-white rounded"
                            title={isExpanded ? "축소" : "확대"}
                        >
                            {isExpanded ? <EyeIcon className="w-3 h-3" /> : <ZoomInIcon className="w-3 h-3" />}
                        </button>
                    </div>
                )}
            </div>

            {/* 슬라이드 미니어처 */}
            <div
                className={`relative bg-gradient-to-br from-gray-50 to-white transition-all duration-200 ${isExpanded ? 'h-48' : 'h-24'
                    }`}
                style={{ aspectRatio: '16/9' }}
            >
                {/* 레이아웃 가이드라인 (옅은 격자) */}
                <div className="absolute inset-0 opacity-10">
                    <div className="absolute top-1/3 left-0 w-full h-px bg-gray-300"></div>
                    <div className="absolute top-2/3 left-0 w-full h-px bg-gray-300"></div>
                    <div className="absolute left-1/3 top-0 w-px h-full bg-gray-300"></div>
                    <div className="absolute left-2/3 top-0 w-px h-full bg-gray-300"></div>
                </div>

                {/* 슬라이드 요소들 */}
                {slide.elements.map((element) => {
                    const isTextbox = element.type === 'textbox';
                    const isMapped = !!getMappedContent(element.id);

                    return (
                        <div
                            key={element.id}
                            style={{
                                ...getElementPositionStyle(element),
                                backgroundColor: isTextbox ? getElementBackgroundColor(element.id) : 'transparent',
                                border: isTextbox ? `1px solid ${isMapped ? '#22c55e' : '#f59e0b'}` : 'none'
                            }}
                            onClick={() => onElementClick?.(element.id)}
                            onMouseEnter={() => setHoveredElementId(element.id)}
                            onMouseLeave={() => setHoveredElementId(null)}
                            title={isTextbox ? `${element.position} - ${isMapped ? '매핑됨' : '미매핑'}` : element.type}
                        >
                            {/* 요소 타입 표시 (텍스트박스가 아닌 경우) */}
                            {!isTextbox && (
                                <div className="w-full h-full flex items-center justify-center bg-gray-100 border border-dashed border-gray-300 text-gray-500">
                                    <span style={{ fontSize: '4px' }}>
                                        {element.type.toUpperCase()}
                                    </span>
                                </div>
                            )}

                            {/* 텍스트 콘텐츠 */}
                            {isTextbox && (
                                <>
                                    <div className="w-full h-full overflow-hidden">
                                        {getPreviewContent(element)}
                                    </div>

                                    {/* 매핑 상태 표시 (작은 아이콘) */}
                                    <div className="absolute top-0 right-0 w-2 h-2 rounded-full transform translate-x-1 -translate-y-1">
                                        <div className={`w-full h-full rounded-full ${isMapped ? 'bg-green-500' : 'bg-yellow-500'
                                            }`}></div>
                                    </div>
                                </>
                            )}

                            {/* 호버 시 편집 아이콘 */}
                            {hoveredElementId === element.id && onElementClick && isTextbox && (
                                <div className="absolute top-0 left-0 w-3 h-3 bg-blue-500 rounded-br flex items-center justify-center transform -translate-x-1 -translate-y-1">
                                    <EditIcon className="w-2 h-2 text-white" />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* 확장 상태일 때 추가 정보 */}
            {isExpanded && (
                <div className="p-2 bg-gray-50 border-t space-y-1">
                    <div className="text-xs text-gray-600">
                        <span className="font-medium">요소:</span> {slide.elements.length}개
                    </div>

                    <div className="text-xs text-gray-600">
                        <span className="font-medium">매핑 완료:</span>{' '}
                        {mappings.filter(m => m.slideIndex === slide.pageNumber - 1).length}/
                        {slide.elements.filter(e => e.type === 'textbox').length}
                    </div>

                    {/* 매핑 상태별 요약 */}
                    <div className="flex items-center space-x-2 text-xs">
                        <div className="flex items-center space-x-1">
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                            <span className="text-gray-600">매핑됨</span>
                        </div>
                        <div className="flex items-center space-x-1">
                            <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                            <span className="text-gray-600">미매핑</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default SlidePreviewMini;

/**
 * Template Slide Preview Component
 * 
 * 템플릿 슬라이드의 듀얼 프리뷰 제공:
 * - Edit View: 속성 기반 편집 뷰
 * - Design View: PDF 기반 디자인 뷰
 * 
 * v2.0 - Human in the Loop 워크플로우 지원
 */
import { ChevronLeft, ChevronRight, Edit, Eye, ZoomIn, ZoomOut } from 'lucide-react';
import React, { useState } from 'react';

// 타입 정의
interface SlidePreviewInfo {
    slide_index: number;
    preview_url: string;
    thumbnail_url: string;
    width?: number;
    height?: number;
}

interface SlideElement {
    id: string;
    content: string;
    type: string;
    position: {
        left: number;
        top: number;
        width: number;
        height: number;
    };
    fontFamily?: string;
    fontSize?: number | null;
    color?: string;
    fontWeight?: string;
    is_fixed?: boolean;
    fixed_reason?: string | null;
    element_role?: string;
}

interface SlideMapping {
    template_slide: number;
    outline_slide: number;
    action: 'ai_content' | 'keep_original' | 'skip';
    confidence: number;
    ai_content: {
        title?: string;
        key_message?: string;
        bullets?: string[];
    };
    element_mappings: Array<{
        element_id: string;
        element_role: string;
        original_content: string;
        new_content: string;
        is_editable: boolean;
    }>;
}

interface TemplateSlidePreviewProps {
    templateId: string;
    slides: SlidePreviewInfo[];
    metadata?: {
        slides: Array<{
            index: number;
            role?: string;
            elements: SlideElement[];
            editable_elements?: string[];
            fixed_elements?: string[];
        }>;
    };
    mappings?: SlideMapping[];
    onMappingChange?: (slideIndex: number, elementId: string, newContent: string) => void;
    onActionChange?: (slideIndex: number, action: 'ai_content' | 'keep_original' | 'skip') => void;
    authToken?: string;
    className?: string;
}

const TemplateSlidePreview: React.FC<TemplateSlidePreviewProps> = ({
    templateId,
    slides,
    metadata,
    mappings,
    onMappingChange,
    onActionChange,
    authToken,
    className = ''
}) => {
    const [currentSlide, setCurrentSlide] = useState(1);
    const [viewMode, setViewMode] = useState<'edit' | 'design'>('design');
    const [zoom, setZoom] = useState(100);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const [, setIsLoading] = useState(false);  // 향후 로딩 상태 표시용
    const [, setPreviewError] = useState<string | null>(null);  // 향후 오류 표시용

    const totalSlides = slides.length;
    const currentSlideInfo = slides.find(s => s.slide_index === currentSlide);
    const currentMetadata = metadata?.slides?.find(s => s.index === currentSlide);
    const currentMapping = mappings?.find(m => m.template_slide === currentSlide);

    // 슬라이드 네비게이션
    const goToSlide = (index: number) => {
        if (index >= 1 && index <= totalSlides) {
            setCurrentSlide(index);
        }
    };

    const nextSlide = () => goToSlide(currentSlide + 1);
    const prevSlide = () => goToSlide(currentSlide - 1);

    // 줌 조절
    const zoomIn = () => setZoom(Math.min(zoom + 25, 200));
    const zoomOut = () => setZoom(Math.max(zoom - 25, 50));

    // 액션 변경 핸들러
    const handleActionChange = (action: 'ai_content' | 'keep_original' | 'skip') => {
        if (onActionChange) {
            onActionChange(currentSlide, action);
        }
    };

    // 콘텐츠 변경 핸들러
    const handleContentChange = (elementId: string, newContent: string) => {
        if (onMappingChange) {
            onMappingChange(currentSlide, elementId, newContent);
        }
    };

    // 이미지 URL에 토큰 추가
    const getImageUrl = (url: string) => {
        if (!url) return '';
        const separator = url.includes('?') ? '&' : '?';
        return authToken ? `${url}${separator}token=${authToken}` : url;
    };

    // 역할에 따른 배지 색상
    const getRoleBadgeColor = (role?: string) => {
        switch (role) {
            case 'title': return 'bg-purple-100 text-purple-700';
            case 'toc': return 'bg-blue-100 text-blue-700';
            case 'content': return 'bg-green-100 text-green-700';
            case 'thanks': return 'bg-orange-100 text-orange-700';
            default: return 'bg-gray-100 text-gray-700';
        }
    };

    // 액션에 따른 배지 색상
    const getActionBadgeColor = (action?: string) => {
        switch (action) {
            case 'ai_content': return 'bg-blue-500 text-white';
            case 'keep_original': return 'bg-gray-500 text-white';
            case 'skip': return 'bg-red-500 text-white';
            default: return 'bg-gray-200 text-gray-600';
        }
    };

    return (
        <div className={`flex flex-col h-full bg-white rounded-lg shadow ${className}`}>
            {/* 헤더: 뷰 모드 토글 및 페이지 네비게이션 */}
            <div className="flex items-center justify-between px-4 py-2 border-b bg-gray-50 flex-shrink-0">
                {/* 뷰 모드 토글 */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setViewMode('design')}
                        className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 text-sm transition-colors ${viewMode === 'design'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                            }`}
                    >
                        <Eye size={14} />
                        디자인
                    </button>
                    <button
                        onClick={() => setViewMode('edit')}
                        className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 text-sm transition-colors ${viewMode === 'edit'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                            }`}
                    >
                        <Edit size={14} />
                        편집
                    </button>

                    {/* 페이지 네비게이션 - 편집 버튼 오른쪽 */}
                    <div className="flex items-center gap-1 ml-4 border-l pl-4">
                        <button
                            onClick={prevSlide}
                            disabled={currentSlide <= 1}
                            className={`p-1.5 rounded ${currentSlide <= 1 ? 'text-gray-300 cursor-not-allowed' : 'hover:bg-gray-200 text-gray-600'}`}
                        >
                            <ChevronLeft size={18} />
                        </button>
                        <span className="text-sm text-gray-700 min-w-[50px] text-center font-medium">
                            {currentSlide} / {totalSlides}
                        </span>
                        <button
                            onClick={nextSlide}
                            disabled={currentSlide >= totalSlides}
                            className={`p-1.5 rounded ${currentSlide >= totalSlides ? 'text-gray-300 cursor-not-allowed' : 'hover:bg-gray-200 text-gray-600'}`}
                        >
                            <ChevronRight size={18} />
                        </button>
                    </div>
                </div>

                {/* 슬라이드 역할 정보 */}
                <div className="flex items-center gap-2">
                    {currentMetadata?.role && (
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getRoleBadgeColor(currentMetadata.role)}`}>
                            {currentMetadata.role}
                        </span>
                    )}
                    {currentMapping && (
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getActionBadgeColor(currentMapping.action)}`}>
                            {currentMapping.action === 'ai_content' ? 'AI 콘텐츠' :
                                currentMapping.action === 'keep_original' ? '원본 유지' : '건너뛰기'}
                        </span>
                    )}
                </div>

                {/* 줌 컨트롤 */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={zoomOut}
                        className="p-1.5 rounded hover:bg-gray-200"
                        title="축소"
                    >
                        <ZoomOut size={16} />
                    </button>
                    <span className="text-sm text-gray-600 w-12 text-center">{zoom}%</span>
                    <button
                        onClick={zoomIn}
                        className="p-1.5 rounded hover:bg-gray-200"
                        title="확대"
                    >
                        <ZoomIn size={16} />
                    </button>
                </div>
            </div>

            {/* 메인 콘텐츠 영역 */}
            <div className="flex-1 flex min-h-0">
                {/* 왼쪽: 썸네일 패널 - 스크롤 가능 */}
                <div className="w-32 border-r bg-gray-50 overflow-y-auto p-2 space-y-2 flex-shrink-0">
                    {slides.map((slide) => {
                        const slideMapping = mappings?.find(m => m.template_slide === slide.slide_index);
                        const isActive = slide.slide_index === currentSlide;

                        return (
                            <div
                                key={slide.slide_index}
                                onClick={() => goToSlide(slide.slide_index)}
                                className={`cursor-pointer rounded-md overflow-hidden border-2 transition-all ${isActive
                                    ? 'border-blue-500 ring-2 ring-blue-200'
                                    : 'border-transparent hover:border-gray-300'
                                    } ${slideMapping?.action === 'skip' ? 'opacity-50' : ''}`}
                            >
                                <img
                                    src={getImageUrl(slide.thumbnail_url)}
                                    alt={`슬라이드 ${slide.slide_index}`}
                                    className="w-full h-auto"
                                    onError={(e) => {
                                        (e.target as HTMLImageElement).src = '/placeholder-slide.png';
                                    }}
                                />
                                <div className="text-xs text-center py-1 bg-gray-100">
                                    {slide.slide_index}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* 메인 프리뷰 영역 - 슬라이드 전체 표시 */}
                <div className="flex-1 p-2 flex items-center justify-center bg-gray-100 overflow-hidden">
                    {viewMode === 'design' ? (
                        /* Design View: PDF/이미지 기반 프리뷰 */
                        <div
                            className="w-full h-full flex items-center justify-center"
                            style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'center center' }}
                        >
                            {currentSlideInfo ? (
                                <img
                                    src={getImageUrl(currentSlideInfo.preview_url)}
                                    alt={`슬라이드 ${currentSlide} 프리뷰`}
                                    className="max-w-full max-h-full object-contain shadow-xl rounded-lg"
                                    onError={() => setPreviewError('프리뷰 이미지를 로드할 수 없습니다')}
                                />
                            ) : (
                                <div className="text-gray-500">프리뷰를 불러오는 중...</div>
                            )}
                        </div>
                    ) : (
                        /* Edit View: 속성 기반 편집 뷰 */
                        <div className="max-w-2xl mx-auto space-y-4 overflow-y-auto max-h-full">
                            {/* 액션 선택 */}
                            {onActionChange && (
                                <div className="bg-gray-50 rounded-lg p-4">
                                    <h4 className="text-sm font-medium text-gray-700 mb-3">슬라이드 액션</h4>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => handleActionChange('ai_content')}
                                            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${currentMapping?.action === 'ai_content'
                                                ? 'bg-blue-500 text-white'
                                                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                                                }`}
                                        >
                                            AI 콘텐츠 적용
                                        </button>
                                        <button
                                            onClick={() => handleActionChange('keep_original')}
                                            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${currentMapping?.action === 'keep_original'
                                                ? 'bg-gray-500 text-white'
                                                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                                                }`}
                                        >
                                            원본 유지
                                        </button>
                                        <button
                                            onClick={() => handleActionChange('skip')}
                                            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${currentMapping?.action === 'skip'
                                                ? 'bg-red-500 text-white'
                                                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                                                }`}
                                        >
                                            건너뛰기
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* 요소별 편집 */}
                            {currentMapping?.action === 'ai_content' && currentMapping.element_mappings && (
                                <div className="space-y-3">
                                    <h4 className="text-sm font-medium text-gray-700">콘텐츠 편집</h4>
                                    {currentMapping.element_mappings
                                        .filter(em => em.is_editable)
                                        .map((elem) => (
                                            <div key={elem.element_id} className="bg-white border rounded-lg p-3">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className="text-xs font-medium text-gray-500">
                                                        {elem.element_role || '콘텐츠'}
                                                    </span>
                                                    {elem.original_content && (
                                                        <span className="text-xs text-gray-400">
                                                            (원본: {elem.original_content.slice(0, 30)}...)
                                                        </span>
                                                    )}
                                                </div>
                                                <textarea
                                                    value={elem.new_content}
                                                    onChange={(e) => handleContentChange(elem.element_id, e.target.value)}
                                                    className="w-full px-3 py-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                    rows={elem.element_role === 'body' ? 4 : 2}
                                                    placeholder={`${elem.element_role || '콘텐츠'} 입력...`}
                                                />
                                            </div>
                                        ))}
                                </div>
                            )}

                            {/* 고정 요소 표시 */}
                            {currentMetadata?.fixed_elements && currentMetadata.fixed_elements.length > 0 && (
                                <div className="bg-gray-50 rounded-lg p-3">
                                    <h4 className="text-xs font-medium text-gray-500 mb-2">고정 요소 (편집 불가)</h4>
                                    <div className="flex flex-wrap gap-1">
                                        {currentMetadata.fixed_elements.map((elemId) => (
                                            <span
                                                key={elemId}
                                                className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded"
                                            >
                                                {elemId}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* 푸터: 슬라이드 네비게이션 */}
            <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
                <button
                    onClick={prevSlide}
                    disabled={currentSlide <= 1}
                    className={`px-3 py-1.5 rounded-md flex items-center gap-1 text-sm ${currentSlide <= 1
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                >
                    <ChevronLeft size={16} />
                    이전
                </button>

                <div className="flex items-center gap-2">
                    <input
                        type="number"
                        min={1}
                        max={totalSlides}
                        value={currentSlide}
                        onChange={(e) => goToSlide(parseInt(e.target.value) || 1)}
                        className="w-12 px-2 py-1 text-center border rounded text-sm"
                    />
                    <span className="text-sm text-gray-600">/ {totalSlides}</span>
                </div>

                <button
                    onClick={nextSlide}
                    disabled={currentSlide >= totalSlides}
                    className={`px-3 py-1.5 rounded-md flex items-center gap-1 text-sm ${currentSlide >= totalSlides
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                >
                    다음
                    <ChevronRight size={16} />
                </button>
            </div>
        </div>
    );
};

export default TemplateSlidePreview;

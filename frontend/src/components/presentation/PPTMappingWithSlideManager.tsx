import { ChevronLeft, ChevronRight, Grid, Settings } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { TextBoxMapping } from '../../types/presentation';
import PPTObjectMappingEditor from './PPTObjectMappingEditor';
import SlideManager, { SlideInfo } from './SlideManager';

interface PPTMappingWithSlideManagerProps {
    templateData: any; // 전체 템플릿 데이터
    contentSegments: any[];
    mappings: TextBoxMapping[];
    onMappingChange: (mappings: TextBoxMapping[]) => void;
    onSlideManagementChange?: (slideManagement: any[]) => void; // 슬라이드 관리 정보 변경 콜백
    className?: string;
}

const PPTMappingWithSlideManager: React.FC<PPTMappingWithSlideManagerProps> = ({
    templateData,
    contentSegments,
    mappings,
    onMappingChange,
    onSlideManagementChange,
    className = ''
}) => {
    const [currentSlide, setCurrentSlide] = useState(0);
    const [slides, setSlides] = useState<SlideInfo[]>([]);
    const [viewMode, setViewMode] = useState<'slide-by-slide' | 'overview'>('slide-by-slide');

    // 템플릿 데이터가 변경되면 슬라이드 정보 초기화
    useEffect(() => {
        if (!templateData?.slides) return;

        const initialSlides: SlideInfo[] = templateData.slides.map((slide: any, index: number) => ({
            index,
            originalIndex: index,
            title: slide.title || `슬라이드 ${index + 1}`,
            isEnabled: true,
            isVisible: true,
            objects: slide.elements || [] // 슬라이드의 오브젝트 정보 포함
        }));

        setSlides(initialSlides);

        // 초기 슬라이드 관리 정보를 부모에게 전달
        if (onSlideManagementChange) {
            const slideManagement = initialSlides.map(slide => ({
                index: slide.index,
                original_index: slide.originalIndex,
                base_slide_index: slide.base_slide_index, // 추가: 기반 슬라이드 인덱스
                title: slide.title,
                is_enabled: slide.isEnabled,
                is_visible: slide.isVisible
            }));
            console.log('🔄 초기 슬라이드 관리 정보 전달:', slideManagement);
            onSlideManagementChange(slideManagement);
        }
    }, [templateData, onSlideManagementChange]);

    // 슬라이드 업데이트 처리
    const handleSlidesUpdate = (newSlides: SlideInfo[]) => {
        setSlides(newSlides);

        // 슬라이드 관리 정보를 부모에게 전달
        if (onSlideManagementChange) {
            const slideManagement = newSlides.map(slide => ({
                index: slide.index,
                original_index: slide.originalIndex,
                base_slide_index: slide.base_slide_index, // 추가: 기반 슬라이드 인덱스
                title: slide.title,
                is_enabled: slide.isEnabled,
                is_visible: slide.isVisible
            }));
            console.log('🔄 슬라이드 관리 정보 업데이트:', slideManagement);
            onSlideManagementChange(slideManagement);
        }

        // 매핑 데이터 조정 (새 슬라이드 추가로 인한 인덱스 변경 반영)
        const updatedMappings = mappings.map(mapping => {
            // 기존 매핑의 슬라이드 인덱스를 새로운 슬라이드 배열에서 찾기
            const oldSlideInfo = slides[mapping.slideIndex];
            if (!oldSlideInfo) return mapping;

            // 원본 인덱스를 기준으로 새 배열에서 해당 슬라이드 찾기
            const newSlideInfo = newSlides.find(slide => {
                // 복사본이 아닌 원본 슬라이드 매칭
                return slide.originalIndex === oldSlideInfo.originalIndex &&
                    !slide.title?.includes('복사본') &&
                    !slide.title?.includes('새 슬라이드');
            });

            if (newSlideInfo && newSlideInfo.index !== mapping.slideIndex) {
                console.log(`🔧 매핑 인덱스 조정: ${mapping.elementId} - ${mapping.slideIndex} → ${newSlideInfo.index}`);
                return {
                    ...mapping,
                    slideIndex: newSlideInfo.index
                };
            }

            return mapping;
        }).filter(mapping => {
            // 유효한 슬라이드 인덱스를 가진 매핑만 유지
            return mapping.slideIndex < newSlides.length;
        });

        console.log(`🔧 매핑 조정: ${mappings.length}개 → ${updatedMappings.length}개 (복사본 슬라이드 매핑 제외)`);
        onMappingChange(updatedMappings);

        // 현재 슬라이드가 삭제되었거나 범위를 벗어난 경우 조정
        if (currentSlide >= newSlides.length) {
            setCurrentSlide(Math.max(0, newSlides.length - 1));
        }
    };

    // 슬라이드 네비게이션
    const goToSlide = (slideIndex: number) => {
        if (slideIndex >= 0 && slideIndex < slides.length) {
            setCurrentSlide(slideIndex);
        }
    };

    const goToPrevSlide = () => {
        if (currentSlide > 0) {
            setCurrentSlide(currentSlide - 1);
        }
    };

    const goToNextSlide = () => {
        if (currentSlide < slides.length - 1) {
            setCurrentSlide(currentSlide + 1);
        }
    };

    // 현재 슬라이드 데이터 가져오기
    const getCurrentSlideData = () => {
        if (!slides[currentSlide]) return null;

        const currentSlideInfo = slides[currentSlide];

        // 새로 추가된 슬라이드인 경우 (originalIndex가 없거나 템플릿 범위를 벗어남)
        if (!currentSlideInfo.originalIndex && currentSlideInfo.originalIndex !== 0 && currentSlideInfo.objects) {
            // 새 슬라이드의 경우 SlideInfo의 objects 정보 사용
            return {
                title: currentSlideInfo.title,
                elements: currentSlideInfo.objects,
                slideInfo: currentSlideInfo
            };
        }

        // 기존 템플릿 슬라이드인 경우
        if (templateData?.slides) {
            const originalSlideData = templateData.slides[currentSlideInfo.originalIndex || currentSlideInfo.index];

            return {
                ...originalSlideData,
                slideInfo: currentSlideInfo
            };
        }

        return null;
    };

    // 현재 슬라이드의 매핑 필터링
    const getCurrentSlideMappings = () => {
        return mappings.filter(mapping => mapping.slideIndex === currentSlide);
    };

    const currentSlideData = getCurrentSlideData();

    return (
        <div className={`ppt-mapping-with-slide-manager ${className}`}>
            {/* 상단 컨트롤바 */}
            <div className="flex items-center justify-between p-4 border-b bg-gray-50">
                <div className="flex items-center gap-4">
                    <h2 className="text-lg font-semibold">PPT 매핑 편집</h2>

                    {/* 뷰 모드 스위치 */}
                    <div className="flex items-center gap-2 bg-white border rounded-lg p-1">
                        <button
                            onClick={() => setViewMode('slide-by-slide')}
                            className={`px-3 py-1 rounded text-sm flex items-center gap-1 ${viewMode === 'slide-by-slide'
                                ? 'bg-blue-500 text-white'
                                : 'text-gray-600 hover:text-gray-800'
                                }`}
                        >
                            <Settings className="h-4 w-4" />
                            슬라이드별
                        </button>
                        <button
                            onClick={() => setViewMode('overview')}
                            className={`px-3 py-1 rounded text-sm flex items-center gap-1 ${viewMode === 'overview'
                                ? 'bg-blue-500 text-white'
                                : 'text-gray-600 hover:text-gray-800'
                                }`}
                        >
                            <Grid className="h-4 w-4" />
                            전체보기
                        </button>
                    </div>
                </div>

                {/* 슬라이드 네비게이션 (슬라이드별 모드일 때) */}
                {viewMode === 'slide-by-slide' && (
                    <div className="flex items-center gap-2">
                        <button
                            onClick={goToPrevSlide}
                            disabled={currentSlide === 0}
                            className="p-2 border rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </button>

                        <span className="text-sm font-medium px-3 py-1 bg-white border rounded">
                            {currentSlide + 1} / {slides.length}
                        </span>

                        <button
                            onClick={goToNextSlide}
                            disabled={currentSlide === slides.length - 1}
                            className="p-2 border rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <ChevronRight className="h-4 w-4" />
                        </button>
                    </div>
                )}
            </div>

            <div className="flex h-full">
                {/* 왼쪽: 슬라이드 관리자 - 40% 너비 */}
                <div className="flex-none w-2/5 border-r bg-gray-50">
                    <SlideManager
                        slides={slides}
                        currentSlide={currentSlide}
                        onSlideChange={goToSlide}
                        onSlidesUpdate={handleSlidesUpdate}
                        templateData={templateData}
                        maxSlides={20}
                    />
                </div>

                {/* 오른쪽: 매핑 편집기 - 60% 너비 */}
                <div className="flex-none w-3/5 overflow-auto">
                    {viewMode === 'slide-by-slide' ? (
                        // 슬라이드별 편집 모드
                        currentSlideData ? (
                            <div className="p-6">
                                {/* 매핑 편집기 */}
                                <PPTObjectMappingEditor
                                    slideIndex={currentSlide}
                                    slideData={currentSlideData}
                                    contentSegments={contentSegments}
                                    mappings={getCurrentSlideMappings()}
                                    onMappingChange={(updatedMappings) => {
                                        // 다른 슬라이드 매핑은 유지하고 현재 슬라이드만 업데이트
                                        const otherSlidesMappings = mappings.filter(
                                            mapping => mapping.slideIndex !== currentSlide
                                        );
                                        onMappingChange([...otherSlidesMappings, ...updatedMappings]);
                                    }}
                                />
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-full text-gray-500">
                                <div className="text-center">
                                    <p className="text-lg mb-2">슬라이드를 선택해주세요</p>
                                    <p className="text-sm">왼쪽 슬라이드 목록에서 편집할 슬라이드를 선택하세요</p>
                                </div>
                            </div>
                        )
                    ) : (
                        // 전체보기 모드
                        <div className="p-6">
                            <div className="grid gap-6">
                                {slides.map((slide, index) => (
                                    <div key={slide.index} className="border rounded-lg p-4">
                                        <div className="flex items-center justify-between mb-4">
                                            <h3 className="font-semibold">
                                                {slide.title} ({index + 1}/{slides.length})
                                            </h3>
                                            <button
                                                onClick={() => {
                                                    setCurrentSlide(index);
                                                    setViewMode('slide-by-slide');
                                                }}
                                                className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
                                            >
                                                편집하기
                                            </button>
                                        </div>

                                        {templateData?.slides?.[slide.originalIndex || index] && (
                                            <PPTObjectMappingEditor
                                                slideIndex={index}
                                                slideData={templateData.slides[slide.originalIndex || index]}
                                                contentSegments={contentSegments}
                                                mappings={mappings.filter(mapping => mapping.slideIndex === index)}
                                                onMappingChange={(updatedMappings) => {
                                                    const otherSlidesMappings = mappings.filter(
                                                        mapping => mapping.slideIndex !== index
                                                    );
                                                    onMappingChange([...otherSlidesMappings, ...updatedMappings]);
                                                }}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default PPTMappingWithSlideManager;

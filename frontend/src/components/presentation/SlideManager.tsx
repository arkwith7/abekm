import {
    ChevronDown,
    ChevronUp,
    Copy,
    Eye,
    EyeOff,
    FileImage,
    GripVertical,
    Plus,
    Trash2
} from 'lucide-react';
import React, { useState } from 'react';

// 슬라이드 데이터 타입 정의
export interface SlideInfo {
    index: number;
    originalIndex?: number; // 원본 템플릿에서의 인덱스
    base_slide_index?: number; // 새 슬라이드 생성 시 기반이 되는 슬라이드 인덱스
    title?: string;
    thumbnail?: string;
    isEnabled: boolean;
    isVisible: boolean; // 미리보기 표시 여부
    objects?: any[]; // 슬라이드 내 오브젝트들
    needsTextClear?: boolean; // 🆕 "추가" 버튼으로 생성되어 텍스트 클리어가 필요한지 표시
}

export interface SlideManagerProps {
    slides: SlideInfo[];
    currentSlide: number;
    onSlideChange: (slideIndex: number) => void;
    onSlidesUpdate: (newSlides: SlideInfo[]) => void;
    templateData?: any; // 추가: 템플릿 데이터
    maxSlides?: number;
}

const SlideManager: React.FC<SlideManagerProps> = ({
    slides,
    currentSlide,
    onSlideChange,
    onSlidesUpdate,
    templateData,
    maxSlides = 20
}) => {
    const [draggedSlide, setDraggedSlide] = useState<number | null>(null);
    const [showPreview, setShowPreview] = useState(false);

    // 슬라이드 복사 (텍스트 내용 유지)
    const duplicateSlide = (slideIndex: number) => {
        if (slides.length >= maxSlides) {
            alert(`최대 ${maxSlides}개의 슬라이드만 생성 가능합니다.`);
            return;
        }

        const targetSlide = slides[slideIndex];
        const newSlide: SlideInfo = {
            ...targetSlide,
            index: slides.length,
            title: `${targetSlide.title || `슬라이드 ${slideIndex + 1}`} (복사본)`,
            originalIndex: targetSlide.originalIndex || slideIndex,
            needsTextClear: false // 복사는 텍스트 클리어 안함
        };

        const newSlides = [...slides];
        newSlides.splice(slideIndex + 1, 0, newSlide);

        // 인덱스 재정렬
        const reindexedSlides = newSlides.map((slide, index) => ({
            ...slide,
            index
        }));

        console.log(`📋 슬라이드 복사 (텍스트 유지): ${newSlide.title}`);
        onSlidesUpdate(reindexedSlides);
    };

    // 슬라이드 삭제
    const deleteSlide = (slideIndex: number) => {
        if (slides.length <= 1) {
            alert('최소 1개의 슬라이드는 필요합니다.');
            return;
        }

        if (!window.confirm('이 슬라이드를 삭제하시겠습니까?')) {
            return;
        }

        const newSlides = slides.filter((_, index) => index !== slideIndex);

        // 인덱스 재정렬
        const reindexedSlides = newSlides.map((slide, index) => ({
            ...slide,
            index
        }));

        onSlidesUpdate(reindexedSlides);

        // 현재 슬라이드가 삭제된 경우 조정
        if (currentSlide === slideIndex) {
            onSlideChange(Math.max(0, slideIndex - 1));
        } else if (currentSlide > slideIndex) {
            onSlideChange(currentSlide - 1);
        }
    };

    // 현재 포커스된 슬라이드를 기반으로 새 슬라이드 추가 (현재 위치 다음에)
    const addEmptySlide = () => {
        if (slides.length >= maxSlides) {
            alert(`최대 ${maxSlides}개의 슬라이드만 생성 가능합니다.`);
            return;
        }

        // 현재 포커스된 슬라이드의 정보 가져오기
        const baseSlide = slides[currentSlide];
        let baseSlideObjects = [];

        // 템플릿 데이터에서 기반 슬라이드의 오브젝트 정보 가져오기
        if (templateData?.slides && baseSlide) {
            const originalSlideIndex = baseSlide.originalIndex !== undefined
                ? baseSlide.originalIndex
                : currentSlide;

            const originalSlideData = templateData.slides[originalSlideIndex];
            if (originalSlideData?.elements) {
                // 기반 슬라이드의 오브젝트 정보를 복사하되 텍스트는 클리어
                const timestamp = Date.now();
                const randomSuffix = Math.random().toString(36).substr(2, 9);

                baseSlideObjects = originalSlideData.elements.map((element: any, index: number) => {
                    // 더 안전한 ID 생성
                    const originalId = element.id || element.name || element.displayName || `element_${index}`;
                    const uniqueId = `${originalId}_copy_${timestamp}_${randomSuffix}_${index}`;

                    // 🆕 "추가" 버튼은 텍스트 내용을 클리어하고 슬라이드 구조만 복사
                    const clearedElement = { ...element, id: uniqueId };

                    // 텍스트 관련 필드들을 클리어
                    if (element.content) clearedElement.content = '';
                    if (element.text) clearedElement.text = '';
                    if (element.value) clearedElement.value = '';
                    if (element.innerHTML) clearedElement.innerHTML = '';

                    return clearedElement;
                });
                console.log(`🔄 기반 슬라이드 ${currentSlide + 1}의 오브젝트 ${baseSlideObjects.length}개 복사 (텍스트 클리어됨)`);
            }
        }

        // 새 슬라이드를 현재 위치 다음에 삽입
        const insertPosition = currentSlide + 1;

        const newSlide: SlideInfo = {
            index: insertPosition,
            title: `새 슬라이드 ${slides.length + 1}`,
            isEnabled: true,
            isVisible: true,
            objects: baseSlideObjects, // 기반 슬라이드의 오브젝트 복사 (텍스트 클리어됨)
            // 현재 포커스된 슬라이드를 기반으로 설정
            base_slide_index: currentSlide,
            // 🆕 추가 버튼으로 생성되었음을 표시 (텍스트 클리어 필요)
            needsTextClear: true
        };

        // 기존 슬라이드들의 인덱스를 재조정하고 새 슬라이드 삽입
        const updatedSlides = [
            ...slides.slice(0, insertPosition),
            newSlide,
            ...slides.slice(insertPosition).map(slide => ({
                ...slide,
                index: slide.index + 1
            }))
        ];

        console.log(`➕ 새 슬라이드 생성 (텍스트 클리어): ${newSlide.title}, 기반: 슬라이드 ${currentSlide + 1}, 삽입 위치: ${insertPosition + 1}, 오브젝트: ${baseSlideObjects.length}개`);
        onSlidesUpdate(updatedSlides);

        // 새로 추가된 슬라이드로 포커스 이동
        onSlideChange(insertPosition);
    };

    // 슬라이드 활성화/비활성화
    const toggleSlideEnabled = (slideIndex: number) => {
        const newSlides = slides.map((slide, index) =>
            index === slideIndex
                ? { ...slide, isEnabled: !slide.isEnabled }
                : slide
        );
        onSlidesUpdate(newSlides);
    };

    // 슬라이드 순서 변경
    const moveSlide = (fromIndex: number, toIndex: number) => {
        if (fromIndex === toIndex) return;

        const newSlides = [...slides];
        const [movedSlide] = newSlides.splice(fromIndex, 1);
        newSlides.splice(toIndex, 0, movedSlide);

        // 인덱스 재정렬
        const reindexedSlides = newSlides.map((slide, index) => ({
            ...slide,
            index
        }));

        onSlidesUpdate(reindexedSlides);

        // 현재 슬라이드 인덱스 조정
        if (currentSlide === fromIndex) {
            onSlideChange(toIndex);
        } else if (currentSlide === toIndex) {
            onSlideChange(fromIndex < toIndex ? currentSlide + 1 : currentSlide - 1);
        }
    };

    // 드래그 앤 드롭 핸들러
    const handleDragStart = (e: React.DragEvent, slideIndex: number) => {
        setDraggedSlide(slideIndex);
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    };

    const handleDrop = (e: React.DragEvent, targetIndex: number) => {
        e.preventDefault();
        if (draggedSlide !== null) {
            moveSlide(draggedSlide, targetIndex);
            setDraggedSlide(null);
        }
    };

    return (
        <div className="slide-manager bg-white border rounded-lg p-4">
            {/* 헤더 */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <FileImage className="h-5 w-5" />
                    <h3 className="text-lg font-semibold">슬라이드 관리</h3>
                    <span className="text-sm text-gray-500">({slides.length}개)</span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowPreview(!showPreview)}
                        className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
                        title="미리보기 토글"
                    >
                        {showPreview ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                    <button
                        onClick={addEmptySlide}
                        className="flex items-center gap-1 px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
                        title="빈 슬라이드 추가"
                    >
                        <Plus className="h-4 w-4" />
                        추가
                    </button>
                </div>
            </div>

            {/* 슬라이드 목록 */}
            <div className="space-y-2 max-h-96 overflow-y-auto">
                {slides.map((slide, index) => (
                    <div
                        key={slide.index}
                        className={`slide-item border rounded-lg p-3 transition-all ${currentSlide === index
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                            } ${!slide.isEnabled ? 'opacity-50' : ''}`}
                        draggable
                        onDragStart={(e) => handleDragStart(e, index)}
                        onDragOver={handleDragOver}
                        onDrop={(e) => handleDrop(e, index)}
                    >
                        <div className="flex items-center gap-3">
                            {/* 드래그 핸들 */}
                            <div className="cursor-move text-gray-400 hover:text-gray-600">
                                <GripVertical className="h-4 w-4" />
                            </div>

                            {/* 슬라이드 번호 */}
                            <div className="flex-shrink-0">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${currentSlide === index
                                    ? 'bg-blue-500 text-white'
                                    : 'bg-gray-200 text-gray-700'
                                    }`}>
                                    {index + 1}
                                </div>
                            </div>

                            {/* 슬라이드 정보 */}
                            <div className="flex-grow min-w-0">
                                <div
                                    className="cursor-pointer"
                                    onClick={() => onSlideChange(index)}
                                >
                                    <div className="font-medium text-sm truncate">
                                        {slide.title || `슬라이드 ${index + 1}`}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                        {slide.objects?.length || 0}개 오브젝트
                                        {slide.originalIndex !== undefined &&
                                            ` • 원본: ${slide.originalIndex + 1}번`
                                        }
                                    </div>
                                </div>

                                {/* 미리보기 (showPreview가 true일 때) */}
                                {showPreview && slide.thumbnail && (
                                    <div className="mt-2">
                                        <img
                                            src={slide.thumbnail}
                                            alt={`슬라이드 ${index + 1} 미리보기`}
                                            className="w-full h-16 object-contain bg-gray-50 rounded border"
                                        />
                                    </div>
                                )}
                            </div>

                            {/* 컨트롤 버튼들 */}
                            <div className="flex items-center gap-1">
                                {/* 활성화 토글 */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        toggleSlideEnabled(index);
                                    }}
                                    className={`p-2 rounded text-xs ${slide.isEnabled
                                        ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                                        }`}
                                    title={slide.isEnabled ? '슬라이드 비활성화' : '슬라이드 활성화'}
                                >
                                    {slide.isEnabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                                </button>

                                {/* 복사 */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        duplicateSlide(index);
                                    }}
                                    className="p-2 text-blue-600 hover:text-blue-800 hover:bg-blue-100 rounded"
                                    title="슬라이드 복사"
                                >
                                    <Copy className="h-4 w-4" />
                                </button>

                                {/* 위로 이동 */}
                                {index > 0 && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            moveSlide(index, index - 1);
                                        }}
                                        className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
                                        title="위로 이동"
                                    >
                                        <ChevronUp className="h-4 w-4" />
                                    </button>
                                )}

                                {/* 아래로 이동 */}
                                {index < slides.length - 1 && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            moveSlide(index, index + 1);
                                        }}
                                        className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
                                        title="아래로 이동"
                                    >
                                        <ChevronDown className="h-4 w-4" />
                                    </button>
                                )}

                                {/* 삭제 */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        deleteSlide(index);
                                    }}
                                    className="p-2 text-red-600 hover:text-red-800 hover:bg-red-100 rounded"
                                    title="슬라이드 삭제"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* 슬라이드가 없을 때 */}
            {slides.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                    <FileImage className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                    <p>슬라이드가 없습니다.</p>
                    <button
                        onClick={addEmptySlide}
                        className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                    >
                        첫 슬라이드 추가하기
                    </button>
                </div>
            )}
        </div>
    );
};

export default SlideManager;

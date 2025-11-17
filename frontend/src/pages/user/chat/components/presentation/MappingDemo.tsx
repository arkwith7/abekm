import React, { useState } from 'react';
import {
    ContentSegment,
    SimpleTemplateMetadata,
    TextBoxMapping
} from '../../../../../types/presentation';
import ContentSegmentationPanel from './ContentSegmentationPanel';
import SlidePreviewMini from './SlidePreviewMini';
import TextBoxMappingEditor from './TextBoxMappingEditor';

// 데모용 데이터
const demoTemplateMetadata: SimpleTemplateMetadata = {
    presentationTitle: "스마트 인슐린 펌프 제품소개서",
    totalPages: 3,
    slides: [
        {
            pageNumber: 1,
            layout: "Title Slide",
            elements: [
                {
                    id: "element_title",
                    type: "textbox",
                    position: "top-center-header",
                    content: "제품명",
                    style: { fontSize: "44pt", fontWeight: "bold", alignment: "center" }
                },
                {
                    id: "element_subtitle",
                    type: "textbox",
                    position: "center",
                    content: "부제목",
                    style: { fontSize: "24pt", alignment: "center" }
                }
            ]
        },
        {
            pageNumber: 2,
            layout: "Content Slide",
            elements: [
                {
                    id: "element_header2",
                    type: "textbox",
                    position: "top-left-header",
                    content: "섹션 제목"
                },
                {
                    id: "element_main2",
                    type: "textbox",
                    position: "middle-left-main",
                    content: "주요 내용"
                },
                {
                    id: "element_image2",
                    type: "image",
                    position: "right-half",
                    content: "이미지"
                }
            ]
        }
    ]
};

const demoAiContent = `스마트 인슐린 펌프 시스템 소개

1. 제품 개요
본 제품은 연속혈당측정기(CGM)와 연동하여 주입량을 자동으로 보정하는 휴대형 당뇨 관리 기기입니다.

2. 주요 기능
• 자동 베이설 조절: CGM 추세 기반 알고리즘으로 목표 혈당 범위(TIR) 유지
• 볼루스 추천: 인슐린 감수성 요인(ISF) 및 탄수화물비(CR) 기반 권장 주입량 계산
• 모바일 앱 연동: 블루투스 5.3 기반 iOS/Android 앱지원

3. 기술 사양
크기: 78 × 48 × 18 mm
무게: 78g
배터리 수명: 최대 5일
방수 등급: IPX8`;

interface MappingDemoProps {
    open: boolean;
    onClose: () => void;
}

const MappingDemo: React.FC<MappingDemoProps> = ({ open, onClose }) => {
    const [activeTab, setActiveTab] = useState<'segment' | 'mapping' | 'preview'>('segment');
    const [contentSegments, setContentSegments] = useState<ContentSegment[]>([]);
    const [textBoxMappings, setTextBoxMappings] = useState<TextBoxMapping[]>([]);
    const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);

    if (!open) return null;

    const currentSlide = demoTemplateMetadata.slides[selectedSlideIndex];

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-[95vw] h-[90vh] flex flex-col">
                {/* 헤더 */}
                <div className="flex items-center justify-between p-4 border-b">
                    <h2 className="text-xl font-semibold text-gray-800">
                        PPT 텍스트박스 매핑 데모
                    </h2>
                    <button
                        onClick={onClose}
                        className="text-gray-500 hover:text-gray-700"
                    >
                        ✕
                    </button>
                </div>

                {/* 탭 네비게이션 */}
                <div className="flex border-b">
                    <button
                        onClick={() => setActiveTab('segment')}
                        className={`px-6 py-3 font-medium ${activeTab === 'segment'
                            ? 'text-blue-600 border-b-2 border-blue-600'
                            : 'text-gray-600 hover:text-gray-800'
                            }`}
                    >
                        1. 콘텐츠 분할
                    </button>
                    <button
                        onClick={() => setActiveTab('mapping')}
                        className={`px-6 py-3 font-medium ${activeTab === 'mapping'
                            ? 'text-blue-600 border-b-2 border-blue-600'
                            : 'text-gray-600 hover:text-gray-800'
                            }`}
                    >
                        2. 텍스트박스 매핑
                    </button>
                    <button
                        onClick={() => setActiveTab('preview')}
                        className={`px-6 py-3 font-medium ${activeTab === 'preview'
                            ? 'text-blue-600 border-b-2 border-blue-600'
                            : 'text-gray-600 hover:text-gray-800'
                            }`}
                    >
                        3. 미리보기
                    </button>
                </div>

                {/* 콘텐츠 영역 */}
                <div className="flex-1 overflow-hidden">
                    {activeTab === 'segment' && (
                        <div className="h-full p-4">
                            <ContentSegmentationPanel
                                content={demoAiContent}
                                onSegmentChange={setContentSegments}
                            />
                        </div>
                    )}

                    {activeTab === 'mapping' && (
                        <div className="h-full p-4">
                            <div className="mb-4">
                                <div className="flex items-center space-x-2">
                                    <span className="text-sm text-gray-600">슬라이드 선택:</span>
                                    {demoTemplateMetadata.slides.map((slide, index) => (
                                        <button
                                            key={index}
                                            onClick={() => setSelectedSlideIndex(index)}
                                            className={`px-3 py-1 text-sm rounded ${selectedSlideIndex === index
                                                ? 'bg-blue-100 text-blue-700 border border-blue-300'
                                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                                }`}
                                        >
                                            슬라이드 {slide.pageNumber}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <TextBoxMappingEditor
                                slideIndex={selectedSlideIndex}
                                slideData={currentSlide}
                                contentSegments={contentSegments}
                                mappings={textBoxMappings}
                                onMappingChange={setTextBoxMappings}
                            />
                        </div>
                    )}

                    {activeTab === 'preview' && (
                        <div className="h-full p-4">
                            <div className="grid grid-cols-3 gap-4">
                                {demoTemplateMetadata.slides.map((slide, index) => (
                                    <SlidePreviewMini
                                        key={index}
                                        slide={slide}
                                        mappings={textBoxMappings}
                                        contentSegments={contentSegments}
                                        onElementClick={(elementId) => console.log('Clicked:', elementId)}
                                        isSelected={selectedSlideIndex === index}
                                        className="border-2"
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* 하단 버튼 */}
                <div className="flex items-center justify-between p-4 border-t bg-gray-50">
                    <div className="text-sm text-gray-600">
                        {activeTab === 'segment' && `콘텐츠 세그먼트: ${contentSegments.length}개`}
                        {activeTab === 'mapping' && `매핑 완료: ${textBoxMappings.length}개`}
                        {activeTab === 'preview' && `전체 슬라이드: ${demoTemplateMetadata.totalPages}개`}
                    </div>

                    <div className="space-x-2">
                        {activeTab === 'segment' && (
                            <button
                                onClick={() => setActiveTab('mapping')}
                                disabled={contentSegments.length === 0}
                                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                            >
                                다음: 매핑하기
                            </button>
                        )}

                        {activeTab === 'mapping' && (
                            <button
                                onClick={() => setActiveTab('preview')}
                                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                            >
                                다음: 미리보기
                            </button>
                        )}

                        {activeTab === 'preview' && (
                            <button
                                onClick={() => alert('PPT 생성 기능 연동 예정')}
                                className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
                            >
                                PPT 생성
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MappingDemo;

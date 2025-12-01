import React, { useCallback, useEffect, useState } from 'react';
import FileViewer from '../../../../../components/common/FileViewer';
import PPTMappingWithSlideManager from '../../../../../components/presentation/PPTMappingWithSlideManager';
import { ContentSegment, DiagramData, SimpleTemplateMetadata, SlideLayoutSelection, TextBoxMapping } from '../../../../../types/presentation';
import { Document } from '../../../../../types/user.types';
import AnswerTab from './AnswerTab';
import TemplateManager from './TemplateManager';

type PrimaryTab = 'answer' | 'mapping' | 'template';

interface OutlineData {
    title: string;
    sections: Array<{
        id: string;
        title: string;
        content: string;
        layoutSelection?: SlideLayoutSelection;
        diagram?: DiagramData;
    }>;
}

interface Props {
    open: boolean;
    onClose: () => void;
    initialOutline?: any;
    onConfirm: (outline: any) => void;
    /** 원본 AI 답변 (참고용) */
    sourceContent?: string;
    loading?: boolean;
    templates?: any[];
    selectedTemplateId?: string | null | undefined;
    onTemplateChange?: (id: string) => void;
}

const PresentationOutlineModal: React.FC<Props> = ({
    open,
    onClose,
    initialOutline,
    onConfirm,
    sourceContent,
    loading,
    templates = [],
    selectedTemplateId,
    onTemplateChange
}) => {
    const [outline, setOutline] = useState<OutlineData>({ title: '', sections: [] });
    const [primaryTab, setPrimaryTab] = useState<PrimaryTab>('answer');

    // 템플릿 관련 상태
    const [allTemplates, setAllTemplates] = useState<any[]>([]);

    // 파일뷰어 상태
    const [isFileViewerOpen, setIsFileViewerOpen] = useState(false);
    const [fileViewerDocument, setFileViewerDocument] = useState<Document | null>(null);

    // 매핑 관련 상태
    const [simpleMetadata, setSimpleMetadata] = useState<SimpleTemplateMetadata | null>(null);
    const [contentSegments, setContentSegments] = useState<ContentSegment[]>([]);
    const [textBoxMappings, setTextBoxMappings] = useState<TextBoxMapping[]>([]);
    // 🆕 확장된 매핑 (테이블 메타데이터 등 포함)
    const [pptObjectMappings] = useState<any[]>([]);
    // 🆕 슬라이드 관리 정보
    const [slideManagement, setSlideManagement] = useState<any[]>([]);
    // const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);

    // 클릭 기반 매핑을 위한 상태 (새 슬라이드 관리자에서는 사용하지 않음)
    // const [selectedSegment, setSelectedSegment] = useState<ContentSegment | null>(null);
    // const [selectedTextBox, setSelectedTextBox] = useState<string | null>(null);

    // toModalOutline 함수
    const toModalOutline = useCallback((apiOutline: any): OutlineData => {
        if (!apiOutline) return { title: '', sections: [] };

        // API might return 'slides' instead of 'sections'
        const sourceSlides = apiOutline.sections || apiOutline.slides || [];

        const sections = sourceSlides.map((section: any, index: number) => ({
            id: section.id || `section_${index}`,
            title: section.title || `섹션 ${index + 1}`,
            content: section.content || section.key_message || '',
            layoutSelection: section.layoutSelection || undefined,
            diagram: section.diagram || undefined
        }));

        return {
            title: apiOutline.title || '새 프레젠테이션',
            sections
        };
    }, []);

    // 초기 아웃라인 설정
    useEffect(() => {
        if (initialOutline) {
            setOutline(toModalOutline(initialOutline));
        }
    }, [initialOutline, toModalOutline]);

    // 템플릿 목록 동기화
    useEffect(() => {
        if (templates && templates.length > 0) {
            setAllTemplates(templates);
        }
    }, [templates]);

    // 기본 템플릿 선택
    useEffect(() => {
        // 템플릿이 로드되고 선택된 템플릿이 없을 때 기본 템플릿 자동 선택
        if (allTemplates.length > 0 && !selectedTemplateId) {
            const defaultTemplate = allTemplates.find(t => t.is_default);
            if (defaultTemplate && onTemplateChange) {
                console.log('🎯 기본 템플릿 자동 선택:', defaultTemplate.name);
                onTemplateChange(defaultTemplate.id);
            } else if (allTemplates.length > 0 && onTemplateChange) {
                // 기본 템플릿이 없으면 첫 번째 템플릿 선택
                console.log('🎯 첫 번째 템플릿 자동 선택:', allTemplates[0].name);
                onTemplateChange(allTemplates[0].id);
            }
        }
    }, [allTemplates, selectedTemplateId, onTemplateChange]);

    // AI 답변 자동 분할 함수
    const autoSegmentContent = useCallback((content: string) => {
        if (!content) return;

        // 문단별로 분할
        const paragraphs = content.split('\n\n').filter(p => p.trim());

        const segments: ContentSegment[] = paragraphs.map((paragraph, index) => {
            // 제목인지 판단 (짧고 굵은 글씨체 또는 번호 형태)
            const isTitle = paragraph.length < 100 &&
                (paragraph.match(/^\d+\./) || paragraph.includes('**') || paragraph.match(/^#{1,3}\s/));

            // 리스트 항목인지 판단
            const isBullet = paragraph.includes('•') || paragraph.includes('-') || paragraph.match(/^\d+\./);

            return {
                id: `segment_${index}`,
                content: paragraph.trim(),
                type: isTitle ? 'title' : (isBullet ? 'bullet' : 'paragraph'),
                priority: isTitle ? 9 : (isBullet ? 7 : 5),
                suggestedPosition: isTitle ? 'center' : 'top-left-main'
            };
        });

        setContentSegments(segments);
    }, []);

    // 단순화된 메타데이터 로드
    useEffect(() => {
        const loadTemplateData = async () => {
            if (!selectedTemplateId) {
                return;
            }

            try {
                // 단순화된 메타데이터 로드 (매핑용)
                const simpleMetadataResponse = await fetch(
                    `/api/v1/agent/presentation/templates/${encodeURIComponent(selectedTemplateId)}/simple-metadata`,
                    {
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                        }
                    }
                );

                if (simpleMetadataResponse.ok) {
                    const simpleData = await simpleMetadataResponse.json();
                    console.log('🎯 단순 메타데이터 로드 성공:', simpleData);
                    setSimpleMetadata(simpleData.metadata);
                    // AI 답변 자동 분할
                    if (sourceContent) {
                        autoSegmentContent(sourceContent);
                    }
                } else {
                    console.error('🚫 단순 메타데이터 로드 실패:', simpleMetadataResponse.status);
                    setSimpleMetadata(null);
                }
            } catch (error) {
                console.error('템플릿 데이터 로드 실패:', error);
            }
        };

        loadTemplateData();
    }, [selectedTemplateId, sourceContent, autoSegmentContent]);

    const handleTemplatesRefresh = async () => {
        try {
            const response = await fetch(
                `/api/v1/agent/presentation/templates`,
                {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                    }
                }
            );

            if (response.ok) {
                const data = await response.json();
                setAllTemplates(data.templates || []);
            }
        } catch (error) {
            console.error('템플릿 목록 새로고침 실패:', error);
        }
    };

    // 매핑 관련 핸들러들
    const handleMappingChange = useCallback((mappings: TextBoxMapping[]) => {
        setTextBoxMappings(mappings);
    }, []);

    const handleCloseFileViewer = useCallback(() => {
        setIsFileViewerOpen(false);
        setFileViewerDocument(null);
    }, []);

    const handleConfirm = () => {
        const mappedSlides = outline.sections.map(section => ({
            id: section.id,
            title: section.title,
            content: section.content,
            key_message: section.content,
            layoutSelection: section.layoutSelection,
            diagram: section.diagram
        }));

        const finalOutline = {
            title: outline.title,
            sections: mappedSlides,
            slides: mappedSlides,
            // 매핑 정보 추가
            textBoxMappings: textBoxMappings,
            contentSegments: contentSegments,
            // 🆕 확장된 오브젝트 매핑 포함 (백엔드가 지원할 경우 사용)
            object_mappings: pptObjectMappings,
            // 🆕 슬라이드 관리 정보 추가
            slide_management: slideManagement
        };
        console.log('🚀 PPT 생성을 위한 최종 데이터:');
        console.log('  textBoxMappings:', textBoxMappings);
        console.log('  object_mappings:', pptObjectMappings);
        console.log('  slide_management:', slideManagement);
        console.log('  Full outline:', finalOutline);
        onConfirm(finalOutline);
        onClose();
    };

    // 템플릿 목록이 비어있으면 자동으로 로드
    useEffect(() => {
        if (allTemplates.length === 0) {
            handleTemplatesRefresh();
        }
    }, [allTemplates.length]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl max-h-[90vh] flex flex-col">
                {/* 헤더 */}
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">PPT 생성 설정</h2>
                    <div className="flex items-center space-x-4">
                        {/* 템플릿 선택 */}
                        <select
                            value={selectedTemplateId || ''}
                            onChange={(e) => onTemplateChange?.(e.target.value)}
                            className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        >
                            <option value="">템플릿 선택...</option>
                            {/* 기본 템플릿을 먼저 표시 */}
                            {allTemplates
                                .sort((a, b) => {
                                    if (a.is_default && !b.is_default) return -1;
                                    if (!a.is_default && b.is_default) return 1;
                                    return a.name.localeCompare(b.name);
                                })
                                .map((template) => (
                                    <option key={template.id} value={template.id}>
                                        {template.name} {template.is_default ? '(기본)' : ''}
                                    </option>
                                ))}
                        </select>

                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-gray-600 transition-colors"
                        >
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* 탭 네비게이션 */}
                <div className="px-6 py-3 border-b border-gray-200">
                    <div className="flex space-x-1">
                        <button
                            onClick={() => setPrimaryTab('answer')}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${primaryTab === 'answer'
                                ? 'bg-blue-100 text-blue-700'
                                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                                }`}
                        >
                            AI 답변
                        </button>
                        <button
                            onClick={() => setPrimaryTab('mapping')}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${primaryTab === 'mapping'
                                ? 'bg-blue-100 text-blue-700'
                                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                                }`}
                        >
                            매핑 편집
                        </button>
                        <button
                            onClick={() => setPrimaryTab('template')}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${primaryTab === 'template'
                                ? 'bg-blue-100 text-blue-700'
                                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                                }`}
                        >
                            템플릿 관리
                        </button>
                    </div>
                </div>

                {/* 메인 콘텐츠 */}
                <div className="p-6 overflow-y-auto max-h-[calc(90vh-210px)]">
                    {loading && outline.sections.length > 0 ? (
                        // 🤖 AI 생성 중이지만 기본 아웃라인이 있는 경우
                        <>
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                                <div className="flex items-center gap-3">
                                    <div className="animate-spin h-5 w-5 rounded-full border-2 border-blue-200 border-t-blue-600" />
                                    <div>
                                        <div className="text-sm font-medium text-blue-800">🤖 AI가 더 나은 아웃라인을 생성하고 있습니다</div>
                                        <div className="text-xs text-blue-600 mt-1">지금도 편집하실 수 있으며, AI 생성 완료 시 선택적으로 적용됩니다</div>
                                    </div>
                                </div>
                            </div>
                            {renderMainContent()}
                        </>
                    ) : loading ? (
                        // 📝 완전 로딩 상태 (기본 아웃라인도 없는 경우)
                        <div className="flex flex-col items-center justify-center py-24 text-center text-gray-500 gap-3">
                            <div className="animate-spin h-8 w-8 rounded-full border-4 border-gray-200 border-t-blue-600" />
                            <div className="text-sm font-medium">아웃라인을 생성하고 있습니다...</div>
                            <div className="text-xs text-gray-400">곧 편집 가능한 상태로 전환됩니다</div>
                        </div>
                    ) : (
                        renderMainContent()
                    )}
                </div>

                {/* 푸터 */}
                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50">
                    <div className="flex items-center space-x-4">
                        <div className="text-sm text-gray-600">
                            총 {outline.sections.length}개 섹션
                        </div>
                    </div>
                    <div className="flex items-center space-x-3">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                        >
                            취소
                        </button>
                        <button
                            onClick={handleConfirm}
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
                        >
                            PPT 생성하기
                        </button>
                    </div>
                </div>
            </div>

            {/* 템플릿 파일뷰어 */}
            <FileViewer
                isOpen={isFileViewerOpen}
                onClose={handleCloseFileViewer}
                document={fileViewerDocument}
            />
        </div>
    );

    // 메인 콘텐츠 렌더링 함수
    function renderMainContent() {
        switch (primaryTab) {
            case 'answer':
                return <AnswerTab sourceContent={sourceContent} />;

            case 'mapping':
                return (
                    <div className="h-full">
                        {!simpleMetadata && selectedTemplateId && (
                            <div className="flex items-center justify-center p-8">
                                <div className="text-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
                                    <p className="text-gray-600">템플릿 메타데이터 로딩 중...</p>
                                </div>
                            </div>
                        )}

                        {!selectedTemplateId && (
                            <div className="flex items-center justify-center p-8">
                                <p className="text-gray-600">템플릿을 먼저 선택해주세요.</p>
                            </div>
                        )}

                        {simpleMetadata && (
                            <PPTMappingWithSlideManager
                                templateData={simpleMetadata}
                                contentSegments={contentSegments}
                                mappings={textBoxMappings}
                                onMappingChange={handleMappingChange}
                                onSlideManagementChange={setSlideManagement}
                                className="h-full"
                            />
                        )}
                    </div>
                ); case 'template':
                return (
                    <TemplateManager
                        templates={allTemplates}
                        selectedTemplateId={selectedTemplateId || null}
                        onTemplateChange={onTemplateChange || (() => { })}
                        onTemplatesRefresh={handleTemplatesRefresh}
                    />
                );

            default:
                return null;
        }
    }
};

export default PresentationOutlineModal;
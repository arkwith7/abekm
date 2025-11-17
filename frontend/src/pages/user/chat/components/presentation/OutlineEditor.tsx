import React, { useState } from 'react';
import { SlideLayoutSelection } from '../../../../../types/presentation';

// SVG 아이콘 컴포넌트들
const PlusIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
);

const TrashIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
);

const ArrowUpIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
    </svg>
);

const ArrowDownIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
);

interface OutlineData {
    title: string;
    sections: Array<{
        id: string;
        title: string;
        content: string;
        layoutSelection?: SlideLayoutSelection;
    }>;
}

interface OutlineEditorProps {
    outline: OutlineData;
    onOutlineChange: (outline: OutlineData) => void;
    viewMode: 'overview' | 'edit';
    onViewModeChange: (mode: 'overview' | 'edit') => void;
    activeTabIndex: number;
    onActiveTabChange: (index: number) => void;
    availableLayouts?: any[];
    templateMetadata?: any;
}

const OutlineEditor: React.FC<OutlineEditorProps> = ({
    outline,
    onOutlineChange,
    viewMode,
    onViewModeChange,
    activeTabIndex,
    onActiveTabChange,
    availableLayouts = [],
    templateMetadata
}) => {
    const [editingTitle, setEditingTitle] = useState(false);

    const updateTitle = (newTitle: string) => {
        onOutlineChange({ ...outline, title: newTitle });
    };

    const updateSection = (index: number, updates: Partial<typeof outline.sections[0]>) => {
        const newSections = [...outline.sections];
        newSections[index] = { ...newSections[index], ...updates };
        onOutlineChange({ ...outline, sections: newSections });
    };

    const addSection = () => {
        const newSection = {
            id: `section_${Date.now()}`,
            title: `새 섹션 ${outline.sections.length + 1}`,
            content: '내용을 입력하세요.'
        };
        onOutlineChange({
            ...outline,
            sections: [...outline.sections, newSection]
        });
        onActiveTabChange(outline.sections.length);
    };

    const removeSection = (index: number) => {
        if (outline.sections.length <= 1) return;
        const newSections = outline.sections.filter((_, i) => i !== index);
        onOutlineChange({ ...outline, sections: newSections });
        if (activeTabIndex >= newSections.length) {
            onActiveTabChange(newSections.length - 1);
        }
    };

    const moveSection = (index: number, direction: 'up' | 'down') => {
        if (
            (direction === 'up' && index === 0) ||
            (direction === 'down' && index === outline.sections.length - 1)
        ) {
            return;
        }

        const newSections = [...outline.sections];
        const targetIndex = direction === 'up' ? index - 1 : index + 1;
        [newSections[index], newSections[targetIndex]] = [newSections[targetIndex], newSections[index]];

        onOutlineChange({ ...outline, sections: newSections });
        onActiveTabChange(targetIndex);
    };

    const renderOverviewMode = () => (
        <div className="space-y-4">
            {/* 제목 섹션 */}
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-gray-700">프레젠테이션 제목</h3>
                    <button
                        onClick={() => setEditingTitle(true)}
                        className="text-xs text-blue-600 hover:text-blue-700"
                    >
                        편집
                    </button>
                </div>
                {editingTitle ? (
                    <input
                        type="text"
                        value={outline.title}
                        onChange={(e) => updateTitle(e.target.value)}
                        onBlur={() => setEditingTitle(false)}
                        onKeyDown={(e) => e.key === 'Enter' && setEditingTitle(false)}
                        className="w-full p-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        autoFocus
                    />
                ) : (
                    <div className="text-sm text-gray-900">{outline.title || '제목을 입력하세요'}</div>
                )}
            </div>

            {/* 섹션 목록 */}
            <div className="space-y-3">
                {outline.sections.map((section, index) => (
                    <div key={section.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center space-x-2">
                                <span className="text-xs font-medium text-gray-500">슬라이드 {index + 1}</span>
                                <h4 className="text-sm font-medium text-gray-900">{section.title}</h4>
                            </div>
                            <button
                                onClick={() => {
                                    onActiveTabChange(index);
                                    onViewModeChange('edit');
                                }}
                                className="text-xs text-blue-600 hover:text-blue-700"
                            >
                                편집
                            </button>
                        </div>
                        <div className="text-xs text-gray-600 line-clamp-2">
                            {section.content}
                        </div>
                    </div>
                ))}
            </div>

            {/* 섹션 추가 버튼 */}
            <button
                onClick={addSection}
                className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center space-x-2"
            >
                <PlusIcon className="w-4 h-4" />
                <span>새 섹션 추가</span>
            </button>
        </div>
    );

    const renderEditMode = () => {
        const currentSection = outline.sections[activeTabIndex];
        if (!currentSection) return null;

        return (
            <div className="space-y-4">
                {/* 탭 네비게이션 */}
                <div className="flex space-x-1 overflow-x-auto pb-2">
                    {outline.sections.map((section, index) => (
                        <button
                            key={section.id}
                            onClick={() => onActiveTabChange(index)}
                            className={`px-3 py-2 text-xs font-medium rounded-md whitespace-nowrap transition-colors ${index === activeTabIndex
                                ? 'bg-blue-100 text-blue-700 border border-blue-300'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            슬라이드 {index + 1}
                        </button>
                    ))}
                    <button
                        onClick={addSection}
                        className="px-3 py-2 text-xs font-medium rounded-md whitespace-nowrap bg-green-100 text-green-700 hover:bg-green-200 transition-colors flex items-center space-x-1"
                    >
                        <PlusIcon className="w-3 h-3" />
                        <span>추가</span>
                    </button>
                </div>

                {/* 섹션 편집 */}
                <div className="border border-gray-200 rounded-lg p-4 space-y-4">
                    {/* 섹션 헤더 */}
                    <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium text-gray-900">
                            슬라이드 {activeTabIndex + 1} 편집
                        </h3>
                        <div className="flex items-center space-x-2">
                            <button
                                onClick={() => moveSection(activeTabIndex, 'up')}
                                disabled={activeTabIndex === 0}
                                className="p-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                title="위로 이동"
                            >
                                <ArrowUpIcon className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => moveSection(activeTabIndex, 'down')}
                                disabled={activeTabIndex === outline.sections.length - 1}
                                className="p-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                title="아래로 이동"
                            >
                                <ArrowDownIcon className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => removeSection(activeTabIndex)}
                                disabled={outline.sections.length <= 1}
                                className="p-1.5 text-red-500 hover:text-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                title="섹션 삭제"
                            >
                                <TrashIcon className="w-4 h-4" />
                            </button>
                        </div>
                    </div>

                    {/* 제목 편집 */}
                    <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                            슬라이드 제목
                        </label>
                        <input
                            type="text"
                            value={currentSection.title}
                            onChange={(e) => updateSection(activeTabIndex, { title: e.target.value })}
                            className="w-full p-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            placeholder="슬라이드 제목을 입력하세요"
                        />
                    </div>

                    {/* 내용 편집 */}
                    <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                            슬라이드 내용
                        </label>
                        <textarea
                            value={currentSection.content}
                            onChange={(e) => updateSection(activeTabIndex, { content: e.target.value })}
                            rows={8}
                            className="w-full p-3 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                            placeholder="슬라이드 내용을 입력하세요..."
                        />
                    </div>

                    {/* 레이아웃 선택 (향후 구현) */}
                    {templateMetadata && (
                        <div>
                            <label className="block text-xs font-medium text-gray-700 mb-2">
                                템플릿 레이아웃 정보
                            </label>
                            <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
                                <div className="text-xs text-gray-600 space-y-1">
                                    {templateMetadata.slides?.length > 0 && (
                                        <div>총 {templateMetadata.slides.length}개 슬라이드 레이아웃 사용 가능</div>
                                    )}
                                    <div className="text-green-600">🎨 템플릿 기반 자동 매핑 적용됨</div>
                                </div>
                            </div>
                        </div>
                    )}
                    {availableLayouts.length > 0 && !templateMetadata && (
                        <div>
                            <label className="block text-xs font-medium text-gray-700 mb-2">
                                슬라이드 레이아웃
                            </label>
                            <div className="text-xs text-gray-500">
                                레이아웃 선택 기능이 곧 추가됩니다.
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-4">
            {/* 뷰 모드 전환 */}
            <div className="flex items-center space-x-2">
                <button
                    onClick={() => onViewModeChange('overview')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${viewMode === 'overview'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    전체보기
                </button>
                <button
                    onClick={() => onViewModeChange('edit')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${viewMode === 'edit'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    편집모드
                </button>
            </div>

            {/* 메인 콘텐츠 */}
            {viewMode === 'overview' ? renderOverviewMode() : renderEditMode()}
        </div>
    );
};

export default OutlineEditor;

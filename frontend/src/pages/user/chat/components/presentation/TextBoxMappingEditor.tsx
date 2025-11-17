import React, { useState } from 'react';
import {
    ContentSegment,
    SimpleSlide,
    TextBoxMapping
} from '../../../../../types/presentation';

interface Props {
    slideIndex: number;
    slideData: SimpleSlide;
    contentSegments: ContentSegment[];
    mappings: TextBoxMapping[];
    onMappingChange: (mappings: TextBoxMapping[]) => void;
    className?: string;
    // 클릭 모드 관련 props
    selectedSegment?: ContentSegment | null;
    selectedTextBox?: string | null;
    onTextBoxClick?: (elementId: string) => void;
    onClearMapping?: (elementId: string) => void;
}

const TextBoxMappingEditor: React.FC<Props> = ({
    slideIndex,
    slideData,
    contentSegments,
    mappings,
    onMappingChange,
    className = '',
    selectedSegment,
    selectedTextBox,
    onTextBoxClick,
    onClearMapping
}) => {
    // 편집 상태 관리
    const [editingElementId, setEditingElementId] = useState<string | null>(null);
    const [editContent, setEditContent] = useState<string>('');

    // 텍스트박스만 필터링하고 ID가 없으면 생성
    const textBoxElements = slideData.elements
        .filter(element => element.type === 'textbox' || element.type === 'list')
        .map((element, index) => ({
            ...element,
            id: element.id || `textbox-${slideIndex}-${index}`
        }));

    console.log('슬라이드 데이터 전체:', slideData);
    console.log('텍스트박스 elements:', textBoxElements.map(el => ({
        id: el.id,
        type: el.type,
        content: el.content,
        position: el.position
    })));

    // 특정 텍스트박스에 대한 매핑 찾기
    const findMappingForTextBox = (elementId: string): TextBoxMapping | undefined => {
        const mapping = mappings.find(m => m.slideIndex === slideIndex && m.elementId === elementId);
        console.log(`매핑 조회 - slideIndex: ${slideIndex}, elementId: ${elementId}`, {
            found: !!mapping,
            totalMappings: mappings.length,
            mapping: mapping
        });
        return mapping;
    };

    // 텍스트박스 클릭 핸들러
    const handleTextBoxClick = (elementId: string) => {
        onTextBoxClick?.(elementId);
    };

    // 매핑 클리어 핸들러
    const handleClearMapping = (elementId: string) => {
        onClearMapping?.(elementId);
    };

    // 원본 텍스트 사용
    const handleUseOriginalContent = (elementId: string) => {
        const element = textBoxElements.find(el => el.id === elementId);
        if (!element || !element.content) return;

        const newMapping: TextBoxMapping = {
            slideIndex,
            elementId,
            elementType: 'textbox',
            originalContent: element.content,
            assignedContent: element.content,
            contentSource: 'keep_original',
            position: element.position || 'center'
        };

        // 기존 매핑을 제거하고 새 매핑을 추가
        const filteredMappings = mappings.filter(
            m => !(m.slideIndex === slideIndex && m.elementId === elementId)
        );

        onMappingChange([...filteredMappings, newMapping]);
    };

    // 편집 시작
    const handleStartEdit = (elementId: string) => {
        const mapping = findMappingForTextBox(elementId);
        const element = textBoxElements.find(el => el.id === elementId);

        const currentContent = mapping?.assignedContent || element?.content || '';
        setEditContent(currentContent);
        setEditingElementId(elementId);
    };

    // 편집 저장
    const handleSaveEdit = (elementId: string) => {
        if (!editContent.trim()) return;

        const element = textBoxElements.find(el => el.id === elementId);
        const existingMapping = findMappingForTextBox(elementId);

        const newMapping: TextBoxMapping = {
            slideIndex,
            elementId,
            elementType: 'textbox',
            originalContent: element?.content || '',
            assignedContent: editContent.trim(),
            contentSource: existingMapping?.contentSource || 'user_input',
            position: element?.position || 'center'
        };

        // 기존 매핑을 제거하고 새 매핑을 추가
        const filteredMappings = mappings.filter(
            m => !(m.slideIndex === slideIndex && m.elementId === elementId)
        );

        onMappingChange([...filteredMappings, newMapping]);

        setEditingElementId(null);
        setEditContent('');
    };

    // 편집 취소
    const handleCancelEdit = () => {
        setEditingElementId(null);
        setEditContent('');
    };

    return (
        <div className={`space-y-4 ${className}`}>
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">텍스트박스 매핑</h3>
                {selectedSegment && (
                    <div className="text-sm text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
                        선택된 세그먼트: "{selectedSegment.content.substring(0, 30)}..."
                    </div>
                )}
            </div>

            {/* 사용법 안내 */}
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                <p className="text-sm text-orange-800">
                    💡 <strong>텍스트박스를 클릭</strong>하여 선택된 콘텐츠를 매핑하세요.
                    {selectedSegment ? (
                        <span className="font-medium text-green-700"> 세그먼트가 선택되었습니다!</span>
                    ) : (
                        <span className="text-gray-600"> 먼저 왼쪽에서 세그먼트를 선택하세요.</span>
                    )}
                </p>
            </div>

            {/* 텍스트박스 목록 */}
            <div className="space-y-3">
                <h4 className="text-sm font-medium text-gray-700">
                    슬라이드 {slideIndex + 1}의 텍스트박스 ({textBoxElements.length}개)
                </h4>

                {textBoxElements.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                        <p>이 슬라이드에는 텍스트박스가 없습니다.</p>
                    </div>
                ) : (
                    <div className="grid gap-3">
                        {textBoxElements.map((element, index) => {
                            const mapping = findMappingForTextBox(element.id);
                            const isSelected = selectedTextBox === element.id;
                            const hasMapped = !!mapping;

                            return (
                                <div
                                    key={element.id}
                                    onClick={() => handleTextBoxClick(element.id)}
                                    className={`border rounded-lg p-4 transition-all duration-200 cursor-pointer ${isSelected
                                        ? 'border-blue-500 bg-blue-50 shadow-md ring-2 ring-blue-200'
                                        : hasMapped
                                            ? 'border-green-500 bg-green-50 hover:bg-green-100'
                                            : 'border-gray-200 bg-white hover:shadow-sm hover:border-gray-300'
                                        }`}
                                >
                                    {/* 텍스트박스 헤더 */}
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center space-x-2">
                                            {/* 체크박스 추가 */}
                                            <input
                                                type="checkbox"
                                                checked={hasMapped}
                                                onChange={(e) => {
                                                    e.stopPropagation();
                                                    if (hasMapped) {
                                                        handleClearMapping(element.id);
                                                    } else {
                                                        handleTextBoxClick(element.id);
                                                    }
                                                }}
                                                className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                                            />
                                            <div className={`w-3 h-3 rounded-full ${isSelected
                                                ? 'bg-blue-500'
                                                : hasMapped
                                                    ? 'bg-green-500'
                                                    : 'bg-gray-300'
                                                }`}></div>
                                            <span className="text-sm font-medium text-gray-700">
                                                텍스트박스 #{index + 1}
                                            </span>
                                            <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                                                {element.type}
                                            </span>
                                        </div>                                        <div className="flex items-center space-x-2">
                                            {hasMapped && (
                                                <>
                                                    <span className="text-xs text-green-600 font-medium">
                                                        ✓ 매핑됨
                                                    </span>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleClearMapping(element.id);
                                                        }}
                                                        className="text-xs text-red-600 hover:text-red-800"
                                                    >
                                                        해제
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* 텍스트박스 정보 */}
                                    <div className="text-sm text-gray-600 mb-2">
                                        <div>위치: {element.position || 'unknown'}</div>
                                    </div>

                                    {/* 매핑된 콘텐츠 또는 원본 콘텐츠 */}
                                    <div className="bg-gray-50 rounded p-2 mb-3">
                                        {mapping ? (
                                            <div>
                                                <div className="text-xs text-green-600 font-medium mb-1">
                                                    매핑된 콘텐츠 ({mapping.contentSource}):
                                                </div>
                                                {editingElementId === element.id ? (
                                                    <div className="space-y-2">
                                                        <textarea
                                                            value={editContent}
                                                            onChange={(e) => setEditContent(e.target.value)}
                                                            className="w-full text-sm p-2 border border-gray-300 rounded resize-none"
                                                            rows={3}
                                                            placeholder="내용을 입력하세요..."
                                                        />
                                                        <div className="flex space-x-2">
                                                            <button
                                                                onClick={() => handleSaveEdit(element.id)}
                                                                className="text-xs bg-blue-500 text-white px-2 py-1 rounded hover:bg-blue-600"
                                                            >
                                                                저장
                                                            </button>
                                                            <button
                                                                onClick={handleCancelEdit}
                                                                className="text-xs bg-gray-500 text-white px-2 py-1 rounded hover:bg-gray-600"
                                                            >
                                                                취소
                                                            </button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-sm text-gray-800">
                                                        {mapping.assignedContent}
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div>
                                                <div className="text-xs text-gray-500 mb-1">
                                                    원본 콘텐츠:
                                                </div>
                                                <div className="text-sm text-gray-600">
                                                    {element.content || '(빈 텍스트박스)'}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* 액션 버튼들 */}
                                    <div className="flex flex-wrap gap-2">
                                        {!mapping && element.content && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleUseOriginalContent(element.id);
                                                }}
                                                className="text-xs bg-gray-500 text-white px-3 py-1 rounded hover:bg-gray-600"
                                            >
                                                원본 사용
                                            </button>
                                        )}

                                        {mapping && editingElementId !== element.id && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleStartEdit(element.id);
                                                }}
                                                className="text-xs bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                                            >
                                                편집
                                            </button>
                                        )}
                                    </div>

                                    {/* 클릭 안내 */}
                                    {selectedSegment && !hasMapped && (
                                        <div className="mt-2 text-xs text-blue-600 font-medium">
                                            클릭하여 "{selectedSegment.content.substring(0, 20)}..." 매핑
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* 매핑 통계 */}
            <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-sm text-gray-600">
                    <div className="flex justify-between">
                        <span>총 텍스트박스:</span>
                        <span className="font-medium">{textBoxElements.length}개</span>
                    </div>
                    <div className="flex justify-between">
                        <span>매핑 완료:</span>
                        <span className="font-medium text-green-600">
                            {mappings.filter(m => m.slideIndex === slideIndex).length}개
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span>미매핑:</span>
                        <span className="font-medium text-orange-600">
                            {textBoxElements.length - mappings.filter(m => m.slideIndex === slideIndex).length}개
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TextBoxMappingEditor;

/**
 * 문서 유형 선택 컴포넌트
 * 
 * 업로드 시 문서 유형(논문, 특허, 일반 문서 등)을 선택하고
 * 유형별 처리 옵션을 설정할 수 있는 UI 제공
 */

import React, { useEffect, useState } from 'react';
import { DocumentTypeInfo, getDocumentTypes } from '../services/documentService';

interface DocumentTypeSelectorProps {
    selectedType: string;
    onTypeChange: (typeId: string, options: Record<string, any>) => void;
    className?: string;
}

/**
 * 문서 유형 선택기
 * 
 * @param selectedType 현재 선택된 문서 유형 ID
 * @param onTypeChange 유형 변경 콜백 (typeId, options)
 * @param className 추가 CSS 클래스
 */
export const DocumentTypeSelector: React.FC<DocumentTypeSelectorProps> = ({
    selectedType,
    onTypeChange,
    className = ''
}) => {
    const [documentTypes, setDocumentTypes] = useState<DocumentTypeInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [processingOptions, setProcessingOptions] = useState<Record<string, any>>({});
    const [showOptions, setShowOptions] = useState(false);

    // 문서 유형 목록 로드
    useEffect(() => {
        const fetchDocumentTypes = async () => {
            try {
                setLoading(true);
                const response = await getDocumentTypes();
                setDocumentTypes(response.document_types);

                // 기본 선택 유형의 옵션 설정
                const defaultType = response.document_types.find(t => t.id === selectedType);
                if (defaultType) {
                    setProcessingOptions(defaultType.default_options);
                }

                setError(null);
            } catch (err) {
                console.error('문서 유형 로드 실패:', err);
                setError('문서 유형을 불러오는데 실패했습니다.');
            } finally {
                setLoading(false);
            }
        };

        fetchDocumentTypes();
    }, []);

    // 유형 변경 핸들러
    const handleTypeChange = (typeId: string) => {
        const selectedDocType = documentTypes.find(t => t.id === typeId);
        if (selectedDocType) {
            const defaultOpts = selectedDocType.default_options;
            setProcessingOptions(defaultOpts);
            onTypeChange(typeId, defaultOpts);
            setShowOptions(typeId !== 'general'); // 일반 문서가 아니면 옵션 표시
        }
    };

    // 옵션 변경 핸들러
    const handleOptionChange = (optionKey: string, value: any) => {
        const updatedOptions = { ...processingOptions, [optionKey]: value };
        setProcessingOptions(updatedOptions);
        onTypeChange(selectedType, updatedOptions);
    };

    if (loading) {
        return (
            <div className={`text-gray-600 ${className}`}>
                <span className="animate-pulse">문서 유형 로딩 중...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className={`text-red-600 ${className}`}>
                <span>⚠️ {error}</span>
            </div>
        );
    }

    return (
        <div className={`space-y-4 ${className}`}>
            {/* 문서 유형 선택 그리드 */}
            <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                    문서 유형 선택
                </label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {documentTypes.map((docType) => (
                        <button
                            key={docType.id}
                            type="button"
                            onClick={() => handleTypeChange(docType.id)}
                            className={`
                p-4 border-2 rounded-lg transition-all
                ${selectedType === docType.id
                                    ? 'border-blue-500 bg-blue-50 shadow-md'
                                    : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'
                                }
              `}
                        >
                            <div className="flex flex-col items-center space-y-2">
                                <span className="text-3xl">{docType.icon}</span>
                                <span className="text-sm font-medium text-gray-900">
                                    {docType.name}
                                </span>
                                <span className="text-xs text-gray-500 text-center">
                                    {docType.description}
                                </span>
                                <div className="flex flex-wrap gap-1 justify-center">
                                    {docType.supported_formats.slice(0, 3).map((fmt) => (
                                        <span
                                            key={fmt}
                                            className="text-xs bg-gray-200 px-2 py-0.5 rounded"
                                        >
                                            .{fmt}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* 처리 옵션 (선택된 유형에 따라 표시) */}
            {showOptions && selectedType !== 'general' && (
                <div className="border-t pt-4">
                    <button
                        type="button"
                        onClick={() => setShowOptions(!showOptions)}
                        className="flex items-center justify-between w-full text-sm font-medium text-gray-700 mb-3"
                    >
                        <span>고급 처리 옵션</span>
                        <span className="text-gray-400">
                            {showOptions ? '▲' : '▼'}
                        </span>
                    </button>

                    {showOptions && (
                        <div className="space-y-3 bg-gray-50 p-4 rounded-lg">
                            {/* 학술 논문 옵션 */}
                            {selectedType === 'academic_paper' && (
                                <>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.extract_figures ?? true}
                                            onChange={(e) => handleOptionChange('extract_figures', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">Figure/Table 캡션 추출</span>
                                    </label>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.parse_references ?? true}
                                            onChange={(e) => handleOptionChange('parse_references', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">References 섹션 파싱</span>
                                    </label>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.figure_caption_required ?? true}
                                            onChange={(e) => handleOptionChange('figure_caption_required', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">캡션이 있는 Figure만 추출</span>
                                    </label>
                                </>
                            )}

                            {/* 특허 옵션 */}
                            {selectedType === 'patent' && (
                                <>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.extract_claims ?? true}
                                            onChange={(e) => handleOptionChange('extract_claims', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">Claims 섹션 추출</span>
                                    </label>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.parse_citations ?? true}
                                            onChange={(e) => handleOptionChange('parse_citations', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">인용 특허 파싱</span>
                                    </label>
                                </>
                            )}

                            {/* 프레젠테이션 옵션 */}
                            {selectedType === 'presentation' && (
                                <>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.extract_key_slides ?? true}
                                            onChange={(e) => handleOptionChange('extract_key_slides', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">핵심 슬라이드 추출</span>
                                    </label>
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={processingOptions.extract_charts ?? true}
                                            onChange={(e) => handleOptionChange('extract_charts', e.target.checked)}
                                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="text-sm text-gray-700">차트/그래프 추출</span>
                                    </label>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default DocumentTypeSelector;

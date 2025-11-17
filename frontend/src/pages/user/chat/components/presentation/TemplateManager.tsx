import React, { useRef, useState } from 'react';

interface Template {
    id: string;
    name: string;
    type: 'built-in' | 'user-uploaded';
    is_content_cleaned?: boolean;
    dynamic_template_id?: string;
    is_default?: boolean; // 기본 템플릿 여부
}

interface TemplateManagerProps {
    templates: Template[];
    selectedTemplateId: string | null | undefined;
    onTemplateChange: (id: string) => void;
    onTemplatesRefresh: () => void;
}

const TemplateManager: React.FC<TemplateManagerProps> = ({
    templates,
    selectedTemplateId,
    onTemplateChange,
    onTemplatesRefresh
}) => {
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string>('');
    const [previewTemplate, setPreviewTemplate] = useState<Template | null>(null);
    const [previewLayouts, setPreviewLayouts] = useState<any[]>([]);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // 기본 템플릿 설정
    const handleSetDefaultTemplate = async (templateId: string) => {
        try {
            const response = await fetch(
                `/api/v1/chat/presentation/templates/${encodeURIComponent(templateId)}/set-default`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                    }
                }
            );

            if (response.ok) {
                console.log('기본 템플릿 설정 성공');
                // 약간의 지연을 둔 후 템플릿 목록 새로고침
                setTimeout(() => {
                    onTemplatesRefresh();
                }, 100);
            } else {
                const error = await response.json();
                console.error('기본 템플릿 설정 실패:', error);
                alert(error.detail || '기본 템플릿 설정에 실패했습니다.');
            }
        } catch (error) {
            console.error('기본 템플릿 설정 오류:', error);
            alert('기본 템플릿 설정 중 오류가 발생했습니다.');
        }
    };

    // 현재 사용자가 관리자인지 확인
    const isAdmin = () => {
        try {
            const userInfo = localStorage.getItem('ABEKM_user');
            if (userInfo) {
                const user = JSON.parse(userInfo);
                return user.is_admin === true;
            }
        } catch (error) {
            console.error('사용자 정보 확인 오류:', error);
        }
        return false;
    };

    // 템플릿 미리보기 불러오기
    const handlePreviewTemplate = async (template: Template) => {
        setPreviewTemplate(template);
        setIsLoadingPreview(true);
        setPreviewLayouts([]);

        try {
            const response = await fetch(
                `/api/v1/chat/presentation/templates/${encodeURIComponent(template.id)}/layouts`,
                {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                    }
                }
            );

            if (response.ok) {
                const layouts = await response.json();
                setPreviewLayouts(layouts || []);
            } else {
                console.error('레이아웃 정보를 가져올 수 없습니다.');
            }
        } catch (error) {
            console.error('레이아웃 미리보기 오류:', error);
        } finally {
            setIsLoadingPreview(false);
        }
    };

    // 템플릿 파일 다운로드/미리보기
    const handleDownloadTemplate = (template: Template) => {
        const token = localStorage.getItem('ABEKM_token');
        const downloadUrl = `/api/v1/chat/presentation/templates/${encodeURIComponent(template.id)}/download?token=${token}`;

        // 새 창에서 다운로드 (PowerPoint 파일이므로 자동으로 다운로드됨)
        window.open(downloadUrl, '_blank');
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.pptx')) {
            setUploadError('PowerPoint 파일(.pptx)만 업로드 가능합니다.');
            return;
        }

        setIsUploading(true);
        setUploadError('');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(
                `/api/v1/chat/presentation/templates/upload`,
                {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                    }
                }
            );

            if (response.ok) {
                const result = await response.json();
                console.log('템플릿 업로드 성공:', result);
                onTemplatesRefresh();

                // 파일 입력 초기화
                if (fileInputRef.current) {
                    fileInputRef.current.value = '';
                }
            } else {
                const error = await response.json();
                setUploadError(error.detail || '업로드에 실패했습니다.');
            }
        } catch (error) {
            console.error('템플릿 업로드 오류:', error);
            setUploadError('업로드 중 오류가 발생했습니다.');
        } finally {
            setIsUploading(false);
        }
    };

    const handleDeleteTemplate = async (templateId: string) => {
        if (!window.confirm('정말로 이 템플릿을 삭제하시겠습니까?')) return;

        try {
            const response = await fetch(
                `/api/v1/chat/presentation/templates/${encodeURIComponent(templateId)}`,
                {
                    method: 'DELETE',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                    }
                }
            );

            if (response.ok) {
                console.log('템플릿 삭제 성공');
                onTemplatesRefresh();

                // 삭제된 템플릿이 선택되어 있다면 선택 해제
                if (selectedTemplateId === templateId) {
                    const remainingTemplates = templates.filter(t => t.id !== templateId);
                    if (remainingTemplates.length > 0) {
                        onTemplateChange(remainingTemplates[0].id);
                    }
                }
            } else {
                const error = await response.json();
                alert(error.detail || '삭제에 실패했습니다.');
            }
        } catch (error) {
            console.error('템플릿 삭제 오류:', error);
            alert('삭제 중 오류가 발생했습니다.');
        }
    };

    // 템플릿을 타입별로 분류
    const builtInTemplates = templates.filter(t => t.type === 'built-in').sort((a, b) => {
        // 기본 템플릿을 먼저 보여주기
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        return a.name.localeCompare(b.name);
    });
    const userTemplates = templates.filter(t => t.type === 'user-uploaded').sort((a, b) => {
        // 기본 템플릿을 먼저 보여주기
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        return a.name.localeCompare(b.name);
    });

    // 기본 템플릿 찾기
    const defaultTemplate = templates.find(t => t.is_default);

    // 컴포넌트가 마운트될 때 기본 템플릿이 있고 선택된 템플릿이 없으면 기본 템플릿 선택
    React.useEffect(() => {
        if (!selectedTemplateId && defaultTemplate) {
            onTemplateChange(defaultTemplate.id);
        }
    }, [selectedTemplateId, defaultTemplate, onTemplateChange]);

    return (
        <div className="space-y-6">
            {/* 템플릿 업로드 */}
            <div className="border border-gray-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-800 mb-3">새 템플릿 업로드</h3>
                <div className="space-y-3">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pptx"
                        onChange={handleFileUpload}
                        className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                        disabled={isUploading}
                    />
                    {uploadError && (
                        <div className="text-sm text-red-600 bg-red-50 p-2 rounded-md">
                            {uploadError}
                        </div>
                    )}
                    {isUploading && (
                        <div className="flex items-center space-x-2 text-sm text-blue-600">
                            <div className="animate-spin h-4 w-4 rounded-full border-2 border-blue-200 border-t-blue-600"></div>
                            <span>업로드 중...</span>
                        </div>
                    )}
                </div>
            </div>

            {/* 사용자 업로드 템플릿 */}
            {userTemplates.length > 0 && (
                <div>
                    <h3 className="text-sm font-medium text-gray-800 mb-3">업로드된 템플릿</h3>
                    <div className="space-y-2">
                        {userTemplates.map((template) => (
                            <div
                                key={template.id}
                                className={`p-3 rounded-lg border transition-colors ${selectedTemplateId === template.id
                                    ? 'border-blue-300 bg-blue-50'
                                    : 'border-gray-200 hover:bg-gray-50'
                                    }`}
                            >
                                <div className="flex items-center justify-between">
                                    <div
                                        className="flex-1 cursor-pointer"
                                        onClick={() => onTemplateChange(template.id)}
                                    >
                                        <div className="text-sm font-medium text-gray-900">
                                            {template.name}
                                            {template.is_default && (
                                                <span className="ml-2 inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                                                    기본 템플릿
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-xs text-gray-500 mt-1">
                                            {template.is_content_cleaned ? (
                                                <span className="text-green-600">✓ 메타데이터 추출 완료</span>
                                            ) : (
                                                <span className="text-yellow-600">⚠ 메타데이터 추출 중...</span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center space-x-1">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handlePreviewTemplate(template);
                                            }}
                                            className="p-1.5 text-gray-500 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                                            title="템플릿 미리보기"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDownloadTemplate(template);
                                            }}
                                            className="p-1.5 text-gray-500 hover:text-green-700 hover:bg-green-50 rounded-md transition-colors"
                                            title="템플릿 파일 다운로드"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                            </svg>
                                        </button>
                                        {!template.is_default && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleSetDefaultTemplate(template.id);
                                                }}
                                                className="p-1.5 text-gray-500 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                                                title="기본 템플릿으로 설정"
                                            >
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                                </svg>
                                            </button>
                                        )}
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDeleteTemplate(template.id);
                                            }}
                                            className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
                                            title="템플릿 삭제"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 기본 템플릿 */}
            {builtInTemplates.length > 0 && (
                <div>
                    <h3 className="text-sm font-medium text-gray-800 mb-3">기본 템플릿</h3>
                    <div className="space-y-2">
                        {builtInTemplates.map((template) => (
                            <div
                                key={template.id}
                                className={`p-3 rounded-lg border transition-colors ${selectedTemplateId === template.id
                                    ? 'border-blue-300 bg-blue-50'
                                    : 'border-gray-200 hover:bg-gray-50'
                                    }`}
                            >
                                <div className="flex items-center justify-between">
                                    <div
                                        className="flex-1 cursor-pointer"
                                        onClick={() => onTemplateChange(template.id)}
                                    >
                                        <div className="text-sm font-medium text-gray-900">
                                            {template.name}
                                            {template.is_default && (
                                                <span className="ml-2 inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                                                    기본 템플릿
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center space-x-1">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handlePreviewTemplate(template);
                                            }}
                                            className="p-1.5 text-gray-500 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                                            title="템플릿 미리보기"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDownloadTemplate(template);
                                            }}
                                            className="p-1.5 text-gray-500 hover:text-green-700 hover:bg-green-50 rounded-md transition-colors"
                                            title="템플릿 파일 다운로드"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                            </svg>
                                        </button>
                                        {!template.is_default && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleSetDefaultTemplate(template.id);
                                                }}
                                                className="p-1.5 text-gray-500 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                                                title="기본 템플릿으로 설정"
                                            >
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                                </svg>
                                            </button>
                                        )}
                                        {isAdmin() && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteTemplate(template.id);
                                                }}
                                                className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
                                                title="템플릿 삭제"
                                            >
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                </svg>
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {templates.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                    <div className="text-sm">사용 가능한 템플릿이 없습니다.</div>
                    <div className="text-xs mt-1">PowerPoint 파일을 업로드해주세요.</div>
                </div>
            )}

            {/* 템플릿 미리보기 모달 */}
            {previewTemplate && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
                        {/* 헤더 */}
                        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-gray-900">
                                템플릿 미리보기: {previewTemplate.name}
                            </h3>
                            <div className="flex items-center space-x-3">
                                <button
                                    onClick={() => {
                                        onTemplateChange(previewTemplate.id);
                                        setPreviewTemplate(null);
                                    }}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
                                >
                                    이 템플릿 선택
                                </button>
                                <button
                                    onClick={() => setPreviewTemplate(null)}
                                    className="text-gray-400 hover:text-gray-600 transition-colors"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>

                        {/* 콘텐츠 */}
                        <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
                            {isLoadingPreview ? (
                                <div className="flex flex-col items-center justify-center py-12 text-center text-gray-500">
                                    <div className="animate-spin h-8 w-8 rounded-full border-4 border-gray-200 border-t-blue-600 mb-4"></div>
                                    <div className="text-sm">레이아웃 정보를 불러오는 중...</div>
                                </div>
                            ) : (
                                <div>
                                    {/* 실제 템플릿 파일 미리보기 */}
                                    <div className="mb-6">
                                        <h4 className="text-sm font-medium text-gray-800 mb-3">템플릿 파일 미리보기</h4>
                                        <div className="border border-gray-200 rounded-lg bg-gray-50" style={{ height: '400px' }}>
                                            <iframe
                                                src={`/api/v1/chat/presentation/templates/${encodeURIComponent(previewTemplate.id)}/file?token=${localStorage.getItem('ABEKM_token')}`}
                                                className="w-full h-full rounded-lg"
                                                title="템플릿 미리보기"
                                                onLoad={() => console.log('템플릿 PDF 로드 완료')}
                                                onError={(e) => console.error('템플릿 PDF 로드 실패:', e)}
                                            />
                                        </div>
                                    </div>

                                    {/* 레이아웃 정보 */}
                                    {previewLayouts.length > 0 && (
                                        <div className="mb-4">
                                            <h4 className="text-sm font-medium text-gray-800 mb-2">
                                                사용 가능한 레이아웃 ({previewLayouts.length}개)
                                            </h4>
                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                                {previewLayouts.map((layout, index) => (
                                                    <div
                                                        key={index}
                                                        className="border border-gray-200 rounded-lg p-3 bg-gray-50"
                                                    >
                                                        <div className="text-xs font-medium text-gray-700 mb-1">
                                                            {layout.name || `레이아웃 ${index + 1}`}
                                                        </div>
                                                        <div className="text-xs text-gray-500">
                                                            {layout.placeholders?.length || 0}개 플레이스홀더
                                                        </div>
                                                        {layout.placeholders && layout.placeholders.length > 0 && (
                                                            <div className="mt-2 text-xs text-gray-400">
                                                                {layout.placeholders.map((ph: any, i: number) => (
                                                                    <span key={i} className="inline-block bg-gray-200 rounded px-1.5 py-0.5 mr-1 mb-1">
                                                                        {ph.type}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                        <div className="text-sm text-blue-800">
                                            <div className="font-medium mb-1">💡 템플릿 정보</div>
                                            <div className="text-xs space-y-1">
                                                <div>• 타입: {previewTemplate.type === 'built-in' ? '기본 제공' : '사용자 업로드'}</div>
                                                <div>• 레이아웃 수: {previewLayouts.length}개</div>
                                                {previewTemplate.is_content_cleaned && <div>• ✅ 메타데이터 추출 완료</div>}
                                                {previewTemplate.dynamic_template_id && <div>• 🤖 AI 템플릿 최적화 적용</div>}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TemplateManager;

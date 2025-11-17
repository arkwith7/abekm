import React, { useEffect, useState } from 'react';
import { SlideLayoutSelection, TemplateLayout } from '../../../../../types/presentation';

interface Props {
    sectionIndex: number;
    sectionTitle: string;
    selectedLayoutIndex?: number;
    templateId?: string;
    onLayoutChange: (sectionIndex: number, selection: SlideLayoutSelection) => void;
    disabled?: boolean;
}

const LayoutSelector: React.FC<Props> = ({
    sectionIndex,
    sectionTitle,
    selectedLayoutIndex,
    templateId,
    onLayoutChange,
    disabled = false
}) => {
    const [layouts, setLayouts] = useState<TemplateLayout[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 템플릿 레이아웃 정보 로드
    useEffect(() => {
        if (!templateId) return;

        const fetchLayouts = async () => {
            setLoading(true);
            setError(null);

            try {
                const response = await fetch(
                    `/api/v1/chat/presentation/templates/${encodeURIComponent(templateId)}/layouts`,
                    {
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('wikl_token')}`
                        }
                    }
                );

                if (!response.ok) {
                    throw new Error('레이아웃 정보를 불러올 수 없습니다');
                }

                const data = await response.json();
                if (data.success && data.layouts?.layouts) {
                    setLayouts(data.layouts.layouts);
                } else {
                    throw new Error('레이아웃 데이터가 올바르지 않습니다');
                }
            } catch (err) {
                console.error('레이아웃 로드 실패:', err);
                setError(err instanceof Error ? err.message : '레이아웃 로드 실패');
            } finally {
                setLoading(false);
            }
        };

        fetchLayouts();
    }, [templateId]);

    const handleLayoutChange = (layoutIndex: number) => {
        const selectedLayout = layouts.find(l => l.layout_index === layoutIndex);
        if (!selectedLayout) return;

        const selection: SlideLayoutSelection = {
            slideIndex: sectionIndex,
            layoutIndex: layoutIndex,
            layoutName: selectedLayout.layout_name,
            layoutType: selectedLayout.layout_type
        };

        onLayoutChange(sectionIndex, selection);
    };

    const getLayoutDisplayName = (layout: TemplateLayout) => {
        const types: Record<string, string> = {
            'title-only': '제목만',
            'title-and-content': '제목+내용',
            'title-content-image': '제목+내용+이미지',
            'title-and-image': '제목+이미지',
            'content-only': '내용만',
            'custom-textbox': '사용자 정의',
            'blank': '빈 슬라이드'
        };

        return `${layout.layout_name} (${types[layout.layout_type] || layout.layout_type})`;
    };

    const getLayoutDescription = (layout: TemplateLayout) => {
        const features = [];
        if (layout.supports_title) features.push('제목');
        if (layout.supports_content) features.push('본문');
        if (layout.supports_image) features.push('이미지');
        if (layout.supports_chart) features.push('차트');

        return features.length > 0 ? `지원: ${features.join(', ')}` : '기본 레이아웃';
    };

    if (loading) {
        return (
            <div className="flex items-center space-x-2 text-sm text-gray-500">
                <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                <span>레이아웃 로드 중...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-sm text-red-500 bg-red-50 p-2 rounded">
                {error}
            </div>
        );
    }

    if (layouts.length === 0) {
        return (
            <div className="text-sm text-gray-500">
                사용 가능한 레이아웃이 없습니다
            </div>
        );
    }

    return (
        <div className="space-y-2">
            <div className="text-xs font-medium text-gray-600">
                슬라이드 레이아웃 선택
            </div>

            <select
                value={selectedLayoutIndex ?? -1}
                onChange={(e) => handleLayoutChange(parseInt(e.target.value))}
                disabled={disabled}
                className={`
          w-full px-3 py-2 text-sm border rounded-md
          ${disabled
                        ? 'bg-gray-50 text-gray-400 cursor-not-allowed'
                        : 'bg-white border-gray-300 hover:border-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
                    }
        `}
            >
                <option value={-1}>레이아웃 선택...</option>
                {layouts.map((layout) => (
                    <option key={layout.layout_index} value={layout.layout_index}>
                        {getLayoutDisplayName(layout)}
                    </option>
                ))}
            </select>

            {selectedLayoutIndex !== undefined && selectedLayoutIndex >= 0 && (
                <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                    {(() => {
                        const layout = layouts.find(l => l.layout_index === selectedLayoutIndex);
                        return layout ? getLayoutDescription(layout) : '';
                    })()}
                </div>
            )}
        </div>
    );
};

export default LayoutSelector;

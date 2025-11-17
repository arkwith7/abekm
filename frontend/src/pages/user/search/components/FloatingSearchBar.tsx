import { ChevronDown, ChevronUp, Filter, Image, Search, X } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useSidebar } from '../../../../contexts/SidebarContext';
import { SearchFilters } from '../types';

interface FloatingSearchBarProps {
    query: string;
    setQuery: (query: string) => void;
    isSearching: boolean;
    onSearch: (searchQuery?: string, imageFile?: File | null) => void;
    onClear: () => void;
    filters: SearchFilters;
    updateFilters: (filters: Partial<SearchFilters>) => void;
    totalCount?: number;
}

export const FloatingSearchBar: React.FC<FloatingSearchBarProps> = ({
    query,
    setQuery,
    isSearching,
    onSearch,
    onClear,
    filters,
    updateFilters,
    totalCount = 0
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const { isOpen: isSidebarOpen } = useSidebar();
    const [contentOffset, setContentOffset] = useState(0); // dynamic left offset (sidebar width)
    const [isFilterOpen, setIsFilterOpen] = useState(false);
    const [selectedImage, setSelectedImage] = useState<File | null>(null);
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const [imageMode, setImageMode] = useState(false);
    const [isVisible, setIsVisible] = useState(true); // 스크롤 시 보이기/숨기기
    const [lastScrollY, setLastScrollY] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Calculate offset so that centering is relative to content area (excluding sidebar)
    useEffect(() => {
        const calcOffset = () => {
            if (typeof window === 'undefined') return;
            if (window.innerWidth < 768) {
                setContentOffset(0); // mobile: full width
            } else {
                setContentOffset(isSidebarOpen ? 256 : 64); // match w-64 / collapsed width
            }
        };
        calcOffset();
        window.addEventListener('resize', calcOffset);
        return () => window.removeEventListener('resize', calcOffset);
    }, [isSidebarOpen]);

    // 스크롤 시 검색창 자동 숨김/표시
    useEffect(() => {
        const handleScroll = () => {
            const currentScrollY = window.scrollY;

            // 스크롤 내릴 때 (아래로) 숨김, 올릴 때 (위로) 표시
            if (currentScrollY > lastScrollY && currentScrollY > 100) {
                setIsVisible(false);
            } else {
                setIsVisible(true);
            }

            setLastScrollY(currentScrollY);
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
        return () => window.removeEventListener('scroll', handleScroll);
    }, [lastScrollY]);
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const hasText = query.trim().length > 0;
        if (!hasText && !selectedImage) {
            return;
        }

        onSearch(hasText ? query : undefined, selectedImage);
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const toggleExpanded = () => {
        setIsExpanded(!isExpanded);
        if (!isExpanded) {
            setIsFilterOpen(false);
        }
    };

    // 이미지 업로드 핸들러
    const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드할 수 있습니다.');
                return;
            }
            if (file.size > 10 * 1024 * 1024) {
                alert('이미지 파일 크기는 10MB 이하여야 합니다.');
                return;
            }
            setSelectedImage(file);
            setImageMode(true);
            const reader = new FileReader();
            reader.onloadend = () => {
                setImagePreview(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleRemoveImage = () => {
        setSelectedImage(null);
        setImagePreview(null);
        setImageMode(false);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    // 클립보드 이미지 붙여넣기 지원
    const handlePaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
        console.log('📋 Paste event triggered');
        const items = event.clipboardData.items;
        console.log('📋 Clipboard items:', items.length);

        // 클립보드 아이템 타입 확인
        for (let i = 0; i < items.length; i++) {
            console.log(`📋 Item ${i}: type=${items[i].type}, kind=${items[i].kind}`);
        }

        // 이미지 찾기
        let imageFound = false;
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.type.startsWith('image/')) {
                imageFound = true;
                console.log('✅ Image found in clipboard!');
                event.preventDefault();
                const file = item.getAsFile();
                if (!file) {
                    console.error('❌ Failed to get file from clipboard item');
                    continue;
                }

                console.log('📷 Image file:', file.name, file.size, 'bytes');

                if (file.size > 10 * 1024 * 1024) {
                    alert('이미지 파일 크기는 10MB 이하여야 합니다.');
                    return;
                }

                setSelectedImage(file);
                setImageMode(true);
                setQuery('');

                if (!isMultimodalMode) {
                    console.log('🔄 Switching to multimodal mode');
                    updateFilters({ searchType: 'multimodal' });
                }

                const reader = new FileReader();
                reader.onloadend = () => {
                    console.log('✅ Image preview loaded');
                    setImagePreview(reader.result as string);
                };
                reader.readAsDataURL(file);
                break;
            }
        }

        if (!imageFound) {
            console.log('ℹ️ No image found in clipboard (텍스트만 있거나 클립보드가 비어있음)');
        }
    };

    // 멀티모달/CLIP 검색 모드인지 확인
    const isMultimodalMode = filters.searchType === 'multimodal' || filters.searchType === 'clip';

    return (
        <>
            {/* 검색창 표시/숨김 토글 버튼 (검색창이 숨겨졌을 때만 표시) */}
            {!isVisible && (
                <button
                    onClick={() => setIsVisible(true)}
                    className="fixed bottom-6 right-6 z-50 bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition-all duration-300 animate-bounce"
                    title="검색창 표시"
                >
                    <Search className="w-6 h-6" />
                </button>
            )}

            <div
                className={`fixed bottom-6 z-50 transition-all duration-300 ${isVisible ? 'translate-y-0 opacity-100' : 'translate-y-32 opacity-0 pointer-events-none'
                    }`}
                style={{ left: contentOffset, width: `calc(100% - ${contentOffset}px)` }}
            >
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-center">
                        <div className="w-full max-w-4xl bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
                            {/* 기본 검색창 */}
                            <div className="px-4 py-4">
                                {/* 이미지 미리보기 (상단에 표시) */}
                                {imagePreview && (
                                    <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <img
                                                src={imagePreview}
                                                alt="검색 이미지"
                                                className="w-16 h-16 object-cover rounded border border-gray-300"
                                            />
                                            <div className="text-sm">
                                                <p className="font-medium text-gray-700">{selectedImage?.name || '클립보드 이미지'}</p>
                                                <p className="text-gray-500">
                                                    {selectedImage && `${(selectedImage.size / 1024).toFixed(1)} KB`}
                                                </p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={handleRemoveImage}
                                            className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                            title="이미지 제거"
                                        >
                                            <X className="w-5 h-5" />
                                        </button>
                                    </div>
                                )}

                                <form onSubmit={handleSubmit} className="flex items-center space-x-3">
                                    <div className="flex-1 relative">
                                        <input
                                            type="text"
                                            value={query}
                                            onChange={(e) => setQuery(e.target.value)}
                                            onKeyPress={handleKeyPress}
                                            onPaste={handlePaste}
                                            placeholder={imageMode ? '🖼️ 이미지로 검색 중... (텍스트 추가 가능)' : (isMultimodalMode ? '텍스트 입력 또는 이미지 붙여넣기 (Ctrl+V)' : '하이브리드 검색으로 더 정확한 결과를 찾아보세요')}
                                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-24"
                                            disabled={isSearching}
                                        />
                                        {/* 이미지 업로드 버튼 (멀티모달 모드) */}
                                        {isMultimodalMode && (
                                            <button
                                                type="button"
                                                onClick={() => fileInputRef.current?.click()}
                                                className="absolute right-14 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-blue-600"
                                                title="이미지로 검색"
                                            >
                                                <Image className="w-5 h-5" />
                                            </button>
                                        )}
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept="image/*"
                                            onChange={handleImageSelect}
                                            className="hidden"
                                        />
                                        {query && !imageMode && (
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setQuery('');
                                                    onClear();
                                                }}
                                                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                            >
                                                <X className="w-5 h-5" />
                                            </button>
                                        )}
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={(isSearching || (!query.trim() && !selectedImage))}
                                        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
                                    >
                                        <Search className="w-5 h-5" />
                                        <span>{isSearching ? '검색중...' : '검색'}</span>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setIsFilterOpen(!isFilterOpen)}
                                        className="px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center space-x-2"
                                    >
                                        <Filter className="w-5 h-5" />
                                        <span>필터</span>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={toggleExpanded}
                                        className="px-3 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                                        title={isExpanded ? '축소' : '확장'}
                                    >
                                        {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronUp className="w-5 h-5" />}
                                    </button>
                                </form>

                                {totalCount > 0 && (
                                    <div className="mt-2 text-sm text-gray-600 text-center">
                                        총 <span className="font-medium text-blue-600">{totalCount.toLocaleString()}</span>개의 결과
                                    </div>
                                )}
                            </div>
                            {isExpanded && (
                                <div className="border-t border-gray-200 p-4 bg-gray-50">
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">검색 방식</label>
                                            <select
                                                value={filters.searchType}
                                                onChange={(e) => updateFilters({ searchType: e.target.value as any })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            >
                                                <option value="hybrid">하이브리드 (추천)</option>
                                                <option value="vector_only">벡터 유사도</option>
                                                <option value="keyword_only">키워드</option>
                                                <option value="multimodal">🎨 멀티모달 (이미지 우선)</option>
                                                <option value="clip">🖼️ CLIP (이미지 검색)</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">지식 컨테이너</label>
                                            <select
                                                value={filters.containerIds.length > 0 ? filters.containerIds[0] : ''}
                                                onChange={(e) => updateFilters({
                                                    containerIds: e.target.value ? [e.target.value] : []
                                                })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            >
                                                <option value="">전체 컨테이너</option>
                                                <option value="wj_root">용진</option>
                                                <option value="wj_ceo">CEO직속</option>
                                                <option value="wj_hr">인사전략팀</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">파일 형식</label>
                                            <select
                                                value={filters.documentTypes.length > 0 ? filters.documentTypes[0] : ''}
                                                onChange={(e) => updateFilters({
                                                    documentTypes: e.target.value ? [e.target.value] : []
                                                })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            >
                                                <option value="">모든 형식</option>
                                                <option value="pdf">PDF</option>
                                                <option value="doc">Word</option>
                                                <option value="ppt">PowerPoint</option>
                                                <option value="xls">Excel</option>
                                                <option value="txt">텍스트</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">시작 날짜</label>
                                            <input
                                                type="date"
                                                value={filters.dateRange?.start || ''}
                                                onChange={(e) => updateFilters({
                                                    dateRange: { ...filters.dateRange, start: e.target.value }
                                                })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">종료 날짜</label>
                                            <input
                                                type="date"
                                                value={filters.dateRange?.end || ''}
                                                onChange={(e) => updateFilters({
                                                    dateRange: { ...filters.dateRange, end: e.target.value }
                                                })}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            />
                                        </div>
                                    </div>
                                    <div className="mt-4 flex justify-end">
                                        <button
                                            type="button"
                                            onClick={() => updateFilters({
                                                searchType: 'hybrid',
                                                containerIds: [],
                                                documentTypes: [],
                                                dateRange: { start: undefined, end: undefined }
                                            })}
                                            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                                        >
                                            필터 초기화
                                        </button>
                                    </div>
                                </div>
                            )}
                            {isFilterOpen && (
                                <div className="border-t border-gray-200 p-4 bg-blue-50">
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">유사도 임계값</label>
                                            <div className="flex items-center space-x-4">
                                                <input
                                                    type="range"
                                                    min="0"
                                                    max="1"
                                                    step="0.1"
                                                    value={filters.scoreThreshold}
                                                    onChange={(e) => updateFilters({ scoreThreshold: parseFloat(e.target.value) })}
                                                    className="flex-1"
                                                />
                                                <span className="text-sm text-gray-600 min-w-12">
                                                    {(filters.scoreThreshold * 100).toFixed(0)}%
                                                </span>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">하위 컨테이너 포함</label>
                                            <label className="flex items-center">
                                                <input
                                                    type="checkbox"
                                                    checked={filters.includeSubContainers}
                                                    onChange={(e) => updateFilters({ includeSubContainers: e.target.checked })}
                                                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                                />
                                                <span className="ml-2 text-sm text-gray-700">
                                                    선택한 컨테이너의 하위 컨테이너도 검색에 포함
                                                </span>
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

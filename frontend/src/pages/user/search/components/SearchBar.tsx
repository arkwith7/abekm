import { Image, X } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { getSearchSuggestions } from '../../../../services/searchService';

interface SearchBarProps {
  query: string;
  setQuery: (query: string) => void;
  isSearching: boolean;
  onSearch: (searchQuery?: string, imageFile?: File | null) => void;
  onClear?: () => void;
  enableImageUpload?: boolean; // 멀티모달 검색 활성화 여부
}

const SearchBar: React.FC<SearchBarProps> = ({
  query,
  setQuery,
  isSearching,
  onSearch,
  onClear,
  enableImageUpload = false
}) => {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageMode, setImageMode] = useState(false); // 이미지 검색 모드 플래그
  const searchBarRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const fetchSuggestions = async () => {
      try {
        const suggestionResults = await getSearchSuggestions(query);
        setSuggestions(suggestionResults);
        setShowSuggestions(true);
      } catch (error) {
        console.error('제안 가져오기 실패:', error);
        setSuggestions([]);
        setShowSuggestions(false);
      }
    };

    const timeoutId = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timeoutId);
  }, [query]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchBarRef.current && !searchBarRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    setTimeout(() => onSearch(suggestion, selectedImage), 100);
  };

  // 이미지 업로드 핸들러
  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // 이미지 파일만 허용
      if (!file.type.startsWith('image/')) {
        alert('이미지 파일만 업로드할 수 있습니다.');
        return;
      }

      // 파일 크기 제한 (10MB)
      if (file.size > 10 * 1024 * 1024) {
        alert('이미지 파일 크기는 10MB 이하여야 합니다.');
        return;
      }

      setSelectedImage(file);

      // 미리보기 생성
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // 이미지 제거 핸들러
  const handleRemoveImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    setImageMode(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // 클립보드 붙여넣기 핸들러 (NEW!)
  const handlePaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
    if (!enableImageUpload) return;

    const items = event.clipboardData.items;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        event.preventDefault();

        const file = items[i].getAsFile();
        if (!file) continue;

        // 파일 크기 제한 (10MB)
        if (file.size > 10 * 1024 * 1024) {
          alert('이미지 파일 크기는 10MB 이하여야 합니다.');
          return;
        }

        setSelectedImage(file);
        setImageMode(true);
        setQuery(''); // 텍스트 쿼리 초기화

        // 미리보기 생성
        const reader = new FileReader();
        reader.onloadend = () => {
          setImagePreview(reader.result as string);
        };
        reader.readAsDataURL(file);

        console.log('📎 클립보드 이미지 붙여넣기 완료:', file.name, file.size);
        break;
      }
    }
  };

  // 검색 실행 시 이미지 포함
  const handleSearch = () => {
    onSearch(imageMode ? undefined : query, selectedImage);
    setShowSuggestions(false);
  };

  return (
    <div ref={searchBarRef} className="relative mb-4">
      {/* 이미지 검색 모드 표시 */}
      {imageMode && imagePreview && (
        <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Image className="w-5 h-5 text-blue-600" />
              <span className="text-sm font-medium text-blue-900">🖼️ 이미지 검색 모드</span>
            </div>
            <button
              onClick={handleRemoveImage}
              className="p-1 text-blue-400 hover:text-red-600"
              title="이미지 제거"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex items-center gap-3">
            <img
              src={imagePreview}
              alt="검색 이미지"
              className="w-20 h-20 object-cover rounded border-2 border-blue-300"
            />
            <div className="text-sm">
              <p className="font-medium text-gray-700">{selectedImage?.name || '클립보드 이미지'}</p>
              <p className="text-gray-500">
                {selectedImage && `${(selectedImage.size / 1024).toFixed(1)} KB`}
              </p>
              <p className="text-blue-600 text-xs mt-1">💡 유사한 이미지를 검색합니다</p>
            </div>
          </div>
        </div>
      )}

      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleSearch();
            }
          }}
          onPaste={handlePaste}  // 클립보드 붙여넣기 이벤트
          onFocus={() => setShowSuggestions(suggestions.length > 0)}
          placeholder={
            imageMode
              ? "🖼️ 이미지로 검색 중... (텍스트 추가 가능)"
              : enableImageUpload
                ? "텍스트 입력 또는 이미지 붙여넣기 (Ctrl+V)"
                : "문서 내용, 제목, 키워드로 검색하세요..."
          }
          className="w-full px-4 py-3 pr-24 text-lg border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm"
          disabled={imageMode}  // 이미지 모드에서는 텍스트 입력 비활성화
        />

        {/* 이미지 업로드 버튼 (멀티모달 검색 활성화 시) */}
        {enableImageUpload && (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="absolute right-14 top-3 p-1 text-gray-400 hover:text-blue-600"
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

        {query && onClear && !imageMode && (
          <button
            onClick={onClear}
            className="absolute right-14 top-3 p-1 text-gray-400 hover:text-red-600"
            title="검색어 지우기"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
        <button
          onClick={handleSearch}
          disabled={isSearching || (!query.trim() && !selectedImage)}
          className="absolute right-3 top-3 p-1 text-gray-400 hover:text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSearching ? (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m21 21-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
        </button>
      </div>

      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 bg-white border border-gray-300 rounded-lg mt-1 shadow-lg z-10 max-h-60 overflow-y-auto">
          {suggestions.map((suggestion, index) => (
            <div
              key={index}
              onClick={() => handleSuggestionClick(suggestion)}
              className="px-4 py-3 hover:bg-blue-50 cursor-pointer border-b last:border-b-0 flex items-center"
            >
              <svg className="w-4 h-4 text-gray-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span className="text-gray-900">{suggestion}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchBar;

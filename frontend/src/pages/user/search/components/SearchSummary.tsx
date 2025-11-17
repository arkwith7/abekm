import React from 'react';

interface SearchSummaryProps {
  query: string;
  totalCount: number;
  searchTime: number | null;
  isSearching: boolean;
  viewMode: 'list' | 'grid';
  setViewMode: (mode: 'list' | 'grid') => void;
  hasResults: boolean;
}

const SearchSummary: React.FC<SearchSummaryProps> = ({
  query,
  totalCount,
  searchTime,
  isSearching,
  viewMode,
  setViewMode,
  hasResults,
}) => {
  if (!query && !isSearching) return null;

  return (
    <div className="flex items-center justify-between text-sm text-gray-600">
      <div>
        {isSearching ? (
          <span>검색 중...</span>
        ) : hasResults ? (
          <span>
            "{query}"에 대한 검색결과 <strong>{totalCount}건</strong>
            {searchTime && <span className="ml-2">({searchTime}ms)</span>}
          </span>
        ) : (
          <span>"{query}"에 대한 검색 결과가 없습니다.</span>
        )}
      </div>
      
      {hasResults && (
        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-gray-100 rounded-md p-1">
            <button
              onClick={() => setViewMode('list')}
              className={`p-1 rounded text-xs ${viewMode === 'list' ? 'bg-white shadow' : ''}`}
            >
              ☰ 목록
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1 rounded text-xs ${viewMode === 'grid' ? 'bg-white shadow' : ''}`}
            >
              ⊞ 그리드
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchSummary;

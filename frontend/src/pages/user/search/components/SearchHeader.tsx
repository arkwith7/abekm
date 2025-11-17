import React from 'react';

interface SearchHeaderProps {
  searchType: string;
}

const SearchHeader: React.FC<SearchHeaderProps> = ({ searchType }) => {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">🔍 통합 지식검색</h1>
        <p className="text-sm text-gray-600 mt-1">하이브리드 검색으로 더 정확한 결과를 찾아보세요</p>
      </div>
      <div className="flex items-center space-x-2">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          {searchType === 'hybrid' ? '🔄 하이브리드' : 
           searchType === 'vector_only' ? '🧠 의미검색' : '🔤 키워드검색'}
        </span>
      </div>
    </div>
  );
};

export default SearchHeader;

import React from 'react';

interface EmptyStateProps {
  query: string;
  hasSearched: boolean;
  isSearching: boolean;
  hasError: boolean;
  hasResults: boolean;
  onRetry: () => void;
  onClear: () => void;
  isImageSearch?: boolean;
}

const EmptyState: React.FC<EmptyStateProps> = ({
  query,
  hasSearched,
  isSearching,
  hasError,
  hasResults,
  onRetry,
  onClear,
  isImageSearch = false
}) => {
  // 검색 결과가 있거나 로딩 중이면 아무것도 표시하지 않음
  if (hasResults || isSearching) return null;

  // 검색을 했지만 결과가 없고 에러도 없는 경우
  if (hasSearched && !hasError) {
    return (
      <div className="text-center py-12">
        <div className="w-24 h-24 mx-auto mb-6 bg-gray-100 rounded-full flex items-center justify-center">
          {isImageSearch ? (
            <span className="text-5xl">🖼️</span>
          ) : (
            <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-6-4h6m2 5.291A7.962 7.962 0 0112 15c-2.34 0-4.291-1.5-6.291-4.291M16 4h2a2 2 0 012 2v12a2 2 0 01-2 2h-2M4 6h2m0 0v12m0-12a2 2 0 012-2h12a2 2 0 012 2v2" />
            </svg>
          )}
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          {isImageSearch ? '유사한 이미지를 찾을 수 없습니다' : '검색 결과가 없습니다'}
        </h3>
        <p className="text-gray-600 mb-6">
          {isImageSearch
            ? '업로드하신 이미지와 유사한 문서나 이미지를 찾을 수 없습니다.'
            : `"${query}"와 관련된 문서를 찾을 수 없습니다.`
          }
        </p>

        <div className="space-y-4">
          <div className="bg-blue-50 rounded-lg p-4 max-w-md mx-auto">
            <h4 className="text-sm font-medium text-blue-900 mb-2">💡 검색 팁</h4>
            <ul className="text-sm text-blue-800 space-y-1 text-left">
              {isImageSearch ? (
                <>
                  <li>• 다른 이미지로 검색해보세요</li>
                  <li>• 이미지와 함께 텍스트 키워드를 추가해보세요</li>
                  <li>• 이미지 품질이 선명한지 확인해보세요</li>
                  <li>• 검색 방식을 멀티모달 또는 하이브리드로 변경해보세요</li>
                </>
              ) : (
                <>
                  <li>• 다른 키워드로 검색해보세요</li>
                  <li>• 검색 방식을 변경해보세요 (하이브리드 ↔ 의미검색 ↔ 키워드검색)</li>
                  <li>• 필터 조건을 완화해보세요</li>
                  <li>• 유사도 임계값을 낮춰보세요</li>
                </>
              )}
            </ul>
          </div>

          <div className="flex justify-center space-x-4">
            <button
              onClick={onRetry}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              다시 검색
            </button>
            <button
              onClick={onClear}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
            >
              검색 초기화
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 초기 상태 (검색하지 않은 상태)
  if (!hasSearched && !hasError) {
    return (
      <div className="text-center py-12">
        <div className="w-24 h-24 mx-auto mb-6 bg-gradient-to-br from-blue-100 to-purple-100 rounded-full flex items-center justify-center">
          <span className="text-4xl">🔍</span>
        </div>
        <h2 className="text-xl font-medium text-gray-900 mb-2">지식을 검색해보세요</h2>
        <p className="text-gray-600 mb-8">
          하이브리드 검색으로 의미 검색과 키워드 검색을 동시에 활용하여<br />
          더 정확하고 포괄적인 검색 결과를 제공합니다.
        </p>

        {/* 검색 방식 설명 카드 */}
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🧠</span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">의미 검색</h3>
              <p className="text-gray-600 text-sm">AI가 문맥과 의미를 이해하여 관련된 문서를 찾습니다</p>
            </div>

            <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🔤</span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">키워드 검색</h3>
              <p className="text-gray-600 text-sm">정확한 단어나 구문이 포함된 문서를 찾습니다</p>
            </div>

            <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🔄</span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">하이브리드</h3>
              <p className="text-gray-600 text-sm">두 방식을 결합하여 최적의 검색 결과를 제공합니다</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default EmptyState;

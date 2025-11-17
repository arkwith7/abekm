import React from 'react';

interface LoadMoreButtonProps {
  isLoading: boolean;
  onClick: () => void;
  remainingCount: number;
}

const LoadMoreButton: React.FC<LoadMoreButtonProps> = ({
  isLoading,
  onClick,
  remainingCount
}) => {
  return (
    <div className="text-center mt-8">
      <button
        onClick={onClick}
        disabled={isLoading}
        className="inline-flex items-center px-6 py-3 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? (
          <>
            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            더 불러오는 중...
          </>
        ) : (
          <>
            더 보기
            <span className="ml-2 text-sm text-gray-500">
              (남은 {remainingCount}개)
            </span>
          </>
        )}
      </button>
    </div>
  );
};

export default LoadMoreButton;

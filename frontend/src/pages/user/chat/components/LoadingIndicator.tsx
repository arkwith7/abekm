import React from 'react';
import { Bot } from 'lucide-react';

interface LoadingIndicatorProps {
  status?: 'searching' | 'generating' | 'streaming';
  message?: string;
}

const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ 
  status = 'generating', 
  message 
}) => {
  const getStatusMessage = () => {
    switch (status) {
      case 'searching':
        return message || '🔍 관련 문서를 검색하고 있습니다...';
      case 'generating':
        return message || '🤖 AI가 답변을 생성하고 있습니다...';
      case 'streaming':
        return message || '📝 답변을 작성하고 있습니다...';
      default:
        return message || 'AI가 응답을 생성하고 있습니다...';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'searching':
        return '🔍';
      case 'generating':
        return '🤖';
      case 'streaming':
        return '📝';
      default:
        return '🤖';
    }
  };

  return (
    <div className="w-full flex justify-start">
      {/* AI 아바타 */}
      <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center mr-3">
        <Bot className="w-6 h-6 text-white" />
      </div>

      {/* 로딩 메시지 */}
      <div className="flex-1 max-w-md">
        <div className="bg-white text-gray-900 border border-gray-100 px-4 py-3 rounded-2xl shadow-sm">
          <div className="flex items-center space-x-3">
            {/* 상태 아이콘 */}
            <span className="text-lg">{getStatusIcon()}</span>
            
            {/* 애니메이션 도트 */}
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
            <span className="text-sm text-gray-600">{getStatusMessage()}</span>
          </div>
          
          {/* 프로그레스 바 */}
          <div className="mt-2 w-full bg-gray-200 rounded-full h-1">
            <div 
              className="bg-gradient-to-r from-blue-400 to-purple-500 h-1 rounded-full animate-pulse" 
              style={{ 
                width: status === 'streaming' ? '80%' : '60%',
                animationDuration: status === 'streaming' ? '1s' : '2s'
              }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadingIndicator;
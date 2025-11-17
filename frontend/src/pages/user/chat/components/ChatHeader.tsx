import React from 'react';
import { RotateCcw } from 'lucide-react';

interface ChatHeaderProps {
  sessionId: string;
  messageCount: number;
  onClearMessages: () => void;
  onOpenSettings?: () => void;
  sessionType?: 'new' | 'loaded' | 'continued';
  originalSessionId?: string | null;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  sessionId,
  messageCount,
  onClearMessages,
  onOpenSettings,
  sessionType = 'new',
  originalSessionId
}) => {
  // 세션 상태에 따른 표시 정보
  const getSessionInfo = () => {
    switch (sessionType) {
      case 'new':
        return messageCount > 0 ? `새 대화 - ${messageCount}개 메시지` : '새 대화';
      case 'loaded':
        return `기존 대화 로드 - ${messageCount}개 메시지`;
      case 'continued':
        return `기존 대화 계속 - ${messageCount}개 메시지`;
      default:
        return messageCount > 0 ? `${messageCount}개 메시지` : '';
    }
  };

  const getSessionColor = () => {
    switch (sessionType) {
      case 'new':
        return 'text-blue-600';
      case 'loaded':
        return 'text-green-600';
      case 'continued':
        return 'text-orange-600';
      default:
        return 'text-gray-500';
    }
  };

  return (
    <div className="bg-white/95 backdrop-blur-sm border-b border-gray-100 px-4 py-2 sticky top-0 z-40">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        {/* 세션 정보 (좌측) */}
        <div className={`text-sm font-medium ${getSessionColor()}`}>
          {getSessionInfo()}
          {originalSessionId && sessionType === 'continued' && (
            <div className="text-xs text-gray-400 mt-1">
              원본: {originalSessionId.substring(0, 12)}...
            </div>
          )}
        </div>

        {/* 대화 저장 후 초기화 버튼 (우측) */}
        <button
          onClick={() => {
            console.log('🔥 ChatHeader: 대화 저장 후 초기화 버튼 클릭!');
            onClearMessages();
          }}
          className="flex items-center justify-center w-8 h-8 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
          title="현재 대화를 저장하고 새 대화 시작"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default ChatHeader;
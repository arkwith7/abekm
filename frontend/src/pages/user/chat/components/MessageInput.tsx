import React, { useState, useRef, useEffect } from 'react';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  placeholder?: string;
}

const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  isLoading,
  placeholder = "메시지를 입력하세요... (Shift+Enter로 줄바꿈, Enter로 전송)"
}) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSendMessage(message.trim());
      setMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    
    // 자동 높이 조절
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  };

  useEffect(() => {
    if (textareaRef.current && !isLoading) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  const suggestedPrompts = [
    "프로젝트 계획서 PPT를 만들어줘",
    "회계 정책 기반으로 보고서 초안 작성해줘",
    "마케팅 전략 엑셀 템플릿 생성해줘",
    "기술 문서를 요약해줘"
  ];

  return (
    <div className="bg-white border-t border-gray-200 px-6 py-4">
      {/* 제안 프롬프트 (메시지가 비어있을 때만 표시) */}
      {!message.trim() && (
        <div className="mb-4">
          <div className="text-sm text-gray-600 mb-2">💡 제안 프롬프트:</div>
          <div className="flex flex-wrap gap-2">
            {suggestedPrompts.map((prompt, index) => (
              <button
                key={index}
                onClick={() => setMessage(prompt)}
                className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors"
                disabled={isLoading}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 메시지 입력 폼 */}
      <form onSubmit={handleSubmit} className="flex items-end space-x-3">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isLoading}
            rows={1}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
            style={{ maxHeight: '120px' }}
          />
          
          {/* 문자 수 표시 */}
          <div className="absolute bottom-1 right-2 text-xs text-gray-400">
            {message.length}/2000
          </div>
        </div>

        <button
          type="submit"
          disabled={!message.trim() || isLoading}
          className="flex-shrink-0 w-12 h-12 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-lg transition-colors flex items-center justify-center"
        >
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>
      </form>

      {/* 도움말 텍스트 */}
      <div className="mt-2 text-xs text-gray-500 text-center">
        Shift+Enter로 줄바꿈, Enter로 전송 • 최대 2000자
      </div>
    </div>
  );
};

export default MessageInput;
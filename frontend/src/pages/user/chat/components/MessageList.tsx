import React, { useMemo } from 'react';
import { useSelectedDocuments } from '../../../../contexts/GlobalAppContext';
import { ChatMessage, ConversationState } from '../types/chat.types';
import { annotateMessagesWithPresentationIntent } from '../utils/intent';
import ConversationContextToggle from './ConversationContextToggle';
import LoadingIndicator from './LoadingIndicator';
import MessageBubble from './MessageBubble';
import PPTReasoningPanel from './presentation/PPTReasoningPanel';
import ReasoningPanel from './ReasoningPanel';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  onOpenDocument?: (doc: { id: string; file_name: string; file_extension?: string; title?: string }) => void;
  conversationState?: ConversationState | null;
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  messagesEndRef,
  onOpenDocument,
  conversationState
}) => {
  const { selectedDocuments } = useSelectedDocuments();
  const firstViewHint = useMemo(() => {
    if (messages.length > 0) return null;
    if (selectedDocuments.length === 0) return null;
    const topNames = selectedDocuments.map((d: any) => d.fileName).slice(0, 2);
    const more = selectedDocuments.length > 2 ? ` 외 ${selectedDocuments.length - 2}개` : '';
    return `선택 문서: ${topNames.join(', ')}${more}`;
  }, [messages.length, selectedDocuments]);
  const showQuick = messages.length === 0 && selectedDocuments.length > 0;
  // PPT 의도 감지된 메시지 배열 생성 (메모이제이션 가능하지만 messages 길이가 크지 않다면 단순 처리)
  const annotatedMessages = useMemo(() => annotateMessagesWithPresentationIntent(messages), [messages]);

  const renderedMessages: React.ReactNode[] = [];

  annotatedMessages.forEach((message, idx) => {
    const previousMessage = idx > 0 ? annotatedMessages[idx - 1] : null;

    // 모든 assistant 메시지 앞에 대화 컨텍스트 토글 표시 (이전 메시지가 user인 경우)
    if (
      message.role === 'assistant' &&
      previousMessage?.role === 'user'
    ) {
      // 🆕 메시지 자체의 conversationContext를 우선 사용, 없으면 전역 conversationState 사용
      const contextToDisplay = message.conversationContext || conversationState;

      if (contextToDisplay) {
        renderedMessages.push(
          <ConversationContextToggle
            key={`conversation-context-${message.id || idx}`}
            state={contextToDisplay}
            isLoading={isLoading}
          />
        );
      }
    }

    renderedMessages.push(
      <MessageBubble key={`${message.id || 'msg'}-${idx}`} message={message} onOpenDocument={onOpenDocument} />
    );

    // 🆕 assistant 메시지 뒤에 Reasoning 패널 표시 (있는 경우)
    if (message.role === 'assistant' && (message as any).reasoning) {
      renderedMessages.push(
        <div key={`reasoning-${message.id || idx}`} className="max-w-4xl mx-auto">
          <ReasoningPanel
            reasoning={(message as any).reasoning}
            isLoading={isLoading && idx === annotatedMessages.length - 1}
          />
        </div>
      );
    }

    // 🆕 PPT 생성 진행 상태 패널 표시 (pptReasoning이 있는 경우)
    if (message.role === 'assistant' && (message as any).pptReasoning) {
      const pptData = (message as any).pptReasoning;
      renderedMessages.push(
        <div key={`ppt-reasoning-${message.id || idx}`} className="max-w-4xl mx-auto">
          <PPTReasoningPanel
            data={pptData}
            isLoading={isLoading && idx === annotatedMessages.length - 1 && !pptData.isComplete}
            mode={pptData.mode || 'quick'}
          />
        </div>
      );
    }
  });

  return (
    <div
      className="w-full px-1 py-6 space-y-6 overflow-x-hidden"
      style={{ scrollbarGutter: 'stable both-edges' }}
    >
      {/* 초기 힌트: 선택 문서 요약 + 안내 */}
      {firstViewHint && (
        <div className="max-w-2xl mx-auto w-full">
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="text-sm text-green-800 font-medium mb-1">RAG 준비 완료</div>
            <div className="text-sm text-green-700">{firstViewHint}</div>
            <div className="text-xs text-green-600 mt-1">이 문서들을 바탕으로 질문을 입력해 주세요.</div>
          </div>
        </div>
      )}
      {/* 추천 액션 칩 */}
      {showQuick && (
        <div className="max-w-2xl mx-auto w-full">
          <div className="flex flex-wrap gap-2">
            {[
              '두 문서 비교 요약',
              '핵심 포인트 5가지 추출',
              '중복/유사 내용 찾아줘',
              '의사결정용 요약 작성',
              '다음 단계 실행 항목 만들기'
            ].map((label) => (
              <span key={label} className="px-2.5 py-1 text-xs rounded-full bg-gray-100 text-gray-700 border border-gray-200">
                {label}
              </span>
            ))}
          </div>
        </div>
      )}
      {/* 기본 환영 메시지 제거: 문서 기반 안내가 더 유용함 */}

      {/* 메시지들 */}
      {renderedMessages}

      {/* 로딩 인디케이터 */}
      {isLoading && (
        <div className="w-full">
          <LoadingIndicator />
        </div>
      )}

      {/* 스크롤 앵커 */}
      <div ref={messagesEndRef} className="h-1" />
    </div>
  );
};

export default MessageList;
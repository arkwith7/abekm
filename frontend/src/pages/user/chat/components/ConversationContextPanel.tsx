import { RefreshCcw } from 'lucide-react';
import React from 'react';
import { ConversationState } from '../types/chat.types';

interface ConversationContextPanelProps {
  state: ConversationState | null;
  onRefresh?: () => void;
  isLoading?: boolean;
  showHeader?: boolean;
}

const ConversationContextPanel: React.FC<ConversationContextPanelProps> = ({
  state,
  onRefresh,
  isLoading,
  showHeader = true
}) => {
  if (!state) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-white/60 p-4 text-sm text-gray-500">
        <p className="font-medium text-gray-600">대화 컨텍스트 분석 준비 중</p>
        <p className="mt-1 leading-relaxed">
          질문을 입력하면 AI가 요약·키워드·관련 문서를 분석하여 여기에 표시합니다.
        </p>
      </div>
    );
  }

  const {
    summary,
    keywords,
    relevantDocuments,
    topicContinuity,
    lastIntent,
    updatedAt,
    hints
  } = state;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      {showHeader && (
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-blue-600">대화 컨텍스트</p>
            <p className="text-xs text-gray-400">마지막 업데이트 {new Date(updatedAt).toLocaleTimeString()}</p>
          </div>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2 py-1 text-xs text-gray-500 hover:border-blue-300 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading}
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              새로고침
            </button>
          )}
        </div>
      )}

      {summary && (
        <div className="rounded-xl bg-blue-50/60 p-3 text-sm leading-relaxed text-blue-900">
          {summary}
        </div>
      )}

      {keywords?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">핵심 키워드</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {keywords.map((keyword, index) => (
              <span
                key={`${keyword}-${index}`}
                className="inline-flex items-center rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-xs text-blue-600"
              >
                #{keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {relevantDocuments?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">선택된 문서</p>
          <ul className="mt-2 space-y-2">
            {relevantDocuments.slice(0, 5).map((doc, index) => (
              <li
                key={`${doc.id ?? 'doc'}-${index}`}
                className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-600"
              >
                <span className="font-medium text-gray-700">{doc.title}</span>
                {doc.containerName && (
                  <span className="ml-2 text-gray-400">({doc.containerName})</span>
                )}
                {typeof doc.similarity === 'number' && (
                  <span className="ml-2 text-blue-500">
                    {(doc.similarity * 100).toFixed(0)}%
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 grid gap-3 text-xs text-gray-500 sm:grid-cols-2">
        <div>
          <p className="font-semibold text-gray-600">주제 연속성</p>
          <p className="mt-1 text-sm text-gray-700">{Math.round(topicContinuity * 100)}%</p>
        </div>
        <div>
          <p className="font-semibold text-gray-600">최근 의도</p>
          <p className="mt-1 text-sm text-gray-700">{lastIntent || '분석 중'}</p>
        </div>
      </div>

      {hints && hints.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
          <p className="font-semibold">다음 질문 힌트</p>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {hints.map((hint, index) => (
              <li key={`${hint}-${index}`}>{hint}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ConversationContextPanel;


import React, { useState } from 'react';
import { ChunkViewer } from './ChunkViewer';

// 🆕 Legacy reference interface (기존 ChatReference - chat.types.ts와 일치)
interface ChatReference {
  title: string;
  excerpt: string;
  url?: string;
  file_name?: string;
  file_bss_info_sno?: number;
  chunk_index?: number;
  similarity_score?: number;
  page_number?: number;
  keywords?: string;
  document_type?: string;
  relevance_grade?: string;
  relevance_percentage?: number;
  ai_summary?: string;
  user_friendly_position?: string;
  chunk_position?: string;
  section_title?: string;
  content_length?: number;
}

// 🆕 Detailed chunk interface (신규 백엔드 데이터 - chat.types.ts와 일치)
interface DetailedChunk {
  index: number;
  file_id: number;  // number 타입 (chat.types.ts와 일치)
  file_name: string;
  chunk_index: number;
  page_number?: number | null;
  content_preview: string;
  similarity_score: number;
  search_type: string;
  section_title?: string | null;
  // 🆕 인터넷 검색 결과용 추가 필드
  full_content?: string;
  url?: string;
}

// Union type for references
type Reference = ChatReference | DetailedChunk;

interface ReferencePanelProps {
  references: Reference[];
  contextInfo?: {
    search_mode?: string;
    total_chunks?: number;
    chunks_count?: number;
    documents_count?: number;
    context_tokens?: number;
    reranking_applied?: boolean;
    rag_used?: boolean;
  };
  ragStats?: {
    query_length: number;
    total_candidates: number;
    final_chunks: number;
    avg_similarity: number | null;
    search_time: number | null;
    search_mode: string;
    has_korean_keywords: boolean;
    embedding_dimension: number;
    embedding_provider: string | null;
    llm_provider: string | null;  // 백엔드 .env 설정 사용
  };
}

const ReferencePanel: React.FC<ReferencePanelProps> = ({
  references,
  contextInfo,
  ragStats
}) => {
  const [chunkViewerOpen, setChunkViewerOpen] = useState(false);
  const [selectedReference, setSelectedReference] = useState<Reference | null>(null);

  // 🆕 Type guard to check if reference is DetailedChunk
  const isDetailedChunk = (ref: Reference): ref is DetailedChunk => {
    return 'content_preview' in ref && 'file_id' in ref;
  };

  const handleViewChunk = (ref: Reference) => {
    setSelectedReference(ref);
    setChunkViewerOpen(true);
  };

  // 🆕 Extract common fields from both types
  const getDisplayData = (ref: Reference, index: number) => {
    if (isDetailedChunk(ref)) {
      return {
        displayIndex: ref.index,
        fileName: ref.file_name,
        excerpt: ref.content_preview,
        chunkIndex: ref.chunk_index,
        pageNumber: ref.page_number,
        similarityScore: ref.similarity_score,
        sectionTitle: ref.section_title,
        searchType: ref.search_type,
        fileId: ref.file_id,
        keywords: null,
        documentType: null,
        relevanceGrade: null,
        aiSummary: null,
        url: ref.url || null,
        fullContent: ref.full_content || ref.content_preview,
        isInternetSearch: ref.search_type === 'internet' || ref.file_id === 0
      };
    } else {
      return {
        displayIndex: index + 1,
        fileName: ref.file_name || ref.title || 'Unknown',
        excerpt: ref.excerpt,
        chunkIndex: ref.chunk_index || 0,
        pageNumber: ref.page_number,
        similarityScore: ref.similarity_score,
        sectionTitle: ref.section_title,
        searchType: null,
        fileId: ref.file_bss_info_sno,
        keywords: ref.keywords,
        documentType: ref.document_type,
        relevanceGrade: ref.relevance_grade,
        aiSummary: ref.ai_summary,
        url: ref.url,
        fullContent: ref.excerpt,
        isInternetSearch: false
      };
    }
  };

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4 w-full overflow-hidden">
      {/* 참고자료 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-2 w-full">
        <h4 className="text-sm font-medium text-gray-900">
          📚 참고자료 ({contextInfo?.chunks_count || references.length}개)
        </h4>
        {contextInfo?.documents_count && (
          <div className="text-xs text-gray-500">
            {contextInfo.documents_count}개 문서
          </div>
        )}
        {ragStats && ragStats.avg_similarity !== null && ragStats.avg_similarity !== undefined && (
          <div className="text-xs text-gray-500">
            평균 관련도: {(ragStats.avg_similarity * 100).toFixed(1)}%
          </div>
        )}
      </div>

      {/* 참고자료 목록 */}
      <div className="space-y-2">
        {references.map((ref, index) => {
          const data = getDisplayData(ref, index);

          return (
            <div
              key={index}
              className="bg-white border border-gray-200 rounded-lg p-3 hover:shadow-sm transition-shadow w-full overflow-hidden"
            >
              {/* 파일명과 순서 - Flex 레이아웃으로 변경하여 wrap 지원 */}
              <div className="flex flex-wrap items-center gap-2 mb-2 w-full">
                {/* 왼쪽: 순번과 파일명 */}
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 shrink-0">
                    #{data.displayIndex}
                  </span>
                  <span
                    className="font-medium text-gray-900 text-sm truncate flex-1 min-w-0"
                    title={data.fileName}
                  >
                    {data.fileName}
                  </span>
                </div>

                {/* 중간: 타입 정보 */}
                <div className="flex items-center gap-2 shrink-0">
                  {data.documentType && (
                    <span className="text-xs text-gray-600 whitespace-nowrap">
                      {data.documentType}
                    </span>
                  )}
                  {data.searchType && (
                    <span className="text-xs text-gray-500 whitespace-nowrap">
                      {data.searchType}
                    </span>
                  )}
                </div>

                {/* 오른쪽: 점수 배지 */}
                <div className="flex items-center gap-2 shrink-0">
                  {data.similarityScore !== undefined && data.similarityScore !== null && (
                    <span className="text-xs text-white px-2 py-1 rounded font-medium bg-blue-600 whitespace-nowrap">
                      {(data.similarityScore * 100).toFixed(1)}%
                    </span>
                  )}
                  {data.relevanceGrade && (
                    <span className="text-xs text-white px-2 py-1 rounded font-medium whitespace-nowrap" style={{
                      backgroundColor: data.relevanceGrade.includes('높음') ? '#dc2626' :
                        data.relevanceGrade.includes('보통') ? '#f59e0b' :
                          data.relevanceGrade.includes('낮음') ? '#10b981' : '#6b7280'
                    }}>
                      {data.relevanceGrade}
                    </span>
                  )}
                </div>
              </div>

              {/* AI 요약 (legacy만) */}
              {data.aiSummary && (
                <div className="mb-2 text-xs text-gray-700 bg-blue-50 px-2 py-1 rounded break-words">
                  {data.aiSummary}
                </div>
              )}

              {/* 섹션 제목 */}
              {data.sectionTitle && (
                <div
                  className="mb-2 text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded truncate"
                  title={data.sectionTitle}
                >
                  📖 {data.sectionTitle}
                </div>
              )}

              {/* 위치 정보 - Flex 레이아웃으로 변경하여 wrap 지원 */}
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2 w-full">
                {/* 왼쪽: 페이지와 청크 정보 */}
                <div className="flex items-center gap-2 shrink-0">
                  {data.pageNumber && (
                    <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded whitespace-nowrap">
                      p.{data.pageNumber}
                    </span>
                  )}
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded whitespace-nowrap">
                    청크 {data.chunkIndex + 1}
                  </span>
                </div>

                {/* 오른쪽: 상세보기 버튼 또는 외부 링크 */}
                {data.isInternetSearch && data.url ? (
                  <a
                    href={data.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-green-600 hover:text-green-800 bg-green-50 hover:bg-green-100 px-3 py-1 rounded border border-green-200 transition-colors shrink-0 whitespace-nowrap"
                    title="외부 링크로 이동"
                  >
                    🔗 원문 보기
                  </a>
                ) : (data.fileId !== undefined && data.fileId !== 0) && (
                  <button
                    onClick={() => handleViewChunk(ref)}
                    className="text-xs text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-1 rounded border border-blue-200 transition-colors shrink-0 whitespace-nowrap"
                    title="청크 내용 상세 보기"
                  >
                    📋 상세보기
                  </button>
                )}
              </div>

              {/* 발췌 내용 */}
              {data.excerpt && (
                <div
                  className="text-sm text-gray-700 leading-relaxed break-words"
                  style={{
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    wordBreak: 'break-word'
                  }}
                >
                  {data.excerpt}
                </div>
              )}

              {/* 키워드 (legacy만) */}
              {data.keywords && data.keywords.trim() && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {data.keywords.split(',').slice(0, 5).map((keyword: string, idx: number) => {
                    const trimmedKeyword = keyword.trim();
                    return trimmedKeyword ? (
                      <span key={idx} className="text-xs bg-gray-200 text-gray-700 px-2 py-1 rounded">
                        {trimmedKeyword}
                      </span>
                    ) : null;
                  })}
                </div>
              )}

              {/* URL - 인터넷 검색 결과용 (legacy 및 신규) */}
              {data.url && !data.isInternetSearch && (
                <div className="mt-2 flex items-center space-x-3 text-xs text-gray-500">
                  <a
                    href={data.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 underline"
                  >
                    원본 보기
                  </a>
                </div>
              )}

              {/* 인터넷 검색 출처 표시 */}
              {data.isInternetSearch && data.url && (
                <div className="mt-2 text-xs text-gray-500 truncate" title={data.url}>
                  🌐 {(() => {
                    try {
                      return new URL(data.url).hostname;
                    } catch {
                      return data.url;
                    }
                  })()}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* RAG 통계 정보 */}
      {contextInfo && (
        <div className="border-t border-gray-200 pt-3 mt-4">
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900 select-none">
              🔍 검색 세부 정보
              <span className="ml-2 transform transition-transform group-open:rotate-180 inline-block">
                ▼
              </span>
            </summary>
            <div className="mt-2 text-xs text-gray-600 space-y-1">
              {contextInfo.search_mode && (
                <div className="flex justify-between">
                  <span>검색 모드:</span>
                  <span>{contextInfo.search_mode}</span>
                </div>
              )}
              {contextInfo.chunks_count !== undefined && (
                <div className="flex justify-between">
                  <span>사용된 청크:</span>
                  <span>{contextInfo.chunks_count}개</span>
                </div>
              )}
              {contextInfo.documents_count !== undefined && (
                <div className="flex justify-between">
                  <span>참조 문서:</span>
                  <span>{contextInfo.documents_count}개</span>
                </div>
              )}
              {contextInfo.context_tokens !== undefined && (
                <div className="flex justify-between">
                  <span>컨텍스트 토큰:</span>
                  <span>{contextInfo.context_tokens}개</span>
                </div>
              )}
              {contextInfo.reranking_applied !== undefined && (
                <div className="flex justify-between">
                  <span>재랭킹 적용:</span>
                  <span>{contextInfo.reranking_applied ? '예' : '아니오'}</span>
                </div>
              )}
              {ragStats && (
                <>
                  {ragStats.search_time !== null && ragStats.search_time !== undefined && (
                    <div className="flex justify-between">
                      <span>검색 시간:</span>
                      <span>{ragStats.search_time.toFixed(2)}ms</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>한국어 키워드:</span>
                    <span>{ragStats.has_korean_keywords ? '포함' : '미포함'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>임베딩 차원:</span>
                    <span>{ragStats.embedding_dimension}차원</span>
                  </div>
                </>
              )}
            </div>
          </details>
        </div>
      )}

      {/* ChunkViewer 모달 */}
      {selectedReference && (
        <>
          {/* Agent 참고자료는 full_content 직접 표시 */}
          {isDetailedChunk(selectedReference) && selectedReference.file_id === 0 && (selectedReference as any).full_content ? (
            <div
              className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
              onClick={() => {
                setChunkViewerOpen(false);
                setSelectedReference(null);
              }}
            >
              <div
                className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                {/* 헤더 */}
                <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold">{selectedReference.file_name}</h3>
                      <div className="flex items-center gap-3 mt-1 text-sm text-blue-100">
                        <span>청크 {selectedReference.chunk_index}</span>
                        {selectedReference.page_number && <span>페이지 {selectedReference.page_number}</span>}
                        <span className="bg-white/20 px-2 py-0.5 rounded">
                          {(selectedReference.similarity_score * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setChunkViewerOpen(false);
                        setSelectedReference(null);
                      }}
                      className="text-white hover:text-gray-200 text-2xl font-light"
                    >
                      ×
                    </button>
                  </div>
                </div>

                {/* 내용 - 흰색 배경으로 변경 */}
                <div className="p-6 bg-white overflow-y-auto max-h-[calc(80vh-120px)]">
                  <div className="prose prose-sm max-w-none">
                    <div className="whitespace-pre-wrap text-sm text-gray-800 leading-relaxed font-sans bg-white p-4 rounded border border-gray-200">
                      {(selectedReference as any).full_content}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <ChunkViewer
              fileBssInfoSno={
                isDetailedChunk(selectedReference)
                  ? selectedReference.file_id
                  : (selectedReference.file_bss_info_sno || 0)
              }
              fileName={isDetailedChunk(selectedReference) ? selectedReference.file_name : (selectedReference.file_name || selectedReference.title || 'Unknown')}
              chunkIndex={isDetailedChunk(selectedReference) ? selectedReference.chunk_index : (selectedReference.chunk_index || 0)}
              isOpen={chunkViewerOpen}
              onClose={() => {
                setChunkViewerOpen(false);
                setSelectedReference(null);
              }}
            />
          )}
        </>
      )}
    </div>
  );
};

export default ReferencePanel;

import React, { useCallback, useEffect, useState } from 'react';
import { getDocumentChunks } from '../../../../services/userService';

interface ChunkViewerProps {
    fileBssInfoSno: number;
    fileName: string;
    chunkIndex?: number;
    isOpen: boolean;
    onClose: () => void;
    // 참고자료 선택 정보 추가
    similarityScore?: number;
    relevanceGrade?: string;
    searchKeywords?: string[];
    excerpt?: string;
}

interface ChunkData {
    chunk_sno: number;
    chunk_index: number;
    chunk_text: string;
    chunk_size: number;
    page_number?: number;
    section_title?: string;
    keywords: string[];
    named_entities: string[];
    created_date?: string;
    last_modified_date?: string;
}

const ChunkViewer: React.FC<ChunkViewerProps> = ({
    fileBssInfoSno,
    fileName,
    chunkIndex,
    isOpen,
    onClose,
    similarityScore,
    relevanceGrade,
    searchKeywords = [],
    excerpt
}) => {
    const [chunks, setChunks] = useState<ChunkData[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedChunkIndex, setSelectedChunkIndex] = useState(chunkIndex || 0);
    const [documentInfo, setDocumentInfo] = useState<any>(null);

    const fetchChunks = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await getDocumentChunks(fileBssInfoSno);
            setChunks(response.chunks);
            setDocumentInfo(response.document_info);

            if (chunkIndex !== undefined && response.chunks.length > chunkIndex) {
                setSelectedChunkIndex(chunkIndex);
            }
        } catch (err) {
            console.error('청크 조회 실패:', err);
            setError('청크 데이터를 불러오는데 실패했습니다.');
        } finally {
            setLoading(false);
        }
    }, [fileBssInfoSno, chunkIndex]);

    useEffect(() => {
        if (isOpen) {
            fetchChunks();
        }
    }, [isOpen, fetchChunks]);

    // 키워드 하이라이팅 함수
    const highlightKeywords = (text: string, keywords: string[]) => {
        if (!keywords.length) return text;

        let highlightedText = text;
        keywords.forEach(keyword => {
            const regex = new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
            highlightedText = highlightedText.replace(regex, '<mark style="background-color: #fef08a; padding: 1px 2px; border-radius: 2px; font-weight: 500;">$1</mark>');
        });
        return highlightedText;
    };

    const currentChunk = chunks[selectedChunkIndex];

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-5xl max-h-[90vh] w-full flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
                    <div className="flex-1">
                        <h2 className="text-lg font-semibold text-gray-900 mb-1">
                            📋 문서 청크 조회
                        </h2>
                        <p className="text-sm text-gray-600">
                            {documentInfo?.file_name || fileName} {chunks.length > 0 && `(총 ${chunks.length}개 청크)`}
                        </p>
                        {documentInfo?.container_id && (
                            <p className="text-xs text-gray-500">
                                컨테이너: {documentInfo.container_id}
                            </p>
                        )}

                        {/* 참고자료 선택 이유 표시 */}
                        {(similarityScore !== undefined || relevanceGrade) && (
                            <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
                                <div className="text-xs font-medium text-blue-800 mb-1">🎯 참고자료 선택 이유</div>
                                <div className="flex flex-wrap gap-2 text-xs">
                                    {similarityScore !== undefined && (
                                        <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">
                                            유사도: {(similarityScore * 100).toFixed(1)}%
                                        </span>
                                    )}
                                    {relevanceGrade && (
                                        <span className="bg-green-100 text-green-800 px-2 py-1 rounded">
                                            관련도: {relevanceGrade}
                                        </span>
                                    )}
                                    {searchKeywords.length > 0 && (
                                        <span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                                            키워드 매칭: {searchKeywords.length}개
                                        </span>
                                    )}
                                </div>
                                {searchKeywords.length > 0 && (
                                    <div className="mt-1 flex flex-wrap gap-1">
                                        {searchKeywords.map((keyword, idx) => (
                                            <span
                                                key={idx}
                                                className="text-xs bg-yellow-200 text-yellow-900 px-1 py-0.5 rounded"
                                            >
                                                {keyword}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 text-xl font-bold ml-4 p-1 hover:bg-gray-100 rounded"
                    >
                        ×
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Chunk List */}
                    {chunks.length > 1 && (
                        <div className="w-1/3 border-r border-gray-200 overflow-y-auto bg-gray-50">
                            <div className="p-3 bg-gray-100 border-b border-gray-200">
                                <h3 className="text-sm font-medium text-gray-800">📋 청크 목록</h3>
                                <p className="text-xs text-gray-600 mt-1">총 {chunks.length}개 청크</p>
                            </div>
                            <div className="p-2">
                                {chunks.map((chunk, index) => (
                                    <button
                                        key={chunk.chunk_sno}
                                        onClick={() => setSelectedChunkIndex(index)}
                                        className={`w-full text-left p-3 rounded mb-2 text-sm transition-all duration-200 border ${selectedChunkIndex === index
                                            ? 'bg-blue-100 border-blue-300 shadow-sm'
                                            : 'bg-white border-gray-200 hover:bg-gray-50 hover:border-gray-300'
                                            }`}
                                    >
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="font-medium text-gray-900">청크 {chunk.chunk_index + 1}</span>
                                            <span className="text-xs text-gray-500">{chunk.chunk_size.toLocaleString()}자</span>
                                        </div>
                                        {chunk.page_number && (
                                            <div className="text-xs text-gray-600 mb-1">📄 페이지 {chunk.page_number}</div>
                                        )}
                                        {chunk.section_title && (
                                            <div className="text-xs text-gray-700 truncate mb-1 font-medium">
                                                📑 {chunk.section_title}
                                            </div>
                                        )}
                                        {chunk.keywords.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-1">
                                                {chunk.keywords.slice(0, 3).map((keyword, idx) => (
                                                    <span
                                                        key={idx}
                                                        className="text-xs bg-blue-50 text-blue-700 px-1 py-0.5 rounded border border-blue-200"
                                                    >
                                                        {keyword}
                                                    </span>
                                                ))}
                                                {chunk.keywords.length > 3 && (
                                                    <span className="text-xs text-gray-500">+{chunk.keywords.length - 3}</span>
                                                )}
                                            </div>
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Chunk Content */}
                    <div className={`${chunks.length > 1 ? 'flex-1' : 'w-full'} overflow-y-auto`}>
                        {loading ? (
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                                    <p className="text-gray-600">청크 데이터를 불러오는 중...</p>
                                </div>
                            </div>
                        ) : error ? (
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center text-red-600">
                                    <p className="mb-2">⚠️ 오류 발생</p>
                                    <p className="text-sm">{error}</p>
                                    <button
                                        onClick={fetchChunks}
                                        className="mt-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                                    >
                                        다시 시도
                                    </button>
                                </div>
                            </div>
                        ) : currentChunk ? (
                            <div className="p-4 bg-white">
                                {/* Chunk Metadata */}
                                <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                    <div className="grid grid-cols-2 gap-3 text-sm">
                                        <div className="flex items-center">
                                            <span className="font-medium text-gray-700 w-20">청크 번호:</span>
                                            <span className="text-gray-900">{currentChunk.chunk_index + 1}</span>
                                        </div>
                                        <div className="flex items-center">
                                            <span className="font-medium text-gray-700 w-16">크기:</span>
                                            <span className="text-gray-900">{currentChunk.chunk_size.toLocaleString()}자</span>
                                        </div>
                                        {currentChunk.page_number && (
                                            <div className="flex items-center">
                                                <span className="font-medium text-gray-700 w-20">페이지:</span>
                                                <span className="text-gray-900">{currentChunk.page_number}</span>
                                            </div>
                                        )}
                                        {currentChunk.section_title && (
                                            <div className="col-span-2 flex items-center">
                                                <span className="font-medium text-gray-700 w-20">섹션:</span>
                                                <span className="text-gray-900">{currentChunk.section_title}</span>
                                            </div>
                                        )}
                                    </div>

                                    {/* Keywords */}
                                    {currentChunk.keywords.length > 0 && (
                                        <div className="mt-3 pt-3 border-t border-gray-200">
                                            <span className="font-medium text-gray-700 block mb-2">🏷️ 키워드:</span>
                                            <div className="flex flex-wrap gap-1">
                                                {currentChunk.keywords.map((keyword, idx) => (
                                                    <span
                                                        key={idx}
                                                        className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded border border-blue-200"
                                                    >
                                                        {keyword}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Named Entities */}
                                    {currentChunk.named_entities.length > 0 && (
                                        <div className="mt-3 pt-3 border-t border-gray-200">
                                            <span className="font-medium text-gray-700 block mb-2">🏢 개체명:</span>
                                            <div className="flex flex-wrap gap-1">
                                                {currentChunk.named_entities.map((entity, idx) => (
                                                    <span
                                                        key={idx}
                                                        className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded border border-green-200"
                                                    >
                                                        {entity}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Chunk Text */}
                                <div className="space-y-3">
                                    <h4 className="text-sm font-medium text-gray-700 flex items-center">
                                        📄 청크 내용
                                        {searchKeywords.length > 0 && (
                                            <span className="ml-2 text-xs text-yellow-600 bg-yellow-100 px-2 py-1 rounded">
                                                검색 키워드 하이라이트됨
                                            </span>
                                        )}
                                    </h4>
                                    <div className="border border-gray-300 rounded-lg overflow-hidden">
                                        <div className="p-4 bg-white max-h-96 overflow-y-auto">
                                            <div
                                                className="text-sm text-gray-900 font-sans leading-relaxed whitespace-pre-wrap"
                                                dangerouslySetInnerHTML={{
                                                    __html: searchKeywords.length > 0
                                                        ? highlightKeywords(currentChunk.chunk_text, searchKeywords)
                                                        : currentChunk.chunk_text.replace(/\n/g, '<br>')
                                                }}
                                            />
                                        </div>
                                    </div>
                                </div>

                                {/* 참고자료에서 발췌된 부분 표시 */}
                                {excerpt && excerpt !== currentChunk.chunk_text && (
                                    <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                                        <h5 className="text-xs font-medium text-yellow-800 mb-2">💡 참고자료 발췌 부분</h5>
                                        <div
                                            className="text-sm text-yellow-900 leading-relaxed"
                                            dangerouslySetInnerHTML={{
                                                __html: searchKeywords.length > 0
                                                    ? highlightKeywords(excerpt, searchKeywords)
                                                    : excerpt.replace(/\n/g, '<br>')
                                            }}
                                        />
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-full">
                                <p className="text-gray-500">청크 데이터가 없습니다.</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-2 p-4 border-t border-gray-200">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
                    >
                        닫기
                    </button>
                </div>
            </div>
        </div>
    );
};

export { ChunkViewer };

/**
 * 선택된 문서 표시 및 관리 컴포넌트
 */
import {
    Calendar,
    ChevronDown,
    ChevronUp,
    Download,
    Eye,
    FileText,
    FolderOpen,
    Search,
    X
} from 'lucide-react';
import React, { useState } from 'react';
import { useSelectedDocuments, useWorkContext } from '../../contexts/GlobalAppContext';

interface SelectedDocumentsDisplayProps {
    maxDisplay?: number;
    showActions?: boolean;
    compact?: boolean;
    className?: string;
    // 선택 제어 콜백(선택 사항): SearchPage에서 전달 시 체크박스까지 동기화됨
    onClearAll?: () => void;
    onRemove?: (fileId: string) => void;
    onViewDocument?: (doc: any) => void; // 문서 뷰어 콜백 추가
}

export const SelectedDocumentsDisplay: React.FC<SelectedDocumentsDisplayProps> = ({
    maxDisplay = 5,
    showActions = true,
    compact = false,
    className = '',
    onClearAll,
    onRemove,
    onViewDocument
}) => {
    const { selectedDocuments, removeSelectedDocument, clearSelectedDocuments } = useSelectedDocuments();
    const { workContext } = useWorkContext();
    const [showAll, setShowAll] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    // 검색 필터링
    const filteredDocuments = selectedDocuments.filter((doc: any) =>
        doc.fileName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.containerName?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const displayedDocuments = showAll
        ? filteredDocuments
        : filteredDocuments.slice(0, maxDisplay);

    const hasMore = filteredDocuments.length > maxDisplay;

    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    };

    const getFileTypeColor = (fileType: string) => {
        const colors: Record<string, string> = {
            'pdf': 'bg-red-100 text-red-800',
            'doc': 'bg-blue-100 text-blue-800',
            'docx': 'bg-blue-100 text-blue-800',
            'ppt': 'bg-orange-100 text-orange-800',
            'pptx': 'bg-orange-100 text-orange-800',
            'xls': 'bg-green-100 text-green-800',
            'xlsx': 'bg-green-100 text-green-800',
            'txt': 'bg-gray-100 text-gray-800',
            'md': 'bg-purple-100 text-purple-800',
            'default': 'bg-gray-100 text-gray-800'
        };
        return colors[fileType.toLowerCase()] || colors.default;
    };

    if (selectedDocuments.length === 0) {
        return (
            <div className={`bg-gray-50 border border-gray-200 rounded-lg p-6 text-center ${className}`}>
                <FileText className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <h3 className="text-sm font-medium text-gray-900 mb-1">선택된 문서가 없습니다</h3>
                <p className="text-xs text-gray-600">
                    {workContext.sourcePageType ? (
                        <>
                            <span className="font-medium">{workContext.sourcePageType}</span>에서 문서를 선택하거나
                        </>
                    ) : (
                        '내 지식 또는 통합검색에서 문서를 선택하거나'
                    )}
                    <br />직접 업로드하여 AI 채팅을 시작하세요.
                </p>
            </div>
        );
    }

    return (
        <div className={`bg-white border border-gray-200 rounded-lg ${className}`}>
            {/* 헤더 */}
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                        <FolderOpen className="w-4 h-4 text-gray-600" />
                        <h3 className="text-sm font-medium text-gray-900">
                            선택된 문서 ({selectedDocuments.length})
                        </h3>
                        {workContext.sourcePageType && (
                            <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                                from {workContext.sourcePageType}
                            </span>
                        )}
                    </div>

                    {showActions && selectedDocuments.length > 0 && (
                        <button
                            type="button"
                            onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                console.log('🗑️ 전체 삭제 버튼 클릭됨');
                                if (onClearAll) onClearAll();
                                else clearSelectedDocuments();
                            }}
                            className="text-xs text-red-600 hover:text-red-800 font-medium transition-colors"
                        >
                            전체 삭제
                        </button>
                    )}
                </div>

                {/* 검색 (문서가 많을 때만) */}
                {selectedDocuments.length > 3 && (
                    <div className="mt-2 relative">
                        <Search className="w-4 h-4 absolute left-2 top-2 text-gray-400" />
                        <input
                            type="text"
                            placeholder="문서 제목 또는 컨테이너명으로 검색..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-8 pr-3 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>
                )}
            </div>

            {/* 문서 목록 */}
            <div className="max-h-64 overflow-y-auto">
                <div className="divide-y divide-gray-100">
                    {displayedDocuments.map((doc: any) => (
                        <div key={`${doc.fileId}-${workContext.sourcePageType}`} className="p-3 hover:bg-gray-50">
                            {compact ? (
                                /* 간단한 표시 */
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center space-x-2 min-w-0 flex-1 text-left">
                                        <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
                                        <span className="text-sm text-gray-900 truncate text-left">{doc.fileName}</span>
                                        <span className={`px-1.5 py-0.5 text-xs rounded ${getFileTypeColor(doc.fileType)}`}>
                                            {doc.fileType.toUpperCase()}
                                        </span>
                                    </div>
                                    {showActions && (
                                        <div className="flex items-center space-x-1">
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    if (onViewDocument) onViewDocument(doc);
                                                }}
                                                className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                                                title="문서 보기"
                                            >
                                                <Eye className="w-3 h-3" />
                                            </button>
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    console.log('❌ 개별 삭제 버튼 클릭됨 (카드형), fileId:', doc.fileId);
                                                    if (onRemove) onRemove(doc.fileId);
                                                    else removeSelectedDocument(doc.fileId);
                                                }}
                                                className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                                                title="선택 해제"
                                            >
                                                <X className="w-3 h-3" />
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                /* 상세 표시 */
                                <div className="space-y-2">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-start space-x-3 min-w-0 flex-1 text-left">
                                            <FileText className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
                                            <div className="min-w-0 flex-1">
                                                <h4 className="text-sm font-medium text-gray-900 text-left line-clamp-2">
                                                    {doc.fileName}
                                                </h4>
                                            </div>
                                        </div>

                                        {showActions && (
                                            <div className="flex items-center space-x-1 flex-shrink-0">
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        e.stopPropagation();
                                                        if (onViewDocument) onViewDocument(doc);
                                                    }}
                                                    className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                                                    title="문서 보기"
                                                >
                                                    <Eye className="w-4 h-4" />
                                                </button>
                                                <button
                                                    type="button"
                                                    className="p-1 text-gray-400 hover:text-green-600 transition-colors"
                                                    title="다운로드"
                                                >
                                                    <Download className="w-4 h-4" />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        e.stopPropagation();
                                                        console.log('❌ 개별 삭제 버튼 클릭됨 (리스트형), fileId:', doc.fileId);
                                                        if (onRemove) onRemove(doc.fileId);
                                                        else removeSelectedDocument(doc.fileId);
                                                    }}
                                                    className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                                                    title="선택 해제"
                                                >
                                                    <X className="w-4 h-4" />
                                                </button>
                                            </div>
                                        )}
                                    </div>

                                    {/* 메타데이터 */}
                                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                                        <span className={`px-1.5 py-0.5 rounded ${getFileTypeColor(doc.fileType)}`}>
                                            {doc.fileType.toUpperCase()}
                                        </span>
                                        {doc.fileSize && (
                                            <span className="flex items-center">
                                                📊 {formatFileSize(doc.fileSize)}
                                            </span>
                                        )}
                                        {doc.uploadDate && (
                                            <span className="flex items-center">
                                                <Calendar className="w-3 h-3 mr-1" />
                                                {formatDate(doc.uploadDate)}
                                            </span>
                                        )}
                                    </div>

                                    {/* 요약 또는 설명 */}
                                    {doc.summary && (
                                        <p className="text-xs text-gray-600 line-clamp-2 bg-gray-50 p-2 rounded">
                                            {doc.summary}
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* 더보기/접기 버튼 */}
            {hasMore && (
                <div className="px-4 py-2 border-t border-gray-200 bg-gray-50">
                    <button
                        onClick={() => setShowAll(!showAll)}
                        className="w-full flex items-center justify-center space-x-1 text-xs text-gray-600 hover:text-gray-800 transition-colors"
                    >
                        <span>
                            {showAll ? '접기' : `${filteredDocuments.length - maxDisplay}개 더보기`}
                        </span>
                        {showAll ? (
                            <ChevronUp className="w-3 h-3" />
                        ) : (
                            <ChevronDown className="w-3 h-3" />
                        )}
                    </button>
                </div>
            )}

            {/* 검색 결과가 없을 때 */}
            {searchQuery && filteredDocuments.length === 0 && (
                <div className="p-4 text-center">
                    <p className="text-sm text-gray-500">검색 결과가 없습니다.</p>
                </div>
            )}
        </div>
    );
};

export default SelectedDocumentsDisplay;

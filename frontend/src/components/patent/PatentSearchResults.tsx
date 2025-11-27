/**
 * PatentSearchResults - 특허 검색 결과 카드 컴포넌트
 * 검색된 특허 목록을 카드 형태로 표시
 */
import {
    Building2,
    Calendar,
    ExternalLink,
    FileText,
    Globe,
    Tag,
    User,
} from 'lucide-react';
import React from 'react';

export interface PatentResult {
    id: string;
    title: string;
    abstract?: string;
    applicationNumber?: string;
    publicationNumber?: string;
    filingDate?: string;
    publicationDate?: string;
    applicant?: string;
    inventor?: string;
    assignee?: string;
    classification?: string[];
    status?: string;
    country?: string;
    url?: string;
    source?: 'kipris' | 'google_patents' | 'unknown';
    relevanceScore?: number;
}

interface PatentSearchResultsProps {
    results: PatentResult[];
    title?: string;
    showAbstract?: boolean;
    onPatentClick?: (patent: PatentResult) => void;
    maxResults?: number;
}

const PatentSearchResults: React.FC<PatentSearchResultsProps> = ({
    results,
    title = '검색 결과',
    showAbstract = true,
    onPatentClick,
    maxResults,
}) => {
    const displayResults = maxResults ? results.slice(0, maxResults) : results;

    const getSourceBadge = (source?: string) => {
        switch (source) {
            case 'kipris':
                return (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        KIPRIS
                    </span>
                );
            case 'google_patents':
                return (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                        Google Patents
                    </span>
                );
            default:
                return null;
        }
    };

    const getStatusBadge = (status?: string) => {
        if (!status) return null;

        const statusColors: Record<string, string> = {
            '등록': 'bg-green-100 text-green-800',
            'granted': 'bg-green-100 text-green-800',
            '출원': 'bg-blue-100 text-blue-800',
            'pending': 'bg-blue-100 text-blue-800',
            '공개': 'bg-yellow-100 text-yellow-800',
            'published': 'bg-yellow-100 text-yellow-800',
            '거절': 'bg-red-100 text-red-800',
            'rejected': 'bg-red-100 text-red-800',
        };

        const colorClass = statusColors[status.toLowerCase()] || 'bg-gray-100 text-gray-800';

        return (
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
                {status}
            </span>
        );
    };

    if (!results.length) {
        return (
            <div className="text-center py-8 text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>검색 결과가 없습니다</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {title && (
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
                    <span className="text-sm text-gray-500">
                        총 {results.length}건
                    </span>
                </div>
            )}

            <div className="space-y-3">
                {displayResults.map((patent, index) => (
                    <div
                        key={patent.id || index}
                        className={`
              bg-white border border-gray-200 rounded-lg p-4 
              hover:border-teal-300 hover:shadow-md transition-all
              ${onPatentClick ? 'cursor-pointer' : ''}
            `}
                        onClick={() => onPatentClick?.(patent)}
                    >
                        {/* 헤더 */}
                        <div className="flex items-start justify-between gap-3 mb-2">
                            <h4 className="text-base font-medium text-gray-900 flex-1 line-clamp-2">
                                {patent.title}
                            </h4>
                            <div className="flex items-center gap-2 flex-shrink-0">
                                {getSourceBadge(patent.source)}
                                {getStatusBadge(patent.status)}
                            </div>
                        </div>

                        {/* 메타 정보 */}
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600 mb-2">
                            {patent.applicationNumber && (
                                <span className="flex items-center gap-1">
                                    <FileText className="w-3.5 h-3.5" />
                                    {patent.applicationNumber}
                                </span>
                            )}
                            {patent.filingDate && (
                                <span className="flex items-center gap-1">
                                    <Calendar className="w-3.5 h-3.5" />
                                    {patent.filingDate}
                                </span>
                            )}
                            {patent.country && (
                                <span className="flex items-center gap-1">
                                    <Globe className="w-3.5 h-3.5" />
                                    {patent.country}
                                </span>
                            )}
                        </div>

                        {/* 출원인/발명자 */}
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600 mb-2">
                            {(patent.applicant || patent.assignee) && (
                                <span className="flex items-center gap-1">
                                    <Building2 className="w-3.5 h-3.5" />
                                    {patent.applicant || patent.assignee}
                                </span>
                            )}
                            {patent.inventor && (
                                <span className="flex items-center gap-1">
                                    <User className="w-3.5 h-3.5" />
                                    {patent.inventor}
                                </span>
                            )}
                        </div>

                        {/* 분류 */}
                        {patent.classification && patent.classification.length > 0 && (
                            <div className="flex items-center gap-1 flex-wrap mb-2">
                                <Tag className="w-3.5 h-3.5 text-gray-400" />
                                {patent.classification.slice(0, 3).map((cls, i) => (
                                    <span
                                        key={i}
                                        className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
                                    >
                                        {cls}
                                    </span>
                                ))}
                                {patent.classification.length > 3 && (
                                    <span className="text-xs text-gray-500">
                                        +{patent.classification.length - 3}
                                    </span>
                                )}
                            </div>
                        )}

                        {/* 초록 */}
                        {showAbstract && patent.abstract && (
                            <p className="text-sm text-gray-600 line-clamp-2 mt-2">
                                {patent.abstract}
                            </p>
                        )}

                        {/* 외부 링크 */}
                        {patent.url && (
                            <a
                                href={patent.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-sm text-teal-600 hover:text-teal-700 mt-2"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <ExternalLink className="w-3.5 h-3.5" />
                                상세 보기
                            </a>
                        )}
                    </div>
                ))}
            </div>

            {maxResults && results.length > maxResults && (
                <p className="text-sm text-center text-gray-500">
                    {results.length - maxResults}건 더 있음
                </p>
            )}
        </div>
    );
};

export default PatentSearchResults;

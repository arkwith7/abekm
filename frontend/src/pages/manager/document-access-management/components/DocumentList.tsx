import {
    Download,
    Edit3,
    Eye,
    FileText,
    Filter,
    Globe,
    Lock,
    Search,
    Shield,
    Users
} from 'lucide-react';
import React, { useState } from 'react';
import type { AccessibleDocument, AccessLevel, DocumentAccessFilter } from '../../../../types/manager.types';

interface DocumentListProps {
    documents: AccessibleDocument[];
    onDocumentSelect?: (document: AccessibleDocument) => void;
    onFilterChange?: (filter: DocumentAccessFilter) => void;
    onRefresh?: () => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
    documents,
    onDocumentSelect,
    onFilterChange,
    onRefresh
}) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [accessLevelFilter, setAccessLevelFilter] = useState<AccessLevel | ''>('');
    const [showFilters, setShowFilters] = useState(false);

    // 필터 적용
    const filteredDocuments = documents.filter(doc => {
        const matchesSearch = !searchQuery ||
            doc.file_lgc_nm.toLowerCase().includes(searchQuery.toLowerCase()) ||
            doc.file_psl_nm.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesAccessLevel = !accessLevelFilter || doc.access_level === accessLevelFilter;

        return matchesSearch && matchesAccessLevel;
    });

    // 접근 레벨 뱃지
    const getAccessLevelBadge = (level: AccessLevel) => {
        switch (level) {
            case 'public':
                return (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <Globe className="w-3 h-3 mr-1" />
                        공개
                    </span>
                );
            case 'restricted':
                return (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                        <Users className="w-3 h-3 mr-1" />
                        제한
                    </span>
                );
            case 'private':
                return (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        <Lock className="w-3 h-3 mr-1" />
                        비공개
                    </span>
                );
        }
    };

    // 권한 레벨 아이콘
    const getPermissionIcon = (permission: 'view' | 'download' | 'edit') => {
        switch (permission) {
            case 'view':
                return <Eye className="w-4 h-4 text-gray-500" />;
            case 'download':
                return <Download className="w-4 h-4 text-blue-500" />;
            case 'edit':
                return <Edit3 className="w-4 h-4 text-purple-500" />;
        }
    };

    // 파일 확장자 색상
    const getFileExtColor = (ext: string) => {
        const extLower = ext.toLowerCase();
        if (['pdf'].includes(extLower)) return 'text-red-600';
        if (['doc', 'docx'].includes(extLower)) return 'text-blue-600';
        if (['xls', 'xlsx'].includes(extLower)) return 'text-green-600';
        if (['ppt', 'pptx'].includes(extLower)) return 'text-orange-600';
        return 'text-gray-600';
    };

    const handleFilterApply = () => {
        if (onFilterChange) {
            onFilterChange({
                access_level: accessLevelFilter || undefined,
                search_query: searchQuery || undefined
            });
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            {/* 헤더 */}
            <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-gray-900">문서 목록</h3>
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                        <Filter className="w-4 h-4 mr-2" />
                        필터
                    </button>
                </div>

                {/* 검색 바 */}
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="문서 검색..."
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>

                {/* 필터 패널 */}
                {showFilters && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-md">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    접근 레벨
                                </label>
                                <select
                                    value={accessLevelFilter}
                                    onChange={(e) => setAccessLevelFilter(e.target.value as AccessLevel | '')}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="">전체</option>
                                    <option value="public">공개</option>
                                    <option value="restricted">제한</option>
                                    <option value="private">비공개</option>
                                </select>
                            </div>
                        </div>
                        <div className="mt-4 flex justify-end">
                            <button
                                onClick={handleFilterApply}
                                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                            >
                                필터 적용
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* 문서 목록 */}
            <div className="overflow-x-auto">
                {filteredDocuments.length === 0 ? (
                    <div className="text-center py-12">
                        <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                        <p className="text-gray-500">문서가 없습니다.</p>
                    </div>
                ) : (
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    문서명
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    확장자
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    접근 레벨
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    권한
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    상속
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    생성일
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    작업
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {filteredDocuments.map((doc) => (
                                <tr
                                    key={doc.file_bss_info_sno}
                                    className="hover:bg-gray-50 cursor-pointer"
                                    onClick={() => onDocumentSelect && onDocumentSelect(doc)}
                                >
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center">
                                            <FileText className="w-5 h-5 text-gray-400 mr-3" />
                                            <div>
                                                <div className="text-sm font-medium text-gray-900">
                                                    {doc.file_lgc_nm}
                                                </div>
                                                <div className="text-xs text-gray-500">
                                                    {doc.file_psl_nm}
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className={`text-sm font-medium ${getFileExtColor(doc.file_extsn)}`}>
                                            .{doc.file_extsn}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        {getAccessLevelBadge(doc.access_level)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center">
                                            {getPermissionIcon(doc.permission_level)}
                                            <span className="ml-2 text-sm text-gray-700 capitalize">
                                                {doc.permission_level}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        {doc.is_inherited === 'Y' ? (
                                            <span className="text-xs text-gray-500">컨테이너 상속</span>
                                        ) : (
                                            <span className="text-xs text-blue-600">수동 설정</span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {new Date(doc.created_date).toLocaleDateString('ko-KR')}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onDocumentSelect && onDocumentSelect(doc);
                                            }}
                                            className="text-blue-600 hover:text-blue-800 font-medium"
                                        >
                                            <Shield className="w-4 h-4 inline mr-1" />
                                            권한 설정
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* 푸터 - 결과 요약 */}
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
                <p className="text-sm text-gray-600">
                    총 {filteredDocuments.length}개 문서
                    {searchQuery && ` (검색: "${searchQuery}")`}
                    {accessLevelFilter && ` (필터: ${accessLevelFilter})`}
                </p>
            </div>
        </div>
    );
};

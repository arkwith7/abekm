import { FileText, RefreshCw } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import {
    getAccessibleDocuments,
    getAccessLevelStats
} from '../../../services/managerService';
import type {
    AccessibleDocument,
    AccessLevelStats,
    DocumentAccessFilter
} from '../../../types/manager.types';
import { AccessControlModal, AccessStats, DocumentList } from './components';

const DocumentAccessManagement: React.FC = () => {
    const [documents, setDocuments] = useState<AccessibleDocument[]>([]);
    const [stats, setStats] = useState<AccessLevelStats>({
        public_count: 0,
        restricted_count: 0,
        private_count: 0,
        total_count: 0
    });
    const [isLoading, setIsLoading] = useState(false);
    const [selectedDocument, setSelectedDocument] = useState<AccessibleDocument | null>(null);
    const [showModal, setShowModal] = useState(false);
    const [filter, setFilter] = useState<DocumentAccessFilter>({});

    // 데이터 로드
    const loadData = useCallback(async () => {
        try {
            setIsLoading(true);

            // 문서 목록 조회
            const docsData = await getAccessibleDocuments(filter);
            setDocuments(docsData);

            // 통계 조회
            const statsData = await getAccessLevelStats(filter.container_id);
            setStats(statsData);

        } catch (error) {
            console.error('Failed to load document access data:', error);
        } finally {
            setIsLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // 문서 선택 핸들러
    const handleDocumentSelect = (document: AccessibleDocument) => {
        setSelectedDocument(document);
        setShowModal(true);
    };

    // 모달 닫기
    const handleCloseModal = () => {
        setShowModal(false);
        setSelectedDocument(null);
    };

    // 모달 성공 핸들러
    const handleModalSuccess = () => {
        loadData(); // 데이터 새로고침
    };

    // 필터 변경 핸들러
    const handleFilterChange = (newFilter: DocumentAccessFilter) => {
        setFilter(prev => ({ ...prev, ...newFilter }));
    };

    return (
        <div className="min-h-screen bg-gray-50 py-4 px-4 sm:px-6 lg:px-8">
            <div className="max-w-7xl mx-auto">
                {/* 헤더 */}
                <div className="mb-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 flex items-center">
                                <FileText className="w-8 h-8 mr-3 text-blue-600" />
                                문서 접근 관리
                            </h1>
                            <p className="mt-2 text-sm text-gray-600">
                                문서별 접근 권한을 설정하고 관리합니다.
                            </p>
                        </div>
                        <button
                            onClick={loadData}
                            disabled={isLoading}
                            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                        >
                            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                            새로고침
                        </button>
                    </div>
                </div>

                {/* 통계 및 문서 목록 */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* 통계 (왼쪽 사이드바) */}
                    <div className="lg:col-span-1">
                        <AccessStats stats={stats} />

                        {/* 안내 메시지 */}
                        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <h4 className="text-sm font-medium text-blue-900 mb-2">
                                접근 레벨 안내
                            </h4>
                            <ul className="text-sm text-blue-800 space-y-1">
                                <li>• <strong>공개:</strong> 모든 사용자가 접근 가능</li>
                                <li>• <strong>제한:</strong> 특정 사용자/부서만 접근</li>
                                <li>• <strong>비공개:</strong> 관리자만 접근 가능</li>
                            </ul>
                        </div>

                        {/* 권한 레벨 안내 */}
                        <div className="mt-4 bg-purple-50 border border-purple-200 rounded-lg p-4">
                            <h4 className="text-sm font-medium text-purple-900 mb-2">
                                권한 레벨 안내
                            </h4>
                            <ul className="text-sm text-purple-800 space-y-1">
                                <li>• <strong>View:</strong> 조회만 가능</li>
                                <li>• <strong>Download:</strong> 조회 + 다운로드</li>
                                <li>• <strong>Edit:</strong> 조회 + 다운로드 + 편집</li>
                            </ul>
                        </div>
                    </div>

                    {/* 문서 목록 (메인 영역) */}
                    <div className="lg:col-span-2">
                        <DocumentList
                            documents={documents}
                            onDocumentSelect={handleDocumentSelect}
                            onFilterChange={handleFilterChange}
                            onRefresh={loadData}
                        />
                    </div>
                </div>

                {/* 접근 제어 모달 */}
                {selectedDocument && (
                    <AccessControlModal
                        document={selectedDocument}
                        isOpen={showModal}
                        onClose={handleCloseModal}
                        onSuccess={handleModalSuccess}
                    />
                )}
            </div>
        </div>
    );
};

export default DocumentAccessManagement;

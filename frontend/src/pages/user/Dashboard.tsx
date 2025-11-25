import { Clock, FileText, Folder, Image, MessageSquare, Search, TrendingUp, Upload, X } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSelectedDocuments, useWorkContext } from '../../contexts/GlobalAppContext';
import { useSidebar } from '../../contexts/SidebarContext';
import { useAuth } from '../../hooks/useAuth';
import {
    getContainerSummary,
    getDashboardSummary,
    getRecentActivities,
    getRecentChatSessions,
    getRecentDocuments
} from '../../services/dashboardService';
import type {
    ChatHistory,
    ContainerSummary,
    DashboardSummary,
    RecentActivity,
    RecentDocument
} from '../../types/dashboard.types';

export const UserDashboard: React.FC = () => {
    const { user } = useAuth();
    const { hasSelectedDocuments, selectedCount, clearSelectedDocuments } = useSelectedDocuments();
    const {
        navigateWithContext,
        userActivity,
        incrementActivityCount
    } = useWorkContext();
    const { isOpen: isSidebarOpen } = useSidebar();

    // 검색 상태 관리
    const [searchQuery, setSearchQuery] = useState('');
    const [contentOffset, setContentOffset] = useState(0);
    const [selectedImage, setSelectedImage] = useState<File | null>(null);
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // 대시보드 데이터 상태
    const [summary, setSummary] = useState<DashboardSummary | null>(null);
    const [recentDocuments, setRecentDocuments] = useState<RecentDocument[]>([]);
    const [recentActivities, setRecentActivities] = useState<RecentActivity[]>([]);
    const [containerSummaries, setContainerSummaries] = useState<ContainerSummary[]>([]);
    const [chatHistory, setChatHistory] = useState<ChatHistory[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // 🆕 중복 호출 방지
    const loadingRef = useRef(false);
    const mountedRef = useRef(false);

    // 데이터 로드
    useEffect(() => {
        // 🆕 이미 마운트되었으면 스킵 (Strict Mode 대응)
        if (mountedRef.current) {
            console.log('✅ 이미 마운트됨 - 대시보드 로드 스킵');
            return;
        }
        mountedRef.current = true;

        loadDashboardData();
    }, []);

    const loadDashboardData = async () => {
        // 🆕 이미 로딩 중이면 스킵
        if (loadingRef.current) {
            console.log('⏭️ 대시보드 로딩 중복 호출 방지');
            return;
        }
        loadingRef.current = true;

        try {
            setIsLoading(true);
            console.log('🔄 대시보드 데이터 로드 시작...');

            const [summaryData, documentsData, activitiesData, containersData, chatData] = await Promise.all([
                getDashboardSummary(),
                getRecentDocuments(5),
                getRecentActivities(10),
                getContainerSummary(),
                getRecentChatSessions(5)
            ]);

            if (summaryData.success) {
                setSummary(summaryData.data);
            }

            if (documentsData.success) {
                setRecentDocuments(documentsData.documents);
            }

            if (activitiesData.success) {
                setRecentActivities(activitiesData.activities);
            }

            if (containersData.success) {
                setContainerSummaries(containersData.containers);
            }

            if (chatData.success) {
                setChatHistory(chatData.sessions);
            }

            console.log('✅ 대시보드 데이터 로드 완료');
        } catch (error: any) {
            console.error('❌ 대시보드 데이터 로드 실패:', error);

            // 403 에러 처리 (권한 없음)
            if (error?.response?.status === 403) {
                console.warn('⚠️ 대시보드 접근 권한이 없습니다. 관리자 권한이 필요합니다.');
                // 기본 데이터로 설정하여 빈 화면 방지
                setSummary({
                    my_documents_count: 0,
                    chat_sessions_count: 0,
                    pending_requests_count: 0
                });
            }
        } finally {
            setIsLoading(false);
            loadingRef.current = false;
        }
    };

    // 🆕 컴포넌트 언마운트 시 정리
    useEffect(() => {
        return () => {
            console.log('🔄 대시보드 언마운트');
            loadingRef.current = false;
        };
    }, []);

    // 컴포넌트 마운트 시 활동 카운트 증가
    useEffect(() => {
        incrementActivityCount('view');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // 빈 배열: 마운트 시 한 번만 실행 (incrementActivityCount는 안정적인 dispatch 함수)

    // 사이드바 상태에 따른 컨텐츠 오프셋 계산
    useEffect(() => {
        const calcOffset = () => {
            if (typeof window === 'undefined') return;
            if (window.innerWidth < 768) {
                setContentOffset(0);
            } else {
                setContentOffset(isSidebarOpen ? 256 : 64);
            }
        };
        calcOffset();
        window.addEventListener('resize', calcOffset);
        return () => window.removeEventListener('resize', calcOffset);
    }, [isSidebarOpen]);

    // 빠른 액션 핸들러들
    const handleQuickSearch = useCallback(() => {
        incrementActivityCount('search');
        navigateWithContext('search', {}, {});
    }, [navigateWithContext, incrementActivityCount]);

    const handleUploadDocument = useCallback(() => {
        incrementActivityCount('upload');
        navigateWithContext('my-knowledge', {}, {});
    }, [navigateWithContext, incrementActivityCount]);

    const handleAIChat = useCallback(() => {
        incrementActivityCount('chat');
        navigateWithContext('agent-chat', {}, { ragMode: hasSelectedDocuments });
    }, [navigateWithContext, hasSelectedDocuments, incrementActivityCount]);

    const handleClearSelectedDocuments = useCallback(() => {
        clearSelectedDocuments();
    }, [clearSelectedDocuments]);

    // 검색 핸들러들
    const handleSearch = useCallback(() => {
        if (searchQuery.trim() || selectedImage) {
            incrementActivityCount('search');

            // 이미지가 있으면 sessionStorage에 저장 (File 객체는 직접 전달 불가)
            if (selectedImage) {
                const reader = new FileReader();
                reader.onloadend = () => {
                    sessionStorage.setItem('pendingSearchImage', JSON.stringify({
                        data: reader.result,
                        name: selectedImage.name,
                        type: selectedImage.type,
                        size: selectedImage.size
                    }));

                    // 이미지 저장 후 검색 페이지로 이동
                    navigateWithContext('search', {
                        query: searchQuery.trim() || undefined,
                        hasImage: true
                    }, {});
                };
                reader.readAsDataURL(selectedImage);
            } else {
                // 텍스트만 있는 경우
                navigateWithContext('search', { query: searchQuery.trim() }, {});
            }
        }
    }, [searchQuery, selectedImage, incrementActivityCount, navigateWithContext]);

    const handleSearchSubmit = useCallback((e: React.FormEvent) => {
        e.preventDefault();
        handleSearch();
    }, [handleSearch]);

    const handleSearchKeyPress = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSearch();
        }
    }, [handleSearch]);

    // 이미지 업로드 핸들러
    const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드할 수 있습니다.');
                return;
            }
            if (file.size > 10 * 1024 * 1024) {
                alert('이미지 파일 크기는 10MB 이하여야 합니다.');
                return;
            }
            setSelectedImage(file);
            const reader = new FileReader();
            reader.onloadend = () => {
                setImagePreview(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleRemoveImage = () => {
        setSelectedImage(null);
        setImagePreview(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    // 클립보드 이미지 붙여넣기
    const handlePaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
        console.log('📋 [Dashboard] Paste event triggered');
        const items = event.clipboardData.items;
        console.log('📋 [Dashboard] Clipboard items:', items.length);

        for (let i = 0; i < items.length; i++) {
            console.log(`📋 [Dashboard] Item ${i}: type=${items[i].type}, kind=${items[i].kind}`);
        }

        let imageFound = false;
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.type.startsWith('image/')) {
                imageFound = true;
                console.log('✅ [Dashboard] Image found in clipboard!');
                event.preventDefault();
                const file = item.getAsFile();
                if (!file) {
                    console.error('❌ [Dashboard] Failed to get file from clipboard item');
                    continue;
                }

                console.log('📷 [Dashboard] Image file:', file.name, file.size, 'bytes');

                if (file.size > 10 * 1024 * 1024) {
                    alert('이미지 파일 크기는 10MB 이하여야 합니다.');
                    return;
                }

                setSelectedImage(file);
                setSearchQuery('');

                const reader = new FileReader();
                reader.onloadend = () => {
                    console.log('✅ [Dashboard] Image preview loaded');
                    setImagePreview(reader.result as string);
                };
                reader.readAsDataURL(file);
                break;
            }
        }

        if (!imageFound) {
            console.log('ℹ️ [Dashboard] No image in clipboard');
        }
    };

    // 날짜 포맷 헬퍼
    const formatDate = (dateString?: string) => {
        if (!dateString) return '날짜 없음';
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins}분 전`;
        if (diffHours < 24) return `${diffHours}시간 전`;
        if (diffDays < 7) return `${diffDays}일 전`;
        return date.toLocaleDateString('ko-KR');
    };

    // 파일 크기 포맷
    const formatFileSize = (bytes?: number) => {
        if (!bytes) return '0 KB';
        const kb = bytes / 1024;
        if (kb < 1024) return `${kb.toFixed(1)} KB`;
        return `${(kb / 1024).toFixed(1)} MB`;
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                    <p className="text-gray-600">대시보드 로딩 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 pb-40">
            {/* 환영 메시지 */}
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-sm border border-blue-100 p-6">
                <h1 className="text-2xl font-bold text-gray-900 mb-2">
                    안녕하세요, {user?.name}님! 👋
                </h1>
                <p className="text-gray-700">
                    효율적인 지식 관리와 스마트한 업무를 위한 대시보드입니다.
                </p>
            </div>

            {/* 대시보드 요약 카드 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* 내 문서 카드 */}
                <div
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all cursor-pointer hover:scale-105"
                    onClick={() => navigateWithContext('my-knowledge', {}, {})}
                >
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-gray-500 mb-1">내 문서</p>
                            <p className="text-3xl font-bold text-blue-600">
                                {summary?.my_documents_count || 0}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">총 업로드 문서</p>
                        </div>
                        <FileText className="w-12 h-12 text-blue-600 opacity-20" />
                    </div>
                </div>

                {/* 선택된 문서 카드 */}
                <div
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all cursor-pointer hover:scale-105"
                    onClick={hasSelectedDocuments ? handleAIChat : undefined}
                >
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-gray-500 mb-1">선택된 문서</p>
                            <p className="text-3xl font-bold text-green-600">
                                {selectedCount}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">AI 분석 준비됨</p>
                        </div>
                        <Folder className="w-12 h-12 text-green-600 opacity-20" />
                    </div>
                </div>

                {/* AI 대화 카드 */}
                <div
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all cursor-pointer hover:scale-105"
                    onClick={() => navigateWithContext('chat', {}, {})}
                >
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-gray-500 mb-1">AI 대화</p>
                            <p className="text-3xl font-bold text-purple-600">
                                {summary?.chat_sessions_count || 0}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">총 대화 세션</p>
                        </div>
                        <MessageSquare className="w-12 h-12 text-purple-600 opacity-20" />
                    </div>
                </div>

                {/* 대기 요청 카드 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-gray-500 mb-1">대기 요청</p>
                            <p className="text-3xl font-bold text-orange-600">
                                {summary?.pending_requests_count || 0}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">권한 승인 대기</p>
                        </div>
                        <Clock className="w-12 h-12 text-orange-600 opacity-20" />
                    </div>
                </div>
            </div>

            {/* 선택된 문서 상태 */}
            {hasSelectedDocuments && (
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                                <span className="text-blue-600 font-bold">📚</span>
                            </div>
                            <div>
                                <h3 className="text-base font-semibold text-blue-900">
                                    선택된 문서 {selectedCount}개
                                </h3>
                                <p className="text-blue-700 text-xs">
                                    선택한 문서들로 AI 에이전트를 시작하거나 관리할 수 있습니다.
                                </p>
                            </div>
                        </div>
                        <div className="flex space-x-2">
                            <button
                                onClick={handleAIChat}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                            >
                                💬 AI 에이전트 시작
                            </button>
                            <button
                                onClick={handleClearSelectedDocuments}
                                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors text-sm"
                            >
                                선택 해제
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 메인 콘텐츠 그리드 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
                {/* 빠른 시작 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                        <TrendingUp className="w-5 h-5 mr-2 text-blue-600" />
                        빠른 시작
                    </h3>
                    <div className="space-y-3">
                        <button
                            onClick={handleUploadDocument}
                            className="w-full text-left p-3 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
                        >
                            <div className="flex items-center">
                                <Upload className="w-5 h-5 mr-3 text-blue-600" />
                                <div>
                                    <div className="font-medium text-blue-900 text-sm">새 문서 업로드</div>
                                    <div className="text-xs text-blue-700">파일을 업로드하고 공유하세요</div>
                                </div>
                            </div>
                        </button>

                        <button
                            onClick={handleAIChat}
                            className="w-full text-left p-3 bg-green-50 rounded-lg hover:bg-green-100 transition-colors"
                        >
                            <div className="flex items-center">
                                <MessageSquare className="w-5 h-5 mr-3 text-green-600" />
                                <div>
                                    <div className="font-medium text-green-900 text-sm">
                                        AI에게 질문 {hasSelectedDocuments && `(${selectedCount}개 문서 선택됨)`}
                                    </div>
                                    <div className="text-xs text-green-700">
                                        {hasSelectedDocuments
                                            ? '선택한 문서들과 함께 AI와 대화하세요'
                                            : '궁금한 것을 바로 물어보세요'
                                        }
                                    </div>
                                </div>
                            </div>
                        </button>

                        <button
                            onClick={handleQuickSearch}
                            className="w-full text-left p-3 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors"
                        >
                            <div className="flex items-center">
                                <Search className="w-5 h-5 mr-3 text-purple-600" />
                                <div>
                                    <div className="font-medium text-purple-900 text-sm">검색하기</div>
                                    <div className="text-xs text-purple-700">필요한 정보를 찾아보세요</div>
                                </div>
                            </div>
                        </button>
                    </div>
                </div>

                {/* 최근 활동 타임라인 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                        <Clock className="w-5 h-5 mr-2 text-orange-600" />
                        최근 활동
                    </h3>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                        {recentActivities.length > 0 ? (
                            recentActivities.map((activity, index) => (
                                <div
                                    key={index}
                                    className="flex items-start space-x-3 p-2 rounded-lg hover:bg-gray-50 transition-colors"
                                >
                                    <div className={`flex-shrink-0 w-8 h-8 rounded-full bg-${activity.color}-100 flex items-center justify-center text-lg`}>
                                        {activity.icon}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-gray-900 truncate">
                                            {activity.title}
                                        </p>
                                        {activity.description && (
                                            <p className="text-xs text-gray-600 mt-0.5">
                                                {activity.description}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-0.5">
                                            {formatDate(activity.timestamp)}
                                        </p>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-8 text-gray-500">
                                <Clock className="w-12 h-12 mx-auto mb-2 opacity-20" />
                                <p className="text-sm">최근 활동이 없습니다</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* 최근 문서 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                        <FileText className="w-5 h-5 mr-2 text-gray-600" />
                        최근 문서
                    </h3>
                    <div className="space-y-3">
                        {recentDocuments.length > 0 ? (
                            recentDocuments.map((doc) => (
                                <div
                                    key={doc.file_bss_info_sno}
                                    className="border border-gray-200 rounded-lg p-3 hover:bg-gray-50 cursor-pointer transition-colors"
                                >
                                    <div className="font-medium text-gray-900 text-sm truncate" title={doc.title}>
                                        {doc.title}
                                    </div>
                                    <div className="text-xs text-gray-600 mt-1 flex items-center justify-between">
                                        <span>📁 {doc.container_name}</span>
                                        <span>⏰ {formatDate(doc.created_at)}</span>
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1">
                                        {formatFileSize(doc.file_size)} • {doc.file_type?.toUpperCase()}
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-8 text-gray-500">
                                <FileText className="w-12 h-12 mx-auto mb-2 opacity-20" />
                                <p className="text-sm">업로드한 문서가 없습니다</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* 최근 AI 대화 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                        <MessageSquare className="w-5 h-5 mr-2 text-purple-600" />
                        최근 AI 대화
                    </h3>
                    <div className="space-y-3">
                        {chatHistory.length > 0 ? (
                            chatHistory.map((chat) => {
                                // 🆕 세션 타입에 따라 라우팅 분기
                                const isAgentChat = chat.session_type === 'agent' || chat.session_id.startsWith('agent_');
                                const targetPage = isAgentChat ? 'agent-chat' : 'chat';

                                return (
                                    <div
                                        key={chat.session_id}
                                        className="border border-gray-200 rounded-lg p-3 hover:bg-gray-50 cursor-pointer transition-colors"
                                        onClick={() => navigateWithContext(targetPage, { sessionId: chat.session_id }, {})}
                                    >
                                        <div className="font-medium text-gray-900 text-sm truncate flex items-center gap-2" title={chat.title}>
                                            {isAgentChat && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">Agent</span>}
                                            {chat.title}
                                        </div>
                                        <div className="text-xs text-gray-600 mt-1 flex items-center justify-between">
                                            <span>💬 {chat.message_count}개 메시지</span>
                                            <span>📄 {chat.document_count}개 문서</span>
                                        </div>
                                        <div className="text-xs text-gray-500 mt-1">
                                            {formatDate(chat.last_message_at)}
                                        </div>
                                    </div>
                                );
                            })
                        ) : (
                            <div className="text-center py-8 text-gray-500">
                                <MessageSquare className="w-12 h-12 mx-auto mb-2 opacity-20" />
                                <p className="text-sm">AI 대화 기록이 없습니다</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* 내 컨테이너 현황 */}
            {containerSummaries.length > 0 && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                        <Folder className="w-5 h-5 mr-2 text-blue-600" />
                        내 지식 컨테이너 현황
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {containerSummaries.slice(0, 6).map((container) => (
                            <div
                                key={container.container_id}
                                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-all"
                            >
                                <div className="flex items-start justify-between mb-2">
                                    <h4 className="font-medium text-gray-900 text-sm">{container.container_name}</h4>
                                    <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                                        {container.my_permission}
                                    </span>
                                </div>
                                <div className="text-sm text-gray-600 space-y-1">
                                    <div className="flex justify-between">
                                        <span>내 문서:</span>
                                        <span className="font-medium">{container.my_documents_count}개</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>전체 문서:</span>
                                        <span className="font-medium">{container.total_documents_count}개</span>
                                    </div>
                                    {container.last_updated && (
                                        <div className="text-xs text-gray-500 mt-2">
                                            최근 업데이트: {formatDate(container.last_updated)}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 나의 활동 통계 */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">📊 나의 활동 통계</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 bg-blue-50 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">{userActivity.searchCount}</div>
                        <div className="text-sm text-gray-600 mt-1">🔍 검색</div>
                    </div>
                    <div className="text-center p-4 bg-green-50 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">{userActivity.uploadCount}</div>
                        <div className="text-sm text-gray-600 mt-1">📤 업로드</div>
                    </div>
                    <div className="text-center p-4 bg-purple-50 rounded-lg">
                        <div className="text-2xl font-bold text-purple-600">{userActivity.chatCount}</div>
                        <div className="text-sm text-gray-600 mt-1">💬 질문</div>
                    </div>
                    <div className="text-center p-4 bg-orange-50 rounded-lg">
                        <div className="text-2xl font-bold text-orange-600">{userActivity.viewCount}</div>
                        <div className="text-sm text-gray-600 mt-1">👀 조회</div>
                    </div>
                </div>
            </div>

            {/* 플로팅 검색창 */}
            <div
                className="fixed bottom-6 z-50 transition-all duration-300"
                style={{
                    left: contentOffset,
                    width: `calc(100% - ${contentOffset}px)`
                }}
            >
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-center">
                        <div className="w-full max-w-4xl bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
                            <div className="px-4 py-4">
                                {/* 이미지 미리보기 (상단에 표시) */}
                                {imagePreview && (
                                    <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <img
                                                src={imagePreview}
                                                alt="검색 이미지"
                                                className="w-16 h-16 object-cover rounded border border-gray-300"
                                            />
                                            <div className="text-sm">
                                                <p className="font-medium text-gray-700">{selectedImage?.name || '클립보드 이미지'}</p>
                                                <p className="text-gray-500">
                                                    {selectedImage && `${(selectedImage.size / 1024).toFixed(1)} KB`}
                                                </p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={handleRemoveImage}
                                            className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                            title="이미지 제거"
                                        >
                                            <X className="w-5 h-5" />
                                        </button>
                                    </div>
                                )}

                                <form onSubmit={handleSearchSubmit} className="flex items-center space-x-3">
                                    <div className="flex-1 relative">
                                        <input
                                            type="text"
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            onKeyPress={handleSearchKeyPress}
                                            onPaste={handlePaste}
                                            placeholder={selectedImage ? '🖼️ 이미지로 검색 중... (텍스트 추가 가능)' : '문서, 질문, 키워드로 검색하세요... (Ctrl+V로 이미지 붙여넣기)'}
                                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-24"
                                        />
                                        {/* 이미지 업로드 버튼 */}
                                        <button
                                            type="button"
                                            onClick={() => fileInputRef.current?.click()}
                                            className="absolute right-14 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-blue-600"
                                            title="이미지로 검색"
                                        >
                                            <Image className="w-5 h-5" />
                                        </button>
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept="image/*"
                                            onChange={handleImageSelect}
                                            className="hidden"
                                        />
                                        {searchQuery && !selectedImage && (
                                            <button
                                                type="button"
                                                onClick={() => setSearchQuery('')}
                                                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                            >
                                                <X className="w-5 h-5" />
                                            </button>
                                        )}
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={!searchQuery.trim() && !selectedImage}
                                        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
                                    >
                                        <Search className="w-5 h-5" />
                                        <span>검색</span>
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

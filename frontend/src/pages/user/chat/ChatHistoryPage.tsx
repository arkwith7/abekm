import { CalendarClock, Clock, FileText, History, MessageSquare, PlusCircle, RefreshCw } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGlobalApp } from '../../../contexts/GlobalAppContext';
import { useSidebar } from '../../../contexts/SidebarContext';
import { getRecentChatSessions } from '../../../services/dashboardService';
import type { ChatHistory } from '../../../types/dashboard.types';

const formatRelativeTime = (timestamp?: string) => {
    if (!timestamp) return '시간 정보 없음';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMinutes < 1) return '방금 전';
    if (diffMinutes < 60) return `${diffMinutes}분 전`;
    if (diffHours < 24) return `${diffHours}시간 전`;
    if (diffDays < 7) return `${diffDays}일 전`;
    return date.toLocaleDateString('ko-KR');
};

const formatDateTime = (timestamp?: string) => {
    if (!timestamp) return '시간 정보 없음';
    return new Date(timestamp).toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
};

const RecentChatsCard: React.FC<{
    items: ChatHistory[];
    onOpen: (sessionId: string) => void;
    loading: boolean;
}> = ({ items, onOpen, loading }) => {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                <div>
                    <p className="text-sm font-semibold text-gray-900">최근 AI 대화</p>
                    <p className="text-xs text-gray-500">마지막 5개의 대화를 빠르게 확인하세요.</p>
                </div>
                <History className="h-5 w-5 text-blue-500" />
            </div>

            <div className="space-y-3 px-5 py-4">
                {loading ? (
                    <div className="space-y-2">
                        {Array.from({ length: 3 }).map((_, idx) => (
                            <div key={idx} className="animate-pulse">
                                <div className="h-4 w-40 rounded-full bg-gray-200" />
                                <div className="mt-2 h-3 w-24 rounded-full bg-gray-100" />
                            </div>
                        ))}
                    </div>
                ) : items.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-4 text-center text-sm text-gray-500">
                        아직 대화 기록이 없습니다.
                    </div>
                ) : (
                    items.slice(0, 5).map((session) => {
                        const isAgentSession = session.session_type === 'agent' || session.session_id.startsWith('agent_');
                        return (
                            <button
                                key={session.session_id}
                                type="button"
                                onClick={() => onOpen(session.session_id)}
                                className="w-full rounded-xl border border-transparent bg-gray-50 px-4 py-3 text-left transition-colors hover:border-blue-200 hover:bg-blue-50"
                            >
                                <p className="truncate text-sm font-semibold text-gray-800 flex items-center gap-2">
                                    {isAgentSession && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">Agent</span>}
                                    {session.title || '제목 없는 대화'}
                                </p>
                                <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                                    <MessageSquare className="h-3.5 w-3.5" />
                                    <span>{session.message_count}개 메시지</span>
                                    <span className="text-gray-300">·</span>
                                    <span>{formatRelativeTime(session.last_message_at || session.created_at)}</span>
                                </div>
                            </button>
                        );
                    })
                )}
            </div>
        </div>
    );
};

const PAGE_SIZE = 10;

const ChatHistoryPage: React.FC = () => {
    const navigate = useNavigate();
    const { isOpen: isSidebarOpen } = useSidebar();
    const [contentOffset, setContentOffset] = useState(0);

    // 🆕 글로벌 상태에서 저장된 상태 복원
    const { state: globalState, actions } = useGlobalApp();
    const savedStateRef = useRef(globalState.pageStates?.chatHistory);

    const [history, setHistory] = useState<ChatHistory[]>(savedStateRef.current?.sessions || []);
    const [loading, setLoading] = useState(!savedStateRef.current?.sessions?.length); // 저장된 데이터가 있으면 로딩 스킵
    const [error, setError] = useState<string | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [cursor, setCursor] = useState<string | null>(savedStateRef.current?.cursor || null);
    const [hasMore, setHasMore] = useState(savedStateRef.current?.hasMore || false);
    const sentinelRef = useRef<HTMLDivElement | null>(null);
    const [autoLoadEnabled, setAutoLoadEnabled] = useState(false);
    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        const handleResize = () => {
            if (typeof window === 'undefined') return;
            if (window.innerWidth < 768) {
                setContentOffset(0);
            } else {
                setContentOffset(isSidebarOpen ? 256 : 64);
            }
        };

        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [isSidebarOpen]);

    const loadFirstPage = async () => {
        setAutoLoadEnabled(false);
        setHasMore(false);
        setCursor(null);
        try {
            setLoading(true);
            setError(null);
            const response = await getRecentChatSessions(PAGE_SIZE);
            if (response.success) {
                setHistory(response.sessions || []);
                setCursor(response.next_cursor || null);
                setHasMore(
                    typeof response.has_more === 'boolean'
                        ? response.has_more
                        : (response.sessions || []).length === PAGE_SIZE && !!response.next_cursor
                );
            } else {
                setError('대화 이력을 불러오지 못했습니다.');
            }
        } catch (err) {
            console.error('대화 이력 로드 실패:', err);
            setError('대화 이력을 불러오는 중 오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    // 🆕 상태 변경 시 저장 (디바운스)
    useEffect(() => {
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        saveTimeoutRef.current = setTimeout(() => {
            actions.savePageState('chatHistory', {
                sessions: history,
                cursor,
                hasMore,
                lastLoadTime: new Date().toISOString()
            });
        }, 500);

        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [history, cursor, hasMore]);

    useEffect(() => {
        // 저장된 데이터가 있고 최근 5분 이내라면 백엔드 조회 건너뛰기
        const savedState = savedStateRef.current;
        const lastLoad = savedState?.lastLoadTime ? new Date(savedState.lastLoadTime).getTime() : 0;
        const now = Date.now();
        const fiveMinutes = 5 * 60 * 1000;

        if (savedState?.sessions?.length && (now - lastLoad) < fiveMinutes) {
            console.log('✅ 저장된 대화 이력 사용 (백엔드 조회 스킵)');
            setLoading(false);
            return;
        }

        // 저장된 데이터가 없거나 오래된 경우 백엔드에서 조회
        loadFirstPage();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const loadMore = async () => {
        if (loadingMore || !hasMore) return;
        try {
            setLoadingMore(true);
            const response = await getRecentChatSessions(PAGE_SIZE, cursor || undefined);
            if (response.success) {
                const items = response.sessions || [];
                setHistory(prev => [...prev, ...items]);
                setCursor(response.next_cursor || null);
                setHasMore(
                    typeof response.has_more === 'boolean'
                        ? response.has_more
                        : items.length === PAGE_SIZE && !!response.next_cursor
                );
            }
        } catch (err) {
            console.warn('더보기 로드 실패:', err);
        } finally {
            setLoadingMore(false);
        }
    };

    // 사용자가 스크롤을 조금이라도 하면 자동 로드 활성화
    useEffect(() => {
        const onScroll = () => {
            if (window.scrollY > 80) {
                setAutoLoadEnabled(true);
            }
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    // 무한 스크롤 옵저버 (사용자가 스크롤을 시작한 이후에만 동작)
    useEffect(() => {
        if (!autoLoadEnabled || !hasMore) return;
        const el = sentinelRef.current;
        if (!el) return;
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    loadMore();
                }
            });
        }, { rootMargin: '0px 0px 200px 0px' });
        observer.observe(el);
        return () => observer.disconnect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoLoadEnabled, cursor, hasMore, loadingMore]);

    const stats = useMemo(() => {
        const totalSessions = history.length;
        const totalMessages = history.reduce((sum, session) => sum + (session.message_count || 0), 0);
        const totalDocuments = history.reduce((sum, session) => sum + (session.document_count || 0), 0);
        const latestTimestamp = history.reduce((latest, session) => {
            const candidate = new Date(session.last_message_at || session.created_at || 0).getTime();
            return candidate > latest ? candidate : latest;
        }, 0);
        return {
            totalSessions,
            totalMessages,
            totalDocuments,
            lastUpdated: latestTimestamp ? formatRelativeTime(new Date(latestTimestamp).toISOString()) : '기록 없음'
        };
    }, [history]);

    const handleOpenSession = (sessionId: string) => {
        if (!sessionId) return;

        // 🆕 세션 타입에 따라 올바른 채팅 페이지로 라우팅
        const isAgentSession = sessionId.startsWith('agent_');
        const targetPath = isAgentSession ? '/user/agent-chat' : '/user/chat';

        navigate(`${targetPath}?session=${sessionId}`);
    };

    return (
        <div className="min-h-full bg-gradient-to-br from-slate-50 via-white to-slate-100">
            <div
                className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8"
                style={{ paddingLeft: contentOffset ? Math.max(contentOffset - 64, 0) : 0 }}
            >
                <header className="flex flex-col gap-4 rounded-2xl border border-blue-100 bg-white/90 p-6 shadow-sm md:flex-row md:items-center md:justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">대화 이력</h1>
                        <p className="mt-1 text-sm text-gray-600">
                            AI 에이전트와 진행한 모든 대화를 한 곳에서 확인하고, 필요한 순간에 다시 이어갈 수 있습니다.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            onClick={loadFirstPage}
                            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600"
                            disabled={loading}
                        >
                            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-blue-500' : ''}`} />
                            새로고침
                        </button>
                        <button
                            type="button"
                            onClick={() => navigate('/user/chat')}
                            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700"
                        >
                            <PlusCircle className="h-4 w-4" />
                            새 대화 시작
                        </button>
                    </div>
                </header>

                <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">총 대화</p>
                        <div className="mt-2 flex items-center gap-3">
                            <MessageSquare className="h-8 w-8 text-blue-500" />
                            <div>
                                <p className="text-2xl font-bold text-gray-900">{stats.totalSessions}</p>
                                <p className="text-xs text-gray-500">저장된 AI 대화 세션</p>
                            </div>
                        </div>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">메시지</p>
                        <div className="mt-2 flex items-center gap-3">
                            <MessageSquare className="h-8 w-8 text-purple-500" />
                            <div>
                                <p className="text-2xl font-bold text-gray-900">{stats.totalMessages}</p>
                                <p className="text-xs text-gray-500">누적 메시지 수</p>
                            </div>
                        </div>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">참조 문서</p>
                        <div className="mt-2 flex items-center gap-3">
                            <FileText className="h-8 w-8 text-emerald-500" />
                            <div>
                                <p className="text-2xl font-bold text-gray-900">{stats.totalDocuments}</p>
                                <p className="text-xs text-gray-500">연결된 문서 개수</p>
                            </div>
                        </div>
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">최근 업데이트</p>
                        <div className="mt-2 flex items-center gap-3">
                            <Clock className="h-8 w-8 text-amber-500" />
                            <div>
                                <p className="text-2xl font-bold text-gray-900">{stats.lastUpdated}</p>
                                <p className="text-xs text-gray-500">마지막 대화 활동</p>
                            </div>
                        </div>
                    </div>
                </section>

                <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
                    <section className="space-y-4">
                        {error && (
                            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                                {error}
                            </div>
                        )}

                        {loading ? (
                            <div className="space-y-4">
                                {Array.from({ length: 4 }).map((_, idx) => (
                                    <div key={idx} className="animate-pulse rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                                        <div className="h-5 w-1/3 rounded-full bg-gray-200" />
                                        <div className="mt-3 h-4 w-1/2 rounded-full bg-gray-100" />
                                        <div className="mt-6 flex gap-3">
                                            <div className="h-6 w-20 rounded-full bg-gray-100" />
                                            <div className="h-6 w-24 rounded-full bg-gray-100" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : history.length === 0 ? (
                            <div className="rounded-3xl border border-dashed border-gray-200 bg-white p-10 text-center shadow-sm">
                                <p className="text-lg font-semibold text-gray-700">아직 저장된 대화가 없습니다.</p>
                                <p className="mt-2 text-sm text-gray-500">AI 에이전트와의 첫 대화를 시작해 보세요. 선택한 문서를 기반으로 맞춤형 답변을 제공합니다.</p>
                                <button
                                    type="button"
                                    onClick={() => navigate('/user/chat')}
                                    className="mt-4 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
                                >
                                    <PlusCircle className="h-4 w-4" />
                                    AI 에이전트 열기
                                </button>
                            </div>
                        ) : (
                            history.map((session) => {
                                const isAgentSession = session.session_type === 'agent' || session.session_id.startsWith('agent_');
                                return (
                                    <article
                                        key={session.session_id}
                                        className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
                                    >
                                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                            <div>
                                                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                                                    {isAgentSession && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">Agent</span>}
                                                    {session.title || '제목 없는 대화'}
                                                </h2>
                                                <p className="mt-1 text-sm text-gray-500">
                                                    마지막 활동 {formatRelativeTime(session.last_message_at || session.created_at)} · 생성 {formatDateTime(session.created_at)}
                                                </p>
                                            </div>
                                            <div className="flex flex-wrap items-center gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => handleOpenSession(session.session_id)}
                                                    className="inline-flex items-center gap-2 rounded-xl border border-blue-200 px-4 py-2 text-sm font-medium text-blue-600 transition-colors hover:bg-blue-50"
                                                >
                                                    <MessageSquare className="h-4 w-4" />
                                                    대화 열기
                                                </button>
                                            </div>
                                        </div>

                                        <div className="mt-4 flex flex-wrap gap-3 text-sm text-gray-600">
                                            <span className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-blue-700">
                                                <MessageSquare className="h-4 w-4" />
                                                {session.message_count}개 메시지
                                            </span>
                                            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-emerald-700">
                                                <FileText className="h-4 w-4" />
                                                참조 문서 {session.document_count}개
                                            </span>
                                            <span className="inline-flex items-center gap-2 rounded-full border border-gray-100 bg-gray-50 px-3 py-1 text-gray-700">
                                                <CalendarClock className="h-4 w-4" />
                                                생성일 {formatDateTime(session.created_at)}
                                            </span>
                                        </div>
                                    </article>
                                );
                            })
                        )}
                        {/* 무한 스크롤 센티넬 */}
                        <div ref={sentinelRef} />
                        {/* 더보기 버튼 (폴백) */}
                        {!loading && hasMore && (
                            <div className="flex justify-center">
                                <button
                                    type="button"
                                    onClick={loadMore}
                                    disabled={loadingMore}
                                    className="mt-2 rounded-xl border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:border-blue-300 hover:text-blue-600 disabled:opacity-50"
                                >
                                    {loadingMore ? '불러오는 중…' : '더보기'}
                                </button>
                            </div>
                        )}
                    </section>

                    <aside className="space-y-4">
                        <RecentChatsCard items={history} loading={loading} onOpen={handleOpenSession} />
                    </aside>
                </div>
            </div>
        </div>
    );
};

export default ChatHistoryPage;

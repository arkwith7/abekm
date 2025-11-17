/**
 * 글로벌 앱 상태 관리 Context
 */
import React, { createContext, ReactNode, useContext, useEffect, useMemo, useReducer } from 'react';
import { getGlobalNavigate } from '../utils/navigation';
import {
    globalAppReducer,
    initialGlobalState,
    loadStateFromLocalStorage,
    saveStateToLocalStorage
} from './globalAppReducer';
import {
    AgentType,
    ChatMessage,
    ChatSession,
    Document,
    GlobalAppAction,
    GlobalAppState,
    KnowledgeContainer,
    SourcePageType,
    UserActivity
} from './types';

// Context 타입 정의
interface GlobalAppContextType {
    state: GlobalAppState;
    dispatch: React.Dispatch<GlobalAppAction>;

    // 편의 함수들
    actions: {
        // 사용자 관련
        setUser: (user: GlobalAppState['user']) => void;

        // 컨테이너 관련
        setSelectedContainers: (containers: KnowledgeContainer[]) => void;
        addSelectedContainer: (container: KnowledgeContainer) => void;
        removeSelectedContainer: (containerId: string) => void;

        // 문서 관련
        setSelectedDocuments: (documents: Document[]) => void;
        addSelectedDocument: (document: Document) => void;
        removeSelectedDocument: (fileId: string) => void;
        clearSelectedDocuments: () => void;
        toggleDocumentSelection: (document: Document) => void;

        // 페이지별 문서 관리
        setPageSelectedDocuments: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat', documents: Document[]) => void;
        addPageSelectedDocument: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat', document: Document) => void;
        removePageSelectedDocument: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat', fileId: string) => void;
        clearPageSelectedDocuments: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat') => void;

        // 작업 컨텍스트 관련
        updateWorkContext: (context: Partial<GlobalAppState['workContext']>) => void;
        navigateWithContext: (
            to: SourcePageType,
            preserveState?: any,
            options?: { ragMode?: boolean; selectedAgent?: AgentType; selectedAgentChain?: string }
        ) => boolean;

        // 채팅 관련
        setChatSession: (session: ChatSession | null) => void;
        addChatMessage: (message: ChatMessage) => void;
        clearChatHistory: () => void;

        // 페이지 상태 관리
        savePageState: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' | 'chatHistory' | 'containerExplorer', state: any) => void;
        restorePageState: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' | 'chatHistory' | 'containerExplorer') => any;

        // UI 관련
        setLoading: (loading: boolean) => void;
        setError: (error: string | null) => void;
        addNotification: (type: 'success' | 'error' | 'warning' | 'info', message: string) => void;
        removeNotification: (id: string) => void;

        // 🆕 워크플로우 관련
        startWorkflow: (step: string, data?: any) => void;
        updateWorkflowStep: (step: string, data?: any) => void;
        completeWorkflow: (data?: any) => void;
        cancelWorkflow: () => void;
        updateUserActivity: (activity: Partial<UserActivity>) => void;
        incrementActivityCount: (type: 'search' | 'upload' | 'chat' | 'view') => void;

        // 기타
        resetState: () => void;
        clearAllDocumentsOnLogout: () => void; // 로그아웃 시 모든 선택된 문서 클리어
    };
}

// Context 생성
const GlobalAppContext = createContext<GlobalAppContextType | undefined>(undefined);

// Provider 컴포넌트
interface GlobalAppProviderProps {
    children: ReactNode;
}

export const GlobalAppProvider: React.FC<GlobalAppProviderProps> = ({ children }) => {
    const [state, dispatch] = useReducer(globalAppReducer, initialGlobalState);
    const lastNavigationRef = React.useRef<{ route: string; at: number } | null>(null);

    // 로컬 스토리지에서 상태 복원
    useEffect(() => {
        const savedState = loadStateFromLocalStorage();
        if (savedState) {
            // 각 저장된 상태를 개별적으로 복원
            if (savedState.selectedContainers) {
                dispatch({ type: 'SET_SELECTED_CONTAINERS', payload: savedState.selectedContainers });
            }
            if (savedState.selectedDocuments) {
                dispatch({ type: 'SET_SELECTED_DOCUMENTS', payload: savedState.selectedDocuments });
            }
            if (savedState.workContext) {
                dispatch({ type: 'UPDATE_WORK_CONTEXT', payload: savedState.workContext });
            }
            if (savedState.pageStates) {
                if (savedState.pageStates.search) {
                    dispatch({
                        type: 'SAVE_PAGE_STATE',
                        payload: { page: 'search', state: savedState.pageStates.search }
                    });
                }
                if (savedState.pageStates.myKnowledge) {
                    dispatch({
                        type: 'SAVE_PAGE_STATE',
                        payload: { page: 'myKnowledge', state: savedState.pageStates.myKnowledge }
                    });
                }
                if (savedState.pageStates.chat) {
                    dispatch({
                        type: 'SET_PAGE_SELECTED_DOCUMENTS',
                        payload: { page: 'chat', documents: savedState.pageStates.chat.selectedDocuments || [] }
                    });
                }
                if (savedState.pageStates.agentChat) {
                    dispatch({
                        type: 'SET_PAGE_SELECTED_DOCUMENTS',
                        payload: { page: 'agentChat', documents: savedState.pageStates.agentChat.selectedDocuments || [] }
                    });
                }
            }
        }
    }, []);

    // 상태 변경 시 로컬 스토리지에 저장
    useEffect(() => {
        saveStateToLocalStorage(state);
    }, [state]);

    // navigateWithContext는 state를 참조하므로 useCallback으로 별도 메모이제이션
    const navigateWithContext = React.useCallback((
        to: SourcePageType,
        preserveState?: any,
        options?: { ragMode?: boolean; selectedAgent?: AgentType; selectedAgentChain?: string }
    ) => {
        let navigated = false;
        // 페이지 전환 시 문서 동기화 로직
        const fromPage = state.workContext.sourcePageType;

        const documentsEqual = (a: Document[] = [], b: Document[] = []) => {
            if (a.length !== b.length) {
                return false;
            }
            return a.every((doc, idx) => doc.fileId === b[idx]?.fileId);
        };

        const cloneDocuments = (docs: Document[] = []) => docs.map(doc => ({ ...doc }));

        const syncDocumentsIfNeeded = (
            page: 'search' | 'myKnowledge' | 'chat' | 'agentChat',
            docs: Document[] = []
        ) => {
            const existing = state.pageStates[page]?.selectedDocuments || [];
            const sanitizedDocs = cloneDocuments(docs);
            if (!documentsEqual(existing, sanitizedDocs)) {
                dispatch({
                    type: 'SET_PAGE_SELECTED_DOCUMENTS',
                    payload: { page, documents: sanitizedDocs }
                });
            }
        };

        // 검색/내지식 → 일반 채팅 이동
        if ((fromPage === 'search' || fromPage === 'my-knowledge') && to === 'chat') {
            const sourceDocs = fromPage === 'search'
                ? state.pageStates.search.selectedDocuments
                : state.pageStates.myKnowledge.selectedDocuments;
            if (sourceDocs && sourceDocs.length > 0 && (!state.pageStates.chat.selectedDocuments || state.pageStates.chat.selectedDocuments.length === 0)) {
                syncDocumentsIfNeeded('chat', sourceDocs);
            }
        }

        // 검색/내지식 → Agent 채팅 이동 (선택 문서를 그대로 전달)
        if ((fromPage === 'search' || fromPage === 'my-knowledge') && to === 'agent-chat') {
            const sourceDocs = fromPage === 'search'
                ? state.pageStates.search.selectedDocuments
                : state.pageStates.myKnowledge.selectedDocuments;
            syncDocumentsIfNeeded('agentChat', sourceDocs || []);
        }

        // 일반 채팅 → 검색/내지식 이동 (기존 로직 유지)
        if (fromPage === 'chat' && (to === 'search' || to === 'my-knowledge')) {
            const chatDocs = state.pageStates.chat.selectedDocuments;
            const targetPage = to === 'search' ? 'search' : 'myKnowledge';
            const existing = state.pageStates[targetPage]?.selectedDocuments || [];
            if (chatDocs && chatDocs.length > 0) {
                const mergedMap: Record<string, Document> = {};
                existing.forEach((d: Document) => { mergedMap[d.fileId] = d; });
                chatDocs.forEach((d: Document) => { mergedMap[d.fileId] = d; });
                const merged = Object.values(mergedMap);
                if (!documentsEqual(existing, merged)) {
                    syncDocumentsIfNeeded(targetPage as 'search' | 'myKnowledge', merged);
                }
            }
        }

        // 일반 채팅 → Agent 채팅 이동 (선택 문서를 복사)
        if (fromPage === 'chat' && to === 'agent-chat') {
            const chatDocs = state.pageStates.chat.selectedDocuments || [];
            syncDocumentsIfNeeded('agentChat', chatDocs);
        }

        // Agent 채팅 → 검색/내지식 이동 (문서 공유)
        if (fromPage === 'agent-chat' && (to === 'search' || to === 'my-knowledge')) {
            const agentDocs = state.pageStates.agentChat.selectedDocuments || [];
            const targetPage = to === 'search' ? 'search' : 'myKnowledge';
            const existing = state.pageStates[targetPage]?.selectedDocuments || [];
            if (agentDocs.length > 0) {
                const mergedMap: Record<string, Document> = {};
                existing.forEach((d: Document) => { mergedMap[d.fileId] = d; });
                agentDocs.forEach((d: Document) => { mergedMap[d.fileId] = d; });
                const merged = Object.values(mergedMap);
                if (!documentsEqual(existing, merged)) {
                    syncDocumentsIfNeeded(targetPage as 'search' | 'myKnowledge', merged);
                }
            } else if (existing.length > 0) {
                syncDocumentsIfNeeded(targetPage as 'search' | 'myKnowledge', []);
            }
        }

        // Agent 채팅 ↔ 일반 채팅 간 이동 시 선택 문서 동기화
        if (fromPage === 'agent-chat' && to === 'chat') {
            const agentDocs = state.pageStates.agentChat.selectedDocuments || [];
            syncDocumentsIfNeeded('chat', agentDocs);
        }

        // 1. 상태 업데이트
        dispatch({
            type: 'UPDATE_WORK_CONTEXT',
            payload: {
                sourcePageType: to,
                sourcePageState: preserveState,
                ragMode: options?.ragMode ?? state.workContext.ragMode,
                selectedAgent: options?.selectedAgent ?? state.workContext.selectedAgent,
                selectedAgentChain: options?.selectedAgentChain ?? state.workContext.selectedAgentChain,
                isChainMode: !!options?.selectedAgentChain,
                mode: options?.selectedAgentChain ? 'chain' : (state.workContext.mode || 'single')
            }
        });

        // 2. 실제 페이지 이동
        const navigate = getGlobalNavigate();
        const routeMap: Record<SourcePageType, string> = {
            'my-knowledge': '/user/my-knowledge',
            'search': '/user/search',
            'chat': '/user/chat',
            'agent-chat': '/user/agent-chat',  // 🆕 Agent 채팅 추가
            'dashboard': '/user'
        };

        let targetRoute = routeMap[to];

        if (!targetRoute) {
            console.warn(`⚠️ 알 수 없는 페이지 타입: ${to}`);
            return false;
        }

        // 🆕 채팅 페이지(일반/Agent) 이동 시 sessionId가 있으면 URL 파라미터로 추가
        if ((to === 'chat' || to === 'agent-chat') && preserveState?.sessionId) {
            targetRoute = `${targetRoute}?session=${preserveState.sessionId}`;
            console.log('🔗 채팅 세션 ID 포함하여 이동:', to, preserveState.sessionId);
        }

        // 현재 경로와 동일하면 중복 네비게이션 방지 (단, 쿼리 파라미터가 다른 경우는 허용)
        const currentFullPath = typeof window !== 'undefined' ? window.location.pathname + window.location.search : '';
        if (currentFullPath === targetRoute) {
            console.log('ℹ️ 동일한 경로로 이미 있음, 이동 생략:', targetRoute);
            return true; // 이미 해당 경로에 있으므로 이동 성공으로 간주
        }

        // 아주 짧은 시간 내 동일 경로로의 연속 호출 방지 (디바운스)
        const now = Date.now();
        if (lastNavigationRef.current && lastNavigationRef.current.route === targetRoute && now - lastNavigationRef.current.at < 300) {
            try { console.warn('[navigateWithContext] suppressed rapid duplicate navigation to', targetRoute); } catch { }
            return true;
        }
        lastNavigationRef.current = { route: targetRoute, at: now };

        if (navigate) {
            navigate(targetRoute);
            navigated = true;
        } else if (typeof window !== 'undefined') {
            window.location.href = targetRoute;
            navigated = true;
        } else {
            console.warn('[navigateWithContext] No navigation method available');
        }
        return navigated;
    }, [state.workContext, state.pageStates]); // state의 관련 필드만 의존성에 추가

    // 편의 함수들 - dispatch만 의존하도록 리팩토링 (state 참조 제거)
    const actions = useMemo(() => ({
        // 사용자 관련
        setUser: (user: GlobalAppState['user']) => {
            dispatch({ type: 'SET_USER', payload: user });
        },

        // 컨테이너 관련
        setSelectedContainers: (containers: KnowledgeContainer[]) => {
            dispatch({ type: 'SET_SELECTED_CONTAINERS', payload: containers });
        },

        addSelectedContainer: (container: KnowledgeContainer) => {
            dispatch({ type: 'ADD_SELECTED_CONTAINER', payload: container });
        },

        removeSelectedContainer: (containerId: string) => {
            dispatch({ type: 'REMOVE_SELECTED_CONTAINER', payload: containerId });
        },

        // 문서 관련
        setSelectedDocuments: (documents: Document[]) => {
            dispatch({ type: 'SET_SELECTED_DOCUMENTS', payload: documents });
        },

        addSelectedDocument: (document: Document) => {
            dispatch({ type: 'ADD_SELECTED_DOCUMENT', payload: document });
        },

        removeSelectedDocument: (fileId: string) => {
            // state 참조 제거: 리듀서에서 currentPage 판단하도록 위임
            dispatch({
                type: 'REMOVE_SELECTED_DOCUMENT',
                payload: fileId
            });
        },

        clearSelectedDocuments: () => {
            // state 참조 제거: 리듀서에서 currentPage 판단하도록 위임
            dispatch({
                type: 'CLEAR_SELECTED_DOCUMENTS'
            });
        },

        // 페이지별 선택된 문서 관리 함수들
        setPageSelectedDocuments: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat', documents: Document[]) => {
            dispatch({
                type: 'SET_PAGE_SELECTED_DOCUMENTS',
                payload: { page, documents }
            });
        },

        addPageSelectedDocument: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat', document: Document) => {
            dispatch({
                type: 'ADD_PAGE_SELECTED_DOCUMENT',
                payload: { page, document }
            });
        },

        removePageSelectedDocument: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat', fileId: string) => {
            dispatch({
                type: 'REMOVE_PAGE_SELECTED_DOCUMENT',
                payload: { page, fileId }
            });
        },

        clearPageSelectedDocuments: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat') => {
            dispatch({
                type: 'CLEAR_PAGE_SELECTED_DOCUMENTS',
                payload: { page }
            });
        },

        toggleDocumentSelection: (document: Document) => {
            // state 참조 제거: 리듀서에서 현재 페이지와 선택 상태 판단하도록 위임
            dispatch({
                type: 'TOGGLE_DOCUMENT_SELECTION',
                payload: document
            });
        },

        // 작업 컨텍스트 관련
        updateWorkContext: (context: Partial<GlobalAppState['workContext']>) => {
            dispatch({ type: 'UPDATE_WORK_CONTEXT', payload: context });
        },

        // navigateWithContext는 useCallback으로 별도 정의됨 (아래에서 추가)

        // 채팅 관련
        setChatSession: (session: ChatSession | null) => {
            dispatch({ type: 'SET_CHAT_SESSION', payload: session });
        },

        addChatMessage: (message: ChatMessage) => {
            dispatch({ type: 'ADD_CHAT_MESSAGE', payload: message });
        },

        clearChatHistory: () => {
            dispatch({ type: 'CLEAR_CHAT_HISTORY' });
        },

        // 페이지 상태 관리
        savePageState: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' | 'chatHistory' | 'containerExplorer', state: any) => {
            dispatch({ type: 'SAVE_PAGE_STATE', payload: { page, state } });
        },

        restorePageState: (page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' | 'chatHistory' | 'containerExplorer') => {
            dispatch({ type: 'RESTORE_PAGE_STATE', payload: { page } });
            return state.pageStates[page];
        },

        // UI 관련
        setLoading: (loading: boolean) => {
            dispatch({ type: 'SET_LOADING', payload: loading });
        },

        setError: (error: string | null) => {
            dispatch({ type: 'SET_ERROR', payload: error });
        },

        addNotification: (type: 'success' | 'error' | 'warning' | 'info', message: string) => {
            dispatch({ type: 'ADD_NOTIFICATION', payload: { type, message } });
        },

        removeNotification: (id: string) => {
            dispatch({ type: 'REMOVE_NOTIFICATION', payload: id });
        },

        // 🆕 워크플로우 관련 액션들
        startWorkflow: (step: string, data?: any) => {
            dispatch({ type: 'START_WORKFLOW', payload: { step, data } });
        },

        updateWorkflowStep: (step: string, data?: any) => {
            dispatch({ type: 'UPDATE_WORKFLOW_STEP', payload: { step, data } });
        },

        completeWorkflow: (data?: any) => {
            dispatch({ type: 'COMPLETE_WORKFLOW', payload: data });
        },

        cancelWorkflow: () => {
            dispatch({ type: 'CANCEL_WORKFLOW' });
        },

        updateUserActivity: (activity: Partial<UserActivity>) => {
            dispatch({ type: 'UPDATE_USER_ACTIVITY', payload: activity });
        },

        incrementActivityCount: (type: 'search' | 'upload' | 'chat' | 'view') => {
            dispatch({ type: 'INCREMENT_ACTIVITY_COUNT', payload: { type } });
        },

        // 기타
        resetState: () => {
            dispatch({ type: 'RESET_STATE' });
        },

        clearAllDocumentsOnLogout: () => {
            // 모든 페이지의 선택된 문서 클리어
            dispatch({ type: 'CLEAR_PAGE_SELECTED_DOCUMENTS', payload: { page: 'search' } });
            dispatch({ type: 'CLEAR_PAGE_SELECTED_DOCUMENTS', payload: { page: 'myKnowledge' } });
            dispatch({ type: 'CLEAR_PAGE_SELECTED_DOCUMENTS', payload: { page: 'chat' } });
            dispatch({ type: 'CLEAR_PAGE_SELECTED_DOCUMENTS', payload: { page: 'agentChat' } });
            dispatch({ type: 'SET_SELECTED_DOCUMENTS', payload: [] });

            // 🆕 localStorage 정리
            try {
                localStorage.removeItem('pageStates'); // 페이지별 상태 (선택 문서 포함)
                localStorage.removeItem('wikl_chat_state'); // 채팅 상태
                localStorage.removeItem('wikl_agent_chat_state'); // Agent 채팅 상태
                console.log('🧹 로그아웃: 모든 선택 문서 + localStorage 클리어 완료');
            } catch (error) {
                console.warn('⚠️ localStorage 정리 실패:', error);
            }
        },

        // navigateWithContext는 useCallback으로 별도 정의되어 아래에서 추가됨
        navigateWithContext
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }), [dispatch, navigateWithContext]); // navigateWithContext는 이미 useCallback으로 state.pageStates, state.workContext에 의존

    const contextValue: GlobalAppContextType = {
        state,
        dispatch,
        actions
    };

    return (
        <GlobalAppContext.Provider value={contextValue}>
            {children}
        </GlobalAppContext.Provider>
    );
};

// Custom Hook
export const useGlobalApp = (): GlobalAppContextType => {
    const context = useContext(GlobalAppContext);
    if (context === undefined) {
        throw new Error('useGlobalApp must be used within a GlobalAppProvider');
    }
    return context;
};

// 개별 기능별 커스텀 훅들
export const useSelectedDocuments = () => {
    const { state, actions } = useGlobalApp();

    // 현재 페이지에 따라 적절한 선택된 문서들을 반환
    const currentPage = state.workContext.sourcePageType;
    const getCurrentPageDocuments = () => {
        switch (currentPage) {
            case 'search':
                return state.pageStates.search.selectedDocuments;
            case 'my-knowledge':
                return state.pageStates.myKnowledge.selectedDocuments;
            case 'chat':
                return state.pageStates.chat.selectedDocuments;
            case 'agent-chat':
                return state.pageStates.agentChat.selectedDocuments;
            default:
                return [];
        }
    };

    const selectedDocuments = getCurrentPageDocuments() || [];
    const targetPage = currentPage === 'search' ? 'search' :
        currentPage === 'my-knowledge' ? 'myKnowledge' :
            currentPage === 'agent-chat' ? 'agentChat' : 'chat';

    return {
        selectedDocuments,
        setSelectedDocuments: (documents: Document[]) => {
            actions.setPageSelectedDocuments(targetPage, documents);
        },
        addSelectedDocument: (document: Document) => {
            actions.addPageSelectedDocument(targetPage, document);
        },
        removeSelectedDocument: actions.removeSelectedDocument,
        clearSelectedDocuments: actions.clearSelectedDocuments,
        toggleDocumentSelection: (document: Document) => {
            const isSelected = selectedDocuments.some((doc: Document) => doc.fileId === document.fileId);
            if (isSelected) actions.removeSelectedDocument(document.fileId); else actions.addPageSelectedDocument(targetPage, document);
        },
        hasSelectedDocuments: (selectedDocuments?.length || 0) > 0,
        selectedCount: selectedDocuments?.length || 0
    };
};

export const useWorkContext = () => {
    const { state, actions } = useGlobalApp();
    return {
        workContext: state.workContext,
        updateWorkContext: actions.updateWorkContext,
        navigateWithContext: actions.navigateWithContext,
        isRagMode: state.workContext.ragMode,
        selectedAgent: state.workContext.selectedAgent,
        selectedAgentChain: state.workContext.selectedAgentChain,
        isChainMode: state.workContext.isChainMode,
        agentMode: state.workContext.mode || 'single',
        selectedAgents: state.workContext.selectedAgents || [],
        sourcePageType: state.workContext.sourcePageType,
        // 🆕 워크플로우 관련 함수들
        workflow: state.workflow,
        startWorkflow: actions.startWorkflow,
        updateWorkflowStep: actions.updateWorkflowStep,
        completeWorkflow: actions.completeWorkflow,
        cancelWorkflow: actions.cancelWorkflow,
        userActivity: state.userActivity,
        updateUserActivity: actions.updateUserActivity,
        incrementActivityCount: actions.incrementActivityCount
    };
};

export const useChatState = () => {
    const { state, actions } = useGlobalApp();
    return {
        currentSession: state.currentChatSession,
        chatHistory: state.chatHistory,
        setChatSession: actions.setChatSession,
        addChatMessage: actions.addChatMessage,
        clearChatHistory: actions.clearChatHistory,
        hasMessages: state.chatHistory.length > 0
    };
};

export const usePageState = () => {
    const { state, actions } = useGlobalApp();
    return {
        pageStates: state.pageStates,
        savePageState: actions.savePageState,
        restorePageState: actions.restorePageState
    };
};

export const useNotifications = () => {
    const { state, actions } = useGlobalApp();
    return {
        notifications: state.ui.notifications,
        addNotification: actions.addNotification,
        removeNotification: actions.removeNotification,
        hasNotifications: state.ui.notifications.length > 0
    };
};

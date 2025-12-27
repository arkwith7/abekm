/**
 * 글로벌 앱 상태 관리 Context
 */
import React, { ReactNode, useMemo } from 'react';
import { getGlobalNavigate } from '../utils/navigation';
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
import { useGlobalAppStore } from '../store/globalAppStore';

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

// Provider 컴포넌트
interface GlobalAppProviderProps {
    children: ReactNode;
}

export const GlobalAppProvider: React.FC<GlobalAppProviderProps> = ({ children }) => {
    // Provider는 구독/값 전달을 하지 않음 (호환성 유지용 래퍼)
    return <>{children}</>;
};

// Custom Hook
export const useGlobalApp = (): GlobalAppContextType => {
    // explicit typing to satisfy CRA/tsc strict compilation inside Docker
    const storeActions = useGlobalAppStore((s: import('../store/globalAppStore').GlobalAppStore) => s.actions);
    const state = useGlobalAppStore((s: import('../store/globalAppStore').GlobalAppStore) => {
        // store에는 actions가 포함되므로 제거해서 기존 타입과 정합
        const { actions: _a, ...rest } = s as any;
        return rest as GlobalAppState;
    });
    const dispatch = React.useCallback((action: GlobalAppAction) => {
        // 기존 reducer-style dispatch를 최소 지원 (신규 개발은 storeActions 사용 권장)
        switch (action.type) {
            case 'SET_USER':
                storeActions.setUser(action.payload);
                break;
            case 'SET_SELECTED_CONTAINERS':
                storeActions.setSelectedContainers(action.payload);
                break;
            case 'SET_SELECTED_DOCUMENTS':
                storeActions.setSelectedDocuments(action.payload);
                break;
            case 'SET_PAGE_SELECTED_DOCUMENTS':
                storeActions.setPageSelectedDocuments(action.payload.page as any, action.payload.documents);
                break;
            case 'ADD_PAGE_SELECTED_DOCUMENT':
                storeActions.addPageSelectedDocument(action.payload.page as any, action.payload.document);
                break;
            case 'REMOVE_PAGE_SELECTED_DOCUMENT':
                storeActions.removePageSelectedDocument(action.payload.page as any, action.payload.fileId);
                break;
            case 'CLEAR_PAGE_SELECTED_DOCUMENTS':
                storeActions.clearPageSelectedDocuments(action.payload.page as any);
                break;
            case 'UPDATE_WORK_CONTEXT':
                storeActions.updateWorkContext(action.payload);
                break;
            case 'SAVE_PAGE_STATE':
                storeActions.savePageState(action.payload.page as any, action.payload.state);
                break;
            case 'RESTORE_PAGE_STATE':
                storeActions.restorePageState(action.payload.page as any);
                break;
            case 'SET_CHAT_SESSION':
                storeActions.setChatSession(action.payload);
                break;
            case 'ADD_CHAT_MESSAGE':
                storeActions.addChatMessage(action.payload);
                break;
            case 'CLEAR_CHAT_HISTORY':
                storeActions.clearChatHistory();
                break;
            case 'SET_LOADING':
                storeActions.setLoading(action.payload);
                break;
            case 'SET_ERROR':
                storeActions.setError(action.payload);
                break;
            case 'ADD_NOTIFICATION':
                storeActions.addNotification(action.payload.type, action.payload.message);
                break;
            case 'REMOVE_NOTIFICATION':
                storeActions.removeNotification(action.payload);
                break;
            case 'UPDATE_USER_ACTIVITY':
                storeActions.updateUserActivity(action.payload);
                break;
            case 'INCREMENT_ACTIVITY_COUNT':
                storeActions.incrementActivityCount(action.payload.type);
                break;
            case 'RESET_STATE':
                storeActions.resetState();
                break;
            default:
                break;
        }
    }, [storeActions]);

    // navigateWithContext는 기존 API 호환성을 위해 유지하되, 스토어 기반으로 상태만 업데이트
    const navigateWithContext = React.useCallback((
        to: SourcePageType,
        preserveState?: any,
        options?: { ragMode?: boolean; selectedAgent?: AgentType; selectedAgentChain?: string }
    ) => {
        const normalizeSelectedDocs = (docs: any[]): any[] => {
            if (!Array.isArray(docs)) return [];
            return docs
                .filter(Boolean)
                .map((doc: any) => {
                    const fileId = doc?.fileId ?? doc?.id;
                    const fileName = doc?.fileName ?? doc?.file_name ?? doc?.physicalName ?? doc?.name;
                    const originalName = doc?.originalName ?? doc?.title ?? fileName;
                    return {
                        ...doc,
                        fileId,
                        fileName,
                        originalName,
                    };
                });
        };

        // 0) (search/my-knowledge 등) 현재 페이지에서 선택된 문서를 agent-chat/chat로 이동 시 함께 전달
        // - useSelectedDocuments()는 workContext.sourcePageType 기반으로 pageStates.*.selectedDocuments를 보므로
        //   이동 대상 페이지의 selectedDocuments를 미리 채워줘야 "선택된 문서가 없습니다" 상태가 되지 않음
        const from = state.workContext.sourcePageType;
        const fromKey =
            from === 'search' ? 'search' :
                from === 'my-knowledge' ? 'myKnowledge' :
                    from === 'agent-chat' ? 'agentChat' : 'chat';
        const destKey = to === 'agent-chat' ? 'agentChat' : (to === 'chat' ? 'chat' : null);

        // 우선순위:
        // 1) preserveState.selectedDocsSnapshot(명시 전달)
        // 2) 현재 페이지 선택 문서(pageStates[fromKey].selectedDocuments) - 우선순위 상향
        // 3) 통합 선택 문서(state.selectedDocuments)
        const snapshotFromPreserve = (preserveState && Array.isArray(preserveState.selectedDocsSnapshot))
            ? preserveState.selectedDocsSnapshot
            : null;
        const snapshotFromCurrent = (state.pageStates as any)?.[fromKey]?.selectedDocuments || [];
        const snapshotFromUnified = (state.selectedDocuments || []);
        
        // 문서 전달 로직 개선: preserveState > 현재 페이지 > 통합 선택
        const shouldCarryDocs = Boolean(destKey) &&
            (Boolean(snapshotFromPreserve?.length) || Boolean(snapshotFromCurrent?.length) || Boolean(snapshotFromUnified?.length));

        if (destKey && shouldCarryDocs) {
            // 우선순위대로 선택: preserveState > 현재 페이지 > 통합
            const docsToCarry = (snapshotFromPreserve?.length 
                ? snapshotFromPreserve 
                : (snapshotFromCurrent?.length ? snapshotFromCurrent : snapshotFromUnified)) as any;

            const normalizedDocsToCarry = normalizeSelectedDocs(docsToCarry);
            
            // 대상 페이지에 문서 설정
            storeActions.setPageSelectedDocuments(destKey as any, normalizedDocsToCarry);
            
            // 통합 선택 문서도 동기화 (UI 일관성 유지)
            if (normalizedDocsToCarry?.length) {
                storeActions.setSelectedDocuments(normalizedDocsToCarry);
            }
        }

        // 1) workContext 업데이트
        storeActions.updateWorkContext({
            sourcePageType: to,
            sourcePageState: preserveState,
            ragMode: options?.ragMode ?? state.workContext.ragMode,
            selectedAgent: options?.selectedAgent ?? state.workContext.selectedAgent,
            selectedAgentChain: options?.selectedAgentChain ?? state.workContext.selectedAgentChain,
            isChainMode: !!options?.selectedAgentChain,
            mode: options?.selectedAgentChain ? 'chain' : (state.workContext.mode || 'single'),
        });

        // 2) 실제 라우팅
        const navigate = getGlobalNavigate();
        const routeMap: Record<SourcePageType, string> = {
            'my-knowledge': '/user/my-knowledge',
            'search': '/user/search',
            'chat': '/user/chat',
            'agent-chat': '/user/agent-chat',
            'dashboard': '/user'
        };
        let targetRoute = routeMap[to];
        if (!targetRoute) return false;
        if ((to === 'chat' || to === 'agent-chat') && preserveState?.sessionId) {
            targetRoute = `${targetRoute}?session=${preserveState.sessionId}`;
        }
        if (navigate) {
            navigate(targetRoute);
            return true;
        }
        if (typeof window !== 'undefined') {
            window.location.href = targetRoute;
            return true;
        }
        return false;
    }, [state.pageStates, state.selectedDocuments, state.workContext, storeActions]);

    const actions = useMemo(() => ({
        setUser: storeActions.setUser,
        setSelectedContainers: storeActions.setSelectedContainers,
        addSelectedContainer: storeActions.addSelectedContainer,
        removeSelectedContainer: storeActions.removeSelectedContainer,
        setSelectedDocuments: storeActions.setSelectedDocuments,
        addSelectedDocument: (document: Document) => storeActions.setSelectedDocuments([...(state.selectedDocuments || []), document]),
        removeSelectedDocument: (fileId: string) =>
            storeActions.setSelectedDocuments((state.selectedDocuments || []).filter((d: Document) => d.fileId !== fileId)),
        clearSelectedDocuments: () => storeActions.setSelectedDocuments([]),
        setPageSelectedDocuments: storeActions.setPageSelectedDocuments as any,
        addPageSelectedDocument: storeActions.addPageSelectedDocument as any,
        removePageSelectedDocument: storeActions.removePageSelectedDocument as any,
        clearPageSelectedDocuments: storeActions.clearPageSelectedDocuments as any,
        toggleDocumentSelection: (document: Document) => {
            const currentPage = state.workContext.sourcePageType;
            const targetPage =
                currentPage === 'search' ? 'search' :
                    currentPage === 'my-knowledge' ? 'myKnowledge' :
                        currentPage === 'agent-chat' ? 'agentChat' : 'chat';
            const selected = (state.pageStates as any)[targetPage]?.selectedDocuments || [];
            const isSelected = selected.some((d: Document) => d.fileId === document.fileId);
            if (isSelected) storeActions.removePageSelectedDocument(targetPage as any, document.fileId);
            else storeActions.addPageSelectedDocument(targetPage as any, document);
        },
        updateWorkContext: storeActions.updateWorkContext,
        navigateWithContext,
        setChatSession: storeActions.setChatSession,
        addChatMessage: storeActions.addChatMessage,
        clearChatHistory: storeActions.clearChatHistory,
        savePageState: (page: any, next: any) => storeActions.savePageState(page, next),
        restorePageState: (page: any) => storeActions.restorePageState(page),
        setLoading: storeActions.setLoading,
        setError: storeActions.setError,
        addNotification: storeActions.addNotification,
        removeNotification: storeActions.removeNotification,
        startWorkflow: (_step: string, _data?: any) => { /* noop */ },
        updateWorkflowStep: (_step: string, _data?: any) => { /* noop */ },
        completeWorkflow: (_data?: any) => { /* noop */ },
        cancelWorkflow: () => { /* noop */ },
        updateUserActivity: storeActions.updateUserActivity,
        incrementActivityCount: storeActions.incrementActivityCount,
        resetState: storeActions.resetState,
        clearAllDocumentsOnLogout: storeActions.clearAllDocumentsOnLogout,
    }), [navigateWithContext, state.pageStates, state.selectedDocuments, state.workContext, storeActions]);

    return { state, dispatch, actions };
};

// 개별 기능별 커스텀 훅들
export const useSelectedDocuments = (pageOverride?: 'search' | 'myKnowledge' | 'chat' | 'agentChat') => {
    const { state, actions } = useGlobalApp();

    // 현재 페이지에 따라 적절한 선택된 문서들을 반환 (옵션: pageOverride로 강제)
    const currentPage = state.workContext.sourcePageType;
    const targetPage =
        pageOverride
            ? pageOverride
            : (currentPage === 'search'
                ? 'search'
                : currentPage === 'my-knowledge'
                    ? 'myKnowledge'
                    : currentPage === 'agent-chat'
                        ? 'agentChat'
                        : 'chat');

    const selectedDocuments = ((state.pageStates as any)[targetPage]?.selectedDocuments || []) as Document[];

    return {
        selectedDocuments,
        setSelectedDocuments: (documents: Document[]) => {
            actions.setPageSelectedDocuments(targetPage, documents);
        },
        addSelectedDocument: (document: Document) => {
            actions.addPageSelectedDocument(targetPage, document);
        },
        removeSelectedDocument: (fileId: string) => {
            actions.removePageSelectedDocument(targetPage, fileId);
        },
        clearSelectedDocuments: () => {
            actions.clearPageSelectedDocuments(targetPage);
        },
        toggleDocumentSelection: (document: Document) => {
            const isSelected = selectedDocuments.some((doc: Document) => doc.fileId === document.fileId);
            if (isSelected) actions.removePageSelectedDocument(targetPage, document.fileId);
            else actions.addPageSelectedDocument(targetPage, document);
        },
        hasSelectedDocuments: (selectedDocuments?.length || 0) > 0,
        selectedCount: selectedDocuments?.length || 0
    };
};

// ✅ 전역(통합) 선택 문서 훅: 지식검색/지식컨테이너 등에서 선택된 문서를 한 곳에서 관리
// - 팝업(SelectedDocumentsDisplay)은 이 훅을 사용해야 "통합 선택" UX가 됨
export const useUnifiedSelectedDocuments = () => {
    const { state, actions } = useGlobalApp();
    const selectedDocuments = state.selectedDocuments || [];

    const removeEverywhere = (fileId: string) => {
        // 1) 전역 선택에서 제거
        actions.setSelectedDocuments((selectedDocuments || []).filter((d: any) => d?.fileId !== fileId));
        // 2) 페이지별 선택에서도 제거 (체크박스/버튼 상태 동기화)
        const pages: Array<'search' | 'myKnowledge' | 'chat' | 'agentChat'> = ['search', 'myKnowledge', 'chat', 'agentChat'];
        pages.forEach((p) => actions.removePageSelectedDocument(p as any, fileId));
    };

    const clearEverywhere = () => {
        actions.setSelectedDocuments([]);
        const pages: Array<'search' | 'myKnowledge' | 'chat' | 'agentChat'> = ['search', 'myKnowledge', 'chat', 'agentChat'];
        pages.forEach((p) => actions.clearPageSelectedDocuments(p as any));
    };

    return {
        selectedDocuments,
        setSelectedDocuments: (docs: any[]) => actions.setSelectedDocuments(docs as any),
        addSelectedDocument: (doc: any) => {
            const exists = (selectedDocuments || []).some((d: any) => d?.fileId === doc?.fileId);
            if (exists) return;
            actions.setSelectedDocuments([...(selectedDocuments || []), doc]);
        },
        removeSelectedDocument: removeEverywhere,
        clearSelectedDocuments: clearEverywhere,
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

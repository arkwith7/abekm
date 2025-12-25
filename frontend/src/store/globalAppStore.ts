import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type {
  ChatMessage,
  ChatSession,
  Document,
  GlobalAppState,
  KnowledgeContainer,
  SourcePageType,
  UserActivity,
  UserInfo,
} from '../contexts/types';

import { initialGlobalState } from '../contexts/globalAppReducer';

// CRA/tsc strict 환경에서 set/get/state 콜백의 implicit any를 방지하기 위한 최소 타입
type SetState<T> = (partial: Partial<T> | ((state: T) => Partial<T>), replace?: boolean) => void;
type GetState<T> = () => T;

type PageKey =
  | 'search'
  | 'myKnowledge'
  | 'chat'
  | 'agentChat'
  | 'chatHistory'
  | 'containerExplorer';

type PageKeyWithSelectedDocs = 'search' | 'myKnowledge' | 'chat' | 'agentChat';

type PersistedState = Pick<GlobalAppState, 'selectedContainers' | 'selectedDocuments' | 'workContext' | 'pageStates'>;

function isPlainObject(value: unknown): value is Record<string, any> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function deepMerge<T>(base: T, patch: any): T {
  if (!isPlainObject(base) || !isPlainObject(patch)) {
    return (patch ?? base) as T;
  }
  const out: Record<string, any> = { ...(base as any) };
  for (const k of Object.keys(patch)) {
    const next = patch[k];
    const prev = (base as any)[k];
    if (isPlainObject(prev) && isPlainObject(next)) out[k] = deepMerge(prev, next);
    else out[k] = next;
  }
  return out as T;
}

export type GlobalAppActions = {
  // 사용자/권한
  setUser: (user: UserInfo | null) => void;

  // 컨테이너/문서 선택
  setSelectedContainers: (containers: KnowledgeContainer[]) => void;
  addSelectedContainer: (container: KnowledgeContainer) => void;
  removeSelectedContainer: (containerId: string) => void;

  setSelectedDocuments: (documents: Document[]) => void;
  setPageSelectedDocuments: (page: PageKeyWithSelectedDocs, documents: Document[]) => void;
  addPageSelectedDocument: (page: PageKeyWithSelectedDocs, document: Document) => void;
  removePageSelectedDocument: (page: PageKeyWithSelectedDocs, fileId: string) => void;
  clearPageSelectedDocuments: (page: PageKeyWithSelectedDocs) => void;

  // 페이지 상태 저장/복원
  savePageState: (page: PageKey, state: any) => void;
  restorePageState: (page: PageKey) => any;

  // 작업 컨텍스트/네비게이션
  updateWorkContext: (context: Partial<GlobalAppState['workContext']>) => void;
  setSourcePageType: (to: SourcePageType) => void;

  // 채팅
  setChatSession: (session: ChatSession | null) => void;
  addChatMessage: (message: ChatMessage) => void;
  clearChatHistory: () => void;

  // UI
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addNotification: (type: 'success' | 'error' | 'warning' | 'info', message: string) => void;
  removeNotification: (id: string) => void;

  // 활동/워크플로우
  updateUserActivity: (activity: Partial<UserActivity>) => void;
  incrementActivityCount: (type: 'search' | 'upload' | 'chat' | 'view') => void;

  // 세션/로그아웃 정리
  clearAllDocumentsOnLogout: () => void;
  resetState: () => void;
};

export type GlobalAppStore = GlobalAppState & { actions: GlobalAppActions };

const STORAGE_KEY = 'ABEKM-app-state';

export const useGlobalAppStore = create<GlobalAppStore>()(
  persist(
    (set: SetState<GlobalAppStore>, get: GetState<GlobalAppStore>) => ({
      ...initialGlobalState,
      actions: {
        setUser: (user: UserInfo | null) => set({ user }),

        setSelectedContainers: (containers: KnowledgeContainer[]) => set({ selectedContainers: containers }),
        addSelectedContainer: (container: KnowledgeContainer) =>
          set((state: GlobalAppStore) => {
            const exists = state.selectedContainers.some((c: KnowledgeContainer) => c.containerId === container.containerId);
            if (exists) return state;
            return { selectedContainers: [...state.selectedContainers, container] } as Partial<GlobalAppStore>;
          }),
        removeSelectedContainer: (containerId: string) =>
          set((state: GlobalAppStore) => ({
            selectedContainers: state.selectedContainers.filter((c: KnowledgeContainer) => c.containerId !== containerId),
          })),

        setSelectedDocuments: (documents: Document[]) => set({ selectedDocuments: documents }),
        setPageSelectedDocuments: (page: PageKeyWithSelectedDocs, documents: Document[]) =>
          set((state: GlobalAppStore) => ({
            pageStates: {
              ...state.pageStates,
              [page]: {
                ...(state.pageStates as any)[page],
                selectedDocuments: documents,
              },
            } as any,
          })),
        addPageSelectedDocument: (page: PageKeyWithSelectedDocs, document: Document) =>
          set((state: GlobalAppStore) => {
            const current = ((state.pageStates as any)[page]?.selectedDocuments || []) as Document[];
            const exists = current.some((d: Document) => d.fileId === document.fileId);
            if (exists) return state;
            return {
              pageStates: {
                ...state.pageStates,
                [page]: {
                  ...(state.pageStates as any)[page],
                  selectedDocuments: [...current, document],
                },
              } as any,
            } as Partial<GlobalAppStore>;
          }),
        removePageSelectedDocument: (page: PageKeyWithSelectedDocs, fileId: string) =>
          set((state: GlobalAppStore) => {
            const current = ((state.pageStates as any)[page]?.selectedDocuments || []) as Document[];
            return {
              pageStates: {
                ...state.pageStates,
                [page]: {
                  ...(state.pageStates as any)[page],
                  selectedDocuments: current.filter((d) => d.fileId !== fileId),
                },
              } as any,
            };
          }),
        clearPageSelectedDocuments: (page: PageKeyWithSelectedDocs) =>
          set((state: GlobalAppStore) => ({
            pageStates: {
              ...state.pageStates,
              [page]: {
                ...(state.pageStates as any)[page],
                selectedDocuments: [],
              },
            } as any,
          })),

        savePageState: (page: PageKey, pageStatePatch: any) =>
          set((state: GlobalAppStore) => ({
            pageStates: {
              ...state.pageStates,
              [page]: {
                ...(state.pageStates as any)[page],
                ...(pageStatePatch || {}),
              },
            } as any,
          })),

        restorePageState: (page: PageKey) => {
          const saved = (get().pageStates as any)[page];
          // workContext.sourcePageState 용도로만 동기화 (페이지는 saved를 직접 읽는 패턴이 더 안전함)
          set((state: GlobalAppStore) => ({
            workContext: {
              ...state.workContext,
              sourcePageState: saved,
            },
          }));
          return saved;
        },

        updateWorkContext: (context: Partial<GlobalAppState['workContext']>) =>
          set((state: GlobalAppStore) => ({
            workContext: {
              ...state.workContext,
              ...(context || {}),
            },
          })),

        setSourcePageType: (to: SourcePageType) =>
          set((state: GlobalAppStore) => ({
            workContext: {
              ...state.workContext,
              sourcePageType: to,
            },
          })),

        setChatSession: (session: ChatSession | null) =>
          set((state: GlobalAppStore) => ({
            currentChatSession: session,
            chatHistory: session === null ? [] : state.chatHistory,
          })),
        addChatMessage: (message: ChatMessage) =>
          set((state: GlobalAppStore) => ({
            chatHistory: [...state.chatHistory, message],
          })),
        clearChatHistory: () => set({ chatHistory: [] }),

        setLoading: (loading: boolean) =>
          set((state: GlobalAppStore) => ({ ui: { ...state.ui, isLoading: loading } })),
        setError: (error: string | null) => set((state: GlobalAppStore) => ({ ui: { ...state.ui, error } })),
        addNotification: (type: 'success' | 'error' | 'warning' | 'info', message: string) =>
          set((state: GlobalAppStore) => ({
            ui: {
              ...state.ui,
              notifications: [
                ...state.ui.notifications,
                {
                  id: Date.now().toString() + Math.random().toString(36).slice(2, 9),
                  type,
                  message,
                  timestamp: new Date().toISOString(),
                },
              ],
            },
          })),
        removeNotification: (id: string) =>
          set((state: GlobalAppStore) => ({
            ui: {
              ...state.ui,
              notifications: state.ui.notifications.filter((n: any) => n.id !== id),
            },
          })),

        updateUserActivity: (activity: Partial<UserActivity>) =>
          set((state: GlobalAppStore) => ({
            userActivity: {
              ...state.userActivity,
              ...(activity || {}),
              lastActivity: new Date().toISOString(),
            },
          })),

        incrementActivityCount: (type: 'search' | 'upload' | 'chat' | 'view') =>
          set((state: GlobalAppStore) => {
            const key = `${type}Count` as keyof UserActivity;
            const currentCount = (state.userActivity[key] as unknown as number) || 0;
            return {
              userActivity: {
                ...state.userActivity,
                [key]: currentCount + 1,
                lastActivity: new Date().toISOString(),
              } as UserActivity,
            };
          }),

        clearAllDocumentsOnLogout: () => {
          // 선택 문서/페이지 상태 정리 + persisted state도 정리
          set((state: GlobalAppStore) => ({
            selectedDocuments: [],
            selectedContainers: [],
            currentChatSession: null,
            chatHistory: [],
            pageStates: {
              ...state.pageStates,
              search: { ...state.pageStates.search, selectedDocuments: [] },
              myKnowledge: { ...state.pageStates.myKnowledge, selectedDocuments: [] },
              chat: { ...state.pageStates.chat, selectedDocuments: [] },
              agentChat: { ...state.pageStates.agentChat, selectedDocuments: [] },
            } as any,
          }));
          try {
            localStorage.removeItem(STORAGE_KEY);
            // 기존 키들(레거시)도 함께 제거
            localStorage.removeItem('pageStates');
            localStorage.removeItem('ABEKM_chat_state');
            localStorage.removeItem('ABEKM_agent_chat_state');
          } catch {
            // ignore
          }
        },

        resetState: () => {
          const user = get().user;
          set({ ...initialGlobalState, user } as GlobalAppStore);
        },
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state: GlobalAppStore): PersistedState => ({
        selectedContainers: state.selectedContainers,
        selectedDocuments: state.selectedDocuments,
        workContext: {
          ...state.workContext,
          // 화면 복원 용도에서는 너무 큰 state/히스토리를 피함
          sourcePageState: null,
          navigationHistory: [],
        },
        pageStates: {
          // 검색: UI 상태는 저장, 결과는 메모리에만 유지(새로고침 시 재조회)
          search: {
            ...state.pageStates.search,
            results: [],
          },
          // 내 지식: UI 상태는 저장, containers/documents는 메모리에만 유지
          myKnowledge: {
            ...state.pageStates.myKnowledge,
            containers: [],
            documents: [],
          },
          // 채팅: 세션/에이전트 목록은 메모리, 선택 문서/세션 id 정도만 유지
          chat: {
            ...state.pageStates.chat,
            sessions: [],
            availableAgents: [],
            availableChains: [],
          },
          agentChat: {
            ...state.pageStates.agentChat,
          },
          // 대화 이력: 목록은 메모리, cursor/hasMore 등만 유지
          chatHistory: {
            ...state.pageStates.chatHistory,
            sessions: [],
          },
          // 컨테이너 탐색: 트리/문서 목록은 메모리, 확장/선택 상태만 유지
          containerExplorer: {
            ...state.pageStates.containerExplorer,
            tree: [],
            documents: [],
          },
        },
      }),
      merge: (persistedState: unknown, currentState: unknown) => deepMerge(currentState as any, persistedState as any),
      version: 1,
    }
  )
);



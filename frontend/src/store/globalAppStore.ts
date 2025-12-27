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

function getPath(obj: any, path: string): any {
  return path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), obj);
}

function setPath(obj: any, path: string, value: any): void {
  const parts = path.split('.');
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i];
    if (!cur[key] || typeof cur[key] !== 'object') cur[key] = {};
    cur = cur[key];
  }
  cur[parts[parts.length - 1]] = value;
}

function mergePersistedState(currentState: any, persistedState: any): any {
  // 기본은 persisted → current 로 deep merge 하되,
  // "persisted가 빈 배열로 덮어써서 런타임 선택 문서가 사라지는" 케이스는 방지한다.
  const merged = deepMerge(currentState, persistedState);

  const protectedArrayPaths = [
    'selectedDocuments',
    'pageStates.search.selectedDocuments',
    'pageStates.myKnowledge.selectedDocuments',
    'pageStates.chat.selectedDocuments',
    'pageStates.agentChat.selectedDocuments',
  ];

  for (const p of protectedArrayPaths) {
    const curVal = getPath(currentState, p);
    const persistedVal = getPath(persistedState, p);

    // persisted가 비어있음([]/null/undefined)인데 current가 이미 선택 문서를 갖고 있으면 current를 보존
    // (구버전 persisted 스키마에서 null이 들어온 경우도 방어)
    const persistedIsEmptyArray = Array.isArray(persistedVal) && persistedVal.length === 0;
    const persistedIsNil = persistedVal == null;
    if (Array.isArray(curVal) && curVal.length > 0 && (persistedIsEmptyArray || persistedIsNil)) {
      setPath(merged, p, curVal);
    }
  }

  return merged;
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
          set((state: GlobalAppStore) => {
            // ✅ 로그아웃 직후(localStorage.clear 이후) 언마운트 flush/save가
            //    이전 선택 문서를 다시 저장(persist)하는 것을 방지
            try {
              const hasToken = Boolean(
                localStorage.getItem('ABEKM_token') ||
                localStorage.getItem('abkms_token') ||
                localStorage.getItem('access_token') ||
                localStorage.getItem('token')
              );
              if (!hasToken) return state;
            } catch {
              // ignore (SSR/blocked storage)
            }

            return {
              pageStates: {
                ...state.pageStates,
                [page]: {
                  ...(state.pageStates as any)[page],
                  ...(pageStatePatch || {}),
                },
              } as any,
            };
          }),

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
          // ✅ 로그아웃 후 재로그인 시 "항상 초기 상태"로 시작해야 하므로
          // - 선택 문서뿐 아니라 검색/필터/페이지 등 모든 UI 상태를 초기화
          // - actions는 유지되어야 하므로 state.actions는 건드리지 않음
          set(() => ({
            ...initialGlobalState,
          } as any));
          try {
            localStorage.removeItem(STORAGE_KEY);
            // 기존 키들(레거시)도 함께 제거
            localStorage.removeItem('pageStates');
            localStorage.removeItem('ABEKM_chat_state');
            localStorage.removeItem('ABEKM_agent_chat_state');
            localStorage.removeItem('bedrock_conversations');
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
      merge: (persistedState: unknown, currentState: unknown) => mergePersistedState(currentState as any, persistedState as any),
      version: 1,
    }
  )
);



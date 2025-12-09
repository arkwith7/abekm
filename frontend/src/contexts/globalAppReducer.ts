/**
 * 글로벌 앱 상태 Reducer
 */
import { Document as DocType, GlobalAppAction, GlobalAppState, SourcePageType } from './types';

const mapSourcePageToStateKey = (
  source?: SourcePageType
): 'search' | 'myKnowledge' | 'chat' | 'agentChat' => {
  switch (source) {
    case 'search':
      return 'search';
    case 'my-knowledge':
      return 'myKnowledge';
    case 'agent-chat':
      return 'agentChat';
    default:
      return 'chat';
  }
};

// 초기 상태
export const initialGlobalState: GlobalAppState = {
  user: null,
  selectedContainers: [],
  selectedDocuments: [], // 전역 선택 문서 (더 이상 사용하지 않음, 호환성을 위해 유지)
  workContext: {
    sourcePageType: 'dashboard',
    sourcePageState: null,
    ragMode: false,
    selectedAgent: null,
    selectedAgentChain: null,
    isChainMode: false,
    mode: 'single',
    selectedAgents: [],
    navigationHistory: []
  },
  currentChatSession: null,
  chatHistory: [],
  // 🆕 워크플로우 및 활동 상태 추가
  workflow: {
    currentStep: 'dashboard',
    stepHistory: [],
    selectedDocuments: [],
    isActive: false
  },
  userActivity: {
    searchCount: 0,
    uploadCount: 0,
    chatCount: 0,
    viewCount: 0,
    lastActivity: new Date().toISOString(),
    recentSearches: [],
    recentDocuments: []
  },
  pageStates: {
    search: {
      query: '',
      filters: {},
      results: [],
      selectedResults: [],
      viewMode: 'list',
      currentPage: 1,
      selectedDocuments: [], // 검색 페이지 전용 선택 문서
    },
    myKnowledge: {
      selectedContainer: null,
      expandedContainers: [],
      searchTerm: '',
      filterStatus: 'all',
      sortBy: 'date',
      sortOrder: 'desc',
      selectedDocuments: [],
      currentPage: 1,
      viewMode: 'list',
      containers: [],
      documents: [],
    },
    chat: {
      sessions: [],
      currentSessionId: null,
      isLoading: false,
      error: null,
      availableAgents: [],
      availableChains: [],
      selectedDocuments: [],
    },
    agentChat: {
      selectedDocuments: [],
      currentSessionId: null,
    },
    chatHistory: {
      sessions: [],
      cursor: null,
      hasMore: false,
      scrollPosition: 0,
    },
    containerExplorer: {
      tree: [],
      expanded: [],
      selectedId: null,
      documents: [],
      lastLoadTime: undefined,
    },
  },
  ui: {
    isLoading: false,
    error: null,
    notifications: [],
  },
};

// Reducer 함수
export const globalAppReducer = (state: GlobalAppState, action: GlobalAppAction): GlobalAppState => {
  switch (action.type) {
    case 'SET_USER':
      return {
        ...state,
        user: action.payload
      };

    case 'SET_SELECTED_CONTAINERS':
      return {
        ...state,
        selectedContainers: action.payload
      };

    case 'ADD_SELECTED_CONTAINER':
      const existingContainer = state.selectedContainers.find(
        container => container.containerId === action.payload.containerId
      );
      if (existingContainer) {
        return state; // 이미 존재하면 추가하지 않음
      }
      return {
        ...state,
        selectedContainers: [...state.selectedContainers, action.payload]
      };

    case 'REMOVE_SELECTED_CONTAINER':
      return {
        ...state,
        selectedContainers: state.selectedContainers.filter(
          container => container.containerId !== action.payload
        )
      };

    case 'SET_SELECTED_DOCUMENTS':
      return {
        ...state,
        selectedDocuments: action.payload
      };

    case 'ADD_SELECTED_DOCUMENT':
      const existingDocument = state.selectedDocuments.find(
        doc => doc.fileId === action.payload.fileId
      );
      if (existingDocument) {
        return state; // 이미 존재하면 추가하지 않음
      }
      return {
        ...state,
        selectedDocuments: [...state.selectedDocuments, action.payload]
      };

    case 'REMOVE_SELECTED_DOCUMENT':
      console.log('🔧 REMOVE_SELECTED_DOCUMENT 리듀서 실행됨');
      console.log('🗑️ 삭제할 fileId:', action.payload);

      // 현재 페이지 판단하여 해당 페이지의 선택된 문서에서 제거
      const currentPageForRemove = state.workContext.sourcePageType;
      const targetPageForRemove = mapSourcePageToStateKey(currentPageForRemove);

      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [targetPageForRemove]: {
            ...state.pageStates[targetPageForRemove],
            selectedDocuments: (state.pageStates[targetPageForRemove]?.selectedDocuments || []).filter(
              (doc: DocType) => doc.fileId !== action.payload
            )
          }
        },
        // 전역 selectedDocuments도 제거 (호환성 유지)
        selectedDocuments: state.selectedDocuments.filter(
          (doc: DocType) => doc.fileId !== action.payload
        )
      };

    case 'CLEAR_SELECTED_DOCUMENTS':
      console.log('� CLEAR_SELECTED_DOCUMENTS 리듀서 실행됨');

      // 현재 페이지 판단하여 해당 페이지의 선택된 문서 클리어
      const currentPageForClear = state.workContext.sourcePageType;
      const targetPageForClear = mapSourcePageToStateKey(currentPageForClear);

      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [targetPageForClear]: {
            ...state.pageStates[targetPageForClear],
            selectedDocuments: []
          }
        },
        // 전역 selectedDocuments도 클리어 (호환성 유지)
        selectedDocuments: []
      };

    case 'TOGGLE_DOCUMENT_SELECTION':
      console.log('🔧 TOGGLE_DOCUMENT_SELECTION 리듀서 실행됨');
      console.log('📄 토글할 문서:', action.payload);

      // 현재 페이지 판단
      const currentPageForToggle = state.workContext.sourcePageType;
      const targetPageForToggle = mapSourcePageToStateKey(currentPageForToggle);

      const currentPageDocs = state.pageStates[targetPageForToggle]?.selectedDocuments || [];
      const isSelected = currentPageDocs.some((doc: DocType) => doc.fileId === action.payload.fileId);

      if (isSelected) {
        // 선택 해제
        return {
          ...state,
          pageStates: {
            ...state.pageStates,
            [targetPageForToggle]: {
              ...state.pageStates[targetPageForToggle],
              selectedDocuments: currentPageDocs.filter((doc: DocType) => doc.fileId !== action.payload.fileId)
            }
          },
          selectedDocuments: state.selectedDocuments.filter((doc: DocType) => doc.fileId !== action.payload.fileId)
        };
      } else {
        // 선택 추가
        return {
          ...state,
          pageStates: {
            ...state.pageStates,
            [targetPageForToggle]: {
              ...state.pageStates[targetPageForToggle],
              selectedDocuments: [...currentPageDocs, action.payload]
            }
          },
          selectedDocuments: [...state.selectedDocuments, action.payload]
        };
      }

    // 페이지별 선택된 문서 관리
    case 'SET_PAGE_SELECTED_DOCUMENTS':
      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [action.payload.page]: {
            ...state.pageStates[action.payload.page],
            selectedDocuments: action.payload.documents
          }
        }
      };

    case 'ADD_PAGE_SELECTED_DOCUMENT':
      const existingPageDocument = (state.pageStates[action.payload.page]?.selectedDocuments || []).find(
        (doc: DocType) => doc.fileId === action.payload.document.fileId
      );
      if (existingPageDocument) {
        return state; // 이미 존재하면 추가하지 않음
      }
      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [action.payload.page]: {
            ...state.pageStates[action.payload.page],
            selectedDocuments: [...(state.pageStates[action.payload.page]?.selectedDocuments || []), action.payload.document]
          }
        }
      };

    case 'REMOVE_PAGE_SELECTED_DOCUMENT':
      console.log('🔧 REMOVE_PAGE_SELECTED_DOCUMENT 리듀서 실행됨');
      console.log('🗑️ 페이지:', action.payload.page, '삭제할 fileId:', action.payload.fileId);
      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [action.payload.page]: {
            ...state.pageStates[action.payload.page],
            selectedDocuments: (state.pageStates[action.payload.page]?.selectedDocuments || []).filter(
              (doc: DocType) => doc.fileId !== action.payload.fileId
            )
          }
        }
      };

    case 'CLEAR_PAGE_SELECTED_DOCUMENTS':
      console.log('🔧 CLEAR_PAGE_SELECTED_DOCUMENTS 리듀서 실행됨');
      console.log('🗑️ 페이지:', action.payload.page);
      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [action.payload.page]: {
            ...state.pageStates[action.payload.page],
            selectedDocuments: []
          }
        }
      };

    case 'UPDATE_WORK_CONTEXT':
      // 네비게이션 히스토리 추가
      const newNavigationHistory = [...state.workContext.navigationHistory];
      if (action.payload.sourcePageType && action.payload.sourcePageType !== state.workContext.sourcePageType) {
        newNavigationHistory.push({
          from: state.workContext.sourcePageType,
          to: action.payload.sourcePageType,
          timestamp: new Date().toISOString(),
          preservedState: state.workContext.sourcePageState
        });

        // 히스토리는 최대 10개까지만 유지
        if (newNavigationHistory.length > 10) {
          newNavigationHistory.shift();
        }
      }

      return {
        ...state,
        workContext: {
          ...state.workContext,
          ...action.payload,
          navigationHistory: newNavigationHistory
        }
      };

    case 'SET_CHAT_SESSION':
      return {
        ...state,
        currentChatSession: action.payload,
        // 새 세션일 때는 채팅 히스토리 초기화
        chatHistory: action.payload === null ? [] : state.chatHistory
      };

    case 'ADD_CHAT_MESSAGE':
      return {
        ...state,
        chatHistory: [...state.chatHistory, action.payload]
      };

    case 'CLEAR_CHAT_HISTORY':
      return {
        ...state,
        chatHistory: []
      };

    case 'SAVE_PAGE_STATE':
      return {
        ...state,
        pageStates: {
          ...state.pageStates,
          [action.payload.page]: {
            // 기존 페이지 상태 유지 (특히 selectedDocuments 보존)
            ...state.pageStates[action.payload.page],
            // 새로 전달된 필드만 업데이트
            ...action.payload.state
          }
        }
      };

    case 'RESTORE_PAGE_STATE':
      // 복원할 상태가 있는지 확인하고 반환
      const savedState = state.pageStates[action.payload.page];
      return {
        ...state,
        workContext: {
          ...state.workContext,
          sourcePageState: savedState
        }
      };

    case 'SET_LOADING':
      return {
        ...state,
        ui: {
          ...state.ui,
          isLoading: action.payload
        }
      };

    case 'SET_ERROR':
      return {
        ...state,
        ui: {
          ...state.ui,
          error: action.payload
        }
      };

    case 'ADD_NOTIFICATION':
      const notification = {
        id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
        type: action.payload.type,
        message: action.payload.message,
        timestamp: new Date().toISOString()
      };
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: [...state.ui.notifications, notification]
        }
      };

    case 'REMOVE_NOTIFICATION':
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: state.ui.notifications.filter(
            notification => notification.id !== action.payload
          )
        }
      };

    case 'RESET_STATE':
      return {
        ...initialGlobalState,
        user: state.user // 사용자 정보는 유지
      };

    // 🆕 워크플로우 관련 액션들
    case 'START_WORKFLOW':
      return {
        ...state,
        workflow: {
          currentStep: action.payload.step as any,
          stepHistory: [{
            id: Date.now().toString(),
            name: action.payload.step,
            page: state.workContext.sourcePageType,
            timestamp: new Date().toISOString(),
            data: action.payload.data
          }],
          selectedDocuments: [],
          isActive: true,
          startTime: new Date().toISOString()
        }
      };

    case 'UPDATE_WORKFLOW_STEP':
      return {
        ...state,
        workflow: {
          ...state.workflow,
          currentStep: action.payload.step as any,
          stepHistory: [...state.workflow.stepHistory, {
            id: Date.now().toString(),
            name: action.payload.step,
            page: state.workContext.sourcePageType,
            timestamp: new Date().toISOString(),
            data: action.payload.data
          }]
        }
      };

    case 'COMPLETE_WORKFLOW':
      return {
        ...state,
        workflow: {
          ...state.workflow,
          currentStep: 'complete',
          isActive: false
        }
      };

    case 'CANCEL_WORKFLOW':
      return {
        ...state,
        workflow: {
          ...initialGlobalState.workflow,
          currentStep: 'dashboard'
        }
      };

    case 'UPDATE_USER_ACTIVITY':
      return {
        ...state,
        userActivity: {
          ...state.userActivity,
          ...action.payload,
          lastActivity: new Date().toISOString()
        }
      };

    case 'INCREMENT_ACTIVITY_COUNT':
      const currentCount = state.userActivity[`${action.payload.type}Count` as keyof typeof state.userActivity] as number;
      return {
        ...state,
        userActivity: {
          ...state.userActivity,
          [`${action.payload.type}Count`]: currentCount + 1,
          lastActivity: new Date().toISOString()
        }
      };

    default:
      return state;
  }
};

// 로컬 스토리지 관련 유틸리티 함수들
export const saveStateToLocalStorage = (state: GlobalAppState) => {
  try {
    // ⚠️ DB 데이터(containers, documents, results)는 저장하지 않음
    // UI 설정만 저장 (viewMode, selectedContainer, expandedContainers 등)
    const stateToSave = {
      selectedContainers: state.selectedContainers,
      selectedDocuments: state.selectedDocuments,
      workContext: state.workContext,
      pageStates: {
        search: {
          query: state.pageStates.search.query,
          filters: state.pageStates.search.filters,
          // results는 저장하지 않음 (DB 데이터)
          selectedResults: state.pageStates.search.selectedResults,
          viewMode: state.pageStates.search.viewMode,
          currentPage: state.pageStates.search.currentPage,
          selectedDocuments: state.pageStates.search.selectedDocuments,
        },
        myKnowledge: {
          selectedContainer: state.pageStates.myKnowledge.selectedContainer,
          expandedContainers: state.pageStates.myKnowledge.expandedContainers,
          searchTerm: state.pageStates.myKnowledge.searchTerm,
          filterStatus: state.pageStates.myKnowledge.filterStatus,
          sortBy: state.pageStates.myKnowledge.sortBy,
          sortOrder: state.pageStates.myKnowledge.sortOrder,
          selectedDocuments: state.pageStates.myKnowledge.selectedDocuments,
          currentPage: state.pageStates.myKnowledge.currentPage,
          viewMode: state.pageStates.myKnowledge.viewMode,
          // containers, documents는 저장하지 않음 (DB 데이터)
        },
        chat: state.pageStates.chat,
        agentChat: state.pageStates.agentChat,
        chatHistory: state.pageStates.chatHistory,
        containerExplorer: state.pageStates.containerExplorer,
      }
    };
    localStorage.setItem('ABEKM-app-state', JSON.stringify(stateToSave));
  } catch (error) {
    console.warn('상태를 로컬 스토리지에 저장할 수 없습니다:', error);
  }
};

export const loadStateFromLocalStorage = (): Partial<GlobalAppState> | null => {
  try {
    const savedState = localStorage.getItem('ABEKM-app-state');
    if (savedState) {
      return JSON.parse(savedState);
    }
  } catch (error) {
    console.warn('로컬 스토리지에서 상태를 불러올 수 없습니다:', error);
  }
  return null;
};

export const clearLocalStorageState = () => {
  try {
    localStorage.removeItem('ABEKM-app-state');
  } catch (error) {
    console.warn('로컬 스토리지 상태를 삭제할 수 없습니다:', error);
  }
};

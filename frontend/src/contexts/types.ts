/**
 * 글로벌 앱 상태 관리를 위한 타입 정의
 */

// 기본 엔티티 타입들
export interface UserInfo {
  id: string;
  empNo: string;
  name: string;
  department: string;
  role: 'USER' | 'MANAGER' | 'ADMIN';
  email?: string;
}

export interface KnowledgeContainer {
  containerId: string;
  containerName: string;
  description?: string;
  parentId?: string;
  level: number;
  hasChildren: boolean;
  documentCount: number;
  permissions: {
    canRead: boolean;
    canWrite: boolean;
    canDelete: boolean;
  };
}

export interface Document {
  fileId: string;
  fileName: string;
  originalName: string;
  fileSize: number;
  fileType: string;
  uploadDate: string;
  containerName: string;
  containerId: string;
  content?: string; // RAG를 위한 문서 내용
  summary?: string; // AI 생성 요약
  keywords?: string[]; // 추출된 키워드
  isSelected?: boolean;
}

// AI Agent 관련 타입들
export type AgentType =
  | 'general'           // 일반 대화
  | 'summarizer'        // 문서 요약
  | 'keyword-extractor' // 키워드 추출
  | 'presentation'      // PPT 생성  
  | 'template'          // 템플릿 기반 문서
  | 'knowledge-graph'   // 지식 그래프
  | 'analyzer'          // 문서 분석
  | 'insight'           // 인사이트 도출
  | 'report-generator'  // 보고서 생성
  | 'script-generator'  // 발표 스크립트
  | 'key-points';       // 핵심 포인트 추출

export interface AgentConfig {
  type: AgentType;
  name: string;
  description: string;
  icon: string;
  systemPrompt: string;
  requiredDocuments: number;
  outputFormat: 'text' | 'markdown' | 'json' | 'pptx' | 'docx';
  estimatedTime: number; // 예상 처리 시간 (초)
}

export interface AgentChain {
  id: string;
  name: string;
  description: string;
  agents: AgentType[];
  outputFormat: string;
  estimatedTime: number;
  requiresDocuments: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  agentType?: AgentType;
  relatedDocuments?: string[]; // 참조된 문서 ID들
  metadata?: {
    processingTime?: number;
    tokensUsed?: number;
    confidence?: number;
  };
}

export interface ChatSession {
  sessionId: string;
  title: string;
  createdAt: string;
  lastMessageAt: string;
  messageCount: number;
  agentType: AgentType;
  relatedDocuments: Document[];
  metadata?: any;
}

export interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  error: string | null;
  availableAgents: AgentConfig[];
  availableChains: AgentChain[];
  lastLoadTime?: number; // 마지막 세션 목록 로드 시간
  selectedDocuments?: Document[]; // 채팅에 사용될 선택된 문서 목록
}

export interface AgentChatPageState {
  selectedDocuments: Document[];
  currentSessionId?: string | null;
  lastVisitedAt?: string;
}

// 페이지별 상태 타입
export interface DashboardState {
  // 대시보드 위젯 데이터
  widgets: {
    type: 'document-trends' | 'user-activity' | 'system-health';
    data: any;
  }[];

  // 최근 활동 기록
  recentActivities: {
    timestamp: string;
    type: 'document-upload' | 'document-update' | 'chat-interaction';
    details: any;
  }[];

  // 즐겨찾기 문서
  favoriteDocuments: Document[];

  // 사용자 맞춤 설정
  userPreferences: {
    theme: 'light' | 'dark';
    language: string;
    notificationsEnabled: boolean;
  };
}

// 작업 컨텍스트
export type SourcePageType = 'my-knowledge' | 'search' | 'chat' | 'agent-chat' | 'dashboard';

export interface WorkContext {
  sourcePageType: SourcePageType;
  sourcePageState: any; // 이전 페이지 상태 보존
  ragMode: boolean; // RAG 채팅 모드 여부
  selectedAgent: AgentType | null;
  selectedAgentChain: string | null; // Agent Chain ID
  isChainMode: boolean; // 단일 Agent vs Chain 모드
  // 🆕 에이전트 믹싱 모드 및 다중 선택 지원
  mode?: 'single' | 'multi' | 'chain';
  selectedAgents?: AgentType[]; // multi 모드에서 사용
  navigationHistory: {
    from: SourcePageType;
    to: SourcePageType;
    timestamp: string;
    preservedState: any;
  }[];
}

// 검색 관련 상태 (복원용)
export interface SearchState {
  query: string;
  filters: any;
  results: any[];
  selectedResults: string[];
  viewMode: 'list' | 'grid';
  currentPage: number;
  selectedDocuments: Document[]; // 검색 페이지 전용 선택된 문서
  lastLoadTime?: number;
}

// 내 지식 관련 상태 (복원용)  
export interface MyKnowledgeState {
  selectedContainer?: string | null;
  expandedContainers?: string[];
  searchTerm?: string;
  filterStatus?: string;
  sortBy?: string;
  sortOrder?: string;
  selectedDocuments?: Document[];
  currentPage?: number;
  itemsPerPage?: number;
  totalItems?: number;
  hasNext?: boolean;
  hasPrevious?: boolean;
  viewMode?: 'grid' | 'list';
  containers?: any[]; // KnowledgeContainer[]
  documents?: any[]; // ExtendedDocument[]
  lastLoadTime?: number;
}

export interface ChatHistoryState {
  sessions: any[]; // Simplified ChatSession type
  cursor: string | null;
  hasMore: boolean;
  scrollPosition?: number;
  lastLoadTime?: number;
}

// 컨테이너 탐색 페이지 상태
export interface ContainerExplorerState {
  tree: any[]; // 컨테이너 트리 구조
  selectedId: string | null; // 선택된 컨테이너 ID
  expanded: string[]; // 확장된 노드 ID 목록
  documents: any[]; // 로드된 문서 목록
  scrollPosition?: number; // 스크롤 위치
  lastLoadTime?: number; // 마지막 로드 시간 (타임스탬프)
}

// 🆕 워크플로우 상태 타입 추가
export interface WorkflowStep {
  id: string;
  name: string;
  page: SourcePageType;
  timestamp: string;
  data?: any;
}

export interface UserActivity {
  searchCount: number;
  uploadCount: number;
  chatCount: number;
  viewCount: number;
  lastActivity: string;
  recentSearches: string[];
  recentDocuments: string[];
}

export interface WorkflowState {
  currentStep: 'dashboard' | 'search' | 'my-knowledge' | 'chat' | 'complete';
  stepHistory: WorkflowStep[];
  selectedDocuments: Document[];
  targetAction?: 'ai-chat' | 'download' | 'share' | 'edit';
  isActive: boolean;
  startTime?: string;
}

// 메인 글로벌 상태
export interface GlobalAppState {
  // 사용자 정보
  user: UserInfo | null;

  // 선택된 지식 컨테이너들
  selectedContainers: KnowledgeContainer[];

  // 선택된 문서들 (RAG 소스)
  selectedDocuments: Document[];

  // 현재 작업 컨텍스트
  workContext: WorkContext;

  // 채팅 관련
  currentChatSession: ChatSession | null;
  chatHistory: ChatMessage[];

  // 🆕 워크플로우 및 활동 상태
  workflow: WorkflowState;
  userActivity: UserActivity;

  // 페이지 상태 보존
  pageStates: {
    search: SearchState;
    myKnowledge: MyKnowledgeState;
    chat: ChatState;
    agentChat: AgentChatPageState;
    chatHistory: ChatHistoryState;
    containerExplorer: ContainerExplorerState;
  };

  // UI 상태
  ui: {
    isLoading: boolean;
    error: string | null;
    notifications: Array<{
      id: string;
      type: 'success' | 'error' | 'warning' | 'info';
      message: string;
      timestamp: string;
    }>;
  };
}

// Action 타입들
export type GlobalAppAction =
  | { type: 'SET_USER'; payload: UserInfo | null }
  | { type: 'SET_SELECTED_CONTAINERS'; payload: KnowledgeContainer[] }
  | { type: 'ADD_SELECTED_CONTAINER'; payload: KnowledgeContainer }
  | { type: 'REMOVE_SELECTED_CONTAINER'; payload: string }
  | { type: 'SET_SELECTED_DOCUMENTS'; payload: Document[] }
  | { type: 'ADD_SELECTED_DOCUMENT'; payload: Document }
  | { type: 'REMOVE_SELECTED_DOCUMENT'; payload: string }
  | { type: 'CLEAR_SELECTED_DOCUMENTS' }
  | { type: 'TOGGLE_DOCUMENT_SELECTION'; payload: Document }
  // 페이지별 선택된 문서 관리 액션들
  | { type: 'SET_PAGE_SELECTED_DOCUMENTS'; payload: { page: 'search' | 'myKnowledge' | 'chat' | 'agentChat'; documents: Document[] } }
  | { type: 'ADD_PAGE_SELECTED_DOCUMENT'; payload: { page: 'search' | 'myKnowledge' | 'chat' | 'agentChat'; document: Document } }
  | { type: 'REMOVE_PAGE_SELECTED_DOCUMENT'; payload: { page: 'search' | 'myKnowledge' | 'chat' | 'agentChat'; fileId: string } }
  | { type: 'CLEAR_PAGE_SELECTED_DOCUMENTS'; payload: { page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' } }
  | { type: 'UPDATE_WORK_CONTEXT'; payload: Partial<WorkContext> }
  | { type: 'SET_CHAT_SESSION'; payload: ChatSession | null }
  | { type: 'ADD_CHAT_MESSAGE'; payload: ChatMessage }
  | { type: 'CLEAR_CHAT_HISTORY' }
  | { type: 'SAVE_PAGE_STATE'; payload: { page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' | 'chatHistory' | 'containerExplorer'; state: any } }
  | { type: 'RESTORE_PAGE_STATE'; payload: { page: 'search' | 'myKnowledge' | 'chat' | 'agentChat' | 'chatHistory' | 'containerExplorer' } }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'ADD_NOTIFICATION'; payload: { type: 'success' | 'error' | 'warning' | 'info'; message: string } }
  | { type: 'REMOVE_NOTIFICATION'; payload: string }
  // 🆕 워크플로우 및 활동 액션들
  | { type: 'START_WORKFLOW'; payload: { step: string; data?: any } }
  | { type: 'UPDATE_WORKFLOW_STEP'; payload: { step: string; data?: any } }
  | { type: 'COMPLETE_WORKFLOW'; payload?: any }
  | { type: 'CANCEL_WORKFLOW' }
  | { type: 'UPDATE_USER_ACTIVITY'; payload: Partial<UserActivity> }
  | { type: 'INCREMENT_ACTIVITY_COUNT'; payload: { type: 'search' | 'upload' | 'chat' | 'view' } }
  | { type: 'RESET_STATE' };

// Agent 설정 상수
export const AGENT_CONFIGS: Record<AgentType, AgentConfig> = {
  'general': {
    type: 'general',
    name: '일반 대화',
    description: '자유로운 대화가 가능한 범용 AI',
    icon: '💬',
    systemPrompt: '당신은 도움이 되는 AI 어시스턴트입니다.',
    requiredDocuments: 0,
    outputFormat: 'text',
    estimatedTime: 5
  },
  'summarizer': {
    type: 'summarizer',
    name: '문서 요약',
    description: '문서의 핵심 내용을 간결하게 요약',
    icon: '📝',
    systemPrompt: '당신은 문서 요약 전문가입니다. 핵심 내용을 명확하고 간결하게 요약해주세요.',
    requiredDocuments: 1,
    outputFormat: 'markdown',
    estimatedTime: 10
  },
  'keyword-extractor': {
    type: 'keyword-extractor',
    name: '키워드 추출',
    description: '문서에서 중요한 키워드와 주제 추출',
    icon: '🔍',
    systemPrompt: '문서에서 핵심 키워드와 주제를 추출하는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'json',
    estimatedTime: 8
  },
  'presentation': {
    type: 'presentation',
    name: 'PPT 생성',
    description: '문서 내용을 바탕으로 프리젠테이션 생성',
    icon: '📊',
    systemPrompt: '효과적인 프리젠테이션 자료를 만드는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'pptx',
    estimatedTime: 20
  },
  'template': {
    type: 'template',
    name: '템플릿 문서',
    description: '특정 템플릿 형식으로 문서 생성',
    icon: '📄',
    systemPrompt: '다양한 템플릿 형식의 문서를 생성하는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'docx',
    estimatedTime: 15
  },
  'knowledge-graph': {
    type: 'knowledge-graph',
    name: '지식 그래프',
    description: '문서들 간의 연관관계를 시각화',
    icon: '🕸️',
    systemPrompt: '지식 그래프를 생성하고 분석하는 전문가입니다.',
    requiredDocuments: 2,
    outputFormat: 'json',
    estimatedTime: 25
  },
  'analyzer': {
    type: 'analyzer',
    name: '문서 분석',
    description: '문서의 구조와 패턴을 깊이 있게 분석',
    icon: '🔬',
    systemPrompt: '문서를 체계적으로 분석하는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'markdown',
    estimatedTime: 12
  },
  'insight': {
    type: 'insight',
    name: '인사이트 도출',
    description: '데이터에서 의미있는 통찰과 패턴 발견',
    icon: '💡',
    systemPrompt: '데이터에서 인사이트를 도출하는 전문가입니다.',
    requiredDocuments: 2,
    outputFormat: 'markdown',
    estimatedTime: 18
  },
  'report-generator': {
    type: 'report-generator',
    name: '보고서 작성',
    description: '체계적이고 전문적인 보고서 생성',
    icon: '📋',
    systemPrompt: '전문적인 보고서를 작성하는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'docx',
    estimatedTime: 22
  },
  'script-generator': {
    type: 'script-generator',
    name: '발표 스크립트',
    description: '프리젠테이션용 발표 스크립트 생성',
    icon: '🎭',
    systemPrompt: '효과적인 발표 스크립트를 작성하는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'text',
    estimatedTime: 15
  },
  'key-points': {
    type: 'key-points',
    name: '핵심 포인트',
    description: '문서의 핵심 포인트를 구조화하여 정리',
    icon: '🎯',
    systemPrompt: '핵심 포인트를 명확하게 정리하는 전문가입니다.',
    requiredDocuments: 1,
    outputFormat: 'markdown',
    estimatedTime: 8
  }
};

// Agent Chain 설정
export const AGENT_CHAINS: AgentChain[] = [
  {
    id: 'full-presentation',
    name: '완전 프리젠테이션 패키지',
    description: '문서 요약 → 키워드 추출 → PPT 생성 → 발표 스크립트',
    agents: ['summarizer', 'keyword-extractor', 'presentation', 'script-generator'],
    outputFormat: 'pptx + script',
    estimatedTime: 55,
    requiresDocuments: true
  },
  {
    id: 'knowledge-synthesis',
    name: '지식 통합 분석',
    description: '문서 분석 → 지식그래프 생성 → 인사이트 도출 → 보고서 작성',
    agents: ['analyzer', 'knowledge-graph', 'insight', 'report-generator'],
    outputFormat: 'comprehensive-report',
    estimatedTime: 77,
    requiresDocuments: true
  },
  {
    id: 'quick-summary',
    name: '빠른 문서 분석',
    description: '문서 요약 → 핵심 포인트 추출',
    agents: ['summarizer', 'key-points'],
    outputFormat: 'structured-summary',
    estimatedTime: 18,
    requiresDocuments: true
  },
  {
    id: 'content-creation',
    name: '콘텐츠 제작 패키지',
    description: '키워드 추출 → 템플릿 문서 생성 → 프리젠테이션 변환',
    agents: ['keyword-extractor', 'template', 'presentation'],
    outputFormat: 'multi-format',
    estimatedTime: 43,
    requiresDocuments: true
  },
  {
    id: 'research-analysis',
    name: '연구 분석 워크플로우',
    description: '문서 분석 → 인사이트 도출 → 연구 보고서 작성',
    agents: ['analyzer', 'insight', 'report-generator'],
    outputFormat: 'research-report',
    estimatedTime: 52,
    requiresDocuments: true
  }
];

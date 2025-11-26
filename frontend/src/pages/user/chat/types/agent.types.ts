/**
 * Agent Chat Types
 * 
 * AI Agent 기반 채팅에서 사용하는 타입 정의
 */

import { ChatMessage } from './chat.types';

/**
 * Agent 의도 (Intent)
 */
export type AgentIntent =
  | 'FACTUAL_QA'        // 사실 기반 질문
  | 'KEYWORD_SEARCH'    // 키워드 검색
  | 'DOCUMENT_ANALYSIS' // 문서 분석
  | 'GENERAL_CHAT'      // 일반 대화
  | 'UNKNOWN';          // 의도 불명

/**
 * Agent 도구 이름
 */
export type AgentToolName =
  | 'VectorSearchTool'
  | 'KeywordSearchTool'
  | 'FulltextSearchTool'
  | 'DeduplicateTool'
  | 'RerankTool'
  | 'ContextBuilderTool';

/**
 * Agent 실행 단계
 */
export interface AgentStep {
  step_number: number;
  tool_name: AgentToolName;
  reasoning: string;        // 도구 선택 이유
  latency_ms: number;       // 실행 시간
  items_returned?: number;  // 반환된 아이템 수
  success: boolean;         // 성공 여부
  timestamp?: string;       // 실행 시각
}

/**
 * Agent 참조 문서
 */
export interface AgentReference {
  chunk_id: string;
  content: string;
  score: number;            // 유사도/관련도 점수
  document_id?: string;
  title?: string;
  page_number?: number;
  file_name?: string;
  container_name?: string;
  metadata?: Record<string, any>;
}

/**
 * Agent 성능 지표
 */
export interface AgentMetrics {
  total_latency_ms: number;       // 전체 실행 시간
  total_chunks_found: number;     // 검색된 총 청크 수
  total_tokens_used?: number;     // 사용된 토큰 수
  deduplication_rate?: number;    // 중복 제거율 (0.0~1.0)
  search_time_ms?: number;        // 검색 시간
  rerank_time_ms?: number;        // 리랭킹 시간
  context_build_time_ms?: number; // 컨텍스트 구성 시간
  llm_time_ms?: number;           // LLM 추론 시간
  [key: string]: any;
}

/**
 * 🆕 Reasoning 데이터 (AI 사고 과정)
 */
export interface ReasoningStep {
  stage: string;  // 'query_analysis', 'search', 'postprocess', 'context_building', 'answer_generation'
  status: 'started' | 'completed' | 'error';
  tool?: string;
  message: string;
  result?: any;
  duration_ms?: number;
  timestamp?: string;
}

export interface SearchProgress {
  tool: string;
  chunks_found: number;
  total_chunks: number;
  avg_similarity?: number;
}

export interface ReasoningData {
  steps: ReasoningStep[];
  searchProgress: SearchProgress[];
  totalDuration?: number;
  intent?: string;
  keywords?: string[];
  strategy?: string[];
  searchStats?: Record<string, any>;
}

/**
 * Agent 메시지 (ChatMessage 확장)
 */
export interface AgentMessage extends ChatMessage {
  // Agent 고유 필드
  intent?: AgentIntent;
  strategy_used?: string[];      // 사용된 도구 조합
  agent_steps?: AgentStep[];     // 실행 단계 목록
  agent_metrics?: AgentMetrics;  // 성능 지표
  agent_references?: AgentReference[]; // Agent 참조 문서
  agent_errors?: string[];       // Agent 실행 중 에러

  // 🆕 Reasoning (AI 사고 과정)
  reasoning?: ReasoningData;

  // 🆕 첨부 파일 메타데이터
  attached_files?: Array<{
    file_name: string;
    file_size: number;
    text_length: number;
  }>;
}

/**
 * Agent 채팅 세션 상태
 */
export interface AgentChatState {
  sessionId: string;
  messages: AgentMessage[];
  isLoading: boolean;
  error: string | null;
  currentIntent?: AgentIntent;
  currentSteps?: AgentStep[];
  currentMetrics?: AgentMetrics;
}

/**
 * Agent 설정
 */
export interface AgentSettings {
  max_chunks: number;           // 최대 청크 수 (1~50)
  max_tokens: number;           // 최대 토큰 수 (100~8000)
  similarity_threshold: number; // 유사도 임계값 (0.0~1.0)
  container_ids?: string[];     // 컨테이너 필터
  document_ids?: string[];      // 문서 필터
}

/**
 * Agent 전략 (도구 조합)
 */
export interface AgentStrategy {
  name: string;
  tools: AgentToolName[];
  description: string;
  best_for: AgentIntent[];
}

/**
 * 사전 정의된 Agent 전략들
 */
export const AGENT_STRATEGIES: Record<string, AgentStrategy> = {
  FACTUAL_QA: {
    name: '사실 기반 질문 전략',
    tools: ['VectorSearchTool', 'DeduplicateTool', 'ContextBuilderTool'],
    description: '의미론적 검색 → 중복 제거 → 컨텍스트 구성',
    best_for: ['FACTUAL_QA']
  },
  KEYWORD_SEARCH: {
    name: '키워드 검색 전략',
    tools: ['KeywordSearchTool', 'FulltextSearchTool', 'DeduplicateTool', 'ContextBuilderTool'],
    description: '키워드 매칭 + 전문 검색 → 중복 제거 → 컨텍스트 구성',
    best_for: ['KEYWORD_SEARCH']
  },
  DEEP_ANALYSIS: {
    name: '심층 분석 전략',
    tools: ['VectorSearchTool', 'KeywordSearchTool', 'DeduplicateTool', 'RerankTool', 'ContextBuilderTool'],
    description: '벡터 + 키워드 검색 → 중복 제거 → 리랭킹 → 컨텍스트 구성',
    best_for: ['DOCUMENT_ANALYSIS']
  }
};

/**
 * Intent 한글 레이블
 */
export const INTENT_LABELS: Record<AgentIntent, string> = {
  FACTUAL_QA: '사실 기반 질문',
  KEYWORD_SEARCH: '키워드 검색',
  DOCUMENT_ANALYSIS: '문서 분석',
  GENERAL_CHAT: '일반 대화',
  UNKNOWN: '의도 불명'
};

/**
 * Tool 한글 레이블
 */
export const TOOL_LABELS: Record<AgentToolName, string> = {
  VectorSearchTool: '벡터 검색',
  KeywordSearchTool: '키워드 검색',
  FulltextSearchTool: '전문 검색',
  DeduplicateTool: '중복 제거',
  RerankTool: '리랭킹',
  ContextBuilderTool: '컨텍스트 구성'
};

/**
 * Tool 아이콘 매핑 (Heroicons)
 */
export const TOOL_ICONS: Record<AgentToolName, string> = {
  VectorSearchTool: 'MagnifyingGlassIcon',
  KeywordSearchTool: 'MagnifyingGlassIcon',
  FulltextSearchTool: 'DocumentMagnifyingGlassIcon',
  DeduplicateTool: 'FunnelIcon',
  RerankTool: 'ArrowsUpDownIcon',
  ContextBuilderTool: 'CubeIcon'
};

/**
 * Tool 색상 매핑 (Tailwind)
 */
export const TOOL_COLORS: Record<AgentToolName, { bg: string; text: string; border: string }> = {
  VectorSearchTool: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  KeywordSearchTool: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  FulltextSearchTool: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  DeduplicateTool: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  RerankTool: { bg: 'bg-pink-50', text: 'text-pink-700', border: 'border-pink-200' },
  ContextBuilderTool: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' }
};

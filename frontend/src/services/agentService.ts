/**
 * Agent Chat Service
 * 
 * AI Agent 기반 채팅 API 호출 서비스
 * Endpoint: /api/v1/agent/*
 */

import axios from 'axios';
import { authService } from './authService';

// Axios 인스턴스 생성
const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// JWT 토큰 자동 추가
api.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 에러 처리
authService.setupResponseInterceptor(api);


// ========== TypeScript Types ==========

/**
 * Agent 채팅 요청
 */
export interface AgentChatRequest {
  message: string;
  session_id?: string;
  max_chunks?: number;
  max_tokens?: number;
  similarity_threshold?: number;
  container_ids?: string[];
  document_ids?: string[];
}

/**
 * Agent 실행 단계
 */
export interface AgentStepResponse {
  step_number: number;
  tool_name: string;
  reasoning: string;
  latency_ms: number;
  items_returned?: number;
  success: boolean;
}

/**
 * 참조 문서
 */
export interface ReferenceDocument {
  chunk_id: string;
  content: string;
  score: number;
  document_id?: string;
  title?: string;
  page_number?: number;
}

/**
 * 상세 청크 정보 (일반 채팅과 동일 형식)
 */
export interface DetailedChunk {
  index: number;
  file_id: number;
  file_name: string;
  chunk_index: number;
  page_number?: number;
  content_preview: string;
  similarity_score: number;
  search_type: string;
  section_title: string;
}

/**
 * Agent 채팅 응답
 */
export interface AgentChatResponse {
  answer: string;
  intent: string;
  strategy_used: string[];
  references: ReferenceDocument[];
  detailed_chunks: DetailedChunk[];  // 🆕 일반 채팅과 동일 형식
  steps: AgentStepResponse[];
  metrics: {
    total_latency_ms: number;
    total_chunks_found: number;
    total_tokens_used?: number;
    deduplication_rate?: number;
    [key: string]: any;
  };
  success: boolean;
  errors: string[];
}

/**
 * A/B 비교 응답
 */
export interface CompareResponse {
  query: string;
  agent_result: {
    answer: string;
    latency_ms: number;
    references_count: number;
    strategy: string[];
    steps_count: number;
  };
  old_result?: {
    answer: string;
    latency_ms: number;
    references_count: number;
  };
  winner: 'agent' | 'old' | 'tie';
  analysis: {
    latency_improvement: number;
    quality_score: number;
    cost_comparison: any;
  };
}


// ========== API Methods ==========

export const agentService = {
  /**
   * Agent 기반 채팅 메시지 전송
   */
  async sendAgentChat(request: AgentChatRequest): Promise<AgentChatResponse> {
    try {
      console.log('🤖 [AgentService] 요청:', {
        message: request.message.slice(0, 50),
        container_ids: request.container_ids,
        max_chunks: request.max_chunks
      });

      const response = await api.post<AgentChatResponse>(
        '/api/v1/agent/chat',
        {
          message: request.message,
          session_id: request.session_id,
          max_chunks: request.max_chunks || 10,
          max_tokens: request.max_tokens || 2000,
          similarity_threshold: request.similarity_threshold || 0.5,
          container_ids: request.container_ids || null,
          document_ids: request.document_ids || null,
          provider: null
        }
      );

      console.log('✅ [AgentService] 응답:', {
        intent: response.data.intent,
        strategy: response.data.strategy_used,
        steps_count: response.data.steps.length,
        references_count: response.data.references.length,
        latency_ms: response.data.metrics.total_latency_ms
      });

      return response.data;
    } catch (error: any) {
      console.error('❌ [AgentService] 실패:', error);

      // 에러 처리
      if (error.response?.status === 401) {
        console.warn('🔐 인증 실패 - 로그인 페이지로 리다이렉트');
        localStorage.removeItem('wikl_token');
        localStorage.removeItem('wikl_refresh_token');
        localStorage.removeItem('wikl_user');
        window.location.href = '/login';
      }

      throw new Error(
        error.response?.data?.detail ||
        error.message ||
        'Agent 채팅 요청 실패'
      );
    }
  },

  /**
   * A/B 비교 (기존 vs Agent 아키텍처)
   */
  async compareArchitectures(request: AgentChatRequest): Promise<CompareResponse> {
    try {
      console.log('📊 [AgentService] A/B 비교 요청:', request.message.slice(0, 50));

      const response = await api.post<CompareResponse>(
        '/api/v1/agent/compare',
        {
          message: request.message,
          session_id: request.session_id,
          max_chunks: request.max_chunks || 10,
          max_tokens: request.max_tokens || 2000,
          similarity_threshold: request.similarity_threshold || 0.5,
          container_ids: request.container_ids || null,
          document_ids: request.document_ids || null,
          provider: null
        }
      );

      console.log('✅ [AgentService] 비교 완료:', {
        winner: response.data.winner,
        latency_improvement: response.data.analysis.latency_improvement
      });

      return response.data;
    } catch (error: any) {
      console.error('❌ [AgentService] 비교 실패:', error);
      throw new Error(
        error.response?.data?.detail ||
        error.message ||
        'A/B 비교 요청 실패'
      );
    }
  },

  /**
   * Agent 시스템 헬스 체크
   */
  async checkHealth(): Promise<{
    status: string;
    agent_available: boolean;
    tools_count: number;
    version: string;
  }> {
    try {
      const response = await api.get('/api/v1/agent/health');
      return response.data;
    } catch (error: any) {
      console.error('❌ [AgentService] 헬스체크 실패:', error);
      throw new Error('Agent 시스템 상태 확인 실패');
    }
  }
};

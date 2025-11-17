import axios from 'axios';
import { getApiUrl } from '../utils/apiConfig';
import { authService } from './authService';

const API_BASE_URL = getApiUrl();

// axios 인스턴스 생성
const api = axios.create({
  baseURL: '', // 프록시 사용으로 빈 문자열
  headers: {
    'Content-Type': 'application/json',
  },
});

// 토큰 인터셉터 - authService 사용
api.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터: 401 에러 처리
authService.setupResponseInterceptor(api);

// Bedrock 서비스 인터페이스
export interface ChatRequest {
  message: string;
  include_context?: boolean;
  conversation_id?: string;
}

export interface ChatResponse {
  response: string;
  context_used: string[];
  conversation_id: string;
  model_used: string;
}

export interface EmbeddingRequest {
  texts: string[];
  model?: string; // "titan" 또는 "cohere"
}

export interface EmbeddingResponse {
  embeddings: number[][];
  model_used: string;
  dimensions: number;
}

export interface DocumentUploadResponse {
  filename: string;
  document_id: string;
  chunks_created: number;
  embedding_model: string;
  status: string;
}

export interface ModelStatusResponse {
  claude_3_5_sonnet: boolean;
  titan_embeddings_v2: boolean;
  cohere_embed_multilingual: boolean;
  message: string;
}

export interface SearchResult {
  query: string;
  results: any[];
  embedding_model: string;
  total_found: number;
}

class BedrockService {
  /**
   * AWS Bedrock 모델 상태 확인
   */
  async checkModelStatus(): Promise<ModelStatusResponse> {
    try {
      const response = await api.get('/api/bedrock/models/status');
      return response.data;
    } catch (error) {
      console.error('모델 상태 확인 실패:', error);
      throw error;
    }
  }

  /**
   * Claude 3.5 Sonnet v2를 사용한 채팅
   */
  async chatWithClaude(request: ChatRequest): Promise<ChatResponse> {
    try {
      const response = await api.post('/api/bedrock/chat', request);
      return response.data;
    } catch (error) {
      console.error('Bedrock 채팅 실패:', error);
      throw error;
    }
  }

  /**
   * 임베딩 생성 (Titan 또는 Cohere)
   */
  async generateEmbeddings(request: EmbeddingRequest): Promise<EmbeddingResponse> {
    try {
      const response = await api.post('/api/bedrock/embeddings', request);
      return response.data;
    } catch (error) {
      console.error('임베딩 생성 실패:', error);
      throw error;
    }
  }

  /**
   * 문서 업로드 및 벡터화
   */
  async uploadDocument(
    file: File,
    embeddingModel: string = 'titan'
  ): Promise<DocumentUploadResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('embedding_model', embeddingModel);

      const response = await api.post('/api/bedrock/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('문서 업로드 실패:', error);
      throw error;
    }
  }

  /**
   * 벡터 검색을 통한 문서 찾기
   */
  async searchDocuments(
    query: string,
    limit: number = 10,
    embeddingModel: string = 'titan'
  ): Promise<SearchResult> {
    try {
      const response = await api.get('/api/bedrock/documents/search', {
        params: {
          query,
          limit,
          embedding_model: embeddingModel,
        },
      });
      return response.data;
    } catch (error) {
      console.error('문서 검색 실패:', error);
      throw error;
    }
  }

  /**
   * 스트리밍 채팅 (향후 구현용)
   */
  async streamChat(request: ChatRequest): Promise<ReadableStream> {
    // TODO: Server-Sent Events 또는 WebSocket을 사용한 스트리밍 구현
    throw new Error('스트리밍 채팅은 아직 구현되지 않았습니다.');
  }
}

// 싱글톤 인스턴스 생성
export const bedrockService = new BedrockService();

// 유틸리티 함수들
export const BedrockUtils = {
  /**
   * 모델 이름을 한국어로 변환
   */
  getModelDisplayName(modelId: string): string {
    const modelNames: { [key: string]: string } = {
      'anthropic.claude-3-5-sonnet-20241022-v2:0': 'Claude 3.5 Sonnet v2',
      'amazon.titan-embed-text-v2:0': 'Titan Text Embeddings V2',
      'cohere.embed-multilingual-v3': 'Marengo Embed 2.7',
    };
    return modelNames[modelId] || modelId;
  },

  /**
   * 에러 메시지를 사용자 친화적으로 변환
   */
  getErrorMessage(error: any): string {
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (error.message) {
      return error.message;
    }
    return '알 수 없는 오류가 발생했습니다.';
  },

  /**
   * 파일 크기를 읽기 쉬운 형태로 변환
   */
  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  /**
   * 지원되는 파일 형식 확인
   */
  isFileTypeSupported(fileName: string): boolean {
    const supportedExtensions = ['.pdf', '.docx', '.pptx', '.txt', '.md'];
    const extension = fileName.toLowerCase().substring(fileName.lastIndexOf('.'));
    return supportedExtensions.includes(extension);
  },

  /**
   * 대화 히스토리 로컬 저장소 관리
   */
  saveConversation(conversationId: string, message: string, response: string): void {
    const conversations = JSON.parse(localStorage.getItem('bedrock_conversations') || '{}');
    if (!conversations[conversationId]) {
      conversations[conversationId] = [];
    }
    conversations[conversationId].push({
      timestamp: new Date().toISOString(),
      user: message,
      assistant: response,
    });
    localStorage.setItem('bedrock_conversations', JSON.stringify(conversations));
  },

  /**
   * 대화 히스토리 불러오기
   */
  getConversation(conversationId: string): any[] {
    const conversations = JSON.parse(localStorage.getItem('bedrock_conversations') || '{}');
    return conversations[conversationId] || [];
  },
};

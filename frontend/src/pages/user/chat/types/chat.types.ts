export type AttachmentCategory = 'image' | 'document' | 'audio';

export interface ChatAttachment {
  id: string;
  fileName: string;
  mimeType: string;
  size: number;
  previewUrl?: string;
  downloadUrl?: string;
  category: AttachmentCategory;
}

export interface ConversationState {
  updatedAt: string;
  summary: string;
  keywords: string[];
  topicContinuity: number;
  lastIntent?: string;
  relevantDocuments: Array<{
    id: string;
    title: string;
    containerName?: string;
    similarity?: number;
  }>;
  hints?: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  // 메시지 콘텐츠 포맷: 기본은 markdown, HTML 슬라이드 등 확장 지원
  content_format?: 'markdown' | 'html';
  // HTML 메시지 메타정보(선택)
  html_meta?: {
    title?: string;
    slide_count?: number;
  };
  timestamp: string;
  // 백엔드 Redis 상의 메시지 ID (SSE complete에서 제공)
  message_id?: string;
  agent_type?: string;
  message_subtype?: 'user_question' | 'selected_documents' | 'presentation_download' | 'agent_thinking';  // 메시지 서브타입 추가
  // 프론트엔드 의도 감지 결과 (PPT 관련 여부)
  presentation_intent?: boolean;
  selected_documents?: SelectedDocument[];  // 선택된 문서 정보
  references?: ChatReference[];

  // 🆕 백엔드에서 전달하는 청크 상세 정보
  detailed_chunks?: Array<{
    index: number;
    file_id: number;
    file_name: string;
    chunk_index: number;
    page_number?: number;
    content_preview: string;
    similarity_score: number;
    search_type: string;
    section_title: string;
  }>;

  context_info?: {
    total_chunks?: number;
    chunks_count?: number;  // 🆕 청크 개수
    documents_count?: number;  // 🆕 문서 개수
    context_tokens?: number;
    search_mode?: string;
    reranking_applied?: boolean;
    rag_used?: boolean;  // 🆕 RAG 사용 여부
    answer_source?: 'internet_search' | 'mixed_search' | 'database_search' | 'attached_documents' | 'general';  // 🆕 답변 출처
    has_internet_results?: boolean;  // 🆕 인터넷 검색 결과 포함 여부
  };
  rag_stats?: {
    query_length: number;
    total_candidates: number;
    final_chunks: number;
    avg_similarity: number | null;
    search_time: number | null;
    search_mode: string;
    has_korean_keywords: boolean;
    embedding_dimension: number;
    provider: string | null;
    embedding_provider: string | null;
    llm_provider: string | null;  // 백엔드 .env 설정 사용
    llm_model: string | null;
    embedding_model: string | null;
  };
  // 🎯 멀티모달 이미지 관련 필드 추가
  image_descriptions?: Array<{
    image_index: number;
    filename: string;
    description: string;
  }>;
  uploaded_images?: Array<{
    filename: string;
    blob_url: string;
    sas_url: string;
    size: number;
  }>;
  attachments?: ChatAttachment[];

  // 🆕 이 메시지가 생성된 시점의 대화 컨텍스트 (각 assistant 응답마다 고유)
  conversationContext?: ConversationState;

  // 🆕 특허 분석 결과
  patent_results?: {
    patents: Array<{
      title: string;
      applicant?: string;
      applicationNumber?: string;
      applicationDate?: string;
      publicationNumber?: string;
      publicationDate?: string;
      abstract?: string;
      ipcCodes?: string[];
      status?: string;
      url?: string;
    }>;
    total_patents: number;
    visualizations?: any[];
    insights?: string[];
    source?: string;
  };

  // 🆕 백엔드 메타데이터 (PPT 생성 관련)
  metadata?: {
    ppt_file_url?: string;
    ppt_file_name?: string;
    structured_content?: string;
    [key: string]: any;
  };

  // 🆕 PPT 생성 진행 상태 (AI 사고 과정 표시용)
  pptReasoning?: PPTReasoningData;
}

// 🆕 PPT 생성 진행 상태 데이터
export interface PPTProgressStep {
  message: string;
  status: 'in_progress' | 'completed' | 'error';
  timestamp?: string;
}

export interface PPTReasoningData {
  steps: PPTProgressStep[];
  isComplete: boolean;
  hasError: boolean;
  mode: 'quick' | 'template';  // PPT 생성 모드
  resultFileName?: string;
  resultFileUrl?: string;
}

// 선택된 문서 정보 인터페이스 추가
export interface SelectedDocument {
  id: number;
  fileName: string;
  fileType: string;
  fileSize?: number;
  uploadDate?: string;
}

export interface ChatReference {
  title: string;
  excerpt: string;
  url?: string;
  file_name?: string;
  file_bss_info_sno?: number;  // 문서 파일 번호 추가
  chunk_index?: number;
  similarity_score?: number;
  page_number?: number;
  keywords?: string;
  // 새로운 사용자 친화적 필드들
  document_type?: string;
  relevance_grade?: string;
  relevance_percentage?: number;
  ai_summary?: string;
  user_friendly_position?: string;
  chunk_position?: string;
  section_title?: string;
  content_length?: number;
}

export interface ChatSession {
  id: string;
  session_id: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface ChatRequest {
  message: string;
  provider?: string;
  container_ids?: number[];
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  provider: string;
  session_id: string;
  references: ChatReference[];
  context_info: {
    total_chunks: number;
    context_tokens: number;
    search_mode: string;
    reranking_applied: boolean;
  };
  rag_stats: {
    query_length: number;
    total_candidates: number;
    final_chunks: number;
    avg_similarity: number;
    search_time: number;
    search_mode: string;
    has_korean_keywords: boolean;
    embedding_dimension: number;
    provider: string;
    embedding_provider: string;
    llm_provider: string | null;  // 백엔드 .env 설정 사용
    llm_model: string;
    embedding_model: string;
  };
  attachments?: ChatAttachment[];
  voice_asset_id?: string;
}

export interface ChatSettings {
  provider?: 'bedrock' | 'azure_openai' | 'openai';  // optional: 백엔드 .env 설정 사용
  temperature: number;
  max_tokens: number;
  container_ids: number[];
}
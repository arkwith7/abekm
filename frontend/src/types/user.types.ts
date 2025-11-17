// 일반 사용자 관련 타입 정의

export interface User {
  id: string;
  emp_no: string;
  name: string;
  username: string;
  email: string;
  department: string;
  position: string;
  role: 'USER' | 'MANAGER' | 'ADMIN';
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  document_id?: string;
  title: string;
  file_name: string;
  file_size: number;
  file_extension?: string;
  document_type?: string;
  quality_score?: number;
  korean_ratio?: number;
  keywords?: string[];
  container_path: string;
  description?: string;
  tags?: string[];
  is_public?: boolean;
  view_count?: number;
  download_count?: number;
  processing_stats?: {
    text_length: number;
    chunk_count: number;
    processing_time?: number;
    quality_score: string;
  };
  created_at?: string;
  updated_at?: string;
  uploaded_by: string;
  // 비동기 처리 상태 필드
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed';
  processing_error?: string;
  processing_started_at?: string;
  processing_completed_at?: string;
}

export interface SearchResult {
  documents: Document[];
  ai_answer?: string;
  related_documents: Document[];
  total_count: number;
  search_time: number;
}

export interface UploadProgress {
  file_name: string;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'error';
  error_message?: string;
}

export interface UploadResult {
  success: boolean;
  message: string;
  document: Document;
  document_id?: string;
  container_path?: string;
  processing_stats?: {
    text_length: number;
    chunk_count: number;
    processing_time?: number;
    quality_score: string;
  };
  korean_analysis?: {
    morphs: Array<{ word: string; pos: string; confidence: number }>;
    keywords: string[];
    sentiment?: string;
  };
}

export interface AIChat {
  id: string;
  question: string;
  answer: string;
  related_documents: Document[];
  sources?: Array<{
    title: string;
    excerpt: string;
    url?: string;
  }>;
  feedback?: 'positive' | 'negative';
  created_at: string;
}

export interface UserActivity {
  search_count: number;
  upload_count: number;
  chat_count: number;
  view_count: number;
  download_count: number;
  like_count: number;
}

export interface QuickAction {
  id: string;
  label: string;
  icon: string;
  path: string;
  description: string;
}

export interface Recommendation {
  type: 'document' | 'search' | 'category';
  title: string;
  description: string;
  items: Document[] | string[];
  reason: string;
}

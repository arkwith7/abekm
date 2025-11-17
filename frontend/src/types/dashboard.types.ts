// 대시보드 관련 타입 정의

/**
 * 대시보드 요약 카드 데이터
 */
export interface DashboardSummary {
  my_documents_count: number;
  chat_sessions_count: number;
  pending_requests_count: number;
}

/**
 * 최근 문서 정보
 */
export interface RecentDocument {
  file_bss_info_sno: number;
  title: string;
  file_name: string;
  file_size?: number;
  file_type?: string;
  container_id?: string;
  container_name: string;
  created_at?: string;
  created_by?: string;
  processing_status?: string;
}

/**
 * 컨테이너 요약 정보
 */
export interface ContainerSummary {
  container_id: string;
  container_name: string;
  my_documents_count: number;
  total_documents_count: number;
  my_permission: string;
  last_updated?: string;
  recent_documents: string[];
}

/**
 * AI 대화 히스토리
 */
export interface ChatHistory {
  session_id: string;
  session_type?: 'agent' | 'chat';  // 🆕 세션 타입 추가
  title: string;
  message_count: number;
  document_count: number;
  created_at?: string;
  last_message_at?: string;
}

/**
 * 최근 활동 내역
 */
export interface RecentActivity {
  activity_type: 'upload' | 'download' | 'chat' | 'permission_request' | 'search';
  title: string;
  description?: string;
  timestamp: string;
  icon: string;
  color: string;
  metadata?: Record<string, any>;
}

/**
 * 일별 활동 통계
 */
export interface DailyActivity {
  date: string;
  count: number;
}

/**
 * 활동 통계
 */
export interface ActivityStats {
  daily_uploads: DailyActivity[];
  document_types: Record<string, number>;
  container_distribution: Record<string, number>;
}

/**
 * 대시보드 API 응답
 */
export interface DashboardSummaryResponse {
  success: boolean;
  data: DashboardSummary;
}

export interface RecentDocumentsResponse {
  success: boolean;
  documents: RecentDocument[];
  total: number;
}

export interface ContainerSummaryResponse {
  success: boolean;
  containers: ContainerSummary[];
  total: number;
}

export interface ChatHistoryResponse {
  success: boolean;
  sessions: ChatHistory[];
  total: number;
  next_cursor?: string;
  has_more?: boolean;
}

export interface RecentActivitiesResponse {
  success: boolean;
  activities: RecentActivity[];
  total: number;
}

export interface ActivityStatsResponse {
  success: boolean;
  period: string;
  stats: ActivityStats;
}

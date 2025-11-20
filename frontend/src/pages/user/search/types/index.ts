
export type SearchType = 'hybrid' | 'vector_only' | 'keyword_only' | 'multimodal' | 'clip';

export interface SearchResult {
  file_id: string;
  title: string;  // 문서 제목 (필수)
  content_preview: string;
  similarity_score: number;
  match_type: string;
  container_id: string;
  container_name?: string;  // 컨테이너 이름
  container_path?: string;  // 컨테이너 경로
  container_icon?: string;
  file_path?: string;  // 파일 경로
  metadata?: {  // metadata를 선택적 필드로 유지
    document_id?: string;
    chunk_index?: number;
    keywords?: string[];
    proper_nouns?: string[];
    corp_names?: string[];
    document_type?: string;
    search_methods?: string[];
    scores?: any;
    last_updated?: string;
    file_name?: string;
    image_provider?: string;
    image_model?: string;
  };
  // 멀티모달 검색 추가 필드
  has_images?: boolean;
  image_count?: number;
  clip_score?: number;
  modality?: 'text' | 'image' | 'table';
  // 이미지 청크 관련 필드
  image_url?: string; // 이미지 URL (Azure Blob Storage)
  image_blob_key?: string; // Blob Storage 키
  chunk_id?: number; // 청크 ID
  // 파일 레벨 썸네일 (그룹화된 결과 표시용)
  thumbnail_blob_key?: string;
  thumbnail_chunk_id?: number;
}

export interface SearchFilters {
  searchType: SearchType;
  containerIds: string[];
  includeSubContainers: boolean; // 하위 컨테이너 포함 여부
  documentTypes: string[];
  dateRange: {
    start?: string;
    end?: string;
  };
  scoreThreshold: number;
}

// API로부터 받을 컨테이너 데이터 구조
export interface ContainerNode {
  id: string;
  name: string;
  children?: ContainerNode[];
  permissionLevel?: string; // 사용자 권한 레벨 (VIEWER, EDITOR, ADMIN, FULL_ACCESS)
  containerType?: string; // 컨테이너 타입
  accessLevel?: string; // 컨테이너 접근 레벨
  permissionSource?: string; // 권한 출처 (direct, role)
  hierarchyPath?: string; // 계층 경로 (예: /WJ_ROOT/WJ_CEO/WJ_HR)
}

// 검색 API 응답 타입
export interface SearchResponse {
  results?: SearchResult[];
  total_count?: number;
  search_time?: number;
  query?: string;
  filters_applied?: Partial<SearchFilters>;
}

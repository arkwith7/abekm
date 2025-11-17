/**
 * 문서 관리 서비스
 * 
 * 문서 유형, 업로드, 메타데이터 관리 관련 API
 */

import axios from 'axios';

/**
 * 문서 유형 정보
 */
export interface DocumentTypeInfo {
  id: string;
  name: string;
  description: string;
  icon: string;
  supported_formats: string[];
  default_options: Record<string, any>;
}

/**
 * 문서 유형 목록 응답
 */
export interface DocumentTypesResponse {
  success: boolean;
  document_types: DocumentTypeInfo[];
  total: number;
}

/**
 * 지원되는 모든 문서 유형 조회
 * 
 * @returns 문서 유형 목록
 */
export const getDocumentTypes = async (): Promise<DocumentTypesResponse> => {
  const response = await axios.get<DocumentTypesResponse>('/api/v1/documents/document-types');
  return response.data;
};

/**
 * 문서 업로드 옵션
 */
export interface DocumentUploadOptions {
  document_type?: string;
  processing_options?: Record<string, any>;
  use_multimodal?: boolean;
}

/**
 * 문서 업로드 (문서 유형 지원)
 * 
 * @param file 업로드할 파일
 * @param container_id 컨테이너 ID
 * @param options 업로드 옵션 (문서 유형, 처리 옵션)
 * @param metadata 문서 메타데이터
 * @param onProgress 업로드 진행률 콜백
 * @returns 업로드 결과
 */
export const uploadDocumentWithType = async (
  file: File,
  container_id: string,
  options: DocumentUploadOptions = {},
  metadata?: any,
  onProgress?: (progress: { file_name: string; progress: number; status: string }) => void
): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('container_id', container_id);

  // 문서 유형 및 처리 옵션 추가
  if (options.document_type) {
    formData.append('document_type', options.document_type);
  }

  if (options.processing_options) {
    formData.append('processing_options', JSON.stringify(options.processing_options));
  }

  if (options.use_multimodal !== undefined) {
    formData.append('use_multimodal', String(options.use_multimodal));
  }

  // 메타데이터 추가
  if (metadata) {
    if (metadata.title) formData.append('title', metadata.title);
    if (metadata.description) formData.append('description', metadata.description);
    if (metadata.keywords) formData.append('keywords', JSON.stringify(metadata.keywords));
    if (metadata.category) formData.append('category', metadata.category);
    if (metadata.author) formData.append('author', metadata.author);
    if (metadata.language) formData.append('language', metadata.language);
    if (metadata.security_level) formData.append('security_level', metadata.security_level);
    if (metadata.tags) formData.append('tags', JSON.stringify(metadata.tags));
  }

  const response = await axios.post(`/api/v1/documents/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress({
          file_name: file.name,
          progress,
          status: 'uploading'
        });
      }
    },
  });

  return response.data;
};

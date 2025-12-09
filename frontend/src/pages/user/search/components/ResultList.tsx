import { Image } from 'lucide-react';
import React from 'react';
import { getApiUrl } from '../../../../utils/apiConfig';
import { SearchResult } from '../types';

const TOKEN_STORAGE_KEYS = ['ABEKM_token', 'access_token', 'token'];

const resolveAuthToken = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  for (const key of TOKEN_STORAGE_KEYS) {
    try {
      const localValue = window.localStorage.getItem(key);
      if (localValue) {
        return localValue;
      }
    } catch (error) {
      console.warn('localStorage 접근 실패:', error);
    }

    try {
      const sessionValue = window.sessionStorage.getItem(key);
      if (sessionValue) {
        return sessionValue;
      }
    } catch (error) {
      console.warn('sessionStorage 접근 실패:', error);
    }
  }

  if (typeof document !== 'undefined' && document.cookie) {
    const cookies = document.cookie.split('; ');
    for (const key of TOKEN_STORAGE_KEYS) {
      const match = cookies.find((row) => row.startsWith(`${key}=`));
      if (match) {
        const value = match.substring(key.length + 1);
        if (value) {
          return decodeURIComponent(value);
        }
      }
    }
  }

  return null;
};

interface ResultListProps {
  results: SearchResult[];
  viewMode: 'list' | 'grid';
  selectedResults: Set<string>;
  onResultSelect: (id: string) => void;
  onFileView: (result: SearchResult) => void;
  onFileDownload: (result: SearchResult) => void;
}

const ResultItem: React.FC<{
  result: SearchResult;
  selected: boolean;
  onSelect: (id: string) => void;
  onFileView: (result: SearchResult) => void;
  onFileDownload: (result: SearchResult) => void;
}> = ({
  result,
  selected,
  onSelect,
  onFileView,
  onFileDownload,
}) => {
    const [imageError, setImageError] = React.useState(false);
    const [imageLoading, setImageLoading] = React.useState(true);
    const [imageBlobUrl, setImageBlobUrl] = React.useState<string | null>(null);

    // 이미지 청크인 경우
    const isImageChunk = result.modality === 'image';

    // 파일 레벨 썸네일이 있는 경우 (이미지 청크가 아니어도 표시)
    const hasThumbnail = Boolean(result.thumbnail_blob_key && result.thumbnail_chunk_id);

    const imageApiUrl = React.useMemo(() => {
      // 우선순위 1: 직접 제공된 이미지 URL
      if (result.image_url) {
        return result.image_url;
      }

      // 우선순위 2: 파일 레벨 썸네일 (thumbnail_chunk_id 사용)
      if (hasThumbnail && result.thumbnail_chunk_id) {
        return `/api/v1/documents/chunks/${result.thumbnail_chunk_id}/image`;
      }

      // 우선순위 3: 이미지 청크 자체
      if (isImageChunk && result.chunk_id) {
        return `/api/v1/documents/chunks/${result.chunk_id}/image`;
      }

      return null;
    }, [hasThumbnail, isImageChunk, result.chunk_id, result.image_url, result.thumbnail_chunk_id]);

    const shouldShowImage = Boolean(imageApiUrl) && (isImageChunk || hasThumbnail || Boolean(result.image_url));

    // 이미지 로드: fetch로 가져와서 Blob URL 생성 (Authorization 헤더 포함)
    React.useEffect(() => {
      let isMounted = true;
      let currentBlobUrl: string | null = null;
      const controller = new AbortController();

      if (!imageApiUrl) {
        setImageBlobUrl(null);
        setImageLoading(false);
        setImageError(false);
        return () => {
          isMounted = false;
          controller.abort();
        };
      }

      setImageLoading(true);
      setImageError(false);
      setImageBlobUrl(null);

      const fetchImage = async () => {
        try {
          const token = resolveAuthToken();
          const headers: Record<string, string> = {};
          if (token) {
            headers['Authorization'] = `Bearer ${token}`;
          }

          // 백엔드 API baseURL 추가 (프록시가 아닌 직접 호출)
          const baseUrl = getApiUrl() || '';
          const fullUrl = imageApiUrl.startsWith('http') ? imageApiUrl : `${baseUrl}${imageApiUrl}`;

          const response = await fetch(fullUrl, {
            headers,
            credentials: 'include',
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }

          const blob = await response.blob();
          if (!isMounted) {
            return;
          }

          currentBlobUrl = URL.createObjectURL(blob);
          setImageBlobUrl(currentBlobUrl);
          setImageLoading(false);
        } catch (error: any) {
          if (controller.signal.aborted) {
            return;
          }
          console.error('이미지 로드 실패:', error);
          if (!isMounted) {
            return;
          }
          setImageError(true);
          setImageLoading(false);
          setImageBlobUrl(null);
        }
      };

      fetchImage();

      // 클린업: Blob URL 해제 및 fetch 취소
      return () => {
        isMounted = false;
        controller.abort();
        if (currentBlobUrl) {
          URL.revokeObjectURL(currentBlobUrl);
        }
      };
    }, [imageApiUrl]);

    return (
      <div
        className={`bg-white rounded-lg shadow hover:shadow-md transition-shadow border ${selected ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
          }`}
      >
        <div className="p-6">
          {/* 결과 헤더 */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-start space-x-3 flex-1">
              <input
                type="checkbox"
                checked={selected}
                onChange={() => onSelect(result.file_id)}
                className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <div className="flex-1">
                <h3
                  className="text-lg font-semibold text-gray-900 line-clamp-2 hover:text-blue-600 cursor-pointer text-left"
                  onClick={() => onFileView(result)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onFileView(result);
                    }
                  }}
                  aria-label={`${result.title} 문서 보기`}
                >
                  {result.title}
                </h3>
                <div className="flex items-center flex-wrap gap-x-2 mt-1">
                  <span className="text-xs text-gray-600 flex items-center bg-blue-50 px-2 py-1 rounded-md">
                    {(() => {
                      const path = result.container_path || result.container_name || '📂 경로 없음';
                      // 디버깅용 로그 (개발 모드에서만)
                      if (process.env.NODE_ENV === 'development' && !result.container_path) {
                        console.warn('🚨 container_path 누락:', {
                          file_id: result.file_id,
                          title: result.title,
                          container_id: result.container_id,
                          container_name: result.container_name,
                          container_path: result.container_path,
                          full_result: result
                        });
                      }
                      return path;
                    })()}
                  </span>
                  <span className="text-xs text-gray-500">📄 {result.metadata?.document_type || 'Unknown'}</span>
                  <span className="text-xs text-gray-500">📊 {(result.similarity_score * 100).toFixed(1)}%</span>

                  {/* 멀티모달 메타데이터 뱃지 */}
                  {result.has_images && !isImageChunk && (
                    <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded-md flex items-center gap-1">
                      <Image className="w-3 h-3" />
                      {result.image_count || 0}
                    </span>
                  )}
                  {hasThumbnail && !isImageChunk && (
                    <span className="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded-md flex items-center gap-1">
                      🖼️ 썸네일
                    </span>
                  )}
                  {isImageChunk && (
                    <span className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded-md flex items-center gap-1">
                      🎨 이미지
                    </span>
                  )}
                  {result.modality === 'table' && (
                    <span className="text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded-md flex items-center gap-1">
                      📊 표
                    </span>
                  )}
                  {result.clip_score !== undefined && result.clip_score > 0 && (
                    (() => {
                      const provider = result.metadata?.image_provider as string | undefined;
                      const label = provider === 'bedrock' ? 'Marengo' : 'CLIP';
                      return (
                        <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-md">
                          🔍 {label} {(result.clip_score * 100).toFixed(0)}%
                        </span>
                      );
                    })()
                  )}
                </div>
              </div>
            </div>

            {/* 검색 방법 배지 */}
            <div className="flex flex-wrap gap-1 ml-2">
              {(result.metadata?.search_methods || []).map((method: string, idx: number) => (
                <span
                  key={idx}
                  className={`px-2 py-1 rounded-full text-xs font-medium ${method === 'vector' ? 'bg-purple-100 text-purple-700' :
                    method === 'keyword' ? 'bg-blue-100 text-blue-700' :
                      'bg-green-100 text-green-700'
                    }`}
                >
                  {method === 'vector' ? '🧠' : method === 'keyword' ? '🔤' : '📝'}
                </span>
              ))}
            </div>
          </div>

          {/* 썸네일 또는 이미지 청크 표시 */}
          {shouldShowImage && !imageError ? (
            <div className={`mb-4 relative rounded-lg overflow-hidden ${isImageChunk ? 'bg-gray-100' : 'bg-gray-50 border border-gray-200'
              }`}>
              {imageLoading && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              )}
              {imageBlobUrl && (
                <img
                  src={imageBlobUrl}
                  alt={hasThumbnail ? `${result.title} 썸네일` : result.title}
                  className={`w-full h-auto object-contain cursor-pointer hover:opacity-90 transition-opacity ${isImageChunk ? 'max-h-96' : 'max-h-48'
                    }`}
                  onClick={() => onFileView(result)}
                />
              )}
              {hasThumbnail && !isImageChunk && imageBlobUrl && (
                <div className="absolute bottom-2 right-2 bg-black bg-opacity-60 text-white text-xs px-2 py-1 rounded">
                  📸 미리보기
                </div>
              )}
            </div>
          ) : null}

          {/* 이미지 로딩 실패 시 대체 UI */}
          {shouldShowImage && imageError && (
            <div className="mb-4 bg-gray-100 rounded-lg p-8 flex flex-col items-center justify-center text-gray-500">
              <Image className="w-12 h-12 mb-2 text-gray-400" />
              <p className="text-sm">이미지를 불러올 수 없습니다</p>
              <p className="text-xs text-gray-400 mt-1">자세히 보기를 클릭하여 원본 문서를 확인하세요</p>
            </div>
          )}

          {/* 내용 미리보기 */}
          {/* 이미지 청크이면서 이미지가 정상 로드되지 않은 경우에만 텍스트 표시 */}
          {isImageChunk && !imageBlobUrl && !imageLoading && (
            <p className="text-gray-500 text-sm italic mb-4">
              {result.content_preview || '이미지 내용'}
            </p>
          )}
          {/* 이미지가 아닌 경우 내용 미리보기 표시 */}
          {!isImageChunk && (
            <p
              className="text-gray-700 text-sm line-clamp-3 mb-4"
              dangerouslySetInnerHTML={{ __html: result.content_preview }}
            />
          )}

          {/* 메타데이터 및 액션 버튼 */}
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>📄 {result.metadata?.file_name || result.title}</span>
            <div className="flex space-x-2">
              <button
                className="text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded px-2 py-1"
                onClick={() => onFileView(result)}
                aria-label={`${result.title} 자세히 보기`}
              >
                자세히 보기
              </button>
              <button
                className="text-green-600 hover:text-green-800 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 rounded px-2 py-1"
                onClick={() => onFileDownload(result)}
                aria-label={`${result.title} 다운로드`}
              >
                다운로드
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

const ResultList: React.FC<ResultListProps> = ({
  results,
  viewMode,
  selectedResults,
  onResultSelect,
  onFileView,
  onFileDownload
}) => {
  return (
    <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-4'}>
      {results.map((result, index) => {
        const itemKey = result.chunk_id
          ? `${result.file_id || 'unknown'}-${result.chunk_id}`
          : result.file_id ? `${result.file_id}-${index}` : `result-${index}`;

        return (
          <ResultItem
            key={itemKey}
            result={result}
            selected={selectedResults.has(result.file_id)}
            onSelect={onResultSelect}
            onFileView={onFileView}
            onFileDownload={onFileDownload}
          />
        );
      })}
    </div>
  );
};

export default ResultList;

import { Download, Maximize2, Minimize2, RotateCw, X, ZoomIn, ZoomOut } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Document } from '../../types/user.types';

interface FileViewerProps {
  isOpen: boolean;
  onClose: () => void;
  document: Document | null;
  onDownload?: (document: Document) => void;
}

const FileViewer: React.FC<FileViewerProps> = ({
  isOpen,
  onClose,
  document,
  onDownload
}) => {
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && document) {
      setIsLoading(true);
      setError(null);
      setZoom(100);
      setRotation(0);
      setIsFullscreen(false);

      // 초기 로딩 후 잠시 대기하여 컴포넌트가 렌더링되도록 함
      setTimeout(() => {
        setIsLoading(false);
      }, 100);
    }
  }, [isOpen, document]);

  if (!isOpen || !document) {
    return null;
  }

  const getFileExtension = (filename: string): string => {
    return filename.split('.').pop()?.toLowerCase() || '';
  };

  const getFileViewerUrl = (document: Document): string => {
    const baseUrl = '';
    const fileExt = document.file_extension?.toLowerCase() || '';

    // 토큰 가져오기 - 우선순위: wikl_token (최신) > access_token > token (오래된)
    let token = localStorage.getItem('wikl_token') ||
      localStorage.getItem('access_token') ||
      localStorage.getItem('token');

    // wikl_user 정보 확인하여 HR001 사용자인지 확인
    const wiklUser = localStorage.getItem('wikl_user');
    if (wiklUser) {
      try {
        const userData = JSON.parse(wiklUser);
        console.log('Current wikl_user:', userData);
        // HR001 사용자인 경우 wikl_token을 우선 사용
        if (userData.emp_no === 'HR001' || userData.username === 'hr.manager') {
          token = localStorage.getItem('wikl_token') || token;
        }
      } catch (e) {
        console.warn('Failed to parse wikl_user:', e);
      }
    }

    let url: string;

    // 템플릿 파일인지 확인 (container_path가 'templates'인 경우)
    if (document.container_path === 'templates') {
      // 템플릿 파일용 특별 엔드포인트 사용 (Query Parameter와 Header 모두 전달)
      url = `${baseUrl}/api/v1/chat/presentation/templates/${encodeURIComponent(document.id)}/file${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    } else if (['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'].includes(fileExt) || ['hwp', 'hwpx'].includes(fileExt)) {
      // Office 및 HWP/HWPX 파일은 office-to-pdf 엔드포인트 사용
      url = `${baseUrl}/api/files/office-to-pdf/${document.id}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    } else {
      // 다른 파일들은 iframe 전용 엔드포인트 사용 (Query Parameter 토큰 필수)
      url = `${baseUrl}/api/files/iframe-view/${document.id}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    }

    console.log('=== File Viewer URL Generation ===');
    console.log('Base URL:', baseUrl);
    console.log('Document ID:', document.id);
    console.log('Document file name:', document.file_name);
    console.log('Document container_path:', document.container_path);
    console.log('File extension:', fileExt);
    console.log('wikl_token:', localStorage.getItem('wikl_token') ? 'available' : 'not found');
    console.log('access_token:', localStorage.getItem('access_token') ? 'available' : 'not found');
    console.log('token:', localStorage.getItem('token') ? 'available' : 'not found');
    console.log('Selected token source:',
      token === localStorage.getItem('wikl_token') ? 'wikl_token' :
        token === localStorage.getItem('access_token') ? 'access_token' : 'token');
    console.log('Token available:', !!token);
    console.log('Token preview:', token ? token.substring(0, 50) + '...' : 'null');
    console.log('Final URL (iframe 전용 토큰 인증):', url);
    console.log('iframe에서 Query Parameter 토큰으로 인증 처리됩니다.');
    console.log('템플릿 파일 여부:', document.container_path === 'templates');
    console.log('===================================');
    return url;
  };

  // const getDownloadUrl = (document: Document): string => {
  //   const baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  //   const token = localStorage.getItem('token');
  //   const url = `${baseUrl}/api/files/download/${document.id}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  //   console.log('Download URL:', url);
  //   return url;
  // };

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 25, 300));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 25, 50));
  };

  const handleRotate = () => {
    setRotation(prev => (prev + 90) % 360);
  };

  const handleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const renderViewer = () => {
    const fileExt = getFileExtension(document.file_name || '');
    const fileUrl = getFileViewerUrl(document);

    console.log('Rendering viewer for:', {
      fileExt,
      fileUrl,
      documentId: document.id,
      fileName: document.file_name
    });

    switch (fileExt) {
      case 'pdf':
        return (
          <div className="w-full h-full">
            <iframe
              src={fileUrl}
              title={`PDF 뷰어 - ${document.file_name}`}
              className="w-full h-full border-0"
              style={{
                transform: `rotate(${rotation}deg)`,
                transformOrigin: 'center center'
              }}
              onLoad={(e) => {
                console.log('PDF iframe loaded successfully:', e);
                console.log('iframe src:', (e.target as HTMLIFrameElement).src);
                setIsLoading(false);
              }}
              onError={(e) => {
                console.error('PDF iframe error:', e);
                console.error('iframe src:', (e.target as HTMLIFrameElement).src);
                setIsLoading(false);
                setError('PDF 파일을 불러올 수 없습니다.');
              }}
              ref={(iframe) => {
                if (iframe) {
                  console.log('PDF iframe ref set, src:', iframe.src);
                  // iframe 로딩 상태 추가 체크
                  const checkLoaded = () => {
                    try {
                      console.log('iframe readyState:', iframe.contentDocument?.readyState);
                      if (iframe.contentDocument?.readyState === 'complete') {
                        console.log('iframe content loaded via readyState check');
                        setIsLoading(false);
                      }
                    } catch (err) {
                      console.log('Cannot access iframe content (CORS):', err);
                      // CORS로 인해 접근할 수 없는 경우도 정상 로딩으로 간주
                      setTimeout(() => setIsLoading(false), 2000);
                    }
                  };

                  iframe.addEventListener('load', checkLoaded);
                  // 백업 타이머
                  setTimeout(checkLoaded, 3000);
                }
              }}
            />
          </div>
        );

      case 'doc':
      case 'docx':
      case 'xls':
      case 'xlsx':
      case 'ppt':
      case 'pptx':
      case 'hwp':
      case 'hwpx':
        return (
          <div className="w-full h-full">
            {/* PDF로 변환하여 표시 */}
            <iframe
              src={getFileViewerUrl(document)}
              title={`문서 뷰어 - ${document.file_name}`}
              className="w-full h-full border-0"
              onLoad={(e) => {
                console.log('✅ iframe 로드 성공:', getFileViewerUrl(document));
                setIsLoading(false);
              }}
              onError={(e) => {
                console.error('❌ iframe 로드 실패:', getFileViewerUrl(document), e);
                setError('파일을 불러올 수 없습니다.');
              }}
            />
          </div>
        );

      case 'txt':
      case 'md':
      case 'log':
        return (
          <TextViewer
            fileUrl={fileUrl}
            zoom={zoom}
            onLoad={() => setIsLoading(false)}
            onError={(err) => {
              setIsLoading(false);
              setError(err);
            }}
          />
        );

      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'bmp':
      case 'webp':
        return (
          <div className="w-full h-full flex items-center justify-center bg-gray-100">
            <img
              src={fileUrl}
              alt={document.title}
              className="max-w-full max-h-full object-contain"
              style={{
                transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
                transformOrigin: 'center center'
              }}
              onLoad={() => setIsLoading(false)}
              onError={() => {
                setIsLoading(false);
                setError('이미지를 불러올 수 없습니다.');
              }}
            />
          </div>
        );

      default:
        return (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">📄</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                미리보기를 지원하지 않는 파일 형식입니다
              </h3>
              <p className="text-gray-600 mb-4">
                파일을 다운로드하여 확인해주세요.
              </p>
              {onDownload && (
                <button
                  onClick={() => onDownload(document)}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
                >
                  <Download className="w-4 h-4 mr-2" />
                  다운로드
                </button>
              )}
            </div>
          </div>
        );
    }
  };

  return (
    <div className={`fixed inset-0 bg-black bg-opacity-75 z-50 ${isFullscreen ? 'p-0' : 'p-4'}`}>
      <div className={`bg-white rounded-lg shadow-xl ${isFullscreen ? 'w-full h-full' : 'w-full h-full max-w-7xl mx-auto'} flex flex-col relative`}>
        {/* 모바일 및 비상 상황 대응용 부동 닫기 버튼 */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-30 p-2 text-gray-700 bg-white/90 shadow rounded-full hover:text-gray-900 hover:bg-white"
          title="닫기"
        >
          <X className="w-5 h-5" />
        </button>
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50 sticky top-0 z-20">
          <div className="flex items-center space-x-3">
            <h2 className="text-lg font-semibold text-gray-900 truncate">
              {document.title}
            </h2>
            <span className="text-sm text-gray-500">
              ({document.file_name})
            </span>
          </div>

          {/* 컨트롤 버튼들 */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleZoomOut}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
              title="축소"
            >
              <ZoomOut className="w-4 h-4" />
            </button>

            <span className="text-sm text-gray-600 px-2">
              {zoom}%
            </span>

            <button
              onClick={handleZoomIn}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
              title="확대"
            >
              <ZoomIn className="w-4 h-4" />
            </button>

            <button
              onClick={handleRotate}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
              title="회전"
            >
              <RotateCw className="w-4 h-4" />
            </button>

            <button
              onClick={handleFullscreen}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
              title={isFullscreen ? "원본 크기" : "전체화면"}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            {onDownload && (
              <button
                onClick={() => onDownload(document)}
                className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
                title="다운로드"
              >
                <Download className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={onClose}
              className="hidden md:inline-flex p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
              title="닫기"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 뷰어 영역 */}
        <div className="flex-1 relative overflow-hidden">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">파일을 불러오는 중...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
              <div className="text-center">
                <div className="text-6xl mb-4">⚠️</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">오류 발생</h3>
                <p className="text-gray-600 mb-4">{error}</p>
                {onDownload && (
                  <button
                    onClick={() => onDownload(document)}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    다운로드
                  </button>
                )}
              </div>
            </div>
          )}

          {(() => {
            console.log('=== Viewer Rendering Check ===');
            console.log('isLoading:', isLoading);
            console.log('error:', error);
            console.log('Will render viewer:', !isLoading && !error);
            console.log('===============================');
            return !isLoading && !error && renderViewer();
          })()}
        </div>
      </div>
    </div>
  );
};

// 텍스트 파일 뷰어 컴포넌트
interface TextViewerProps {
  fileUrl: string;
  zoom: number;
  onLoad: () => void;
  onError: (error: string) => void;
}

const TextViewer: React.FC<TextViewerProps> = ({ fileUrl, zoom, onLoad, onError }) => {
  const [content, setContent] = useState<string>('');

  useEffect(() => {
    const token = localStorage.getItem('access_token') ||
      localStorage.getItem('wikl_token') ||
      localStorage.getItem('token');
    const headers: HeadersInit = {};

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(fileUrl, { headers })
      .then(response => {
        if (!response.ok) {
          throw new Error('파일을 불러올 수 없습니다.');
        }
        return response.text();
      })
      .then(text => {
        setContent(text);
        onLoad();
      })
      .catch(err => {
        onError(err.message);
      });
  }, [fileUrl, onLoad, onError]);

  return (
    <div className="w-full h-full p-4 bg-white overflow-auto">
      <pre
        className="whitespace-pre-wrap font-mono text-sm text-gray-900"
        style={{ fontSize: `${zoom}%` }}
      >
        {content}
      </pre>
    </div>
  );
};

export default FileViewer;

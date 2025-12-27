import { Download, ExternalLink, FileText, Maximize2, Minimize2, RotateCw, X, ZoomIn, ZoomOut } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Document } from '../../types/user.types';
import { getApiUrl } from '../../utils/apiConfig';

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
    // API base URL은 공용 유틸을 사용 (REACT_APP_API_URL=/api 같은 설정도 안전하게 정규화)
    // 빈 값이면 상대 경로(/api/...)로 동작하며 nginx 또는 setupProxy가 처리
    const baseUrl = getApiUrl();
    const fileExt = document.file_extension?.toLowerCase() || '';

    // 토큰 가져오기 - 우선순위: ABEKM_token (최신) > access_token > token (오래된)
    let token = localStorage.getItem('ABEKM_token') ||
      localStorage.getItem('access_token') ||
      localStorage.getItem('token');

    // ABEKM_user 정보 확인하여 HR001 사용자인지 확인
    const ABEKMUser = localStorage.getItem('ABEKM_user');
    if (ABEKMUser) {
      try {
        const userData = JSON.parse(ABEKMUser);
        console.log('Current ABEKM_user:', userData);
        // HR001 사용자인 경우 ABEKM_token을 우선 사용
        if (userData.emp_no === 'HR001' || userData.username === 'hr.manager') {
          token = localStorage.getItem('ABEKM_token') || token;
        }
      } catch (e) {
        console.warn('Failed to parse ABEKM_user:', e);
      }
    }

    let url: string;

    // ⚠️ S3 URL도 직접 열면 AccessDenied가 발생할 수 있으므로(버킷 private),
    // 항상 백엔드 iframe-view 엔드포인트를 통해 presigned URL로 리다이렉트 받도록 한다.

    // 템플릿 파일인지 확인 (container_path가 'templates'인 경우)
    if (document.container_path === 'templates') {
      // 템플릿 파일용 특별 엔드포인트 사용 (Query Parameter와 Header 모두 전달)
      url = `${baseUrl}/api/v1/agent/presentation/templates/${encodeURIComponent(document.id)}/file${token ? `?token=${encodeURIComponent(token)}` : ''}`;
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
    console.log('ABEKM_token:', localStorage.getItem('ABEKM_token') ? 'available' : 'not found');
    console.log('access_token:', localStorage.getItem('access_token') ? 'available' : 'not found');
    console.log('token:', localStorage.getItem('token') ? 'available' : 'not found');
    console.log('Selected token source:',
      token === localStorage.getItem('ABEKM_token') ? 'ABEKM_token' :
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
    // 검색 화면에서는 file_name에 확장자가 없는 경우가 많아서 file_extension을 우선 사용
    const fileExt = (document.file_extension?.toLowerCase() || getFileExtension(document.file_name || '')).toLowerCase();
    const fileUrl = getFileViewerUrl(document);

    console.log('Rendering viewer for:', {
      fileExt,
      fileUrl,
      documentId: document.id,
      fileName: document.file_name
    });

    // 특허 URL(.url) 문서는 링크 전용 뷰어 제공 (PDF는 기존 뷰어 유지)
    const isPatentUrl =
      fileExt === 'url' ||
      (document.document_type === 'patent' && fileExt !== 'pdf') ||
      (typeof document.path === 'string' && document.path.includes('patents.google.com'));
    if (isPatentUrl) {
      const fileName = document.file_name || '';
      const path = document.path || '';
      // 출원번호 추출 우선순위:
      // 1) file_name에 .url이 있으면 그 앞의 숫자
      // 2) URL(q=KR...)에서 숫자 추출
      // 3) 파일명에서 숫자 덩어리 추출
      let applicationNumber = '';
      const m1 = fileName.match(/(\d{10,})/);
      if (fileName.toLowerCase().endsWith('.url')) {
        applicationNumber = fileName.replace(/\.url$/i, '');
      } else if (path) {
        const m2 = path.match(/KR(\d{10,})/i) || path.match(/(\d{10,})/);
        if (m2 && m2[1]) applicationNumber = m2[1];
      }
      if (!applicationNumber && m1 && m1[1]) applicationNumber = m1[1];

      const googlePatentsUrl = `https://patents.google.com/?q=KR${applicationNumber}`;
      
      // KIPRIS 원문 PDF 프록시 URL (백엔드 API 경유)
      const token = localStorage.getItem('ABEKM_token') || localStorage.getItem('access_token') || '';
      const kiprisPdfUrl = `${getApiUrl()}/api/files/patent-fulltext/${applicationNumber}?token=${encodeURIComponent(token)}`;

      return (
        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
          <div className="text-center max-w-2xl mx-auto p-8">
            {/* 특허 아이콘 */}
            <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg">
              <FileText className="w-10 h-10 text-white" />
            </div>
            
            {/* 특허 제목 */}
            <h2 className="text-xl font-bold text-gray-900 mb-4 leading-relaxed">
              {document.title || '특허 문서'}
            </h2>
            
            {/* 출원번호 */}
            <div className="inline-flex items-center px-4 py-2 bg-white rounded-full shadow-sm mb-6">
              <span className="text-sm text-gray-500 mr-2">출원번호:</span>
              <span className="text-sm font-mono font-semibold text-blue-600">KR{applicationNumber}</span>
            </div>
            
            {/* 안내 메시지 */}
            <p className="text-gray-600 mb-6">
              특허 원문을 확인할 수 있습니다.
            </p>
            
            {/* 버튼들 */}
            <div className="flex flex-row justify-center gap-4 mb-6">
              <a
                href={kiprisPdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center px-6 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors shadow-lg"
              >
                <FileText className="w-5 h-5 mr-2" />
                KIPRIS 원문 PDF
              </a>
              <a
                href={googlePatentsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors shadow-lg"
              >
                <ExternalLink className="w-5 h-5 mr-2" />
                Google Patents
              </a>
            </div>
            
            {/* 추가 안내 */}
            <div className="p-4 bg-white/60 rounded-lg text-sm text-gray-500 border border-gray-100">
              <p>📄 KIPRIS 원문 PDF에서 한글 공개공보를,</p>
              <p className="mt-1">Google Patents에서 영문 번역본을 확인할 수 있습니다.</p>
            </div>
          </div>
        </div>
      );
    }

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
      localStorage.getItem('ABEKM_token') ||
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

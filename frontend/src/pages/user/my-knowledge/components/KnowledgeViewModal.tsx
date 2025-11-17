import React from 'react';
import { X, Download, Edit, Trash2, Eye, Calendar, User, Folder, Tag, FileText, Info } from 'lucide-react';
import { Document } from '../../../../types/user.types';

interface KnowledgeViewModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: Document | null;
  onEdit?: (document: Document) => void;
  onDelete?: (documentId: string) => void;
  onDownload?: (document: Document) => void;
  canEdit?: boolean;
}

const KnowledgeViewModal: React.FC<KnowledgeViewModalProps> = ({
  isOpen,
  onClose,
  document,
  onEdit,
  onDelete,
  onDownload,
  canEdit = false
}) => {
  if (!isOpen || !document) return null;

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getFileIcon = (fileType: string): string => {
    switch (fileType.toLowerCase()) {
      case 'pdf': return '📄';
      case 'doc':
      case 'docx': return '📝';
      case 'xls':
      case 'xlsx': return '📊';
      case 'ppt':
      case 'pptx': return '📈';
      case 'txt': return '📃';
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif': return '🖼️';
      default: return '📄';
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-10 mx-auto p-5 border w-11/12 max-w-4xl shadow-lg rounded-md bg-white mb-10">
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center">
            <div className="text-4xl mr-4">
              {getFileIcon(document.file_extension || '')}
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900">{document.title}</h3>
              <p className="text-sm text-gray-600 mt-1">{document.file_name}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {onDownload && (
              <button
                onClick={() => onDownload(document)}
                className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <Download className="w-4 h-4 mr-2" />
                다운로드
              </button>
            )}
            {canEdit && onEdit && (
              <button
                onClick={() => onEdit(document)}
                className="inline-flex items-center px-3 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
              >
                <Edit className="w-4 h-4 mr-2" />
                편집
              </button>
            )}
            {canEdit && onDelete && (
              <button
                onClick={() => {
                  if (window.confirm('정말로 이 지식을 삭제하시겠습니까?')) {
                    onDelete(document.id);
                    onClose();
                  }
                }}
                className="inline-flex items-center px-3 py-2 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                삭제
              </button>
            )}
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 메인 컨텐츠 */}
          <div className="lg:col-span-2 space-y-6">
            {/* 설명 */}
            {document.description && (
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2 flex items-center">
                  <FileText className="w-4 h-4 mr-2" />
                  설명
                </h4>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">
                  {document.description}
                </p>
              </div>
            )}

            {/* 태그 */}
            {document.tags && document.tags.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2 flex items-center">
                  <Tag className="w-4 h-4 mr-2" />
                  태그
                </h4>
                <div className="flex flex-wrap gap-2">
                  {document.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 컨텐츠 미리보기 */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-900 mb-2 flex items-center">
                <Eye className="w-4 h-4 mr-2" />
                미리보기
              </h4>
              <div className="bg-white border border-gray-200 rounded-md p-4 min-h-[200px] flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <div className="text-6xl mb-2">
                    {getFileIcon(document.file_extension || '')}
                  </div>
                  <p className="text-sm">
                    {document.file_extension?.toUpperCase()} 파일
                  </p>
                  <p className="text-xs mt-1">
                    미리보기를 지원하지 않는 파일 형식입니다.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* 사이드바 정보 */}
          <div className="space-y-4">
            {/* 파일 정보 */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <Info className="w-4 h-4 mr-2" />
                파일 정보
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">크기:</span>
                  <span className="text-gray-900">
                    {formatFileSize(document.file_size || 0)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">형식:</span>
                  <span className="text-gray-900">
                    {document.file_extension?.toUpperCase() || 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">상태:</span>
                  <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                    완료
                  </span>
                </div>
                {document.is_public !== undefined && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">공개:</span>
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      document.is_public 
                        ? 'bg-blue-100 text-blue-800' 
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {document.is_public ? '공개' : '비공개'}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* 위치 정보 */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <Folder className="w-4 h-4 mr-2" />
                위치
              </h4>
              <div className="text-sm">
                <p className="text-gray-700 break-words">
                  {document.container_path || '컨테이너 미지정'}
                </p>
              </div>
            </div>

            {/* 생성 정보 */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <Calendar className="w-4 h-4 mr-2" />
                생성 정보
              </h4>
              <div className="space-y-2 text-sm">
                <div>
                  <span className="text-gray-600 block">등록자:</span>
                  <div className="flex items-center mt-1">
                    <User className="w-4 h-4 mr-2 text-gray-400" />
                    <span className="text-gray-900">
                      {document.uploaded_by || 'Unknown'}
                    </span>
                  </div>
                </div>
                <div>
                  <span className="text-gray-600 block">등록일:</span>
                  <span className="text-gray-900">
                    {document.created_at ? formatDate(document.created_at) : 'N/A'}
                  </span>
                </div>
                {document.updated_at && document.updated_at !== document.created_at && (
                  <div>
                    <span className="text-gray-600 block">수정일:</span>
                    <span className="text-gray-900">
                      {formatDate(document.updated_at)}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* 통계 정보 */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">활동</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">조회수:</span>
                  <span className="text-gray-900">
                    {document.view_count || 0}회
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">다운로드:</span>
                  <span className="text-gray-900">
                    {document.download_count || 0}회
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeViewModal;

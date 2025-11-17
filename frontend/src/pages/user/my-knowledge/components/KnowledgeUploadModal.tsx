import { Folder, FolderOpen, Plus, Upload, X } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { DocumentTypeInfo, getDocumentTypes } from '../../../../services/documentService';
import { KnowledgeContainer } from './KnowledgeContainerTree';

interface DocumentMetadata {
  title: string;
  description: string;
  keywords: string[];
  document_type: string;  // ✅ category → document_type 변경
  processing_options?: Record<string, any>;  // ✅ 추가
  author: string;
  language: string;
  security_level: string;
  tags: string[];
}

interface KnowledgeUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (files: File[], container: string, metadata: DocumentMetadata[]) => void;
  containers: KnowledgeContainer[];
  selectedContainer?: KnowledgeContainer | null;
  selectedFiles: File[];
  onFileSelect: (files: File[]) => void;
}

const KnowledgeUploadModal: React.FC<KnowledgeUploadModalProps> = ({
  isOpen,
  onClose,
  onUpload,
  containers,
  selectedContainer,
  selectedFiles,
  onFileSelect
}) => {
  const [uploadTargetContainer, setUploadTargetContainer] = useState(
    selectedContainer?.id || ''
  );
  const [showContainerSelector, setShowContainerSelector] = useState(false);

  // 각 파일별 메타데이터 상태
  const [filesMetadata, setFilesMetadata] = useState<{ [key: string]: DocumentMetadata }>({});

  // ✅ 문서 유형 목록 상태
  const [documentTypes, setDocumentTypes] = useState<DocumentTypeInfo[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(true);

  // 기본 메타데이터 템플릿
  const defaultMetadata: DocumentMetadata = useMemo(() => ({
    title: '',
    description: '',
    keywords: [],
    document_type: 'general',  // ✅ category → document_type, 'general'로 기본값
    processing_options: {},  // ✅ 추가
    author: '',
    language: 'ko',
    security_level: 'PUBLIC',
    tags: []
  }), []);

  // ✅ 문서 유형 목록 로드
  useEffect(() => {
    const fetchDocumentTypes = async () => {
      try {
        setLoadingTypes(true);
        const response = await getDocumentTypes();
        setDocumentTypes(response.document_types);
      } catch (error) {
        console.error('문서 유형 로드 실패:', error);
        // 실패 시 기본 유형만 제공
        setDocumentTypes([
          {
            id: 'general',
            name: '일반 문서',
            description: '기타 일반 문서',
            icon: '📄',
            supported_formats: ['pdf', 'docx', 'txt'],
            default_options: {}
          }
        ]);
      } finally {
        setLoadingTypes(false);
      }
    };

    if (isOpen) {
      fetchDocumentTypes();
    }
  }, [isOpen]);

  React.useEffect(() => {
    if (selectedContainer) {
      setUploadTargetContainer(selectedContainer.id);
      setShowContainerSelector(false);
    }
  }, [selectedContainer]);

  // 파일이 변경될 때 메타데이터 초기화
  React.useEffect(() => {
    const newMetadata: { [key: string]: DocumentMetadata } = {};
    selectedFiles.forEach(file => {
      if (!filesMetadata[file.name]) {
        newMetadata[file.name] = {
          ...defaultMetadata,
          title: file.name.replace(/\.[^/.]+$/, ''), // 확장자 제거한 파일명을 기본 제목으로
          author: '현재사용자' // 실제로는 로그인된 사용자 정보를 사용
        };
      } else {
        newMetadata[file.name] = filesMetadata[file.name];
      }
    });
    setFilesMetadata(newMetadata);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFiles, defaultMetadata]); // filesMetadata 제거

  const updateFileMetadata = (fileName: string, field: keyof DocumentMetadata, value: any) => {
    setFilesMetadata(prev => ({
      ...prev,
      [fileName]: {
        ...prev[fileName],
        [field]: value
      }
    }));
  };

  const handleUpload = () => {
    if (selectedFiles.length === 0 || !uploadTargetContainer) return;

    const metadataArray = selectedFiles.map(file => filesMetadata[file.name] || defaultMetadata);
    onUpload(selectedFiles, uploadTargetContainer, metadataArray);
    onClose();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (fileName: string): string => {
    const extension = fileName.split('.').pop()?.toLowerCase() || '';
    switch (extension) {
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

  // 컨테이너 계층 경로 생성 함수
  const getContainerPath = (container: KnowledgeContainer, allContainers: KnowledgeContainer[]): string => {
    const findContainerById = (containers: KnowledgeContainer[], id: string): KnowledgeContainer | null => {
      for (const cont of containers) {
        if (cont.id === id) return cont;
        if (cont.children) {
          const found = findContainerById(cont.children, id);
          if (found) return found;
        }
      }
      return null;
    };

    // 컨테이너 이름에서 이모티콘 제거하는 함수
    const cleanContainerName = (name: string): string => {
      if (typeof name !== 'string') return '';
      return name
        .replace(/[📁🏢📂🗂️📊📈📉📋📌📍📎📏📐📑📒📓📔📕📖📗📘📙📚]/g, '')
        .replace(/[\uD83C-\uDBFF\uDC00-\uDFFF]+/g, '')
        .replace(/[\u2600-\u27BF]/g, '')
        .replace(/^\s+/, '')
        .replace(/\s+$/, '')
        .trim();
    };

    const buildPath = (cont: KnowledgeContainer): string[] => {
      const path = [cleanContainerName(cont.name)];
      if (cont.parent_id) {
        const parent = findContainerById(allContainers, cont.parent_id);
        if (parent) {
          path.unshift(...buildPath(parent));
        }
      }
      return path;
    };

    return buildPath(container).join('/');
  };

  // 컨테이너 경로를 아이콘과 함께 렌더링하는 함수
  const renderContainerPathWithIcons = (container: KnowledgeContainer, isTarget: boolean = false) => {
    const pathParts = getContainerPath(container, containers).split('/');

    return (
      <div className="flex items-center space-x-1">
        {pathParts.map((part, index) => (
          <React.Fragment key={index}>
            {index > 0 && <span className="text-gray-400">/</span>}
            <div className="flex items-center space-x-1">
              {index === pathParts.length - 1 && isTarget ? (
                <FolderOpen className="w-4 h-4 text-blue-600" />
              ) : (
                <Folder className="w-4 h-4 text-gray-500" />
              )}
              <span className={`text-sm ${index === pathParts.length - 1 && isTarget
                ? 'font-medium text-blue-900'
                : 'text-gray-700'
                }`}>
                {part}
              </span>
            </div>
          </React.Fragment>
        ))}
      </div>
    );
  };

  const renderContainerOptions = (containers: KnowledgeContainer[], level = 0): JSX.Element[] => {
    const options: JSX.Element[] = [];

    containers.forEach(container => {
      if (container.permission === 'OWNER' || container.permission === 'EDITOR') {
        const containerPath = getContainerPath(container, containers);
        options.push(
          <option key={container.id} value={container.id}>
            {'  '.repeat(level) + containerPath}
          </option>
        );

        if (container.children && container.children.length > 0) {
          options.push(...renderContainerOptions(container.children, level + 1));
        }
      }
    });

    return options;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-11/12 max-w-2xl shadow-lg rounded-md bg-white">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">지식 업로드</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="mb-4">
          {selectedContainer && !showContainerSelector ? (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                업로드 대상 컨테이너
              </label>
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  {/* 컨테이너 계층 경로 */}
                  <div className="mb-2">
                    {renderContainerPathWithIcons(selectedContainer, true)}
                  </div>
                  {/* 권한 및 문서 개수 정보 */}
                  <div className="text-sm text-gray-600">
                    <span className="inline-flex items-center">
                      권한: <span className="ml-1 font-medium text-blue-700">
                        {selectedContainer.permission === 'OWNER' ? '소유자' : '편집자'}
                      </span>
                    </span>
                    {selectedContainer.document_count !== undefined && (
                      <span className="ml-3 inline-flex items-center">
                        문서: <span className="ml-1 font-medium">{selectedContainer.document_count}개</span>
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => setShowContainerSelector(true)}
                  className="ml-4 text-sm text-blue-600 hover:text-blue-800 underline flex-shrink-0"
                >
                  변경
                </button>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                업로드할 컨테이너 선택
              </label>
              <select
                value={uploadTargetContainer}
                onChange={(e) => setUploadTargetContainer(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">업로드 권한이 있는 컨테이너를 선택하세요</option>
                {renderContainerOptions(containers)}
              </select>

              {/* 선택된 컨테이너 미리보기 */}
              {uploadTargetContainer && (
                <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-md">
                  <div className="text-sm text-gray-600 mb-1">선택된 컨테이너:</div>
                  {(() => {
                    const findSelectedContainer = (containers: KnowledgeContainer[]): KnowledgeContainer | null => {
                      for (const container of containers) {
                        if (container.id === uploadTargetContainer) return container;
                        if (container.children) {
                          const found = findSelectedContainer(container.children);
                          if (found) return found;
                        }
                      }
                      return null;
                    };
                    const selectedCont = findSelectedContainer(containers);
                    return selectedCont ? renderContainerPathWithIcons(selectedCont, true) : null;
                  })()}
                </div>
              )}

              {/* 선택 완료 버튼 */}
              {uploadTargetContainer && (
                <div className="mt-3">
                  <button
                    onClick={() => setShowContainerSelector(false)}
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
                  >
                    선택 완료
                  </button>
                </div>
              )}

              {selectedContainer && (
                <div className="mt-2 flex justify-between items-center">
                  <p className="text-sm text-gray-500">
                    이전 선택: {selectedContainer.name}
                  </p>
                  <button
                    onClick={() => {
                      setUploadTargetContainer(selectedContainer.id);
                      setShowContainerSelector(false);
                    }}
                    className="text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    되돌리기
                  </button>
                </div>
              )}
              {uploadTargetContainer === '' && (
                <p className="mt-1 text-sm text-red-500">
                  ⚠️ 업로드할 컨테이너를 선택해야 합니다
                </p>
              )}
            </div>
          )}
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            선택된 파일 및 정보 입력 ({selectedFiles.length}개)
          </label>

          {selectedFiles.length === 0 ? (
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600 mb-2">파일을 선택해주세요</p>
              <input
                type="file"
                multiple
                onChange={(e) => onFileSelect(Array.from(e.target.files || []))}
                className="hidden"
                id="file-upload"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif"
              />
              <label
                htmlFor="file-upload"
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer"
              >
                <Plus className="w-4 h-4 mr-2" />
                파일 선택
              </label>
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-md">
              {selectedFiles.map((file, index) => {
                const metadata = filesMetadata[file.name] || defaultMetadata;
                return (
                  <div key={index} className="p-4 border-b border-gray-100 last:border-b-0">
                    {/* 파일 정보 헤더 */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center">
                        <span className="text-lg mr-2">{getFileIcon(file.name)}</span>
                        <div>
                          <p className="text-sm font-medium text-gray-900">{file.name}</p>
                          <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => onFileSelect(selectedFiles.filter((_, i) => i !== index))}
                        className="text-red-600 hover:text-red-800"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    {/* 메타데이터 입력 폼 */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-gray-50 p-3 rounded">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">문서 제목*</label>
                        <input
                          type="text"
                          value={metadata.title}
                          onChange={(e) => updateFileMetadata(file.name, 'title', e.target.value)}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="문서 제목을 입력하세요"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          문서 유형 {loadingTypes && <span className="text-gray-400 text-xs">(로딩 중...)</span>}
                        </label>
                        <select
                          value={metadata.document_type}
                          onChange={(e) => {
                            const selectedType = documentTypes.find(t => t.id === e.target.value);
                            updateFileMetadata(file.name, 'document_type', e.target.value);
                            if (selectedType) {
                              updateFileMetadata(file.name, 'processing_options', selectedType.default_options);
                            }
                          }}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                          disabled={loadingTypes}
                        >
                          {documentTypes.map((docType) => (
                            <option key={docType.id} value={docType.id}>
                              {docType.icon} {docType.name}
                            </option>
                          ))}
                        </select>
                        {metadata.document_type && metadata.document_type !== 'general' && (
                          <p className="mt-1 text-xs text-gray-500">
                            {documentTypes.find(t => t.id === metadata.document_type)?.description}
                          </p>
                        )}
                      </div>

                      <div className="md:col-span-2">
                        <label className="block text-xs font-medium text-gray-700 mb-1">문서 설명</label>
                        <textarea
                          value={metadata.description}
                          onChange={(e) => updateFileMetadata(file.name, 'description', e.target.value)}
                          rows={2}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="문서에 대한 간단한 설명을 입력하세요"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">키워드 (쉼표로 구분)</label>
                        <input
                          type="text"
                          value={metadata.keywords.join(', ')}
                          onChange={(e) => updateFileMetadata(file.name, 'keywords', e.target.value.split(',').map(k => k.trim()).filter(k => k))}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="예: 인사, 평가, 가이드라인"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">보안 등급</label>
                        <select
                          value={metadata.security_level}
                          onChange={(e) => updateFileMetadata(file.name, 'security_level', e.target.value)}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                          <option value="PUBLIC">공개</option>
                          <option value="INTERNAL">내부용</option>
                          <option value="CONFIDENTIAL">기밀</option>
                          <option value="RESTRICTED">제한</option>
                        </select>
                      </div>
                    </div>
                  </div>
                );
              })}

              <div className="p-3 border-t border-gray-200 bg-gray-50">
                <input
                  type="file"
                  multiple
                  onChange={(e) => onFileSelect([...selectedFiles, ...Array.from(e.target.files || [])])}
                  className="hidden"
                  id="additional-file-upload"
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif"
                />
                <label
                  htmlFor="additional-file-upload"
                  className="inline-flex items-center px-3 py-1 border border-gray-300 rounded text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  파일 추가
                </label>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            취소
          </button>
          <button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || !uploadTargetContainer ||
              selectedFiles.some(file => !filesMetadata[file.name]?.title?.trim())}
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            업로드 시작 ({selectedFiles.length}개 파일)
          </button>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeUploadModal;

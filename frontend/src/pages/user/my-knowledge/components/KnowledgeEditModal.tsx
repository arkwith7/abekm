import React, { useState, useEffect } from 'react';
import { X, Save, FileText, Tag, Folder } from 'lucide-react';
import { Document } from '../../../../types/user.types';
import { KnowledgeContainer } from './KnowledgeContainerTree';

interface KnowledgeEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (documentId: string, updates: Partial<Document>) => void;
  document: Document | null;
  containers: KnowledgeContainer[];
}

const KnowledgeEditModal: React.FC<KnowledgeEditModalProps> = ({
  isOpen,
  onClose,
  onSave,
  document,
  containers
}) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    tags: '',
    container_path: '',
    is_public: false
  });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (document) {
      setFormData({
        title: document.title || '',
        description: document.description || '',
        tags: document.tags ? document.tags.join(', ') : '',
        container_path: document.container_path || '',
        is_public: document.is_public || false
      });
    }
  }, [document]);

  const handleSave = async () => {
    if (!document) return;
    
    setIsSaving(true);
    try {
      const updates: Partial<Document> = {
        title: formData.title.trim(),
        description: formData.description.trim(),
        tags: formData.tags.split(',').map(tag => tag.trim()).filter(tag => tag),
        container_path: formData.container_path,
        is_public: formData.is_public
      };
      
      await onSave(document.id, updates);
      onClose();
    } catch (error) {
      console.error('Error saving document:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const renderContainerOptions = (containers: KnowledgeContainer[], level = 0): JSX.Element[] => {
    const options: JSX.Element[] = [];
    
    containers.forEach(container => {
      if (container.permission === 'OWNER' || container.permission === 'EDITOR') {
        options.push(
          <option key={container.id} value={container.path}>
            {'  '.repeat(level) + container.name}
          </option>
        );
        
        if (container.children && container.children.length > 0) {
          options.push(...renderContainerOptions(container.children, level + 1));
        }
      }
    });
    
    return options;
  };

  if (!isOpen || !document) return null;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-11/12 max-w-3xl shadow-lg rounded-md bg-white">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-medium text-gray-900">지식 편집</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <div className="space-y-6">
          {/* 기본 정보 섹션 */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
              <FileText className="w-4 h-4 mr-2" />
              기본 정보
            </h4>
            
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  제목 *
                </label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="지식의 제목을 입력하세요"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  설명
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="지식에 대한 설명을 입력하세요"
                />
              </div>
            </div>
          </div>

          {/* 분류 및 태그 섹션 */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
              <Tag className="w-4 h-4 mr-2" />
              분류 및 태그
            </h4>
            
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  태그
                </label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="태그를 쉼표로 구분하여 입력하세요 (예: 기술문서, 매뉴얼, 가이드)"
                />
                <p className="mt-1 text-sm text-gray-500">
                  쉼표(,)로 구분하여 여러 태그를 입력할 수 있습니다.
                </p>
              </div>
            </div>
          </div>

          {/* 위치 및 권한 섹션 */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
              <Folder className="w-4 h-4 mr-2" />
              위치 및 권한
            </h4>
            
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  컨테이너 *
                </label>
                <select
                  value={formData.container_path}
                  onChange={(e) => setFormData(prev => ({ ...prev, container_path: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">컨테이너를 선택하세요</option>
                  {renderContainerOptions(containers)}
                </select>
              </div>
              
              <div>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.is_public}
                    onChange={(e) => setFormData(prev => ({ ...prev, is_public: e.target.checked }))}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="ml-2 text-sm text-gray-700">
                    공개 지식으로 설정 (다른 사용자도 볼 수 있습니다)
                  </span>
                </label>
              </div>
            </div>
          </div>

          {/* 파일 정보 섹션 (읽기 전용) */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3">파일 정보</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">파일명:</span>
                <span className="ml-2 text-gray-900">{document.file_name}</span>
              </div>
              <div>
                <span className="text-gray-600">크기:</span>
                <span className="ml-2 text-gray-900">
                  {document.file_size ? `${(document.file_size / 1024 / 1024).toFixed(2)} MB` : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-gray-600">확장자:</span>
                <span className="ml-2 text-gray-900">{document.file_extension}</span>
              </div>
              <div>
                <span className="text-gray-600">등록일:</span>
                <span className="ml-2 text-gray-900">
                  {document.created_at ? new Date(document.created_at).toLocaleDateString('ko-KR') : 'N/A'}
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex items-center justify-end space-x-3 mt-6 pt-6 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !formData.title.trim() || !formData.container_path}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                저장 중...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                저장
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeEditModal;

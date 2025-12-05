import axios from 'axios';
import {
  AlertTriangle,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  Image,
  Info,
  MoreVertical,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Star,
  Trash2,
  Upload,
  X
} from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { authService } from '../../services/authService';

// Axios 인스턴스 생성
const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// JWT 토큰 자동 추가
api.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 에러 처리
authService.setupResponseInterceptor(api);

// 템플릿 타입 정의
interface PPTTemplate {
  id: string;
  name: string;
  type: 'built-in' | 'user-uploaded';
  slideCount?: number;
  isDefault?: boolean;
  uploadedAt?: string;
  thumbnailUrl?: string;
  metadata?: {
    slides?: Array<{
      index: number;
      role: string;
      thumbnail?: string;
    }>;
  };
}

// 슬라이드 미리보기 모달
const SlidePreviewModal: React.FC<{
  template: PPTTemplate | null;
  isOpen: boolean;
  onClose: () => void;
}> = ({ template, isOpen, onClose }) => {
  const [slides, setSlides] = useState<Array<{ index: number; url: string; role: string }>>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (template && isOpen) {
      loadSlideThumbnails();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template, isOpen]);

  const loadSlideThumbnails = async () => {
    if (!template) return;
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/agent/presentation/templates/${template.id}/thumbnails`);
      setSlides(response.data.thumbnails || []);
      setCurrentSlide(0);
    } catch (error) {
      console.error('슬라이드 로드 실패:', error);
      setSlides([]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !template) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold">{template.name} - 슬라이드 미리보기</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 콘텐츠 */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center h-96">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : slides.length > 0 ? (
            <div className="flex flex-col items-center">
              {/* 현재 슬라이드 이미지 */}
              <div className="relative w-full aspect-[16/9] bg-gray-100 rounded-lg overflow-hidden mb-4">
                <img
                  src={`/api/v1/agent/presentation/templates/${template.id}/thumbnails/${currentSlide}`}
                  alt={`슬라이드 ${currentSlide + 1}`}
                  className="w-full h-full object-contain"
                />

                {/* 슬라이드 역할 표시 */}
                <div className="absolute top-2 left-2 px-2 py-1 bg-black bg-opacity-60 text-white text-sm rounded">
                  슬라이드 {currentSlide + 1} / {slides.length}
                  {slides[currentSlide]?.role && (
                    <span className="ml-2 text-xs text-gray-300">
                      ({slides[currentSlide].role})
                    </span>
                  )}
                </div>
              </div>

              {/* 네비게이션 */}
              <div className="flex items-center space-x-4">
                <button
                  onClick={() => setCurrentSlide(prev => Math.max(0, prev - 1))}
                  disabled={currentSlide === 0}
                  className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>

                {/* 슬라이드 인디케이터 */}
                <div className="flex space-x-1 overflow-x-auto max-w-md">
                  {slides.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={() => setCurrentSlide(idx)}
                      className={`w-8 h-8 rounded flex items-center justify-center text-sm ${idx === currentSlide
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                    >
                      {idx + 1}
                    </button>
                  ))}
                </div>

                <button
                  onClick={() => setCurrentSlide(prev => Math.min(slides.length - 1, prev + 1))}
                  disabled={currentSlide === slides.length - 1}
                  className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-96 text-gray-500">
              <Image className="w-16 h-16 mb-4 opacity-50" />
              <p>슬라이드 미리보기가 없습니다.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// 템플릿 카드 컴포넌트
const TemplateCard: React.FC<{
  template: PPTTemplate;
  onPreview: () => void;
  onSetDefault: () => void;
  onDownload: () => void;
  onDelete: () => void;
}> = ({ template, onPreview, onSetDefault, onDownload, onDelete }) => {
  const [showMenu, setShowMenu] = useState(false);
  const [imageError, setImageError] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className={`bg-white rounded-lg shadow-sm border ${template.isDefault ? 'border-blue-500 ring-2 ring-blue-100' : 'border-gray-200'} hover:shadow-md transition-shadow`}>
      {/* 썸네일 */}
      <div className="relative aspect-[16/9] bg-gray-50 rounded-t-lg flex items-center justify-center">
        {!imageError ? (
          <img
            src={`/api/v1/agent/presentation/templates/${template.id}/thumbnails/0`}
            alt={template.name}
            className="w-full h-full object-contain"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-gray-400">
            <FileText className="w-12 h-12 mb-2" />
            <span className="text-xs">미리보기 없음</span>
          </div>
        )}

        {/* 기본 템플릿 배지 */}
        {template.isDefault && (
          <div className="absolute top-2 right-2 px-2 py-1 bg-blue-500 text-white text-xs rounded-full flex items-center z-10">
            <Star className="w-3 h-3 mr-1" fill="currentColor" />
            기본 템플릿
          </div>
        )}

        {/* 타입 배지 */}
        <div className={`absolute top-2 left-2 px-2 py-1 text-xs rounded-full z-10 ${template.type === 'built-in'
          ? 'bg-green-100 text-green-700'
          : 'bg-purple-100 text-purple-700'
          }`}>
          {template.type === 'built-in' ? '기본 제공' : '사용자 업로드'}
        </div>

        {/* 호버 오버레이 */}
        <div className="absolute inset-0 bg-black bg-opacity-0 hover:bg-opacity-30 transition-all flex items-center justify-center opacity-0 hover:opacity-100 rounded-t-lg">
          <button
            onClick={onPreview}
            className="px-4 py-2 bg-white text-gray-800 rounded-lg shadow flex items-center space-x-2 hover:bg-gray-100"
          >
            <Eye className="w-4 h-4" />
            <span>미리보기</span>
          </button>
        </div>
      </div>

      {/* 정보 */}
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{template.name}</h3>
            {template.slideCount && (
              <p className="text-sm text-gray-500">
                {template.slideCount}장의 슬라이드
              </p>
            )}
          </div>

          {/* 메뉴 버튼 */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-gray-100 rounded-full"
            >
              <MoreVertical className="w-4 h-4 text-gray-500" />
            </button>

            {showMenu && (
              <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
                <button
                  onClick={() => { onPreview(); setShowMenu(false); }}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 flex items-center space-x-2"
                >
                  <Eye className="w-4 h-4" />
                  <span>미리보기</span>
                </button>
                {!template.isDefault && (
                  <button
                    onClick={() => { onSetDefault(); setShowMenu(false); }}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 flex items-center space-x-2"
                  >
                    <Star className="w-4 h-4" />
                    <span>기본 템플릿으로 설정</span>
                  </button>
                )}
                <button
                  onClick={() => { onDownload(); setShowMenu(false); }}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 flex items-center space-x-2"
                >
                  <Download className="w-4 h-4" />
                  <span>다운로드</span>
                </button>
                {/* 사용자 업로드 템플릿만 삭제 가능 */}
                {template.type === 'user-uploaded' && (
                  <button
                    onClick={() => { onDelete(); setShowMenu(false); }}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center space-x-2"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>삭제</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// 메인 템플릿 관리 컴포넌트
export const TemplateManagement: React.FC = () => {
  const [templates, setTemplates] = useState<PPTTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'built-in' | 'user-uploaded'>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<PPTTemplate | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState('');
  const [notification, setNotification] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // 알림 표시
  const showNotification = useCallback((type: 'success' | 'error' | 'info', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000);
  }, []);

  // 템플릿 목록 로드
  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/v1/agent/presentation/templates');
      const data = response.data;

      // 데이터 정규화
      const allTemplates: PPTTemplate[] = [
        ...(data.built_in || []).map((t: PPTTemplate) => ({ ...t, type: 'built-in' as const })),
        ...(data.user_uploaded || []).map((t: PPTTemplate) => ({ ...t, type: 'user-uploaded' as const }))
      ];

      // 기본 템플릿 표시
      if (data.default_template_id) {
        allTemplates.forEach(t => {
          t.isDefault = t.id === data.default_template_id;
        });
      }

      setTemplates(allTemplates);
    } catch (error) {
      console.error('템플릿 로드 실패:', error);
      showNotification('error', '템플릿 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [showNotification]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // 파일 선택 핸들러
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.pptx')) {
        showNotification('error', 'PPTX 파일만 업로드 가능합니다.');
        return;
      }
      setUploadFile(file);
      setUploadName(file.name.replace('.pptx', ''));
      setShowUploadModal(true);
    }
  };

  // 템플릿 업로드
  const handleUpload = async () => {
    if (!uploadFile) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('name', uploadName || uploadFile.name.replace('.pptx', ''));

      await api.post('/api/v1/agent/presentation/templates/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      showNotification('success', '템플릿이 성공적으로 업로드되었습니다.');
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadName('');
      loadTemplates();
    } catch (error: any) {
      console.error('업로드 실패:', error);
      showNotification('error', error.response?.data?.detail || '템플릿 업로드에 실패했습니다.');
    } finally {
      setUploading(false);
    }
  };

  // 기본 템플릿 설정
  const handleSetDefault = async (template: PPTTemplate) => {
    try {
      await api.post(`/api/v1/agent/presentation/templates/${template.id}/set-default`);
      showNotification('success', `"${template.name}"이(가) 기본 템플릿으로 설정되었습니다.`);
      loadTemplates();
    } catch (error) {
      console.error('기본 템플릿 설정 실패:', error);
      showNotification('error', '기본 템플릿 설정에 실패했습니다.');
    }
  };

  // 템플릿 다운로드
  const handleDownload = async (template: PPTTemplate) => {
    try {
      const response = await api.get(`/api/v1/agent/presentation/templates/${template.id}/download`, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${template.name}.pptx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('다운로드 실패:', error);
      showNotification('error', '템플릿 다운로드에 실패했습니다.');
    }
  };

  // 템플릿 삭제
  const handleDelete = async (template: PPTTemplate) => {
    if (!window.confirm(`"${template.name}" 템플릿을 삭제하시겠습니까?`)) return;

    try {
      await api.delete(`/api/v1/agent/presentation/templates/${template.id}`);
      showNotification('success', '템플릿이 삭제되었습니다.');
      loadTemplates();
    } catch (error) {
      console.error('삭제 실패:', error);
      showNotification('error', '템플릿 삭제에 실패했습니다.');
    }
  };

  // 필터링된 템플릿
  const filteredTemplates = templates.filter(t => {
    const matchesSearch = t.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = filterType === 'all' || t.type === filterType;
    return matchesSearch && matchesType;
  });

  const builtInCount = templates.filter(t => t.type === 'built-in').length;
  const userUploadedCount = templates.filter(t => t.type === 'user-uploaded').length;

  return (
    <div className="p-6 space-y-6">
      {/* 알림 */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center space-x-2 ${notification.type === 'success' ? 'bg-green-500 text-white' :
          notification.type === 'error' ? 'bg-red-500 text-white' :
            'bg-blue-500 text-white'
          }`}>
          {notification.type === 'success' && <CheckCircle className="w-5 h-5" />}
          {notification.type === 'error' && <AlertTriangle className="w-5 h-5" />}
          {notification.type === 'info' && <Info className="w-5 h-5" />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">PPT 템플릿 관리</h1>
          <p className="text-gray-600">프레젠테이션 템플릿을 관리하고 기본 템플릿을 설정합니다.</p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadTemplates}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center space-x-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>새로고침</span>
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>템플릿 업로드</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pptx"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">전체 템플릿</p>
              <p className="text-2xl font-bold text-gray-900">{templates.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Settings className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">기본 제공</p>
              <p className="text-2xl font-bold text-gray-900">{builtInCount}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Upload className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">사용자 업로드</p>
              <p className="text-2xl font-bold text-gray-900">{userUploadedCount}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 검색 및 필터 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
            <input
              type="text"
              placeholder="템플릿 이름 또는 스타일로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setFilterType('all')}
              className={`px-4 py-2 rounded-lg text-sm font-medium ${filterType === 'all'
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
            >
              전체 ({templates.length})
            </button>
            <button
              onClick={() => setFilterType('built-in')}
              className={`px-4 py-2 rounded-lg text-sm font-medium ${filterType === 'built-in'
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
            >
              기본 제공 ({builtInCount})
            </button>
            <button
              onClick={() => setFilterType('user-uploaded')}
              className={`px-4 py-2 rounded-lg text-sm font-medium ${filterType === 'user-uploaded'
                ? 'bg-purple-100 text-purple-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
            >
              사용자 업로드 ({userUploadedCount})
            </button>
          </div>
        </div>
      </div>

      {/* 템플릿 그리드 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : filteredTemplates.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredTemplates.map(template => (
            <TemplateCard
              key={template.id}
              template={template}
              onPreview={() => setSelectedTemplate(template)}
              onSetDefault={() => handleSetDefault(template)}
              onDownload={() => handleDownload(template)}
              onDelete={() => handleDelete(template)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-64 bg-white rounded-lg border border-gray-200">
          <FileText className="w-16 h-16 text-gray-300 mb-4" />
          <p className="text-gray-500">
            {searchTerm ? '검색 결과가 없습니다.' : '등록된 템플릿이 없습니다.'}
          </p>
          {!searchTerm && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              첫 템플릿 업로드
            </button>
          )}
        </div>
      )}

      {/* 슬라이드 미리보기 모달 */}
      <SlidePreviewModal
        template={selectedTemplate}
        isOpen={!!selectedTemplate}
        onClose={() => setSelectedTemplate(null)}
      />

      {/* 업로드 모달 */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold">템플릿 업로드</h3>
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadFile(null);
                  setUploadName('');
                }}
                className="p-2 hover:bg-gray-100 rounded-full"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* 파일 정보 */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <FileText className="w-10 h-10 text-orange-500" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{uploadFile?.name}</p>
                    <p className="text-sm text-gray-500">
                      {uploadFile && (uploadFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
              </div>

              {/* 템플릿 이름 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  템플릿 이름
                </label>
                <input
                  type="text"
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                  placeholder="템플릿 이름 입력"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end p-4 border-t border-gray-200 space-x-3">
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadFile(null);
                  setUploadName('');
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleUpload}
                disabled={uploading || !uploadFile || !uploadName}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {uploading && <RefreshCw className="w-4 h-4 animate-spin" />}
                <span>{uploading ? '업로드 중...' : '업로드'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TemplateManagement;

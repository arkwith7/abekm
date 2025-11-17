import React, { useState, useEffect } from 'react';
import { getManagedDocuments, approveDocument, rejectDocument, getDocumentAnalytics } from '../../services/managerService';
import { ManagerDocument, DocumentAnalytics } from '../../types/manager.types';
import { 
  FileText, 
  CheckCircle, 
  XCircle, 
  Eye, 
  Download, 
  BarChart3,
  Users,
  Calendar
} from 'lucide-react';

export const DocumentManagement: React.FC = () => {
  const [documents, setDocuments] = useState<ManagerDocument[]>([]);
  const [analytics, setAnalytics] = useState<DocumentAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedContainer, setSelectedContainer] = useState<string>('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [documentsData, analyticsData] = await Promise.all([
        getManagedDocuments(),
        getDocumentAnalytics()
      ]);
      setDocuments(documentsData);
      setAnalytics(analyticsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async (documentId: string) => {
    try {
      await approveDocument(documentId);
      await loadData();
    } catch (error) {
      console.error('Failed to approve document:', error);
      alert('문서 승인에 실패했습니다.');
    }
  };

  const handleReject = async (documentId: string) => {
    const reason = prompt('반려 사유를 입력해주세요:');
    if (!reason) return;

    try {
      await rejectDocument(documentId, reason);
      await loadData();
    } catch (error) {
      console.error('Failed to reject document:', error);
      alert('문서 반려에 실패했습니다.');
    }
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesStatus = selectedStatus === 'all' || doc.status === selectedStatus;
    const matchesContainer = selectedContainer === 'all' || doc.container_path?.includes(selectedContainer);
    return matchesStatus && matchesContainer;
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'rejected': return 'bg-red-100 text-red-800';
      case 'archived': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active': return '활성';
      case 'pending': return '승인대기';
      case 'rejected': return '반려';
      case 'archived': return '보관';
      default: return status;
    }
  };

  const containers = Array.from(new Set(documents.map(doc => doc.container_path).filter(Boolean)));

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">문서를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-4 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* 헤더 */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">문서 관리</h1>
          <p className="mt-2 text-sm text-gray-600">
            팀의 문서들을 관리하고 승인/반려를 처리합니다.
          </p>
        </div>

        {/* 분석 대시보드 */}
        {analytics && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">📄</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">총 문서</p>
                  <p className="text-lg font-semibold text-gray-900">{analytics.total_documents}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">⏳</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">승인 대기</p>
                  <p className="text-lg font-semibold text-yellow-600">{analytics.pending_documents}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">👁️</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">이번 달 조회</p>
                  <p className="text-lg font-semibold text-blue-600">{analytics.monthly_views}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0 text-2xl">📈</div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-500">평균 평점</p>
                  <p className="text-lg font-semibold text-green-600">{analytics.average_rating.toFixed(1)}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 필터 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">상태</label>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">모든 상태</option>
                <option value="pending">승인 대기</option>
                <option value="active">활성</option>
                <option value="rejected">반려</option>
                <option value="archived">보관</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">컨테이너</label>
              <select
                value={selectedContainer}
                onChange={(e) => setSelectedContainer(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">모든 컨테이너</option>
                {containers.map((container) => (
                  <option key={container} value={container}>{container}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 문서 목록 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">
              문서 목록 ({filteredDocuments.length}개)
            </h3>
          </div>
          
          <div className="divide-y divide-gray-200">
            {filteredDocuments.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <div className="text-4xl mb-2">📄</div>
                <p>조건에 맞는 문서가 없습니다.</p>
              </div>
            ) : (
              filteredDocuments.map((document) => (
                <div key={document.id} className="p-6 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-2">
                        <FileText className="w-5 h-5 text-blue-600 flex-shrink-0" />
                        <h4 className="text-lg font-medium text-gray-900 truncate">
                          {document.title}
                        </h4>
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(document.status)}`}>
                          {getStatusLabel(document.status)}
                        </span>
                      </div>
                      
                      <div className="space-y-2">
                        <div className="flex items-center text-sm text-gray-500 space-x-4">
                          <span className="flex items-center">
                            <Users className="w-4 h-4 mr-1" />
                            {document.uploaded_by}
                          </span>
                          <span className="flex items-center">
                            <Calendar className="w-4 h-4 mr-1" />
                            {new Date(document.uploaded_at).toLocaleDateString('ko-KR')}
                          </span>
                          <span className="flex items-center">
                            <Eye className="w-4 h-4 mr-1" />
                            {document.view_count}회 조회
                          </span>
                        </div>
                        
                        {document.container_path && (
                          <div className="text-sm text-gray-500">
                            📁 {document.container_path}
                          </div>
                        )}
                        
                        {document.description && (
                          <p className="text-sm text-gray-600 line-clamp-2">
                            {document.description}
                          </p>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2 ml-4">
                      {document.status === 'pending' && (
                        <>
                          <button
                            onClick={() => handleApprove(document.id)}
                            className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md text-green-700 bg-green-100 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-green-500"
                          >
                            <CheckCircle className="w-4 h-4 mr-1" />
                            승인
                          </button>
                          <button
                            onClick={() => handleReject(document.id)}
                            className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500"
                          >
                            <XCircle className="w-4 h-4 mr-1" />
                            반려
                          </button>
                        </>
                      )}
                      
                      <button className="p-2 text-gray-400 hover:text-blue-600">
                        <Eye className="w-4 h-4" />
                      </button>
                      <button className="p-2 text-gray-400 hover:text-blue-600">
                        <Download className="w-4 h-4" />
                      </button>
                      <button className="p-2 text-gray-400 hover:text-blue-600">
                        <BarChart3 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  
                  {document.rejection_reason && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                      <p className="text-sm text-red-800">
                        <strong>반려 사유:</strong> {document.rejection_reason}
                      </p>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* 관리 팁 */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-medium text-blue-900 mb-2">📋 문서 관리 가이드</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-blue-800">
            <ul className="space-y-1">
              <li>• 승인 대기 문서를 정기적으로 검토하세요</li>
              <li>• 반려 시에는 명확한 사유를 제공하세요</li>
              <li>• 문서 품질과 정확성을 검증하세요</li>
            </ul>
            <ul className="space-y-1">
              <li>• 중복 문서가 없는지 확인하세요</li>
              <li>• 적절한 컨테이너에 분류되었는지 점검하세요</li>
              <li>• 정기적으로 문서 활용도를 분석하세요</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentManagement;

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Database,
  FileText,
  FolderOpen,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  Loader2,
  RotateCw,
  BarChart3,
  HardDrive,
  Layers,
  Users
} from 'lucide-react';
import { 
  knowledgeBaseAPI, 
  DocumentStatusSummary, 
  VectorDBStats, 
  ContainerOverview 
} from '../../services/adminService';

const KnowledgeBaseManagement: React.FC = () => {
  const [documentStatus, setDocumentStatus] = useState<DocumentStatusSummary | null>(null);
  const [vectorStats, setVectorStats] = useState<VectorDBStats | null>(null);
  const [containerOverview, setContainerOverview] = useState<ContainerOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'documents' | 'vectors' | 'containers'>('documents');

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [docStatus, vecStats, contOverview] = await Promise.all([
        knowledgeBaseAPI.getDocumentsStatus(),
        knowledgeBaseAPI.getVectorDBStats(),
        knowledgeBaseAPI.getContainersOverview()
      ]);
      
      setDocumentStatus(docStatus);
      setVectorStats(vecStats);
      setContainerOverview(contOverview);
    } catch (err) {
      console.error('지식베이스 데이터 로드 실패:', err);
      setError('지식베이스 데이터를 불러오는데 실패했습니다. 관리자 권한이 필요합니다.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleReprocess = async (fileId: number) => {
    try {
      setReprocessingId(fileId);
      await knowledgeBaseAPI.reprocessDocument(fileId);
      await fetchData(); // 데이터 새로고침
    } catch (err) {
      console.error('문서 재처리 실패:', err);
      setError('문서 재처리에 실패했습니다.');
    } finally {
      setReprocessingId(null);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <Database className="w-7 h-7 text-indigo-600" />
            <span>지식베이스 관리</span>
          </h1>
          <p className="text-gray-600">문서 처리 현황 및 벡터 DB 상태를 모니터링하세요</p>
        </div>
        <button 
          onClick={fetchData}
          disabled={isLoading}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>새로고침</span>
        </button>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{error}</span>
        </div>
      )}

      {/* 요약 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">전체 문서</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatNumber(documentStatus?.total_documents || 0)}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-blue-100">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">전체 청크</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatNumber(vectorStats?.total_chunks || 0)}
              </p>
              <p className="text-xs text-gray-500">
                평균 {vectorStats?.avg_chunk_size || 0}자
              </p>
            </div>
            <div className="p-3 rounded-lg bg-purple-100">
              <Layers className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">컨테이너</p>
              <p className="text-2xl font-bold text-gray-900">
                {containerOverview?.total_containers || 0}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-green-100">
              <FolderOpen className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">처리 실패</p>
              <p className="text-2xl font-bold text-red-600">
                {documentStatus?.by_status.failed || 0}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-red-100">
              <XCircle className="w-6 h-6 text-red-600" />
            </div>
          </div>
        </div>
      </div>

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: 'documents', label: '문서 처리 현황', icon: FileText },
            { id: 'vectors', label: '벡터 DB 통계', icon: HardDrive },
            { id: 'containers', label: '컨테이너 현황', icon: FolderOpen }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* 문서 처리 현황 탭 */}
      {activeTab === 'documents' && documentStatus && (
        <div className="space-y-6">
          {/* 처리 상태별 현황 */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-4 flex items-center space-x-3">
              <Clock className="w-8 h-8 text-gray-400" />
              <div>
                <p className="text-2xl font-bold text-gray-900">{documentStatus.by_status.pending}</p>
                <p className="text-sm text-gray-500">대기 중</p>
              </div>
            </div>
            <div className="bg-blue-50 rounded-lg p-4 flex items-center space-x-3">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              <div>
                <p className="text-2xl font-bold text-blue-600">{documentStatus.by_status.processing}</p>
                <p className="text-sm text-blue-500">처리 중</p>
              </div>
            </div>
            <div className="bg-green-50 rounded-lg p-4 flex items-center space-x-3">
              <CheckCircle2 className="w-8 h-8 text-green-500" />
              <div>
                <p className="text-2xl font-bold text-green-600">{documentStatus.by_status.completed}</p>
                <p className="text-sm text-green-500">완료</p>
              </div>
            </div>
            <div className="bg-red-50 rounded-lg p-4 flex items-center space-x-3">
              <XCircle className="w-8 h-8 text-red-500" />
              <div>
                <p className="text-2xl font-bold text-red-600">{documentStatus.by_status.failed}</p>
                <p className="text-sm text-red-500">실패</p>
              </div>
            </div>
          </div>

          {/* 실패한 문서 목록 */}
          {documentStatus.failed_documents.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div className="p-6 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  <span>처리 실패 문서</span>
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">파일명</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">컨테이너</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">에러</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">생성일</th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">작업</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {documentStatus.failed_documents.map((doc) => (
                      <tr key={doc.file_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm font-medium text-gray-900">{doc.file_name}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{doc.container_id || '-'}</td>
                        <td className="px-6 py-4 text-sm text-red-600 max-w-xs truncate">{doc.error || '-'}</td>
                        <td className="px-6 py-4 text-sm text-gray-500">
                          {doc.created_at ? new Date(doc.created_at).toLocaleString('ko-KR') : '-'}
                        </td>
                        <td className="px-6 py-4 text-center">
                          <button
                            onClick={() => handleReprocess(doc.file_id)}
                            disabled={reprocessingId === doc.file_id}
                            className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
                          >
                            {reprocessingId === doc.file_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RotateCw className="w-4 h-4" />
                            )}
                            <span>재처리</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 최근 처리 완료 문서 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                <CheckCircle2 className="w-5 h-5 text-green-500" />
                <span>최근 처리 완료</span>
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">파일명</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">컨테이너</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">청크 수</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">완료 시간</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {documentStatus.recent_completed.map((doc) => (
                    <tr key={doc.file_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{doc.file_name}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{doc.container_id || '-'}</td>
                      <td className="px-6 py-4 text-sm text-right text-gray-900">{doc.chunk_count}</td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {doc.completed_at ? new Date(doc.completed_at).toLocaleString('ko-KR') : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 벡터 DB 통계 탭 */}
      {activeTab === 'vectors' && vectorStats && (
        <div className="space-y-6">
          {/* 임베딩 커버리지 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                <BarChart3 className="w-5 h-5 text-indigo-600" />
                <span>임베딩 커버리지</span>
              </h3>
            </div>
            <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-600">{formatNumber(vectorStats.embedding_coverage.azure_1536)}</p>
                <p className="text-sm text-blue-500">Azure (1536d)</p>
              </div>
              <div className="text-center p-4 bg-orange-50 rounded-lg">
                <p className="text-2xl font-bold text-orange-600">{formatNumber(vectorStats.embedding_coverage.aws_1024)}</p>
                <p className="text-sm text-orange-500">AWS (1024d)</p>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <p className="text-2xl font-bold text-purple-600">{formatNumber(vectorStats.embedding_coverage.multimodal_512)}</p>
                <p className="text-sm text-purple-500">멀티모달 (512d)</p>
              </div>
              <div className="text-center p-4 bg-gray-100 rounded-lg">
                <p className="text-2xl font-bold text-gray-600">{formatNumber(vectorStats.embedding_coverage.legacy)}</p>
                <p className="text-sm text-gray-500">레거시</p>
              </div>
            </div>
          </div>

          {/* 컨테이너별 청크 분포 */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                <Database className="w-5 h-5 text-indigo-600" />
                <span>컨테이너별 청크 분포</span>
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">컨테이너 ID</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">문서 수</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">청크 수</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">비율</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {vectorStats.by_container.map((container) => (
                    <tr key={container.container_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{container.container_id}</td>
                      <td className="px-6 py-4 text-sm text-right text-gray-600">{container.document_count}</td>
                      <td className="px-6 py-4 text-sm text-right text-gray-900">{formatNumber(container.chunk_count)}</td>
                      <td className="px-6 py-4">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-indigo-600 h-2 rounded-full" 
                            style={{ width: `${Math.min((container.chunk_count / vectorStats.total_chunks) * 100, 100)}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 컨테이너 현황 탭 */}
      {activeTab === 'containers' && containerOverview && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
              <FolderOpen className="w-5 h-5 text-green-600" />
              <span>컨테이너 상세 현황</span>
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">컨테이너 ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">이름</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">공개</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">문서 수</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">청크 수</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    <div className="flex items-center justify-end space-x-1">
                      <Users className="w-3 h-3" />
                      <span>사용자</span>
                    </div>
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">생성일</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {containerOverview.containers.map((container) => (
                  <tr key={container.container_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-mono text-gray-900">{container.container_id}</td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{container.container_name}</td>
                    <td className="px-6 py-4 text-center">
                      {container.is_public ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">공개</span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">비공개</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-right text-gray-900">{container.document_count}</td>
                    <td className="px-6 py-4 text-sm text-right text-gray-900">{formatNumber(container.chunk_count)}</td>
                    <td className="px-6 py-4 text-sm text-right text-gray-600">{container.user_count}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {container.created_at ? new Date(container.created_at).toLocaleDateString('ko-KR') : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 안내 */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <Database className="w-5 h-5 text-indigo-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-indigo-800">지식베이스 관리 안내</h3>
            <p className="text-sm text-indigo-700 mt-1">
              문서 업로드 시 자동으로 텍스트 추출, 청킹, 임베딩 처리가 진행됩니다.
              처리 실패 시 '재처리' 버튼으로 다시 시도할 수 있습니다.
              벡터 DB에는 Azure, AWS, 멀티모달 임베딩이 별도로 저장됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseManagement;


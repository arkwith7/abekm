import React, { useState } from 'react';
import { 
  Database, 
  Search, 
  Filter, 
  Download, 
  Eye, 
  Calendar,
  User,
  Activity,
  Shield,
  FileText,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Settings,
  RefreshCw
} from 'lucide-react';

interface AuditLog {
  id: string;
  timestamp: string;
  userId: string;
  userName: string;
  action: string;
  resource: string;
  details: string;
  ipAddress: string;
  userAgent: string;
  result: 'success' | 'failure' | 'warning';
  category: 'authentication' | 'authorization' | 'data_access' | 'configuration' | 'system';
}

const AuditLogComponent: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedResult, setSelectedResult] = useState('all');
  const [selectedDateRange, setSelectedDateRange] = useState('today');
  const [showDetails, setShowDetails] = useState<string | null>(null);

  const auditLogs: AuditLog[] = [
    {
      id: '1',
      timestamp: '2024-01-15 14:30:25',
      userId: 'SYS001',
      userName: '최시스템',
      action: '시스템 설정 변경',
      resource: '/admin/settings/security',
      details: '비밀번호 정책 업데이트: 최소 길이 8자 → 10자',
      ipAddress: '192.168.1.10',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      result: 'success',
      category: 'configuration'
    },
    {
      id: '2',
      timestamp: '2024-01-15 14:15:12',
      userId: 'HR001',
      userName: '김인사',
      action: '사용자 권한 변경',
      resource: '/manager/permissions/user/IT002',
      details: '박개발 사용자 권한 변경: USER → MANAGER',
      ipAddress: '192.168.1.15',
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      result: 'success',
      category: 'authorization'
    },
    {
      id: '3',
      timestamp: '2024-01-15 13:45:33',
      userId: 'unknown',
      userName: '알 수 없음',
      action: '로그인 실패',
      resource: '/auth/login',
      details: '잘못된 자격 증명으로 로그인 시도 (5회 연속)',
      ipAddress: '203.142.15.88',
      userAgent: 'curl/7.68.0',
      result: 'failure',
      category: 'authentication'
    },
    {
      id: '4',
      timestamp: '2024-01-15 13:30:45',
      userId: 'IT002',
      userName: '박개발',
      action: '문서 다운로드',
      resource: '/api/documents/download/12345',
      details: '기밀문서 "2024 사업계획.pdf" 다운로드',
      ipAddress: '192.168.1.20',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      result: 'success',
      category: 'data_access'
    },
    {
      id: '5',
      timestamp: '2024-01-15 12:15:20',
      userId: 'MK003',
      userName: '이마케팅',
      action: '문서 업로드',
      resource: '/api/documents/upload',
      details: '"마케팅 전략 2024.pptx" 파일 업로드',
      ipAddress: '192.168.1.25',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      result: 'success',
      category: 'data_access'
    },
    {
      id: '6',
      timestamp: '2024-01-15 11:45:15',
      userId: 'SYS001',
      userName: '최시스템',
      action: '데이터베이스 백업',
      resource: '/system/backup',
      details: '일일 데이터베이스 자동 백업 실행',
      ipAddress: '127.0.0.1',
      userAgent: 'System/Scheduler',
      result: 'success',
      category: 'system'
    },
    {
      id: '7',
      timestamp: '2024-01-15 11:30:08',
      userId: 'FN004',
      userName: '정재무',
      action: '권한 없는 접근 시도',
      resource: '/admin/users',
      details: '관리자 페이지 접근 시도 (권한 없음)',
      ipAddress: '192.168.1.30',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      result: 'failure',
      category: 'authorization'
    },
    {
      id: '8',
      timestamp: '2024-01-15 10:15:42',
      userId: 'HR001',
      userName: '김인사',
      action: '로그인 성공',
      resource: '/auth/login',
      details: '정상 로그인 (2FA 인증 완료)',
      ipAddress: '192.168.1.15',
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      result: 'success',
      category: 'authentication'
    }
  ];

  const getResultIcon = (result: string) => {
    switch (result) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failure':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getResultColor = (result: string) => {
    switch (result) {
      case 'success':
        return 'bg-green-100 text-green-800';
      case 'failure':
        return 'bg-red-100 text-red-800';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'authentication':
        return <User className="w-4 h-4" />;
      case 'authorization':
        return <Shield className="w-4 h-4" />;
      case 'data_access':
        return <FileText className="w-4 h-4" />;
      case 'configuration':
        return <Settings className="w-4 h-4" />;
      case 'system':
        return <Database className="w-4 h-4" />;
      default:
        return <Activity className="w-4 h-4" />;
    }
  };

  const getCategoryName = (category: string) => {
    switch (category) {
      case 'authentication':
        return '인증';
      case 'authorization':
        return '권한';
      case 'data_access':
        return '데이터 접근';
      case 'configuration':
        return '설정 변경';
      case 'system':
        return '시스템';
      default:
        return category;
    }
  };

  const filteredLogs = auditLogs.filter(log => {
    const matchesSearch = log.userName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.details.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || log.category === selectedCategory;
    const matchesResult = selectedResult === 'all' || log.result === selectedResult;
    
    return matchesSearch && matchesCategory && matchesResult;
  });

  const logStats = {
    total: auditLogs.length,
    success: auditLogs.filter(log => log.result === 'success').length,
    failure: auditLogs.filter(log => log.result === 'failure').length,
    warning: auditLogs.filter(log => log.result === 'warning').length
  };

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">감사 로그</h1>
          <p className="text-gray-600">시스템 활동과 보안 이벤트를 추적하고 분석하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <button className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            <Download className="w-4 h-4" />
            <span>로그 내보내기</span>
          </button>
          <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            <RefreshCw className="w-4 h-4" />
            <span>새로고침</span>
          </button>
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Database className="w-6 h-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">전체 로그</p>
              <p className="text-2xl font-bold text-gray-900">{logStats.total}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">성공</p>
              <p className="text-2xl font-bold text-gray-900">{logStats.success}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-red-100 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">실패</p>
              <p className="text-2xl font-bold text-gray-900">{logStats.failure}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">경고</p>
              <p className="text-2xl font-bold text-gray-900">{logStats.warning}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 필터 및 검색 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0 md:space-x-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="사용자명, 액션, 세부정보로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <select 
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="all">모든 카테고리</option>
                <option value="authentication">인증</option>
                <option value="authorization">권한</option>
                <option value="data_access">데이터 접근</option>
                <option value="configuration">설정 변경</option>
                <option value="system">시스템</option>
              </select>
            </div>
            <select 
              value={selectedResult}
              onChange={(e) => setSelectedResult(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="all">모든 결과</option>
              <option value="success">성공</option>
              <option value="failure">실패</option>
              <option value="warning">경고</option>
            </select>
            <select 
              value={selectedDateRange}
              onChange={(e) => setSelectedDateRange(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="today">오늘</option>
              <option value="week">최근 1주일</option>
              <option value="month">최근 1개월</option>
              <option value="custom">사용자 지정</option>
            </select>
          </div>
        </div>
      </div>

      {/* 감사 로그 테이블 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">감사 로그 목록</h2>
            <span className="text-sm text-gray-500">{filteredLogs.length}개 항목</span>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">시간</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">사용자</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">액션</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">카테고리</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">결과</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP 주소</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">작업</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredLogs.map((log) => (
                <React.Fragment key={log.id}>
                  <tr className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="flex items-center space-x-2">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        <span>{log.timestamp}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
                          <span className="text-xs font-medium text-gray-700">
                            {log.userName.charAt(0)}
                          </span>
                        </div>
                        <div className="ml-3">
                          <div className="text-sm font-medium text-gray-900">{log.userName}</div>
                          <div className="text-sm text-gray-500">{log.userId}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">{log.action}</div>
                      <div className="text-sm text-gray-500 truncate max-w-xs">{log.details}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        {getCategoryIcon(log.category)}
                        <span className="text-sm text-gray-900">{getCategoryName(log.category)}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        {getResultIcon(log.result)}
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getResultColor(log.result)}`}>
                          {log.result === 'success' ? '성공' : log.result === 'failure' ? '실패' : '경고'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {log.ipAddress}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        onClick={() => setShowDetails(showDetails === log.id ? null : log.id)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                  {showDetails === log.id && (
                    <tr>
                      <td colSpan={7} className="px-6 py-4 bg-gray-50">
                        <div className="space-y-2 text-sm">
                          <div><strong>리소스:</strong> {log.resource}</div>
                          <div><strong>세부 정보:</strong> {log.details}</div>
                          <div><strong>User Agent:</strong> {log.userAgent}</div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {filteredLogs.length === 0 && (
          <div className="text-center py-12">
            <Database className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">로그가 없습니다</h3>
            <p className="mt-1 text-sm text-gray-500">검색 조건을 변경해보세요.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export { AuditLogComponent as AuditLog };
export default AuditLogComponent;

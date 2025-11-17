import React, { useState } from 'react';
import { 
  Shield, 
  Lock, 
  Key, 
  Users, 
  AlertTriangle, 
  CheckCircle, 
  Settings, 
  Eye, 
  EyeOff,
  RefreshCw,
  Download,
  Upload,
  Server,
  Database,
  Wifi
} from 'lucide-react';

interface SecurityPolicyType {
  id: string;
  name: string;
  description: string;
  status: 'enabled' | 'disabled';
  lastModified: string;
  category: 'authentication' | 'authorization' | 'data' | 'network';
}

interface SecurityEvent {
  id: string;
  type: 'login_attempt' | 'access_denied' | 'policy_violation' | 'system_alert';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  source: string;
  timestamp: string;
  resolved: boolean;
}

const SecurityPolicyComponent: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [showPasswords, setShowPasswords] = useState(false);

  const securityPolicies: SecurityPolicyType[] = [
    {
      id: '1',
      name: '비밀번호 복잡성 정책',
      description: '최소 8자, 대소문자, 숫자, 특수문자 포함',
      status: 'enabled',
      lastModified: '2024-01-10',
      category: 'authentication'
    },
    {
      id: '2',
      name: '계정 잠금 정책',
      description: '5회 실패 시 30분 잠금',
      status: 'enabled',
      lastModified: '2024-01-08',
      category: 'authentication'
    },
    {
      id: '3',
      name: '세션 타임아웃',
      description: '비활성 30분 후 자동 로그아웃',
      status: 'enabled',
      lastModified: '2024-01-05',
      category: 'authentication'
    },
    {
      id: '4',
      name: '관리자 권한 분리',
      description: '시스템 관리와 데이터 관리 권한 분리',
      status: 'enabled',
      lastModified: '2024-01-12',
      category: 'authorization'
    },
    {
      id: '5',
      name: '데이터 암호화',
      description: '저장 데이터 AES-256 암호화',
      status: 'enabled',
      lastModified: '2024-01-01',
      category: 'data'
    },
    {
      id: '6',
      name: '방화벽 규칙',
      description: '내부 네트워크만 접근 허용',
      status: 'enabled',
      lastModified: '2024-01-15',
      category: 'network'
    }
  ];

  const securityEvents: SecurityEvent[] = [
    {
      id: '1',
      type: 'login_attempt',
      severity: 'high',
      description: '알 수 없는 IP에서 관리자 계정 로그인 시도',
      source: '192.168.1.100',
      timestamp: '2024-01-15 14:30',
      resolved: false
    },
    {
      id: '2',
      type: 'access_denied',
      severity: 'medium',
      description: '권한 없는 사용자의 시스템 설정 접근 시도',
      source: 'user@company.com',
      timestamp: '2024-01-15 13:45',
      resolved: true
    },
    {
      id: '3',
      type: 'policy_violation',
      severity: 'low',
      description: '약한 비밀번호 사용 시도',
      source: 'test@company.com',
      timestamp: '2024-01-15 12:20',
      resolved: true
    },
    {
      id: '4',
      type: 'system_alert',
      severity: 'critical',
      description: '비정상적인 데이터베이스 접근 패턴 감지',
      source: 'Database Server',
      timestamp: '2024-01-15 11:15',
      resolved: false
    }
  ];

  const securityMetrics = [
    {
      title: '활성 정책',
      value: securityPolicies.filter(p => p.status === 'enabled').length,
      total: securityPolicies.length,
      icon: Shield,
      color: 'green'
    },
    {
      title: '미해결 위험',
      value: securityEvents.filter(e => !e.resolved && (e.severity === 'high' || e.severity === 'critical')).length,
      total: securityEvents.filter(e => e.severity === 'high' || e.severity === 'critical').length,
      icon: AlertTriangle,
      color: 'red'
    },
    {
      title: '오늘 로그인',
      value: 234,
      total: 300,
      icon: Users,
      color: 'blue'
    },
    {
      title: '시스템 가동률',
      value: '99.9%',
      total: '100%',
      icon: CheckCircle,
      color: 'green'
    }
  ];

  const getCategoryName = (category: string) => {
    switch (category) {
      case 'authentication':
        return '인증';
      case 'authorization':
        return '권한';
      case 'data':
        return '데이터';
      case 'network':
        return '네트워크';
      default:
        return category;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'authentication':
        return <Key className="w-4 h-4" />;
      case 'authorization':
        return <Shield className="w-4 h-4" />;
      case 'data':
        return <Database className="w-4 h-4" />;
      case 'network':
        return <Wifi className="w-4 h-4" />;
      default:
        return <Settings className="w-4 h-4" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'login_attempt':
        return <Key className="w-4 h-4" />;
      case 'access_denied':
        return <Lock className="w-4 h-4" />;
      case 'policy_violation':
        return <AlertTriangle className="w-4 h-4" />;
      case 'system_alert':
        return <Server className="w-4 h-4" />;
      default:
        return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const filteredPolicies = selectedCategory === 'all' 
    ? securityPolicies 
    : securityPolicies.filter(policy => policy.category === selectedCategory);

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">보안 정책</h1>
          <p className="text-gray-600">시스템 보안 정책을 관리하고 모니터링하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <button className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            <Download className="w-4 h-4" />
            <span>정책 내보내기</span>
          </button>
          <button className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            <Upload className="w-4 h-4" />
            <span>정책 가져오기</span>
          </button>
          <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            <RefreshCw className="w-4 h-4" />
            <span>정책 새로고침</span>
          </button>
        </div>
      </div>

      {/* 보안 메트릭 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {securityMetrics.map((metric, index) => {
          const Icon = metric.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{metric.title}</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {typeof metric.value === 'string' ? metric.value : metric.value}
                  </p>
                  {typeof metric.value === 'number' && (
                    <p className="text-sm text-gray-500">총 {metric.total}개</p>
                  )}
                </div>
                <div className={`p-3 rounded-lg bg-${metric.color}-100`}>
                  <Icon className={`w-6 h-6 text-${metric.color}-600`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 보안 정책 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Shield className="w-5 h-5 text-gray-600" />
                <h2 className="text-lg font-semibold text-gray-900">보안 정책</h2>
              </div>
              <select 
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="all">모든 카테고리</option>
                <option value="authentication">인증</option>
                <option value="authorization">권한</option>
                <option value="data">데이터</option>
                <option value="network">네트워크</option>
              </select>
            </div>
          </div>
          
          <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
            {filteredPolicies.map((policy) => (
              <div key={policy.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      {getCategoryIcon(policy.category)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <h3 className="text-sm font-medium text-gray-900">{policy.name}</h3>
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                          {getCategoryName(policy.category)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{policy.description}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        마지막 수정: {policy.lastModified}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      policy.status === 'enabled' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {policy.status === 'enabled' ? '활성' : '비활성'}
                    </span>
                    <button className="text-gray-400 hover:text-gray-600">
                      <Settings className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 보안 이벤트 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5 text-gray-600" />
                <h2 className="text-lg font-semibold text-gray-900">보안 이벤트</h2>
              </div>
              <button 
                onClick={() => setShowPasswords(!showPasswords)}
                className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-900"
              >
                {showPasswords ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                <span>{showPasswords ? '숨기기' : '세부정보'}</span>
              </button>
            </div>
          </div>
          
          <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
            {securityEvents.map((event) => (
              <div key={event.id} className={`p-4 border-l-4 ${getSeverityColor(event.severity)}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      {getEventIcon(event.type)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(event.severity)}`}>
                          {event.severity === 'critical' ? '위험' : 
                           event.severity === 'high' ? '높음' : 
                           event.severity === 'medium' ? '보통' : '낮음'}
                        </span>
                        {event.resolved && (
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                            해결됨
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-900 mt-1">{event.description}</p>
                      {showPasswords && (
                        <div className="text-xs text-gray-500 mt-1 space-y-1">
                          <p>출처: {event.source}</p>
                          <p>시간: {event.timestamp}</p>
                        </div>
                      )}
                    </div>
                  </div>
                  {!event.resolved && (
                    <button className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors">
                      처리
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 빠른 액션 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">빠른 보안 액션</h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button className="flex items-center space-x-3 p-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              <Lock className="w-6 h-6 text-blue-600" />
              <div className="text-left">
                <div className="font-medium text-gray-900">모든 세션 종료</div>
                <div className="text-sm text-gray-500">활성 사용자 세션 강제 종료</div>
              </div>
            </button>
            <button className="flex items-center space-x-3 p-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              <RefreshCw className="w-6 h-6 text-green-600" />
              <div className="text-left">
                <div className="font-medium text-gray-900">정책 업데이트</div>
                <div className="text-sm text-gray-500">최신 보안 정책 적용</div>
              </div>
            </button>
            <button className="flex items-center space-x-3 p-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              <AlertTriangle className="w-6 h-6 text-red-600" />
              <div className="text-left">
                <div className="font-medium text-gray-900">보안 스캔</div>
                <div className="text-sm text-gray-500">시스템 취약점 검사</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export { SecurityPolicyComponent as SecurityPolicy };
export default SecurityPolicyComponent;

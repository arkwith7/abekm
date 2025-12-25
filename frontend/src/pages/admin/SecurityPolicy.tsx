import React, { useState } from 'react';
import { 
  Shield, 
  Lock, 
  Key, 
  AlertTriangle, 
  CheckCircle, 
  Info,
  Database,
  Wifi,
  Clock
} from 'lucide-react';

interface SecurityPolicyType {
  id: string;
  name: string;
  description: string;
  status: 'enabled' | 'disabled';
  category: 'authentication' | 'authorization' | 'data' | 'network';
  configurable: boolean;
}

const SecurityPolicyComponent: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState('all');

  // 현재 적용된 보안 정책 (읽기 전용)
  const securityPolicies: SecurityPolicyType[] = [
    {
      id: '1',
      name: '비밀번호 복잡성 정책',
      description: '최소 8자, 대소문자, 숫자, 특수문자 포함 필수',
      status: 'enabled',
      category: 'authentication',
      configurable: false
    },
    {
      id: '2',
      name: '계정 잠금 정책',
      description: '5회 연속 로그인 실패 시 계정 잠금',
      status: 'enabled',
      category: 'authentication',
      configurable: false
    },
    {
      id: '3',
      name: 'JWT 토큰 만료',
      description: '액세스 토큰 30분, 리프레시 토큰 7일 만료',
      status: 'enabled',
      category: 'authentication',
      configurable: false
    },
    {
      id: '4',
      name: '역할 기반 접근 제어 (RBAC)',
      description: '시스템 관리자, 지식 관리자, 일반 사용자 권한 분리',
      status: 'enabled',
      category: 'authorization',
      configurable: false
    },
    {
      id: '5',
      name: '컨테이너별 권한 관리',
      description: '지식 컨테이너 단위로 읽기/쓰기 권한 설정',
      status: 'enabled',
      category: 'authorization',
      configurable: false
    },
    {
      id: '6',
      name: '비밀번호 암호화',
      description: 'bcrypt 해싱 알고리즘으로 비밀번호 저장',
      status: 'enabled',
      category: 'data',
      configurable: false
    },
    {
      id: '7',
      name: 'HTTPS 통신',
      description: '모든 API 통신 TLS/SSL 암호화 (운영 환경)',
      status: 'enabled',
      category: 'network',
      configurable: false
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
        return <Lock className="w-4 h-4" />;
    }
  };

  const filteredPolicies = selectedCategory === 'all' 
    ? securityPolicies 
    : securityPolicies.filter(policy => policy.category === selectedCategory);

  const enabledCount = securityPolicies.filter(p => p.status === 'enabled').length;

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">보안 정책</h1>
          <p className="text-gray-600">현재 적용된 시스템 보안 정책을 확인하세요</p>
        </div>
      </div>

      {/* 읽기 전용 안내 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start space-x-3">
        <Info className="w-5 h-5 text-blue-500 mt-0.5" />
        <div>
          <h3 className="font-medium text-blue-800">읽기 전용 모드</h3>
          <p className="text-sm text-blue-700 mt-1">
            보안 정책 설정 변경 API가 아직 구현되지 않아 현재 정책 현황만 표시됩니다.
            정책 변경이 필요한 경우 시스템 관리자에게 문의하세요.
          </p>
        </div>
      </div>

      {/* 보안 메트릭 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">활성 정책</p>
              <p className="text-2xl font-bold text-gray-900">{enabledCount} / {securityPolicies.length}</p>
            </div>
            <div className="p-3 rounded-lg bg-green-100">
              <Shield className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">보안 등급</p>
              <p className="text-2xl font-bold text-green-600">양호</p>
            </div>
            <div className="p-3 rounded-lg bg-green-100">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">마지막 점검</p>
              <p className="text-2xl font-bold text-gray-900">{new Date().toLocaleDateString()}</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-100">
              <Clock className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>
      </div>

      {/* 보안 정책 목록 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Shield className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">적용된 보안 정책</h2>
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
        
        <div className="divide-y divide-gray-200">
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
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    policy.status === 'enabled' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {policy.status === 'enabled' ? '✓ 활성' : '비활성'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 향후 개발 안내 */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-amber-800">개발 예정 기능</h3>
            <ul className="mt-2 text-sm text-amber-700 space-y-1">
              <li>• 비밀번호 정책 설정 (길이, 복잡도, 만료 주기)</li>
              <li>• 계정 잠금 임계치 설정</li>
              <li>• 세션 타임아웃 설정</li>
              <li>• IP 화이트리스트/블랙리스트</li>
              <li>• 2단계 인증 (2FA) 활성화</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export { SecurityPolicyComponent as SecurityPolicy };
export default SecurityPolicyComponent;

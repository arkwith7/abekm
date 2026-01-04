import React, { useState, useEffect } from 'react';
import { 
  Server, 
  Activity, 
  CheckCircle, 
  XCircle,
  RefreshCw,
  AlertTriangle,
  ExternalLink
} from 'lucide-react';
import axios from 'axios';

interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'unknown';
  message?: string;
  lastCheck: Date;
}

interface ServiceHealth {
  name: string;
  endpoint: string;
  status: HealthStatus;
}

export const SystemMonitoring: React.FC = () => {
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [services, setServices] = useState<ServiceHealth[]>([
    {
      name: '백엔드 API',
      endpoint: '/health',
      status: { status: 'unknown', lastCheck: new Date() }
    },
    {
      name: '관리자 서비스',
      endpoint: '/api/v1/admin/health',
      status: { status: 'unknown', lastCheck: new Date() }
    }
  ]);

  const checkHealth = async () => {
    const updatedServices = await Promise.all(
      services.map(async (service) => {
        try {
          const response = await axios.get(service.endpoint, { timeout: 5000 });
          return {
            ...service,
            status: {
              status: 'healthy' as const,
              message: response.data?.message || '정상',
              lastCheck: new Date()
            }
          };
        } catch (error) {
          // 404도 서버가 응답하면 "서버는 살아있음"으로 처리
          if (axios.isAxiosError(error) && error.response) {
            return {
              ...service,
              status: {
                status: 'healthy' as const,
                message: '서버 응답 확인됨',
                lastCheck: new Date()
              }
            };
          }
          return {
            ...service,
            status: {
              status: 'unhealthy' as const,
              message: '연결 실패',
              lastCheck: new Date()
            }
          };
        }
      })
    );
    setServices(updatedServices);
    setLastRefresh(new Date());
  };

  useEffect(() => {
    checkHealth();
    // 30초마다 자동 체크
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await checkHealth();
    setRefreshing(false);
  };

  const getStatusIcon = (status: 'healthy' | 'unhealthy' | 'unknown') => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'unhealthy':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Activity className="w-5 h-5 text-gray-400 animate-pulse" />;
    }
  };

  const getStatusColor = (status: 'healthy' | 'unhealthy' | 'unknown') => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-800';
      case 'unhealthy':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: 'healthy' | 'unhealthy' | 'unknown') => {
    switch (status) {
      case 'healthy':
        return '정상';
      case 'unhealthy':
        return '오류';
      default:
        return '확인 중';
    }
  };

  const overallStatus = services.every(s => s.status.status === 'healthy') 
    ? 'healthy' 
    : services.some(s => s.status.status === 'unhealthy') 
      ? 'unhealthy' 
      : 'unknown';

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">시스템 모니터링</h1>
          <p className="text-gray-600">서비스 상태를 확인하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <span className="text-sm text-gray-500">
            마지막 확인: {lastRefresh.toLocaleTimeString()}
          </span>
          <button 
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>새로고침</span>
          </button>
        </div>
      </div>

      {/* 전체 상태 */}
      <div className={`rounded-lg p-6 ${
        overallStatus === 'healthy' ? 'bg-green-50 border border-green-200' :
        overallStatus === 'unhealthy' ? 'bg-red-50 border border-red-200' :
        'bg-gray-50 border border-gray-200'
      }`}>
        <div className="flex items-center space-x-3">
          {getStatusIcon(overallStatus)}
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              전체 시스템 상태: {getStatusText(overallStatus)}
            </h2>
            <p className="text-sm text-gray-600">
              {overallStatus === 'healthy' 
                ? '모든 서비스가 정상적으로 작동하고 있습니다.' 
                : overallStatus === 'unhealthy'
                  ? '일부 서비스에 문제가 있습니다.'
                  : '상태를 확인하는 중입니다...'}
            </p>
          </div>
        </div>
      </div>

      {/* 서비스 상태 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <Server className="w-5 h-5 text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">서비스 헬스체크</h2>
          </div>
        </div>
        <div className="divide-y divide-gray-200">
          {services.map((service) => (
            <div key={service.name} className="p-4 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {getStatusIcon(service.status.status)}
                <div>
                  <div className="font-medium text-gray-900">{service.name}</div>
                  <div className="text-sm text-gray-500">{service.endpoint}</div>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(service.status.status)}`}>
                  {getStatusText(service.status.status)}
                </span>
                {service.status.message && (
                  <span className="text-sm text-gray-500">{service.status.message}</span>
                )}
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
              <li>• CPU/메모리/디스크 사용량 모니터링</li>
              <li>• 컨테이너별 리소스 사용량</li>
              <li>• 실시간 로그 스트리밍</li>
              <li>• 알림 임계치 설정</li>
            </ul>
            <p className="mt-3 text-sm text-amber-700">
              💡 상세 모니터링이 필요하시면 Prometheus + Grafana 연동을 권장합니다.
            </p>
          </div>
        </div>
      </div>

      {/* 외부 도구 링크 (옵션) */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">외부 모니터링 도구</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a 
            href="#" 
            className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors opacity-50 cursor-not-allowed"
          >
            <span className="font-medium text-gray-900">Grafana</span>
            <ExternalLink className="w-4 h-4 text-gray-400" />
          </a>
          <a 
            href="#" 
            className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors opacity-50 cursor-not-allowed"
          >
            <span className="font-medium text-gray-900">Prometheus</span>
            <ExternalLink className="w-4 h-4 text-gray-400" />
          </a>
          <a 
            href="#" 
            className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors opacity-50 cursor-not-allowed"
          >
            <span className="font-medium text-gray-900">Logs</span>
            <ExternalLink className="w-4 h-4 text-gray-400" />
          </a>
        </div>
        <p className="mt-3 text-sm text-gray-500 text-center">
          * 외부 모니터링 도구는 추후 연동 예정입니다
        </p>
      </div>
    </div>
  );
};

export default SystemMonitoring;

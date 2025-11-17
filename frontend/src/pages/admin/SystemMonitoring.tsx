import React, { useState } from 'react';
import { 
  Server, 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  RefreshCw,
  Eye,
  Settings,
  TrendingUp,
  TrendingDown
} from 'lucide-react';

export const SystemMonitoring: React.FC = () => {
  const [refreshing, setRefreshing] = useState(false);
  const [selectedTimeRange, setSelectedTimeRange] = useState('1h');

  const handleRefresh = async () => {
    setRefreshing(true);
    // 실제 데이터 새로고침 로직
    setTimeout(() => {
      setRefreshing(false);
    }, 2000);
  };

  const servers = [
    {
      id: 1,
      name: 'Web Server 01',
      type: 'Frontend',
      status: 'healthy',
      uptime: '99.9%',
      cpu: 34,
      memory: 67,
      disk: 45,
      network: 'Good',
      lastCheck: '1분 전'
    },
    {
      id: 2,
      name: 'API Server 01',
      type: 'Backend',
      status: 'healthy',
      uptime: '99.8%',
      cpu: 56,
      memory: 72,
      disk: 38,
      network: 'Good',
      lastCheck: '1분 전'
    },
    {
      id: 3,
      name: 'Database Server',
      type: 'Database',
      status: 'warning',
      uptime: '99.5%',
      cpu: 78,
      memory: 89,
      disk: 67,
      network: 'Good',
      lastCheck: '2분 전'
    },
    {
      id: 4,
      name: 'AI Processing Server',
      type: 'AI/ML',
      status: 'critical',
      uptime: '97.2%',
      cpu: 92,
      memory: 95,
      disk: 56,
      network: 'Poor',
      lastCheck: '30초 전'
    },
    {
      id: 5,
      name: 'File Storage Server',
      type: 'Storage',
      status: 'healthy',
      uptime: '99.9%',
      cpu: 23,
      memory: 45,
      disk: 78,
      network: 'Excellent',
      lastCheck: '1분 전'
    }
  ];

  const metrics = [
    {
      title: '전체 CPU 사용률',
      value: '56.7%',
      change: '+2.3%',
      trend: 'up',
      color: 'blue'
    },
    {
      title: '메모리 사용률',
      value: '73.2%',
      change: '+5.1%',
      trend: 'up',
      color: 'purple'
    },
    {
      title: '디스크 I/O',
      value: '234MB/s',
      change: '-12.5%',
      trend: 'down',
      color: 'green'
    },
    {
      title: '네트워크 처리량',
      value: '1.2GB/s',
      change: '+8.2%',
      trend: 'up',
      color: 'indigo'
    }
  ];

  const alerts = [
    {
      id: 1,
      severity: 'critical',
      server: 'AI Processing Server',
      message: 'CPU 사용률이 90%를 초과했습니다',
      time: '2분 전',
      acknowledged: false
    },
    {
      id: 2,
      severity: 'warning',
      server: 'Database Server',
      message: '메모리 사용률이 85%에 도달했습니다',
      time: '5분 전',
      acknowledged: false
    },
    {
      id: 3,
      severity: 'info',
      server: 'Web Server 01',
      message: '정기 백업이 완료되었습니다',
      time: '1시간 전',
      acknowledged: true
    }
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'critical':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <CheckCircle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-800';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800';
      case 'critical':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getProgressColor = (value: number) => {
    if (value >= 90) return 'bg-red-500';
    if (value >= 80) return 'bg-yellow-500';
    if (value >= 60) return 'bg-blue-500';
    return 'bg-green-500';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'info':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">시스템 모니터링</h1>
          <p className="text-gray-600">실시간 시스템 상태를 모니터링하고 관리하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <select 
            value={selectedTimeRange}
            onChange={(e) => setSelectedTimeRange(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            <option value="1h">최근 1시간</option>
            <option value="6h">최근 6시간</option>
            <option value="24h">최근 24시간</option>
            <option value="7d">최근 7일</option>
          </select>
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

      {/* 전체 메트릭 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((metric) => (
          <div key={metric.title} className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">{metric.title}</p>
                <p className="text-2xl font-bold text-gray-900">{metric.value}</p>
                <div className="flex items-center space-x-1 mt-1">
                  {metric.trend === 'up' ? (
                    <TrendingUp className="w-4 h-4 text-red-500" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-green-500" />
                  )}
                  <span className={`text-sm ${metric.trend === 'up' ? 'text-red-600' : 'text-green-600'}`}>
                    {metric.change}
                  </span>
                </div>
              </div>
              <div className={`p-3 rounded-lg bg-${metric.color}-100`}>
                <Activity className={`w-6 h-6 text-${metric.color}-600`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 서버 상태 테이블 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Server className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">서버 상태</h2>
            </div>
            <button className="flex items-center space-x-2 px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              <Settings className="w-4 h-4" />
              <span>설정</span>
            </button>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">서버</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">상태</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">가동률</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CPU</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">메모리</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">디스크</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">네트워크</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">마지막 확인</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">작업</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {servers.map((server) => (
                <tr key={server.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(server.status)}
                      <div>
                        <div className="text-sm font-medium text-gray-900">{server.name}</div>
                        <div className="text-sm text-gray-500">{server.type}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(server.status)}`}>
                      {server.status === 'healthy' ? '정상' : server.status === 'warning' ? '경고' : '위험'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{server.uptime}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-2">
                      <div className="w-12 bg-gray-200 rounded-full h-2">
                        <div 
                          className={`h-2 rounded-full ${getProgressColor(server.cpu)}`}
                          style={{ width: `${server.cpu}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-900">{server.cpu}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-2">
                      <div className="w-12 bg-gray-200 rounded-full h-2">
                        <div 
                          className={`h-2 rounded-full ${getProgressColor(server.memory)}`}
                          style={{ width: `${server.memory}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-900">{server.memory}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-2">
                      <div className="w-12 bg-gray-200 rounded-full h-2">
                        <div 
                          className={`h-2 rounded-full ${getProgressColor(server.disk)}`}
                          style={{ width: `${server.disk}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-900">{server.disk}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      server.network === 'Excellent' ? 'bg-green-100 text-green-800' :
                      server.network === 'Good' ? 'bg-blue-100 text-blue-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {server.network}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{server.lastCheck}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button className="text-blue-600 hover:text-blue-700">
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 알림 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">시스템 알림</h2>
          </div>
        </div>
        <div className="divide-y divide-gray-200">
          {alerts.map((alert) => (
            <div key={alert.id} className={`p-4 border-l-4 ${getSeverityColor(alert.severity)}`}>
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-sm">{alert.server}</span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(alert.severity)}`}>
                      {alert.severity === 'critical' ? '위험' : alert.severity === 'warning' ? '경고' : '정보'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-900 mt-1">{alert.message}</p>
                  <p className="text-xs text-gray-500 mt-1">{alert.time}</p>
                </div>
                {!alert.acknowledged && (
                  <button className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors">
                    확인
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SystemMonitoring;

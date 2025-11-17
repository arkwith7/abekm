import React from 'react';
import { 
  Users, 
  Database, 
  Activity, 
  TrendingUp, 
  AlertTriangle,
  CheckCircle,
  XCircle,
  Server,
  Cpu,
  HardDrive,
  Wifi
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const systemStats = [
    {
      title: '총 사용자',
      value: '1,234',
      change: '+5.2%',
      icon: Users,
      color: 'blue'
    },
    {
      title: '활성 세션',
      value: '89',
      change: '+12.1%',
      icon: Activity,
      color: 'green'
    },
    {
      title: '저장소 사용량',
      value: '2.4TB',
      change: '+8.5%',
      icon: Database,
      color: 'purple'
    },
    {
      title: '시스템 성능',
      value: '98.5%',
      change: '+0.3%',
      icon: TrendingUp,
      color: 'indigo'
    }
  ];

  const serverStatus = [
    {
      name: 'Web Server',
      status: 'healthy',
      cpu: 45,
      memory: 62,
      disk: 33
    },
    {
      name: 'Database Server',
      status: 'healthy',
      cpu: 32,
      memory: 78,
      disk: 56
    },
    {
      name: 'AI Processing Server',
      status: 'warning',
      cpu: 89,
      memory: 91,
      disk: 41
    },
    {
      name: 'File Storage Server',
      status: 'healthy',
      cpu: 23,
      memory: 45,
      disk: 67
    }
  ];

  const recentAlerts = [
    {
      id: 1,
      type: 'warning',
      message: 'AI Processing Server CPU 사용률 높음 (89%)',
      time: '5분 전',
      resolved: false
    },
    {
      id: 2,
      type: 'info',
      message: '시스템 백업 완료',
      time: '1시간 전',
      resolved: true
    },
    {
      id: 3,
      type: 'error',
      message: '로그인 실패 횟수 임계치 초과 (IP: 192.168.1.100)',
      time: '2시간 전',
      resolved: false
    },
    {
      id: 4,
      type: 'success',
      message: '보안 패치 적용 완료',
      time: '3시간 전',
      resolved: true
    }
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <CheckCircle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      default:
        return <Activity className="w-5 h-5 text-blue-500" />;
    }
  };

  const getProgressColor = (value: number) => {
    if (value >= 80) return 'bg-red-500';
    if (value >= 60) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="p-6 space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">시스템 관리 대시보드</h1>
          <p className="text-gray-600">전체 시스템 상태와 성능을 모니터링하세요</p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
            시스템 정상
          </div>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            리포트 생성
          </button>
        </div>
      </div>

      {/* 시스템 통계 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {systemStats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.title} className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                  <p className={`text-sm ${stat.change.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
                    {stat.change} 전월 대비
                  </p>
                </div>
                <div className={`p-3 rounded-lg bg-${stat.color}-100`}>
                  <Icon className={`w-6 h-6 text-${stat.color}-600`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 서버 상태 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <Server className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">서버 상태</h2>
            </div>
          </div>
          <div className="p-6 space-y-4">
            {serverStatus.map((server) => (
              <div key={server.name} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    {getStatusIcon(server.status)}
                    <span className="font-medium text-gray-900">{server.name}</span>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    server.status === 'healthy' ? 'bg-green-100 text-green-800' :
                    server.status === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {server.status}
                  </span>
                </div>
                
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Cpu className="w-4 h-4 text-gray-500" />
                      <span className="text-sm text-gray-600">CPU</span>
                    </div>
                    <span className="text-sm font-medium">{server.cpu}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${getProgressColor(server.cpu)}`}
                      style={{ width: `${server.cpu}%` }}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Activity className="w-4 h-4 text-gray-500" />
                      <span className="text-sm text-gray-600">Memory</span>
                    </div>
                    <span className="text-sm font-medium">{server.memory}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${getProgressColor(server.memory)}`}
                      style={{ width: `${server.memory}%` }}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <HardDrive className="w-4 h-4 text-gray-500" />
                      <span className="text-sm text-gray-600">Disk</span>
                    </div>
                    <span className="text-sm font-medium">{server.disk}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${getProgressColor(server.disk)}`}
                      style={{ width: `${server.disk}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 최근 알림 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5 text-gray-600" />
                <h2 className="text-lg font-semibold text-gray-900">최근 알림</h2>
              </div>
              <button className="text-blue-600 hover:text-blue-700 text-sm font-medium">
                모두 보기
              </button>
            </div>
          </div>
          <div className="divide-y divide-gray-200">
            {recentAlerts.map((alert) => (
              <div key={alert.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start space-x-3">
                  {getAlertIcon(alert.type)}
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${alert.resolved ? 'text-gray-500' : 'text-gray-900'}`}>
                      {alert.message}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">{alert.time}</p>
                  </div>
                  {alert.resolved && (
                    <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                      해결됨
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 네트워크 상태 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <Wifi className="w-5 h-5 text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">네트워크 상태</h2>
          </div>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">99.9%</div>
              <div className="text-sm text-gray-600">가용성</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">45ms</div>
              <div className="text-sm text-gray-600">평균 응답시간</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">1.2GB/s</div>
              <div className="text-sm text-gray-600">네트워크 처리량</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;

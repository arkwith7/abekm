import React, { useState, useEffect, useCallback } from 'react';
import { 
  Brain,
  Cpu,
  DollarSign,
  Activity,
  TrendingUp,
  Users,
  RefreshCw,
  AlertTriangle,
  Loader2,
  BarChart3,
  Zap
} from 'lucide-react';
import { 
  adminDashboardAPI, 
  AIUsageSummary, 
  AIUsageDaily, 
  AITopUser, 
  AIModelConfig 
} from '../../services/adminService';

const AIManagement: React.FC = () => {
  const [summary, setSummary] = useState<AIUsageSummary | null>(null);
  const [dailyUsage, setDailyUsage] = useState<AIUsageDaily[]>([]);
  const [topUsers, setTopUsers] = useState<AITopUser[]>([]);
  const [modelConfigs, setModelConfigs] = useState<AIModelConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDays, setSelectedDays] = useState(30);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [summaryData, dailyData, usersData, modelsData] = await Promise.all([
        adminDashboardAPI.getAIUsageSummary(selectedDays),
        adminDashboardAPI.getAIDailyUsage(selectedDays),
        adminDashboardAPI.getAITopUsers(selectedDays, 10),
        adminDashboardAPI.getAIModelConfigs()
      ]);
      
      setSummary(summaryData);
      setDailyUsage(dailyData);
      setTopUsers(usersData);
      setModelConfigs(modelsData);
    } catch (err) {
      console.error('AI 사용량 데이터 로드 실패:', err);
      setError('AI 사용량 데이터를 불러오는데 실패했습니다. 관리자 권한이 필요합니다.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedDays]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toLocaleString();
  };

  const formatCurrency = (amount: number) => {
    return `$${amount.toFixed(4)}`;
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
            <Brain className="w-7 h-7 text-purple-600" />
            <span>AI 사용량 관리</span>
          </h1>
          <p className="text-gray-600">LLM API 사용량 및 비용을 모니터링하세요</p>
        </div>
        <div className="flex items-center space-x-3">
          <select 
            value={selectedDays}
            onChange={(e) => setSelectedDays(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            <option value={7}>최근 7일</option>
            <option value={30}>최근 30일</option>
            <option value={90}>최근 90일</option>
          </select>
          <button 
            onClick={fetchData}
            disabled={isLoading}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>새로고침</span>
          </button>
        </div>
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
              <p className="text-sm font-medium text-gray-600">총 요청 수</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatNumber(summary?.summary.total_requests || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                성공률 {summary?.summary.success_rate.toFixed(1) || 0}%
              </p>
            </div>
            <div className="p-3 rounded-lg bg-blue-100">
              <Activity className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">총 토큰 수</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatNumber(summary?.summary.total_tokens || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                입력: {formatNumber(summary?.summary.total_input_tokens || 0)} / 
                출력: {formatNumber(summary?.summary.total_output_tokens || 0)}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-purple-100">
              <Zap className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">예상 비용</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(summary?.summary.total_cost_usd || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">USD 기준</p>
            </div>
            <div className="p-3 rounded-lg bg-green-100">
              <DollarSign className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">평균 응답 시간</p>
              <p className="text-2xl font-bold text-gray-900">
                {(summary?.summary.avg_latency_ms || 0).toFixed(0)}ms
              </p>
              <p className="text-xs text-gray-500 mt-1">전체 평균</p>
            </div>
            <div className="p-3 rounded-lg bg-orange-100">
              <TrendingUp className="w-6 h-6 text-orange-600" />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 제공자별 사용량 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">AI 제공자별 사용량</h2>
            </div>
          </div>
          <div className="p-6">
            {summary?.by_provider && summary.by_provider.length > 0 ? (
              <div className="space-y-4">
                {summary.by_provider.map((provider) => (
                  <div key={provider.provider} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div>
                      <div className="font-medium text-gray-900 capitalize">{provider.provider}</div>
                      <div className="text-sm text-gray-500">{formatNumber(provider.tokens)} 토큰</div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium text-gray-900">{provider.requests.toLocaleString()} 요청</div>
                      <div className="text-sm text-green-600">{formatCurrency(provider.cost)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Cpu className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>아직 AI 사용 기록이 없습니다</p>
              </div>
            )}
          </div>
        </div>

        {/* 상위 사용자 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <Users className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">상위 사용자</h2>
            </div>
          </div>
          <div className="p-6">
            {topUsers && topUsers.length > 0 ? (
              <div className="space-y-3">
                {topUsers.map((user, index) => (
                  <div key={user.user_emp_no} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800' :
                        index === 1 ? 'bg-gray-200 text-gray-800' :
                        index === 2 ? 'bg-orange-100 text-orange-800' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {index + 1}
                      </span>
                      <span className="font-medium text-gray-900">{user.user_emp_no}</span>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900">{formatNumber(user.tokens)} 토큰</div>
                      <div className="text-xs text-gray-500">{user.requests} 요청</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Users className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>아직 사용자별 기록이 없습니다</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 모델 비용 설정 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">등록된 AI 모델 및 비용 단가</h2>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">제공자</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">모델</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">표시 이름</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">입력 ($/1K)</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">출력 ($/1K)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {modelConfigs.map((config) => (
                <tr key={config.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      config.provider === 'bedrock' ? 'bg-orange-100 text-orange-800' :
                      config.provider === 'azure_openai' ? 'bg-blue-100 text-blue-800' :
                      'bg-green-100 text-green-800'
                    }`}>
                      {config.provider}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                    {config.model}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {config.display_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                    {config.input_cost_per_1k ? `$${config.input_cost_per_1k.toFixed(5)}` : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                    {config.output_cost_per_1k ? `$${config.output_cost_per_1k.toFixed(5)}` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 안내 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <Brain className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-800">AI 사용량 추적 안내</h3>
            <p className="text-sm text-blue-700 mt-1">
              AI 사용량은 Agent Chat, 문서 요약, 검색 등 LLM API 호출 시 자동으로 기록됩니다.
              현재 표시된 비용은 설정된 단가 기준 추정치이며, 실제 청구 비용과 다를 수 있습니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIManagement;


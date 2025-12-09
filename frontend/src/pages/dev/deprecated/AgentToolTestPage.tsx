import React, { useEffect, useState } from 'react';
import { useSelectedDocuments } from '../../contexts/GlobalAppContext';
import type { Document as GlobalDocument } from '../../contexts/types';
import { getApiUrl } from '../../utils/apiConfig';

interface AgentCapability {
    tool_name: string;
    description: string;
    available: boolean;
}

interface AgentCapabilities {
    [agentType: string]: AgentCapability;
}

const AgentToolTestPage: React.FC = () => {
    console.log('🔧 AgentToolTestPage 컴포넌트 로드됨');

    const [capabilities, setCapabilities] = useState<AgentCapabilities>({});
    const [selectedAgent, setSelectedAgent] = useState<string>('general');
    const [testQuery, setTestQuery] = useState<string>('');
    const [testResult, setTestResult] = useState<any>(null);
    // Presentation options (dev only) - defaults
    const [pptOptions, setPptOptions] = useState<{ slideCount: number; templateStyle: string; includeCharts: boolean }>({
        slideCount: 8,
        templateStyle: 'business',
        includeCharts: true
    });
    const [isLoading, setIsLoading] = useState(false);
    const [isDownloading, setIsDownloading] = useState(false);
    const { selectedDocuments } = useSelectedDocuments();

    // 에이전트 역량 정보 로드
    useEffect(() => {
        const fetchCapabilities = async () => {
            try {
                const token = localStorage.getItem('ABEKM_token');

                // 토큰이 없거나 유효하지 않으면 요청하지 않음
                if (!token || token === 'undefined' || token === 'null') {
                    console.log('유효한 토큰이 없어 capabilities 요청을 건너뜁니다.');
                    setCapabilities({}); // 빈 capabilities 설정
                    return;
                }

                console.log('🔍 Capabilities API 호출 시도...');

                const apiBaseUrl = getApiUrl();
                const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/chat/multi-agent/capabilities` : '/api/v1/chat/multi-agent/capabilities';
                
                const response = await fetch(apiUrl, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });

                if (!response.ok) {
                    if (response.status === 401) {
                        console.log('토큰이 만료되어 capabilities 요청이 실패했습니다.');
                        setCapabilities({}); // 빈 capabilities 설정
                        return; // 401 에러 시 조용히 반환
                    }
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                if (data.success) {
                    console.log('✅ Capabilities 로드 성공:', data.agent_capabilities);
                    setCapabilities(data.agent_capabilities);
                } else {
                    console.log('❌ Capabilities 응답 실패:', data);
                    setCapabilities({});
                }
            } catch (error) {
                console.error('에이전트 역량 조회 실패:', error);
                setCapabilities({}); // 에러 시에도 빈 capabilities 설정
            }
        };

        fetchCapabilities();

        // 토큰 업데이트 이벤트 리스너 추가
        const handleTokenUpdate = () => {
            console.log('토큰이 업데이트되어 capabilities를 다시 로드합니다.');
            fetchCapabilities();
        };

        window.addEventListener('token:updated', handleTokenUpdate);

        // 컴포넌트 언마운트 시 이벤트 리스너 제거
        return () => {
            window.removeEventListener('token:updated', handleTokenUpdate);
        };
    }, []); // 의존성 배열을 빈 배열로 유지

    // 에이전트 툴 테스트 실행
    const handleTestAgent = async () => {
        if (!testQuery.trim()) return;

        setIsLoading(true);
        setTestResult(null);

        try {
            const token = localStorage.getItem('ABEKM_token');
            const apiBaseUrl = getApiUrl();
            const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/chat/agent-tool/execute` : '/api/v1/chat/agent-tool/execute';
            
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    agent_type: selectedAgent,
                    user_query: selectedAgent === 'presentation'
                        ? `[[PPT_OPTS:${JSON.stringify({
                            slide_count: pptOptions.slideCount,
                            template_style: pptOptions.templateStyle,
                            include_charts: pptOptions.includeCharts
                        })}]]\n` + testQuery
                        : testQuery,
                    selected_documents: selectedDocuments.map((doc: GlobalDocument) => ({
                        id: doc.fileId,
                        fileName: doc.fileName,
                        fileType: doc.fileType,
                        originalName: doc.originalName,
                        fileSize: doc.fileSize,
                        uploadDate: doc.uploadDate,
                        containerName: doc.containerName,
                        containerId: doc.containerId,
                        content: doc.content || '',
                        summary: doc.summary || '',
                        keywords: doc.keywords || []
                    }))
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            setTestResult(data);
        } catch (error) {
            console.error('에이전트 툴 테스트 실패:', error);
            setTestResult({
                success: false,
                error: error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.'
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold mb-6">🔧 AI Agent Tool 테스트</h1>

            {/* 에이전트 역량 현황 */}
            <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                <h2 className="text-lg font-semibold mb-4">📊 에이전트 툴 현황</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(capabilities).map(([agentType, capability]) => (
                        <div
                            key={agentType}
                            className={`p-3 rounded border ${capability.available
                                ? 'bg-green-50 border-green-200'
                                : 'bg-yellow-50 border-yellow-200'
                                }`}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="font-medium">{agentType}</span>
                                <span className={`px-2 py-1 rounded text-xs ${capability.available
                                    ? 'bg-green-100 text-green-800'
                                    : 'bg-yellow-100 text-yellow-800'
                                    }`}>
                                    {capability.available ? '✅ 사용가능' : '🚧 구현중'}
                                </span>
                            </div>
                            <p className="text-sm text-gray-600 mb-1">{capability.description}</p>
                            <p className="text-xs text-gray-500">툴: {capability.tool_name}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* 테스트 인터페이스 */}
            <div className="bg-white border rounded-lg p-6">
                <h2 className="text-lg font-semibold mb-4">🧪 에이전트 툴 테스트</h2>

                {/* 에이전트 선택 */}
                <div className="mb-4">
                    <label className="block text-sm font-medium mb-2">테스트할 에이전트:</label>
                    <select
                        value={selectedAgent}
                        onChange={(e) => setSelectedAgent(e.target.value)}
                        className="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500"
                    >
                        {Object.entries(capabilities).map(([agentType, capability]) => (
                            <option
                                key={agentType}
                                value={agentType}
                                disabled={!capability.available}
                            >
                                {agentType} {!capability.available && '(구현중)'}
                            </option>
                        ))}
                    </select>
                </div>

                {/* 선택된 문서 표시 */}
                {selectedDocuments.length > 0 && (
                    <div className="mb-4 p-3 bg-blue-50 rounded">
                        <p className="text-sm font-medium text-blue-800 mb-2">
                            선택된 문서 ({selectedDocuments.length}개):
                        </p>
                        {selectedDocuments.slice(0, 3).map((doc: GlobalDocument) => (
                            <p key={doc.fileId} className="text-xs text-blue-600">
                                📄 {doc.fileName}
                            </p>
                        ))}
                        {selectedDocuments.length > 3 && (
                            <p className="text-xs text-blue-500">외 {selectedDocuments.length - 3}개...</p>
                        )}
                    </div>
                )}

                {/* Presentation options (dev only) */}
                {selectedAgent === 'presentation' && (
                    <div className="mb-4 p-3 border rounded bg-purple-50">
                        <p className="text-sm font-medium text-purple-800 mb-2">프레젠테이션 옵션</p>
                        <div className="flex flex-wrap gap-4">
                            <label className="flex flex-col text-xs font-medium text-purple-700">
                                슬라이드 수
                                <input
                                    type="number"
                                    min={1}
                                    max={40}
                                    value={pptOptions.slideCount}
                                    onChange={(e) => setPptOptions(o => ({ ...o, slideCount: Math.max(1, Math.min(40, parseInt(e.target.value, 10) || 1)) }))}
                                    className="mt-1 px-2 py-1 border border-purple-300 rounded bg-white"
                                />
                            </label>
                            <label className="flex flex-col text-xs font-medium text-purple-700">
                                템플릿 스타일
                                <select
                                    value={pptOptions.templateStyle}
                                    onChange={(e) => setPptOptions(o => ({ ...o, templateStyle: e.target.value }))}
                                    className="mt-1 px-2 py-1 border border-purple-300 rounded bg-white"
                                >
                                    <option value="business">Business</option>
                                    <option value="minimal">Minimal</option>
                                    <option value="modern">Modern</option>
                                    <option value="playful">Playful</option>
                                </select>
                            </label>
                            <label className="flex items-center gap-2 text-xs font-medium text-purple-700 mt-5">
                                <input
                                    type="checkbox"
                                    checked={pptOptions.includeCharts}
                                    onChange={() => setPptOptions(o => ({ ...o, includeCharts: !o.includeCharts }))}
                                    className="w-4 h-4 text-purple-600 border-purple-300 rounded"
                                />
                                차트 포함
                            </label>
                        </div>
                        <p className="mt-2 text-[11px] text-purple-600">옵션은 [[PPT_OPTS:...]] 마커로 프롬프트 앞부분에 삽입되어 백엔드에서 파싱할 수 있습니다.</p>
                    </div>
                )}

                {/* 테스트 쿼리 입력 */}
                <div className="mb-4">
                    <label className="block text-sm font-medium mb-2">테스트 쿼리:</label>
                    <textarea
                        value={testQuery}
                        onChange={(e) => setTestQuery(e.target.value)}
                        placeholder="에이전트가 처리할 내용을 입력하세요..."
                        className="w-full p-3 border rounded focus:ring-2 focus:ring-blue-500"
                        rows={3}
                    />
                </div>

                {/* 테스트 실행 버튼 */}
                <button
                    onClick={handleTestAgent}
                    disabled={isLoading || !testQuery.trim() || !capabilities[selectedAgent]?.available}
                    className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                    {isLoading ? '🔄 실행 중...' : '🚀 에이전트 툴 테스트'}
                </button>
            </div>

            {/* 테스트 결과 */}
            {testResult && (
                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                    <h3 className="text-lg font-semibold mb-3">📋 테스트 결과</h3>

                    {testResult.success ? (
                        <div className="space-y-4">
                            {/* 실행 정보 */}
                            <div className="p-3 bg-green-50 rounded border border-green-200">
                                <p className="text-sm font-medium text-green-800">✅ 실행 성공</p>
                                <p className="text-xs text-green-600">
                                    에이전트: {testResult.agent_type} |
                                    실행 모드: {testResult.tool_execution_result?.execution_mode}
                                </p>
                                {testResult.tool_execution_result?.tool_used && (
                                    <p className="text-xs text-green-600">
                                        사용된 툴: {testResult.tool_execution_result.tool_used}
                                    </p>
                                )}
                                {testResult.tool_execution_result?.tool_result?.file_path && (
                                    <p className="mt-2 text-xs flex items-center gap-2">
                                        📎 <button
                                            type="button"
                                            onClick={async () => {
                                                if (isDownloading) return;
                                                try {
                                                    setIsDownloading(true);
                                                    const token = localStorage.getItem('ABEKM_token');
                                                    const rawName = testResult.tool_execution_result.tool_result.file_name || testResult.tool_execution_result.tool_result.file_path.split('/').pop();
                                                    const url = `/api/v1/agent/presentation/download/${encodeURIComponent(rawName)}`;
                                                    const resp = await fetch(url, {
                                                        headers: { 'Authorization': `Bearer ${token}` }
                                                    });
                                                    if (!resp.ok) {
                                                        const txt = await resp.text();
                                                        throw new Error(`HTTP ${resp.status} - ${txt.slice(0, 120)}`);
                                                    }
                                                    const blob = await resp.blob();
                                                    const dlUrl = window.URL.createObjectURL(blob);
                                                    const a = document.createElement('a');
                                                    a.href = dlUrl;
                                                    a.download = rawName;
                                                    document.body.appendChild(a);
                                                    a.click();
                                                    a.remove();
                                                    setTimeout(() => window.URL.revokeObjectURL(dlUrl), 4000);
                                                } catch (e) {
                                                    alert(`다운로드 실패: ${(e as Error).message}`);
                                                } finally {
                                                    setIsDownloading(false);
                                                }
                                            }}
                                            className="px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-400"
                                            disabled={isDownloading}
                                        >{isDownloading ? '다운로드 중...' : 'PPT 다운로드'}</button>
                                    </p>
                                )}
                            </div>

                            {/* 응답 내용 */}
                            {testResult.tool_execution_result?.response && (
                                <div className="p-3 bg-white rounded border">
                                    <p className="text-sm font-medium mb-2">🤖 AI 응답:</p>
                                    <div className="text-sm text-gray-700 whitespace-pre-wrap">
                                        {testResult.tool_execution_result.response}
                                    </div>
                                </div>
                            )}

                            {/* 상세 결과 (개발자용) */}
                            <details className="text-xs">
                                <summary className="cursor-pointer text-gray-600 hover:text-gray-800">
                                    🔍 상세 결과 보기 (개발자용)
                                </summary>
                                <pre className="mt-2 p-3 bg-gray-100 rounded overflow-x-auto text-xs">
                                    {JSON.stringify(testResult, null, 2)}
                                </pre>
                            </details>
                        </div>
                    ) : (
                        <div className="p-3 bg-red-50 rounded border border-red-200">
                            <p className="text-sm font-medium text-red-800">❌ 실행 실패</p>
                            <p className="text-xs text-red-600">
                                {testResult.error || testResult.detail || '알 수 없는 오류'}
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default AgentToolTestPage;

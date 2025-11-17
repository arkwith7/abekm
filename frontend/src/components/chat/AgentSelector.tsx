/**
 * AI Agent 선택 컴포넌트
 * 단일 Agent 또는 Agent Chain 선택 가능
 */
import { Bot, ChevronRight, Clock, FileText, Info, Zap } from 'lucide-react';
import React from 'react';
import { AGENT_CHAINS, AGENT_CONFIGS, AgentType } from '../../contexts/types';

interface AgentSelectorProps {
    selectedAgent: AgentType | null;
    selectedAgentChain: string | null;
    isChainMode: boolean;
    onAgentSelect: (agent: AgentType) => void;
    onAgentChainSelect: (chainId: string) => void;
    onModeChange: (isChainMode: boolean) => void;
    requiredDocuments?: number;
    className?: string;
}

export const AgentSelector: React.FC<AgentSelectorProps> = ({
    selectedAgent,
    selectedAgentChain,
    isChainMode,
    onAgentSelect,
    onAgentChainSelect,
    onModeChange,
    requiredDocuments = 0,
    className = ''
}) => {
    // 사용 가능한 Agent들 필터링 (필요한 문서 수 조건)
    const availableAgents = Object.values(AGENT_CONFIGS).filter(
        agent => agent.requiredDocuments <= requiredDocuments || agent.requiredDocuments === 0
    );

    // 사용 가능한 Agent Chain들 필터링
    const availableChains = AGENT_CHAINS.filter(
        chain => !chain.requiresDocuments || requiredDocuments > 0
    );

    const formatTime = (seconds: number) => {
        if (seconds < 60) return `${seconds}초`;
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return remainingSeconds > 0 ? `${minutes}분 ${remainingSeconds}초` : `${minutes}분`;
    };

    return (
        <div className={`bg-white rounded-lg border border-gray-200 ${className}`}>
            {/* 모드 선택 탭 */}
            <div className="flex border-b border-gray-200">
                <button
                    onClick={() => onModeChange(false)}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${!isChainMode
                        ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                        : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <Bot className="w-4 h-4 inline mr-2" />
                    단일 Agent
                </button>
                <button
                    onClick={() => onModeChange(true)}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${isChainMode
                        ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                        : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <Zap className="w-4 h-4 inline mr-2" />
                    Agent Chain
                </button>
            </div>

            <div className="p-4">
                {!isChainMode ? (
                    /* 단일 Agent 선택 */
                    <div className="space-y-3">
                        <div className="text-sm text-gray-600 mb-4">
                            원하는 AI Agent를 선택하세요.
                            {requiredDocuments > 0 && (
                                <span className="text-blue-600 font-medium">
                                    (선택된 문서: {requiredDocuments}개)
                                </span>
                            )}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {availableAgents.map((agent) => (
                                <div
                                    key={agent.type}
                                    className={`relative p-3 border rounded-lg cursor-pointer transition-all ${selectedAgent === agent.type
                                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                        }`}
                                    onClick={() => onAgentSelect(agent.type)}
                                >
                                    <div className="flex items-start space-x-3">
                                        <div className="text-2xl flex-shrink-0">{agent.icon}</div>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-medium text-gray-900 text-sm">{agent.name}</h4>
                                            <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                                                {agent.description}
                                            </p>
                                            <div className="flex items-center space-x-3 mt-2 text-xs text-gray-500">
                                                <span className="flex items-center">
                                                    <Clock className="w-3 h-3 mr-1" />
                                                    {formatTime(agent.estimatedTime)}
                                                </span>
                                                <span className="flex items-center">
                                                    <FileText className="w-3 h-3 mr-1" />
                                                    {agent.outputFormat}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* 선택 표시 */}
                                    {selectedAgent === agent.type && (
                                        <div className="absolute top-2 right-2 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
                                            <div className="w-2 h-2 bg-white rounded-full" />
                                        </div>
                                    )}

                                    {/* 문서 요구사항 부족 시 비활성화 표시 */}
                                    {agent.requiredDocuments > requiredDocuments && requiredDocuments >= 0 && (
                                        <div className="absolute inset-0 bg-gray-100 bg-opacity-75 rounded-lg flex items-center justify-center">
                                            <div className="text-xs text-gray-600 text-center px-2">
                                                최소 {agent.requiredDocuments}개 문서 필요
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    /* Agent Chain 선택 */
                    <div className="space-y-3">
                        <div className="text-sm text-gray-600 mb-4">
                            여러 Agent를 조합한 워크플로우를 선택하세요.
                        </div>

                        <div className="space-y-3">
                            {availableChains.map((chain) => (
                                <div
                                    key={chain.id}
                                    className={`p-4 border rounded-lg cursor-pointer transition-all ${selectedAgentChain === chain.id
                                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                        }`}
                                    onClick={() => onAgentChainSelect(chain.id)}
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1">
                                            <h4 className="font-medium text-gray-900 text-sm mb-1">{chain.name}</h4>
                                            <p className="text-xs text-gray-600 mb-3">{chain.description}</p>

                                            {/* Agent 순서 표시 */}
                                            <div className="flex items-center space-x-1 mb-3">
                                                {chain.agents.map((agentType, index) => {
                                                    const agent = AGENT_CONFIGS[agentType];
                                                    return (
                                                        <React.Fragment key={agentType}>
                                                            <div className="flex items-center space-x-1 px-2 py-1 bg-white rounded border">
                                                                <span className="text-xs">{agent.icon}</span>
                                                                <span className="text-xs font-medium">{agent.name}</span>
                                                            </div>
                                                            {index < chain.agents.length - 1 && (
                                                                <ChevronRight className="w-3 h-3 text-gray-400" />
                                                            )}
                                                        </React.Fragment>
                                                    );
                                                })}
                                            </div>

                                            <div className="flex items-center space-x-4 text-xs text-gray-500">
                                                <span className="flex items-center">
                                                    <Clock className="w-3 h-3 mr-1" />
                                                    약 {formatTime(chain.estimatedTime)}
                                                </span>
                                                <span className="flex items-center">
                                                    <FileText className="w-3 h-3 mr-1" />
                                                    {chain.outputFormat}
                                                </span>
                                                <span className="text-blue-600">
                                                    {chain.agents.length}단계 프로세스
                                                </span>
                                            </div>
                                        </div>

                                        {/* 선택 표시 */}
                                        {selectedAgentChain === chain.id && (
                                            <div className="w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0">
                                                <div className="w-2 h-2 bg-white rounded-full" />
                                            </div>
                                        )}
                                    </div>

                                    {/* 문서 요구사항 부족 시 비활성화 표시 */}
                                    {chain.requiresDocuments && requiredDocuments === 0 && (
                                        <div className="absolute inset-0 bg-gray-100 bg-opacity-75 rounded-lg flex items-center justify-center">
                                            <div className="text-xs text-gray-600 text-center px-2">
                                                문서 선택이 필요합니다
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* 도움말 정보 */}
                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-start space-x-2">
                        <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                        <div className="text-xs text-blue-800">
                            <p className="font-medium mb-1">💡 사용 팁</p>
                            <ul className="list-disc list-inside space-y-1">
                                <li><strong>단일 Agent</strong>: 특정 작업에 특화된 빠른 처리</li>
                                <li><strong>Agent Chain</strong>: 복합적인 작업을 단계별로 수행</li>
                                <li>문서를 선택하면 더 많은 Agent를 사용할 수 있습니다</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AgentSelector;

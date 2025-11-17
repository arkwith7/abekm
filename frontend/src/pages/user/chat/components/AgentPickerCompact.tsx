import React, { useMemo } from 'react';
import { AGENT_CHAINS, AGENT_CONFIGS, AgentType } from '../../../../contexts/types';

type Mode = 'single' | 'multi' | 'chain';

interface AgentPickerCompactProps {
    mode: Mode;
    selectedAgent: AgentType | null;
    selectedAgents: AgentType[];
    selectedAgentChain: string | null;
    onChangeMode: (mode: Mode) => void;
    onSelectAgent: (agent: AgentType) => void;
    onToggleAgent: (agent: AgentType) => void;
    onSelectChain: (chainId: string) => void;
}

const tabs: { key: Mode; label: string }[] = [
    { key: 'single', label: '단일' },
    { key: 'multi', label: '멀티' },
    { key: 'chain', label: '체인' },
];

const AgentPickerCompact: React.FC<AgentPickerCompactProps> = ({
    mode,
    selectedAgent,
    selectedAgents,
    selectedAgentChain,
    onChangeMode,
    onSelectAgent,
    onToggleAgent,
    onSelectChain,
}) => {
    const agentList = useMemo(() => Object.values(AGENT_CONFIGS), []);

    return (
        <div className="w-full">
            {/* Mode tabs */}
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden mb-2">
                {tabs.map(t => (
                    <button
                        key={t.key}
                        onClick={() => onChangeMode(t.key)}
                        className={`px-3 py-1.5 text-sm ${mode === t.key ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            {mode === 'single' && (
                <div className="flex flex-wrap gap-2">
                    {agentList.map(a => (
                        <button
                            key={a.type}
                            onClick={() => onSelectAgent(a.type)}
                            className={`px-2.5 py-1.5 text-sm rounded-md border ${selectedAgent === a.type ? 'bg-blue-50 border-blue-400 text-blue-700' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'}`}
                            title={a.description}
                        >
                            <span className="mr-1">{a.icon}</span>{a.name}
                        </button>
                    ))}
                </div>
            )}

            {mode === 'multi' && (
                <div className="flex flex-wrap gap-2">
                    {agentList.map(a => (
                        <button
                            key={a.type}
                            onClick={() => onToggleAgent(a.type)}
                            className={`px-2.5 py-1.5 text-sm rounded-md border ${selectedAgents.includes(a.type) ? 'bg-purple-50 border-purple-400 text-purple-700' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'}`}
                            title={a.description}
                        >
                            <span className="mr-1">{a.icon}</span>{a.name}
                        </button>
                    ))}
                </div>
            )}

            {mode === 'chain' && (
                <div className="flex flex-wrap gap-2">
                    {AGENT_CHAINS.map(chain => (
                        <button
                            key={chain.id}
                            onClick={() => onSelectChain(chain.id)}
                            className={`px-2.5 py-1.5 text-sm rounded-md border ${selectedAgentChain === chain.id ? 'bg-emerald-50 border-emerald-400 text-emerald-700' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'}`}
                            title={chain.description}
                        >
                            {chain.name}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};

export default AgentPickerCompact;

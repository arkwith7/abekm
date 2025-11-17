import { ChevronRight } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { ConversationState } from '../types/chat.types';
import ConversationContextPanel from './ConversationContextPanel';

interface ConversationContextToggleProps {
    state: ConversationState;
    isLoading?: boolean;
}

const ConversationContextToggle: React.FC<ConversationContextToggleProps> = ({ state, isLoading }) => {
    const [isOpen, setIsOpen] = useState(false);

    const formattedUpdatedAt = useMemo(() => {
        try {
            return new Date(state.updatedAt).toLocaleTimeString();
        } catch (error) {
            return '';
        }
    }, [state.updatedAt]);

    const toggleLabel = isOpen ? '대화 컨텍스트 접기' : '대화 컨텍스트 펼치기';

    return (
        <div className="max-w-2xl mx-auto w-full">
            <button
                type="button"
                onClick={() => setIsOpen((prev) => !prev)}
                className="flex w-full items-center justify-between rounded-xl border border-gray-200 bg-white/80 px-3 py-2 text-left shadow-sm transition hover:border-blue-300 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                aria-expanded={isOpen}
                aria-controls="conversation-context-panel"
            >
                <span className="flex items-center gap-2">
                    <ChevronRight
                        className={`h-4 w-4 transition-transform duration-200 ${isOpen ? 'rotate-90 text-blue-600' : 'text-gray-400'}`}
                        aria-hidden="true"
                    />
                    <span className="text-sm font-medium text-gray-700">{toggleLabel}</span>
                </span>
                {formattedUpdatedAt && (
                    <span className="text-xs text-gray-400">마지막 업데이트 {formattedUpdatedAt}</span>
                )}
            </button>

            {isOpen && (
                <div id="conversation-context-panel" className="mt-3">
                    <ConversationContextPanel state={state} isLoading={isLoading} showHeader={false} />
                </div>
            )}
        </div>
    );
};

export default ConversationContextToggle;

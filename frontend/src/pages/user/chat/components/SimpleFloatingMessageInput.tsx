import { ChevronDown, ChevronUp, Paperclip, Send, Square } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AGENT_CHAINS, AGENT_CONFIGS, AgentType } from '../../../../contexts/types';
import AgentPickerCompact from './AgentPickerCompact';

interface SimpleFloatingMessageInputProps {
    onSendMessage: (message: string, files?: File[], voiceBlob?: Blob) => void;
    onStopStreaming?: () => void;
    isLoading: boolean;
    mode: 'single' | 'multi' | 'chain';
    selectedAgent: string | null;
    selectedAgents: string[];
    selectedAgentChain: string | null;
    onChangeMode: (mode: 'single' | 'multi' | 'chain') => void;
    onSelectAgent: (agentId: string) => void;
    onToggleAgent: (agentId: string) => void;
    onSelectChain: (chainId: string) => void;
    placeholder?: string;
}

const SimpleFloatingMessageInput: React.FC<SimpleFloatingMessageInputProps> = ({
    onSendMessage,
    onStopStreaming,
    isLoading,
    mode,
    selectedAgent,
    selectedAgents,
    selectedAgentChain,
    onChangeMode,
    onSelectAgent,
    onToggleAgent,
    onSelectChain,
    placeholder = "메시지를 입력하세요..."
}) => {
    const [message, setMessage] = useState('');
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isAgentPanelOpen, setAgentPanelOpen] = useState(false);

    const agentSummary = useMemo(() => {
        if (mode === 'chain') {
            const chain = AGENT_CHAINS.find(c => c.id === selectedAgentChain);
            return chain ? `체인: ${chain.name}` : '체인: 미선택';
        }
        if (mode === 'multi') {
            const names = (selectedAgents as AgentType[])
                .map(a => AGENT_CONFIGS[a]?.name || a)
                .slice(0, 2);
            const more = selectedAgents.length > 2 ? ` 외 ${selectedAgents.length - 2}개` : '';
            return selectedAgents.length > 0
                ? `멀티: ${names.join(', ')}${more}`
                : '멀티: 미선택';
        }
        const a = (selectedAgent as AgentType) || 'general';
        const name = AGENT_CONFIGS[a]?.name || a;
        return `단일: ${name}`;
    }, [mode, selectedAgent, selectedAgents, selectedAgentChain]);

    // 기존 select 기반 옵션 제거, AgentPickerCompact 사용

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if ((message.trim() || selectedFiles.length > 0) && !isLoading) {
            onSendMessage(message.trim(), selectedFiles);
            setMessage('');
            setSelectedFiles([]);
            // reset height after clearing
            setTimeout(() => adjustTextareaHeight(), 0);
        }
    };

    // Auto-resize textarea height (grow upward as container is bottom-fixed)
    const adjustTextareaHeight = () => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = 'auto';
        const nextH = Math.min(el.scrollHeight, 120); // clamp max height
        el.style.height = `${Math.max(nextH, 48)}px`;
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        // Avoid global handlers (e.g., space for slide navigation) from intercepting typing
        e.stopPropagation();
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
        // allow Space and others by default
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setSelectedFiles(Array.from(e.target.files));
        }
    };

    const removeFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    // 🎯 클립보드 이미지 붙여넣기 핸들러
    const handlePaste = async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
        const items = e.clipboardData?.items;
        if (!items) return;

        const imageFiles: File[] = [];

        // 클립보드 아이템 순회
        for (let i = 0; i < items.length; i++) {
            const item = items[i];

            // 이미지 타입 확인
            if (item.type.indexOf('image') !== -1) {
                e.preventDefault(); // 기본 붙여넣기 동작 방지

                const file = item.getAsFile();
                if (file) {
                    // 파일명 생성 (timestamp + 원본 확장자)
                    const timestamp = new Date().getTime();
                    const extension = file.type.split('/')[1] || 'png';
                    const newFile = new File(
                        [file],
                        `clipboard-image-${timestamp}.${extension}`,
                        { type: file.type }
                    );
                    imageFiles.push(newFile);
                }
            }
        }

        // 이미지가 있으면 파일 목록에 추가
        if (imageFiles.length > 0) {
            setSelectedFiles(prev => [...prev, ...imageFiles]);
            console.log(`📋 클립보드에서 ${imageFiles.length}개 이미지 붙여넣기 완료`);
        }
    };

    useEffect(() => {
        if (textareaRef.current && !isLoading) {
            textareaRef.current.focus();
            adjustTextareaHeight();
        }
    }, [isLoading]);

    return (
        <div className="w-full">
            {/* 에이전트 선택기 (접기/펼치기) */}
            <div className="mb-2">
                <div className="flex items-center justify-between px-2 py-1.5 rounded-md bg-gray-50 border border-gray-200">
                    <div className="flex items-center gap-2 text-sm text-gray-700">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-700">
                            에이전트
                        </span>
                        <span className="truncate max-w-[60vw] sm:max-w-[40vw] md:max-w-[30vw]" title={agentSummary}>{agentSummary}</span>
                    </div>
                    <button
                        type="button"
                        aria-expanded={isAgentPanelOpen}
                        onClick={() => setAgentPanelOpen(o => !o)}
                        className="inline-flex items-center gap-1 text-sm text-gray-600 hover:text-gray-800"
                        title={isAgentPanelOpen ? '접기' : '펼치기'}
                    >
                        <span>{isAgentPanelOpen ? '접기' : '펼치기'}</span>
                        {isAgentPanelOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                </div>
                {isAgentPanelOpen && (
                    <div className="mt-2">
                        <AgentPickerCompact
                            mode={mode}
                            selectedAgent={selectedAgent as any}
                            selectedAgents={selectedAgents as any}
                            selectedAgentChain={selectedAgentChain}
                            onChangeMode={onChangeMode}
                            onSelectAgent={(a) => onSelectAgent(a)}
                            onToggleAgent={(a) => onToggleAgent(a)}
                            onSelectChain={(id) => onSelectChain(id)}
                        />
                    </div>
                )}
            </div>

            {/* Presentation inline options removed for main chat screen */}

            {/* 선택된 파일들 */}
            {selectedFiles.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-2">
                    {selectedFiles.map((file, index) => {
                        const isImage = file.type.startsWith('image/');
                        const previewUrl = isImage ? URL.createObjectURL(file) : null;

                        return (
                            <div
                                key={index}
                                className="flex items-center space-x-2 bg-blue-50 px-3 py-2 rounded-lg border border-blue-200"
                            >
                                {/* 이미지 미리보기 */}
                                {isImage && previewUrl && (
                                    <img
                                        src={previewUrl}
                                        alt={file.name}
                                        className="w-10 h-10 object-cover rounded"
                                        onLoad={() => URL.revokeObjectURL(previewUrl)} // 메모리 정리
                                    />
                                )}
                                <div className="flex flex-col">
                                    <span className="text-sm text-blue-700">{file.name}</span>
                                    {isImage && (
                                        <span className="text-xs text-blue-500">
                                            🖼️ {(file.size / 1024).toFixed(1)}KB
                                        </span>
                                    )}
                                </div>
                                <button
                                    onClick={() => removeFile(index)}
                                    className="text-blue-500 hover:text-blue-700 font-bold"
                                    title="파일 제거"
                                >
                                    ×
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* 메시지 입력 폼 */}
            <form onSubmit={handleSubmit} className="flex items-end space-x-3">
                {/* 파일 첨부 버튼 */}
                <div className="flex-shrink-0">
                    <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        onChange={handleFileSelect}
                        className="hidden"
                        accept=".pdf,.doc,.docx,.txt,.ppt,.pptx,.xls,.xlsx,image/*"
                    />
                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="p-3 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        title="파일 첨부 (이미지 포함)"
                    >
                        <Paperclip className="w-5 h-5" />
                    </button>
                </div>

                {/* 텍스트 입력 영역 */}
                <div className="flex-1 min-w-0">
                    <textarea
                        ref={textareaRef}
                        value={message}
                        onChange={(e) => { setMessage(e.target.value); adjustTextareaHeight(); }}
                        onKeyDown={handleKeyDown}
                        onPaste={handlePaste}
                        placeholder={placeholder}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                        rows={1}
                        style={{ minHeight: '48px', maxHeight: '120px' }}
                        spellCheck={true}
                        autoCorrect="on"
                        autoCapitalize="sentences"
                    />
                    {/* 붙여넣기 힌트 */}
                    <div className="mt-1 text-xs text-gray-400">
                        💡 Ctrl+V로 이미지 붙여넣기 가능
                    </div>
                </div>

                {/* 전송/중지 버튼 */}
                <div className="flex-shrink-0">
                    {isLoading ? (
                        <button
                            type="button"
                            onClick={onStopStreaming}
                            className="p-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                            title="스트리밍 중지"
                        >
                            <Square className="w-5 h-5" />
                        </button>
                    ) : (
                        <button
                            type="submit"
                            disabled={!message.trim() && selectedFiles.length === 0}
                            className={`p-3 rounded-lg transition-colors ${message.trim() || selectedFiles.length > 0
                                ? 'bg-blue-500 text-white hover:bg-blue-600'
                                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                }`}
                            title="메시지 전송"
                        >
                            <Send className="w-5 h-5" />
                        </button>
                    )}
                </div>
            </form>
        </div>
    );
};

export default SimpleFloatingMessageInput;

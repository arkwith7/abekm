/**
 * AgentChatPage
 * 
 * AI Agent 기반 채팅 페이지
 * - Agent API 사용 (/api/v1/agent/chat)
 * - 도구 실행 단계 시각화
 * - 성능 지표 표시
 * - 기존 컴포넌트 재사용 (MessageList, MessageComposer)
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSelectedDocuments, useWorkContext } from '../../contexts/GlobalAppContext';
import { Document as GlobalDocument } from '../../contexts/types';

// 재사용 컴포넌트
import FileViewer from '../../components/common/FileViewer';
import ChatHeader from './chat/components/ChatHeader';
import ChatAssetViewerModal from './chat/components/ChatAssetViewerModal';
import MessageComposer from './chat/components/MessageComposer';
import MessageList from './chat/components/MessageList';
import PresentationOutlineModal from './chat/components/presentation/PresentationOutlineModal';
import { usePresentation } from './chat/components/presentation/usePresentation';

// Hooks & Types
import { Document as ViewerDocument } from '../../types/user.types';
import { useAgentChat } from './chat/hooks/useAgentChat';

// 🔧 상수로 추출하여 매 렌더링마다 새 객체가 생성되는 것 방지
const DEFAULT_AGENT_SETTINGS = {
    max_chunks: 10,
    max_tokens: 4000,  // 일반 채팅과 동일하게 증가
    similarity_threshold: 0.25,  // 일반 채팅과 동일하게 감소
    container_ids: []
};

const AgentChatPage: React.FC = () => {
    const [inputCentered, setInputCentered] = useState(true);
    const [isRealtimeSttSupported, setRealtimeSttSupported] = useState(true);

    // 글로벌 상태
    const { selectedDocuments, setSelectedDocuments } = useSelectedDocuments();
    const { workContext, updateWorkContext } = useWorkContext();
    const hasInitializedContext = useRef(false);

    // Agent 채팅 hook - 🆕 SSE 스트리밍 사용
    const {
        messages,
        isLoading,
        error,
        sendMessage,
        clearMessages,
        addAssistantMessage, // 🆕 어시스턴트 메시지 추가
        setContainerFilter,
        loadSession,
        isSessionRestored,
        uploadedAssets,      // 🆕 세션 첨부 파일
        removeAttachment,    // 🆕 개별 파일 제거
        clearAttachments,    // 🆕 전체 파일 제거
        sessionId,           // 🆕 세션 ID
        setMessages          // 🆕 메시지 직접 업데이트 (진행 상태 표시용)
    } = useAgentChat({
        defaultSettings: DEFAULT_AGENT_SETTINGS
    });

    // PPT 생성 관련 상태
    const [outlineModalOpen, setOutlineModalOpen] = useState(false);
    const [targetMessageId, setTargetMessageId] = useState<string | null>(null);
    const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
    const { buildFromMessage, buildWithOutline } = usePresentation(sessionId);

    // 파일 뷰어 상태
    const [selectedDocument, setSelectedDocument] = useState<ViewerDocument | null>(null);
    const [viewerOpen, setViewerOpen] = useState(false);
    const [chatAssetViewerOpen, setChatAssetViewerOpen] = useState(false);
    const [chatAssetUrl, setChatAssetUrl] = useState<string | null>(null);
    const [chatAssetFileName, setChatAssetFileName] = useState<string | null>(null);
    const [ragOpen, setRagOpen] = useState(false);
    const previousDocumentCountRef = useRef(0);
    const lastAppliedContainerFilterKeyRef = useRef<string>('__init__');

    // 메시지 끝 스크롤 ref
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // 컨텍스트 초기화
    useEffect(() => {
        if (hasInitializedContext.current) return;
        hasInitializedContext.current = true;

        // 🆕 Agent 채팅은 'agent-chat' 타입으로 설정
        if (workContext.sourcePageType !== 'agent-chat') {
            updateWorkContext({ sourcePageType: 'agent-chat' });
        }
    }, [workContext.sourcePageType, updateWorkContext]);

    // 🆕 PPT 생성 이벤트 리스너 (하이브리드 모드 지원)
    useEffect(() => {
        const handleOpenOutline = (e: CustomEvent) => {
            const { sourceMessageId } = e.detail;
            console.log('📝 [AgentChat] PPT 구조 확인 및 재생성 요청:', sourceMessageId);
            setTargetMessageId(sourceMessageId);
            setOutlineModalOpen(true);
        };

        const handleBuildOneClick = (e: CustomEvent) => {
            const { sourceMessageId, presentationType } = e.detail;
            console.log('📊 [AgentChat] PPT 바로 생성 요청:', sourceMessageId);

            // AI 답변 메시지 내용 찾기
            const msg = messages.find(m => (m.message_id || m.id) === sourceMessageId);
            const messageContent = msg?.content || '';

            // 🆕 PPT Reasoning 데이터 초기화
            const thinkingMessageId = `thinking_quick_${Date.now()}`;
            const initialPptReasoning = {
                steps: [{ message: 'Quick PPT 생성을 시작합니다...', status: 'in_progress' as const }],
                isComplete: false,
                hasError: false,
                mode: 'quick' as const
            };

            // 🔹 AI 사고 과정 메시지 시작 (pptReasoning 데이터 포함)
            addAssistantMessage(
                '',  // 내용은 PPTReasoningPanel에서 표시
                {
                    agent_type: 'presentation',
                    message_subtype: 'agent_thinking',
                    id: thinkingMessageId,
                    pptReasoning: initialPptReasoning
                }
            );

            let pptSteps: Array<{ message: string; status: 'in_progress' | 'completed' | 'error' }> = [
                { message: 'Quick PPT 생성을 시작합니다...', status: 'completed' }
            ];
            let hasError = false;

            // SSE 빌드하고 완료 시 다운로드 링크를 채팅 메시지로 추가
            buildFromMessage(sourceMessageId, {
                onProgress: (p) => {
                    // 🆕 pptReasoning steps에 추가
                    if (p.message) {
                        const newStep = {
                            message: p.message,
                            status: p.stage === 'error' ? 'error' as const : 'in_progress' as const
                        };

                        if (p.stage === 'error') {
                            hasError = true;
                        }

                        // 이전 스텝들을 completed로 변경하고 새 스텝 추가
                        pptSteps = pptSteps.map(s => ({ ...s, status: 'completed' as const }));
                        pptSteps.push(newStep);

                        // 메시지 업데이트 (pptReasoning 데이터)
                        setMessages(prev => prev.map(msg =>
                            msg.id === thinkingMessageId
                                ? {
                                    ...msg,
                                    pptReasoning: {
                                        steps: pptSteps,
                                        isComplete: false,
                                        hasError: hasError,
                                        mode: 'quick' as const
                                    }
                                }
                                : msg
                        ));
                    }
                },
                onComplete: (fileUrl, fileName) => {
                    // 마지막 스텝을 completed로 변경
                    pptSteps = pptSteps.map(s => ({ ...s, status: 'completed' as const }));

                    if (hasError) {
                        console.log('⚠️ PPT 생성 중 오류 발생');
                        setMessages(prev => prev.map(msg =>
                            msg.id === thinkingMessageId
                                ? {
                                    ...msg,
                                    pptReasoning: {
                                        steps: pptSteps,
                                        isComplete: true,
                                        hasError: true,
                                        mode: 'quick' as const
                                    }
                                }
                                : msg
                        ));
                        return;
                    }

                    console.log('✅ PPT 생성 완료:', fileUrl);
                    const modeLabel = presentationType === 'product_introduction' ? '제품소개서' : 'PPT';
                    const token = localStorage.getItem('ABEKM_token');
                    const downloadUrl = token ? `${fileUrl}?token=${encodeURIComponent(token)}` : fileUrl;

                    // 완료 상태로 업데이트
                    pptSteps.push({ message: `PPT 생성 완료 (${fileName || 'presentation.pptx'})`, status: 'completed' });

                    setMessages(prev => prev.map(msg =>
                        msg.id === thinkingMessageId
                            ? {
                                ...msg,
                                pptReasoning: {
                                    steps: pptSteps,
                                    isComplete: true,
                                    hasError: false,
                                    mode: 'quick' as const,
                                    resultFileName: fileName || `생성된 ${modeLabel}.pptx`,
                                    resultFileUrl: downloadUrl
                                }
                            }
                            : msg
                    ));

                    // 다운로드 링크 메시지도 별도로 추가
                    const link = `📎 [${fileName || `생성된 ${modeLabel} 다운로드`}](${downloadUrl})`;
                    addAssistantMessage(link, { agent_type: 'presentation', message_subtype: 'presentation_download' });
                },
                presentationType: presentationType,
                messageContent: messageContent
            });
        };

        window.addEventListener('presentation:openOutline', handleOpenOutline as EventListener);
        window.addEventListener('presentation:buildOneClick', handleBuildOneClick as EventListener);

        return () => {
            window.removeEventListener('presentation:openOutline', handleOpenOutline as EventListener);
            window.removeEventListener('presentation:buildOneClick', handleBuildOneClick as EventListener);
        };
    }, [buildFromMessage, addAssistantMessage, messages, setMessages]);

    // 🆕 URL 파라미터 기반 세션 복원
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const sessionParam = params.get('session');

        if (sessionParam && sessionParam.startsWith('agent_')) {
            console.log('🔄 [AgentChat] URL 파라미터에서 세션 복원 시도:', sessionParam);
            loadSession(sessionParam);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // mount 시 한 번만 실행

    // 사이드바는 UserLayout에서 관리하므로 별도 오프셋 계산 불필요

    // 선택된 문서가 변경되면 컨테이너 필터 업데이트
    // ✅ key(정렬된 unique) 기반으로 "변경된 경우에만" setState → 최대 업데이트 깊이(렌더 루프) 방지
    const selectedContainerIds = useMemo(() => {
        const ids = selectedDocuments
            .map(doc => doc.containerId)
            .filter((id): id is string => Boolean(id));
        return Array.from(new Set(ids)).sort();
    }, [selectedDocuments]);

    const selectedContainerIdsKey = useMemo(() => selectedContainerIds.join('|'), [selectedContainerIds]);

    useEffect(() => {
        if (lastAppliedContainerFilterKeyRef.current === selectedContainerIdsKey) {
            return;
        }
        lastAppliedContainerFilterKeyRef.current = selectedContainerIdsKey;
        setContainerFilter(selectedContainerIds);
        console.log('📁 [AgentChat] 컨테이너 필터 업데이트:', selectedContainerIds);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedContainerIdsKey]); // 의도적으로 key만 추적 (setContainerFilter는 안정적)

    useEffect(() => {
        const previousCount = previousDocumentCountRef.current;
        const currentCount = selectedDocuments.length;

        if (currentCount === 0) {
            setRagOpen(false);
        } else if (previousCount === 0 && currentCount > 0) {
            setRagOpen(true);
        }

        previousDocumentCountRef.current = currentCount;
    }, [selectedDocuments.length]);

    // 메시지 전송 핸들러
    const handleSendMessage = async (content: string, files?: File[], tool?: string) => {
        await sendMessage(content, selectedDocuments, files, tool);
    };

    // 문서 열기 핸들러 (향후 사용 예정)
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const handleOpenDocument = (doc: GlobalDocument) => {
        const resolvedFileName = doc.fileName || doc.originalName || '문서';
        const viewerDoc: ViewerDocument = {
            id: doc.fileId,
            title: resolvedFileName,
            file_name: resolvedFileName,
            file_extension: doc.fileType || '',
            container_path: doc.containerName || '',
            created_at: new Date().toISOString(),
            uploaded_by: '',
            file_size: doc.fileSize || 0
        };
        setSelectedDocument(viewerDoc);
        setViewerOpen(true);
    };

    // 문서 뷰어 닫기
    const handleCloseViewer = () => {
        setViewerOpen(false);
        setSelectedDocument(null);
    };

    const handleOpenChatAsset = (asset: { url: string; fileName?: string }) => {
        setChatAssetUrl(asset.url);
        setChatAssetFileName(asset.fileName || null);
        setChatAssetViewerOpen(true);
    };

    const handleCloseChatAssetViewer = () => {
        setChatAssetViewerOpen(false);
        setChatAssetUrl(null);
        setChatAssetFileName(null);
    };

    const simplifiedSelectedDocuments = useMemo(() => (
        selectedDocuments.map(doc => ({
            id: String(doc.fileId),
            name: doc.fileName || doc.originalName || '문서',
            fileType: doc.fileType
        }))
    ), [selectedDocuments]);

    const ragActive = Boolean(workContext.ragMode || selectedDocuments.length > 0);

    useEffect(() => {
        setInputCentered(messages.length === 0);
    }, [messages.length]);

    return (
        <div className="relative flex flex-col h-full bg-white">
            {/* 헤더 */}
            <div className="flex-shrink-0">
                <ChatHeader
                    sessionId="agent-chat-session"
                    messageCount={messages.length}
                    onClearMessages={clearMessages}
                    sessionType="new"
                />
            </div>

            {!isRealtimeSttSupported && (
                <div className="px-6">
                    <div className="mx-auto mt-3 max-w-4xl rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700">
                        현재 브라우저에서는 실시간 음성인식을 완전히 지원하지 않습니다. 최신 Chrome/Edge 또는 전용 앱에서 더 나은 경험을 얻을 수 있습니다.
                    </div>
                </div>
            )}

            {/* 에러 메시지 표시 */}
            {error && (
                <div className="px-6">
                    <div className="mx-auto mt-3 max-w-4xl rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        <div className="flex items-start">
                            <svg className="w-5 h-5 mr-2 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                            <div className="whitespace-pre-line">{error}</div>
                        </div>
                    </div>
                </div>
            )}

            {/* 🆕 세션 첨부 파일 표시 */}
            {uploadedAssets.length > 0 && (
                <div className="px-6">
                    <div className="mx-auto mt-3 max-w-4xl rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 text-blue-800 font-medium mb-2">
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                                    </svg>
                                    <span>세션 첨부 파일 ({uploadedAssets.length}개)</span>
                                    <span className="text-xs text-blue-600 font-normal">- 대화 종료 시까지 참조됩니다</span>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {uploadedAssets.map((asset) => (
                                        <div key={asset.assetId} className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-blue-200 text-sm">
                                            <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                            </svg>
                                            <span className="text-gray-700">{asset.fileName}</span>
                                            <span className="text-gray-500">({(asset.size / 1024).toFixed(0)}KB)</span>
                                            <button
                                                onClick={() => removeAttachment(asset.assetId)}
                                                className="ml-1 text-red-500 hover:text-red-700 transition-colors"
                                                title="파일 제거"
                                            >
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                </svg>
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <button
                                onClick={clearAttachments}
                                className="ml-4 px-3 py-1.5 text-sm text-red-600 hover:text-red-700 hover:bg-red-100 rounded-lg transition-colors"
                                title="모든 파일 제거"
                            >
                                전체 제거
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 메인 콘텐츠 영역 */}
            <div className="flex-1 flex justify-center transition-all duration-200 min-h-0">
                <div className="max-w-5xl w-full flex flex-col px-6 relative">
                    {/* 메시지가 없을 때: 입력창을 중앙에 배치 */}
                    {inputCentered && messages.length === 0 ? (
                        <div className="flex-1 flex items-center justify-center">
                            <div className="w-full max-w-4xl -mt-16">
                                <div className="text-center mb-8">
                                    <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
                                        <span className="text-3xl">🤖</span>
                                    </div>
                                    <h2 className="text-2xl font-bold text-gray-800 mb-2">
                                        {isSessionRestored ? '세션 복원됨' : 'AI Agent 채팅'}
                                    </h2>
                                    <p className="text-gray-600 max-w-md mx-auto">
                                        {isSessionRestored
                                            ? '이전 대화 내역을 불러왔습니다. 계속해서 대화를 진행하세요.'
                                            : '질문을 입력하시면 AI Agent가 최적의 검색 전략을 선택하여 정확한 답변을 제공합니다.'}
                                    </p>
                                </div>

                                {/* 중앙 입력창 */}
                                <MessageComposer
                                    onSendMessage={handleSendMessage}
                                    onRealtimeSupportChange={setRealtimeSttSupported}
                                    isLoading={isLoading}
                                    ragState={{
                                        isActive: ragActive,
                                        isCollapsed: !ragOpen,
                                        selectedCount: selectedDocuments.length,
                                        onToggleDetails: () => setRagOpen(prev => !prev),
                                        onClearDocuments: () => setSelectedDocuments([]),
                                        documents: simplifiedSelectedDocuments,
                                        onOpenDocument: (id: string) => {
                                            const target = selectedDocuments.find(doc => String(doc.fileId) === id);
                                            if (target) {
                                                handleOpenDocument(target);
                                            }
                                        }
                                    }}
                                />
                                <div className="mt-4 text-center text-xs text-gray-400">
                                    AI는 실수를 할 수 있습니다. 중요한 정보는 확인이 필요합니다.
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* 메시지가 있을 때: 일반 채팅 레이아웃 */
                        <>
                            {/* 메시지 리스트 영역 */}
                            <div className="flex-1 overflow-y-auto space-y-4 py-6 min-h-0" style={{ scrollbarGutter: 'stable both-edges' }}>
                                <MessageList
                                    messages={messages}
                                    isLoading={isLoading}
                                    messagesEndRef={messagesEndRef}
                                    onOpenDocument={(doc) => {
                                        handleOpenDocument({
                                            fileId: doc.id,
                                            fileName: doc.file_name,
                                            originalName: doc.file_name,
                                            fileType: doc.file_extension || (doc.file_name.includes('.') ? doc.file_name.split('.').pop() || '' : ''),
                                            containerName: '',
                                            fileSize: 0,
                                            containerId: ''
                                        } as any);
                                    }}
                                    onOpenChatAsset={handleOpenChatAsset}
                                />
                            </div>

                            {/* 하단 입력창 */}
                            <div className="sticky bottom-0 pb-6 px-4">
                                <div className="mx-auto max-w-4xl">
                                    <MessageComposer
                                        onSendMessage={handleSendMessage}
                                        onRealtimeSupportChange={setRealtimeSttSupported}
                                        isLoading={isLoading}
                                        ragState={{
                                            isActive: ragActive,
                                            isCollapsed: !ragOpen,
                                            selectedCount: selectedDocuments.length,
                                            onToggleDetails: () => setRagOpen(prev => !prev),
                                            onClearDocuments: () => setSelectedDocuments([]),
                                            documents: simplifiedSelectedDocuments,
                                            onOpenDocument: (id: string) => {
                                                const target = selectedDocuments.find(doc => String(doc.fileId) === id);
                                                if (target) {
                                                    handleOpenDocument(target);
                                                }
                                            }
                                        }}
                                    />
                                    <div className="mt-2 text-center text-xs text-gray-400">
                                        AI는 실수를 할 수 있습니다. 중요한 정보는 확인이 필요합니다.
                                    </div>
                                    {error && (
                                        <div className="mt-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
                                            ❌ {error}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* 파일 뷰어 모달 */}
            {viewerOpen && selectedDocument && (
                <FileViewer
                    isOpen={viewerOpen}
                    document={selectedDocument}
                    onClose={handleCloseViewer}
                />
            )}

            {/* 채팅 생성 파일(리포트) 뷰어 모달 */}
            <ChatAssetViewerModal
                isOpen={chatAssetViewerOpen}
                onClose={handleCloseChatAssetViewer}
                assetUrl={chatAssetUrl}
                fileName={chatAssetFileName}
            />

            {/* 🆕 하이브리드 모드: PPT 구조 확인 및 재생성 모달 */}
            {outlineModalOpen && targetMessageId && (() => {
                const targetMsg = messages.find(m => m.id === targetMessageId || m.message_id === targetMessageId);

                // 🔧 FIX: 사용자의 원본 질의문 찾기 (AI 응답이 아닌 사용자 메시지)
                // targetMsg는 AI 응답 메시지이므로, 그 직전의 사용자 메시지를 찾아야 함
                const targetMsgIndex = messages.findIndex(m => m.id === targetMessageId || m.message_id === targetMessageId);
                let userQuery = "";

                // AI 응답 메시지 이전의 사용자 메시지 찾기
                for (let i = targetMsgIndex - 1; i >= 0; i--) {
                    if (messages[i].role === 'user') {
                        userQuery = messages[i].content || "";
                        break;
                    }
                }

                // fallback: metadata에서 original_query 사용
                if (!userQuery && targetMsg?.metadata?.original_query) {
                    userQuery = targetMsg.metadata.original_query;
                }

                return (
                    <PresentationOutlineModal
                        open={outlineModalOpen}
                        onClose={() => setOutlineModalOpen(false)}
                        sourceContent={userQuery}  // 🔧 사용자 원본 질의문만 전달
                        selectedTemplateId={selectedTemplateId}
                        onTemplateChange={setSelectedTemplateId}
                        sessionId={sessionId}  // 채팅 세션 ID 전달
                        containerIds={selectedDocuments?.map(d => String(d.containerId)).filter(Boolean)}  // 선택된 컨테이너 IDs
                        onConfirm={(outline) => {
                            console.log('✅ [AgentChat] PPT 재생성 시작:', outline);

                            // 🔹 모달을 먼저 닫아서 채팅창에서 AI 사고 과정 확인 가능하도록
                            setOutlineModalOpen(false);

                            // 🆕 PPT Reasoning 데이터 초기화
                            const thinkingMessageId = `thinking_template_${Date.now()}`;
                            const initialPptReasoning = {
                                steps: [{ message: 'Template PPT 생성을 시작합니다...', status: 'in_progress' as const }],
                                isComplete: false,
                                hasError: false,
                                mode: 'template' as const
                            };

                            // 🔹 AI 사고 과정 메시지 시작 (pptReasoning 데이터 포함)
                            addAssistantMessage(
                                '',  // 내용은 PPTReasoningPanel에서 표시
                                {
                                    agent_type: 'presentation',
                                    message_subtype: 'agent_thinking',
                                    id: thinkingMessageId,
                                    pptReasoning: initialPptReasoning
                                }
                            );

                            let pptSteps: Array<{ message: string; status: 'in_progress' | 'completed' | 'error' }> = [
                                { message: 'Template PPT 생성을 시작합니다...', status: 'completed' }
                            ];
                            let hasError = false;

                            // 아웃라인 기반 PPT 재생성 API 호출
                            // 🆕 messageContent 추가: AI 답변 원본을 백엔드에 전달 (Redis 조회 실패 시 폴백용)
                            buildWithOutline(targetMessageId, outline, selectedTemplateId, {
                                messageContent: targetMsg?.content || '',  // 🆕 AI 답변 원본 전달
                                onProgress: (p) => {
                                    // 🆕 pptReasoning steps에 추가
                                    if (p.message) {
                                        const newStep = {
                                            message: p.message,
                                            status: p.stage === 'error' ? 'error' as const : 'in_progress' as const
                                        };

                                        if (p.stage === 'error') {
                                            hasError = true;
                                        }

                                        // 이전 스텝들을 completed로 변경하고 새 스텝 추가
                                        pptSteps = pptSteps.map(s => ({ ...s, status: 'completed' as const }));
                                        pptSteps.push(newStep);

                                        // 메시지 업데이트 (pptReasoning 데이터)
                                        setMessages(prev => prev.map(msg =>
                                            msg.id === thinkingMessageId
                                                ? {
                                                    ...msg,
                                                    pptReasoning: {
                                                        steps: pptSteps,
                                                        isComplete: false,
                                                        hasError: hasError,
                                                        mode: 'template' as const
                                                    }
                                                }
                                                : msg
                                        ));
                                    }
                                },
                                onComplete: (fileUrl, fileName) => {
                                    // 마지막 스텝을 completed로 변경
                                    pptSteps = pptSteps.map(s => ({ ...s, status: 'completed' as const }));

                                    if (hasError) {
                                        console.log('⚠️ Template PPT 생성 중 오류 발생');
                                        setMessages(prev => prev.map(msg =>
                                            msg.id === thinkingMessageId
                                                ? {
                                                    ...msg,
                                                    pptReasoning: {
                                                        steps: pptSteps,
                                                        isComplete: true,
                                                        hasError: true,
                                                        mode: 'template' as const
                                                    }
                                                }
                                                : msg
                                        ));
                                        return;
                                    }

                                    console.log('✅ PPT 재생성 완료:', fileUrl);

                                    if (fileUrl) {
                                        const token = localStorage.getItem('ABEKM_token');
                                        const downloadUrl = token ? `${fileUrl}?token=${encodeURIComponent(token)}` : fileUrl;
                                        const linkText = fileName || '재생성된 PPT 다운로드';

                                        // 완료 상태로 업데이트
                                        pptSteps.push({ message: `PPT 생성 완료 (${linkText})`, status: 'completed' });

                                        setMessages(prev => prev.map(msg =>
                                            msg.id === thinkingMessageId
                                                ? {
                                                    ...msg,
                                                    pptReasoning: {
                                                        steps: pptSteps,
                                                        isComplete: true,
                                                        hasError: false,
                                                        mode: 'template' as const,
                                                        resultFileName: linkText,
                                                        resultFileUrl: downloadUrl
                                                    }
                                                }
                                                : msg
                                        ));

                                        // 다운로드 링크 메시지도 별도로 추가
                                        const markdownLink = `📎 [${linkText}](${downloadUrl})`;
                                        addAssistantMessage(markdownLink, { agent_type: 'presentation', message_subtype: 'presentation_download' });
                                    } else {
                                        console.warn('⚠️ PPT 재생성 완료 알림에 파일 URL이 없습니다.');
                                    }
                                }
                            });
                        }}
                    />
                );
            })()}
        </div>
    );
};

export default AgentChatPage;

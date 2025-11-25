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
import MessageComposer from './chat/components/MessageComposer';
import MessageList from './chat/components/MessageList';

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
        setContainerFilter,
        loadSession,
        isSessionRestored
    } = useAgentChat({
        defaultSettings: DEFAULT_AGENT_SETTINGS
    });

    // 파일 뷰어 상태
    const [selectedDocument, setSelectedDocument] = useState<ViewerDocument | null>(null);
    const [viewerOpen, setViewerOpen] = useState(false);
    const [ragOpen, setRagOpen] = useState(false);
    const previousDocumentCountRef = useRef(0);

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
    useEffect(() => {
        if (selectedDocuments.length > 0) {
            const containerIds = Array.from(
                new Set(
                    selectedDocuments
                        .map(doc => doc.containerId)
                        .filter(id => id)
                )
            );
            setContainerFilter(containerIds);
            console.log('📁 [AgentChat] 컨테이너 필터 업데이트:', containerIds);
        } else {
            setContainerFilter([]);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDocuments]); // setContainerFilter는 안정적인 함수이므로 의존성에서 제거

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
    const handleSendMessage = async (content: string, files?: File[]) => {
        await sendMessage(content, selectedDocuments);
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
        <div className="relative flex flex-col h-full bg-gradient-to-br from-blue-50 via-white to-purple-50">
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

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
                                    <FeatureCard
                                        icon="🔍"
                                        title="지능형 검색"
                                        description="벡터, 키워드, 전문 검색을 자동으로 조합"
                                    />
                                    <FeatureCard
                                        icon="⚡"
                                        title="실행 단계 표시"
                                        description="각 도구의 실행 과정을 실시간으로 확인"
                                    />
                                    <FeatureCard
                                        icon="📊"
                                        title="성능 분석"
                                        description="검색 속도, 정확도, 토큰 사용량 추적"
                                    />
                                    <FeatureCard
                                        icon="🎯"
                                        title="의도 분석"
                                        description="질문 의도를 파악하여 최적화된 전략 선택"
                                    />
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
        </div>
    );
};

// Feature Card 컴포넌트
interface FeatureCardProps {
    icon: string;
    title: string;
    description: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon, title, description }) => {
    return (
        <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="text-2xl mb-2">{icon}</div>
            <h3 className="font-semibold text-gray-800 mb-1">{title}</h3>
            <p className="text-sm text-gray-600">{description}</p>
        </div>
    );
};

export default AgentChatPage;

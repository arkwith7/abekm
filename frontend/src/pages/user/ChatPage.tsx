import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import FileViewer from '../../components/common/FileViewer';
import { useSelectedDocuments, useWorkContext } from '../../contexts/GlobalAppContext';
import { Document as GlobalDocument } from '../../contexts/types';
import { transcribeChatAudio } from '../../services/userService';
import { Document as ViewerDocument } from '../../types/user.types';
import ChatHeader from './chat/components/ChatHeader';
import MessageComposer from './chat/components/MessageComposer';
import MessageList from './chat/components/MessageList';
import PresentationOutlineModal from './chat/components/presentation/PresentationOutlineModal';
import { usePresentation } from './chat/components/presentation/usePresentation';
import { useChat } from './chat/hooks/useChat';

const ChatPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const sessionIdFromUrl = searchParams.get('session');

  // 🆕 채팅 입력창 중앙/하단 위치 상태
  const [inputCentered, setInputCentered] = useState(true);

  // 글로벌 상태 hooks
  const { selectedDocuments, hasSelectedDocuments, setSelectedDocuments } = useSelectedDocuments();
  const { workContext, updateWorkContext } = useWorkContext();
  const hasInitializedContext = useRef(false);

  // 🆕 마운트 시 localStorage에서 선택된 문서 복원
  useEffect(() => {
    if (hasInitializedContext.current) {
      return;
    }
    hasInitializedContext.current = true;

    if (workContext.sourcePageType !== 'chat') {
      updateWorkContext({ sourcePageType: 'chat' });
    }

    // localStorage에서 선택된 문서 복원 (세션 복원 시)
    if (sessionIdFromUrl && selectedDocuments.length === 0) {
      try {
        const pageStates = JSON.parse(localStorage.getItem('pageStates') || '{}');
        const chatState = pageStates['chat'];

        if (chatState?.selectedDocuments && chatState.selectedDocuments.length > 0) {
          console.log('💾 localStorage에서 선택된 문서 복원:', chatState.selectedDocuments.length, '개');

          const restoredDocs: GlobalDocument[] = chatState.selectedDocuments.map((doc: any) => ({
            fileId: doc.id || doc.fileId,
            fileName: doc.fileName || doc.file_name || '알 수 없음',
            fileType: doc.fileType || doc.file_type || '',
            fileSize: 0,
            uploadDate: doc.uploadDate || new Date().toISOString(),
            containerName: doc.containerName || '',
            containerId: doc.containerId || '',
            content: '',
            keywords: [],
            isSelected: true
          }));

          setSelectedDocuments(restoredDocs);
          setRagOpen(true);

          console.log('📂 RAG 패널 자동 오픈: 선택된 문서', restoredDocs.length, '개 표시');
        }
      } catch (err) {
        console.warn('⚠️ localStorage 복원 실패:', err);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 마운트 시 한 번만 실행

  const {
    messages,
    isLoading,
    conversationState,
    sendMessage,
    clearMessages,
    stopStreaming,
    sessionId,
    messagesEndRef,
    loadSession,
    sessionType,
    originalSessionId,
    addAssistantMessage
  } = useChat({
    useStreaming: true, // 스트리밍 활성화
    onSuccess: (message: string) => {
      // 성공 메시지 표시 (간단한 알림)
      console.log('✅', message);
      // 여기에 토스트 알림이나 다른 UI 피드백을 추가할 수 있습니다
    }
  });

  const [documentsAddedToChat, setDocumentsAddedToChat] = useState(false);
  const [ragOpen, setRagOpen] = useState(false);

  // 파일 뷰어 상태
  const [selectedDocument, setSelectedDocument] = useState<ViewerDocument | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  // 문서 열기 핸들러
  const handleOpenDocument = (doc: GlobalDocument) => {
    const viewerDoc: ViewerDocument = {
      id: doc.fileId,
      title: doc.fileName,
      file_name: doc.fileName,
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

  // Presentation state
  const { buildFromMessage, getOutline, buildWithOutline } = usePresentation(sessionId);
  const [outlineModalOpen, setOutlineModalOpen] = useState(false);
  const [pendingSourceMessageId, setPendingSourceMessageId] = useState<string | null>(null);
  const [currentOutline, setCurrentOutline] = useState<any | null>(null);
  const [pptProgress, setPptProgress] = useState<{
    stage: 'outline_generating' | 'outline_ready' | 'building' | 'complete' | 'error';
    message?: string;
  } | null>(null);
  const [outlineLoading, setOutlineLoading] = useState(false);
  const [templates, setTemplates] = useState<any[]>([]);
  const [templatesLoaded, setTemplatesLoaded] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  // 🚀 기본 아웃라인 생성 함수
  const createBasicOutline = (content: string, sourceMessageId: string) => {
    // AI 답변에서 기본 섹션 추출
    const lines = content.split('\n').filter(line => line.trim());
    const sections = [];
    let currentSection = null;
    let sectionCounter = 1;

    for (const line of lines) {
      const trimmed = line.trim();

      // 제목 패턴 감지 (##, **, 숫자. 등)
      if (trimmed.match(/^(##\s|#{1,3}\s|\*\*.*\*\*|\d+\.\s|[가-힣]+\s*:)/)) {
        // 이전 섹션 저장
        if (currentSection) {
          sections.push(currentSection);
        }

        // 새 섹션 시작
        const title = trimmed
          .replace(/^#{1,3}\s/, '')
          .replace(/^\*\*(.*)\*\*$/, '$1')
          .replace(/^\d+\.\s/, '')
          .replace(/:$/, '')
          .slice(0, 50); // 제목 길이 제한

        currentSection = {
          id: `section_${sectionCounter++}`,
          title: title || `섹션 ${sectionCounter - 1}`,
          content: ''
        };
      } else if (currentSection && trimmed) {
        // 현재 섹션에 내용 추가
        currentSection.content += (currentSection.content ? '\n' : '') + trimmed;
      }
    }

    // 마지막 섹션 저장
    if (currentSection) {
      sections.push(currentSection);
    }

    // 섹션이 없으면 기본 구조 생성
    if (sections.length === 0) {
      sections.push(
        { id: 'section_1', title: '개요', content: '주요 내용을 입력하세요.' },
        { id: 'section_2', title: '세부사항', content: '세부 내용을 입력하세요.' },
        { id: 'section_3', title: '결론', content: '결론을 입력하세요.' }
      );
    }

    return {
      title: content.slice(0, 100).replace(/[#*\n]/g, '').trim() || '새 프레젠테이션',
      sections: sections.slice(0, 8) // 최대 8개 섹션
    };
  };

  // Adapters: server outline <-> modal outline
  const toModalOutline = (serverOutline: any) => {
    if (!serverOutline) return { title: '', sections: [] };
    const title = serverOutline.topic || '';
    const sections = (serverOutline.slides || []).map((s: any) => ({
      title: s.title || '',
      bullets: s.bullets || [],
      // 유지할 수 있는 메타 정보는 프런트 편집 후 다시 서버에 전달할 수 있도록 보관 (사용X시 무시)
      _key_message: s.key_message,
      _diagram: s.diagram,
      _layout: s.layout,
      _flags: s.flags
    }));
    return { title, sections };
  };
  const toServerOutline = (modalOutline: any) => {
    const slides = (modalOutline?.sections || []).map((s: any) => ({
      title: s.title || '',
      key_message: s._key_message || '',
      bullets: s.bullets || [],
      diagram: s._diagram || { type: 'none', data: {} },
      layout: s._layout || 'title_and_content',
      flags: s._flags
    }));

    // 매핑 정보가 있다면 포함
    const result: any = {
      topic: modalOutline?.title || '발표자료',
      max_slides: slides.length || 8,
      slides
    };

    if (modalOutline?.textBoxMappings) {
      result.textBoxMappings = modalOutline.textBoxMappings;
      console.log('매핑 정보 포함된 서버 아웃라인:', result);
    }

    if (modalOutline?.contentSegments) {
      result.contentSegments = modalOutline.contentSegments;
    }

    // 🆕 확장된 오브젝트 매핑 전달
    if (modalOutline?.object_mappings) {
      result.object_mappings = modalOutline.object_mappings;
    }

    // 🆕 슬라이드 관리 정보 전달
    if (modalOutline?.slide_management) {
      result.slide_management = modalOutline.slide_management;
    }

    return result;
  };

  // 원본 AI 답변 (아웃라인 생성에 사용된 메시지 콘텐츠) 캐시
  const [sourceAnswerContent, setSourceAnswerContent] = useState<string>('');

  // 🆕 세션 복원 시 선택된 문서와 참고자료 복원 이벤트 수신 (먼저 등록)
  useEffect(() => {
    const handleRestoreSelectedDocuments = (event: CustomEvent) => {
      const { documents } = event.detail;
      console.log('📄 세션 복원: 선택된 문서 복원', documents.length, '개');

      // 백엔드에서 받은 문서 정보를 GlobalDocument 형식으로 변환
      const restoredDocs: GlobalDocument[] = documents.map((doc: any) => ({
        fileId: doc.id || doc.fileId,
        fileName: doc.fileName || doc.file_name || '알 수 없음',
        fileType: doc.fileType || doc.file_type || '',
        fileSize: 0,
        uploadDate: doc.uploadDate || new Date().toISOString(),
        containerName: doc.containerName || '',
        containerId: doc.containerId || '',
        content: '',
        keywords: [],
        isSelected: true
      }));

      setSelectedDocuments(restoredDocs);
      setDocumentsAddedToChat(true); // 복원 시에는 안내 메시지 생략

      // 🆕 선택된 문서가 있으면 RAG 패널 자동 오픈
      if (restoredDocs.length > 0) {
        setRagOpen(true);
        console.log('📂 RAG 패널 자동 오픈: 선택된 문서', restoredDocs.length, '개 표시');
      }
    };

    const handleRestoreReferencedDocuments = (event: CustomEvent) => {
      const { documents } = event.detail;
      console.log('📚 세션 복원: 참고자료', documents.length, '개');
      // 참고자료는 각 메시지의 context_info에 포함되므로 별도 처리 불필요
      // 필요시 여기서 UI에 표시할 수 있음
    };

    window.addEventListener('restoreSelectedDocuments', handleRestoreSelectedDocuments as EventListener);
    window.addEventListener('restoreReferencedDocuments', handleRestoreReferencedDocuments as EventListener);

    return () => {
      window.removeEventListener('restoreSelectedDocuments', handleRestoreSelectedDocuments as EventListener);
      window.removeEventListener('restoreReferencedDocuments', handleRestoreReferencedDocuments as EventListener);
    };
  }, [setSelectedDocuments]);

  // URL 파라미터에서 세션 ID가 있으면 해당 세션 로드 (이벤트 리스너 등록 후)
  useEffect(() => {
    if (sessionIdFromUrl) {
      // 세션 ID가 변경되었거나, 메시지가 없을 때 로드
      if (sessionIdFromUrl !== sessionId || messages.length === 0) {
        console.log('🔄 URL에서 세션 로드:', sessionIdFromUrl, '(현재 세션:', sessionId, ', 메시지:', messages.length, '개)');
        loadSession(sessionIdFromUrl);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionIdFromUrl]); // sessionId 의존성 제거 - URL 변경 시에만 로드

  // 검색 → 채팅 이동 시 스냅샷 우선 적용 및 한 번만 전체 리스트를 안내
  useEffect(() => {
    const snapshot = (workContext?.sourcePageState?.selectedDocsSnapshot as GlobalDocument[] | undefined) || undefined;
    // 1) 스냅샷이 있고, 채팅 페이지 선택 문서가 비거나 수량이 다른 경우 동기화
    if (snapshot && snapshot.length > 0) {
      const needSync = selectedDocuments.length !== snapshot.length
        || snapshot.some(s => !selectedDocuments.find((d: any) => d.fileId === s.fileId));
      if (needSync) {
        setSelectedDocuments(snapshot);
      }
    }

    // 2) 안내 메시지는 스냅샷이 있으면 스냅샷으로, 아니면 현재 선택으로 한 번만 전송
    const docsToAnnounce = snapshot && snapshot.length > 0 ? snapshot : selectedDocuments;
    if (!documentsAddedToChat && docsToAnnounce.length > 0) {
      const documentList = docsToAnnounce.map((doc: any) => `📄 ${doc.fileName} (${(doc.fileType || '').toUpperCase()})`).join('\n');
      // 약간의 지연 후 전송 (렌더 안정화)
      const t = setTimeout(() => {
        sendMessage(`선택된 문서 정보:\n${documentList}`, workContext.selectedAgent || 'general');
      }, 150);
      setDocumentsAddedToChat(true);
      return () => clearTimeout(t);
    }
  }, [workContext?.sourcePageState, selectedDocuments, documentsAddedToChat, sendMessage, setSelectedDocuments, workContext.selectedAgent]);

  // 선택된 문서 변경 시 RAG 모드 업데이트
  useEffect(() => {
    const ragMode = hasSelectedDocuments;
    updateWorkContext({ ragMode });
    console.log('📄 문서 선택 상태 변경:', {
      documentsCount: selectedDocuments.length,
      ragMode
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasSelectedDocuments, selectedDocuments.length]); // updateWorkContext 제거

  // Wire global events from MessageBubble action bar
  useEffect(() => {
    const handleBuildOneClick = (e: any) => {
      const sourceMessageId = e?.detail?.sourceMessageId as string;
      const presentationType = e?.detail?.presentationType as string;
      if (!sourceMessageId) return;

      // AI 답변 메시지 내용 찾기
      const msg = messages.find(m => (m.message_id || m.id) === sourceMessageId);
      const messageContent = msg?.content || '';

      // Trigger SSE build and append link on complete
      buildFromMessage(sourceMessageId, {
        onProgress: (p) => {
          setPptProgress(p);
        },
        onComplete: (fileUrl, fileName) => {
          const modeLabel = presentationType === 'product_introduction' ? '제품소개서' : 'PPT';
          const link = `📎 [${fileName || `생성된 ${modeLabel} 다운로드`}](${fileUrl})`;
          addAssistantMessage(link, { agent_type: 'presentation', message_subtype: 'presentation_download' });
          setPptProgress(null);
        },
        presentationType: presentationType,
        messageContent: messageContent  // AI 답변 내용 전달
      });
    };
    const handleOpenOutline = async (e: any) => {
      const sourceMessageId = e?.detail?.sourceMessageId as string;
      const presentationType = e?.detail?.presentationType as string;
      if (!sourceMessageId) return;

      setPendingSourceMessageId(sourceMessageId);

      // 🚀 즉시 모달 열기 - 기본 아웃라인으로 시작
      const msg = messages.find(m => (m.message_id || m.id) === sourceMessageId);
      const basicOutline = createBasicOutline(msg?.content || '', sourceMessageId);
      setCurrentOutline(basicOutline);
      setSourceAnswerContent(msg?.content || '');
      setOutlineModalOpen(true);

      // 📋 템플릿 목록 즉시 로드 (이전에 빈 목록으로 로드되었을 수 있으므로 빈 경우에도 재요청)
      if (!templatesLoaded || templates.length === 0) {
        try {
          const resp = await fetch(`/api/v1/chat/presentation/templates`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}` }
          });

          if (resp.status === 401) {
            // 인증 만료 시 로그인 페이지로 리다이렉트
            localStorage.removeItem('ABEKM_token');
            localStorage.removeItem('ABEKM_refresh_token');
            window.dispatchEvent(new Event('session:invalid'));
            window.location.href = '/login';
            return;
          }

          if (resp.ok) {
            const data = await resp.json();
            setTemplates(data.templates || []);
            setTemplatesLoaded(true);
            // 서버는 default_template_id 필드를 반환함
            if (!selectedTemplateId && data.default_template_id) setSelectedTemplateId(data.default_template_id);
          }
        } catch (err) { console.warn('템플릿 목록 불러오기 실패', err); }
      }

      // 🤖 백그라운드에서 AI 아웃라인 생성
      setOutlineLoading(true);
      try {
        const aiOutline = await getOutline(sourceMessageId, presentationType);
        // 🔄 AI 생성 완료 시 업데이트 (사용자가 편집 중이 아닐 때만)
        setCurrentOutline((prevOutline: any) => {
          // 사용자가 이미 편집했는지 확인
          const hasUserEdits = prevOutline.sections.some((section: any) =>
            section.title !== basicOutline.sections.find((s: any) => s.id === section.id)?.title ||
            section.content !== basicOutline.sections.find((s: any) => s.id === section.id)?.content
          );

          if (hasUserEdits) {
            // 사용자가 편집한 경우, 조심스럽게 병합하거나 알림만 표시
            console.log('🎯 AI 아웃라인 생성 완료, 하지만 사용자가 이미 편집 중');
            return prevOutline; // 기존 편집 내용 유지
          } else {
            // 사용자가 편집하지 않았으면 AI 결과로 교체
            return toModalOutline(aiOutline);
          }
        });
      } catch (err) {
        console.error('AI 아웃라인 생성 실패:', err);
        // 기본 아웃라인이 이미 표시되어 있으므로 사용자는 계속 편집 가능
      } finally {
        setOutlineLoading(false);
      }
    };
    window.addEventListener('presentation:buildOneClick', handleBuildOneClick as EventListener);
    window.addEventListener('presentation:openOutline', handleOpenOutline as EventListener);
    return () => {
      window.removeEventListener('presentation:buildOneClick', handleBuildOneClick as EventListener);
      window.removeEventListener('presentation:openOutline', handleOpenOutline as EventListener);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildFromMessage, getOutline, addAssistantMessage, messages, selectedTemplateId, templatesLoaded]);

  // 자동 스크롤 효과
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, messagesEndRef]);

  // 🆕 메시지 추가 시 입력창을 하단으로 이동
  useEffect(() => {
    if (messages.length > 0) {
      setInputCentered(false);
    }
  }, [messages.length]);

  const handleSendMessage = async (message: string, files?: File[], voiceBlob?: Blob) => {
    // 현재 선택된 문서를 백엔드 스키마에 맞게 변환
    const currentSelectedDocuments = selectedDocuments.map((doc: any) => ({
      fileId: doc.fileId,
      fileName: doc.fileName,
      fileType: doc.fileType,
      filePath: (doc as any).filePath || '',
      metadata: (doc as any).metadata || {}
    }));

    console.log('📤 메시지 전송 - 현재 선택된 문서:', currentSelectedDocuments.length);
    if (currentSelectedDocuments.length === 0) {
      console.log('ℹ️ 선택 문서 없음 → 전체 문서에서 자동 검색됩니다.');
    } else {
      console.log('📄 선택 문서:', currentSelectedDocuments.map((d: any) => d.fileName).join(', '));
    }

    // 모드별 분기: 백엔드 다중-응답 미지원 시, 우선 순차 전송 또는 주석 프리픽스
    const mode = workContext.mode || (workContext.isChainMode ? 'chain' : 'single');
    if (mode === 'chain') {
      await sendMessage(message, workContext.selectedAgentChain || 'general', files, voiceBlob, currentSelectedDocuments);
      return;
    }
    if (mode === 'multi') {
      const agents = workContext.selectedAgents && workContext.selectedAgents.length > 0
        ? workContext.selectedAgents
        : [workContext.selectedAgent || 'general'];
      // 임시: 첫 번째 에이전트로 전송하고, 메시지에 멀티 정보 주석
      const annotated = agents.length > 1
        ? `[multi:${agents.join(',')}] ${message}`
        : message;
      await sendMessage(annotated, agents[0], files, voiceBlob, currentSelectedDocuments);
      return;
    }
    await sendMessage(message, workContext.selectedAgent || 'general', files, voiceBlob, currentSelectedDocuments);
  };

  const handleVoiceDraftTranscription = async (blob: Blob) => {
    try {
      const result = await transcribeChatAudio(blob);
      return result?.transcript ?? '';
    } catch (error) {
      console.warn('음성 초안 변환 실패', error);
      return '';
    }
  };

  // File viewer state for in-chat document open
  const [chatViewerOpen, setChatViewerOpen] = useState(false);
  const [chatViewerDocument, setChatViewerDocument] = useState<ViewerDocument | null>(null);

  // (presentation options removed from main chat page per user request)

  const simplifiedSelectedDocuments = useMemo(() => (
    selectedDocuments.map(doc => ({
      id: String(doc.fileId),
      name: doc.fileName,
      fileType: doc.fileType
    }))
  ), [selectedDocuments]);

  return (
    <div className="relative flex flex-col h-full bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* 헤더 */}
      <div className="flex-shrink-0">
        <ChatHeader
          sessionId={sessionId}
          messageCount={messages.length}
          onClearMessages={clearMessages}
          sessionType={sessionType}
          originalSessionId={originalSessionId}
        />
      </div>

      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 flex justify-center transition-all duration-200 min-h-0">
        <div className="max-w-5xl w-full flex flex-col px-6 relative">
          {/* One-click build progress toast */}
          {pptProgress && pptProgress.stage !== 'complete' && (
            <div className="fixed top-20 right-4 z-50">
              <div className="px-3 py-2 text-xs rounded-md shadow bg-white border border-gray-200 text-gray-700 flex items-center gap-2">
                <span>📊 PPT 생성 진행 중</span>
                <span className="text-gray-400">·</span>
                <span>
                  {pptProgress.stage === 'outline_generating' && '아웃라인 생성'}
                  {pptProgress.stage === 'outline_ready' && '아웃라인 완료'}
                  {pptProgress.stage === 'building' && 'PPT 생성'}
                  {pptProgress.stage === 'error' && (pptProgress.message || '오류')}
                </span>
              </div>
            </div>
          )}

          {/* Presentation Outline Modal */}
          <PresentationOutlineModal
            open={outlineModalOpen}
            onClose={() => setOutlineModalOpen(false)}
            initialOutline={currentOutline}
            sourceContent={sourceAnswerContent}
            loading={outlineLoading}
            templates={templates}
            selectedTemplateId={selectedTemplateId}
            onTemplateChange={setSelectedTemplateId}
            onConfirm={async (outline) => {
              if (!pendingSourceMessageId) return;
              if (!selectedTemplateId) {
                window.alert('템플릿을 선택해 주세요.');
                return;
              }
              const serverOutline = toServerOutline(outline);
              setPptProgress({ stage: 'outline_generating', message: '커스텀 아웃라인 사용' });
              const outlineWithTemplate = { ...serverOutline };
              await buildWithOutline(pendingSourceMessageId, outlineWithTemplate, selectedTemplateId, {
                onProgress: (p) => setPptProgress(p),
                onComplete: (fileUrl, fileName) => {
                  const link = `📎 [${fileName || '생성된 파일 다운로드'}](${fileUrl})`;
                  addAssistantMessage(link, { agent_type: 'presentation', message_subtype: 'presentation_download' });
                  setPptProgress(null);
                }
              });
              setOutlineModalOpen(false);
            }}
          />

          {/* 🆕 메시지가 없을 때: 입력창을 중앙에 배치 */}
          {inputCentered && messages.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="w-full max-w-4xl -mt-16">
                <div className="text-center mb-8">
                  <h1 className="text-4xl font-bold text-gray-800 mb-3">무엇을 도와드릴까요?</h1>
                  <p className="text-gray-500">질문을 입력하면 AI가 답변해 드립니다.</p>
                </div>

                {/* 중앙 입력창 */}
                <MessageComposer
                  onSendMessage={handleSendMessage}
                  onStopStreaming={stopStreaming}
                  isLoading={isLoading}
                  onDraftTranscription={handleVoiceDraftTranscription}
                  ragState={{
                    isActive: !!workContext.ragMode,
                    isCollapsed: !ragOpen,
                    selectedCount: selectedDocuments.length,
                    onToggleDetails: () => setRagOpen(prev => !prev),
                    onClearDocuments: () => setSelectedDocuments([]),
                    documents: simplifiedSelectedDocuments,
                    onOpenDocument: (id) => {
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
            /* 🆕 메시지가 있을 때: 일반 채팅 레이아웃 */
            <>
              {/* 메시지 리스트 영역 */}
              <div
                className="flex-1 overflow-y-auto space-y-4 py-6 min-h-0"
                style={{ scrollbarGutter: 'stable both-edges' }}
              >
                <MessageList
                  messages={messages}
                  isLoading={isLoading}
                  messagesEndRef={messagesEndRef}
                  conversationState={conversationState}
                  onOpenDocument={(doc) => {
                    if (!doc) {
                      console.warn('⚠️ onOpenDocument: doc is undefined');
                      return;
                    }

                    const fileName = doc.file_name || doc.title || 'Unknown';
                    const fileExtension = doc.file_extension ||
                      (fileName.includes('.') ? fileName.split('.').pop() || '' : '');

                    setChatViewerDocument({
                      id: doc.id,
                      document_id: doc.id,
                      title: doc.title || fileName,
                      file_name: fileName,
                      file_size: 0,
                      file_extension: fileExtension,
                      document_type: '',
                      quality_score: 0,
                      korean_ratio: 0,
                      keywords: [],
                      container_path: '',
                      description: '',
                      tags: [],
                      is_public: false,
                      view_count: 0,
                      download_count: 0,
                      created_at: '',
                      updated_at: '',
                      uploaded_by: 'system'
                    });
                    setChatViewerOpen(true);
                  }}
                />
              </div>

              {/* 하단 입력창 */}
              <div className="sticky bottom-0 pb-6 px-4">
                <div className="mx-auto max-w-4xl">
                  <MessageComposer
                    onSendMessage={handleSendMessage}
                    onStopStreaming={stopStreaming}
                    isLoading={isLoading}
                    onDraftTranscription={handleVoiceDraftTranscription}
                    ragState={{
                      isActive: !!workContext.ragMode,
                      isCollapsed: !ragOpen,
                      selectedCount: selectedDocuments.length,
                      onToggleDetails: () => setRagOpen(prev => !prev),
                      onClearDocuments: () => setSelectedDocuments([]),
                      documents: simplifiedSelectedDocuments,
                      onOpenDocument: (id) => {
                        const target = selectedDocuments.find(doc => String(doc.fileId) === id);
                        if (target) {
                          handleOpenDocument(target);
                        }
                      }
                    }}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 파일 뷰어 (연관 문서 링크 open) */}
      <FileViewer
        isOpen={chatViewerOpen}
        onClose={() => setChatViewerOpen(false)}
        document={chatViewerDocument}
        onDownload={(doc: ViewerDocument) => {
          if (!doc) return;
          // TODO: 통일된 다운로드 로직 필요 시 구현
        }}
      />

      {/* 선택된 문서 뷰어 */}
      <FileViewer
        isOpen={viewerOpen}
        onClose={handleCloseViewer}
        document={selectedDocument}
        onDownload={(doc: ViewerDocument) => {
          if (!doc) return;
          // TODO: 다운로드 로직 구현
        }}
      />
    </div>
  );
};

export default ChatPage;

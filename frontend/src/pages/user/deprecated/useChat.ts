import { useCallback, useEffect, useRef, useState } from 'react';
import { getAuthHeader } from '../../../../services/authService';
import { sendRagChatMessage, uploadChatAttachments, UploadedChatAsset } from '../../../../services/userService';
import { getApiUrl } from '../../../../utils/apiConfig';
import { handleUnauthorized } from '../../../../utils/authUtils';
import { CHAT_SESSION_TTL_MS, clearPersistedChatState, isChatStateExpired, readPersistedChatState, writePersistedChatState } from '../../../../utils/chatState';
import { ChatAttachment, ChatMessage, ChatSettings, ConversationState } from '../types/chat.types';
const mapAssetToAttachment = (asset: UploadedChatAsset): ChatAttachment => ({
  id: asset.assetId,
  fileName: asset.fileName,
  mimeType: asset.mimeType,
  size: asset.size,
  previewUrl: asset.previewUrl,
  downloadUrl: asset.downloadUrl,
  category: asset.category
});

const mapPayloadToAttachment = (payload: any): ChatAttachment => ({
  id: payload?.asset_id || payload?.id || `${Date.now()}_${Math.random().toString(36).slice(2)}`,
  fileName: payload?.file_name || payload?.name || '첨부 파일',
  mimeType: payload?.mime_type || 'application/octet-stream',
  size: payload?.size || 0,
  previewUrl: payload?.preview_url,
  downloadUrl: payload?.download_url,
  category: (payload?.category || 'document') as ChatAttachment['category']
});

const API_BASE_URL = getApiUrl();
const CHAT_TTL_CHECK_INTERVAL_MS = 60 * 1000;
const ALLOWED_SESSION_TYPES: SessionType[] = ['new', 'loaded', 'continued'];

interface UseChatOptions {
  defaultSettings?: Partial<ChatSettings>;
  onError?: (error: Error) => void;
  useStreaming?: boolean; // 스트리밍 사용 여부
  onSuccess?: (message: string) => void; // 성공 메시지 콜백
}

// 세션 타입 정의
type SessionType = 'new' | 'loaded' | 'continued';

export const useChat = (options: UseChatOptions = {}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationState, setConversationState] = useState<ConversationState | null>(null);
  const [sessionId, setSessionId] = useState<string>(() =>
    `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );

  // 🎯 세션 상태 관리 추가
  const [sessionType, setSessionType] = useState<SessionType>('new');
  const [originalSessionId, setOriginalSessionId] = useState<string | null>(null);

  const restoreSessionIdRef = useRef<string | null>(null);
  const lastInteractionRef = useRef<number>(Date.now());
  const expirationGuardRef = useRef(false);

  const [settings, setSettings] = useState<ChatSettings>({
    provider: undefined,  // 백엔드 .env 설정 사용 (프론트엔드에서 지정 안 함)
    max_tokens: 4096,
    temperature: 0.7,
    container_ids: [],
    ...options.defaultSettings
  });

  const archiveSessionSilently = useCallback(async (targetSessionId: string | null | undefined) => {
    if (!targetSessionId) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/sessions/${targetSessionId}/archive`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(getAuthHeader())
        },
        body: JSON.stringify({ reason: 'ttl-expired' })
      });

      if (!response.ok) {
        console.warn('⚠️ 채팅 세션 자동 아카이브 실패', response.status);
      }
    } catch (archiveError) {
      console.warn('⚠️ 채팅 세션 자동 아카이브 요청 실패', archiveError);
    }
  }, []);

  useEffect(() => {
    const storedState = readPersistedChatState();
    if (!storedState) {
      return;
    }

    if (isChatStateExpired(storedState)) {
      archiveSessionSilently(storedState.sessionId);
      clearPersistedChatState();
      return;
    }

    if (storedState.messages && storedState.messages.length > 0) {
      setMessages(storedState.messages);
    }

    if (storedState.sessionId) {
      setSessionId(storedState.sessionId);
      restoreSessionIdRef.current = storedState.sessionId;
    }

    if (storedState.sessionType && ALLOWED_SESSION_TYPES.includes(storedState.sessionType as SessionType)) {
      setSessionType(storedState.sessionType as SessionType);
    }

    if (storedState.originalSessionId) {
      setOriginalSessionId(storedState.originalSessionId);
    } else if (storedState.sessionId) {
      setOriginalSessionId(storedState.sessionId);
    }

    if (storedState.conversationState) {
      setConversationState(storedState.conversationState);
    }

    if (storedState.lastInteraction) {
      lastInteractionRef.current = storedState.lastInteraction;
    }
  }, [archiveSessionSilently]);

  const prepareAttachments = useCallback(async (files: File[] | undefined) => {
    if (!files?.length) {
      return {
        uploadedAssets: [] as UploadedChatAsset[],
        attachmentsForMessage: [] as ChatAttachment[]
      };
    }

    try {
      // 파일 크기 제한 (3MB)
      const MAX_FILE_SIZE = 3 * 1024 * 1024;
      const oversizedFiles = files.filter(f => f.size > MAX_FILE_SIZE);

      if (oversizedFiles.length > 0) {
        const oversizedNames = oversizedFiles.map(f =>
          `${f.name} (${(f.size / (1024 * 1024)).toFixed(1)}MB)`
        ).join(', ');
        throw new Error(`파일 크기 제한 초과: ${oversizedNames}. 채팅에서는 3MB 이하의 파일만 처리 가능합니다. 문서 업로드 기능을 사용해주세요.`);
      }

      const uploadedAssets = await uploadChatAttachments(files);
      return {
        uploadedAssets,
        attachmentsForMessage: uploadedAssets.map(mapAssetToAttachment)
      };
    } catch (uploadError) {
      console.error('📁 첨부 파일 업로드 실패', uploadError);
      throw uploadError;
    }
  }, []);

  const persistChatState = useCallback(() => {
    if (!sessionId) {
      return;
    }

    writePersistedChatState({
      sessionId,
      sessionType,
      originalSessionId,
      messages,
      conversationState,
      lastInteraction: lastInteractionRef.current
    });
  }, [sessionId, sessionType, originalSessionId, messages, conversationState]);

  useEffect(() => {
    if (!messages.length) {
      return;
    }

    const lastMessage = messages[messages.length - 1];
    const parsedTimestamp = lastMessage?.timestamp ? Date.parse(lastMessage.timestamp) : NaN;
    const resolvedTimestamp = Number.isFinite(parsedTimestamp) ? parsedTimestamp : Date.now();
    lastInteractionRef.current = Math.max(lastInteractionRef.current, resolvedTimestamp);
  }, [messages]);

  useEffect(() => {
    persistChatState();
  }, [persistChatState]);

  useEffect(() => {
    const checkExpiration = () => {
      const persisted = readPersistedChatState();
      if (!persisted || !persisted.sessionId) {
        return;
      }

      const lastInteraction = persisted.lastInteraction ?? lastInteractionRef.current;
      if (!lastInteraction) {
        return;
      }

      if (Date.now() - lastInteraction <= CHAT_SESSION_TTL_MS) {
        return;
      }

      if (expirationGuardRef.current) {
        return;
      }

      expirationGuardRef.current = true;

      archiveSessionSilently(persisted.sessionId);
      clearPersistedChatState();

      const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      setSessionId(newSessionId);
      setSessionType('new');
      setOriginalSessionId(null);
      setConversationState(null);
      setMessages([{
        id: `expired_${Date.now()}`,
        role: 'assistant',
        content: '채팅 세션이 만료되어 새로운 대화를 시작합니다.',
        timestamp: new Date().toISOString()
      }]);
      setError(null);
      setIsLoading(false);
      restoreSessionIdRef.current = null;
      lastInteractionRef.current = Date.now();

      expirationGuardRef.current = false;
    };

    const intervalId = window.setInterval(checkExpiration, CHAT_TTL_CHECK_INTERVAL_MS);
    checkExpiration();

    return () => window.clearInterval(intervalId);
  }, [archiveSessionSilently]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 🎯 외부 이벤트 수신 (세션 삭제, 새 대화 시작)
  useEffect(() => {
    const handleSessionDeleted = (event: CustomEvent) => {
      const deletedSessionId = event.detail.sessionId;
      console.log('🔔 세션 삭제 이벤트 수신:', deletedSessionId);

      // 현재 채팅창의 세션과 삭제된 세션이 같은지 확인
      const isCurrentSessionDeleted =
        sessionId === deletedSessionId ||
        originalSessionId === deletedSessionId ||
        (sessionType === 'continued' && originalSessionId === deletedSessionId);

      if (isCurrentSessionDeleted) {
        console.log('🔄 삭제된 세션이 현재 채팅창과 연결됨 - 채팅창 초기화');

        // 채팅창 완전 초기화
        const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        setMessages([{
          id: 'deleted_reset',
          role: 'assistant',
          content: '대화가 삭제되었습니다. 새로운 대화를 시작합니다.',
          timestamp: new Date().toISOString()
        }]);
        setSessionId(newSessionId);
        setError(null);
        setIsLoading(false);

        // 세션 상태 초기화
        setSessionType('new');
        setOriginalSessionId(null);

        // URL 정리
        const url = new URL(window.location.href);
        url.searchParams.delete('session');
        window.history.replaceState({}, '', url.toString());

        console.log('✅ 채팅창 초기화 완료:', newSessionId);
      } else {
        console.log('ℹ️ 삭제된 세션이 현재 채팅창과 다름 - 채팅창 유지');
      }
    };

    const handleClearChatFromSidebar = () => {
      console.log('🆕 사이드바에서 새 대화 시작 이벤트 수신 - 대화 초기화와 동일한 동작 수행');

      // 대화 초기화 함수와 동일한 로직 실행
      // 현재 대화가 있으면 저장하고 초기화
      clearMessages();
    };

    // 이벤트 리스너 등록
    window.addEventListener('chatSessionDeleted', handleSessionDeleted as EventListener);
    window.addEventListener('clearChatFromSidebar', handleClearChatFromSidebar as EventListener);

    // 클린업
    return () => {
      window.removeEventListener('chatSessionDeleted', handleSessionDeleted as EventListener);
      window.removeEventListener('clearChatFromSidebar', handleClearChatFromSidebar as EventListener);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, originalSessionId, sessionType]);

  // 새 세션 생성
  const createNewSession = useCallback(() => {
    const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content: '새로운 대화를 시작합니다. 무엇을 도와드릴까요?',
        timestamp: new Date().toISOString()
      }
    ]);
    setError(null);
  }, []);

  // 세션 로드
  const loadSession = useCallback(async (targetSessionId: string) => {
    try {
      // 🚫 Agent 세션은 일반 채팅에서 로드하지 않음
      if (targetSessionId.startsWith('agent_')) {
        console.warn('⚠️ [useChat] Agent 세션은 일반 채팅에서 로드할 수 없음:', targetSessionId);
        setError('이 세션은 AI Agent 채팅에서만 열 수 있습니다.');
        return;
      }

      console.log('🔄 세션 로드 시작:', targetSessionId);

      // 먼저 채팅창 초기화
      setMessages([]);
      setError(null);
      setIsLoading(true);

      // 🎯 세션 상태를 'loaded'로 설정
      setSessionType('loaded');
      setOriginalSessionId(targetSessionId);

      const response = await fetch(`${API_BASE_URL}/api/v1/chat/sessions/${targetSessionId}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(getAuthHeader())
        }
      });

      if (response.status === 401) {
        // 인증 만료 시 로그인 페이지로 리다이렉트
        handleUnauthorized();
        return;
      }

      if (response.ok) {
        const data = await response.json();

        console.log('📦 세션 데이터 수신:', {
          sessionId: targetSessionId,
          success: data.success,
          messageCount: data.messages?.length || 0,
          referencedDocumentsCount: data.referenced_documents?.length || 0,
          selectedDocumentsCount: data.selected_documents?.length || 0
        });

        if (!data.success) {
          console.warn('⚠️ 백엔드에서 세션 로드 실패 응답:', data);
          throw new Error(data.message || '세션을 찾을 수 없습니다');
        }

        setSessionId(targetSessionId);

        // 백엔드에서 받은 메시지로 채팅창 설정
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
          console.log('✅ 기존 세션 로드 완료:', {
            sessionId: targetSessionId,
            messageCount: data.messages.length,
            sessionType: 'loaded',
            firstMessage: data.messages[0]?.content?.substring(0, 50) || 'N/A'
          });

          // 🆕 선택된 문서 복원 (최초 대화 시 선택한 문서들)
          if (data.selected_documents && data.selected_documents.length > 0) {
            console.log('📄 선택된 문서 복원:', data.selected_documents.length, '개');

            // 1. localStorage에 저장 (페이지 새로고침 대비)
            try {
              const pageStates = JSON.parse(localStorage.getItem('pageStates') || '{}');
              pageStates['chat'] = {
                ...(pageStates['chat'] || {}),
                selectedDocuments: data.selected_documents,
                lastUpdated: new Date().toISOString()
              };
              localStorage.setItem('pageStates', JSON.stringify(pageStates));
              console.log('💾 선택된 문서 localStorage 저장 완료');
            } catch (err) {
              console.warn('⚠️ localStorage 저장 실패:', err);
            }

            // 2. conversationState 업데이트 (RAG 패널 표시용)
            const relevantDocs = data.selected_documents.map((doc: any) => ({
              id: doc.id || doc.fileId,
              title: doc.fileName || doc.file_name || '알 수 없음',
              containerName: doc.containerName || '',
              similarity: 1.0 // 선택된 문서이므로 100%
            }));

            setConversationState({
              summary: `${data.selected_documents.length}개 문서 기반 대화`,
              keywords: [],
              relevantDocuments: relevantDocs,
              topicContinuity: 1.0,
              lastIntent: 'search',
              updatedAt: new Date().toISOString(),
              hints: []
            });
            console.log('📊 conversationState 업데이트: relevantDocuments', relevantDocs.length, '개');

            // 3. 이벤트 발송하여 ChatPage에서 처리
            window.dispatchEvent(new CustomEvent('restoreSelectedDocuments', {
              detail: { documents: data.selected_documents }
            }));
          }

          // 🆕 참고자료 목록 복원 (전체 대화에서 참고한 문서들)
          if (data.referenced_documents && data.referenced_documents.length > 0) {
            console.log('📚 참고자료 복원:', data.referenced_documents.length, '개');

            // 참고자료는 각 메시지의 context_info에 이미 포함되어 있으므로
            // 별도 상태 관리는 불필요하지만, 전체 목록을 표시하려면 이벤트 발송
            window.dispatchEvent(new CustomEvent('restoreReferencedDocuments', {
              detail: { documents: data.referenced_documents }
            }));
          }

          // Redis 세션 복원은 첫 메시지 전송 시 자동으로 처리됨
          console.log('ℹ️ Redis 세션은 다음 메시지 전송 시 자동 생성됩니다.');
        } else {
          console.warn('⚠️ 세션은 있으나 메시지가 없음');
          // 메시지가 없는 경우 기본 메시지 표시
          setMessages([
            {
              id: '1',
              role: 'assistant',
              content: '대화를 불러왔습니다. 이전 메시지가 없습니다. 새로운 대화를 시작하세요.',
              timestamp: new Date().toISOString()
            }
          ]);
        }
        setError(null);
      } else {
        const errorText = await response.text();
        console.error('❌ 세션 로드 HTTP 오류:', response.status, errorText);
        setError(`세션을 불러오는데 실패했습니다 (${response.status})`);
        // 실패 시 세션 타입 리셋
        setSessionType('new');
        setOriginalSessionId(null);
      }
    } catch (error: any) {
      console.error('❌ 세션 로드 실패:', error);
      setError(error.message || '세션을 불러오는데 실패했습니다.');
      // 실패 시 세션 타입 리셋
      setSessionType('new');
      setOriginalSessionId(null);
    } finally {
      setIsLoading(false);
    }
  }, []); const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 스트리밍 채팅 함수
  const sendStreamingMessage = useCallback(async (
    content: string,
    agentType?: string,
    files?: File[],
    currentSelectedDocuments?: Array<{ fileId: string; fileName: string; fileType: string; filePath?: string; metadata?: any }>
  ) => {
    if ((!content.trim() && !files?.length) || isLoading) return;

    setIsLoading(true);
    setError(null);

    let uploadedAssets: UploadedChatAsset[] = [];
    let attachmentsForMessage: ChatAttachment[] = [];

    try {
      const attachmentResult = await prepareAttachments(files);
      uploadedAssets = attachmentResult.uploadedAssets;
      attachmentsForMessage = attachmentResult.attachmentsForMessage;
    } catch (uploadErr: any) {
      console.error('📁 첨부 업로드 실패:', uploadErr);
      const errorMessage = uploadErr?.response?.data?.detail
        || uploadErr?.message
        || '첨부 파일 업로드 중 오류가 발생했습니다.';
      setError(errorMessage);
      setIsLoading(false);
      if (options.onError) {
        options.onError(new Error(errorMessage));
      }
      return;
    }

    if (sessionType === 'loaded') {
      console.log('🎯 세션 타입 변경: loaded → continued (기존 세션에 새 메시지 추가)');
      console.log('🔍 현재 상태:', { sessionId, originalSessionId, sessionType });
      setSessionType('continued');
    } else {
      console.log('🔍 현재 세션 타입:', sessionType, '변경 없음');
    }

    let finalContent = content.trim();
    if (files?.length) {
      finalContent += `\n\n📎 첨부 파일: ${files.map(f => f.name).join(', ')}`;
    }

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: finalContent,
      timestamp: new Date().toISOString(),
      agent_type: agentType,
      attachments: attachmentsForMessage
    };

    setMessages(prev => [...prev, userMessage]);

    const streamingMessageId = `assistant_${Date.now()}`;
    const streamingMessage: ChatMessage = {
      id: streamingMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      references: [],
      context_info: {
        total_chunks: 0,
        context_tokens: 0,
        search_mode: 'hybrid',
        reranking_applied: false
      },
      rag_stats: {
        query_length: 0,
        total_candidates: 0,
        final_chunks: 0,
        avg_similarity: null,
        search_time: null,
        search_mode: 'hybrid',
        has_korean_keywords: false,
        embedding_dimension: 1024,
        provider: null,
        embedding_provider: null,
        llm_provider: null,
        llm_model: null,
        embedding_model: null
      }
    };

    setMessages(prev => [...prev, streamingMessage]);

    const updateStreamingMessage = (updater: (msg: ChatMessage) => ChatMessage) => {
      setMessages(prev => {
        let found = false;
        const next = prev.map(msg => {
          if (msg.id === streamingMessageId) {
            found = true;
            return updater(msg);
          }
          return msg;
        });

        if (!found) {
          return [...prev, updater(streamingMessage)];
        }

        return next;
      });
    };

    let streamingContent = '';

    try {
      let messageToSend = content.trim();

      if (agentType && agentType !== 'general') {
        messageToSend = `[${agentType}] ${messageToSend}`;
      }

      abortControllerRef.current = new AbortController();

      let selectedDocumentsPayload: Array<{ id: string; fileName: string; fileType: string; filePath?: string; metadata?: any }> = [];

      if (currentSelectedDocuments) {
        selectedDocumentsPayload = currentSelectedDocuments
          .filter((doc: any) => !!(doc.fileId || doc.id))
          .map((doc: any) => ({
            id: String(doc.fileId || doc.id),
            fileName: doc.fileName || doc.originalName || 'Unknown',
            fileType: doc.fileType || 'unknown',
            filePath: doc.filePath || doc.containerName || '',
            metadata: doc.metadata || {}
          }));
        console.log('🎯 실시간 선택된 문서 사용:', selectedDocumentsPayload);
      } else {
        try {
          const storedData = localStorage.getItem('ABEKM_workContext');
          if (storedData) {
            const parsed = JSON.parse(storedData);
            const chatDocs = parsed?.pageStates?.chat?.selectedDocuments || [];
            selectedDocumentsPayload = chatDocs
              .filter((doc: any) => !!(doc.id || doc.fileId))
              .map((doc: any) => ({
                id: String(doc.id || doc.fileId),
                fileName: doc.fileName || doc.file_name || doc.originalName || 'Unknown',
                fileType: doc.fileType || doc.file_type || 'unknown',
                filePath: doc.filePath || doc.file_path || doc.containerName || '',
                metadata: doc.metadata || {}
              }));
          }
        } catch (err) {
          console.error('📂 로컬 스토리지 문서 파싱 실패:', err);
        }
        console.log('📂 로컬 스토리지에서 문서 가져옴:', selectedDocumentsPayload);
      }

      const timeoutId = setTimeout(() => {
        abortControllerRef.current?.abort();
      }, 60000);

      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(getAuthHeader())
          },
          body: JSON.stringify({
            message: messageToSend,
            provider: null,
            agent_type: agentType || 'general',
            container_ids: settings.container_ids,
            selected_documents: selectedDocumentsPayload,
            session_id: sessionId,
            max_tokens: settings.max_tokens,
            temperature: settings.temperature,
            include_references: true,
            attachments: uploadedAssets.map(asset => ({
              asset_id: asset.assetId,
              category: asset.category,
              file_name: asset.fileName
            })),
            use_rag: true,
            search_mode: 'hybrid',
            max_chunks: 20,
            similarity_threshold: 0.4,
            use_reranking: true
          }),
          signal: abortControllerRef.current.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          if (response.status === 401) {
            console.warn('🔐 인증 실패 - 로그인 페이지로 리다이렉트');
            localStorage.removeItem('ABEKM_token');
            localStorage.removeItem('ABEKM_refresh_token');
            localStorage.removeItem('ABEKM_user');
            localStorage.removeItem('csrf_token');

            const evt = new CustomEvent('session:invalid', { detail: { status: 401 } });
            window.dispatchEvent(evt);
            window.location.href = '/login';
            return;
          }

          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Response body is null');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        const handleSseLine = (line: string) => {
          if (!line.startsWith('data: ')) {
            return;
          }

          const dataContent = line.slice(6).trim();

          if (dataContent === '[DONE]') {
            console.log('✅ SSE 스트림 완료: [DONE] 수신');
            return;
          }

          if (!dataContent) {
            return;
          }

          try {
            const data = JSON.parse(dataContent);

            switch (data.type) {
              case 'start':
                break;
              case 'searching':
                updateStreamingMessage(msg => ({
                  ...msg,
                  content: '🔍 관련 문서를 검색하고 있습니다...'
                }));
                break;
              case 'search_complete':
                updateStreamingMessage(msg => ({
                  ...msg,
                  content: `📚 ${data.chunks_count || 0}개의 관련 문서를 찾았습니다.\n\n🤖 AI가 답변을 생성하고 있습니다...`
                }));
                break;
              case 'generating':
                updateStreamingMessage(msg => {
                  const replaced = msg.content.replace(/🤖 AI가 답변을 생성하고 있습니다\.\.\./, '🤖 AI가 답변을 생성하고 있습니다...');
                  return {
                    ...msg,
                    content: replaced || '🤖 AI가 답변을 생성하고 있습니다...'
                  };
                });
                break;
              case 'content': {
                const chunkText: string = data.content || '';
                if (chunkText) {
                  streamingContent += chunkText;
                  const currentContent = streamingContent;
                  updateStreamingMessage(msg => ({
                    ...msg,
                    content: currentContent
                  }));
                }
                break;
              }
              case 'search_failed': {
                const aggregatedContent = streamingContent;
                updateStreamingMessage(msg => {
                  const cleaned = msg.content
                    .replace(/📚 \d+개의 관련 문서를 찾았습니다\.\n\n🤖 AI가 답변을 생성하고 있습니다\.\.\./, '')
                    .replace(/🤖 AI가 답변을 생성하고 있습니다\.\.\./, '')
                    .replace(/🔍 관련 문서를 검색하고 있습니다\.\.\./, '');
                  return {
                    ...msg,
                    content: aggregatedContent || cleaned
                  };
                });
                break;
              }
              case 'complete': {
                if (data.session_id) {
                  setSessionId(data.session_id);
                }
                const aggregatedContent = streamingContent;
                updateStreamingMessage(msg => {
                  let appendedContent = aggregatedContent || msg.content;
                  if (data.file_url) {
                    const name = data.file_name || '생성된 파일 다운로드';
                    const linkLine = `\n\n📎 [${name}](${data.file_url})`;
                    if (!appendedContent.includes(data.file_url)) {
                      appendedContent = (appendedContent || '') + linkLine;
                    }
                  }
                  return {
                    ...msg,
                    message_id: data.assistant_message_id || data.message_id || msg.message_id,
                    content: appendedContent,
                    references: data.references || [],
                    context_info: data.context_info || {},
                    rag_stats: data.rag_stats || {},
                    attachments: Array.isArray(data.attachments)
                      ? data.attachments.map(mapPayloadToAttachment)
                      : msg.attachments
                  };
                });
                break;
              }
              case 'metadata':
                if (data.session_id) {
                  setSessionId(data.session_id);
                }
                updateStreamingMessage(msg => ({
                  ...msg,
                  references: data.references || msg.references || [],
                  context_info: data.context_info || msg.context_info || {},
                  rag_stats: data.rag_stats || msg.rag_stats || {}
                }));
                break;
              case 'conversation_state':
                if (data.state) {
                  const contextState = data.state as ConversationState;
                  setConversationState(contextState);
                  // 🆕 현재 스트리밍 중인 메시지에 컨텍스트 저장
                  updateStreamingMessage(msg => ({
                    ...msg,
                    conversationContext: contextState
                  }));
                }
                break;
              case 'ping':
                break;
              case 'done': {
                const aggregatedContent = streamingContent;
                updateStreamingMessage(msg => ({
                  ...msg,
                  content: aggregatedContent || msg.content
                }));
                break;
              }
              case 'error':
                throw new Error(data.message);
            }
          } catch (parseError) {
            console.error('❌ SSE 데이터 파싱 오류:', {
              error: parseError,
              dataContent: dataContent.substring(0, 100),
              line: line.substring(0, 100)
            });
          }
        };

        while (true) {
          const { done, value } = await reader.read();

          if (value) {
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
              handleSseLine(line);
            }
          }

          if (done) {
            break;
          }
        }

        // Flush any remaining decoder buffer and process trailing data
        buffer += decoder.decode();
        if (buffer) {
          const remainingLines = buffer.split('\n');
          buffer = remainingLines.pop() || '';
          for (const line of remainingLines) {
            handleSseLine(line);
          }
          if (buffer.trim()) {
            handleSseLine(buffer);
            buffer = '';
          }
        }

        console.log('✅ 스트리밍 완료, 최종 메시지 길이:', streamingContent.length);
      } catch (err: any) {
        clearTimeout(timeoutId);
        console.error('스트리밍 채팅 메시지 전송 실패:', err);
        const errorMessage = err.name === 'AbortError'
          ? '요청이 취소되었습니다.'
          : err.message || '메시지 전송 중 오류가 발생했습니다.';

        setError(errorMessage);

        updateStreamingMessage(msg => ({
          ...msg,
          content: `죄송합니다. 오류가 발생했습니다: ${errorMessage}\n\n다시 시도해 주세요.`
        }));

        if (options.onError) {
          options.onError(new Error(errorMessage));
        }
      }
    } catch (err: any) {
      console.error('외부 오류:', err);
      setError(err.message);
      if (options.onError) {
        options.onError(err);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [isLoading, sessionType, sessionId, originalSessionId, settings, options, prepareAttachments]);

  const sendMessage = useCallback(async (
    content: string,
    agentType?: string,
    files?: File[],
    currentSelectedDocuments?: Array<{ fileId: string; fileName: string; fileType: string; filePath?: string; metadata?: any }>
  ) => {
    // 스트리밍 사용 여부에 따라 다른 함수 호출
    if (options.useStreaming) {
      return sendStreamingMessage(content, agentType, files, currentSelectedDocuments);
    }

    // 기존 비스트리밍 로직
    if ((!content.trim() && !files?.length) || isLoading) return;

    setIsLoading(true);
    setError(null);

    let finalContent = content.trim();
    if (files?.length) {
      finalContent += `\n\n📎 첨부 파일: ${files.map(f => f.name).join(', ')}`;
    }

    let uploadedAssets: UploadedChatAsset[] = [];
    let attachmentsForMessage: ChatAttachment[] = [];

    try {
      const attachmentResult = await prepareAttachments(files);
      uploadedAssets = attachmentResult.uploadedAssets;
      attachmentsForMessage = attachmentResult.attachmentsForMessage;
    } catch (uploadErr: any) {
      console.error('📁 첨부 업로드 실패(비스트리밍):', uploadErr);
      const errorMessage = uploadErr?.response?.data?.detail
        || uploadErr?.message
        || '첨부 파일 업로드 중 오류가 발생했습니다.';
      setError(errorMessage);
      setIsLoading(false);
      if (options.onError) {
        options.onError(new Error(errorMessage));
      }
      return;
    }

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: finalContent,
      timestamp: new Date().toISOString(),
      agent_type: agentType,
      attachments: attachmentsForMessage
    };

    setMessages(prev => [...prev, userMessage]);

    try {
      let messageToSend = content.trim();

      // 에이전트 타입/모드에 따른 메시지 보강 (멀티/체인 호환 주석)
      if (agentType && agentType !== 'general') {
        messageToSend = `[${agentType}] ${messageToSend}`;
      }

      const response = await sendRagChatMessage(messageToSend, {
        provider: null,  // 백엔드 .env 설정 사용
        container_ids: settings.container_ids,
        session_id: sessionId,
        max_tokens: settings.max_tokens,
        temperature: settings.temperature,
        include_references: true,
        attachments: uploadedAssets.map(asset => ({
          asset_id: asset.assetId,
          category: asset.category,
          file_name: asset.fileName
        }))
      });

      const assistantMessage: ChatMessage = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        references: response.references || [],
        context_info: response.context_info,
        rag_stats: response.rag_stats,
        // 🎯 이미지 관련 정보 추가
        image_descriptions: response.image_descriptions,
        uploaded_images: response.images,
        attachments: Array.isArray(response.attachments)
          ? response.attachments.map(mapPayloadToAttachment)
          : undefined
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error('채팅 메시지 전송 실패:', err);
      const errorMessage = err.response?.data?.detail || err.message || '메시지 전송 중 오류가 발생했습니다.';
      setError(errorMessage);

      const errorAssistantMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: `죄송합니다. 오류가 발생했습니다: ${errorMessage}\n\n다시 시도해 주세요.`,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, errorAssistantMessage]);

      if (options.onError) {
        options.onError(new Error(errorMessage));
      }
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, settings, sessionId, options, sendStreamingMessage, prepareAttachments]);

  const clearMessages = useCallback(async () => {
    console.log('🎯 대화 초기화 버튼 클릭!', {
      currentSessionId: sessionId,
      messageCount: messages.length,
      sessionType,
      originalSessionId
    });

    try {
      // 🎯 세션 타입에 따른 다른 처리
      if (sessionType === 'continued' && originalSessionId) {
        // 기존 세션에 추가 대화가 있었던 경우 - 업데이트된 세션을 저장
        console.log('💾 기존 세션 업데이트 저장:', originalSessionId);

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/chat/sessions/${originalSessionId}/archive`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(getAuthHeader())
            }
          });

          if (response.status === 401) {
            // 인증 만료 시 로그인 페이지로 리다이렉트
            handleUnauthorized();
            return;
          }

          if (response.ok) {
            const result = await response.json();
            console.log('✅ 기존 세션 업데이트 저장 성공:', result.message);

            if (options.onSuccess) {
              options.onSuccess('기존 대화가 업데이트되어 저장되었습니다.');
            }
          } else {
            console.warn('⚠️ 세션 업데이트 저장 실패 (계속 진행):', response.statusText);
          }
        } catch (error) {
          console.warn('⚠️ 세션 업데이트 저장 실패 (계속 진행):', error);
        }

      } else if (sessionType === 'new' && sessionId && sessionId !== 'default') {
        // 새 대화였던 경우 - 새 세션으로 저장
        console.log('💾 새 세션 저장:', sessionId);

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/chat/sessions/${sessionId}/archive`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(getAuthHeader())
            }
          });

          if (response.status === 401) {
            // 인증 만료 시 로그인 페이지로 리다이렉트
            handleUnauthorized();
            return;
          }

          if (response.ok) {
            const result = await response.json();
            console.log('✅ 새 세션 저장 성공:', result.message);

            if (options.onSuccess) {
              options.onSuccess('새 대화가 저장되었습니다.');
            }
          } else {
            console.warn('⚠️ 새 세션 저장 실패 (계속 진행):', response.statusText);
          }
        } catch (error) {
          console.warn('⚠️ 새 세션 저장 실패 (계속 진행):', error);
        }

      } else if (sessionType === 'loaded') {
        // 기존 세션을 로드만 했고 새 메시지가 없었던 경우 - 저장하지 않음
        console.log('ℹ️ 로드만 된 세션, 저장하지 않음');
      }

      // 🔥 완전한 상태 초기화
      console.log('🔥 완전한 상태 초기화 시작...');
      console.log('🔍 초기화 전 상태:', {
        currentSessionId: sessionId,
        currentSessionType: sessionType,
        currentOriginalSessionId: originalSessionId,
        currentMessageCount: messages.length
      });

      // 1. 새 세션 ID 생성
      const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      console.log('🔥 새 세션 ID 생성:', newSessionId);

      // 2. 강제로 모든 상태 초기화 (React 배치 업데이트 방지를 위해 순차 실행)
      console.log('🔥 메시지 배열 강제 초기화...');
      setMessages([{
        id: 'clear_conversation',
        role: 'assistant',
        content: '대화가 초기화되었습니다. 새로운 대화를 시작합니다.',
        timestamp: new Date().toISOString()
      }]);

      console.log('🔥 세션 ID 강제 업데이트...');
      setSessionId(newSessionId);

      console.log('🔥 세션 타입 강제 초기화...');
      setSessionType('new');

      console.log('🔥 원본 세션 ID 강제 초기화...');
      setOriginalSessionId(null);

      console.log('🔥 대화 컨텍스트 상태 초기화...');
      setConversationState(null);

      console.log('🔥 에러 상태 강제 초기화...');
      setError(null);

      console.log('🔥 로딩 상태 강제 초기화...');
      setIsLoading(false);

      // 3. URL 정리
      console.log('🔥 URL 파라미터 강제 정리...');
      const url = new URL(window.location.href);
      url.searchParams.delete('session');
      window.history.replaceState({}, '', url.toString());

      // 4. 추가 강제 업데이트 (React 상태 업데이트 보장)
      setTimeout(() => {
        console.log('🔥 지연된 추가 강제 초기화...');
        setMessages([{
          id: 'final_clear',
          role: 'assistant',
          content: '새로운 대화를 시작합니다. 무엇을 도와드릴까요?',
          timestamp: new Date().toISOString()
        }]);

        console.log('🔍 최종 상태 확인:', {
          finalSessionId: newSessionId,
          finalSessionType: 'new',
          finalOriginalSessionId: null
        });
      }, 100);

      console.log('✅ 대화 초기화 1차 완료:', {
        newSessionId,
        sessionType: 'new',
        originalSessionId: null
      });

    } catch (error) {
      console.error('❌ 대화 초기화 중 오류:', error);

      // 🚨 응급 초기화
      const emergencySessionId = `emergency_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      setMessages([{
        id: 'emergency_reset',
        role: 'assistant',
        content: '새로운 대화를 시작합니다. 무엇을 도와드릴까요?',
        timestamp: new Date().toISOString()
      }]);
      setSessionId(emergencySessionId);
      setError(null);
      setIsLoading(false);

      // 세션 상태도 응급 초기화
      setSessionType('new');
      setOriginalSessionId(null);

      // URL 정리
      const url = new URL(window.location.href);
      url.searchParams.delete('session');
      window.history.replaceState({}, '', url.toString());

      console.log('🚨 응급 초기화 완료:', emergencySessionId);
    }
  }, [sessionId, sessionType, originalSessionId, options, messages.length]);

  // 세션 삭제
  const deleteSession = useCallback(async (targetSessionId: string) => {
    try {
      console.log('🗑️ 세션 삭제 시작:', {
        targetSessionId,
        currentSessionId: sessionId,
        originalSessionId,
        sessionType
      });

      const response = await fetch(`${API_BASE_URL}/api/v1/chat/sessions/${targetSessionId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(getAuthHeader())
        }
      });

      if (response.status === 401) {
        // 인증 만료 시 로그인 페이지로 리다이렉트
        handleUnauthorized();
        return;
      }

      if (response.ok) {
        console.log('✅ 백엔드에서 세션 삭제 성공:', targetSessionId);

        // 🎯 중요: 현재 채팅창의 세션과 삭제된 세션이 같은지 확인
        const isCurrentSessionDeleted =
          sessionId === targetSessionId ||
          originalSessionId === targetSessionId ||
          (sessionType === 'continued' && originalSessionId === targetSessionId);

        if (isCurrentSessionDeleted) {
          console.log('🔄 삭제된 세션이 현재 채팅창과 연결됨 - 채팅창 초기화 시작');

          // 채팅창 완전 초기화
          const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

          setMessages([{
            id: 'deleted_reset',
            role: 'assistant',
            content: '삭제된 대화입니다. 새로운 대화를 시작합니다.',
            timestamp: new Date().toISOString()
          }]);
          setSessionId(newSessionId);
          setError(null);
          setIsLoading(false);

          // 세션 상태 초기화
          setSessionType('new');
          setOriginalSessionId(null);

          // URL 정리
          const url = new URL(window.location.href);
          url.searchParams.delete('session');
          window.history.replaceState({}, '', url.toString());

          console.log('✅ 채팅창 초기화 완료:', newSessionId);

          // 성공 메시지 표시
          if (options.onSuccess) {
            options.onSuccess('대화가 삭제되어 새로운 대화를 시작합니다.');
          }
        } else {
          console.log('ℹ️ 삭제된 세션이 현재 채팅창과 다름 - 채팅창 유지');
        }

        return true;
      } else {
        console.error('❌ 세션 삭제 실패:', response.statusText);
        return false;
      }
    } catch (error) {
      console.error('❌ 세션 삭제 중 오류:', error);
      return false;
    }
  }, [sessionId, originalSessionId, sessionType, options]);

  const updateSettings = useCallback((newSettings: Partial<ChatSettings>) => {
    setSettings(prev => ({ ...prev, ...newSettings }));
  }, []);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // Append an assistant message locally (no backend call)
  const addAssistantMessage = useCallback((content: string, extras?: Partial<ChatMessage>) => {
    const msg: ChatMessage = {
      id: `assistant_${Date.now()}`,
      role: 'assistant',
      content,
      timestamp: new Date().toISOString(),
      ...extras
    } as ChatMessage;
    setMessages(prev => [...prev, msg]);
  }, []);

  return {
    // State
    messages,
    setMessages, // 🆕 setMessages 노출
    isLoading,
    error,
    conversationState,
    sessionId,
    settings,
    messagesEndRef,

    // 🎯 세션 상태 정보 추가
    sessionType,
    originalSessionId,

    // Actions
    sendMessage,
    clearMessages,
    deleteSession,
    updateSettings,
    stopStreaming,
    addAssistantMessage,
    createNewSession,
    loadSession,

    // Utils
    scrollToBottom
  };
};
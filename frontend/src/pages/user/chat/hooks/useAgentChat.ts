/**
 * useAgentChat Hook
 * 
 * AI Agent 기반 채팅을 위한 React Hook
 * - Agent API 호출 (/api/v1/agent/chat)
 * - Agent 응답 처리 (steps, metrics, references)
 * - 세션 관리
 * - localStorage 자동 백업/복원
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { AgentChatRequest, agentService } from '../../../../services/agentService';
import { uploadChatAttachments, UploadedChatAsset } from '../../../../services/userService';
import {
  clearPersistedAgentChatState,
  isAgentChatStateExpired,
  readPersistedAgentChatState,
  writePersistedAgentChatState
} from '../../../../utils/agentChatState';
import {
  AgentMessage,
  AgentMetrics,
  AgentSettings,
  AgentStep
} from '../types/agent.types';

interface UseAgentChatOptions {
  defaultSettings?: Partial<AgentSettings>;
  onError?: (error: Error) => void;
  onSuccess?: (message: string) => void;
}

export const useAgentChat = (options: UseAgentChatOptions = {}) => {
  // 메시지 상태
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 🆕 첨부 파일 상태
  const [uploadedAssets, setUploadedAssets] = useState<UploadedChatAsset[]>([]);

  // 세션 상태
  const [sessionId, setSessionId] = useState<string>(() =>
    `agent_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );
  const [isSessionRestored, setIsSessionRestored] = useState(false);

  // 🆕 마지막 상호작용 시간 추적
  const lastInteractionRef = useRef<number>(Date.now());
  const isRestoringRef = useRef<boolean>(false); // 복원 중 플래그
  const isMountedRef = useRef<boolean>(false); // 마운트 완료 플래그

  // Agent 설정
  const [settings, setSettings] = useState<AgentSettings>({
    max_chunks: 10,
    max_tokens: 4000,  // 2000 → 4000으로 증가 (일반 RAG와 동일)
    similarity_threshold: 0.25,  // 0.5 → 0.25로 변경 (일반 RAG와 동일)
    container_ids: [],
    document_ids: [],
    ...options.defaultSettings
  });

  // 현재 실행 중인 Agent 상태
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState<AgentMetrics | null>(null);

  /**
   * 🆕 localStorage에 상태 저장 (AgentChatPage에서만)
   */
  const persistAgentChatState = useCallback(() => {
    // ⚠️ 중요: AgentChatPage에서만 저장되어야 함
    const isAgentChatPage = window.location.pathname.includes('/agent-chat');
    if (!isAgentChatPage) {
      return;
    }

    if (!sessionId) return;

    // 빈 세션은 저장하지 않음
    if (messages.length === 0 && !isSessionRestored) {
      return;
    }

    writePersistedAgentChatState({
      sessionId,
      messages,
      settings,
      lastInteraction: lastInteractionRef.current
    });
  }, [sessionId, messages, settings, isSessionRestored]);

  /**
   * 🆕 메시지 변경 시 마지막 상호작용 시간 업데이트
   */
  useEffect(() => {
    if (!messages.length) return;

    const lastMessage = messages[messages.length - 1];
    const parsedTimestamp = lastMessage?.timestamp ? Date.parse(lastMessage.timestamp) : NaN;
    const resolvedTimestamp = Number.isFinite(parsedTimestamp) ? parsedTimestamp : Date.now();
    lastInteractionRef.current = Math.max(lastInteractionRef.current, resolvedTimestamp);
  }, [messages]);

  /**
   * 🆕 마운트 완료 플래그 설정
   */
  useEffect(() => {
    // 첫 렌더링 직후 플래그 설정
    isMountedRef.current = true;
  }, []);

  /**
   * 🆕 상태 변경 시 자동 저장 (복원 중에는 건너뜀)
   */
  useEffect(() => {
    // 아직 마운트되지 않았으면 저장하지 않음 (초기 렌더링)
    if (!isMountedRef.current) {
      return;
    }

    if (isRestoringRef.current) {
      return; // 복원 중에는 저장하지 않음
    }

    // 빈 세션은 저장하지 않음 (초기 상태)
    if (messages.length === 0 && !isSessionRestored) {
      return;
    }

    persistAgentChatState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, messages, settings]); // persistAgentChatState 대신 실제 의존성 사용

  /**
   * 🆕 초기 mount 시 localStorage에서 복원 (AgentChatPage에서만)
   */
  useEffect(() => {
    // ⚠️ 중요: AgentChatPage에서만 복원되어야 함
    // 일반 채팅 페이지에서는 복원하지 않음
    const isAgentChatPage = window.location.pathname.includes('/agent-chat');
    if (!isAgentChatPage) {
      console.log('🚫 [useAgentChat] Agent 채팅 페이지가 아니므로 복원 건너뜀');
      return;
    }

    // URL 파라미터로 세션 복원하는 경우는 AgentChatPage에서 처리
    // 여기서는 페이지 새로고침이나 재방문 시에만 localStorage 복원
    const urlParams = new URLSearchParams(window.location.search);
    const sessionParam = urlParams.get('session');

    if (sessionParam) {
      // URL 파라미터가 있으면 복원하지 않음 (AgentChatPage에서 처리)
      console.log('🔗 [useAgentChat] URL 파라미터 존재, localStorage 복원 건너뜀');
      return;
    }

    const persisted = readPersistedAgentChatState();
    if (!persisted || !persisted.sessionId) {
      console.log('📭 [useAgentChat] localStorage에 저장된 세션 없음');
      return;
    }

    if (isAgentChatStateExpired(persisted)) {
      console.log('⏰ [useAgentChat] 세션 만료:', persisted.sessionId);
      clearPersistedAgentChatState();
      return;
    }

    // 세션 복원
    console.log('💾 [useAgentChat] localStorage에서 세션 복원:', {
      sessionId: persisted.sessionId,
      messageCount: persisted.messages?.length || 0
    });

    // 복원 플래그 설정
    isRestoringRef.current = true;

    setSessionId(persisted.sessionId);
    setMessages(persisted.messages || []);
    if (persisted.settings) {
      setSettings(prev => ({ ...prev, ...persisted.settings }));
    }
    lastInteractionRef.current = persisted.lastInteraction || Date.now();
    setIsSessionRestored(true);

    // 복원 완료 후 플래그 해제
    setTimeout(() => {
      isRestoringRef.current = false;
    }, 100);
  }, []); // mount 시 한 번만 실행

  /**
   * 🆕 Agent 채팅 메시지 전송 (SSE 스트리밍)
   */
  const sendAgentMessage = useCallback(async (
    content: string,
    selectedDocuments?: Array<{ fileId: string; fileName: string; containerName?: string }>,
    files?: File[],
    tool?: string
  ) => {
    if (!content.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);
    setCurrentSteps([]);
    setCurrentMetrics(null);

    // 🆕 파일 업로드 처리
    let currentUploadedAssets = uploadedAssets;
    if (files && files.length > 0) {
      // 파일 크기 제한 (3MB) - 업로드 전 체크
      const MAX_FILE_SIZE = 3 * 1024 * 1024;
      const oversizedFiles = files.filter(f => f.size > MAX_FILE_SIZE);

      if (oversizedFiles.length > 0) {
        const oversizedNames = oversizedFiles.map(f =>
          `${f.name} (${(f.size / (1024 * 1024)).toFixed(1)}MB)`
        ).join(', ');
        const errorMsg = `📁 파일 크기 제한 초과\n\n${oversizedNames}\n\n채팅에서는 3MB 이하의 파일만 처리 가능합니다.\n큰 파일은 '문서 컨테이너' 메뉴에서 업로드해주세요.`;

        console.error('❌ 파일 크기 초과:', oversizedNames);
        setError(errorMsg);
        setIsLoading(false);

        // 사용자에게 즉시 알림
        if (options.onError) {
          options.onError(new Error(errorMsg));
        }
        return;
      }

      try {
        console.log('📎 파일 업로드 시작:', files.length, '개');
        const uploaded = await uploadChatAttachments(files);
        currentUploadedAssets = [...uploadedAssets, ...uploaded];
        setUploadedAssets(currentUploadedAssets);
        console.log('✅ 파일 업로드 완료:', uploaded);
      } catch (uploadError: any) {
        const errorMsg = uploadError?.message || '파일 업로드 중 오류가 발생했습니다.';
        console.error('❌ 파일 업로드 실패:', uploadError);
        setError(errorMsg);
        setIsLoading(false);

        if (options.onError) {
          options.onError(uploadError);
        }
        return;
      }
    }

    // 사용자 메시지 추가 (🆕 첨부 파일 정보 포함)
    const userMessage: AgentMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
      // 🆕 첨부 파일 정보 추가
      attachments: currentUploadedAssets.length > 0 ? currentUploadedAssets.map(asset => ({
        id: asset.assetId,
        fileName: asset.fileName,
        mimeType: asset.mimeType,
        size: asset.size,
        category: asset.category,
        // 이미지는 미리보기 URL 추가 (백엔드 API 사용)
        // 주의: 백엔드 URL인 경우 인증이 필요하므로 previewUrl에 설정하지 않음 (AuthenticatedImageAttachment가 downloadUrl을 통해 fetch하도록 함)
        previewUrl: (asset.previewUrl && (asset.previewUrl.startsWith('blob:') || asset.previewUrl.startsWith('data:')))
          ? asset.previewUrl
          : undefined,
        downloadUrl: asset.downloadUrl || `/api/v1/chat/assets/${asset.assetId}`
      })) : undefined
    };

    setMessages(prev => [...prev, userMessage]);

    // 🆕 Reasoning 데이터 수집
    const reasoningSteps: any[] = [];
    const searchProgress: any[] = [];
    let streamingContent = '';
    let metadata: any = null;

    try {
      // 🆕 SSE 스트리밍 요청
      const request = {
        message: content.trim(),
        session_id: sessionId,
        max_chunks: settings.max_chunks,
        max_tokens: settings.max_tokens,
        similarity_threshold: settings.similarity_threshold,
        container_ids: settings.container_ids,
        document_ids: settings.document_ids,
        tool: tool, // 🆕 도구 강제 선택
        attachments: currentUploadedAssets.map(asset => ({
          asset_id: asset.assetId,
          id: asset.assetId,  // 백엔드 호환성
          category: asset.category,
          file_name: asset.fileName,
          mime_type: asset.mimeType
        }))
      };

      console.log('🤖 [useAgentChat] SSE 스트리밍 요청:', request);

      const token = localStorage.getItem('ABEKM_token');
      const response = await fetch('/api/v1/agent/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(request),
      });

      if (!response.ok || !response.body) {
        throw new Error('스트리밍 응답 실패');
      }

      // 🆕 SSE 스트리밍 처리
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // 임시 메시지 ID
      const tempMessageId = `agent_${Date.now()}`;

      // 실시간 메시지 업데이트 함수
      const updateStreamingMessage = (updater: (prev: AgentMessage) => AgentMessage) => {
        setMessages(prev => {
          const existingIdx = prev.findIndex(m => m.id === tempMessageId);
          if (existingIdx >= 0) {
            const updated = [...prev];
            updated[existingIdx] = updater(updated[existingIdx] as AgentMessage);
            return updated;
          } else {
            // 첫 메시지 생성
            return [...prev, updater({
              id: tempMessageId,
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
              reasoning: {
                steps: [],
                searchProgress: []
              }
            } as AgentMessage)];
          }
        });
      };

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data:')) continue;

          try {
            const dataStr = line.replace(/^data:\s*/, '').trim();
            if (!dataStr) continue;

            const data = JSON.parse(dataStr);

            // 이벤트 타입별 처리
            const eventMatch = lines[lines.indexOf(line) - 1]?.match(/^event:\s*(.+)/);
            const eventType = eventMatch ? eventMatch[1].trim() : 'unknown';

            if (eventType === 'reasoning_step') {
              // Reasoning 단계 추가
              reasoningSteps.push(data);
              updateStreamingMessage(msg => ({
                ...msg,
                reasoning: {
                  ...msg.reasoning!,
                  steps: reasoningSteps
                }
              }));
            } else if (eventType === 'search_progress') {
              // 검색 진행 상황
              searchProgress.push(data);
              updateStreamingMessage(msg => ({
                ...msg,
                reasoning: {
                  ...msg.reasoning!,
                  searchProgress
                }
              }));
            } else if (eventType === 'content') {
              // 답변 텍스트 추가
              streamingContent += data.delta || '';
              // eslint-disable-next-line no-loop-func
              updateStreamingMessage(msg => ({
                ...msg,
                content: streamingContent
              }));
            } else if (eventType === 'metadata') {
              // 최종 메타데이터
              metadata = data;
            } else if (eventType === 'done') {
              console.log('✅ [useAgentChat] 스트리밍 완료');
              // 🆕 첨부 파일 초기화하지 않음 - 세션 내내 유지
              // setUploadedAssets([]);  // ← 제거: 세션 종료 시에만 초기화
            } else if (eventType === 'error') {
              throw new Error(data.error || '스트리밍 오류');
            }
          } catch (parseError) {
            console.error('SSE 파싱 오류:', parseError, line);
          }
        }
      }

      // 최종 메시지 업데이트
      if (metadata) {
        // 첨부 파일 정보 추출
        const attachedFiles = metadata.attached_files || [];
        // 🆕 특허 분석 결과 추출
        const patentResults = metadata.patent_results || null;
        updateStreamingMessage(msg => ({
          ...msg,
          metadata,
          intent: metadata.intent as any,
          strategy_used: metadata.strategy_used,
          detailed_chunks: metadata.detailed_chunks || [],
          presentation_intent: metadata.intent === 'ppt_generation' ? true : msg.presentation_intent,
          attached_files: attachedFiles,  // 🆕 첨부 파일 메타데이터
          patent_results: patentResults,  // 🆕 특허 분석 결과
          references: metadata.detailed_chunks?.map((chunk: any) => ({
            title: chunk.file_name,
            excerpt: chunk.content_preview,
            file_name: chunk.file_name,
            file_bss_info_sno: chunk.file_id,
            chunk_index: chunk.chunk_index,
            similarity_score: chunk.similarity_score,
            page_number: chunk.page_number,
            section_title: chunk.section_title,
            relevance_percentage: Math.round(chunk.similarity_score * 100),
            relevance_grade: chunk.similarity_score > 0.8 ? '매우 높음' : chunk.similarity_score > 0.6 ? '높음' : '보통'
          })) || [],
          context_info: {
            chunks_count: metadata.chunks_used || 0,
            rag_used: (metadata.total_chunks_searched || 0) > 0,
            total_chunks: metadata.total_chunks_searched || 0,
            answer_source: metadata.patent_results ? 'patent_analysis' : (metadata.answer_source || 'general'),  // 🆕 특허 분석 시 출처 변경
            has_internet_results: metadata.has_internet_results || false  // 🆕 인터넷 검색 결과 여부
          },
          reasoning: {
            steps: reasoningSteps,
            searchProgress,
            intent: metadata.intent,
            strategy: metadata.strategy_used,
            searchStats: metadata.search_stats
          }
        }));
      }

      // 성공 콜백
      if (options.onSuccess) {
        options.onSuccess(streamingContent);
      }

    } catch (err: any) {
      console.error('❌ [useAgentChat] 실패:', err);

      const errorMessage = err.message || 'Agent 채팅 요청 실패';
      setError(errorMessage);

      // 에러 메시지 추가
      const errorAgentMessage: AgentMessage = {
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: `죄송합니다. 오류가 발생했습니다: ${errorMessage}\n\n다시 시도해 주세요.`,
        timestamp: new Date().toISOString(),
        agent_errors: [errorMessage]
      };

      setMessages(prev => [...prev, errorAgentMessage]);

      // 에러 콜백
      if (options.onError) {
        options.onError(new Error(errorMessage));
      }
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, sessionId, settings, options, uploadedAssets]);

  /**
   * 메시지 초기화
   */
  const clearMessages = useCallback(() => {
    console.log('🧹 [useAgentChat] 메시지 초기화');
    setMessages([]);
    clearPersistedAgentChatState();

    // 새 세션 ID 생성
    const freshSessionId = `agent_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(freshSessionId);
    setIsSessionRestored(false);
    setCurrentSteps([]);
    setCurrentMetrics(null);
    setError(null);

    // 🆕 첨부 파일도 초기화 (새 세션 시작)
    setUploadedAssets([]);

    console.log('✅ [useAgentChat] 새 세션:', freshSessionId);
  }, []);

  /**
   * 🆕 어시스턴트 메시지 추가 (PPT 다운로드 링크 등)
   */
  const addAssistantMessage = useCallback((content: string, metadata?: Record<string, any>) => {
    const newMessage: AgentMessage = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      role: 'assistant',
      content,
      timestamp: new Date().toISOString(),
      ...metadata
    };

    setMessages(prev => [...prev, newMessage]);
    console.log('💬 [useAgentChat] 어시스턴트 메시지 추가:', content.substring(0, 50));
  }, []);

  /**
   * Agent 설정 업데이트
   */
  const updateSettings = useCallback((newSettings: Partial<AgentSettings>) => {
    setSettings(prev => ({ ...prev, ...newSettings }));
    console.log('⚙️ [useAgentChat] 설정 업데이트:', newSettings);
  }, []);

  /**
   * 컨테이너 필터 설정
   */
  const setContainerFilter = useCallback((containerIds: string[]) => {
    setSettings(prev => {
      // 값이 실제로 변경되었는지 확인
      const prevIds = prev.container_ids || [];
      if (prevIds.length === containerIds.length &&
        prevIds.every((id, idx) => id === containerIds[idx])) {
        return prev; // 동일하면 상태 업데이트하지 않음
      }
      return { ...prev, container_ids: containerIds };
    });
    console.log('📁 [useAgentChat] 컨테이너 필터:', containerIds);
  }, []);

  /**
   * 특정 메시지 가져오기
   */
  const getMessage = useCallback((messageId: string) => {
    return messages.find(msg => msg.id === messageId);
  }, [messages]);

  /**
   * 마지막 Agent 메시지 가져오기
   */
  const getLastAgentMessage = useCallback(() => {
    const agentMessages = messages.filter(msg => msg.role === 'assistant');
    return agentMessages[agentMessages.length - 1];
  }, [messages]);

  /**
 * 🆕 세션 복원
 */
  const loadSession = useCallback(async (sessionIdToLoad: string) => {
    try {
      console.log('🔄 [useAgentChat] 세션 복원 시작:', sessionIdToLoad);

      const token = localStorage.getItem('ABEKM_token');
      const response = await fetch(`/api/v1/agent/sessions/${sessionIdToLoad}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('세션 복원 실패');
      }

      const sessionData = await response.json();
      console.log('✅ [useAgentChat] 세션 데이터 로드:', {
        session_id: sessionData.session_id,
        message_count: sessionData.message_count
      });

      // 세션 ID 설정
      setSessionId(sessionData.session_id);

      // 메시지 복원
      const restoredMessages: AgentMessage[] = [];
      for (const msg of sessionData.messages) {
        // 사용자 메시지
        restoredMessages.push({
          id: `user_${msg.chat_id}`,
          role: 'user',
          content: msg.user_message,
          timestamp: msg.created_date
        });

        // Assistant 메시지
        restoredMessages.push({
          id: `agent_${msg.chat_id}`,
          role: 'assistant',
          content: msg.assistant_response,
          timestamp: msg.created_date,
          references: msg.search_results?.chunks || [],
          intent: msg.model_parameters?.intent,
          strategy_used: msg.model_parameters?.strategy
        });
      }

      setMessages(restoredMessages);
      setIsSessionRestored(true);

      // 컨테이너 설정 복원
      if (sessionData.allowed_containers) {
        setSettings(prev => ({
          ...prev,
          container_ids: sessionData.allowed_containers
        }));
      }

      console.log(`✅ [useAgentChat] 세션 복원 완료: ${restoredMessages.length}개 메시지`);

      return sessionData;
    } catch (err: any) {
      console.error('❌ [useAgentChat] 세션 복원 실패:', err);
      setError('세션 복원에 실패했습니다.');
      return null;
    }
  }, []);

  /**
   * 🆕 세션 목록 조회
   */
  const listSessions = useCallback(async (limit: number = 20, offset: number = 0) => {
    try {
      const token = localStorage.getItem('ABEKM_token');
      const response = await fetch(`/api/v1/agent/sessions?limit=${limit}&offset=${offset}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('세션 목록 조회 실패');
      }

      const data = await response.json();
      console.log('✅ [useAgentChat] 세션 목록:', data.sessions.length);

      return data;
    } catch (err: any) {
      console.error('❌ [useAgentChat] 세션 목록 조회 실패:', err);
      return { sessions: [], total: 0 };
    }
  }, []);

  /**
   * 🆕 localStorage에 세션 백업
   */
  const backupSessionToLocalStorage = useCallback(() => {
    try {
      const sessionData = {
        sessionId,
        messages: messages.slice(-10), // 최근 10개만 저장
        timestamp: new Date().toISOString()
      };

      localStorage.setItem(`agent_session_${sessionId}`, JSON.stringify(sessionData));
      console.log('💾 [useAgentChat] localStorage 백업 완료');
    } catch (err) {
      console.error('❌ [useAgentChat] localStorage 백업 실패:', err);
    }
  }, [sessionId, messages]);

  /**
   * 🆕 localStorage에서 세션 복원
   */
  const restoreSessionFromLocalStorage = useCallback((sessionIdToRestore: string) => {
    try {
      const stored = localStorage.getItem(`agent_session_${sessionIdToRestore}`);
      if (!stored) return false;

      const sessionData = JSON.parse(stored);
      setSessionId(sessionData.sessionId);
      setMessages(sessionData.messages);
      setIsSessionRestored(true);

      console.log('✅ [useAgentChat] localStorage 복원 완료');
      return true;
    } catch (err) {
      console.error('❌ [useAgentChat] localStorage 복원 실패:', err);
      return false;
    }
  }, []);

  /**
   * A/B 비교 실행
   */
  const compareWithOldArchitecture = useCallback(async (content: string) => {
    try {
      console.log('📊 [useAgentChat] A/B 비교 시작:', content.slice(0, 50));

      const request: AgentChatRequest = {
        message: content.trim(),
        session_id: sessionId,
        max_chunks: settings.max_chunks,
        max_tokens: settings.max_tokens,
        similarity_threshold: settings.similarity_threshold,
        container_ids: settings.container_ids,
        document_ids: settings.document_ids
      };

      const result = await agentService.compareArchitectures(request);

      console.log('✅ [useAgentChat] A/B 비교 완료:', {
        winner: result.winner,
        latency_improvement: result.analysis.latency_improvement
      });

      return result;
    } catch (err: any) {
      console.error('❌ [useAgentChat] A/B 비교 실패:', err);
      throw err;
    }
  }, [sessionId, settings]);

  /**
   * 🆕 개별 첨부 파일 제거
   */
  const removeAttachment = useCallback((assetId: string) => {
    setUploadedAssets(prev => prev.filter(asset => asset.assetId !== assetId));
    console.log('🗑️ [useAgentChat] 첨부 파일 제거:', assetId);
  }, []);

  /**
   * 🆕 모든 첨부 파일 제거
   */
  const clearAttachments = useCallback(() => {
    setUploadedAssets([]);
    console.log('🗑️ [useAgentChat] 모든 첨부 파일 제거');
  }, []);

  return {
    // 상태
    messages,
    isLoading,
    error,
    sessionId,
    settings,
    currentSteps,
    currentMetrics,
    isSessionRestored,
    uploadedAssets,  // 🆕 첨부 파일 상태

    // 액션
    sendMessage: sendAgentMessage,
    clearMessages,
    addAssistantMessage,  // 🆕 어시스턴트 메시지 추가
    updateSettings,
    setContainerFilter,
    getMessage,
    getLastAgentMessage,
    compareWithOldArchitecture,
    setUploadedAssets,  // 🆕 첨부 파일 관리
    removeAttachment,   // 🆕 개별 파일 제거
    clearAttachments,   // 🆕 전체 파일 제거

    // 🆕 세션 관리
    loadSession,
    listSessions,
    backupSessionToLocalStorage,
    restoreSessionFromLocalStorage
  };
};

import { useState } from 'react';
import { getApiUrl } from '../../../../../utils/apiConfig';

type BuildProgress = {
  stage: 'outline_generating' | 'outline_ready' | 'building' | 'complete' | 'error';
  message?: string;
};

export function usePresentation(sessionId: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const buildFromMessage = async (
    sourceMessageId: string,
    opts?: {
      onProgress?: (p: BuildProgress) => void;
      onComplete?: (fileUrl: string, fileName?: string) => void;
      presentationType?: string;
      messageContent?: string;  // AI 답변 내용 추가
    }
  ) => {
    setLoading(true);
    setError(null);
    try {
      // AI 답변 내용을 content_segments로 변환 (현재 사용하지 않음)
      // const outline = opts?.messageContent ? {
      //   contentSegments: [{
      //     id: 'main_content',
      //     type: 'text',
      //     content: opts.messageContent,
      //     priority: 1
      //   }]
      // } : undefined;

      // 원클릭 전용 엔드포인트로 변경
      const apiBaseUrl = getApiUrl();
      const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/agent/presentation/build-quick` : '/api/v1/agent/presentation/build-quick';
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          source_message_id: sourceMessageId,
          // 폴백: 백엔드가 source_message_id를 찾지 못할 때 메시지 본문을 사용
          message: opts?.messageContent
        })
      });

      if (!response.ok || !response.body) {
        if (response.status === 401) {
          // 인증 만료 시 로그인 페이지로 리다이렉트
          localStorage.removeItem('ABEKM_token');
          localStorage.removeItem('ABEKM_refresh_token');
          window.dispatchEvent(new Event('session:invalid'));
          window.location.href = '/login';
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      // SSE 처리: 간단 원클릭. 호출측에서 메시지 업데이트는 기존 훅의 complete 처리로 덮습니다.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'error') {
                setError(data.message || '생성 중 오류가 발생했습니다');
                opts?.onProgress?.({ stage: 'error', message: data.message });
              } else if (data.type === 'warning') {
                // 백엔드 경고 메시지 표시
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message });
              } else if (data.type === 'status') {
                // 백엔드 상태 메시지 표시 (가장 중요!)
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message });
              } else if ((data.type === 'structuring') || (data.type === 'outline_generating')) {
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message || '구조화 중' });
              } else if (data.type === 'agent_thinking') {
                // ReAct Agent 분석 중
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message || 'AI Agent가 분석 중입니다...' });
              } else if (data.type === 'start') {
                // 시작 이벤트 (agent_type 정보 포함 가능)
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message || (data.agent_type === 'ReAct' ? 'ReAct Agent 시작...' : '생성 시작...') });
              } else if (data.type === 'complete') {
                const fileUrl: string | undefined = data.file_url;
                const fileName: string | undefined = data.file_name;
                if (fileUrl) {
                  opts?.onProgress?.({ stage: 'complete' });
                  opts?.onComplete?.(fileUrl, fileName);
                  // ReAct Agent 메타 정보 로깅
                  if (data.agent_type === 'ReAct') {
                    console.log(`✅ [ReAct] PPT 생성 완료 - iterations: ${data.iterations}, tools: ${data.tools_used?.join(', ')}`);
                  }
                }
              }
            } catch { }
          }
        }
      }
    } catch (e: any) {
      setError(e.message || '요청 실패');
    } finally {
      setLoading(false);
    }
  };

  const getOutline = async (sourceMessageId: string, presentationType?: string) => {
    setLoading(true);
    setError(null);
    try {
      const apiBaseUrl = getApiUrl();
      const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/agent/presentation/outline` : '/api/v1/agent/presentation/outline';
      
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          source_message_id: sourceMessageId,
          presentation_type: presentationType || "general"
        })
      });
      if (!res.ok) {
        if (res.status === 401) {
          // 인증 만료 시 로그인 페이지로 리다이렉트
          localStorage.removeItem('ABEKM_token');
          localStorage.removeItem('ABEKM_refresh_token');
          window.dispatchEvent(new Event('session:invalid'));
          window.location.href = '/login';
          return null;
        }
        throw new Error(`HTTP ${res.status}`);
      }
      const json = await res.json();
      return json.outline;
    } catch (e: any) {
      setError(e.message || '아웃라인 요청 실패');
      return null;
    } finally {
      setLoading(false);
    }
  };

  const buildWithOutline = async (
    sourceMessageId: string,
    outline: any,
    templateId?: string,
    opts?: {
      onProgress?: (p: BuildProgress) => void;
      onComplete?: (fileUrl: string, fileName?: string) => void;
      messageContent?: string;  // AI 답변 원본 (폴백용)
    }
  ) => {
    // SSE 엔드포인트 재사용 (outline 전달)
    setLoading(true);
    setError(null);
    try {
      const requestBody: any = { session_id: sessionId, source_message_id: sourceMessageId, outline };
      if (templateId) requestBody.template_id = templateId;

      console.log('서버로 전송하는 PPT 생성 요청:', {
        ...requestBody,
        outline: {
          ...outline,
          textBoxMappings: outline.textBoxMappings?.length || 0,
          contentSegments: outline.contentSegments?.length || 0
        }
      });

      // 🆕 ReAct Agent 엔드포인트 사용 (Plan-Execute도 지원)
      const apiBaseUrl = getApiUrl();
      const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/agent/presentation/build-with-template-react` : '/api/v1/agent/presentation/build-with-template-react';
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          source_message_id: sourceMessageId,
          template_id: templateId,
          max_slides: outline?.slides?.length || outline?.sections?.length || 8,
          presentation_type: 'general',
          // 🆕 AI 답변 원본을 message 필드로 전달 (폴백용)
          message: opts?.messageContent,
          // 레거시 필드 (폴백용)
          outline,
          slide_management: outline?.slide_management,
          object_mappings: outline?.object_mappings,
          content_segments: outline?.contentSegments
        })
      });

      if (!response.ok || !response.body) {
        if (response.status === 401) {
          // 인증 만료 시 로그인 페이지로 리다이렉트
          localStorage.removeItem('ABEKM_token');
          localStorage.removeItem('ABEKM_refresh_token');
          window.dispatchEvent(new Event('session:invalid'));
          window.location.href = '/login';
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'error') {
                setError(data.message || '생성 중 오류');
                opts?.onProgress?.({ stage: 'error', message: data.message });
              } else if (data.type === 'warning') {
                // 백엔드 경고 메시지 표시
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message });
              } else if (data.type === 'status') {
                // 백엔드 상태 메시지 표시 (가장 중요!)
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message });
              } else if (data.type === 'heartbeat') {
                // 🆕 Heartbeat: 연결 유지 + 진행 상태 표시
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message || '작업 진행 중...' });
              } else if (data.type === 'start') {
                // ReAct/PlanExecute 시작
                const agentType = data.agent_type === 'TemplatedReAct' ? 'Template ReAct' :
                  data.agent_type === 'PlanExecute' ? 'Plan-Execute' : '에이전트';
                opts?.onProgress?.({ stage: 'outline_generating', message: `${agentType} Agent 시작...` });
              } else if (data.type === 'agent_thinking') {
                opts?.onProgress?.({ stage: 'outline_generating', message: data.message || 'AI가 분석 중입니다...' });
              } else if (data.type === 'outline_generating' || data.type === 'template_loading') {
                opts?.onProgress?.({ stage: 'outline_generating', message: '아웃라인/템플릿 준비' });
              } else if (data.type === 'outline_ready') {
                opts?.onProgress?.({ stage: 'outline_ready', message: '아웃라인 완료' });
              } else if (data.type === 'complete') {
                if (data.file_url) {
                  opts?.onProgress?.({ stage: 'complete' });
                  opts?.onComplete?.(data.file_url, data.file_name);
                  // ReAct/PlanExecute 메타 정보 로깅
                  if (data.agent_type === 'TemplatedReAct') {
                    console.log(`✅ [TemplatedReAct] PPT 생성 완료 - iterations: ${data.iterations}, tools: ${data.tools_used?.join(', ')}`);
                  } else if (data.agent_type === 'PlanExecute') {
                    console.log(`✅ [PlanExecute] PPT 생성 완료 - steps: ${data.plan_steps}`);
                  }
                  return { file_url: data.file_url, file_name: data.file_name };
                }
              }
            } catch { }
          }
        }
      }
      return null;
    } catch (e: any) {
      setError(e.message || 'PPT 생성 실패');
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { loading, error, buildFromMessage, getOutline, buildWithOutline };
}

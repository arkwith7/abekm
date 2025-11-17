import { useState } from 'react';

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
      const response = await fetch(`/api/v1/chat/presentation/build-quick`, {
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
              } else if ((data.type === 'structuring') || (data.type === 'outline_generating')) {
                opts?.onProgress?.({ stage: 'outline_generating', message: '구조화 중' });
              } else if (data.type === 'complete') {
                const fileUrl: string | undefined = data.file_url;
                const fileName: string | undefined = data.file_name;
                if (fileUrl) {
                  opts?.onProgress?.({ stage: 'complete' });
                  opts?.onComplete?.(fileUrl, fileName);
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
      const res = await fetch(`/api/v1/chat/presentation/outline`, {
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
    opts?: { onProgress?: (p: BuildProgress) => void; onComplete?: (fileUrl: string, fileName?: string) => void }
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

      const response = await fetch(`/api/v1/chat/presentation/build-with-template`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          source_message_id: sourceMessageId,
          template_id: templateId,
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
              } else if (data.type === 'outline_generating' || data.type === 'template_loading') {
                opts?.onProgress?.({ stage: 'outline_generating', message: '아웃라인/템플릿 준비' });
              } else if (data.type === 'outline_ready') {
                opts?.onProgress?.({ stage: 'outline_ready', message: '아웃라인 완료' });
              } else if (data.type === 'complete') {
                if (data.file_url) {
                  opts?.onProgress?.({ stage: 'complete' });
                  opts?.onComplete?.(data.file_url, data.file_name);
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

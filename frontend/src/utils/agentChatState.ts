/**
 * Agent Chat 세션 상태 관리 (localStorage)
 * 
 * 일반 채팅(chatState.ts)과 동일한 패턴으로 구현
 * - localStorage에 자동 저장/복원
 * - TTL 기반 만료 처리 (30분)
 * - 다른 페이지 이동 후 복귀 시 세션 유지
 */

const resolveAgentChatTtlEnv = (): string | undefined => {
  try {
    // Create React App 환경 변수
    if (typeof process !== 'undefined' && process.env) {
      const reactEnv = process.env.REACT_APP_CHAT_SESSION_TTL_MINUTES;
      if (reactEnv) {
        return reactEnv;
      }
    }

    // window 전역 환경 변수 (런타임 주입용)
    if (typeof window !== 'undefined') {
      const windowEnv = (window as unknown as { __env__?: Record<string, string | undefined> }).__env__;
      if (windowEnv?.CHAT_SESSION_TTL_MINUTES) {
        return windowEnv.CHAT_SESSION_TTL_MINUTES;
      }
    }
  } catch (error) {
    console.warn('⚠️ Agent 채팅 TTL 환경 변수 해석 실패:', error);
  }

  return undefined;
};

const AGENT_CHAT_TTL_ENV = resolveAgentChatTtlEnv();

const parseTtlMinutes = (value: string | undefined): number => {
  if (!value) return 30;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 30;
};

export const AGENT_CHAT_STATE_STORAGE_KEY = 'wikl_agent_chat_state';
export const AGENT_CHAT_SESSION_TTL_MS = parseTtlMinutes(AGENT_CHAT_TTL_ENV) * 60 * 1000;

export interface PersistedAgentChatState {
  sessionId: string;
  messages?: any[];
  settings?: any;
  lastInteraction?: number;
}

const hasLocalStorage = () => typeof window !== 'undefined' && !!window.localStorage;

export const readPersistedAgentChatState = (): PersistedAgentChatState | null => {
  if (!hasLocalStorage()) return null;
  try {
    const raw = window.localStorage.getItem(AGENT_CHAT_STATE_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedAgentChatState;
  } catch (error) {
    console.warn('⚠️ Agent 채팅 상태 복원 실패:', error);
    return null;
  }
};

export const writePersistedAgentChatState = (state: PersistedAgentChatState) => {
  if (!hasLocalStorage()) return;
  try {
    window.localStorage.setItem(AGENT_CHAT_STATE_STORAGE_KEY, JSON.stringify(state));
    console.log('💾 [agentChatState] localStorage 저장:', {
      sessionId: state.sessionId,
      messageCount: state.messages?.length || 0
    });
  } catch (error) {
    console.warn('⚠️ Agent 채팅 상태 저장 실패:', error);
  }
};

export const clearPersistedAgentChatState = () => {
  if (!hasLocalStorage()) return;
  try {
    window.localStorage.removeItem(AGENT_CHAT_STATE_STORAGE_KEY);
    console.log('🗑️ [agentChatState] localStorage 삭제');
  } catch (error) {
    console.warn('⚠️ Agent 채팅 상태 삭제 실패:', error);
  }
};

export const isAgentChatStateExpired = (state: PersistedAgentChatState | null, now: number = Date.now()) => {
  if (!state || !state.sessionId) return true;
  if (!state.lastInteraction) return false;
  return now - state.lastInteraction > AGENT_CHAT_SESSION_TTL_MS;
};

export const getActiveAgentChatSessionId = (): string | null => {
  const state = readPersistedAgentChatState();
  if (!state) return null;
  if (isAgentChatStateExpired(state)) {
    console.log('⏰ [agentChatState] 세션 만료:', state.sessionId);
    return null;
  }
  return state.sessionId || null;
};

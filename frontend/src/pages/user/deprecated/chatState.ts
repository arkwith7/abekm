const resolveChatTtlEnv = (): string | undefined => {
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
    console.warn('⚠️ 채팅 TTL 환경 변수 해석 실패:', error);
  }

  return undefined;
};

const CHAT_TTL_ENV = resolveChatTtlEnv();

const parseTtlMinutes = (value: string | undefined): number => {
  if (!value) return 30;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 30;
};

export const CHAT_STATE_STORAGE_KEY = 'ABEKM_chat_state';
export const CHAT_SESSION_TTL_MS = parseTtlMinutes(CHAT_TTL_ENV) * 60 * 1000;

export interface PersistedChatState {
  sessionId: string;
  sessionType?: string;
  originalSessionId?: string | null;
  messages?: any[];
  conversationState?: any;
  lastInteraction?: number;
}

const hasLocalStorage = () => typeof window !== 'undefined' && !!window.localStorage;

export const readPersistedChatState = (): PersistedChatState | null => {
  if (!hasLocalStorage()) return null;
  try {
    const raw = window.localStorage.getItem(CHAT_STATE_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedChatState;
  } catch (error) {
    console.warn('⚠️ 채팅 상태 복원 실패:', error);
    return null;
  }
};

export const writePersistedChatState = (state: PersistedChatState) => {
  if (!hasLocalStorage()) return;
  try {
    window.localStorage.setItem(CHAT_STATE_STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('⚠️ 채팅 상태 저장 실패:', error);
  }
};

export const clearPersistedChatState = () => {
  if (!hasLocalStorage()) return;
  try {
    window.localStorage.removeItem(CHAT_STATE_STORAGE_KEY);
  } catch (error) {
    console.warn('⚠️ 채팅 상태 삭제 실패:', error);
  }
};

export const isChatStateExpired = (state: PersistedChatState | null, now: number = Date.now()) => {
  if (!state || !state.sessionId) return true;
  if (!state.lastInteraction) return false;
  return now - state.lastInteraction > CHAT_SESSION_TTL_MS;
};

export const getActiveChatSessionId = (): string | null => {
  const state = readPersistedChatState();
  if (!state) return null;
  if (isChatStateExpired(state)) return null;
  return state.sessionId || null;
};

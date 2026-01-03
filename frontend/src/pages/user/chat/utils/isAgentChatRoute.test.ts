import { isAgentChatRoute } from './isAgentChatRoute';

describe('isAgentChatRoute', () => {
  test('matches agent chat related routes', () => {
    expect(isAgentChatRoute('/user/agent-chat')).toBe(true);
    expect(isAgentChatRoute('/user/ip-copilot')).toBe(true);
    expect(isAgentChatRoute('/user/prior-art')).toBe(true);
  });

  test('does not match unrelated routes', () => {
    expect(isAgentChatRoute('/user')).toBe(false);
    expect(isAgentChatRoute('/user/my-knowledge')).toBe(false);
    expect(isAgentChatRoute('/user/chat/history')).toBe(false);
  });
});

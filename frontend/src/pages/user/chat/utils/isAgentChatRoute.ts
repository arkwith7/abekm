export const isAgentChatRoute = (pathname: string) => {
  return (
    pathname.includes('/agent-chat') ||
    pathname.includes('/ip-copilot') ||
    pathname.includes('/prior-art')
  );
};

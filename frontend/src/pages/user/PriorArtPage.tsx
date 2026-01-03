import React from 'react';
import AgentChatPage from './AgentChatPage';
import { ToolType } from './chat/components/MessageComposer';

const PriorArtPage: React.FC = () => {
  return (
    <AgentChatPage
      defaultTool={('prior-art' as ToolType)}
      emptyStateTitle="선행기술 조사"
      emptyStateDescription="조사 대상/키워드/발명의 핵심 내용을 입력하면 선행기술 조사 워크플로우를 실행합니다."
    />
  );
};

export default PriorArtPage;

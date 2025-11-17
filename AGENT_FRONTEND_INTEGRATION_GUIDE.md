# AI Agent 프런트엔드 통합 가이드

## 📋 개요

AI Agent 기반 채팅 시스템을 기존 프런트엔드에 통합했습니다. 기존 ChatPage와 병행 운영되며, 사용자는 두 가지 채팅 방식을 선택할 수 있습니다.

---

## 🎯 구현 전략

### 선택한 방식: **Option B - 새 페이지 추가**

**이유:**
- 기존 ChatPage는 복잡한 스트리밍 로직(697줄)이 있어 수정 리스크가 높음
- Agent는 고유한 UI 요소 필요 (Steps Timeline, Intent/Strategy 표시)
- A/B 테스트를 통한 점진적 전환 가능
- 기존 사용자 영향 없이 안전하게 배포 가능

---

## 📂 구현된 파일 구조

```
frontend/src/
├── services/
│   └── agentService.ts                    ✅ Agent API 호출 서비스
├── pages/user/
│   ├── AgentChatPage.tsx                  ✅ Agent 채팅 페이지
│   └── chat/
│       ├── hooks/
│       │   └── useAgentChat.ts            ✅ Agent 전용 hook
│       ├── types/
│       │   └── agent.types.ts             ✅ Agent 타입 정의
│       └── components/
│           ├── AgentStepsTimeline.tsx     ✅ 도구 실행 단계 시각화
│           └── AgentMetricsPanel.tsx      ✅ 성능 지표 패널
└── App.tsx                                 ✅ 라우팅 추가
```

---

## 🚀 접속 방법

### 1. URL 직접 접속
```
http://localhost:3000/user/agent-chat
```

### 2. 사이드바 메뉴 추가 (권장)
`frontend/src/components/Sidebar.tsx` 또는 네비게이션 컴포넌트에 다음 링크 추가:

```tsx
<Link 
  to="/user/agent-chat" 
  className="menu-item"
>
  🤖 AI Agent 채팅 (Beta)
</Link>
```

---

## 🔧 주요 기능

### 1. **Agent API 호출 (`agentService.ts`)**

```typescript
import { agentService } from '../services/agentService';

// 기본 채팅
const response = await agentService.sendAgentChat({
  message: "Roadmapping for Ambidextrous Leadership란?",
  max_chunks: 10,
  max_tokens: 2000,
  similarity_threshold: 0.5,
  container_ids: ["USER_77107791_0627BBC2"]
});

// A/B 비교
const comparison = await agentService.compareArchitectures({
  message: "양손잡이 리더십 문서 찾아줘",
  max_chunks: 10
});
```

**응답 데이터:**
```typescript
{
  answer: string,              // AI 답변
  intent: "FACTUAL_QA",        // 분석된 의도
  strategy_used: ["VectorSearchTool", "DeduplicateTool"],
  steps: [                     // 실행 단계
    {
      step_number: 1,
      tool_name: "VectorSearchTool",
      reasoning: "사용자가 의미 기반 검색을 원함",
      latency_ms: 1100,
      items_returned: 5,
      success: true
    }
  ],
  references: [...],           // 참조 문서
  metrics: {                   // 성능 지표
    total_latency_ms: 15800,
    total_chunks_found: 5,
    deduplication_rate: 0.5
  }
}
```

---

### 2. **Agent 전용 Hook (`useAgentChat`)**

```typescript
import { useAgentChat } from './chat/hooks/useAgentChat';

const {
  messages,           // Agent 메시지 (AgentMessage[])
  isLoading,          // 로딩 상태
  sendMessage,        // 메시지 전송
  clearMessages,      // 초기화
  currentSteps,       // 현재 실행 중인 단계
  currentMetrics,     // 현재 지표
  setContainerFilter  // 컨테이너 필터 설정
} = useAgentChat({
  defaultSettings: {
    max_chunks: 10,
    max_tokens: 2000
  }
});

// 사용 예시
await sendMessage("양손잡이 리더십이란?", selectedDocuments);
```

---

### 3. **UI 컴포넌트**

#### AgentStepsTimeline
도구 실행 과정을 시각적으로 표시:

```tsx
<AgentStepsTimeline 
  steps={lastAgentMessage?.agent_steps}
  isLoading={isLoading}
/>
```

**표시 정보:**
- 각 도구 이름 + 단계 번호
- 실행 시간 (latency_ms)
- 반환된 아이템 수
- 성공/실패 상태
- 추론(Reasoning) 설명

#### AgentMetricsPanel
성능 지표 및 전략 표시:

```tsx
<AgentMetricsPanel
  intent={lastAgentMessage?.intent}
  strategy={lastAgentMessage?.strategy_used}
  metrics={lastAgentMessage?.agent_metrics}
/>
```

**표시 정보:**
- Intent (의도): FACTUAL_QA, KEYWORD_SEARCH 등
- Strategy (전략): 사용된 도구 조합
- Metrics (지표): 실행시간, 검색 청크 수, 토큰 사용량, 중복 제거율

---

## 🧪 테스트 방법

### 1. 개발 서버 실행

```bash
# Backend
cd /home/admin/wkms-aws/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend
cd /home/admin/wkms-aws/frontend
npm start
```

### 2. 브라우저에서 테스트

```
http://localhost:3000/user/agent-chat
```

### 3. 테스트 쿼리 예시

#### ✅ FACTUAL_QA 의도 (벡터 검색)
```
"What is Roadmapping for Ambidextrous Leadership?"
"양손잡이 리더십의 정의는 무엇인가요?"
```

**예상 결과:**
- Intent: `FACTUAL_QA`
- Strategy: `["VectorSearchTool", "DeduplicateTool", "ContextBuilderTool"]`
- 실행시간: ~15초
- 참조 문서: 1-3개

#### ✅ KEYWORD_SEARCH 의도 (하이브리드 검색)
```
"Ambidextrous Leadership 문서 찾아줘"
"리더십 관련 자료 검색"
```

**예상 결과:**
- Intent: `KEYWORD_SEARCH`
- Strategy: `["KeywordSearchTool", "FulltextSearchTool", "DeduplicateTool", "ContextBuilderTool"]`
- 실행시간: ~13초
- 참조 문서: 3-5개
- 중복 제거율: 50%

---

## 🔍 디버깅

### 브라우저 콘솔 확인

```javascript
// Agent 요청 로그
🤖 [AgentService] 요청: { message: "...", container_ids: [...] }

// Agent 응답 로그
✅ [AgentService] 응답: {
  intent: "FACTUAL_QA",
  strategy: ["VectorSearchTool", ...],
  steps_count: 3,
  references_count: 1,
  latency_ms: 15800
}

// Hook 상태 로그
🤖 [useAgentChat] Agent 요청: { message: "...", max_chunks: 10 }
✅ [useAgentChat] Agent 응답: { intent: "FACTUAL_QA", ... }
```

### 네트워크 탭 확인

```
POST /api/v1/agent/chat
Request:
{
  "message": "...",
  "session_id": "agent_...",
  "max_chunks": 10,
  "max_tokens": 2000,
  "similarity_threshold": 0.5,
  "container_ids": ["USER_77107791_0627BBC2"]
}

Response: 200 OK
{
  "answer": "...",
  "intent": "FACTUAL_QA",
  "strategy_used": [...],
  "steps": [...],
  "references": [...],
  "metrics": {...}
}
```

---

## 📊 기존 ChatPage vs AgentChatPage 비교

| 기능 | ChatPage (기존) | AgentChatPage (신규) |
|------|----------------|---------------------|
| **API** | `/api/v1/chat/stream` (SSE) | `/api/v1/agent/chat` (REST) |
| **검색 방식** | 단일 벡터 검색 | 동적 전략 (벡터+키워드+전문) |
| **스트리밍** | ✅ 실시간 스트리밍 | ❌ 완료 후 일괄 응답 |
| **도구 시각화** | ❌ 없음 | ✅ 단계별 표시 |
| **성능 지표** | 기본 통계만 | ✅ 상세 지표 (latency, dedup 등) |
| **의도 분석** | ❌ 없음 | ✅ Intent 자동 분류 |
| **중복 제거** | ❌ 없음 | ✅ 50% 효율 |
| **A/B 테스트** | ❌ 불가능 | ✅ `/api/v1/agent/compare` |

---

## 🎨 UI 개선 제안

### 1. 사이드바에 Agent 메뉴 추가

`frontend/src/components/Sidebar.tsx`:

```tsx
{/* 기존 메뉴 */}
<Link to="/user/chat">💬 일반 채팅</Link>

{/* 추가 메뉴 */}
<Link to="/user/agent-chat">
  🤖 AI Agent 채팅
  <span className="beta-badge">Beta</span>
</Link>
```

### 2. ChatPage에 Agent 모드 전환 버튼 추가 (옵션)

```tsx
<button onClick={() => navigate('/user/agent-chat')}>
  🤖 Agent 모드로 전환
</button>
```

### 3. Agent 결과를 기존 ChatPage에서도 표시 (향후)

기존 사용자가 Agent 기능을 체험할 수 있도록 ChatPage에 "Agent로 다시 검색" 버튼 추가 가능.

---

## 🚧 알려진 제약사항

1. **스트리밍 미지원**: Agent는 REST API이므로 실시간 스트리밍 불가
   - 해결 방안: 향후 SSE 지원 추가 또는 WebSocket 전환

2. **세션 관리**: Agent는 자체 세션 ID 사용
   - 기존 채팅 세션과 분리됨

3. **파일 첨부**: 현재 미지원
   - 향후 백엔드 확장 필요

---

## 📈 다음 단계

### Phase 1: 테스트 및 피드백 (현재)
- [x] Agent 채팅 페이지 구현
- [x] 라우팅 추가
- [ ] 실제 문서로 테스트
- [ ] UI/UX 피드백 수집

### Phase 2: 개선
- [ ] 스트리밍 지원 추가
- [ ] 에러 처리 강화
- [ ] 로딩 상태 애니메이션
- [ ] 모바일 반응형 개선

### Phase 3: 통합
- [ ] 사이드바 메뉴 추가
- [ ] 기존 ChatPage에 Agent 모드 토글
- [ ] A/B 테스트 UI
- [ ] 사용자 피드백 수집 시스템

### Phase 4: 프로덕션
- [ ] 성능 최적화
- [ ] 캐싱 전략
- [ ] 에러 모니터링
- [ ] 점진적 롤아웃 (10% → 50% → 100%)

---

## 🔗 관련 문서

- Backend Agent 구현: `/home/admin/wkms-aws/backend/app/agents/paper_search_agent.py`
- Agent API 명세: `/home/admin/wkms-aws/backend/app/api/v1/agent.py`
- 도구 계약: `/home/admin/wkms-aws/backend/app/tools/contracts.py`
- 아키텍처 문서: `/home/admin/wkms-aws/01.docs/AGENT_ARCHITECTURE_REVIEW.md`

---

## 💡 팁

### Agent 성능 최적화
```typescript
// 빠른 검색 (정확도 낮음)
const settings = {
  max_chunks: 5,
  max_tokens: 1000,
  similarity_threshold: 0.7
};

// 정확한 검색 (속도 느림)
const settings = {
  max_chunks: 20,
  max_tokens: 4000,
  similarity_threshold: 0.4
};
```

### 컨테이너 필터 활용
```typescript
// 특정 컨테이너만 검색
setContainerFilter(["USER_77107791_0627BBC2"]);

// 전체 검색
setContainerFilter([]);
```

---

## 🐛 문제 해결

### 1. Agent 페이지가 보이지 않음
- 라우팅 확인: `frontend/src/App.tsx`에 `<Route path="agent-chat" element={<AgentChatPage />} />` 존재 확인
- 로그인 상태 확인: `/user` 경로는 인증 필요

### 2. API 호출 실패 (401 Unauthorized)
- JWT 토큰 확인: `localStorage.getItem('ABEKM_token')`
- 백엔드 실행 확인: `http://localhost:8000/docs`

### 3. 빈 응답 또는 에러
- 컨테이너에 문서 존재 확인
- 백엔드 로그 확인: `backend/logs/agent.log`
- 환경 변수 확인: `USE_AGENT_ARCHITECTURE=true`

---

## ✅ 체크리스트

프로덕션 배포 전 확인사항:

- [ ] Agent API 정상 작동 확인
- [ ] 모든 Intent 타입 테스트 완료
- [ ] 에러 처리 검증
- [ ] 모바일 반응형 테스트
- [ ] 성능 벤치마크 (평균 응답시간 < 20초)
- [ ] 사용자 피드백 반영
- [ ] 문서화 완료
- [ ] 모니터링 설정

---

**마지막 업데이트:** 2024년 (구현 완료)
**작성자:** AI Assistant
**버전:** 1.0.0

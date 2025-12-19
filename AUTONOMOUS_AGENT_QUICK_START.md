# 자율형 AI 에이전트 빠른 시작 가이드

## 1. 환경 설정

### .env 파일 업데이트

```bash
# 자율형 에이전트 시스템 활성화
ENABLE_AUTONOMOUS_AGENTS=true
USE_PAPER_SEARCH_AGENT_V2=true

# 에이전트 실행 제한
AGENT_MAX_ITERATIONS=15        # 도구 호출 최대 횟수
AGENT_TIMEOUT_SECONDS=180      # 타임아웃 (초)

# LLM 설정 (기존)
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_LLM_DEPLOYMENT=gpt-4o
```

## 2. 서버 시작

```bash
cd /home/admin/Dev/abekm/backend

# 가상환경 활성화
source ../.venv/bin/activate

# 서버 시작
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 3. API 테스트

### 3.1 PaperSearchAgentV2 테스트

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "디지털 트윈 기술의 최신 동향을 알려줘",
    "max_chunks": 10,
    "container_ids": []
  }'
```

**예상 응답**:
```json
{
  "answer": "디지털 트윈 기술은...",
  "intent": "general",
  "strategy_used": ["vector_search", "keyword_search", "rerank", "context_builder"],
  "steps": [
    {
      "step_number": 1,
      "tool_name": "vector_search",
      "reasoning": "의미 기반 검색으로 관련 문서를 찾습니다.",
      "success": true
    }
  ],
  "success": true
}
```

### 3.2 SupervisorAgentV2 테스트 (Python)

```python
from app.agents.supervisor_agent_v2 import supervisor_agent_v2
from langchain_core.messages import HumanMessage

# Supervisor를 통한 자동 라우팅
result = await supervisor_agent_v2.ainvoke({
    "messages": [HumanMessage(content="삼성전자 AI 특허를 분석해줘")],
    "next": "",
    "shared_context": {"request_id": "test-123"}
})

print(result["messages"][-1].content)
# Supervisor가 자동으로 patent_v2 에이전트를 선택하고 실행
```

### 3.3 PatentAnalysisAgentV2 테스트

```python
from app.agents.patent.patent_analysis_agent_v2 import patent_analysis_agent_v2
from app.agents.base import AgentExecutionContext

context = AgentExecutionContext(
    request_id="patent-test-1",
    max_iterations=15,
    timeout=180
)

# ❌ 기존 방식 (analysis_type 필요)
# result = await old_agent.execute(query="삼성 AI 특허", analysis_type="search")

# ✅ 새 방식 (자동 판단)
result = await patent_analysis_agent_v2.execute(
    query="삼성전자와 LG전자의 OLED 특허를 비교 분석해줘",
    context=context
)

print(result.answer)
print(f"실행 단계: {len(result.steps)}")
for step in result.steps:
    print(f"  {step.step_number}. {step.tool_name}: {step.reasoning[:50]}...")
```

## 4. 로그 확인

### 에이전트 실행 로그

```bash
tail -f logs/abekm.log | grep -E "(PaperSearchAgentV2|SupervisorV2|PatentAnalysisV2)"
```

**주요 로그 예시**:
```
[PaperSearchAgentV2] Starting ReAct execution for query: 디지털 트윈...
[PaperSearchAgentV2] Step 1: vector_search - 의미 기반 검색 수행
[PaperSearchAgentV2] Step 2: rerank - 관련도 재정렬
[PaperSearchAgentV2] Completed in 3 steps
```

## 5. 새 에이전트 추가하기

### 5.1 에이전트 클래스 생성

```python
# app/agents/my_custom_agent_v2.py
from app.agents.base import BaseAutonomousAgent, AgentExecutionContext, AgentExecutionResult

class MyCustomAgentV2(BaseAutonomousAgent):
    def __init__(self):
        super().__init__(
            name="my_custom_agent",
            description="나만의 커스텀 에이전트",
            version="2.0.0"
        )
        self._tools = [...]  # 도구 등록
    
    async def _execute_impl(self, query: str, context: AgentExecutionContext, **kwargs):
        # ReAct 패턴 구현
        pass
```

### 5.2 레지스트리에 등록

```python
# app/agents/autonomous_registry.py의 auto_register_autonomous_agents() 함수에 추가

from app.agents.my_custom_agent_v2 import MyCustomAgentV2

AutonomousAgentRegistry.register(
    name="my_custom_agent",
    agent_class=MyCustomAgentV2,
    display_name="My Custom Agent",
    description="커스텀 기능 수행",
    capabilities=["custom", "special"],
    priority=30,
    enabled=True
)
```

### 5.3 자동 발견 확인

```python
# SupervisorAgentV2가 자동으로 인식
from app.agents.autonomous_registry import AutonomousAgentRegistry

agents = AutonomousAgentRegistry.list_enabled()
for agent in agents:
    print(f"{agent.name}: {agent.description}")
# 출력:
# paper_search_v2: 자율형 논문/문서 검색...
# patent_v2: 자율형 특허 검색/분석...
# my_custom_agent: 커스텀 기능 수행  # ✅ 자동 등록됨
```

## 6. 디버깅 팁

### 6.1 Thought-Action-Observation 추적

```python
result = await paper_search_agent_v2.execute(query="...", context=context)

print("=== 에이전트 실행 추적 ===")
for step in result.steps:
    print(f"\nStep {step.step_number}")
    print(f"  Thought: {step.reasoning}")
    print(f"  Action: {step.tool_name}({step.tool_input})")
    print(f"  Observation: {step.tool_output[:100]}...")
```

### 6.2 상태 조회

```python
from app.agents.base.agent_state import AgentStateManager

# 현재 상태
state = AgentStateManager.get_state()
print(f"Request ID: {state.request_id}")
print(f"Iterations: {state.current_iteration}")
print(f"Tools used: {[t['tool_name'] for t in state.tool_usage_history]}")
```

### 6.3 Health Check

```python
agent = AutonomousAgentRegistry.get("paper_search_v2")
health = await agent.health_check()

print(health)
# {
#   "agent_name": "paper_search_agent_v2",
#   "status": "healthy",
#   "version": "2.0.0",
#   "uptime_seconds": 123.45,
#   "tools": {
#     "vector_search": "healthy",
#     "keyword_search": "healthy",
#     ...
#   }
# }
```

## 7. 성능 최적화

### 7.1 최대 반복 횟수 조정

```python
# 복잡한 분석: 더 많은 반복 허용
context = AgentExecutionContext(
    max_iterations=20,  # 기본 15 → 20
    timeout=300
)
```

### 7.2 타임아웃 설정

```python
# 빠른 응답 필요 시
context = AgentExecutionContext(
    max_iterations=10,
    timeout=60  # 1분으로 제한
)
```

### 7.3 도구 실행 병렬화 (향후)

현재 순차 실행, 향후 병렬 실행 지원 예정:
```python
# TODO: 향후 구현
result = await agent.execute(
    query="...",
    context=context,
    parallel_tools=True  # 독립적인 도구는 병렬 실행
)
```

## 8. 문제 해결

### 문제: "Agent not found" 오류

**원인**: 레지스트리에 미등록

**해결**:
```python
# auto_register_autonomous_agents() 함수에 등록되어 있는지 확인
from app.agents.autonomous_registry import auto_register_autonomous_agents
auto_register_autonomous_agents()
```

### 문제: "Max iterations exceeded"

**원인**: 에이전트가 도구를 반복 호출하여 제한 초과

**해결**:
1. `agent_max_iterations` 증가
2. 프롬프트 개선 (불필요한 도구 호출 방지)
3. 로그에서 반복 패턴 분석

### 문제: "Timeout exceeded"

**원인**: 도구 실행 시간 초과

**해결**:
1. `agent_timeout_seconds` 증가
2. 느린 도구 최적화
3. 쿼리 단순화

## 9. 참고 문서

- [AUTONOMOUS_AGENT_IMPLEMENTATION_COMPLETE.md](./AUTONOMOUS_AGENT_IMPLEMENTATION_COMPLETE.md) - 전체 구현 보고서
- [LANGCHAIN_1X_AGENT_IMPROVEMENT_PLAN.md](./LANGCHAIN_1X_AGENT_IMPROVEMENT_PLAN.md) - 개선 계획
- [LangChain ReAct 공식 문서](https://python.langchain.com/docs/modules/agents/agent_types/react)

## 10. 다음 단계

- [ ] SummaryAgentV2 구현
- [ ] DeepResearchAgent 구현
- [ ] ImageGenerationAgent 구현
- [ ] 통합 테스트 작성
- [ ] 성능 벤치마크

---

**작성일**: 2025-12-19  
**버전**: 1.0

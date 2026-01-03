# Search RAG (Feature Pack)

이 디렉토리는 Search RAG 에이전트를 **feature-pack(에이전트 단위 응집)** 형태로 묶습니다.

구성:
- `prompt.md`: 시스템 프롬프트(단일 소스)
- `agent.py`: 기존 `PaperSearchAgent` 구현(이전 위치: `app.agents.paper_search_agent`)
- `graph.py`: Supervisor Worker node(entrypoint)
- `worker.py`: AgentCatalog discovery용 WorkerSpec 제공

호환성:
- 기존 import 경로 `app.agents.paper_search_agent` 는 shim으로 유지됩니다.

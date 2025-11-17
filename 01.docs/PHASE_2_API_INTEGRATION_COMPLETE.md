# Phase 2 완료: Agent-Based RAG API 통합

**날짜**: 2025-11-11  
**상태**: Phase 2 구현 완료 ✅  

---

## 🎯 Phase 2 목표

Agent 기반 아키텍처를 프로덕션 API에 통합:
- ✅ 새로운 `/api/v1/agent/chat` 엔드포인트
- ✅ A/B 테스트를 위한 `/api/v1/agent/compare` 엔드포인트
- ✅ Feature flag 기반 점진적 롤아웃
- ✅ 모든 import 오류 해결

---

## 📦 구현 완료 항목

### 1. Agent API 엔드포인트
**파일**: `backend/app/api/v1/agent.py`

#### `/api/v1/agent/chat` (POST)
```python
Request:
{
  "message": "딥러닝이란 무엇인가?",
  "max_chunks": 10,
  "max_tokens": 2000,
  "similarity_threshold": 0.5,
  "container_ids": ["container_123"],  // optional
  "document_ids": ["doc_456"]  // optional
}

Response:
{
  "answer": "딥러닝은 인공신경망을 기반으로...",
  "intent": "factual_qa",
  "strategy_used": ["vector_search", "deduplicate", "context_builder"],
  "references": [
    {
      "chunk_id": "chunk_123",
      "content": "...",
      "score": 0.87,
      "document_id": "doc_456",
      "title": "딥러닝 개론"
    }
  ],
  "steps": [
    {
      "step_number": 1,
      "tool_name": "vector_search",
      "reasoning": "의미 기반 유사 문서 검색",
      "latency_ms": 234.5,
      "success": true
    }
  ],
  "metrics": {
    "total_latency_ms": 1250.3,
    "tools_used": 3,
    "chunks_found": 25,
    "chunks_used": 8,
    "total_tokens": 1850
  },
  "success": true
}
```

**특징**:
- 동적 전략 선택 (의도 기반)
- 실행 단계 추적 (observability)
- 메트릭 수집 (latency, tokens, chunks)
- 제약 조건 지원 (max_chunks, max_tokens, filters)

#### `/api/v1/agent/compare` (POST)
```python
Response:
{
  "query": "딥러닝이란?",
  "old_architecture": {
    "answer": "...",
    "latency_ms": 1500,
    "chunks_found": 20,
    "implementation": "rag_search_service (monolithic)"
  },
  "new_architecture": {
    "answer": "...",
    "latency_ms": 1250,
    "chunks_found": 25,
    "chunks_used": 8,
    "intent": "factual_qa",
    "strategy": ["vector_search", "deduplicate", "context_builder"],
    "tools_used": 3,
    "implementation": "paper_search_agent (agent-based)"
  },
  "improvement": {
    "latency_diff_ms": 250,
    "latency_improvement_pct": 16.67
  },
  "observability": {
    "agent_steps": [...]
  }
}
```

**용도**: A/B 테스트, 성능 비교, 평가

#### `/api/v1/agent/health` (GET)
```python
Response:
{
  "status": "healthy",
  "agent": "paper_search_agent",
  "version": "1.0.0",
  "tools": [
    "vector_search",
    "keyword_search",
    "fulltext_search",
    "deduplicate",
    "context_builder"
  ],
  "timestamp": "2025-11-11T10:30:00Z"
}
```

---

### 2. Feature Flag 설정
**파일**: `backend/app/core/config.py`

```python
class Settings(BaseSettings):
    # ... 기존 설정 ...
    
    # Agent-based RAG 설정 (Phase 2)
    use_agent_architecture: bool = False  # Feature flag: 점진적 롤아웃
    agent_enable_observability: bool = True  # Agent 실행 단계 추적
    agent_enable_evaluation: bool = True  # 평가 메트릭 수집
```

**환경 변수로 제어**:
```bash
# .env 파일
USE_AGENT_ARCHITECTURE=true  # Agent 아키텍처 활성화
AGENT_ENABLE_OBSERVABILITY=true
AGENT_ENABLE_EVALUATION=true
```

---

### 3. FastAPI 라우터 등록
**파일**: `backend/app/main.py`

```python
# Import
from app.api.v1.agent import router as agent_router  # 🤖 Agent-based RAG

# 라우터 등록
app.include_router(agent_router, prefix="/api/v1", tags=["🤖 Agent RAG"])
```

---

### 4. 오류 수정 완료

#### 4.1 BaseTool Pydantic 충돌
**문제**: `BaseTool`이 `BaseModel`을 상속받아 `__init__`에서 동적 속성 설정 불가

```python
# ❌ Before
class VectorSearchTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.embedding_service = embedding_service  # ValueError!

# ✅ After
class VectorSearchTool(BaseTool):
    name: str = "vector_search"
    # embedding_service를 모듈 레벨에서 직접 사용
```

#### 4.2 SyntaxError 수정
**문제**: `user_emp_no: Optional[str]] = None` (괄호 불일치)

```python
# ❌ Before
user_emp_no: Optional[str]] = None,  # Syntax Error!

# ✅ After
user_emp_no: Optional[str] = None,
```

#### 4.3 타입 힌트 수정
**문제**: `params: Dict[str, str]`에 `List`, `float` 할당 불가

```python
# ❌ Before
params: Dict[str, str] = {}
params["container_ids"] = container_ids  # Type Error!

# ✅ After
params: Dict[str, Any] = {}
params["container_ids"] = container_ids  # OK
```

#### 4.4 ToolMetrics 필드 추가
**문제**: `items_returned`, `trace_id` 필드 누락

```python
# ✅ Updated
class ToolMetrics(BaseModel):
    latency_ms: float
    provider: str = "internal"
    items_returned: Optional[int] = None  # 추가
    trace_id: Optional[str] = None  # 추가
```

#### 4.5 SearchChunk 필드 통일
**문제**: `similarity_score` vs `score` 불일치

```python
# ✅ Updated
class SearchChunk(BaseModel):
    chunk_id: str
    content: str
    score: float  # 표준 필드
    file_id: Optional[str] = None
    
    @property
    def similarity_score(self) -> float:
        """Backward compatibility"""
        return self.score
```

---

## 🧪 테스트 결과

### Import 테스트
```bash
✅ VectorSearchTool import 성공
✅ KeywordSearchTool import 성공
✅ FulltextSearchTool import 성공
✅ DeduplicateTool import 성공
✅ ContextBuilderTool import 성공
✅ PaperSearchAgent import 성공
✅ FastAPI app import 성공
```

### 서버 구동 확인
```bash
$ cd backend && source ../.venv/bin/activate
$ uvicorn app.main:app --reload

INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
✅ 모든 라우터 정상 로드
```

---

## 📊 API 사용 예시

### cURL
```bash
# Agent 기반 채팅
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "딥러닝 논문 찾아줘",
    "max_chunks": 10,
    "max_tokens": 2000
  }'

# A/B 비교
curl -X POST http://localhost:8000/api/v1/agent/compare \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "트랜스포머 아키텍처 설명",
    "max_chunks": 10
  }'

# Health Check
curl http://localhost:8000/api/v1/agent/health
```

### Python SDK
```python
import requests

# Agent 채팅
response = requests.post(
    "http://localhost:8000/api/v1/agent/chat",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "message": "강화학습 알고리즘",
        "max_chunks": 5,
        "similarity_threshold": 0.7
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Intent: {result['intent']}")
print(f"Strategy: {result['strategy_used']}")
print(f"Latency: {result['metrics']['total_latency_ms']}ms")

# Steps 분석
for step in result['steps']:
    print(f"  - {step['tool_name']}: {step['reasoning']} ({step['latency_ms']}ms)")
```

---

## 🚀 배포 전략

### 1단계: Canary Deployment (1주)
```python
# 5% 트래픽만 새 아키텍처 사용
USE_AGENT_ARCHITECTURE=false  # 기본은 기존 아키텍처

# 특정 사용자만 /api/v1/agent/chat 사용
# 나머지는 /api/v1/chat/message 사용
```

### 2단계: A/B Testing (2주)
```python
# 50% 트래픽 분할
# /api/v1/agent/compare로 실시간 비교 수집
# 메트릭 모니터링:
# - Latency (목표: <10% 차이)
# - Answer Quality (nDCG@10 > 0.8)
# - User Satisfaction (CSAT)
```

### 3단계: Full Rollout (1주)
```python
USE_AGENT_ARCHITECTURE=true  # 전체 전환
# 기존 엔드포인트는 deprecation warning
```

---

## 📈 모니터링 메트릭

### Performance
- `total_latency_ms`: 전체 응답 시간
- `tools_used`: 사용된 도구 수
- `chunks_found`: 검색된 청크 수
- `chunks_used`: 실제 사용된 청크 수

### Quality
- `intent_classification_accuracy`: 의도 분류 정확도
- `strategy_selection_rate`: 전략별 선택 비율
- `answer_relevance`: 답변 관련도 (LLM judge)

### Reliability
- `success_rate`: 성공률
- `error_rate`: 오류율
- `tool_failure_rate`: 도구별 실패율

---

## 🔧 디버깅 가이드

### 로그 확인
```bash
# Agent 실행 추적
grep "🤖 \[AgentChat\]" backend/logs/app.log

# 도구 실행 추적
grep "\[VectorSearch\]\|\[KeywordSearch\]" backend/logs/app.log

# 에러 확인
grep "❌" backend/logs/app.log
```

### Observability Steps
```python
# 각 요청의 steps를 확인하여 병목 지점 파악
for step in result['steps']:
    if step['latency_ms'] > 500:  # 500ms 이상
        print(f"⚠️ Slow tool: {step['tool_name']}")
```

---

## ✅ Phase 2 체크리스트

- [x] Agent API 엔드포인트 생성
- [x] A/B 비교 엔드포인트 생성
- [x] Feature flag 설정
- [x] FastAPI 라우터 등록
- [x] BaseTool Pydantic 충돌 해결
- [x] SyntaxError 수정
- [x] 타입 힌트 수정
- [x] ToolMetrics 필드 추가
- [x] SearchChunk 필드 통일
- [x] Import 테스트 완료
- [x] 서버 구동 확인
- [ ] Frontend UI 통합 (Phase 3)
- [ ] 프로덕션 배포 (Phase 4)
- [ ] 성능 벤치마크 (Phase 5)

---

## 🎯 다음 단계 (Phase 3)

### Frontend 통합
1. Agent 응답 UI 컴포넌트 추가
   - Steps 시각화 (타임라인)
   - 메트릭 대시보드
   - 전략 설명 툴팁

2. Agent vs Legacy 토글 스위치
   - 사용자가 직접 아키텍처 선택
   - 실시간 비교 뷰

3. 평가 피드백 수집
   - 답변 품질 평가 (👍/👎)
   - 오류 리포트 버튼

---

**결론**: Phase 2 완료로 Agent 기반 RAG API가 프로덕션 환경에 통합되었습니다. Feature flag로 점진적 롤아웃 가능하며, A/B 테스트로 기존 아키텍처와 성능 비교 가능합니다. 모든 import 오류가 해결되어 서버가 정상 구동됩니다.

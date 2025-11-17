# AI Agent 기반 RAG 전환 비판적 분석 (2025-11-11)

## 1. 현재 상태 진단

### 1.1 구조적 문제점

#### 문제 A: "도구" vs "서비스" 경계 불명확
**현재 상태:**
```python
# enhanced_agent_tools.py - 970+ lines
class GeneralChatTool(BaseTool):
    async def _arun(self, ...):
        # 내부에서 ai_agent_service 직접 호출
        enhanced_query, references, context_info, rag_stats = 
            await ai_agent_service.prepare_context_with_documents(...)
        
        # RAG 검색 로직이 Tool 내부에 숨어있음
        # → Tool이 실제로는 "오케스트레이터" 역할
```

**문제점:**
- `GeneralChatTool`이 실제로는 RAG 검색 + LLM 호출 + 웹 검색 fallback을 모두 수행하는 "메타 에이전트"
- 도구(Tool)라기보다는 "서비스 파사드(Facade)" 수준
- 개별 검색 전략(벡터/키워드/하이브리드)을 독립적으로 조합할 수 없음

#### 문제 B: RAG 검색 로직의 과도한 응집
**현재 상태:**
```python
# rag_search_service.py - 1986 lines
class RAGSearchService:
    async def search_for_rag_context(self, ...):
        # 질의 분석
        # 언어 감지
        # 멀티턴 컨텍스트 강화
        # 하이브리드 검색 (벡터+키워드+fulltext)
        # Adaptive threshold
        # PPT 의도 부스팅
        # 중복 제거
        # 품질 검증
        # 리랭킹
        # 컨텍스트 빌드
        # 토큰 컷
        # ... (모든 기능이 단일 메서드에 집중)
```

**문제점:**
- 단일 책임 원칙(SRP) 위반: 12개 이상의 독립적 기능이 하나의 파이프라인에 하드코딩
- 검색 전략 교체 불가능: 벡터 검색만 사용하거나, 키워드만 사용하는 경로 없음
- 테스트 불가능: 중간 단계(예: 후보 수집 vs 리랭킹)를 독립적으로 검증할 수 없음
- Agent가 "도구"를 선택할 수 없음: 이미 모든 전략이 고정된 순서로 실행됨

#### 문제 C: LangGraph 워크플로우의 유명무실
```python
# langgraph_workflow.py
class MultiAgentOrchestrator:
    def document_analyzer_node(self, state):
        # 실제 분석 없음 - 목업 데이터만 반환
        analysis_result = {
            "document_count": len(documents),
            "content_summary": "문서들의 주요 내용 요약",  # 하드코딩
            ...
        }
```

**문제점:**
- LangGraph는 도입했지만 실제 도구 호출 없음
- Agent 오케스트레이션이 아닌 "시뮬레이션"
- `integrated_service.py`의 단일/멀티 분기도 휴리스틱 기반 결정 후 결국 동일 서비스 호출

### 1.2 아키텍처 불일치
**의도한 설계:**
```
Agent → Tool Selection → Tool Execution → Result Aggregation
```

**실제 구현:**
```
API → IntegratedService → (단순 분기) → RagSearchService (monolith) → LLM
                                     ↘ LangGraphWorkflow (mock)
```

---

## 2. "AI Agent 기반 RAG" 전환 목표 재정의

### 2.1 핵심 설계 원칙
1. **도구 원자성(Tool Atomicity)**: 각 도구는 단일 명확한 책임
2. **조합 가능성(Composability)**: Agent가 런타임에 도구 조합 결정
3. **관찰 가능성(Observability)**: 각 도구 호출이 독립적으로 추적 가능
4. **교체 가능성(Replaceability)**: 인터페이스만 유지하면 구현 교체 가능

### 2.2 도구(Tool) 정의 기준
**도구로 적합:**
- 입력/출력이 명확하고 부수효과(side effect) 최소
- 독립적으로 테스트/평가 가능
- 다른 도구와 조합해 사용 가능

**도구로 부적합 (서비스/헬퍼):**
- 다른 도구를 여러 개 호출하는 오케스트레이션
- 상태 의존적이거나 컨텍스트가 필요
- 비즈니스 로직 의사결정 포함

---

## 3. 제안: 3-Layer 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: Agent Orchestration                            │
│  - PaperSearchAgent, PPTAgent, WebSearchAgent          │
│  - ReAct/Chain-of-Thought planning                      │
│  - Tool selection + execution loop                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: Atomic Tools (Stateless, Testable)            │
│  ┌─────────────┬──────────────┬────────────────────┐   │
│  │ Retrieval   │ Processing   │ Generation         │   │
│  ├─────────────┼──────────────┼────────────────────┤   │
│  │ VectorTool  │ RerankTool   │ SummarizeTool      │   │
│  │ KeywordTool │ DedupeTool   │ OutlineTool        │   │
│  │ FulltextTool│ FilterTool   │ SlideContentTool   │   │
│  │ WebSearchTool│ ContextTool │ CiteTool           │   │
│  └─────────────┴──────────────┴────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: Core Services (Stateful, Reusable)            │
│  - Database Access (Repository)                         │
│  - Embedding Service (Multi-provider)                   │
│  - LLM Service (Multi-provider)                         │
│  - NLP Service (Tokenizer, Morphology)                  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 구체적 재설계 제안

### 4.1 원자 도구 분해 (Atomic Tool Decomposition)

#### 현재 (문제):
```python
# rag_search_service.search_for_rag_context()
# → 12개 기능이 단일 파이프라인에 하드코딩
```

#### 제안 (해결):
```python
# 1) 검색 도구 (독립적)
class VectorSearchTool(BaseTool):
    """벡터 유사도 검색 전용"""
    async def _arun(self, query: str, embedding: List[float], 
                    top_k: int, threshold: float, 
                    container_ids: Optional[List[str]]) -> SearchResult:
        # pgvector <=> 연산만 수행
        # 리랭킹/필터/중복제거 등 다른 로직 포함 X

class KeywordSearchTool(BaseTool):
    """키워드 매칭 검색 전용 (ILIKE/regex)"""
    async def _arun(self, query: str, keywords: List[str], 
                    top_k: int, container_ids: Optional[List[str]]) -> SearchResult:
        # 키워드 ILIKE/regex 검색만

class FulltextSearchTool(BaseTool):
    """전문검색 (tsvector) 전용"""
    async def _arun(self, query: str, tsquery: str, 
                    top_k: int, language: str) -> SearchResult:
        # PostgreSQL tsvector @@ tsquery만

# 2) 후처리 도구 (독립적)
class RerankTool(BaseTool):
    """Cross-encoder 재랭킹"""
    async def _arun(self, query: str, candidates: List[Chunk], 
                    model: str, top_k: int) -> RankedResult:
        # bge-reranker / cohere rerank API 호출만

class DeduplicateTool(BaseTool):
    """중복 청크 제거"""
    async def _arun(self, chunks: List[Chunk], 
                    threshold: float) -> DedupeResult:
        # 해시/유사도 기반 중복 제거만

class ContextBuilderTool(BaseTool):
    """컨텍스트 토큰 패킹"""
    async def _arun(self, chunks: List[Chunk], max_tokens: int, 
                    tokenizer: str) -> ContextResult:
        # 토큰 계산 + 우선순위 정렬 + 슬라이싱만

# 3) 웹 증강 도구 (현재 GeneralChatTool 내부에 숨어있음 → 독립)
class WebSearchTool(BaseTool):
    """외부 웹 검색 (이미 구현됨 - 개선 필요)"""
    # 현재는 mock만 반환, 실제 API 연동 필요

class WebFetchTool(BaseTool):
    """URL 본문 추출"""
    # 현재 구현 양호
```

### 4.2 Agent 구현 패턴

#### 현재 문제:
```python
# integrated_service.py
async def _execute_single_agent(...):
    # "single" 이라지만 실제로는 복잡한 파이프라인 실행
    enhanced_query, references, context_info, rag_stats = 
        await ai_agent_service.prepare_context_with_documents(...)
    # ↑ 내부에서 이미 모든 검색/리랭킹/컨텍스트 구성 완료
```

#### 제안:
```python
class PaperSearchAgent:
    """논문/문서 검색 전문 Agent"""
    
    def __init__(self):
        # 도구 등록 (느슨한 결합)
        self.tools = {
            "vector_search": VectorSearchTool(),
            "keyword_search": KeywordSearchTool(),
            "fulltext_search": FulltextSearchTool(),
            "rerank": RerankTool(),
            "dedupe": DeduplicateTool(),
            "context_builder": ContextBuilderTool(),
            "web_search": WebSearchTool(),  # fallback용
        }
    
    async def search(self, query: str, constraints: Dict) -> AgentResult:
        # Step 1: 질의 분석 (Agent 책임)
        intent = self._classify_intent(query)
        keywords = self._extract_keywords(query)
        embedding = await self._get_embedding(query)
        
        # Step 2: 검색 전략 선택 (Agent 책임 - 동적 결정)
        strategy = self._select_strategy(intent, constraints)
        # strategy 예: ["vector_search", "keyword_search", "rerank", "dedupe"]
        
        # Step 3: 도구 순차 실행 (각 도구는 독립적)
        results = []
        for tool_name in strategy:
            tool = self.tools[tool_name]
            if tool_name == "vector_search":
                result = await tool._arun(
                    query=query, 
                    embedding=embedding, 
                    top_k=constraints.get("top_k", 20),
                    threshold=constraints.get("threshold", 0.25),
                    container_ids=constraints.get("container_ids")
                )
            elif tool_name == "rerank":
                result = await tool._arun(
                    query=query,
                    candidates=results,  # 이전 단계 결과 재사용
                    model="bge-reranker",
                    top_k=10
                )
            # ... 각 도구 호출 파라미터 Agent가 결정
            results = result.chunks
        
        # Step 4: 최종 컨텍스트 구성
        context = await self.tools["context_builder"]._arun(
            chunks=results,
            max_tokens=constraints.get("max_tokens", 4000),
            tokenizer="gpt-3.5-turbo"
        )
        
        # Step 5: LLM 응답 생성 (Agent 책임)
        answer = await self._generate_answer(query, context)
        
        return AgentResult(
            answer=answer,
            references=context.chunks,
            steps=self._trace,  # 사용된 도구 로그
            metrics=self._collect_metrics()
        )
    
    def _select_strategy(self, intent: str, constraints: Dict) -> List[str]:
        """동적 전략 선택 - 핵심 Agent 로직"""
        if intent == "factual_qa":
            # 사실 확인 질문 → 벡터 + 리랭킹
            return ["vector_search", "rerank", "dedupe", "context_builder"]
        
        elif intent == "keyword_search":
            # 키워드 중심 → 키워드 + 전문검색 병합
            return ["keyword_search", "fulltext_search", "dedupe", "context_builder"]
        
        elif intent == "exploratory":
            # 탐색 질문 → 하이브리드 + 웹 fallback
            base = ["vector_search", "keyword_search", "rerank"]
            # 내부 검색 실패 시 웹 검색 추가
            if constraints.get("allow_web_fallback"):
                base.append("web_search")
            base.extend(["dedupe", "context_builder"])
            return base
        
        else:
            # 기본 전략
            return ["vector_search", "dedupe", "context_builder"]
```

### 4.3 도구 표준 인터페이스

```python
# tools/contracts.py
from typing import Protocol, TypedDict, Any, List
from pydantic import BaseModel

class ToolMetrics(TypedDict):
    latency_ms: float
    provider: str
    cache_hit: bool
    retries: int
    cost_estimate: Optional[float]

class ToolResult(BaseModel):
    success: bool
    data: Any
    metrics: ToolMetrics
    errors: List[str]
    trace_id: str

class SearchToolResult(ToolResult):
    """검색 도구 전용 결과 타입"""
    data: List[Dict[str, Any]]  # chunks
    total_found: int
    filtered_count: int

class ToolProtocol(Protocol):
    name: str
    description: str
    version: str
    
    async def _arun(self, **kwargs) -> ToolResult:
        """비동기 실행 (권장)"""
        ...
    
    def _run(self, **kwargs) -> ToolResult:
        """동기 실행 (폴백)"""
        ...
```

---

## 5. 마이그레이션 로드맵

### Phase 1: 도구 추출 (2주)
```
rag_search_service.py (1986 lines)
  ↓ 분해
retrieval/
  vector_search_tool.py      (150 lines)
  keyword_search_tool.py     (120 lines)
  fulltext_search_tool.py    (100 lines)
processing/
  rerank_tool.py             (180 lines)
  dedupe_tool.py             (90 lines)
  filter_tool.py             (80 lines)
context/
  context_builder_tool.py    (150 lines)
  token_optimizer.py         (100 lines)
```

**검증:**
- 각 도구별 단위 테스트 (입력 → 출력 검증)
- 골든셋 100건으로 Recall@K 회귀 테스트

### Phase 2: Agent 구현 (2주)
```python
agents/
  paper_search_agent.py      # 논문 검색 전문
  ppt_generation_agent.py    # PPT 생성 전문
  web_search_agent.py        # 웹 검색 전문
  base_agent.py              # 공통 추상 클래스
  contracts.py               # Agent 인터페이스
```

**검증:**
- Agent별 end-to-end 테스트
- 전략 선택 로직 단위 테스트
- 기존 API 응답 호환성 검증

### Phase 3: 평가 체계 (1주)
```
evaluation/
  datasets/
    paper_search_golden.json
    ppt_generation_golden.json
  metrics/
    search_quality.py          # nDCG, Recall, MRR
    generation_quality.py      # BLEU, ROUGE, Faithfulness
  harness.py                   # 자동 평가 실행
```

### Phase 4: 관측성 (1주)
```python
# OpenTelemetry 추가
@trace_tool_execution
async def _arun(self, **kwargs):
    with tracer.start_as_current_span(self.name) as span:
        span.set_attribute("tool.version", self.version)
        span.set_attribute("tool.input.size", len(str(kwargs)))
        result = await self._execute(**kwargs)
        span.set_attribute("tool.output.success", result.success)
        return result

# Prometheus 지표
tool_latency = Histogram("tool_execution_latency_seconds", 
                         ["tool_name", "success"])
tool_calls = Counter("tool_calls_total", ["tool_name", "agent"])
```

### Phase 5: 점진 전환 (2주)
```python
# Feature flag 기반 A/B
if feature_flags.is_enabled("new_agent_architecture", user_id):
    agent = PaperSearchAgent()
    result = await agent.search(query, constraints)
else:
    # 기존 경로
    result = await rag_search_service.search_for_rag_context(...)
```

---

## 6. 비판적 평가: 현재 vs 제안

### 6.1 현재 접근의 문제
| 측면 | 현재 상태 | 문제점 |
|------|-----------|--------|
| **도구 정의** | Tool이 "메타 서비스" (GeneralChatTool이 RAG 전체 수행) | 도구 조합 불가능 |
| **검색 전략** | 하드코딩된 파이프라인 (벡터→키워드→전문→리랭킹 고정) | 동적 선택 불가 |
| **테스트** | 통합 테스트만 가능 (중간 단계 검증 불가) | 회귀 감지 어려움 |
| **확장성** | 새 검색 방식 추가 시 1986 라인 파일 수정 | 높은 변경 비용 |
| **Agent 역할** | 단순 분기 (single vs multi) 결정만 | 실질적 Agent 아님 |

### 6.2 제안 접근의 장점
| 측면 | 제안 설계 | 이점 |
|------|-----------|------|
| **도구 정의** | 원자 단위 (VectorSearchTool, RerankTool 독립) | 조합 가능 |
| **검색 전략** | Agent가 런타임 결정 (_select_strategy) | 의도/제약 기반 최적화 |
| **테스트** | 도구별 독립 단위 테스트 + Agent 통합 테스트 | 회귀 즉시 감지 |
| **확장성** | 새 도구 추가만으로 기능 확장 (기존 코드 수정 X) | 낮은 변경 비용 |
| **Agent 역할** | 실제 계획(planning) + 실행(execution) | 진정한 Agent |

---

## 7. 잠재 리스크 & 완화 전략

### Risk 1: 성능 오버헤드
**우려:** 도구 호출 오버헤드 누적 (12개 도구 → 12번 함수 호출)
**완화:**
- 도구 내부는 lean (DB 쿼리/API 호출 시간이 지배적)
- 병렬 실행 가능한 도구는 asyncio.gather 사용
- 측정 후 병목 도구만 최적화 (premature optimization 방지)

### Risk 2: 복잡도 증가
**우려:** 12개 독립 파일 → 유지보수 부담?
**완화:**
- 명확한 인터페이스 (ToolProtocol) → 학습 곡선 낮음
- 각 파일 100~200 라인(현재 1986 라인보다 낮음)
- 도구별 독립 테스트 → 디버깅 시간 단축

### Risk 3: 전환 비용
**우려:** 기존 시스템 전체 재작성?
**완화:**
- Phase별 점진 전환 (5단계 × 1~2주)
- Feature flag로 병렬 운영
- 기존 API 엔드포인트 유지 (내부만 교체)

---

## 8. 즉시 실행 가능한 Quick Wins

### Quick Win 1: VectorSearchTool 추출 (3일)
```python
# 현재: rag_search_service.py 내부
async def _execute_hybrid_search(...):
    # 벡터 검색 SQL 직접 실행
    query = text("""SELECT ... FROM doc_embedding WHERE ...""")

# 제안: tools/vector_search_tool.py
class VectorSearchTool(BaseTool):
    async def _arun(self, query_embedding, top_k, threshold, ...):
        # 동일 SQL이지만 독립 모듈
        # → 테스트/재사용/교체 가능
```

### Quick Win 2: RerankTool 독립화 (2일)
```python
# 현재: rag_search_service._rerank_results()
# → 내부 메서드, 독립 호출 불가

# 제안: tools/rerank_tool.py
class RerankTool(BaseTool):
    async def _arun(self, query, candidates, model="bge-reranker"):
        # Cross-encoder 재랭킹
        # → 다른 Agent에서도 재사용 가능
```

### Quick Win 3: 평가 데이터셋 (1일)
```json
// evaluation/datasets/search_golden.json
[
  {
    "query": "인슐린 펌프의 작동 원리",
    "intent": "factual_qa",
    "expected_docs": ["doc_123", "doc_456"],
    "min_similarity": 0.6
  },
  // ... 100건
]
```

---

## 9. 최종 권고사항

### ✅ 제안 아키텍처 채택 권장
**이유:**
1. 현재 구조는 "Agent"라는 이름만 있고 실질적으로는 monolithic service
2. RAG 검색이 하드코딩된 파이프라인 → 도구 조합 불가능
3. 테스트/평가/확장 모두 어려움 → 장기적 유지보수 비용 ↑
4. 제안된 3-Layer 아키텍처는 업계 표준 (LangChain, LlamaIndex, Haystack 등 동일 구조)

### ⚠️ 단, 점진적 전환 필수
**전체 재작성 금지:**
- Phase별 마이그레이션 (5단계 × 1~2주 = 2.5개월)
- Feature flag로 기존 시스템 병렬 운영
- 핵심 도구(VectorSearch, Rerank) 먼저 추출
- 평가 데이터셋으로 회귀 지속 확인

### 🎯 첫 Sprint 목표 (2주)
1. `VectorSearchTool`, `KeywordSearchTool`, `RerankTool` 추출
2. `PaperSearchAgent` v0.1 구현 (3개 도구만 사용)
3. 평가 데이터셋 100건 구축
4. 기존 vs 신규 성능 비교 (nDCG@10, Recall@10)

---

## 10. 결론

**현재 구현의 근본 문제:**  
"AI Agent 기반"이라고 하지만 실제로는 **"복잡한 서비스를 Tool로 wrapping한 것"**에 불과합니다. `GeneralChatTool`이 내부에서 RAG 전체 파이프라인을 실행하므로, Agent가 도구를 "선택"하거나 "조합"할 여지가 없습니다.

**제안의 핵심 가치:**  
진정한 **"Tool as Primitive"** 설계로, Agent가 런타임에 검색 전략을 동적으로 구성할 수 있게 합니다. 이는 단순히 구조 개선이 아니라, **테스트 가능성·확장성·품질 측정 가능성을 동시에 확보**하는 전략입니다.

**제안 아키텍처를 채택하면:**
- 새로운 검색 방식(예: GraphRAG, Hybrid Reranker) 추가가 기존 코드 수정 없이 가능
- 각 도구별 성능 측정으로 병목 지점 정확히 식별
- Agent별 특화 전략 개발 (PaperSearch vs PPTGeneration 다른 도구 조합)
- A/B 테스트로 전략 효과 정량 평가

**권장 시작점:** Quick Win 3개부터 시작하여 점진적 전환하세요.

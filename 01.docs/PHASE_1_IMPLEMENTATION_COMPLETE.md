# Agent-Based RAG Architecture - Implementation Complete (Phase 1)

**날짜**: 2025-01-11  
**상태**: Phase 1 구현 완료  

---

## 🎯 구현 목표

기존 모놀리식 RAG 파이프라인을 **Agent 기반 아키텍처**로 전환:
- 🔧 **Tool as Primitive**: 단일 책임 원칙을 따르는 독립적 도구
- 🤖 **Agent Orchestration**: 동적 전략 선택과 도구 조합
- 📊 **Observability**: 추적 가능한 실행 단계와 메트릭
- ✅ **Testability**: 개별 도구 단위 테스트 가능

---

## 📦 Phase 1 완료 항목

### 1. 표준 인터페이스 정의
**파일**: `backend/app/tools/contracts.py`

```python
# 핵심 프로토콜
- ToolProtocol: 모든 도구가 구현해야 할 표준 인터페이스
- AgentProtocol: 에이전트 표준 인터페이스
- ToolResult: 표준 반환 타입 (success, data, metrics, errors, trace_id)
- SearchChunk: 검색 결과 청크 표준 포맷
- AgentResult: 에이전트 실행 결과
```

**의미**:
- 모든 도구가 동일한 계약(contract)을 따름
- 도구 교체/추가가 쉬움 (느슨한 결합)
- 관찰 가능성 내장 (metrics, trace_id)

---

### 2. Atomic Tools (6개 도구)

#### 2.1 검색 도구 (Retrieval)

##### VectorSearchTool
**파일**: `backend/app/tools/retrieval/vector_search_tool.py`

```python
입력: query, top_k, similarity_threshold, container_ids, document_ids
출력: List[SearchChunk] with pgvector <=> scores
기능: 쿼리 임베딩 → pgvector 유사도 검색 → 점수 계산
```

##### KeywordSearchTool
**파일**: `backend/app/tools/retrieval/keyword_search_tool.py`

```python
입력: query, keywords, top_k
출력: List[SearchChunk] with keyword match scores
기능: 키워드 추출 → ILIKE 매칭 → 매칭 점수 계산
```

##### FulltextSearchTool
**파일**: `backend/app/tools/retrieval/fulltext_search_tool.py`

```python
입력: query, tsquery_str, top_k
출력: List[SearchChunk] with ts_rank scores
기능: tsquery 생성 → tsvector @@ tsquery → ts_rank 점수
```

#### 2.2 후처리 도구 (Processing)

##### DeduplicateTool
**파일**: `backend/app/tools/processing/deduplicate_tool.py`

```python
입력: chunks, similarity_threshold
출력: List[SearchChunk] (중복 제거됨)
기능: chunk_id 중복 제거 → 내용 유사도 중복 제거
```

##### RerankTool
**파일**: `backend/app/tools/processing/rerank_tool.py`

```python
입력: chunks, query, model_name
출력: List[SearchChunk] (재순위화됨)
기능: Cross-encoder로 쿼리-문서 관련도 재평가 (현재 mock)
```

#### 2.3 컨텍스트 도구

##### ContextBuilderTool
**파일**: `backend/app/tools/context/context_builder_tool.py`

```python
입력: chunks, max_tokens, include_metadata, format_style
출력: 포맷된 컨텍스트 텍스트 + used_chunks + total_tokens
기능: 토큰 추정 → 우선순위 정렬 → 포맷팅 (citation 스타일)
```

---

### 3. PaperSearchAgent 구현
**파일**: `backend/app/agents/paper_search_agent.py`

```python
역할:
1. 질의 분석 (의도 분류, 키워드 추출)
2. 전략 선택 (의도에 따라 도구 조합 결정)
3. 도구 순차 실행 (각 도구는 독립적)
4. 컨텍스트 구성 및 답변 생성

핵심 메서드:
- classify_intent(query) → AgentIntent
- select_strategy(intent, constraints) → List[tool_names]
- execute(query, db_session, constraints) → AgentResult

전략 예시:
- FACTUAL_QA: ["vector_search", "deduplicate", "context_builder"]
- KEYWORD_SEARCH: ["keyword_search", "fulltext_search", "deduplicate", "context_builder"]
- COMPARISON: ["vector_search", "keyword_search", "deduplicate", "context_builder"]
```

**핵심 장점**:
- 동적 전략 선택: 의도에 따라 다른 도구 조합
- 관찰 가능성: 모든 단계(AgentStep) 추적
- 확장 가능: 새 도구 추가 시 전략만 수정

---

### 4. 평가 시스템

#### Golden Dataset
**파일**: `backend/app/evaluation/datasets/paper_search_golden.json`

```json
{
  "queries": [
    {
      "id": "q001",
      "query": "딥러닝을 활용한 자연어 처리 방법론",
      "intent": "factual_qa",
      "expected_documents": ["doc_12345_chunk_1", ...],
      "relevance_judgments": {
        "doc_12345_chunk_1": {"score": 3, "label": "highly_relevant"}
      }
    }
  ]
}
```

#### Metrics
**파일**: `backend/app/evaluation/metrics.py`

```python
함수:
- calculate_ndcg_at_k(retrieved, relevance, k=10) → float
- calculate_recall_at_k(retrieved, expected, k=10) → float
- calculate_precision_at_k(retrieved, expected, k=10) → float
- calculate_mrr(retrieved, expected) → float
- evaluate_query(query_data, retrieved) → Dict[metric_name, score]
- aggregate_metrics(query_metrics) → Dict[avg/std metrics]
```

---

### 5. 테스트 코드

#### 통합 테스트
**파일**: `backend/app/tests/test_paper_search_agent.py`

```python
테스트:
- test_paper_search_agent_factual_qa: 사실 확인 질문
- test_paper_search_agent_keyword_search: 키워드 검색
- test_paper_search_agent_comparison: 비교 질문
- test_paper_search_agent_with_constraints: 제약 조건
- test_paper_search_agent_observability: 관찰 가능성 (steps/metrics)
```

#### 단위 테스트
**파일**: `backend/app/tests/test_tools.py`

```python
테스트:
- test_vector_search_tool: 벡터 검색
- test_keyword_search_tool: 키워드 검색
- test_fulltext_search_tool: 전문검색
- test_deduplicate_tool: 중복 제거
- test_context_builder_tool: 컨텍스트 구성
- test_tool_error_handling: 에러 핸들링
```

---

## 🏗️ 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────┐
│            API Layer (FastAPI)                  │
│  /api/v1/chat, /api/v1/search                   │
└─────────────────┬───────────────────────────────┘
                  │
        ┌─────────▼─────────┐
        │  PaperSearchAgent │  ← 전략 선택 & 오케스트레이션
        │  (Orchestration)  │
        └─────────┬─────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐   ┌────▼────┐   ┌───▼────┐
│Vector │   │Keyword  │   │Fulltext│  ← Atomic Tools
│Search │   │Search   │   │Search  │    (단일 책임)
└───┬───┘   └────┬────┘   └───┬────┘
    │             │            │
    └─────────────┼────────────┘
                  │
        ┌─────────▼─────────┐
        │  DeduplicateTool  │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │ ContextBuilderTool│
        └─────────┬─────────┘
                  │
    ┌─────────────▼─────────────┐
    │   Core Services Layer     │
    │ (Embedding, AI, NLP, DB)  │
    └───────────────────────────┘
```

---

## 📊 Before vs After

### Before (Monolithic)
```python
rag_search_service.py (1986 lines)
├─ 벡터 검색 로직
├─ 키워드 검색 로직
├─ 전문검색 로직
├─ 중복 제거 로직
├─ 재순위화 로직
├─ 컨텍스트 구성 로직
├─ 대화 이력 관리
├─ 적응형 임계값 조정
├─ 하이브리드 병합
└─ 답변 생성
    → 하드코딩된 파이프라인
    → 단위 테스트 불가
    → 전략 변경 시 전체 수정
```

### After (Agent-based)
```python
PaperSearchAgent
├─ classify_intent(query) → AgentIntent
├─ select_strategy(intent) → List[tool_names]  ← 핵심!
└─ execute() → AgentResult
      ├─ VectorSearchTool (250 lines)
      ├─ KeywordSearchTool (200 lines)
      ├─ FulltextSearchTool (180 lines)
      ├─ DeduplicateTool (150 lines)
      └─ ContextBuilderTool (180 lines)
          → 동적 도구 조합
          → 개별 도구 단위 테스트 가능
          → 새 전략 추가 시 도구만 조합
```

---

## 🔑 핵심 개선 사항

### 1. Tool as Primitive
- **Before**: "도구"가 실제로는 전체 파이프라인을 오케스트레이션하는 메타-서비스
- **After**: 도구는 진짜 원자적 작업 수행 (검색, 중복제거, 컨텍스트 구성 등)

### 2. 느슨한 결합 (Loose Coupling)
- **Before**: 모든 로직이 rag_search_service.py에 강결합
- **After**: 각 도구가 독립적, 표준 인터페이스(ToolProtocol)로 통신

### 3. 동적 전략 선택
- **Before**: 하드코딩된 단일 파이프라인
- **After**: 의도에 따라 다른 도구 조합 (`select_strategy()`)

### 4. 관찰 가능성 (Observability)
- **Before**: 블랙박스 (내부 실행 과정 추적 불가)
- **After**: 
  - 모든 도구가 `ToolResult` 반환 (success, metrics, trace_id)
  - 에이전트가 `AgentStep[]` 추적
  - 디버깅/모니터링 가능

### 5. 테스트 가능성
- **Before**: 통합 테스트만 가능 (1986줄 전체 실행)
- **After**: 
  - 도구별 단위 테스트 가능
  - 에이전트 통합 테스트 가능
  - Mocking 쉬움 (느슨한 결합)

### 6. 평가 시스템
- **Before**: 주관적 평가만 가능
- **After**: 
  - Golden dataset으로 객관적 평가
  - nDCG@10, Recall@10, Precision@10, MRR 측정
  - 전략별 성능 비교 가능

---

## 📁 디렉토리 구조

```
backend/app/
├─ tools/                          ← 도구 계층
│  ├─ __init__.py
│  ├─ contracts.py                 ← 표준 인터페이스/타입
│  ├─ retrieval/
│  │  ├─ __init__.py
│  │  ├─ vector_search_tool.py
│  │  ├─ keyword_search_tool.py
│  │  └─ fulltext_search_tool.py
│  ├─ processing/
│  │  ├─ __init__.py
│  │  ├─ deduplicate_tool.py
│  │  └─ rerank_tool.py
│  └─ context/
│     ├─ __init__.py
│     └─ context_builder_tool.py
│
├─ agents/                         ← 에이전트 계층
│  ├─ __init__.py
│  └─ paper_search_agent.py
│
├─ evaluation/                     ← 평가 시스템
│  ├─ __init__.py
│  ├─ metrics.py
│  └─ datasets/
│     └─ paper_search_golden.json
│
└─ tests/                          ← 테스트
   ├─ test_tools.py                (단위 테스트)
   └─ test_paper_search_agent.py  (통합 테스트)
```

---

## 🚀 다음 단계 (Phase 2)

### 1. API 통합
- `/api/v1/chat` 엔드포인트에서 `paper_search_agent.execute()` 호출
- Feature flag로 기존 `rag_search_service`와 병행 운영

### 2. 추가 에이전트 구현
- `PPTAgent`: PPT 생성 전문 에이전트
- `WebSearchAgent`: 웹 검색 전문 에이전트

### 3. 평가 자동화
- Golden dataset 확장 (100+ queries)
- CI/CD 파이프라인에 평가 통합
- 성능 리그레션 감지

### 4. 고급 기능
- Cross-encoder 모델 실제 통합 (RerankTool)
- LangGraph로 멀티-에이전트 워크플로우
- 대화 이력 기반 쿼리 재작성
- 적응형 임계값 자동 조정

---

## ✅ 검증 체크리스트

- [x] 표준 계약(contracts) 정의
- [x] 6개 atomic tools 구현
- [x] PaperSearchAgent 구현
- [x] Golden dataset 템플릿 작성
- [x] 평가 메트릭 구현
- [x] 단위 테스트 작성
- [x] 통합 테스트 작성
- [ ] API 엔드포인트 통합 (Phase 2)
- [ ] 실제 데이터로 평가 (Phase 2)
- [ ] 성능 벤치마크 (Phase 2)

---

## 📝 핵심 코드 예시

### 에이전트 사용법

```python
from app.agents import paper_search_agent
from app.tools.contracts import AgentConstraints
from sqlalchemy.ext.asyncio import AsyncSession

async def search_papers(query: str, db: AsyncSession):
    # 에이전트 실행
    result = await paper_search_agent.execute(
        query=query,
        db_session=db,
        constraints=AgentConstraints(
            max_chunks=10,
            max_tokens=2000,
            similarity_threshold=0.5
        ),
        context={"user_emp_no": "user123"}
    )
    
    # 결과 활용
    print(f"답변: {result.answer}")
    print(f"의도: {result.intent}")
    print(f"전략: {result.strategy_used}")
    print(f"참조 문서: {len(result.references)}개")
    print(f"실행 단계: {len(result.steps)}개")
    
    # 관찰 가능성
    for step in result.steps:
        print(f"  - {step.tool_name}: {step.reasoning}")
        print(f"    Latency: {step.tool_output.metrics.latency_ms}ms")
```

### 개별 도구 사용법

```python
from app.tools import vector_search_tool, deduplicate_tool, context_builder_tool

# 1. 벡터 검색
search_result = await vector_search_tool._arun(
    query="딥러닝 논문",
    db_session=db,
    top_k=20
)

# 2. 중복 제거
dedup_result = await deduplicate_tool._arun(
    chunks=search_result.data
)

# 3. 컨텍스트 구성
context_result = await context_builder_tool._arun(
    chunks=dedup_result.data,
    max_tokens=2000
)

print(context_result.data)  # 포맷된 컨텍스트
```

---

**결론**: Phase 1 완료로 **Tool as Primitive** 아키텍처 기반 확립. Agent가 동적으로 전략을 선택하고 도구를 조합할 수 있는 구조 완성. 이제 API 통합과 실제 평가로 넘어갈 준비 완료.

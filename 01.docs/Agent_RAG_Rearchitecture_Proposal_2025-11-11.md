# 에이전트/도구 중심 RAG 재아키텍처 제안 (2025-11-11)

본 문서는 현재 복잡한 RAG + 멀티 에이전트 구현을 "에이전트(Agent)와 도구(Tool)" 중심 구조로 재정렬하는 제안서입니다. 목표는 명확한 책임 경계, 테스트 용이성, 품질 측정 가능성, 향후 확장/운영 편의성입니다.

---

## 1. 문제 인식 (현재 상태 평가)
- RAG 핵심 로직이 단일 대형 서비스에 응집되어(예: `rag_search_service.py`) 전처리/후보수집/랭킹/컨텍스트/통계/휴리스틱이 혼재됨.
- LangGraph 워크플로우 노드 로직은 목업 수준이며 실제 도구 호출/오케스트레이션과 분리.
- 임베딩/LLM 다중 벤더 폴백은 구현되어 있으나, 품질/비용/지연 기반의 동적 선택 정책은 미흡.
- 평가/테스트/메트릭 체계가 부족하여 휴리스틱 조정에 대한 객관적 성능 검증이 어려움.

---

## 2. 설계 원칙
- SRP(단일 책임), 명확한 계약(Contract), 표준화된 I/O 스키마, 가벼운 도구(재사용), 강한 관측성.
- "에이전트 = 목표 지향 오케스트레이터", "도구 = 검증 가능한 순수 기능(검색, 요약, 생성, 변환 등)".
- 모든 도구는 동등한 계약을 가지며 독립 테스트가 가능해야 함.

---

## 3. 표준 도구 계약 (Tool Contract)
각 도구는 동일한 인터페이스를 따릅니다.
- 입력(Input): `name`, `version`, `params`(dict), `context`(선택)
- 출력(Output): `success: bool`, `data: any`, `metrics: dict`, `usage: dict`, `errors: list[str]`
- 오류 모드: 입력검증 실패(400), 외부의존 오류(502), 타임아웃(504), 내부예외(500)
- 공통 메트릭: `latency_ms`, `provider`, `cost_tokens/$`(가능 시), `cache_hit`, `retries`

제안 Python 시그니처 예:
```python
class ToolProtocol(Protocol):
    name: str
    version: str
    async def arun(self, params: dict, context: dict | None = None) -> ToolResult: ...
```

---

## 4. 표준 에이전트 계약 (Agent Contract)
- 역할: 사용자 목표 달성을 위해 도구들을 선택/조합/순서화.
- 입력: `user_query`, `selected_documents`(선택), `constraints`(토큰 한도, 시간, 비용)
- 출력: `answer`, `references`, `steps`(사용된 도구 호출 로그), `metrics`(총 지연/비용)
- 실패 시: 부분 결과 + 디버그 가능한 step 로그 제공.

---

## 5. 목표 에이전트 정의 (3종)

### 5.1 AI 논문검색 Agent (PaperSearchAgent)
- 목적: 내부/외부 논문 탐색 및 근거 반환.
- 주요 도구:
  - RAGSearchTool: 내부 DB 하이브리드 검색(텍스트/표/이미지) + 컨텍스트 빌드
  - WebSearchTool: 외부 검색(API) + HTML→텍스트 추출 + 요약
  - RerankTool: Cross-Encoder 재랭킹
  - CiteFormatTool: 참고 문헌 포맷팅(BibTeX/APA)
- 입력: `topic`, `constraints(max_docs, date_range, containers)`
- 출력: `summary`, `citations[]`, `evidence_chunks[]`, `metrics`

### 5.2 AI PPT 생성 Agent (PPTAgent)
- 목적: 질의/자료 기반 슬라이드 아웃라인 생성 및 PPTX 출력.
- 도구:
  - OutlineTool: 문서 요약→슬라이드 구조 생성
  - SlideContentTool: 슬라이드별 본문/키포인트 생성
  - ChartSuggestionTool: 데이터 테이블→차트 제안
  - PPTExportTool: 파워포인트 파일 생성(템플릿/스타일 적용)
- 입력: `prompt`, `selected_documents`, `slide_count`, `template_style`
- 출력: `pptx_path`, `outline`, `preview_images(optional)`, `metrics`

### 5.3 AI Web검색 Agent (WebSearchAgent)
- 목적: 최신 외부 정보 수집→요약→근거 반환.
- 도구:
  - WebSearchTool: 검색쿼리 확장 + 결과 스크래핑
  - DeduplicateTool: 중복/저품질 필터
  - SummarizeTool: 소스별 요약 + 집계 요약
  - VerifyTool: 사실 검증(여러 소스 교차)
- 출력: `final_summary`, `sources[]`, `risk_notes`, `metrics`

---

## 6. 모듈 구조 (제안)
```
app/
  agents/
    paper_search_agent.py
    ppt_agent.py
    web_search_agent.py
    contracts.py  # AgentContract, ToolContract
  tools/
    rag_search_tool.py
    web_search_tool.py
    rerank_tool.py
    outline_tool.py
    slide_content_tool.py
    ppt_export_tool.py
    utils/  # 공통 전처리/토크나이저/메트릭
  retrieval/
    query_processing.py
    candidate_retrieval.py
    ranking.py
    context_builder.py
  eval/
    datasets/
    metrics.py
    harness.py
```

---

## 7. 마이그레이션 단계
1) 도구 추출: `rag_search_service.py`를 `retrieval/*` + `tools/rag_search_tool.py`로 분해.
2) PPT 기능 분해: 프레젠테이션 관련 로직을 `tools/`로 이동, 통합 서비스는 Agent에서 orchestration만.
3) Agent 구현: 세 에이전트를 명확한 입력/출력 계약으로 작성, 기존 API는 Agent 엔드포인트로 매핑.
4) 평가/테스트: 골든셋 작성 → `eval/harness.py`로 자동 평가(nDCG@K, Recall@K, Rerank gain 등).
5) 관측성: OpenTelemetry trace + Prometheus 지표(도구/에이전트 단위) 추가.
6) 점진 릴리스: 기능 flag로 일부 트래픽을 신규 경로로 전환(A/B).

---

## 8. 품질·테스트 전략
- 데이터셋: 내부 쿼리 100~300건 수준, 문서 정답 라벨(문서ID/청크ID), 최신성 태그.
- 메트릭: Recall@K, nDCG@K, MRR, Context Utilization Rate, Answer Faithfulness(LLM judge 선택적).
- 하니스: 동일 질의/조건에서 baseline vs candidate 비교 + 통계 유의성 검정.
- 단위 테스트: Tool별 input validation, timeout, error path, serialization.
- 통합 테스트: Agent end-to-end(가짜 LLM/DB로 결정적 결과 보장).

---

## 9. 운영 가이드(요약)
- Provider Selection Policy: 지연/오류/비용 기반 동적 선택(EMA).
- 임베딩 차원 정책: 단일 표준 차원으로 통일하거나 모델별 컬럼 분리.
- 비밀/로그: PII 마스킹, secret redaction, 쿼리 샘플링 제한.
- 재인덱싱: 증분 파이프라인(Celery), 메타 데이터 변경 이벤트 기반.

---

## 10. 일정/비용 러프 추정
- 2–4주: 도구 분해 + PaperSearchAgent v1 + 평가 하니스 v1
- 4–6주: PPTAgent v1 + WebSearchAgent v1 + 관측성 지표
- 6–8주: Provider policy + reranker 도입 + A/B 실험

---

## 11. 결론
에이전트/도구 중심으로 재정렬하면 모듈 경계가 명확해지고, 각 구성요소를 독립적으로 테스트/측정/교체할 수 있습니다. 이는 운영 안정성과 품질 개선 속도를 동시에 높이며, 향후 기능 확장(새 도구/새 에이전트 추가)도 예측 가능한 비용으로 구현 가능하게 합니다.

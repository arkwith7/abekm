# WKMS AI Agent & RAG 구현 리뷰 (2025-11-11)

## 1. 개요
본 문서는 현재 `backend` / `frontend` 디렉토리에서 확인된 AI Agent 및 RAG(Relevent-Augmented Generation) 기반 검색/응답 시스템의 구조, 강점, 리스크, 개선 방향을 정리한 기술 리뷰입니다.

## 2. 전반 아키텍처 요약
- **백엔드 기술 스택**: FastAPI, PostgreSQL (pgvector + tsvector), SQLAlchemy, LangChain, LangGraph, AWS Bedrock, Azure OpenAI, OpenAI, Redis, Celery.
- **프론트엔드 기술 스택**: React + TypeScript + TailwindCSS. 서비스 레이어를 통해 REST API 호출.
- **주요 기능 블럭**:
  - 질의 전처리 파이프라인 (`query_pipeline.py`)
  - 다중 LLM/Embedding 제공자 관리 (`ai_service.py`, `embedding_service.py`)
  - RAG 검색 및 컨텍스트 구성 (`rag_search_service.py`)
  - 통합 검색(하이브리드, 벡터, 키워드, 멀티모달) API (`app/api/v1/search.py`)
  - 멀티 에이전트 워크플로우 (LangGraph 기반, `langgraph_workflow.py` + 통합 서비스 `integrated_service.py`)
  - 프론트엔드 검색/에이전트 호출 서비스 (`searchService.ts`, `AgentToolTestPage.tsx`)

## 3. RAG 구현 상세
### 3.1 질의 처리
`process_user_query()`에서
1) 정규화 → 2) 언어 감지 → 3) 스펠링 교정(영어) → 4) 의도 분류(룰 기반) → 5) 형태소 분석(korean_nlp_service) → 6) 불용어 제거 → 7) Fulltext / Keyword 쿼리 생성 → 8) 임베딩 생성 → 9) 검색 전략 선택.

### 3.2 임베딩/LLM
- **임베딩**: Bedrock, Azure OpenAI, OpenAI 순차/폴백. 캐시 + in-flight Future 관리. Zero-padding으로 차원 강제 맞춤.
- **LLM**: 다중 provider 초기화와 폴백, 스트리밍 처리(astream) 구현.

### 3.3 검색 & 컨텍스트
- `rag_search_service.py`가 Hybrid 검색(semantic + keyword + fulltext), adaptive threshold, PPT 의도 부스팅, 중복 제거, 품질 검증, 리랭킹, 멀티턴 문맥 강화, 컨텍스트 토큰 컷 등을 단일 파일에서 처리.
- 결과: 후보 청크 + 사용된 청크 + context text + 통계(reranking 여부, 토큰 수, 프로바이더, 멀티턴 메타 등).

### 3.4 멀티모달
- 이미지/표/텍스트 기반 확장 고려 흔적(CLIP 검색 구조). 아직 표준화된 재랭킹/중복 제거 로직은 초기 단계.

### 3.5 멀티 에이전트
- LangGraph 워크플로우: 문서 분석 → 인사이트 추출 → 요약 → 프레젠테이션 구성 → 최종화.
- 현재 노드 로직은 목업 수준(실제 분석/LLM 호출 부분은 확장 필요). `integrated_service.py`에서 단일/멀티/hybrid 실행 모드 휴리스틱 결정.

## 4. 강점
1. 다중 벤더 지원(비용/안정성 폴백 구조)
2. Hybrid 검색으로 한국어/영어 혼합 대응
3. 멀티턴 문맥 고려(강화 재검색 로직)
4. Adaptive threshold & intent 기반 가중치 등 고급 튜닝
5. 임베딩 캐시 + in-flight 중복 제거로 성능 최적화
6. LangGraph 도입으로 향후 복잡 워크플로우 확장 가능성 확보
7. 프론트엔드 API 단순화(서비스 레이어로 유지보수 용이)

## 5. 주요 리스크 / 문제점
| 영역 | 이슈 | 영향 |
|------|------|------|
| 구조 | `rag_search_service.py` 단일 비대형(>1900 lines) | 유지보수·테스트 난이도 증가 |
| 품질 | 휴리스틱 랭킹/threshold 조정 | 성능 회귀 추적 어려움 |
| 임베딩 | Zero-padding 차원 강제 | 유사도 정확도 왜곡 가능 |
| 의도/언어 감지 | 단순 문자/룰 기반 | 오판 → 잘못된 전략 적용 |
| 에이전트 | LangGraph 노드 목업 수준 | 실제 가치·확장성 제한 |
| 오류 처리 | 임베딩 실패 시 dummy 벡터 채용 | 검색 랭킹 노이즈 유입 |
| 관측성 | 구조화 메트릭/추적 부족 | 성능/장애 원인 파악 지연 |
| 보안/로그 | 질의·메타데이터 과다 로깅 | 민감정보 유출 위험 |
| 테스트 | 검색/에이전트 품질 테스트 부재 | 회귀·튜닝 효과 검증 불가 |
| 비용 최적화 | Provider 선택이 단순 | 토큰 비용/지연 반영 미흡 |
| Context 토큰 | 추정 기반 4000 토큰 컷 | 실제 모델 한도/오차 발생 가능 |
| 멀티모달 | 부스팅/랭킹 일관성 미정 | 결과 품질 불안정 |

## 6. 개선 제안 (우선순위)
### 6.1 단기 (1–2주)
- `rag_search_service.py` 기능 분할: 분석/후보수집/랭킹/컨텍스트/통계 모듈.
- 평가 세트(`evaluation/queries.json`, `judgments.json`) + nDCG/Recall 계산 스크립트.
- 임베딩 실패 처리 수정: dummy 제거, 실패 청크 제외.
- 로그 마스킹(쿼리 50자 제한, 파일명 해시 처리), PII 필터.
- 언어 감지 개선: cld3 또는 fastText 경량 모델.
- DEV 목업 플래그 분리(`REACT_APP_USE_SEARCH_MOCK`).

### 6.2 중기 (3–6주)
- Cross-Encoder reranker(bge-reranker 등) 도입.
- Provider 선택 점수화(EMA latency + error rate + 품질 피드백).
- LangGraph 노드 실제화(각 단계별 RAG 호출 + 결과 저장).
- 임베딩 테이블/차원 표준화: 모델별 분리 또는 projection.
- OpenTelemetry + Prometheus 지표(embedding_latency_ms, rag_pipeline_ms 등).

### 6.3 장기
- 사용자 피드백 루프(선택/거절/편집 → 랭킹 학습). 
- Guardrail(프롬프트 인젝션 탐지, 민감정보 검출) 레이어.
- 증분 재인덱싱 파이프라인(Celery 주기적 업데이트).
- 멀티모달 세분화(텍스트/표/이미지 별 스코어 Late Fusion + 중복 제거).
- 온라인 A/B 실험 인프라로 파라미터 튜닝 효과 검증.

## 7. 즉시 적용 Top 5 액션
1. 서비스 파일 리팩터링 & 단위 테스트 추가.
2. 검색 품질 평가 자동화 도입.
3. 임베딩 차원/실패 처리 재설계.
4. 로그/보안/메트릭 관측성 강화.
5. LangGraph 워크플로우 실제 로직 연결.

## 8. 종합 결론
기능 범위는 넓고 RAG + 에이전트 시스템의 기반이 갖춰져 있으나, 구조화·객관적 품질 측정·관측성·안전성 측면 개선이 필요합니다. 위의 단계별 개선을 통해 유지보수성과 검색 품질을 동시에 향상할 수 있습니다.

## 9. 후속 작업 제안
- 리팩터링 계획 문서화(`RAG_Refactor_Plan.md`)
- 평가 데이터셋 샘플 정의 및 저장
- 메트릭 대시보드 요구사항 수립(Prometheus + Grafana)
- 에이전트 실제 분석 체인 PoC 구현

(문서 생성일: 2025-11-11)

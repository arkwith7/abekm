## OpenAPI 보강 및 SSE E2E 테스트 계획

### 1) OpenAPI 스키마 보강
- 목적: 프런트 타입 자동생성, 계약 회귀검증, 문서화 품질 확보
- 대상 엔드포인트(우선순위)
  - `/api/v1/chat/stream` (SSE 이벤트 타입 문서화: start/searching/search_complete/metadata/generating/content/complete/error)
  - `/api/v1/chat/message`, `/api/v1/chat/sessions/*`
  - `/api/v1/search/*` (hybrid/unified/context/vector/keyword/suggestions/analytics)
  - `/api/v1/multimodal`, `/api/v1/search/clip`
- 작업 항목
  - Pydantic 모델의 필드 설명/예시 추가
  - FastAPI 라우터에 response_model/summary/description 태그 정비
  - 스키마 내 enums/oneOf 등 활용해 가독성 향상
  - CI에서 OpenAPI JSON을 아티팩트로 보존

### 2) SSE E2E 테스트 계획
- 목적: 검색→메타→콘텐츠→완료 시퀀스 보장 및 회귀 테스트
- 환경: pytest + httpx.AsyncClient (실서버 또는 TestClient 기반), Redis/DB 통합 테스트 태그
- 시나리오
  1. 토큰 발급(모의 사용자)
  2. `/api/v1/chat/stream` POST 요청(SSE)
  3. 수신 이벤트 순서 검증
     - start → searching → search_complete(+chunks_count) → metadata(참조/통계) → generating → content(누적) → complete → [DONE]
  4. complete 이벤트 내 `references/context_info/rag_stats` 구조 검증
  5. 세션 저장 검증(`/api/v1/chat/sessions/{id}` 조회로 메시지/참조 복원)
- 실패/시간초과 처리
  - 이벤트 미수신 타임아웃(예: 15s) 시 실패
  - 중간 오류 이벤트(type=error) 발생 시 상세 로그 보존

### 3) 구현 메모
- 브라우저 환경에서는 fetch(EventStream) 사용, 테스트는 httpx로 chunked 응답 처리
- 토큰/401 재시도는 프런트 axios 인터셉터에서 처리하고, 테스트는 200 정상 흐름에 집중
- PPT 모드(코드펜스 제거/후처리) 분기 테스트는 별도 케이스로 분리



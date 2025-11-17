## WKMS-AWS 소스코드 기반 아키텍처 분석 (2025-11-08)

- 대상 디렉터리
  - 백엔드: `/home/admin/wkms-aws/backend`
  - 프런트엔드: `/home/admin/wkms-aws/frontend`
- 목적: 현재 구현 상태를 소스코드 기준으로 정리하고, 업그레이드/개선 포인트를 식별

---

## 1) 백엔드 개요

- 프레임워크: FastAPI
- 아키텍처: 라우터(`/app/api/v1/*`) + 서비스 레이어(`/app/services/*`) + 모델/스키마 + 의존성 주입
- 주요 기능
  - 통합 검색(하이브리드: 벡터+키워드+FTS, 멀티모달 CLIP)
  - RAG 챗봇(스트리밍 SSE, Redis + PostgreSQL 세션 동기화)
  - 문서 파이프라인(추출/전처리/청크/저장/검색 인덱스)
  - 권한 관리(RBAC, 컨테이너 계층 상속)
  - 대시보드/파일/컨테이너/권한 요청 API
- 데이터 계층: SQLAlchemy Async + Alembic(마이그레이션)
- 캐시/세션: Redis (채팅 세션/메시지 관리)
- 로깅: 회전 파일 + 콘솔, SQL 전용 로거 분리

### 1.1 진입점과 라우팅
- 진입점: `backend/app/main.py`
  - Lifespan(Startup/Shutdown)에서 모델/환경 로그 출력 및 로깅 레벨 조정
  - CORS, 정적 업로드 경로(`/uploads`) 마운트
  - 라우터 등록:
    - 인증/사용자: `app.api.v1.users`
    - 채팅: `app.api.v1.chat`
    - 검색/멀티모달: `app.api.v1.search`, `app.api.v1.multimodal_search`
    - 문서/파일: `app.api.v1.documents`, `app.api.v1.files`
    - 권한/권한요청/컨테이너/문서접근: `app.api.v1.permissions`, `permission_requests`, `containers`, `document_access`
    - 대시보드: `app.api.v1.dashboard`

### 1.2 검색 API
- 파일: `backend/app/api/v1/search.py`
- 특징
  - `/api/v1/search` 기본 검색(레거시 호환 포맷 반환)
  - `/api/v1/search/unified` 파일 단위 통합 결과
  - `/api/v1/search/context` RAG용 청크 단위 컨텍스트
  - `/api/v1/search/hybrid` 검색 타입별 튜닝
  - `/api/v1/search/vector | /keyword | /suggestions | /analytics`
  - CLIP 기반 멀티모달 `/api/v1/multimodal`, `/api/v1/search/clip`
- 서비스 의존
  - `app.services.search.search_service` (통합 검색)
  - `app.services.search.multimodal_search_service` (CLIP)
  - `app.services.search.search_service_v2`는 차기 구조 초안(스켈레톤)

### 1.3 챗봇/RAG
- 파일: `backend/app/api/v1/chat.py`
- 엔드포인트
  - `/api/v1/chat/stream`: SSE 스트리밍 기반 응답
  - `/api/v1/chat/message`: 동기 응답(완료 결과만 반환)
  - `/api/v1/chat/sessions`(목록/조회/삭제), `/archive`(보관)
  - `/api/v1/chat/vision`: 이미지 첨부 비스트리밍 분석
- 핵심 흐름
  - Redis 세션 생성/메시지 저장 + PostgreSQL 영구 보관(tb_chat_sessions/tb_chat_history) 동기화
  - `ai_agent_service.prepare_context_with_documents`로 선택 문서/히스토리 기반 RAG 컨텍스트 구성
  - SSE 이벤트 타입: start/searching/search_complete/metadata/generating/content/complete/error
  - PPT 의도 감지/포맷 보정 로직 포함(스트림/최종 저장 시 후처리)

### 1.4 권한 관리(RBAC)
- 파일: `backend/app/services/auth/permission_service.py`
- 개념
  - 사용자-컨테이너 권한(tb_user_permissions) + 컨테이너 계층 상속
  - 권한 계층: ADMIN > MANAGER > EDITOR > VIEWER (+ 조직/레거시 맵핑)
  - 시스템 관리자 판별, 접근 가능한 컨테이너, 업로드/다운로드/삭제 권한 체크
  - 권한 부여/취소 + 감사 로그(tb_permission_audit_log)
- 주의
  - 일부 개발 편의 코드(일부 관리자 true 반환, 'ADMIN001' 하드코딩)가 남아 있음 → 보안 강화를 위한 정비 필요

### 1.5 문서/파이프라인/스토리지
- 서비스 경로:
  - `app/services/document/processing|extraction|chunking|pipeline|storage/*`
  - Azure Document Intelligence(ocr), 이미지 임베딩(CLIP), 조합형 파이프라인 라우팅
  - 파일 스토리지/검색 인덱스/벡터 스토리지 어댑터 분리
- 마이그레이션/인덱스
  - Alembic 스크립트 + `migrations/*.sql`
  - 텍스트 FTS/pg_trgm, 멀티모달 확장 스키마 포함

---

## 2) 프런트엔드 개요

- 스택: React + TypeScript + React Router + Tailwind + PostCSS
- 구조
  - 라우팅: `src/App.tsx` (User/Manager/Admin 영역 Role 기반 보호)
  - 상태: `contexts/GlobalAppContext` (문서 선택, 페이지별 상태, 작업 컨텍스트, 워크플로우 등)
  - 서비스: `src/services/*` (auth/chat/search/document/permission/manager/admin 등)
  - 채팅: `pages/user/chat/hooks/useChat.ts` (SSE 스트리밍, 세션 로드/삭제/보관)
  - UI: Dashboard/Search/Chat/MyKnowledge/ContainerExplorer/Permission Management 등
- API 설정
  - `utils/apiConfig.ts` 에서 `REACT_APP_API_URL` 존재 시 직접, 없으면 dev 프록시(`/api`) 사용
  - 개발환경 프록시: `setupProxy.js`

### 2.1 라우팅/보호
- `ProtectedRoute`로 Role 검사 후 하위 라우팅 표시
- User/Manager/Admin 레이아웃과 각 페이지를 분리 배치

### 2.2 채팅 흐름(useChat)
- 세션 상태(new/loaded/continued) + 세션 ID 로테이션
- SSE 기반 `/api/v1/chat/stream` 호출
  - 수신 이벤트 타입에 따라 메시지 UI를 순차 갱신
  - 완료 시 references/context_info/rag_stats 메타 업데이트
- 이미지 포함 시 비스트리밍 Vision 경로(`/api/v1/chat/vision`)
- 세션 조회/삭제/보관 API 연동
- 선택 문서 상태는 Global Context와 이벤트로 상호 동기화

### 2.3 서비스 계층
- `chatService.ts`
  - JWT 인터셉터 포함 axios 인스턴스
  - 컨테이너/권한/채팅 등 편의 API
  - 참고: `sendMessage()`가 `/api/v1/chat` 경로를 호출하도록 남아 있으나, 실제 백엔드에는 `/chat/message` 또는 `/chat/stream`이 존재 → 경로 정합성 점검 필요

---

## 3) 프런트·백엔드 계약(API) 정합성 체크 포인트

- 채팅
  - 백엔드: `/api/v1/chat/stream`(SSE), `/api/v1/chat/message`(동기)
  - 프런트: `useChat`은 SSE를 직접 fetch로 사용. `chatService.sendMessage`는 `/api/v1/chat` 호출(불일치) → 미사용이거나 경로 정리가 필요
- 세션
  - 조회: `GET /api/v1/chat/sessions/{id}` (PostgreSQL 우선, Redis 폴백)
  - 삭제/보관: `DELETE /api/v1/chat/sessions/{id}`, `POST /api/v1/chat/sessions/{id}/archive`
- 검색
  - 통합/하이브리드/컨텍스트/멀티모달/CLIP 경로 모두 존재
  - 프런트 검색 서비스에서 실제 사용 경로 맵핑 확인 필요
- 권한/컨테이너
  - `GET /api/v1/permissions/*`, `GET /api/v1/containers` 존재

---

## 4) 운영/설정/로깅

- 로깅: 회전 파일 + SQL 전용 로그 파일, 레벨/포맷 환경설정
- CORS: 환경변수/설정 반영, 디버그 출력
- 업로드 정적 경로 마운트(`/uploads`)
- API Base URL
  - 프로덕션: `REACT_APP_API_URL` 사용
  - 개발: 프록시(`/api`) 경유

---

## 5) 리스크/기술부채/개선 제안

### 5.1 계약/호출 경로 정리
- `frontend/src/services/chatService.ts`의 `sendMessage()`는 `/api/v1/chat`로 POST 요청
  - 백엔드에는 `/api/v1/chat` 핸들러가 존재하지 않음(동기는 `/chat/message`, 스트림은 `/chat/stream`)
  - 조치: 실제 사용 위치 확인 후
    - 미사용이면 삭제
    - 사용할 경우 백엔드 경로(`/chat/message`)로 수정하고 타입 정의 동기화
- fetch와 axios 혼용
  - `useChat`에서 fetch 사용(토큰/401 처리 로직 직접 구현) vs axios 인터셉터
  - 조치: 공통 axios 인스턴스 사용으로 표준화(401 처리 일원화, 헤더 일관성)

### 5.2 권한 서비스 보안 강화
- 임시/개발 편의 코드 제거
  - 시스템 관리자 강제 True 반환, 하드코딩 사번('ADMIN001') 의존
  - 조치: 환경/역할 테이블 기반으로 엄격 판정, 하드코딩 제거
  - 감사 로그 기록 시 사용자 치환 로직도 실제 운영 기준으로 단순/명확화

### 5.3 검색 레이어 정리
- `search_service_v2` 스켈레톤 정리
  - 파일/청크/멀티모달 컨텍스트 API로 분리 목표 명확
  - 조치: V1과 공존 기간 동안 인터페이스/응답 스키마 호환 어댑터 제공, 전환 가이드 추가
  - 제안: 재랭킹/중복제거/가중치 조정 전략을 설정화(설정에서 TopK, Weight, Threshold 조정 가능)

### 5.4 SSE 안정성/UX
- 재연결/중복 방지/취소 플로우
  - `AbortController`로 취소는 처리됨
  - 조치: 네트워크 오류/타임아웃 시 백오프 재연결 옵션 추가, 중복 세션 이벤트 방지 가드 보강
  - PPT 모드 실시간 필터링은 존재하나, 프런트 렌더러에서 마크다운 안전성(sanitize) 검토 필요

### 5.5 프런트 상태/보안
- LocalStorage 저장 범위 최소화(문서/세션/사용자 PII 노출 방지)
  - 조치: 민감 정보 마스킹/단기 세션 스토리지 전환/만료 시점 동기화
  - 로그아웃 시 클린업은 구현됨 → 전역적으로 재검증
- `setupProxy.js` 위치 중복 의심(`src/setupProxy.js`와 루트 동시 존재 여부)
  - 조치: CRA 규칙에 맞게 단일화

### 5.6 테스트/가시성
- 이미 풍부한 스크립트/테스트 존재
  - 조치: SSE 스트리밍 E2E 테스트 추가(검색→메타→콘텐츠→완료 시퀀스 검증)
  - OpenAPI 스키마 동기화로 계약 테스트 가능하게 정비
  - 대시보드 API 사용 시 실제 카드/지표와 백엔드 계산 일치 여부 점검

### 5.7 문서화/운영
- FastAPI `/docs` 커스터마이징 및 운영용 리드미에 API 호출 예/샘플 응답 명시
- 마이그레이션 가이드(알림/롤백/데이터 백필) 정리
- 로깅 레벨/포맷을 환경(Profile)별 preset으로 단순화

---

## 6) 즉시 수행 가능한 작은 정비 목록

- 프런트 `chatService.sendMessage` 경로 정정 또는 삭제
- `useChat`의 fetch 호출을 공용 axios 인스턴스로 통일(401 인터셉터 재사용)
- PermissionService에서 개발 편의 반환 제거 및 실제 관리자 판별 로직 적용
- `search_service_v2` 설계 문서 추가 및 V1→V2 전환 계획 명시
- `setupProxy.js` 중복 여부를 확인하여 하나만 유지
- 프런트 마크다운 렌더러에 sanitize 옵션 적용 여부 점검
- OpenAPI 스키마 점검/보강(프런트 타입 생성에 활용 가능)

---

## 7) 2025-11-08 적용된 개선 작업 요약

- **프런트엔드**
  - `frontend/src/services/userService.ts`: 검색/하이브리드 검색에 인-플라이트 공유 + 5초 TTL 캐시 적용으로 동일 파라미터 중복 API 호출 제거.
- **백엔드**
  - `app/services/auth/permission_service.py`: 직접/상속 권한, 컨테이너 메타, 시스템 관리자 판정에 요청 범위 캐시 추가.
  - `app/services/search/query_pipeline.py` + `spell_checker.py`: 영어 질의 SpellChecker 기반 오탈자 교정 및 키워드/FTS 보강.
  - `app/services/core/embedding_service.py`: 임베딩 결과 TTL 캐시 & 배치 처리 캐시로 Azure 임베딩 호출 수 감축.
  - `app/services/chat/rag_search_service.py`: gpt-5-nano 호출 시 `max_output_tokens` 사용, 토큰 초과 시 청크 단위 동적 축소.
  - `app/services/search/search_service.py`: 컨테이너 메타 조회 TTL 캐시 및 일괄 조회로 DB 반복 호출 최소화.
  - `backend/requirements.txt`: `pyspellchecker` 추가(오탈자 교정용).

- **문서 업데이트**
  - 본 섹션을 포함해 `01.docs`에 개선 내역 기록.

---

## 8) 파일 레퍼런스

- 백엔드
  - `backend/app/main.py` (FastAPI 앱, 라우터/로깅/CORS/정적 경로)
  - `backend/app/api/v1/search.py` (통합 검색/멀티모달/CLIP)
  - `backend/app/api/v1/chat.py` (SSE 스트리밍/세션/비전)
  - `backend/app/services/auth/permission_service.py` (권한/감사/상속)
  - `backend/app/services/search/search_service_v2.py` (차기 구조 스켈레톤)
- 프런트엔드
  - `frontend/src/App.tsx` (라우팅/Role 보호)
  - `frontend/src/pages/user/chat/hooks/useChat.ts` (SSE 채팅)
  - `frontend/src/services/chatService.ts` (axios + JWT, 일부 경로 정합성 점검 필요)
  - `frontend/src/contexts/GlobalAppContext.tsx` (전역 상태/문서 선택/워크플로우)
  - `frontend/src/utils/apiConfig.ts` (API Base URL 결정)

--- 

본 문서는 소스코드 기준으로 구현 상태를 요약했습니다. 개선 제안 중 “계약/호출 경로 정리, 권한 서비스 보안 강화, 검색 레이어 정리, SSE 안정성, 프런트 상태/보안, 테스트/문서화”는 단기/중기로 나누어 계획 수립을 권장합니다.



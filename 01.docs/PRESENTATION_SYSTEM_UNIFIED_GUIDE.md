# Presentation Generation System — Unified Guide

작성일: 2025-11-13
상태: 단일 소스 문서 (SSoT)

이 문서는 PPT 생성 시스템의 단일 소스 문서입니다. 아래 4개 문서의 내용을 병합·정리하고 최신 UX 방향과 API/구조를 반영했습니다.
- 01.docs/PPT_GENERATION_ARCHITECTURE.md
- 01.docs/PPT_IMPLEMENTATION_STATUS_REPORT.md
- 01.docs/PPT_IMPLEMENTATION_COMPLETE.md
- 01.docs/PROMPT_MANAGEMENT_IMPROVEMENT.md

---

## 간단 개요

- 목표: AI 채팅 결과를 마크다운 → StructuredOutline(JSON) → HTML 프리뷰 → PPTX 파일로 생성/다운로드
- 설계 원칙: 모듈 독립 배포, 구조화 데이터 우선(JSON), 설정 기반 통합, HTML+PPTX 이중 출력
- 구성: Frontend(React) · Backend(FastAPI) · Office Generator(Node + PptxGenJS) · LLM(Azure OpenAI)

---

## 아키텍처와 데이터 흐름

1) 사용자 입력(채팅) → LLM이 마크다운 응답 생성
2) Backend가 마크다운을 LLM으로 구조화하여 StructuredOutline(JSON) 생성
3) StructuredOutline을 바탕으로 LLM이 인터랙티브 HTML 생성(프리뷰/경량 편집)
4) 저장: HTML, Outline(JSON)
5) PPTX 필요 시 Backend가 Office Generator(Node)로 StructuredOutline 전달 → PPTX 생성/저장
6) 프론트엔드에 HTML 프리뷰 링크와 PPTX 다운로드 링크 제공

주요 이점
- HTML 파싱 회피: JSON → PPTX 직접 변환으로 안정성 향상
- 템플릿 기반 확장: 신규 슬라이드 레이아웃 추가만으로 디자인 확장 가능

---

## 데이터 모델 (요약)

StructuredOutline
- title: string
- theme: 'business' 등
- slides: Array<StructuredSlide>

StructuredSlide
- title: string
- content?: string
- layout: 'title' | 'title-and-bullets' | 'two-column-grid' | 'divider' | 'image-placeholder'
- visual_elements?: { bullets?: string[]; icons?: string[]; grid?: { cols: number; items: { title?: string; description?: string; value?: string }[] }, image?: { url?: string; caption?: string } }

파일 저장 디렉토리(예)
- data/presentations/html/*.html
- data/presentations/outline/*.json
- data/presentations/pptx/*.pptx

---

## 백엔드 API (요약)

1) POST /api/v1/agent/presentation/generate
- 입력: { session_id, message_id, title_override?, markdown?, style?, output_format: 'html' | 'pptx' | 'both', options?: { max_slides?, audience?, theme? } }
- 동작: Markdown → Outline(JSON) → HTML 생성 및 저장. output_format=both/pptx 인 경우 PPTX도 생성
- 응답: { success, html_url?, outline_url, pptx_url?, metadata }

2) POST /api/v1/agent/presentation/generate-pptx
- 입력: outline_filename, theme?
- 동작: 저장된 Outline을 읽어 Office Generator 호출 → PPTX 생성/저장
- 응답: { success, pptx_url, filename, size_bytes, slide_count? }

3) GET /api/v1/agent/presentation/download/{filename}
- 동작: PPTX 파일 다운로드

4) GET /api/v1/agent/presentation/view/{filename}
- 동작: 저장된 HTML 프리뷰 반환

비고: 정확한 필드/엔드포인트 경로는 백엔드 소스의 최신 정의를 기준으로 하며, 상기 요약은 현재 구현과 합치합니다.

---

## Office Generator(Node) 개요

- 주요 파일
  - src/routes/pptx.routes.js: POST /api/pptx/convert, GET /api/pptx/health
  - src/converters/structured-to-pptx.js: StructuredOutline → PPTX Buffer 변환
  - src/templates/*: Title, TitleAndBullets, TwoColumnGrid, Divider, ImagePlaceholder 템플릿
  - src/utils/icons/icon-fetcher.js: Lucide 아이콘 이름 → Unicode/emoji 매핑

요청 페이로드(요약)
```
{
  "outlineJson": { ...StructuredOutline... },
  "options": { "theme": "business" }
}
```

응답: PPTX 바이너리 (Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation)

---

## 프롬프트 관리(외부화)

- 위치: backend/prompts/presentation/*.txt
- 로더: backend/app/utils/prompt_loader.py (캐싱/리로드 지원)
- 적용: content_structurer.py, html_generator.py가 파일에서 프롬프트 로드
- 이점: 코드와 프롬프트 분리, 핫스왑 가능, Git 이력 관리

---

## Frontend UX — 하이브리드 전략(RBAC+에이전트 셀렉터)

배경: 엔터프라이즈 환경에서 역할 기반 접근 제어(RBAC)와 가시성/발견성 간 균형이 중요합니다. 합의된 전략은 다음과 같습니다.

1) 사이드바 메뉴(권한 기반)
- Agent Registry를 기준으로 사용자 역할/권한에 따라 기능을 노출
- 예: “프레젠테이션 생성” 패널은 ppt:generate 권한에만 표시

2) 인-채팅 에이전트 선택기(선택적)
- 채팅 입력창 근처에서 작업 대상 에이전트를 빠르게 전환
- 선택된 에이전트의 권한/옵션을 상단 패널에서 자동 반영

3) 일관된 아티팩트 취급
- 생성 결과(HTML/PPTX) 링크는 메시지 버블 내 빠른 액션 + 측면 다운로드 섹션 양쪽에 노출

권장 컴포넌트(예)
- PresentationPanel.tsx: 스타일/옵션 선택, 생성 요청 트리거
- PresentationPreview.tsx: iframe HTML 프리뷰, 키보드 내비게이션
- DownloadLink.tsx: 아티팩트 다운로드/복구

---

## Agent Registry 제안(계약 초안)

단일 소스의 에이전트/기능 레지스트리로 RBAC와 UI 노출을 통합 관리합니다.

리소스 식별자
- agentId: 'presentation'
- actions: ['generate', 'preview', 'download'] 등

권한 스키마(예)
```
type Permission = {
  resource: string;   // 'agent:presentation'
  action: string;     // 'generate' | 'download' ...
  effect: 'allow' | 'deny';
}

type AgentDescriptor = {
  id: 'presentation';
  displayName: 'PPT 생성';
  description?: string;
  routes: {
    generate: '/api/v1/agent/presentation/generate';
    download: '/api/v1/agent/presentation/download/{filename}';
  };
  ui: {
    sidebar: true;          // 사이드바 노출
    inChatSelector: true;   // 인-채팅 선택기 노출
  };
  requiredPermissions: Permission[]; // 최소 권한
}
```

레지스트리 저장 위치는 조직 표준에 따르되, FE/BE 공용 스키마를 공유하는 것을 권장합니다.

---

## 테스트와 검증(요약)

- Node Office Generator: test-pptx-convert.sh + test-samples/*.json으로 로컬 변환 검증
- Backend Prompt Loader: backend/test_prompt_loader.py로 프롬프트 로드/캐시/리로드 테스트 완료
- E2E(제안): 세션/메시지 기반 통합 테스트를 추가하여 generate(both) 경로의 성공을 검증

---

## 마이그레이션/이관 노트 및 폐기 문서

이 문서로 아래 문서는 더 이상 업데이트되지 않습니다. 최신 정보는 본 문서를 참조하세요.
- PPT_GENERATION_ARCHITECTURE.md
- PPT_IMPLEMENTATION_STATUS_REPORT.md
- PPT_IMPLEMENTATION_COMPLETE.md
- PROMPT_MANAGEMENT_IMPROVEMENT.md

각 문서 상단에 폐기 배너가 추가되었습니다.

---

## 변경 이력

- 2025-11-13: 초기 통합본 생성. 하이브리드 UX와 Agent Registry 제안 포함. 백엔드/오피스 제너레이터 엔드포인트 요약 반영.

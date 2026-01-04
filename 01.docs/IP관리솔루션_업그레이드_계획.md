# IPBridge → IP 관리 솔루션 전환 프로젝트 (집중 개발 계획)
## IP 포트폴리오 및 선행기술 조사 에이전트 구축

---

**작성일**: 2026년 1월 3일  
**프로젝트명**: IPBridge IP Core Upgrade  
**목표**: "지식 컨테이너"를 "IP 포트폴리오"로 고도화하고, "선행기술 조사"에 특화된 IP Copilot 구축  
**범위**: IP 포트폴리오, IP Copilot (통합), 선행기술 조사 Agent, IP 대시보드

---

## 📋 목차

1. [개요 및 집중 목표](#1-개요-및-집중-목표)
2. [IP 포트폴리오 (구 지식 컨테이너) 개편](#2-ip-포트폴리오-구-지식-컨테이너-개편)
3. [IP Copilot 및 선행기술 조사 Agent](#3-ip-copilot-및-선행기술-조사-agent)
4. [IP 인사이트 대시보드 개편](#4-ip-인사이트-대시보드-개편)
5. [기술 아키텍처 및 DB 설계](#5-기술-아키텍처-및-db-설계)
6. [단계별 실행 계획 (12주)](#6-단계별-실행-계획-12주)

---

## 0. 구현 진행 현황 (프론트 1차 반영)

아래 항목은 계획이 아닌 **코드에 실제 반영되어 검증(테스트/빌드)까지 완료**된 상태입니다.

- **좌측 메뉴/라우팅 IP 전환**: IP 포트폴리오 / IP Copilot / 선행기술 조사 / 대화 이력
- **라우트**: `/user/ip-portfolio`, `/user/ip-copilot`, `/user/prior-art` (기존 화면 재사용 + alias)
- **선행기술 조사 진입점**: 전용 페이지에서 기본 도구를 `prior-art`로 고정해 백엔드 워크플로우가 일관되게 트리거됨
- **세션 복원 정책**: 채팅 세션 localStorage 백업/복원이 `/user/ip-copilot`, `/user/prior-art`에서도 동일하게 동작
- **검증**: 프론트 단위 테스트 추가 및 `npm test`, `npm run build`로 동작 확인

---

## 1. 개요 및 집중 목표

기존의 광범위한 IP 관리 기능 중, 가장 핵심이 되는 **자산 관리(Portfolio)**와 **조사 분석(Prior Art Search)** 기능에 집중하여 실질적인 가치를 빠르게 창출하는 것을 목표로 합니다.

### 🎯 3대 핵심 과제

1.  **지식 컨테이너 → IP 포트폴리오 전환**
    *   단순 폴더 구조를 **IPC(국제특허분류)/CPC 기반의 기술 분류 체계**로 전환
    *   특허 문서에 특화된 메타데이터 관리 및 시각화

2.  **지식검색 + AI Agents → IP Copilot 통합**
    *   분리된 검색과 에이전트 화면을 하나로 통합하여 **대화형 검색/분석 환경** 제공
    *   단순 RAG를 넘어선 **목적 지향적 에이전트 워크플로우** 구현

3.  **선행기술 조사 (Prior Art Search) Agent 심화 개발**
    *   발명 아이디어 입력 시 **KIPRIS 실시간 검색**과 **내부 DB 검색**을 병행
    *   **X-Y 매트릭스** 자동 생성 및 유사도 기반 회피 설계 제안

---

## 2. IP 포트폴리오 (구 지식 컨테이너) 개편

기존의 `Knowledge Container`는 조직/부서 중심의 파일 저장소였습니다. 이를 특허 관리의 표준인 기술 분류 체계로 재편합니다.

### 2.1 구조적 변화

| 구분 | 기존 (Knowledge Container) | 변경 (IP Portfolio) |
| :--- | :--- | :--- |
| **분류 기준** | 부서/프로젝트 (예: 인사팀, 프로젝트A) | **기술 분류 (IPC/CPC)** (예: H04W, G06N) |
| **계층 구조** | 폴더 깊이 제한 없음 (임의 생성) | **표준 계층 구조** (섹션-클래스-서브클래스-그룹) |
| **문서 속성** | 파일명, 크기, 업로더 | **출원번호, 출원일, 출원인, 법적상태, 청구항** |
| **보기 방식** | 리스트/그리드 뷰 | **트리 뷰 (좌측) + 특허 카드/리스트 (우측)** |

### 2.2 주요 기능 상세

#### 🌳 IPC/CPC 기술 분류 트리
*   **표준 분류 탑재**: IPC 8개 섹션 및 하위 클래스 DB 구축
*   **커스텀 매핑**: 기업 내부 분류(예: "차세대 배터리")를 특정 IPC 코드(H01M)와 매핑하여 가상 폴더로 제공
*   **자동 분류**: 특허 문서 업로드 시, 텍스트 분석을 통해 적절한 IPC 코드를 추천하고 해당 폴더로 자동 분류

#### 📄 특허 문서 카드 (Patent Card)
*   기존 파일 아이콘 대신 특허 정보를 요약한 카드 UI 제공
*   **표시 정보**:
    *   대표 도면 (썸네일)
    *   발명의 명칭 (한글/영문)
    *   출원번호 / 등록번호
    *   현재 법적 상태 (등록, 공개, 거절, 소멸 등 - 색상 코딩)
    *   핵심 키워드 태그 (AI 추출)

---

## 3. IP Copilot 및 선행기술 조사 Agent

"검색" 메뉴와 "AI Agents" 메뉴를 **IP Copilot**으로 통합합니다. 사용자는 채팅 인터페이스에서 자연어로 요청하며, 에이전트는 필요에 따라 검색, 분석, 보고서 생성을 수행합니다.

### 3.1 통합 인터페이스 (IP Copilot)

*   **단일 진입점**: 모든 IP 관련 작업(검색, 분석, 조사)을 하나의 채팅창에서 시작
*   **모드 전환**:
    *   **General Mode**: 일반적인 RAG 기반 질의응답 (기존 기능)
    *   **Analyst Mode**: 선행기술 조사, 특허 분석 등 전문 작업 수행 (신규)

### 3.2 🕵️‍♂️ 선행기술 조사 (Prior Art Search) Agent 상세

이 프로젝트의 핵심 엔진입니다. 사용자의 아이디어가 기존 특허와 얼마나 유사한지 분석합니다.

#### 🔄 처리 프로세스 (Workflow)

1.  **발명 아이디어 입력 & 파싱**
    *   사용자 입력: "스마트폰 배터리 수명을 늘리기 위한 AI 기반 충전 제어 방법"
    *   Agent 동작: 핵심 구성요소(Component)와 기능(Function) 추출
        *   *예: [구성: AI 모델, 충전 회로], [기능: 배터리 상태 예측, 충전 속도 조절]*

2.  **검색 전략 수립 (Query Formulation)**
    *   **키워드 확장**: "AI" → "인공지능", "머신러닝", "딥러닝", "신경망"
    *   **IPC 한정**: 배터리 제어 관련 IPC (H01M 10/44, H02J 7/00) 자동 식별
    *   **검색식 생성**: `(AI OR 인공지능) AND (충전 제어) * IPC=[H01M, H02J]`

3.  **하이브리드 검색 실행**
    *   **외부 검색 (KIPRIS API)**: 최신 한국 특허 실시간 검색
    *   **내부 검색 (Vector DB)**: 기 보유 특허 및 기술 문서 검색 (의미 기반)

4.  **심층 분석 & X-Y 매트릭스 생성**
    *   검색된 상위 10~20개 특허에 대해 상세 분석 수행
    *   **유사도 스코어링**: SBERT(Sentence-BERT) 활용, 문장 단위 유사도 계산
    *   **X-Y 매트릭스 구성**:
        *   X축: 사용자 발명의 핵심 구성요소
        *   Y축: 검색된 선행 문헌
        *   Cell: 해당 구성요소의 개시 여부 (O/X/△) 및 관련 문장 발췌

5.  **결과 리포팅**
    *   **종합 의견**: 신규성/진보성 확보 가능성 (High/Medium/Low)
    *   **회피 설계 제안**: "선행기술 A는 XX 방식을 사용하므로, YY 방식을 도입하여 차별화 필요"

---

## 4. IP 인사이트 대시보드 개편

기존의 일반적인 시스템 현황 대시보드를 IP 관리자 및 연구자를 위한 전용 대시보드로 변경합니다.

### 4.1 주요 위젯 구성

1.  **IP 자산 현황 (Portfolio Summary)**
    *   총 보유 특허 수 (등록/출원/해외)
    *   기술 분야별(IPC) 분포 (도넛 차트)
    *   최근 1년간 출원 추이 (라인 차트)

2.  **선행기술 조사 현황 (Prior Art Status)**
    *   최근 수행한 조사 프로젝트 목록
    *   진행 중인 조사 상태 (검색중, 분석중, 완료)
    *   "새로운 조사 시작하기" 퀵 버튼

3.  **관심 기술 트렌드 (Tech Watch)**
    *   설정된 관심 IPC 분야의 최신 등록 특허 (KIPRIS 연동)
    *   경쟁사 최신 공개 특허 알림

---

## 5. 기술 아키텍처 및 DB 설계

### 5.1 Backend (FastAPI)

*   **Agent Orchestrator**: LangGraph 또는 자체 State Machine을 도입하여 복잡한 조사 워크플로우 제어
*   **KIPRIS Client**: `app/clients/kipris.py` 고도화 (검색, 상세조회, 공보다운로드)
*   **Analysis Engine**: `sentence-transformers`를 활용한 로컬 임베딩 및 유사도 계산 모듈

### 5.2 Database (PostgreSQL)

#### 신규 테이블

```sql
-- 1. 기술 분류 체계
CREATE TABLE tb_ipc_code (
    code VARCHAR(20) PRIMARY KEY, -- H04W
    level VARCHAR(10),            -- SECTION, CLASS, SUBCLASS
    description_ko TEXT,
    parent_code VARCHAR(20)
);

-- 2. 특허 메타데이터 (Documents 테이블 확장 또는 1:1 매핑)
CREATE TABLE tb_patent_metadata (
    document_id INT REFERENCES tb_documents(id),
    application_number VARCHAR(50), -- 출원번호
    ipc_codes TEXT[],               -- IPC 코드 배열
    applicant VARCHAR(200),         -- 출원인
    status VARCHAR(50),             -- 법적상태
    abstract TEXT,                  -- 요약
    claims TEXT                     -- 청구항 전문
);

-- 3. 선행기술 조사 프로젝트
CREATE TABLE tb_prior_art_search (
    id SERIAL PRIMARY KEY,
    user_id INT,
    query_text TEXT,                -- 사용자 입력 발명 내용
    search_strategy JSONB,          -- 사용된 검색식 및 키워드
    status VARCHAR(20),             -- PENDING, PROCESSING, COMPLETED
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. 조사 결과 (X-Y 매트릭스 데이터)
CREATE TABLE tb_search_results (
    search_id INT REFERENCES tb_prior_art_search(id),
    ref_document_id INT,            -- 내부 문서일 경우
    external_metadata JSONB,        -- 외부(KIPRIS) 문서일 경우
    similarity_score FLOAT,
    component_analysis JSONB        -- X-Y 매트릭스 분석 결과
);
```

---

## 6. 단계별 실행 계획 (12주)

선택과 집중을 통해 3개월 내 핵심 기능을 완성합니다.

### Phase 1: IP 포트폴리오 기반 구축 (4주)
*   **1주**: IPC 코드 DB 구축 및 `tb_patent_metadata` 설계
*   **2주**: KIPRIS API 연동 고도화 (특허 상세 정보 파싱 및 DB 저장)
*   **3주**: Frontend - IP 포트폴리오 트리 뷰 및 리스트 UI 개발
*   **4주**: 기존 문서의 메타데이터 추출 및 자동 분류 로직 적용

### Phase 2: 선행기술 조사 Agent 개발 (6주)
*   **5주**: Agent 워크플로우 설계 (입력 → 키워드 → 검색식)
    *   ✅ **완료 (2026-01-04)**: IPC 권한 관리 백엔드 API 구현
        - 관리자 IPC 권한 CRUD API 8개 엔드포인트 구현
        - `/api/v1/admin/ipc-permissions` 라우터 완성
        - 백엔드 API 테스트 8개 작성 (5개 통과, 3개 수정 필요)
        - 2단계 권한 체계 확정: 사용자/시스템관리자
*   **6주**: KIPRIS 검색 연동 및 결과 파싱 모듈 개발
*   **7주**: 유사도 분석 엔진 (SBERT) 및 X-Y 매트릭스 생성 로직 구현
*   **8주**: Frontend - IP Copilot 채팅 인터페이스 통합 (모드 전환)
*   **9주**: Frontend - 조사 결과 보고서 및 매트릭스 시각화 UI
*   **10주**: 통합 테스트 및 튜닝 (검색 정확도 개선)

### Phase 3: 대시보드 및 안정화 (2주)
*   **11주**: IP 인사이트 대시보드 위젯 개발 및 연동
*   **12주**: 전체 시스템 통합 테스트, 버그 수정, 배포

---

**문의**: 성균관대학교 기술경영대학원 Smart Factory Research Group  
**작성일**: 2026년 1월 3일  
**버전**: 2.0 (Focused Plan)

---

## 작업 일지

### 2026-01-04: IPC 권한 관리 백엔드 완료

#### 구현 완료 사항

**1. 백엔드 API 구현**
- [admin_ipc_permissions.py](../backend/app/api/v1/admin_ipc_permissions.py): 관리자 전용 IPC 권한 관리 라우터
  - 8개 엔드포인트 구현: 목록조회, 생성, 수정, 삭제, 사용자별조회, 벌크생성, 인증테스트
  - `require_admin` 의존성 주입으로 시스템 관리자만 접근 가능
  - 필터링/페이징 지원 (부서코드, 사용자명, 권한명)
- [ipc_permission_service.py](../backend/app/services/auth/ipc_permission_service.py): IPC 권한 비즈니스 로직 서비스 레이어

**2. 테스트 작성 및 환경 설정**
- [test_admin_ipc_permissions.py](../backend/tests/api/test_admin_ipc_permissions.py): 8개 테스트 케이스 작성
  - 테스트 결과 (2026-01-04 09:13):
    - ✅ **통과 (5/8)**: `test_list_empty`, `test_update_permission`, `test_delete_permission`, `test_get_user_permissions`, `test_bulk_create`
    - ❌ **실패 (2/8)**: `test_create_success`, `test_create_duplicate_returns_409`
    - ⚠️ **에러 (1/8)**: `test_unauthorized_access`
- [conftest.py](../backend/tests/conftest.py): pytest 환경 설정 대규모 리팩토링
  - Docker 컨테이너 Python path 추가 (`sys.path.insert(0, '/app')`)
  - DATABASE_URL 비밀번호 마스킹 방지 헬퍼 함수 추가
  - httpx AsyncClient transport 방식 수정 (0.23+ 호환)
  - simple 테스트 모드 도입 (개발 DB 직접 사용, 격리 없음)

**3. 버그 수정**
- TbUser → User import 수정 (6곳)
- connect_args None → {} 수정
- pgvector extension 설치 스크립트 추가

#### 다음 작업 (우선순위)

**1. 테스트 수정 및 안정화 (최우선)**
- [ ] 실패한 3개 테스트 디버깅 및 수정
  - `test_create_success`: API 응답 스펙 검증
  - `test_create_duplicate_returns_409`: 중복 처리 로직 확인
  - `test_unauthorized_access`: 인증 fixture 수정
- [ ] 전체 테스트 통과 확인
- [ ] Swagger UI에서 실제 API 동작 검증 (http://localhost:8000/docs)

**2. 프론트엔드 관리자 UI 개발**
- [ ] `/admin/ipc-permissions` 페이지 구현
  - IPC 권한 목록 테이블 (필터링/페이징)
  - 권한 생성/수정/삭제 모달
  - 사용자별 권한 조회 및 벌크 생성 기능
- [ ] 백엔드 API와 통합 테스트

**3. 문서화**
- [ ] API 명세서 작성 (엔드포인트별 request/response)
- [ ] 관리자 사용자 가이드 작성

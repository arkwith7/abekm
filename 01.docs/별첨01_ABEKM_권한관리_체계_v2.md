# 별첨01. ABEKM 권한 관리 체계

## 1. 개요

### 1.1 문서 목적

본 문서는 ABEKM(AI Based Enterprise Knowledge Management)의 권한 관리 체계를 정의합니다. 지식맵 구조에 따른 계층적 권한 관리와 역할 기반 접근 제어(RBAC) 시스템을 상세히 기술합니다.

### 1.2 권한 관리 범위

- **지식 컨테이너**: 계층적 구조의 지식 저장소 권한 관리
- **문서 접근 권한**: 파일별 세분화된 접근 권한 제어
- **역할 기반 권한**: 사용자 역할에 따른 체계적 권한 할당
- **SAP 연동 권한**: 조직도 기반 자동 권한 동기화

## 2. 지식맵 계층 구조

### 2.1 지식맵 계층 정의

```
🏢 기업 조직 (ROOT - COMPANY 레벨)
├── 📁 CEO직속 (DIVISION 레벨)
│   ├── 📁 인사전략팀 (DEPARTMENT 레벨)
│   │   ├── 📁 채용팀 (TEAM 레벨)
│   │   │   ├── 📄 채용가이드.pdf (DOCUMENT 레벨)
│   │   │   ├── 📄 면접평가표.xlsx (DOCUMENT 레벨)
│   │   │   └── 📄 신입사원교육.pptx (DOCUMENT 레벨)
│   │   └── 📁 교육팀
│   └── 📁 기확팀
├── 📁 클라우드사업본부
│   ├── 📁 클라우드서비스팀
│   └── 📁 MS서비스팀
└── 📁 CTI사업본부
    ├── 📁 인프라컨설팅팀
    └── 📁 Biz운영1팀
```

### 2.2 권한 상속 메커니즘

- **하향 상속**: 상위 컨테이너 권한이 하위로 선택적 상속
- **직접 권한**: 특정 컨테이너/문서에 직접 부여된 권한이 최우선
- **역할 기반**: 사용자 역할에 따른 기본 권한 자동 부여

## 3. 권한 관리 데이터베이스 설계

### 3.1 핵심 권한 관리 테이블

#### 3.1.1 지식 컨테이너 테이블 (tb_knowledge_containers)

```sql
CREATE TABLE tb_knowledge_containers (
    container_id VARCHAR(50) PRIMARY KEY,
    container_name VARCHAR(200) NOT NULL,
    parent_container_id VARCHAR(50) REFERENCES tb_knowledge_containers(container_id),
    sap_org_code VARCHAR(20),
    container_type VARCHAR(20) NOT NULL DEFAULT 'DEPARTMENT',
    hierarchy_level INTEGER NOT NULL DEFAULT 1,
    hierarchy_path VARCHAR(500),
    is_active CHAR(1) NOT NULL DEFAULT 'Y',
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3.1.2 컨테이너별 권한 테이블 (tb_container_permissions)

```sql
CREATE TABLE tb_container_permissions (
    permission_id SERIAL PRIMARY KEY,
    container_id VARCHAR(50) NOT NULL REFERENCES tb_knowledge_containers(container_id),
    user_id VARCHAR(50) NOT NULL,
    permission_type VARCHAR(20) NOT NULL, -- READ, WRITE, DELETE, ADMIN
    is_inherited CHAR(1) NOT NULL DEFAULT 'N',
    granted_by VARCHAR(50),
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,
    is_active CHAR(1) NOT NULL DEFAULT 'Y',
    UNIQUE(container_id, user_id, permission_type)
);
```

#### 3.1.3 사용자 역할 테이블 (tb_user_roles)

```sql
CREATE TABLE tb_user_roles (
    role_assignment_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    role_id VARCHAR(20) NOT NULL, -- ADMIN, MANAGER, EDITOR, VIEWER
    container_id VARCHAR(50) REFERENCES tb_knowledge_containers(container_id),
    assigned_by VARCHAR(50),
    assigned_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active CHAR(1) NOT NULL DEFAULT 'Y',
    UNIQUE(user_id, role_id, container_id)
);
```

#### 3.1.4 역할별 권한 정의 테이블 (tb_role_permissions)

```sql
CREATE TABLE tb_role_permissions (
    role_permission_id SERIAL PRIMARY KEY,
    role_id VARCHAR(20) NOT NULL,
    permission_type VARCHAR(20) NOT NULL,
    resource_type VARCHAR(20) NOT NULL, -- DOCUMENT, CONTAINER, SEARCH, CHAT
    is_default CHAR(1) NOT NULL DEFAULT 'Y',
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## 4. 지식생성자 권한 관리 시나리오

### 4.1 파일 업로드 시 접근 범위 설정

#### 4.1.1 접근 범위 옵션

| 설정 옵션     | 접근 범위      | 자동 권한 부여 대상 | 사용 시나리오      |
| --------- | ---------- | ----------- | ------------ |
| **나만 보기** | PRIVATE    | 본인만         | 개인 작업 문서, 초안 |
| **팀 공유**  | TEAM       | 같은 팀 전체     | 팀 내부 업무 매뉴얼  |
| **부서 공유** | DEPARTMENT | 같은 부서 전체    | 부서 정책 문서     |
| **본부 공유** | DIVISION   | 같은 본부 전체    | 본부 차원 가이드라인  |
| **전사 공유** | COMPANY    | 전 직원        | 전사 공통 양식, 규정 |

#### 4.1.2 세분화된 권한 제어

- **읽기**: 문서 조회, 검색 결과 포함
- **다운로드**: 파일 다운로드 허용
- **댓글**: 문서에 댓글 작성 허용
- **외부공유**: 시스템 외부로 공유 허용
- **권한 만료**: 일정 기간 후 자동 권한 회수

### 4.2 지식생성자 권한 관리 UI 예시

```
┌─────────────────────────────────────────────────┐
│  📤 파일 업로드 - 접근 권한 설정                    │
├─────────────────────────────────────────────────┤
│  파일: 채용가이드.pdf                              │
│  카테고리: 인사 > 채용                             │
│                                                 │
│  🔒 접근 범위 설정:                                │
│  ○ 나만 보기 (비공개)                              │
│  ● 팀 공유 (채용팀)                 👥 5명         │
│  ○ 부서 공유 (인사팀)               👥 23명        │
│  ○ 본부 공유 (경영지원본부)         👥 89명        │
│  ○ 전사 공유 (전체 직원)            👥 1,247명     │
│                                                 │
│  🎯 세부 권한 설정:                                │
│  ✅ 읽기    ✅ 다운로드    ❌ 댓글    ❌ 외부공유     │
│                                                 │
│  👤 특정 사용자 추가:                              │
│  [검색: 이름 또는 사번]              [+ 추가]       │
│                                                 │
│  ⏰ 권한 만료 설정:                                │
│  ○ 무제한    ● 1년    ○ 사용자 지정: [____]       │
│                                                 │
│         [취소]              [업로드 및 권한설정]   │
└─────────────────────────────────────────────────┘
```

## 5. 지식관리자 권한 관리 시나리오

### 5.1 지식관리자 역할별 권한 범위

| 역할           | 권한 범위 | 주요 기능                  | 관리 대상          |
| ------------ | ----- | ---------------------- | -------------- |
| **팀 지식관리자**  | 팀 레벨  | 팀 내 문서 품질 관리, 분류 체계 관리 | 소속 팀 컨테이너      |
| **부서 지식관리자** | 부서 레벨 | 부서 지식 정책 수립, 접근 권한 승인  | 소속 부서 + 하위 팀들  |
| **본부 지식관리자** | 본부 레벨 | 본부 지식 전략 수립, 부서간 협업 관리 | 소속 본부 + 하위 부서들 |
| **전사 지식관리자** | 전사 레벨 | 전사 지식 거버넌스, 보안 정책 수립   | 전체 시스템         |

### 5.2 지식관리자 대시보드 UI 예시

```
┌───────────────────────────────────────────────────────────────┐
│  🏗️ 인사팀 지식컨테이너 관리 - 김지식 (부서 지식관리자)              │
├───────────────────────────────────────────────────────────────┤
│  📊 컨테이너 현황:                                              │
│  총 문서: 1,247개  활성 사용자: 67명  대기 권한 요청: 8건         │
│                                                               │
│  📁 하위 컨테이너 구조:                                         │
│  ├── 📁 채용팀 (문서 324개, 사용자 12명)    [관리] [권한보기]     │
│  ├── 📁 교육팀 (문서 198개, 사용자 8명)     [관리] [권한보기]     │
│  ├── 📁 평가팀 (문서 156개, 사용자 15명)    [관리] [권한보기]     │
│  └── 📁 복리후생팀 (문서 89개, 사용자 7명)   [관리] [권한보기]     │
│                                                               │
│  🔔 권한 요청 대기 목록:                                        │
│  • 이마케팅 → 채용가이드.pdf 읽기 권한          [승인] [거부]     │
│  • 영업팀 → 인사평가양식.xlsx 읽기 권한 (팀 전체) [승인] [거부]     │
│  • 박신입 → 교육자료 폴더 접근 권한             [승인] [거부]     │
│                                                               │
│  ⚡ 빠른 작업:                                                │
│  [신규 프로젝트 팀 권한 설정] [부서 이동자 권한 업데이트]          │
│  [대량 권한 일괄 변경]        [권한 정책 템플릿 적용]            │
└───────────────────────────────────────────────────────────────┘
```

## 6. 권한 확인 프로세스

### 6.1 파일 접근 시 권한 확인 알고리즘

```python
def check_file_access(user_id: str, file_id: str, action: str) -> bool:
    """파일 접근 권한 확인 (계층적 상속 고려)"""
    
    # 1. 직접 권한 확인
    if check_direct_permission(user_id, file_id, action):
        return True
    
    # 2. 파일이 속한 컨테이너의 권한 확인
    file_container = get_file_container(file_id)
    if check_container_permission(user_id, file_container.id, action):
        return True
    
    # 3. 상위 컨테이너의 상속 권한 확인
    parent_containers = get_parent_containers_hierarchy(file_container.id)
    for parent_container in parent_containers:
        if check_inherited_permission(user_id, parent_container.id, action):
            return True
    
    # 4. 역할 기반 권한 확인
    user_roles = get_user_roles(user_id, file_container.id)
    for role in user_roles:
        if check_role_permission(role.role_code, action, 'DOCUMENT'):
            return True
    
    return False
```

### 6.2 권한 확인 PostgreSQL 함수

```sql
CREATE OR REPLACE FUNCTION check_user_permission(
    p_user_id VARCHAR(50),
    p_container_id VARCHAR(50),
    p_permission_type VARCHAR(20)
) RETURNS BOOLEAN AS $$
DECLARE
    has_permission BOOLEAN := FALSE;
    current_container_id VARCHAR(50) := p_container_id;
BEGIN
    -- 직접 권한 확인
    SELECT COUNT(*) > 0 INTO has_permission
    FROM tb_container_permissions
    WHERE user_id = p_user_id
      AND container_id = p_container_id
      AND permission_type = p_permission_type
      AND is_active = 'Y'
      AND (valid_until IS NULL OR valid_until > NOW());
    
    -- 상속된 권한 확인 (상위 컨테이너)
    WHILE NOT has_permission AND current_container_id IS NOT NULL LOOP
        SELECT parent_container_id INTO current_container_id
        FROM tb_knowledge_containers
        WHERE container_id = current_container_id;
        
        IF current_container_id IS NOT NULL THEN
            SELECT COUNT(*) > 0 INTO has_permission
            FROM tb_container_permissions
            WHERE user_id = p_user_id
              AND container_id = current_container_id
              AND permission_type = p_permission_type
              AND is_active = 'Y'
              AND is_inherited = 'Y'
              AND (valid_until IS NULL OR valid_until > NOW());
        END IF;
    END LOOP;
    
    RETURN has_permission;
END;
$$ LANGUAGE plpgsql;
```

## 7. SAP 연동 자동 권한 관리

### 7.1 조직도 변경 시 자동 권한 업데이트

#### 7.1.1 직원 부서 이동 시나리오

```
🔄 조직개편: 김신입 (마케팅팀 → 인사팀 이동)
├── 📡 SAP 연동: 부서 이동 정보 자동 감지
├── 🔒 권한회수: 마케팅팀 관련 문서 접근 권한 자동 회수
├── 🔓 권한부여: 인사팀 관련 문서 접근 권한 자동 부여
└── 📧 알림발송: 권한 변경 내역 본인 및 관리자에게 통지
```

#### 7.1.2 자동 권한 동기화 프로세스

```python
def handle_employee_transfer(emp_no: str, from_dept: str, to_dept: str):
    """직원 부서 이동 시 자동 권한 업데이트"""
    
    # 1. 기존 부서 권한 회수
    revoke_department_permissions(emp_no, from_dept)
    
    # 2. 새 부서 기본 권한 부여
    assign_default_department_permissions(emp_no, to_dept)
    
    # 3. 개인 권한은 유지 (생성한 문서 등)
    preserve_personal_permissions(emp_no)
    
    # 4. 권한 변경 이력 기록
    log_permission_change(emp_no, from_dept, to_dept)
    
    # 5. 관련자에게 알림 발송
    send_permission_change_notification(emp_no, from_dept, to_dept)
```

## 8. 실제 업무 시나리오 예시

### 8.1 시나리오 1: 채용팀 직원의 문서 업로드

```
👤 김채용 (채용팀) → 📄 "2025년 채용가이드.pdf" 업로드
├── 🎯 접근범위: "팀 공유" 선택
├── 🔒 권한설정: 읽기+다운로드 허용
├── 👥 자동권한: 채용팀 5명 모두 접근 가능
└── 📈 결과: 팀 내부에서만 활용되는 업무 문서로 분류
```

### 8.2 시나리오 2: 부서 지식관리자의 권한 승인

```
👨‍💼 김지식 (인사팀 지식관리자) 
├── 🔔 권한요청: 영업팀 → 채용가이드 읽기 권한 요청
├── 📋 검토과정: 업무 연관성 및 보안 등급 확인
├── ✅ 승인처리: 영업팀에 읽기 권한 부여 (30일 제한)
└── 📊 모니터링: 접근 로그 및 사용 통계 추적
```

### 8.3 시나리오 3: 프로젝트 기반 임시 권한

```
🚀 신규 프로젝트: "2025 신입사원 채용 프로젝트"
├── 📁 임시 컨테이너: 프로젝트 전용 지식 공간 생성
├── 👥 팀 구성: 인사팀 3명 + 마케팅팀 2명 + 외부 컨설턴트 1명
├── ⏰ 권한 기간: 프로젝트 기간 (6개월) 동안만 유효
├── 🔒 접근 제어: 프로젝트 관련 문서만 접근 가능
└── 🗑️ 자동 정리: 프로젝트 종료 시 임시 권한 자동 회수
```

## 9. 권한 관리 API 설계

### 9.1 컨테이너 관리 API 엔드포인트

| 엔드포인트                                              | HTTP 메서드 | 기능         | 설명           |
| -------------------------------------------------- | -------- | ---------- | ------------ |
| `/api/admin/containers`                            | GET      | 컨테이너 목록 조회 | 계층적 구조로 반환   |
| `/api/admin/containers`                            | POST     | 컨테이너 생성    | 새 지식 컨테이너 생성 |
| `/api/admin/containers/{id}/permissions`           | GET      | 컨테이너 권한 목록 | 사용자별 권한 현황   |
| `/api/admin/containers/{id}/permissions`           | POST     | 권한 부여      | 사용자에게 권한 할당  |
| `/api/admin/containers/{id}/permissions/{user_id}` | DELETE   | 권한 삭제      | 특정 사용자 권한 회수 |
| `/api/admin/containers/{id}/sync`                  | POST     | SAP 조직 동기화 | 조직도 변경사항 반영  |

### 9.2 문서 업로드 시 권한 설정 API

```json
POST /api/documents/upload
{
  "file": "채용가이드.pdf",
  "permissions": {
    "access_scope": "TEAM",
    "permissions": ["READ", "DOWNLOAD"],
    "expires_at": "2025-12-31T23:59:59Z",
    "specific_users": ["emp002", "emp003"],
    "inherit_to_children": false
  }
}
```

## 10. 권한 관리 모니터링 및 감사

### 10.1 권한 변경 이력 추적

- 모든 권한 변경사항 실시간 로깅
- 권한 부여자, 변경 내용, 변경 일시 기록
- 권한 남용 패턴 자동 감지 및 알림

### 10.2 접근 통계 및 분석

- 문서별/사용자별 접근 빈도 분석
- 권한 사용률 통계 제공
- 불필요한 권한 정리 권고사항 제공

### 10.3 보안 정책 준수

- 최소 권한 원칙 (Principle of Least Privilege) 적용
- 정기적인 권한 검토 및 정리 프로세스
- 민감 정보 접근에 대한 추가 승인 절차

---

이 권한 관리 체계를 통해 ABEKM 시스템에서는 지식생성자와 지식관리자가 각자의 역할에 맞는 세분화된 권한 관리를 수행할 수 있으며, SAP 조직도와 연동하여 자동화된 권한 관리가 가능합니다.

## 11. 실제 구현 업데이트 (2025-10-31)

최근 릴리스에서 권한 관리 체계가 다음과 같이 구체 구현되었습니다.

### 11.1 표준 엔드포인트 및 응답 스키마

- GET `/api/v1/permissions/all-user-permissions`
    - 권한 현황 전체 리스트(관리 권한 사용자만 접근)
    - 응답 핵심 필드:
        - `user_emp_no`(사번), `user_name`(HR.emp_nm), `department`(HR.dept_nm)
        - `container_id`, `container_name`
        - `permission_type` ∈ {`admin`, `write`, `read`}
        - `granted_at`, `expires_date`

- GET `/api/v1/permission-requests/pending`
    - 대기 요청 목록: `{ total: number, requests: RequestDto[] }`
    - 페이지네이션/정렬은 차기 반영 예정

### 11.2 역할→권한 타입 매핑 규칙

- `role_id` 표준 매핑(서버에서 변환 후 `permission_type`으로 반환)
    - ADMIN 계열 → `admin`
    - EDITOR/WRITE 계열 → `write`
    - VIEWER/READ 계열 → `read`

### 11.3 HR 연계 필드 정합성

- 사용자 이름/부서:
    - `TbSapHrInfo.emp_nm` → `user_name`
    - `TbSapHrInfo.dept_nm` → `department`

- 권한 만료일:
    - `expires_date` 사용 (이전 `valid_until` 명칭 사용 금지)

### 11.4 지식관리자 스코프(관리 범위) 적용

- 정책: “관리자가 관리하는 컨테이너”로 권한 조회/승인 범위를 제한
- 현황: 프런트 필터로 우선 적용, 서버 쿼리 레벨 강제 제한 단계적 도입(컨테이너-관리자 매핑 조인 추가 예정)

### 11.5 프런트엔드 연동 파일

- `frontend/src/services/managerService.ts` → `/api/v1/permissions/all-user-permissions` 연동 및 필드 매핑
- `frontend/src/pages/manager/PermissionApprovalManagement.tsx` → 승인 대기/현황/이력 탭
- `frontend/src/pages/manager/UserPermissionManagement.tsx` → 사용자별 권한 현황, 필터/검색

### 11.6 사용자 권한 신청 현황 화면 (2025-11-05)

- 신규 사용자 전용 엔드포인트: `GET /api/v1/permission-requests/my-requests`
    - 지원 파라미터: `status`, `container_id`, `from_date`, `to_date`, `page`, `size`
    - 응답 스키마: `{ requests: PermissionRequestResponse[], total_count: number }`
    - 각 요청 항목은 `request_id`, `container_name`, `requested_permission_level`, `request_reason`, `status`, `requested_at`, `processed_at`, `rejection_reason` 등을 포함 (ISO8601 문자열)
- 프런트엔드 연동: `frontend/src/services/permissionRequestService.ts`
    - Axios + `getAuthHeader()`로 JWT 인증 헤더 자동 첨부
    - 백엔드 응답을 `PermissionRequest` 타입으로 재매핑하여 UI에서 일관된 필드명 사용 (`requested_permission_level` → 배지, `request_reason` → 표 설명 등)
    - 장애 시 빈 배열 반환으로 UI 안전성 확보, 콘솔 디버그 로그(`[UI DEBUG]`) 유지
- 화면 구성: `frontend/src/pages/user/PermissionRequestsPage.tsx`
    - 통계 카드 4종 (전체/대기/승인/거부) 클라이언트 계산, Tailwind 기반 배지 컴포넌트(`getStatusBadge`, `getPermissionLevelBadge`)로 시각화
    - 상태 필터 버튼(`all`, `pending`, `approved`, `rejected`) 즉시 적용 및 빈 상태 안내 메시지 제공
    - 테이블 열: 신청일시, 컨테이너, 요청 권한, 신청 사유, 상태, 처리일시, 처리 사유
- 상태/라벨 매핑 (로컬라이즈 적용)
    - `PENDING` → "승인 대기"
    - `APPROVED` → "승인됨"
    - `REJECTED` → "거부됨"
    - `CANCELLED` → "취소됨"
- 권한 레벨 배지: VIEWER(읽기), EDITOR(편집), MANAGER(관리), ADMIN(관리자), OWNER(소유자) → Tailwind 색상 토큰으로 구분

## 12. 권한 관리 핵심 원칙 및 적용 규칙 (2025-10-31)

### 12.1 사용자 유형별 권한 범위 원칙

#### 12.1.1 시스템 관리자 (SYSTEM_ADMIN)

**정의**: 전체 시스템에 대한 최고 권한 보유자

**특성**:
- 사번: `ADMIN001` (예: 김관리자)
- 역할: `SYSTEM_ADMIN` 또는 `ADMIN` (tb_user_roles.role_name)
- 권한 범위: **모든 지식 컨테이너**
- 특별 권한:
  - 모든 컨테이너/문서 접근 가능
  - 모든 권한 요청 승인/거부 가능
  - 시스템 설정 변경 가능
  - 사용자 역할 부여/회수 가능

**백엔드 처리 로직**:
```python
# SYSTEM_ADMIN은 manager_emp_no 필터링을 적용하지 않음
if user_role == 'SYSTEM_ADMIN':
    # 전체 데이터 조회 (필터링 없음)
    permissions = await list_all_permissions(manager_emp_no=None)
else:
    # 지식관리자는 관리 범위만 조회
    permissions = await list_all_permissions(manager_emp_no=current_user.emp_no)
```

#### 12.1.2 지식관리자 (MANAGER)

**정의**: 특정 컨테이너 계층에 대한 관리 권한 보유자

**특성**:
- 사번: 일반 직원 사번 (예: 정MS)
- 역할: `MANAGER`, `OWNER` (특정 컨테이너에 대한)
- 권한 범위: **관리 컨테이너 + 모든 하위 컨테이너**
- 특별 권한:
  - 관리 범위 내 권한 요청 승인/거부
  - 관리 범위 내 사용자 권한 조회/수정
  - 관리 범위 내 문서 품질 관리

**예시**: 정MS (MS서비스팀 지식관리자)
- 직접 관리 컨테이너: `MS서비스팀`
- 상위 컨테이너: `클라우드사업본부` → `CEO직속` (루트)
- 하위 컨테이너: (아직 없음, 생성 시 자동 관리 범위 포함)

### 12.2 컨테이너 계층 구조 및 권한 상속 원칙

#### 12.2.1 계층 구조 예시

```
🏢 CEO직속 (ROOT - container_id: "CEO직속")
├── 📁 클라우드사업본부 (container_id: "클라우드사업본부", parent_container_id: "CEO직속")
│   ├── 📁 클라우드서비스팀 (parent_container_id: "클라우드사업본부")
│   └── 📁 MS서비스팀 (parent_container_id: "클라우드사업본부")
│       ├── 📁 (미래 하위팀 1)
│       └── 📁 (미래 하위팀 2)
└── 📁 CTI사업본부 (parent_container_id: "CEO직속")
    └── ...
```

#### 12.2.2 권한 상속 규칙

**원칙 1: 상향 읽기 권한 자동 부여**
- 하위 컨테이너 관리자는 **모든 상위 컨테이너에 최소 READ 권한** 자동 부여
- 예: `MS서비스팀` 관리자 정MS
  - `MS서비스팀`: MANAGER (직접 부여)
  - `클라우드사업본부`: READ (자동 부여) ← **상위 컨테이너**
  - `CEO직속`: READ (자동 부여) ← **루트 컨테이너**

**원칙 2: 하향 권한 자동 확장**
- 특정 컨테이너에 대한 관리 권한은 **모든 하위 컨테이너에 자동 적용**
- 예: `클라우드사업본부` 관리자
  - `클라우드사업본부`: MANAGER (직접 부여)
  - `클라우드서비스팀`: MANAGER (자동 확장)
  - `MS서비스팀`: MANAGER (자동 확장)
  - `MS서비스팀` 아래 미래 하위팀: MANAGER (자동 확장)

**원칙 3: 직접 권한 우선 원칙**
- 상속 권한과 직접 권한이 충돌할 경우 **직접 부여된 권한 우선**
- 권한 레벨: ADMIN > MANAGER > WRITE > READ

#### 12.2.3 권한 확인 우선순위

```
1순위: 직접 권한 (tb_user_permissions에 명시적으로 기록된 권한)
2순위: 관리자 하향 상속 (상위 컨테이너의 MANAGER/OWNER 권한)
3순위: 상향 읽기 권한 (하위 관리자의 상위 컨테이너 READ 권한)
4순위: 역할 기반 권한 (tb_user_roles의 기본 역할)
```

### 12.3 관리 범위 필터링 로직

#### 12.3.1 백엔드 필터링 전략

**get_managed_container_ids(manager_emp_no) 동작 방식**:

```python
async def get_managed_container_ids(manager_emp_no: str) -> List[str]:
    """
    지식관리자가 관리하는 모든 컨테이너 ID 조회
    
    반환값:
    - 시스템 관리자(SYSTEM_ADMIN): 빈 리스트 [] → 필터링 없음
    - 지식관리자: [관리 컨테이너 + 모든 하위 컨테이너]
    """
    
    # 1. 시스템 관리자 체크
    if await is_system_admin(manager_emp_no):
        return []  # 빈 리스트 = 전체 조회 (필터링 안 함)
    
    # 2. 관리자 권한을 가진 컨테이너 조회
    # role_id IN ('ADMIN', 'MANAGER', 'OWNER', 'SYSTEM_ADMIN')
    root_containers = await get_manager_root_containers(manager_emp_no)
    
    # 3. 각 관리 컨테이너의 하위 계층 재귀 조회
    all_containers = set(root_containers)
    for root_id in root_containers:
        descendants = await get_all_descendants(root_id)
        all_containers.update(descendants)
    
    return list(all_containers)
```

**사용 예시**:
```python
# 정MS (MS서비스팀 관리자)
allowed_ids = await get_managed_container_ids("정MS")
# 반환: ["MS서비스팀", "MS서비스팀_하위1", "MS서비스팀_하위2", ...]

# 김관리자 (SYSTEM_ADMIN)
allowed_ids = await get_managed_container_ids("ADMIN001")
# 반환: [] → 빈 리스트는 "전체 조회" 의미
```

#### 12.3.2 프론트엔드 필터링 보완

- 백엔드 필터링이 1차 보안 레이어
- 프론트엔드는 UX 개선용 클라이언트 필터링 제공
- 두 레이어 모두 동일한 논리 적용

### 12.4 권한 요청 승인 범위

#### 12.4.1 승인 가능 범위 결정 로직

```python
async def can_approve_request(approver_emp_no: str, request: PermissionRequest) -> bool:
    """
    승인자가 해당 요청을 승인할 권한이 있는지 확인
    
    조건:
    1. 시스템 관리자: 모든 요청 승인 가능
    2. 지식관리자: 요청 대상 컨테이너가 관리 범위 내에 있어야 함
    """
    
    # 시스템 관리자 체크
    if await is_system_admin(approver_emp_no):
        return True
    
    # 지식관리자의 관리 범위 확인
    managed_containers = await get_managed_container_ids(approver_emp_no)
    
    return request.container_id in managed_containers
```

### 12.5 컨테이너 생성 시 권한 자동 부여

#### 12.5.1 신규 컨테이너 생성 규칙

```python
async def create_container(parent_container_id: str, container_name: str, creator_emp_no: str):
    """
    신규 컨테이너 생성 시 자동 권한 부여
    """
    
    # 1. 컨테이너 생성
    new_container = await insert_container(parent_container_id, container_name)
    
    # 2. 생성자에게 OWNER 권한 부여
    await grant_permission(creator_emp_no, new_container.id, role_id='OWNER')
    
    # 3. 상위 컨테이너 관리자들에게 MANAGER 권한 자동 부여
    parent_managers = await get_container_managers(parent_container_id)
    for manager in parent_managers:
        await grant_permission(manager.emp_no, new_container.id, role_id='MANAGER')
    
    # 4. 하위 관리자에게 상위 READ 권한 부여 (역방향)
    # creator_emp_no → parent_container_id, 최상위까지 READ 권한
    current_parent = parent_container_id
    while current_parent:
        await ensure_read_permission(creator_emp_no, current_parent)
        current_parent = await get_parent_container_id(current_parent)
    
    return new_container
```

### 12.6 구현 체크리스트

- [x] PermissionService.get_managed_container_ids() 구현
- [x] PermissionService.is_system_admin() 구현
- [x] 시스템 관리자 vs 지식관리자 구분 로직
- [x] 시스템 관리자 필터링 예외 처리 (빈 리스트 반환)
- [x] 지식관리자 범위 필터링 (관리 컨테이너 + 하위)
- [ ] **상향 READ 권한 자동 부여 로직** (TODO)
- [ ] **하위 컨테이너 생성 시 권한 자동 상속** (TODO)
- [ ] 권한 확인 우선순위 알고리즘 적용
- [x] 백엔드 API 필터링 적용 (list_all_permissions, get_pending_requests)
- [x] 프론트엔드 범위 제한 적용

### 12.7 구현 예시

#### 예시 1: 시스템 관리자 (김관리자, ADMIN001)

```python
# 김관리자 권한 조회
allowed_ids = await get_managed_container_ids("ADMIN001")
# 반환: [] (빈 리스트 = 시스템 관리자, 필터링 없음)

# API 호출 시
GET /api/v1/permissions/all-user-permissions
# 응답: 모든 컨테이너의 모든 권한 (필터링 없음)
```

#### 예시 2: 지식관리자 (정MS, MS서비스팀 관리자)

```python
# 정MS 권한 조회
allowed_ids = await get_managed_container_ids("정MS")
# 반환: ["MS서비스팀", "MS서비스팀_하위1", "MS서비스팀_하위2", ...]

# API 호출 시
GET /api/v1/permissions/all-user-permissions
# 응답: MS서비스팀 및 하위 컨테이너의 권한만 반환

# 권한 요청 승인
POST /api/v1/permission-requests/{request_id}/approve
# 조건: request.container_id가 allowed_ids 안에 있어야 승인 가능
```

#### 예시 3: 정MS의 상위 컨테이너 읽기 권한 (자동 부여 예정)

```sql
-- 현재 구현: 명시적 권한 필요
INSERT INTO tb_user_permissions (user_emp_no, container_id, role_id)
VALUES ('정MS', 'MS서비스팀', 'MANAGER');

-- TODO: 자동 상향 READ 권한 부여
INSERT INTO tb_user_permissions (user_emp_no, container_id, role_id, is_inherited)
VALUES 
  ('정MS', '클라우드사업본부', 'READ', 'Y'),  -- 상위 컨테이너
  ('정MS', 'CEO직속', 'READ', 'Y');            -- 루트 컨테이너
```

---

**문서 버전**: v3.3  
**최종 업데이트**: 2025-11-04  
**작성자**: WKMS 개발팀  
**검토자**: 시스템 아키텍트

## 13. 최신 구현 업데이트 (2025-11-04)

### 13.1 사용자 컨테이너 생성 및 권한 관리

#### 13.1.1 사용자 컨테이너 생성 기능 구현

**목적**: 일반 사용자가 자신의 개인 지식 컨테이너를 생성하고 관리할 수 있는 기능

**구현 내용**:

1. **백엔드 API 엔드포인트**:
   - `POST /api/v1/containers/user/create`: 사용자 컨테이너 생성
   - `DELETE /api/v1/containers/user/{container_id}`: 사용자 컨테이너 삭제

2. **컨테이너 생성 규칙**:
   ```python
   # 컨테이너 ID 패턴: USER_{emp_no}_{UUID}
   # 예: USER_77107791_9408CC51
   
   container_id = f"USER_{emp_no}_{uuid.uuid4().hex[:8].upper()}"
   ```

3. **자동 권한 부여**:
   ```python
   async def create_user_container(parent_container_id, container_name, user_emp_no):
       """
       사용자 컨테이너 생성 시 자동 권한 부여
       
       자동으로 부여되는 권한:
       1. 생성자(사용자): OWNER 권한
       2. 시스템관리자(ADMIN001): ADMIN 권한
       """
       
       # 1. 컨테이너 생성
       new_container = await create_container(
           parent_container_id=parent_container_id,
           container_name=container_name,
           container_type='PERSONAL',
           owner_emp_no=user_emp_no
       )
       
       # 2. 생성자에게 OWNER 권한 부여
       await create_permission(
           container_id=new_container.container_id,
           user_emp_no=user_emp_no,
           role_id='OWNER',
           granted_by='SYSTEM'
       )
       
       # 3. 시스템관리자에게 ADMIN 권한 부여
       await create_permission(
           container_id=new_container.container_id,
           user_emp_no='ADMIN001',
           role_id='ADMIN',
           granted_by='SYSTEM'
       )
       
       return new_container
   ```

4. **컨테이너 삭제 검증**:
   ```python
   async def delete_user_container(container_id, user_emp_no):
       """
       사용자 컨테이너 삭제 검증
       
       삭제 가능 조건:
       1. USER_로 시작하는 PERSONAL 컨테이너
       2. 사용자가 OWNER 권한 보유
       3. 문서가 없는 빈 컨테이너
       """
       
       # 1. PERSONAL 컨테이너 확인
       if not container_id.startswith('USER_'):
           raise PermissionError("PERSONAL 컨테이너만 삭제 가능")
       
       # 2. OWNER 권한 확인
       permission = await check_permission(user_emp_no, container_id)
       if permission.role_id != 'OWNER':
           raise PermissionError("OWNER 권한 필요")
       
       # 3. 빈 컨테이너 확인
       if container.document_count > 0:
           raise ValueError("문서가 있는 컨테이너는 삭제 불가")
       
       await delete_container(container_id)
   ```

#### 13.1.2 프론트엔드 UI 구현

**파일**: `frontend/src/pages/user/MyKnowledge.tsx`

**기능**:
1. "컨테이너 추가" 버튼: 선택된 부모 컨테이너 하위에 새 컨테이너 생성
2. "컨테이너 삭제" 버튼: 빈 PERSONAL 컨테이너 삭제
3. 자동 포커스: 생성/삭제 후 자동으로 해당 위치로 포커스 이동
4. 트리 확장: 생성된 컨테이너까지의 전체 경로 자동 확장

**컴포넌트**: `frontend/src/pages/user/my-knowledge/components/ContainerCreateModal.tsx`

```typescript
interface ContainerCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string) => Promise<void>;
  parentContainerName: string;
}

// 사용 예시
<ContainerCreateModal
  isOpen={isCreateModalOpen}
  onClose={() => setIsCreateModalOpen(false)}
  onSubmit={handleContainerCreate}
  parentContainerName={selectedContainer?.name || ''}
/>
```

### 13.2 권한 시스템 개선

#### 13.2.1 OWNER 역할 업로드 권한 추가

**문제**: 사용자가 자신의 컨테이너를 생성했지만 문서 업로드 시 권한 오류 발생

**원인**: `check_upload_permission`에서 OWNER 역할을 허용 목록에 포함하지 않음

**수정 내용**:
```python
# backend/app/services/auth/permission_service.py

async def check_upload_permission(
    self,
    user_emp_no: str,
    container_id: str
) -> Tuple[bool, str]:
    """
    컨테이너 업로드 권한 확인
    
    업로드 허용 권한:
    - OWNER: 컨테이너 소유자
    - ADMIN: 시스템 관리자
    - MANAGER: 지식 관리자
    - EDITOR: 편집자
    - CONTRIBUTOR: 기여자
    - MEMBER_DEPT: 부서 멤버
    """
    
    permission_level = await service.get_user_permission_level(user_emp_no, container_id)
    
    # OWNER를 최우선 권한으로 추가
    upload_allowed_levels = ["OWNER", "ADMIN", "MANAGER", "EDITOR", "CONTRIBUTOR", "MEMBER_DEPT"]
    can_upload = permission_level in upload_allowed_levels
    
    if not can_upload:
        return False, f"업로드 권한이 없습니다. 현재 권한: {permission_level}"
    
    return True, permission_level
```

#### 13.2.2 시스템 관리자 및 지식 관리자 권한 자동 부여

**구현 스크립트**: `add_admin_permissions_to_user_containers.py`

**목적**: 기존 사용자 컨테이너에 시스템 관리자 권한 자동 추가

```python
async def add_admin_permissions():
    """
    모든 USER_ 컨테이너에 ADMIN001에게 ADMIN 권한 부여
    
    처리 내용:
    - USER_로 시작하는 PERSONAL 컨테이너 조회
    - 각 컨테이너에 ADMIN001 ADMIN 권한 확인
    - 없으면 자동 생성
    """
    
    user_containers = await get_user_containers()
    
    for container in user_containers:
        # 기존 ADMIN 권한 확인
        existing = await check_admin_permission(container.container_id)
        
        if not existing:
            # ADMIN 권한 생성
            await create_permission(
                container_id=container.container_id,
                user_emp_no='ADMIN001',
                role_id='ADMIN',
                permission_type='DIRECT',
                access_scope='FULL',
                permission_source='SYSTEM_AUTO',
                granted_by='SYSTEM'
            )
```

**실행 결과**:
```
✅ 컨테이너: USER_77107791_CB46AC5B - ADMIN 권한 추가
✅ 컨테이너: USER_77107791_5877FEA6 - ADMIN 권한 추가
✅ 컨테이너: USER_77107791_D4600368 - ADMIN 권한 추가
✅ 컨테이너: USER_77107791_9408CC51 - ADMIN 권한 추가
✅ 컨테이너: USER_77107791_0627BBC2 - ADMIN 권한 추가

총 5개 컨테이너에 ADMIN 권한 추가 완료
```

### 13.3 MS서비스팀 권한 체계 수정

#### 13.3.1 문제 상황

**정MS (MSS001) 사용자**:
- 역할: MS서비스팀 팀장
- 기대 권한:
  - WJ_MS_SERVICE 컨테이너: OWNER 권한
  - 하위 myMS서비스 컨테이너들: VIEWER 권한

**발견된 문제**:
1. WJ_MS_SERVICE에 OWNER_DEPT 권한만 있음 → OWNER로 변경 필요
2. 하위 USER_ 컨테이너에 권한 없음 → VIEWER 권한 추가 필요

#### 13.3.2 권한 수정 스크립트

**파일**: `check_ms_permissions.py`

```python
async def fix_ms_permissions():
    """
    MS서비스팀 권한 수정
    
    처리 내용:
    1. WJ_MS_SERVICE: MSS001에게 OWNER 권한 부여
    2. 하위 myMS서비스 컨테이너들: MSS001에게 VIEWER 권한 부여
    """
    
    # 1. WJ_MS_SERVICE OWNER 권한 업데이트
    existing_perm = await get_permission('MSS001', 'WJ_MS_SERVICE')
    if existing_perm.role_id != 'OWNER':
        await update_permission(
            permission_id=existing_perm.permission_id,
            role_id='OWNER'
        )
    
    # 2. 하위 컨테이너 VIEWER 권한 추가
    child_containers = await get_child_containers('WJ_MS_SERVICE', prefix='USER_')
    for container in child_containers:
        await create_permission(
            container_id=container.container_id,
            user_emp_no='MSS001',
            role_id='VIEWER',
            granted_by='SYSTEM'
        )
```

**실행 결과**:
```
✅ WJ_MS_SERVICE: OWNER_DEPT → OWNER 권한으로 업데이트
✅ USER_77107791_5877FEA6 (myMS서비스): VIEWER 권한 추가
✅ USER_77107791_D4600368 (myMS서비스): VIEWER 권한 추가
✅ USER_77107791_9408CC51 (myMS서비스): VIEWER 권한 추가
✅ USER_77107791_0627BBC2 (myMS서비스): VIEWER 권한 추가

권한 수정 완료!
```

### 13.4 문서 처리 상태 관리 개선

#### 13.4.1 chunk_count 업데이트 누락 문제

**문제**: 
- Celery 태스크가 문서 처리를 완료했지만 `chunk_count`가 0으로 유지
- `processing_status`는 'completed'인데 실제 검색 불가능

**원인**:
- `_process_document_multimodal` 함수에서 처리 완료 시 `chunk_count` 미업데이트
- `TbFileBssInfo.chunk_count` 필드가 DB에 반영되지 않음

#### 13.4.2 수정 내용

**파일**: `backend/app/tasks/document_tasks.py`

```python
async def _process_document_multimodal(document_id, file_path, ...):
    """
    멀티모달 파이프라인 실행 후 chunk_count 업데이트
    """
    
    pipeline_result = await PipelineRouter.process_document(...)
    
    if pipeline_result.get('success'):
        stats = pipeline_result.get('statistics', {})
        chunks_count = stats.get('total_chunks', 0)
        
        # 🆕 TbFileBssInfo의 chunk_count 업데이트
        from sqlalchemy import update
        try:
            update_stmt = (
                update(TbFileBssInfo)
                .where(TbFileBssInfo.file_bss_info_sno == document_id)
                .values(chunk_count=chunks_count)
            )
            await session.execute(update_stmt)
            await session.commit()
            logger.info(f"✅ [CHUNK-COUNT] chunk_count 업데이트 완료: doc_id={document_id}, count={chunks_count}")
        except Exception as e:
            logger.error(f"❌ [CHUNK-COUNT] chunk_count 업데이트 실패: {e}")
            await session.rollback()
        
        return {
            'success': True,
            'chunks_count': chunks_count,
            'embeddings_count': stats.get('total_embeddings', 0),
            ...
        }
```

#### 13.4.3 기존 파일 수정 스크립트

**파일**: `fix_chunk_counts.py`

```python
async def fix_chunk_counts():
    """
    chunk_count=0이지만 실제 청크가 있는 파일 수정
    """
    
    # chunk_count가 0인 completed 파일 조회
    files = await get_completed_files_with_zero_chunks()
    
    for file in files:
        # 실제 청크 개수 확인
        actual_count = await count_chunks(file.file_bss_info_sno)
        
        if actual_count > 0:
            # chunk_count 업데이트
            await update_chunk_count(file.file_bss_info_sno, actual_count)
            print(f"✅ {file.file_lgc_nm}: chunk_count 업데이트 0 → {actual_count}")
```

**실행 결과**:
```
📄 파일: 토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf
   ID: 4
   DB chunk_count: 0
   실제 chunk 개수: 64
   ✅ chunk_count 업데이트: 0 → 64

📄 파일: 토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf
   ID: 3
   DB chunk_count: 0
   실제 chunk 개수: 64
   ✅ chunk_count 업데이트: 0 → 64

📄 파일: Ambidextrous Leadership and Innovative Work Behavior...
   ID: 2
   DB chunk_count: 0
   실제 chunk 개수: 77
   ✅ chunk_count 업데이트: 0 → 77

====================================================================================================
✅ 작업 완료
   업데이트된 파일: 3개
   청크가 없는 파일: 0개
====================================================================================================
```

### 13.5 Azure Blob 파일 뷰어 한글 파일명 처리

#### 13.5.1 문제

**증상**: 한글 파일명이 포함된 PDF 파일을 브라우저에서 열 때 Azure Blob 에러 발생

**에러 메시지**:
```
InvalidQueryParameterValue: Value for one of the query parameters specified in the request URI is invalid.
query parameter values contain invalid characters
```

#### 13.5.2 원인 분석

1. **SAS URL 생성 시 blob_name이 한글 그대로 전달**
   - `generate_blob_sas(blob_name="raw/.../토픽 모델링...pdf")`
   - Azure SDK가 blob_name을 인코딩하지 않고 서명 생성
   - 서명과 URL의 경로가 불일치

2. **content_disposition 헤더에 한글 포함**
   - `content_disposition = f'inline; filename="토픽 모델링...pdf"'`
   - Azure Blob SAS는 쿼리 파라미터에 ASCII만 허용

#### 13.5.3 수정 내용

**파일 1**: `backend/app/services/core/azure_blob_service.py`

```python
def generate_sas_url(
    self,
    blob_path: str,
    purpose: str = 'raw',
    expiry_seconds: Optional[int] = None,
    content_disposition: Optional[str] = None,
    content_type: Optional[str] = None,
) -> str:
    """
    Azure Blob SAS URL 생성
    
    수정 사항:
    1. SAS 서명 생성: 원본 blob_name 사용 (한글 그대로)
    2. URL 생성: 인코딩된 경로 사용
    """
    
    # SAS 서명 생성: 원본 blob_name 사용 (한글 그대로)
    sas = generate_blob_sas(
        account_name=self.account_name,
        account_key=self.account_key,
        container_name=container,
        blob_name=blob_path,  # 원본 경로 (한글 포함)
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
        content_disposition=content_disposition,
        content_type=content_type
    )
    
    # URL 생성: 인코딩된 경로 사용
    safe_blob_path = quote(blob_path, safe="/")
    base_url = f"https://{self.account_name}.blob.core.windows.net/{container}/{safe_blob_path}"
    return f"{base_url}?{sas}"
```

**파일 2**: `backend/app/api/v1/files.py`

```python
# iframe 파일 뷰어 엔드포인트
if storage_backend == 'azure_blob':
    filename = file_info.get("file_logical_name", f"file_{file_id}")
    mime_type, _ = mimetypes.guess_type(filename)
    
    # Azure Blob SAS는 content_disposition에 ASCII만 허용
    # filename에는 안전한 ASCII 대체값, filename*에만 UTF-8 인코딩된 실제 파일명 사용
    encoded_filename = urllib.parse.quote(filename)
    safe_ascii_filename = f"document_{file_id}.{file_info.get('file_extension', 'pdf')}"
    content_disposition = f"inline; filename=\"{safe_ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
    
    sas_url = azure_blob.generate_sas_url(
        blob_path=file_path,
        purpose='raw',
        expiry_seconds=3600,
        content_disposition=content_disposition,
        content_type=mime_type
    )
    return RedirectResponse(sas_url, status_code=307)
```

**수정 결과**:
- ✅ 한글 파일명 PDF 정상 표시
- ✅ 브라우저에서 파일 뷰어 정상 작동
- ✅ Azure Blob 에러 해결

### 13.6 API 프록시 설정 수정

#### 13.6.1 문제

**증상**: AI 지식생성 채팅 메뉴에서 메시지 전송 시 연결 오류

**에러**:
```
POST http://127.0.0.1:8000/api/v1/chat/stream net::ERR_CONNECTION_REFUSED
```

#### 13.6.2 원인

**파일**: `frontend/.env`

```properties
# 문제: 로컬 개발 환경에서 직접 백엔드 포트로 요청
REACT_APP_API_URL=http://127.0.0.1:8000
```

프록시를 사용하지 않고 직접 백엔드 포트(8000)로 요청하여 연결 실패

#### 13.6.3 수정 내용

```properties
# frontend/.env

# 백엔드 API 서버 (로컬 개발용)
# 로컬 개발 시 프록시 사용을 위해 주석 처리
# setupProxy.js가 /api 경로를 백엔드로 프록시합니다
# REACT_APP_API_URL=http://localhost:8000
# REACT_APP_API_URL=http://127.0.0.1:8000

# 환경 식별자
REACT_APP_ENV=development
```

**동작 방식**:
1. `REACT_APP_API_URL`이 설정되지 않음
2. `getApiUrl()` → 빈 문자열 반환
3. `/api/v1/chat/stream` 요청
4. `setupProxy.js`가 `/api` 경로를 `http://localhost:8000`으로 프록시
5. 정상 작동

### 13.7 구현 요약

#### 13.7.1 권한 관리 기능

| 기능 | 상태 | 설명 |
|------|------|------|
| 사용자 컨테이너 생성 | ✅ 완료 | USER_{emp_no}_{UUID} 패턴 |
| 사용자 컨테이너 삭제 | ✅ 완료 | 빈 컨테이너만 삭제 가능 |
| OWNER 권한 자동 부여 | ✅ 완료 | 생성자에게 OWNER 권한 |
| ADMIN 권한 자동 부여 | ✅ 완료 | ADMIN001에게 ADMIN 권한 |
| OWNER 업로드 권한 | ✅ 완료 | upload_allowed_levels에 추가 |
| 지식관리자 권한 체계 | ✅ 완료 | MS서비스팀 권한 수정 |
| 하위 컨테이너 VIEWER 권한 | ✅ 완료 | 상위 관리자의 하위 컨테이너 조회 |

#### 13.7.2 문서 처리 개선

| 기능 | 상태 | 설명 |
|------|------|------|
| chunk_count 자동 업데이트 | ✅ 완료 | 파이프라인 완료 시 자동 반영 |
| 기존 파일 수정 | ✅ 완료 | 3개 파일 chunk_count 수정 |
| 처리 상태 정확성 | ✅ 완료 | completed + chunk_count > 0 |

#### 13.7.3 파일 뷰어 개선

| 기능 | 상태 | 설명 |
|------|------|------|
| 한글 파일명 지원 | ✅ 완료 | Azure Blob SAS URL 인코딩 |
| content_disposition ASCII | ✅ 완료 | ASCII 안전 파일명 사용 |
| 브라우저 호환성 | ✅ 완료 | filename* UTF-8 인코딩 |

#### 13.7.4 개발 환경 설정

| 기능 | 상태 | 설명 |
|------|------|------|
| API 프록시 설정 | ✅ 완료 | setupProxy.js 사용 |
| 환경변수 정리 | ✅ 완료 | REACT_APP_API_URL 주석 |
| 로컬 개발 환경 | ✅ 완료 | 프록시 통한 백엔드 연결 |

### 13.8 테스트 케이스

#### 13.8.1 사용자 컨테이너 생성 시나리오

```
1. 사용자 "홍길동"이 "MS서비스팀" 선택 후 "컨테이너 추가" 클릭
2. 모달에서 "myMS서비스" 입력
3. 서버에서 컨테이너 생성:
   - container_id: USER_77107791_9408CC51
   - parent_container_id: WJ_MS_SERVICE
   - container_type: PERSONAL
   - owner_emp_no: 77107791

4. 자동 권한 부여:
   - 홍길동(77107791): OWNER 권한
   - 시스템관리자(ADMIN001): ADMIN 권한

5. UI 업데이트:
   - 트리뷰 자동 확장
   - 생성된 컨테이너로 포커스 이동

✅ 결과: 사용자가 자신의 컨테이너를 생성하고 즉시 사용 가능
```

#### 13.8.2 문서 업로드 권한 확인

```
1. 사용자 "홍길동"이 자신의 컨테이너에 문서 업로드
2. check_upload_permission 호출:
   - user_emp_no: 77107791
   - container_id: USER_77107791_9408CC51

3. 권한 확인:
   - permission_level = 'OWNER'
   - upload_allowed_levels = ['OWNER', 'ADMIN', 'MANAGER', ...]
   - can_upload = True ✅

4. 문서 처리:
   - Celery 태스크 실행
   - 멀티모달 파이프라인 처리
   - chunk_count 자동 업데이트

✅ 결과: OWNER 권한으로 업로드 및 처리 성공
```

#### 13.8.3 지식관리자 권한 확인

```
1. 정MS(MSS001)가 MS서비스팀 하위 컨테이너 조회
2. 권한 확인:
   - WJ_MS_SERVICE: OWNER
   - USER_77107791_5877FEA6: VIEWER
   - USER_77107791_D4600368: VIEWER
   - USER_77107791_9408CC51: VIEWER
   - USER_77107791_0627BBC2: VIEWER

3. UI 표시:
   - MS서비스팀 및 모든 하위 컨테이너 표시
   - 각 컨테이너의 문서 목록 조회 가능

✅ 결과: 지식관리자가 관리 범위 내 모든 컨테이너 조회 가능
```

---

**문서 버전**: v3.3  
**최종 업데이트**: 2025-11-04  
**작성자**: WKMS 개발팀  
**검토자**: 시스템 아키텍트

## 14. 지식컨테이너 접근권한 요청 및 승인 시스템

### 14.1 개요

사용자가 접근 권한이 없는 지식 컨테이너에 대해 권한을 요청하고, 해당 컨테이너의 관리자가 승인/거부할 수 있는 워크플로우 시스템입니다.

### 14.2 권한 요청 프로세스

#### 14.2.1 권한 요청 흐름도

```
[사용자] 
   ↓ (1) 컨테이너 접근 시도
[권한 없음 확인]
   ↓ (2) 권한 요청 버튼 클릭
[권한 요청 모달]
   ↓ (3) 요청 정보 입력
      - 요청 권한 레벨 (VIEWER, EDITOR, etc.)
      - 요청 사유 (필수, 최소 10자)
      - 업무 필요성 (선택)
      - 사용 예정 기간 (선택)
      - 긴급도 (선택)
   ↓ (4) 요청 생성
[DB 저장: tb_permission_requests]
   ↓ (5) 승인자 식별
[컨테이너 관리자에게 알림]
   ↓ (6) 관리자 검토
[승인 대기 목록 표시]
   ↓ (7) 승인/거부 결정
[권한 부여 또는 거부]
   ↓ (8) 요청자에게 결과 통보
[완료]
```

#### 14.2.2 데이터베이스 스키마

**권한 요청 테이블 (tb_permission_requests)**

```sql
CREATE TABLE tb_permission_requests (
    -- 기본 정보
    request_id SERIAL PRIMARY KEY,
    requester_emp_no VARCHAR(20) NOT NULL REFERENCES tb_sap_hr_info(emp_no),
    container_id VARCHAR(50) NOT NULL REFERENCES tb_knowledge_containers(container_id),
    
    -- 요청 내용
    requested_permission VARCHAR(20) NOT NULL,
    current_permission VARCHAR(20),
    justification TEXT NOT NULL,
    business_need TEXT,
    requested_duration VARCHAR(50),
    temp_end_date TIMESTAMP WITH TIME ZONE,
    
    -- 요청 상태
    request_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority_level VARCHAR(10) NOT NULL DEFAULT 'normal',
    
    -- 승인 정보
    approver_emp_no VARCHAR(20) REFERENCES tb_sap_hr_info(emp_no),
    approval_date TIMESTAMP WITH TIME ZONE,
    approval_comment TEXT,
    rejection_reason TEXT,
    
    -- 자동 처리
    auto_approved BOOLEAN NOT NULL DEFAULT FALSE,
    notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- 시스템 필드
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    last_modified_date TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

### 14.3 주요 API 엔드포인트

#### 14.3.1 권한 요청 생성

**Endpoint**: `POST /api/v1/permission-requests`

**Request**:
```json
{
  "container_id": "WJ_INFRA_CONSULT",
  "requested_permission_level": "VIEWER",
  "request_reason": "프로젝트 참고 자료 열람을 위해 권한이 필요합니다",
  "business_justification": "고객사 제안서 작성",
  "expected_usage_period": "1개월",
  "urgency_level": "normal"
}
```

**Response**:
```json
{
  "success": true,
  "message": "컨테이너 관리자의 승인이 필요합니다 (요청 ID: 3)",
  "request_id": "3",
  "auto_approved": false
}
```

#### 14.3.2 승인 대기 목록 조회

**Endpoint**: `GET /api/v1/permission-requests/pending`

**Response**:
```json
{
  "requests": [
    {
      "request_id": "3",
      "requester_name": "홍길동",
      "requester_department": "MS서비스팀",
      "container_name": "인프라컨설팅팀",
      "requested_permission_level": "VIEWER",
      "request_reason": "프로젝트 열람권한을 신청합니다",
      "status": "pending",
      "requested_at": "2025-11-04T06:57:16+00:00"
    }
  ],
  "total_count": 1
}
```

#### 14.3.3 승인 처리

**Endpoint**: `POST /api/v1/permission-requests/{request_id}/approve`

**Request**:
```json
{
  "approval_comment": "업무 협업을 위해 승인합니다"
}
```

#### 14.3.4 거부 처리

**Endpoint**: `POST /api/v1/permission-requests/{request_id}/reject`

**Request**:
```json
{
  "rejection_reason": "해당 컨테이너는 내부 문서로 구성되어 있어 접근이 제한됩니다"
}
```

### 14.4 주요 이슈 및 해결

#### 14.4.1 타입 변환 오류 수정

**문제**: PostgreSQL 타입 비교 오류
```
연산자 없음: integer = character varying
```

**원인**: FastAPI path parameter(string)와 서비스 메서드(int) 타입 불일치

**해결**:
```python
# 모든 엔드포인트에서 request_id 타입 변환 적용
success = await service.approve_request(
    request_id=int(request_id),  # ✅ string → int 변환
    approver_emp_no=current_user.emp_no
)
```

#### 14.4.2 관계 데이터 로딩 최적화

**문제**: 요청자 이름, 부서, 컨테이너 이름이 `None`으로 표시

**해결**: SQLAlchemy의 `selectinload` 사용
```python
from sqlalchemy.orm import selectinload

result = await self.session.execute(
    select(TbPermissionRequests)
    .options(
        selectinload(TbPermissionRequests.requester),
        selectinload(TbPermissionRequests.knowledge_container),
        selectinload(TbPermissionRequests.approver)
    )
    .where(and_(*conditions))
)
```

#### 14.4.3 프론트엔드 필드 매핑

**문제**: 백엔드 새 스키마 필드와 프론트엔드 기존 필드 불일치

**해결**: 매퍼 함수에서 fallback 처리
```typescript
const mapPermissionRequestDto = (dto: PermissionRequestDTO) => {
  const userName = dto.requester_name || dto.user_name || '알 수 없음';
  const department = dto.requester_department || dto.user_department || '';
  const requestReason = dto.request_reason || dto.reason || '';
  return { user_name: userName, user_department: department, reason: requestReason };
};
```

### 14.5 테스트 시나리오

#### 14.5.1 권한 요청 생성 테스트

```
1. 사용자 "홍길동"이 WJ_INFRA_CONSULT 선택
2. "권한 요청" 버튼 클릭
3. 요청 사유 입력 (10자 이상)
4. 요청 생성 성공
   ✅ request_id: 3
   ✅ status: pending
   ✅ 승인자: INF001
```

#### 14.5.2 승인 처리 테스트

```
1. 관리자 INF001 로그인
2. "승인 대기" 탭에서 요청 확인
   ✅ 요청자: 홍길동
   ✅ 부서: MS서비스팀
   ✅ 요청사유: "프로젝트 열람권한을 신청합니다"
3. "승인" 버튼 클릭
4. 권한 부여 성공
   ✅ tb_user_permissions에 레코드 생성
   ✅ request_status = 'approved'
   ✅ 사용자가 컨테이너 접근 가능
```

### 14.6 구현 요약

| 기능 | 상태 | 설명 |
|------|------|------|
| 권한 요청 생성 | ✅ 완료 | 사용자가 컨테이너 접근 권한 요청 |
| 요청 사유 입력 | ✅ 완료 | 최소 10자 이상 필수 입력 |
| 승인자 자동 식별 | ✅ 완료 | ADMIN/MANAGER/OWNER 자동 식별 |
| 승인 대기 목록 | ✅ 완료 | 관리자별 관리 범위 필터링 |
| 관계 데이터 로딩 | ✅ 완료 | 요청자/컨테이너 정보 표시 |
| 승인 처리 | ✅ 완료 | 권한 부여 및 상태 업데이트 |
| 거부 처리 | ✅ 완료 | 거부 사유와 함께 상태 업데이트 |
| 타입 변환 수정 | ✅ 완료 | request_id string→int 변환 |
| 필드 매핑 수정 | ✅ 완료 | 백엔드/프론트엔드 필드 호환 |

### 14.7 향후 개발 계획

| 기능 | 우선순위 | 설명 |
|------|---------|------|
| 알림 시스템 | 높음 | 요청/승인/거부 시 이메일/푸시 알림 |
| 자동 승인 규칙 | 중간 | 특정 조건 충족 시 자동 승인 |
| 요청 만료 처리 | 중간 | 일정 기간 미처리 시 자동 만료 |
| 일괄 승인/거부 | 중간 | 여러 요청 동시 처리 |
| 요청 히스토리 | 낮음 | 승인/거부 이력 조회 |


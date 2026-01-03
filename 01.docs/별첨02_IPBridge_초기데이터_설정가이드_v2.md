# 별첨02 - IPBridge 초기 데이터 설정 가이드

## 📋 문서 개요

### 목적

IPBridge(AI Based Enterprise Knowledge Management) 초기 데이터를 **CSV 파일 기반**으로 관리하여:
- ✅ 비개발자도 데이터 수정 가능
- ✅ 코드 변경 없이 데이터 구조 변경
- ✅ 버전 관리 및 이력 추적
- ✅ 다른 환경에 동일한 데이터 적용

### 적용 범위

- CSV 기반 초기 데이터 관리
- 조직 구조 기반 지식 컨테이너 생성
- SAP HR 정보 연동
- 사용자 계정 및 권한 관리
- 지식 카테고리 체계 구축
- 역할 기반 접근 제어 (RBAC) 설정

### 문서 버전

- **버전**: 3.2
- **최종 업데이트**: 2025-11-17
- **작성자**: 시스템 관리팀
- **검토자**: IT운영팀

### 주요 변경 사항 (v3.2) - 2025-11-17

- ✅ **Alembic 마이그레이션 절차 추가** - 데이터베이스 스키마 생성 가이드
- ✅ **실제 데이터 로딩 결과 업데이트** - 2025-11-17 실행 결과 반영
- ✅ **데이터베이스 상태 검증 스크립트 추가** - 38개 테이블 확인 방법
- ✅ **지식관리자 API 변경사항 반영** - managed-scope-permissions API
- ✅ **TwelveLabs Marengo 임베딩 모델 정보 추가** - AWS 멀티모달 임베딩
- ✅ **로그인 계정 정보 업데이트** - 실제 사용 가능한 계정 목록
- ✅ **로그인 검증 체크리스트 추가** - 권한별 접근 제어 확인

### 주요 변경 사항 (v3.1) - 2025-11-04

- ✅ **권한 검증 체크리스트 추가** - 시스템관리자/지식관리자/사용자 권한 검증
- ✅ **사용자 컨테이너 자동 권한 부여 규칙 문서화** (OWNER/ADMIN 자동 할당)
- ✅ **초기 데이터 검증 결과 추가** - 12개 컨테이너 전체 검증 완료
- ✅ **권한 계층 및 상속 규칙 명시** - CASCADING/SELECTIVE 규칙 설명

### 주요 변경 사항 (v3.0)

- ✅ **CSV 기반 데이터 관리 체계로 전환** (코드 → CSV)
- ✅ `backend/data/` 디렉토리 구조 개편
- ✅ 검증 스크립트 분리 (`validate_initial_data.py`)
- ✅ Seeder 스크립트 모듈화 (`seeds/` 디렉토리)
- ✅ 통합 실행기 제공 (`run_all_seeders.py`)
- ✅ 데이터 수정 = CSV 편집 (코드 수정 불필요)
- ✅ **문서 유형(DOCUMENT_TYPE) 체계 정립** - common_codes.csv 추가
  - 실제 구현된 처리 파이프라인만 정의 (일반문서, 학술논문, 특허)
  - 기술보고서/업무문서/프레젠테이션 → 일반문서로 통합
  - 프론트엔드 업로드 화면 자동 연동

---

## 🎯 설계 철학

### CSV 기반 데이터 관리

```
┌─────────────────┐
│  CSV 파일       │  ← 단일 진실 소스 (Single Source of Truth)
│  (데이터 정의)  │     사용자가 직접 편집
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 검증 스크립트   │  ← 데이터 정합성 검증
│ (validate)      │     문제 조기 발견
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Seeder          │  ← DB 적재 로직
│ (단순 적재)     │     CSV → DB 변환
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PostgreSQL DB   │
└─────────────────┘
```

### 핵심 원칙

1. **데이터 수정 = CSV 편집** (코드 수정 X)
2. **검증 먼저, 적재 나중**
3. **선언적 데이터 관리**
4. **외래키 순서 준수** (시스템 → HR → 사용자 → 컨테이너 → 권한)

---

## 🗂️ 디렉토리 구조

### backend/data/ 구조 (2025-10-27 기준)

```
backend/data/
├── README.md                          # 📘 완전한 사용 가이드 (790줄)
├── validate_initial_data.py           # 🔍 검증 스크립트 (484줄)
│
├── csv/                               # 📂 CSV 데이터 파일 (단일 진실 소스)
│   ├── users.csv                      # 사용자 계정 (9명)
│   ├── sap_hr_info.csv               # SAP HR 조직 정보 (9명)
│   ├── knowledge_containers.csv      # 컨테이너 트리 구조 (12개)
│   ├── user_permissions.csv          # 사용자별 컨테이너 권한
│   ├── user_roles.csv                # 역할 정의 (ADMIN, MANAGER, EDITOR, VIEWER)
│   ├── categories.csv                # 지식 카테고리
│   └── common_codes.csv              # 공통 코드
│
└── seeds/                             # 🌱 Seeder 스크립트 (DB 적재)
    ├── base_seeder.py                # 공통 적재 로직
    ├── system_seeder.py              # 시스템 데이터 (공통코드, 카테고리)
    ├── hr_seeder.py                  # SAP HR 정보
    ├── user_seeder.py                # 사용자 계정
    ├── container_seeder.py           # 지식 컨테이너
    ├── permission_seeder.py          # 권한 및 역할
    └── run_all_seeders.py            # 🚀 전체 통합 실행기 (167줄)
```

### 데이터 흐름

```
1. CSV 편집 (csv/*.csv)
   ↓
2. 검증 실행 (validate_initial_data.py)
   ↓ (검증 통과)
3. Seeder 실행 (run_all_seeders.py)
   ↓
4. PostgreSQL DB 적재
```

---

## 📄 CSV 데이터 파일 상세

### 1. users.csv

**목적**: 사용자 계정 정보 정의

**필수 컬럼**:
```csv
emp_no,username,email,password_plain,password_hash,is_active,is_admin,failed_login_attempts,created_date,last_modified_date
```

**샘플 데이터**:
```csv
ADMIN001,admin,admin@woongjin.co.kr,admin123!,$2b$12$...,true,true,0,2025-09-30 13:00:00,2025-09-30 13:00:00
HR001,hr.manager,hr.manager@woongjin.co.kr,hr123!,$2b$12$...,true,false,0,2025-09-30 13:00:00,2025-09-30 13:00:00
REC001,recruit,recruit@woongjin.co.kr,recruit123!,$2b$12$...,true,false,0,2025-09-30 13:00:00,2025-09-30 13:00:00
```

**주의사항**:
- `password_hash`: bcrypt로 암호화된 값 (bcrypt.hashpw)
- `is_admin`: 시스템 관리자만 `true` (ADMIN001)
- `emp_no`: SAP HR 정보와 반드시 일치해야 함
- `password_plain`: 개발용, 운영 환경에서는 제거 권장

**현재 등록된 사용자 (10명)** - 2025-11-17 기준:
| emp_no | username | 역할 | 소속 | 비밀번호 |
|--------|----------|------|------|---------|
| ADMIN001 | admin | 시스템 관리자 | IT운영팀 | admin123! |
| HR001 | hr.manager | 팀장 | 인사전략팀 | hr123! |
| REC001 | recruit | 선임 | 채용팀 | recruit123! |
| TRN001 | training | 선임 | 교육팀 | training123! |
| PLN001 | planning | 팀장 | 기획팀 | planning123! |
| CLD001 | cloud | 팀장 | 클라우드서비스팀 | cloud123! |
| MSS001 | ms.service | 팀장 | MS서비스팀 | ms123! |
| INF001 | infra | 팀장 | 인프라컨설팅팀 | infra123! |
| BIZ001 | biz.ops | 팀장 | Biz운영1팀 | biz123! |
| 77107791 | user.staff | 팀원 | MS서비스팀 | staff2025 |

---

### 2. sap_hr_info.csv

**목적**: SAP HR 조직 정보

**필수 컬럼**:
```csv
emp_no,emp_nm,dept_cd,dept_nm,postn_cd,postn_nm,email,telno,mbtlno,entrps_de,rsgntn_de,emp_stats_cd,del_yn,created_by,created_date
```

**조직 코드 매핑**:
| 조직 코드 | 조직명 | 컨테이너 ID | 레벨 |
|----------|--------|-------------|------|
| CEO000 | CEO직속 | WJ_CEO | DIVISION |
| HR100 | 인사전략팀 | WJ_HR | DEPARTMENT |
| HR110 | 채용팀 | WJ_RECRUIT | TEAM |
| HR120 | 교육팀 | WJ_TRAINING | TEAM |
| PLN100 | 기획팀 | WJ_PLANNING | DEPARTMENT |
| WJ200 | 클라우드사업본부 | WJ_CLOUD | DIVISION |
| CLD100 | 클라우드서비스팀 | WJ_CLOUD_SERVICE | DEPARTMENT |
| MSS100 | MS서비스팀 | WJ_MS_SERVICE | DEPARTMENT |
| WJ300 | CTI사업본부 | WJ_CTI | DIVISION |
| INF100 | 인프라컨설팅팀 | WJ_INFRA_CONSULT | DEPARTMENT |
| BIZ100 | Biz운영1팀 | WJ_BIZ_OPS1 | DEPARTMENT |

**샘플 데이터**:
```csv
ADMIN001,시스템관리자,IT000,IT운영팀,ADM,시스템관리자,admin@woongjin.co.kr,02-1234-5678,010-1234-5678,2020-01-01,,,1,N,SYSTEM,2025-09-30
HR001,김인사,HR100,인사전략팀,MGR,팀장,hr.manager@woongjin.co.kr,02-1234-5679,010-1234-5679,2021-03-15,,,1,N,SYSTEM,2025-09-30
```

---

### 3. knowledge_containers.csv

**목적**: 계층적 컨테이너 트리 구조 정의

**필수 컬럼**:
```csv
container_id,container_name,parent_container_id,container_type,sap_org_code,org_level,org_path,permission_inheritance_type,auto_assign_by_org,require_approval_for_access,is_active,created_by,created_date
```

**컨테이너 타입**:
- `COMPANY`: 회사 레벨 (WJ_ROOT)
- `DIVISION`: 본부 레벨 (WJ_CEO, WJ_CLOUD, WJ_CTI)
- `DEPARTMENT`: 부서 레벨 (WJ_HR, WJ_PLANNING 등)
- `TEAM`: 팀 레벨 (WJ_RECRUIT, WJ_TRAINING)

**트리 구조** (12개 컨테이너):
```
WJ_ROOT (COMPANY, level=1)
├── WJ_CEO (DIVISION, level=2)
│   ├── WJ_HR (DEPARTMENT, level=3)
│   │   ├── WJ_RECRUIT (TEAM, level=4)
│   │   └── WJ_TRAINING (TEAM, level=4)
│   └── WJ_PLANNING (DEPARTMENT, level=3)
├── WJ_CLOUD (DIVISION, level=2)
│   ├── WJ_CLOUD_SERVICE (DEPARTMENT, level=3)
│   └── WJ_MS_SERVICE (DEPARTMENT, level=3)
└── WJ_CTI (DIVISION, level=2)
    ├── WJ_INFRA_CONSULT (DEPARTMENT, level=3)
    └── WJ_BIZ_OPS1 (DEPARTMENT, level=3)
```

**중요 필드**:
- `org_level`: 계층 깊이 (1=COMPANY, 2=DIVISION, 3=DEPARTMENT, 4=TEAM)
- `org_path`: 전체 경로 (예: `/WJ_ROOT/WJ_CEO/WJ_HR`)
- `parent_container_id`: 부모 컨테이너 (ROOT는 빈 값)
- `permission_inheritance_type`: CASCADING (상위→하위 권한 상속)
- `auto_assign_by_org`: true (조직 기반 자동 할당)

**샘플 데이터**:
```csv
WJ_ROOT,지식관리루트,,COMPANY,,1,/WJ_ROOT,CASCADING,true,false,true,SYSTEM,2025-09-30
WJ_CEO,CEO직속,WJ_ROOT,DIVISION,CEO000,2,/WJ_ROOT/WJ_CEO,CASCADING,true,true,true,SYSTEM,2025-09-30
WJ_HR,인사전략팀,WJ_CEO,DEPARTMENT,HR100,3,/WJ_ROOT/WJ_CEO/WJ_HR,CASCADING,true,false,true,SYSTEM,2025-09-30
```

---

### 4. user_permissions.csv

**목적**: 사용자별 컨테이너 접근 권한 정의

**필수 컬럼**:
```csv
user_emp_no,container_id,role_id,permission_type,permission_level,access_scope,granted_by,granted_date,is_active
```

**권한 타입**:
| 권한 | 설명 | 가능 작업 |
|------|------|-----------|
| `ADMIN` | 관리자 | 생성, 읽기, 수정, 삭제, 권한 관리 |
| `MANAGER` | 관리자 | 생성, 읽기, 수정, 삭제 |
| `EDITOR` | 편집자 | 생성, 읽기, 수정 |
| `VIEWER` | 조회자 | 읽기만 가능 |

**권한 할당 원칙**:
1. **ADMIN001**: 모든 컨테이너에 `ADMIN` 권한 (필수)
2. **팀장**: 소속 컨테이너에 `MANAGER` 권한
3. **팀원**: 소속 컨테이너에 `EDITOR` 권한

**샘플 데이터**:
```csv
ADMIN001,WJ_ROOT,1,ADMIN,10,ALL,SYSTEM,2025-09-30,true
ADMIN001,WJ_CEO,1,ADMIN,10,ALL,SYSTEM,2025-09-30,true
HR001,WJ_HR,2,MANAGER,8,DEPARTMENT,ADMIN001,2025-09-30,true
REC001,WJ_RECRUIT,3,EDITOR,6,TEAM,ADMIN001,2025-09-30,true
```

---

### 5. user_roles.csv

**목적**: 역할 정의 및 권한 레벨 설정

**필수 컬럼**:
```csv
role_id,role_name,role_description,permission_level,can_create,can_read,can_update,can_delete,can_manage_permissions
```

**기본 역할** (4개):
| role_id | role_name | permission_level | 권한 |
|---------|-----------|------------------|------|
| 1 | ADMIN | 10 | 모든 권한 + 권한 관리 |
| 2 | MANAGER | 8 | CRUD 모두 가능 |
| 3 | EDITOR | 6 | CRU 가능 (삭제 불가) |
| 4 | VIEWER | 2 | R만 가능 |

---

### 6. categories.csv

**목적**: 지식 카테고리 체계 정의

**현재 상태**: ⚠️ **프론트엔드에서 미사용** (하드코딩으로 대체됨)

**필수 컬럼**:
```csv
category_id,category_name,parent_category_id,category_level,category_path,description,icon,is_active
```

**기본 카테고리**:
- 업무문서
- 기술문서
- 교육자료
- 프로젝트
- 연구개발
- 경영전략

**⚠️ 주의사항**:
현재 프론트엔드 업로드 화면에서는 이 CSV 데이터를 사용하지 않고, 
하드코딩된 카테고리 목록(일반, 인사, 재무, 마케팅, 기술, 법무, 교육)을 사용합니다.
향후 동적 카테고리 관리가 필요한 경우 API 연동을 추가해야 합니다.

---

### 7. common_codes.csv

**목적**: 시스템 전역 공통 코드 관리

**필수 컬럼**:
```csv
grp_cd,item_cd,item_nm,item_desc,sort_ord,use_yn,created_by,created_date
```

**주요 코드 그룹**:
- `CONTAINER_TYPE`: COMPANY, DIVISION, DEPARTMENT, TEAM
- `PERMISSION_LEVEL`: ADMIN, MANAGER, EDITOR, VIEWER
- `DOCUMENT_TYPE`: general, academic_paper, patent (✅ **실제 사용 중**)
- `ACCESS_LEVEL`: PUBLIC, INTERNAL, RESTRICTED, CONFIDENTIAL
- `EMP_STATUS`: ACTIVE, RETIRED, LEAVE

#### **📌 문서 유형 (DOCUMENT_TYPE) 상세**

**용도**: 업로드된 문서의 **처리 파이프라인**을 결정

**코드 정의** (2025-10-27 기준):
```csv
DOCUMENT_TYPE,general,일반 문서,기타 일반 문서 (기술보고서/업무문서/프레젠테이션 포함),1,Y,SYSTEM,2025-10-27
DOCUMENT_TYPE,academic_paper,학술 논문,Journal/Conference paper 전용 처리 파이프라인,2,Y,SYSTEM,2025-10-27
DOCUMENT_TYPE,patent,특허 문서,특허 서지정보 추출 전용 파이프라인 (향후 구현),3,Y,SYSTEM,2025-10-27
```

**문서 유형별 처리 차이**:

| 문서 유형                      | 아이콘 | 처리 파이프라인              | 추출 기능                               | 구현 상태    |
| -------------------------- | --- | --------------------- | ----------------------------------- | -------- |
| **일반 문서** (general)        | 📄  | GeneralPipeline       | 기본 텍스트/이미지 추출                       | ✅ 구현됨    |
| **학술 논문** (academic_paper) | 📚  | AcademicPaperPipeline | Figure/Table 캡션, References, 섹션 구조화 | ✅ 구현됨    |
| **특허 문서** (patent)         | 📜  | PatentPipeline        | Claims, 인용특허, 서지정보                  | 🔜 향후 구현 |

**프론트엔드 업로드 화면 연동**:
- API: `/api/v1/documents/document-types`
- 사용자가 선택한 문서 유형에 따라 자동으로 처리 옵션이 설정됨
- 예: 학술 논문 선택 시 → `extract_figures: true`, `parse_references: true` 자동 적용

**categories.csv vs DOCUMENT_TYPE 차이**:
- **categories.csv**: 문서 분류 (주제/분야별) - 현재 미사용
- **DOCUMENT_TYPE**: 처리 파이프라인 결정 (구조/형식별) - 실제 사용 중

---

## 🔧 초기 데이터 적재 프로세스

### 실행 순서 (외래키 순서 준수)

```
1단계: 시스템 기본 데이터
   ├─ common_codes.csv → tb_cmns_cd_grp_item
   └─ categories.csv → tb_knowledge_categories
      ↓
2단계: SAP HR 정보
   └─ sap_hr_info.csv → tb_sap_hr_info
      ↓
3단계: 사용자 정보
   └─ users.csv → tb_user
      ↓
4단계: 지식 컨테이너
   └─ knowledge_containers.csv → tb_knowledge_containers
      ↓
5단계: 권한 및 역할
   ├─ user_roles.csv → tb_user_roles
   └─ user_permissions.csv → tb_user_permissions
```

### 전체 실행 명령

#### 1. 검증 실행 (필수)

```bash
cd /home/wjadmin/Dev/InsightBridge/backend

# 데이터 검증
python -m data.validate_initial_data

# 출력 예시:
# 🌲 컨테이너 트리 구조 검증 중...
#    ✅ 필수 컨테이너 12개 모두 존재
#    ✅ 부모 컨테이너 참조 무결성 통과
#    ✅ 계층 구조 검증 통과
# 
# 🔐 ADMIN001 권한 검증 중...
#    ✅ ADMIN001이 모든 12개 컨테이너에 ADMIN 권한 보유
# 
# ✅ 모든 검증 통과!
```

#### 2. 데이터 적재 실행

```bash
cd /home/wjadmin/Dev/InsightBridge/backend

# 전체 Seeder 실행
python -m data.seeds.run_all_seeders

# 또는 개별 실행
python -m data.seeds.system_seeder      # 시스템 데이터
python -m data.seeds.hr_seeder          # SAP HR
python -m data.seeds.user_seeder        # 사용자
python -m data.seeds.container_seeder   # 컨테이너
python -m data.seeds.permission_seeder  # 권한
```

#### 3. 실행 로그 예시

```

## ✅ 3. 실행 및 확인

### 3.1 데이터베이스 마이그레이션 (필수 선행 작업)

**목적**: 데이터베이스 스키마 생성 및 테이블 초기화

```

bash
# 1. 가상환경 활성화
cd /home/admin/Dev/abekm/backend
source /home/admin/Dev/abekm/.venv/bin/activate

# 2. Alembic 마이그레이션 실행

alembic upgrade head

# 3. 마이그레이션 결과 확인

# ✅ Total tables created: 38

# ✅ Alembic version: 20251114_003 (최신)

```

**마이그레이션 주요 내용**:
- 초기 스키마 생성 (300c1a2a7c7f)
- 멀티모달 검색 지원 (CLIP, TwelveLabs Marengo)
- 벡터 차원 변경 (1024→1536 for text-embedding-3-small)
- 한국어/영어 혼합 검색 지원
- 권한 요청 테이블 생성
- AWS 멀티모달 임베딩 (TwelveLabs Marengo Embed 3.0, 512d)

**⚠️ 주의사항**:
- pgvector 0.5.1: 최대 2000차원 지원
- Korean FTS configuration 자동 생성
- 마이그레이션 실패 시 데이터베이스 완전 초기화 필요

### 3.2 데이터베이스 상태 검증

```

bash
cd /home/admin/Dev/abekm/backend
source /home/admin/Dev/abekm/.venv/bin/activate

python -c "
import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect('postgresql://wkms:wkms123@localhost:5432/wkms')
    
    # 테이블 개수
    count = await conn.fetchval('''
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
    ''')
    print(f'✅ Total tables: {count}')
    
    # 주요 테이블 확인
    key_tables = ['tb_user', 'tb_sap_hr_info', 'tb_knowledge_containers',
                  'tb_user_permissions', 'doc_chunk', 'doc_embedding']
    for table in key_tables:
        exists = await conn.fetchval(f'''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table}'
            )
        ''')
        print(f'  {\"✓\" if exists else \"✗\"} {table}')
    
    await conn.close()

asyncio.run(check())
"

# 예상 출력:

# ✅ Total tables: 38

#   ✓ tb_user

#   ✓ tb_sap_hr_info

#   ✓ tb_knowledge_containers

#   ✓ tb_user_permissions

#   ✓ doc_chunk

#   ✓ doc_embedding

```

### 3.3 초기 데이터 로딩

```

bash
cd /home/admin/Dev/abekm/backend
source /home/admin/Dev/abekm/.venv/bin/activate

# 전체 시드 데이터 실행

python data/seeds/run_all_seeders.py

# 실행 시 확인 메시지

# 기존 데이터를 삭제하고 다시 로드하시겠습니까? (y/N): y

```

**실제 실행 결과** (2025-11-17 기준):

```

2025-11-17 17:11:54 - INFO - 🚀 WKMS 마스터 데이터 초기화 시작...
============================================================
📋 1단계: 시스템 기본 데이터 로딩...
   ✅ common_codes.csv 로드 완료: 36개 레코드
   ✅ tb_cmns_cd_grp_item: 36개 삽입, 0개 스킵
   ✅ categories.csv 로드 완료: 13개 레코드
   ✅ tb_knowledge_categories: 13개 삽입, 0개 스킵

🏢 2단계: SAP HR 조직 정보 로딩...
   ✅ sap_hr_info.csv 로드 완료: 10개 레코드
   ✅ tb_sap_hr_info: 10개 삽입, 0개 스킵

👥 3단계: 사용자 정보 로딩...
   ✅ users.csv 로드 완료: 10개 레코드
   ✅ tb_user: 10개 삽입, 0개 스킵

📁 4단계: 지식 컨테이너 구조 생성...
   ✅ knowledge_containers.csv 로드 완료: 12개 레코드
   ✅ tb_knowledge_containers: 12개 삽입, 0개 스킵

🔐 5단계: 사용자 권한 및 역할 설정...
   ✅ user_roles.csv 로드 완료: 10개 레코드
   ✅ tb_user_roles: 10개 삽입, 0개 스킵
   ✅ user_permissions.csv 로드 완료: 30개 레코드
   ✅ tb_user_permissions: 30개 삽입, 0개 스킵

============================================================
🎉 WKMS 마스터 데이터 초기화 완료!
============================================================

📊 데이터 로딩 결과 요약:
   ✅ 공통 코드: 36개
   ✅ 지식 카테고리: 13개
   ✅ SAP HR 정보: 10개
   ✅ 사용자: 10개
   ✅ 지식 컨테이너: 12개
   ✅ 사용자 역할: 10개
   ✅ 사용자 권한: 30개

✅ 모든 시드 데이터 로딩이 성공적으로 완료되었습니다!

🔑 기본 로그인 정보:
   관리자: ADMIN001 / admin123!
   일반사용자: 77107791 / staff2025

💡 참고: 로그인 시 사번(emp_no)과 비밀번호를 입력하세요
```

### 3.4 로그인 테스트

**시스템관리자 로그인**:
```
사용자명: ADMIN001
비밀번호: admin123!
```

**지식관리자 로그인** (예: MS서비스팀장):
```
사용자명: MSS001
비밀번호: ms123!
```

**일반 사용자 로그인**:
```
사용자명: 77107791
비밀번호: staff2025
```

**로그인 검증 항목**:
- ✅ 인증 성공 (200 OK)
- ✅ 대시보드 접근
- ✅ 컨테이너 계층 조회
- ✅ 권한별 접근 제어 작동

---

## ✅ 권한 검증 체크리스트 (2025-11-04 업데이트)

### 📋 시스템관리자 권한 검증

**ADMIN001 필수 권한**: 모든 지식 컨테이너에 ADMIN 권한 보유

| 컨테이너 ID          | 컨테이너 명   | ADMIN001 권한      | 상태   |
| ---------------- | -------- | ---------------- | ---- |
| WJ_ROOT          | 웅진       | ADMIN (level 10) | ✅ 정상 |
| WJ_CEO           | CEO직속    | ADMIN (level 10) | ✅ 정상 |
| WJ_CLOUD         | 클라우드사업본부 | ADMIN (level 10) | ✅ 정상 |
| WJ_CTI           | CTI사업본부  | ADMIN (level 10) | ✅ 정상 |
| WJ_HR            | 인사전략팀    | ADMIN (level 10) | ✅ 정상 |
| WJ_PLANNING      | 기획팀      | ADMIN (level 10) | ✅ 정상 |
| WJ_CLOUD_SERVICE | 클라우드서비스팀 | ADMIN (level 10) | ✅ 정상 |
| WJ_MS_SERVICE    | MS서비스팀   | ADMIN (level 10) | ✅ 정상 |
| WJ_INFRA_CONSULT | 인프라컨설팅팀  | ADMIN (level 10) | ✅ 정상 |
| WJ_BIZ_OPS1      | Biz운영1팀  | ADMIN (level 10) | ✅ 정상 |
| WJ_RECRUIT       | 채용팀      | ADMIN (level 10) | ✅ 정상 |
| WJ_TRAINING      | 교육팀      | ADMIN (level 10) | ✅ 정상 |

**검증 결과**: ✅ **ADMIN001이 전체 12개 컨테이너에 ADMIN 권한 보유 확인**

---

### 📋 지식관리자 권한 검증

**부서/팀장 역할**: 담당 컨테이너 및 하위 컨테이너에 MANAGER 권한 보유

| 사용자        | 역할       | 담당 컨테이너               | 보유 권한        | 상태   |
| ---------- | -------- | --------------------- | ------------ | ---- |
| **HR001**  | 인사전략팀장   | WJ_HR                 | MANAGER      | ✅ 정상 |
|            |          | WJ_RECRUIT (하위)       | MANAGER (상속) | ✅ 정상 |
|            |          | WJ_TRAINING (하위)      | MANAGER (상속) | ✅ 정상 |
| **PLN001** | 기획팀장     | WJ_PLANNING           | MANAGER      | ✅ 정상 |
| **CLD001** | 클라우드본부장  | WJ_CLOUD              | MANAGER      | ✅ 정상 |
|            |          | WJ_CLOUD_SERVICE (하위) | MANAGER      | ✅ 정상 |
| **MSS001** | MS서비스팀장  | WJ_MS_SERVICE         | MANAGER      | ✅ 정상 |
|            |          | WJ_CLOUD (상위)         | VIEWER       | ✅ 정상 |
| **INF001** | CTI본부장   | WJ_CTI                | MANAGER      | ✅ 정상 |
|            |          | WJ_INFRA_CONSULT (하위) | MANAGER      | ✅ 정상 |
| **BIZ001** | Biz운영1팀장 | WJ_BIZ_OPS1           | MANAGER      | ✅ 정상 |
|            |          | WJ_CTI (상위)           | VIEWER       | ✅ 정상 |
| **REC001** | 채용팀장     | WJ_RECRUIT            | MANAGER      | ✅ 정상 |
|            |          | WJ_HR (상위)            | VIEWER       | ✅ 정상 |
| **TRN001** | 교육팀장     | WJ_TRAINING           | MANAGER      | ✅ 정상 |
|            |          | WJ_HR (상위)            | VIEWER       | ✅ 정상 |

**검증 결과**: ✅ **모든 지식관리자가 담당 컨테이너에 적절한 권한 보유 확인**

---

### 📋 일반 사용자 권한 검증

**팀원 역할**: 소속 컨테이너에 EDITOR 또는 VIEWER 권한 보유

| 사용자          | 역할        | 소속 컨테이너       | 보유 권한  | 상태   |
| ------------ | --------- | ------------- | ------ | ---- |
| **77107791** | MS서비스팀 팀원 | WJ_MS_SERVICE | EDITOR | ✅ 정상 |
|              |           | WJ_CLOUD (상위) | VIEWER | ✅ 정상 |

**검증 결과**: ✅ **일반 사용자가 소속 컨테이너에 적절한 권한 보유 확인**

---

### 📋 사용자 개인 컨테이너 권한 검증 (2025-11-04 구현)

**자동 권한 할당 규칙**:
1. **컨테이너 생성자**: OWNER 권한 자동 부여
2. **ADMIN001**: ADMIN 권한 자동 부여 (모든 사용자 컨테이너)

**사용자 컨테이너 패턴**: `USER_{emp_no}_{UUID}`

| 예시 컨테이너              | 생성자      | OWNER 권한 | ADMIN001 ADMIN 권한 | 상태 |
| -------------------- | -------- | -------- | ----------------- | -- |
| USER_HR001_abc123    | HR001    | ✅ 자동 부여  | ✅ 자동 부여           | 정상 |
| USER_CLD001_def456   | CLD001   | ✅ 자동 부여  | ✅ 자동 부여           | 정상 |
| USER_ADMIN001_xyz789 | ADMIN001 | ✅ 자동 부여  | ✅ 자동 부여           | 정상 |

**구현 코드** (`backend/app/services/knowledge_container.py`):
```python
async def create_user_container(container_data, creator_emp_no):
    # 1. 컨테이너 생성
    container = await create_container(container_data)
    
    # 2. 생성자에게 OWNER 권한 자동 부여
    await assign_permission(
        user_emp_no=creator_emp_no,
        container_id=container.container_id,
        permission_type="OWNER"
    )
    
    # 3. ADMIN001에게 ADMIN 권한 자동 부여
    await assign_permission(
        user_emp_no="ADMIN001",
        container_id=container.container_id,
        permission_type="ADMIN"
    )
```

**검증 결과**: ✅ **사용자 컨테이너 생성 시 OWNER/ADMIN 권한 자동 부여 확인**

---

### 📋 권한 계층 검증

**권한 레벨 정의** (`user_roles.csv`):
| 역할 | 권한 레벨 | 생성 | 읽기 | 수정 | 삭제 | 권한관리 |
|------|---------|------|------|------|------|---------|
| OWNER | 15 | ✅ | ✅ | ✅ | ✅ | ✅ |
| ADMIN | 10 | ✅ | ✅ | ✅ | ✅ | ✅ |
| MANAGER | 8 | ✅ | ✅ | ✅ | ✅ | ❌ |
| EDITOR | 6 | ✅ | ✅ | ✅ | ❌ | ❌ |
| VIEWER | 2 | ❌ | ✅ | ❌ | ❌ | ❌ |

**권한 상속 규칙**:
- **CASCADING**: 하위 컨테이너로 자동 권한 전파 (예: 본부장 → 팀 VIEWER)
- **SELECTIVE**: 명시적 권한 할당만 인정
- **NONE**: 권한 상속 없음

**검증 결과**: ✅ **권한 계층 구조 및 상속 규칙 정상 작동 확인**

---

### 📋 초기 데이터 검증 스크립트 실행 결과

**실행 명령**:
```bash
cd /home/admin/wkms-aws/backend
python -m data.validate_initial_data
```

**검증 결과**:
```
🌲 컨테이너 트리 구조 검증 중...
   ✅ 필수 컨테이너 12개 모두 존재
   ✅ 부모 컨테이너 참조 무결성 통과
   ✅ 계층 구조 검증 통과

🔐 ADMIN001 권한 검증 중...
   ✅ ADMIN001이 모든 12개 컨테이너에 ADMIN 권한 보유

👥 사용자-컨테이너 권한 검증 중...
   ✅ 모든 지식관리자가 담당 컨테이너 관리 권한 보유
   ✅ 권한 상속 규칙 정상 작동
   ✅ 외래키 무결성 검증 통과

✅ 모든 검증 통과!
```

**검증 항목 요약**:
1. ✅ 컨테이너 트리 구조 무결성
2. ✅ ADMIN001 전체 컨테이너 ADMIN 권한
3. ✅ 지식관리자 담당 컨테이너 MANAGER 권한
4. ✅ 일반 사용자 소속 컨테이너 EDITOR/VIEWER 권한
5. ✅ 권한 상속 규칙 (CASCADING, SELECTIVE)
6. ✅ 외래키 참조 무결성
7. ✅ 사용자 컨테이너 자동 권한 부여 (OWNER, ADMIN)

---

## 📝 데이터 수정 가이드

### CSV 파일 편집 방법

#### 1. Excel 또는 Google Sheets 사용

```
1. CSV 파일 열기
2. 데이터 수정
3. UTF-8 인코딩으로 저장
   - Excel: "CSV UTF-8(쉼표로 구분)(*.csv)" 형식 선택
   - Google Sheets: 파일 > 다운로드 > CSV(.csv)
```

#### 2. 주의사항

- ✅ **UTF-8 인코딩 필수** (한글 깨짐 방지)
- ✅ **컬럼 순서 유지** (헤더 행 순서 변경 금지)
- ✅ **빈 값 처리**: 빈 값은 빈 칸으로 남김 (NULL 문자열 X)
- ✅ **날짜 형식**: `YYYY-MM-DD HH:MM:SS` (예: 2025-09-30 13:00:00)
- ✅ **Boolean 값**: `true` 또는 `false` (소문자)

### 사용자 추가 예시

#### 1. sap_hr_info.csv에 추가

```csv
# 마지막 행에 추가
DEV001,개발자,CLD100,클라우드서비스팀,SEN,선임,dev@woongjin.co.kr,02-1234-5688,010-1234-5688,2025-11-01,,,1,N,SYSTEM,2025-10-27
```

#### 2. users.csv에 추가

```csv
# 마지막 행에 추가
DEV001,developer,dev@woongjin.co.kr,dev123!,$2b$12$xxxxxxxxxxxxxxx,true,false,0,2025-10-27 10:00:00,2025-10-27 10:00:00
```

**패스워드 해시 생성**:
```python
import bcrypt
password = "dev123!"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))
```

#### 3. user_permissions.csv에 추가

```csv
# 클라우드서비스팀 EDITOR 권한 부여
DEV001,WJ_CLOUD_SERVICE,3,EDITOR,6,DEPARTMENT,ADMIN001,2025-10-27,true
```

#### 4. 검증 및 적재

```bash
# 1. 검증
python -m data.validate_initial_data

# 2. 적재 (검증 통과 후)
python -m data.seeds.run_all_seeders --clear-existing
```

### 컨테이너 추가 예시

#### knowledge_containers.csv에 추가

```csv
# 새로운 팀 추가 (WJ_HR 하위에 복리후생팀)
WJ_WELFARE,복리후생팀,WJ_HR,TEAM,HR130,4,/WJ_ROOT/WJ_CEO/WJ_HR/WJ_WELFARE,CASCADING,true,false,true,SYSTEM,2025-10-27
```

**주의사항**:
- `parent_container_id`가 존재해야 함 (WJ_HR)
- `org_level`은 부모 + 1 (WJ_HR=3, TEAM=4)
- `org_path`는 부모 경로 + 자신 ID

---

## 🔍 검증 및 문제 해결

### validate_initial_data.py 검증 항목

#### 1. 컨테이너 트리 구조 검증

```python
# 검증 내용:
✅ 필수 컨테이너 12개 존재 여부
✅ 부모 컨테이너 참조 무결성 (parent_container_id)
✅ 계층 깊이 일치 (org_level vs org_path)
✅ ROOT 컨테이너 유일성 (parent_container_id 빈 값)
```

#### 2. ADMIN001 권한 검증

```python
# 검증 내용:
✅ ADMIN001이 모든 컨테이너에 ADMIN 권한 보유
✅ permission_type = 'ADMIN'
✅ permission_level = 10
✅ is_active = true
```

#### 3. 외래키 무결성 검증

```python
# 검증 내용:
✅ users.emp_no ∈ sap_hr_info.emp_no
✅ user_permissions.user_emp_no ∈ users.emp_no
✅ user_permissions.container_id ∈ knowledge_containers.container_id
✅ user_permissions.role_id ∈ user_roles.role_id
```

### 일반적인 오류 및 해결

#### 오류 1: 컨테이너 트리 구조 오류

```
❌ 잘못된 parent_container_id: {'WJ_INVALID'}
```

**해결**:
1. `knowledge_containers.csv` 열기
2. `parent_container_id` 컬럼에서 `WJ_INVALID` 검색
3. 올바른 부모 컨테이너 ID로 수정 (예: WJ_CEO → WJ_ROOT)

#### 오류 2: ADMIN001 권한 누락

```
❌ ADMIN001이 다음 컨테이너에 ADMIN 권한이 없습니다: ['WJ_HR', 'WJ_PLANNING']
```

**해결**:
1. `user_permissions.csv` 열기
2. ADMIN001의 누락된 컨테이너 권한 추가:
```csv
ADMIN001,WJ_HR,1,ADMIN,10,ALL,SYSTEM,2025-10-27,true
ADMIN001,WJ_PLANNING,1,ADMIN,10,ALL,SYSTEM,2025-10-27,true
```

#### 오류 3: 외래키 참조 오류

```
❌ 사용자 DEV001이 SAP HR 정보에 없습니다.
```

**해결**:
1. `sap_hr_info.csv`에 DEV001 정보 먼저 추가
2. 그 다음 `users.csv`에 추가

### 데이터베이스 초기화 (전체 삭제 후 재적재)

```bash
# 1. 데이터베이스 초기화
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_user_permissions CASCADE;"
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_user_roles CASCADE;"
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_knowledge_containers CASCADE;"
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_user CASCADE;"
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_sap_hr_info CASCADE;"
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_knowledge_categories CASCADE;"
psql -U postgres -d wkms_db -c "TRUNCATE TABLE tb_cmns_cd_grp_item CASCADE;"

# 2. 검증
python -m data.validate_initial_data

# 3. 재적재
python -m data.seeds.run_all_seeders
```

---

## ❓ FAQ

### Q1: CSV 파일을 수정했는데 변경사항이 반영되지 않습니다.

**A**: 데이터베이스를 초기화하거나 `--clear-existing` 옵션을 사용하세요.

```bash
# 옵션 1: clear-existing 플래그 사용
python -m data.seeds.run_all_seeders --clear-existing

# 옵션 2: 테이블 직접 초기화 후 재적재
# (위의 "데이터베이스 초기화" 섹션 참조)
```

### Q2: 새로운 조직을 추가하려면 어떻게 하나요?

**A**: 3개 CSV 파일을 순서대로 수정하세요.

```
1. sap_hr_info.csv       # SAP 조직 코드 추가
2. knowledge_containers.csv  # 컨테이너 추가
3. user_permissions.csv  # ADMIN001에 권한 추가 (필수!)
```

### Q3: 패스워드를 변경하려면?

**A**: `users.csv`의 `password_hash` 컬럼을 수정하세요.

```python
# 패스워드 해시 생성 스크립트
import bcrypt

new_password = "newpass123!"
hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
print(f"New hash: {hashed.decode('utf-8')}")

# 출력된 해시를 users.csv에 복사
```

### Q4: 검증 스크립트가 실패합니다. 어떻게 디버깅하나요?

**A**: 상세 로그를 확인하세요.

```bash
# 상세 로그 출력
python -m data.validate_initial_data --verbose

# 특정 검증만 실행
python -c "
from data.validate_initial_data import InitialDataValidator
validator = InitialDataValidator()
validator.validate_containers_tree()
"
```

### Q5: 운영 환경에 배포할 때 주의사항은?

**A**:
1. ✅ `password_plain` 컬럼 제거 (보안)
2. ✅ 초기 패스워드 변경 강제
3. ✅ ADMIN001 계정 이름 변경
4. ✅ CSV 파일 접근 권한 제한 (600)
5. ✅ 백업 후 적재

```bash
# CSV 파일 권한 설정 (읽기 전용)
chmod 600 backend/data/csv/*.csv

# 백업
cp -r backend/data/csv/ backend/data/csv_backup_$(date +%Y%m%d)/

# 적재
python -m data.seeds.run_all_seeders
```

---

## 📚 관련 문서

- `backend/data/README.md`: 완전한 사용 가이드 (790줄)
- `01.docs/별첨01_IPBridge_권한관리_체계_v2.md`: 권한 관리 상세
- `01.docs/01.system_overview_design.md`: 시스템 전체 아키텍처
- `01.docs/08.static_design_specification.md`: 데이터베이스 스키마

---

## 📊 부록: 전체 데이터 구조

### 데이터베이스 테이블 관계도

```
tb_cmns_cd_grp_item (공통코드)
tb_knowledge_categories (카테고리)
   ↓
tb_sap_hr_info (SAP HR)
   ↓ (emp_no FK)
tb_user (사용자)
   ↓ (user_emp_no FK)
tb_knowledge_containers (컨테이너)
   ↓ (container_id FK)
tb_user_roles (역할)
   ↓ (role_id FK)
tb_user_permissions (권한)
```

### CSV 파일 크기 및 레코드 수

| CSV 파일                   | 레코드 수 | 크기   |
| ------------------------ | ----- | ---- |
| common_codes.csv         | ~20   | ~2KB |
| categories.csv           | ~6    | ~1KB |
| sap_hr_info.csv          | 9     | ~2KB |
| users.csv                | 9     | ~3KB |
| knowledge_containers.csv | 12    | ~4KB |
| user_roles.csv           | 4     | ~1KB |
| user_permissions.csv     | ~50   | ~5KB |

---

**최종 업데이트**: 2025-10-27  
**문서 버전**: 3.0  
**변경 이력**: CSV 기반 데이터 관리 체계로 전면 개편

### 8단계: 시스템 설정 검증 (`verify_complete_setup()`)

#### 목적

초기 데이터 설정 완료 후 시스템 상태 검증 및 현황 출력

#### 검증 항목

- SAP HR 정보 개수 확인
- 사용자 계정 개수 확인
- 지식 컨테이너 유형별 개수 확인
- 지식 카테고리 개수 확인
- 사용자 역할 개수 확인
- 활성 권한 할당 개수 확인
- 샘플 문서 개수 확인
- 조직 구조 계층 출력
- 주요 권한 할당 현황 출력

---

## 📊 설정 완료 현황

### 최종 생성 데이터 통계 (2025-11-17 실행 결과)

- **데이터베이스 테이블**: 38개
- **공통 코드**: 36개
- **지식 카테고리**: 13개
- **SAP HR 정보**: 10명
- **사용자 계정**: 10개
- **지식 컨테이너**: 12개
  - COMPANY: 1개 (조직 최상위)
  - DIVISION: 3개 (CEO직속, 클라우드사업본부, CTI사업본부)
  - DEPARTMENT: 6개 (각 팀/부서)
  - TEAM: 2개 (채용팀, 교육팀)
- **사용자 역할**: 10개
- **권한 할당**: 30개

**마이그레이션 정보**:
- Alembic 버전: 20251114_003 (최신)
- pgvector 버전: 0.5.1 (최대 2000차원 지원)
- 벡터 차원: 1536d (text-embedding-3-small)
- 멀티모달 임베딩: 512d (TwelveLabs Marengo)

### 생성되는 조직구조

```
🏢 기업 조직
├── 📁 CEO직속
│   ├── 📁 인사전략팀
│   │   ├── 📁 채용팀
│   │   └── 📁 교육팀
│   └── 📁 기획팀
├── 📁 클라우드사업본부
│   ├── 📁 클라우드서비스팀
│   └── 📁 MS서비스팀
└── 📁 CTI사업본부
    ├── 📁 인프라컨설팅팀
    └── 📁 Biz운영1팀
```

### 포함되는 기능

✅ **SAP HR 정보** (9명의 직원 데이터)
✅ **사용자 계정** (9개 계정)
✅ **지식 컨테이너** (12개 조직 구조)
✅ **지식 카테고리** (4개 카테고리)
✅ **사용자 역할** (4단계 권한)
✅ **권한 할당** (RBAC 시스템)
✅ **샘플 문서** (3개 문서)

### 보안 및 접근 제어

- **패스워드 정책**: bcrypt 해싱, 특수문자 포함 8자 이상
- **권한 상속**: 계층적 권한 상속 체계
- **접근 제어**: 조직별, 역할별 세분화된 접근 권한
- **감사 로그**: 모든 권한 변경 및 접근 기록 추적

---

## 🔧 실행 방법

### 통합 스크립트 사용

#### 기본 실행 (기존 데이터 유지)

```bash
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate
python init_woongjin_master.py
```

#### 완전 초기화 후 재설정 (기존 데이터 삭제)

```bash
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate
python init_woongjin_master.py --reset
```

### 환경 준비

```bash
# 백엔드 디렉토리로 이동
cd /home/admin/wkms-aws/backend

# 가상환경 활성화
source ../.venv/bin/activate

# PostgreSQL 컨테이너 실행 확인
docker ps | grep postgres
```

### 실행 결과 확인

스크립트 실행 시 다음과 같은 단계별 로그가 출력됩니다:
```
🚀 IPBridge 마스터 초기 데이터 설정을 시작합니다...

1️⃣ SAP HR 정보 생성 중...
✅ SAP HR 정보 생성 완료

2️⃣ 사용자 계정 생성 중...
✅ 사용자 계정 생성 완료

3️⃣ 조직 지식 컨테이너 구조 생성 중...
✅ 조직 지식 컨테이너 구조 생성 완료

4️⃣ 지식 카테고리 체계 생성 중...
✅ 지식 카테고리 체계 생성 완료

5️⃣ 사용자 역할 정의 생성 중...
✅ 사용자 역할 정의 생성 완료

6️⃣ 사용자 권한 할당 중...
✅ 사용자 권한 할당 완료

7️⃣ 샘플 문서 생성 중...
✅ 샘플 문서 생성 완료

8️⃣ 시스템 설정 검증 중...
🏢 IPBridge 시스템 설정 검증:
   👥 SAP HR 정보: 9명
   🔐 사용자 계정: 9개
   📁 지식 컨테이너:
      DEPARTMENT: 6개
      DIVISION: 3개
      TEAM: 2개
      COMPANY: 1개
   📚 지식 카테고리: 4개
   🎭 사용자 역할: 4개
   🔒 권한 할당: 24개
   📄 샘플 문서: 3개

🎉 IPBridge 마스터 초기 데이터 설정이 완료되었습니다!
```

---

## 🔑 로그인 정보

### 🔐 시스템 관리자

- Username: `admin`
- Password: `admin123!`
- 권한: 전체 시스템 관리

### 👥 부서별 관리자

- **인사팀장**: `hr.manager` / `hr123!`
- **기획팀장**: `planning` / `planning123!`
- **클라우드팀장**: `cloud` / `cloud123!`
- **MS서비스팀장**: `ms.service` / `ms123!`
- **인프라팀장**: `infra` / `infra123!`
- **Biz운영팀장**: `biz.ops` / `biz123!`

### 👤 팀별 담당자  

- **채용담당**: `recruit` / `recruit123!`
- **교육담당**: `training` / `training123!`

### 보안 권고사항

- 초기 패스워드는 첫 로그인 후 즉시 변경 권장
- 패스워드 정책: 8자 이상, 영문+숫자+특수문자 조합
- 정기적인 패스워드 변경 (3개월 주기 권장)

---

## 🔄 다음 단계

### 1. API 서버 실행 및 테스트

```bash
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. API 문서 확인

- URL: http://localhost:8000/docs
- Swagger UI를 통한 API 테스트

### 3. 프론트엔드 연동 테스트

```bash
cd /home/admin/wkms-aws/frontend
npm start
```

### 4. 파일 업로드 및 벡터 검색 테스트

- 문서 업로드 기능 테스트
- pgvector 기반 유사도 검색 테스트
- 지식 추천 알고리즘 검증

### 5. SAP 연동 설정

- SAP RFC 연결 설정
- 조직도 동기화 스케줄 설정
- 사용자 정보 자동 업데이트 구성

---

## 🛠️ 유지보수 가이드

### 1. 데이터 백업

```bash
# PostgreSQL 데이터 백업
docker exec wkms-postgres pg_dump -U wkms -d wkms > wkms_backup_$(date +%Y%m%d).sql

# 파일 시스템 백업
tar -czf wkms_files_backup_$(date +%Y%m%d).tar.gz /home/admin/wkms-aws/uploads/
```

### 2. 권한 관리

- 정기적인 권한 검토 및 정리
- 퇴사자 계정 비활성화
- 조직 변경에 따른 권한 재할당

### 3. 성능 모니터링

- 데이터베이스 성능 모니터링
- 파일 저장소 용량 관리
- API 응답 시간 모니터링

### 4. 보안 점검

- 취약점 스캔 및 패치 적용
- 접근 로그 분석
- 비정상 접근 패턴 탐지

---

## ❓ FAQ (자주 묻는 질문)

### Q1. CSV 파일을 수정했는데 반영이 안 됩니다

**A1**: 다음 순서로 재실행하세요:
1. `python backend/data/validate_initial_data.py` (검증)
2. `python backend/data/seeds/run_all_seeders.py` (재적재)
3. 서버 재시작

### Q2. 조직 구조를 변경하려면 어떻게 하나요?

**A2**: `knowledge_containers.csv` 파일 수정:
- 새 컨테이너 추가: 새 행 추가
- 기존 컨테이너 수정: 해당 행 수정
- 계층 구조 변경: `parent_container_id` 변경

### Q3. 신규 사용자를 추가하려면?

**A3**: 
1. `sap_hr_info.csv`에 SAP 정보 추가
2. `users.csv`에 계정 정보 추가 (비밀번호는 bcrypt 해시)
3. `user_permissions.csv`에 권한 할당

### Q4. 운영 환경에 배포 시 주의사항은?

**A4**:
- 반드시 백업 먼저 수행
- 데이터 검증 스크립트 실행 필수
- 점검 시간대에 배포 권장
- 롤백 계획 준비

### Q5. 문서 유형(DOCUMENT_TYPE)과 카테고리(categories)의 차이는?

**A5**: 
- **문서 유형(DOCUMENT_TYPE)**: 문서 **처리 파이프라인** 결정 (✅ 실제 사용 중)
  - 예: 학술 논문 → Figure/Reference 자동 추출
  - 정의: `common_codes.csv`의 DOCUMENT_TYPE 그룹
  - 화면: 업로드 시 "문서 유형" 드롭다운 (📄 일반 문서, 📚 학술 논문, 📜 특허 문서)
  
- **카테고리(categories)**: 문서 **주제/분야** 분류 (⚠️ 현재 미사용)
  - 예: 기술문서, 업무문서, 교육자료
  - 정의: `categories.csv`
  - 화면: 하드코딩된 카테고리 목록 사용 (일반, 인사, 재무 등)

**권장**: 현재는 문서 유형(DOCUMENT_TYPE)만 사용하며, 카테고리는 향후 DB 연동 시 활성화 예정

### Q6. 지식관리자가 권한 조회 시 403 에러가 발생합니다.

**A6** (2025-11-17 업데이트):
- **원인**: 지식관리자는 전체 권한 조회 불가 (보안상 올바른 동작)
- **해결**: 프론트엔드가 자동으로 `managed-scope-permissions` API 사용
- **변경 내역**:
  ```
  변경 전: GET /api/v1/permissions/all-user-permissions (403 Forbidden)
  변경 후: GET /api/v1/permissions/managed-scope-permissions (200 OK)
  ```
- **동작**:
  - 시스템 관리자: 모든 권한 조회
  - 지식관리자: 관리하는 컨테이너 범위 내 권한만 조회
  - 응답 필드: `is_system_admin`, `managed_container_count`

### Q7. TwelveLabs Marengo 임베딩 모델은 무엇인가요?

**A7** (2025-11-17 추가):
- **용도**: AWS Bedrock 멀티모달 임베딩 (이미지+텍스트)
- **모델 ID**: `twelvelabs.marengo-embed-3-0-v1:0`
- **차원**: 512d (고효율 임베딩)
- **특징**:
  - 비디오/이미지/텍스트 멀티모달 지원
  - Twelve Labs 비디오 AI 전문 기술 기반
  - 시맨틱 검색, 객체 인식, 장면 이해 최적화
  - 한국어 텍스트 지원
  - ap-northeast-2(서울) 리전 교차 추론 지원
- **이전 모델**: cohere.embed-v4:0 (1024d, 128K 토큰, 128개 언어)
- **마이그레이션**: 20251114_003 버전에서 추가
- **환경 변수**: 
  ```
  BEDROCK_MULTIMODAL_EMBEDDING_MODEL_ID=twelvelabs.marengo-embed-3-0-v1:0
  BEDROCK_MULTIMODAL_EMBEDDING_DIMENSION=512
  ```

---

## 📞 문의 및 지원

### 기술 지원

- **담당팀**: IT운영팀
- **연락처**: 02-1234-5678
- **이메일**: admin@woongjin.co.kr

### 업무 지원

- **인사 관련**: 인사전략팀 (hr.manager@woongjin.co.kr)
- **시스템 문의**: 시스템관리자 (admin@woongjin.co.kr)

---

## 📋 변경 이력

| 버전  | 날짜         | 변경 내용                                                             | 작성자    |
| --- | ---------- | ----------------------------------------------------------------- | ------ |
| 1.0 | 2025-01-29 | 초기 문서 작성                                                          | 시스템관리팀 |
| 2.0 | 2025-07-30 | 통합 스크립트 반영, 중복 파일 정리, 실행 방법 업데이트                                  | 시스템관리팀 |
| 3.0 | 2025-10-27 | CSV 기반 데이터 관리 체계 전환, 문서 유형(DOCUMENT_TYPE) 체계 정립, FAQ 추가           | 시스템관리팀 |
| 3.1 | 2025-11-04 | 권한 검증 체크리스트 추가, 사용자 컨테이너 자동 권한 부여 규칙 문서화, 권한 검증 결과 추가             | 시스템관리팀 |
| 3.2 | 2025-11-17 | Alembic 마이그레이션 추가, 실제 실행 결과 업데이트, 지식관리자 API 변경, 데이터베이스 검증 스크립트 추가 | 시스템관리팀 |

---

*이 문서는 IPBridge 시스템의 초기 데이터 설정을 위한 공식 가이드입니다. 시스템 변경 시 본 문서도 함께 업데이트해 주시기 바랍니다.*

# IP 포트폴리오 시스템 개선 계획서

> **작성일**: 2026-01-04  
> **목적**: 기존 "지식 컨테이너"(조직도 기반) 개념을 **IPC 분류 체계 기반 IP 포트폴리오**로 재정의하여 "IP 포트폴리오" 메뉴로 제공 (조직도 컨테이너는 레거시/선택)  
> **기반**: IPC 관리 API(`/backend/app/api/v1/ipc.py`) + 특허 메타데이터(`tb_patent_metadata`) + (레거시) `/backend/app/api/v1/containers.py`

---

## 1. 현황 분석

### 1.1 기존 시스템 (지식 컨테이너)

**테이블 구조**:
- `tb_knowledge_containers`: 조직도 기반 계층 구조 (SAP 연동)
- `tb_file_bss_info`: 문서 메타데이터 (knowledge_container_id 매핑)
- `tb_user_permissions`: 컨테이너별 사용자 권한

**주요 API 엔드포인트** (`/backend/app/api/v1/containers.py`):
```
GET  /api/v1/containers/full-hierarchy       # 전체 컨테이너 트리 (권한 포함)
GET  /api/v1/containers/user-accessible      # 사용자 접근 가능 컨테이너 ID 목록
GET  /api/v1/containers/                     # 컨테이너 목록 조회 (페이징)
GET  /api/v1/containers/hierarchy            # 계층 구조 조회
GET  /api/v1/containers/{container_id}       # 상세 정보
POST /api/v1/containers/                     # 컨테이너 생성
PUT  /api/v1/containers/{container_id}       # 컨테이너 수정
DELETE /api/v1/containers/{container_id}     # 컨테이너 삭제

GET  /api/v1/containers/{container_id}/permissions        # 권한 목록
POST /api/v1/containers/{container_id}/permissions        # 권한 추가
PUT  /api/v1/containers/{container_id}/permissions/{user} # 권한 수정
DELETE /api/v1/containers/{container_id}/permissions/{user} # 권한 삭제
GET  /api/v1/containers/{container_id}/my-permission      # 내 권한 조회

POST /api/v1/containers/user/create         # 사용자 컨테이너 생성
DELETE /api/v1/containers/user/{container_id} # 사용자 컨테이너 삭제
```

**특징**:
- ✅ 조직도 기반 계층 구조 (SAP 연동)
- ✅ 세밀한 권한 관리 (ADMIN, MANAGER, EDITOR, VIEWER)
- ✅ 재귀 CTE 기반 트리 조회 최적화
- ⚠️ **특허/IP 관점 기능 부재** (IPC 분류, 특허 메타데이터, 법적상태 등)

### 1.2 신규 구현 (IPC 관리 API)

**테이블 구조**:
- `tb_ipc_code`: 국제특허분류 마스터 (8개 섹션 + 계층)
- `tb_patent_metadata`: 특허 메타데이터 (출원번호, 법적상태, IPC 코드 등)

**주요 API 엔드포인트** (`/backend/app/api/v1/ipc.py`):
```
GET  /api/v1/admin/ipc/codes                 # IPC 코드 목록 (필터링/검색)
GET  /api/v1/admin/ipc/codes/tree            # IPC 계층 트리
POST /api/v1/admin/ipc/codes                 # IPC 코드 추가
PATCH /api/v1/admin/ipc/codes/{code}         # IPC 코드 수정
GET  /api/v1/admin/ipc/codes/{code}          # IPC 상세 조회
GET  /api/v1/admin/ipc/statistics            # IPC 통계 (Top 20, 미분류 특허)
```

**특징**:
- ✅ IPC 표준 분류 체계 관리
- ✅ 계층 구조 트리 조회 (재귀 빌딩)
- ✅ 특허 메타데이터 연계 (tb_patent_metadata)
- ⚠️ **아직 containers.py와 통합되지 않음**

---

## 2. IP 포트폴리오 재정의 전략

### 2.1 핵심 개념 전환

| 기존 (지식 컨테이너) | 개선 (IP 포트폴리오) |
|---------------------|---------------------|
| 조직도 기반 폴더 (부서/팀) | **IPC/CPC 기술 분류** (국제 표준, 조직 독립) |
| 일반 문서 저장소 | **특허 문서 중심** (출원번호, 법적상태, 청구항) |
| 3단계 권한 (사용자/관리자/시스템관리자) | **2단계 권한 (사용자/시스템관리자)** ⭐ |
| 권한 요청 승인 워크플로우 | **직접 권한 할당** (빠른 액세스) |
| 단순 파일 개수 통계 | **IP 통계 (기술 분야별 특허 분포, 법적상태, 인용 관계)** |

### 2.2 권한 체계 단순화

**IP 포트폴리오 2단계 권한 체계** (지식 컨테이너 3단계 → IP 포트폴리오 2단계):

```
┌─────────────────────────────────────────────────────────┐
│         IP 포트폴리오 권한 체계 (Simple 2-Tier)         │
├─────────────────────────────────────────────────────────┤
│ 1️⃣ 사용자 (User)                                         │
│   - 할당된 IPC 범위 내 특허 조회/편집                     │
│   - 권한: VIEWER (조회), EDITOR (편집)                   │
│                                                          │
│ 2️⃣ 시스템관리자 (System Admin)                          │
│   - IPC 권한 직접 할당 (승인 프로세스 없음)               │
│   - IPC 코드 마스터 관리                                 │
│   - 권한: ADMIN                                          │
└─────────────────────────────────────────────────────────┘
```

**설계 근거**:
- ✅ 단순하고 명확한 권한 구조
- ✅ 관리 오버헤드 최소화
- ✅ 빠른 권한 할당 가능
- ⚠️ MANAGER 역할은 데이터 모델에 존재하지만 Phase 1에서는 UI 미제공
- 🔄 향후 권한 요청 승인 워크플로우 필요 시 MANAGER 역할 활성화 가능

### 2.3 통합 아키텍처 (2단계 권한 체계)

```
┌─────────────────────────────────────────────────────────────┐
│              IP 포트폴리오 시스템 (IPC 중심)                  │
├─────────────────────────────────────────────────────────────┤
│  IPC 분류/권한/특허 중심 (2단계 권한)                         │
│  ├─ IPC 코드 마스터: tb_ipc_code                             │
│  ├─ 특허 메타데이터: tb_patent_metadata                      │
│  ├─ IPC 권한: tb_ipc_permissions                             │
│  │   - role_id: ADMIN, EDITOR, VIEWER                        │
│  │   - MANAGER 역할은 Phase 2 이후 활성화 예정               │
│  ├─ 권한 서비스: IpcPermissionService                        │
│  └─ IP 포트폴리오 API: /api/v1/ip-portfolio/*               │
├─────────────────────────────────────────────────────────────┤
│  시스템 관리자 UI (Phase 1)                                  │
│  ├─ /admin/ipc-permissions: 사용자별 IPC 권한 할당            │
│  ├─ /admin/ipc/codes: IPC 코드 마스터 관리                    │
│  └─ 직접 권한 할당 (승인 프로세스 없음)                       │
├─────────────────────────────────────────────────────────────┤
│  (레거시/선택) 조직도 컨테이너/권한                           │
│  ├─ containers.py / tb_knowledge_containers                  │
│  └─ 기존 문서 저장/권한 모델 (필요 시 읽기 전용 유지)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 구체적 개선 방안

### 3.1 데이터 모델 확장

#### 3.1.1 IPC 권한 테이블 (신규)

```sql
-- IPC 코드별 사용자 권한 (IP 포트폴리오 접근 제어의 기준)
CREATE TABLE tb_ipc_permissions (
    permission_id SERIAL PRIMARY KEY,
    user_emp_no VARCHAR(20) NOT NULL REFERENCES tb_user(emp_no),
    ipc_code VARCHAR(20) NOT NULL REFERENCES tb_ipc_code(code),
    role_id VARCHAR(20) NOT NULL,            -- ADMIN/MANAGER/EDITOR/VIEWER
    access_scope VARCHAR(20) DEFAULT 'FULL', -- FULL/READ_ONLY/WRITE_ONLY
    include_children BOOLEAN DEFAULT true,   -- 하위 IPC까지 권한 적용
    valid_from TIMESTAMP DEFAULT now(),
    valid_until TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_date TIMESTAMP DEFAULT now(),
    created_by VARCHAR(20),
    UNIQUE(user_emp_no, ipc_code)
);

CREATE INDEX idx_ipc_perm_user ON tb_ipc_permissions(user_emp_no);
CREATE INDEX idx_ipc_perm_code ON tb_ipc_permissions(ipc_code);
CREATE INDEX idx_ipc_perm_active ON tb_ipc_permissions(is_active, valid_until);
```

**사용 시나리오**:
- 사용자에게 IPC "H"(전기) 또는 "H01M"(전기화학 셀) 권한을 부여
- 사용자는 해당 IPC(및 하위 코드)의 특허만 IP 포트폴리오에서 조회
- 조직 이동과 무관하게 기술 분야 기준으로 접근 제어 유지

#### 3.1.2 tb_patent_metadata 확장

```sql
-- 기존 tb_patent_metadata는 이미 생성됨 (2026-01-03)
-- IP 포트폴리오(IPC 중심)를 위해 최소 확장
ALTER TABLE tb_patent_metadata
ADD COLUMN legacy_container_id VARCHAR(50),            -- 레거시 조직 컨테이너 참조 보존
ADD COLUMN primary_ipc_section VARCHAR(10),            -- IPC 섹션/대분류 (A~H 등)
ADD COLUMN keywords TEXT[];                           -- 키워드 배열 (검색/필터용)

CREATE INDEX idx_patent_meta_ipc_section ON tb_patent_metadata(primary_ipc_section);
CREATE INDEX idx_patent_meta_keywords ON tb_patent_metadata USING gin(keywords);
CREATE INDEX idx_patent_meta_legacy_container ON tb_patent_metadata(legacy_container_id);
```

### 3.2 API 구성 (IPC 중심으로 전환)

#### 3.2.1 IP 포트폴리오 라우터 신설 (권장)

**신규 엔드포인트(안)**:
- `GET /api/v1/ip-portfolio/ipc-tree` : IPC 트리(권한 기반)
- `GET /api/v1/ip-portfolio/patents` : IPC/섹션/상태/연도/키워드 필터 특허 목록
- `GET /api/v1/ip-portfolio/patents/{metadata_id}` : 특허 상세
- `GET /api/v1/ip-portfolio/statistics` : 사용자 권한 범위 내 통계
- (관리자) `POST/PUT/DELETE /api/v1/admin/ipc-permissions/*` : IPC 권한 관리

**레거시 처리**:
- `/api/v1/containers/*` 는 "IP 포트폴리오" 메뉴의 주 API가 아니라 **레거시(조직 문서용)로 분리/Deprecated**
    if include_ipc:
        # IPC 매핑 정보 조회
        ipc_query = """
        SELECT ipc.code, ipc.description_kr, ipc.section, 
               m.custom_label, m.is_primary,
               COUNT(p.metadata_id) as patent_count
        FROM tb_container_ipc_mapping m
        JOIN tb_ipc_code ipc ON m.ipc_code = ipc.code
        LEFT JOIN tb_patent_metadata p ON p.main_ipc_code = ipc.code 
            AND p.container_id = :container_id
        WHERE m.container_id = :container_id
        GROUP BY ipc.code, ipc.description_kr, ipc.section, 
                 m.custom_label, m.is_primary
        ORDER BY m.is_primary DESC, patent_count DESC
        """
        ipc_result = await db.execute(text(ipc_query), {"container_id": container_id})
        ipc_mappings = [dict(row) for row in ipc_result]
        
    if include_patent_stats:
        # 특허 통계 조회
        stats_query = """
        SELECT 
            COUNT(*) as total_patents,
            COUNT(CASE WHEN patent_status = '등록' THEN 1 END) as registered_count,
            COUNT(CASE WHEN patent_status = '공개' THEN 1 END) as published_count,
            COUNT(CASE WHEN patent_status = '거절' THEN 1 END) as rejected_count,
            EXTRACT(YEAR FROM MIN(application_date)) as earliest_year,
            EXTRACT(YEAR FROM MAX(application_date)) as latest_year
        FROM tb_patent_metadata
        WHERE container_id = :container_id
        """
        stats_result = await db.execute(text(stats_query), {"container_id": container_id})
        patent_stats = dict(stats_result.first())
    
    return {
        **container_info,  # 기존 컨테이너 정보
        "ipc_classifications": ipc_mappings if include_ipc else [],
        "patent_statistics": patent_stats if include_patent_stats else {}
    }
```

#### 3.2.2 IP 포트폴리오 문서 조회 (IPC 필터링)

**신규 엔드포인트**:
```python
# GET /api/v1/containers/{container_id}/patents (신규)

@router.get("/{container_id}/patents", response_model=IPPortfolioPatentsResponse)
async def get_ip_portfolio_patents(
    container_id: str,
    ipc_code: Optional[str] = Query(None, description="IPC 코드 필터 (예: H01M)"),
    ipc_section: Optional[str] = Query(None, description="IPC 섹션 필터 (A~H)"),
    patent_status: Optional[str] = Query(None, description="법적상태 필터 (등록/공개/거절)"),
    year_from: Optional[int] = Query(None, description="출원연도 시작"),
    year_to: Optional[int] = Query(None, description="출원연도 종료"),
    keyword: Optional[str] = Query(None, description="키워드 검색"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    IP 포트폴리오 내 특허 목록 조회 (IPC 필터링 지원)
    
    필터:
    - IPC 코드: 특정 기술 분야 (예: H01M - 전기화학 셀)
    - IPC 섹션: 대분류 (A=생활필수품, B=처리조작, ..., H=전기)
    - 법적상태: 등록/공개/거절/소멸
    - 출원연도: 범위 지정
    - 키워드: 특허명/요약 전문 검색
    """
    # 권한 확인
    permission_service = PermissionService(db)
    has_access = await permission_service.check_container_access(
        current_user.emp_no, container_id, "READ"
    )
    if not has_access:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    
    # 동적 필터 빌딩
    filters = [TbPatentMetadata.container_id == container_id]
    
    if ipc_code:
        # 특정 IPC 코드 또는 하위 코드 (예: H01M → H01M10, H01M12 등)
        filters.append(or_(
            TbPatentMetadata.main_ipc_code == ipc_code,
            TbPatentMetadata.ipc_codes.any(ipc_code)  # PostgreSQL array contains
        ))
    
    if ipc_section:
        filters.append(TbPatentMetadata.primary_ipc_section == ipc_section)
    
    if patent_status:
        filters.append(TbPatentMetadata.patent_status == patent_status)
    
    if year_from:
        filters.append(extract('year', TbPatentMetadata.application_date) >= year_from)
    
    if year_to:
        filters.append(extract('year', TbPatentMetadata.application_date) <= year_to)
    
    if keyword:
        # 특허명 또는 요약에서 키워드 검색
        filters.append(or_(
            TbPatentMetadata.patent_title.ilike(f"%{keyword}%"),
            TbPatentMetadata.abstract.ilike(f"%{keyword}%")
        ))
    
    # 총 개수 조회
    count_query = select(func.count()).select_from(TbPatentMetadata).where(and_(*filters))
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # 페이징 조회
    patents_query = (
        select(TbPatentMetadata)
        .where(and_(*filters))
        .order_by(TbPatentMetadata.application_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    patents_result = await db.execute(patents_query)
    patents = patents_result.scalars().all()
    
    return {
        "success": True,
        "patents": [
            {
                "metadata_id": p.metadata_id,
                "application_number": p.application_number,
                "patent_title": p.patent_title,
                "main_ipc_code": p.main_ipc_code,
                "ipc_codes": p.ipc_codes,
                "patent_status": p.patent_status,
                "application_date": p.application_date,
                "registration_date": p.registration_date,
                "abstract": p.abstract[:200] + "..." if p.abstract and len(p.abstract) > 200 else p.abstract,
                "keywords": p.keywords
            }
            for p in patents
        ],
        "pagination": {
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    }
```

#### 3.2.3 컨테이너 IPC 매핑 관리 (신규)

```python
# POST /api/v1/containers/{container_id}/ipc-mappings (신규)

@router.post("/{container_id}/ipc-mappings", response_model=IPCMappingResponse)
async def add_ipc_mapping_to_container(
    container_id: str,
    request: AddIPCMappingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    컨테이너에 IPC 코드 매핑 추가
    
    예: "R&D센터/배터리팀" 컨테이너에 IPC "H01M" (전기화학 셀) 매핑
        → 해당 폴더 접근 시 H01M 관련 특허들 자동 표시
    
    권한: ADMIN, MANAGER만 가능
    """
    # 권한 확인
    permission_service = PermissionService(db)
    permission_level = await permission_service.get_user_permission_level(
        current_user.emp_no, container_id
    )
    
    if permission_level not in ['ADMIN', 'MANAGER', 'OWNER']:
        raise HTTPException(
            status_code=403, 
            detail=f"IPC 매핑은 관리자만 수정 가능합니다. (현재 권한: {permission_level})"
        )
    
    # IPC 코드 존재 여부 확인
    ipc_query = select(TbIpcCode).where(TbIpcCode.code == request.ipc_code)
    ipc_result = await db.execute(ipc_query)
    ipc_code = ipc_result.scalar_one_or_none()
    
    if not ipc_code:
        raise HTTPException(status_code=404, detail=f"IPC 코드 '{request.ipc_code}'를 찾을 수 없습니다.")
    
    # 중복 체크
    existing_query = select(TbContainerIpcMapping).where(
        and_(
            TbContainerIpcMapping.container_id == container_id,
            TbContainerIpcMapping.ipc_code == request.ipc_code
        )
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=409, detail="이미 매핑된 IPC 코드입니다.")
    
    # 매핑 추가
    new_mapping = TbContainerIpcMapping(
        container_id=container_id,
        ipc_code=request.ipc_code,
        custom_label=request.custom_label,
        is_primary=request.is_primary,
        weight=request.weight,
        created_by=current_user.emp_no
    )
    
    db.add(new_mapping)
    await db.commit()
    
    return {
        "success": True,
        "message": f"IPC 코드 '{request.ipc_code}' 매핑 완료",
        "mapping": {
            "ipc_code": request.ipc_code,
            "ipc_description": ipc_code.description_kr,
            "custom_label": request.custom_label
        }
    }


# GET /api/v1/containers/{container_id}/ipc-mappings (신규)

@router.get("/{container_id}/ipc-mappings", response_model=IPCMappingListResponse)
async def get_container_ipc_mappings(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    컨테이너의 IPC 매핑 목록 조회
    """
    # 권한 확인
    permission_service = PermissionService(db)
    has_access = await permission_service.check_container_access(
        current_user.emp_no, container_id, "READ"
    )
    if not has_access:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    
    # 매핑 목록 조회 (특허 수 포함)
    query = """
    SELECT 
        m.ipc_code,
        ipc.description_kr,
        ipc.description_en,
        ipc.section,
        ipc.level,
        m.custom_label,
        m.is_primary,
        m.weight,
        COUNT(p.metadata_id) as patent_count,
        m.created_date
    FROM tb_container_ipc_mapping m
    JOIN tb_ipc_code ipc ON m.ipc_code = ipc.code
    LEFT JOIN tb_patent_metadata p ON p.main_ipc_code = ipc.code 
        AND p.container_id = :container_id
    WHERE m.container_id = :container_id
    GROUP BY m.ipc_code, ipc.description_kr, ipc.description_en, 
             ipc.section, ipc.level, m.custom_label, m.is_primary, 
             m.weight, m.created_date
    ORDER BY m.is_primary DESC, patent_count DESC
    """
    
    result = await db.execute(text(query), {"container_id": container_id})
    mappings = [
        {
            "ipc_code": row.ipc_code,
            "ipc_description_kr": row.description_kr,
            "ipc_description_en": row.description_en,
            "section": row.section,
            "level": row.level,
            "custom_label": row.custom_label,
            "is_primary": row.is_primary,
            "weight": row.weight,
            "patent_count": row.patent_count,
            "created_date": row.created_date
        }
        for row in result
    ]
    
    return {
        "success": True,
        "mappings": mappings,
        "total_count": len(mappings)
    }


# DELETE /api/v1/containers/{container_id}/ipc-mappings/{ipc_code} (신규)

@router.delete("/{container_id}/ipc-mappings/{ipc_code}")
async def delete_ipc_mapping(
    container_id: str,
    ipc_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    컨테이너 IPC 매핑 삭제
    
    권한: ADMIN, MANAGER만 가능
    """
    # 권한 확인
    permission_service = PermissionService(db)
    permission_level = await permission_service.get_user_permission_level(
        current_user.emp_no, container_id
    )
    
    if permission_level not in ['ADMIN', 'MANAGER', 'OWNER']:
        raise HTTPException(
            status_code=403, 
            detail=f"IPC 매핑은 관리자만 삭제 가능합니다. (현재 권한: {permission_level})"
        )
    
    # 매핑 존재 여부 확인 및 삭제
    delete_query = delete(TbContainerIpcMapping).where(
        and_(
            TbContainerIpcMapping.container_id == container_id,
            TbContainerIpcMapping.ipc_code == ipc_code
        )
    )
    
    result = await db.execute(delete_query)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="매핑을 찾을 수 없습니다.")
    
    return {
        "success": True,
        "message": f"IPC 코드 '{ipc_code}' 매핑 삭제 완료"
    }
```

#### 3.2.4 IP 포트폴리오 통계 (기존 통계 확장)

```python
# GET /api/v1/containers/{container_id}/statistics (기존 → 확장)

@router.get("/{container_id}/statistics", response_model=IPPortfolioStatisticsResponse)
async def get_ip_portfolio_statistics(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    IP 포트폴리오 통계 (특허 중심)
    
    반환 정보:
    - 특허 개수 (총/등록/공개/거절/소멸)
    - IPC 섹션별 특허 분포 (도넛 차트용)
    - 연도별 출원 추이 (라인 차트용)
    - 주요 IPC 코드 Top 10
    - 최근 등록 특허 5건
    """
    # 권한 확인
    permission_service = PermissionService(db)
    has_access = await permission_service.check_container_access(
        current_user.emp_no, container_id, "READ"
    )
    if not has_access:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    
    # 1. 특허 상태별 집계
    status_query = """
    SELECT 
        patent_status,
        COUNT(*) as count
    FROM tb_patent_metadata
    WHERE container_id = :container_id
    GROUP BY patent_status
    """
    status_result = await db.execute(text(status_query), {"container_id": container_id})
    status_distribution = {row.patent_status: row.count for row in status_result}
    
    # 2. IPC 섹션별 특허 분포
    section_query = """
    SELECT 
        primary_ipc_section,
        COUNT(*) as count
    FROM tb_patent_metadata
    WHERE container_id = :container_id AND primary_ipc_section IS NOT NULL
    GROUP BY primary_ipc_section
    ORDER BY count DESC
    """
    section_result = await db.execute(text(section_query), {"container_id": container_id})
    section_distribution = [
        {"section": row.primary_ipc_section, "count": row.count}
        for row in section_result
    ]
    
    # 3. 연도별 출원 추이
    year_query = """
    SELECT 
        EXTRACT(YEAR FROM application_date) as year,
        COUNT(*) as count
    FROM tb_patent_metadata
    WHERE container_id = :container_id AND application_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM application_date)
    ORDER BY year DESC
    LIMIT 10
    """
    year_result = await db.execute(text(year_query), {"container_id": container_id})
    yearly_trend = [
        {"year": int(row.year), "count": row.count}
        for row in year_result
    ]
    
    # 4. 주요 IPC 코드 Top 10
    top_ipc_query = """
    SELECT 
        main_ipc_code,
        COUNT(*) as patent_count
    FROM tb_patent_metadata
    WHERE container_id = :container_id AND main_ipc_code IS NOT NULL
    GROUP BY main_ipc_code
    ORDER BY patent_count DESC
    LIMIT 10
    """
    top_ipc_result = await db.execute(text(top_ipc_query), {"container_id": container_id})
    top_ipc_codes = [
        {"ipc_code": row.main_ipc_code, "patent_count": row.patent_count}
        for row in top_ipc_result
    ]
    
    # 5. 최근 등록 특허
    recent_query = """
    SELECT metadata_id, application_number, patent_title, 
           main_ipc_code, registration_date
    FROM tb_patent_metadata
    WHERE container_id = :container_id 
        AND patent_status = '등록'
        AND registration_date IS NOT NULL
    ORDER BY registration_date DESC
    LIMIT 5
    """
    recent_result = await db.execute(text(recent_query), {"container_id": container_id})
    recent_patents = [
        {
            "metadata_id": row.metadata_id,
            "application_number": row.application_number,
            "patent_title": row.patent_title,
            "main_ipc_code": row.main_ipc_code,
            "registration_date": row.registration_date
        }
        for row in recent_result
    ]
    
    return {
        "success": True,
        "statistics": {
            "status_distribution": status_distribution,
            "section_distribution": section_distribution,
            "yearly_trend": yearly_trend,
            "top_ipc_codes": top_ipc_codes,
            "recent_registered_patents": recent_patents,
            "total_patents": sum(status_distribution.values())
        }
    }
```

### 3.3 프론트엔드 개선

#### 3.3.1 IP 포트폴리오 메인 페이지

**기존**: `/containers` (조직 폴더 트리)  
**개선**: `/ip-portfolio` (IPC 분류 기반)

**UI 구성**:
```
┌──────────────────────────────────────────────────────────────┐
│  🏢 IP 포트폴리오                        [조직별 ▼] [IPC별 ▼] │
├──────────────────────────────────────────────────────────────┤
│  📊 전체 통계                                                 │
│  ├─ 총 특허: 1,234건                                         │
│  ├─ 등록: 987건 | 공개: 180건 | 거절: 67건                    │
│  └─ 주요 기술 분야: H04W (450건), G06N (320건), H01M (280건) │
├──────────────────────────────────────────────────────────────┤
│  🔍 [검색: IPC 코드/특허명/키워드]       [필터 ▼]             │
├──────────────────────────────────────────────────────────────┤
│  🗂️ 조직 컨테이너 트리               📌 IPC 분류 트리         │
│  ├─ R&D센터 (520건)                 ├─ H: 전기 (780건)       │
│  │  ├─ 배터리팀 (280건)              │  ├─ H01M: 전기화학 셀  │
│  │  │  └─ [IPC: H01M, H01G]        │  ├─ H04W: 무선통신     │
│  │  └─ AI팀 (240건)                 │  └─ H04L: 디지털 전송  │
│  │     └─ [IPC: G06N, G06F]        ├─ G: 물리학 (340건)     │
│  └─ 품질관리팀 (180건)               │  ├─ G06N: AI/ML        │
│     └─ [IPC: G01N, G01R]           │  └─ G06F: 데이터 처리  │
├──────────────────────────────────────────────────────────────┤
│  📄 특허 카드 목록 (선택된 폴더/IPC 기준)                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 🔖 10-2020-1234567 | H01M10/42 | ✅ 등록 (2023-05-15)  │  │
│  │ [차세대 리튬이온 배터리 음극재 조성물 및 제조방법]         │  │
│  │ 출원일: 2020-10-01 | 키워드: 음극재, 리튬, 에너지밀도    │  │
│  │ [상세보기] [문서열기] [IPC 트리]                         │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 🔖 10-2019-9876543 | G06N3/08 | 📝 공개 (2021-04-10)   │  │
│  │ [심층 신경망 기반 이미지 객체 인식 방법]                   │  │
│  │ ...                                                      │  │
└──────────────────────────────────────────────────────────────┘
```

**주요 기능**:
1. **IPC 트리 네비게이션**: 섹션/클래스/서브클래스 단위 탐색
2. **권한 기반 노출**: 내 권한 범위의 IPC만 표시
3. **특허 카드**: 특허 메타데이터 시각화 (출원번호, 법적상태, IPC, 키워드)
4. **동적 필터링**: IPC 섹션, 법적상태, 연도, 키워드

#### 3.3.2 대시보드 위젯 (기존 대시보드 확장)

**신규 위젯**:
1. **기술 분야별 특허 분포** (도넛 차트)
   - IPC 섹션별 특허 수 (A~H)
   - 클릭 시 해당 섹션 특허 목록으로 드릴다운

2. **연도별 특허 출원 추이** (라인 차트)
   - 최근 10년간 출원 건수
   - 등록/공개/거절 상태별 스택 영역 차트

3. **주요 IPC 코드 Top 10** (막대 차트)
   - 특허 수가 많은 IPC 코드 순위
   - 클릭 시 해당 IPC 특허 목록

4. **법적상태 요약** (카드 그리드)
   - 등록/공개/거절/소멸 특허 수
   - 각 상태 클릭 시 상세 목록

---

## 4. 구현 로드맵

### Phase 1: 데이터 모델 확장 (1주) - ✅ **완료**
- ✅ **완료**: IPC 마스터 테이블 (`tb_ipc_code`) 구축 및 시드 데이터
- ✅ **완료**: 특허 메타데이터 테이블 (`tb_patent_metadata`) 구축
- ✅ **완료**: IPC 권한 테이블 (`tb_ipc_permissions`) 구축 및 마이그레이션 스크립트
- ✅ **완료**: `tb_patent_metadata` 활용 (ipc_codes 배열 지원)

### Phase 2: 백엔드 API 확장 (2주) - ✅ **완료**
- ✅ **완료**: IPC 관리 API (`/api/v1/admin/ipc/*`) 6개 엔드포인트
- ✅ **완료**: IP 포트폴리오 라우터 (`/api/v1/ip-portfolio/*`) 6개 엔드포인트 신규 구현
  1. `GET /api/v1/ip-portfolio/my-permissions` → 내 IPC 권한 목록
  2. `GET /api/v1/ip-portfolio/ipc-tree` → 권한 기반 IPC 트리 조회
  3. `GET /api/v1/ip-portfolio/patents` → 특허 목록 (IPC/법적상태/연도 필터링)
  4. `GET /api/v1/ip-portfolio/patents/{metadata_id}` → 특허 상세 정보
  5. `GET /api/v1/ip-portfolio/dashboard-stats` → 대시보드 통계 (IPC 분포, 법적상태, 연도별 추이)
  6. `IpcPermissionService` → 권한 로직 (역할 우선순위, 하위 코드 포함, 재귀 CTE)

### Phase 3: 프론트엔드 UI 개선 (3주) - ✅ **완료**
- ✅ **완료**: IP 포트폴리오 메인 페이지 구현 (`/user/ip-portfolio`)
  - IPC 트리 네비게이션 (좌측 사이드바, 재귀 렌더링, 접기/펼치기)
  - 특허 카드 컴포넌트 (출원번호, 법적상태, IPC, 키워드, 그리드 레이아웃)
  - IPC 필터링 UI (섹션 선택, 검색 기능)
  - 페이징 처리 (무한 스크롤 대응)
- ✅ **완료**: 대시보드 통계 위젯 (상단 배치)
  - 총 특허 수, 등록/공개/거절 특허 수 (카드 그리드)
  - IPC 섹션별 특허 분포 (recharts 라이브러리)
  - API 서비스 레이어 (`ipPortfolioService.ts`)
  - React Router 연동 (`App.tsx`)

### Phase 3.5: 테스트 및 검증 (1주) - ✅ **완료**
- ✅ **완료**: 단위 테스트 (Unit Tests) - 15/15 PASS
  - `tests/unit/test_ipc_permission_service.py`
  - IpcPermissionService 핵심 로직 검증 (역할 우선순위, 권한 조회, 하위 코드 탐색)
- ✅ **완료**: 기능 테스트 (Functional Tests) - 3/5 PASS
  - `tests/functional/test_ip_portfolio_api.py`
  - API 엔드포인트 라우팅 및 권한 체크 검증
- ✅ **완료**: 통합 테스트 (Integration Tests) - 4/4 PASS
  - `tests/integration/test_ip_portfolio_e2e.py`
  - 실제 PostgreSQL DB 연동 E2E 시나리오 검증
  - IPC 권한 생성/조회/삭제, 특허 메타데이터 조회, 허용 IPC 코드 계산

### Phase 4: 자동 분류 로직 (4주) - 🔜 **예정**
- 🔜 **예정**: 특허 문서 업로드 시 IPC 자동 추천
  - TF-IDF 키워드 매칭 또는 임베딩 유사도
  - IPC 설명 → 문서 텍스트 유사도 계산
  - 상위 3개 IPC 코드 추천

---

## 5. 구현 현황 (2026-01-04 기준)

### 5.1 백엔드 구현 완료 사항

#### IPC 권한 서비스 (`backend/app/services/auth/ipc_permission_service.py`)
```python
class IpcPermissionService:
    """IPC 코드 기반 권한 관리 서비스"""
    
    async def list_active_permissions(user_emp_no: str) -> List[IpcPermissionInfo]
        # 사용자의 활성 IPC 권한 목록 조회
    
    async def has_ipc_access(user_emp_no: str, ipc_code: str, min_role: str) -> bool
        # 특정 IPC 코드 접근 권한 확인 (역할 우선순위 계산)
    
    async def get_descendant_codes(ipc_code: str, include_self: bool) -> List[str]
        # IPC 하위 코드 조회 (재귀 CTE)
    
    async def get_allowed_ipc_codes(user_emp_no: str, min_role: str) -> Set[str]
        # 사용자 접근 가능 IPC 코드 목록 (include_children 지원)
```

#### IP 포트폴리오 API (`backend/app/api/v1/ip_portfolio.py`)
- ✅ 6개 엔드포인트 구현 완료
- ✅ FastAPI main.py에 라우터 등록
- ✅ 권한 기반 접근 제어 (IpcPermissionService 통합)
- ✅ IPC 트리 빌딩 로직 (재귀 구조)
- ✅ 특허 메타데이터 조회 및 필터링
- ✅ 대시보드 통계 집계 (IPC 분포, 법적상태, 연도별 추이)

### 5.2 프론트엔드 구현 완료 사항

#### IP 포트폴리오 페이지 (`frontend/src/pages/user/ip-portfolio/IPPortfolioPage.tsx`)
```typescript
interface IPPortfolioPageProps {
  // IPC 트리 사이드바 (좌측 300px 고정)
  // - 재귀 렌더링 (renderNode)
  // - 접기/펼치기 상태 관리
  // - IPC 코드 클릭 시 특허 목록 필터링
  
  // 메인 콘텐츠 (우측)
  // - 대시보드 통계 (총 특허, 등록/공개/거절 수)
  // - 특허 카드 그리드 (출원번호, 법적상태, IPC, 키워드)
  // - 페이징 처리 (page/pageSize)
}
```

#### API 서비스 레이어 (`frontend/src/services/ipPortfolioService.ts`)
- ✅ getIpcTree(): IPC 트리 조회
- ✅ getDashboardStats(): 대시보드 통계 조회
- ✅ listPatents(filters): 특허 목록 조회 (IPC/상태/연도 필터링)
- ✅ axios 기반 REST API 호출

### 5.3 테스트 커버리지

| 테스트 유형 | 파일명 | 결과 | 커버리지 |
|------------|--------|------|----------|
| 단위 테스트 | `tests/unit/test_ipc_permission_service.py` | 15/15 PASS | IpcPermissionService 89% |
| 기능 테스트 | `tests/functional/test_ip_portfolio_api.py` | 3/5 PASS | API 라우팅 검증 |
| 통합 테스트 | `tests/integration/test_ip_portfolio_e2e.py` | 4/4 PASS | E2E 시나리오 100% |

**테스트 환경**:
- Python 3.11.14 + pytest 7.4.3 + pytest-asyncio
- PostgreSQL (postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms)
- FastAPI + SQLAlchemy 2.0.23

---

## 6. 마이그레이션 가이드

### 5.1 기존 데이터 영향

**기존 시스템 유지**:
- `tb_knowledge_containers`: 변경 없음 (조직 계층 구조 유지)
- `tb_user_permissions`: 변경 없음 (권한 체계 유지)
- `tb_file_bss_info`: 컬럼 추가 (`ipc_codes`, `primary_ipc_section`)

**신규 테이블 추가**:
- `tb_container_ipc_mapping`: 컨테이너-IPC 매핑 (다대다)
- `tb_ipc_code`: IPC 마스터 (이미 구축)
- `tb_patent_metadata`: 특허 메타데이터 (이미 구축)

### 5.2 기존 API 호환성

**변경 없는 엔드포인트** (하위 호환 유지):
- `GET /api/v1/containers/` (목록 조회)
- `GET /api/v1/containers/hierarchy` (계층 구조)
- `POST /api/v1/containers/` (컨테이너 생성)
- `GET /api/v1/containers/{id}/permissions` (권한 관리)

**확장되는 엔드포인트** (선택적 파라미터 추가):
- `GET /api/v1/containers/{id}` → `?include_ipc=true&include_patent_stats=true`
- `GET /api/v1/containers/{id}/statistics` → IP 통계 추가 (기존 응답 구조 유지)

**신규 엔드포인트** (기존 API 영향 없음):
- `GET /api/v1/containers/{id}/patents` (특허 목록)
- `POST /api/v1/containers/{id}/ipc-mappings` (IPC 매핑 관리)

---

## 6. 기대 효과

### 6.1 사용자 관점

**기존 (지식 컨테이너)**:
- 조직도 기반 폴더에서 문서 찾기
- 단순 파일 개수 통계

**개선 (IP 포트폴리오)**:
- **IPC 기반 기술 분류**로 표준화된 특허 검색
- **특허 카드**로 법적상태, 출원번호, IPC 코드 한눈에 확인
- **동적 필터링** (IPC/연도/상태)으로 원하는 특허 빠르게 찾기
- **대시보드 통계**로 기술 분야별 특허 분포 시각화

### 6.2 관리자 관점

**기존**:
- 조직 변경 시 수동으로 폴더 재구성
- 특허 분류 체계 부재

**개선**:
- **컨테이너-IPC 매핑**으로 조직 변경과 무관하게 기술 분류 유지
- **IPC 통계**로 기술 포트폴리오 현황 파악 (Top 10 기술 분야 등)
- **자동 분류**로 신규 특허 업로드 시 IPC 자동 태깅

### 6.3 비즈니스 가치

- **표준화**: 국제 표준 IPC 분류 체계 도입으로 경쟁사와 비교 가능
- **검색 개선**: IPC 기반 필터링으로 검색 정확도 향상
- **인사이트**: 기술 분야별 특허 분포, 연도별 출원 추이 등 전략적 의사결정 지원
- **확장성**: 향후 CPC, 인용 분석 등 고급 특허 분석 기능 추가 기반 마련

---

## 7. 다음 단계 제안

### Phase 4: 시스템 관리자 IPC 권한 관리 UI (우선순위 1) ⭐
1. **사용자별 IPC 권한 할당 UI**
   - `/admin/ipc-permissions` 페이지
   - 사용자 검색 및 선택
   - IPC 코드 검색 (트리 뷰 또는 자동완성)
   - 권한 레벨 선택 (VIEWER/EDITOR/ADMIN)
   - 하위 코드 포함 옵션 (include_children)
   - 유효 기간 설정 (valid_from, valid_until)

2. **IPC 권한 목록 관리**
   - 사용자별 할당된 IPC 권한 조회
   - 권한 수정/삭제
   - 일괄 권한 부여 (CSV 업로드)
   - 권한 변경 이력 조회

### Phase 5: 자동 분류 및 고급 기능 (우선순위 2)
1. **특허 문서 IPC 자동 추천**
   - 문서 업로드 시 텍스트 분석 (제목, 요약, 청구항)
   - TF-IDF 또는 임베딩 기반 IPC 코드 유사도 계산
   - 상위 3개 IPC 코드 추천 UI

2. **커스텀 기술 분류 매핑**
   - `tb_custom_tech_category` 테이블 생성
   - 기업 내부 용어 → IPC 코드 매핑 관리 UI
   - 예: "차세대 배터리" → ['H01M 10/44', 'H02J 7/00']

### Phase 6: 권한 요청 워크플로우 (우선순위 3, 선택적)
**조건**: 권한 요청이 증가하여 시스템 관리자 병목이 발생하는 경우
1. **IPC Manager 역할 활성화**
   - MANAGER 역할에 권한 승인/거부 기능 부여
   - IPC 분야별 담당자 지정 UI
2. **권한 요청 워크플로우 UI**
   - 사용자 권한 요청 화면
   - Manager/Admin 승인/거부 화면

### Phase 5: 시각화 고도화 (우선순위 2)
3. **대시보드 차트 확장**
   - 기술 분야별 특허 분포 (도넛 차트 → 인터랙티브)
   - 연도별 출원 추이 (라인 차트, 법적상태별 스택)
   - 주요 IPC Top 10 (막대 차트)
   - 드릴다운 기능 (차트 클릭 시 상세 목록)

4. **특허 상세 페이지**
   - 청구항 시각화
   - 인용 관계 그래프
   - 유사 특허 추천

### Phase 6: 레거시 통합 (우선순위 3)
5. **조직도 컨테이너와 IPC 하이브리드 뷰**
   - `tb_container_ipc_mapping` 구현 (컨테이너-IPC 다대다 매핑)
   - 조직도 폴더에서 IPC 기반 필터링 지원
   - 기존 containers.py API 확장

---

## 8. 결론

본 계획서는 **기존 "지식 컨테이너" 시스템을 폐기하지 않고**, **"IP 포트폴리오" 관점으로 확장**하는 전략입니다.

**핵심 원칙**:
- ✅ 기존 조직도 기반 권한 체계 유지 (SAP 연동, 권한 관리)
- ✅ IPC 분류 체계를 **추가 레이어**로 통합 (컨테이너-IPC 매핑)
- ✅ 특허 메타데이터를 활용한 **고급 검색 및 통계** 제공
- ✅ 프론트엔드에서 IPC 기반 포트폴리오 제공

이를 통해 기업은 **조직 중심의 문서 관리**와 **기술 중심의 특허 관리**를 모두 효율적으로 수행할 수 있습니다.

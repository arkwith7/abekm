# IP 포트폴리오 - IPC 중심 전환 분석

> **작성일**: 2026-01-04  
> **질문**: 조직도 기반 컨테이너(containers.py)를 완전히 제거하고, IPC 분류 체계(ipc.py)만으로 IP 포트폴리오를 운영할 수 있는가?

---

## 1. 결론: **완전히 가능하며, 오히려 권장됨** ✅

### 1.1 비교 분석

| 구분 | 조직도 기반 (기존) | IPC 중심 (제안) |
|------|-------------------|-----------------|
| **분류 기준** | 부서/팀 조직도 (SAP 연동) | 국제 표준 IPC 기술 분류 |
| **표준화** | ❌ 기업별 조직 구조 의존 | ✅ 글로벌 표준 (IPC/CPC) |
| **조직 변경 영향** | ❌ 조직 개편 시 재구성 필요 | ✅ 조직 변경과 무관 |
| **특허 관리 적합성** | ❌ 기술 분류 부재 | ✅ 기술 중심 분류 최적화 |
| **검색/필터링** | 조직 단위 검색 | ✅ IPC 코드, 섹션, 키워드 |
| **권한 관리** | 조직 멤버십 기반 자동 부여 | IPC 코드별 권한 부여 (명시적) |
| **대시보드 통계** | 조직별 문서 수 | ✅ 기술 분야별 특허 분포 |
| **경쟁사 비교** | ❌ 불가능 (조직 구조 다름) | ✅ 가능 (동일 IPC 기준) |
| **유지보수** | SAP RFC 연동 유지 필요 | ✅ IPC 마스터 데이터만 관리 |

### 1.2 최종 권고

**✅ IPC 중심 IP 포트폴리오 전환 권장**

**이유**:
1. **특허 관리 본질에 부합**: 기술 분류가 핵심
2. **국제 표준 준수**: IPC/CPC는 전 세계 특허청에서 사용
3. **조직 독립성**: 조직 개편과 무관하게 특허 자산 유지
4. **확장성**: 향후 CPC, 인용 분석, AI 추천 등 고급 기능 추가 용이
5. **복잡도 감소**: SAP 연동, 조직도 동기화 불필요

---

## 2. 기존 시스템 레거시 처리 방안

### 2.1 containers.py 단계적 폐기 계획

#### Phase 1: IPC 중심 IP 포트폴리오 구축 (4주)
- IPC 기반 특허 조회 API 구현
- IPC 트리 네비게이션 UI
- 특허 카드 UI (IPC 코드 중심)

#### Phase 2: 하이브리드 운영 (4주)
- 기존 containers.py 유지 (읽기 전용)
- 신규 특허는 IPC 중심으로만 분류
- 사용자에게 점진적 전환 안내

#### Phase 3: 완전 전환 (4주)
- 기존 조직 기반 문서 → IPC 자동 분류
- containers.py 엔드포인트 deprecated 표시
- 6개월 후 완전 제거

### 2.2 기존 데이터 마이그레이션

**tb_knowledge_containers 데이터 처리**:
```sql
-- 기존 컨테이너에 속한 특허 메타데이터에 IPC 코드 자동 매핑
UPDATE tb_patent_metadata p
SET 
    main_ipc_code = COALESCE(p.main_ipc_code, 'UNCLASSIFIED'),
    ipc_codes = COALESCE(p.ipc_codes, ARRAY[]::TEXT[]),
    legacy_container_id = p.container_id  -- 레거시 참조 보존
WHERE p.container_id IS NOT NULL;

-- 조직 기반 컨테이너 ID를 레거시 컬럼으로 이동
ALTER TABLE tb_patent_metadata
ADD COLUMN legacy_container_id VARCHAR(50),
ALTER COLUMN container_id DROP NOT NULL;

-- 향후 container_id는 사용하지 않거나 IPC 섹션 코드로 재활용
```

**권한 마이그레이션**:
```sql
-- 기존 조직 권한 → IPC 섹션 권한으로 전환
-- 예: "R&D센터" ADMIN 권한 → "H" (전기) 섹션 ADMIN 권한
INSERT INTO tb_ipc_permissions (user_emp_no, ipc_code, role_id)
SELECT 
    up.user_emp_no,
    'H' as ipc_code,  -- 조직별 주요 IPC 섹션 매핑 (수동 정의 필요)
    up.role_id
FROM tb_user_permissions up
JOIN tb_knowledge_containers kc ON up.container_id = kc.container_id
WHERE kc.container_name LIKE '%R&D%' OR kc.container_name LIKE '%기술%';
```

---

## 3. IPC 중심 IP 포트폴리오 아키텍처

### 3.1 새로운 데이터 모델

#### 3.1.1 IPC 권한 테이블 (신규)

```sql
-- IPC 코드별 사용자 권한 (조직 권한 대체)
CREATE TABLE tb_ipc_permissions (
    permission_id SERIAL PRIMARY KEY,
    user_emp_no VARCHAR(20) NOT NULL REFERENCES tb_users(emp_no),
    ipc_code VARCHAR(20) NOT NULL REFERENCES tb_ipc_code(code),
    
    -- 권한 레벨
    role_id VARCHAR(20) NOT NULL,  -- ADMIN, MANAGER, EDITOR, VIEWER
    access_scope VARCHAR(20) DEFAULT 'FULL',  -- FULL, READ_ONLY, WRITE_ONLY
    
    -- 권한 범위 (IPC 계층 상속)
    include_children BOOLEAN DEFAULT true,  -- 하위 IPC 코드도 권한 적용
    
    -- 유효 기간
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

**권한 계층 상속 예시**:
- 사용자 A에게 IPC "H" (전기) 섹션 ADMIN 권한 부여 + `include_children=true`
- → H01 (기본 전기 소자), H04 (전기 통신) 등 모든 하위 코드 자동 권한

#### 3.1.2 특허 메타데이터 간소화

```sql
-- tb_patent_metadata (기존) - container_id 제거, IPC 중심으로 재설계
ALTER TABLE tb_patent_metadata
DROP COLUMN container_id,  -- 조직 컨테이너 연결 제거
ADD COLUMN legacy_container_id VARCHAR(50),  -- 레거시 참조용 (nullable)
ADD COLUMN primary_ipc_section VARCHAR(10),  -- IPC 섹션 (A~H)
ADD COLUMN ipc_codes TEXT[],  -- 복수 IPC 코드 배열
ADD COLUMN keywords TEXT[],  -- 자동 추출 키워드
ADD COLUMN patent_status VARCHAR(30);  -- 법적상태

-- IPC 기반 인덱스
CREATE INDEX idx_patent_main_ipc ON tb_patent_metadata(main_ipc_code);
CREATE INDEX idx_patent_ipc_section ON tb_patent_metadata(primary_ipc_section);
CREATE INDEX idx_patent_ipc_codes ON tb_patent_metadata USING gin(ipc_codes);
CREATE INDEX idx_patent_keywords ON tb_patent_metadata USING gin(keywords);
```

#### 3.1.3 IPC 즐겨찾기 (선택적)

```sql
-- 사용자별 자주 사용하는 IPC 코드
CREATE TABLE tb_user_favorite_ipc (
    favorite_id SERIAL PRIMARY KEY,
    user_emp_no VARCHAR(20) NOT NULL REFERENCES tb_users(emp_no),
    ipc_code VARCHAR(20) NOT NULL REFERENCES tb_ipc_code(code),
    custom_label VARCHAR(100),  -- 사용자 정의 라벨 (예: "배터리 기술")
    sort_order INTEGER DEFAULT 0,
    created_date TIMESTAMP DEFAULT now(),
    
    UNIQUE(user_emp_no, ipc_code)
);

CREATE INDEX idx_fav_ipc_user ON tb_user_favorite_ipc(user_emp_no);
```

### 3.2 새로운 API 설계

#### 3.2.1 IP 포트폴리오 메인 API (`/api/v1/ip-portfolio/*`)

**신규 라우터** (`backend/app/api/v1/ip_portfolio.py`):

```python
"""
IP 포트폴리오 API - IPC 중심
조직도 기반 컨테이너(containers.py)를 대체
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, TbIpcCode, TbPatentMetadata, TbIpcPermissions


router = APIRouter(prefix="/api/v1/ip-portfolio", tags=["📊 IP Portfolio"])


# =============================================================================
# 1. IPC 트리 네비게이션 (계층 구조)
# =============================================================================

@router.get("/ipc-tree", response_model=IPCTreeResponse)
async def get_ipc_navigation_tree(
    section: Optional[str] = Query(None, description="특정 섹션만 조회 (A~H)"),
    include_patent_count: bool = Query(True, description="특허 수 포함"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    IP 포트폴리오 IPC 트리 네비게이션
    
    반환:
    - 사용자가 권한이 있는 IPC 코드만 표시
    - 계층 구조 (SECTION → CLASS → SUBCLASS → GROUP)
    - 각 노드의 특허 수
    """
    # 1. 사용자 권한이 있는 IPC 코드 조회
    user_ipc_codes = await get_user_accessible_ipc_codes(db, current_user.emp_no)
    
    # 2. IPC 트리 빌딩 (재귀)
    tree = await build_ipc_tree_with_permissions(
        db, 
        user_ipc_codes, 
        section_filter=section,
        include_patent_count=include_patent_count
    )
    
    return {"tree": tree, "total_sections": len(tree)}


# =============================================================================
# 2. 특허 목록 조회 (IPC 필터링)
# =============================================================================

@router.get("/patents", response_model=PatentListResponse)
async def get_patents_by_ipc(
    ipc_code: Optional[str] = Query(None, description="IPC 코드 필터 (예: H01M)"),
    ipc_section: Optional[str] = Query(None, description="IPC 섹션 (A~H)"),
    patent_status: Optional[str] = Query(None, description="법적상태 (등록/공개/거절)"),
    year_from: Optional[int] = Query(None, description="출원연도 시작"),
    year_to: Optional[int] = Query(None, description="출원연도 종료"),
    keyword: Optional[str] = Query(None, description="키워드 검색"),
    sort_by: str = Query("application_date", description="정렬 기준 (application_date/registration_date/patent_title)"),
    sort_order: str = Query("desc", description="정렬 순서 (asc/desc)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    IP 포트폴리오 특허 목록 조회
    
    필터:
    - IPC 코드: 특정 기술 분야 (예: H01M - 전기화학 셀)
    - IPC 섹션: 대분류 (A=생활필수품, ..., H=전기)
    - 법적상태: 등록/공개/거절/소멸
    - 출원연도: 범위 지정
    - 키워드: 특허명/요약 전문 검색
    
    권한 체크:
    - 사용자가 권한이 있는 IPC 코드의 특허만 조회
    """
    # 1. 사용자 권한 확인
    user_ipc_codes = await get_user_accessible_ipc_codes(db, current_user.emp_no)
    
    if not user_ipc_codes:
        return {
            "success": True,
            "patents": [],
            "pagination": {"total_count": 0, "page": page, "page_size": page_size}
        }
    
    # 2. 동적 필터 빌딩
    filters = []
    
    # IPC 권한 필터 (필수)
    filters.append(or_(
        TbPatentMetadata.main_ipc_code.in_(user_ipc_codes),
        TbPatentMetadata.ipc_codes.overlap(user_ipc_codes)  # PostgreSQL array overlap
    ))
    
    # 추가 필터
    if ipc_code:
        filters.append(or_(
            TbPatentMetadata.main_ipc_code == ipc_code,
            TbPatentMetadata.main_ipc_code.like(f"{ipc_code}%"),  # 하위 코드 포함
            TbPatentMetadata.ipc_codes.any(ipc_code)
        ))
    
    if ipc_section:
        filters.append(TbPatentMetadata.primary_ipc_section == ipc_section)
    
    if patent_status:
        filters.append(TbPatentMetadata.patent_status == patent_status)
    
    if year_from:
        filters.append(func.extract('year', TbPatentMetadata.application_date) >= year_from)
    
    if year_to:
        filters.append(func.extract('year', TbPatentMetadata.application_date) <= year_to)
    
    if keyword:
        filters.append(or_(
            TbPatentMetadata.patent_title.ilike(f"%{keyword}%"),
            TbPatentMetadata.abstract.ilike(f"%{keyword}%"),
            TbPatentMetadata.keywords.any(keyword)
        ))
    
    # 3. 총 개수 조회
    count_query = select(func.count()).select_from(TbPatentMetadata).where(and_(*filters))
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # 4. 정렬 및 페이징
    order_column = getattr(TbPatentMetadata, sort_by, TbPatentMetadata.application_date)
    order_func = desc if sort_order == "desc" else lambda x: x
    
    patents_query = (
        select(TbPatentMetadata)
        .where(and_(*filters))
        .order_by(order_func(order_column))
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


# =============================================================================
# 3. 특허 상세 조회
# =============================================================================

@router.get("/patents/{metadata_id}", response_model=PatentDetailResponse)
async def get_patent_detail(
    metadata_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특허 상세 정보 조회
    
    반환:
    - 특허 메타데이터 전체
    - IPC 코드 및 설명
    - 연결된 문서 파일 (tb_file_bss_info)
    - 사용자 권한 정보
    """
    # 1. 특허 조회
    patent_query = select(TbPatentMetadata).where(TbPatentMetadata.metadata_id == metadata_id)
    patent_result = await db.execute(patent_query)
    patent = patent_result.scalar_one_or_none()
    
    if not patent:
        raise HTTPException(status_code=404, detail="특허를 찾을 수 없습니다.")
    
    # 2. 권한 확인
    user_ipc_codes = await get_user_accessible_ipc_codes(db, current_user.emp_no)
    
    has_access = (
        patent.main_ipc_code in user_ipc_codes or
        any(ipc in user_ipc_codes for ipc in (patent.ipc_codes or []))
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail="이 특허에 접근할 권한이 없습니다.")
    
    # 3. IPC 코드 상세 정보 조회
    ipc_details = []
    if patent.main_ipc_code:
        ipc_query = select(TbIpcCode).where(TbIpcCode.code == patent.main_ipc_code)
        ipc_result = await db.execute(ipc_query)
        main_ipc = ipc_result.scalar_one_or_none()
        if main_ipc:
            ipc_details.append({
                "code": main_ipc.code,
                "description_ko": main_ipc.description_ko,
                "description_en": main_ipc.description_en,
                "level": main_ipc.level,
                "is_primary": True
            })
    
    # 4. 연결된 문서 파일 조회
    from app.models import TbFileBssInfo
    files_query = select(TbFileBssInfo).where(
        TbFileBssInfo.patent_metadata_id == metadata_id
    )
    files_result = await db.execute(files_query)
    files = files_result.scalars().all()
    
    return {
        "success": True,
        "patent": {
            "metadata_id": patent.metadata_id,
            "application_number": patent.application_number,
            "patent_title": patent.patent_title,
            "main_ipc_code": patent.main_ipc_code,
            "ipc_codes": patent.ipc_codes,
            "patent_status": patent.patent_status,
            "application_date": patent.application_date,
            "registration_date": patent.registration_date,
            "publication_date": patent.publication_date,
            "abstract": patent.abstract,
            "claims": patent.claims,
            "inventors": patent.inventors,
            "applicants": patent.applicants,
            "keywords": patent.keywords
        },
        "ipc_details": ipc_details,
        "attached_files": [
            {
                "file_id": f.FILE_BSS_INFO_SNO,
                "file_name": f.ORG_FILE_NM,
                "file_size": f.FILE_SIZE,
                "upload_date": f.REG_DT
            }
            for f in files
        ]
    }


# =============================================================================
# 4. IP 포트폴리오 대시보드 통계
# =============================================================================

@router.get("/statistics", response_model=IPPortfolioStatisticsResponse)
async def get_ip_portfolio_statistics(
    ipc_section: Optional[str] = Query(None, description="특정 섹션 통계만 조회"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    IP 포트폴리오 전체 통계
    
    반환:
    - 전체 특허 수 (사용자 권한 기준)
    - 법적상태별 분포 (등록/공개/거절/소멸)
    - IPC 섹션별 특허 분포 (도넛 차트용)
    - 연도별 출원 추이 (라인 차트용)
    - 주요 IPC 코드 Top 20
    - 최근 등록 특허 10건
    """
    # 1. 사용자 권한 확인
    user_ipc_codes = await get_user_accessible_ipc_codes(db, current_user.emp_no)
    
    if not user_ipc_codes:
        return {
            "success": True,
            "statistics": {
                "total_patents": 0,
                "status_distribution": {},
                "section_distribution": [],
                "yearly_trend": [],
                "top_ipc_codes": [],
                "recent_patents": []
            }
        }
    
    base_filter = or_(
        TbPatentMetadata.main_ipc_code.in_(user_ipc_codes),
        TbPatentMetadata.ipc_codes.overlap(user_ipc_codes)
    )
    
    # 2. 전체 특허 수
    total_query = select(func.count()).select_from(TbPatentMetadata).where(base_filter)
    total_result = await db.execute(total_query)
    total_patents = total_result.scalar()
    
    # 3. 법적상태별 분포
    status_query = text("""
    SELECT 
        patent_status,
        COUNT(*) as count
    FROM tb_patent_metadata
    WHERE main_ipc_code = ANY(:ipc_codes) OR ipc_codes && :ipc_codes
    GROUP BY patent_status
    """)
    status_result = await db.execute(status_query, {"ipc_codes": user_ipc_codes})
    status_distribution = {row.patent_status: row.count for row in status_result}
    
    # 4. IPC 섹션별 분포
    section_query = text("""
    SELECT 
        primary_ipc_section,
        COUNT(*) as count
    FROM tb_patent_metadata
    WHERE (main_ipc_code = ANY(:ipc_codes) OR ipc_codes && :ipc_codes)
      AND primary_ipc_section IS NOT NULL
    GROUP BY primary_ipc_section
    ORDER BY count DESC
    """)
    section_result = await db.execute(section_query, {"ipc_codes": user_ipc_codes})
    section_distribution = [
        {"section": row.primary_ipc_section, "count": row.count}
        for row in section_result
    ]
    
    # 5. 연도별 출원 추이
    year_query = text("""
    SELECT 
        EXTRACT(YEAR FROM application_date) as year,
        COUNT(*) as count
    FROM tb_patent_metadata
    WHERE (main_ipc_code = ANY(:ipc_codes) OR ipc_codes && :ipc_codes)
      AND application_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM application_date)
    ORDER BY year DESC
    LIMIT 10
    """)
    year_result = await db.execute(year_query, {"ipc_codes": user_ipc_codes})
    yearly_trend = [
        {"year": int(row.year), "count": row.count}
        for row in year_result
    ]
    
    # 6. 주요 IPC 코드 Top 20
    top_ipc_query = text("""
    SELECT 
        main_ipc_code,
        COUNT(*) as patent_count
    FROM tb_patent_metadata
    WHERE main_ipc_code = ANY(:ipc_codes) AND main_ipc_code IS NOT NULL
    GROUP BY main_ipc_code
    ORDER BY patent_count DESC
    LIMIT 20
    """)
    top_ipc_result = await db.execute(top_ipc_query, {"ipc_codes": user_ipc_codes})
    top_ipc_codes = [
        {"ipc_code": row.main_ipc_code, "patent_count": row.patent_count}
        for row in top_ipc_result
    ]
    
    # 7. 최근 등록 특허
    recent_query = (
        select(TbPatentMetadata)
        .where(and_(
            base_filter,
            TbPatentMetadata.patent_status == '등록',
            TbPatentMetadata.registration_date.isnot(None)
        ))
        .order_by(desc(TbPatentMetadata.registration_date))
        .limit(10)
    )
    recent_result = await db.execute(recent_query)
    recent_patents = [
        {
            "metadata_id": p.metadata_id,
            "application_number": p.application_number,
            "patent_title": p.patent_title,
            "main_ipc_code": p.main_ipc_code,
            "registration_date": p.registration_date
        }
        for p in recent_result.scalars().all()
    ]
    
    return {
        "success": True,
        "statistics": {
            "total_patents": total_patents,
            "status_distribution": status_distribution,
            "section_distribution": section_distribution,
            "yearly_trend": yearly_trend,
            "top_ipc_codes": top_ipc_codes,
            "recent_patents": recent_patents
        }
    }


# =============================================================================
# 5. IPC 권한 관리
# =============================================================================

@router.get("/my-ipc-permissions", response_model=UserIPCPermissionsResponse)
async def get_my_ipc_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    현재 사용자의 IPC 권한 목록 조회
    """
    permissions_query = (
        select(TbIpcPermissions)
        .where(and_(
            TbIpcPermissions.user_emp_no == current_user.emp_no,
            TbIpcPermissions.is_active == True
        ))
    )
    permissions_result = await db.execute(permissions_query)
    permissions = permissions_result.scalars().all()
    
    # IPC 코드 상세 정보 조인
    ipc_details = []
    for perm in permissions:
        ipc_query = select(TbIpcCode).where(TbIpcCode.code == perm.ipc_code)
        ipc_result = await db.execute(ipc_query)
        ipc = ipc_result.scalar_one_or_none()
        
        ipc_details.append({
            "ipc_code": perm.ipc_code,
            "ipc_description": ipc.description_ko if ipc else None,
            "role_id": perm.role_id,
            "access_scope": perm.access_scope,
            "include_children": perm.include_children,
            "valid_until": perm.valid_until,
            "granted_date": perm.created_date
        })
    
    return {
        "success": True,
        "permissions": ipc_details,
        "total_count": len(ipc_details)
    }


# =============================================================================
# Helper Functions
# =============================================================================

async def get_user_accessible_ipc_codes(db: AsyncSession, user_emp_no: str) -> List[str]:
    """
    사용자가 접근 가능한 IPC 코드 목록 조회 (권한 계층 상속 포함)
    """
    # 1. 직접 권한 조회
    permissions_query = (
        select(TbIpcPermissions)
        .where(and_(
            TbIpcPermissions.user_emp_no == user_emp_no,
            TbIpcPermissions.is_active == True,
            or_(
                TbIpcPermissions.valid_until.is_(None),
                TbIpcPermissions.valid_until > datetime.now()
            )
        ))
    )
    permissions_result = await db.execute(permissions_query)
    permissions = permissions_result.scalars().all()
    
    accessible_codes = set()
    
    for perm in permissions:
        accessible_codes.add(perm.ipc_code)
        
        # 2. 하위 코드 포함 옵션이 있으면 자식 코드 모두 추가
        if perm.include_children:
            children_query = (
                select(TbIpcCode.code)
                .where(or_(
                    TbIpcCode.parent_code == perm.ipc_code,
                    TbIpcCode.code.like(f"{perm.ipc_code}%")  # 계층 구조 매칭
                ))
            )
            children_result = await db.execute(children_query)
            child_codes = children_result.scalars().all()
            accessible_codes.update(child_codes)
    
    return list(accessible_codes)


async def build_ipc_tree_with_permissions(
    db: AsyncSession,
    user_ipc_codes: List[str],
    section_filter: Optional[str] = None,
    include_patent_count: bool = True
) -> List[Dict]:
    """
    사용자 권한 기반 IPC 트리 빌딩
    """
    # 권한이 있는 IPC 코드만 조회
    filters = [TbIpcCode.code.in_(user_ipc_codes)]
    
    if section_filter:
        filters.append(TbIpcCode.section == section_filter)
    
    ipc_query = (
        select(TbIpcCode)
        .where(and_(*filters))
        .order_by(TbIpcCode.code)
    )
    ipc_result = await db.execute(ipc_query)
    ipc_codes = ipc_result.scalars().all()
    
    # 트리 구조 빌딩 (재귀)
    # ... (기존 build_ipc_tree_recursive 로직 재사용)
    
    return []  # 트리 구조 반환
```

---

## 4. 마이그레이션 단계

### 4.1 Phase 1: IPC 중심 시스템 구축 (1개월)

**Week 1-2: 데이터 모델 구축**
```bash
# Alembic 마이그레이션 스크립트 생성
alembic revision -m "create_ipc_permissions_table"
alembic revision -m "add_ipc_fields_to_patent_metadata"

# 실행
alembic upgrade head
```

**Week 3-4: API 구현**
- `ip_portfolio.py` 라우터 생성 (위 코드)
- IPC 트리 네비게이션
- 특허 목록/상세 조회
- 대시보드 통계

### 4.2 Phase 2: 프론트엔드 전환 (1개월)

**Week 1-2: IP 포트폴리오 메인 페이지**
- IPC 트리 사이드바
- 특허 카드 그리드
- 필터링 UI (IPC/연도/상태)

**Week 3-4: 대시보드**
- 기술 분야별 특허 분포 (도넛 차트)
- 연도별 출원 추이 (라인 차트)
- 주요 IPC Top 20 (막대 차트)

### 4.3 Phase 3: 레거시 정리 (1개월)

**Week 1-2: 데이터 마이그레이션**
- 기존 조직 기반 권한 → IPC 권한 전환
- 특허 메타데이터 IPC 자동 분류

**Week 3-4: 완전 전환**
- containers.py 엔드포인트 deprecated
- 사용자 공지 및 교육
- 6개월 후 완전 제거

---

## 5. 권한 관리 비교

### 5.1 기존 (조직도 기반)

```
사용자 "홍길동"
└─ 조직: "R&D센터/배터리팀"
   └─ 자동 권한: "배터리팀" 컨테이너 VIEWER
      └─ 접근 가능 특허: "배터리팀" 폴더의 모든 문서
```

**문제점**:
- 조직 이동 시 권한 재설정 필요
- 기술 분야와 무관한 권한 부여 (팀원이라서 자동 부여)
- 교차 기능 협업 시 복잡 (여러 조직 권한 필요)

### 5.2 개선 (IPC 중심)

```
사용자 "홍길동"
└─ IPC 권한: "H01M" (전기화학 셀) EDITOR
   ├─ include_children: true
   └─ 접근 가능 특허: H01M, H01M10, H01M12 등 모든 배터리 관련 특허
```

**장점**:
- 조직 이동과 무관
- 기술 분야 중심 권한 (전문성 기반)
- 명확한 권한 범위 (IPC 계층)

---

## 6. 프론트엔드 UI 비교

### 6.1 기존 (조직도 기반)

```
🏢 지식 컨테이너
├─ 경영진
│  ├─ CEO
│  └─ 이사회
├─ R&D센터
│  ├─ 배터리팀 (280건)
│  ├─ AI팀 (240건)
│  └─ 플랫폼팀
└─ 품질관리팀
```

### 6.2 개선 (IPC 중심)

```
📊 IP 포트폴리오
├─ H: 전기 (780건)
│  ├─ H01M: 전기화학 셀 (280건)
│  │  ├─ H01M 10: 이차전지 (180건)
│  │  └─ H01M 12: 하이브리드 전지 (100건)
│  ├─ H04W: 무선통신 (320건)
│  └─ H04L: 디지털 전송 (180건)
├─ G: 물리학 (340건)
│  ├─ G06N: AI/ML (240건)
│  └─ G06F: 데이터 처리 (100건)
└─ B: 처리조작 (220건)
   └─ B60L: 전기차 (220건)
```

---

## 7. 최종 권고사항

### ✅ IPC 중심 전환 강력 추천

**이유**:
1. **본질에 충실**: 특허 관리는 기술 분류가 핵심
2. **국제 표준**: IPC는 전 세계 특허청 표준
3. **조직 독립성**: 조직 개편과 무관
4. **확장성**: CPC, 인용 분석 등 고급 기능 추가 용이
5. **복잡도 감소**: SAP 연동 불필요

### 단계적 전환 계획

**즉시 (1개월)**:
1. `tb_ipc_permissions` 테이블 생성
2. `ip_portfolio.py` API 구현
3. IPC 트리 프론트엔드

**단기 (2~3개월)**:
4. 기존 조직 권한 → IPC 권한 마이그레이션
5. 사용자 교육 및 병행 운영
6. containers.py → deprecated

**장기 (6개월 후)**:
7. containers.py 완전 제거
8. 레거시 데이터 아카이빙

---

## 8. 구현 우선순위

### 우선순위 1 (즉시 착수) ⭐⭐⭐
1. **tb_ipc_permissions 테이블 생성** (Alembic 마이그레이션)
2. **ip_portfolio.py 라우터 생성** (IPC 트리, 특허 목록)

### 우선순위 2 (1주 내) ⭐⭐
3. **프론트엔드 IPC 트리 네비게이션**
4. **특허 카드 컴포넌트**

### 우선순위 3 (2주 내) ⭐
5. **대시보드 통계 위젯**
6. **권한 마이그레이션 스크립트**

---

## 결론

**조직도 기반 컨테이너를 IPC 분류 체계로 완전 대체하는 것을 강력 권장합니다.**

핵심 이유:
- ✅ 특허 관리 본질에 부합 (기술 분류)
- ✅ 국제 표준 준수 (IPC/CPC)
- ✅ 조직 독립성 (개편 영향 없음)
- ✅ 확장성 (고급 특허 분석 기능)
- ✅ 복잡도 감소 (SAP 연동 불필요)

다음 단계로 **마이그레이션 스크립트 작성**부터 시작하시겠습니까?

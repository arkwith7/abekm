"""
IPC 코드 관리 API - Phase 1 (관리자용)
국제특허분류(IPC) 마스터 데이터 관리 및 조회 기능
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from loguru import logger

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models import User, TbIpcCode, TbPatentMetadata


router = APIRouter(prefix="/api/v1/admin/ipc", tags=["🗂️ IPC Code Management"])


# =============================================================================
# Request/Response Models
# =============================================================================

class IPCCodeBase(BaseModel):
    """IPC 코드 기본 정보"""
    code: str = Field(..., max_length=20, description="IPC 코드 (예: H04W, H04W 4/00)")
    level: str = Field(..., description="분류 레벨 (SECTION/CLASS/SUBCLASS/GROUP/SUBGROUP)")
    parent_code: Optional[str] = Field(None, description="상위 코드")
    description_ko: Optional[str] = Field(None, description="한글 설명")
    description_en: Optional[str] = Field(None, description="영문 설명")
    section: Optional[str] = Field(None, max_length=1, description="섹션 (A~H)")
    class_code: Optional[str] = Field(None, max_length=3, description="클래스")
    subclass_code: Optional[str] = Field(None, max_length=4, description="서브클래스")


class IPCCodeCreate(IPCCodeBase):
    """IPC 코드 생성 요청"""
    pass


class IPCCodeUpdate(BaseModel):
    """IPC 코드 수정 요청"""
    description_ko: Optional[str] = None
    description_en: Optional[str] = None
    is_active: Optional[str] = Field(None, pattern="^[YN]$")


class IPCCodeResponse(IPCCodeBase):
    """IPC 코드 응답"""
    is_active: str
    patent_count: int = Field(default=0, description="해당 IPC를 가진 특허 수")
    created_date: str
    last_modified_date: Optional[str] = None
    
    class Config:
        from_attributes = True


class IPCTreeNode(BaseModel):
    """IPC 트리 노드"""
    code: str
    level: str
    description_ko: Optional[str]
    description_en: Optional[str]
    is_active: str
    patent_count: int = 0
    children: List["IPCTreeNode"] = Field(default_factory=list)


class IPCCodeListResponse(BaseModel):
    """IPC 코드 목록 응답"""
    ipc_codes: List[IPCCodeResponse]
    total: int
    page: int
    page_size: int


class IPCTreeResponse(BaseModel):
    """IPC 트리 응답"""
    tree: List[IPCTreeNode]


class IPCStatistics(BaseModel):
    """IPC 통계"""
    total_codes: int
    active_codes: int
    inactive_codes: int
    section_count: int
    class_count: int
    subclass_count: int
    total_patents: int
    unclassified_patents: int
    top_used_codes: List[Dict[str, Any]]


# =============================================================================
# Helper Functions
# =============================================================================

async def get_ipc_code(db: AsyncSession, code: str) -> Optional[TbIpcCode]:
    """IPC 코드 조회"""
    stmt = select(TbIpcCode).where(TbIpcCode.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_patent_count_by_ipc(db: AsyncSession, ipc_code: str) -> int:
    """특정 IPC 코드를 가진 특허 수 조회"""
    stmt = select(func.count()).select_from(TbPatentMetadata).where(
        and_(
            TbPatentMetadata.del_yn == 'N',
            or_(
                TbPatentMetadata.main_ipc_code == ipc_code,
                TbPatentMetadata.ipc_codes.contains(ipc_code)
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def build_ipc_tree_recursive(
    db: AsyncSession,
    parent_code: Optional[str],
    include_patent_count: bool = False
) -> List[IPCTreeNode]:
    """재귀적으로 IPC 트리 생성"""
    stmt = select(TbIpcCode).where(
        TbIpcCode.parent_code == parent_code,
        TbIpcCode.is_active == 'Y'
    ).order_by(TbIpcCode.code)
    
    result = await db.execute(stmt)
    nodes = result.scalars().all()
    
    tree = []
    for node in nodes:
        patent_count = 0
        if include_patent_count:
            patent_count = await get_patent_count_by_ipc(db, node.code)
        
        children = await build_ipc_tree_recursive(db, node.code, include_patent_count)
        
        tree.append(IPCTreeNode(
            code=node.code,
            level=node.level,
            description_ko=node.description_ko,
            description_en=node.description_en,
            is_active=node.is_active,
            patent_count=patent_count,
            children=children
        ))
    
    return tree


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/codes", response_model=IPCCodeListResponse, summary="IPC 코드 목록 조회")
async def list_ipc_codes(
    level: Optional[str] = Query(None, description="분류 레벨 필터 (SECTION/CLASS/SUBCLASS/GROUP/SUBGROUP)"),
    parent_code: Optional[str] = Query(None, description="상위 코드 필터"),
    search: Optional[str] = Query(None, description="검색 키워드 (코드/한글설명/영문설명)"),
    is_active: Optional[str] = Query(None, pattern="^[YN]$", description="활성 여부 (Y/N)"),
    section: Optional[str] = Query(None, max_length=1, description="섹션 필터 (A~H)"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=200, description="페이지 크기"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 코드 목록 조회 (관리자 전용)
    
    - 레벨, 상위 코드, 섹션 필터링 지원
    - 코드/설명 키워드 검색
    - 각 IPC 코드의 특허 수 포함
    """
    # 기본 쿼리
    stmt = select(TbIpcCode)
    count_stmt = select(func.count()).select_from(TbIpcCode)
    
    # 필터 조건
    conditions = []
    
    if level:
        conditions.append(TbIpcCode.level == level)
    
    if parent_code:
        conditions.append(TbIpcCode.parent_code == parent_code)
    
    if search:
        search_pattern = f"%{search}%"
        conditions.append(
            or_(
                TbIpcCode.code.ilike(search_pattern),
                TbIpcCode.description_ko.ilike(search_pattern),
                TbIpcCode.description_en.ilike(search_pattern)
            )
        )
    
    if is_active:
        conditions.append(TbIpcCode.is_active == is_active)
    
    if section:
        conditions.append(TbIpcCode.section == section.upper())
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))
    
    # 정렬 및 페이징
    stmt = stmt.order_by(TbIpcCode.code).offset((page - 1) * page_size).limit(page_size)
    
    # 실행
    result = await db.execute(stmt)
    ipc_codes = result.scalars().all()
    
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    # 각 IPC 코드의 특허 수 조회
    ipc_responses = []
    for ipc in ipc_codes:
        patent_count = await get_patent_count_by_ipc(db, ipc.code)
        ipc_responses.append(IPCCodeResponse(
            code=ipc.code,
            level=ipc.level,
            parent_code=ipc.parent_code,
            description_ko=ipc.description_ko,
            description_en=ipc.description_en,
            section=ipc.section,
            class_code=ipc.class_code,
            subclass_code=ipc.subclass_code,
            is_active=ipc.is_active,
            patent_count=patent_count,
            created_date=ipc.created_date.isoformat() if ipc.created_date else None,
            last_modified_date=ipc.last_modified_date.isoformat() if ipc.last_modified_date else None
        ))
    
    return IPCCodeListResponse(
        ipc_codes=ipc_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/codes/tree", response_model=IPCTreeResponse, summary="IPC 코드 트리 조회")
async def get_ipc_tree(
    root_section: Optional[str] = Query(None, max_length=1, description="루트 섹션 (A~H, 전체 조회 시 생략)"),
    include_patent_count: bool = Query(False, description="특허 수 포함 여부"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 코드 계층 구조 트리 조회 (관리자 전용)
    
    - 섹션부터 하위 클래스, 서브클래스, 그룹까지 전체 트리 반환
    - include_patent_count=true 시 각 노드의 특허 수 포함 (성능 저하 주의)
    """
    if root_section:
        # 특정 섹션만 조회
        tree = await build_ipc_tree_recursive(db, root_section.upper(), include_patent_count)
    else:
        # 전체 섹션 조회
        tree = await build_ipc_tree_recursive(db, None, include_patent_count)
    
    return IPCTreeResponse(tree=tree)


@router.post("/codes", response_model=IPCCodeResponse, status_code=status.HTTP_201_CREATED, summary="IPC 코드 추가")
async def create_ipc_code(
    ipc_create: IPCCodeCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 IPC 코드 추가 (관리자 전용)
    
    - 코드 중복 체크
    - 부모 코드 존재 여부 검증
    """
    # 중복 체크
    existing = await get_ipc_code(db, ipc_create.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IPC 코드 '{ipc_create.code}'가 이미 존재합니다."
        )
    
    # 부모 코드 검증
    if ipc_create.parent_code:
        parent = await get_ipc_code(db, ipc_create.parent_code)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"상위 코드 '{ipc_create.parent_code}'가 존재하지 않습니다."
            )
    
    # 생성
    new_ipc = TbIpcCode(
        code=ipc_create.code,
        level=ipc_create.level,
        parent_code=ipc_create.parent_code,
        description_ko=ipc_create.description_ko,
        description_en=ipc_create.description_en,
        section=ipc_create.section,
        class_code=ipc_create.class_code,
        subclass_code=ipc_create.subclass_code,
        is_active='Y'
    )
    
    db.add(new_ipc)
    await db.commit()
    await db.refresh(new_ipc)
    
    logger.info(f"IPC 코드 추가: {ipc_create.code} by {current_user.emp_no}")
    
    return IPCCodeResponse(
        code=new_ipc.code,
        level=new_ipc.level,
        parent_code=new_ipc.parent_code,
        description_ko=new_ipc.description_ko,
        description_en=new_ipc.description_en,
        section=new_ipc.section,
        class_code=new_ipc.class_code,
        subclass_code=new_ipc.subclass_code,
        is_active=new_ipc.is_active,
        patent_count=0,
        created_date=new_ipc.created_date.isoformat() if new_ipc.created_date else None,
        last_modified_date=new_ipc.last_modified_date.isoformat() if new_ipc.last_modified_date else None
    )


@router.patch("/codes/{code}", response_model=IPCCodeResponse, summary="IPC 코드 수정")
async def update_ipc_code(
    code: str,
    ipc_update: IPCCodeUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 코드 수정 (관리자 전용)
    
    - 설명 수정 가능
    - 활성/비활성 토글 가능
    - 코드 자체는 변경 불가 (참조 무결성)
    """
    ipc = await get_ipc_code(db, code)
    if not ipc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IPC 코드 '{code}'를 찾을 수 없습니다."
        )
    
    # 수정
    if ipc_update.description_ko is not None:
        ipc.description_ko = ipc_update.description_ko
    
    if ipc_update.description_en is not None:
        ipc.description_en = ipc_update.description_en
    
    if ipc_update.is_active is not None:
        ipc.is_active = ipc_update.is_active
    
    await db.commit()
    await db.refresh(ipc)
    
    logger.info(f"IPC 코드 수정: {code} by {current_user.emp_no}")
    
    patent_count = await get_patent_count_by_ipc(db, code)
    
    return IPCCodeResponse(
        code=ipc.code,
        level=ipc.level,
        parent_code=ipc.parent_code,
        description_ko=ipc.description_ko,
        description_en=ipc.description_en,
        section=ipc.section,
        class_code=ipc.class_code,
        subclass_code=ipc.subclass_code,
        is_active=ipc.is_active,
        patent_count=patent_count,
        created_date=ipc.created_date.isoformat() if ipc.created_date else None,
        last_modified_date=ipc.last_modified_date.isoformat() if ipc.last_modified_date else None
    )


@router.get("/codes/{code}", response_model=IPCCodeResponse, summary="IPC 코드 상세 조회")
async def get_ipc_code_detail(
    code: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 IPC 코드 상세 조회 (관리자 전용)
    """
    ipc = await get_ipc_code(db, code)
    if not ipc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IPC 코드 '{code}'를 찾을 수 없습니다."
        )
    
    patent_count = await get_patent_count_by_ipc(db, code)
    
    return IPCCodeResponse(
        code=ipc.code,
        level=ipc.level,
        parent_code=ipc.parent_code,
        description_ko=ipc.description_ko,
        description_en=ipc.description_en,
        section=ipc.section,
        class_code=ipc.class_code,
        subclass_code=ipc.subclass_code,
        is_active=ipc.is_active,
        patent_count=patent_count,
        created_date=ipc.created_date.isoformat() if ipc.created_date else None,
        last_modified_date=ipc.last_modified_date.isoformat() if ipc.last_modified_date else None
    )


@router.get("/statistics", response_model=IPCStatistics, summary="IPC 활용 통계")
async def get_ipc_statistics(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    IPC 코드 활용 현황 통계 (관리자 전용)
    
    - 전체/활성/비활성 코드 수
    - 레벨별 코드 수
    - 전체 특허 수 및 미분류 특허 수
    - 가장 많이 사용된 상위 20개 IPC 코드
    """
    # 전체 코드 수
    total_stmt = select(func.count()).select_from(TbIpcCode)
    total_result = await db.execute(total_stmt)
    total_codes = total_result.scalar() or 0
    
    # 활성 코드 수
    active_stmt = select(func.count()).select_from(TbIpcCode).where(TbIpcCode.is_active == 'Y')
    active_result = await db.execute(active_stmt)
    active_codes = active_result.scalar() or 0
    
    inactive_codes = total_codes - active_codes
    
    # 레벨별 코드 수
    section_stmt = select(func.count()).select_from(TbIpcCode).where(TbIpcCode.level == 'SECTION')
    section_result = await db.execute(section_stmt)
    section_count = section_result.scalar() or 0
    
    class_stmt = select(func.count()).select_from(TbIpcCode).where(TbIpcCode.level == 'CLASS')
    class_result = await db.execute(class_stmt)
    class_count = class_result.scalar() or 0
    
    subclass_stmt = select(func.count()).select_from(TbIpcCode).where(TbIpcCode.level == 'SUBCLASS')
    subclass_result = await db.execute(subclass_stmt)
    subclass_count = subclass_result.scalar() or 0
    
    # 전체 특허 수
    total_patents_stmt = select(func.count()).select_from(TbPatentMetadata).where(TbPatentMetadata.del_yn == 'N')
    total_patents_result = await db.execute(total_patents_stmt)
    total_patents = total_patents_result.scalar() or 0
    
    # 미분류 특허 수 (main_ipc_code가 NULL인 경우)
    unclassified_stmt = select(func.count()).select_from(TbPatentMetadata).where(
        and_(
            TbPatentMetadata.del_yn == 'N',
            TbPatentMetadata.main_ipc_code.is_(None)
        )
    )
    unclassified_result = await db.execute(unclassified_stmt)
    unclassified_patents = unclassified_result.scalar() or 0
    
    # 가장 많이 사용된 IPC 코드 Top 20
    top_used_stmt = select(
        TbPatentMetadata.main_ipc_code,
        func.count().label('count')
    ).where(
        and_(
            TbPatentMetadata.del_yn == 'N',
            TbPatentMetadata.main_ipc_code.isnot(None)
        )
    ).group_by(TbPatentMetadata.main_ipc_code).order_by(desc('count')).limit(20)
    
    top_used_result = await db.execute(top_used_stmt)
    top_used_raw = top_used_result.all()
    
    top_used_codes = []
    for row in top_used_raw:
        ipc_code = row[0]
        count = row[1]
        
        # IPC 코드 상세 조회
        ipc = await get_ipc_code(db, ipc_code)
        top_used_codes.append({
            "ipc_code": ipc_code,
            "description_ko": ipc.description_ko if ipc else None,
            "patent_count": count
        })
    
    return IPCStatistics(
        total_codes=total_codes,
        active_codes=active_codes,
        inactive_codes=inactive_codes,
        section_count=section_count,
        class_count=class_count,
        subclass_count=subclass_count,
        total_patents=total_patents,
        unclassified_patents=unclassified_patents,
        top_used_codes=top_used_codes
    )

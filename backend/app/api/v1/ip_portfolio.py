"""IP 포트폴리오 API (IPC 중심)

- IPC 트리(권한 기반)
- IPC 범위 내 특허 목록/상세
- 대시보드 통계(권한 기반)

"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import TbIpcCode, TbPatentMetadata, User
from app.services.auth.ipc_permission_service import IpcPermissionService


router = APIRouter(prefix="/api/v1/ip-portfolio", tags=["📁 IP Portfolio"])


# =============================================================================
# Response Models
# =============================================================================

class IPCTreeNode(BaseModel):
    code: str
    level: str
    description_ko: Optional[str] = None
    description_en: Optional[str] = None
    patent_count: int = 0
    children: List["IPCTreeNode"] = Field(default_factory=list)


class IPCTreeResponse(BaseModel):
    tree: List[IPCTreeNode]


class PatentCard(BaseModel):
    metadata_id: int
    application_number: str
    applicant: Optional[str] = None
    patent_status: Optional[str] = None
    legal_status: Optional[str] = None
    main_ipc_code: Optional[str] = None
    primary_ipc_section: Optional[str] = None
    abstract: Optional[str] = None


class PatentListResponse(BaseModel):
    items: List[PatentCard]
    total: int
    page: int
    page_size: int


class PatentDetailResponse(PatentCard):
    publication_number: Optional[str] = None
    registration_number: Optional[str] = None
    ipc_codes: Optional[str] = None
    application_date: Optional[str] = None
    publication_date: Optional[str] = None
    registration_date: Optional[str] = None
    keywords: Optional[List[str]] = None


class DashboardStatsResponse(BaseModel):
    total_patents: int
    by_patent_status: List[Dict[str, Any]]
    by_ipc_section: List[Dict[str, Any]]


class MyIpcPermission(BaseModel):
    permission_id: int
    ipc_code: str
    role_id: str
    include_children: bool
    access_scope: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    is_active: bool


# =============================================================================
# Helpers
# =============================================================================

def _to_card(p: TbPatentMetadata) -> PatentCard:
    return PatentCard(
        metadata_id=int(p.metadata_id),
        application_number=str(p.application_number),
        applicant=getattr(p, "applicant", None),
        patent_status=getattr(p, "patent_status", None),
        legal_status=getattr(p, "legal_status", None),
        main_ipc_code=getattr(p, "main_ipc_code", None),
        primary_ipc_section=getattr(p, "primary_ipc_section", None),
        abstract=getattr(p, "abstract", None),
    )


def _build_tree(nodes: List[TbIpcCode], counts_by_code: dict[str, int]) -> List[IPCTreeNode]:
    by_code: dict[str, TbIpcCode] = {str(n.code): n for n in nodes}
    children_map: dict[str | None, list[str]] = {}
    for n in nodes:
        parent = getattr(n, "parent_code", None)
        children_map.setdefault(parent, []).append(str(n.code))

    # roots = nodes whose parent not in selected set
    roots: list[str] = []
    for code, n in by_code.items():
        parent = getattr(n, "parent_code", None)
        if not parent or str(parent) not in by_code:
            roots.append(code)

    def build(code: str) -> IPCTreeNode:
        n = by_code[code]
        child_codes = sorted(children_map.get(code, []))
        return IPCTreeNode(
            code=str(n.code),
            level=str(n.level),
            description_ko=getattr(n, "description_ko", None),
            description_en=getattr(n, "description_en", None),
            patent_count=int(counts_by_code.get(str(n.code), 0)),
            children=[build(c) for c in child_codes],
        )

    return [build(c) for c in sorted(roots)]


async def _patent_counts_by_main_ipc(db: AsyncSession, ipc_codes: set[str]) -> dict[str, int]:
    if not ipc_codes:
        return {}
    stmt = (
        select(TbPatentMetadata.main_ipc_code, func.count())
        .where(
            and_(
                TbPatentMetadata.del_yn == "N",
                TbPatentMetadata.main_ipc_code.in_(list(ipc_codes)),
            )
        )
        .group_by(TbPatentMetadata.main_ipc_code)
    )
    result = await db.execute(stmt)
    return {str(code): int(cnt) for code, cnt in result.all() if code}


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/my-permissions", response_model=List[MyIpcPermission], summary="내 IPC 권한 목록")
async def my_ipc_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = IpcPermissionService(db)
    perms = await service.list_active_permissions(str(current_user.emp_no))
    return [
        MyIpcPermission(
            permission_id=int(p.permission_id),
            ipc_code=str(p.ipc_code),
            role_id=str(p.role_id),
            include_children=bool(p.include_children),
            access_scope=str(p.access_scope),
            valid_from=p.valid_from.isoformat() if getattr(p, "valid_from", None) else None,
            valid_until=p.valid_until.isoformat() if getattr(p, "valid_until", None) else None,
            is_active=bool(p.is_active),
        )
        for p in perms
    ]


@router.get("/ipc-tree", response_model=IPCTreeResponse, summary="IPC 트리(권한 기반)")
async def ipc_tree(
    include_patent_count: bool = Query(False, description="각 노드 특허 수 포함 여부"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = IpcPermissionService(db)
    allowed_codes = await service.get_allowed_ipc_codes(str(current_user.emp_no), min_role="VIEWER")
    if not allowed_codes:
        return IPCTreeResponse(tree=[])

    stmt = (
        select(TbIpcCode)
        .where(and_(TbIpcCode.code.in_(list(allowed_codes)), TbIpcCode.is_active == "Y"))
        .order_by(TbIpcCode.code)
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    counts: dict[str, int] = {}
    if include_patent_count:
        counts = await _patent_counts_by_main_ipc(db, allowed_codes)

    return IPCTreeResponse(tree=_build_tree(nodes, counts))


@router.get("/patents", response_model=PatentListResponse, summary="특허 목록(권한 기반)")
async def list_patents(
    ipc_code: Optional[str] = Query(None, description="선택 IPC 코드"),
    include_children: bool = Query(True, description="선택 IPC 하위까지 포함"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = IpcPermissionService(db)
    user_emp_no = str(current_user.emp_no)

    allowed_codes = await service.get_allowed_ipc_codes(user_emp_no, min_role="VIEWER")
    if not allowed_codes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IPC 접근 권한이 없습니다")

    target_codes: set[str]
    if ipc_code:
        if not await service.has_ipc_access(user_emp_no, ipc_code, min_role="VIEWER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 IPC 접근 권한이 없습니다")

        if include_children:
            descendants = await service.get_descendant_codes([ipc_code])
            target_codes = set(descendants) & set(allowed_codes)
        else:
            target_codes = {str(ipc_code)} if str(ipc_code) in allowed_codes else set()
    else:
        target_codes = set(allowed_codes)

    if not target_codes:
        return PatentListResponse(items=[], total=0, page=page, page_size=page_size)

    base_where = and_(TbPatentMetadata.del_yn == "N", TbPatentMetadata.main_ipc_code.in_(list(target_codes)))

    total_stmt = select(func.count()).select_from(TbPatentMetadata).where(base_where)
    total_result = await db.execute(total_stmt)
    total = int(total_result.scalar() or 0)

    stmt = (
        select(TbPatentMetadata)
        .where(base_where)
        .order_by(TbPatentMetadata.metadata_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = [_to_card(p) for p in result.scalars().all()]

    return PatentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/patents/{metadata_id}", response_model=PatentDetailResponse, summary="특허 상세(권한 기반)")
async def get_patent_detail(
    metadata_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TbPatentMetadata).where(TbPatentMetadata.metadata_id == metadata_id)
    result = await db.execute(stmt)
    patent = result.scalar_one_or_none()
    if not patent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="특허를 찾을 수 없습니다")

    service = IpcPermissionService(db)
    user_emp_no = str(current_user.emp_no)
    ipc = getattr(patent, "main_ipc_code", None)

    if ipc:
        if not await service.has_ipc_access(user_emp_no, str(ipc), min_role="VIEWER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 특허 접근 권한이 없습니다")
    else:
        # 분류 없는 특허는 기본적으로 접근 금지 (필요 시 정책으로 완화)
        if not getattr(current_user, "is_admin", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 특허 접근 권한이 없습니다")

    return PatentDetailResponse(
        **_to_card(patent).model_dump(),
        publication_number=getattr(patent, "publication_number", None),
        registration_number=getattr(patent, "registration_number", None),
        ipc_codes=getattr(patent, "ipc_codes", None),
        application_date=patent.application_date.isoformat() if getattr(patent, "application_date", None) else None,
        publication_date=patent.publication_date.isoformat() if getattr(patent, "publication_date", None) else None,
        registration_date=patent.registration_date.isoformat() if getattr(patent, "registration_date", None) else None,
        keywords=list(getattr(patent, "keywords", None) or []) or None,
    )


@router.get("/dashboard-stats", response_model=DashboardStatsResponse, summary="IP 포트폴리오 대시보드 통계")
async def dashboard_stats(
    ipc_code: Optional[str] = Query(None, description="선택 IPC 코드 (없으면 권한 전체 범위)"),
    include_children: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = IpcPermissionService(db)
    user_emp_no = str(current_user.emp_no)

    allowed_codes = await service.get_allowed_ipc_codes(user_emp_no, min_role="VIEWER")
    if not allowed_codes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IPC 접근 권한이 없습니다")

    target_codes: set[str]
    if ipc_code:
        if not await service.has_ipc_access(user_emp_no, ipc_code, min_role="VIEWER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 IPC 접근 권한이 없습니다")
        if include_children:
            descendants = await service.get_descendant_codes([ipc_code])
            target_codes = set(descendants) & set(allowed_codes)
        else:
            target_codes = {str(ipc_code)} if str(ipc_code) in allowed_codes else set()
    else:
        target_codes = set(allowed_codes)

    if not target_codes:
        return DashboardStatsResponse(total_patents=0, by_patent_status=[], by_ipc_section=[])

    where_clause = and_(TbPatentMetadata.del_yn == "N", TbPatentMetadata.main_ipc_code.in_(list(target_codes)))

    total_stmt = select(func.count()).select_from(TbPatentMetadata).where(where_clause)
    total_result = await db.execute(total_stmt)
    total = int(total_result.scalar() or 0)

    status_stmt = (
        select(TbPatentMetadata.patent_status, func.count())
        .where(where_clause)
        .group_by(TbPatentMetadata.patent_status)
        .order_by(func.count().desc())
    )
    status_result = await db.execute(status_stmt)
    by_status = [
        {"patent_status": (s or "UNKNOWN"), "count": int(c)} for s, c in status_result.all()
    ]

    section_stmt = (
        select(TbPatentMetadata.primary_ipc_section, func.count())
        .where(where_clause)
        .group_by(TbPatentMetadata.primary_ipc_section)
        .order_by(func.count().desc())
    )
    section_result = await db.execute(section_stmt)
    by_section = [
        {"primary_ipc_section": (s or "UNKNOWN"), "count": int(c)} for s, c in section_result.all()
    ]

    return DashboardStatsResponse(total_patents=total, by_patent_status=by_status, by_ipc_section=by_section)

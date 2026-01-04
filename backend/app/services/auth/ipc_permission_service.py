from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TbIpcCode, TbIpcPermissions


_ROLE_RANK: dict[str, int] = {
    "VIEWER": 1,
    "EDITOR": 2,
    "MANAGER": 3,
    "ADMIN": 4,
}


def _role_rank(role: Optional[str]) -> int:
    if not role:
        return 0
    return _ROLE_RANK.get(role.upper(), 0)


@dataclass(frozen=True)
class IpcPermissionRow:
    ipc_code: str
    role_id: str
    include_children: bool


class IpcPermissionService:
    """IPC 기반 IP 포트폴리오 권한 조회/검증 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active_permissions(self, user_emp_no: str) -> list[TbIpcPermissions]:
        now = datetime.utcnow()
        stmt = (
            select(TbIpcPermissions)
            .where(
                and_(
                    TbIpcPermissions.user_emp_no == str(user_emp_no),
                    TbIpcPermissions.is_active.is_(True),
                    TbIpcPermissions.valid_from <= now,
                    or_(TbIpcPermissions.valid_until.is_(None), TbIpcPermissions.valid_until >= now),
                )
            )
            .order_by(TbIpcPermissions.ipc_code)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_active_permission_rows(
        self,
        user_emp_no: str,
        min_role: str = "VIEWER",
    ) -> list[IpcPermissionRow]:
        perms = await self.list_active_permissions(user_emp_no)
        min_rank = _role_rank(min_role)
        rows: list[IpcPermissionRow] = []
        for p in perms:
            if _role_rank(getattr(p, "role_id", None)) >= min_rank:
                rows.append(
                    IpcPermissionRow(
                        ipc_code=str(p.ipc_code),
                        role_id=str(p.role_id),
                        include_children=bool(p.include_children),
                    )
                )
        return rows

    async def has_ipc_access(
        self,
        user_emp_no: str,
        ipc_code: str,
        min_role: str = "VIEWER",
    ) -> bool:
        """사용자가 특정 IPC 코드(또는 해당 코드가 하위일 때 상위 권한 포함) 접근 가능한지."""
        now = datetime.utcnow()
        target = str(ipc_code)

        # ancestors CTE: target -> parent -> ...
        ancestors = (
            select(TbIpcCode.code.label("code"), TbIpcCode.parent_code.label("parent_code"))
            .where(TbIpcCode.code == target)
            .cte("ipc_ancestors", recursive=True)
        )
        ancestors = ancestors.union_all(
            select(TbIpcCode.code, TbIpcCode.parent_code).where(TbIpcCode.code == ancestors.c.parent_code)
        )

        stmt = (
            select(TbIpcPermissions)
            .join(ancestors, TbIpcPermissions.ipc_code == ancestors.c.code)
            .where(
                and_(
                    TbIpcPermissions.user_emp_no == str(user_emp_no),
                    TbIpcPermissions.is_active.is_(True),
                    TbIpcPermissions.valid_from <= now,
                    or_(TbIpcPermissions.valid_until.is_(None), TbIpcPermissions.valid_until >= now),
                )
            )
        )
        result = await self.db.execute(stmt)
        perms = list(result.scalars().all())

        min_rank = _role_rank(min_role)
        for p in perms:
            if _role_rank(getattr(p, "role_id", None)) < min_rank:
                continue
            # 직접 권한이면 include_children과 무관
            if str(p.ipc_code) == target:
                return True
            # 상위 권한이면 include_children이 True일 때만
            if bool(getattr(p, "include_children", False)):
                return True

        return False

    async def get_descendant_codes(self, roots: Iterable[str]) -> set[str]:
        roots_list = [str(r) for r in roots if r]
        if not roots_list:
            return set()

        tree = (
            select(TbIpcCode.code.label("code"), TbIpcCode.parent_code.label("parent_code"))
            .where(TbIpcCode.code.in_(roots_list))
            .cte("ipc_desc", recursive=True)
        )
        tree = tree.union_all(
            select(TbIpcCode.code, TbIpcCode.parent_code).where(TbIpcCode.parent_code == tree.c.code)
        )

        result = await self.db.execute(select(tree.c.code).distinct())
        return {str(row[0]) for row in result.all() if row[0]}

    async def get_allowed_ipc_codes(self, user_emp_no: str, min_role: str = "VIEWER") -> set[str]:
        rows = await self.list_active_permission_rows(user_emp_no, min_role=min_role)
        if not rows:
            return set()

        direct_only = {r.ipc_code for r in rows if not r.include_children}
        roots_with_children = [r.ipc_code for r in rows if r.include_children]
        descendants = await self.get_descendant_codes(roots_with_children)
        return set(descendants) | set(direct_only)

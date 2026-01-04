"""Admin IPC Permission Management API tests.

Covers:
- GET    /api/v1/admin/ipc-permissions
- POST   /api/v1/admin/ipc-permissions
- PUT    /api/v1/admin/ipc-permissions/{permission_id}
- DELETE /api/v1/admin/ipc-permissions/{permission_id}
- GET    /api/v1/admin/ipc-permissions/user/{emp_no}
- POST   /api/v1/admin/ipc-permissions/bulk
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete

from app.models.patent.ipc_models import TbIpcCode, TbIpcPermissions


@pytest.mark.asyncio
class TestAdminIpcPermissions:
    
    @pytest.fixture(autouse=True)
    async def cleanup_test_data(self, db_session: AsyncSession):
        """각 테스트 전후에 테스트 데이터 정리"""
        # 테스트 전: 정리
        await db_session.execute(sql_delete(TbIpcPermissions))
        await db_session.commit()
        
        yield
        
        # 테스트 후: 정리 (선택적)
        await db_session.execute(sql_delete(TbIpcPermissions))
        await db_session.commit()
    
    async def _ensure_ipc_code(self, db_session: AsyncSession, code: str = "H04W") -> TbIpcCode:
        """IPC 코드가 없으면 생성, 있으면 조회"""
        result = await db_session.execute(
            select(TbIpcCode).where(TbIpcCode.code == code)
        )
        ipc = result.scalar_one_or_none()
        
        if ipc is None:
            ipc = TbIpcCode(
                code=code,
                level="SUBCLASS",
                parent_code="H04",
                description_ko="테스트 IPC",
                section=code[0],
                class_code=code[:3],
                subclass_code=code[:4],
                is_active="Y",
            )
            db_session.add(ipc)
            await db_session.commit()
        
        return ipc

    async def test_list_empty(self, async_client_with_admin: AsyncClient):
        res = await async_client_with_admin.get("/api/v1/admin/ipc-permissions")
        assert res.status_code == 200
        data = res.json()
        assert data["permissions"] == []
        assert data["total_count"] == 0
        assert data["page"] == 1

    async def test_create_success(self, async_client_with_admin: AsyncClient, db_session: AsyncSession):
        ipc = await self._ensure_ipc_code(db_session, code="H04W")

        payload = {
            "user_emp_no": "test_user_001",
            "ipc_code": ipc.code,
            "role_id": "EDITOR",
            "access_scope": "FULL",
            "include_children": True,
        }
        res = await async_client_with_admin.post("/api/v1/admin/ipc-permissions", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["user_emp_no"] == "test_user_001"
        assert data["ipc_code"] == ipc.code
        assert data["role_id"] == "EDITOR"
        assert data["include_children"] is True

    async def test_create_duplicate_returns_409(self, async_client_with_admin: AsyncClient, db_session: AsyncSession):
        ipc = await self._ensure_ipc_code(db_session, code="G06N")

        payload = {
            "user_emp_no": "dup_user",
            "ipc_code": ipc.code,
            "role_id": "VIEWER",
            "access_scope": "FULL",
            "include_children": True,
        }
        res1 = await async_client_with_admin.post("/api/v1/admin/ipc-permissions", json=payload)
        assert res1.status_code == 200

        res2 = await async_client_with_admin.post("/api/v1/admin/ipc-permissions", json=payload)
        assert res2.status_code == 409

    async def test_update_permission(self, async_client_with_admin: AsyncClient, db_session: AsyncSession):
        ipc = await self._ensure_ipc_code(db_session, code="A01B")

        created = TbIpcPermissions(
            user_emp_no="upd_user",
            ipc_code=ipc.code,
            role_id="VIEWER",
            access_scope="FULL",
            include_children=False,
            is_active=True,
        )
        db_session.add(created)
        await db_session.commit()
        await db_session.refresh(created)

        payload = {"role_id": "EDITOR", "include_children": True}
        res = await async_client_with_admin.put(
            f"/api/v1/admin/ipc-permissions/{created.permission_id}",
            json=payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["permission_id"] == created.permission_id
        assert data["role_id"] == "EDITOR"
        assert data["include_children"] is True

    async def test_delete_permission(self, async_client_with_admin: AsyncClient, db_session: AsyncSession):
        ipc = await self._ensure_ipc_code(db_session, code="A01C")

        created = TbIpcPermissions(
            user_emp_no="del_user",
            ipc_code=ipc.code,
            role_id="VIEWER",
            access_scope="FULL",
            include_children=True,
            is_active=True,
        )
        db_session.add(created)
        await db_session.commit()
        await db_session.refresh(created)

        res = await async_client_with_admin.delete(
            f"/api/v1/admin/ipc-permissions/{created.permission_id}"
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

    async def test_get_user_permissions(self, async_client_with_admin: AsyncClient, db_session: AsyncSession):
        ipc1 = await self._ensure_ipc_code(db_session, code="H04L")
        ipc2 = await self._ensure_ipc_code(db_session, code="H04N")

        db_session.add_all(
            [
                TbIpcPermissions(
                    user_emp_no="u123",
                    ipc_code=ipc1.code,
                    role_id="VIEWER",
                    access_scope="FULL",
                    include_children=False,
                    is_active=True,
                ),
                TbIpcPermissions(
                    user_emp_no="u123",
                    ipc_code=ipc2.code,
                    role_id="EDITOR",
                    access_scope="FULL",
                    include_children=True,
                    is_active=True,
                ),
            ]
        )
        await db_session.commit()

        res = await async_client_with_admin.get("/api/v1/admin/ipc-permissions/user/u123")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert {p["ipc_code"] for p in data} == {ipc1.code, ipc2.code}

    async def test_bulk_create(self, async_client_with_admin: AsyncClient, db_session: AsyncSession):
        ipc1 = await self._ensure_ipc_code(db_session, code="B01D")
        ipc2 = await self._ensure_ipc_code(db_session, code="B01F")

        payload = {
            "permissions": [
                {
                    "user_emp_no": "bulk_user",
                    "ipc_code": ipc1.code,
                    "role_id": "VIEWER",
                    "access_scope": "FULL",
                    "include_children": True,
                },
                {
                    "user_emp_no": "bulk_user",
                    "ipc_code": ipc2.code,
                    "role_id": "EDITOR",
                    "access_scope": "FULL",
                    "include_children": False,
                },
            ]
        }
        res = await async_client_with_admin.post("/api/v1/admin/ipc-permissions/bulk", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert data["success_count"] == 2

    async def test_unauthorized_access(self, async_client: AsyncClient):
        res = await async_client.get("/api/v1/admin/ipc-permissions")
        assert res.status_code in (401, 403)

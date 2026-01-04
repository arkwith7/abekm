"""단위 테스트: IpcPermissionService

IPC 권한 서비스의 핵심 로직 단위 테스트
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth.ipc_permission_service import (
    IpcPermissionRow,
    IpcPermissionService,
    _role_rank,
)


class TestRoleRank:
    """역할 우선순위 계산 테스트"""

    def test_role_rank_viewer(self):
        assert _role_rank("VIEWER") == 1

    def test_role_rank_editor(self):
        assert _role_rank("EDITOR") == 2

    def test_role_rank_manager(self):
        assert _role_rank("MANAGER") == 3

    def test_role_rank_admin(self):
        assert _role_rank("ADMIN") == 4

    def test_role_rank_none(self):
        assert _role_rank(None) == 0

    def test_role_rank_unknown(self):
        assert _role_rank("UNKNOWN") == 0

    def test_role_rank_case_insensitive(self):
        assert _role_rank("viewer") == 1
        assert _role_rank("AdMiN") == 4


class TestIpcPermissionService:
    """IPC 권한 서비스 단위 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock AsyncSession"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        """테스트용 서비스 인스턴스"""
        return IpcPermissionService(mock_db)

    @pytest.mark.asyncio
    async def test_list_active_permissions_empty(self, service, mock_db):
        """권한 없는 사용자"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.list_active_permissions("test_user")

        assert result == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_active_permissions_with_data(self, service, mock_db):
        """활성 권한 조회"""
        mock_perm = MagicMock()
        mock_perm.user_emp_no = "test_user"
        mock_perm.ipc_code = "H04W"
        mock_perm.role_id = "VIEWER"
        mock_perm.include_children = True
        mock_perm.is_active = True
        mock_perm.valid_from = datetime.utcnow() - timedelta(days=1)
        mock_perm.valid_until = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_perm]
        mock_db.execute.return_value = mock_result

        result = await service.list_active_permissions("test_user")

        assert len(result) == 1
        assert result[0].ipc_code == "H04W"

    @pytest.mark.asyncio
    async def test_list_active_permission_rows_filters_by_role(self, service, mock_db):
        """최소 역할 필터링"""
        mock_perm_viewer = MagicMock()
        mock_perm_viewer.ipc_code = "H04W"
        mock_perm_viewer.role_id = "VIEWER"
        mock_perm_viewer.include_children = True

        mock_perm_admin = MagicMock()
        mock_perm_admin.ipc_code = "G06N"
        mock_perm_admin.role_id = "ADMIN"
        mock_perm_admin.include_children = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_perm_viewer, mock_perm_admin]
        mock_db.execute.return_value = mock_result

        # EDITOR 이상만 조회
        result = await service.list_active_permission_rows("test_user", min_role="EDITOR")

        assert len(result) == 1
        assert result[0].ipc_code == "G06N"
        assert result[0].role_id == "ADMIN"

    @pytest.mark.asyncio
    async def test_has_ipc_access_direct(self, service, mock_db):
        """직접 권한 확인"""
        mock_perm = MagicMock()
        mock_perm.ipc_code = "H04W"
        mock_perm.role_id = "VIEWER"
        mock_perm.include_children = True
        mock_perm.is_active = True
        mock_perm.valid_from = datetime.utcnow() - timedelta(days=1)
        mock_perm.valid_until = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_perm]
        mock_db.execute.return_value = mock_result

        result = await service.has_ipc_access("test_user", "H04W", min_role="VIEWER")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_ipc_access_no_permission(self, service, mock_db):
        """권한 없는 경우"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.has_ipc_access("test_user", "H04W", min_role="VIEWER")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_descendant_codes_empty(self, service, mock_db):
        """빈 루트 입력"""
        result = await service.get_descendant_codes([])
        assert result == set()

    @pytest.mark.asyncio
    async def test_get_descendant_codes_with_children(self, service, mock_db):
        """하위 코드 조회"""
        mock_result = MagicMock()
        mock_result.all.return_value = [("H04W",), ("H04W 4/00",), ("H04W 4/02",)]
        mock_db.execute.return_value = mock_result

        result = await service.get_descendant_codes(["H04W"])

        assert len(result) == 3
        assert "H04W" in result
        assert "H04W 4/00" in result

    @pytest.mark.asyncio
    async def test_get_allowed_ipc_codes_combines_direct_and_children(self, service, mock_db):
        """직접 권한 + include_children 권한 조합"""
        mock_perm1 = MagicMock()
        mock_perm1.ipc_code = "H04W"
        mock_perm1.role_id = "VIEWER"
        mock_perm1.include_children = True

        mock_perm2 = MagicMock()
        mock_perm2.ipc_code = "G06N"
        mock_perm2.role_id = "VIEWER"
        mock_perm2.include_children = False

        mock_result_perms = MagicMock()
        mock_result_perms.scalars.return_value.all.return_value = [mock_perm1, mock_perm2]

        mock_result_descendants = MagicMock()
        mock_result_descendants.all.return_value = [("H04W",), ("H04W 4/00",)]

        mock_db.execute.side_effect = [mock_result_perms, mock_result_descendants]

        result = await service.get_allowed_ipc_codes("test_user")

        assert "G06N" in result  # direct only
        assert "H04W" in result  # root with children
        assert "H04W 4/00" in result  # descendant


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

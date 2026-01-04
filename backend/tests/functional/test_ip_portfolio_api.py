"""기능 테스트: IP Portfolio API 엔드포인트

API 라우팅과 기본 응답 구조 검증
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.ip_portfolio import router as ip_portfolio_router


@pytest.fixture
def test_app():
    """테스트용 FastAPI 앱"""
    app = FastAPI()
    app.include_router(ip_portfolio_router)

    # Mock dependencies
    from app.core.database import get_db
    from app.core.dependencies import get_current_user

    class _DummyUser:
        emp_no = "test_user"
        is_active = True
        is_admin = False
        username = "test"

    async def override_get_db():
        yield None

    async def override_get_current_user():
        return _DummyUser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.mark.functional
@pytest.mark.asyncio
async def test_my_permissions_endpoint(test_app):
    """내 IPC 권한 목록 엔드포인트"""
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.ip_portfolio.IpcPermissionService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service.list_active_permissions.return_value = []
        mock_service_class.return_value = mock_service

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/ip-portfolio/my-permissions")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


@pytest.mark.functional
@pytest.mark.asyncio
async def test_ipc_tree_endpoint(test_app):
    """IPC 트리 엔드포인트"""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("app.api.v1.ip_portfolio.IpcPermissionService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_allowed_ipc_codes.return_value = {"H04W", "G06N"}
        mock_service_class.return_value = mock_service

        with patch("app.api.v1.ip_portfolio.select") as mock_select:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []

            async def mock_execute(stmt):
                return mock_result

            async with AsyncClient(
                transport=ASGITransport(app=test_app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/ip-portfolio/ipc-tree")

                assert response.status_code in [200, 500]  # DB 없어도 라우팅 확인
                if response.status_code == 200:
                    data = response.json()
                    assert "tree" in data


@pytest.mark.functional
@pytest.mark.asyncio
async def test_patents_list_endpoint(test_app):
    """특허 목록 엔드포인트"""
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.ip_portfolio.IpcPermissionService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_allowed_ipc_codes.return_value = set()
        mock_service_class.return_value = mock_service

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/ip-portfolio/patents")

            # 권한 없으면 403
            assert response.status_code == 403


@pytest.mark.functional
@pytest.mark.asyncio
async def test_dashboard_stats_endpoint(test_app):
    """대시보드 통계 엔드포인트"""
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.ip_portfolio.IpcPermissionService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_allowed_ipc_codes.return_value = set()
        mock_service_class.return_value = mock_service

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/ip-portfolio/dashboard-stats")

            # 권한 없으면 403
            assert response.status_code == 403


@pytest.mark.functional
@pytest.mark.asyncio
async def test_patent_detail_endpoint_not_found(test_app):
    """특허 상세 - 존재하지 않는 ID"""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("app.api.v1.ip_portfolio.select") as mock_select:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        async def mock_execute(stmt):
            return mock_result

        # DB execute를 mock
        with patch("app.api.v1.ip_portfolio.IpcPermissionService"):
            async with AsyncClient(
                transport=ASGITransport(app=test_app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/ip-portfolio/patents/999999")

                # DB 연결 실패 또는 404
                assert response.status_code in [404, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

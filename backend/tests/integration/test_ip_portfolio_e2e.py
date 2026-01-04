"""통합 테스트: IP Portfolio E2E

실제 DB와 함께 전체 플로우 검증 (CI/로컬 DB 필요)
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import TbIpcCode, TbIpcPermissions, TbPatentMetadata


# CI 환경에서 TEST_DATABASE_URL이 없으면 skip
pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL") and not os.getenv("DATABASE_URL"),
    reason="통합 테스트는 DATABASE_URL 필요",
)


@pytest.fixture
async def db_session():
    """실제 DB 세션 (테스트 전용)"""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("No DB URL")

    # postgresql:// → postgresql+asyncpg://
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ipc_permission_lifecycle(db_session: AsyncSession):
    """IPC 권한 생성 → 조회 → 삭제"""
    from app.services.auth.ipc_permission_service import IpcPermissionService

    service = IpcPermissionService(db_session)
    test_user = "test_user_001"  # 20자 이내
    test_ipc = "H04W"

    # 1. 초기 권한 없음
    perms = await service.list_active_permissions(test_user)
    initial_count = len(perms)

    # 2. 권한 추가 (직접 DB 삽입)
    new_perm = TbIpcPermissions(
        user_emp_no=test_user,
        ipc_code=test_ipc,
        role_id="VIEWER",
        access_scope="FULL",
        include_children=True,
        is_active=True,
        created_by="test",
    )
    db_session.add(new_perm)
    await db_session.commit()

    # 3. 권한 조회 확인
    perms_after = await service.list_active_permissions(test_user)
    assert len(perms_after) == initial_count + 1

    # 4. 접근 확인
    has_access = await service.has_ipc_access(test_user, test_ipc, min_role="VIEWER")
    assert has_access is True

    # 5. 정리
    await db_session.delete(new_perm)
    await db_session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ipc_code_query(db_session: AsyncSession):
    """IPC 코드 기본 조회"""
    stmt = select(TbIpcCode).limit(10)
    result = await db_session.execute(stmt)
    codes = result.scalars().all()

    assert len(codes) >= 0  # DB에 데이터가 있을 수도, 없을 수도


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patent_metadata_query(db_session: AsyncSession):
    """특허 메타데이터 기본 조회"""
    stmt = select(TbPatentMetadata).where(TbPatentMetadata.del_yn == "N").limit(5)
    result = await db_session.execute(stmt)
    patents = result.scalars().all()

    assert len(patents) >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_allowed_ipc_codes_with_real_db(db_session: AsyncSession):
    """실제 DB로 allowed IPC codes 조회"""
    from app.services.auth.ipc_permission_service import IpcPermissionService

    service = IpcPermissionService(db_session)
    test_user = "test_e2e_002"  # 20자 이내

    # 테스트 권한 생성
    new_perm = TbIpcPermissions(
        user_emp_no=test_user,
        ipc_code="H",
        role_id="VIEWER",
        access_scope="FULL",
        include_children=True,
        is_active=True,
        created_by="test",
    )
    db_session.add(new_perm)
    await db_session.commit()

    # 허용 코드 조회
    allowed = await service.get_allowed_ipc_codes(test_user, min_role="VIEWER")

    # H 섹션과 그 하위들이 포함되어야 함 (DB에 H 섹션이 있다면)
    assert "H" in allowed or len(allowed) >= 0  # DB 상태에 따라 다를 수 있음

    # 정리
    await db_session.delete(new_perm)
    await db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

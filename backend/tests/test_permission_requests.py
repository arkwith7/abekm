"""
권한 요청 시스템 테스트
"""
import pytest
from datetime import datetime, timedelta
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.auth.permission_request_models import TbPermissionRequests, TbAutoApprovalRules
from app.models.auth.user import User
from app.models.knowledge.knowledge_container import TbKnowledgeContainers


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """테스트 사용자 생성"""
    user = User(
        emp_no="TEST001",
        username="testuser",
        name="테스트사용자",
        email="test@example.com",
        department="테스트부서",
        position="사원",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_manager(db_session: AsyncSession):
    """테스트 관리자 생성"""
    manager = User(
        emp_no="MGR001",
        username="manager",
        name="관리자",
        email="manager@example.com",
        department="관리부서",
        position="부장",
        is_active=True
    )
    db_session.add(manager)
    await db_session.commit()
    await db_session.refresh(manager)
    return manager


@pytest.fixture
async def test_container(db_session: AsyncSession, test_manager):
    """테스트 컨테이너 생성"""
    container = TbKnowledgeContainers(
        container_id="TEST_CONTAINER_001",
        container_name="테스트 컨테이너",
        description="테스트용 컨테이너입니다",
        manager_emp_no=test_manager.emp_no,
        is_active=True
    )
    db_session.add(container)
    await db_session.commit()
    await db_session.refresh(container)
    return container


@pytest.fixture
async def auto_approval_rule(db_session: AsyncSession):
    """자동 승인 규칙 생성"""
    rule = TbAutoApprovalRules(
        rule_name="VIEWER 권한 자동 승인",
        role_id="VIEWER",
        conditions={"department": "테스트부서"},
        priority=1,
        is_active=True
    )
    db_session.add(rule)
    await db_session.commit()
    await db_session.refresh(rule)
    return rule


class TestPermissionRequestCreate:
    """권한 요청 생성 테스트"""

    @pytest.mark.asyncio
    async def test_create_permission_request_success(
        self,
        async_client: AsyncClient,
        test_user,
        test_container
    ):
        """권한 요청 생성 성공 테스트"""
        request_data = {
            "container_id": test_container.container_id,
            "requested_role_id": "VIEWER",
            "reason": "테스트 목적으로 조회 권한이 필요합니다."
        }

        response = await async_client.post(
            "/api/v1/permission-requests",
            json=request_data,
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["request"]["container_id"] == test_container.container_id
        assert data["request"]["requested_role_id"] == "VIEWER"
        assert data["request"]["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_create_permission_request_with_auto_approval(
        self,
        async_client: AsyncClient,
        test_user,
        test_container,
        auto_approval_rule
    ):
        """자동 승인 규칙이 적용되는 권한 요청 테스트"""
        request_data = {
            "container_id": test_container.container_id,
            "requested_role_id": "VIEWER",
            "reason": "자동 승인 테스트입니다."
        }

        response = await async_client.post(
            "/api/v1/permission-requests",
            json=request_data,
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["request"]["status"] == "APPROVED"
        assert data["request"]["auto_approved"] is True

    @pytest.mark.asyncio
    async def test_create_duplicate_request_fails(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_container
    ):
        """중복 권한 요청 실패 테스트"""
        # 첫 번째 요청 생성
        existing_request = TbPermissionRequests(
            user_id=test_user.user_id,
            user_emp_no=test_user.emp_no,
            container_id=test_container.container_id,
            requested_role_id="VIEWER",
            reason="첫 번째 요청",
            status="PENDING"
        )
        db_session.add(existing_request)
        await db_session.commit()

        # 중복 요청 시도
        request_data = {
            "container_id": test_container.container_id,
            "requested_role_id": "VIEWER",
            "reason": "중복 요청 시도"
        }

        response = await async_client.post(
            "/api/v1/permission-requests",
            json=request_data,
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_create_request_invalid_container(
        self,
        async_client: AsyncClient,
        test_user
    ):
        """존재하지 않는 컨테이너에 대한 요청 실패 테스트"""
        request_data = {
            "container_id": "INVALID_CONTAINER",
            "requested_role_id": "VIEWER",
            "reason": "유효하지 않은 컨테이너 테스트"
        }

        response = await async_client.post(
            "/api/v1/permission-requests",
            json=request_data,
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPermissionRequestApproval:
    """권한 요청 승인/거부 테스트"""

    @pytest.mark.asyncio
    async def test_approve_permission_request(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """권한 요청 승인 테스트"""
        # 권한 요청 생성
        request = TbPermissionRequests(
            user_id=test_user.user_id,
            user_emp_no=test_user.emp_no,
            container_id=test_container.container_id,
            requested_role_id="VIEWER",
            reason="승인 테스트",
            status="PENDING"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)

        # 승인
        response = await async_client.post(
            f"/api/v1/permission-requests/{request.request_id}/approve",
            json={"approver_comment": "승인합니다"},
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["request"]["status"] == "APPROVED"
        assert data["request"]["processed_by"] == test_manager.emp_no

    @pytest.mark.asyncio
    async def test_reject_permission_request(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """권한 요청 거부 테스트"""
        # 권한 요청 생성
        request = TbPermissionRequests(
            user_id=test_user.user_id,
            user_emp_no=test_user.emp_no,
            container_id=test_container.container_id,
            requested_role_id="ADMIN",
            reason="거부 테스트",
            status="PENDING"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)

        # 거부
        response = await async_client.post(
            f"/api/v1/permission-requests/{request.request_id}/reject",
            json={"rejection_reason": "권한 레벨이 너무 높습니다"},
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["request"]["status"] == "REJECTED"
        assert data["request"]["rejection_reason"] == "권한 레벨이 너무 높습니다"

    @pytest.mark.asyncio
    async def test_reject_without_reason_fails(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """거부 사유 없이 거부 실패 테스트"""
        request = TbPermissionRequests(
            user_id=test_user.user_id,
            user_emp_no=test_user.emp_no,
            container_id=test_container.container_id,
            requested_role_id="VIEWER",
            reason="테스트",
            status="PENDING"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)

        response = await async_client.post(
            f"/api/v1/permission-requests/{request.request_id}/reject",
            json={},
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPermissionRequestQuery:
    """권한 요청 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_my_requests(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_container
    ):
        """내 권한 요청 목록 조회 테스트"""
        # 여러 요청 생성
        for i in range(3):
            request = TbPermissionRequests(
                user_id=test_user.user_id,
                user_emp_no=test_user.emp_no,
                container_id=test_container.container_id,
                requested_role_id="VIEWER",
                reason=f"테스트 요청 {i+1}",
                status="PENDING" if i % 2 == 0 else "APPROVED"
            )
            db_session.add(request)
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/permission-requests/my-requests",
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["requests"]) == 3

    @pytest.mark.asyncio
    async def test_get_pending_requests(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """대기 중 요청 목록 조회 테스트 (관리자)"""
        # 대기 중 요청 생성
        for i in range(2):
            request = TbPermissionRequests(
                user_id=test_user.user_id,
                user_emp_no=test_user.emp_no,
                container_id=test_container.container_id,
                requested_role_id="VIEWER",
                reason=f"대기 요청 {i+1}",
                status="PENDING"
            )
            db_session.add(request)
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/permission-requests/pending",
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["requests"]) >= 2


class TestBatchOperations:
    """일괄 처리 테스트"""

    @pytest.mark.asyncio
    async def test_batch_approve(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """일괄 승인 테스트"""
        # 여러 요청 생성
        request_ids = []
        for i in range(3):
            request = TbPermissionRequests(
                user_id=test_user.user_id,
                user_emp_no=test_user.emp_no,
                container_id=test_container.container_id,
                requested_role_id="VIEWER",
                reason=f"일괄 승인 테스트 {i+1}",
                status="PENDING"
            )
            db_session.add(request)
            await db_session.flush()
            request_ids.append(str(request.request_id))
        await db_session.commit()

        # 일괄 승인
        response = await async_client.post(
            "/api/v1/permission-requests/batch-approve",
            json={"request_ids": request_ids},
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_batch_reject(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """일괄 거부 테스트"""
        # 여러 요청 생성
        request_ids = []
        for i in range(2):
            request = TbPermissionRequests(
                user_id=test_user.user_id,
                user_emp_no=test_user.emp_no,
                container_id=test_container.container_id,
                requested_role_id="ADMIN",
                reason=f"일괄 거부 테스트 {i+1}",
                status="PENDING"
            )
            db_session.add(request)
            await db_session.flush()
            request_ids.append(str(request.request_id))
        await db_session.commit()

        # 일괄 거부
        response = await async_client.post(
            "/api/v1/permission-requests/batch-reject",
            json={
                "request_ids": request_ids,
                "rejection_reason": "권한 레벨이 부적절합니다"
            },
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True


class TestPermissionRequestStatistics:
    """통계 테스트"""

    @pytest.mark.asyncio
    async def test_get_statistics(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_manager,
        test_container
    ):
        """권한 요청 통계 조회 테스트"""
        # 다양한 상태의 요청 생성
        statuses = ["PENDING", "APPROVED", "REJECTED", "APPROVED"]
        for i, status_val in enumerate(statuses):
            request = TbPermissionRequests(
                user_id=test_user.user_id,
                user_emp_no=test_user.emp_no,
                container_id=test_container.container_id,
                requested_role_id="VIEWER",
                reason=f"통계 테스트 {i+1}",
                status=status_val,
                auto_approved=(status_val == "APPROVED" and i == 1)
            )
            db_session.add(request)
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/permission-requests/statistics/summary",
            headers={"Authorization": f"Bearer {test_manager.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "statistics" in data
        assert data["statistics"]["total_requests"] >= 4
        assert data["statistics"]["pending_requests"] >= 1
        assert data["statistics"]["approved_requests"] >= 2


class TestPermissionRequestCancellation:
    """권한 요청 취소 테스트"""

    @pytest.mark.asyncio
    async def test_cancel_own_request(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_container
    ):
        """자신의 요청 취소 테스트"""
        request = TbPermissionRequests(
            user_id=test_user.user_id,
            user_emp_no=test_user.emp_no,
            container_id=test_container.container_id,
            requested_role_id="VIEWER",
            reason="취소 테스트",
            status="PENDING"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)

        response = await async_client.delete(
            f"/api/v1/permission-requests/{request.request_id}",
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["request"]["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_cannot_cancel_approved_request(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_container
    ):
        """승인된 요청은 취소할 수 없음 테스트"""
        request = TbPermissionRequests(
            user_id=test_user.user_id,
            user_emp_no=test_user.emp_no,
            container_id=test_container.container_id,
            requested_role_id="VIEWER",
            reason="취소 불가 테스트",
            status="APPROVED"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)

        response = await async_client.delete(
            f"/api/v1/permission-requests/{request.request_id}",
            headers={"Authorization": f"Bearer {test_user.emp_no}"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

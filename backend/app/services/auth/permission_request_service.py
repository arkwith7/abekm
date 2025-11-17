"""
권한 요청 서비스
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.auth.permission_models import (
    TbPermissionRequests,
    TbPermissionAuditLog,
    TbAutoApprovalRules,
    TbKnowledgeContainers
)
from app.models import TbSapHrInfo, TbUserPermissions
from app.services.auth.permission_service import PermissionService


class PermissionRequestService:
    """권한 요청 관리 서비스"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_service = PermissionService(session)
    
    async def create_request(
        self,
        requester_emp_no: str,
        container_id: str,
        requested_permission: str,
        justification: str,
        business_need: Optional[str] = None,
        requested_duration: Optional[str] = None,
        priority_level: str = 'normal'
    ) -> Optional[int]:
        """권한 요청 생성"""
        try:
            result = await self.session.execute(
                select(TbSapHrInfo).where(TbSapHrInfo.emp_no == requester_emp_no)
            )
            requester = result.scalar_one_or_none()
            if not requester:
                return None
            
            result = await self.session.execute(
                select(TbKnowledgeContainers).where(
                    TbKnowledgeContainers.container_id == container_id
                )
            )
            container = result.scalar_one_or_none()
            if not container:
                return None
            
            # 현재 사용자의 컨테이너에 대한 기존 권한 레벨 조회
            current_permission = await self.permission_service.get_user_permission_level(
                requester_emp_no, container_id
            )
            
            existing = await self._check_duplicate_request(
                requester_emp_no, container_id, requested_permission
            )
            if existing:
                return None
            
            auto_approved = await self._check_auto_approval(
                requester_emp_no, container_id, requested_permission
            )
            
            temp_end_date = None
            if requested_duration == '30days':
                temp_end_date = datetime.now() + timedelta(days=30)
            elif requested_duration == '90days':
                temp_end_date = datetime.now() + timedelta(days=90)
            
            # TbPermissionRequests 모델에 맞춰 생성
            # created_date, last_modified_date는 server_default로 자동 생성됨
            request = TbPermissionRequests(
                requester_emp_no=requester_emp_no,
                container_id=container_id,
                requested_permission=requested_permission,
                current_permission=current_permission,
                justification=justification,
                business_need=business_need,
                requested_duration=requested_duration,
                temp_end_date=temp_end_date,
                request_status='pending',
                priority_level=priority_level,
                auto_approved=auto_approved,
                notification_sent=False  # 알림 미발송 상태로 초기화
            )
            
            self.session.add(request)
            await self.session.flush()
            
            # 자동 승인 처리 (현재는 항상 False)
            if auto_approved:
                await self._process_auto_approval(request)
            else:
                # 승인 대기 상태: 컨테이너 관리자 찾기
                approvers = await self._find_container_approvers(container_id)
                if approvers:
                    logger.info(f"권한 요청 승인 대기 중 - 승인자: {', '.join(approvers)}")
                    # TODO: 향후 알림 발송 기능 추가
                    # await self._send_approval_notification(request, approvers)
                else:
                    logger.warning(f"컨테이너 {container_id}의 승인자를 찾을 수 없습니다. 시스템 관리자가 승인해야 합니다.")
            
            await self.session.commit()
            
            logger.info(f"권한 요청 생성: ID={request.request_id}, 상태={'자동승인' if auto_approved else '승인대기'}")
            return request.request_id
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"권한 요청 생성 실패: {str(e)}")
            return None
    
    async def _check_duplicate_request(self, requester_emp_no: str, container_id: str, requested_permission: str) -> bool:
        result = await self.session.execute(
            select(TbPermissionRequests).where(
                and_(
                    TbPermissionRequests.requester_emp_no == requester_emp_no,
                    TbPermissionRequests.container_id == container_id,
                    TbPermissionRequests.requested_permission == requested_permission,
                    TbPermissionRequests.request_status == 'pending'
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def _check_auto_approval(self, requester_emp_no: str, container_id: str, requested_permission: str) -> bool:
        """자동 승인 여부 확인
        
        현재 정책: 모든 권한 요청은 컨테이너 관리자의 승인 필요
        - VIEWER, EDITOR, MANAGER, ADMIN 모두 승인 필요
        - 자동 승인 규칙은 향후 확장 가능 (예: 같은 부서원은 VIEWER 자동 승인 등)
        
        Returns:
            False: 모든 권한 요청은 승인 필요
        """
        # 🔒 보안 정책: 모든 권한 요청은 컨테이너 관리자의 명시적 승인 필요
        # TODO: 향후 자동 승인 규칙 추가 시 여기에 구현
        # 예시:
        # - 같은 부서원이 VIEWER 요청 시 자동 승인
        # - 시스템 관리자가 요청 시 자동 승인
        # - 특정 역할 보유자가 요청 시 자동 승인
        
        logger.info(f"권한 요청 승인 대기: {requester_emp_no} → {container_id} ({requested_permission})")
        return False  # 모든 요청은 승인 필요
    
    async def _find_container_approvers(self, container_id: str) -> List[str]:
        """컨테이너의 승인 권한을 가진 관리자 목록 조회
        
        승인 권한자 우선순위:
        1. ADMIN 권한 보유자 (컨테이너 관리자)
        2. MANAGER 권한 보유자 (부서/팀 관리자)
        3. 컨테이너 소유자 (container_owner)
        4. 시스템 관리자 (ADMIN001)
        
        Returns:
            승인 권한자 사번 목록
        """
        try:
            approvers = []
            
            # 1. 컨테이너에 ADMIN 또는 MANAGER 권한을 가진 사용자 조회
            result = await self.session.execute(
                select(TbUserPermissions.user_emp_no).where(
                    and_(
                        TbUserPermissions.container_id == container_id,
                        TbUserPermissions.role_id.in_(['ADMIN', 'MANAGER', 'OWNER', 'OWNER_DEPT', 'OWNER_DIVISION', 'MANAGER_DEPT', 'MANAGER_DIVISION']),
                        TbUserPermissions.is_active == True
                    )
                ).distinct()
            )
            container_admins = result.scalars().all()
            approvers.extend([str(emp_no) for emp_no in container_admins])
            
            # 2. 컨테이너 소유자 추가
            result = await self.session.execute(
                select(TbKnowledgeContainers.container_owner).where(
                    TbKnowledgeContainers.container_id == container_id
                )
            )
            container_owner = result.scalar_one_or_none()
            if container_owner and str(container_owner) not in approvers:
                approvers.append(str(container_owner))
            
            # 3. 승인자가 없으면 시스템 관리자 추가
            if not approvers:
                system_admin = await self._get_system_admin_emp_no()
                if system_admin:
                    approvers.append(system_admin)
            
            return approvers
            
        except Exception as e:
            logger.error(f"컨테이너 승인자 조회 실패: {container_id}, {str(e)}")
            # 오류 발생 시 시스템 관리자를 기본 승인자로 반환
            try:
                system_admin = await self._get_system_admin_emp_no()
                return [system_admin] if system_admin else []
            except:
                return []
    
    async def _get_system_admin_emp_no(self) -> str:
        """시스템 관리자 사번 조회 (PermissionService 위임)
        
        Returns:
            시스템 관리자 사번, 찾을 수 없으면 'ADMIN001' (기본값)
        """
        try:
            system_admin = await self.permission_service._get_system_admin_emp_no()
            return system_admin if system_admin else 'ADMIN001'
        except Exception as e:
            logger.error(f"시스템 관리자 조회 실패: {str(e)}")
            return 'ADMIN001'
    
    async def _process_auto_approval(self, request: TbPermissionRequests):
        """자동 승인 처리
        
        실제 시스템 관리자 사번을 사용하여 권한 부여 및 승인 처리
        """
        # 실제 시스템 관리자 사번 조회
        system_admin_emp_no = await self._get_system_admin_emp_no()
        
        # 권한 부여 (grant_permission 내부에서 _log_permission_audit 호출 시 자동으로 처리됨)
        await self.permission_service.grant_permission(
            user_emp_no=request.requester_emp_no,
            container_id=request.container_id,
            permission_level=request.requested_permission,
            granted_by=system_admin_emp_no,  # ✅ 실제 시스템 관리자 사번 사용
            valid_until=request.temp_end_date,
            skip_permission_check=True
        )
        
        # 요청 상태 업데이트
        request.request_status = 'approved'
        request.approver_emp_no = system_admin_emp_no  # ✅ 실제 시스템 관리자 사번 사용
        request.approval_date = datetime.now()
        request.approval_comment = '자동 승인 (VIEWER 권한)'
    
    async def approve_request(self, request_id: int, approver_emp_no: str, approval_comment: Optional[str] = None) -> bool:
        try:
            result = await self.session.execute(
                select(TbPermissionRequests).where(TbPermissionRequests.request_id == request_id)
            )
            request = result.scalar_one_or_none()
            if not request or request.request_status != 'pending':
                return False
            
            granted = await self.permission_service.grant_permission(
                user_emp_no=request.requester_emp_no,
                container_id=request.container_id,
                permission_level=request.requested_permission,
                granted_by=approver_emp_no,
                valid_until=request.temp_end_date
            )
            if not granted:
                return False
            
            request.request_status = 'approved'
            request.approver_emp_no = approver_emp_no
            request.approval_date = datetime.now()
            request.approval_comment = approval_comment
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"승인 실패: {str(e)}")
            return False
    
    async def reject_request(self, request_id: int, approver_emp_no: str, rejection_reason: str) -> bool:
        try:
            result = await self.session.execute(
                select(TbPermissionRequests).where(TbPermissionRequests.request_id == request_id)
            )
            request = result.scalar_one_or_none()
            if not request or request.request_status != 'pending':
                return False
            
            request.request_status = 'rejected'
            request.approver_emp_no = approver_emp_no
            request.approval_date = datetime.now()
            request.rejection_reason = rejection_reason
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            return False
    
    async def cancel_request(self, request_id: int, requester_emp_no: str) -> bool:
        try:
            result = await self.session.execute(
                select(TbPermissionRequests).where(
                    and_(
                        TbPermissionRequests.request_id == request_id,
                        TbPermissionRequests.requester_emp_no == requester_emp_no
                    )
                )
            )
            request = result.scalar_one_or_none()
            if not request or request.request_status != 'pending':
                return False
            
            request.request_status = 'cancelled'
            request.approval_date = datetime.now()
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            return False
    
    async def get_my_requests(
        self,
        requester_emp_no: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """사용자가 요청한 권한 신청 목록을 조회한다.

        NOTE: AsyncSession + lazy relationship 접근 시 greenlet 에러가 발생하므로
        명시적으로 필요한 컬럼만 SELECT 하여 dict 형태로 반환한다.
        """
        try:
            from sqlalchemy.orm import aliased

            requester_alias = aliased(TbSapHrInfo)
            approver_alias = aliased(TbSapHrInfo)

            conditions = [TbPermissionRequests.requester_emp_no == requester_emp_no]
            normalized_status = status.lower() if status else None
            if normalized_status:
                conditions.append(TbPermissionRequests.request_status == normalized_status)

            count_stmt = select(func.count()).select_from(TbPermissionRequests).where(and_(*conditions))
            count_result = await self.session.execute(count_stmt)
            total = count_result.scalar() or 0

            stmt = (
                select(
                    TbPermissionRequests.request_id.label("request_id"),
                    TbPermissionRequests.requester_emp_no.label("requester_emp_no"),
                    TbPermissionRequests.container_id.label("container_id"),
                    TbPermissionRequests.current_permission.label("current_permission_level"),
                    TbPermissionRequests.requested_permission.label("requested_permission_level"),
                    TbPermissionRequests.justification.label("request_reason"),
                    TbPermissionRequests.business_need.label("business_justification"),
                    TbPermissionRequests.requested_duration.label("expected_usage_period"),
                    TbPermissionRequests.priority_level.label("urgency_level"),
                    TbPermissionRequests.request_status.label("status"),
                    TbPermissionRequests.approver_emp_no.label("approver_emp_no"),
                    TbPermissionRequests.approval_comment.label("approval_comment"),
                    TbPermissionRequests.rejection_reason.label("rejection_reason"),
                    TbPermissionRequests.auto_approved.label("auto_approved"),
                    TbPermissionRequests.created_date.label("requested_at"),
                    TbPermissionRequests.approval_date.label("processed_at"),
                    TbPermissionRequests.temp_end_date.label("expires_at"),
                    requester_alias.emp_nm.label("requester_name"),
                    requester_alias.dept_nm.label("requester_department"),
                    TbKnowledgeContainers.container_name.label("container_name"),
                    approver_alias.emp_nm.label("approver_name")
                )
                .join(requester_alias, TbPermissionRequests.requester_emp_no == requester_alias.emp_no, isouter=True)
                .join(TbKnowledgeContainers, TbPermissionRequests.container_id == TbKnowledgeContainers.container_id, isouter=True)
                .join(approver_alias, TbPermissionRequests.approver_emp_no == approver_alias.emp_no, isouter=True)
                .where(and_(*conditions))
                .order_by(desc(TbPermissionRequests.created_date))
                .limit(limit)
                .offset(offset)
            )

            result = await self.session.execute(stmt)
            rows = result.fetchall()

            requests: List[Dict[str, Any]] = []
            for row in rows:
                data = dict(row._mapping)

                # id/request_id 포맷 정규화
                raw_request_id = data.get("request_id")
                if raw_request_id is not None:
                    data["id"] = int(raw_request_id)
                    data["request_id"] = str(raw_request_id)
                else:
                    data["id"] = None

                # 상태 값은 프런트에서 대문자 기준으로 처리하므로 변환
                if data.get("status"):
                    data["status"] = str(data["status"]).upper()

                # 문자열 필드 기본값 보정
                if data.get("request_reason") is None:
                    data["request_reason"] = ""

                # 날짜/시간 필드는 ISO 포맷 문자열로 변환
                for key in ("requested_at", "processed_at", "expires_at"):
                    value = data.get(key)
                    if value is not None:
                        data[key] = value.isoformat()

                requests.append(data)

            return {
                'total': total,
                'requests': requests,
                'limit': limit,
                'offset': offset
            }
        except Exception as e:
            logger.error(f"get_my_requests 에러: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'total': 0, 'requests': [], 'limit': limit, 'offset': offset}
    
    async def get_pending_requests(
        self, 
        container_id: Optional[str] = None, 
        limit: int = 50, 
        offset: int = 0,
        manager_emp_no: Optional[str] = None
    ) -> Dict[str, Any]:
        """대기 중인 권한 요청 조회
        
        Args:
            container_id: 특정 컨테이너 필터링
            limit: 최대 반환 개수
            offset: 페이징 시작 위치
            manager_emp_no: 지식관리자 사번 (범위 제한 적용)
        """
        try:
            from app.services.auth.permission_service import PermissionService
            from sqlalchemy.orm import selectinload
            
            conditions = [TbPermissionRequests.request_status == 'pending']
            
            # 지식관리자 범위 제한 적용
            if manager_emp_no:
                permission_service = PermissionService(self.session)
                allowed_container_ids = await permission_service.get_managed_container_ids(manager_emp_no)
                
                # 빈 리스트가 아닐 경우에만 필터링 적용
                # 빈 리스트 = 시스템 관리자 = 전체 조회
                if allowed_container_ids:
                    conditions.append(TbPermissionRequests.container_id.in_(allowed_container_ids))
                elif not await permission_service.is_system_admin(manager_emp_no):
                    # 시스템 관리자가 아니면서 관리 범위가 없으면 빈 목록 반환
                    return {'total': 0, 'requests': [], 'limit': limit, 'offset': offset}

            
            if container_id:
                conditions.append(TbPermissionRequests.container_id == container_id)
            
            count_result = await self.session.execute(
                select(func.count()).select_from(TbPermissionRequests).where(and_(*conditions))
            )
            total = count_result.scalar()
            
            # Join with related tables to get requester name, department, and container name
            result = await self.session.execute(
                select(TbPermissionRequests)
                .options(
                    selectinload(TbPermissionRequests.requester),
                    selectinload(TbPermissionRequests.knowledge_container),
                    selectinload(TbPermissionRequests.approver)
                )
                .where(and_(*conditions))
                .order_by(desc(TbPermissionRequests.created_date)).limit(limit).offset(offset)
            )
            requests = result.scalars().all()
            
            return {'total': total, 'requests': requests, 'limit': limit, 'offset': offset}
        except Exception as e:
            return {'total': 0, 'requests': [], 'limit': limit, 'offset': offset}
    
    async def get_request_statistics(self) -> Dict[str, Any]:
        try:
            result = await self.session.execute(
                select(TbPermissionRequests.request_status, func.count())
                .group_by(TbPermissionRequests.request_status)
            )
            status_stats = {row[0]: row[1] for row in result.all()}
            
            total_count = sum(status_stats.values())
            
            return {
                'status_distribution': status_stats,
                'total_requests': total_count,
                'pending_requests': status_stats.get('pending', 0),
                'approved_requests': status_stats.get('approved', 0),
                'rejected_requests': status_stats.get('rejected', 0)
            }
        except Exception as e:
            return {}

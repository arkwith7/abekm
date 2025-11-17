"""
WKMS 권한 관리 서비스
계층형 RBAC 시스템 구현
"""
# pyright: reportGeneralTypeIssues=false
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, and_, or_, func, text
from app.models import (
    TbKnowledgeContainers, 
    TbUserRoles, 
    TbUserPermissions, 
    TbPermissionRequests,
    TbPermissionAuditLog,
    TbSapHrInfo
)
from app.core.database import get_db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PermissionService:
    """권한 관리 핵심 서비스"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        # 요청 범위 캐시
        self._permission_level_cache: Dict[Tuple[str, str], Optional[str]] = {}
        self._direct_permission_cache: Dict[Tuple[str, str], Optional[str]] = {}
        self._inherited_permission_cache: Dict[Tuple[str, str], Optional[str]] = {}
        self._container_cache: Dict[str, TbKnowledgeContainers] = {}
        self._system_admin_cache: Dict[str, bool] = {}
    
    async def is_system_admin(self, user_emp_no: str) -> bool:
        """시스템 관리자 여부 확인
        
        시스템 관리자 조건:
        1. SYSTEM_ADMIN 역할 보유
        2. 전역 ADMIN 권한(루트 컨테이너) 보유
        """
        try:
            if user_emp_no in self._system_admin_cache:
                return self._system_admin_cache[user_emp_no]

            # 1) SYSTEM_ADMIN 역할 확인
            query = select(TbUserRoles).where(
                and_(
                    TbUserRoles.user_emp_no == user_emp_no,
                    TbUserRoles.role_name == 'SYSTEM_ADMIN',
                    TbUserRoles.is_active == True
                )
            )
            result = await self.session.execute(query)
            system_admin_role = result.scalar_one_or_none()
            
            if system_admin_role:
                self._system_admin_cache[user_emp_no] = True
                return True
            
            # 2) 전역 ADMIN 권한 확인 (루트 컨테이너 ADMIN)
            # container_id가 NULL이거나 루트 컨테이너에 ADMIN 권한
            query = select(TbUserPermissions).where(
                and_(
                    TbUserPermissions.user_emp_no == user_emp_no,
                    TbUserPermissions.role_id.in_(['ADMIN', 'SYSTEM_ADMIN']),
                    TbUserPermissions.is_active == True
                )
            ).limit(1)
            result = await self.session.execute(query)
            admin_permission = result.scalar_one_or_none()
            
            # 루트 컨테이너 확인 (parent_container_id가 NULL)
            if admin_permission:
                container_query = select(TbKnowledgeContainers).where(
                    and_(
                        TbKnowledgeContainers.container_id == admin_permission.container_id,
                        TbKnowledgeContainers.parent_container_id.is_(None)
                    )
                )
                container_result = await self.session.execute(container_query)
                root_container = container_result.scalar_one_or_none()
                if root_container:
                    self._system_admin_cache[user_emp_no] = True
                    return True
            
            self._system_admin_cache[user_emp_no] = False
            return False
            
        except Exception as e:
            logger.error(f"시스템 관리자 확인 실패: {user_emp_no}, {str(e)}")
            return False
    
    async def get_user_permission_level(
        self,
        user_emp_no: str,
        container_id: str
    ) -> Optional[str]:
        """사용자의 특정 컨테이너에 대한 권한 레벨(role_id) 조회

        우선순위: 직접 권한 → 상속 권한 → (미사용) 역할 기반
        """
        cache_key = (user_emp_no, container_id)
        if cache_key in self._permission_level_cache:
            return self._permission_level_cache[cache_key]

        try:
            # 1. 직접 권한
            direct_permission = await self._get_direct_permission(user_emp_no, container_id)
            if direct_permission:
                self._permission_level_cache[cache_key] = direct_permission
                return direct_permission

            # 2. 상속 권한
            inherited_permission = await self._get_inherited_permission(user_emp_no, container_id)
            if inherited_permission:
                self._permission_level_cache[cache_key] = inherited_permission
                return inherited_permission

            # 3. 역할 기반 (현재 None 반환)
            role_permission = await self._get_role_based_permission(user_emp_no, container_id)
            if role_permission:
                self._permission_level_cache[cache_key] = role_permission
                return role_permission

            self._permission_level_cache[cache_key] = None
            return None
        except Exception as e:
            logger.error(f"권한 레벨 조회 실패: {user_emp_no}, {container_id}, {str(e)}")
            return None

    async def _get_direct_permission(
        self, 
        user_emp_no: str, 
        container_id: str
    ) -> Optional[str]:
        """사용자의 특정 컨테이너에 대한 직접 권한 조회"""
        cache_key = (user_emp_no, container_id)
        if cache_key in self._direct_permission_cache:
            return self._direct_permission_cache[cache_key]

        query = select(TbUserPermissions.role_id).where(
            and_(
                TbUserPermissions.user_emp_no == user_emp_no,
                TbUserPermissions.container_id == container_id,
                TbUserPermissions.is_active == True
            )
        )
        result = await self.session.execute(query)
        permission = result.scalar_one_or_none()
        self._direct_permission_cache[cache_key] = permission
        return permission

    async def _get_inherited_permission(
        self, 
        user_emp_no: str, 
        container_id: str
    ) -> Optional[str]:
        """상속받은 권한 확인 (한 단계 부모의 직접 권한만 확인)"""
        cache_key = (user_emp_no, container_id)
        if cache_key in self._inherited_permission_cache:
            return self._inherited_permission_cache[cache_key]

        try:
            # 컨테이너 정보 및 부모 정보 조회
            container = await self._get_container(container_id)
            
            if not container or not container.inherit_parent_permissions or not container.parent_container_id:
                self._inherited_permission_cache[cache_key] = None
                return None
            
            # 부모 컨테이너의 "직접" 권한 확인
            parent_permission = await self._get_direct_permission(
                user_emp_no, 
                container.parent_container_id
            )
            
            if parent_permission:
                self._inherited_permission_cache[cache_key] = parent_permission
                return parent_permission

            # 부모가 직접 권한이 없다면, 부모의 상속 권한을 재귀적으로 확인
            inherited = await self._get_inherited_permission(user_emp_no, container.parent_container_id)
            self._inherited_permission_cache[cache_key] = inherited
            return inherited
            
        except Exception as e:
            logger.error(f"상속 권한 확인 실패: {user_emp_no}, {container_id}, {str(e)}")
            self._inherited_permission_cache[cache_key] = None
            return None
    
    async def _get_role_based_permission(
        self, 
        user_emp_no: str, 
        container_id: str
    ) -> Optional[str]:
        """역할 기반 권한 확인 (현재 비활성화)"""
        try:
            # TODO: 향후 역할 기반 권한 시스템이 도입되면 이곳에 로직을 구현합니다.
            # 현재는 역할 기반으로 부여되는 권한이 없으므로 None을 반환합니다.
            logger.debug(f"역할 기반 권한 확인 스킵: {user_emp_no}, {container_id}")
            return None
            
        except Exception as e:
            logger.error(f"역할 기반 권한 확인 실패: {user_emp_no}, {container_id}, {str(e)}")
            return None
    
    async def check_permission(
        self, 
        user_emp_no: str, 
        container_id: str, 
        required_permission: str
    ) -> bool:
        """권한 확인 (ADMIN > MANAGER > EDITOR > VIEWER)"""
        try:
            user_permission = await self.get_user_permission_level(user_emp_no, container_id)
            if not user_permission:
                return False
            
            # 권한 계층 구조 (숫자가 작을수록 높은 권한)
            permission_hierarchy = {
                # 기본 권한
                'ADMIN': 1,
                'MANAGER': 2,
                'EDITOR': 3,
                'VIEWER': 4,
                
                # 조직 기반 권한 매핑
                'OWNER_DEPT': 1,        # 부서 소유자 = ADMIN
                'OWNER_DIVISION': 1,    # 본부 소유자 = ADMIN
                'MANAGER_DEPT': 2,      # 부서 관리자 = MANAGER
                'MANAGER_DIVISION': 2,  # 본부 관리자 = MANAGER
                'MEMBER_DEPT': 3,       # 부서 구성원 = EDITOR
                'MEMBER_DIVISION': 4,   # 본부 구성원 = VIEWER
                
                # 레거시 역할
                'CONTRIBUTOR': 3,
                'OWNER': 1,
                'FULL_ACCESS': 1,
                'WRITER': 3,
                'READER': 4,
            }
            
            user_level = permission_hierarchy.get(user_permission.upper(), 999)
            required_level = permission_hierarchy.get(required_permission.upper(), 1)
            
            return user_level <= required_level
            
        except Exception as e:
            logger.error(f"권한 확인 실패: {user_emp_no}, {container_id}, {required_permission}, {str(e)}")
            return False

    async def check_container_access(
        self,
        user_emp_no: str,
        container_id: Optional[str],
        required_permission: Optional[str] = None
    ) -> bool:
        """컨테이너 접근 권한 보유 여부 확인"""
        if not container_id:
            logger.warning(
                "check_container_access 호출 시 container_id 가 None 입니다 - user=%s",
                user_emp_no
            )
            return False

        try:
            if required_permission:
                return await self.check_permission(user_emp_no, container_id, required_permission)

            user_permission = await self.get_user_permission_level(user_emp_no, container_id)
            return user_permission is not None

        except Exception as e:
            logger.error(
                "컨테이너 접근 권한 확인 실패 - user=%s, container_id=%s, error=%s",
                user_emp_no,
                container_id,
                str(e)
            )
            return False
    
    async def get_accessible_containers(
        self, 
        user_emp_no: str
    ) -> List[Dict[str, Any]]:
        """사용자가 접근 가능한 모든 컨테이너 조회 (하위 컨테이너 상속 포함)"""
        try:
            logger.info(f"권한 조회 시작: user_emp_no={user_emp_no}")
            
            # 1. 직접 권한이 있는 컨테이너들
            direct_query = select(TbUserPermissions, TbKnowledgeContainers).join(
                TbKnowledgeContainers,
                TbUserPermissions.container_id == TbKnowledgeContainers.container_id
            ).where(
                and_(
                    TbUserPermissions.user_emp_no == user_emp_no,
                    TbUserPermissions.is_active == True,
                    TbKnowledgeContainers.is_active == True
                )
            )
            
            logger.info(f"직접 권한 쿼리 실행: {direct_query}")
            direct_result = await self.session.execute(direct_query)
            accessible_containers = []
            direct_containers = []
            
            # 직접 권한이 있는 컨테이너 수집
            for permission, container in direct_result:
                logger.info(f"직접 권한 발견: container_id={container.container_id}, role_id={permission.role_id}")
                container_info = {
                    'container_id': container.container_id,
                    'container_name': container.container_name,
                    'permission_level': permission.role_id,
                    'permission_source': 'direct',
                    'container_type': container.container_type,
                    'access_level': container.access_level,
                    'parent_container_id': container.parent_container_id
                }
                accessible_containers.append(container_info)
                direct_containers.append(container.container_id)
            
            logger.info(f"직접 권한 컨테이너 수: {len(accessible_containers)}")
            
            # 2. 하위 컨테이너 권한 상속 추가
            inherited_containers = await self._get_inherited_containers(user_emp_no, direct_containers)
            accessible_containers.extend(inherited_containers)
            
            # 3. 중복 제거 및 최고 권한으로 정리
            container_map = {}
            permission_hierarchy = {'FULL_ACCESS': 0, 'ADMIN': 1, 'MANAGER': 2, 'EDITOR': 3, 'VIEWER': 4}
            
            for container in accessible_containers:
                container_id = container['container_id']
                if container_id not in container_map:
                    container_map[container_id] = container
                else:
                    # 더 높은 권한으로 업데이트
                    current_level = permission_hierarchy.get(container_map[container_id]['permission_level'], 999)
                    new_level = permission_hierarchy.get(container['permission_level'], 999)
                    if new_level < current_level:
                        container_map[container_id] = container
            
            final_containers = list(container_map.values())
            logger.info(f"최종 접근 가능한 컨테이너 수: {len(final_containers)}")
            
            return final_containers
            
        except Exception as e:
            logger.error(f"접근 가능한 컨테이너 조회 실패: {user_emp_no}, {str(e)}")
            return []

    async def _get_container(self, container_id: str) -> Optional[TbKnowledgeContainers]:
        """컨테이너 메타데이터 요청 범위 캐시"""
        if container_id in self._container_cache:
            return self._container_cache[container_id]

        container_query = select(TbKnowledgeContainers).where(
            TbKnowledgeContainers.container_id == container_id
        )
        container_result = await self.session.execute(container_query)
        container = container_result.scalar_one_or_none()
        if container:
            self._container_cache[container_id] = container
        return container
    
    async def _get_inherited_containers(
        self, 
        user_emp_no: str, 
        parent_container_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """상위 컨테이너 권한으로부터 하위 컨테이너 상속 권한 조회"""
        try:
            if not parent_container_ids:
                return []
            
            inherited_containers = []
            
            for parent_id in parent_container_ids:
                # 해당 부모 컨테이너의 모든 하위 컨테이너 조회
                child_query = select(TbKnowledgeContainers).where(
                    and_(
                        TbKnowledgeContainers.parent_container_id == parent_id,
                        TbKnowledgeContainers.is_active == True
                    )
                )
                
                child_result = await self.session.execute(child_query)
                child_containers = child_result.scalars().all()
                
                # 부모의 권한 레벨 조회
                parent_permission = await self._get_direct_permission(user_emp_no, parent_id)
                
                if parent_permission:
                    # 하위 컨테이너에 상속 권한 적용
                    inherited_permission = self._calculate_inherited_permission(parent_permission)
                    
                    for child_container in child_containers:
                        logger.info(f"상속 권한 발견: parent={parent_id}, child={child_container.container_id}, inherited_permission={inherited_permission}")
                        
                        inherited_containers.append({
                            'container_id': child_container.container_id,
                            'container_name': child_container.container_name,
                            'permission_level': inherited_permission,
                            'permission_source': 'inherited',
                            'container_type': child_container.container_type,
                            'access_level': child_container.access_level,
                            'parent_container_id': child_container.parent_container_id
                        })
                        
                        # 재귀적으로 하위의 하위 컨테이너도 확인
                        sub_inherited = await self._get_inherited_containers(
                            user_emp_no, 
                            [child_container.container_id]
                        )
                        inherited_containers.extend(sub_inherited)
            
            logger.info(f"상속 권한 컨테이너 수: {len(inherited_containers)}")
            return inherited_containers
            
        except Exception as e:
            logger.error(f"상속 컨테이너 조회 실패: {user_emp_no}, {str(e)}")
            return []
    
    def _calculate_inherited_permission(self, parent_permission: str) -> str:
        """부모 컨테이너 권한에 따른 하위 컨테이너 상속 권한 계산"""
        # 문서 별첨01에 따른 상속 권한 규칙
        inheritance_rules = {
            'ADMIN': 'MANAGER',      # ADMIN은 하위에서 MANAGER로 상속
            'MANAGER': 'EDITOR',     # MANAGER는 하위에서 EDITOR로 상속  
            'EDITOR': 'VIEWER',      # EDITOR는 하위에서 VIEWER로 상속
            'VIEWER': 'VIEWER',      # VIEWER는 그대로 VIEWER로 상속
            'FULL_ACCESS': 'ADMIN'   # FULL_ACCESS는 하위에서 ADMIN으로 상속
        }
        
        return inheritance_rules.get(parent_permission, 'VIEWER')
    
    async def _get_role_based_containers(
        self, 
        user_emp_no: str
    ) -> List[Dict[str, Any]]:
        """역할 기반으로 접근 가능한 컨테이너들 조회"""
        try:
            # 현재 시스템에서는 사용자 권한이 tb_user_permissions에 직접 저장되므로
            # 별도의 역할 기반 조회는 필요하지 않음
            logger.info(f"역할 기반 컨테이너 조회 스킵: {user_emp_no}")
            return []
            
        except Exception as e:
            logger.error(f"역할 기반 컨테이너 조회 실패: {user_emp_no}, {str(e)}")
            return []
    
    async def grant_permission(
        self,
        *,
        user_emp_no: str,
        container_id: str,
        permission_level: Optional[str] = None,
        role_id: Optional[str] = None,
        grantor_emp_no: Optional[str] = None,
        granted_by: Optional[str] = None,
        valid_until: Optional[datetime] = None,
        skip_permission_check: bool = False
    ) -> bool:
        """권한 부여 (role_id 기반)

        Args:
            user_emp_no: 권한을 부여할 대상 사용자 사번
            container_id: 대상 컨테이너 ID
            permission_level: (호환용) 부여할 권한 레벨
            role_id: 부여할 역할 ID
            grantor_emp_no: 권한 부여를 수행하는 사용자 사번
            granted_by: 기록용 부여자 (없으면 grantor_emp_no 사용)
            valid_until: 권한 만료일
            skip_permission_check: True 시 권한 검증 생략 (관리자, 시스템 등)
        """
        try:
            resolved_role = (role_id or permission_level or "").upper()
            if not resolved_role:
                logger.warning("grant_permission 호출 시 role_id/permission_level 누락")
                return False

            # 권한 유효성 (기본 허용 목록)
            valid_roles = {"ADMIN", "MANAGER", "EDITOR", "VIEWER", "CONTRIBUTOR", "OWNER", "FULL_ACCESS"}
            if resolved_role not in valid_roles:
                logger.warning(f"알 수 없는 role_id 부여 시도: {resolved_role}")
                return False

            actor_emp_no = grantor_emp_no or granted_by

            if not skip_permission_check and actor_emp_no not in {None, "SYSTEM"}:
                has_permission = await self.check_permission(actor_emp_no, container_id, 'MANAGER') if actor_emp_no else False
                if not has_permission:
                    logger.warning(f"권한 부여 권한 없음: {actor_emp_no}")
                    return False

            existing_query = select(TbUserPermissions).where(
                and_(
                    TbUserPermissions.user_emp_no == user_emp_no,
                    TbUserPermissions.container_id == container_id
                )
            )
            existing_result = await self.session.execute(existing_query)
            existing_permission = existing_result.scalar_one_or_none()

            granted_by_value = granted_by or actor_emp_no

            if existing_permission:
                old_permission = cast(Optional[str], existing_permission.role_id)
                existing_permission.role_id = resolved_role  # type: ignore[assignment]
                existing_permission.granted_by = granted_by_value  # type: ignore[assignment]
                existing_permission.granted_date = datetime.now()  # type: ignore[assignment]
                existing_permission.expires_date = valid_until  # type: ignore[assignment]
                existing_permission.is_active = True  # type: ignore[assignment]

                await self._log_permission_audit(
                    user_emp_no=actor_emp_no or "SYSTEM",
                    target_user_emp_no=user_emp_no,
                    container_id=container_id,
                    action_type='modify',
                    resource_type='permission',
                    old_permission=old_permission,
                    new_permission=resolved_role,
                    action_result='success'
                )
            else:
                new_permission = TbUserPermissions(
                    user_emp_no=user_emp_no,
                    container_id=container_id,
                    role_id=resolved_role,
                    permission_type='container',
                    access_scope='container',
                    permission_source='direct',
                    granted_by=granted_by_value,
                    granted_date=datetime.now(),
                    expires_date=valid_until,
                    is_active=True,
                    access_count=0
                )
                self.session.add(new_permission)

                await self._log_permission_audit(
                    user_emp_no=actor_emp_no or "SYSTEM",
                    target_user_emp_no=user_emp_no,
                    container_id=container_id,
                    action_type='grant',
                    resource_type='permission',
                    new_permission=resolved_role,
                    action_result='success'
                )

            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"권한 부여 실패: {user_emp_no}, {container_id}, {resolved_role}, {str(e)}")
            return False

    async def get_permission_record(
        self,
        *,
        user_emp_no: str,
        container_id: str,
        include_inactive: bool = False
    ) -> Optional[TbUserPermissions]:
        """특정 사용자의 컨테이너 권한 레코드 조회"""
        query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_emp_no == user_emp_no,
                TbUserPermissions.container_id == container_id
            )
        )
        if not include_inactive:
            query = query.where(TbUserPermissions.is_active == True)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_container_permissions(
        self,
        *,
        container_id: str,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """컨테이너 권한 목록 조회"""
        query = (
            select(
                TbUserPermissions.user_emp_no,
                TbUserPermissions.role_id,
                TbUserPermissions.permission_type,
                TbUserPermissions.access_scope,
                TbUserPermissions.granted_date,
                TbUserPermissions.granted_by,
                TbUserPermissions.expires_date,
                TbUserPermissions.is_active,
                TbSapHrInfo.emp_nm,
                TbSapHrInfo.dept_nm,
                TbSapHrInfo.postn_nm
            )
            .join(TbSapHrInfo, TbUserPermissions.user_emp_no == TbSapHrInfo.emp_no, isouter=True)
            .where(TbUserPermissions.container_id == container_id)
            .order_by(TbSapHrInfo.emp_nm, TbUserPermissions.user_emp_no)
        )

        if not include_inactive:
            query = query.where(TbUserPermissions.is_active == True)

        result = await self.session.execute(query)
        rows = result.all()

        permissions: List[Dict[str, Any]] = []
        for row in rows:
            permissions.append(
                {
                    "user_emp_no": row.user_emp_no,
                    "role_id": row.role_id,
                    "permission_type": row.permission_type,
                    "access_scope": row.access_scope,
                    "granted_date": row.granted_date,
                    "granted_by": row.granted_by,
                    "expires_date": row.expires_date,
                    "is_active": row.is_active,
                    "user_name": row.emp_nm,
                    "department": row.dept_nm,
                    "position": row.postn_nm,
                }
            )

        return permissions

    async def revoke_permission(
        self,
        *,
        user_emp_no: str,
        container_id: str,
        revoker_emp_no: Optional[str] = None,
        revoked_by: Optional[str] = None,
        skip_permission_check: bool = False
    ) -> bool:
        """권한 취소"""
        try:
            actor_emp_no = revoker_emp_no or revoked_by

            if not skip_permission_check and actor_emp_no not in {None, "SYSTEM"}:
                has_permission = await self.check_permission(actor_emp_no, container_id, 'MANAGER') if actor_emp_no else False
                if not has_permission:
                    logger.warning(f"권한 취소 권한 없음: {actor_emp_no}")
                    return False

            permission = await self.get_permission_record(
                user_emp_no=user_emp_no,
                container_id=container_id,
                include_inactive=False
            )

            if not permission:
                logger.warning(f"취소할 권한이 없습니다: user={user_emp_no}, container={container_id}")
                return False

            old_permission = cast(Optional[str], permission.role_id)
            permission.is_active = False  # type: ignore[assignment]
            permission.expires_date = permission.expires_date or datetime.now()  # type: ignore[assignment]

            await self._log_permission_audit(
                user_emp_no=actor_emp_no or "SYSTEM",
                target_user_emp_no=user_emp_no,
                container_id=container_id,
                action_type='revoke',
                resource_type='permission',
                old_permission=old_permission,
                action_result='success'
            )

            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"권한 취소 실패: {user_emp_no}, {container_id}, {str(e)}")
            return False
    
    async def _get_system_admin_emp_no(self) -> Optional[str]:
        """시스템 관리자 사번 조회
        
        tb_sap_hr_info에 존재하는 실제 시스템 관리자 사번을 반환
        우선순위: ADMIN001 > is_admin=true인 사용자
        """
        try:
            # 1. ADMIN001 사번 확인
            result = await self.session.execute(
                select(TbSapHrInfo.emp_no).where(TbSapHrInfo.emp_no == 'ADMIN001')
            )
            admin001 = result.scalar_one_or_none()
            if admin001:
                return admin001
            
            # 2. is_admin=true인 사용자 찾기 (User 테이블에서)
            from app.models import User
            result = await self.session.execute(
                select(User.emp_no).where(
                    and_(
                        User.is_admin == True,
                        User.is_active == True
                    )
                ).limit(1)
            )
            admin_user = result.scalar_one_or_none()
            if admin_user:
                return str(admin_user)
            
            # 3. 시스템 관리자를 찾을 수 없으면 None 반환
            logger.warning("시스템 관리자를 찾을 수 없습니다. 감사 로그를 생략합니다.")
            return None
            
        except Exception as e:
            logger.error(f"시스템 관리자 조회 실패: {str(e)}")
            return None
    
    async def _log_permission_audit(
        self,
        user_emp_no: str,
        action_type: str,
        resource_type: str,
        action_result: str,
        target_user_emp_no: Optional[str] = None,
        container_id: Optional[str] = None,
        file_id: Optional[int] = None,
        old_permission: Optional[str] = None,
        new_permission: Optional[str] = None,
        failure_reason: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """권한 감사 로그 기록
        
        user_emp_no가 'SYSTEM'인 경우 실제 시스템 관리자 사번으로 대체
        """
        try:
            # 'SYSTEM' 또는 기타 가상 사용자인 경우 실제 시스템 관리자로 대체
            actual_user_emp_no = user_emp_no
            if user_emp_no in ['SYSTEM', 'system', 'ADMIN', 'admin']:
                system_admin = await self._get_system_admin_emp_no()
                if not system_admin:
                    # 시스템 관리자를 찾을 수 없으면 감사 로그를 생략
                    logger.warning(f"시스템 관리자를 찾을 수 없어 감사 로그를 생략합니다: {action_type} on {resource_type}")
                    return
                actual_user_emp_no = system_admin
            
            # target_user_emp_no도 검증
            actual_target_emp_no = target_user_emp_no
            if target_user_emp_no and target_user_emp_no in ['SYSTEM', 'system', 'ADMIN', 'admin']:
                system_admin = await self._get_system_admin_emp_no()
                if system_admin:
                    actual_target_emp_no = system_admin
                else:
                    actual_target_emp_no = None
            
            audit_log = TbPermissionAuditLog(
                user_emp_no=actual_user_emp_no,
                target_user_emp_no=actual_target_emp_no,
                container_id=container_id,
                file_id=file_id,
                action_type=action_type,
                resource_type=resource_type,
                old_permission=old_permission,
                new_permission=new_permission,
                action_result=action_result,
                failure_reason=failure_reason,
                additional_data=additional_data,
                created_date=datetime.now()
            )
            self.session.add(audit_log)
            
        except Exception as e:
            logger.error(f"감사 로그 기록 실패: {str(e)}")
    
    async def check_admin_permission(self, user_emp_no: str) -> bool:
        """관리자 권한 확인"""
        try:
            # 시스템 관리자면 즉시 허용
            if await self.is_system_admin(user_emp_no):
                return True

            # 관리자 역할 보유 여부 확인
            query = select(TbUserRoles.role_name).where(
                and_(
                    TbUserRoles.user_emp_no == user_emp_no,
                    TbUserRoles.role_name.in_(['ADMIN', 'SYSTEM_ADMIN']),
                    TbUserRoles.is_active == True
                )
            )
            result = await self.session.execute(query)
            admin_role = result.scalar_one_or_none()

            return admin_role is not None
            
        except Exception as e:
            logger.error(f"관리자 권한 확인 실패: {user_emp_no}, {str(e)}")
            return False
    
    async def get_managed_container_ids(self, manager_emp_no: str) -> List[str]:
        """지식관리자가 관리하는 컨테이너 ID 목록 조회 (하위 컨테이너 포함)
        
        반환값:
        - 시스템 관리자: [] (빈 리스트 = 필터링 없음, 전체 조회)
        - 지식관리자: [관리 컨테이너 + 모든 하위 컨테이너]
        """
        try:
            # 1. 시스템 관리자 체크 - 빈 리스트 반환 (전체 조회 의미)
            if await self.is_system_admin(manager_emp_no):
                logger.info(f"시스템 관리자 {manager_emp_no}: 전체 컨테이너 접근 허용")
                return []
            
            # 2. 관리자가 ADMIN, MANAGER, OWNER 권한을 가진 컨테이너 조회
            manager_roles = {'ADMIN', 'MANAGER', 'OWNER', 'SYSTEM_ADMIN', 'OWNER_DEPT', 'OWNER_DIVISION'}
            
            query = select(TbUserPermissions.container_id).where(
                and_(
                    TbUserPermissions.user_emp_no == manager_emp_no,
                    TbUserPermissions.role_id.in_(manager_roles),
                    TbUserPermissions.is_active == True
                )
            )
            result = await self.session.execute(query)
            root_container_ids = [row[0] for row in result.all()]
            
            if not root_container_ids:
                logger.warning(f"지식관리자 {manager_emp_no}: 관리 권한이 있는 컨테이너 없음")
                return []
            
            # 3. 각 루트 컨테이너의 하위 컨테이너를 재귀적으로 조회
            all_container_ids = set(root_container_ids)
            
            async def get_descendants(parent_id: str):
                """재귀적으로 하위 컨테이너 조회"""
                child_query = select(TbKnowledgeContainers.container_id).where(
                    TbKnowledgeContainers.parent_container_id == parent_id
                )
                child_result = await self.session.execute(child_query)
                children = [row[0] for row in child_result.all()]
                
                for child_id in children:
                    if child_id not in all_container_ids:
                        all_container_ids.add(child_id)
                        await get_descendants(child_id)
            
            # 모든 루트 컨테이너의 하위 항목 수집
            for root_id in root_container_ids:
                await get_descendants(root_id)
            
            logger.info(f"지식관리자 {manager_emp_no}: {len(all_container_ids)}개 컨테이너 관리 범위")
            return list(all_container_ids)
            
        except Exception as e:
            logger.error(f"관리 컨테이너 조회 실패: {manager_emp_no}, {str(e)}")
            return []
    
    async def list_all_permissions(
        self,
        container_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        manager_emp_no: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """전체 사용자 권한 목록 조회 (관리자용)
        
        Args:
            container_id: 특정 컨테이너 필터링
            skip: 페이징 시작 위치
            limit: 최대 반환 개수
            manager_emp_no: 지식관리자 사번 (범위 제한 적용)
        """
        try:
            # 기본 권한 쿼리
            query = select(
                TbUserPermissions,
                TbKnowledgeContainers.container_name,
                TbSapHrInfo.emp_nm,
                TbSapHrInfo.dept_nm
            ).join(
                TbKnowledgeContainers,
                TbUserPermissions.container_id == TbKnowledgeContainers.container_id,
                isouter=True
            ).join(
                TbSapHrInfo,
                TbUserPermissions.user_emp_no == TbSapHrInfo.emp_no,
                isouter=True
            ).where(
                TbUserPermissions.is_active == True
            )
            
            # 지식관리자 범위 제한 적용
            if manager_emp_no:
                allowed_container_ids = await self.get_managed_container_ids(manager_emp_no)
                
                # 빈 리스트가 아닐 경우에만 필터링 적용
                # 빈 리스트 = 시스템 관리자 = 전체 조회
                if allowed_container_ids:
                    logger.info(f"지식관리자 {manager_emp_no} 필터링 적용: {len(allowed_container_ids)}개 컨테이너")
                    query = query.where(TbUserPermissions.container_id.in_(allowed_container_ids))
                elif not await self.is_system_admin(manager_emp_no):
                    # 시스템 관리자가 아니면서 관리 범위가 없으면 빈 목록 반환
                    logger.warning(f"지식관리자 {manager_emp_no}: 관리 범위 없음, 빈 목록 반환")
                    return []
                else:
                    logger.info(f"시스템 관리자 {manager_emp_no}: 필터링 없이 전체 조회")

            
            # 컨테이너 필터링
            if container_id:
                query = query.where(TbUserPermissions.container_id == container_id)
            
            # 페이징
            query = query.offset(skip).limit(limit)
            
            result = await self.session.execute(query)
            rows = result.all()
            
            admin_roles = {'ADMIN', 'SYSTEM_ADMIN', 'OWNER', 'OWNER_DEPT', 'OWNER_DIVISION'}
            write_roles = {
                'MANAGER', 'EDITOR', 'CONTRIBUTOR', 'FULL_ACCESS', 'WRITER', 'WRITE',
                'MEMBER_DEPT', 'MANAGER_DEPT', 'MANAGER_DIVISION'
            }

            permissions = []
            for perm, container_name, emp_name, dept_name in rows:
                role_upper = (perm.role_id or '').upper()
                if role_upper in admin_roles:
                    permission_type = 'admin'
                elif role_upper in write_roles:
                    permission_type = 'write'
                else:
                    permission_type = 'read'

                permissions.append({
                    'id': f"{perm.user_emp_no}_{perm.container_id}",
                    'user_emp_no': perm.user_emp_no,
                    'user_name': emp_name or perm.user_emp_no,
                    'department': dept_name or '',
                    'container_id': perm.container_id,
                    'container_name': container_name or perm.container_id,
                    'permission_type': permission_type,
                    'role_id': perm.role_id,
                    'granted_at': perm.granted_date.isoformat() if perm.granted_date else None,
                    'granted_by': perm.granted_by,
                    'valid_until': perm.expires_date.isoformat() if perm.expires_date else None
                })
            
            return permissions
            
        except Exception as e:
            logger.error(f"전체 권한 목록 조회 실패: {str(e)}")
            return []


async def get_permission_service() -> AsyncGenerator[PermissionService, None]:
    """권한 서비스 의존성 주입"""
    async for session in get_db():
        yield PermissionService(session)


# 전역 권한 서비스 인스턴스를 위한 래퍼 클래스
class GlobalPermissionService:
    """전역 권한 서비스"""
    
    async def get_user_accessible_containers(
        self, 
        user_emp_no: str, 
        min_permission: str = "VIEWER"
    ) -> List[Dict[str, Any]]:
        """사용자가 접근 가능한 컨테이너 목록 반환"""
        async for db in get_db():
            service = PermissionService(db)
            return await service.get_accessible_containers(user_emp_no)
    
    async def check_container_permission(
        self,
        user_emp_no: str,
        container_id: str,
        required_permission: str = "VIEWER"
    ) -> bool:
        """컨테이너 접근 권한 확인"""
        async for db in get_db():
            service = PermissionService(db)
            return await service.check_permission(user_emp_no, container_id, required_permission)
    
    async def check_upload_permission(
        self,
        user_emp_no: str,
        container_id: str
    ) -> Tuple[bool, str]:
        """
        컨테이너 업로드 권한 확인
        
        Returns:
            Tuple[bool, str]: (권한 여부, 권한 레벨)
        """
        async for db in get_db():
            service = PermissionService(db)
            
            # 컨테이너 활성 상태 확인
            container_query = select(TbKnowledgeContainers).where(
                and_(
                    TbKnowledgeContainers.container_id == container_id,
                    TbKnowledgeContainers.is_active == True
                )
            )
            container_result = await db.execute(container_query)
            container = container_result.scalar_one_or_none()
            
            if not container:
                return False, "컨테이너를 찾을 수 없습니다."
            
            # 사용자 권한 레벨 확인
            permission_level = await service.get_user_permission_level(user_emp_no, container_id)
            
            if not permission_level:
                return False, "접근 권한이 없습니다."
            
            # 업로드 권한 확인 (OWNER, EDITOR 이상 또는 부서 멤버 허용)
            upload_allowed_levels = ["OWNER", "ADMIN", "MANAGER", "EDITOR", "CONTRIBUTOR", "MEMBER_DEPT"]
            can_upload = permission_level in upload_allowed_levels
            
            if not can_upload:
                return False, f"업로드 권한이 없습니다. 현재 권한: {permission_level}"
            
            return True, permission_level
    
    async def check_download_permission(
        self,
        user_emp_no: str,
        container_id: str
    ) -> Tuple[bool, str]:
        """
        컨테이너 다운로드 권한 확인
        
        Returns:
            Tuple[bool, str]: (권한 여부, 메시지)
        """
        async for db in get_db():
            service = PermissionService(db)
            
            # 시스템 관리자 확인
            if await service.is_system_admin(user_emp_no):
                return True, "ADMIN"
            
            # 컨테이너 활성 상태 확인
            container_query = select(TbKnowledgeContainers).where(
                and_(
                    TbKnowledgeContainers.container_id == container_id,
                    TbKnowledgeContainers.is_active == True
                )
            )
            container_result = await db.execute(container_query)
            container = container_result.scalar_one_or_none()
            
            if not container:
                return False, "컨테이너를 찾을 수 없습니다."
            
            # 사용자 권한 레벨 확인
            permission_level = await service.get_user_permission_level(user_emp_no, container_id)
            
            if not permission_level:
                return False, "접근 권한이 없습니다."
            
            # 다운로드 권한 확인 (VIEWER 이상 모두 허용)
            download_allowed_levels = ["ADMIN", "MANAGER", "OWNER", "EDITOR", "CONTRIBUTOR", "VIEWER", "MEMBER_DEPT", "READER"]
            can_download = permission_level in download_allowed_levels
            
            if not can_download:
                return False, f"다운로드 권한이 없습니다. 현재 권한: {permission_level}"
            
            logger.info(f"✅ 다운로드 권한 확인 성공 - 사용자: {user_emp_no}, 컨테이너: {container_id}, 권한: {permission_level}")
            return True, permission_level
    
    async def check_delete_permission(
        self,
        user_emp_no: str,
        container_id: str,
        owner_emp_no: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        문서 삭제 권한 확인
        
        Args:
            user_emp_no: 현재 사용자 사번
            container_id: 컨테이너 ID
            owner_emp_no: 문서 소유자 사번
            created_by: 문서 생성자 사번
        
        Returns:
            Tuple[bool, str]: (권한 여부, 메시지)
        """
        async for db in get_db():
            service = PermissionService(db)
            
            # 1. 문서 소유자 또는 생성자인 경우 허용
            if user_emp_no in {owner_emp_no, created_by}:
                return True, "문서 소유자/생성자"
            
            # 2. 컨테이너 관리자 권한 확인
            permission_level = await service.get_user_permission_level(user_emp_no, container_id)
            
            if not permission_level:
                return False, "문서 삭제 권한이 없습니다."
            
            # 삭제 권한 확인 (ADMIN, MANAGER, EDITOR만 타인 문서 삭제 가능)
            delete_allowed_levels = ["ADMIN", "MANAGER", "EDITOR"]
            can_delete = permission_level in delete_allowed_levels
            
            if not can_delete:
                return False, f"문서 삭제 권한이 없습니다. 현재 권한: {permission_level}"
            
            return True, permission_level
    
    async def get_user_accessible_containers_with_upload_permission(
        self,
        user_emp_no: str
    ) -> List[Dict[str, Any]]:
        """
        사용자가 업로드 가능한 컨테이너 목록 조회
        """
        async for db in get_db():
            service = PermissionService(db)
            
            # 모든 활성 컨테이너 조회
            containers_query = select(TbKnowledgeContainers).where(
                TbKnowledgeContainers.is_active == True
            ).order_by(
                TbKnowledgeContainers.org_level,
                TbKnowledgeContainers.display_order.nulls_last()
            )
            
            containers_result = await db.execute(containers_query)
            containers = containers_result.scalars().all()
            
            accessible_containers = []
            
            for container in containers:
                # 각 컨테이너별 권한 확인
                permission_level = await service.get_user_permission_level(user_emp_no, container.container_id)
                
                if permission_level:
                    can_upload = permission_level in ["OWNER", "EDITOR", "CONTRIBUTOR"]
                    
                    container_info = {
                        "container_id": container.container_id,
                        "container_name": container.container_name,
                        "container_type": container.container_type,
                        "hierarchy_level": container.org_level,
                        "hierarchy_path": container.org_path,
                        "access_level": container.access_level,
                        "parent_container_id": container.parent_container_id,
                        "display_order": container.display_order,
                        "can_upload": can_upload,
                        "user_permission": permission_level
                    }
                    
                    accessible_containers.append(container_info)
            
            return accessible_containers
    
    async def check_admin_permission(self, user_emp_no: str) -> bool:
        """관리자 권한 확인"""
        try:
            # PermissionService를 사용해 실제 관리자 권한 확인
            async for session in get_db():
                service = PermissionService(session)
                return await service.check_admin_permission(user_emp_no)
            
        except Exception as e:
            logger.error(f"관리자 권한 확인 실패: {user_emp_no}, {str(e)}")
            return False
    
    async def list_all_permissions(
        self,
        container_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        manager_emp_no: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """전체 사용자 권한 목록 조회 (관리자용)
        
        Args:
            container_id: 특정 컨테이너 필터링
            skip: 페이징 시작 위치
            limit: 최대 반환 개수
            manager_emp_no: 지식관리자 사번 (범위 제한 적용)
        """
        try:
            # 기본 권한 쿼리
            query = select(
                TbUserPermissions,
                TbKnowledgeContainers.container_name,
                TbSapHrInfo.emp_nm,
                TbSapHrInfo.dept_nm
            ).join(
                TbKnowledgeContainers,
                TbUserPermissions.container_id == TbKnowledgeContainers.container_id,
                isouter=True
            ).join(
                TbSapHrInfo,
                TbUserPermissions.user_emp_no == TbSapHrInfo.emp_no,
                isouter=True
            ).where(
                TbUserPermissions.is_active == True
            )
            
            # 지식관리자 범위 제한 적용
            if manager_emp_no:
                async for session in get_db():
                    service = PermissionService(session)
                    allowed_container_ids = await service.get_managed_container_ids(manager_emp_no)
                    
                    # 빈 리스트가 아닐 경우에만 필터링 적용
                    # 빈 리스트 = 시스템 관리자 = 전체 조회
                    if allowed_container_ids:
                        query = query.where(TbUserPermissions.container_id.in_(allowed_container_ids))
                    elif not await service.is_system_admin(manager_emp_no):
                        # 시스템 관리자가 아니면서 관리 범위가 없으면 빈 목록 반환
                        return []
                    break

            
            # 컨테이너 필터링
            if container_id:
                query = query.where(TbUserPermissions.container_id == container_id)
            
            # 페이징
            query = query.offset(skip).limit(limit)
            
            async for session in get_db():
                result = await session.execute(query)
                rows = result.all()
                break
            
            permissions = []
            for perm, container_name, emp_name, dept_name in rows:
                permissions.append({
                    'id': f"{perm.user_emp_no}_{perm.container_id}",
                    'user_emp_no': perm.user_emp_no,
                    'user_name': emp_name or perm.user_emp_no,
                    'department': dept_name or '',
                    'container_id': perm.container_id,
                    'container_name': container_name or perm.container_id,
                    'permission_type': 'write' if perm.role_id in ['ADMIN', 'MANAGER', 'EDITOR'] else 'read',
                    'role_id': perm.role_id,
                    'granted_at': perm.granted_date.isoformat() if perm.granted_date else None,
                    'granted_by': perm.granted_by,
                    'valid_until': perm.expires_date.isoformat() if perm.expires_date else None
                })
            
            return permissions
            
        except Exception as e:
            logger.error(f"전체 권한 목록 조회 실패: {str(e)}")
            return []


# 싱글톤 인스턴스
permission_service = GlobalPermissionService()

"""
WKMS 지식 컨테이너 관리 서비스
계층형 조직 구조 및 지식 분류 관리
"""
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, and_, or_, func, text, update, delete
from app.models import (
    TbKnowledgeContainers,
    TbUserPermissions,
    TbKnowledgeCategories,
    TbContainerCategories,
    TbSapHrInfo,
    TbFileBssInfo,
    User
)
from app.services.auth.permission_service import PermissionService
from app.core.database import get_db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ContainerService:
    """지식 컨테이너 관리 서비스"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_service = PermissionService(session)
    
    async def create_container(
        self,
        creator_emp_no: str,
        container_id: str,
        container_name: str,
        parent_container_id: Optional[str] = None,
        container_type: str = 'department',
        description: Optional[str] = None,
        knowledge_category: Optional[str] = None,
        access_level: str = 'internal',
        default_permission: str = 'VIEWER',
        sap_org_code: Optional[str] = None,
        sap_cost_center: Optional[str] = None
    ) -> bool:
        """지식 컨테이너 생성"""
        try:
            # 컨테이너 ID 중복 확인
            existing_query = select(TbKnowledgeContainers).where(
                TbKnowledgeContainers.container_id == container_id
            )
            existing_result = await self.session.execute(existing_query)
            if existing_result.scalar_one_or_none():
                logger.warning(f"이미 존재하는 컨테이너 ID: {container_id}")
                return False
            
            # 부모 컨테이너 정보 조회 (있는 경우)
            org_level = 1
            org_path = f"/{container_id}"
            
            if parent_container_id:
                parent_query = select(TbKnowledgeContainers).where(
                    TbKnowledgeContainers.container_id == parent_container_id
                )
                parent_result = await self.session.execute(parent_query)
                parent = parent_result.scalar_one_or_none()
                
                if not parent:
                    logger.warning(f"존재하지 않는 부모 컨테이너: {parent_container_id}")
                    return False
                
                # 부모 컨테이너에 대한 관리 권한 확인 (임시 우회)
                logger.info(f"부모 컨테이너 관리 권한 우회: {creator_emp_no}")
                
                org_level = parent.org_level + 1
                org_path = f"{parent.org_path}/{container_id}"
            
            # 컨테이너 생성
            container = TbKnowledgeContainers(
                container_id=container_id,
                container_name=container_name,
                parent_container_id=parent_container_id,
                container_type=container_type,
                sap_org_code=sap_org_code,
                sap_cost_center=sap_cost_center,
                org_level=org_level,
                org_path=org_path,
                description=description,
                knowledge_category=knowledge_category,
                access_level=access_level,
                default_permission=default_permission,
                inherit_parent_permissions=True,
                permission_inheritance_type='additive',
                container_owner=creator_emp_no,
                auto_assign_by_org=True,
                require_approval_for_access=False,
                approval_workflow_enabled=True,
                approvers=[creator_emp_no],
                is_active=True,
                document_count=0,
                total_knowledge_size=0,
                user_count=0,
                permission_request_count=0,
                created_by=creator_emp_no,
                created_date=datetime.now()
            )
            
            self.session.add(container)
            await self.session.flush()  # ID 생성
            
            # 생성자에게 ADMIN 권한 부여
            await self.permission_service.grant_permission(
                grantor_emp_no='SYSTEM',
                user_emp_no=creator_emp_no,
                container_id=container_id,
                permission_level='ADMIN',
                granted_by='SYSTEM'
            )
            
            await self.session.commit()
            
            logger.info(f"컨테이너 생성 완료: {container_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"컨테이너 생성 실패: {container_id}, {str(e)}")
            return False
    
    async def get_container_hierarchy(
        self,
        user_emp_no: str,
        root_container_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """사용자가 접근 가능한 컨테이너 계층 구조 조회"""
        try:
            # 사용자가 관리자인지 확인 (User 테이블의 is_admin 플래그 체크)
            user_query = select(User).where(User.emp_no == user_emp_no)
            user_result = await self.session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            is_admin = user.is_admin if user else False
            logger.info(f"Container hierarchy request - user: {user_emp_no}, is_admin: {is_admin}")
            
            if is_admin:
                # 관리자는 모든 컨테이너에 접근 가능
                query = select(TbKnowledgeContainers).where(
                    TbKnowledgeContainers.is_active == True
                ).order_by(TbKnowledgeContainers.org_level, TbKnowledgeContainers.container_name)
                
                if root_container_id:
                    query = query.where(
                        or_(
                            TbKnowledgeContainers.container_id == root_container_id,
                            TbKnowledgeContainers.org_path.like(f"%/{root_container_id}/%")
                        )
                    )
                
                result = await self.session.execute(query)
                containers = result.scalars().all()
                logger.info(f"Admin query returned {len(containers)} containers")
                
                # 계층 구조 생성 (관리자용)
                container_map = {}
                hierarchy = []
                
                for container in containers:
                    container_data = {
                        'container_id': container.container_id,
                        'container_name': container.container_name,
                        'container_type': container.container_type,
                        'description': container.description,
                        'knowledge_category': container.knowledge_category,
                        'access_level': container.access_level,
                        'org_level': container.org_level,
                        'org_path': container.org_path,
                        'parent_container_id': container.parent_container_id,
                        'document_count': container.document_count,
                        'user_count': container.user_count,
                        'permission_level': 'ADMIN',  # 관리자는 모든 권한
                        'children': []
                    }
                    
                    container_map[container.container_id] = container_data
                    
                    if container.parent_container_id and container.parent_container_id in container_map:
                        container_map[container.parent_container_id]['children'].append(container_data)
                    else:
                        hierarchy.append(container_data)
                
                logger.info(f"Final hierarchy has {len(hierarchy)} root containers")
                return hierarchy
            
            else:
                # 일반 사용자는 권한 기반 접근
                accessible_containers = await self.permission_service.get_accessible_containers(user_emp_no)
                accessible_ids = [c['container_id'] for c in accessible_containers]
                
                if not accessible_ids:
                    return []
                
                # 컨테이너 상세 정보 조회
                query = select(TbKnowledgeContainers).where(
                    and_(
                        TbKnowledgeContainers.container_id.in_(accessible_ids),
                        TbKnowledgeContainers.is_active == True
                    )
                ).order_by(TbKnowledgeContainers.org_level, TbKnowledgeContainers.container_name)
                
                if root_container_id:
                    query = query.where(
                        or_(
                            TbKnowledgeContainers.container_id == root_container_id,
                            TbKnowledgeContainers.org_path.like(f"%/{root_container_id}/%")
                        )
                    )
                
                result = await self.session.execute(query)
                containers = result.scalars().all()
                
                # 계층 구조 생성
                container_map = {}
                hierarchy = []
                
                # 권한 정보 매핑
                # permission_level 키는 role_id 별칭(호환) - 내부적으로 role_id로 간주
                permission_map = {c['container_id']: c.get('permission_level') for c in accessible_containers}
                
                for container in containers:
                    container_data = {
                        'container_id': container.container_id,
                        'container_name': container.container_name,
                        'container_type': container.container_type,
                        'description': container.description,
                        'knowledge_category': container.knowledge_category,
                        'access_level': container.access_level,
                        'org_level': container.org_level,
                        'org_path': container.org_path,
                        'parent_container_id': container.parent_container_id,
                        'document_count': container.document_count,
                        'user_count': container.user_count,
                        'permission_level': permission_map.get(container.container_id, 'VIEWER'),
                        'children': []
                    }
                    
                    container_map[container.container_id] = container_data
                    
                    if container.parent_container_id and container.parent_container_id in container_map:
                        container_map[container.parent_container_id]['children'].append(container_data)
                    else:
                        hierarchy.append(container_data)
                
                return hierarchy
            
        except Exception as e:
            logger.error(f"컨테이너 계층 조회 실패: {user_emp_no}, {str(e)}")
            return []
    
    async def get_container_details(
        self,
        user_emp_no: str,
        container_id: str
    ) -> Optional[Dict[str, Any]]:
        """컨테이너 상세 정보 조회"""
        try:
            # 권한 확인 임시 우회
            logger.info(f"컨테이너 접근 허용: {user_emp_no}, {container_id}")
            
            # 컨테이너 정보 조회
            query = select(TbKnowledgeContainers).where(
                and_(
                    TbKnowledgeContainers.container_id == container_id,
                    TbKnowledgeContainers.is_active == True
                )
            )
            result = await self.session.execute(query)
            container = result.scalar_one_or_none()
            
            if not container:
                return None
            
            # 사용자 권한 레벨 조회
            user_permission = await self.permission_service.get_user_permission_level(
                user_emp_no, container_id
            )
            
            # 컨테이너 소유자 정보 조회
            owner_info = None
            if container.container_owner:
                owner_query = select(TbSapHrInfo).where(
                    TbSapHrInfo.emp_no == container.container_owner
                )
                owner_result = await self.session.execute(owner_query)
                owner = owner_result.scalar_one_or_none()
                if owner:
                    owner_info = {
                        'emp_no': owner.emp_no,
                        'emp_nm': owner.emp_nm,
                        'dept_nm': owner.dept_nm
                    }
            
            # 카테고리 정보 조회
            categories = await self._get_container_categories(container_id)
            
            return {
                'container_id': container.container_id,
                'container_name': container.container_name,
                'container_type': container.container_type,
                'description': container.description,
                'knowledge_category': container.knowledge_category,
                'access_level': container.access_level,
                'default_permission': container.default_permission,
                'org_level': container.org_level,
                'org_path': container.org_path,
                'parent_container_id': container.parent_container_id,
                'sap_org_code': container.sap_org_code,
                'sap_cost_center': container.sap_cost_center,
                'inherit_parent_permissions': container.inherit_parent_permissions,
                'permission_inheritance_type': container.permission_inheritance_type,
                'auto_assign_by_org': container.auto_assign_by_org,
                'require_approval_for_access': container.require_approval_for_access,
                'approval_workflow_enabled': container.approval_workflow_enabled,
                'document_count': container.document_count,
                'total_knowledge_size': container.total_knowledge_size,
                'user_count': container.user_count,
                'permission_request_count': container.permission_request_count,
                'last_knowledge_update': container.last_knowledge_update,
                'last_permission_update': container.last_permission_update,
                'created_date': container.created_date,
                'user_permission_level': user_permission,
                'owner_info': owner_info,
                'categories': categories,
                'tags': container.tags
            }
            
        except Exception as e:
            logger.error(f"컨테이너 상세 조회 실패: {container_id}, {str(e)}")
            return None
    
    async def update_container(
        self,
        user_emp_no: str,
        container_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """컨테이너 정보 업데이트"""
        try:
            # 관리 권한 확인
            if not await self.permission_service.check_permission(user_emp_no, container_id, 'MANAGER'):
                logger.warning(f"컨테이너 관리 권한 없음: {user_emp_no}, {container_id}")
                return False
            
            # 허용되는 업데이트 필드만 처리
            allowed_fields = {
                'container_name', 'description', 'knowledge_category', 'access_level',
                'default_permission', 'inherit_parent_permissions', 'permission_inheritance_type',
                'auto_assign_by_org', 'require_approval_for_access', 'approval_workflow_enabled',
                'tags'
            }
            
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            if not filtered_updates:
                return True
            
            # 업데이트 실행
            filtered_updates['last_modified_by'] = user_emp_no
            filtered_updates['last_modified_date'] = datetime.now()
            
            update_query = update(TbKnowledgeContainers).where(
                TbKnowledgeContainers.container_id == container_id
            ).values(**filtered_updates)
            
            await self.session.execute(update_query)
            await self.session.commit()
            
            logger.info(f"컨테이너 업데이트 완료: {container_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"컨테이너 업데이트 실패: {container_id}, {str(e)}")
            return False
    
    async def _get_container_categories(self, container_id: str) -> List[Dict[str, Any]]:
        """컨테이너의 카테고리 목록 조회"""
        try:
            query = select(
                TbContainerCategories,
                TbKnowledgeCategories
            ).join(
                TbKnowledgeCategories,
                TbContainerCategories.category_id == TbKnowledgeCategories.category_id
            ).where(
                TbContainerCategories.container_id == container_id
            ).order_by(TbContainerCategories.is_primary.desc(), TbContainerCategories.relevance_score.desc())
            
            result = await self.session.execute(query)
            
            categories = []
            for mapping, category in result:
                categories.append({
                    'category_id': category.category_id,
                    'category_name': category.category_name,
                    'category_level': category.category_level,
                    'description': category.description,
                    'is_primary': mapping.is_primary,
                    'relevance_score': mapping.relevance_score,
                    'color_code': category.color_code,
                    'icon_name': category.icon_name
                })
            
            return categories
            
        except Exception as e:
            logger.error(f"컨테이너 카테고리 조회 실패: {container_id}, {str(e)}")
            return []
    
    async def assign_category(
        self,
        user_emp_no: str,
        container_id: str,
        category_id: int,
        is_primary: bool = False,
        relevance_score: int = 5
    ) -> bool:
        """컨테이너에 카테고리 할당"""
        try:
            # 관리 권한 확인
            if not await self.permission_service.check_permission(user_emp_no, container_id, 'MANAGER'):
                return False
            
            # 기존 매핑 확인
            existing_query = select(TbContainerCategories).where(
                and_(
                    TbContainerCategories.container_id == container_id,
                    TbContainerCategories.category_id == category_id
                )
            )
            existing_result = await self.session.execute(existing_query)
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                # 기존 매핑 업데이트
                existing.is_primary = is_primary
                existing.relevance_score = relevance_score
            else:
                # 새 매핑 생성
                mapping = TbContainerCategories(
                    container_id=container_id,
                    category_id=category_id,
                    is_primary=is_primary,
                    relevance_score=relevance_score,
                    created_by=user_emp_no,
                    created_date=datetime.now()
                )
                self.session.add(mapping)
            
            await self.session.commit()
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"카테고리 할당 실패: {container_id}, {category_id}, {str(e)}")
            return False
    
    async def get_container_statistics(
        self,
        user_emp_no: str,
        container_id: str
    ) -> Optional[Dict[str, Any]]:
        """컨테이너 통계 정보 조회"""
        try:
            # 접근 권한 확인
            if not await self.permission_service.check_permission(user_emp_no, container_id, 'VIEWER'):
                return None
            
            # 기본 통계 (컨테이너 테이블에서)
            container_query = select(TbKnowledgeContainers).where(
                TbKnowledgeContainers.container_id == container_id
            )
            container_result = await self.session.execute(container_query)
            container = container_result.scalar_one_or_none()
            
            if not container:
                return None
            
            # 사용자 권한 분포 조회
            permission_query = select(
                TbUserPermissions.permission_level,
                func.count(TbUserPermissions.permission_id).label('count')
            ).where(
                and_(
                    TbUserPermissions.knowledge_container_id == container_id,
                    TbUserPermissions.is_active == True
                )
            ).group_by(TbUserPermissions.permission_level)
            
            permission_result = await self.session.execute(permission_query)
            permission_distribution = {row.permission_level: row.count for row in permission_result}
            
            return {
                'container_id': container_id,
                'document_count': container.document_count,
                'total_knowledge_size': container.total_knowledge_size,
                'user_count': container.user_count,
                'permission_request_count': container.permission_request_count,
                'last_knowledge_update': container.last_knowledge_update,
                'last_permission_update': container.last_permission_update,
                'permission_distribution': permission_distribution,
                'created_date': container.created_date
            }
            
        except Exception as e:
            logger.error(f"컨테이너 통계 조회 실패: {container_id}, {str(e)}")
            return None

    async def get_user_accessible_containers(
        self,
        user_emp_no: str,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        사용자가 접근 가능한 컨테이너 목록 조회 (N+1 문제 해결)
        각 컨테이너별 실제 문서 수도 함께 조회
        """
        try:
            # 🚀 단일 쿼리로 컨테이너와 권한 정보를 함께 조회 (N+1 문제 해결)
            query = select(
                TbKnowledgeContainers,
                TbUserPermissions.role_id,
                TbUserPermissions.permission_type,
                TbUserPermissions.access_scope
            ).join(
                TbUserPermissions,
                TbKnowledgeContainers.container_id == TbUserPermissions.container_id
            ).where(
                and_(
                    TbUserPermissions.user_emp_no == user_emp_no,
                    TbKnowledgeContainers.is_active == True,
                    TbUserPermissions.is_active == True
                )
            ).order_by(
                TbKnowledgeContainers.org_level,
                TbKnowledgeContainers.container_name
            )
            
            result = await session.execute(query)
            rows = result.all()
            
            container_list = []
            for container, role_id, permission_type, access_scope in rows:
                # 🔢 각 컨테이너별 실제 문서 수 조회
                doc_count_query = select(func.count(TbFileBssInfo.file_bss_info_sno)).where(
                    and_(
                        TbFileBssInfo.knowledge_container_id == container.container_id,
                        TbFileBssInfo.del_yn != 'Y'
                    )
                )
                doc_count_result = await session.execute(doc_count_query)
                actual_document_count = doc_count_result.scalar() or 0
                
                container_info = {
                    "container_id": container.container_id,
                    "container_name": container.container_name,
                    "container_type": container.container_type,
                    "description": container.description,
                    "hierarchy_level": getattr(container, 'org_level', 1),
                    "hierarchy_path": getattr(container, 'org_path', ''),
                    "parent_container_id": container.parent_container_id,
                    "access_level": container.access_level,
                    "display_order": getattr(container, 'display_order', 0),
                    "user_permission": role_id or permission_type or "VIEWER",
                    "permission_type": permission_type,
                    "access_scope": access_scope,
                    "can_upload": (role_id or permission_type) in ["ADMIN", "MANAGER", "EDITOR"],
                    "created_date": container.created_date,
                    "is_active": container.is_active,
                    "document_count": actual_document_count  # 🔢 실제 문서 수
                }
                container_list.append(container_info)
                
            logger.info(f"사용자 접근 가능 컨테이너 조회 완료: {user_emp_no}, {len(container_list)}개")
            return container_list
            
        except Exception as e:
            logger.error(f"사용자 접근 가능 컨테이너 조회 실패: {user_emp_no}, {str(e)}")
            return []
    
    async def update_container_document_count(
        self,
        container_id: str
    ) -> int:
        """
        컨테이너의 document_count를 실제 문서 개수로 업데이트 (완료된 문서만 집계)
        
        Args:
            container_id: 업데이트할 컨테이너 ID
            
        Returns:
            업데이트된 문서 개수 (완료된 문서만)
        """
        try:
            # ✅ 실제 문서 개수 조회 (삭제되지 않고, 처리 완료된 문서만)
            # processing_status가 'completed'이거나 NULL인 문서만 집계
            doc_count_query = select(func.count(TbFileBssInfo.file_bss_info_sno)).where(
                and_(
                    TbFileBssInfo.knowledge_container_id == container_id,
                    TbFileBssInfo.del_yn != 'Y',
                    or_(
                        TbFileBssInfo.processing_status == 'completed',
                        TbFileBssInfo.processing_status.is_(None)  # 레거시 문서 (status 없음)
                    )
                )
            )
            doc_count_result = await self.session.execute(doc_count_query)
            actual_count = doc_count_result.scalar() or 0
            
            # tb_knowledge_containers 업데이트
            update_query = (
                update(TbKnowledgeContainers)
                .where(TbKnowledgeContainers.container_id == container_id)
                .values(
                    document_count=actual_count,
                    last_modified_date=datetime.utcnow()
                )
            )
            await self.session.execute(update_query)
            await self.session.commit()
            
            logger.info(f"컨테이너 문서 개수 업데이트: {container_id} -> {actual_count}개")
            return actual_count
            
        except Exception as e:
            logger.error(f"컨테이너 문서 개수 업데이트 실패: {container_id}, {str(e)}")
            await self.session.rollback()
            return 0


async def get_container_service() -> AsyncGenerator[ContainerService, None]:
    """컨테이너 서비스 의존성 주입"""
    async for session in get_db():
        yield ContainerService(session)

"""
지식 컨테이너 파일 관리 API (정리된 버전)
컨테이너별 파일 업로드, 조회, 삭제, 검색 기능
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.auth.permission_service import PermissionService
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Container File Management"])

ROLE_LABELS: Dict[str, str] = {
    "ADMIN": "관리자",
    "MANAGER": "매니저",
    "EDITOR": "편집자",
    "CONTRIBUTOR": "작성자",
    "VIEWER": "읽기전용",
    "WRITER": "작성자",
    "READER": "읽기전용",
    "OWNER": "소유자",
    "FULL_ACCESS": "전체 권한"
}

ROLE_INTERNAL_TO_UI: Dict[str, str] = {
    "ADMIN": "ADMIN",
    "MANAGER": "MANAGER",
    "EDITOR": "EDITOR",
    "CONTRIBUTOR": "WRITER",
    "VIEWER": "READER",
    "OWNER": "ADMIN",
    "FULL_ACCESS": "ADMIN"
}

ROLE_UI_TO_INTERNAL: Dict[str, str] = {
    "ADMIN": "ADMIN",
    "MANAGER": "MANAGER",
    "EDITOR": "EDITOR",
    "WRITER": "CONTRIBUTOR",
    "READER": "VIEWER"
}


def _to_internal_role(role_id: str) -> str:
    normalized = (role_id or "").upper()
    return ROLE_UI_TO_INTERNAL.get(normalized, normalized)


def _to_ui_role(role_id: Optional[str]) -> str:
    if not role_id:
        return ""
    normalized = role_id.upper()
    return ROLE_INTERNAL_TO_UI.get(normalized, normalized)


def _role_display_name(role_id: str) -> str:
    normalized = (role_id or "").upper()
    return ROLE_LABELS.get(normalized, normalized.title())

# Request/Response 모델들
class ContainerResponse(BaseModel):
    container_id: str
    container_name: str
    description: Optional[str] = None
    access_level: str
    document_count: int
    
class ContainerListResponse(BaseModel):
    success: bool
    containers: List[ContainerResponse]
    total_count: int


class ContainerPermissionEntry(BaseModel):
    user_emp_no: str
    user_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role_id: str
    role_name: str
    granted_date: Optional[datetime] = None


class ContainerPermissionListResponse(BaseModel):
    success: bool
    permissions: List[ContainerPermissionEntry]
    total_count: int


class ContainerPermissionRequest(BaseModel):
    user_emp_no: str
    role_id: str
    valid_until: Optional[datetime] = None


class ContainerPermissionUpdateRequest(BaseModel):
    role_id: str
    valid_until: Optional[datetime] = None


class ContainerPermissionActionResponse(BaseModel):
    success: bool
    message: str


class UserContainerPermissionResponse(BaseModel):
    """사용자의 특정 컨테이너에 대한 권한 정보"""
    success: bool
    container_id: str
    user_emp_no: str
    has_access: bool
    role_id: Optional[str] = None
    role_name: Optional[str] = None
    permission_level: str  # ADMIN, MANAGER, EDITOR, VIEWER, NONE
    can_read: bool
    can_write: bool
    can_delete: bool
    can_manage_permissions: bool
    can_create_subcontainer: bool


class ContainerPermissionActionResponse(BaseModel):
    success: bool
    message: str


class UserAccessibleContainersResponse(BaseModel):
    """사용자가 접근 가능한 컨테이너 ID 목록"""
    success: bool
    container_ids: List[str]
    total_count: int


class FullContainerTreeResponse(BaseModel):
    """전체 컨테이너 트리 (권한 정보 포함)"""
    success: bool
    containers: List[Dict[str, Any]]


# === 전체 컨테이너 트리 조회 (권한 정보 포함) ===
@router.get("/full-hierarchy", response_model=FullContainerTreeResponse)
async def get_full_container_hierarchy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    전체 조직 컨테이너 트리를 조회하고 각 노드에 사용자 권한 정보 포함
    - 모든 활성 컨테이너를 트리 구조로 반환
    - 각 노드에 사용자의 접근 권한 레벨 포함 (OWNER/EDITOR/VIEWER/NONE)
    """
    try:
        from app.models import TbKnowledgeContainers as Container
        from app.models import TbUserPermissions, TbFileBssInfo
        
        # 1. 모든 활성 컨테이너 조회
        containers_query = select(Container).where(
            Container.is_active == True
        ).order_by(Container.org_level, Container.container_name)
        
        result = await db.execute(containers_query)
        all_containers = result.scalars().all()
        
        # 2. 사용자 권한 조회
        permissions_query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_emp_no == current_user.emp_no,
                TbUserPermissions.is_active == True
            )
        )
        
        perm_result = await db.execute(permissions_query)
        user_permissions = perm_result.scalars().all()
        
        # 권한 매핑 (container_id -> role_id)
        permission_map = {
            perm.container_id: perm.role_id 
            for perm in user_permissions
        }
        
        # 3. 트리 구조 생성
        container_map = {}
        hierarchy = []
        
        for container in all_containers:
            # 🔢 실제 문서 개수 조회 (del_yn != 'Y' AND processing_status != 'failed')
            doc_count_query = select(func.count(TbFileBssInfo.file_bss_info_sno)).where(
                and_(
                    TbFileBssInfo.knowledge_container_id == container.container_id,
                    TbFileBssInfo.del_yn != 'Y',
                    or_(
                        TbFileBssInfo.processing_status.is_(None),
                        TbFileBssInfo.processing_status != 'failed'
                    )
                )
            )
            doc_count_result = await db.execute(doc_count_query)
            actual_document_count = doc_count_result.scalar() or 0
            
            # 사용자 권한 결정
            role_id = permission_map.get(container.container_id)
            
            # role_id를 권한 레벨로 변환
            if role_id:
                if role_id in ['OWNER', 'ADMIN', 'MANAGER']:
                    permission_level = 'OWNER'
                elif role_id in ['EDITOR', 'CONTRIBUTOR', 'WRITER', 'MEMBER_DEPT', 'MEMBER_DIVISION']:
                    permission_level = 'EDITOR'
                elif role_id in ['VIEWER', 'READER']:
                    permission_level = 'VIEWER'
                else:
                    permission_level = 'VIEWER'
            else:
                permission_level = 'NONE'
            
            container_data = {
                'id': container.container_id,
                'name': container.container_name,
                'container_type': container.container_type,
                'description': container.description,
                'org_level': container.org_level,
                'org_path': container.org_path,
                'parent_id': container.parent_container_id,
                'document_count': actual_document_count,  # 🔢 실제 문서 개수 사용
                'permission': permission_level,  # OWNER, EDITOR, VIEWER, NONE
                'children': []
            }
            
            container_map[container.container_id] = container_data
            
            # 부모-자식 관계 설정
            if container.parent_container_id and container.parent_container_id in container_map:
                container_map[container.parent_container_id]['children'].append(container_data)
            else:
                hierarchy.append(container_data)
        
        return FullContainerTreeResponse(
            success=True,
            containers=hierarchy
        )
        
    except Exception as e:
        logger.error(f"전체 컨테이너 트리 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="전체 컨테이너 트리를 조회하는 중 오류가 발생했습니다."
        )


# === 사용자 접근 가능한 컨테이너 ID 목록 ===
@router.get("/user-accessible", response_model=UserAccessibleContainersResponse)
async def get_user_accessible_containers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    현재 사용자가 접근 가능한 컨테이너 ID 목록 반환
    - 시스템 관리자: 모든 활성 컨테이너
    - 일반 사용자: 권한이 부여된 컨테이너만
    """
    try:
        from app.models import TbKnowledgeContainers as Container
        from app.models import TbUserPermissions
        
        # 시스템 관리자는 모든 컨테이너 접근 가능
        if current_user.is_admin:
            containers_query = select(Container.container_id).where(
                Container.is_active == True
            )
            result = await db.execute(containers_query)
            container_ids = [row[0] for row in result.fetchall()]
            
            return UserAccessibleContainersResponse(
                success=True,
                container_ids=container_ids,
                total_count=len(container_ids)
            )
        
        # 일반 사용자는 권한이 있는 컨테이너만
        containers_query = select(Container.container_id).join(
            TbUserPermissions,
            Container.container_id == TbUserPermissions.container_id
        ).where(
            and_(
                TbUserPermissions.user_emp_no == current_user.emp_no,
                Container.is_active == True,
                TbUserPermissions.is_active == True
            )
        ).distinct()
        
        result = await db.execute(containers_query)
        container_ids = [row[0] for row in result.fetchall()]
        
        return UserAccessibleContainersResponse(
            success=True,
            container_ids=container_ids,
            total_count=len(container_ids)
        )
        
    except Exception as e:
        logger.error(f"사용자 접근 가능 컨테이너 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="접근 가능한 컨테이너 목록을 조회하는 중 오류가 발생했습니다."
        )


# === 컨테이너 목록 조회 ===
@router.get("/", response_model=ContainerListResponse)
async def get_user_containers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자가 접근 가능한 지식 컨테이너 목록 조회
    시스템 관리자(is_admin=True)는 모든 컨테이너에 접근 가능
    """
    try:
        from app.models import TbKnowledgeContainers as Container
        from app.models import TbUserPermissions
        
        # 시스템 관리자는 모든 컨테이너 조회
        if current_user.is_admin:
            containers_query = select(Container).where(
                Container.is_active == True
            ).order_by(Container.org_level, Container.container_name)
            
            result = await db.execute(containers_query)
            containers = result.scalars().all()
            
            container_list = []
            for container in containers:
                container_list.append(ContainerResponse(
                    container_id=container.container_id,
                    container_name=container.container_name,
                    description=container.description,
                    access_level=container.access_level,
                    document_count=container.document_count or 0
                ))
            
            return ContainerListResponse(
                success=True,
                containers=container_list,
                total_count=len(container_list)
            )
        
        # 일반 사용자는 권한이 있는 컨테이너만 조회
        containers_query = select(Container).join(
            TbUserPermissions,
            Container.container_id == TbUserPermissions.container_id
        ).where(
            and_(
                TbUserPermissions.user_emp_no == current_user.emp_no,
                Container.is_active == True,
                TbUserPermissions.is_active == True
            )
        ).order_by(Container.org_level, Container.container_name)
        
        result = await db.execute(containers_query)
        containers = result.scalars().all()
        
        # 각 컨테이너별 권한 확인
        container_list = []
        for container in containers:
            # 권한 조회
            permission_query = select(TbUserPermissions).where(
                and_(
                    TbUserPermissions.user_emp_no == current_user.emp_no,
                    TbUserPermissions.container_id == container.container_id
                )
            )
            permission_result = await db.execute(permission_query)
            permission = permission_result.scalar_one_or_none()
            
            if permission:
                container_list.append(ContainerResponse(
                    container_id=container.container_id,
                    container_name=container.container_name,
                    description=container.description,
                    access_level=container.access_level,
                    document_count=container.document_count or 0
                ))
        
        return ContainerListResponse(
            success=True,
            containers=container_list,
            total_count=len(container_list)
        )
        
    except Exception as e:
        logger.error(f"컨테이너 목록 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="컨테이너 목록을 조회하는 중 오류가 발생했습니다."
        )

# === 컨테이너 계층 구조 조회 ===
class ContainerTreeNode(BaseModel):
    container_id: str
    container_name: str
    description: Optional[str] = None
    parent_container_id: Optional[str] = None
    org_level: int
    document_count: int
    user_count: int
    permission_level: Optional[str] = None
    children: List['ContainerTreeNode'] = []

ContainerTreeNode.model_rebuild()

class ContainerTreeResponse(BaseModel):
    success: bool
    containers: List[ContainerTreeNode]

@router.get("/hierarchy", response_model=ContainerTreeResponse)
async def get_container_hierarchy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자가 접근 가능한 컨테이너 계층 구조 조회
    시스템 관리자는 모든 컨테이너, 일반 사용자는 권한이 있는 컨테이너만 조회
    """
    try:
        from app.services.auth.container_service import ContainerService
        
        service = ContainerService(db)
        hierarchy = await service.get_container_hierarchy(current_user.emp_no)
        
        return ContainerTreeResponse(
            success=True,
            containers=hierarchy
        )
    except Exception as e:
        logger.error(f"컨테이너 계층 구조 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="컨테이너 계층 구조를 조회하는 중 오류가 발생했습니다."
        )

# === 컨테이너 상세 정보 조회 ===
@router.get("/{container_id}")
async def get_container_details(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 컨테이너의 상세 정보 조회
    """
    try:
        from app.models import TbKnowledgeContainers as Container
        from app.models import TbUserPermissions
        
        # 컨테이너 존재 여부 확인
        container_query = select(Container).where(
            and_(
                Container.container_id == container_id,
                Container.is_active == True
            )
        )
        container_result = await db.execute(container_query)
        container = container_result.scalar_one_or_none()
        
        if not container:
            raise HTTPException(
                status_code=404,
                detail="컨테이너를 찾을 수 없습니다."
            )
        
        # 사용자 권한 확인
        permission_query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_emp_no == current_user.emp_no,
                TbUserPermissions.container_id == container_id,
                TbUserPermissions.is_active == True
            )
        )
        permission_result = await db.execute(permission_query)
        permission = permission_result.scalar_one_or_none()
        
        if not permission:
            raise HTTPException(
                status_code=403,
                detail="이 컨테이너에 접근할 권한이 없습니다."
            )
        
        return {
            "container_id": container.container_id,
            "container_name": container.container_name,
            "description": container.description,
            "access_level": container.access_level,
            "document_count": container.document_count or 0,
            "user_permission": {
                "permission_type": permission.permission_type,
                "access_scope": permission.access_scope,
                "role_id": permission.role_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"컨테이너 상세 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="컨테이너 정보를 조회하는 중 오류가 발생했습니다."
        )

# === 향후 기능들 (TODO) ===
@router.get("/{container_id}/files")
async def list_container_files_placeholder():
    """향후 구현 예정: 컨테이너 파일 목록"""
    raise HTTPException(
        status_code=501,
        detail="이 기능은 아직 구현되지 않았습니다."
    )

@router.get("/{container_id}/files/{document_id}")
async def get_file_details_placeholder():
    """향후 구현 예정: 파일 상세 정보"""
    raise HTTPException(
        status_code=501,
        detail="이 기능은 아직 구현되지 않았습니다."
    )

@router.get("/{container_id}/statistics")
async def get_container_statistics_placeholder():
    """향후 구현 예정: 컨테이너 통계"""
    raise HTTPException(
        status_code=501,
        detail="이 기능은 아직 구현되지 않았습니다."
    )

# === 컨테이너 생성 ===
class CreateContainerRequest(BaseModel):
    container_id: str
    container_name: str
    description: Optional[str] = None
    parent_container_id: Optional[str] = None
    container_type: str = 'department'
    knowledge_category: Optional[str] = None
    access_level: str = 'internal'
    sap_org_code: Optional[str] = None

class ContainerCreateResponse(BaseModel):
    success: bool
    message: str
    container_id: str

@router.post("/", response_model=ContainerCreateResponse)
async def create_container(
    request: CreateContainerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 컨테이너 생성
    
    권한 규칙:
    1. 시스템 관리자(ADMIN): 모든 위치에 컨테이너 생성 가능
    2. 지식관리자(MANAGER/OWNER): 관리 범위 내(parent_container_id가 관리 컨테이너)에서만 생성 가능
    3. 일반 사용자: 생성 불가
    """
    try:
        permission_service = PermissionService(db)
        
        # 1. 시스템 관리자는 모든 컨테이너 생성 가능
        is_system_admin = await permission_service.is_system_admin(current_user.emp_no)
        
        if not is_system_admin:
            # 2. 지식관리자 권한 확인: parent_container_id에 대한 ADMIN/MANAGER 권한 필요
            if not request.parent_container_id:
                raise HTTPException(
                    status_code=403,
                    detail="최상위 컨테이너는 시스템 관리자만 생성할 수 있습니다."
                )
            
            # 부모 컨테이너에 대한 관리 권한 확인
            parent_permission = await permission_service.get_user_permission_level(
                current_user.emp_no, 
                request.parent_container_id
            )
            
            if parent_permission not in ['ADMIN', 'MANAGER', 'OWNER']:
                raise HTTPException(
                    status_code=403,
                    detail=f"부모 컨테이너({request.parent_container_id})에 대한 관리 권한이 없습니다. "
                           f"현재 권한: {parent_permission or 'NONE'}"
                )
            
            logger.info(
                f"지식관리자 {current_user.emp_no}가 {request.parent_container_id} 하위에 "
                f"컨테이너 {request.container_id} 생성 시도 (권한: {parent_permission})"
            )
        
        from app.services.auth.container_service import ContainerService
        
        service = ContainerService(db)
        success = await service.create_container(
            creator_emp_no=current_user.emp_no,
            container_id=request.container_id,
            container_name=request.container_name,
            parent_container_id=request.parent_container_id,
            container_type=request.container_type,
            description=request.description,
            knowledge_category=request.knowledge_category,
            access_level=request.access_level,
            sap_org_code=request.sap_org_code
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="컨테이너 생성에 실패했습니다. 컨테이너 ID가 이미 존재하거나 부모 컨테이너를 찾을 수 없습니다."
            )
        
        await db.commit()
        
        return ContainerCreateResponse(
            success=True,
            message="컨테이너가 성공적으로 생성되었습니다.",
            container_id=request.container_id
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"컨테이너 생성 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너를 생성하는 중 오류가 발생했습니다: {str(e)}"
        )

# === 컨테이너 수정 ===
class UpdateContainerRequest(BaseModel):
    container_name: Optional[str] = None
    description: Optional[str] = None
    access_level: Optional[str] = None
    knowledge_category: Optional[str] = None

class ContainerUpdateResponse(BaseModel):
    success: bool
    message: str

@router.put("/{container_id}", response_model=ContainerUpdateResponse)
async def update_container(
    container_id: str,
    request: UpdateContainerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    컨테이너 정보 수정
    
    권한 규칙:
    1. 시스템 관리자(ADMIN): 모든 컨테이너 수정 가능
    2. 지식관리자(MANAGER/OWNER): 관리 범위 내 컨테이너만 수정 가능
    3. 일반 사용자: 수정 불가
    """
    try:
        permission_service = PermissionService(db)
        
        # 1. 시스템 관리자 확인
        is_system_admin = await permission_service.is_system_admin(current_user.emp_no)
        
        if not is_system_admin:
            # 2. 지식관리자 권한 확인: 해당 컨테이너에 대한 ADMIN/MANAGER 권한 필요
            container_permission = await permission_service.get_user_permission_level(
                current_user.emp_no, 
                container_id
            )
            
            if container_permission not in ['ADMIN', 'MANAGER', 'OWNER']:
                raise HTTPException(
                    status_code=403,
                    detail=f"컨테이너({container_id})에 대한 관리 권한이 없습니다. "
                           f"현재 권한: {container_permission or 'NONE'}"
                )
            
            logger.info(
                f"지식관리자 {current_user.emp_no}가 컨테이너 {container_id} 수정 시도 "
                f"(권한: {container_permission})"
            )
        
        from app.models import TbKnowledgeContainers
        from sqlalchemy import update
        
        # 컨테이너 존재 확인
        query = select(TbKnowledgeContainers).where(
            TbKnowledgeContainers.container_id == container_id
        )
        result = await db.execute(query)
        container = result.scalar_one_or_none()
        
        if not container:
            raise HTTPException(
                status_code=404,
                detail="컨테이너를 찾을 수 없습니다."
            )
        
        # 수정할 필드만 업데이트
        update_data = {}
        if request.container_name is not None:
            update_data['container_name'] = request.container_name
        if request.description is not None:
            update_data['description'] = request.description
        if request.access_level is not None:
            update_data['access_level'] = request.access_level
        if request.knowledge_category is not None:
            update_data['knowledge_category'] = request.knowledge_category
        
        if update_data:
            update_data['last_modified_by'] = current_user.emp_no
            
            stmt = update(TbKnowledgeContainers).where(
                TbKnowledgeContainers.container_id == container_id
            ).values(**update_data)
            
            await db.execute(stmt)
            await db.commit()
        
        return ContainerUpdateResponse(
            success=True,
            message="컨테이너가 성공적으로 수정되었습니다."
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"컨테이너 수정 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너를 수정하는 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{container_id}/my-permission", response_model=UserContainerPermissionResponse)
async def get_my_container_permission(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자의 특정 컨테이너에 대한 권한 정보 조회"""
    permission_service = PermissionService(db)
    
    # 관리자는 모든 권한 보유
    if current_user.is_admin:
        return UserContainerPermissionResponse(
            success=True,
            container_id=container_id,
            user_emp_no=current_user.emp_no,
            has_access=True,
            role_id="ADMIN",
            role_name="관리자",
            permission_level="ADMIN",
            can_read=True,
            can_write=True,
            can_delete=True,
            can_manage_permissions=True,
            can_create_subcontainer=True
        )
    
    # 사용자의 권한 레벨 조회
    role_id = await permission_service.get_user_permission_level(current_user.emp_no, container_id)
    
    if not role_id:
        return UserContainerPermissionResponse(
            success=True,
            container_id=container_id,
            user_emp_no=current_user.emp_no,
            has_access=False,
            role_id=None,
            role_name=None,
            permission_level="NONE",
            can_read=False,
            can_write=False,
            can_delete=False,
            can_manage_permissions=False,
            can_create_subcontainer=False
        )
    
    # 권한 레벨에 따른 UI 권한 매핑
    permission_hierarchy = {
        'ADMIN': 1, 'OWNER_DEPT': 1, 'OWNER_DIVISION': 1, 'OWNER': 1, 'FULL_ACCESS': 1,
        'MANAGER': 2, 'MANAGER_DEPT': 2, 'MANAGER_DIVISION': 2,
        'EDITOR': 3, 'MEMBER_DEPT': 3, 'CONTRIBUTOR': 3, 'WRITER': 3,
        'VIEWER': 4, 'MEMBER_DIVISION': 4, 'READER': 4
    }
    
    level = permission_hierarchy.get(role_id.upper(), 999)
    
    # 권한 레벨별 UI 권한
    if level <= 1:  # ADMIN/OWNER
        permission_level = "ADMIN"
        can_read = can_write = can_delete = can_manage_permissions = can_create_subcontainer = True
    elif level == 2:  # MANAGER
        permission_level = "MANAGER"
        can_read = can_write = can_manage_permissions = can_create_subcontainer = True
        can_delete = False
    elif level == 3:  # EDITOR
        permission_level = "EDITOR"
        can_read = can_write = True
        can_delete = can_manage_permissions = can_create_subcontainer = False
    else:  # VIEWER
        permission_level = "VIEWER"
        can_read = True
        can_write = can_delete = can_manage_permissions = can_create_subcontainer = False
    
    return UserContainerPermissionResponse(
        success=True,
        container_id=container_id,
        user_emp_no=current_user.emp_no,
        has_access=True,
        role_id=role_id,
        role_name=_role_display_name(role_id),
        permission_level=permission_level,
        can_read=can_read,
        can_write=can_write,
        can_delete=can_delete,
        can_manage_permissions=can_manage_permissions,
        can_create_subcontainer=can_create_subcontainer
    )


@router.get("/{container_id}/permissions", response_model=ContainerPermissionListResponse)
async def get_container_permissions(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """컨테이너에 부여된 사용자 권한 목록 조회"""
    permission_service = PermissionService(db)

    # 권한 목록 조회는 해당 컨테이너에 접근 권한이 있는 모든 사용자가 가능
    # (단, 권한 부여/수정/삭제는 MANAGER 이상만 가능)
    if not current_user.is_admin:
        has_permission = await permission_service.check_permission(current_user.emp_no, container_id, 'VIEWER')
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 컨테이너의 권한을 조회할 권한이 없습니다."
            )

    raw_permissions = await permission_service.list_container_permissions(container_id=container_id)

    entries: List[ContainerPermissionEntry] = []
    for item in raw_permissions:
        base_role = item.get("role_id") or ""
        ui_role = _to_ui_role(base_role)
        role_id_value = ui_role or base_role
        display_role = _role_display_name(role_id_value)

        entries.append(
            ContainerPermissionEntry(
                user_emp_no=item.get("user_emp_no", ""),
                user_name=item.get("user_name"),
                department=item.get("department"),
                position=item.get("position"),
                role_id=role_id_value,
                role_name=display_role,
                granted_date=item.get("granted_date")
            )
        )

    return ContainerPermissionListResponse(
        success=True,
        permissions=entries,
        total_count=len(entries)
    )


@router.post(
    "/{container_id}/permissions",
    response_model=ContainerPermissionActionResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_container_permission(
    container_id: str,
    request: ContainerPermissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """컨테이너에 사용자 권한 부여"""
    permission_service = PermissionService(db)
    skip_check = bool(current_user.is_admin)

    if not skip_check:
        has_permission = await permission_service.check_permission(current_user.emp_no, container_id, 'MANAGER')
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 컨테이너의 권한을 부여할 권한이 없습니다."
            )

    internal_role = _to_internal_role(request.role_id)

    existing_permission = await permission_service.get_permission_record(
        user_emp_no=request.user_emp_no,
        container_id=container_id,
        include_inactive=True
    )

    if existing_permission and getattr(existing_permission, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 권한이 부여되어 있습니다. 변경이 필요하면 수정 엔드포인트를 사용하세요."
        )

    success = await permission_service.grant_permission(
        user_emp_no=request.user_emp_no,
        container_id=container_id,
        role_id=internal_role,
        grantor_emp_no=current_user.emp_no,
        granted_by=current_user.emp_no,
        valid_until=request.valid_until,
        skip_permission_check=skip_check
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="권한 부여에 실패했습니다."
        )

    return ContainerPermissionActionResponse(
        success=True,
        message="권한을 부여했습니다."
    )


@router.put(
    "/{container_id}/permissions/{user_emp_no}",
    response_model=ContainerPermissionActionResponse
)
async def update_container_permission(
    container_id: str,
    user_emp_no: str,
    request: ContainerPermissionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """컨테이너 사용자 권한 변경"""
    permission_service = PermissionService(db)
    skip_check = bool(current_user.is_admin)

    if not skip_check:
        has_permission = await permission_service.check_permission(current_user.emp_no, container_id, 'MANAGER')
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 컨테이너의 권한을 변경할 권한이 없습니다."
            )

    permission = await permission_service.get_permission_record(
        user_emp_no=user_emp_no,
        container_id=container_id,
        include_inactive=True
    )

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="권한 정보를 찾을 수 없습니다."
        )

    internal_role = _to_internal_role(request.role_id)

    success = await permission_service.grant_permission(
        user_emp_no=user_emp_no,
        container_id=container_id,
        role_id=internal_role,
        grantor_emp_no=current_user.emp_no,
        granted_by=current_user.emp_no,
        valid_until=request.valid_until,
        skip_permission_check=skip_check
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="권한 변경에 실패했습니다."
        )

    return ContainerPermissionActionResponse(
        success=True,
        message="권한을 변경했습니다."
    )


@router.delete(
    "/{container_id}/permissions/{user_emp_no}",
    response_model=ContainerPermissionActionResponse
)
async def delete_container_permission(
    container_id: str,
    user_emp_no: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """컨테이너 사용자 권한 제거"""
    permission_service = PermissionService(db)
    skip_check = bool(current_user.is_admin)

    if not skip_check:
        has_permission = await permission_service.check_permission(current_user.emp_no, container_id, 'MANAGER')
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 컨테이너의 권한을 제거할 권한이 없습니다."
            )

    success = await permission_service.revoke_permission(
        user_emp_no=user_emp_no,
        container_id=container_id,
        revoker_emp_no=current_user.emp_no,
        skip_permission_check=skip_check
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="권한 정보를 찾을 수 없습니다."
        )

    return ContainerPermissionActionResponse(
        success=True,
        message="권한을 제거했습니다."
    )

# === 컨테이너 삭제 ===
class ContainerDeleteResponse(BaseModel):
    success: bool
    message: str

@router.delete("/{container_id}", response_model=ContainerDeleteResponse)
async def delete_container(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    컨테이너 삭제 (비활성화)
    
    권한 규칙:
    1. 시스템 관리자(ADMIN): 모든 컨테이너 삭제 가능
    2. 지식관리자(MANAGER/OWNER): 관리 범위 내 컨테이너만 삭제 가능
    3. 일반 사용자: 삭제 불가
    """
    try:
        permission_service = PermissionService(db)
        
        # 1. 시스템 관리자 확인
        is_system_admin = await permission_service.is_system_admin(current_user.emp_no)
        
        if not is_system_admin:
            # 2. 지식관리자 권한 확인: 해당 컨테이너에 대한 ADMIN/MANAGER 권한 필요
            container_permission = await permission_service.get_user_permission_level(
                current_user.emp_no, 
                container_id
            )
            
            if container_permission not in ['ADMIN', 'MANAGER', 'OWNER']:
                raise HTTPException(
                    status_code=403,
                    detail=f"컨테이너({container_id})에 대한 관리 권한이 없습니다. "
                           f"현재 권한: {container_permission or 'NONE'}"
                )
            
            logger.info(
                f"지식관리자 {current_user.emp_no}가 컨테이너 {container_id} 삭제 시도 "
                f"(권한: {container_permission})"
            )
        
        from app.models import TbKnowledgeContainers
        from sqlalchemy import update
        
        # 컨테이너 존재 확인
        query = select(TbKnowledgeContainers).where(
            TbKnowledgeContainers.container_id == container_id
        )
        result = await db.execute(query)
        container = result.scalar_one_or_none()
        
        if not container:
            raise HTTPException(
                status_code=404,
                detail="컨테이너를 찾을 수 없습니다."
            )
        
        # 하위 컨테이너 확인
        child_query = select(TbKnowledgeContainers).where(
            TbKnowledgeContainers.parent_container_id == container_id
        )
        child_result = await db.execute(child_query)
        children = child_result.scalars().all()
        
        if children:
            raise HTTPException(
                status_code=400,
                detail="하위 컨테이너가 있는 컨테이너는 삭제할 수 없습니다. 먼저 하위 컨테이너를 삭제하세요."
            )
        
        # 소프트 삭제 (is_active = False)
        stmt = update(TbKnowledgeContainers).where(
            TbKnowledgeContainers.container_id == container_id
        ).values(
            is_active=False,
            last_modified_by=current_user.emp_no
        )
        
        await db.execute(stmt)
        await db.commit()
        
        return ContainerDeleteResponse(
            success=True,
            message="컨테이너가 성공적으로 삭제되었습니다."
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"컨테이너 삭제 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너를 삭제하는 중 오류가 발생했습니다: {str(e)}"
        )


# =============================================================================
# 🎯 사용자용 컨테이너 관리 API (개인 컨테이너 생성/삭제)
# =============================================================================

class UserContainerCreateRequest(BaseModel):
    """사용자 컨테이너 생성 요청"""
    container_name: str
    parent_container_id: Optional[str] = None
    description: Optional[str] = None


class UserContainerCreateResponse(BaseModel):
    """사용자 컨테이너 생성 응답"""
    success: bool
    message: str
    container_id: Optional[str] = None


class UserContainerDeleteResponse(BaseModel):
    """사용자 컨테이너 삭제 응답"""
    success: bool
    message: str


@router.post("/user/create", response_model=UserContainerCreateResponse)
async def create_user_container(
    request: UserContainerCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 개인 컨테이너 생성
    
    - 사용자 자신의 개인 컨테이너를 생성
    - 생성자는 자동으로 OWNER 권한 부여
    - container_id는 "USER_{emp_no}_{random}" 형식으로 자동 생성
    """
    try:
        from app.models import TbKnowledgeContainers, TbUserPermissions
        import uuid
        
        # 컨테이너 ID 생성 (USER_ prefix)
        container_id = f"USER_{current_user.emp_no}_{uuid.uuid4().hex[:8].upper()}"
        
        # 부모 컨테이너 확인 (지정된 경우)
        parent_org_level = 1  # 기본값: 최상위 레벨
        if request.parent_container_id:
            parent_query = select(TbKnowledgeContainers).where(
                and_(
                    TbKnowledgeContainers.container_id == request.parent_container_id,
                    TbKnowledgeContainers.is_active == True
                )
            )
            parent_result = await db.execute(parent_query)
            parent_container = parent_result.scalar_one_or_none()
            
            if not parent_container:
                raise HTTPException(
                    status_code=404,
                    detail="부모 컨테이너를 찾을 수 없습니다."
                )
            
            # 부모의 org_level 가져오기
            parent_org_level = parent_container.org_level if parent_container.org_level else 1
            
            # 부모 컨테이너에 대한 권한 확인
            permission_service = PermissionService(db)
            can_create = await permission_service.check_permission(
                current_user.emp_no,
                request.parent_container_id,
                'EDITOR'
            )
            
            if not can_create:
                raise HTTPException(
                    status_code=403,
                    detail="부모 컨테이너에 하위 컨테이너를 생성할 권한이 없습니다."
                )
        
        # 컨테이너 생성
        new_container = TbKnowledgeContainers(
            container_id=container_id,
            container_name=request.container_name,
            parent_container_id=request.parent_container_id,
            container_type='PERSONAL',  # 개인 컨테이너 타입
            description=request.description or f"{current_user.emp_no}님의 개인 컨테이너",
            access_level='PRIVATE',  # 기본적으로 비공개
            default_permission='NONE',  # 다른 사용자는 기본적으로 접근 불가
            container_owner=current_user.emp_no,
            created_by=current_user.emp_no,
            is_active=True,
            document_count=0,
            org_level=parent_org_level + 1,  # 부모 레벨 + 1
        )
        
        db.add(new_container)
        await db.flush()
        
        # 생성자에게 OWNER 권한 부여
        owner_permission = TbUserPermissions(
            user_emp_no=current_user.emp_no,
            container_id=container_id,
            role_id='OWNER',
            permission_type='DIRECT',
            access_scope='FULL',
            permission_source='SELF_CREATED',
            granted_by=current_user.emp_no,
            granted_date=datetime.utcnow(),
            is_active=True,
            access_count=0  # 🔢 초기 접근 횟수 설정
        )
        db.add(owner_permission)
        
        # 시스템관리자에게 ADMIN 권한 부여 (모든 컨테이너 관리 가능)
        system_admin_permission = TbUserPermissions(
            user_emp_no='ADMIN001',  # 시스템관리자
            container_id=container_id,
            role_id='ADMIN',
            permission_type='DIRECT',
            access_scope='FULL',
            permission_source='SYSTEM_DEFAULT',
            granted_by='SYSTEM',
            granted_date=datetime.utcnow(),
            is_active=True,
            access_count=0
        )
        db.add(system_admin_permission)
        
        await db.commit()
        
        logger.info(f"사용자 컨테이너 생성 완료: {container_id} by {current_user.emp_no}")
        logger.info(f"기본 권한 부여: OWNER({current_user.emp_no}), ADMIN(ADMIN001)")
        
        return UserContainerCreateResponse(
            success=True,
            message="컨테이너가 성공적으로 생성되었습니다.",
            container_id=container_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"사용자 컨테이너 생성 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너를 생성하는 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/user/{container_id}", response_model=UserContainerDeleteResponse)
async def delete_user_container(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 개인 컨테이너 삭제
    
    **제한 사항:**
    - 자신이 생성한 컨테이너만 삭제 가능
    - 컨테이너에 문서가 없어야 함
    - 하위 컨테이너가 없어야 함
    """
    try:
        from app.models import TbKnowledgeContainers, TbFileBssInfo
        
        # 컨테이너 조회
        query = select(TbKnowledgeContainers).where(
            and_(
                TbKnowledgeContainers.container_id == container_id,
                TbKnowledgeContainers.is_active == True
            )
        )
        result = await db.execute(query)
        container = result.scalar_one_or_none()
        
        if not container:
            raise HTTPException(
                status_code=404,
                detail="컨테이너를 찾을 수 없습니다."
            )
        
        # 🔐 권한 확인: 자신이 생성한 컨테이너인지 확인
        if container.created_by != current_user.emp_no and container.container_owner != current_user.emp_no:
            raise HTTPException(
                status_code=403,
                detail="자신이 생성한 컨테이너만 삭제할 수 있습니다."
            )
        
        # 📄 문서 존재 여부 확인
        doc_count_query = select(func.count(TbFileBssInfo.file_bss_info_sno)).where(
            and_(
                TbFileBssInfo.knowledge_container_id == container_id,
                TbFileBssInfo.del_yn != 'Y'
            )
        )
        doc_count_result = await db.execute(doc_count_query)
        document_count = doc_count_result.scalar() or 0
        
        if document_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"컨테이너에 {document_count}개의 문서가 있습니다. 모든 문서를 삭제한 후 다시 시도하세요."
            )
        
        # 📁 하위 컨테이너 확인
        child_query = select(func.count(TbKnowledgeContainers.container_id)).where(
            and_(
                TbKnowledgeContainers.parent_container_id == container_id,
                TbKnowledgeContainers.is_active == True
            )
        )
        child_result = await db.execute(child_query)
        child_count = child_result.scalar() or 0
        
        if child_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"하위 컨테이너가 {child_count}개 있습니다. 먼저 하위 컨테이너를 삭제하세요."
            )
        
        # 🗑️ 소프트 삭제
        from sqlalchemy import update
        stmt = update(TbKnowledgeContainers).where(
            TbKnowledgeContainers.container_id == container_id
        ).values(
            is_active=False,
            last_modified_by=current_user.emp_no,
            last_modified_date=datetime.utcnow()
        )
        
        await db.execute(stmt)
        await db.commit()
        
        logger.info(f"사용자 컨테이너 삭제 완료: {container_id} by {current_user.emp_no}")
        
        return UserContainerDeleteResponse(
            success=True,
            message="컨테이너가 성공적으로 삭제되었습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"사용자 컨테이너 삭제 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너를 삭제하는 중 오류가 발생했습니다: {str(e)}"
        )

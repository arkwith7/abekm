"""
지식 컨테이너 관리 API 엔드포인트
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

# Core dependencies
from app.core.database import get_db
from app.services.auth_service import get_current_user
from app.models import User

# Models
from app.models import TbKnowledgeContainers, TbUserPermissions

# Schemas
from app.schemas.container import (
    ContainerResponse,
    ContainerListResponse,
    ContainerPermissionInfo
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/containers", tags=["containers"])


@router.get("/user-accessible", response_model=ContainerListResponse)
async def get_user_accessible_containers(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    사용자가 접근 가능한 컨테이너 목록 조회
    - 사용자 조직 기반 컨테이너 필터링
    - 권한 레벨별 접근 가능 여부 표시
    """
    try:
        # 모든 활성 컨테이너 조회
        query = select(TbKnowledgeContainers).where(
            TbKnowledgeContainers.is_active == True
        ).order_by(
            TbKnowledgeContainers.hierarchy_level,
            TbKnowledgeContainers.display_order
        )
        
        containers_result = await session.execute(query)
        containers = containers_result.scalars().all()
        
        # 사용자의 컨테이너 권한 확인
        permission_query = select(TbUserPermissions).where(
            TbUserPermissions.user_id == user.id
        )
        
        permissions_result = await session.execute(permission_query)
        user_permissions = permissions_result.scalars().all()
        
        # 컨테이너별 권한 매핑
        permission_map = {
            perm.container_id: perm.permission_level 
            for perm in user_permissions
        }
        
        # 응답 데이터 구성
        container_list = []
        for container in containers:
            permission_level = permission_map.get(container.container_id, "none")
            
            container_info = ContainerResponse(
                container_id=container.container_id,
                container_name=container.container_name,
                description=container.description,
                hierarchy_level=container.hierarchy_level,
                parent_container_id=container.parent_container_id,
                is_active=container.is_active,
                permission_level=permission_level,
                can_read=permission_level in ["read", "write", "admin"],
                can_write=permission_level in ["write", "admin"],
                can_admin=permission_level == "admin"
            )
            container_list.append(container_info)
        
        return ContainerListResponse(
            containers=container_list,
            total_count=len(container_list),
            user_id=user.id,
            user_name=user.username
        )
        
    except Exception as e:
        logger.error(f"컨테이너 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="컨테이너 목록을 조회하는 중 오류가 발생했습니다"
        )


@router.get("/{container_id}/info", response_model=ContainerResponse)
async def get_container_info(
    container_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    특정 컨테이너의 상세 정보 조회
    - 사용자 권한 확인
    - 컨테이너 메타데이터 반환
    """
    try:
        # 특정 컨테이너 정보 조회
        container_query = select(TbKnowledgeContainers).where(
            and_(
                TbKnowledgeContainers.container_id == container_id,
                TbKnowledgeContainers.is_active == True
            )
        )
        
        container_result = await session.execute(container_query)
        container = container_result.scalar_one_or_none()
        
        if not container:
            raise HTTPException(
                status_code=404,
                detail="컨테이너를 찾을 수 없습니다"
            )
        
        # 사용자의 해당 컨테이너 권한 확인
        permission_query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_id == user.id,
                TbUserPermissions.container_id == container_id
            )
        )
        
        permission_result = await session.execute(permission_query)
        permission = permission_result.scalar_one_or_none()
        
        permission_level = permission.permission_level if permission else "none"
        
        # 읽기 권한이 없는 경우 접근 거부
        if permission_level == "none":
            raise HTTPException(
                status_code=403,
                detail="해당 컨테이너에 대한 접근 권한이 없습니다"
            )
        
        return ContainerResponse(
            container_id=container.container_id,
            container_name=container.container_name,
            description=container.description,
            hierarchy_level=container.hierarchy_level,
            parent_container_id=container.parent_container_id,
            is_active=container.is_active,
            permission_level=permission_level,
            can_read=permission_level in ["read", "write", "admin"],
            can_write=permission_level in ["write", "admin"],
            can_admin=permission_level == "admin"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"컨테이너 정보 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="컨테이너 정보를 조회하는 중 오류가 발생했습니다"
        )

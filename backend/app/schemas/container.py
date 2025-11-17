"""
컨테이너 관련 스키마 정의
"""

from typing import List, Optional
from pydantic import BaseModel


class ContainerPermissionInfo(BaseModel):
    """컨테이너 권한 정보"""
    container_id: str
    container_name: str
    container_type: str  # ROOT, DIVISION, DEPARTMENT, TEAM
    hierarchy_level: int
    hierarchy_path: str
    access_level: str  # PUBLIC, RESTRICTED, TEAM_ONLY, PRIVATE
    parent_container_id: Optional[str] = None
    display_order: int
    can_upload: bool
    user_permission: str  # OWNER, MEMBER, VIEWER, NONE


class ContainerResponse(BaseModel):
    """단일 컨테이너 응답"""
    success: bool
    container: ContainerPermissionInfo


class ContainerListResponse(BaseModel):
    """컨테이너 목록 응답"""
    success: bool
    containers: List[ContainerPermissionInfo]
    total_count: int


class ContainerCreateRequest(BaseModel):
    """컨테이너 생성 요청"""
    container_name: str
    container_description: Optional[str] = None
    container_type: str
    parent_container_id: Optional[str] = None
    access_level: str = 'RESTRICTED'
    sap_org_code: Optional[str] = None


class ContainerUpdateRequest(BaseModel):
    """컨테이너 수정 요청"""
    container_name: Optional[str] = None
    container_description: Optional[str] = None
    access_level: Optional[str] = None
    is_active: Optional[bool] = None

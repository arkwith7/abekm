"""
WKMS 지식 컨테이너 관리 API
컨테이너 생성, 조회, 수정, 계층 구조 관리 기능 제공
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.container_service import ContainerService
from app.core.dependencies import get_current_user
from datetime import datetime

router = APIRouter(tags=["Knowledge Containers"])
security = HTTPBearer()


# Pydantic 모델들
class CreateContainerRequest(BaseModel):
    container_id: str = Field(..., description="컨테이너 ID (고유)")
    container_name: str = Field(..., description="컨테이너 명")
    parent_container_id: Optional[str] = Field(None, description="상위 컨테이너 ID")
    container_type: str = Field("department", description="컨테이너 유형 (company/division/department/team)")
    description: Optional[str] = Field(None, description="컨테이너 설명")
    knowledge_category: Optional[str] = Field(None, description="주요 지식 분야")
    access_level: str = Field("internal", description="접근 수준 (public/internal/restricted/confidential)")
    default_permission: str = Field("VIEWER", description="기본 권한 레벨")
    sap_org_code: Optional[str] = Field(None, description="SAP 조직 코드")
    sap_cost_center: Optional[str] = Field(None, description="SAP 코스트 센터")


class UpdateContainerRequest(BaseModel):
    container_name: Optional[str] = Field(None, description="컨테이너 명")
    description: Optional[str] = Field(None, description="컨테이너 설명")
    knowledge_category: Optional[str] = Field(None, description="주요 지식 분야")
    access_level: Optional[str] = Field(None, description="접근 수준")
    default_permission: Optional[str] = Field(None, description="기본 권한 레벨")
    inherit_parent_permissions: Optional[bool] = Field(None, description="상위 컨테이너 권한 상속 여부")
    permission_inheritance_type: Optional[str] = Field(None, description="권한 상속 방식")
    auto_assign_by_org: Optional[bool] = Field(None, description="조직도 기반 자동 권한 할당")
    require_approval_for_access: Optional[bool] = Field(None, description="접근 시 승인 필요")
    approval_workflow_enabled: Optional[bool] = Field(None, description="권한 요청 승인 워크플로우")
    tags: Optional[List[str]] = Field(None, description="컨테이너 태그")


class ContainerHierarchyResponse(BaseModel):
    container_id: str
    container_name: str
    container_type: str
    description: Optional[str]
    knowledge_category: Optional[str]
    access_level: str
    org_level: int
    org_path: str
    parent_container_id: Optional[str]
    document_count: int
    user_count: int
    permission_level: str
    children: List['ContainerHierarchyResponse'] = []


class ContainerDetailsResponse(BaseModel):
    container_id: str
    container_name: str
    container_type: str
    description: Optional[str]
    knowledge_category: Optional[str]
    access_level: str
    default_permission: str
    org_level: int
    org_path: str
    parent_container_id: Optional[str]
    sap_org_code: Optional[str]
    sap_cost_center: Optional[str]
    inherit_parent_permissions: bool
    permission_inheritance_type: str
    auto_assign_by_org: bool
    require_approval_for_access: bool
    approval_workflow_enabled: bool
    document_count: int
    total_knowledge_size: int
    user_count: int
    permission_request_count: int
    last_knowledge_update: Optional[datetime]
    last_permission_update: Optional[datetime]
    created_date: datetime
    user_permission_level: Optional[str]
    owner_info: Optional[Dict[str, Any]]
    categories: List[Dict[str, Any]]
    tags: Optional[List[str]]


class ContainerStatisticsResponse(BaseModel):
    container_id: str
    document_count: int
    total_knowledge_size: int
    user_count: int
    permission_request_count: int
    last_knowledge_update: Optional[datetime]
    last_permission_update: Optional[datetime]
    permission_distribution: Dict[str, int]
    created_date: datetime


class AssignCategoryRequest(BaseModel):
    category_id: int = Field(..., description="카테고리 ID")
    is_primary: bool = Field(False, description="주 카테고리 여부")
    relevance_score: int = Field(5, description="관련도 점수 (1-10)")


# API 엔드포인트들
@router.get(
    "/",
    response_model=List[ContainerHierarchyResponse],
    summary="컨테이너 목록 조회",
    description="사용자가 접근 가능한 모든 컨테이너 목록을 계층 구조로 조회합니다."
)
async def get_containers(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 목록 조회 (루트 경로)"""
    try:
        container_service = ContainerService(session)
        
        hierarchy = await container_service.get_container_hierarchy(
            user_emp_no=current_user.emp_no,
            root_container_id=None
        )
        
        return [
            ContainerHierarchyResponse(**container)
            for container in hierarchy
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 목록 조회 실패: {str(e)}"
        )


@router.post(
    "/create",
    summary="컨테이너 생성",
    description="새로운 지식 컨테이너를 생성합니다."
)
async def create_container(
    request: CreateContainerRequest,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 생성"""
    try:
        container_service = ContainerService(session)
        
        success = await container_service.create_container(
            creator_emp_no=current_user.emp_no,
            container_id=request.container_id,
            container_name=request.container_name,
            parent_container_id=request.parent_container_id,
            container_type=request.container_type,
            description=request.description,
            knowledge_category=request.knowledge_category,
            access_level=request.access_level,
            default_permission=request.default_permission,
            sap_org_code=request.sap_org_code,
            sap_cost_center=request.sap_cost_center
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="컨테이너 생성에 실패했습니다"
            )
        
        return {
            "message": "컨테이너가 성공적으로 생성되었습니다",
            "container_id": request.container_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 생성 실패: {str(e)}"
        )


@router.get(
    "/hierarchy",
    response_model=List[ContainerHierarchyResponse],
    summary="컨테이너 계층 구조",
    description="사용자가 접근 가능한 컨테이너들의 계층 구조를 조회합니다."
)
async def get_container_hierarchy(
    root_container_id: Optional[str] = Query(None, description="루트 컨테이너 ID (전체 조회시 생략)"),
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 계층 구조 조회"""
    try:
        container_service = ContainerService(session)
        
        hierarchy = await container_service.get_container_hierarchy(
            user_emp_no=current_user.emp_no,
            root_container_id=root_container_id
        )
        
        return [
            ContainerHierarchyResponse(**container)
            for container in hierarchy
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 계층 조회 실패: {str(e)}"
        )


@router.get(
    "/{container_id}",
    response_model=ContainerDetailsResponse,
    summary="컨테이너 상세 정보",
    description="특정 컨테이너의 상세 정보를 조회합니다."
)
async def get_container_details(
    container_id: str,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 상세 정보 조회"""
    try:
        container_service = ContainerService(session)
        
        details = await container_service.get_container_details(
            user_emp_no=current_user.emp_no,
            container_id=container_id
        )
        
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="컨테이너를 찾을 수 없거나 접근 권한이 없습니다"
            )
        
        return ContainerDetailsResponse(**details)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 상세 조회 실패: {str(e)}"
        )


@router.put(
    "/{container_id}",
    summary="컨테이너 정보 수정",
    description="컨테이너 정보를 수정합니다."
)
async def update_container(
    container_id: str,
    request: UpdateContainerRequest,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 정보 수정"""
    try:
        container_service = ContainerService(session)
        
        # None이 아닌 값들만 업데이트 딕셔너리에 포함
        updates = {
            k: v for k, v in request.dict().items() 
            if v is not None
        }
        
        if not updates:
            return {"message": "수정할 내용이 없습니다"}
        
        success = await container_service.update_container(
            user_emp_no=current_user.emp_no,
            container_id=container_id,
            updates=updates
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="컨테이너 수정에 실패했습니다"
            )
        
        return {"message": "컨테이너 정보가 성공적으로 수정되었습니다"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 수정 실패: {str(e)}"
        )


@router.get(
    "/{container_id}/statistics",
    response_model=ContainerStatisticsResponse,
    summary="컨테이너 통계",
    description="컨테이너의 통계 정보를 조회합니다."
)
async def get_container_statistics(
    container_id: str,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 통계 조회"""
    try:
        container_service = ContainerService(session)
        
        statistics = await container_service.get_container_statistics(
            user_emp_no=current_user.emp_no,
            container_id=container_id
        )
        
        if not statistics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="컨테이너를 찾을 수 없거나 접근 권한이 없습니다"
            )
        
        return ContainerStatisticsResponse(**statistics)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 통계 조회 실패: {str(e)}"
        )


@router.post(
    "/{container_id}/categories",
    summary="컨테이너 카테고리 할당",
    description="컨테이너에 카테고리를 할당합니다."
)
async def assign_category(
    container_id: str,
    request: AssignCategoryRequest,
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 카테고리 할당"""
    try:
        container_service = ContainerService(session)
        
        success = await container_service.assign_category(
            user_emp_no=current_user.emp_no,
            container_id=container_id,
            category_id=request.category_id,
            is_primary=request.is_primary,
            relevance_score=request.relevance_score
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="카테고리 할당에 실패했습니다"
            )
        
        return {"message": "카테고리가 성공적으로 할당되었습니다"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"카테고리 할당 실패: {str(e)}"
        )


@router.get(
    "/search",
    response_model=List[ContainerHierarchyResponse],
    summary="컨테이너 검색",
    description="컨테이너를 검색합니다."
)
async def search_containers(
    query: str = Query(..., description="검색 쿼리"),
    container_type: Optional[str] = Query(None, description="컨테이너 유형 필터"),
    access_level: Optional[str] = Query(None, description="접근 수준 필터"),
    limit: int = Query(50, description="최대 결과 수"),
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """컨테이너 검색"""
    try:
        container_service = ContainerService(session)
        
        # 기본적으로 접근 가능한 컨테이너들을 가져온 후 필터링
        hierarchy = await container_service.get_container_hierarchy(
            user_emp_no=current_user.emp_no
        )
        
        # 플래튼하게 변환
        def flatten_hierarchy(containers):
            result = []
            for container in containers:
                result.append(container)
                if container.get('children'):
                    result.extend(flatten_hierarchy(container['children']))
            return result
        
        all_containers = flatten_hierarchy(hierarchy)
        
        # 검색 필터링
        filtered_containers = []
        query_lower = query.lower()
        
        for container in all_containers:
            # 이름 또는 설명에 쿼리가 포함되어 있는지 확인
            if (query_lower in container['container_name'].lower() or
                (container.get('description') and query_lower in container['description'].lower())):
                
                # 추가 필터 적용
                if container_type and container['container_type'] != container_type:
                    continue
                if access_level and container['access_level'] != access_level:
                    continue
                
                # children 제거 (검색 결과에서는 계층 구조 제거)
                container_copy = container.copy()
                container_copy['children'] = []
                filtered_containers.append(container_copy)
        
        # 결과 제한
        filtered_containers = filtered_containers[:limit]
        
        return [
            ContainerHierarchyResponse(**container)
            for container in filtered_containers
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨테이너 검색 실패: {str(e)}"
        )


# Self-referencing model update
ContainerHierarchyResponse.model_rebuild()

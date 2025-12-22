"""
특허 수집 API
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.services.patent.collection_service import PatentCollectionService
from app.tasks.patent_collection_tasks import collect_patents_from_kipris

router = APIRouter(prefix="/api/v1/patent-collection", tags=["Patent Collection"])


# ---------------------------
# Pydantic 스키마
# ---------------------------
class PatentSearchConfig(BaseModel):
    ipc_codes: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    applicants: Optional[List[str]] = None


class PatentCollectionSettingCreate(BaseModel):
    container_id: str
    search_config: PatentSearchConfig
    max_results: int = 100
    auto_download_pdf: bool = False
    auto_generate_embeddings: bool = True
    schedule_type: str = "manual"
    schedule_config: Optional[Dict[str, Any]] = None


class PatentCollectionSettingResponse(BaseModel):
    setting_id: int
    user_emp_no: str
    container_id: str
    search_config: Dict[str, Any]
    max_results: int
    auto_download_pdf: bool
    auto_generate_embeddings: bool
    schedule_type: str
    schedule_config: Optional[Dict[str, Any]]
    is_active: bool
    last_collection_date: Optional[str]


class PatentCollectionStartRequest(BaseModel):
    setting_id: int


class PatentCollectionTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class PatentCollectionStatusResponse(BaseModel):
    task_id: str
    status: str
    progress_current: int
    progress_total: int
    collected_count: int
    error_count: int


# ---------------------------
# API 엔드포인트
# ---------------------------
@router.post("/settings", response_model=PatentCollectionSettingResponse)
async def create_patent_collection_setting(
    data: PatentCollectionSettingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PatentCollectionService(db)
    setting = await service.create_collection_setting(
        user_emp_no=current_user.emp_no,
        container_id=data.container_id,
        search_config=data.search_config.dict(),
        max_results=data.max_results,
        auto_download_pdf=data.auto_download_pdf,
        auto_generate_embeddings=data.auto_generate_embeddings,
        schedule_type=data.schedule_type,
        schedule_config=data.schedule_config,
    )
    return PatentCollectionSettingResponse(
        setting_id=setting.setting_id,
        user_emp_no=setting.user_emp_no,
        container_id=setting.container_id,
        search_config=setting.search_config,
        max_results=setting.max_results,
        auto_download_pdf=setting.auto_download_pdf,
        auto_generate_embeddings=setting.auto_generate_embeddings,
        schedule_type=setting.schedule_type,
        schedule_config=setting.schedule_config,
        is_active=setting.is_active,
        last_collection_date=setting.last_collection_date.isoformat() if setting.last_collection_date else None,
    )


@router.get("/settings", response_model=List[PatentCollectionSettingResponse])
async def get_patent_collection_settings(
    container_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PatentCollectionService(db)
    settings = await service.get_user_settings(current_user.emp_no, container_id)
    return [
        PatentCollectionSettingResponse(
            setting_id=s.setting_id,
            user_emp_no=s.user_emp_no,
            container_id=s.container_id,
            search_config=s.search_config,
            max_results=s.max_results,
            auto_download_pdf=s.auto_download_pdf,
            auto_generate_embeddings=s.auto_generate_embeddings,
            schedule_type=s.schedule_type,
            schedule_config=s.schedule_config,
            is_active=s.is_active,
            last_collection_date=s.last_collection_date.isoformat() if s.last_collection_date else None,
        )
        for s in settings
    ]


@router.post("/start", response_model=PatentCollectionTaskResponse)
async def start_patent_collection(
    data: PatentCollectionStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PatentCollectionService(db)
    settings = await service.get_user_settings(current_user.emp_no)
    setting = next((s for s in settings if s.setting_id == data.setting_id), None)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="특허 수집 설정을 찾을 수 없습니다",
        )

    task = collect_patents_from_kipris.delay(
        setting_id=setting.setting_id,
        user_emp_no=current_user.emp_no,
        container_id=setting.container_id,
        search_config=setting.search_config,
        max_results=setting.max_results,
        auto_download_pdf=setting.auto_download_pdf,
        auto_generate_embeddings=setting.auto_generate_embeddings,
    )

    return PatentCollectionTaskResponse(
        task_id=task.id,
        status="started",
        message="특허 수집이 백그라운드에서 시작되었습니다",
    )


@router.get("/status/{task_id}", response_model=PatentCollectionStatusResponse)
async def get_patent_collection_status(task_id: str):
    from celery.result import AsyncResult

    task_result = AsyncResult(task_id)

    status_map = {
        "PENDING": "pending",
        "PROGRESS": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
    }
    status_str = status_map.get(task_result.state, "pending")
    current = 0
    total = 0
    collected = 0
    errors = 0

    if task_result.state == "PROGRESS":
        info = task_result.info or {}
        current = info.get("current", 0)
        total = info.get("total", 0)
        collected = info.get("collected", 0)
        errors = info.get("errors", 0)
    elif task_result.state == "SUCCESS":
        result = task_result.result or {}
        current = result.get("total", 0)
        total = result.get("total", 0)
        collected = result.get("collected", 0)
        errors = result.get("errors", 0)

    return PatentCollectionStatusResponse(
        task_id=task_id,
        status=status_str,
        progress_current=current,
        progress_total=total,
        collected_count=collected,
        error_count=errors,
    )

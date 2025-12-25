"""
시스템 관리자 API 엔드포인트
관리자 대시보드 통계, 감사 로그 조회 등 관리 기능 제공
"""
import logging
import os
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models import User, TbFileBssInfo, TbChatSessions, TbKnowledgeContainers, VsDocContentsChunks
from app.models.auth.permission_models import TbPermissionAuditLog, TbUserPermissions
from app.services.admin.ai_usage_service import AIUsageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["🔧 System Admin"])


# ==================== Response Models ====================

class AdminDashboardStats(BaseModel):
    """관리자 대시보드 통계"""
    total_users: int
    active_users: int
    total_documents: int
    total_containers: int
    total_chat_sessions: int
    storage_used_bytes: int
    storage_used_display: str


class AuditLogItem(BaseModel):
    """감사 로그 항목"""
    audit_id: int
    timestamp: str
    user_emp_no: str
    user_name: Optional[str]
    target_user_emp_no: Optional[str]
    target_user_name: Optional[str]
    container_id: Optional[str]
    container_name: Optional[str]
    action_type: str
    resource_type: str
    old_permission: Optional[str]
    new_permission: Optional[str]
    action_result: str
    ip_address: Optional[str]
    failure_reason: Optional[str]


class AuditLogResponse(BaseModel):
    """감사 로그 조회 응답"""
    success: bool
    logs: List[AuditLogItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class StorageInfo(BaseModel):
    """저장소 정보"""
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_display: str
    total_display: str
    usage_percent: float


# ==================== Helper Functions ====================

def format_bytes(bytes_val: int) -> str:
    """바이트를 읽기 쉬운 형식으로 변환"""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def get_directory_size(path: str) -> int:
    """디렉토리의 총 크기를 바이트 단위로 계산"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
    except (OSError, PermissionError):
        pass
    return total_size


# ==================== Endpoints ====================

@router.get("/dashboard/stats", summary="관리자 대시보드 통계")
async def get_admin_dashboard_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자 대시보드 핵심 통계
    - 총 사용자 수 / 활성 사용자 수
    - 총 문서 수
    - 총 컨테이너 수
    - 총 대화 세션 수
    - 저장소 사용량
    """
    try:
        logger.info(f"📊 관리자 대시보드 통계 요청 - 사용자: {current_user.username}")
        
        # 1. 총 사용자 수
        total_users_result = await db.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0
        
        # 2. 활성 사용자 수
        active_users_result = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users_result.scalar() or 0
        
        # 3. 총 문서 수
        total_docs_result = await db.execute(
            select(func.count(TbFileBssInfo.file_bss_info_sno)).where(
                TbFileBssInfo.del_yn == 'N'
            )
        )
        total_documents = total_docs_result.scalar() or 0
        
        # 4. 총 컨테이너 수
        total_containers_result = await db.execute(
            select(func.count(TbKnowledgeContainers.container_id)).where(
                TbKnowledgeContainers.is_active == True
            )
        )
        total_containers = total_containers_result.scalar() or 0
        
        # 5. 총 대화 세션 수
        total_sessions_result = await db.execute(
            select(func.count(TbChatSessions.session_id))
        )
        total_chat_sessions = total_sessions_result.scalar() or 0
        
        # 6. 저장소 사용량 (uploads 디렉토리)
        from app.core.config import settings
        upload_dir = str(settings.resolved_upload_dir)
        storage_used = get_directory_size(upload_dir)
        
        logger.info(f"✅ 관리자 대시보드 통계 조회 완료")
        
        return {
            "success": True,
            "data": {
                "total_users": int(total_users),
                "active_users": int(active_users),
                "total_documents": int(total_documents),
                "total_containers": int(total_containers),
                "total_chat_sessions": int(total_chat_sessions),
                "storage_used_bytes": storage_used,
                "storage_used_display": format_bytes(storage_used)
            }
        }
        
    except Exception as e:
        logger.error(f"관리자 대시보드 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/audit-logs", summary="감사 로그 조회")
async def get_audit_logs(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    category: Optional[str] = Query(None, description="카테고리 필터 (permission, access, system)"),
    result: Optional[str] = Query(None, description="결과 필터 (success, failure)"),
    search: Optional[str] = Query(None, description="검색어"),
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    권한 감사 로그 조회
    - 권한 변경 이력
    - 접근 시도 기록
    - 페이징 및 필터링 지원
    """
    try:
        logger.info(f"📋 감사 로그 조회 - 페이지: {page}, 사용자: {current_user.username}")
        
        # 기간 필터
        start_date = datetime.now() - timedelta(days=days)
        
        # 기본 쿼리
        base_query = (
            select(
                TbPermissionAuditLog,
                TbKnowledgeContainers.container_name
            )
            .outerjoin(
                TbKnowledgeContainers,
                TbPermissionAuditLog.container_id == TbKnowledgeContainers.container_id
            )
            .where(TbPermissionAuditLog.created_date >= start_date)
        )
        
        # 카테고리 필터
        if category:
            category_map = {
                'permission': ['grant', 'revoke', 'modify', 'approve', 'reject'],
                'access': ['access', 'download', 'view'],
                'system': ['login', 'logout', 'config_change']
            }
            if category in category_map:
                base_query = base_query.where(
                    TbPermissionAuditLog.action_type.in_(category_map[category])
                )
        
        # 결과 필터
        if result:
            base_query = base_query.where(TbPermissionAuditLog.action_result == result)
        
        # 검색어 필터
        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.where(
                or_(
                    TbPermissionAuditLog.user_emp_no.ilike(search_pattern),
                    TbPermissionAuditLog.action_type.ilike(search_pattern),
                    TbKnowledgeContainers.container_name.ilike(search_pattern)
                )
            )
        
        # 전체 개수 조회
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 페이징 적용
        offset = (page - 1) * page_size
        paginated_query = (
            base_query
            .order_by(desc(TbPermissionAuditLog.created_date))
            .offset(offset)
            .limit(page_size)
        )
        
        result_data = await db.execute(paginated_query)
        rows = result_data.all()
        
        # 응답 데이터 구성
        logs = []
        for audit_log, container_name in rows:
            logs.append({
                "audit_id": audit_log.audit_id,
                "timestamp": audit_log.created_date.isoformat() if audit_log.created_date else None,
                "user_emp_no": audit_log.user_emp_no,
                "user_name": None,  # TODO: JOIN with user table if needed
                "target_user_emp_no": audit_log.target_user_emp_no,
                "target_user_name": None,
                "container_id": audit_log.container_id,
                "container_name": container_name,
                "action_type": audit_log.action_type,
                "resource_type": audit_log.resource_type,
                "old_permission": audit_log.old_permission,
                "new_permission": audit_log.new_permission,
                "action_result": audit_log.action_result,
                "ip_address": audit_log.ip_address,
                "failure_reason": audit_log.failure_reason
            })
        
        total_pages = (total + page_size - 1) // page_size
        
        logger.info(f"✅ 감사 로그 조회 완료 - {len(logs)}건 반환 (총 {total}건)")
        
        return {
            "success": True,
            "logs": logs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
        
    except Exception as e:
        logger.error(f"감사 로그 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"감사 로그 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/audit-logs/stats", summary="감사 로그 통계")
async def get_audit_log_stats(
    days: int = Query(30, ge=1, le=365, description="통계 기간 (일)"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    감사 로그 통계 요약
    - 성공/실패 건수
    - 작업 유형별 건수
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        # 전체 건수
        total_result = await db.execute(
            select(func.count(TbPermissionAuditLog.audit_id))
            .where(TbPermissionAuditLog.created_date >= start_date)
        )
        total = total_result.scalar() or 0
        
        # 성공 건수
        success_result = await db.execute(
            select(func.count(TbPermissionAuditLog.audit_id))
            .where(
                and_(
                    TbPermissionAuditLog.created_date >= start_date,
                    TbPermissionAuditLog.action_result == 'success'
                )
            )
        )
        success_count = success_result.scalar() or 0
        
        # 실패 건수
        failure_result = await db.execute(
            select(func.count(TbPermissionAuditLog.audit_id))
            .where(
                and_(
                    TbPermissionAuditLog.created_date >= start_date,
                    TbPermissionAuditLog.action_result == 'failure'
                )
            )
        )
        failure_count = failure_result.scalar() or 0
        
        return {
            "success": True,
            "period_days": days,
            "stats": {
                "total": total,
                "success": success_count,
                "failure": failure_count,
                "warning": total - success_count - failure_count
            }
        }
        
    except Exception as e:
        logger.error(f"감사 로그 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/storage", summary="저장소 사용량 조회")
async def get_storage_info(
    current_user: User = Depends(require_admin)
):
    """
    저장소 사용량 정보
    - 업로드 디렉토리 사용량
    - 디스크 공간 정보
    """
    try:
        from app.core.config import settings
        import shutil
        
        upload_dir = str(settings.resolved_upload_dir)
        
        # 업로드 디렉토리 사용량
        used_bytes = get_directory_size(upload_dir)
        
        # 디스크 전체 용량 (upload_dir이 있는 파티션)
        try:
            disk_usage = shutil.disk_usage(upload_dir)
            total_bytes = disk_usage.total
            free_bytes = disk_usage.free
        except Exception:
            total_bytes = 0
            free_bytes = 0
        
        usage_percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
        
        return {
            "success": True,
            "storage": {
                "upload_dir": upload_dir,
                "used_bytes": used_bytes,
                "used_display": format_bytes(used_bytes),
                "total_bytes": total_bytes,
                "total_display": format_bytes(total_bytes),
                "free_bytes": free_bytes,
                "free_display": format_bytes(free_bytes),
                "usage_percent": round(usage_percent, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"저장소 정보 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"저장소 정보 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/health", summary="시스템 헬스체크")
async def admin_health_check(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자용 상세 시스템 헬스체크
    - 데이터베이스 연결 상태
    - 서비스 상태
    """
    try:
        health_status = {
            "database": "healthy",
            "api": "healthy",
            "storage": "healthy"
        }
        
        # 데이터베이스 연결 확인
        try:
            await db.execute(select(func.now()))
        except Exception as db_error:
            health_status["database"] = "unhealthy"
            logger.error(f"Database health check failed: {db_error}")
        
        # 저장소 확인
        from app.core.config import settings
        upload_dir = str(settings.resolved_upload_dir)
        if not os.path.exists(upload_dir) or not os.access(upload_dir, os.W_OK):
            health_status["storage"] = "unhealthy"
        
        overall_status = "healthy" if all(v == "healthy" for v in health_status.values()) else "unhealthy"
        
        return {
            "status": overall_status,
            "services": health_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ==================== AI Usage Endpoints ====================

@router.get("/ai/usage/summary", summary="AI 사용량 요약")
async def get_ai_usage_summary(
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    AI 사용량 요약 통계
    - 총 요청 수, 토큰 수, 비용
    - 제공자별, 작업별 통계
    """
    try:
        service = AIUsageService(db)
        summary = await service.get_usage_summary(days=days)
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"AI 사용량 요약 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 사용량 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/ai/usage/daily", summary="일별 AI 사용량")
async def get_ai_daily_usage(
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    일별 AI 사용량 통계 (차트용)
    """
    try:
        service = AIUsageService(db)
        daily_usage = await service.get_daily_usage(days=days)
        
        return {
            "success": True,
            "data": daily_usage
        }
        
    except Exception as e:
        logger.error(f"일별 AI 사용량 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/ai/usage/top-users", summary="상위 AI 사용자")
async def get_ai_top_users(
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    limit: int = Query(10, ge=1, le=100, description="조회 개수"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    AI 사용량 상위 사용자 목록
    """
    try:
        service = AIUsageService(db)
        top_users = await service.get_top_users(days=days, limit=limit)
        
        return {
            "success": True,
            "data": top_users
        }
        
    except Exception as e:
        logger.error(f"상위 AI 사용자 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/ai/models", summary="AI 모델 설정 목록")
async def get_ai_model_configs(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    등록된 AI 모델 및 비용 설정 목록
    """
    try:
        service = AIUsageService(db)
        models = await service.get_model_configs()
        
        return {
            "success": True,
            "data": models
        }
        
    except Exception as e:
        logger.error(f"AI 모델 설정 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/ai/usage/test-data", summary="테스트 데이터 생성 (개발용)")
async def create_test_ai_usage_data(
    count: int = Query(10, ge=1, le=100, description="생성할 테스트 데이터 개수"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    AI 사용량 테스트 데이터 생성 (개발/테스트 환경용)
    """
    import random
    
    try:
        service = AIUsageService(db)
        
        # 테스트 데이터 생성
        providers = ['bedrock', 'azure_openai', 'openai']
        models = {
            'bedrock': ['anthropic.claude-3-5-sonnet-20241022-v2:0', 'amazon.titan-embed-text-v2:0'],
            'azure_openai': ['gpt-4o', 'gpt-4o-mini'],
            'openai': ['gpt-4o', 'text-embedding-3-small']
        }
        operations = ['chat', 'embedding', 'summarize', 'search']
        
        created = []
        for _ in range(count):
            provider = random.choice(providers)
            model = random.choice(models[provider])
            operation = random.choice(operations)
            
            input_tokens = random.randint(100, 5000) if operation != 'embedding' else random.randint(100, 1000)
            output_tokens = random.randint(50, 2000) if operation != 'embedding' else 0
            
            log = await service.log_usage(
                provider=provider,
                model=model,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=random.randint(100, 5000),
                success=random.random() > 0.05,  # 95% 성공률
                user_id=current_user.id,
                user_emp_no=current_user.emp_no,
                session_id=f"test-session-{random.randint(1000, 9999)}"
            )
            created.append(log.id)
        
        return {
            "success": True,
            "message": f"{count}개의 테스트 데이터 생성 완료",
            "created_ids": created
        }
        
    except Exception as e:
        logger.error(f"테스트 데이터 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"테스트 데이터 생성 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== Knowledge Base Management Endpoints ====================

@router.get("/documents/status", summary="문서 처리 현황")
async def get_documents_status(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    문서 처리 상태별 현황 조회
    - pending: 대기 중
    - processing: 처리 중
    - completed: 완료
    - failed: 실패
    """
    try:
        # 전체 문서 수
        total_result = await db.execute(
            select(func.count()).select_from(TbFileBssInfo).where(TbFileBssInfo.del_yn == 'N')
        )
        total_documents = total_result.scalar() or 0
        
        # 처리 상태별 카운트
        status_result = await db.execute(
            select(
                TbFileBssInfo.processing_status,
                func.count(TbFileBssInfo.file_bss_info_sno).label('count')
            )
            .where(TbFileBssInfo.del_yn == 'N')
            .group_by(TbFileBssInfo.processing_status)
        )
        status_counts = {row.processing_status or 'unknown': row.count for row in status_result.all()}
        
        # 문서 유형별 카운트
        type_result = await db.execute(
            select(
                TbFileBssInfo.document_type,
                func.count(TbFileBssInfo.file_bss_info_sno).label('count')
            )
            .where(TbFileBssInfo.del_yn == 'N')
            .group_by(TbFileBssInfo.document_type)
        )
        type_counts = {row.document_type or 'general': row.count for row in type_result.all()}
        
        # 최근 실패한 문서 목록 (최근 10건)
        failed_result = await db.execute(
            select(
                TbFileBssInfo.file_bss_info_sno,
                TbFileBssInfo.file_lgc_nm,
                TbFileBssInfo.knowledge_container_id,
                TbFileBssInfo.processing_error,
                TbFileBssInfo.processing_started_at,
                TbFileBssInfo.created_date
            )
            .where(
                and_(
                    TbFileBssInfo.del_yn == 'N',
                    TbFileBssInfo.processing_status == 'failed'
                )
            )
            .order_by(desc(TbFileBssInfo.created_date))
            .limit(10)
        )
        failed_documents = [
            {
                "file_id": row.file_bss_info_sno,
                "file_name": row.file_lgc_nm,
                "container_id": row.knowledge_container_id,
                "error": row.processing_error,
                "started_at": row.processing_started_at.isoformat() if row.processing_started_at else None,
                "created_at": row.created_date.isoformat() if row.created_date else None
            }
            for row in failed_result.all()
        ]
        
        # 최근 처리 완료 문서 (최근 10건)
        recent_result = await db.execute(
            select(
                TbFileBssInfo.file_bss_info_sno,
                TbFileBssInfo.file_lgc_nm,
                TbFileBssInfo.knowledge_container_id,
                TbFileBssInfo.chunk_count,
                TbFileBssInfo.processing_completed_at
            )
            .where(
                and_(
                    TbFileBssInfo.del_yn == 'N',
                    TbFileBssInfo.processing_status == 'completed'
                )
            )
            .order_by(desc(TbFileBssInfo.processing_completed_at))
            .limit(10)
        )
        recent_completed = [
            {
                "file_id": row.file_bss_info_sno,
                "file_name": row.file_lgc_nm,
                "container_id": row.knowledge_container_id,
                "chunk_count": row.chunk_count or 0,
                "completed_at": row.processing_completed_at.isoformat() if row.processing_completed_at else None
            }
            for row in recent_result.all()
        ]
        
        return {
            "success": True,
            "data": {
                "total_documents": total_documents,
                "by_status": {
                    "pending": status_counts.get('pending', 0),
                    "processing": status_counts.get('processing', 0),
                    "completed": status_counts.get('completed', 0),
                    "failed": status_counts.get('failed', 0)
                },
                "by_type": type_counts,
                "failed_documents": failed_documents,
                "recent_completed": recent_completed
            }
        }
        
    except Exception as e:
        logger.error(f"문서 처리 현황 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/documents/{file_id}/reprocess", summary="문서 재처리")
async def reprocess_document(
    file_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    실패한 문서 재처리 요청
    - 처리 상태를 'pending'으로 리셋
    - 백그라운드 워커가 다시 처리
    """
    try:
        # 문서 조회
        result = await db.execute(
            select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == file_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"문서를 찾을 수 없습니다: {file_id}"
            )
        
        if document.del_yn == 'Y':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="삭제된 문서는 재처리할 수 없습니다"
            )
        
        # 처리 상태 리셋
        document.processing_status = 'pending'
        document.processing_error = None
        document.processing_started_at = None
        document.processing_completed_at = None
        
        await db.commit()
        
        logger.info(f"✅ 문서 재처리 요청: file_id={file_id}, user={current_user.emp_no}")
        
        return {
            "success": True,
            "message": f"문서 재처리가 요청되었습니다",
            "file_id": file_id,
            "file_name": document.file_lgc_nm
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 재처리 요청 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"재처리 요청 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/vector-db/stats", summary="벡터 DB 통계")
async def get_vector_db_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    벡터 데이터베이스 통계 조회
    - 총 청크 수
    - 임베딩 제공자별 통계
    - 컨테이너별 청크 분포
    """
    try:
        # 전체 청크 수
        total_result = await db.execute(
            select(func.count()).select_from(VsDocContentsChunks).where(VsDocContentsChunks.del_yn == 'N')
        )
        total_chunks = total_result.scalar() or 0
        
        # 임베딩 제공자별 통계
        provider_result = await db.execute(
            select(
                VsDocContentsChunks.embedding_provider,
                func.count(VsDocContentsChunks.chunk_sno).label('count')
            )
            .where(VsDocContentsChunks.del_yn == 'N')
            .group_by(VsDocContentsChunks.embedding_provider)
        )
        by_provider = {row.embedding_provider or 'legacy': row.count for row in provider_result.all()}
        
        # 컨테이너별 청크 수
        container_result = await db.execute(
            select(
                VsDocContentsChunks.knowledge_container_id,
                func.count(VsDocContentsChunks.chunk_sno).label('chunk_count'),
                func.count(func.distinct(VsDocContentsChunks.file_bss_info_sno)).label('doc_count')
            )
            .where(VsDocContentsChunks.del_yn == 'N')
            .group_by(VsDocContentsChunks.knowledge_container_id)
            .order_by(desc(func.count(VsDocContentsChunks.chunk_sno)))
            .limit(20)
        )
        by_container = [
            {
                "container_id": row.knowledge_container_id or 'unassigned',
                "chunk_count": row.chunk_count,
                "document_count": row.doc_count
            }
            for row in container_result.all()
        ]
        
        # 임베딩 존재 여부 통계
        embedding_stats_result = await db.execute(
            select(
                func.count(VsDocContentsChunks.chunk_sno).filter(
                    VsDocContentsChunks.azure_embedding_1536.isnot(None)
                ).label('azure_count'),
                func.count(VsDocContentsChunks.chunk_sno).filter(
                    VsDocContentsChunks.aws_embedding_1024.isnot(None)
                ).label('aws_count'),
                func.count(VsDocContentsChunks.chunk_sno).filter(
                    VsDocContentsChunks.multimodal_embedding.isnot(None)
                ).label('multimodal_count'),
                func.count(VsDocContentsChunks.chunk_sno).filter(
                    VsDocContentsChunks.chunk_embedding.isnot(None)
                ).label('legacy_count')
            )
            .where(VsDocContentsChunks.del_yn == 'N')
        )
        embedding_stats = embedding_stats_result.one()
        
        # 평균 청크 크기
        avg_size_result = await db.execute(
            select(func.avg(VsDocContentsChunks.chunk_size))
            .where(VsDocContentsChunks.del_yn == 'N')
        )
        avg_chunk_size = avg_size_result.scalar() or 0
        
        return {
            "success": True,
            "data": {
                "total_chunks": total_chunks,
                "avg_chunk_size": int(avg_chunk_size),
                "by_provider": by_provider,
                "by_container": by_container,
                "embedding_coverage": {
                    "azure_1536": embedding_stats.azure_count or 0,
                    "aws_1024": embedding_stats.aws_count or 0,
                    "multimodal_512": embedding_stats.multimodal_count or 0,
                    "legacy": embedding_stats.legacy_count or 0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"벡터 DB 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/containers/overview", summary="컨테이너 전체 현황")
async def get_containers_overview(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    지식 컨테이너 전체 현황 조회
    - 컨테이너별 문서 수, 청크 수, 용량
    - 권한 현황
    """
    try:
        # 컨테이너 기본 정보 조회
        containers_result = await db.execute(
            select(
                TbKnowledgeContainers.container_id,
                TbKnowledgeContainers.container_name,
                TbKnowledgeContainers.container_type,
                TbKnowledgeContainers.created_date,
                TbKnowledgeContainers.access_level
            )
            .where(TbKnowledgeContainers.is_active == True)
            .order_by(TbKnowledgeContainers.container_name)
        )
        containers = containers_result.all()
        
        # 컨테이너별 문서 수 집계
        doc_counts_result = await db.execute(
            select(
                TbFileBssInfo.knowledge_container_id,
                func.count(TbFileBssInfo.file_bss_info_sno).label('doc_count'),
                func.sum(TbFileBssInfo.chunk_count).label('chunk_count')
            )
            .where(TbFileBssInfo.del_yn == 'N')
            .group_by(TbFileBssInfo.knowledge_container_id)
        )
        doc_counts = {
            row.knowledge_container_id: {
                "doc_count": row.doc_count,
                "chunk_count": row.chunk_count or 0
            }
            for row in doc_counts_result.all()
        }
        
        # 컨테이너별 권한 사용자 수
        perm_counts_result = await db.execute(
            select(
                TbUserPermissions.container_id,
                func.count(func.distinct(TbUserPermissions.user_emp_no)).label('user_count')
            )
            .group_by(TbUserPermissions.container_id)
        )
        perm_counts = {row.container_id: row.user_count for row in perm_counts_result.all()}
        
        # 결과 조합
        container_list = []
        for container in containers:
            container_stats = doc_counts.get(container.container_id, {"doc_count": 0, "chunk_count": 0})
            container_list.append({
                "container_id": container.container_id,
                "container_name": container.container_name,
                "container_type": container.container_type,
                "access_level": container.access_level,
                "is_public": container.access_level == 'public',
                "document_count": container_stats["doc_count"],
                "chunk_count": container_stats["chunk_count"],
                "user_count": perm_counts.get(container.container_id, 0),
                "created_at": container.created_date.isoformat() if container.created_date else None
            })
        
        # 요약 통계
        total_docs = sum(c["document_count"] for c in container_list)
        total_chunks = sum(c["chunk_count"] for c in container_list)
        
        return {
            "success": True,
            "data": {
                "total_containers": len(container_list),
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "containers": container_list
            }
        }
        
    except Exception as e:
        logger.error(f"컨테이너 현황 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"조회 중 오류가 발생했습니다: {str(e)}"
        )


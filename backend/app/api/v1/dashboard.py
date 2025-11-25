"""
대시보드 API 엔드포인트
사용자 대시보드에 표시할 요약 정보 및 최근 활동 데이터 제공
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import (
    User,
    TbFileBssInfo,
    TbChatSessions,
    TbChatHistory,
    TbPermissionRequests,
    TbKnowledgeContainers,
)
from app.utils.provider_filters import get_provider_filter_with_status
from app.models.document.multimodal_models import DocExtractionSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


# ==================== Response Models ====================

class DashboardSummary(BaseModel):
    my_documents_count: int
    chat_sessions_count: int
    pending_requests_count: int


class RecentDocument(BaseModel):
    file_bss_info_sno: int
    title: str
    file_name: str
    file_size: Optional[int]
    file_type: Optional[str]
    container_id: Optional[str]
    container_name: str
    created_at: Optional[str]
    created_by: Optional[str]
    processing_status: Optional[str]


class ContainerSummary(BaseModel):
    container_id: str
    container_name: str
    my_documents_count: int
    total_documents_count: int
    my_permission: str
    last_updated: Optional[str]
    recent_documents: list[str]


class RecentActivity(BaseModel):
    activity_type: str  # 'upload', 'download', 'chat', 'permission_request', 'search'
    title: str
    description: Optional[str]
    timestamp: str
    icon: str
    color: str
    metadata: Optional[dict] = None


# ==================== Endpoints ====================

@router.get("/recent-activities", summary="최근 활동 내역")
async def get_recent_activities(
    limit: int = Query(10, ge=1, le=50, description="조회할 활동 수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자의 최근 활동 내역 타임라인
    - 문서 업로드
    - AI 대화 시작
    - 권한 요청
    """
    try:
        activities = []
        
        # 1. 최근 문서 업로드 활동
        upload_query = (
            select(TbFileBssInfo, TbKnowledgeContainers)
            .outerjoin(
                TbKnowledgeContainers,
                TbFileBssInfo.knowledge_container_id == TbKnowledgeContainers.container_id
            )
            .where(
                and_(
                    TbFileBssInfo.created_by == str(current_user.emp_no),
                    TbFileBssInfo.del_yn == 'N'
                )
            )
            .order_by(desc(TbFileBssInfo.created_date))
            .limit(5)
        )
        upload_result = await db.execute(upload_query)
        uploads = upload_result.all()
        
        for file_info, container in uploads:
            activities.append({
                "activity_type": "upload",
                "title": f"문서 업로드: {file_info.file_lgc_nm}",
                "description": f"{container.container_name if container else 'Unknown'} 컨테이너",
                "timestamp": file_info.created_date.isoformat() if file_info.created_date else None,
                "icon": "📤",
                "color": "blue",
                "metadata": {
                    "file_id": file_info.file_bss_info_sno,
                    "file_type": file_info.file_extsn,
                    "container_id": file_info.knowledge_container_id
                }
            })
        
        # 2. 최근 AI 대화 시작
        chat_query = (
            select(TbChatSessions)
            .where(TbChatSessions.user_emp_no == str(current_user.emp_no))
            .order_by(desc(TbChatSessions.created_date))
            .limit(5)
        )
        chat_result = await db.execute(chat_query)
        chats = chat_result.scalars().all()
        
        for session in chats:
            # 세션명(session_name) 사용
            title = getattr(session, "session_name", None) or "새 대화"
            if len(title) > 30:
                title = title[:30] + "..."

            created_at = getattr(session, "created_date", None)
            timestamp = created_at.isoformat() if created_at else None

            activities.append({
                "activity_type": "chat",
                "title": f"AI 대화: {title}",
                "description": "지식생성 AI와 대화를 시작했습니다",
                "timestamp": timestamp,
                "icon": "💬",
                "color": "purple",
                "metadata": {
                    "session_id": session.session_id
                }
            })
        
        # 3. 최근 권한 요청
        permission_query = (
            select(TbPermissionRequests, TbKnowledgeContainers)
            .outerjoin(
                TbKnowledgeContainers,
                TbPermissionRequests.container_id == TbKnowledgeContainers.container_id
            )
            .where(TbPermissionRequests.requester_emp_no == str(current_user.emp_no))
            .order_by(desc(TbPermissionRequests.created_date))
            .limit(5)
        )
        permission_result = await db.execute(permission_query)
        permissions = permission_result.all()
        
        for perm, container in permissions:
            status_text = {
                'PENDING': '대기중',
                'APPROVED': '승인됨',
                'REJECTED': '거부됨'
            }.get(perm.request_status, perm.request_status)
            
            activities.append({
                "activity_type": "permission_request",
                "title": f"권한 요청: {container.container_name if container else 'Unknown'}",
                "description": f"상태: {status_text}",
                "timestamp": perm.created_date.isoformat() if perm.created_date else None,
                "icon": "🔐",
                "color": "orange",
                "metadata": {
                    "request_id": perm.request_id,
                    "status": perm.request_status,
                    "requested_permission": perm.requested_permission
                }
            })
        
        # 모든 활동을 시간순으로 정렬
        all_activities = sorted(
            activities,
            key=lambda x: x['timestamp'] if x['timestamp'] else '',
            reverse=True
        )[:limit]
        
        return {
            "success": True,
            "activities": all_activities,
            "total": len(all_activities)
        }
        
    except Exception as e:
        logger.error(f"최근 활동 내역 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"최근 활동 내역 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/summary", summary="대시보드 요약 정보")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    대시보드 요약 카드 정보
    - 내 문서 수
    - AI 대화 세션 수
    - 대기중인 권한 요청 수
    """
    logger.info(f"📊 대시보드 요약 요청 - 사용자: {current_user.username} (사번: {current_user.emp_no})")
    try:
        # 1. 내가 업로드한 문서 개수
        my_documents_result = await db.execute(
            select(func.count(TbFileBssInfo.file_bss_info_sno))
            .where(
                and_(
                    TbFileBssInfo.created_by == str(current_user.emp_no),
                    TbFileBssInfo.del_yn == 'N'
                )
            )
        )
        my_documents_count = my_documents_result.scalar() or 0
        
        # 2. 내 AI 대화 세션 수
        chat_sessions_result = await db.execute(
            select(func.count(TbChatSessions.session_id))
            .where(TbChatSessions.user_emp_no == str(current_user.emp_no))
        )
        chat_sessions_count = chat_sessions_result.scalar() or 0
        
        # 3. 내가 요청한 권한 중 대기중인 것
        pending_requests_result = await db.execute(
            select(func.count(TbPermissionRequests.request_id))
            .where(
                and_(
                    TbPermissionRequests.requester_emp_no == str(current_user.emp_no),
                    TbPermissionRequests.request_status == 'PENDING'
                )
            )
        )
        pending_requests_count = pending_requests_result.scalar() or 0
        
        return {
            "success": True,
            "data": {
                "my_documents_count": int(my_documents_count),
                "chat_sessions_count": int(chat_sessions_count),
                "pending_requests_count": int(pending_requests_count),
            }
        }
    except Exception as e:
        logger.error(f"대시보드 요약 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대시보드 요약 조회 실패: {str(e)}"
        )


@router.get("/recent-documents", summary="최근 문서 목록")
async def get_recent_documents(
    limit: int = Query(5, ge=1, le=20, description="조회할 문서 수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자가 최근 업로드한 문서 목록
    """
    try:
        logger.info(f"최근 문서 조회 - 사용자: {current_user.emp_no}, limit: {limit}")
        
        # 사용자가 업로드한 최근 문서 조회 (현재 프로바이더로 처리된 문서만)
        # 서브쿼리: 현재 프로바이더로 성공 처리된 문서 sno 목록
        processed_docs_subquery = (
            select(DocExtractionSession.file_bss_info_sno)
            .where(get_provider_filter_with_status(DocExtractionSession, include_pending=False))
            .distinct()
        )
        
        query = (
            select(TbFileBssInfo, TbKnowledgeContainers)
            .outerjoin(
                TbKnowledgeContainers, 
                TbFileBssInfo.knowledge_container_id == TbKnowledgeContainers.container_id
            )
            .where(
                and_(
                    TbFileBssInfo.created_by == str(current_user.emp_no),
                    TbFileBssInfo.del_yn == 'N',
                    # 현재 프로바이더로 처리된 문서 OR 처리 대기 중
                    or_(
                        TbFileBssInfo.file_bss_info_sno.in_(processed_docs_subquery),
                        TbFileBssInfo.processing_status.in_(['pending', 'processing'])
                    )
                )
            )
            .order_by(desc(TbFileBssInfo.created_date))
            .limit(limit)
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        documents = []
        for file_info, container in rows:
            documents.append({
                "file_bss_info_sno": file_info.file_bss_info_sno,
                "title": file_info.file_lgc_nm,
                "file_name": file_info.file_psl_nm,
                "file_size": 0,  # TbFileBssInfo에 file_size 컬럼이 없음
                "file_type": file_info.file_extsn,
                "container_id": file_info.knowledge_container_id,
                "container_name": container.container_name if container else "Unknown",
                "created_at": file_info.created_date.isoformat() if file_info.created_date else None,
                "created_by": file_info.created_by,
                "processing_status": file_info.processing_status
            })
        
        logger.info(f"최근 문서 조회 완료 - {len(documents)}개 반환")
        
        return {
            "success": True,
            "documents": documents,
            "total": len(documents)
        }
        
    except Exception as e:
        logger.error(f"최근 문서 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"최근 문서 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/container-summary", summary="내 컨테이너 요약")
async def get_container_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자가 접근 가능한 컨테이너별 요약 정보
    - 컨테이너 이름
    - 내 문서 수 / 전체 문서 수
    - 내 권한 레벨
    - 최근 업데이트된 문서
    """
    try:
        from app.services.auth.permission_service import PermissionService
        
        # PermissionService 인스턴스 생성
        permission_service = PermissionService(db)
        
        # 사용자가 접근 가능한 컨테이너 목록 조회
        containers_query = select(TbKnowledgeContainers).where(
            TbKnowledgeContainers.is_active == True
        )
        containers_result = await db.execute(containers_query)
        all_containers = containers_result.scalars().all()
        
        summaries = []
        
        for container in all_containers:
            # 권한 확인
            permission = await permission_service.get_user_permission_level(
                str(current_user.emp_no),
                str(container.container_id)
            )
            
            if not permission or permission == "NONE":
                continue
            
            # 내 문서 수 (현재 프로바이더로 처리된 문서만)
            processed_docs_subquery = (
                select(DocExtractionSession.file_bss_info_sno)
                .where(get_provider_filter_with_status(DocExtractionSession, include_pending=False))
                .distinct()
            )
            
            my_docs_result = await db.execute(
                select(func.count(TbFileBssInfo.file_bss_info_sno))
                .where(
                    and_(
                        TbFileBssInfo.knowledge_container_id == container.container_id,
                        TbFileBssInfo.created_by == str(current_user.emp_no),
                        TbFileBssInfo.del_yn == 'N',
                        or_(
                            TbFileBssInfo.file_bss_info_sno.in_(processed_docs_subquery),
                            TbFileBssInfo.processing_status.in_(['pending', 'processing'])
                        )
                    )
                )
            )
            my_docs_count = my_docs_result.scalar() or 0
            
            # 전체 문서 수 (현재 프로바이더로 처리된 문서만)
            total_docs_result = await db.execute(
                select(func.count(TbFileBssInfo.file_bss_info_sno))
                .where(
                    and_(
                        TbFileBssInfo.knowledge_container_id == container.container_id,
                        TbFileBssInfo.del_yn == 'N',
                        or_(
                            TbFileBssInfo.file_bss_info_sno.in_(processed_docs_subquery),
                            TbFileBssInfo.processing_status.in_(['pending', 'processing'])
                        )
                    )
                )
            )
            total_docs_count = total_docs_result.scalar() or 0
            
            # 최근 문서 3개 제목 (현재 프로바이더로 처리된 문서만)
            recent_docs_query = (
                select(TbFileBssInfo.file_lgc_nm)
                .where(
                    and_(
                        TbFileBssInfo.knowledge_container_id == container.container_id,
                        TbFileBssInfo.del_yn == 'N',
                        or_(
                            TbFileBssInfo.file_bss_info_sno.in_(processed_docs_subquery),
                            TbFileBssInfo.processing_status.in_(['pending', 'processing'])
                        )
                    )
                )
                .order_by(desc(TbFileBssInfo.created_date))
                .limit(3)
            )
            recent_docs_result = await db.execute(recent_docs_query)
            recent_docs = [row[0] for row in recent_docs_result.all()]
            
            # 마지막 업데이트 시간 (현재 프로바이더로 처리된 문서만)
            last_updated_query = (
                select(func.max(TbFileBssInfo.created_date))
                .where(
                    and_(
                        TbFileBssInfo.knowledge_container_id == container.container_id,
                        TbFileBssInfo.del_yn == 'N',
                        or_(
                            TbFileBssInfo.file_bss_info_sno.in_(processed_docs_subquery),
                            TbFileBssInfo.processing_status.in_(['pending', 'processing'])
                        )
                    )
                )
            )
            last_updated_result = await db.execute(last_updated_query)
            last_updated = last_updated_result.scalar()
            
            summaries.append({
                "container_id": container.container_id,
                "container_name": container.container_name,
                "my_documents_count": int(my_docs_count),
                "total_documents_count": int(total_docs_count),
                "my_permission": permission,
                "last_updated": last_updated.isoformat() if last_updated else None,
                "recent_documents": recent_docs
            })
        
        return {
            "success": True,
            "containers": summaries,
            "total": len(summaries)
        }
        
    except Exception as e:
        logger.error(f"컨테이너 요약 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너 요약 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/recent-chat-sessions", summary="최근 AI 대화 히스토리")
async def get_recent_chat_sessions(
    limit: int = Query(5, ge=1, le=20),
    cursor: Optional[datetime] = Query(None, description="이 커서(ISO) 이전의 항목을 페이지네이션으로 조회"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자의 최근 AI 대화 세션 목록
    - PostgreSQL에서 세션 및 실제 메시지 수 조회
    - 참고자료 수도 실제 데이터에서 집계
    """
    try:
        from sqlalchemy import func, text as sql_text
        
        # 최근 대화 세션 조회 (실제 메시지 수 포함)
        activity_col = func.coalesce(
            TbChatSessions.last_modified_date,
            TbChatSessions.last_activity,
            TbChatSessions.created_date
        ).label("activity_ts")
        sessions_query = (
            select(
                TbChatSessions.session_id,
                TbChatSessions.session_name,
                TbChatSessions.message_count,
                TbChatSessions.created_date,
                TbChatSessions.last_modified_date,
                TbChatSessions.last_activity,
                activity_col,
                # 실제 메시지 수 계산
                func.count(TbChatHistory.chat_id).label('actual_message_count')
            )
            .select_from(TbChatSessions)
            .outerjoin(
                TbChatHistory,
                TbChatSessions.session_id == TbChatHistory.session_id
            )
            .where(TbChatSessions.user_emp_no == str(current_user.emp_no))
            .where(TbChatSessions.is_active == True)
            .group_by(
                TbChatSessions.session_id,
                TbChatSessions.session_name,
                TbChatSessions.message_count,
                TbChatSessions.created_date,
                TbChatSessions.last_modified_date,
                TbChatSessions.last_activity,
                activity_col
            )
            .order_by(desc(activity_col))
            .limit(limit + 1)
        )
        
        # 커서가 있으면 해당 시점 이전 항목만 조회
        if cursor:
            sessions_query = sessions_query.where(activity_col < cursor)
        
        sessions_result = await db.execute(sessions_query)
        session_rows = sessions_result.all()
        
        has_more = len(session_rows) > limit
        sessions = session_rows[:limit]
        
        chat_history = []
        next_cursor_value: Optional[datetime] = None
        for row in sessions:
            session_id = row.session_id
            
            # 세션명 처리
            title = row.session_name or "새 대화"
            if len(title) > 50:
                title = title[:50] + "..."
            
            # 실제 메시지 수 (대화 쌍 수로 계산: 1 대화 = user + assistant)
            actual_count = row.actual_message_count or 0
            if actual_count > 0:
                message_count = actual_count
            else:
                message_count = row.message_count or 0  # PostgreSQL 미동기화 세션은 선언된 카운트 사용
            
            # 참고자료 수 계산 (referenced_documents 배열에서 고유 문서 ID 집계)
            document_count = 0
            try:
                doc_query = sql_text("""
                    SELECT COUNT(DISTINCT doc_id) as doc_count
                    FROM (
                        SELECT unnest(referenced_documents) as doc_id
                        FROM tb_chat_history
                        WHERE session_id = :session_id
                        AND referenced_documents IS NOT NULL
                        AND array_length(referenced_documents, 1) > 0
                    ) as docs
                """)
                doc_result = await db.execute(doc_query, {"session_id": session_id})
                doc_row = doc_result.fetchone()
                if doc_row and doc_row.doc_count:
                    document_count = doc_row.doc_count
            except Exception as doc_error:
                logger.warning(f"⚠️ 문서 수 계산 실패 (세션 {session_id}): {doc_error}")
                document_count = 0
            
            # 날짜 필드 처리
            created_at = row.created_date
            last_modified = row.last_modified_date or row.last_activity or row.created_date
            
            # 🆕 세션 타입 구분 (agent_ 접두사로 판단)
            session_type = "agent" if session_id.startswith("agent_") else "chat"
            
            chat_history.append({
                "session_id": session_id,
                "session_type": session_type,  # 🆕 추가
                "title": title,
                "message_count": message_count,
                "document_count": document_count,
                "created_at": created_at.isoformat() if created_at else None,
                "last_message_at": last_modified.isoformat() if last_modified else None
            })
        
        if has_more and sessions:
            last_row = sessions[-1]
            next_cursor_value = last_row.activity_ts or (
                last_row.last_modified_date or last_row.last_activity or last_row.created_date
            )
        else:
            next_cursor_value = None
        
        logger.info(f"✅ 대시보드: {len(chat_history)}개 세션 조회 (user={current_user.emp_no})")
        
        return {
            "success": True,
            "sessions": chat_history,
            "total": len(chat_history),
            "next_cursor": next_cursor_value.isoformat() if next_cursor_value else None,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"최근 대화 히스토리 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"최근 대화 히스토리 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/activity-stats", summary="활동 통계")
async def get_activity_stats(
    period: str = Query("7d", regex="^(7d|30d|90d)$", description="통계 기간"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 활동 통계 (차트용)
    - 기간별 문서 업로드 수
    - 문서 타입 분포
    - 컨테이너별 분포
    """
    try:
        # 기간 계산
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        days = days_map[period]
        start_date = datetime.now() - timedelta(days=days)
        
        # 1. 일별 업로드 통계
        daily_uploads_query = (
            select(
                func.date(TbFileBssInfo.created_date).label('date'),
                func.count(TbFileBssInfo.file_bss_info_sno).label('count')
            )
            .where(
                and_(
                    TbFileBssInfo.created_by == str(current_user.emp_no),
                    TbFileBssInfo.created_date >= start_date,
                    TbFileBssInfo.del_yn == 'N'
                )
            )
            .group_by(func.date(TbFileBssInfo.created_date))
            .order_by(func.date(TbFileBssInfo.created_date))
        )
        daily_result = await db.execute(daily_uploads_query)
        daily_stats = [
            {"date": str(row.date), "count": row.count}
            for row in daily_result.all()
        ]
        
        # 2. 문서 타입별 분포
        type_stats_query = (
            select(
                TbFileBssInfo.file_extsn,
                func.count(TbFileBssInfo.file_bss_info_sno).label('count')
            )
            .where(
                and_(
                    TbFileBssInfo.created_by == str(current_user.emp_no),
                    TbFileBssInfo.del_yn == 'N'
                )
            )
            .group_by(TbFileBssInfo.file_extsn)
        )
        type_result = await db.execute(type_stats_query)
        document_types = {
            row.file_extsn or 'unknown': row.count
            for row in type_result.all()
        }
        
        # 3. 컨테이너별 분포
        container_stats_query = (
            select(
                TbKnowledgeContainers.container_name,
                func.count(TbFileBssInfo.file_bss_info_sno).label('count')
            )
            .join(
                TbKnowledgeContainers,
                TbFileBssInfo.knowledge_container_id == TbKnowledgeContainers.container_id
            )
            .where(
                and_(
                    TbFileBssInfo.created_by == str(current_user.emp_no),
                    TbFileBssInfo.del_yn == 'N'
                )
            )
            .group_by(TbKnowledgeContainers.container_name)
        )
        container_result = await db.execute(container_stats_query)
        container_distribution = {
            row.container_name: row.count
            for row in container_result.all()
        }
        
        return {
            "success": True,
            "period": period,
            "stats": {
                "daily_uploads": daily_stats,
                "document_types": document_types,
                "container_distribution": container_distribution
            }
        }
        
    except Exception as e:
        logger.error(f"활동 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"활동 통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

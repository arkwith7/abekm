from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Header, Request
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import json
import os
import urllib.parse
from pathlib import Path
from datetime import datetime
import uuid

from app.core.dependencies import get_current_user
from app.core.security import AuthUtils
from app.services.auth.async_user_service import AsyncUserService
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User
from app.models.chat import RedisChatManager, get_redis_client, TbChatHistory, RedisChatMessage, MessageType
from app.core.config import settings
# from app.services.presentation.quick_ppt_generator_service import quick_ppt_service  # Deprecated
from app.services.presentation.templated_ppt_generator_service import templated_ppt_service
from app.services.presentation.ppt_template_manager import template_manager
from app.services.presentation.template_migration_service import template_migration_service
from app.services.presentation.template_debugger import template_debugger
from app.services.presentation.template_content_generator_service import template_content_generator
from app.services.presentation.file_manager import file_manager
from app.services.presentation.office_generator_client import office_generator_client
from app.models.presentation import PresentationRequest, PresentationResponse, PresentationMetadata, StructuredOutline

# 🚀 Unified Agent (Replaces all legacy agents)
from app.agents.presentation.unified_presentation_agent import unified_presentation_agent
import logging


router = APIRouter(tags=["📊 Presentation"])
logger = logging.getLogger(__name__)


# ===== Shared helpers (isolated to avoid circular imports) =====
def get_redis_chat_manager() -> RedisChatManager:
    redis_client = get_redis_client()
    return RedisChatManager(redis_client)


async def _get_message_by_id(chat_manager: RedisChatManager, session_id: str, message_id: str, db: Optional[AsyncSession] = None):
    # 1. Redis lookup
    msgs = await chat_manager.get_recent_messages(session_id, limit=1000)
    for msg in msgs:
        if getattr(msg, 'message_id', None) == message_id:
            return msg, msgs
            
    # 2. DB lookup (Fallback)
    if db:
        try:
            # Fetch all messages for session
            stmt = select(TbChatHistory).where(TbChatHistory.session_id == session_id).order_by(TbChatHistory.created_date.asc())
            result = await db.execute(stmt)
            history = result.scalars().all()
            
            if not history:
                return None, msgs
                
            # Convert DB history to pseudo-RedisChatMessage objects
            converted_msgs = []
            target_msg = None
            
            for row in history:
                # User message
                user_msg_obj = RedisChatMessage(
                    message_id=f"user_{row.chat_id}",
                    session_id=row.session_id,
                    message_type=MessageType.USER,
                    content=row.user_message,
                    user_emp_no=row.user_emp_no,
                    user_name="",
                    timestamp=row.created_date,
                    sequence_number=row.chat_id * 2 - 1
                )
                converted_msgs.append(user_msg_obj)
                if message_id == user_msg_obj.message_id:
                    target_msg = user_msg_obj
                    
                # Assistant message
                asst_msg_obj = RedisChatMessage(
                    message_id=f"agent_{row.chat_id}",
                    session_id=row.session_id,
                    message_type=MessageType.ASSISTANT,
                    content=row.assistant_response,
                    user_emp_no=row.user_emp_no,
                    user_name="AI Agent",
                    timestamp=row.created_date,
                    sequence_number=row.chat_id * 2,
                    model_used=row.model_used,
                    search_context=row.search_results,
                    referenced_documents=row.referenced_documents
                )
                converted_msgs.append(asst_msg_obj)
                
                if message_id == asst_msg_obj.message_id:
                    target_msg = asst_msg_obj
            
            # Fallback: If exact match failed, but we have messages, try to find by timestamp or just return last assistant message
            if not target_msg and converted_msgs:
                # If message_id looks like a timestamp (agent_17...), it might be from a fresh session that was saved to DB
                # In this case, we can't match ID exactly.
                # We assume the user wants the latest context.
                assistants = [m for m in converted_msgs if m.message_type == MessageType.ASSISTANT]
                if assistants:
                    target_msg = assistants[-1]
                    logger.info(f"⚠️ Exact message ID match failed for {message_id}, using last assistant message from DB")
            
            if target_msg:
                logger.info(f"✅ Found message in DB: {target_msg.message_id}")
                return target_msg, converted_msgs
                
        except Exception as e:
            logger.error(f"❌ DB lookup failed: {e}")

    return None, msgs


def _compose_context_from_messages(source_msg, all_msgs: List[Any]) -> tuple[str, str, Optional[List[Dict[str, Any]]]]:
    assistant_text = getattr(source_msg, 'content', '') or ''
    seq = getattr(source_msg, 'sequence_number', None)
    prev_user_text = ''
    referenced_docs = None
    
    # 디버깅: 전체 메시지 내용 확인
    logger.info(f"🔍 source_msg type: {type(source_msg)}")
    logger.info(f"🔍 source_msg content 길이: {len(assistant_text)}")
    logger.info(f"🔍 source_msg 첫 200자: '{assistant_text[:200]}'")
    
    # source_msg가 dict 형태인 경우도 처리
    if hasattr(source_msg, '__dict__'):
        logger.info(f"🔍 source_msg attributes: {list(source_msg.__dict__.keys())}")
        # 참고자료 정보 추출
        if hasattr(source_msg, 'referenced_documents'):
            referenced_docs = getattr(source_msg, 'referenced_documents', None)
            if referenced_docs:
                logger.info(f"📚 참고자료 발견: {len(referenced_docs)}개")
            else:
                logger.info("📚 참고자료 없음")
    elif isinstance(source_msg, dict):
        logger.info(f"🔍 source_msg keys: {list(source_msg.keys())}")
        assistant_text = source_msg.get('content', '') or source_msg.get('message', '') or assistant_text
        referenced_docs = source_msg.get('referenced_documents', None)
        logger.info(f"🔍 dict에서 추출된 content 길이: {len(assistant_text)}")
        if referenced_docs:
            logger.info(f"📚 dict에서 참고자료 발견: {len(referenced_docs)}개")
    
    if seq is not None:
        candidates = [m for m in all_msgs if getattr(m, 'sequence_number', -1) < seq]
        for m in reversed(candidates):
            if getattr(m, 'message_type', None) and getattr(m, 'message_type').value == 'user':
                prev_user_text = getattr(m, 'content', '') or ''
                break
    
    topic = (prev_user_text or assistant_text)[:80]
    context_text = assistant_text
    
    logger.info(f"🔍 최종 context_text 길이: {len(context_text)}")
    logger.info(f"🔍 최종 topic: '{topic}'")
    
    return topic, context_text, referenced_docs


def _ensure_markdown_structure(text: str, topic: str) -> str:
    """
    AI 답변을 마크다운 구조로 변환하여 outline_generation_tool 파싱 성공률 향상.
    
    Args:
        text: AI 답변 텍스트
        topic: 주제
        
    Returns:
        구조화된 마크다운 텍스트 (## 제목, ### 섹션 구조)
    """
    import re
    
    # 이미 ## 헤더가 있으면 그대로 반환
    if re.search(r'^##\s+', text, re.MULTILINE):
        return text
    
    # 빈 텍스트 처리
    if not text or len(text.strip()) < 50:
        return text
    
    # 기본 구조 생성
    lines = text.split('\n')
    structured_lines = [f"## {topic}", ""]
    
    current_section = None
    section_content = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # 빈 줄
        if not line_stripped:
            if section_content:
                section_content.append("")
            continue
        
        # 숫자 목록 (1., 2., 3. 등) → ### 섹션으로 변환
        numbered_match = re.match(r'^(\d+)\.\s+(.+)$', line_stripped)
        if numbered_match:
            # 이전 섹션 저장
            if current_section and section_content:
                structured_lines.append(f"### {current_section}")
                structured_lines.extend(section_content)
                structured_lines.append("")
                section_content = []
            
            # 새 섹션 시작
            current_section = numbered_match.group(2)
            continue
        
        # Bullet point (-, *, •)
        if re.match(r'^[-*•]\s+', line_stripped):
            section_content.append(line_stripped)
            continue
        
        # 일반 텍스트
        if current_section:
            # 현재 섹션의 내용으로 추가
            section_content.append(f"- {line_stripped}")
        else:
            # 첫 섹션 없이 나온 내용 → "개요" 섹션으로
            if not any(s.startswith("### 개요") for s in structured_lines):
                structured_lines.append("### 개요")
            structured_lines.append(f"- {line_stripped}")
    
    # 마지막 섹션 저장
    if current_section and section_content:
        structured_lines.append(f"### {current_section}")
        structured_lines.extend(section_content)
    
    result = '\n'.join(structured_lines)
    
    # 최소 3개 이상의 ### 섹션이 없으면 원본 반환 (구조화 실패)
    section_count = len(re.findall(r'^###\s+', result, re.MULTILINE))
    if section_count < 2:
        logger.warning(f"⚠️ 구조화 실패 (섹션 {section_count}개만 생성) - 원본 사용")
        return text
    
    logger.info(f"✅ 구조화 성공: {section_count}개 섹션 생성")
    return result


def _extract_document_filename(referenced_docs: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """Extract primary document filename from referenced documents metadata."""
    if not referenced_docs:
        return None

    primary = referenced_docs[0] or {}
    if not isinstance(primary, dict):
        return None

    candidate_keys = ("file_name", "fileName", "document_name", "title", "name")

    for key in candidate_keys:
        value = primary.get(key)
        if value:
            return str(value)

    metadata = primary.get("metadata")
    if isinstance(metadata, dict):
        for key in candidate_keys:
            value = metadata.get(key)
            if value:
                return str(value)

    return None

async def _compose_fallback_context(chat_manager: RedisChatManager, session_id: str, title: Optional[str], message: Optional[str]) -> tuple[str, str, Optional[str]]:
    try:
        # 1) 요청의 message가 있으면 우선 사용
        if message and message.strip():
            topic = (title or message).strip()[:80]
            return topic, message, None
        # 2) 최근 메시지에서 어시스턴트>유저 순으로 사용
        recent = await chat_manager.get_recent_messages(session_id, limit=50)
        if recent:
            assistant_msgs = [m for m in recent if getattr(m, 'message_type', None) and getattr(m, 'message_type').value == 'assistant']
            user_msgs = [m for m in recent if getattr(m, 'message_type', None) and getattr(m, 'message_type').value == 'user']
            if assistant_msgs:
                m = assistant_msgs[-1]
                topic = (title or getattr(m, 'content', '') or '발표자료')[:80]
                return topic, getattr(m, 'content', '') or '', None
            if user_msgs:
                m = user_msgs[-1]
                topic = (title or getattr(m, 'content', '') or '발표자료')[:80]
                return topic, getattr(m, 'content', '') or '', None
    except Exception as e:
        logger.warning(f"fallback context 구성 중 오류: {e}")
    # 3) 최종 폴백
    return (title or '발표자료'), (message or ''), None


@router.post(
    "/agent/presentation/generate",
    response_model=PresentationResponse,
    summary="[DEPRECATED] Generate presentation via HTML-first pipeline",
    deprecated=True
)
async def generate_agent_presentation(
    request: PresentationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    [DEPRECATED] This legacy endpoint has been removed.
    
    Please use one of the following endpoints instead:
    - /api/v1/agent/presentation/build-quick (Quick PPT)
    - /api/v1/agent/presentation/build-unified (Unified Agent)
    """
    raise HTTPException(
        status_code=410,
        detail={
            "error": "This endpoint has been deprecated and removed.",
            "alternatives": [
                "/api/v1/agent/presentation/build-quick",
                "/api/v1/agent/presentation/build-unified"
            ],
            "message": "Please use the new unified agent endpoints for presentation generation."
        }
    )


@router.get(
    "/agent/presentation/view/{filename}",
    response_class=HTMLResponse,
    summary="View generated HTML presentation"
)
async def view_generated_presentation(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    try:
        path = file_manager.resolve_file(filename, "html")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Presentation not found") from exc

    html_content = path.read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)


@router.get(
    "/agent/presentation/outline/{filename}",
    response_class=JSONResponse,
    summary="Retrieve stored presentation outline"
)
async def get_generated_outline(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    try:
        path = file_manager.resolve_file(filename, "outline")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Outline not found") from exc

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode outline JSON: %s", exc)
        raise HTTPException(status_code=500, detail="Stored outline is corrupted") from exc

    return JSONResponse(content=payload)


@router.post(
    "/agent/presentation/generate-pptx",
    summary="Generate PPTX from outline",
    description="Convert stored outline JSON to PPTX file using Office Generator Service"
)
async def generate_pptx_from_outline(
    outline_filename: str = Query(..., description="Outline JSON filename (e.g., presentation_xxx.json)"),
    theme: Optional[str] = Query(None, description="Optional theme override (business, modern, playful)"),
    current_user: User = Depends(get_current_user)
):
    """
    Generate PPTX from stored outline
    
    Steps:
    1. Load outline JSON from file
    2. Call Office Generator Service
    3. Save PPTX file
    4. Return download URL
    """
    try:
        # 1. Load outline JSON
        try:
            outline_path = file_manager.resolve_file(outline_filename, "outline")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Outline not found: {outline_filename}")
        
        try:
            outline_data = json.loads(outline_path.read_text(encoding="utf-8"))
            outline = StructuredOutline(**outline_data)
        except json.JSONDecodeError:
            logger.error("Failed to decode outline JSON")
            raise HTTPException(status_code=500, detail="Stored outline is corrupted")
        except Exception as e:
            logger.error(f"Failed to parse outline: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid outline format: {str(e)}")
        
        logger.info(
            f"Generating PPTX for outline: {outline_filename} (theme: {theme or outline.theme})"
        )
        
        # 2. Call Office Generator Service
        try:
            pptx_data = await office_generator_client.convert_to_pptx(outline, theme)
        except Exception as e:
            logger.error(f"Office Generator conversion failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"PPTX conversion failed: {str(e)}"
            )
        
        # 3. Save PPTX file
        try:
            # Use same base filename as outline
            base_filename = outline_filename.replace('.json', '')
            pptx_path = file_manager.save_pptx(pptx_data, base_filename)
        except Exception as e:
            logger.error(f"Failed to save PPTX: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to save PPTX file")
        
        # 4. Return download URL
        pptx_url = f"/api/v1/agent/presentation/download/{pptx_path.name}"
        
        logger.info(
            f"PPTX generated successfully: {pptx_path.name} ({len(pptx_data)} bytes)"
        )
        
        return {
            "success": True,
            "pptx_url": pptx_url,
            "filename": pptx_path.name,
            "size_bytes": len(pptx_data),
            "slide_count": len(outline.slides)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_pptx_from_outline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# NOTE: 다운로드 엔드포인트는 download_presentation_file() 함수로 통합됨 (아래 참조)
# 쿼리 파라미터 token 지원을 위해 중복 엔드포인트 제거


# ===== Schemas (presentation only) =====
class PresentationOutlineRequest(BaseModel):
    session_id: str
    source_message_id: str
    max_slides: int = 8
    provider: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None  # 폴백 메시지
    presentation_type: str = "general"
    template_id: Optional[str] = None


class PresentationOutlineResponse(BaseModel):
    success: bool
    outline: Dict[str, Any]


class SlideManagementInfo(BaseModel):
    index: int
    original_index: Optional[int] = None
    base_slide_index: Optional[int] = None
    title: Optional[str] = None
    is_enabled: bool = True
    is_visible: bool = True


class PresentationBuildFromMessageRequest(BaseModel):
    session_id: str
    source_message_id: str
    provider: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None  # 폴백 메시지
    outline: Optional[Dict[str, Any]] = None
    presentation_type: str = "general"
    slide_management: Optional[List[SlideManagementInfo]] = None
    template_id: Optional[str] = None


class PresentationBuildRequest(BaseModel):
    session_id: str
    source_message_id: str
    provider: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None  # 폴백 메시지
    outline: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    file_basename: Optional[str] = None
    object_mappings: Optional[List[Dict[str, Any]]] = None
    content_segments: Optional[List[Dict[str, Any]]] = None
    slide_management: Optional[List[SlideManagementInfo]] = None


# ===== Templates =====
@router.get("/agent/presentation/templates", summary="PPT 템플릿 목록")
async def list_presentation_templates(current_user: User = Depends(get_current_user)):
    """사용자별 템플릿 목록 조회 (공용 + 개인)"""
    from app.services.presentation.user_template_manager import user_template_manager
    
    user_id = str(current_user.id)
    return user_template_manager.list_templates_for_user(user_id)

@router.get("/agent/presentation/templates/_debug/state", summary="[DEBUG] 템플릿 레지스트리 상태")
async def debug_presentation_templates_state():
    try:
        items = []
        for tid, t in template_manager._registry.items():  # noqa: SLF001
            items.append({
                "id": tid,
                "exists": os.path.exists(t.get("path", "")) if isinstance(t, dict) else False,
            })
        return {"success": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/presentation/templates/{template_id}", summary="PPT 템플릿 상세")
async def get_presentation_template_details(template_id: str):
    details = template_manager.get_template_details(template_id)
    if not details:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
    return {"success": True, "template": details}


@router.get("/agent/presentation/templates/{template_id}/thumbnail", summary="PPT 템플릿 썸네일")
async def get_presentation_template_thumbnail(template_id: str):
    path = template_manager.get_thumbnail_path(template_id)
    if not path:
        raise HTTPException(status_code=404, detail="썸네일이 없습니다")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="썸네일 파일을 찾을 수 없습니다")
    filename = os.path.basename(path)
    return FileResponse(path, media_type='image/png', filename=filename)


@router.get("/agent/presentation/templates/{template_id}/layouts", summary="PPT 템플릿 레이아웃 목록")
async def get_presentation_template_layouts(template_id: str):
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        template_details = template_manager.get_template_details(decoded_template_id)
        if not template_details:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
        template_path = template_details.get('path')
        if not template_path or not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="템플릿 파일을 찾을 수 없습니다")
        layouts_info = template_manager.analyze_template_layouts(decoded_template_id)
        return {"success": True, "template_id": decoded_template_id, "layouts": layouts_info}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="레이아웃 정보 조회 중 오류가 발생했습니다")


@router.get("/agent/presentation/templates/{template_id}/thumbnails", summary="템플릿 썸네일 목록")
async def get_template_thumbnails(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        from app.services.presentation.user_template_manager import user_template_manager
        import urllib.parse
        
        decoded_template_id = urllib.parse.unquote(template_id)
        logger.info(f"템플릿 썸네일 목록 요청: {decoded_template_id} (user={current_user.id})")
        
        # 사용자 템플릿에서 먼저 찾기
        template_details = user_template_manager.get_template_details(str(current_user.id), decoded_template_id)
        
        # 없으면 기존 template_manager에서 찾기 (fallback)
        if not template_details:
            template_details = template_manager.get_template_details(decoded_template_id)
        
        if not template_details:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
        
        thumbnails = template_details.get('thumbnails', [])
        logger.info(f"✅ 썸네일 수: {len(thumbnails)}")
        return {
            "success": True,
            "template_id": decoded_template_id,
            "template_name": template_details.get('name', ''),
            "thumbnails": thumbnails
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"템플릿 썸네일 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/presentation/templates/{template_id}/thumbnails/{slide_index}", summary="슬라이드 썸네일 이미지")
async def get_slide_thumbnail(template_id: str, slide_index: int):
    try:
        from app.services.presentation.thumbnail_generator import thumbnail_generator
        logger.info(f"슬라이드 썸네일 이미지 요청: {template_id}/{slide_index}")
        thumbnail_data = thumbnail_generator.get_slide_thumbnail(template_id, slide_index)
        if thumbnail_data:
            from fastapi.responses import Response
            return Response(content=thumbnail_data, media_type="image/png")
        else:
            raise HTTPException(status_code=404, detail="썸네일 이미지를 찾을 수 없습니다")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"슬라이드 썸네일 이미지 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/presentation/templates/upload", summary="PPT 템플릿 업로드")
async def upload_presentation_template(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """사용자별 템플릿 업로드"""
    from app.services.presentation.user_template_manager import user_template_manager
    
    if not file.filename or not file.filename.lower().endswith('.pptx'):
        raise HTTPException(status_code=400, detail="pptx 파일만 지원합니다")
    
    user_id = str(current_user.id)
    data = await file.read()
    
    entry = user_template_manager.upload_template(
        user_id=user_id,
        file_content=data,
        filename=file.filename,
        name=name
    )
    return {"success": True, "template": entry}


@router.delete("/agent/presentation/templates/{template_id}", summary="PPT 템플릿 삭제")
async def delete_presentation_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """사용자 템플릿 삭제 (공용 템플릿은 삭제 불가)"""
    from app.services.presentation.user_template_manager import user_template_manager
    
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        user_id = str(current_user.id)
        
        ok = user_template_manager.delete_template(user_id, decoded_template_id)
        if not ok:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없거나 삭제 권한이 없습니다")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"템플릿 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail="템플릿 삭제 중 오류가 발생했습니다")


@router.post("/agent/presentation/templates/{template_id}/set-default", summary="PPT 템플릿을 기본 템플릿으로 설정")
async def set_default_presentation_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """사용자별 기본 템플릿 설정"""
    from app.services.presentation.user_template_manager import user_template_manager
    
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        user_id = str(current_user.id)
        
        ok = user_template_manager.set_default_template(user_id, decoded_template_id)
        if not ok:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"기본 템플릿 설정 실패: {e}")
        raise HTTPException(status_code=500, detail="기본 템플릿 설정 중 오류가 발생했습니다")


@router.get("/agent/presentation/templates/{template_id}/download", summary="PPT 템플릿 원본 파일 다운로드")
async def download_presentation_template(
    template_id: str,
    token: Optional[str] = Query(None, description="인증 토큰 (iframe용)"),
    authorization: Optional[str] = Header(None),
):
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        template_path = template_manager.get_template_file_path(decoded_template_id)
        if not template_path or not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="템플릿 파일을 찾을 수 없습니다")
        original_filename = os.path.basename(template_path)
        def generate():
            with open(template_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
        encoded_filename = urllib.parse.quote(original_filename)
        return StreamingResponse(
            generate(),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="템플릿 파일 다운로드 중 오류가 발생했습니다")


@router.get("/agent/presentation/templates/{template_id}/file", summary="PPT 템플릿 파일 조회 (PDF 변환)")
async def get_presentation_template_file(
    template_id: str,
    token: Optional[str] = Query(None, description="인증 토큰 (iframe용)"),
    authorization: Optional[str] = Header(None),
):
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        path = template_manager.get_template_file_path(decoded_template_id)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="템플릿 파일을 찾을 수 없습니다")
        pdf_path = template_manager.get_template_pdf_path(decoded_template_id)
        if not pdf_path or not os.path.exists(pdf_path):
            # 도구 설치 여부 안내
            try:
                import shutil as _shutil
                tool = _shutil.which('soffice') or _shutil.which('libreoffice')
            except Exception:
                tool = None
            if not tool:
                raise HTTPException(status_code=500, detail="PDF 변환 도구(soffice/libreoffice)가 설치되어 있지 않아 미리보기를 생성할 수 없습니다")
            raise HTTPException(status_code=500, detail="템플릿 PDF 변환 중 오류가 발생했습니다")
        def generate():
            with open(pdf_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
        encoded_filename = urllib.parse.quote(f"{decoded_template_id}.pdf")
        return StreamingResponse(
            generate(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"}
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="템플릿 파일 변환 중 오류가 발생했습니다")


@router.get("/agent/presentation/templates/{template_id}/simple-metadata", summary="PPT 템플릿 단순화된 메타데이터 (UI 친화적)")
async def get_template_simple_metadata(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """Return UI-friendly template metadata expected by the mapping editor.

    Shape:
    {
      success: true,
      template_id: string,
      metadata: {
        presentationTitle: string,
        totalPages: number,
        slides: Array<{ pageNumber: number, layout: string, elements: [...], shapes?: [...] }>
      }
    }
    """
    try:
        from app.services.presentation.user_template_manager import user_template_manager
        
        logger.info(f"🔍 [simple-metadata] 요청: raw_id='{template_id}'")
        decoded_id = urllib.parse.unquote(template_id)
        logger.info(f"🔍 [simple-metadata] 디코딩된 ID: '{decoded_id}'")
        
        user_id = str(current_user.id)

        # 🔄 사용자 템플릿에서 먼저 찾기
        template_details = user_template_manager.get_template_details(user_id, decoded_id)
        full = None
        if template_details:
            logger.info(f"✅ [simple-metadata] 사용자 템플릿 발견: user={user_id}")
            full = user_template_manager.get_template_metadata(user_id, decoded_id)
        else:
            # 기존 template_manager에서 찾기 (fallback)
            template_details = template_manager.get_template_details(decoded_id)
            if template_details:
                full = template_manager.get_template_metadata(decoded_id)
        
        if not template_details:
            logger.error(f"❌ [simple-metadata] 템플릿을 찾을 수 없음: '{decoded_id}'")
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {decoded_id}")

        # 메타데이터 확인 (이미 위에서 로드됨)
        if not full:
            logger.warning(f"⚠️ [simple-metadata] 메타데이터 파일 없음 → 빈 기본값 반환: '{decoded_id}'")
            simple = {
                "presentationTitle": template_details.get("name") or decoded_id,
                "totalPages": 0,
                "slides": []
            }
            return {"success": True, "template_id": decoded_id, "metadata": simple}

        # 가공: extractor 구조(slides/shapes/elements)를 SimpleTemplateMetadata로 변환
        slides = full.get("slides", []) or []
        total_pages = len(slides)
        logger.info(f"✅ [simple-metadata] 원본 슬라이드 수: {total_pages}")

        def _normalize_element(e: dict) -> dict:
            # UI가 사용하는 필드 위주로 정규화; 알 수 없는 필드는 그대로 둠
            out = {
                "id": e.get("id") or e.get("name") or e.get("element_id") or "",
                "type": (e.get("type") or "textbox").lower(),
                "content": e.get("content") or (e.get("text") if isinstance(e.get("text"), str) else None),
                # position은 객체 형태를 그대로 유지(에디터가 좌표객체도 처리함)
                "position": e.get("position") or {
                    "left": e.get("left_px"),
                    "top": e.get("top_px"),
                    "width": e.get("width_px"),
                    "height": e.get("height_px"),
                }
            }
            # 가능한 스타일 힌트
            if "fontSize" in e or "fontWeight" in e or "alignment" in e:
                out["style"] = {
                    "fontSize": e.get("fontSize"),
                    "fontWeight": e.get("fontWeight"),
                    "alignment": e.get("alignment"),
                    "width": str(e.get("width_px")) if e.get("width_px") is not None else None,
                    "height": str(e.get("height_px")) if e.get("height_px") is not None else None,
                }
            return out

        simple_slides = []
        width_px = full.get("slide_width_px")
        height_px = full.get("slide_height_px")
        for s in slides:
            # elements: 추출기에서 이미 간단화된 텍스트박스 목록이 있음
            elts = [
                _normalize_element(e)
                for e in (s.get("elements") or [])
            ]

            # shapes: 원시 shape도 추가해 편집기에서 보조정보로 활용
            raw_shapes = s.get("shapes") or []
            shapes_norm = []
            for sh in raw_shapes:
                shapes_norm.append({
                    "id": sh.get("name"),
                    "type": (str(sh.get("type")) if sh.get("type") else "").upper(),
                    "name": sh.get("name"),
                    "left_px": sh.get("left_px"),
                    "top_px": sh.get("top_px"),
                    "width_px": sh.get("width_px"),
                    "height_px": sh.get("height_px"),
                    "text": sh.get("text", {}).get("raw") if isinstance(sh.get("text"), dict) else None,
                })

            simple_slides.append({
                "pageNumber": s.get("index") or 0,
                "layout": s.get("layout_name") or "",
                "elements": elts,
                # 편집기가 참고하는 보조 필드들
                "shapes": shapes_norm,
                "slide_width_px": width_px,
                "slide_height_px": height_px,
                # 제목 힌트(있으면)
                "title": None,
            })

        simple = {
            "presentationTitle": template_details.get("name") or full.get("file") or decoded_id,
            "totalPages": total_pages,
            "slides": simple_slides,
        }

        logger.info(
            f"✅ [simple-metadata] 변환 완료: pages={simple['totalPages']}, first_slide_elements="
            f"{len(simple['slides'][0]['elements']) if simple['slides'] else 0}"
        )
        return {"success": True, "template_id": decoded_id, "metadata": simple}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [simple-metadata] 처리 실패: {e}")
        import traceback
        logger.error(f"❌ 상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"템플릿 메타데이터 조회 중 오류: {str(e)}")


@router.get("/agent/presentation/templates/{template_id}/metadata")
async def get_template_metadata(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        from app.services.presentation.user_template_manager import user_template_manager
        
        decoded_id = urllib.parse.unquote(template_id)
        user_id = str(current_user.id)
        
        # 🔄 사용자 템플릿에서 먼저 찾기
        data = user_template_manager.get_template_metadata(user_id, decoded_id)
        if not data:
            # 기존 template_manager에서 찾기 (fallback)
            data = template_manager.get_template_metadata(decoded_id)
        
        if not data:
            raise HTTPException(status_code=404, detail=f"템플릿 메타데이터를 찾을 수 없습니다: {decoded_id}")
        
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Outline =====
@router.post("/agent/presentation/outline", response_model=PresentationOutlineResponse)
async def create_presentation_outline(
    req: PresentationOutlineRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"🔍 아웃라인 생성 요청: session_id={req.session_id}, source_message_id={req.source_message_id}")
        logger.info(f"🔍 요청 파라미터: provider={req.provider}, title={req.title}, presentation_type={req.presentation_type}")
        
        source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id, db)
        referenced_documents: Optional[List[Dict[str, Any]]] = None
        document_filename: Optional[str] = None
        if not source_msg:
            logger.warning(f"⚠️ source_message_id를 찾지 못함: {req.source_message_id} → 폴백 컨텍스트 사용")
            topic, context_text, document_filename = await _compose_fallback_context(
                chat_manager,
                req.session_id,
                req.title,
                req.message,
            )
        else:
            logger.info(f"✅ 메시지 조회 성공: {len(msgs)}개 메시지")
            topic, context_text, referenced_documents = _compose_context_from_messages(source_msg, msgs)
            document_filename = _extract_document_filename(referenced_documents)
        
        if req.title:
            topic = req.title
            logger.info(f"🔍 사용자 지정 제목 사용: '{topic}'")
        
        effective_provider = req.provider or settings.get_current_llm_provider()
        logger.info(f"🔍 최종 Provider: '{effective_provider}'")
        
        deck = await templated_ppt_service.generate_enhanced_outline(
            topic=topic,
            context_text=context_text,
            provider=effective_provider,
            document_filename=document_filename,
            presentation_type=req.presentation_type
        )
        
        if deck:
            logger.info(f"✅ 아웃라인 생성 성공: {len(deck.slides)}개 슬라이드")
            return {"success": True, "outline": deck.model_dump()}
        else:
            logger.error("❌ 아웃라인 생성 실패: deck이 None")
            raise HTTPException(status_code=500, detail="아웃라인 생성에 실패했습니다")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 아웃라인 생성 중 오류: {e}")
        import traceback
        logger.error(f"❌ 상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"아웃라인 생성 중 오류가 발생했습니다: {str(e)}")


# ===== Build from message (SSE) =====
@router.post("/agent/presentation/build-from-message")
async def build_presentation_from_message_sse(
    req: PresentationBuildFromMessageRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    async def stream():
        try:
            import time
            t0 = time.perf_counter()
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            try:
                source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id, db)
                if not source_msg:
                    logger.warning(f"⚠️ source_message_id not found → fallback context")
                    topic, context_text, document_filename = await _compose_fallback_context(
                        chat_manager,
                        req.session_id,
                        req.title,
                        req.message,
                    )
                else:
                    topic, context_text, referenced_documents = _compose_context_from_messages(source_msg, msgs)
                    document_filename = _extract_document_filename(referenced_documents)
                if req.title:
                    topic = req.title
                t1 = time.perf_counter()
                yield f"data: {json.dumps({'type': 'outline_generating', 't_ms': int((t1-t0)*1000)})}\n\n"
                user_template_id = None
                custom_template_path = None
                if req.template_id:
                    template_details = template_manager.get_template_details(req.template_id)
                    if template_details:
                        if template_details.get('dynamic_template_id'):
                            user_template_id = template_details['dynamic_template_id']
                        if template_details.get('cleaned_template_path'):
                            custom_template_path = template_details['cleaned_template_path']
                        elif template_details.get('path'):
                            custom_template_path = template_details['path']
                deck = await templated_ppt_service.generate_enhanced_outline(
                    topic=topic,
                    context_text=context_text,
                    provider=req.provider,
                    document_filename=document_filename,
                    presentation_type=req.presentation_type
                )
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'outline step failed: {str(e)}'})}\n\n"; yield "data: [DONE]\n\n"; return
            t2 = time.perf_counter()
            yield f"data: {json.dumps({'type': 'outline_ready', 'slides': len(deck.slides), 't_ms': int((t2-t0)*1000)})}\n\n"
            custom_template_path = None
            user_template_id = None
            if req.template_id:
                tpl = template_manager.get_template_details(req.template_id)
                if tpl:
                    user_template_id = tpl.get('dynamic_template_id')
                    template_path = tpl.get('cleaned_template_path') or tpl.get('path')
                    if template_path and os.path.exists(template_path):
                        custom_template_path = template_path
            text_box_mappings = None
            content_segments = None
            object_mappings = None
            slide_management_info = None
            if req.outline:
                object_mappings = req.outline.get('object_mappings') or req.outline.get('objectMappings')
                text_box_mappings = req.outline.get('textBoxMappings')
                content_segments = req.outline.get('contentSegments')
                slide_management_info = req.outline.get('slide_management')
            if req.slide_management and not slide_management_info:
                slide_management_info = [sm.dict() if hasattr(sm, 'dict') else sm for sm in req.slide_management]
            # ensure slide_management is list[dict]
            if slide_management_info:
                slide_management_info = [s if isinstance(s, dict) else getattr(s, 'dict', lambda: {})() for s in slide_management_info]
            file_path = templated_ppt_service.build_enhanced_pptx_with_slide_management(
                deck,
                custom_template_path=custom_template_path,
                user_template_id=user_template_id,
                text_box_mappings=object_mappings or text_box_mappings,
                content_segments=content_segments,
                slide_management=slide_management_info
            )
            file_name_only = os.path.basename(file_path)
            file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name_only)}"
            yield f"data: {json.dumps({'type': 'complete', 'file_url': file_url, 'file_name': file_name_only})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"; yield "data: [DONE]\n\n"
    return StreamingResponse(
        stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


# ===== NEW: Quick and Templated explicit pipelines =====
class QuickPresentationBuildRequest(BaseModel):
    session_id: str
    source_message_id: Optional[str] = None
    message: Optional[str] = None
    max_slides: int = 8


@router.post(
    "/agent/presentation/build-quick",
    summary="🧠 ReAct Agent 기반 Quick PPT 생성",
    description="""
    **ReAct (Reasoning + Acting) Agent** 패턴을 사용한 PPT 생성.
    
    LLM이 직접 도구를 선택하고 Thought → Action → Observation 루프를 통해 
    동적으로 PPT를 생성합니다.
    
    **특징:**
    - LLM이 상황에 따라 도구 선택 (outline_generation, visualization, pptx_builder, quality_validator)
    - 중간 결과를 바탕으로 다음 행동 결정
    - 품질 검증 및 자동 개선 시도
    """
)
async def build_presentation_quick(
    req: QuickPresentationBuildRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    """ReAct Agent 기반 Quick PPT 생성 (기존 파이프라인 대체)"""
    async def stream():
        try:
            run_id = str(uuid.uuid4())
            yield f"data: {json.dumps({'type': 'start', 'agent_type': 'ReAct', 'run_id': run_id, 'trace_id': run_id})}\n\n"
            
            # 메시지 소스 추출 (기존 로직 유지)
            topic = "발표자료"
            context_text = ""
            referenced_documents = None
            
            if req.source_message_id:
                logger.info(f"🔍 [ReAct] 메시지 ID로 검색: {req.source_message_id}")
                source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id, db)
                
                if not source_msg:
                    if req.message:
                        logger.info(f"✅ [ReAct] 폴백으로 요청 본문의 message 사용: {len(req.message)}자")
                        topic = req.message[:80]
                        context_text = req.message
                    else:
                        try:
                            recent_msgs = await chat_manager.get_recent_messages(req.session_id, limit=10)
                            assistant_msgs = [m for m in recent_msgs if getattr(m, 'message_type', None) and getattr(m, 'message_type').value == 'assistant']
                            if assistant_msgs:
                                source_msg = assistant_msgs[-1]
                                tpc, ctx, ref_docs = _compose_context_from_messages(source_msg, msgs or [])
                                topic, context_text, referenced_documents = (tpc or topic), (ctx or context_text), ref_docs
                            else:
                                yield f"data: {json.dumps({'type': 'error', 'message': '어시스턴트 메시지를 찾을 수 없습니다'})}\n\n"
                                yield "data: [DONE]\n\n"
                                return
                        except Exception as e:
                            logger.error(f"❌ [ReAct] 폴백 메시지 조회 실패: {e}")
                            yield f"data: {json.dumps({'type': 'error', 'message': '메시지를 찾을 수 없습니다'})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                else:
                    tpc, ctx, ref_docs = _compose_context_from_messages(source_msg, msgs or [])
                    topic, context_text, referenced_documents = (tpc or topic), (ctx or context_text), ref_docs
            elif req.message:
                topic = req.message[:80]
                context_text = req.message
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'message or source_message_id required'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 컨텍스트 유효성 검증
            if not context_text or len(context_text.strip()) < 50:
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI 답변 내용이 충분하지 않습니다.'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            logger.info(f"🧠 [ReAct] Agent 실행 시작 - topic: '{topic[:50]}', context: {len(context_text)}자")
            
            # 📝 콘텐츠 구조화 전처리 (마크다운 헤더 구조 보장)
            yield f"data: {json.dumps({'type': 'status', 'message': '질의어를 기반으로 Task를 만들고 있습니다...'})}\n\n"
            structured_context = _ensure_markdown_structure(context_text, topic)
            logger.info(f"📐 [ReAct] 구조화 완료: {len(structured_context)}자 (원본: {len(context_text)}자)")
            
            yield f"data: {json.dumps({'type': 'status', 'message': '질의어를 재구성했습니다.'})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': '질의어를 기반으로 검색 전략을 수립했습니다.'})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'PPT 콘텐츠를 구조화하고 있습니다...'})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': f'컨텍스트 구조화 완료 ({len(structured_context)}자)'})}\n\n"
            
            # 🧠 Unified Agent (Quick + ReAct) 실행
            try:
                yield f"data: {json.dumps({'type': 'status', 'message': 'PPT 파일을 생성하고 있습니다...'})}\n\n"
                
                result = await unified_presentation_agent.run(
                    mode="quick",
                    pattern="tool_calling",
                    topic=topic,
                    context_text=structured_context,
                    max_slides=req.max_slides,
                    run_id=run_id,
                )

                # Fallback: if tool calling isn't supported by the selected model/provider,
                # retry with legacy react to preserve UX.
                if not result.get("success") and isinstance(result.get("error"), str):
                    err = result.get("error") or ""
                    if "does not support tool calling" in err or "bind_tools" in err:
                        logger.warning(f"⚠️ [Quick] tool_calling not available; falling back to react: {err}")
                        result = await unified_presentation_agent.run(
                            mode="quick",
                            pattern="react",
                            topic=topic,
                            context_text=structured_context,
                            max_slides=req.max_slides,
                            run_id=run_id,
                        )
                
                # 결과 확인
                if result.get("success"):
                    file_path = result.get("file_path")
                    file_name = result.get("file_name")
                    slide_count = result.get("slide_count", 0)
                    
                    # file_path에서 file_name 추출 (폴백)
                    if file_path and not file_name:
                        file_name = os.path.basename(file_path)
                    
                    if file_name:
                        file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name)}"
                        logger.info(f"📦 [QuickReAct] PPT 생성 완료 - 파일: {file_name}")
                        
                        # 최종 상태 메시지
                        yield f"data: {json.dumps({'type': 'status', 'message': f'PPT 생성 완료 ({file_name})'})}\n\n"
                        
                        response_data: Dict[str, Any] = {
                            'type': 'complete',
                            'file_url': file_url,
                            'file_name': file_name,
                            'agent_type': 'ReAct',
                            'slide_count': slide_count,
                            'iterations': result.get("iterations", 0),
                            'tools_used': result.get("tools_used", []),
                            'run_id': result.get('run_id') or run_id,
                            'trace_id': result.get('trace_id') or run_id,
                        }
                        
                        if result.get("final_answer"):
                            response_data['agent_summary'] = result["final_answer"]
                        
                        if referenced_documents:
                            response_data['referenced_documents'] = referenced_documents
                        
                        yield f"data: {json.dumps(response_data)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent가 파일 생성에 실패했습니다'})}\n\n"
                else:
                    error_msg = result.get("error", "Agent 실행 중 오류 발생")
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    
            except Exception as agent_error:
                logger.error(f"❌ [ReAct] Agent 실행 오류: {agent_error}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': f'Agent 오류: {str(agent_error)}'})}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"❌ [ReAct] 스트림 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")


# ===== /build-quick-react는 /build-quick으로 통합됨 =====
# 하위 호환성을 위해 리디렉트 엔드포인트 유지
@router.post(
    "/agent/presentation/build-quick-react",
    summary="🔄 [REDIRECT] → /agent/presentation/build-quick",
    description="이 엔드포인트는 /agent/presentation/build-quick으로 통합되었습니다."
)
async def build_presentation_quick_react_redirect(
    req: QuickPresentationBuildRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """build-quick으로 리디렉트"""
    return await build_presentation_quick(req, current_user, chat_manager)


class TemplatedPresentationBuildRequest(BaseModel):
    session_id: str
    source_message_id: Optional[str] = None
    message: Optional[str] = None
    template_id: str
    max_slides: int = 8
    presentation_type: str = "general"
    outline: Optional[Dict[str, Any]] = None
    slide_management: Optional[List[SlideManagementInfo]] = None
    object_mappings: Optional[List[Dict[str, Any]]] = None
    content_segments: Optional[List[Dict[str, Any]]] = None


@router.post(
    "/agent/presentation/build-with-template-react",
    summary="🎨 ReAct Agent 기반 Template PPT 생성",
    description="""
    **ReAct Agent** 패턴을 사용한 템플릿 기반 PPT 생성.
    
    LLM이 직접 도구를 선택하고 Thought → Action → Observation 루프를 통해 
    템플릿을 활용한 고품질 PPT를 생성합니다.
    
    **특징:**
    - outline_generation_tool: 구조화된 아웃라인 생성
    - template_analyzer_tool: 템플릿 구조 분석
    - content_mapping_tool: AI 기반 콘텐츠 매핑
    - templated_pptx_builder_tool: 템플릿 기반 빌드
    - ppt_quality_validator_tool: 품질 검증 (선택적)
    """
)
async def build_presentation_with_template_react(
    req: TemplatedPresentationBuildRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    """ReAct Agent 기반 Template PPT 생성"""
    async def stream():
        try:
            run_id = str(uuid.uuid4())
            yield f"data: {json.dumps({'type': 'start', 'agent_type': 'TemplatedReAct', 'run_id': run_id, 'trace_id': run_id})}\n\n"
            
            # 메시지 소스 추출
            topic = "발표자료"
            context_text = ""
            referenced_documents = None
            
            # 폴백 0: outline/content_segments에서 직접 컨텍스트 추출 (모달에서 전달된 경우)
            # Note: req.outline은 dict이므로 .get() 사용
            if req.outline:
                content_segments = req.outline.get('contentSegments') or req.outline.get('content_segments') or []
                if content_segments:
                    context_text = "\n\n".join([seg.get('content', '') for seg in content_segments if seg.get('content')])
                    if context_text and len(context_text.strip()) >= 50:
                        logger.info(f"✅ [TemplatedReAct] 폴백 0a: outline.contentSegments에서 컨텍스트 추출 (길이: {len(context_text)}자)")
                        topic = context_text[:80]
            
            # 폴백 0b: req.content_segments 직접 사용 (프론트엔드에서 별도 전달 시)
            if not context_text and req.content_segments:
                context_text = "\n\n".join([seg.get('content', '') for seg in req.content_segments if seg.get('content')])
                if context_text and len(context_text.strip()) >= 50:
                    logger.info(f"✅ [TemplatedReAct] 폴백 0b: req.content_segments에서 컨텍스트 추출 (길이: {len(context_text)}자)")
                    topic = context_text[:80]
            
            # 폴백 0c: req.message 직접 사용 (프론트엔드에서 AI 답변 전달 시)
            if not context_text and req.message and len(req.message.strip()) >= 50:
                logger.info(f"✅ [TemplatedReAct] 폴백 0c: req.message에서 컨텍스트 추출 (길이: {len(req.message)}자)")
                context_text = req.message
                topic = req.message[:80]
            
            # 🆕 폴백 0에서 context_text를 이미 확보했으면 Redis 조회 건너뛰기
            if context_text and len(context_text.strip()) >= 50:
                logger.info(f"✅ [TemplatedReAct] 컨텍스트 이미 확보됨 (길이: {len(context_text)}자) - Redis 조회 건너뜀")
            elif req.source_message_id:
                logger.info(f"🔍 [TemplatedReAct] 메시지 ID로 검색: {req.source_message_id}")
                logger.info(f"🔍 [TemplatedReAct] 세션 ID: {req.session_id}")
                
                source_msg = None
                msgs = []
                
                try:
                    source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id, db)
                    logger.info(f"🔍 [TemplatedReAct] 메시지 검색 완료: found={source_msg is not None}, total_msgs={len(msgs) if msgs else 0}")
                    
                    # 디버깅: 실제 메시지 ID 목록 출력
                    if not source_msg and msgs:
                        msg_ids = [getattr(m, 'message_id', 'N/A') for m in msgs[:10]]
                        logger.warning(f"⚠️ [TemplatedReAct] 메시지 미발견. 찾는 ID: {req.source_message_id}, 실제 ID 샘플: {msg_ids}")
                        # 사용자에게 즉시 안내
                        yield f"data: {json.dumps({'type': 'warning', 'message': '요청한 메시지를 찾을 수 없어 최근 대화를 사용합니다...'})}\n\n"
                except Exception as e:
                    logger.error(f"❌ [TemplatedReAct] 메시지 검색 오류: {e}")
                    # 검색 오류 시 폴백 시도 (바로 return하지 않음)
                
                if not source_msg:
                    # 폴백 1: req.message 사용
                    if req.message and len(req.message.strip()) >= 50:
                        logger.info(f"✅ [TemplatedReAct] 폴백 1: 요청 본문의 message 사용 (길이: {len(req.message)}자)")
                        topic = req.message[:80]
                        context_text = req.message
                    # 폴백 2: 세션 최근 메시지 사용
                    elif msgs and len(msgs) > 0:
                        logger.info(f"✅ [TemplatedReAct] 폴백 2: 세션 최근 메시지 사용")
                        # 가장 최근 assistant 메시지 찾기
                        for msg in reversed(msgs):
                            if msg.message_type == MessageType.ASSISTANT and len(msg.content.strip()) >= 50:
                                source_msg = msg
                                logger.info(f"✅ [TemplatedReAct] 대체 메시지 발견: {msg.message_id}")
                                break
                        if source_msg:
                            tpc, ctx, ref_docs = _compose_context_from_messages(source_msg, msgs)
                            topic, context_text, referenced_documents = (tpc or topic), (ctx or context_text), ref_docs
                        else:
                            # 최근 user + assistant 페어 사용
                            if len(msgs) >= 2:
                                recent_asst = msgs[-1] if msgs[-1].message_type == MessageType.ASSISTANT else None
                                if recent_asst and len(recent_asst.content.strip()) >= 50:
                                    topic = "발표자료"
                                    context_text = recent_asst.content
                                    logger.info(f"✅ [TemplatedReAct] 폴백 3: 최근 응답 사용 (길이: {len(context_text)}자)")
                    
                    # 모든 폴백 실패
                    if not context_text or len(context_text.strip()) < 50:
                        error_details = f"메시지 ID '{req.source_message_id[:20]}...' 조회 실패. 세션에 {len(msgs) if msgs else 0}개 메시지 존재."
                        logger.error(f"❌ [TemplatedReAct] 컨텍스트 부족: {error_details}")
                        error_msg = '먼저 문서 검색 질문을 하신 후 "📝 PPT 생성" 버튼을 눌러주세요. 현재 대화 세션을 확인해주세요.'
                        yield f"data: {json.dumps({'type': 'error', 'message': 'PPT 생성에 필요한 AI 답변을 찾을 수 없습니다.', 'details': error_msg})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                else:
                    tpc, ctx, ref_docs = _compose_context_from_messages(source_msg, msgs or [])
                    topic, context_text, referenced_documents = (tpc or topic), (ctx or context_text), ref_docs
            elif req.message:
                # 폴백: message 필드에서 컨텍스트 추출
                topic = req.message[:80]
                context_text = req.message
            elif not context_text:
                # 모든 폴백 실패 시에만 에러
                yield f"data: {json.dumps({'type': 'error', 'message': 'message or source_message_id required'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 컨텍스트 유효성 검증
            if not context_text or len(context_text.strip()) < 50:
                yield f"data: {json.dumps({'type': 'error', 'message': f'AI 답변 내용이 충분하지 않습니다 (현재: {len(context_text)}자). 최소 50자 이상의 답변이 필요합니다.'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            logger.info(f"🎨 [TemplatedReAct] Agent 실행 시작 - template: '{req.template_id}', topic: '{topic[:50]}'")
            logger.info(f"📝 [TemplatedReAct] 컨텍스트 길이: {len(context_text)}자")
            
            # 사용자에게 컨텍스트 확보 알림
            yield f"data: {json.dumps({'type': 'status', 'message': f'AI 답변 확보 완료 ({len(context_text)}자). 템플릿 PPT 생성을 시작합니다...'})}\n\n"
            
            # 콘텐츠 구조화
            yield f"data: {json.dumps({'type': 'status', 'message': '질의어를 기반으로 Task를 만들고 있습니다...'})}\n\n"
            structured_context = _ensure_markdown_structure(context_text, topic)
            
            yield f"data: {json.dumps({'type': 'status', 'message': '질의어를 재구성했습니다.'})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': '질의어를 기반으로 검색 전략을 수립했습니다.'})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'PPT 콘텐츠를 구조화하고 있습니다...'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'status', 'message': f'컨텍스트 구조화 완료 ({len(structured_context)}자)'})}\n\n"
            
            # 🎨 Unified Agent (Template + ReAct) 실행
            try:
                template_msg = f'템플릿 "{req.template_id}" 적용 시작...'
                yield f"data: {json.dumps({'type': 'status', 'message': template_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'status', 'message': 'AI가 템플릿 구조를 분석하고 콘텐츠를 생성 중입니다...'})}\n\n"
                yield f"data: {json.dumps({'type': 'status', 'message': '⏳ 이 작업은 1-2분 정도 소요될 수 있습니다. 잠시만 기다려주세요...'})}\n\n"
                
                # 🆕 백그라운드 태스크로 Agent 실행 + Heartbeat 유지
                import asyncio
                
                agent_task = asyncio.create_task(
                    unified_presentation_agent.run(
                        mode="template",
                        pattern="tool_calling",
                        topic=topic,
                        context_text=structured_context,
                        template_id=req.template_id,
                        max_slides=req.max_slides,
                        presentation_type=req.presentation_type,
                        user_id=current_user.id,  # 🆕 user_id 전달하여 user-specific 템플릿 접근
                        run_id=run_id,
                    )
                )
                
                # Heartbeat: Agent 실행 중 주기적으로 keep-alive 전송
                heartbeat_messages = [
                    "🔄 아웃라인을 생성하고 있습니다...",
                    "📊 템플릿 구조를 분석 중입니다...",
                    "🎨 콘텐츠를 슬라이드에 배치하고 있습니다...",
                    "📝 슬라이드 내용을 작성 중입니다...",
                    "✨ PPT 파일을 생성하고 있습니다...",
                    "🔍 품질을 검증하고 있습니다...",
                ]
                heartbeat_idx = 0
                
                while not agent_task.done():
                    # 5초마다 heartbeat 전송
                    await asyncio.sleep(5)
                    if not agent_task.done():
                        msg = heartbeat_messages[heartbeat_idx % len(heartbeat_messages)]
                        yield f"data: {json.dumps({'type': 'heartbeat', 'message': msg})}\n\n"
                        heartbeat_idx += 1
                
                # Agent 결과 가져오기
                result = await agent_task

                # Fallback to legacy react if tool calling isn't supported.
                if not result.get("success") and isinstance(result.get("error"), str):
                    err = result.get("error") or ""
                    if "does not support tool calling" in err or "bind_tools" in err:
                        logger.warning(f"⚠️ [TemplatedReAct] tool_calling not available; falling back to react: {err}")
                        result = await unified_presentation_agent.run(
                            mode="template",
                            pattern="react",
                            topic=topic,
                            context_text=structured_context,
                            template_id=req.template_id,
                            max_slides=req.max_slides,
                            presentation_type=req.presentation_type,
                            user_id=current_user.id,
                            run_id=run_id,
                        )
                
                # 결과 확인
                if result.get("success"):
                    file_path = result.get("file_path")
                    file_name = result.get("file_name")
                    slide_count = result.get("slide_count", 0)
                    
                    # file_path에서 file_name 추출 (폴백)
                    if file_path and not file_name:
                        file_name = os.path.basename(file_path)
                    
                    if file_name:
                        file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name)}"
                        logger.info(f"📦 [TemplatedReAct] PPT 생성 완료 - 파일: {file_name}")
                        
                        # 최종 상태 메시지
                        yield f"data: {json.dumps({'type': 'status', 'message': f'PPT 생성 완료 ({file_name})'})}\n\n"
                        
                        response_data: Dict[str, Any] = {
                            'type': 'complete',
                            'file_url': file_url,
                            'file_name': file_name,
                            'agent_type': 'TemplatedReAct',
                            'template_id': req.template_id,
                            'slide_count': slide_count,
                            'iterations': result.get("iterations", 0),
                            'tools_used': result.get("tools_used", []),
                            'run_id': result.get('run_id') or run_id,
                            'trace_id': result.get('trace_id') or run_id,
                        }
                        
                        if result.get("final_answer"):
                            response_data['agent_summary'] = result["final_answer"]
                        
                        if referenced_documents:
                            response_data['referenced_documents'] = referenced_documents
                        
                        yield f"data: {json.dumps(response_data)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent가 파일 생성에 실패했습니다'})}\n\n"
                else:
                    error_msg = result.get("error", "Agent 실행 중 오류 발생")
                    tools_used = result.get("tools_used", [])
                    iterations = result.get("iterations", 0)
                    detail_msg = f"{error_msg} (반복: {iterations}회, 사용 도구: {', '.join(tools_used) if tools_used else '없음'})"
                    yield f"data: {json.dumps({'type': 'error', 'message': detail_msg})}\n\n"
                    
            except Exception as agent_error:
                logger.error(f"❌ [TemplatedReAct] Agent 실행 오류: {agent_error}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': f'Agent 오류: {str(agent_error)}'})}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"❌ [TemplatedReAct] 스트림 오류: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post(
    "/agent/presentation/build-with-template-plan-execute",
    summary="🧠 Plan-and-Execute Agent 기반 Template PPT 생성",
    description="""
    **Plan-and-Execute Agent** 패턴을 사용한 템플릿 기반 PPT 생성.
    
    **특징:**
    - Planning Phase: AI가 전체 워크플로우를 사전 계획
    - Execution Phase: 계획을 순차적으로 실행
    - Re-planning: 실패 시 동적 재계획
    - LangGraph 기반으로 ReAct보다 효율적
    
    **도구:**
    - outline_generation_tool
    - template_analyzer_tool
    - content_mapping_tool
    - templated_pptx_builder_tool
    - ppt_quality_validator_tool
    """
)
async def build_presentation_with_template_plan_execute(
    req: TemplatedPresentationBuildRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    """Plan-and-Execute Agent 기반 Template PPT 생성"""
    async def stream():
        try:
            run_id = str(uuid.uuid4())
            yield f"data: {json.dumps({'type': 'start', 'agent_type': 'PlanExecute', 'run_id': run_id, 'trace_id': run_id})}\n\n"
            
            # 메시지 소스 추출
            topic = "발표자료"
            context_text = ""
            referenced_documents = None
            
            if req.source_message_id:
                logger.info(f"🔍 [PlanExecute] 메시지 ID로 검색: {req.source_message_id}")
                source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id, db)
                
                if not source_msg:
                    if req.message:
                        logger.info(f"✅ [PlanExecute] 폴백으로 요청 본문의 message 사용")
                        topic = req.message[:80]
                        context_text = req.message
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'source_message_id를 찾을 수 없습니다'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                else:
                    tpc, ctx, ref_docs = _compose_context_from_messages(source_msg, msgs or [])
                    topic, context_text, referenced_documents = (tpc or topic), (ctx or context_text), ref_docs
            elif req.message:
                topic = req.message[:80]
                context_text = req.message
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'message or source_message_id required'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 컨텍스트 유효성 검증
            if not context_text or len(context_text.strip()) < 50:
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI 답변 내용이 충분하지 않습니다.'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            logger.info(f"🧠 [PlanExecute] Agent 실행 시작 - template: '{req.template_id}'")
            
            # 콘텍스트 구조화
            structured_context = _ensure_markdown_structure(context_text, topic)
            
            yield f"data: {json.dumps({'type': 'agent_thinking', 'message': 'Plan-and-Execute Agent가 계획을 수립하고 있습니다...'})}\n\n"
            
            # 🧠 Unified Agent (Template + Plan-Execute) 실행
            try:
                result = await unified_presentation_agent.run(
                    mode="template",
                    pattern="plan_execute",
                    topic=topic,
                    context_text=structured_context,
                    template_id=req.template_id,
                    max_slides=req.max_slides,
                    user_id=current_user.id,  # 🆕 user_id 전달하여 user-specific 템플릿 접근
                    run_id=run_id,
                )
                
                # 결과 확인
                if result.get("success"):
                    file_path = result.get("file_path")
                    if file_path:
                        file_name = os.path.basename(file_path)
                        file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name)}"
                        logger.info(f"📦 [PlanExecute] PPT 생성 완료 - 파일: {file_name}")
                        
                        response_data: Dict[str, Any] = {
                            'type': 'complete',
                            'file_url': file_url,
                            'file_name': file_name,
                            'agent_type': 'PlanExecute',
                            'template_id': req.template_id,
                            'execution_metadata': result.get("execution_metadata", {}),
                            'plan_steps': len(result.get("plan", [])),
                            'run_id': result.get('run_id') or run_id,
                            'trace_id': result.get('trace_id') or run_id,
                        }
                        
                        if result.get("validation_result"):
                            response_data['validation_result'] = result["validation_result"]
                        
                        if referenced_documents:
                            response_data['referenced_documents'] = referenced_documents
                        
                        yield f"data: {json.dumps(response_data)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent가 파일 생성에 실패했습니다'})}\n\n"
                else:
                    error_msg = result.get("error", "Agent 실행 중 오류 발생")
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    
            except Exception as agent_error:
                logger.error(f"❌ [PlanExecute] Agent 실행 오류: {agent_error}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': f'Agent 오류: {str(agent_error)}'})}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"❌ [PlanExecute] 스트림 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post(
    "/agent/presentation/build-with-template",
    deprecated=True,
    summary="⚠️ [DEPRECATED] Template-based PPT Generation",
    description="""
    **DEPRECATED**: This endpoint is deprecated and will be removed in a future release.
    
    **Migration**: Use `POST /api/v1/agent/presentation/build-with-template-react` instead.
    
    See PRESENTATION_API_MIGRATION_GUIDE.md for details.
    """
)
async def build_presentation_with_template(
    req: TemplatedPresentationBuildRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    async def stream():
        try:
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            if not req.outline or not req.template_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'outline and template_id are required'})}\n\n"; yield "data: [DONE]\n\n"; return
            tpl = template_manager.get_template_details(req.template_id)
            if not tpl:
                yield f"data: {json.dumps({'type': 'error', 'message': 'template not found'})}\n\n"; yield "data: [DONE]\n\n"; return
            template_path = tpl.get('cleaned_template_path') or tpl.get('path')
            if not template_path or not os.path.exists(template_path):
                yield f"data: {json.dumps({'type': 'error', 'message': 'template file missing'})}\n\n"; yield "data: [DONE]\n\n"; return
            yield f"data: {json.dumps({'type': 'outline_ready'})}\n\n"
            yield f"data: {json.dumps({'type': 'template_loading'})}\n\n"
            
            # 아웃라인을 DeckSpec으로 변환
            deck = templated_ppt_service._parse_ai_response(json.dumps(req.outline), req.outline.get('topic', '발표자료'), 'business')
            if not deck:
                # 폴백: 직접 DeckSpec 생성
                from app.services.presentation.ppt_models import SlideSpec, DeckSpec
                slides = []
                for slide_data in req.outline.get('slides', []):
                    # DiagramData 변환 로직 추가
                    diagram_data = None
                    if slide_data.get('diagram'):
                        from app.services.presentation.ppt_models import DiagramData, ChartData
                        d_raw = slide_data.get('diagram')
                        chart_data = None
                        if d_raw.get('chart'):
                            c_raw = d_raw.get('chart')
                            chart_data = ChartData(
                                type=c_raw.get('type', 'column'),
                                title=c_raw.get('title', ''),
                                categories=c_raw.get('categories', []),
                                series=c_raw.get('series', [])
                            )
                        diagram_data = DiagramData(
                            type=d_raw.get('type', 'none'),
                            data=d_raw.get('data'),
                            chart=chart_data
                        )

                    slides.append(SlideSpec(
                        title=slide_data.get('title', '제목'),
                        key_message=slide_data.get('key_message', ''),
                        bullets=slide_data.get('bullets', []),
                        layout=slide_data.get('layout', 'title-and-content'),
                        diagram=diagram_data
                    ))
                deck = DeckSpec(topic=req.outline.get('topic', '발표자료'), slides=slides, max_slides=len(slides))
            
            yield f"data: {json.dumps({'type': 'building'})}\n\n"
            
            # Extract mappings and slide management from outline if available
            text_box_mappings = req.object_mappings or req.outline.get('object_mappings') or req.outline.get('textBoxMappings')
            content_segments = req.content_segments or req.outline.get('contentSegments')
            slide_management_info = req.outline.get('slide_management')
            
            # Use enhanced build method with slide management for proper template application
            file_path = templated_ppt_service.build_enhanced_pptx_with_slide_management(
                deck,
                custom_template_path=template_path,
                text_box_mappings=text_box_mappings,
                content_segments=content_segments,
                slide_management=slide_management_info
            )
            file_name_only = os.path.basename(file_path)
            file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name_only)}"
            yield f"data: {json.dumps({'type': 'complete', 'file_url': file_url, 'file_name': file_name_only})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"; yield "data: [DONE]\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post(
    "/agent/presentation/build",
    deprecated=True,
    summary="⚠️ [DEPRECATED] Build from Outline",
    description="""
    **DEPRECATED**: This endpoint is deprecated and will be removed in a future release.
    
    **Migration**: Use `POST /api/v1/presentation/agent/generate` instead.
    
    See PRESENTATION_API_MIGRATION_GUIDE.md for details.
    """
)
async def build_presentation_from_outline(
    req: PresentationBuildRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    try:
        source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id, db)
        referenced_documents: Optional[List[Dict[str, Any]]] = None
        document_filename: Optional[str] = None
        if not source_msg and not req.outline:
            logger.warning("⚠️ source_message_id not found and no outline provided → fallback context + AI outline")
            topic, context_text, document_filename = await _compose_fallback_context(chat_manager, req.session_id, req.title, req.message)
            deck = await templated_ppt_service.generate_enhanced_outline(
                topic=topic,
                context_text=context_text,
                provider=req.provider or 'bedrock',
                document_filename=document_filename,
                presentation_type='general'
            )
        elif not source_msg and req.outline:
            from json import dumps as _d
            deck = templated_ppt_service._parse_outline(_d(req.outline), req.title or '발표자료')
        else:
            topic, context_text, referenced_documents = _compose_context_from_messages(source_msg, msgs)
            document_filename = _extract_document_filename(referenced_documents)
            if req.title:
                topic = req.title
            deck = await templated_ppt_service.generate_enhanced_outline(
                topic=topic,
                context_text=context_text,
                provider=req.provider or 'bedrock',
                document_filename=document_filename,
                presentation_type='general'
            )
        custom_template_path = None
        user_template_id = None
        if req.template_id:
            tpl = template_manager.get_template_details(req.template_id)
            if tpl:
                user_template_id = tpl.get('dynamic_template_id')
                custom_template_path = tpl.get('cleaned_template_path') or tpl.get('path')
        file_path = templated_ppt_service.build_enhanced_pptx_with_slide_management(
            deck,
            file_basename=req.file_basename,
            custom_template_path=custom_template_path,
            user_template_id=user_template_id,
            text_box_mappings=req.object_mappings,
            content_segments=req.content_segments,
            slide_management=[sm if isinstance(sm, dict) else sm.dict() for sm in (req.slide_management or [])]
        )
        return {"success": True, "file_url": f"/api/v1/agent/presentation/download/{urllib.parse.quote(os.path.basename(file_path))}", "file_name": os.path.basename(file_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- New Models for Template-First Workflow ---
class GenerateContentRequest(BaseModel):
    user_query: str
    context: Optional[str] = ""
    session_id: Optional[str] = None  # 채팅 세션 ID (컨텍스트 수집용)
    container_ids: Optional[List[str]] = None  # 문서 컨테이너 IDs (RAG 검색용)
    use_rag: bool = True  # RAG 검색 활성화 여부
    use_ai_first: bool = True  # 🆕 AI-First 파이프라인 사용 여부 (기본값: True)

class SlideElementData(BaseModel):
    id: str
    text: Optional[str]

class SlideContentData(BaseModel):
    index: int
    role: Optional[str] = None
    elements: List[SlideElementData]
    note: Optional[str] = None

# 🆕 v3.4: 슬라이드 대체 정보
class SlideReplacementData(BaseModel):
    original: int  # 원본 슬라이드 번호 (1-based)
    replacement: int  # 대체 슬라이드 번호 (1-based)
    reason: Optional[str] = None  # 대체 사유

class BuildFromDataRequest(BaseModel):
    slides: List[SlideContentData]
    output_filename: Optional[str] = "presentation"
    session_id: Optional[str] = None  # 🆕 wizard state lookup key
    slide_replacements: Optional[List[SlideReplacementData]] = None  # 🆕 v3.4
    content_plan: Optional[Dict[str, Any]] = None  # 🆕 v3.8: 동적 슬라이드
    dynamic_slides: Optional[Dict[str, Any]] = None  # 🆕 v3.8: 동적 슬라이드 (mode, add_slides, remove_slides)

@router.post("/agent/presentation/templates/{template_id}/generate-content")
async def generate_template_content(
    template_id: str,
    request: GenerateContentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    템플릿 구조에 맞는 콘텐츠 생성 (Unified Agent 아키텍처)
    
    Agent가 다음 도구들을 순차 실행:
    1. template_analyzer_tool: 템플릿 구조 분석
    2. outline_generation_tool: RAG 기반 콘텐츠 생성
    3. slide_type_matcher_tool: AI-템플릿 슬라이드 매칭
    4. content_mapping_tool: 콘텐츠-텍스트박스 매핑
    """
    try:
        from app.agents.presentation.ppt_wizard_checkpoint import (
            ensure_saved as wizard_cp_ensure_saved,
            is_enabled as wizard_cp_is_enabled,
            make_thread_id as wizard_cp_make_thread_id,
        )
        from app.services.presentation.ppt_wizard_store import PPTWizardKey, ppt_wizard_store

        user_id = str(current_user.emp_no) if hasattr(current_user, 'emp_no') else str(current_user.id)
        
        logger.info(f"📊 PPT 콘텐츠 생성 요청 (Agent): template={template_id}, user={user_id}, use_rag={request.use_rag}, use_ai_first={request.use_ai_first}")
        
        # Agent 아키텍처로 전환: unified_presentation_agent 사용
        result = await unified_presentation_agent.generate_content_for_template(
            template_id=template_id,
            user_query=request.user_query,
            context=request.context or "",
            user_id=user_id,
            session_id=request.session_id,
            container_ids=request.container_ids,
            use_rag=request.use_rag,
            use_ai_first=request.use_ai_first,  # 🆕 AI-First 파이프라인 옵션
        )
        
        if not result.get("success", False):
            error_msg = result.get("error", "콘텐츠 생성 실패")
            logger.error(f"Content generation failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        # Phase 2: persist wizard artifacts via LangGraph checkpointer (preferred).
        if request.session_id and wizard_cp_is_enabled():
            try:
                thread_id = wizard_cp_make_thread_id(
                    user_id=str(current_user.id),
                    session_id=request.session_id,
                    template_id=template_id,
                )

                await wizard_cp_ensure_saved(
                    thread_id=thread_id,
                    state={
                        "user_id": str(current_user.id),
                        "session_id": request.session_id,
                        "template_id": template_id,
                        "thread_id": thread_id,
                        "pipeline": result.get("pipeline") or ("ai_first" if request.use_ai_first else "legacy"),
                        "deck_spec": result.get("deck_spec"),
                        "slide_matches": result.get("slide_matches"),
                        "mappings": result.get("mappings"),
                        # AI-first extras (safe even if None)
                        "slide_replacements": result.get("slide_replacements"),
                        "content_plan": result.get("content_plan"),
                        "dynamic_slides": result.get("dynamic_slides"),
                        "presentation_title": result.get("presentation_title"),
                    },
                )

                # Surface the thread_id to the caller (no UX change required; additive field).
                if isinstance(result, dict):
                    result["thread_id"] = thread_id
            except Exception as e:
                logger.warning(f"🧩 LangGraph wizard checkpoint save failed (fallback to Redis): {e}")

        # Optional legacy fallback: persist wizard artifacts for follow-up build-from-data calls.
        if request.session_id:
            try:
                await ppt_wizard_store.save(
                    key=PPTWizardKey(
                        user_id=str(current_user.id),
                        session_id=request.session_id,
                        template_id=template_id,
                    ),
                    state={
                        "template_id": template_id,
                        "deck_spec": result.get("deck_spec"),
                        "slide_matches": result.get("slide_matches"),
                        "mappings": result.get("mappings"),
                        # AI-first extras
                        "slide_replacements": result.get("slide_replacements"),
                        "content_plan": result.get("content_plan"),
                        "dynamic_slides": result.get("dynamic_slides"),
                    },
                )
            except Exception as e:
                logger.warning(f"🧠 PPT wizard state save failed: {e}")
        
        return JSONResponse(result)
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Content generation failed (ValueError): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Content generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"콘텐츠 생성 실패: {str(e)}")

@router.post("/agent/presentation/templates/{template_id}/build-from-data")
async def build_ppt_from_data(
    template_id: str,
    request: BuildFromDataRequest,
    current_user: User = Depends(get_current_user)
):
    """
    사용자 편집 데이터로 PPT 생성 (Unified Agent 아키텍처)
    
    Agent가 templated_pptx_builder_tool을 사용하여 PPT 생성.
    템플릿 스타일을 완전히 보존하면서 콘텐츠만 교체.
    """
    try:
        from app.agents.presentation.ppt_wizard_checkpoint import (
            load as wizard_cp_load,
            update as wizard_cp_update,
            is_enabled as wizard_cp_is_enabled,
            make_thread_id as wizard_cp_make_thread_id,
        )
        from app.services.presentation.ppt_wizard_store import PPTWizardKey, ppt_wizard_store

        # Convert Pydantic models to dict
        slides_data = [s.dict() for s in request.slides]
        
        # user_id passed to help find user-specific templates
        user_id = str(current_user.emp_no) if hasattr(current_user, 'emp_no') else str(current_user.id)
        
        logger.info(f"🏗️ PPT 빌드 요청 (Agent): template={template_id}, user={user_id}, slides={len(slides_data)}")

        # Phase 2: load prior wizard artifacts from LangGraph checkpointer (preferred).
        wizard_state = None
        thread_id = None
        if request.session_id and wizard_cp_is_enabled():
            try:
                thread_id = wizard_cp_make_thread_id(
                    user_id=str(current_user.id),
                    session_id=request.session_id,
                    template_id=template_id,
                )
                wizard_state = await wizard_cp_load(thread_id=thread_id)
            except Exception as e:
                logger.warning(f"🧩 LangGraph wizard checkpoint load failed (fallback to Redis): {e}")

        # Legacy fallback: load prior wizard artifacts from Redis.
        if wizard_state is None and request.session_id:
            try:
                wizard_state = await ppt_wizard_store.load(
                    key=PPTWizardKey(
                        user_id=str(current_user.id),
                        session_id=request.session_id,
                        template_id=template_id,
                    )
                )
            except Exception as e:
                logger.warning(f"🧠 PPT wizard state load failed: {e}")
        
        # 🆕 v3.4: slide_replacements 처리
        slide_replacements = None
        if request.slide_replacements:
            slide_replacements = [sr.dict() for sr in request.slide_replacements]
            logger.info(f"  🔄 슬라이드 대체 요청: {len(slide_replacements)}개")
        
        # 🆕 v3.8: dynamic_slides 처리
        dynamic_slides = None
        if request.dynamic_slides:
            dynamic_slides = request.dynamic_slides
            # 딕셔너리인 경우에만 get 사용
            if isinstance(dynamic_slides, dict):
                logger.info(f"  📐 동적 슬라이드 요청: mode={dynamic_slides.get('mode')}")
            else:
                logger.info(f"  📐 동적 슬라이드 요청: {type(dynamic_slides)}")
        
        # Agent 아키텍처로 전환: unified_presentation_agent 사용
        # Prefer request-provided advanced options; otherwise, reuse saved AI-first extras.
        slide_replacements_effective = slide_replacements or (wizard_state or {}).get("slide_replacements")
        content_plan_effective = request.content_plan or (wizard_state or {}).get("content_plan")
        dynamic_slides_effective = dynamic_slides or (wizard_state or {}).get("dynamic_slides")

        result = await unified_presentation_agent.build_ppt_from_ui_data(
            template_id=template_id,
            slides_data=slides_data,
            output_filename=request.output_filename,
            user_id=user_id,
            session_id=request.session_id,
            deck_spec=(wizard_state or {}).get("deck_spec"),
            slide_matches=(wizard_state or {}).get("slide_matches"),
            mappings=(wizard_state or {}).get("mappings"),
            slide_replacements=slide_replacements_effective,  # 🆕 v3.4
            content_plan=content_plan_effective,              # 🆕 v3.8
            dynamic_slides=dynamic_slides_effective,          # 🆕 v3.8
        )
        
        if not result.get("success", False):
            error_msg = result.get("error", "PPT 빌드 실패")
            logger.error(f"PPT build failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        file_path = result.get("file_path")
        file_name = result.get("file_name")

        # Phase 2: persist build outputs back to the checkpointer.
        if thread_id and wizard_cp_is_enabled():
            try:
                await wizard_cp_update(
                    thread_id=thread_id,
                    values={
                        "file_path": file_path,
                        "file_name": file_name,
                        "slide_count": result.get("slide_count"),
                        # Keep latest artifacts for potential re-builds.
                        "deck_spec": (wizard_state or {}).get("deck_spec"),
                        "slide_matches": (wizard_state or {}).get("slide_matches"),
                        "mappings": (wizard_state or {}).get("mappings"),
                        "slide_replacements": slide_replacements_effective,
                        "content_plan": content_plan_effective,
                        "dynamic_slides": dynamic_slides_effective,
                    },
                )
            except Exception as e:
                logger.warning(f"🧩 LangGraph wizard checkpoint update failed: {e}")
        
        # Generate download URL
        download_url = f"/api/v1/agent/presentation/download/{file_name}"
        
        response_payload = {
            "file_url": download_url,
            "file_path": file_path,
            "file_name": file_name,
            "run_id": result.get("run_id") or result.get("execution_id"),
            "trace_id": result.get("trace_id") or result.get("execution_id"),
        }
        if thread_id:
            response_payload["thread_id"] = thread_id
        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PPT build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
# ----------------------------------------------


# ===== Generated file download =====
@router.get("/agent/presentation/download/{filename}")
async def download_presentation_file(
    filename: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    import posixpath
    import urllib.parse
    
    # Manual Authentication Logic
    user = None
    try:
        # 1. Try query param token
        if token:
            token_data = AuthUtils.verify_token(token)
            user_service = AsyncUserService(db)
            user = await user_service.get_user_by_emp_no(token_data.emp_no)
        
        # 2. Try Authorization header if no user yet
        if not user:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                header_token = auth_header.split(" ")[1]
                token_data = AuthUtils.verify_token(header_token)
                user_service = AsyncUserService(db)
                user = await user_service.get_user_by_emp_no(token_data.emp_no)
    except Exception as e:
        logger.warning(f"📥 다운로드 인증 실패: {e}")
        # Don't raise immediately, let the check below handle it
        
    if not user:
        raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")
        
    try:
        logger.info(f"📥 PPT 다운로드 요청: 원본 파일명='{filename}', 사용자='{user.username}'")
        
        # URL 디코딩 처리
        try:
            decoded_filename = urllib.parse.unquote(filename)
            logger.info(f"📥 URL 디코딩 완료: '{decoded_filename}'")
        except Exception as decode_err:
            logger.warning(f"📥 URL 디코딩 실패, 원본 사용: {decode_err}")
            decoded_filename = filename
        
        safe_name = os.path.basename(posixpath.normpath(decoded_filename))
        logger.info(f"📥 안전한 파일명: '{safe_name}' (원본: '{decoded_filename}')")
        
        # 경로 조작 시도 검증 (../ 등)
        if ".." in decoded_filename or "/" in safe_name:
            logger.error(f"📥 경로 조작 시도 감지: '{decoded_filename}'")
            raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
        
        if not safe_name.lower().endswith(".pptx"):
            logger.error(f"📥 파일 형식 검증 실패: '{safe_name}'")
            raise HTTPException(status_code=400, detail="허용되지 않은 파일 형식입니다.")
        
        from app.core.config import settings
        upload_dir = settings.resolved_upload_dir
        
        # 여러 경로에서 파일 검색 (기존 download_pptx 함수 로직 통합)
        search_roots = [upload_dir, file_manager.pptx_dir]
        final_path = None
        for root in search_roots:
            candidate = root / safe_name
            if candidate.is_file():
                final_path = candidate
                break
        
        logger.info(f"📥 파일 경로: '{final_path}'")
        
        if not final_path or not os.path.exists(final_path):
            logger.error(f"📥 파일을 찾을 수 없음: '{final_path}'")
            logger.error(f"📥 업로드 디렉토리: '{upload_dir}'")
            # 디렉토리 내 파일 목록 확인
            try:
                files_in_dir = os.listdir(upload_dir)
                logger.error(f"📥 업로드 디렉토리 파일 목록 ({len(files_in_dir)}개):")
                for f in files_in_dir[-10:]:  # 최근 10개만 표시
                    logger.error(f"  - {f}")
            except Exception as list_err:
                logger.error(f"📥 디렉토리 목록 조회 실패: {list_err}")
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {safe_name}")
        def generate():
            with open(final_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
        return StreamingResponse(
            generate(),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(safe_name)}"}
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="파일 다운로드 중 오류가 발생했습니다")


# ===== PPT Preview URL Generation (S3 + Office Online Viewer) =====
@router.get(
    "/agent/presentation/preview-url/{filename}",
    summary="PPT 미리보기 URL 생성 (Office Online Viewer용)",
    description="""
    생성된 PPT 파일을 S3에 업로드하고 Office Online Viewer에서 사용할 수 있는 URL을 반환합니다.
    
    **반환값:**
    - `preview_url`: Office Online Viewer iframe용 URL
    - `direct_url`: 직접 다운로드 URL (S3 presigned)
    - `expires_in`: URL 만료 시간 (초)
    """
)
async def get_presentation_preview_url(
    filename: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """PPT 파일을 S3에 업로드하고 Office Online Viewer URL 생성"""
    import posixpath
    from app.services.core.aws_service import S3Service
    
    # 인증 처리
    user = None
    try:
        if token:
            token_data = AuthUtils.verify_token(token)
            user_service = AsyncUserService(db)
            user = await user_service.get_user_by_emp_no(token_data.emp_no)
        
        if not user:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                header_token = auth_header.split(" ")[1]
                token_data = AuthUtils.verify_token(header_token)
                user_service = AsyncUserService(db)
                user = await user_service.get_user_by_emp_no(token_data.emp_no)
    except Exception as e:
        logger.warning(f"📥 미리보기 URL 인증 실패: {e}")
        
    if not user:
        raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")
    
    try:
        # URL 디코딩
        decoded_filename = urllib.parse.unquote(filename)
        safe_name = os.path.basename(posixpath.normpath(decoded_filename))
        
        # 보안 검증
        if ".." in decoded_filename or "/" in safe_name:
            raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
        
        if not safe_name.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail="허용되지 않은 파일 형식입니다.")
        
        # 로컬 파일 경로 확인
        upload_dir = settings.resolved_upload_dir
        local_path = upload_dir / safe_name
        
        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {safe_name}")
        
        # S3에 업로드
        s3_service = S3Service()
        s3_key = f"presentations/preview/{user.emp_no}/{safe_name}"
        
        with open(local_path, "rb") as f:
            file_data = f.read()
        
        s3_service.s3_client.put_object(
            Bucket=s3_service.bucket_name,
            Key=s3_key,
            Body=file_data,
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            # ACL을 public-read로 설정하거나, presigned URL 사용
        )
        
        logger.info(f"✅ PPT S3 업로드 완료: {s3_key}")
        
        # Presigned URL 생성 (1시간 유효)
        expires_in = 3600
        direct_url = s3_service.generate_presigned_url(
            object_key=s3_key,
            expires_in=expires_in,
            response_content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        
        # Office Online Viewer URL 생성
        # Microsoft Office Online Viewer: https://view.officeapps.live.com/op/embed.aspx?src=<encoded_url>
        # Google Docs Viewer: https://docs.google.com/gview?url=<encoded_url>&embedded=true
        encoded_direct_url = urllib.parse.quote(direct_url, safe='')
        
        # Office Online Viewer (Microsoft)
        office_preview_url = f"https://view.officeapps.live.com/op/embed.aspx?src={encoded_direct_url}"
        
        # Google Docs Viewer (대안)
        google_preview_url = f"https://docs.google.com/gview?url={encoded_direct_url}&embedded=true"
        
        return {
            "success": True,
            "filename": safe_name,
            "preview_url": office_preview_url,  # Office Online 기본
            "google_preview_url": google_preview_url,  # Google Docs 대안
            "direct_url": direct_url,
            "expires_in": expires_in,
            "s3_key": s3_key
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 미리보기 URL 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"미리보기 URL 생성 실패: {str(e)}")


@router.post("/agent/presentation/migrate-templates", summary="기존 템플릿 마이그레이션")
async def migrate_existing_templates(current_user: User = Depends(get_current_user)):
    try:
        logger.info("템플릿 마이그레이션 요청 시작")
        result = template_migration_service.migrate_existing_templates()
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"마이그레이션 실패: {e}")
        raise HTTPException(status_code=500, detail=f"마이그레이션 실패: {str(e)}")


@router.get("/agent/presentation/migration-status", summary="템플릿 마이그레이션 상태 확인")
async def check_migration_status():
    try:
        status = template_migration_service.check_migration_status()
        return {"success": True, "status": status}
    except Exception as e:
        logger.error(f"상태 확인 실패: {e}")
        raise HTTPException(status_code=500, detail=f"상태 확인 실패: {str(e)}")


@router.post("/agent/presentation/debug-template", summary="템플릿 디버깅")
async def debug_template(template_id: str):
    try:
        logger.info(f"템플릿 디버깅 요청: {template_id}")
        template_details = template_manager.get_template_details(template_id)
        if not template_details:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
        template_path = template_details.get('path')
        if not template_path:
            raise HTTPException(status_code=400, detail="템플릿 파일 경로가 없습니다")
        debug_info = template_debugger.debug_template(template_path)
        return {
            "success": True,
            "template_id": template_id,
            "template_path": template_path,
            "debug_info": debug_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"템플릿 디버깅 실패: {e}")
        raise HTTPException(status_code=500, detail=f"디버깅 실패: {str(e)}")


# ===== Agent-Based Presentation Generation =====

class AgentPresentationRequest(BaseModel):
    """Agent-based presentation generation request."""
    mode: str  # "quick" or "enhanced"
    topic: str
    context_text: str
    max_slides: Optional[int] = 10
    template_path: Optional[str] = None
    visualization_hints: Optional[bool] = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "mode": "quick",
                "topic": "AI in Healthcare",
                "context_text": "Recent advances in AI have transformed medical diagnostics...",
                "max_slides": 10,
                "visualization_hints": True
            }
        }


class AgentPresentationResponse(BaseModel):
    """Agent-based presentation generation response."""
    success: bool
    file_path: Optional[str] = None
    slide_count: Optional[int] = None
    mode: str
    strategy: Optional[str] = None
    execution_time: Optional[float] = None
    steps: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


@router.post(
    "/agent/generate",
    response_model=AgentPresentationResponse,
    summary="[DEPRECATED] 🤖 Agent-Based PPT Generation",
    deprecated=True
)
async def generate_presentation_with_agent(
    request: AgentPresentationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    [DEPRECATED] This legacy endpoint has been removed.
    
    Please use one of the following endpoints instead:
    - /api/v1/agent/presentation/build-quick (Quick PPT)
    - /api/v1/agent/presentation/build-unified (Unified Agent)
    """
    raise HTTPException(
        status_code=410,
        detail={
            "error": "This endpoint has been deprecated and removed.",
            "alternatives": [
                "/api/v1/agent/presentation/build-quick",
                "/api/v1/agent/presentation/build-unified"
            ],
            "message": "Please use the new unified agent endpoints for presentation generation."
        }
    )


# ========================================
# 🚀 Unified Agent API (NEW)
# ========================================

class UnifiedPresentationRequest(BaseModel):
    """통합 프레젠테이션 생성 요청"""
    session_id: str
    source_message_id: Optional[str] = None
    message: Optional[str] = None
    mode: str = "quick"  # "quick" | "template"
    pattern: str = "tool_calling"  # "tool_calling" | "react" | "plan_execute"
    template_id: Optional[str] = None
    max_slides: int = 8


@router.post(
    "/agent/presentation/build-unified",
    summary="🚀 통합 에이전트 기반 PPT 생성",
    description="""
    **Unified Presentation Agent**: Quick PPT와 Template PPT를 하나의 엔드포인트로 통합.
    
    **Parameters:**
    - `mode`: "quick" (빠른 생성) | "template" (템플릿 기반)
    - `pattern`: "react" (ReAct 패턴) | "plan_execute" (Plan-and-Execute 패턴)
    - `template_id`: 템플릿 ID (mode="template"인 경우 필수)
    
    **Examples:**
    - Quick PPT with ReAct: `mode=quick, pattern=react`
    - Template PPT with ReAct: `mode=template, pattern=react, template_id=xxx`
    - Template PPT with Plan-Execute: `mode=template, pattern=plan_execute, template_id=xxx`
    
    **Migration from legacy endpoints:**
    - `/build-quick` → `/build-unified?mode=quick&pattern=react`
    - `/build-with-template-react` → `/build-unified?mode=template&pattern=react`
    - `/build-with-template-plan-execute` → `/build-unified?mode=template&pattern=plan_execute`
    """
)
async def build_presentation_unified(
    req: UnifiedPresentationRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """통합 에이전트 기반 PPT 생성"""
    async def stream():
        try:
            run_id = str(uuid.uuid4())
            yield f"data: {json.dumps({'type': 'start', 'mode': req.mode, 'pattern': req.pattern, 'run_id': run_id, 'trace_id': run_id})}\n\n"
            
            # 메시지 소스 추출
            topic = "발표자료"
            context_text = ""
            referenced_documents = None
            
            if req.source_message_id:
                logger.info(f"🔍 [Unified] 메시지 ID로 검색: {req.source_message_id}")
                source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id)
                
                if not source_msg:
                    if req.message:
                        logger.info(f"✅ [Unified] 폴백으로 요청 본문의 message 사용")
                        topic = req.message[:80]
                        context_text = req.message
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'source_message_id를 찾을 수 없습니다'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                else:
                    tpc, ctx, ref_docs = _compose_context_from_messages(source_msg, msgs or [])
                    topic, context_text, referenced_documents = (tpc or topic), (ctx or context_text), ref_docs
            elif req.message:
                topic = req.message[:80]
                context_text = req.message
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'message or source_message_id required'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 컨텍스트 유효성 검증
            if not context_text or len(context_text.strip()) < 50:
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI 답변 내용이 충분하지 않습니다.'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # Template 모드 검증
            if req.mode == "template" and not req.template_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'template_id is required for template mode'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            logger.info(
                f"🚀 [Unified] Agent 실행 시작 - mode={req.mode}, pattern={req.pattern}, "
                f"template={req.template_id or 'N/A'}"
            )
            
            # 콘텐츠 구조화
            structured_context = _ensure_markdown_structure(context_text, topic)
            
            yield f"data: {json.dumps({'type': 'agent_thinking', 'message': f'{req.pattern.upper()} Agent가 분석 중입니다...'})}\n\n"
            
            # 🚀 Unified Agent 실행
            try:
                result = await unified_presentation_agent.run(
                    mode=req.mode,
                    pattern=req.pattern,
                    topic=topic,
                    context_text=structured_context,
                    template_id=req.template_id,
                    max_slides=req.max_slides,
                    user_id=current_user.id,  # 🆕 user_id 전달하여 user-specific 템플릿 접근
                    run_id=run_id,
                )

                # Fallback to legacy react if tool calling isn't supported.
                if req.pattern == "tool_calling" and not result.get("success") and isinstance(result.get("error"), str):
                    err = result.get("error") or ""
                    if "does not support tool calling" in err or "bind_tools" in err:
                        logger.warning(f"⚠️ [Unified] tool_calling not available; falling back to react: {err}")
                        result = await unified_presentation_agent.run(
                            mode=req.mode,
                            pattern="react",
                            topic=topic,
                            context_text=structured_context,
                            template_id=req.template_id,
                            max_slides=req.max_slides,
                            user_id=current_user.id,
                            run_id=run_id,
                        )
                
                # 결과 확인
                if result.get("success"):
                    file_path = result.get("file_path")
                    file_name = result.get("file_name")
                    
                    if file_path and file_name:
                        file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name)}"

                        yield f"data: {json.dumps({'type': 'complete', 'file_url': file_url, 'file_name': file_name, 'slide_count': result.get('slide_count', 0), 'execution_time': result.get('execution_time', 0), 'iterations': result.get('iterations', 0), 'run_id': result.get('run_id') or run_id, 'trace_id': result.get('trace_id') or run_id})}\n\n"
                        logger.info(f"✅ [Unified] 성공: {file_name}, slides={result.get('slide_count')}, time={result.get('execution_time', 0):.2f}s")
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent가 파일 생성에 실패했습니다'})}\n\n"
                else:
                    error_msg = result.get("error", "Unknown error")
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    logger.error(f"❌ [Unified] 실패: {error_msg}")
            
            except Exception as agent_error:
                logger.error(f"❌ [Unified] Agent 실행 오류: {agent_error}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': f'Agent 오류: {str(agent_error)}'})}\n\n"
            
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            logger.error(f"❌ [Unified] Streaming 오류: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")


# ===== v2.0: Template Auto-Mapping API =====

class AutoMappingRequest(BaseModel):
    """자동 매핑 요청"""
    template_id: str
    outline: Dict[str, Any]  # AI 아웃라인 (DeckSpec 형태)


@router.post(
    "/agent/presentation/auto-mapping",
    summary="🔄 AI 아웃라인 → 템플릿 자동 매핑",
    description="""
    AI가 생성한 아웃라인을 선택한 템플릿에 자동으로 매핑합니다.
    
    **기능:**
    - 슬라이드 역할 기반 매핑 (title, toc, content, thanks)
    - 요소별 상세 매핑 (제목, 본문, 불릿 등)
    - 매핑 확신도 제공
    - 사용자 수정을 위한 매핑 결과 반환
    
    **반환:**
    - 슬라이드별 매핑 정보
    - AI 추천 콘텐츠
    - 경고 및 권장 사항
    """
)
async def auto_map_outline_to_template(
    req: AutoMappingRequest,
    current_user: User = Depends(get_current_user)
):
    """AI 아웃라인을 템플릿에 자동 매핑"""
    try:
        from app.services.presentation.template_auto_mapping_service import template_auto_mapping_service
        from app.services.presentation.user_template_manager import UserTemplateManager
        
        logger.info(f"🔄 자동 매핑 요청: template_id={req.template_id}, user_id={current_user.id}")
        
        # 사용자별 템플릿 매니저 사용
        user_template_manager = UserTemplateManager()
        
        # 템플릿 메타데이터 로드 (사용자별)
        decoded_id = urllib.parse.unquote(req.template_id)
        template_metadata = user_template_manager.get_template_metadata(current_user.id, decoded_id)
        
        if not template_metadata:
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {decoded_id}")
        
        # 자동 매핑 수행
        result = template_auto_mapping_service.auto_map_outline_to_template(
            template_id=decoded_id,
            template_metadata=template_metadata,
            ai_outline=req.outline
        )
        
        # 편집기 UI용 형식으로 변환
        export_data = template_auto_mapping_service.export_mapping_for_editor(result)
        
        return {
            "success": result.success,
            "mapping": export_data,
            "template_id": decoded_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 자동 매핑 실패: {e}")
        raise HTTPException(status_code=500, detail=f"자동 매핑 중 오류: {str(e)}")


# ===== v2.0: PDF Preview API =====

@router.post(
    "/agent/presentation/templates/{template_id}/generate-preview",
    summary="📄 템플릿 PDF 프리뷰 생성",
    description="""
    템플릿의 슬라이드별 PDF 프리뷰를 생성합니다.
    
    **기능:**
    - PPTX → PDF 변환
    - 슬라이드별 이미지 생성
    - 썸네일 생성
    - 캐시 관리
    """
)
async def generate_template_preview(
    template_id: str,
    force_regenerate: bool = Query(False, description="기존 캐시 무시하고 재생성"),
    current_user: User = Depends(get_current_user)
):
    """템플릿 PDF 프리뷰 생성"""
    try:
        from app.services.presentation.pdf_preview_generator import pdf_preview_generator
        
        decoded_id = urllib.parse.unquote(template_id)
        logger.info(f"📄 프리뷰 생성 요청: template_id={decoded_id}")
        
        # 템플릿 경로 확인
        template_path = template_manager.get_template_file_path(decoded_id)
        if not template_path:
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {decoded_id}")
        
        # 프리뷰 생성
        result = pdf_preview_generator.generate_template_preview(
            template_id=decoded_id,
            template_path=template_path,
            force_regenerate=force_regenerate
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error_message or "프리뷰 생성 실패")
        
        return {
            "success": True,
            "template_id": decoded_id,
            "total_slides": result.total_slides,
            "pdf_url": f"/api/v1/agent/presentation/templates/{decoded_id}/pdf",
            "slides": [
                {
                    "slide_index": s.slide_index,
                    "preview_url": f"/api/v1/agent/presentation/templates/{decoded_id}/preview/{s.slide_index}",
                    "thumbnail_url": f"/api/v1/agent/presentation/templates/{decoded_id}/thumbnail/{s.slide_index}",
                    "width": s.width,
                    "height": s.height
                }
                for s in result.slides
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 프리뷰 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"프리뷰 생성 중 오류: {str(e)}")


@router.get(
    "/agent/presentation/templates/{template_id}/previews",
    summary="📋 템플릿 프리뷰 목록 조회"
)
async def list_template_previews(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """템플릿의 모든 프리뷰 정보 조회"""
    try:
        from app.services.presentation.pdf_preview_generator import pdf_preview_generator
        
        decoded_id = urllib.parse.unquote(template_id)
        return pdf_preview_generator.list_template_previews(decoded_id)
        
    except Exception as e:
        logger.error(f"❌ 프리뷰 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agent/presentation/templates/{template_id}/preview/{slide_index}",
    summary="🖼️ 특정 슬라이드 프리뷰 이미지"
)
async def get_slide_preview_image(
    template_id: str,
    slide_index: int,
    current_user: User = Depends(get_current_user)
):
    """특정 슬라이드의 프리뷰 이미지 반환"""
    try:
        from app.services.presentation.pdf_preview_generator import pdf_preview_generator
        
        decoded_id = urllib.parse.unquote(template_id)
        image_path = pdf_preview_generator.get_slide_preview_path(decoded_id, slide_index)
        
        if not image_path or not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail=f"슬라이드 {slide_index} 프리뷰를 찾을 수 없습니다")
        
        return FileResponse(
            path=image_path,
            media_type="image/png",
            filename=f"{decoded_id}_slide_{slide_index}.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 슬라이드 프리뷰 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agent/presentation/templates/{template_id}/pdf",
    summary="📄 템플릿 PDF 파일"
)
async def get_template_pdf(
    template_id: str,
    token: Optional[str] = Query(None, description="인증 토큰 (iframe용)"),
    authorization: Optional[str] = Header(None),
):
    """템플릿 PDF 파일 반환 (기존 /file 엔드포인트와 호환)"""
    try:
        decoded_id = urllib.parse.unquote(template_id)
        pdf_path = template_manager.get_template_pdf_path(decoded_id)
        
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다")
        
        def generate():
            with open(pdf_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
        
        encoded_filename = urllib.parse.quote(f"{decoded_id}.pdf")
        return StreamingResponse(
            generate(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== v2.0: Enhanced Metadata API =====

@router.get(
    "/agent/presentation/templates/{template_id}/metadata-v2",
    summary="📊 템플릿 메타데이터 v2 (역할 정보 포함)"
)
async def get_template_metadata_v2(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    v2.0 메타데이터 조회
    - 슬라이드 역할 정보 (title, toc, content, thanks)
    - 편집 가능/고정 요소 구분
    - 요소별 역할 분류
    """
    try:
        decoded_id = urllib.parse.unquote(template_id)
        metadata = template_manager.get_template_metadata(decoded_id)
        
        if not metadata:
            raise HTTPException(status_code=404, detail="메타데이터를 찾을 수 없습니다")
        
        # v2.0 형식인지 확인
        version = metadata.get("version", "1.0")
        
        if version != "2.0":
            # v1.0 메타데이터면 재생성 안내
            return {
                "success": True,
                "template_id": decoded_id,
                "metadata_version": version,
                "metadata": metadata,
                "needs_upgrade": True,
                "upgrade_hint": "템플릿을 재등록하면 v2.0 메타데이터가 생성됩니다."
            }
        
        return {
            "success": True,
            "template_id": decoded_id,
            "metadata_version": version,
            "metadata": metadata,
            "needs_upgrade": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 메타데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


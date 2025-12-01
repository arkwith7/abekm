from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Header, Request
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import json
import os
import urllib.parse
from pathlib import Path
from datetime import datetime

from app.core.dependencies import get_current_user
from app.core.security import AuthUtils
from app.services.auth.async_user_service import AsyncUserService
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.models.chat import RedisChatManager, get_redis_client
from app.core.config import settings
from app.services.presentation.quick_ppt_generator_service import quick_ppt_service
from app.services.presentation.templated_ppt_generator_service import templated_ppt_service
from app.services.presentation.ppt_template_manager import template_manager
from app.services.presentation.template_migration_service import template_migration_service
from app.services.presentation.template_debugger import template_debugger
from app.services.file_manager import file_manager
from app.services.office_generator_client import office_generator_client
from app.models.presentation import PresentationRequest, PresentationResponse, PresentationMetadata, StructuredOutline
from app.agents.presentation.content_structurer import structure_markdown_to_outline
from app.agents.presentation.html_generator import generate_presentation_html
from app.agents.presentation.orchestrator import presentation_agent
from app.agents.presentation.presentation_agent import quick_ppt_react_agent  # 🆕 ReAct Agent
import logging


router = APIRouter(tags=["📊 Presentation"])
logger = logging.getLogger(__name__)


# ===== Shared helpers (isolated to avoid circular imports) =====
def get_redis_chat_manager() -> RedisChatManager:
    redis_client = get_redis_client()
    return RedisChatManager(redis_client)


async def _get_message_by_id(chat_manager: RedisChatManager, session_id: str, message_id: str):
    msgs = await chat_manager.get_recent_messages(session_id, limit=1000)
    for msg in msgs:
        if getattr(msg, 'message_id', None) == message_id:
            return msg, msgs
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
    summary="Generate presentation via HTML-first pipeline"
)
async def generate_agent_presentation(
    request: PresentationRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate an HTML presentation using the new modular pipeline."""
    options = request.options or {}
    chat_manager = get_redis_chat_manager()

    inferred_title = request.title_override
    markdown = request.markdown
    if not markdown:
        source_msg, msgs = await _get_message_by_id(chat_manager, request.session_id, request.message_id)
        if source_msg:
            title_from_msg, context_text, _ = _compose_context_from_messages(source_msg, msgs)
            markdown = context_text
            if not inferred_title:
                inferred_title = title_from_msg
        else:
            fallback_title = inferred_title or options.get("title")
            fallback_message = options.get("message")
            title_from_msg, context_text, _ = await _compose_fallback_context(
                chat_manager,
                request.session_id,
                fallback_title,
                fallback_message,
            )
            markdown = context_text
            if not inferred_title:
                inferred_title = title_from_msg

    if not markdown or not markdown.strip():
        raise HTTPException(status_code=400, detail="No content available for presentation generation")

    try:
        max_slides_opt = options.get("max_slides", 12)
        max_slides = int(max_slides_opt) if isinstance(max_slides_opt, (int, str)) else 12
    except (TypeError, ValueError):  # pragma: no cover - defensive
        max_slides = 12

    audience = options.get("audience", "general")

    try:
        outline = await structure_markdown_to_outline(
            markdown=markdown,
            max_slides=max_slides,
            audience=audience,
            style=request.style,
        )
    except ValueError as exc:
        logger.error("Structured outline generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Outline generation failed: {exc}") from exc

    presentation_title = inferred_title or outline.title
    theme_override = options.get("theme") or request.style or outline.theme
    outline = outline.model_copy(update={
        "title": presentation_title,
        "theme": theme_override,
    })

    temperature_opt = options.get("temperature", 0.5)
    try:
        temperature = float(temperature_opt)
    except (TypeError, ValueError):
        temperature = 0.5

    max_tokens_opt = options.get("max_tokens", 6000)
    try:
        max_tokens = int(max_tokens_opt)
    except (TypeError, ValueError):
        max_tokens = 6000

    try:
        html_content = await generate_presentation_html(
            outline,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # pragma: no cover - network errors
        logger.error("HTML generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="HTML generation failed") from exc

    output_path = file_manager.save_html(html_content, title=presentation_title)
    file_size = output_path.stat().st_size if output_path.exists() else 0

    outline_payload = outline.model_dump(mode="json")
    outline_json = json.dumps(outline_payload, ensure_ascii=False, indent=2)
    outline_path = file_manager.save_outline(outline_json, title=presentation_title)
    outline_size = outline_path.stat().st_size if outline_path.exists() else 0

    metadata = PresentationMetadata(
        title=presentation_title,
        created_at=datetime.utcnow(),
        file_size_bytes=file_size,
        slide_count=len(outline.slides),
        theme=outline.theme,
        html_filename=output_path.name,
        outline_filename=outline_path.name,
        outline_file_size_bytes=outline_size,
    )

    html_url = f"/api/v1/agent/presentation/view/{output_path.name}"
    outline_url = f"/api/v1/agent/presentation/outline/{outline_path.name}"

    # Generate PPTX if requested
    pptx_url = None
    if request.output_format in ("pptx", "both"):
        try:
            logger.info("Generating PPTX automatically...")
            pptx_data = await office_generator_client.convert_to_pptx(outline, theme_override)
            pptx_path = file_manager.save_pptx(pptx_data, title=presentation_title)
            pptx_url = f"/api/v1/agent/presentation/download/{pptx_path.name}"
            logger.info(f"PPTX generated: {pptx_path.name} ({len(pptx_data)} bytes)")
        except Exception as e:
            logger.error(f"Auto PPTX generation failed: {e}", exc_info=True)
            # Don't fail the entire request, just log the error
            pptx_url = None

    logger.info(
        "🖼️ HTML presentation generated: %s (slides=%d)",
        output_path.name,
        len(outline.slides),
    )

    return PresentationResponse(
        success=True,
        html_url=html_url,
        pptx_url=pptx_url,
        preview_available=True,
        slide_count=len(outline.slides),
        metadata=metadata,
        outline_url=outline_url,
        error=None,
        error_code=None,
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


@router.get(
    "/agent/presentation/download/{filename}",
    summary="Download PPTX file",
    description="Download generated PPTX presentation"
)
async def download_pptx(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """Download PPTX file"""
    # 일부 생성 파이프라인은 기존 uploads 디렉터리를 사용하므로 다중 경로 탐색
    safe_filename = Path(filename).name
    search_roots = [file_manager.pptx_dir, settings.resolved_upload_dir]
    pptx_path = None

    for root in search_roots:
        candidate = root / safe_filename
        if candidate.is_file():
            pptx_path = candidate
            break

    if not pptx_path:
        raise HTTPException(status_code=404, detail="PPTX file not found")
    
    return FileResponse(
        path=pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe_filename
    )


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
async def list_presentation_templates():
    all_templates = template_manager.list_templates()
    enhanced_templates = []
    for template in all_templates:
        enhanced_template = template.copy()
        tid = template.get('id') or ""
        details = template_manager.get_template_details(tid) if tid else None
        if details and details.get('dynamic_template_id'):
            enhanced_template['dynamic_template_id'] = details.get('dynamic_template_id')
            enhanced_template['is_content_cleaned'] = details.get('is_content_cleaned', False)
            enhanced_template['type'] = 'user-uploaded' if template.get('is_user_uploaded', False) else 'built-in'
        else:
            enhanced_template['type'] = 'user-uploaded' if template.get('is_user_uploaded', False) else 'built-in'
        enhanced_template['is_default'] = template_manager._registry.get(tid, {}).get('is_default', False)  # noqa: SLF001
        enhanced_templates.append(enhanced_template)
    default_template_id = template_manager.get_default_template_id()
    built_in = [t for t in enhanced_templates if t.get('type') == 'built-in']
    user_uploaded = [t for t in enhanced_templates if t.get('type') == 'user-uploaded']
    return {
        "success": True,
        "templates": enhanced_templates,
        "built_in": built_in,
        "user_uploaded": user_uploaded,
        "default_template_id": default_template_id
    }

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
async def get_template_thumbnails(template_id: str):
    try:
        logger.info(f"템플릿 썸네일 목록 요청: {template_id}")
        template_details = template_manager.get_template_details(template_id)
        if not template_details:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
        thumbnails = template_details.get('thumbnails', [])
        return {
            "success": True,
            "template_id": template_id,
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
    style: str = Form('business'),
    name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    if not file.filename or not file.filename.lower().endswith('.pptx'):
        raise HTTPException(status_code=400, detail="pptx 파일만 지원합니다")
    upload_dir = settings.resolved_upload_dir / 'templates'
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = file.filename.replace('..','_').replace('/','_')
    dest = upload_dir / safe_name
    data = await file.read()
    dest.write_bytes(data)
    entry = template_manager.register_uploaded_template(dest, style=style, name=name)
    return {"success": True, "template": entry}


@router.delete("/agent/presentation/templates/{template_id}", summary="PPT 템플릿 삭제")
async def delete_presentation_template(template_id: str):
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        ok = template_manager.remove_template(decoded_template_id)
        if not ok:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
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
    try:
        decoded_template_id = urllib.parse.unquote(template_id)
        ok = template_manager.set_default_template(decoded_template_id)
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
        logger.info(f"🔍 [simple-metadata] 요청: raw_id='{template_id}'")
        decoded_id = urllib.parse.unquote(template_id)
        logger.info(f"🔍 [simple-metadata] 디코딩된 ID: '{decoded_id}'")

        # 템플릿 확인
        template_details = template_manager.get_template_details(decoded_id)
        if not template_details:
            logger.error(f"❌ [simple-metadata] 템플릿을 찾을 수 없음: '{decoded_id}'")
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {decoded_id}")

        # 원본(추출기) 메타데이터 로드
        full = template_manager.get_template_metadata(decoded_id)
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
        decoded_id = urllib.parse.unquote(template_id)
        data = template_manager.get_template_metadata(decoded_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Outline =====
@router.post("/agent/presentation/outline", response_model=PresentationOutlineResponse)
async def create_presentation_outline(
    req: PresentationOutlineRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    try:
        logger.info(f"🔍 아웃라인 생성 요청: session_id={req.session_id}, source_message_id={req.source_message_id}")
        logger.info(f"🔍 요청 파라미터: provider={req.provider}, title={req.title}, presentation_type={req.presentation_type}")
        
        source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id)
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
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    async def stream():
        try:
            import time
            t0 = time.perf_counter()
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            try:
                source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id)
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
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """ReAct Agent 기반 Quick PPT 생성 (기존 파이프라인 대체)"""
    async def stream():
        try:
            yield f"data: {json.dumps({'type': 'start', 'agent_type': 'ReAct'})}\n\n"
            
            # 메시지 소스 추출 (기존 로직 유지)
            topic = "발표자료"
            context_text = ""
            referenced_documents = None
            
            if req.source_message_id:
                logger.info(f"🔍 [ReAct] 메시지 ID로 검색: {req.source_message_id}")
                source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id)
                
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
            structured_context = _ensure_markdown_structure(context_text, topic)
            logger.info(f"📐 [ReAct] 구조화 완료: {len(structured_context)}자 (원본: {len(context_text)}자)")
            
            yield f"data: {json.dumps({'type': 'agent_thinking', 'message': 'ReAct Agent가 분석 중입니다...'})}\n\n"
            
            # 🧠 ReAct Agent 실행
            try:
                result = await quick_ppt_react_agent.run(
                    user_request="PPT 생성",
                    context_text=structured_context,
                    topic=topic,
                    max_slides=req.max_slides
                )
                
                # 결과 확인
                if result.get("success"):
                    file_name = result.get("file_name")
                    if file_name:
                        file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name)}"
                        logger.info(f"📦 [ReAct] PPT 생성 완료 - 파일: {file_name}")
                        
                        response_data: Dict[str, Any] = {
                            'type': 'complete',
                            'file_url': file_url,
                            'file_name': file_name,
                            'agent_type': 'ReAct',
                            'iterations': result.get("iterations", 0),
                            'tools_used': result.get("tools_used", []),
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
    source_message_id: str
    template_id: str
    outline: Dict[str, Any]
    slide_management: Optional[List[SlideManagementInfo]] = None
    object_mappings: Optional[List[Dict[str, Any]]] = None
    content_segments: Optional[List[Dict[str, Any]]] = None


@router.post(
    "/agent/presentation/build-with-template",
    deprecated=True,
    summary="⚠️ [DEPRECATED] Template-based PPT Generation",
    description="""
    **DEPRECATED**: This endpoint is deprecated and will be removed in a future release.
    
    **Migration**: Use `POST /api/v1/presentation/agent/generate` with `mode="enhanced"` and `template_path` instead.
    
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
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    try:
        source_msg, msgs = await _get_message_by_id(chat_manager, req.session_id, req.source_message_id)
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
        final_path = upload_dir / safe_name
        logger.info(f"📥 파일 경로: '{final_path}'")
        
        if not os.path.exists(final_path):
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
    summary="🤖 Agent-Based PPT Generation",
    description="""
    Generate presentations using the PresentationAgent tool orchestration framework.
    
    **Modes:**
    - `quick`: Fast automated generation (outline → viz → builder)
    - `enhanced`: Advanced generation with optional templates
    
    **Strategies** (auto-selected by agent):
    - `quick_generation`: Simple automated pipeline
    - `enhanced_auto`: Enhanced without template
    - `enhanced_template`: Enhanced with custom template
    
    **Options:**
    - `max_slides`: Maximum number of slides (default: 10)
    - `template_path`: Path to custom template (for enhanced mode)
    - `visualization_hints`: Enable chart/diagram suggestions
    """
)
async def generate_presentation_with_agent(
    request: AgentPresentationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate presentation using PresentationAgent.
    
    This endpoint provides a unified interface for both Quick and Enhanced
    generation modes, with automatic strategy selection and tool orchestration.
    """
    try:
        logger.info(
            f"Agent presentation request: mode={request.mode}, topic={request.topic[:50]}, "
            f"user={current_user.email}"
        )
        
        # Prepare options
        options = {
            "max_slides": request.max_slides,
            "visualization_hints": request.visualization_hints
        }
        
        if request.template_path:
            options["template_path"] = request.template_path
        
        # Execute via agent
        result = await presentation_agent.execute(
            mode=request.mode,
            topic=request.topic,
            context_text=request.context_text,
            options=options
        )
        
        if result["success"]:
            logger.info(
                f"Agent generated presentation: {result['file_path']}, "
                f"slides={result.get('slide_count')}, strategy={result.get('strategy')}, "
                f"time={result.get('execution_time'):.2f}s"
            )
            
            return AgentPresentationResponse(
                success=True,
                file_path=result.get("file_path"),
                slide_count=result.get("slide_count"),
                mode=result.get("mode"),
                strategy=result.get("strategy"),
                execution_time=result.get("execution_time"),
                steps=result.get("steps", [])
            )
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Agent generation failed: {error_msg}")
            
            return AgentPresentationResponse(
                success=False,
                mode=request.mode,
                error=error_msg,
                steps=result.get("steps", [])
            )
    
    except Exception as e:
        logger.error(f"Agent endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Presentation generation failed: {str(e)}"
        )



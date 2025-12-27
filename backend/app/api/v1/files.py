"""
파일 관리 API - 통합된 파일 다운로드 및 업로드 처리
=======================================================

🎯 목적:
- 일반 파일 다운로드 및 접근 제어
- 대용량 파일 업로드 및 스트리밍 처리
- 토큰 기반 인증 및 권한 검증

📋 주요 기능:
1. 📁 파일 다운로드 (/files/download, /files/view)
2. 📦 대용량 파일 업로드 (/files/large-upload)
3. 📊 업로드 진행률 추적
4. 🔐 토큰 기반 접근 제어
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Query, Header, Request, Cookie
from fastapi import UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from starlette.responses import RedirectResponse
from app.core.dependencies import get_current_user
from app.models import User
from app.services.auth.user_service import UserService
from app.core.database import get_db
from app.schemas.user_schemas import TokenData
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import os
import mimetypes
from pathlib import Path
import io
import datetime
import logging
import urllib.parse

# from app.services.document.pipeline.large_file_processor import large_file_processor  # Deprecated
from app.core.config import settings
from app.services.core import azure_blob_service as azure_blob_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["📁 File Management"])

# =============================================================================
# 🔐 인증 헬퍼 함수
# =============================================================================

def extract_token(
    token: Optional[str] = Query(None, description="인증 토큰 (Query Parameter)"),
    authorization: Optional[str] = Header(None, description="Authorization 헤더"),
    access_token: Optional[str] = Cookie(None, description="쿠키의 액세스 토큰")
) -> Optional[str]:
    """다양한 방법으로 토큰 추출 (우선순위: 쿠키 > 헤더 > Query Parameter)"""
    
    # 1. 쿠키에서 토큰 추출 (가장 안전한 방법)
    if access_token:
        logger.debug("🍪 쿠키에서 토큰 추출")
        return access_token
    
    # 2. Authorization 헤더에서 토큰 추출
    if authorization:
        if authorization.startswith("Bearer "):
            logger.debug("🔑 Authorization 헤더에서 토큰 추출")
            return authorization[7:]
        else:
            logger.debug("🔑 Authorization 헤더에서 토큰 추출 (Bearer 없음)")
            return authorization
    
    # 3. Query Parameter에서 토큰 추출 (보안상 권장하지 않음)
    if token:
        logger.debug("🔗 Query Parameter에서 토큰 추출")
        return token
    
    logger.debug("❌ 토큰을 찾을 수 없음")
    return None

async def get_user_from_token(db: AsyncSession, token: str) -> Optional[User]:
    """토큰으로부터 사용자 정보 조회"""
    try:
        logger.debug(f"토큰 인증 시작: {token[:20] + '...' if token and len(token) > 20 else token}")
        
        from app.core.security import AuthUtils
        from fastapi import HTTPException
        
        token_data = AuthUtils.verify_token(token)
        logger.debug(f"토큰 검증 결과: {token_data}")
        
        if token_data and token_data.emp_no:
            emp_no = token_data.emp_no
            logger.debug(f"토큰에서 추출된 emp_no: {emp_no}")
            
            from app.services.auth.user_service import UserService
            user_service = UserService(db)
            user = await user_service.get_user_by_emp_no(emp_no)
            
            if user:
                logger.info(f"✅ 토큰 인증 성공: {user.username} (emp_no: {user.emp_no})")
            else:
                logger.warning(f"❌ 사용자를 찾을 수 없음: {emp_no}")
            
            return user
        else:
            logger.warning("❌ 토큰 데이터가 유효하지 않음")
            return None
            
    except HTTPException as he:
        logger.error(f"❌ 토큰 검증 HTTP Exception: {he.detail}")
        return None
    except Exception as e:
        logger.error(f"❌ 토큰 인증 중 예외 발생: {e}")
        return None

# =============================================================================
# 📁 파일 다운로드 및 뷰어 API
# =============================================================================

@router.get("/files/view/{file_id}")
async def view_file(
    file_id: str,
    auth_token: Optional[str] = Depends(extract_token),
    db: AsyncSession = Depends(get_db)
):
    """파일 뷰어 (브라우저에서 직접 보기) - 쿠키, 헤더, Query Parameter 지원"""
    
    logger.info(f"🔍 파일 뷰어 요청 시작: file_id={file_id}")
    logger.info(f"🔍 추출된 토큰: {auth_token[:20] + '...' if auth_token and len(auth_token) > 20 else auth_token}")
    
    # 토큰 검증
    if not auth_token:
        logger.error("❌ 토큰이 없습니다")
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    
    logger.info("🔍 사용자 인증 시작")
    user = await get_user_from_token(db, auth_token)
    if not user:
        logger.error("❌ 사용자 인증 실패")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    
    logger.info(f"✅ 사용자 인증 성공: {user.username} (emp_no: {user.emp_no})")
    
    # 파일 정보 조회
    try:
        logger.info(f"📁 파일 정보 조회 시작: file_id={file_id}")
        
        # file_id가 숫자인지 확인
        try:
            file_id_int = int(file_id)
            logger.info(f"🔢 파일 ID 변환 성공: {file_id_int}")
        except ValueError as ve:
            logger.error(f"❌ 파일 ID 변환 실패: {file_id} - {ve}")
            raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
        
        from app.services.document.storage.file_storage_service import file_storage_service
        logger.info("📦 file_storage_service 임포트 성공")
        
        file_info = await file_storage_service.get_file_info(file_id_int)
        logger.info(f"📋 파일 정보 조회 결과: {file_info}")
        
        if not file_info:
            logger.error(f"❌ 파일 정보를 찾을 수 없음: file_id={file_id_int}")
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        file_path = file_info.get("file_path")
        logger.info(f"📂 원본 파일 경로: {file_path}")
        
        if not file_path:
            logger.error("❌ 파일 경로가 없음")
            raise HTTPException(status_code=404, detail="파일 경로를 찾을 수 없습니다.")

        # 1) 로컬 파일이 존재하면 로컬로 제공 (이전 local 모드 호환)
        abs_file_path = file_path
        if not os.path.isabs(abs_file_path):
            abs_file_path = os.path.abspath(file_path)
            logger.info(f"🔄 상대 경로를 절대 경로로 변환: {file_path} → {abs_file_path}")
        if os.path.exists(abs_file_path):
            file_path = abs_file_path
            logger.info(f"📁 로컬 파일 사용: {file_path}")
        else:
            # 2) 로컬에 없고 클라우드 스토리지 모드면 처리
            storage_backend = getattr(settings, 'storage_backend', 'local')
            
            if storage_backend == 's3':
                try:
                    from app.services.core.aws_service import S3Service
                    s3 = S3Service()
                    filename = file_info.get("file_logical_name", f"file_{file_id}")
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    encoded_filename = urllib.parse.quote(filename)
                    disposition = f"inline; filename*=UTF-8''{encoded_filename}"
                    url = s3.generate_presigned_url(
                        object_key=file_path,
                        expires_in=getattr(settings, 's3_presign_expiry_seconds', 3600),
                        response_content_disposition=disposition,
                        response_content_type=mime_type,
                    )
                    return RedirectResponse(url, status_code=307)
                except Exception as e:
                    logger.error(f"S3 presigned URL 생성 실패: {e}")
                    raise HTTPException(status_code=500, detail="S3 파일 접근 중 오류가 발생했습니다.")
            
            elif storage_backend == 'azure_blob':
                try:
                    azure_blob = azure_blob_module.get_azure_blob_service()  # type: ignore[attr-defined]
                    filename = file_info.get("file_logical_name", f"file_{file_id}")
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"

                    safe_filename = filename.replace('"', "'")
                    encoded_filename = urllib.parse.quote(filename)
                    content_disposition = f"inline; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}"

                    logger.info(f"🔄 Azure Blob SAS URL 생성: {file_path}")
                    sas_url = azure_blob.generate_sas_url(
                        blob_path=file_path,
                        purpose='raw',
                        expiry_seconds=getattr(settings, 'azure_blob_sas_expiry_seconds', 3600),
                        content_disposition=content_disposition,
                        content_type=mime_type
                    )
                    logger.info(f"✅ Azure Blob SAS URL 생성 완료")
                    return RedirectResponse(sas_url, status_code=307)
                except Exception as e:
                    logger.error(f"❌ Azure Blob SAS URL 생성 실패: {e}")
                    raise HTTPException(status_code=500, detail="Azure Blob 파일 접근 중 오류가 발생했습니다.")
            
            # 3) 그 외엔 404
            logger.error(f"❌ 파일이 존재하지 않음: {abs_file_path}")
            raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")
        
        logger.info(f"✅ 파일 존재 확인 성공: {file_path}")
        
        # MIME 타입 추정
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        logger.info(f"🏷️  MIME 타입: {mime_type}")
        
        # 브라우저에서 바로 볼 수 있는 파일 타입들
        viewable_types = [
            "text/plain", "text/html", "text/css", "text/javascript",
            "application/pdf", "image/jpeg", "image/png", "image/gif", 
            "image/svg+xml", "image/webp"
        ]
        
        # Content-Disposition 헤더 설정
        disposition = "inline" if mime_type in viewable_types else "attachment"
        filename = file_info.get("file_logical_name", f"file_{file_id}")
        
        logger.info(f"📤 응답 준비: disposition={disposition}, filename={filename}")
        
        # 한글 파일명을 안전하게 인코딩
        encoded_filename = urllib.parse.quote(filename)
        
        return FileResponse(
            path=file_path,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'{disposition}; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
    
        
    except ValueError:
        logger.error(f"❌ ValueError: 유효하지 않은 파일 ID: {file_id}")
        raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
    except HTTPException as he:
        logger.error(f"❌ HTTPException: {he.status_code} - {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"❌ 파일 뷰어 예외 발생: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="파일 조회 중 오류가 발생했습니다.")

@router.get("/files/iframe-view/{file_id}")
async def iframe_view_file(
    file_id: str,
    token: str = Query(..., description="인증 토큰 (iframe용 필수)"),
    db: AsyncSession = Depends(get_db)
):
    """iframe 전용 파일 뷰어 - Query Parameter 토큰 필수"""
    
    logger.info(f"🖼️ iframe 파일 뷰어 요청 시작: file_id={file_id}")
    logger.info(f"🔍 Query Parameter 토큰: {token[:20] + '...' if token and len(token) > 20 else token}")
    
    # 사용자 인증
    user = await get_user_from_token(db, token)
    if not user:
        logger.error("❌ iframe 사용자 인증 실패")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    
    logger.info(f"✅ iframe 사용자 인증 성공: {user.username} (emp_no: {user.emp_no})")
    
    # 파일 처리 로직
    try:
        logger.info(f"📁 iframe 파일 정보 조회 시작: file_id={file_id}")
        
        try:
            file_id_int = int(file_id)
            logger.info(f"🔢 iframe 파일 ID 변환 성공: {file_id_int}")
        except ValueError as ve:
            logger.error(f"❌ iframe 파일 ID 변환 실패: {file_id} - {ve}")
            raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
        
        from app.services.document.storage.file_storage_service import file_storage_service
        logger.info("📦 iframe file_storage_service 임포트 성공")
        
        file_info = await file_storage_service.get_file_info(file_id_int)
        logger.info(f"📋 iframe 파일 정보 조회 결과: {file_info}")
        
        if not file_info:
            logger.error(f"❌ iframe 파일 정보를 찾을 수 없음: file_id={file_id_int}")
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        file_path = file_info.get("file_path")
        logger.info(f"📂 iframe 원본 파일 경로: {file_path}")
        
        if not file_path:
            logger.error("❌ iframe 파일 경로가 없음")
            raise HTTPException(status_code=404, detail="파일 경로를 찾을 수 없습니다.")

        # URL 기반 문서 처리
        if isinstance(file_path, str) and (file_path.startswith('http://') or file_path.startswith('https://')):
            # S3 URL인 경우: object key를 추출해 presigned URL로 리다이렉트 (inline)
            if '.amazonaws.com' in file_path or '.s3.' in file_path:
                try:
                    from app.services.core.aws_service import S3Service
                    parsed = urllib.parse.urlparse(file_path)
                    object_key = parsed.path.lstrip('/')  # "/patents/xxx.pdf" -> "patents/xxx.pdf"
                    filename = file_info.get("file_logical_name", f"file_{file_id}")
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/pdf"
                    encoded_filename = urllib.parse.quote(filename)
                    disposition = f"inline; filename*=UTF-8''{encoded_filename}"
                    
                    s3 = S3Service()
                    url = s3.generate_presigned_url(
                        object_key=object_key,
                        expires_in=getattr(settings, 's3_presign_expiry_seconds', 3600),
                        response_content_disposition=disposition,
                        response_content_type=mime_type,
                    )
                    logger.info(f"🔗 S3 presigned URL로 리다이렉트 (iframe): {object_key}")
                    return RedirectResponse(url, status_code=307)
                except Exception as e:
                    logger.error(f"S3 URL presign 실패(iframe): {e}. 원본 URL로 fallback")
                    return RedirectResponse(file_path, status_code=307)
            
            # 다른 외부 URL(특허 등): iframe에서 차단될 수 있어 안내 링크 HTML 반환
            safe_url = file_path
            html = (
                "<!doctype html><html><head><meta charset='utf-8'/><title>External Link</title></head>"
                "<body>"
                "<p>외부 링크 문서입니다. 아래 링크를 클릭하여 열어주세요.</p>"
                f"<p><a href='{safe_url}' target='_blank' rel='noopener noreferrer'>{safe_url}</a></p>"
                "</body></html>"
            )
            return Response(content=html, media_type="text/html")

        storage_backend = getattr(settings, 'storage_backend', 'local')

        # S3 스토리지인 경우: 프리사인드 URL로 리다이렉트 (inline)
        if storage_backend == 's3':
            try:
                from app.services.core.aws_service import S3Service
                s3 = S3Service()
                filename = file_info.get("file_logical_name", f"file_{file_id}")
                mime_type, _ = mimetypes.guess_type(filename)
                if not mime_type:
                    mime_type = "application/octet-stream"
                encoded_filename = urllib.parse.quote(filename)
                disposition = f"inline; filename*=UTF-8''{encoded_filename}"
                url = s3.generate_presigned_url(
                    object_key=file_path,
                    expires_in=getattr(settings, 's3_presign_expiry_seconds', 3600),
                    response_content_disposition=disposition,
                    response_content_type=mime_type,
                )
                return RedirectResponse(url, status_code=307)
            except Exception as e:
                logger.error(f"S3 presigned URL 생성 실패(iframe): {e}")
                raise HTTPException(status_code=500, detail="S3 파일 접근 중 오류가 발생했습니다.")

        # Azure Blob 스토리지인 경우: SAS URL로 리다이렉트 (inline)
        if storage_backend == 'azure_blob':
            try:
                azure_blob = azure_blob_module.get_azure_blob_service()  # type: ignore[attr-defined]
                filename = file_info.get("file_logical_name", f"file_{file_id}")
                mime_type, _ = mimetypes.guess_type(filename)
                if not mime_type:
                    mime_type = "application/octet-stream"
                
                # Azure Blob SAS는 content_disposition에 ASCII만 허용
                # filename에는 안전한 ASCII 대체값, filename*에만 UTF-8 인코딩된 실제 파일명 사용
                encoded_filename = urllib.parse.quote(filename)
                # ASCII 안전 파일명 생성 (file_id 기반)
                safe_ascii_filename = f"document_{file_id}.{file_info.get('file_extension', 'pdf')}"
                content_disposition = f"inline; filename=\"{safe_ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
                
                logger.info(f"🔄 iframe Azure Blob SAS URL 생성: {file_path}")
                sas_url = azure_blob.generate_sas_url(
                    blob_path=file_path,
                    purpose='raw',
                    expiry_seconds=getattr(settings, 'azure_blob_sas_expiry_seconds', 3600),
                    content_disposition=content_disposition,
                    content_type=mime_type
                )
                logger.info("✅ iframe Azure Blob SAS URL 생성 완료")
                return RedirectResponse(sas_url, status_code=307)
            except Exception as e:
                logger.error(f"❌ iframe Azure Blob SAS URL 생성 실패: {e}")
                raise HTTPException(status_code=500, detail="Azure Blob 파일 접근 중 오류가 발생했습니다.")
        
        # 1) 로컬 파일이 존재하면 로컬로 제공
        abs_file_path = file_path
        if not os.path.isabs(abs_file_path):
            abs_file_path = os.path.abspath(file_path)
            logger.info(f"🔄 iframe 상대 경로를 절대 경로로 변환: {file_path} → {abs_file_path}")
        if os.path.exists(abs_file_path):
            file_path = abs_file_path
            logger.info(f"📁 iframe 로컬 파일 사용: {file_path}")
        else:
            # 2) 로컬에 없고 S3 모드면 프리사인드 URL로 리다이렉트 (inline)
            if storage_backend == 's3':
                try:
                    from app.services.core.aws_service import S3Service
                    s3 = S3Service()
                    filename = file_info.get("file_logical_name", f"file_{file_id}")
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    encoded_filename = urllib.parse.quote(filename)
                    disposition = f"inline; filename*=UTF-8''{encoded_filename}"
                    url = s3.generate_presigned_url(
                        object_key=file_path,
                        expires_in=getattr(settings, 's3_presign_expiry_seconds', 3600),
                        response_content_disposition=disposition,
                        response_content_type=mime_type,
                    )
                    return RedirectResponse(url, status_code=307)
                except Exception as e:
                    logger.error(f"S3 presigned URL 생성 실패(iframe): {e}")
                    raise HTTPException(status_code=500, detail="S3 파일 접근 중 오류가 발생했습니다.")
            elif storage_backend == 'azure_blob':
                try:
                    azure_blob = azure_blob_module.get_azure_blob_service()  # type: ignore[attr-defined]
                    filename = file_info.get("file_logical_name", f"file_{file_id}")
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    safe_filename = filename.replace('"', "'")
                    encoded_filename = urllib.parse.quote(filename)
                    content_disposition = f"inline; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}"
                    logger.info(f"🔄 iframe Azure Blob SAS URL 생성(로컬 없음): {file_path}")
                    sas_url = azure_blob.generate_sas_url(
                        blob_path=file_path,
                        purpose='raw',
                        expiry_seconds=getattr(settings, 'azure_blob_sas_expiry_seconds', 3600),
                        content_disposition=content_disposition,
                        content_type=mime_type
                    )
                    logger.info("✅ iframe Azure Blob SAS URL 생성 완료(로컬 없음)")
                    return RedirectResponse(sas_url, status_code=307)
                except Exception as e:
                    logger.error(f"❌ iframe Azure Blob SAS URL 생성 실패(로컬 없음): {e}")
                    raise HTTPException(status_code=500, detail="Azure Blob 파일 접근 중 오류가 발생했습니다.")
            logger.error(f"❌ iframe 파일이 존재하지 않음: {abs_file_path}")
            raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")
        
        logger.info(f"✅ iframe 파일 존재 확인 성공: {file_path}")
        
        # MIME 타입 추정
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        logger.info(f"🏷️  iframe MIME 타입: {mime_type}")
        
        # Content-Disposition 헤더 설정
        viewable_types = [
            "text/plain", "text/html", "text/css", "text/javascript",
            "application/pdf", "image/jpeg", "image/png", "image/gif", 
            "image/svg+xml", "image/webp"
        ]
        disposition = "inline" if mime_type in viewable_types else "attachment"
        filename = file_info.get("file_logical_name", f"file_{file_id}")
        
        logger.info(f"📤 iframe 응답 준비: disposition={disposition}, filename={filename}, mime_type={mime_type}")
        
        # 한국어 파일명을 안전하게 인코딩
        encoded_filename = urllib.parse.quote(filename)
        
        logger.info(f"🔤 iframe 원본 파일명: {filename}")
        logger.info(f"🔤 iframe 인코딩된 파일명: {encoded_filename}")
        
        response = FileResponse(
            path=file_path,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'{disposition}; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
        
        logger.info(f"🖼️ iframe 파일 반환 성공: {filename} ({mime_type})")
        return response
        
    except ValueError as ve:
        logger.error(f"❌ iframe ValueError: {ve}")
        raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
    except HTTPException as he:
        logger.error(f"❌ iframe HTTPException: {he.status_code} - {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"❌ iframe 파일 뷰어 오류: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"❌ iframe 전체 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="파일 조회 중 오류가 발생했습니다.")

@router.get("/files/office-to-pdf/{file_id}")
async def office_to_pdf(
    file_id: str,
    token: Optional[str] = Query(None, description="인증 토큰 (iframe용)"),
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """Office 파일을 PDF로 변환하여 뷰어에 표시 - 쿠키, 헤더, Query Parameter 지원"""
    
    # 토큰 추출 (우선순위: Query Parameter > 쿠키 > 헤더)
    auth_token = None
    if token:
        auth_token = token
        logger.debug("🔗 Query Parameter에서 토큰 추출 (iframe용)")
    elif access_token:
        auth_token = access_token
        logger.debug("🍪 쿠키에서 토큰 추출")
    elif authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
        else:
            auth_token = authorization
        logger.debug("🔑 Authorization 헤더에서 토큰 추출")
    
    # 토큰 검증
    if not auth_token:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    
    user = await get_user_from_token(db, auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    
    logger.info(f"✅ Office PDF 변환 사용자 인증: {user.username}")
    
    # 파일 정보 조회
    try:
        from app.services.document.storage.file_storage_service import file_storage_service
        file_info = await file_storage_service.get_file_info(int(file_id))
        
        if not file_info:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        file_path = file_info.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="파일 경로를 찾을 수 없습니다.")
        
        # 클라우드 저장소인 경우 파일을 임시로 다운로드 후 변환 처리
        storage_backend = getattr(settings, 'storage_backend', 'local')
        
        if storage_backend == 's3' and not os.path.exists(file_path):
            from app.services.core.aws_service import S3Service
            import tempfile
            s3 = S3Service()
            tmpdir = tempfile.gettempdir()
            # 원래 확장자를 알 수 없으면 파일 논리명에서 유추
            logical_name = file_info.get("file_logical_name", f"file_{file_id}")
            suffix = Path(logical_name).suffix or Path(file_path).suffix
            local_tmp_path = str(Path(tmpdir) / f"{file_id}_source{suffix}")
            try:
                await s3.download_file(object_key=file_path, local_path=local_tmp_path)
                file_path = local_tmp_path
            except Exception as e:
                logger.error(f"S3 원본 다운로드 실패: {e}")
                raise HTTPException(status_code=500, detail="S3에서 파일을 가져오는 중 오류가 발생했습니다.")
        
        elif storage_backend == 'azure_blob' and not os.path.exists(file_path):
            from app.services.core.azure_blob_service import get_azure_blob_service
            import tempfile
            azure_blob = get_azure_blob_service()
            tmpdir = tempfile.gettempdir()
            # 원래 확장자를 알 수 없으면 파일 논리명에서 유추
            logical_name = file_info.get("file_logical_name", f"file_{file_id}")
            suffix = Path(logical_name).suffix or Path(file_path).suffix
            local_tmp_path = str(Path(tmpdir) / f"{file_id}_source{suffix}")
            try:
                logger.info(f"🔄 Azure Blob에서 파일 다운로드: {file_path} → {local_tmp_path}")
                azure_blob.download_blob_to_file(blob_path=file_path, local_path=local_tmp_path, purpose='raw')
                file_path = local_tmp_path
                logger.info(f"✅ Azure Blob 파일 다운로드 완료: {local_tmp_path}")
            except Exception as e:
                logger.error(f"❌ Azure Blob 원본 다운로드 실패: {e}")
                raise HTTPException(status_code=500, detail="Azure Blob에서 파일을 가져오는 중 오류가 발생했습니다.")
        
        # 상대 경로를 절대 경로로 변환 (backend 디렉토리 기준)
        if not os.path.isabs(file_path):
            # backend 디렉토리를 기준으로 절대 경로 생성
            backend_dir = Path(__file__).parent.parent.parent.parent  # files.py에서 backend 디렉토리로
            abs_file_path = backend_dir / file_path
            logger.info(f"🔄 Office PDF 상대 경로를 절대 경로로 변환: {file_path} → {abs_file_path}")
            file_path = str(abs_file_path)
        
        if not os.path.exists(file_path):
            logger.error(f"❌ Office PDF 파일이 존재하지 않음: {file_path}")
            raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")
        
        logger.info(f"✅ Office PDF 파일 존재 확인: {file_path}")
        
        filename = file_info.get("file_logical_name", f"file_{file_id}")
        file_extension = Path(filename).suffix.lower()
        
        # Office 파일 확인
        office_extensions = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.hwp', '.hwpx']
        if file_extension not in office_extensions:
            # Office 파일이 아닌 경우 일반 뷰어로 리다이렉트
            return await view_file(file_id, auth_token, db)
        
        # Office 파일을 PDF로 변환
        logger.info(f"Office 파일을 PDF로 변환 시작: {filename}")
        
        try:
            # PDF 변환된 파일 경로 생성
            pdf_filename = f"{Path(filename).stem}.pdf"
            
            # backend 디렉토리 기준으로 PDF 캐시 디렉토리 설정
            backend_dir = Path(__file__).parent.parent.parent.parent  # files.py에서 backend 디렉토리로
            pdf_cache_dir = backend_dir / "uploads" / "pdf_cache"
            pdf_cache_dir.mkdir(exist_ok=True)
            pdf_path = pdf_cache_dir / f"{file_id}_{pdf_filename}"
            
            logger.info(f"📁 PDF 캐시 디렉토리: {pdf_cache_dir}")
            logger.info(f"📄 PDF 파일 경로: {pdf_path}")
            
            # 이미 변환된 PDF가 있는지 확인
            if not pdf_path.exists():
                logger.info(f"PDF 변환 시작: {file_path} → {pdf_path}")
                
                # HWP/HWPX는 LibreOffice 호환성 문제로 텍스트 추출 방식 사용
                if file_extension in ['.hwp', '.hwpx']:
                    logger.info(f"HWP/HWPX 파일은 텍스트 추출 방식으로 처리: {filename}")
                    from app.services.document.extraction.text_extractor_service import text_extractor_service
                    
                    # HWP 텍스트 추출
                    extraction_result = await text_extractor_service.extract_text(file_path, file_extension)
                    
                    if extraction_result.get("success", False) and extraction_result.get("text"):
                        # 텍스트를 HTML로 변환하여 PDF 생성
                        html_content = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>{filename}</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                                h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                                .metadata {{ background: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                                .content {{ white-space: pre-wrap; }}
                            </style>
                        </head>
                        <body>
                            <h1>{filename}</h1>
                            <div class="metadata">
                                <strong>파일 크기:</strong> {extraction_result.get('metadata', {}).get('file_size', 'N/A')} bytes<br>
                                <strong>텍스트 길이:</strong> {extraction_result.get('text_length', 0)} 문자<br>
                                <strong>추출 방법:</strong> {extraction_result.get('metadata', {}).get('extraction_method', 'N/A')}
                            </div>
                            <div class="content">{extraction_result['text'].replace('<', '&lt;').replace('>', '&gt;')}</div>
                        </body>
                        </html>
                        """
                        
                        # HTML을 임시 파일로 저장하고 wkhtmltopdf로 PDF 변환
                        import tempfile, subprocess, shutil
                        with tempfile.TemporaryDirectory() as tmpdir:
                            html_file = Path(tmpdir) / "hwp_content.html"
                            with open(html_file, 'w', encoding='utf-8') as f:
                                f.write(html_content)
                            
                            # wkhtmltopdf로 PDF 변환
                            cmd = ['wkhtmltopdf', '--encoding', 'UTF-8', str(html_file), str(pdf_path)]
                            logger.info(f"wkhtmltopdf 변환 명령어: {' '.join(cmd)}")
                            
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                            if result.returncode == 0:
                                logger.info(f"HWP 텍스트 PDF 변환 성공: {pdf_path}")
                            else:
                                logger.error(f"wkhtmltopdf 변환 실패: {result.stderr}")
                                raise subprocess.CalledProcessError(result.returncode, cmd)
                    else:
                        logger.error(f"HWP 텍스트 추출 실패: {extraction_result.get('error', 'Unknown error')}")
                        raise Exception("HWP 텍스트 추출 실패")
                else:
                    # LibreOffice를 사용한 PDF 변환
                    import subprocess, tempfile
                    # 임시 디렉토리 생성
                    with tempfile.TemporaryDirectory() as temp_dir:
                        try:
                            # LibreOffice가 실행 중인 인스턴스가 있으면 종료
                            subprocess.run(["pkill", "-f", "soffice"], capture_output=True)
                            
                            # 환경 변수 설정 (한국어 폰트 지원)
                            env = os.environ.copy()
                            # 한국어 로케일 설정 (사용 가능한 경우)
                            env['LC_ALL'] = 'ko_KR.UTF-8'
                            env['LANG'] = 'ko_KR.UTF-8'
                            env['LC_CTYPE'] = 'ko_KR.UTF-8'
                            # HOME 디렉토리 설정 (LibreOffice 프로필 생성용)
                            env['HOME'] = os.path.expanduser('~')
                            
                            # PowerPoint에 특화된 고품질 PDF 변환 명령어
                            if file_extension in ['.ppt', '.pptx']:
                                # PowerPoint 최고 품질 변환을 위한 필터 옵션 (폰트 임베딩 활성화)
                                filter_options = "SelectPdfVersion=1;UseTaggedPDF=true;ExportFormFields=true;FormsType=0;ExportBookmarks=true;ExportHiddenSlides=false;SinglePageSheets=false;ExportNotes=false;ExportNotesPages=false;EmbedStandardFonts=true;UseTransitionEffects=false;IsSkipEmptyPages=true;IsAddStream=false;ExportPlaceholders=false;IsCollectPresentationModes=false;Quality=100;ReduceImageResolution=false;MaxImageResolution=600"
                                
                                cmd = [
                                    "libreoffice",
                                    "--headless",
                                    "--invisible",
                                    "--nodefault",
                                    "--nolockcheck",
                                    "--nologo",
                                    "--norestore",
                                    "--convert-to", f"pdf:impress_pdf_Export:{filter_options}",
                                    "--outdir", temp_dir,
                                    file_path
                                ]
                            else:
                                # Word, Excel 등 - 폰트 임베딩 활성화
                                # writer_pdf_Export 필터에서 EmbedStandardFonts=true로 폰트 임베딩
                                filter_options = "EmbedStandardFonts=true;ExportFormFields=true;UseTaggedPDF=true"
                                cmd = [
                                    "libreoffice",
                                    "--headless",
                                    "--invisible",
                                    "--nodefault",
                                    "--nolockcheck",
                                    "--nologo",
                                    "--norestore",
                                    "--convert-to", f"pdf:writer_pdf_Export:{filter_options}",
                                    "--outdir", temp_dir,
                                    file_path
                                ]
                            logger.info(f"LibreOffice 변환 명령어: {' '.join(cmd)}")
                            logger.info(f"변환 설정 - 파일 형식: {file_extension}, 품질: 최고, 이미지 해상도: 600DPI, 한국어 지원: 활성화")
                            
                            result = subprocess.run(
                                cmd,
                                capture_output=True,
                                text=True,
                                timeout=300,  # 5분으로 타임아웃 증가
                                env=env  # 한국어 로케일 환경 변수 적용
                            )
                            if result.returncode == 0:
                                original_filename = Path(file_path).stem
                                temp_pdf = Path(temp_dir) / f"{original_filename}.pdf"
                                logger.info(f"🔍 변환된 PDF 찾기: {temp_pdf}")
                                if temp_pdf.exists():
                                    import shutil
                                    shutil.copy2(temp_pdf, pdf_path)
                                    logger.info(f"PDF 변환 성공: {pdf_path}")
                                else:
                                    logger.error(f"변환된 PDF 파일을 찾을 수 없음: {temp_pdf}")
                                    logger.info(f"임시 디렉토리 내용: {list(Path(temp_dir).iterdir())}")
                                    raise FileNotFoundError("PDF 변환 실패")
                            else:
                                logger.error(f"LibreOffice 변환 실패: {result.stderr}")
                                raise subprocess.CalledProcessError(result.returncode, cmd)
                        except subprocess.TimeoutExpired:
                            logger.error("LibreOffice 변환 타임아웃")
                            raise HTTPException(status_code=500, detail="PDF 변환 시간 초과")
                        except subprocess.CalledProcessError as e:
                            logger.error(f"LibreOffice 변환 오류: {e}")
                            raise HTTPException(status_code=500, detail="PDF 변환 실패")
            else:
                logger.info(f"캐시된 PDF 사용: {pdf_path}")
            
            # 변환된 PDF 파일 반환
            if pdf_path.exists():
                # 한글 파일명을 안전하게 인코딩
                encoded_pdf_filename = urllib.parse.quote(pdf_filename)
                
                return FileResponse(
                    path=str(pdf_path),
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'inline; filename*=UTF-8\'\'{encoded_pdf_filename}'
                    }
                )
            else:
                logger.error(f"변환된 PDF 파일이 존재하지 않음: {pdf_path}")
                raise HTTPException(status_code=500, detail="PDF 변환 후 파일을 찾을 수 없습니다.")
                
        except Exception as e:
            logger.error(f"PDF 변환 중 오류: {e}")
            # 변환 실패 시 원본 파일을 다운로드로 제공
            logger.warning(f"PDF 변환 실패, 원본 파일 다운로드 제공: {filename}")
            
            # PowerPoint 파일의 경우 특별한 안내 메시지 추가
            error_message = "PDF 변환 실패"
            if file_extension in ['.ppt', '.pptx']:
                error_message = "PowerPoint 파일의 PDF 변환이 실패했습니다. 복잡한 애니메이션, 스마트아트, 또는 특수 효과가 포함된 경우 변환이 어려울 수 있습니다. 원본 파일을 다운로드하여 PowerPoint에서 직접 확인하시기 바랍니다."
            elif file_extension in ['.doc', '.docx']:
                error_message = "Word 문서 PDF 변환이 실패했습니다. 복잡한 표, 수식, 또는 특수 폰트가 포함된 경우 변환이 어려울 수 있습니다."
            elif file_extension in ['.xls', '.xlsx']:
                error_message = "Excel 파일 PDF 변환이 실패했습니다. 복잡한 차트, 매크로, 또는 여러 시트가 포함된 경우 변환이 어려울 수 있습니다."
            
            encoded_filename = urllib.parse.quote(filename)
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                # Office 파일의 적절한 MIME 타입 설정
                if file_extension in ['.doc', '.docx']:
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif file_extension in ['.xls', '.xlsx']:
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif file_extension in ['.ppt', '.pptx']:
                    mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                else:
                    mime_type = "application/octet-stream"
            
            return FileResponse(
                path=file_path,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'attachment; filename*=UTF-8\'\'{encoded_filename}',
                    "X-Error-Message": error_message
                }
            )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
    except Exception as e:
        logger.error(f"Office PDF 변환 오류: {e}")
        raise HTTPException(status_code=500, detail="Office 파일 처리 중 오류가 발생했습니다.")

@router.get("/files/download/{file_id}")
async def download_file(
    file_id: str,
    token: Optional[str] = Query(None, description="인증 토큰"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """파일 다운로드 (토큰 인증)"""
    
    # 토큰 추출
    auth_token = None
    if token:
        auth_token = token
    elif authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
        else:
            auth_token = authorization
    
    if not auth_token:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    
    # 사용자 인증
    user = await get_user_from_token(db, auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    
    # 파일 정보 조회 및 다운로드 로직
    try:
        from app.services.document.storage.file_storage_service import file_storage_service
        file_info = await file_storage_service.get_file_info(int(file_id))
        
        if not file_info:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        file_path = file_info.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        # 1) 로컬 파일이 존재하면 로컬로 제공
        abs_file_path = file_path
        if not os.path.isabs(abs_file_path):
            abs_file_path = os.path.abspath(file_path)
        if os.path.exists(abs_file_path):
            file_path = abs_file_path
        else:
            # 2) 로컬에 없고 S3 모드면 프리사인드 URL로 리다이렉트 (attachment)
            if getattr(settings, 'storage_backend', 'local') == 's3':
                try:
                    from app.services.core.aws_service import S3Service
                    s3 = S3Service()
                    filename = file_info.get("file_logical_name", f"file_{file_id}")
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    encoded_filename = urllib.parse.quote(filename)
                    disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
                    url = s3.generate_presigned_url(
                        object_key=file_path,
                        expires_in=getattr(settings, 's3_presign_expiry_seconds', 3600),
                        response_content_disposition=disposition,
                        response_content_type=mime_type,
                    )
                    return RedirectResponse(url, status_code=307)
                except Exception as e:
                    logger.error(f"S3 presigned URL 생성 실패(attachment): {e}")
                    raise HTTPException(status_code=500, detail="S3 파일 다운로드 중 오류가 발생했습니다.")
            raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")
        
        filename = file_info.get("file_logical_name", f"file_{file_id}")
        
        # MIME 타입 추정
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # 한글 파일명을 안전하게 인코딩
        encoded_filename = urllib.parse.quote(filename)
        
        return FileResponse(
            path=file_path,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
    except Exception as e:
        logger.error(f"파일 다운로드 오류: {e}")
        raise HTTPException(status_code=500, detail="파일 다운로드 중 오류가 발생했습니다.")


# =============================================================================
# 📄 특허 원문 PDF 프록시 (KIPRIS API)
# =============================================================================

@router.get("/files/patent-fulltext/{application_number}")
async def get_patent_fulltext_pdf(
    application_number: str,
    token: str = Query(..., description="인증 토큰"),
    db: AsyncSession = Depends(get_db)
):
    """
    KIPRIS Plus API를 통해 특허 원문 PDF를 조회하여 반환
    
    1. KIPRIS API로 PDF 다운로드 URL 조회
    2. PDF 다운로드
    3. 클라이언트에 스트리밍 반환
    """
    logger.info(f"📄 특허 원문 PDF 요청: {application_number}")
    
    # 사용자 인증
    user = await get_user_from_token(db, token)
    if not user:
        logger.error("❌ 사용자 인증 실패")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    
    logger.info(f"✅ 사용자 인증 성공: {user.username}")
    
    try:
        from app.services.patent.kipris_client import KIPRISClient
        
        client = KIPRISClient(settings.kipris_api_key)
        
        # 1. PDF 다운로드 URL 조회
        pdf_info = await client.get_full_text_pdf_url(application_number)
        
        if not pdf_info:
            logger.warning(f"⚠️ 특허 원문 PDF를 찾을 수 없음: {application_number}")
            raise HTTPException(
                status_code=404, 
                detail="특허 원문 PDF를 찾을 수 없습니다. 공개 전문이 없는 특허일 수 있습니다."
            )
        
        pdf_url = pdf_info.get("path")
        doc_name = pdf_info.get("docName", f"{application_number}.pdf")
        
        logger.info(f"📥 PDF 다운로드 시작: {application_number}")
        
        # 2. PDF 다운로드
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            response = await http_client.get(pdf_url, follow_redirects=True)
            response.raise_for_status()
            pdf_content = response.content
        
        logger.info(f"✅ PDF 다운로드 완료: {application_number} ({len(pdf_content)/1024:.1f} KB)")
        
        await client.close()
        
        # 3. PDF 반환
        encoded_filename = urllib.parse.quote(doc_name)
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
                "Content-Length": str(len(pdf_content)),
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 특허 원문 PDF 조회 실패: {application_number}, {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"특허 원문 PDF 조회 중 오류가 발생했습니다: {str(e)}"
        )

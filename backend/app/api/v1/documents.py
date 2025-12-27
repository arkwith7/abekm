"""
📄 WKMS 문서 관리 API - 메인 엔드포인트
===========================================

🎯 목적:
- 웹 프론트엔드에서 직접 사용하는 메인 문서 관리 API
- 컨테이너 기반 권한 관리와 통합된 문서 CRUD 기능 제공
- 단순하고 안정적인 기본 기능부터 시작하여 점진적 확장

🔗 API 관계도:
```
프론트엔드 (React)
    ↓ HTTP 요청
v1/documents.py (메인 API)
    ↓ 서비스 호출
permission_service ← container_service → document_service
    ↓ 데이터 처리
file_models (tb_file_bss_info, tb_file_dtl_info)
    ↓ 저장
PostgreSQL Database
```

📋 주요 기능:
1. 📂 컨테이너 목록 조회 (/containers)
2. 📤 문서 업로드 (/upload)  
3. 📜 문서 목록 조회 (/, /list)
4. 🔍 문서 검색 (/search)
5. 🗑️ 문서 삭제 (/{id})
6. 🔐 권한 검증 (/containers/{id}/validate)
7. 📊 업로드 진행률 (/upload-progress/{id})

🚀 확장 계획:
- [ ] 벡터 검색 기능 (→ v1/search.py로 분리 예정)
- [ ] 고급 문서 처리 (→ services/processing.py 연동)
- [ ] 실시간 업로드 진행률 (WebSocket)
- [ ] 문서 버전 관리
- [ ] 자동 태깅 및 분류

⚠️ 주의사항:
- 모든 엔드포인트는 사용자 인증 필수
- 컨테이너 권한 기반 접근 제어 적용
- 파일 크기 제한: 50MB (설정 가능)
- 지원 형식: PDF, DOCX, PPTX, XLSX, TXT, HWP
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Form, BackgroundTasks, Response
from fastapi.responses import JSONResponse, FileResponse
from starlette.responses import RedirectResponse
import mimetypes
import urllib.parse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_, or_, outerjoin, update

# 🔧 Core dependencies
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User

# 🎛️ Services
from app.services.auth.permission_service import permission_service
from app.services.auth.container_service import ContainerService
from app.services.document.document_service import document_service
from app.services.document.pipeline.integrated_document_pipeline_service import IntegratedDocumentPipelineService
from app.core.config import settings
# 🔮 Future extensions (주석 처리된 고급 기능들)
# from app.services.document_processor_service import document_processor_service
# from app.services.vector_storage_service import vector_storage_service
# from app.services.ai_service import ai_service

# 📊 Models
from app.models import TbKnowledgeContainers as Container, TbUserPermissions
from app.models import TbFileBssInfo, TbFileDtlInfo, TbAcademicDocumentMetadata

# 📋 Schemas
from app.schemas.document import (
    DocumentResponse, 
    DocumentListResponse, 
    DocumentUploadResponse,
    DocumentInfo,
    SearchRequest,
    SearchResponse,
    PreprocessResponse,
    ChunkRequest,
    ChunkResponse
)
from app.services.document.processing.document_preprocessing_service import document_preprocessing_service
from app.services.core.azure_blob_service import get_azure_blob_service

logger = logging.getLogger(__name__)

# 🔧 서비스 인스턴스 초기화
pipeline_service = IntegratedDocumentPipelineService()

# 🌐 FastAPI 라우터 설정
router = APIRouter(
    prefix="",  # /api/v1/documents는 main.py에서 설정
    tags=["📄 Documents"],
    responses={
        400: {"description": "잘못된 요청"},
        401: {"description": "인증 필요"},
        403: {"description": "권한 없음"},
        404: {"description": "리소스를 찾을 수 없음"},
        500: {"description": "서버 내부 오류"}
    }
)

# ⚙️ 업로드 설정
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', str(Path(__file__).parent.parent.parent.parent / "uploads")))
UPLOAD_DIR.mkdir(exist_ok=True)

# 📏 파일 제한 설정
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.hwp'}

# =============================================================================
# � 문서 유형 관리 엔드포인트
# =============================================================================

@router.get("/document-types",
           response_model=dict,
           summary="📋 지원하는 문서 유형 목록",
           description="""
           업로드 가능한 문서 유형 목록과 각 유형별 처리 옵션을 조회합니다.
           
           **반환 정보:**
           - 문서 유형 ID, 이름, 설명
           - 지원 파일 형식
           - 기본 처리 옵션
           """)
async def get_document_types():
    """
    🎯 기능: 지원하는 문서 유형 목록 조회
    📊 응답: { success: bool, document_types: [], total: int }
    🔐 권한: 로그인 사용자 전체
    """
    try:
        from app.schemas.document_types import get_all_document_types
        
        logger.info("문서 유형 목록 조회")
        
        document_types = get_all_document_types()
        
        response = {
            "success": True,
            "document_types": [dt.dict() for dt in document_types],
            "total": len(document_types)
        }
        
        logger.info(f"문서 유형 목록 조회 완료 - 총 {len(document_types)}개")
        return response
        
    except Exception as e:
        logger.error(f"문서 유형 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 유형 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# �📂 컨테이너 관리 엔드포인트
# =============================================================================

@router.get("/containers", 
           response_model=dict,
           summary="📂 사용자 접근 가능 컨테이너 목록",
           description="""
           사용자가 업로드 권한을 가진 컨테이너 목록을 조회합니다.
           
           **반환 정보:**
           - 컨테이너 ID, 이름, 설명
           - 사용자의 접근 권한 레벨
           - 계층 구조 정보
           """)
async def get_user_accessible_containers(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 사용자가 접근 가능한 컨테이너 목록 조회
    📊 응답: { success: bool, containers: [], total: int }
    🔐 권한: 로그인 사용자 전체
    """
    try:
        logger.info(f"컨테이너 목록 조회 시작 - 사용자: {user.emp_no}")
        
        # ContainerService 인스턴스 생성
        container_service = ContainerService(session)
        containers = await container_service.get_user_accessible_containers(
            user_emp_no=str(user.emp_no),
            session=session
        )
        
        response = {
            "success": True,
            "containers": containers,
            "total": len(containers),
            "user_emp_no": str(user.emp_no),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"컨테이너 목록 조회 완료 - 사용자: {user.emp_no}, 개수: {len(containers)}")
        return response
        
    except Exception as e:
        logger.error(f"컨테이너 목록 조회 실패 - 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"컨테이너 목록 조회 중 내부 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# 📤 문서 업로드 엔드포인트
# =============================================================================

@router.post("/upload", 
            response_model=DocumentUploadResponse,
            summary="📤 문서 업로드",
            description="""
            컨테이너에 문서를 업로드합니다.
            
            **처리 과정:**
            1. 컨테이너 권한 검증
            2. 파일 유효성 검사 (형식, 크기)
            3. 서버 파일 시스템에 저장
            4. 데이터베이스에 메타데이터 저장
            
            **향후 확장 예정:**
            - 텍스트 추출 및 NLP 처리
            - 벡터 임베딩 생성
            - 자동 태깅 및 분류
            """)
async def upload_document(
    file: UploadFile = File(..., description="업로드할 문서 파일"),
    container_id: Optional[str] = Form(..., description="문서가 저장될 컨테이너 ID"),
    document_type: str = Form("general", description="문서 유형 (general/academic_paper/patent/...)"),  # ✅ 추가
    processing_options: Optional[str] = Form(None, description="문서 유형별 처리 옵션 (JSON string)"),  # ✅ 추가
    use_multimodal: bool = Form(True, description="멀티모달 파이프라인 사용 여부 (기본: True)"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 문서 업로드 및 기본 파일 저장 (멀티모달 지원 + 문서 유형 분류)
    📋 단계:
        1. 컨테이너 권한 검증
        2. 파일 검증 및 저장
        3. 문서 유형 검증 및 처리 옵션 파싱
        4. 데이터베이스에 파일 정보 저장 (document_type, processing_options 포함)
        5. RAG 파이프라인 실행 (유형별 맞춤 파이프라인)
    🔐 권한: 컨테이너별 업로드 권한 필요
    📊 응답: DocumentUploadResponse (문서 ID, 파일 정보, 처리 통계)
    🎨 멀티모달: 객체 추출 → 청킹 → 임베딩 → 벡터 저장
    """
    upload_start_time = datetime.now()
    
    try:
        # 🔍 1단계: 컨테이너 필수 체크 및 권한 검증
        if not container_id:
            logger.error(f"❌ [UPLOAD-DEBUG] 컨테이너 ID 없음 - 파일: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail="업로드할 컨테이너를 선택해주세요."
            )
        
        logger.info(f"🚀 [UPLOAD-DEBUG] 문서 업로드 시작")
        safe_filename = file.filename or "uploaded_file"
        logger.info(f"   📄 파일명: {safe_filename}")
        logger.info(f"   👤 사용자: {user.emp_no}")
        logger.info(f"   📁 컨테이너: {container_id}")
        logger.info(f"   � 문서 유형: {document_type}")
        logger.info(f"   �📊 파일 크기: {file.size if file.size else 'Unknown'} bytes")
        
        # 📝 문서 유형 및 처리 옵션 검증
        import json
        from app.schemas.document_types import DocumentType, ProcessingOptionsFactory
        
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            logger.error(f"❌ [UPLOAD-DEBUG] 잘못된 문서 유형: {document_type}")
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 문서 유형입니다: {document_type}"
            )
        
        # 처리 옵션 파싱 및 검증
        parsed_options = {}
        if processing_options:
            try:
                parsed_options = json.loads(processing_options)
                logger.info(f"   ⚙️ 처리 옵션: {parsed_options}")
            except json.JSONDecodeError:
                logger.error(f"❌ [UPLOAD-DEBUG] 잘못된 JSON 형식: {processing_options}")
                raise HTTPException(
                    status_code=400,
                    detail="처리 옵션이 올바른 JSON 형식이 아닙니다."
                )
        
        # 옵션 검증 및 기본값 병합
        validated_options = ProcessingOptionsFactory.validate_options(
            doc_type_enum, 
            parsed_options
        )
        logger.info(f"   ✅ 검증된 옵션: {validated_options}")
        
        # 권한 확인
        logger.info(f"🔐 [UPLOAD-DEBUG] 권한 확인 시작")
        can_upload, permission_message = await permission_service.check_upload_permission(
            user_emp_no=str(user.emp_no),
            container_id=container_id
        )
        logger.info(f"🔐 [UPLOAD-DEBUG] 권한 확인 결과: {can_upload}, 메시지: {permission_message}")
        
        if not can_upload:
            logger.warning(f"❌ [UPLOAD-DEBUG] 업로드 권한 없음 - 사용자: {user.emp_no}, 컨테이너: {container_id}")
            raise HTTPException(
                status_code=403,
                detail=f"컨테이너 업로드 권한이 없습니다: {permission_message}"
            )
        
        # ✅ 2단계: 파일 검증
        logger.info(f"📋 [UPLOAD-DEBUG] 파일 검증 시작")
        validation_result = await _validate_upload_file(file)
        logger.info(f"📋 [UPLOAD-DEBUG] 파일 검증 결과: {validation_result['valid']}")
        
        if not validation_result["valid"]:
            logger.warning(f"❌ [UPLOAD-DEBUG] 파일 검증 실패 - 파일: {file.filename}, 오류: {validation_result['error']}")
            raise HTTPException(
                status_code=400,
                detail=validation_result["error"]
            )

        # 💾 3단계: 파일 저장 (로컬 임시)
        logger.info(f"💾 [UPLOAD-DEBUG] 파일 저장 시작")
        saved_file_path = await _save_upload_file(file)
        logger.info(f"💾 [UPLOAD-DEBUG] 파일 저장 완료 - 경로: {saved_file_path}")

        # 🪣 3-1단계: 객체 스토리지 업로드 (S3 또는 Azure Blob) - 실패 시 치명적 오류
        s3_object_key = None
        azure_blob_object_key = None
        try:
            from app.core.config import settings as app_settings
            storage_backend = getattr(app_settings, 'storage_backend', 'local')
        except Exception:
            storage_backend = 'local'

        try:
            from app.utils.storage_paths import build_raw_object_key, classify_key_scheme
        except Exception:
            build_raw_object_key = None  # type: ignore
            classify_key_scheme = lambda k: 'unknown'  # type: ignore

        # 원격 스토리지 업로드 실패 시 DB 저장 중단을 위한 플래그
        remote_upload_failed = False
        remote_upload_error = None

        if storage_backend == 's3':
            try:
                from app.services.core.aws_service import S3Service
                container_prefix = container_id.strip('/') if container_id else 'default'
                basename = os.path.basename(saved_file_path)
                # 새 스킴 적용 여부 판단
                if getattr(app_settings, 'use_standard_raw_prefix', False) and build_raw_object_key:
                    s3_object_key = build_raw_object_key(container_prefix, safe_filename, saved_file_path)
                else:
                    s3_object_key = f"{container_prefix}/{basename}"
                s3 = S3Service()
                await s3.upload_file(file_path=saved_file_path, object_key=s3_object_key)
                scheme = classify_key_scheme(s3_object_key)
                logger.info(f"🪣 [UPLOAD-DEBUG] S3 업로드 완료 - 키: {s3_object_key} (scheme={scheme})")
            except Exception as s3e:
                logger.error(f"❌ [UPLOAD-DEBUG] S3 업로드 실패: {s3e}")
                remote_upload_failed = True
                remote_upload_error = f"S3 업로드 실패: {str(s3e)}"
        elif storage_backend == 'azure_blob':
            try:
                from app.services.core.azure_blob_service import get_azure_blob_service
                container_prefix = container_id.strip('/') if container_id else 'default'
                basename = os.path.basename(saved_file_path)
                if getattr(app_settings, 'use_standard_raw_prefix', False) and build_raw_object_key:
                    azure_blob_object_key = build_raw_object_key(container_prefix, safe_filename, saved_file_path)
                else:
                    # 레거시 호환 (container/filename)
                    azure_blob_object_key = f"{container_prefix}/{basename}"
                azure = get_azure_blob_service()
                azure.upload_file(saved_file_path, azure_blob_object_key, purpose='raw')
                scheme = classify_key_scheme(azure_blob_object_key)
                logger.info(f"🪣 [UPLOAD-DEBUG] Azure Blob 업로드 완료 - 키: {azure_blob_object_key} (scheme={scheme})")
            except Exception as aze:
                logger.error(f"❌ [UPLOAD-DEBUG] Azure Blob 업로드 실패: {aze}")
                remote_upload_failed = True
                remote_upload_error = f"Azure Blob 업로드 실패: {str(aze)}"
        
        # 🚨 원격 스토리지 업로드 실패 시 즉시 중단 및 로컬 파일 정리
        if remote_upload_failed:
            if os.path.exists(saved_file_path):
                try:
                    os.remove(saved_file_path)
                    logger.info(f"🧹 [UPLOAD-DEBUG] 원격 업로드 실패 후 로컬 임시 파일 삭제: {saved_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ [UPLOAD-DEBUG] 로컬 임시 파일 삭제 실패: {cleanup_error}")
            raise HTTPException(
                status_code=500,
                detail=f"파일 저장 실패: {remote_upload_error}"
            )
        
        try:
            # 📊 4단계: 데이터베이스에 파일 정보 저장
            logger.info(f"📊 [UPLOAD-DEBUG] 문서 정보 저장 시작: {file.filename}")
            
            # 파일 정보 생성
            file_size = os.path.getsize(saved_file_path)
            file_extension = Path(safe_filename).suffix
            logger.info(f"📊 [UPLOAD-DEBUG] 파일 메타데이터 - 크기: {file_size}, 확장자: {file_extension}")
            
            # 📋 tb_file_bss_info에 기본 정보 저장
            logger.info(f"📊 [UPLOAD-DEBUG] document_service.create_document_from_upload 호출")
            # DB에는 S3 모드면 object key, 아니면 로컬 경로 저장
            # 저장 경로 결정: 우선순위 azure_blob > s3 > local
            db_file_path = azure_blob_object_key or s3_object_key or saved_file_path
            
            
            document_result = None
            try:
                # 🚀 비동기 백그라운드 처리 모드
                if use_multimodal:
                    # 멀티모달은 백그라운드에서 처리하고 즉시 응답
                    logger.info(f"🚀 [UPLOAD-DEBUG] 비동기 백그라운드 처리 시작")
                    
                    # 1) 기본 문서 정보만 DB에 저장 (RAG 파이프라인 제외)
                    document_result = await document_service.create_document_basic_info(
                        file_path=db_file_path,
                        file_name=safe_filename,
                        file_size=file_size,
                        file_extension=file_extension,
                        user_emp_no=str(user.emp_no),
                        container_id=container_id,
                        session=session,
                        processing_status='pending',  # 🆕 처리 대기 상태
                        document_type=document_type,  # ✅ 추가
                        processing_options=validated_options  # ✅ 추가
                    )
                    
                    if not document_result["success"]:
                        logger.error(f"❌ [UPLOAD-DEBUG] 문서 정보 저장 실패: {document_result.get('error')}")
                        await session.rollback()
                        raise HTTPException(
                            status_code=500,
                            detail=f"문서 정보 저장 실패: {document_result['error']}"
                        )
                    
                    document_id = document_result["document_id"]
                    logger.info(f"✅ [UPLOAD-DEBUG] 문서 기본 정보 저장 완료: doc_id={document_id}")
                    
                    # 2) 백그라운드 작업 등록
                    try:
                        from app.tasks.document_tasks import process_document_async
                        
                        # 🔧 Celery에 전달할 파일 경로 결정
                        # S3/Azure Blob이 있으면 해당 키 사용, 없으면 로컬 경로
                        processing_file_path = azure_blob_object_key or s3_object_key or saved_file_path
                        
                        background_provider = settings.get_current_llm_provider()

                        task = process_document_async.delay(
                            document_id=document_id,
                            file_path=processing_file_path,  # S3/Blob 키 또는 로컬 경로
                            container_id=container_id,
                            user_emp_no=str(user.emp_no),
                            provider=background_provider,
                            model_profile="default"
                        )
                        
                        logger.info(f"🔄 [UPLOAD-DEBUG] 백그라운드 작업 등록 완료: task_id={task.id}, doc_id={document_id}, path={processing_file_path}")
                        
                        # 응답에 태스크 ID 포함
                        document_result["task_id"] = task.id
                        document_result["processing_status"] = "processing"
                        
                    except Exception as task_error:
                        logger.error(f"❌ [UPLOAD-DEBUG] 백그라운드 작업 등록 실패: {task_error}")
                        # 작업 등록 실패 시 상태를 failed로 업데이트
                        update_stmt = (
                            update(TbFileBssInfo)
                            .where(TbFileBssInfo.file_bss_info_sno == document_id)
                            .values(processing_status='failed', processing_error=f"작업 등록 실패: {str(task_error)}")
                        )
                        await session.execute(update_stmt)
                        await session.commit()
                        raise
                else:
                    # 멀티모달 비활성화: 동기 방식 (기존 로직)
                    logger.info(f"📊 [UPLOAD-DEBUG] 동기 처리 모드 (멀티모달 비활성화)")
                    document_result = await document_service.create_document_from_upload(
                        file_path=db_file_path,
                        file_name=safe_filename,
                        file_size=file_size,
                        file_extension=file_extension,
                        user_emp_no=str(user.emp_no),
                        container_id=container_id,
                        session=session,
                        local_source_path=saved_file_path,
                        use_multimodal=False,
                        document_type=document_type,  # ✅ 추가
                        processing_options=validated_options  # ✅ 추가
                    )
                    
                    if not document_result["success"]:
                        logger.error(f"❌ [UPLOAD-DEBUG] 문서 정보 저장 실패: {document_result.get('error')}")
                        await session.rollback()
                        raise HTTPException(
                            status_code=500,
                            detail=f"문서 정보 저장 실패: {document_result['error']}"
                        )
                
                logger.info(f"📊 [UPLOAD-DEBUG] document_service 결과: success={document_result.get('success', False)}")
                
                if not document_result["success"]:
                    logger.error(f"❌ [UPLOAD-DEBUG] 문서 정보 저장 실패: {document_result.get('error')}")
                    # 🔄 DB 트랜잭션 롤백
                    await session.rollback()
                    logger.info(f"🔄 [UPLOAD-DEBUG] DB 트랜잭션 롤백 완료")
                    raise HTTPException(
                        status_code=500,
                        detail=f"문서 정보 저장 실패: {document_result['error']}"
                    )
            except HTTPException:
                raise
            except Exception as db_error:
                logger.error(f"❌ [UPLOAD-DEBUG] DB 저장 중 예외 발생: {db_error}")
                # 🔄 DB 트랜잭션 롤백
                await session.rollback()
                logger.info(f"🔄 [UPLOAD-DEBUG] DB 트랜잭션 롤백 완료")
                raise HTTPException(
                    status_code=500,
                    detail=f"데이터베이스 저장 중 오류 발생: {str(db_error)}"
                )
            
            # 🔄 5단계: 파이프라인은 DocumentService에서 실행됨 (중복 실행 제거)
            pipeline_result = {
                "success": True
            }
            
            # ⏱️ 처리 시간 계산
            processing_time = (datetime.now() - upload_start_time).total_seconds()
            
            # 🎉 5단계: 성공 응답 구성 (실제 파이프라인 결과 반영 + 멀티모달 메타데이터)
            mm_stats = document_result.get("multimodal")
            
            # 멀티모달 메타데이터 구성
            multimodal_meta = None
            if use_multimodal and mm_stats:
                multimodal_meta = {
                    "enabled": True,
                    "images": {
                        "count": mm_stats.get("images", 0),
                        "has_content": mm_stats.get("images", 0) > 0
                    },
                    "tables": {
                        "count": mm_stats.get("tables", 0),
                        "has_content": mm_stats.get("tables", 0) > 0
                    },
                    "charts": {
                        "count": mm_stats.get("figures", 0),
                        "has_content": mm_stats.get("figures", 0) > 0
                    },
                    "embeddings": {
                        "text_embeddings": mm_stats.get("embeddings_count", 0),
                        "clip_embeddings": mm_stats.get("clip_embeddings_count", 0),
                        "has_clip": mm_stats.get("clip_embeddings_count", 0) > 0
                    },
                    "visual_content_available": (
                        mm_stats.get("images", 0) > 0 or mm_stats.get("figures", 0) > 0
                    ),
                    "searchable_by_image": mm_stats.get("clip_embeddings_count", 0) > 0,
                    "processing_stages": mm_stats.get("stages", [])
                }
            
            response = DocumentUploadResponse(
                success=True,
                message="문서 업로드가 완료되었습니다.",
                document_id=document_result["document_id"],
                file_info={
                    "original_name": safe_filename,
                    "file_size": file_size,
                    "file_type": file_extension,
                    "file_hash": document_result.get("file_hash", ""),
                    "upload_time": upload_start_time.isoformat(),
                    "saved_path": db_file_path,
                    **({"s3_object_key": s3_object_key} if s3_object_key else {}),
                    **({"azure_blob_object_key": azure_blob_object_key} if azure_blob_object_key else {}),
                    # 기본 멀티모달 플래그 (하위 호환성)
                    "has_images": (mm_stats and mm_stats.get("images", 0) > 0) if use_multimodal else False,
                    "has_tables": (mm_stats and mm_stats.get("tables", 0) > 0) if use_multimodal else False,
                    "has_charts": (mm_stats and mm_stats.get("figures", 0) > 0) if use_multimodal else False,
                    "visual_content_available": use_multimodal and mm_stats and (mm_stats.get("images", 0) > 0 or mm_stats.get("figures", 0) > 0),
                },
                processing_stats={
                    "text_length": 0,  # 🔮 추후 텍스트 추출시 업데이트
                    "chunk_count": mm_stats.get("chunks_count", 0) if mm_stats else 0,
                    "processing_time": processing_time,
                    "quality_score": 1.0,  # 🔮 추후 품질 분석시 업데이트
                    "korean_ratio": 0.0,  # 🔮 추후 한국어 분석시 업데이트
                    "rag_pipeline_success": mm_stats.get("success", True) if mm_stats else True,
                    "rag_pipeline_error": mm_stats.get("error") if mm_stats else None,
                    # 멀티모달 처리 통계 (실제 결과)
                    "image_count": mm_stats.get("images", 0) if mm_stats else 0,
                    "table_count": mm_stats.get("tables", 0) if mm_stats else 0,
                    "chart_count": mm_stats.get("figures", 0) if mm_stats else 0,
                    "embeddings_count": mm_stats.get("embeddings_count", 0) if mm_stats else 0,
                    "vector_dimension": mm_stats.get("vector_dimension", 0) if mm_stats else 0,
                    "pipeline_elapsed": mm_stats.get("elapsed_seconds", 0) if mm_stats else 0,
                },
                korean_analysis={
                    "document_type": "unknown",  # 🔮 추후 분류 알고리즘 적용
                    "keywords": [],              # 🔮 추후 키워드 추출
                    "proper_nouns": []           # 🔮 추후 고유명사 추출
                },
                container_assignment={
                    "container_id": container_id,
                    "access_level": "VIEWER",  # 🔮 추후 동적 권한 설정
                    "auto_assigned": False
                },
                multimodal_metadata=multimodal_meta  # 멀티모달 메타데이터 추가
            )
            
            logger.info(f"문서 업로드 완료 - ID: {document_result['document_id']}, 파일: {file.filename}, 처리시간: {processing_time:.2f}초")
            
            # 🔢 컨테이너의 document_count 업데이트 (completed 상태만 집계)
            try:
                from app.services.auth.container_service import ContainerService
                container_service = ContainerService(session)
                updated_count = await container_service.update_container_document_count(container_id)
                logger.info(f"📊 [UPLOAD-DEBUG] 컨테이너 문서 개수 업데이트: {container_id} -> {updated_count}개")
            except Exception as count_error:
                logger.warning(f"⚠️ [UPLOAD-DEBUG] 컨테이너 문서 개수 업데이트 실패 (무시): {count_error}")
            
            # 🔧 로컬 임시 파일 정리 (S3/Blob 업로드 완료 후)
            # ⚠️ 주의: Celery 작업이 S3/Blob 키를 사용하므로 로컬 파일은 안전하게 삭제 가능
            try:
                if (s3_object_key or azure_blob_object_key) and os.path.exists(saved_file_path):
                    os.remove(saved_file_path)
                    logger.info(f"🧹 [UPLOAD-DEBUG] 로컬 임시 파일 삭제: {saved_file_path}")
            except Exception as cle:
                logger.warning(f"로컬 임시 파일 삭제 실패: {cle}")
            return response
            
        except Exception as processing_error:
            # 🗑️ 처리 실패 시 업로드된 파일 정리
            logger.error(f"❌ [UPLOAD-DEBUG] 문서 처리 실패, 정리 시작: {processing_error}")
            
            # DB 트랜잭션 롤백
            try:
                await session.rollback()
                logger.info(f"🔄 [UPLOAD-DEBUG] 예외 처리 블록에서 DB 트랜잭션 롤백 완료")
            except Exception as rollback_error:
                logger.warning(f"⚠️ [UPLOAD-DEBUG] DB 롤백 실패(이미 롤백되었을 수 있음): {rollback_error}")
            
            # 원격 스토리지 파일 삭제 시도
            if s3_object_key:
                try:
                    from app.services.core.aws_service import S3Service
                    s3 = S3Service()
                    await s3.delete_file(object_key=s3_object_key)
                    logger.info(f"🧹 [UPLOAD-DEBUG] S3 파일 삭제 완료: {s3_object_key}")
                except Exception as s3_cleanup_error:
                    logger.warning(f"⚠️ [UPLOAD-DEBUG] S3 파일 삭제 실패: {s3_cleanup_error}")
            
            if azure_blob_object_key:
                try:
                    from app.services.core.azure_blob_service import get_azure_blob_service
                    azure = get_azure_blob_service()
                    azure.delete_blob(azure_blob_object_key)
                    logger.info(f"🧹 [UPLOAD-DEBUG] Azure Blob 파일 삭제 완료: {azure_blob_object_key}")
                except Exception as azure_cleanup_error:
                    logger.warning(f"⚠️ [UPLOAD-DEBUG] Azure Blob 파일 삭제 실패: {azure_cleanup_error}")
            
            # 로컬 임시 파일 삭제
            if os.path.exists(saved_file_path):
                try:
                    os.remove(saved_file_path)
                    logger.info(f"🧹 [UPLOAD-DEBUG] 로컬 임시 파일 삭제 완료: {saved_file_path}")
                except Exception as local_cleanup_error:
                    logger.warning(f"⚠️ [UPLOAD-DEBUG] 로컬 임시 파일 삭제 실패: {local_cleanup_error}")
            
            raise processing_error
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 업로드 중 예외 발생 - 파일: {file.filename}, 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 업로드 중 내부 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# 🧪 전처리/청킹 분리 엔드포인트
# =============================================================================

@router.post("/preprocess",
            response_model=PreprocessResponse,
            summary="🧪 문서 전처리만 수행",
            description="파일 경로를 받아 텍스트 추출과 정제만 수행합니다. (DB 저장/임베딩/색인 없음)")
async def preprocess_only(
    file_path: str = Form(..., description="서버 내 접근 가능한 파일 경로"),
    container_id: Optional[str] = Form(None),
    user: User = Depends(get_current_user)
):
    try:
        ext = Path(file_path).suffix
        pre = await document_preprocessing_service.preprocess_document(
            file_path=file_path,
            file_extension=ext,
            container_id=container_id or "",
            user_emp_no=str(user.emp_no)
        )
        if not pre.get("success"):
            raise HTTPException(status_code=400, detail=pre.get("error", "전처리 실패"))

        cleaned = pre.get("cleaned_text", "")
        from app.services.document.processing.document_preprocessing_service import tiktoken
        tokenizer = tiktoken.get_encoding("cl100k_base")
        return PreprocessResponse(
            success=True,
            extracted_text=pre.get("extracted_text", ""),
            cleaned_text=cleaned,
            extraction_metadata=pre.get("extraction_metadata", {}),
            total_chars=len(cleaned),
            total_tokens=len(tokenizer.encode(cleaned))
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"전처리 전용 API 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk",
            response_model=ChunkResponse,
            summary="🧪 청킹만 수행",
            description="정제된 텍스트를 받아 청크 분할만 수행합니다. (DB 저장/임베딩/색인 없음)")
async def chunk_only(
    payload: ChunkRequest,
    user: User = Depends(get_current_user)
):
    try:
        res = document_preprocessing_service.chunk_text(
            payload.text,
            file_path=payload.file_name or "",
            container_id=payload.container_id or "",
            user_emp_no=str(user.emp_no)
        )
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error", "청킹 실패"))
        return ChunkResponse(
            success=True,
            total_chunks=res.get("total_chunks", 0),
            total_tokens=res.get("total_tokens", 0),
            chunks=res.get("chunks", []),
            metadata=res.get("metadata")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"청킹 전용 API 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# � 문서 처리 상태 조회 엔드포인트
# =============================================================================

@router.get("/{document_id}/status",
           summary="📊 문서 처리 상태 조회",
           description="""
           문서의 비동기 처리 상태를 조회합니다.
           
           **처리 상태:**
           - pending: 업로드 완료, 처리 대기 중
           - processing: 백그라운드에서 처리 중
           - completed: 처리 완료
           - failed: 처리 실패
           
           **진행률:**
           - 0%: pending
           - 10-95%: processing (시간 기반 추정)
           - 100%: completed
           """)
async def get_document_processing_status(
    document_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    문서 처리 상태 조회
    
    Returns:
        - document_id: 문서 ID
        - status: 처리 상태
        - progress: 진행률 (0-100)
        - error: 오류 메시지 (실패 시)
        - started_at: 처리 시작 시간
        - completed_at: 처리 완료 시간
    """
    try:
        # 문서 조회
        stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        # 권한 확인 (소유자 또는 컨테이너 접근 권한)
        if str(doc.owner_emp_no) != str(user.emp_no):
            # 컨테이너 접근 권한 확인
            _container_val = getattr(doc, 'knowledge_container_id', None)
            container_id = str(_container_val) if _container_val is not None else None
            if container_id:
                can_access, _ = await permission_service.check_download_permission(
                    user_emp_no=str(user.emp_no),
                    container_id=container_id
                )
                if not can_access:
                    raise HTTPException(status_code=403, detail="문서 접근 권한이 없습니다.")
        
        # 처리 상태 가져오기
        status = getattr(doc, 'processing_status', 'unknown')
        
        # 진행률 계산
        progress = 0
        if status == 'pending':
            progress = 0
        elif status == 'processing':
            # 처리 시작 후 경과 시간 기반 추정
            started = getattr(doc, 'processing_started_at', None)
            if started:
                from datetime import datetime
                elapsed = (datetime.now() - started).total_seconds()
                # 평균 98초 기준으로 진행률 추정 (최대 95%)
                progress = min(int((elapsed / 100) * 100), 95)
            else:
                progress = 10
        elif status == 'completed':
            progress = 100
        elif status == 'failed':
            progress = 0
        else:
            progress = 0
        
        # 시간 정보 포맷팅
        started_at = getattr(doc, 'processing_started_at', None)
        completed_at = getattr(doc, 'processing_completed_at', None)
        
        return {
            "success": True,
            "document_id": document_id,
            "file_name": doc.file_lgc_nm,
            "status": status,
            "progress": progress,
            "error": getattr(doc, 'processing_error', None),
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "message": _get_status_message(status, progress)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 상태 조회 실패 - doc_id: {document_id}, error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )


def _get_status_message(status: str, progress: int) -> str:
    """상태별 안내 메시지"""
    if status == 'pending':
        return "문서 처리를 시작합니다..."
    elif status == 'processing':
        if progress < 30:
            return "문서를 분석하고 있습니다..."
        elif progress < 70:
            return "텍스트와 이미지를 추출하고 있습니다..."
        else:
            return "임베딩을 생성하고 있습니다..."
    elif status == 'completed':
        return "문서 처리가 완료되었습니다."
    elif status == 'failed':
        return "문서 처리 중 오류가 발생했습니다."
    else:
        return "상태를 확인할 수 없습니다."


# =============================================================================
# 🔍 문서 검색 엔드포인트
# =============================================================================

@router.post("/search", 
            response_model=SearchResponse,
            summary="🔍 문서 검색",
            description="""
            키워드를 통한 문서 검색 기능입니다.
            
            **현재 구현:**
            - 기본 검색 인터페이스 제공
            
            **향후 확장 예정:**
            - 벡터 유사도 검색 (semantic)
            - 하이브리드 검색 (키워드 + 의미)
            - 멀티모달 검색 (텍스트 + 이미지)
            - AI 기반 질의응답
            """)
async def search_documents(
    search_request: SearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 문서 검색 (기본 구현 + 멀티모달/하이브리드 확장 대비)
    📋 단계: 권한 기반 필터링 및 기본 검색
    🔮 확장: 벡터 검색은 추후 /api/v1/search/ API로 분리 예정
    
    **멀티모달 검색 확장 포인트:**
    - search_mode: 'keyword', 'semantic', 'hybrid', 'multimodal'
    - image_query: 이미지 기반 검색 (향후 지원)
    - visual_similarity: 시각적 유사도 검색 (향후 지원)
    """
    try:
        logger.info(f"문서 검색 요청 - 쿼리: '{search_request.query}', 사용자: {user.emp_no}")
        
        # 검색 모드 결정 (향후 확장)
        search_mode = getattr(search_request, 'search_mode', 'keyword')  # 기본값: keyword
        
        # 🔮 기본 검색 결과 반환 (추후 벡터 검색 구현 예정)
        response = SearchResponse(
            success=True,
            query=search_request.query,
            results=[],
            total_found=0,
            search_metadata={
                "search_type": search_mode,  # ✅ 검색 모드
                "processing_time": 0.1,
                "timestamp": datetime.now().isoformat(),
                "user_emp_no": user.emp_no,
                # 멀티모달/하이브리드 검색 메타데이터 (향후 확장)
                "supports_multimodal": False,  # 🔮 향후 True로 변경
                "supports_hybrid": False,  # 🔮 향후 True로 변경
                "image_search_available": False,  # 🔮 향후 True로 변경
            },
            query_analysis={
                "original_query": search_request.query,
                "normalized_query": search_request.query.lower().strip(),
                "query_length": len(search_request.query),
                # 향후 확장: 쿼리 분석 결과
                "has_image_query": False,  # 🔮 이미지 쿼리 포함 여부
                "query_type": "text",  # 🔮 text, image, mixed
            }
        )
        
        logger.info(f"검색 완료 - 쿼리: '{search_request.query}', 결과: 0개 (기본 구현)")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 검색 중 예외 발생 - 쿼리: '{search_request.query}', 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검색 중 내부 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# 📜 문서 목록 조회 엔드포인트
# =============================================================================

@router.get("", 
           response_model=DocumentListResponse,
           summary="📜 문서 목록 조회",
           description="""
           사용자가 접근 가능한 문서 목록을 조회합니다.
           
           **필터링 옵션:**
           - 컨테이너별 필터링
           - 페이징 (skip, limit)
           - 권한 기반 자동 필터링
           """,
           status_code=200)
async def get_documents(
    skip: int = Query(0, ge=0, description="건너뛸 문서 수"),
    limit: int = Query(100, ge=1, le=100, description="조회할 문서 수 (최대 100)"),
    container_id: Optional[str] = Query(None, description="특정 컨테이너 필터링"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 사용자의 문서 목록 조회
    📋 단계: 권한 기반 필터링 → 페이징 → 응답 변환
    🔐 권한: 사용자별 접근 가능한 문서만 조회
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DOCUMENTS-API] 🎯 함수 진입 - user={user.emp_no}, container={container_id}")
    try:
        logger.info(f"[DOCUMENTS-API] 🚀 문서 목록 조회 시작 - 사용자: {user.emp_no}, skip: {skip}, limit: {limit}, container_id: {container_id}")
        
        # 📊 tb_file_bss_info와 tb_file_dtl_info JOIN하여 문서 목록 조회
        # 🔐 권한 기반 문서 필터링: 사용자가 접근 가능한 컨테이너의 문서만 표시
        # 🌩️ AWS 환경 필터링: bedrock으로 처리된 문서만 표시 (Azure 데이터 제외)
        from app.models.document.multimodal_models import DocExtractionSession
        
        accessible_containers_subquery = select(TbUserPermissions.container_id).where(
            and_(
                TbUserPermissions.user_emp_no == user.emp_no,
                TbUserPermissions.is_active == True
            )
        )
        
        # 현재 프로바이더(.env 설정)로 처리된 문서만 필터링
        from app.utils.provider_filters import get_provider_filter_with_status
        
        processed_documents_subquery = select(DocExtractionSession.file_bss_info_sno).where(
            get_provider_filter_with_status(DocExtractionSession, include_pending=False)
        ).distinct()
        
        query = select(TbFileBssInfo, TbFileDtlInfo).select_from(
            outerjoin(TbFileBssInfo, TbFileDtlInfo, 
                     TbFileBssInfo.file_dtl_info_sno == TbFileDtlInfo.file_dtl_info_sno)
        ).where(
            and_(
                TbFileBssInfo.del_yn != 'Y',  # 삭제되지 않은 문서만
                or_(
                    TbFileBssInfo.created_by == str(user.emp_no),  # 본인이 생성한 문서
                    TbFileBssInfo.knowledge_container_id.in_(accessible_containers_subquery)  # 권한이 있는 컨테이너의 문서
                ),
                # 🌩️ 프로바이더 환경 필터링: 현재 프로바이더로 처리된 문서 또는 아직 처리되지 않은 문서만 표시
                or_(
                    TbFileBssInfo.file_bss_info_sno.in_(processed_documents_subquery),  # 현재 프로바이더로 처리 완료된 문서
                    TbFileBssInfo.processing_status.in_(['pending', 'processing']),  # 처리 대기 중인 문서
                    TbFileBssInfo.document_type == 'patent',  # 특허는 URL 기반 문서 엔트리로 항상 표시
                )
            )
        ).order_by(desc(TbFileBssInfo.created_date))
        
        # 📦 컨테이너 필터링
        if container_id:
            query = query.where(TbFileBssInfo.knowledge_container_id == container_id)
        
        # 📄 페이징 적용 전에 전체 개수 조회
        count_query = select(func.count(TbFileBssInfo.file_bss_info_sno)).select_from(
            outerjoin(TbFileBssInfo, TbFileDtlInfo, 
                     TbFileBssInfo.file_dtl_info_sno == TbFileDtlInfo.file_dtl_info_sno)
        ).where(
            and_(
                TbFileBssInfo.del_yn != 'Y',  # 삭제되지 않은 문서만
                or_(
                    TbFileBssInfo.created_by == str(user.emp_no),  # 본인이 생성한 문서
                    TbFileBssInfo.knowledge_container_id.in_(accessible_containers_subquery)  # 권한이 있는 컨테이너의 문서
                ),
                # 🌩️ 프로바이더 환경 필터링: 현재 프로바이더로 처리된 문서 또는 아직 처리되지 않은 문서만
                or_(
                    TbFileBssInfo.file_bss_info_sno.in_(processed_documents_subquery),
                    TbFileBssInfo.processing_status.in_(['pending', 'processing']),
                    TbFileBssInfo.document_type == 'patent',
                )
            )
        )
        
        # 📦 컨테이너 필터링 (카운트에도 적용)
        if container_id:
            count_query = count_query.where(TbFileBssInfo.knowledge_container_id == container_id)
        
        # 전체 개수 조회
        total_count_result = await session.execute(count_query)
        total_count = total_count_result.scalar() or 0
        
        # 📄 페이징 적용
        query = query.offset(skip).limit(limit)
        
        result = await session.execute(query)
        rows = result.all()
        
        # 📋 DocumentInfo 형태로 변환
        documents = []
        for file_info, file_detail in rows:
            # 파일 크기는 상세 정보에서 가져오거나 기본값 사용
            file_size = file_detail.file_sz if file_detail else 0
            file_extension = ""
            if file_info.file_psl_nm:
                file_extension = Path(file_info.file_psl_nm).suffix.replace('.', '') if Path(file_info.file_psl_nm).suffix else ""
            
            documents.append(DocumentInfo(
                id=file_info.file_bss_info_sno,
                title=(file_detail.sj if file_detail else None) or file_info.file_lgc_nm or "제목 없음",
                file_name=file_info.file_psl_nm or "",
                file_size=file_size or 0,
                file_extension=file_extension,
                document_type=getattr(file_info, 'document_type', '') or '',  # 문서 유형 (patent 등)
                container_path=file_info.knowledge_container_id or "no_container",
                path=getattr(file_info, 'path', None),  # S3 URL 또는 파일 경로
                created_at=file_info.created_date,
                updated_at=file_info.last_modified_date,
                uploaded_by=file_info.created_by or "",
                # 비동기 처리 상태 필드 추가
                processing_status=getattr(file_info, 'processing_status', 'completed') or 'completed',
                processing_error=getattr(file_info, 'processing_error', None),
                processing_started_at=getattr(file_info, 'processing_started_at', None),
                processing_completed_at=getattr(file_info, 'processing_completed_at', None)
            ))
        
        response = DocumentListResponse(
            success=True,
            documents=documents,
            total=total_count,  # 전체 문서 수
            current_page_count=len(documents),  # 현재 페이지 문서 수
            skip=skip,
            limit=limit,
            has_next=skip + limit < total_count,  # 다음 페이지 여부
            has_previous=skip > 0,  # 이전 페이지 여부
            metadata={
                "user_emp_no": str(user.emp_no),
                "container_filter": container_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        logger.info(f"문서 목록 조회 완료 - 사용자: {user.emp_no}, 조회 건수: {len(documents)}")
        return response

    except HTTPException as http_ex:
        logger.error(f"[DOCUMENTS-API] ❌ HTTP 예외 발생 - status: {http_ex.status_code}, detail: {http_ex.detail}")
        raise
    except Exception as e:
        logger.error(f"[DOCUMENTS-API] ❌ 일반 예외 발생 - 사용자: {user.emp_no}, 오류: {str(e)}, 타입: {type(e).__name__}")
        import traceback
        logger.error(f"[DOCUMENTS-API] 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 목록 조회 중 내부 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# 🎓 학술 문서 필터 엔드포인트 (서지정보 기반)
# =============================================================================

@router.get("/filters/academic",
           response_model=DocumentListResponse,
           summary="🎓 학술 문서 필터 (연도/저널/DOI)",
           description="""
           tb_academic_document_metadata에 저장된 서지정보를 기준으로 문서를 필터링합니다.

           - year_gte/year_lte: 연도 범위 필터 (예: 2023년 이후)
           - journal: 저널명 포함(대소문자 무시)
           - doi: DOI 포함(부분 일치)
           - 권한: 사용자가 접근 가능한 컨테이너의 문서 또는 본인이 생성한 문서만
           """)
async def filter_academic_documents(
    year_gte: int = Query(None, ge=1800, le=2100, description="이 연도 이상"),
    year_lte: int = Query(None, ge=1800, le=2100, description="이 연도 이하"),
    journal: Optional[str] = Query(None, description="저널명 포함 검색"),
    doi: Optional[str] = Query(None, description="DOI 포함 검색"),
    container_id: Optional[str] = Query(None, description="특정 컨테이너 필터링"),
    skip: int = Query(0, ge=0, description="건너뛸 문서 수"),
    limit: int = Query(100, ge=1, le=100, description="조회할 문서 수 (최대 100)"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        logger.info(
            f"학술 문서 필터링 - 사용자: {user.emp_no}, year_gte={year_gte}, year_lte={year_lte}, journal={journal}, doi={doi}, container_id={container_id}, skip={skip}, limit={limit}"
        )

        # 접근 가능한 컨테이너 서브쿼리
        accessible_containers_subquery = select(TbUserPermissions.container_id).where(
            and_(
                TbUserPermissions.user_emp_no == user.emp_no,
                TbUserPermissions.is_active == True,
            )
        )

        # 기본 FROM: 파일 기본 + 학술 메타데이터 INNER JOIN, 파일 상세는 OUTER JOIN
        base_from = outerjoin(
            TbFileBssInfo,
            TbAcademicDocumentMetadata,
            TbFileBssInfo.file_bss_info_sno == TbAcademicDocumentMetadata.file_bss_info_sno,
        )
        base_from = outerjoin(
            base_from,
            TbFileDtlInfo,
            TbFileBssInfo.file_dtl_info_sno == TbFileDtlInfo.file_dtl_info_sno,
        )

        # WHERE: 권한 + 삭제 아님 + 메타데이터 존재
        conditions = [
            TbFileBssInfo.del_yn != 'Y',
            or_(
                TbFileBssInfo.created_by == str(user.emp_no),
                TbFileBssInfo.knowledge_container_id.in_(accessible_containers_subquery),
            ),
            TbAcademicDocumentMetadata.file_bss_info_sno.isnot(None),
        ]

        # 서지 필터 적용
        if journal:
            conditions.append(TbAcademicDocumentMetadata.journal.ilike(f"%{journal}%"))
        if doi:
            conditions.append(TbAcademicDocumentMetadata.doi.ilike(f"%{doi}%"))
        if year_gte is not None:
            # year는 4자리 문자열, 동일 길이이므로 문자열 비교로도 범위 동작
            conditions.append(TbAcademicDocumentMetadata.year >= str(year_gte))
        if year_lte is not None:
            conditions.append(TbAcademicDocumentMetadata.year <= str(year_lte))
        if container_id:
            conditions.append(TbFileBssInfo.knowledge_container_id == container_id)

        query = (
            select(TbFileBssInfo, TbFileDtlInfo, TbAcademicDocumentMetadata)
            .select_from(base_from)
            .where(and_(*conditions))
            .order_by(desc(TbFileBssInfo.created_date))
            .offset(skip)
            .limit(limit)
        )

        # 카운트 쿼리
        count_query = (
            select(func.count(TbFileBssInfo.file_bss_info_sno))
            .select_from(
                outerjoin(
                    TbFileBssInfo,
                    TbAcademicDocumentMetadata,
                    TbFileBssInfo.file_bss_info_sno == TbAcademicDocumentMetadata.file_bss_info_sno,
                )
            )
            .where(and_(*conditions))
        )

        total_count_result = await session.execute(count_query)
        total_count = total_count_result.scalar() or 0

        result = await session.execute(query)
        rows = result.all()

        documents: List[DocumentInfo] = []
        for file_info, file_detail, acad in rows:
            file_size = file_detail.file_sz if file_detail else 0
            file_extension = ""
            if file_info.file_psl_nm:
                file_extension = (
                    Path(file_info.file_psl_nm).suffix.replace('.', '')
                    if Path(file_info.file_psl_nm).suffix
                    else ""
                )

            title = (acad.title if acad and acad.title else None) or (
                file_detail.sj if file_detail and getattr(file_detail, 'sj', None) else None
            ) or file_info.file_lgc_nm or "제목 없음"

            documents.append(
                DocumentInfo(
                    id=file_info.file_bss_info_sno,
                    title=title,
                    file_name=file_info.file_psl_nm or "",
                    file_size=file_size or 0,
                    file_extension=file_extension,
                    document_type=getattr(file_info, 'document_type', '') or '',  # 문서 유형 (patent 등)
                    container_path=file_info.knowledge_container_id or "no_container",
                    path=getattr(file_info, 'path', None),  # S3 URL 또는 파일 경로
                    created_at=file_info.created_date,
                    updated_at=file_info.last_modified_date,
                    uploaded_by=file_info.created_by or "",
                    processing_status=getattr(file_info, 'processing_status', 'completed') or 'completed',
                    processing_error=getattr(file_info, 'processing_error', None),
                    processing_started_at=getattr(file_info, 'processing_started_at', None),
                    processing_completed_at=getattr(file_info, 'processing_completed_at', None),
                )
            )

        response = DocumentListResponse(
            success=True,
            documents=documents,
            total=total_count,
            current_page_count=len(documents),
            skip=skip,
            limit=limit,
            has_next=skip + limit < total_count,
            has_previous=skip > 0,
            metadata={
                "user_emp_no": str(user.emp_no),
                "filters": {
                    "year_gte": year_gte,
                    "year_lte": year_lte,
                    "journal": journal,
                    "doi": doi,
                    "container_id": container_id,
                },
                "timestamp": datetime.now().isoformat(),
            },
        )

        logger.info(f"학술 문서 필터링 완료 - 사용자: {user.emp_no}, 조회 건수: {len(documents)}/{total_count}")
        return response

    except Exception as e:
        logger.error(f"학술 문서 필터링 중 예외 발생 - 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(status_code=500, detail=f"학술 문서 필터링 중 내부 오류: {str(e)}")

# =============================================================================
# � 문서 다운로드 엔드포인트
# =============================================================================

@router.get("/{document_id}/download",
            summary="📥 문서 다운로드",
            description="""
            문서를 다운로드합니다.
            
            **권한 확인:**
            - 문서에 대한 읽기 권한이 있는 사용자만 다운로드 가능
            """)
async def download_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 문서 다운로드
    📋 단계: 권한 확인 → 파일 존재 확인 → Storage 검증 → 파일 전송
    🔐 권한: 문서 읽기 권한
    🌩️ Storage 검증: 현재 프로바이더와 일치하는 저장소인지 확인
    """
    try:
        from app.core.config import settings as app_settings
        
        logger.info(
            f"문서 다운로드 요청 - 문서 ID: {document_id}, 사용자: {getattr(user, 'emp_no', 'unknown')}"
        )

        # 문서 정보 조회
        query = select(TbFileBssInfo).where(
            and_(
                TbFileBssInfo.file_bss_info_sno == int(document_id),
                TbFileBssInfo.del_yn != 'Y'
            )
        )
        result = await session.execute(query)
        file_info = result.scalar_one_or_none()

        if not file_info:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        # 🔐 다운로드 권한 확인
        container_id = getattr(file_info, 'knowledge_container_id', None)
        logger.info(f"🔍 다운로드 권한 확인 시작 - 사용자: {user.emp_no}, 컨테이너: {container_id}")
        
        if container_id:
            can_download, permission_message = await permission_service.check_download_permission(
                user_emp_no=str(user.emp_no),
                container_id=container_id
            )
            logger.info(f"🔍 다운로드 권한 확인 결과 - can_download: {can_download}, message: {permission_message}")
            
            if not can_download:
                logger.warning(
                    f"다운로드 권한 없음 - 사용자: {user.emp_no}, 문서: {document_id}, 컨테이너: {container_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"문서 다운로드 권한이 없습니다: {permission_message}"
                )
        else:
            logger.warning(f"⚠️ 컨테이너 ID 없음 - 문서: {document_id}")
        
        logger.info(f"✅ 다운로드 권한 확인 완료 - 사용자: {user.emp_no}, 문서: {document_id}")

        # ✅ URL 기반 문서(특허 등)
        # - S3 URL(https://...amazonaws.com/...)은 presigned URL로 attachment 다운로드 제공
        # - 그 외 외부 URL은 URL 자체를 담은 .url(바로가기) 파일로 제공
        file_path_value = str(getattr(file_info, 'path', '') or '')
        if file_path_value.startswith('http://') or file_path_value.startswith('https://'):
            # S3 URL인 경우: presigned redirect는 XHR(blob 다운로드)에서 CORS 이슈가 날 수 있으므로
            # 서버가 S3에서 임시로 내려받아 동일 오리진으로 FileResponse 제공
            if ('.amazonaws.com' in file_path_value) or ('.s3.' in file_path_value):
                try:
                    from app.services.core.aws_service import S3Service
                    import tempfile
                    import os as _os

                    s3 = S3Service()
                    parsed = urllib.parse.urlparse(file_path_value)

                    # virtual-hosted style: https://bucket.s3.region.amazonaws.com/key  -> /key
                    object_key = parsed.path.lstrip('/')

                    # path-style: https://s3.region.amazonaws.com/bucket/key -> /bucket/key
                    bucket = getattr(settings, 's3_bucket_name', None)
                    if bucket and object_key.startswith(f"{bucket}/"):
                        object_key = object_key[len(bucket) + 1:]

                    filename = (
                        str(getattr(file_info, 'file_psl_nm', '') or '').strip()
                        or str(getattr(file_info, 'file_lgc_nm', '') or '').strip()
                        or f"document_{document_id}.pdf"
                    )
                    # MIME 타입
                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"

                    encoded_filename = urllib.parse.quote(filename)
                    disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

                    # 임시 파일로 다운로드 후 동일 오리진으로 반환
                    tmp_fd, tmp_path = tempfile.mkstemp(prefix='dl_', suffix=Path(filename).suffix or '.bin')
                    _os.close(tmp_fd)
                    await s3.download_file(object_key=object_key, local_path=tmp_path)

                    background_tasks.add_task(lambda p=tmp_path: _os.path.exists(p) and _os.remove(p))
                    logger.info(f"[DOWNLOAD] S3 URL 서버 프록시 다운로드: key={object_key}, filename={filename}")
                    return FileResponse(
                        path=tmp_path,
                        media_type=mime_type,
                        headers={"Content-Disposition": disposition},
                    )
                except Exception as e:
                    logger.error(f"[DOWNLOAD] S3 URL presign 실패: {e}")
                    raise HTTPException(status_code=500, detail="S3 파일 다운로드 중 오류가 발생했습니다.")

            logical_name = (
                str(getattr(file_info, 'file_lgc_nm', '') or '').strip()
                or str(getattr(file_info, 'file_psl_nm', '') or '').strip()
                or f"document_{document_id}"
            )
            # 확장자 보정
            if not logical_name.lower().endswith('.url'):
                logical_name = f"{logical_name}.url"
            encoded_name = urllib.parse.quote(str(logical_name))
            disposition = f"attachment; filename*=UTF-8''{encoded_name}"

            content = f"[InternetShortcut]\nURL={file_path_value}\n"
            response = Response(content=content, media_type='text/plain; charset=utf-8')
            response.headers['Content-Disposition'] = disposition
            response.headers['X-Content-Type-Options'] = 'nosniff'
            logger.info(f"[DOWNLOAD] URL 바로가기 파일 제공: {logical_name} -> {file_path_value}")
            return response

        # 🌩️ Storage 프로바이더 검증 (URL 문서는 제외)
        from app.utils.provider_filters import is_valid_storage_for_provider
        current_provider = app_settings.get_current_embedding_provider()
        if not is_valid_storage_for_provider(file_path_value):
            logger.warning(
                f"Storage 불일치 - 현재 환경: {current_provider}, 파일 경로: {file_path_value}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"이 문서는 다른 환경({current_provider})에서 처리되어 현재 환경에서 다운로드할 수 없습니다. "
                       f"문서를 재처리하거나 관리자에게 문의하세요."
            )

        # 파일 경로 확인 (상대/절대 경로 모두 처리)
        original_path_for_name = Path(file_path_value)
        file_path = original_path_for_name
        if not file_path.is_absolute():
            # backend 루트를 기준으로 보정 시도
            backend_root = Path(__file__).parent.parent.parent.parent
            file_path = (backend_root / file_path).resolve()

        # 로컬 파일 우선 확인
        if not file_path.exists():
            # 로컬에 없으면 S3 프리사인드 URL로 리다이렉트 시도
            try:
                from app.core.config import settings as app_settings
                storage_backend = getattr(app_settings, 'storage_backend', 'local')
            except Exception:
                storage_backend = 'local'

            looks_like_s3_key = (
                bool(file_path_value)
                and not os.path.isabs(file_path_value)
                and '/' in file_path_value
            )

            if storage_backend == 's3' and looks_like_s3_key:
                try:
                    from app.services.core.aws_service import S3Service
                    import tempfile
                    import os as _os

                    s3 = S3Service()

                    # 파일명 및 MIME 타입 계산
                    logical_name = (
                        str(getattr(file_info, 'file_lgc_nm', '') or '').strip()
                        or str(getattr(file_info, 'file_psl_nm', '') or '').strip()
                        or original_path_for_name.name
                    )
                    if '.' not in Path(logical_name).name:
                        logical_name = f"{logical_name}{original_path_for_name.suffix}"
                    mime_type, _ = mimetypes.guess_type(str(logical_name))
                    if not mime_type:
                        mime_type = 'application/octet-stream'
                    encoded_name = urllib.parse.quote(str(logical_name))
                    disposition = f"attachment; filename*=UTF-8''{encoded_name}"

                    # 서버에서 임시 파일로 다운로드 후 스트리밍 응답
                    tmp_fd, tmp_path = tempfile.mkstemp(prefix='dl_', suffix=original_path_for_name.suffix or '')
                    _os.close(tmp_fd)
                    await s3.download_file(object_key=file_path_value, local_path=tmp_path)

                    response = FileResponse(
                        path=str(tmp_path),
                        media_type=mime_type
                    )
                    response.headers["Content-Disposition"] = disposition
                    response.headers["X-Content-Type-Options"] = "nosniff"

                    # 응답 이후 임시 파일 삭제 (best-effort)
                    if background_tasks is not None:
                        background_tasks.add_task(_os.remove, tmp_path)

                    logger.info("[DOWNLOAD] S3 객체 프록시 다운로드 제공")
                    return response
                except Exception as e:
                    logger.error(f"S3 객체 프록시 다운로드 실패: {e}")
                    # 계속 진행하여 404 처리

            # Azure Blob Storage 처리
            elif storage_backend == 'azure_blob' and looks_like_s3_key:
                try:
                    from app.core.config import settings as app_settings
                    import tempfile
                    import os as _os
                    
                    # 다운로드 방식 설정: "redirect" 또는 "proxy" (기본값: redirect)
                    download_mode = getattr(app_settings, 'azure_blob_download_mode', 'redirect')
                    azure_blob = get_azure_blob_service()
                    
                    # file_path_value에서 purpose(container)와 blob_path 추출
                    # DB 저장 형식: "raw/WJ_MS_SERVICE/2025/10/filename.docx"
                    # Azure Blob 실제 경로: "raw/WJ_MS_SERVICE/2025/10/filename.docx" (프리픽스 포함!)
                    parts = file_path_value.split('/', 1)
                    if len(parts) == 2 and parts[0] in ['raw', 'intermediate', 'derived']:
                        # purpose가 명시된 경우
                        purpose = parts[0]  # "raw"
                        # ✅ 수정: Azure Blob에는 raw/ 프리픽스가 포함되어 저장되므로 전체 경로 사용
                        blob_path = file_path_value  # "raw/WJ_MS_SERVICE/2025/10/..."
                    else:
                        # purpose 없으면 기본 raw 사용
                        purpose = 'raw'
                        blob_path = f"raw/{file_path_value}"  # raw/ 프리픽스 추가
                    
                    if download_mode == 'redirect':
                        # 🔄 302 리다이렉트 방식 (기존 방식, Azure 직접 접근)
                        # 파일명 및 MIME 타입 계산
                        logical_name = (
                            str(getattr(file_info, 'file_lgc_nm', '') or '').strip()
                            or str(getattr(file_info, 'file_psl_nm', '') or '').strip()
                            or original_path_for_name.name
                        )
                        if '.' not in Path(logical_name).name:
                            logical_name = f"{logical_name}{original_path_for_name.suffix}"
                        mime_type, _ = mimetypes.guess_type(str(logical_name))
                        if not mime_type:
                            mime_type = 'application/octet-stream'
                        encoded_name = urllib.parse.quote(str(logical_name))
                        content_disposition = f"attachment; filename*=UTF-8''{encoded_name}"
                        
                        # SAS URL 생성 (1시간 유효, Content-Disposition 헤더 포함)
                        sas_url = azure_blob.generate_sas_url(
                            blob_path=blob_path,
                            purpose=purpose,
                            expiry_seconds=3600,
                            content_disposition=content_disposition,
                            content_type=mime_type
                        )
                        
                        if sas_url:
                            logger.info(f"[DOWNLOAD] Azure Blob SAS URL 리다이렉트 - purpose: {purpose}, blob: {blob_path}, filename: {logical_name}")
                            # 302 redirect로 클라이언트가 직접 Azure Blob에서 다운로드
                            return RedirectResponse(
                                url=sas_url,
                                status_code=302
                            )
                        else:
                            logger.error("Azure Blob SAS URL 생성 실패")
                    else:
                        # 📥 프록시 방식 (서버에서 임시 다운로드 후 전송, 프론트엔드 호환성 향상)
                        # 파일명 및 MIME 타입 계산
                        logical_name = (
                            str(getattr(file_info, 'file_lgc_nm', '') or '').strip()
                            or str(getattr(file_info, 'file_psl_nm', '') or '').strip()
                            or original_path_for_name.name
                        )
                        if '.' not in Path(logical_name).name:
                            logical_name = f"{logical_name}{original_path_for_name.suffix}"
                        mime_type, _ = mimetypes.guess_type(str(logical_name))
                        if not mime_type:
                            mime_type = 'application/octet-stream'
                        encoded_name = urllib.parse.quote(str(logical_name))
                        disposition = f"attachment; filename*=UTF-8''{encoded_name}"

                        # 서버에서 임시 파일로 다운로드 후 스트리밍 응답
                        tmp_fd, tmp_path = tempfile.mkstemp(prefix='dl_azure_', suffix=original_path_for_name.suffix or '')
                        _os.close(tmp_fd)
                        azure_blob.download_blob_to_file(blob_path, tmp_path, purpose=purpose)

                        response = FileResponse(
                            path=str(tmp_path),
                            media_type=mime_type
                        )
                        response.headers["Content-Disposition"] = disposition
                        response.headers["X-Content-Type-Options"] = "nosniff"

                        # 응답 이후 임시 파일 삭제 (best-effort)
                        if background_tasks is not None:
                            background_tasks.add_task(_os.remove, tmp_path)

                        logger.info(f"[DOWNLOAD] Azure Blob 프록시 다운로드 제공 - purpose: {purpose}, blob: {blob_path}")
                        return response
                        
                except Exception as e:
                    logger.error(f"Azure Blob 다운로드 실패: {e}")
                    # 계속 진행하여 404 처리

            logger.error(f"파일을 찾을 수 없음 - 경로: {file_path}")
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        # 접근 횟수 증가 (최선의 노력)
        try:
            current_count = int(getattr(file_info, 'access_count', 0) or 0)
            setattr(file_info, 'access_count', current_count + 1)
            setattr(file_info, 'last_accessed_date', datetime.now())
            await session.commit()
        except Exception as met_e:
            logger.warning(f"다운로드 메트릭 업데이트 실패: {met_e}")

        logger.info(
            f"문서 다운로드 시작 - 문서 ID: {document_id}, 논리명: {getattr(file_info, 'file_lgc_nm', None)}, 물리명: {getattr(file_info, 'file_psl_nm', None)}"
        )

        # MIME 타입 추정 (파일명 우선, 실패 시 경로 기반)
        # Prefer logical (original) filename; fallback to physical
        logical_name = (
            str(getattr(file_info, 'file_lgc_nm', '') or '').strip()
            or str(getattr(file_info, 'file_psl_nm', '') or '').strip()
            or file_path.name
        )
        # Ensure filename has extension; fallback to physical suffix
        if '.' not in Path(logical_name).name:
            # Attach physical extension if missing
            logical_name = f"{logical_name}{file_path.suffix}"
        mime_type, _ = mimetypes.guess_type(str(logical_name))
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            # Office 계열 기본값 보정
            suffix = file_path.suffix.lower()
            office_map = {
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ".ppt": "application/vnd.ms-powerpoint",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xls": "application/vnd.ms-excel",
                ".pdf": "application/pdf",
                ".txt": "text/plain",
            }
            mime_type = office_map.get(suffix, "application/octet-stream")

        # 파일명 인코딩 (한글 안전) - files.py와 동일한 방식 사용
        safe_name = str(logical_name)
        encoded_name = urllib.parse.quote(safe_name)

        # Debug: log what we're about to send
        logger.info(
            "[DOWNLOAD] 파일명/헤더 설정 - safe_name=%s, suffix=%s, mime=%s",
            safe_name,
            file_path.suffix,
            mime_type,
        )
        logger.info(
            "[DOWNLOAD] Content-Disposition preview: %s",
            f"attachment; filename*=UTF-8''{encoded_name}"
        )

        # Create FileResponse with only UTF-8 encoded filename (same as files.py)
        response = FileResponse(
            path=str(file_path),
            media_type=mime_type
        )
        
        # Set headers manually - only use filename* (UTF-8) to avoid latin-1 issues
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_name}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        logger.info("[DOWNLOAD] FileResponse 생성 완료")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 다운로드 실패 - 문서 ID: {document_id}, 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 다운로드 중 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# �🗑️ 문서 삭제 엔드포인트
# =============================================================================

@router.delete("/{document_id}",
              summary="🗑️ 문서 삭제",
              description="""
              문서를 삭제합니다 (소프트 삭제).
              
              **권한 확인:**
              - 문서 업로드자 본인만 삭제 가능
              - 관리자는 모든 문서 삭제 가능
              """)
async def delete_document(
    document_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 문서 삭제 (소프트 삭제)
    📋 단계: 권한 확인 → 소프트 삭제 → 물리적 파일 삭제
    🔐 권한: 문서 업로드자 또는 관리자
    """
    try:
        logger.info(f"문서 삭제 요청 - 문서 ID: {document_id}, 사용자: {user.emp_no}")
        
        result = await document_service.delete_document_by_id(
            document_id=document_id,
            user_emp_no=str(user.emp_no),
            session=session
        )
        
        if not result["success"]:
            if "찾을 수 없" in result["error"]:
                raise HTTPException(status_code=404, detail=result["error"])
            elif "권한" in result["error"]:
                raise HTTPException(status_code=403, detail=result["error"])
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        logger.info(f"문서 삭제 완료 - 문서 ID: {document_id}, 사용자: {user.emp_no}")
        return JSONResponse(content={
            **result,
            "timestamp": datetime.now().isoformat(),
            "deleted_by": user.emp_no
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 삭제 중 예외 발생 - 문서 ID: {document_id}, 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 삭제 중 내부 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# 🔐 권한 관리 엔드포인트
# =============================================================================

@router.post("/containers/{container_id}/validate",
            summary="🔐 컨테이너 권한 검증",
            description="""
            특정 컨테이너에 대한 업로드 권한을 검증합니다.
            
            **사용 목적:**
            - 프론트엔드에서 업로드 UI 활성화/비활성화 결정
            - 실시간 권한 상태 확인
            """)
async def validate_container_access(
    container_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 특정 컨테이너에 대한 접근 권한 검증
    📊 응답: 권한 유무, 권한 레벨, 메시지
    🔐 권한: 로그인 사용자 전체
    """
    try:
        logger.info(f"컨테이너 권한 검증 - 컨테이너: {container_id}, 사용자: {user.emp_no}")
        
        can_upload, permission_message = await permission_service.check_upload_permission(
            user_emp_no=str(user.emp_no),
            container_id=container_id
        )
        
        response = {
            "valid": can_upload,
            "container_id": container_id,
            "permission_message": permission_message,
            "access_level": "UPLOADER" if can_upload else "NONE",
            "user_emp_no": str(user.emp_no),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"컨테이너 권한 검증 완료 - 컨테이너: {container_id}, 사용자: {user.emp_no}, 권한: {can_upload}")
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"컨테이너 권한 검증 실패 - 컨테이너: {container_id}, 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# 📊 모니터링 엔드포인트
# =============================================================================

@router.get("/upload-progress/{upload_id}",
           summary="📊 업로드 진행률 조회",
           description="""
           업로드 진행 상황을 조회합니다.
           
           **현재 구현:**
           - 기본 완료 상태 반환
           
           **향후 확장 예정:**
           - 실시간 진행률 추적 (WebSocket)
           - 배치 업로드 진행률
           - 오류 상세 정보
           """)
async def get_upload_progress(
    upload_id: str,
    user: User = Depends(get_current_user)
):
    """
    🎯 기능: 업로드 진행 상황 조회 (기본 구현)
    🔮 확장: 실시간 진행률 추적은 추후 WebSocket으로 구현 예정
    """
    try:
        logger.info(f"업로드 진행률 조회 - ID: {upload_id}, 사용자: {user.emp_no}")
        
        # 🔮 기본 응답 반환 (추후 실시간 진행률 추적 구현 예정)
        progress = {
            "upload_id": upload_id,
            "status": "completed",  # pending, processing, completed, error
            "progress": 100,
            "message": "업로드 완료",
            "current_step": "완료",
            "total_steps": 1,
            "processing_time": 0.0,
            "user_emp_no": user.emp_no,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(content=progress)
        
    except Exception as e:
        logger.error(f"업로드 진행 상황 조회 실패 - ID: {upload_id}, 사용자: {user.emp_no}, 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# � 문서 청크 조회 엔드포인트
# =============================================================================

@router.get("/{file_bss_info_sno}/chunks",
           summary="📋 문서 청크 조회",
           description="""
           특정 문서의 모든 청크를 조회합니다.
           
           **기능:**
           - 문서의 모든 청크 목록 반환
           - 청크별 메타데이터 포함 (페이지, 섹션, 크기 등)
           - 권한 기반 접근 제어
           
           **응답 형식:**
           - chunks: 청크 목록
           - total_chunks: 총 청크 수
           - document_info: 문서 기본 정보
           """)
async def get_document_chunks(
    file_bss_info_sno: int,
    chunk_index: Optional[int] = Query(None, description="특정 청크 인덱스 (선택적)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    🎯 기능: 문서의 청크 조회
    📋 반환: 청크 목록과 메타데이터
    """
    try:
        logger.info(f"문서 청크 조회 - 문서 ID: {file_bss_info_sno}, 사용자: {user.emp_no}")
        
        # 1. 문서 존재 및 권한 확인
        from sqlalchemy import text
        doc_query = text("""
            SELECT fbi.file_bss_info_sno, fbi.file_lgc_nm, fbi.knowledge_container_id
            FROM tb_file_bss_info fbi
            WHERE fbi.file_bss_info_sno = :file_sno
            AND fbi.del_yn = 'N'
        """)
        
        doc_result = await db.execute(doc_query, {"file_sno": file_bss_info_sno})
        doc_row = doc_result.fetchone()
        
        if not doc_row:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        # 2. 컨테이너 권한 확인
        has_permission = await permission_service.check_container_permission(
            str(user.emp_no), doc_row.knowledge_container_id, "VIEWER"
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="문서 접근 권한이 없습니다.")
        
        # 3. 청크 조회 쿼리 구성
        if chunk_index is not None:
            # 특정 청크만 조회
            chunks_query = text("""
                SELECT 
                    chunk_sno,
                    file_bss_info_sno,
                    chunk_index,
                    chunk_text,
                    chunk_size,
                    page_number,
                    section_title,
                    keywords,
                    named_entities,
                    knowledge_container_id,
                    created_date,
                    last_modified_date
                FROM vs_doc_contents_chunks
                WHERE file_bss_info_sno = :file_sno 
                AND chunk_index = :chunk_idx
                AND del_yn = 'N'
                ORDER BY chunk_index
            """)
            chunks_result = await db.execute(chunks_query, {
                "file_sno": file_bss_info_sno,
                "chunk_idx": chunk_index
            })
        else:
            # 모든 청크 조회
            chunks_query = text("""
                SELECT 
                    chunk_sno,
                    file_bss_info_sno,
                    chunk_index,
                    chunk_text,
                    chunk_size,
                    page_number,
                    section_title,
                    keywords,
                    named_entities,
                    knowledge_container_id,
                    created_date,
                    last_modified_date
                FROM vs_doc_contents_chunks
                WHERE file_bss_info_sno = :file_sno 
                AND del_yn = 'N'
                ORDER BY chunk_index
            """)
            chunks_result = await db.execute(chunks_query, {"file_sno": file_bss_info_sno})
        
        # 4. 결과 처리
        chunks = []
        for row in chunks_result.fetchall():
            chunk_data = {
                "chunk_sno": row.chunk_sno,
                "chunk_index": row.chunk_index,
                "chunk_text": row.chunk_text,
                "chunk_size": row.chunk_size,
                "page_number": row.page_number,
                "section_title": row.section_title,
                "keywords": row.keywords.split(',') if row.keywords else [],
                "named_entities": row.named_entities.split(',') if row.named_entities else [],
                "created_date": row.created_date.isoformat() if row.created_date else None,
                "last_modified_date": row.last_modified_date.isoformat() if row.last_modified_date else None
            }
            chunks.append(chunk_data)
        
        # 5. 응답 구성
        response_data = {
            "success": True,
            "document_info": {
                "file_bss_info_sno": doc_row.file_bss_info_sno,
                "file_name": doc_row.file_lgc_nm,
                "container_id": doc_row.knowledge_container_id
            },
            "chunks": chunks,
            "total_chunks": len(chunks),
            "requested_chunk_index": chunk_index
        }
        
        logger.info(f"✅ 문서 청크 조회 완료 - 문서 ID: {file_bss_info_sno}, 청크 수: {len(chunks)}")
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 청크 조회 실패 - 문서 ID: {file_bss_info_sno}, 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# �🛠️ 헬퍼 함수들
# =============================================================================

async def _validate_upload_file(file: UploadFile) -> dict:
    """
    📋 업로드 파일 유효성 검사
    
    🔍 검증 항목:
    - 파일 확장자 (ALLOWED_EXTENSIONS)
    - 파일 크기 (MAX_FILE_SIZE)
    - 파일명 유효성
    
    📊 반환: {"valid": bool, "error": str}
    """
    
    # 📎 파일 확장자 검증
    if not file.filename:
        return {
            "valid": False,
            "error": "파일명이 제공되지 않았습니다."
        }
    
    safe_name = file.filename or "uploaded_file"
    file_ext = Path(safe_name).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return {
            "valid": False,
            "error": f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(ALLOWED_EXTENSIONS)}"
        }
    
    # 📏 파일 크기 검증 (헤더 기반)
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        return {
            "valid": False,
            "error": f"파일 크기가 너무 큽니다. 최대 크기: {MAX_FILE_SIZE // (1024*1024)}MB"
        }
    
    # 📝 파일명 검증
    if len(safe_name) > 255:
        return {
            "valid": False,
            "error": "파일명이 너무 깁니다. (최대 255자)"
        }
    
    # 🚫 보안: 위험한 파일명 패턴 체크
    dangerous_patterns = ['..', '/', '\\', '<', '>', '|', ':', '*', '?', '"']
    for pattern in dangerous_patterns:
        if pattern in safe_name:
            return {
                "valid": False,
                "error": f"파일명에 허용되지 않은 문자가 포함되어 있습니다: {pattern}"
            }
    
    return {"valid": True}

async def _save_upload_file(file: UploadFile) -> str:
    """
    💾 업로드 파일을 서버에 안전하게 저장
    
    🔧 처리 과정:
    1. 고유한 파일명 생성 (UUID + 원본 확장자)
    2. 서버 파일 시스템에 저장
    3. 저장 후 파일 크기 재검증
    
    📊 반환: 저장된 파일의 절대 경로
    🚫 예외: 파일 크기 초과시 자동 삭제 후 HTTPException
    """
    
    # 🆔 고유한 파일명 생성 (충돌 방지)
    safe_name = file.filename or "uploaded_file"
    file_extension = Path(safe_name).suffix
    unique_filename = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    try:
        # 💾 파일 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 📏 저장 후 실제 파일 크기 검증
        actual_file_size = os.path.getsize(file_path)
        if actual_file_size > MAX_FILE_SIZE:
            os.remove(file_path)  # 즉시 삭제
            raise HTTPException(
                status_code=413,
                detail=f"파일 크기가 너무 큽니다. 실제 크기: {actual_file_size // (1024*1024)}MB, 최대 허용: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # 📂 파일 권한 설정 (읽기 전용)
        os.chmod(file_path, 0o644)

        logger.info(f"파일 저장 성공 - 원본: {safe_name}, 저장: {unique_filename}, 크기: {actual_file_size:,} bytes")
        return str(file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        # 🗑️ 오류 발생시 부분 저장된 파일 정리
        if file_path.exists():
            os.remove(file_path)
        logger.error(f"파일 저장 실패 - 원본: {safe_name}, 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"파일 저장 중 오류가 발생했습니다: {str(e)}"
        )

# =============================================================================
# 📋 API 엔드포인트 요약
# =============================================================================
"""
🌐 WKMS Documents API v1 엔드포인트 목록:

📂 컨테이너 관리:
  GET  /containers                     - 접근 가능한 컨테이너 목록
  POST /containers/{id}/validate       - 컨테이너 권한 검증

📤 문서 업로드:
  POST /upload                         - 문서 업로드 (메인 기능)
  GET  /upload-progress/{id}           - 업로드 진행률 조회

📜 문서 조회:
  GET  /                              - 문서 목록 조회 (페이징 지원)
  
🔍 문서 검색:
  POST /search                        - 문서 검색 (기본 구현)

🗑️ 문서 관리:
  DELETE /{id}                        - 문서 삭제

🔮 향후 확장 예정:
  GET  /{id}                         - 문서 상세 조회
  PUT  /{id}                         - 문서 수정
  GET  /{id}/chunks                  - 문서 청크 조회 (벡터 검색용)
  POST /{id}/reindex                 - 문서 재인덱싱
  GET  /statistics                   - 문서 통계
  POST /batch-upload                 - 배치 업로드

📡 URL 구조:
  /api/v1/documents/                 - 메인 문서 API (이 파일)
  /api/v1/documents/containers       - 컨테이너 목록 조회 (통합됨)
  /api/services/processing/          - 문서 처리 서비스
  /api/services/large-files/         - 대용량 파일 처리
"""

# =============================================================================
# 🖼️ 이미지 청크 조회 API (멀티모달 검색용)
# =============================================================================

@router.get("/chunks/{chunk_id}/image",
    summary="청크 이미지 조회",
    description="이미지 청크의 이미지 파일을 Azure Blob Storage에서 가져와 반환합니다.",
    response_class=FileResponse
)
async def get_chunk_image(
    chunk_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🖼️ 청크 이미지 조회
    
    멀티모달 검색 결과에서 이미지 청크의 실제 이미지를 반환합니다.
    
    Args:
        chunk_id: 청크 ID
        user: 현재 로그인한 사용자
        db: 데이터베이스 세션
        
    Returns:
        이미지 파일 (PNG, JPEG 등)
    """
    logger.info(f"[IMAGE_CHUNK] ========== 엔드포인트 진입 ========== chunk_id={chunk_id}")
    try:
        logger.info(f"[IMAGE_CHUNK] 청크 이미지 조회 시작 - chunk_id={chunk_id}, user={user.emp_no}")
        
        # 1. doc_chunk 테이블에서 이미지 청크 정보 조회
        from app.models.document.multimodal_models import DocChunk, DocChunkSession
        from app.models import TbFileBssInfo
        
        stmt = (
            select(DocChunk, DocChunkSession, TbFileBssInfo)
            .join(DocChunkSession, DocChunk.chunk_session_id == DocChunkSession.chunk_session_id)
            .join(TbFileBssInfo, DocChunk.file_bss_info_sno == TbFileBssInfo.file_bss_info_sno)
            .where(DocChunk.chunk_id == chunk_id)
            .where(TbFileBssInfo.del_yn == 'N')
        )
        
        result = await db.execute(stmt)
        row = result.one_or_none()
        
        if not row:
            logger.warning(f"[IMAGE_CHUNK] 청크를 찾을 수 없음 - chunk_id={chunk_id}")
            raise HTTPException(status_code=404, detail="청크를 찾을 수 없습니다")
        
        chunk, chunk_session, file_info = row
        
        # 2. 권한 검증 - 사용자가 해당 컨테이너에 접근 권한이 있는지 확인
        from app.services.auth.permission_service import PermissionService
        
        permission_service = PermissionService(db)
        container_id = file_info.knowledge_container_id
        
        has_access = await permission_service.check_container_access(
            user_emp_no=str(user.emp_no),
            container_id=container_id
        )
        
        if not has_access:
            logger.warning(
                f"[IMAGE_CHUNK] 권한 없음 - user={user.emp_no}, "
                f"chunk_id={chunk_id}, container_id={container_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="해당 이미지에 접근할 권한이 없습니다"
            )
        
        logger.info(
            f"[IMAGE_CHUNK] 권한 확인 완료 - user={user.emp_no}, "
            f"container_id={container_id}"
        )
        
        # 3. modality 확인 (IMAGE 청크인지 검증)
        if chunk.modality != "image":
            logger.warning(f"[IMAGE_CHUNK] 이미지 청크가 아님 - chunk_id={chunk_id}, modality={chunk.modality}")
            raise HTTPException(status_code=400, detail="이미지 청크가 아닙니다")
        
        # 4. 이미지 blob 키 가져오기
        doc_id = chunk.file_bss_info_sno
        
        # 스토리지 백엔드에 따라 다운로드 함수 선택
        from app.core.config import settings
        
        async def _download_intermediate_blob(path: str) -> bytes:
            loop = asyncio.get_running_loop()
            
            if settings.storage_backend == "s3":
                # AWS S3에서 다운로드
                # path는 이미 "multimodal/23/objects/image_3940_5.png" 형식
                # S3Service.download_bytes()는 purpose='intermediate'로 prefix 자동 추가
                from app.services.core.aws_service import S3Service
                s3_service = S3Service()
                return await loop.run_in_executor(
                    None,
                    lambda: s3_service.download_bytes(path, purpose="intermediate")
                )
            else:
                # Azure Blob에서 다운로드
                blob_service = get_azure_blob_service()
                return await loop.run_in_executor(
                    None,
                    lambda: blob_service.download_blob_to_bytes(path, purpose="intermediate")
                )

        # blob_key가 있으면 직접 사용 (신규 방식)
        if chunk.blob_key:
            image_blob_key = chunk.blob_key
            logger.info(f"[IMAGE_CHUNK] blob_key 직접 사용: {image_blob_key}")
        else:
            # blob_key가 없으면 기존 방식으로 생성 (구 데이터 호환성)
            logger.warning(f"[IMAGE_CHUNK] blob_key 없음 (구 데이터) - chunk_id={chunk_id}, 동적 생성 시도")
            
            # source_object_ids에서 이미지 객체 ID 추출
            if not chunk.source_object_ids or len(chunk.source_object_ids) == 0:
                logger.error(f"[IMAGE_CHUNK] source_object_ids 없음 - chunk_id={chunk_id}")
                raise HTTPException(status_code=404, detail="이미지 객체 ID를 찾을 수 없습니다")
            
            # 첫 번째 source_object_id 사용 (이미지는 보통 하나의 객체만 참조)
            object_id = chunk.source_object_ids[0]
            
            # page_range에서 페이지 번호 추출
            page_number = 1  # 기본값
            if chunk.page_range:
                # page_range는 Range 객체로 반환됨
                page_number = chunk.page_range.lower if hasattr(chunk.page_range, 'lower') else 1
            
            # Blob 키 패턴: multimodal/{doc_id}/objects/image_{object_id}_{page_number}.png
            image_blob_key = f"multimodal/{doc_id}/objects/image_{object_id}_{page_number}.png"
            logger.info(f"[IMAGE_CHUNK] 동적 생성된 blob 키: {image_blob_key} (object_id={object_id}, page={page_number})")
        
        logger.info(f"[IMAGE_CHUNK] 이미지 다운로드 시도 - blob_key={image_blob_key}")
        
        # 5. Azure Blob Storage에서 이미지 다운로드
        try:
            image_bytes = await _download_intermediate_blob(image_blob_key)
            
            if not image_bytes:
                logger.error(f"[IMAGE_CHUNK] 이미지 다운로드 실패 - blob_key={image_blob_key}")
                raise HTTPException(status_code=404, detail="이미지 파일을 찾을 수 없습니다")
            
            logger.info(f"[IMAGE_CHUNK] 이미지 다운로드 성공 - size={len(image_bytes)} bytes")
            
            # 6. 임시 파일로 저장하고 반환
            import tempfile
            import os
            from fastapi.responses import FileResponse
            
            # 임시 파일 생성
            suffix = ".png"  # 기본 PNG
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(image_bytes)
                tmp_path = tmp_file.name
            
            logger.info(f"[IMAGE_CHUNK] 임시 파일 생성 완료 - path={tmp_path}")
            
            # FileResponse 반환 (자동으로 파일 삭제)
            return FileResponse(
                path=tmp_path,
                media_type="image/png",
                filename=f"image_chunk_{chunk_id}.png",
                background=None  # 응답 후 파일 유지 (cleanup은 OS가 처리)
            )
            
        except Exception as e:
            logger.error(f"[IMAGE_CHUNK] 이미지 처리 실패: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"이미지 처리 중 오류 발생: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[IMAGE_CHUNK] 이미지 조회 실패 - chunk_id={chunk_id}, error={str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"이미지 조회 중 오류가 발생했습니다: {str(e)}")


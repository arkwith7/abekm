from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
import asyncio
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

# =============================================================================
# 📦 v1 API 통합 Import
# =============================================================================
from app.api.v1.users import router as user_auth_router, user_router, sap_router
# auth_me.py 제거됨 - users.py에 통합됨
# test_auth.py 제거됨 - 테스트용 코드
# ⚠️ 일반 RAG 채팅 비활성화 (2025-12-09) - AI Agent로 통합
# from app.api.v1.chat import router as chat_router
from app.api.v1.presentation import router as presentation_router  # ✅ PPT 템플릿/생성 API (활성)
from app.api.v1.search import router as search_router
from app.api.v1.multimodal_search import router as multimodal_search_router  # 멀티모달 검색
from app.api.v1.files import router as files_router
from app.api.v1.permissions import router as permissions_router
from app.api.v1.permission_requests import router as permission_requests_router
from app.api.v1.containers import router as containers_router
from app.api.v1.documents import router as documents_router
from app.api.v1.document_access import router as document_access_router
from app.api.v1.agent import router as agent_router  # 🤖 Agent-based RAG
from app.api.v1.patent import router as patent_router  # 🔬 Patent Intelligence
from app.api.v1.endpoints.transcribe import router as transcribe_router  # 🎤 실시간 STT

from app.core.config import settings

def configure_logging():
    os.makedirs(settings.log_dir, exist_ok=True)

    def _prepare_log_file(target_path: str) -> str:
        """Ensure log file is writable; fall back to user home if necessary."""
        full_path = os.path.abspath(target_path)
        log_dir = os.path.dirname(full_path)
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(full_path, "a", encoding="utf-8"):
                pass
            return full_path
        except PermissionError:
            fallback_dir = os.path.join(os.path.expanduser("~"), ".abkms", "logs")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback_path = os.path.join(fallback_dir, os.path.basename(full_path))
            with open(fallback_path, "a", encoding="utf-8"):
                pass
            print(
                f"⚠️  로그 파일에 접근할 수 없어 임시 경로로 대체합니다: {fallback_path}"
            )
            return fallback_path
        except OSError as exc:
            fallback_dir = os.path.join(os.path.expanduser("~"), ".abkms", "logs")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback_path = os.path.join(fallback_dir, os.path.basename(full_path))
            with open(fallback_path, "a", encoding="utf-8"):
                pass
            print(
                f"⚠️  로그 폴더 준비 중 오류({exc})가 발생하여 임시 경로를 사용합니다: {fallback_path}"
            )
            return fallback_path

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear default handlers only once to avoid duplication on reload
    if not getattr(root_logger, "_abkms_logging_configured", False):
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)

        log_format_struct = {
            "json": '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
            "plain": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
        }
        fmt = log_format_struct.get(settings.log_format.lower(), log_format_struct["plain"])

        formatter = logging.Formatter(fmt, "%Y-%m-%dT%H:%M:%S")

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Rotating file handler (general)
        general_log_path = _prepare_log_file(settings.log_file_path())
        file_handler = RotatingFileHandler(
            filename=general_log_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Dedicated SQL query logger (separate file)
        if settings.sql_query_log_enabled:
            sql_fmt_map = {
                "json": '{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
                "plain": "[%(asctime)s] %(levelname)s %(message)s"
            }
            sql_fmt = sql_fmt_map.get(settings.sql_query_log_format.lower(), sql_fmt_map["plain"])
            sql_formatter = logging.Formatter(sql_fmt, "%Y-%m-%dT%H:%M:%S")
            sql_logger = logging.getLogger("app.sql")
            sql_log_path = _prepare_log_file(settings.sql_log_file_path())
            sql_file_handler = RotatingFileHandler(
                filename=sql_log_path,
                maxBytes=settings.log_max_bytes,
                backupCount=settings.log_backup_count,
                encoding="utf-8"
            )
            sql_level = getattr(logging, settings.sql_query_log_level.upper(), logging.INFO)
            sql_file_handler.setLevel(sql_level)
            sql_file_handler.setFormatter(sql_formatter)
            sql_logger.setLevel(sql_level)
            sql_logger.addHandler(sql_file_handler)
            # Propagation off to avoid duplicate in general log
            sql_logger.propagate = False

        root_logger._abkms_logging_configured = True  # type: ignore[attr-defined]

    # Reduce extremely chatty third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.psparser").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.pdfinterp").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.pdfdocument").setLevel(logging.WARNING)

    # =========================================================================
    # 🆕 Loguru Integration (Intercept Standard Logging)
    # =========================================================================
    import sys
    from loguru import logger as loguru_logger

    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = loguru_logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    # 1. Remove default Loguru handler
    loguru_logger.remove()

    # 2. Add File Handler (JSON or Plain)
    # Note: We use the same format as standard logging for consistency if needed,
    # but Loguru's power is in its own formatting. Here we align with settings.
    loguru_logger.add(
        settings.log_file_path(),
        rotation=settings.log_max_bytes,  # Pass int directly for bytes
        retention=settings.log_backup_count,
        level=settings.log_level.upper(),
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    # 3. Add Console Handler
    loguru_logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # 4. Intercept Standard Logging
    # Replace handlers on the root logger
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Ensure Uvicorn logs are also intercepted
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]

configure_logging()

# 로거 설정 (이 모듈 전용)
logger = logging.getLogger("app.main")

# =============================================================================
# 🔄 Lifespan 이벤트 관리 (Startup/Shutdown)
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan 이벤트 관리
    - Startup: 서버 시작 시 설정 정보 출력
    - Shutdown: 서버 종료 시 깔끔하게 정리
    """
        # ===== Startup =====
    print("\n" + "="*80)
    print("🚀 WKMS 백엔드 서버 시작")
    print("="*80)
    
    # 환경 정보 출력
    print(f"📍 환경: {settings.environment}")
    print(f"🗄️  데이터베이스: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'N/A'}")
    print(f"🔴 Redis: {settings.redis_host}:{settings.redis_port}/{settings.redis_db}")
    print(f"🌐 CORS: {len(settings.cors_origins)}개 origin 허용")
    print(f"📦 파일 업로드: {settings.upload_dir} (최대 {settings.max_file_size // 1024 // 1024}MB)")
    print(f"🤖 기본 LLM: {settings.default_llm_provider}")
    print(f"🧠 임베딩: {settings.default_embedding_provider or settings.default_llm_provider}")
    print(f"📄 문서 처리: {settings.document_processing_provider} (Fallback: {settings.document_processing_fallback or 'None'})")
    
    # Upstage 설정 확인
    if settings.document_processing_provider.lower() == "upstage" or settings.document_processing_fallback and settings.document_processing_fallback.lower() == "upstage":
        upstage_configured = bool(settings.upstage_api_key)
        print(f"🔷 Upstage API: {'✅ 설정됨' if upstage_configured else '❌ 미설정'}")
        if upstage_configured:
            print(f"   - Endpoint: {settings.upstage_api_endpoint}")
            print(f"   - Max Pages: {settings.upstage_max_pages}")
            print(f"   - Timeout: {settings.upstage_timeout_seconds}s")
    
    print("="*80 + "\n")
    
    # 로거에도 기록
    logger.info("ABKMS API 서버 시작됨")
    logger.info(f"LLM 공급자: {settings.get_current_llm_provider()}")
    logger.info(f"LLM 모델: {settings.get_current_llm_model()}")
    logger.info(f"텍스트 임베딩 모델: {settings.get_current_embedding_model()}")
    logger.info(f"텍스트 임베딩 차원: {settings.get_current_embedding_dimension()}")
    if settings.is_multimodal_enabled():
        logger.info(f"멀티모달 임베딩 모델: {settings.get_current_multimodal_embedding_model()}")
        logger.info(f"멀티모달 임베딩 차원: {settings.get_current_multimodal_embedding_dimension()}")
    else:
        logger.warning("멀티모달 검색 비활성화 - 멀티모달 임베딩 모델 미설정")

    # SQLAlchemy 로그 레벨 조정
    try:
        sa_engine_logger = logging.getLogger("sqlalchemy.engine")
        sa_engine_logger.setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        logger.info("SQLAlchemy engine log level set to WARNING")
    except Exception as e:
        logger.warning(f"Failed to set SQLAlchemy log level: {e}")
    
    yield  # 서버 실행
    
    # ===== Shutdown =====
    try:
        logger.info("🛑 서버 종료 프로세스 시작...")
        
        # 진행 중인 비동기 작업들에 짧은 대기 시간 부여
        await asyncio.sleep(0.1)
        
        logger.info("✅ 서버가 정상적으로 종료되었습니다.")
    except asyncio.CancelledError:
        # CancelledError는 정상적인 종료 과정이므로 조용히 처리
        logger.debug("Lifespan shutdown cancelled (normal during Ctrl+C)")
    except Exception as e:
        logger.error(f"서버 종료 중 예외 발생: {e}", exc_info=True)

app = FastAPI(
    title="ABKMS API",
    description="ABKMS - AI-Based Knowledge Management System API",
    version="1.0.0",
    lifespan=lifespan  # Lifespan 이벤트 핸들러 등록
)

# CORS 미들웨어 설정 (디버그: 환경 변수 원본도 출력)
import os as _os
_env_cors = _os.getenv("CORS_ORIGINS") or _os.getenv("CORS_ORIGIN")
print(f"🔧 CORS Origins 설정: {settings.cors_origins}")
if _env_cors:
    print(f"🔍 CORS_ORIGINS 환경변수 원본: {_env_cors}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose headers so frontend can read file name and type for downloads
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type", "X-Filename"],
)

# 정적 업로드 파일 제공 (/uploads)
try:
    app.mount("/uploads", StaticFiles(directory=str(settings.resolved_upload_dir)), name="uploads")
except Exception:
    # 기본 uploads 폴더 시도
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# =============================================================================
#  v1 API 라우터 등록 (리팩토링된 구조)
# =============================================================================

# 🔐 사용자 인증 및 관리 API
app.include_router(user_auth_router)  # /api/v1/auth - 로그인, 로그아웃, 리프레시, /me
app.include_router(user_router)       # /api/v1/users - 사용자 CRUD
app.include_router(sap_router)        # /api/v1/sap - SAP HR 정보 관리
# auth_me_router 제거됨 - users.py의 router에 통합됨 (/api/v1/auth/me)
# test_auth_router 제거됨 - 테스트용 코드

# 💬 핵심 기능 API들
# ⚠️ 일반 RAG 채팅 비활성화 (2025-12-09) - AI Agent로 통합
# app.include_router(chat_router, prefix="/api/v1")
app.include_router(presentation_router, prefix="/api/v1")  # ✅ PPT 템플릿/생성 API (프론트엔드 사용 중)
app.include_router(search_router, prefix="/api/v1")

# 🤖 Agent-based RAG API (Phase 2)
app.include_router(agent_router, prefix="/api/v1", tags=["🤖 Agent RAG"])

# 🔬 Patent Intelligence API (Enterprise Intelligence)
app.include_router(patent_router, prefix="/api/v1", tags=["🔬 Patent Intelligence"])

# 🔍 멀티모달 검색 API (텍스트 + 이미지)
app.include_router(multimodal_search_router, prefix="/api/v1", tags=["🔍 Multimodal Search"])

# 📄 문서 관리 API (프론트엔드 메인 사용)
app.include_router(documents_router, prefix="/api/v1/documents")

# 📊 대시보드 API
from app.api.v1.dashboard import router as dashboard_router
app.include_router(dashboard_router)

# 📁 파일 관리 API (통합된 파일 처리)
app.include_router(files_router, prefix="/api", tags=["📁 File Management"])

# 🗂️ 컨테이너 관리 API
app.include_router(containers_router, prefix="/api/v1/containers")

# 🔐 권한 관리 시스템 (통합된 권한 관리)
app.include_router(permissions_router, prefix="/api/v1/permissions")
app.include_router(permission_requests_router, prefix="/api/v1/permission-requests")

# 📄 문서 접근 제어 API (Phase 2)
app.include_router(document_access_router, prefix="/api/v1")

# 🎤 실시간 음성→텍스트 변환 API (AWS Transcribe Streaming)
app.include_router(transcribe_router, prefix="/api/v1/transcribe", tags=["🎤 Speech-to-Text"])

@app.get("/")
async def root():
    return {
        "message": "ABKMS API with Korean NLP is running",
        "features": ["한국어 처리", "하이브리드 검색", "AWS Bedrock", "MS Office + HWP 지원", "문서 자동 처리"],
        "version": "v1.0.0",
        "api_structure": "리팩토링 완료"
    }

@app.get("/favicon.ico")
async def favicon():
    """favicon.ico 요청 처리 - 404 에러 방지"""
    return {"status": "no favicon"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "ABKMS",
        "ai_providers": "multi-vendor",
        "korean_support": "enabled",
        "api_version": "v1",
        "current_config": {
            "llm_provider": settings.get_current_llm_provider(),
            "llm_model": settings.get_current_llm_model(),
            "embedding_model": settings.get_current_embedding_model(),
            "embedding_dimension": settings.get_current_embedding_dimension()
        }
    }

if __name__ == "__main__":
    import uvicorn
    # nest_asyncio와 호환을 위해 uvloop 비활성화
    uvicorn.run(app, host="0.0.0.0", port=8000, loop="asyncio")

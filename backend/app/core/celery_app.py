"""
Celery 애플리케이션 설정
===========================

비동기 백그라운드 작업 처리를 위한 Celery 설정
- 문서 처리 (DI 분석, 임베딩 생성)
- 대용량 파일 처리
- 장시간 실행 작업

사용법:
-------
# Celery Worker 실행
celery -A app.core.celery_app worker --loglevel=info

# Flower 모니터링 (선택)
celery -A app.core.celery_app flower --port=5555
"""

from celery import Celery
from celery.signals import worker_process_init
import os

# 환경 변수에서 Redis URL 가져오기
# 우선순위:
# 1) REDIS_URL (컨테이너/운영에서 compose로 주입하기 쉬움)
# 2) REDIS_HOST/REDIS_PORT/REDIS_DB (로컬 개발/세부 설정용)
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_db = os.getenv("REDIS_DB", "0")
    REDIS_URL = f"redis://{redis_host}:{redis_port}/{redis_db}"

# Celery 앱 초기화
celery_app = Celery(
    "wkms",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.document_tasks']  # 태스크 모듈 자동 로드
)

# Celery 설정
celery_app.conf.update(
    # 직렬화 설정
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 시간대 설정
    timezone='Asia/Seoul',
    enable_utc=True,
    
    # 작업 추적
    task_track_started=True,
    task_time_limit=3600,  # 1시간 제한 (대용량 파일 처리 고려)
    task_soft_time_limit=3300,  # 55분 소프트 제한 (경고)
    
    # 결과 백엔드 설정
    result_expires=3600,  # 결과 1시간 보관
    result_extended=True,  # 확장 결과 정보 포함
    
    # Worker 설정
    worker_prefetch_multiplier=1,  # 한 번에 1개 작업만 가져오기 (메모리 절약)
    worker_max_tasks_per_child=50,  # Worker 프로세스 재시작 (메모리 누수 방지)
    
    # 재시도 설정
    task_acks_late=True,  # 작업 완료 후 ACK
    task_reject_on_worker_lost=True,  # Worker 손실 시 작업 재할당
)

# Celery Beat 스케줄 (주기적 작업 - 선택)
celery_app.conf.beat_schedule = {
    # 예: 매일 자정 Orphan 파일 정리
    # 'cleanup-orphan-files': {
    #     'task': 'app.tasks.document_tasks.cleanup_orphan_files',
    #     'schedule': crontab(hour=0, minute=0),
    # },
}

# Celery Worker 프로세스 초기화 시 무거운 서비스 프리로드
@worker_process_init.connect
def init_worker_process_handler(**kwargs):
    """
    Celery Worker 프로세스가 시작될 때 한 번만 실행
    
    무거운 서비스들을 미리 초기화하여 태스크 실행 시 지연 제거:
    - Kiwi 형태소 분석기 (~5초)
    - KSS 문장 분리기 (~5초)
    - Azure/AWS AI 클라이언트 (~2초)
    
    예상 효과: 매 태스크마다 17초 초기화 시간 제거
    """
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.info("🔧 [WORKER-INIT] Celery Worker 프로세스 초기화 시작...")
    
    try:
        # 0. Config 로드 (settings 객체는 여기서 import해야 .env를 제대로 읽음)
        from app.core.config import settings
        
        # 1. Korean NLP Service (Kiwi, KSS) 프리로드
        from app.services.core.korean_nlp_service import KoreanNLPService
        nlp_start = time.time()
        nlp_service = KoreanNLPService()
        nlp_time = time.time() - nlp_start
        logger.info(f"✅ [WORKER-INIT] KoreanNLPService 초기화 완료 ({nlp_time:.2f}초)")
        
        # 2. Embedding Service (Azure OpenAI, Bedrock) 프리로드
        from app.services.core.embedding_service import EmbeddingService
        emb_start = time.time()
        emb_service = EmbeddingService()
        emb_time = time.time() - emb_start
        logger.info(f"✅ [WORKER-INIT] EmbeddingService 초기화 완료 ({emb_time:.2f}초)")
        
        # 3. Document Processing Service 프리로드 (provider에 따라 선택)
        doc_provider = settings.document_processing_provider.lower()
        logger.info(f"📄 [WORKER-INIT] 문서 처리 제공자: {doc_provider}")
        
        if doc_provider == "upstage":
            from app.services.document.extraction.upstage_document_service import UpstageDocumentService
            doc_start = time.time()
            doc_service = UpstageDocumentService()
            doc_time = time.time() - doc_start
            logger.info(f"✅ [WORKER-INIT] UpstageDocumentService 초기화 완료 ({doc_time:.2f}초)")
        elif doc_provider == "azure_di":
            from app.services.document.extraction.azure_document_intelligence_service import AzureDocumentIntelligenceService
            doc_start = time.time()
            doc_service = AzureDocumentIntelligenceService()
            doc_time = time.time() - doc_start
            logger.info(f"✅ [WORKER-INIT] AzureDocumentIntelligenceService 초기화 완료 ({doc_time:.2f}초)")
        else:
            logger.warning(f"⚠️ [WORKER-INIT] 알 수 없는 문서 처리 제공자: {doc_provider}")
        
        total_time = time.time() - start_time
        logger.info(f"🎉 [WORKER-INIT] 전체 초기화 완료 ({total_time:.2f}초)")
        logger.info(f"📊 [WORKER-INIT] 이제 태스크가 즉시 실행됩니다 (초기화 지연 없음)")
        
    except Exception as e:
        logger.error(f"❌ [WORKER-INIT] 초기화 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == '__main__':
    celery_app.start()

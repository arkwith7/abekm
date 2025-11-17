"""
문서 처리 비동기 백그라운드 태스크
====================================

Celery를 사용한 문서 처리 백그라운드 작업
- 문서 업로드 후 DI 분석, 임베딩 생성
- 장시간 실행 작업을 백그라운드에서 처리
- 처리 상태를 DB에 기록

사용법:
-------
from app.tasks.document_tasks import process_document_async

# 태스크 호출
task = process_document_async.delay(
    document_id=123,
    file_path="/path/to/file.pdf",
    container_id="container_1",
    user_emp_no="12345"
)

# 태스크 ID로 상태 조회
result = AsyncResult(task.id)
"""

from celery import Task
from app.core.celery_app import celery_app
from datetime import datetime
import logging
import asyncio
import nest_asyncio
from typing import Optional, Dict, Any, cast

# Celery Worker에서 asyncio.run() 사용을 위한 설정
nest_asyncio.apply()
import traceback

from app.core.config import settings

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """
    상태 업데이트를 자동으로 처리하는 커스텀 Task 클래스
    
    작업 실패 시 자동으로 DB에 상태 업데이트
    """
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """작업 실패 시 호출"""
        document_id = args[0] if args else kwargs.get('document_id')
        if document_id:
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.error(f"❌ [TASK-FAIL] 문서 처리 실패: doc_id={document_id}, error={error_msg}")
            self.update_status(document_id, 'failed', error_msg)
    
    def on_success(self, retval, task_id, args, kwargs):
        """작업 성공 시 호출"""
        document_id = args[0] if args else kwargs.get('document_id')
        logger.info(f"✅ [TASK-SUCCESS] 문서 처리 성공: doc_id={document_id}, task_id={task_id}")
    
    def update_status(self, document_id: int, status: str, error: Optional[str] = None):
        """
        문서 처리 상태 업데이트 (동기 래퍼)
        
        Args:
            document_id: 문서 ID
            status: 처리 상태 (pending/processing/completed/failed)
            error: 오류 메시지 (실패 시)
        """
        try:
            asyncio.run(self._update_status_async(document_id, status, error))
        except Exception as e:
            logger.error(f"❌ [STATUS-UPDATE] 상태 업데이트 실패: doc_id={document_id}, error={e}")
    
    async def _update_status_async(self, document_id: int, status: str, error: Optional[str] = None):
        """문서 처리 상태 업데이트 (비동기)"""
        from app.core.database import get_async_session_local
        from app.models import TbFileBssInfo
        from sqlalchemy import update
        
        async_session_factory = get_async_session_local()
        async with async_session_factory() as session:
            try:
                update_data: Dict[str, Any] = {'processing_status': status}
                
                if error:
                    update_data['processing_error'] = error[:1000]  # 오류 메시지 길이 제한
                
                if status == 'processing':
                    update_data['processing_started_at'] = datetime.now()
                elif status in ('completed', 'failed'):
                    update_data['processing_completed_at'] = datetime.now()
                
                stmt = (
                    update(TbFileBssInfo)
                    .where(TbFileBssInfo.file_bss_info_sno == document_id)
                    .values(**update_data)
                )
                await session.execute(stmt)
                await session.commit()
                
                logger.info(f"✅ [STATUS-UPDATE] 상태 업데이트 완료: doc_id={document_id}, status={status}")
            except Exception as e:
                logger.error(f"❌ [STATUS-UPDATE] DB 업데이트 실패: {e}")
                await session.rollback()


@celery_app.task(bind=True, base=CallbackTask, name='process_document_async')
def process_document_async(
    self,
    document_id: int,
    file_path: str,
    container_id: str,
    user_emp_no: str,
    provider: Optional[str] = None,
    model_profile: str = "default"
):
    """
    문서 비동기 처리 태스크 (멀티모달 파이프라인)
    
    처리 단계:
    1. 상태를 'processing'으로 변경
    2. Azure DI로 문서 분석 (텍스트, 표, 이미지 추출)
    3. 고급 청킹 (문단/토큰 기반)
    4. 임베딩 생성 (Azure OpenAI)
    5. 검색 인덱스 업데이트
    6. 상태를 'completed'로 변경
    
    Args:
        document_id: 문서 ID (TbFileBssInfo.file_bss_info_sno)
        file_path: 파일 경로
        container_id: 컨테이너 ID
        user_emp_no: 사용자 사번
        provider: AI 제공자 ("azure" 또는 "bedrock")
        model_profile: 모델 프로필 ("default")
    
    Returns:
        Dict: 처리 결과
            - success: 성공 여부
            - document_id: 문서 ID
            - chunks_count: 생성된 청크 수
            - embeddings_count: 생성된 임베딩 수
            - processing_time: 총 처리 시간 (초)
    """
    start_time = datetime.now()
    logger.info(f"🔄 [ASYNC-TASK] 문서 처리 시작: doc_id={document_id}, container={container_id}")
    
    # 상태를 processing으로 변경
    self.update_status(document_id, 'processing')
    
    try:
        # 비동기 함수 실행 (nest_asyncio가 이미 적용되어 Event Loop 중첩 가능)
        effective_provider = provider or settings.get_current_llm_provider()

        result = asyncio.run(
            _process_document_multimodal(
                document_id=document_id,
                file_path=file_path,
                container_id=container_id,
                user_emp_no=user_emp_no,
                provider=effective_provider,
                model_profile=model_profile
            )
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if result.get('success'):
            # 상태를 completed로 변경
            self.update_status(document_id, 'completed')
            
            logger.info(
                f"✅ [ASYNC-TASK] 문서 처리 완료: doc_id={document_id}, "
                f"chunks={result.get('chunks_count', 0)}, "
                f"embeddings={result.get('embeddings_count', 0)}, "
                f"time={processing_time:.2f}초"
            )
            
            return {
                'success': True,
                'document_id': document_id,
                'chunks_count': result.get('chunks_count', 0),
                'embeddings_count': result.get('embeddings_count', 0),
                'objects_count': result.get('objects_count', 0),
                'processing_time': processing_time,
                'stages': result.get('stages', [])
            }
        else:
            # 처리 실패
            error_msg = result.get('error', '알 수 없는 오류')
            self.update_status(document_id, 'failed', error_msg)
            
            logger.error(f"❌ [ASYNC-TASK] 문서 처리 실패: doc_id={document_id}, error={error_msg}")
            
            return {
                'success': False,
                'document_id': document_id,
                'error': error_msg,
                'processing_time': processing_time
            }
            
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        error_trace = traceback.format_exc()
        
        logger.error(f"💥 [ASYNC-TASK] 문서 처리 예외: doc_id={document_id}")
        logger.error(f"💥 [ASYNC-TASK] 에러: {error_msg}")
        logger.error(f"💥 [ASYNC-TASK] 스택트레이스:\n{error_trace}")
        
        # 상태를 failed로 변경
        self.update_status(document_id, 'failed', error_msg)
        
        # Celery에 예외 전파
        raise


async def _process_document_multimodal(
    document_id: int,
    file_path: str,
    container_id: str,
    user_emp_no: str,
    provider: Optional[str] = None,
    model_profile: str = "default"
) -> dict:
    """
    멀티모달 파이프라인 실행 (비동기) - 문서 유형별 라우팅 적용
    
    Args:
        document_id: 문서 ID
        file_path: 파일 경로
        container_id: 컨테이너 ID
        user_emp_no: 사용자 사번
        provider: AI 제공자
        model_profile: 모델 프로필
    
    Returns:
        Dict: 처리 결과
    """
    from app.core.database import get_async_session_local
    from app.models import TbFileBssInfo
    from app.services.document.pipeline_router import PipelineRouter
    from sqlalchemy import select
    
    provider = provider or settings.get_current_llm_provider()

    async_session_factory = get_async_session_local()
    async with async_session_factory() as session:
        try:
            logger.info(f"📊 [PIPELINE] 멀티모달 파이프라인 시작: doc_id={document_id}, provider={provider}")
            
            # 🆕 DB에서 문서 정보 조회 (document_type, processing_options 포함)
            stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == document_id)
            result = await session.execute(stmt)
            file_info = result.scalar_one_or_none()
            
            if not file_info:
                logger.error(f"❌ [PIPELINE] 문서를 찾을 수 없음: doc_id={document_id}")
                return {
                    'success': False,
                    'error': f'문서를 찾을 수 없습니다: {document_id}'
                }
            
            # 문서 유형 및 처리 옵션 가져오기
            document_type = cast(str, file_info.document_type or 'general')
            processing_options = cast(Dict[str, Any], file_info.processing_options or {})
            file_name = cast(str, file_info.file_lgc_nm or "unknown_file")
            
            logger.info(f"🔀 [PIPELINE] 문서 유형: {document_type}, 옵션: {processing_options}")
            
            # 🆕 파이프라인 라우터를 통한 처리
            pipeline_result = await PipelineRouter.process_document(
                document_type=document_type,
                document_id=document_id,
                file_path=file_path,
                file_name=file_name,
                container_id=container_id,
                processing_options=processing_options,
                user_emp_no=user_emp_no
            )
            
            if pipeline_result.get('success'):
                stats = pipeline_result.get('statistics', {})
                chunks_count = stats.get('total_chunks', 0)
                
                logger.info(f"📊 [PIPELINE] 파이프라인 완료: doc_id={document_id}, pipeline={pipeline_result.get('pipeline_type')}")
                logger.info(f"   📊 통계: {stats}")
                
                # 🆕 TbFileBssInfo의 chunk_count 업데이트
                from sqlalchemy import update
                try:
                    update_stmt = (
                        update(TbFileBssInfo)
                        .where(TbFileBssInfo.file_bss_info_sno == document_id)
                        .values(chunk_count=chunks_count)
                    )
                    await session.execute(update_stmt)
                    await session.commit()
                    logger.info(f"✅ [CHUNK-COUNT] chunk_count 업데이트 완료: doc_id={document_id}, count={chunks_count}")
                except Exception as e:
                    logger.error(f"❌ [CHUNK-COUNT] chunk_count 업데이트 실패: {e}")
                    await session.rollback()
                
                # 기존 multimodal_document_service와 호환되는 형식으로 변환
                return {
                    'success': True,
                    'chunks_count': chunks_count,
                    'embeddings_count': stats.get('total_embeddings', 0),
                    'objects_count': stats.get('total_objects_extracted', 0),
                    'pipeline_type': pipeline_result.get('pipeline_type'),
                    'document_type': document_type,
                    'stages': ['extract', 'chunk', 'embed', 'index']
                }
            else:
                logger.error(f"❌ [PIPELINE] 파이프라인 실패: {pipeline_result.get('error')}")
                return {
                    'success': False,
                    'error': pipeline_result.get('error', '알 수 없는 오류')
                }
            
        except Exception as e:
            logger.error(f"❌ [PIPELINE] 파이프라인 예외: doc_id={document_id}, error={e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

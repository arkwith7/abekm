"""
Celery 기반 비동기 문서 처리 시스템 구현 예시
"""

from celery import Celery
from celery.result import AsyncResult
from typing import List, Dict, Any
import logging
import os
import time
from pathlib import Path

# Celery 설정
def create_celery_app() -> Celery:
    """Celery 애플리케이션 생성"""
    celery_app = Celery(
        'wkms_document_processor',
        broker='redis://localhost:6379/0',  # Redis 브로커
        backend='redis://localhost:6379/0',  # 결과 저장소
        include=[
            'app.tasks.document_tasks',
            'app.tasks.korean_nlp_tasks',
            'app.tasks.embedding_tasks'
        ]
    )
    
    # Celery 설정
    celery_app.conf.update(
        # 작업 라우팅
        task_routes={
            'app.tasks.document_tasks.*': {'queue': 'document_processing'},
            'app.tasks.korean_nlp_tasks.*': {'queue': 'korean_nlp'},
            'app.tasks.embedding_tasks.*': {'queue': 'embedding'},
        },
        
        # 동시 실행 제한
        worker_concurrency=4,  # 워커당 동시 작업 수
        
        # 타임아웃 설정
        task_soft_time_limit=300,  # 5분 소프트 제한
        task_time_limit=600,      # 10분 하드 제한
        
        # 결과 만료
        result_expires=3600,      # 1시간 후 결과 삭제
        
        # 작업 직렬화
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        
        # 오류 재시도
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        
        # 모니터링
        task_send_sent_event=True,
        worker_send_task_events=True,
    )
    
    return celery_app

# Celery 앱 인스턴스
celery_app = create_celery_app()

# 문서 처리 작업들
@celery_app.task(bind=True, name='process_single_document')
def process_single_document_task(self, file_path: str, file_info: Dict[str, Any], batch_id: str = None):
    """단일 문서 처리 Celery 작업"""
    try:
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '파일 처리 시작...'}
        )
        
        # 문서 처리 서비스 호출
        from app.services.document_processor_service import document_processor_service
        from app.services.korean_nlp_service import korean_nlp_service
        
        # 1. 텍스트 추출 (30%)
        self.update_state(
            state='PROGRESS', 
            meta={'current': 10, 'total': 100, 'status': '텍스트 추출 중...'}
        )
        
        with open(file_path, 'rb') as f:
            result = document_processor_service.process_document(
                file_content=f.read(),
                file_name=file_info['filename'],
                content_type=file_info['content_type']
            )
        
        # 2. 한국어 NLP 분석 (50%)
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': '한국어 분석 중...'}
        )
        
        if result.get('content'):
            korean_analysis = korean_nlp_service.hybrid_process_korean_text(result['content'])
            result['korean_analysis'] = korean_analysis
        
        # 3. 벡터 임베딩 생성 (70%)
        self.update_state(
            state='PROGRESS',
            meta={'current': 50, 'total': 100, 'status': '벡터 임베딩 생성 중...'}
        )
        
        if result.get('content'):
            embedding = korean_nlp_service.generate_korean_embedding(result['content'])
            result['embedding'] = embedding
        
        # 4. 데이터베이스 저장 (90%)
        self.update_state(
            state='PROGRESS',
            meta={'current': 70, 'total': 100, 'status': '데이터베이스 저장 중...'}
        )
        
        # DB 저장 로직 (구현 필요)
        # await save_to_database(result)
        
        # 5. 완료 (100%)
        self.update_state(
            state='PROGRESS',
            meta={'current': 100, 'total': 100, 'status': '처리 완료'}
        )
        
        return {
            'success': True,
            'file_info': file_info,
            'result': result,
            'processing_time': time.time() - self.request.kwargs.get('eta', time.time())
        }
        
    except Exception as e:
        logging.error(f"Document processing failed: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'file': file_info.get('filename', 'unknown')}
        )
        raise

@celery_app.task(bind=True, name='process_batch_documents')
def process_batch_documents_task(self, file_paths: List[str], file_infos: List[Dict[str, Any]]):
    """배치 문서 처리 Celery 작업"""
    batch_id = self.request.id
    
    try:
        # 배치 처리 시작
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0, 
                'total': len(file_paths), 
                'status': f'{len(file_paths)}개 파일 배치 처리 시작...',
                'batch_id': batch_id
            }
        )
        
        # 각 파일에 대해 개별 작업 생성
        individual_tasks = []
        for i, (file_path, file_info) in enumerate(zip(file_paths, file_infos)):
            task = process_single_document_task.delay(file_path, file_info, batch_id)
            individual_tasks.append({
                'task_id': task.id,
                'filename': file_info['filename']
            })
        
        # 진행 상황 모니터링
        completed = 0
        results = []
        
        while completed < len(individual_tasks):
            time.sleep(2)  # 2초마다 확인
            
            current_completed = 0
            for task_info in individual_tasks:
                task_result = AsyncResult(task_info['task_id'], app=celery_app)
                
                if task_result.ready():
                    current_completed += 1
                    if task_result.successful():
                        results.append(task_result.result)
                    else:
                        results.append({
                            'success': False,
                            'file_info': {'filename': task_info['filename']},
                            'error': str(task_result.result)
                        })
            
            # 진행률 업데이트
            if current_completed > completed:
                completed = current_completed
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': completed,
                        'total': len(file_paths),
                        'status': f'{completed}/{len(file_paths)} 파일 처리 완료',
                        'batch_id': batch_id,
                        'individual_tasks': individual_tasks
                    }
                )
        
        # 최종 결과 반환
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        return {
            'success': len(failed) == 0,
            'batch_id': batch_id,
            'total_files': len(file_paths),
            'successful_files': len(successful),
            'failed_files': len(failed),
            'results': results
        }
        
    except Exception as e:
        logging.error(f"Batch processing failed: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'batch_id': batch_id}
        )
        raise

# 상태 조회 유틸리티
def get_task_status(task_id: str) -> Dict[str, Any]:
    """작업 상태 조회"""
    result = AsyncResult(task_id, app=celery_app)
    
    if result.state == 'PENDING':
        return {
            'state': result.state,
            'status': '대기 중...',
            'current': 0,
            'total': 1
        }
    elif result.state == 'PROGRESS':
        return {
            'state': result.state,
            'status': result.info.get('status', ''),
            'current': result.info.get('current', 0),
            'total': result.info.get('total', 1)
        }
    elif result.state == 'SUCCESS':
        return {
            'state': result.state,
            'status': '처리 완료',
            'current': 1,
            'total': 1,
            'result': result.result
        }
    else:  # FAILURE
        return {
            'state': result.state,
            'status': '처리 실패',
            'error': str(result.info)
        }

# FastAPI와의 통합 예시
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List

router = APIRouter()

@router.post("/async-batch-upload")
async def async_batch_upload_documents(files: List[UploadFile] = File(...)):
    """
    Celery 기반 비동기 배치 업로드
    """
    try:
        # 파일 임시 저장
        file_paths = []
        file_infos = []
        
        for file in files:
            # 임시 파일 저장
            temp_path = f"/tmp/{file.filename}"
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            file_paths.append(temp_path)
            file_infos.append({
                'filename': file.filename,
                'size': len(content),
                'content_type': file.content_type
            })
        
        # Celery 작업 시작
        task = process_batch_documents_task.delay(file_paths, file_infos)
        
        return {
            'success': True,
            'task_id': task.id,
            'message': f'{len(files)}개 파일의 비동기 처리가 시작되었습니다.',
            'status_url': f'/api/documents/task-status/{task.id}'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task-status/{task_id}")
async def get_task_status_endpoint(task_id: str):
    """작업 상태 조회 엔드포인트"""
    try:
        status = get_task_status(task_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Celery worker 실행 명령어:
    # celery -A app.tasks.celery_app worker --loglevel=info --queues=document_processing,korean_nlp,embedding
    
    # Flower 모니터링 도구 실행:
    # celery -A app.tasks.celery_app flower
    
    print("Celery 기반 문서 처리 시스템 준비 완료")
    print("워커 시작: celery -A app.tasks.celery_app worker --loglevel=info")
    print("모니터링: celery -A app.tasks.celery_app flower")

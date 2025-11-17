"""
현재 시스템 개선안 - Celery 없이 성능 최적화
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List, Dict, Any
import asyncio
import aiofiles
import tempfile
import os
from pathlib import Path
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import psutil

logger = logging.getLogger(__name__)

class OptimizedBatchProcessor:
    """최적화된 배치 처리기"""
    
    def __init__(self):
        # 시스템 리소스에 따른 동적 조정
        cpu_count = psutil.cpu_count()
        available_memory = psutil.virtual_memory().available / (1024**3)  # GB
        
        # 동적 동시 처리 수 계산
        self.max_concurrent = min(
            cpu_count * 2,  # CPU 코어 수의 2배
            max(4, int(available_memory)),  # 메모리 GB당 1개, 최소 4개
            16  # 최대 16개로 제한
        )
        
        # 스레드 풀 (CPU 집약적 작업용)
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_concurrent)
        
        # 메모리 사용량 모니터링
        self.memory_threshold = 0.8  # 80% 이상 사용 시 처리 속도 조절
        
        logger.info(f"배치 처리기 초기화: 최대 동시 처리 {self.max_concurrent}개")
    
    async def process_files_optimized(
        self, 
        files: List[UploadFile], 
        batch_id: str
    ) -> Dict[str, Any]:
        """최적화된 파일 배치 처리"""
        
        # 1. 파일 크기별 그룹화 (작은 파일 먼저 처리)
        file_groups = self._group_files_by_size(files)
        
        # 2. 메모리 사용량 모니터링
        memory_monitor = asyncio.create_task(self._monitor_memory())
        
        # 3. 적응적 세마포어 (메모리 상황에 따라 조절)
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        try:
            all_results = []
            
            # 그룹별 순차 처리 (작은 파일부터)
            for group_name, group_files in file_groups.items():
                logger.info(f"처리 그룹: {group_name} ({len(group_files)}개 파일)")
                
                # 메모리 사용량 확인 후 동시 처리 수 조절
                current_memory = psutil.virtual_memory().percent / 100
                if current_memory > self.memory_threshold:
                    # 메모리 부족 시 동시 처리 수 감소
                    adjusted_concurrent = max(2, self.max_concurrent // 2)
                    semaphore = asyncio.Semaphore(adjusted_concurrent)
                    logger.warning(f"메모리 사용량 높음 ({current_memory:.1%}), 동시 처리 수 감소: {adjusted_concurrent}")
                
                # 그룹 내 파일들 병렬 처리
                async def process_with_adaptive_semaphore(file: UploadFile):
                    async with semaphore:
                        return await self._process_single_file_optimized(file, batch_id)
                
                group_results = await asyncio.gather(
                    *[process_with_adaptive_semaphore(file) for file in group_files],
                    return_exceptions=True
                )
                
                all_results.extend(group_results)
                
                # 그룹 간 짧은 휴식 (메모리 정리 시간)
                await asyncio.sleep(0.1)
            
            return self._compile_results(all_results, batch_id)
            
        finally:
            memory_monitor.cancel()
    
    def _group_files_by_size(self, files: List[UploadFile]) -> Dict[str, List[UploadFile]]:
        """파일 크기별 그룹화"""
        small_files = []    # < 1MB
        medium_files = []   # 1MB - 10MB  
        large_files = []    # > 10MB
        
        for file in files:
            size_mb = (file.size or 0) / (1024 * 1024)
            
            if size_mb < 1:
                small_files.append(file)
            elif size_mb < 10:
                medium_files.append(file)
            else:
                large_files.append(file)
        
        return {
            "small": small_files,
            "medium": medium_files, 
            "large": large_files
        }
    
    async def _monitor_memory(self):
        """메모리 사용량 모니터링"""
        while True:
            try:
                memory_percent = psutil.virtual_memory().percent
                if memory_percent > 90:
                    logger.warning(f"메모리 사용량 위험 수준: {memory_percent:.1f}%")
                    # 가비지 컬렉션 강제 실행
                    import gc
                    gc.collect()
                
                await asyncio.sleep(5)  # 5초마다 확인
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"메모리 모니터링 오류: {e}")
                await asyncio.sleep(10)
    
    async def _process_single_file_optimized(
        self, 
        file: UploadFile, 
        batch_id: str
    ) -> Dict[str, Any]:
        """최적화된 단일 파일 처리"""
        
        # 임시 파일을 비동기로 생성
        async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            
            # 파일 내용을 청크 단위로 비동기 저장
            content = await file.read()
            await temp_file.write(content)
        
        try:
            # CPU 집약적 작업은 스레드 풀에서 실행
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.thread_pool,
                self._process_file_sync,
                temp_path,
                file.filename,
                file.content_type
            )
            
            return result
            
        finally:
            # 임시 파일 정리
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"임시 파일 정리 실패: {e}")
    
    def _process_file_sync(self, file_path: str, filename: str, content_type: str) -> Dict[str, Any]:
        """동기적 파일 처리 (스레드 풀에서 실행)"""
        try:
            from app.services.document_processor_service import document_processor_service
            from app.services.korean_nlp_service import korean_nlp_service
            
            # 파일 처리
            with open(file_path, 'rb') as f:
                result = document_processor_service.process_document(
                    file_content=f.read(),
                    file_name=filename,
                    content_type=content_type
                )
            
            # 한국어 NLP (비동기 메서드는 동기 래퍼로 실행)
            if result.get('content'):
                # 여기서는 동기적으로 실행 (실제로는 비동기 메서드를 동기로 래핑 필요)
                pass
            
            return {
                'success': True,
                'filename': filename,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"파일 처리 실패 {filename}: {e}")
            return {
                'success': False,
                'filename': filename,
                'error': str(e)
            }
    
    def _compile_results(self, results: List[Any], batch_id: str) -> Dict[str, Any]:
        """결과 컴파일"""
        successful = []
        failed = []
        
        for result in results:
            if isinstance(result, Exception):
                failed.append({'error': str(result)})
            elif result.get('success'):
                successful.append(result)
            else:
                failed.append(result)
        
        return {
            'batch_id': batch_id,
            'total_files': len(results),
            'successful_files': len(successful),
            'failed_files': len(failed),
            'success_rate': len(successful) / len(results) * 100 if results else 0,
            'results': successful + failed
        }

# 전역 처리기 인스턴스
optimized_processor = OptimizedBatchProcessor()

# FastAPI 라우터
router = APIRouter()

@router.post("/optimized-batch-upload")
async def optimized_batch_upload(files: List[UploadFile] = File(...)):
    """최적화된 배치 업로드"""
    
    if len(files) > 50:
        raise HTTPException(
            status_code=400, 
            detail="최대 50개 파일까지 동시 처리 가능합니다. 더 많은 파일은 Celery 기반 시스템을 사용하세요."
        )
    
    batch_id = str(uuid.uuid4())
    
    try:
        result = await optimized_processor.process_files_optimized(files, batch_id)
        return result
        
    except Exception as e:
        logger.error(f"최적화된 배치 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system-status")
async def get_system_status():
    """시스템 리소스 상태 조회"""
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    return {
        "cpu_usage": f"{cpu_percent:.1f}%",
        "memory_usage": f"{memory.percent:.1f}%",
        "memory_available": f"{memory.available / (1024**3):.1f}GB",
        "max_concurrent": optimized_processor.max_concurrent,
        "recommended_batch_size": min(30, optimized_processor.max_concurrent * 3)
    }

if __name__ == "__main__":
    print("=== 최적화된 배치 처리 시스템 ===")
    print(f"최대 동시 처리: {optimized_processor.max_concurrent}개")
    print("권장 사용:")
    print("- 30개 이하 파일: 현재 시스템")
    print("- 30-50개 파일: 최적화된 시스템") 
    print("- 50개 이상: Celery 도입 권장")

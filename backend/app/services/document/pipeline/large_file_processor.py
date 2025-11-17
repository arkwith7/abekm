"""
대용량 파일 처리 최적화 시스템
"""

import asyncio
import aiofiles
import tempfile
import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import time
import psutil
from fastapi import UploadFile, HTTPException, BackgroundTasks

logger = logging.getLogger(__name__)

class LargeFileProcessor:
    """대용량 파일 전용 처리기"""
    
    def __init__(self):
        self.large_file_threshold = 20 * 1024 * 1024  # 20MB
        self.chunk_strategies = {
            "small": {"size": 1000, "overlap": 200},    # < 20MB
            "medium": {"size": 2000, "overlap": 300},   # 20-50MB  
            "large": {"size": 3000, "overlap": 400},    # 50-100MB
            "xlarge": {"size": 5000, "overlap": 500}    # > 100MB
        }
        
    def get_processing_strategy(self, file_size: int) -> Dict[str, Any]:
        """파일 크기별 처리 전략 결정"""
        size_mb = file_size / (1024 * 1024)
        
        if size_mb < 20:
            strategy = "small"
        elif size_mb < 50:
            strategy = "medium"
        elif size_mb < 100:
            strategy = "large"
        else:
            strategy = "xlarge"
            
        return {
            "strategy": strategy,
            "chunk_size": self.chunk_strategies[strategy]["size"],
            "chunk_overlap": self.chunk_strategies[strategy]["overlap"],
            "requires_background": size_mb > 20,
            "estimated_time": self._estimate_processing_time(size_mb),
            "memory_limit": min(1024, size_mb * 2)  # MB
        }
    
    def _estimate_processing_time(self, size_mb: float) -> float:
        """처리 시간 추정 (초)"""
        base_time = 5
        size_factor = size_mb / 10
        nlp_factor = size_mb / 20
        return base_time + size_factor + nlp_factor
    
    async def process_large_file_streaming(
        self, 
        file: UploadFile, 
        background_tasks: BackgroundTasks = None
    ) -> Dict[str, Any]:
        """대용량 파일 스트리밍 처리"""
        
        file_size = file.size or 0
        strategy = self.get_processing_strategy(file_size)
        
        logger.info(f"대용량 파일 처리 시작: {file.filename} ({file_size/(1024*1024):.1f}MB)")
        logger.info(f"처리 전략: {strategy['strategy']}, 예상 시간: {strategy['estimated_time']:.1f}초")
        
        # 백그라운드 처리가 필요한 경우
        if strategy["requires_background"] and background_tasks:
            return await self._process_in_background(file, strategy, background_tasks)
        else:
            return await self._process_synchronously(file, strategy)
    
    async def _process_synchronously(self, file: UploadFile, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """동기적 처리 (상대적으로 작은 파일)"""
        
        # 메모리 사용량 모니터링
        initial_memory = psutil.virtual_memory().percent
        
        try:
            # 임시 파일로 저장
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                # 파일을 청크 단위로 읽어서 저장 (메모리 절약)
                chunk_size = 1024 * 1024  # 1MB 청크
                while chunk := await file.read(chunk_size):
                    await temp_file.write(chunk)
            
            # 문서 처리
            result = await self._process_document_optimized(temp_path, file.filename, strategy)
            
            # 메모리 사용량 확인
            final_memory = psutil.virtual_memory().percent
            memory_used = final_memory - initial_memory
            
            result["processing_info"] = {
                "strategy": strategy["strategy"],
                "memory_used_percent": memory_used,
                "file_size_mb": file.size / (1024 * 1024) if file.size else 0
            }
            
            return result
            
        finally:
            # 임시 파일 정리
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"임시 파일 정리 실패: {e}")
    
    async def _process_in_background(
        self, 
        file: UploadFile, 
        strategy: Dict[str, Any], 
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """백그라운드 처리 (대용량 파일)"""
        
        import uuid
        task_id = str(uuid.uuid4())
        
        # 임시 파일 저장
        temp_path = f"/tmp/large_file_{task_id}_{file.filename}"
        
        # 파일 저장
        async with aiofiles.open(temp_path, 'wb') as f:
            chunk_size = 1024 * 1024  # 1MB 청크
            while chunk := await file.read(chunk_size):
                await f.write(chunk)
        
        # 백그라운드 태스크 추가
        background_tasks.add_task(
            self._background_processing_task,
            temp_path,
            file.filename,
            strategy,
            task_id
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "processing",
            "message": "대용량 파일이 백그라운드에서 처리 중입니다.",
            "estimated_time": strategy["estimated_time"],
            "check_url": f"/api/documents/large-file-status/{task_id}"
        }
    
    async def _background_processing_task(
        self, 
        file_path: str, 
        filename: str, 
        strategy: Dict[str, Any], 
        task_id: str
    ):
        """백그라운드 처리 태스크"""
        
        try:
            logger.info(f"백그라운드 처리 시작: {filename} (task_id: {task_id})")
            
            # 처리 상태 저장 (실제로는 Redis나 DB 사용)
            self._update_task_status(task_id, "processing", 10)
            
            # 문서 처리
            result = await self._process_document_optimized(file_path, filename, strategy)
            
            # 처리 완료 상태 저장
            self._update_task_status(task_id, "completed", 100, result)
            
            logger.info(f"백그라운드 처리 완료: {filename}")
            
        except Exception as e:
            logger.error(f"백그라운드 처리 실패: {filename}, 오류: {e}")
            self._update_task_status(task_id, "failed", 0, {"error": str(e)})
            
        finally:
            # 임시 파일 정리
            try:
                os.unlink(file_path)
            except Exception as e:
                logger.warning(f"임시 파일 정리 실패: {e}")
    
    async def _process_document_optimized(
        self, 
        file_path: str, 
        filename: str, 
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """최적화된 문서 처리"""
        
        from app.services.document_processor_service import document_processor_service
        from app.services.korean_nlp_service import korean_nlp_service
        
        start_time = time.time()
        
        try:
            # 1. 기본 문서 처리
            with open(file_path, 'rb') as f:
                content = f.read()
            
            result = document_processor_service.process_document(
                file_content=content,
                file_name=filename,
                content_type="application/octet-stream"
            )
            
            if not result.get("success", False):
                return result
            
            # 2. 대용량 파일용 청킹 (최적화된 전략 사용)
            text_content = result.get("content", "")
            if text_content and len(text_content) > 10000:  # 10K 문자 이상
                chunks = self._create_optimized_chunks(
                    text_content, 
                    strategy["chunk_size"], 
                    strategy["chunk_overlap"]
                )
                result["chunks"] = chunks
                result["chunk_count"] = len(chunks)
            
            # 3. 한국어 NLP 처리 (대용량 최적화)
            if text_content:
                # 텍스트를 작은 단위로 나눠서 처리 (메모리 절약)
                max_nlp_chunk = 5000  # NLP 처리용 최대 청크 크기
                nlp_results = []
                
                for i in range(0, len(text_content), max_nlp_chunk):
                    chunk_text = text_content[i:i+max_nlp_chunk]
                    try:
                        nlp_result = await korean_nlp_service.hybrid_process_korean_text(chunk_text)
                        nlp_results.append(nlp_result)
                    except Exception as e:
                        logger.warning(f"NLP 처리 부분 실패: {e}")
                
                # NLP 결과 통합
                result["korean_analysis"] = self._merge_nlp_results(nlp_results)
            
            # 4. 벡터 임베딩 (선택적)
            if len(text_content) < 50000:  # 50K 문자 미만에서만 임베딩 생성
                try:
                    embedding = await korean_nlp_service.generate_korean_embedding(text_content[:10000])
                    result["embedding"] = embedding
                except Exception as e:
                    logger.warning(f"임베딩 생성 실패: {e}")
                    result["embedding"] = None
            else:
                result["embedding"] = None
                result["embedding_note"] = "텍스트가 너무 길어 임베딩을 생략했습니다."
            
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            result["large_file_optimized"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"대용량 파일 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    def _create_optimized_chunks(self, text: str, chunk_size: int, overlap: int) -> List[Dict[str, Any]]:
        """최적화된 청킹"""
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            
            # 문장 경계에서 자르기 (더 나은 청킹)
            if end < len(text):
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                
                if last_period > chunk_size * 0.8:  # 80% 이상 지점에 마침표가 있으면
                    chunk_text = chunk_text[:last_period + 1]
                    end = start + last_period + 1
                elif last_newline > chunk_size * 0.8:  # 80% 이상 지점에 줄바꿈이 있으면
                    chunk_text = chunk_text[:last_newline]
                    end = start + last_newline
            
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text.strip(),
                "start_pos": start,
                "end_pos": end,
                "length": len(chunk_text)
            })
            
            start = end - overlap
            chunk_id += 1
        
        return chunks
    
    def _merge_nlp_results(self, nlp_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """NLP 결과 통합"""
        merged = {
            "keywords": [],
            "entities": [],
            "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            "language": "ko"
        }
        
        for result in nlp_results:
            if result and isinstance(result, dict):
                # 키워드 통합
                if "keywords" in result:
                    merged["keywords"].extend(result["keywords"])
                
                # 엔터티 통합
                if "entities" in result:
                    merged["entities"].extend(result["entities"])
                
                # 감정 분석 평균
                if "sentiment" in result and isinstance(result["sentiment"], dict):
                    for key in merged["sentiment"]:
                        if key in result["sentiment"]:
                            merged["sentiment"][key] += result["sentiment"][key]
        
        # 중복 제거 및 정규화
        merged["keywords"] = list(set(merged["keywords"]))[:20]  # 상위 20개
        merged["entities"] = list(set(merged["entities"]))[:15]   # 상위 15개
        
        # 감정 분석 정규화
        total_sentiment = sum(merged["sentiment"].values())
        if total_sentiment > 0:
            for key in merged["sentiment"]:
                merged["sentiment"][key] = merged["sentiment"][key] / total_sentiment
        
        return merged
    
    def _update_task_status(self, task_id: str, status: str, progress: int, result: Dict[str, Any] = None):
        """작업 상태 업데이트 (실제로는 Redis/DB 사용)"""
        # 임시로 메모리에 저장 (실제 환경에서는 Redis 사용)
        if not hasattr(self, '_task_status'):
            self._task_status = {}
        
        self._task_status[task_id] = {
            "status": status,
            "progress": progress,
            "updated_at": time.time(),
            "result": result
        }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """작업 상태 조회"""
        if not hasattr(self, '_task_status'):
            return {"error": "Task not found"}
        
        return self._task_status.get(task_id, {"error": "Task not found"})

# 전역 인스턴스
large_file_processor = LargeFileProcessor()

if __name__ == "__main__":
    print("=== 대용량 파일 처리 시스템 ===")
    print("지원 기능:")
    print("- 100MB 파일 지원")
    print("- 스트리밍 처리")
    print("- 백그라운드 처리")
    print("- 메모리 최적화")
    print("- 적응적 청킹")

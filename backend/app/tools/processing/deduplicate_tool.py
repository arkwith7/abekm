"""
Deduplication Tool - 중복 청크 제거 도구
"""
import uuid
from typing import List
from datetime import datetime
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.tools.contracts import SearchToolResult, SearchChunk, ToolMetrics


class DeduplicateTool(BaseTool):
    """
    중복 제거 도구
    
    책임:
    - 동일 파일의 동일/유사 청크 제거
    - 내용 해시 기반 중복 감지
    
    전략:
    - 같은 file_id + chunk_id → 완전 중복
    - 같은 file_id + 내용 유사도 > threshold → 유사 중복
    """
    name: str = "deduplicate"
    description: str = """중복된 청크를 제거합니다. 같은 파일에서 중복 청크가 있거나 
내용이 거의 동일한 청크를 필터링합니다."""
    version: str = "1.0.0"
    
    async def _arun(
        self,
        chunks: List[SearchChunk],
        similarity_threshold: float = 0.95,
        keep_strategy: str = "highest_score",
        **kwargs
    ) -> SearchToolResult:
        """
        중복 제거 실행
        
        Args:
            chunks: 입력 청크 목록
            similarity_threshold: 유사 중복 판단 임계값
            keep_strategy: 유지 전략 (highest_score/first/last)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            if not chunks:
                return SearchToolResult(
                    success=True, data=[], total_found=0, filtered_count=0,
                    search_params={}, metrics=ToolMetrics(latency_ms=0, provider="internal"),
                    errors=[], trace_id=trace_id, tool_name=self.name, tool_version=self.version
                )
            
            logger.info(f"🔧 [Dedupe] 입력: {len(chunks)}개 청크")
            
            # 1) 완전 중복 제거 (같은 chunk_id)
            seen_ids = set()
            unique_chunks = []
            for chunk in chunks:
                key = f"{chunk.file_id}:{chunk.chunk_id}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    unique_chunks.append(chunk)
            
            logger.info(f"   - 완전 중복 제거 후: {len(unique_chunks)}개")
            
            # 2) 유사 중복 제거 (간단한 내용 비교)
            final_chunks = []
            for chunk in unique_chunks:
                is_duplicate = False
                content_lower = chunk.content.lower().strip()
                
                for existing in final_chunks:
                    if chunk.file_id != existing.file_id:
                        continue
                    
                    existing_lower = existing.content.lower().strip()
                    
                    # 단순 포함 관계 체크
                    if len(content_lower) < len(existing_lower):
                        shorter, longer = content_lower, existing_lower
                    else:
                        shorter, longer = existing_lower, content_lower
                    
                    # 짧은 것이 긴 것에 거의 포함되면 중복으로 판단
                    if len(shorter) > 0:
                        overlap = sum(1 for c in shorter if c in longer) / len(shorter)
                        if overlap >= similarity_threshold:
                            is_duplicate = True
                            logger.debug(f"   - 유사 중복 감지: overlap={overlap:.2f}")
                            break
                
                if not is_duplicate:
                    final_chunks.append(chunk)
                elif keep_strategy == "highest_score" and chunk.similarity_score > existing.similarity_score:
                    # 점수가 더 높으면 교체
                    final_chunks.remove(existing)
                    final_chunks.append(chunk)
            
            logger.info(f"   - 유사 중복 제거 후: {len(final_chunks)}개")
            
            # 3) 정렬 (점수 기준)
            final_chunks.sort(key=lambda x: x.similarity_score, reverse=True)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ [Dedupe] 완료: {len(chunks)} → {len(final_chunks)}개, latency={latency_ms:.1f}ms")
            
            return SearchToolResult(
                success=True,
                data=final_chunks,
                total_found=len(chunks),
                filtered_count=len(final_chunks),
                search_params={
                    "input_count": len(chunks),
                    "similarity_threshold": similarity_threshold,
                    "keep_strategy": keep_strategy
                },
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internal"),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [Dedupe] 실패: {e}", exc_info=True)
            return SearchToolResult(
                success=False, data=chunks, total_found=len(chunks), filtered_count=len(chunks),
                search_params={}, metrics=ToolMetrics(latency_ms=latency_ms, provider="internal"),
                errors=[str(e)], trace_id=trace_id, tool_name=self.name, tool_version=self.version
            )
    
    def _run(self, **kwargs) -> SearchToolResult:
        import asyncio
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError:
            chunks = kwargs.get("chunks", [])
            return SearchToolResult(
                success=False, data=chunks, total_found=len(chunks), filtered_count=len(chunks),
                search_params={}, metrics=ToolMetrics(latency_ms=0, provider="internal"),
                errors=["use _arun"], trace_id=str(uuid.uuid4()),
                tool_name=self.name, tool_version=self.version
            )
    
    def validate_input(self, **kwargs) -> bool:
        return "chunks" in kwargs and isinstance(kwargs["chunks"], list)


# 전역 인스턴스
deduplicate_tool = DeduplicateTool()

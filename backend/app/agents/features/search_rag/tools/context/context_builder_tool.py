"""
Context Builder Tool - 컨텍스트 토큰 패킹 및 최적화 도구
"""
import uuid
from typing import List, Optional
from datetime import datetime
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.core.contracts import ContextResult, SearchChunk, ToolMetrics


class ContextBuilderTool(BaseTool):
    """
    컨텍스트 빌더 도구
    
    책임:
    - 청크를 토큰 제한 내에서 패킹
    - 우선순위 기반 청크 선택
    - 포맷팅 (citation 포함)
    
    책임 없음:
    - LLM 호출
    - 답변 생성
    """
    name: str = "context_builder"
    description: str = """검색된 청크들을 LLM 컨텍스트로 구성합니다. 
토큰 제한을 고려하여 우선순위 기반으로 청크를 선택하고 포맷팅합니다."""
    version: str = "1.0.0"
    
    def _estimate_tokens(self, text: str) -> int:
        """
        간단한 토큰 추정 (실제 토크나이저 대신)
        한글: 1.5글자당 1토큰, 영어: 4글자당 1토큰
        """
        korean_chars = len([c for c in text if '\uac00' <= c <= '\ud7a3'])
        other_chars = len(text) - korean_chars
        
        tokens = int(korean_chars / 1.5) + int(other_chars / 4)
        return max(tokens, len(text) // 4)  # 최소 보장
    
    async def _arun(
        self,
        chunks: List[SearchChunk],
        max_tokens: int = 4000,
        include_metadata: bool = True,
        format_style: str = "citation",
        priority_by: str = "similarity",
        **kwargs
    ) -> ContextResult:
        """
        컨텍스트 빌드 실행
        
        Args:
            chunks: 입력 청크 목록
            max_tokens: 최대 토큰 수
            include_metadata: 메타데이터 포함 여부
            format_style: 포맷 스타일 (citation/plain/numbered)
            priority_by: 우선순위 기준 (similarity/position/hybrid)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        try:
            if not chunks:
                return ContextResult(
                    success=True,
                    data="",
                    used_chunks=[],
                    total_tokens=0,
                    chunks_included=0,
                    chunks_truncated=0,
                    metrics=ToolMetrics(latency_ms=0, provider="internal"),
                    errors=[],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            logger.info(f"🔧 [ContextBuilder] 입력: {len(chunks)}개, max_tokens={max_tokens}")
            
            # 1) 우선순위 정렬
            if priority_by == "similarity":
                sorted_chunks = sorted(chunks, key=lambda x: x.similarity_score, reverse=True)
            elif priority_by == "position":
                sorted_chunks = sorted(chunks, key=lambda x: x.metadata.get("chunk_index", 999))
            else:  # hybrid
                sorted_chunks = sorted(
                    chunks,
                    key=lambda x: (x.similarity_score * 0.7 + (1.0 - x.metadata.get("chunk_index", 0) / 1000) * 0.3),
                    reverse=True
                )
            
            # 2) 토큰 제한 내에서 패킹
            context_parts = []
            used_chunks = []
            total_tokens = 0
            truncated_count = 0
            
            # 헤더 토큰 예약 (약 100 토큰)
            reserved_tokens = 100
            available_tokens = max_tokens - reserved_tokens
            
            for i, chunk in enumerate(sorted_chunks):
                # 포맷팅
                if format_style == "citation":
                    chunk_text = f"[{i+1}] {chunk.content}"
                    if include_metadata:
                        source = chunk.metadata.get("file_name", "Unknown")
                        chunk_text += f"\n(출처: {source})"
                elif format_style == "numbered":
                    chunk_text = f"{i+1}. {chunk.content}"
                else:  # plain
                    chunk_text = chunk.content
                
                chunk_tokens = self._estimate_tokens(chunk_text)
                
                if total_tokens + chunk_tokens <= available_tokens:
                    context_parts.append(chunk_text)
                    used_chunks.append(chunk)
                    total_tokens += chunk_tokens
                else:
                    truncated_count += 1
                    logger.debug(f"   - 토큰 제한으로 청크 {i+1} 생략")
            
            # 3) 최종 컨텍스트 구성
            if format_style == "citation":
                context_text = "## 참고 문서\n\n" + "\n\n".join(context_parts)
            else:
                context_text = "\n\n".join(context_parts)
            
            # 4) 최종 토큰 계산
            final_tokens = self._estimate_tokens(context_text)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"✅ [ContextBuilder] 완료: {len(used_chunks)}/{len(chunks)}개 포함, "
                f"{final_tokens}토큰, latency={latency_ms:.1f}ms"
            )
            
            return ContextResult(
                success=True,
                data=context_text,
                used_chunks=used_chunks,
                total_tokens=final_tokens,
                chunks_included=len(used_chunks),
                chunks_truncated=truncated_count,
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    tokens_used=final_tokens
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ [ContextBuilder] 실패: {e}", exc_info=True)
            return ContextResult(
                success=False,
                data="",
                used_chunks=[],
                total_tokens=0,
                chunks_included=0,
                chunks_truncated=0,
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internal"),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    def _run(self, **kwargs) -> ContextResult:
        import asyncio
        try:
            return asyncio.run(self._arun(**kwargs))
        except RuntimeError:
            return ContextResult(
                success=False, data="", used_chunks=[], total_tokens=0,
                chunks_included=0, chunks_truncated=0,
                metrics=ToolMetrics(latency_ms=0, provider="internal"),
                errors=["use _arun"], trace_id=str(uuid.uuid4()),
                tool_name=self.name, tool_version=self.version
            )
    
    def validate_input(self, **kwargs) -> bool:
        return "chunks" in kwargs and isinstance(kwargs["chunks"], list)


# 전역 인스턴스
context_builder_tool = ContextBuilderTool()

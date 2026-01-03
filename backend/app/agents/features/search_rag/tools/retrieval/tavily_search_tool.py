"""
Tavily Search Tool - AI 에이전트 최적화 웹 검색 도구
Tavily API를 사용하여 AI 친화적인 검색 결과 제공
"""
import asyncio
import uuid
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

# Tavily 클라이언트
try:
    from tavily import TavilyClient, AsyncTavilyClient
    HAS_TAVILY = True
except ImportError:
    HAS_TAVILY = False
    TavilyClient = None
    AsyncTavilyClient = None

from app.core.contracts import (
    SearchToolResult, SearchChunk, ToolMetrics
)
from app.core.config import settings


class TavilySearchTool(BaseTool):
    """
    Tavily 검색 도구
    
    특징:
    - AI 에이전트에 최적화된 검색 결과
    - 고품질 콘텐츠 추출
    - LangChain 공식 지원
    - 무료 1,000건/월
    
    책임:
    - Tavily API를 통한 웹 검색
    - 검색 결과를 SearchChunk 형태로 변환
    """
    name: str = "tavily_search"
    description: str = "Tavily를 사용한 AI 최적화 웹 검색. 최신 정보와 고품질 콘텐츠를 제공합니다."
    version: str = "1.0.0"
    
    # Pydantic v2 호환
    _client: Optional[Any] = None
    _async_client: Optional[Any] = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialize_client()
    
    def _initialize_client(self):
        """Tavily 클라이언트 초기화"""
        api_key = settings.tavily_api_key
        if api_key and HAS_TAVILY:
            try:
                self._client = TavilyClient(api_key=api_key)
                self._async_client = AsyncTavilyClient(api_key=api_key)
                logger.info("✅ [TavilySearch] 클라이언트 초기화 완료")
            except Exception as e:
                logger.error(f"❌ [TavilySearch] 클라이언트 초기화 실패: {e}")
                self._client = None
                self._async_client = None

    def _format_query_for_log(self, query: str) -> str:
        """Avoid logging raw queries unless explicitly allowed."""
        q = (query or "").strip()
        if settings.web_search_log_queries:
            return q[:200]
        digest = hashlib.sha256(q.encode("utf-8")).hexdigest()[:12] if q else "empty"
        return f"len={len(q)} sha256={digest}"
        
    async def _arun(
        self,
        query: str,
        top_k: int = 5,
        search_depth: str = "basic",  # basic | advanced
        include_answer: bool = True,
        include_raw_content: bool = False,
        **kwargs
    ) -> SearchToolResult:
        """
        Tavily 검색 실행 (비동기)
        
        Args:
            query: 검색 질의
            top_k: 반환할 최대 결과 수
            search_depth: 검색 깊이 (basic: 빠름, advanced: 상세)
            include_answer: AI 생성 답변 포함 여부
            include_raw_content: 원본 콘텐츠 포함 여부
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        # API 키 확인
        if not settings.tavily_api_key:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="tavily", trace_id=trace_id),
                errors=["TAVILY_API_KEY가 설정되지 않았습니다. .env 파일에 TAVILY_API_KEY를 추가하세요."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
        
        if not HAS_TAVILY:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="tavily", trace_id=trace_id),
                errors=["tavily-python 패키지가 설치되지 않았습니다. pip install tavily-python"],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        try:
            # 클라이언트가 없으면 재초기화
            if not self._async_client:
                self._initialize_client()
            
            if not self._async_client:
                raise Exception("Tavily 클라이언트 초기화 실패")

            logger.info(
                f"🔍 [TavilySearch] 검색 시작: query=({self._format_query_for_log(query)}) (depth={search_depth}, top_k={top_k})"
            )
            
            # Tavily 검색 실행
            response = await self._async_client.search(
                query=query,
                search_depth=search_depth,
                max_results=top_k,
                include_answer=include_answer,
                include_raw_content=include_raw_content
            )
            
            chunks = []
            results = response.get('results', [])
            
            for idx, res in enumerate(results):
                title = res.get('title', '')
                content = res.get('content', '')
                url = res.get('url', '')
                score = res.get('score', 0.9 - (idx * 0.05))
                
                # AI 생성 답변이 있으면 첫 번째 청크에 추가
                if idx == 0 and include_answer and response.get('answer'):
                    content = f"[AI 요약] {response['answer']}\n\n[원문] {content}"
                
                full_content = f"제목: {title}\n내용: {content}\n출처: {url}"
                
                chunk = SearchChunk(
                    chunk_id=f"tavily_{trace_id}_{idx}",
                    content=full_content,
                    score=float(score) if score else 0.9 - (idx * 0.05),
                    file_id=None,
                    match_type="internet",
                    container_id="tavily",
                    metadata={
                        "source": "tavily",
                        "url": url,
                        "title": title,
                        "snippet": content[:500] if content else "",
                        "raw_content": res.get('raw_content', '')[:1000] if include_raw_content else None
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ [TavilySearch] 검색 완료: {len(chunks)}개 결과, {latency_ms:.0f}ms")
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=0,
                search_params={
                    "query": query,
                    "top_k": top_k,
                    "search_depth": search_depth
                },
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="tavily",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            logger.error(f"❌ [TavilySearch] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="tavily", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

    def _run(
        self,
        query: str,
        top_k: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        **kwargs
    ) -> SearchToolResult:
        """
        Tavily 검색 실행 (동기)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        if not settings.tavily_api_key:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="tavily", trace_id=trace_id),
                errors=["TAVILY_API_KEY가 설정되지 않았습니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
        
        if not HAS_TAVILY:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="tavily", trace_id=trace_id),
                errors=["tavily-python 패키지가 설치되지 않았습니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        try:
            if not self._client:
                self._initialize_client()
            
            if not self._client:
                raise Exception("Tavily 클라이언트 초기화 실패")
            
            logger.info(f"🔍 [TavilySearch] 검색 시작: query=({self._format_query_for_log(query)})")
            
            response = self._client.search(
                query=query,
                search_depth=search_depth,
                max_results=top_k,
                include_answer=include_answer
            )
            
            chunks = []
            results = response.get('results', [])
            
            for idx, res in enumerate(results):
                title = res.get('title', '')
                content = res.get('content', '')
                url = res.get('url', '')
                score = res.get('score', 0.9 - (idx * 0.05))
                
                if idx == 0 and include_answer and response.get('answer'):
                    content = f"[AI 요약] {response['answer']}\n\n[원문] {content}"
                
                full_content = f"제목: {title}\n내용: {content}\n출처: {url}"
                
                chunk = SearchChunk(
                    chunk_id=f"tavily_{trace_id}_{idx}",
                    content=full_content,
                    score=float(score) if score else 0.9 - (idx * 0.05),
                    file_id=None,
                    match_type="internet",
                    container_id="tavily",
                    metadata={
                        "source": "tavily",
                        "url": url,
                        "title": title,
                        "snippet": content[:500] if content else ""
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ [TavilySearch] 검색 완료: {len(chunks)}개 결과")
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=0,
                search_params={"query": query, "top_k": top_k},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="tavily",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            logger.error(f"❌ [TavilySearch] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="tavily", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )


# 전역 인스턴스
tavily_search_tool = TavilySearchTool()

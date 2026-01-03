"""
Internet Search Tool - 통합 인터넷 검색 도구
Tavily, Bing, DuckDuckGo 등 다양한 검색 엔진을 지원하는 통합 도구
"""
import asyncio
import uuid
import time
import random
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.core.contracts import (
    SearchToolResult, SearchChunk, ToolMetrics
)
from app.core.config import settings

# 개별 검색 도구 import (지연 로딩)
_tavily_tool = None
_bing_tool = None
_HAS_TAVILY = None

def _get_tavily_tool():
    global _tavily_tool, _HAS_TAVILY
    if _tavily_tool is None:
        try:
            from app.agents.features.search_rag.tools.retrieval.tavily_search_tool import tavily_search_tool, HAS_TAVILY
            _tavily_tool = tavily_search_tool
            _HAS_TAVILY = HAS_TAVILY
        except ImportError:
            _HAS_TAVILY = False
    return _tavily_tool, _HAS_TAVILY

def _get_bing_tool():
    global _bing_tool
    if _bing_tool is None:
        try:
            from app.agents.features.search_rag.tools.retrieval.bing_search_tool import bing_search_tool
            _bing_tool = bing_search_tool
        except ImportError:
            pass
    return _bing_tool

# DuckDuckGo 폴백
try:
    from duckduckgo_search import DDGS
    from duckduckgo_search.exceptions import RatelimitException, DuckDuckGoSearchException
    HAS_DDG = True
except ImportError:
    HAS_DDG = False
    RatelimitException = Exception
    DuckDuckGoSearchException = Exception


class InternetSearchTool(BaseTool):
    """
    통합 인터넷 검색 도구
    
    우선순위:
    1. Tavily (API 키 설정 시) - AI 에이전트 최적화
    2. Bing Search (API 키 설정 시) - 엔터프라이즈 안정성
    3. DuckDuckGo (폴백) - 무료, Rate Limit 주의
    
    책임:
    - 설정에 따른 적절한 검색 엔진 선택
    - 검색 결과를 SearchChunk 형태로 통합 반환
    """
    name: str = "internet_search"
    description: str = "인터넷 검색을 수행하여 최신 정보나 외부 지식을 찾습니다."
    version: str = "2.0.0"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_available_providers()
    
    def _log_available_providers(self):
        """사용 가능한 검색 제공자 로깅"""
        providers = []
        _, has_tavily = _get_tavily_tool()
        
        if settings.tavily_api_key and has_tavily:
            providers.append("Tavily ✅")
        if settings.bing_search_api_key:
            providers.append("Bing ✅")
        if HAS_DDG:
            providers.append("DuckDuckGo (폴백)")
        
        if providers:
            logger.info(f"🔍 [InternetSearch] 사용 가능한 제공자: {', '.join(providers)}")
        else:
            logger.warning("⚠️ [InternetSearch] 사용 가능한 검색 제공자가 없습니다")
    
    def _get_preferred_provider(self) -> str:
        """설정에 따른 선호 제공자 반환"""
        provider = settings.web_search_provider.lower()
        _, has_tavily = _get_tavily_tool()

        # "mock" is used as a safe default in config examples.
        # Treat it as disabled to avoid accidental external calls.
        if provider in {"mock", "none", "disabled", "off", "false"}:
            return "none"
        
        # 명시적 설정이 있으면 해당 제공자 사용
        if provider == "tavily" and settings.tavily_api_key and has_tavily:
            return "tavily"
        elif provider == "bing" and settings.bing_search_api_key:
            return "bing"
        elif provider == "duckduckgo" and HAS_DDG:
            return "duckduckgo"
        
        # 자동 선택 (우선순위: tavily > bing > duckduckgo)
        if settings.tavily_api_key and has_tavily:
            return "tavily"
        elif settings.bing_search_api_key:
            return "bing"
        elif HAS_DDG:
            return "duckduckgo"
        
        return "none"

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
        top_k: int = 0,
        provider: Optional[str] = None,  # 명시적 제공자 선택
        **kwargs
    ) -> SearchToolResult:
        """
        인터넷 검색 실행 (비동기)
        
        Args:
            query: 검색 질의
            top_k: 반환할 최대 결과 수
            provider: 사용할 검색 제공자 (tavily, bing, duckduckgo)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())

        # Feature-flag guard: do not call external providers when disabled.
        if not settings.web_search_enabled:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": "" if not settings.web_search_log_queries else query},
                metrics=ToolMetrics(latency_ms=0, provider="disabled", trace_id=trace_id),
                errors=["WEB_SEARCH가 비활성화되어 있습니다 (web_search_enabled=false)."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version,
            )

        # Align default result size with config.
        if not isinstance(top_k, int) or top_k <= 0:
            top_k = int(settings.web_search_max_results or 6)
        
        # 제공자 결정
        selected_provider = provider or self._get_preferred_provider()

        logger.info(
            f"🔍 [InternetSearch] 제공자: {selected_provider}, query=({self._format_query_for_log(query)})"
        )
        
        # 제공자별 검색 실행
        if selected_provider == "tavily":
            result = await self._search_with_tavily(query, top_k, trace_id, **kwargs)
        elif selected_provider == "bing":
            result = await self._search_with_bing(query, top_k, trace_id, **kwargs)
        elif selected_provider == "duckduckgo":
            result = await self._search_with_duckduckgo(query, top_k, trace_id)
        else:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="none", trace_id=trace_id),
                errors=["사용 가능한 검색 제공자가 없습니다. TAVILY_API_KEY 또는 BING_SEARCH_API_KEY를 설정하세요."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
        
        # 실패 시 폴백 시도
        if not result.success and selected_provider != "duckduckgo" and HAS_DDG:
            logger.warning(f"⚠️ [InternetSearch] {selected_provider} 실패, DuckDuckGo로 폴백")
            result = await self._search_with_duckduckgo(query, top_k, trace_id)
        
        return result

    async def _search_with_tavily(
        self, query: str, top_k: int, trace_id: str, **kwargs
    ) -> SearchToolResult:
        """Tavily로 검색"""
        try:
            tavily_tool, _ = _get_tavily_tool()
            if not tavily_tool:
                raise Exception("Tavily 도구를 로드할 수 없습니다")
            
            result = await tavily_tool._arun(
                query=query,
                top_k=top_k,
                search_depth=kwargs.get("search_depth", "basic"),
                include_answer=kwargs.get("include_answer", True)
            )
            # trace_id 업데이트
            result.trace_id = trace_id
            return result
        except Exception as e:
            logger.error(f"❌ [InternetSearch] Tavily 오류: {e}")
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="tavily", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

    async def _search_with_bing(
        self, query: str, top_k: int, trace_id: str, **kwargs
    ) -> SearchToolResult:
        """Bing으로 검색"""
        try:
            bing_tool = _get_bing_tool()
            if not bing_tool:
                raise Exception("Bing 도구를 로드할 수 없습니다")
            
            result = await bing_tool._arun(
                query=query,
                top_k=top_k,
                search_type=kwargs.get("search_type", "web"),
                market=kwargs.get("market", "ko-KR"),
                freshness=kwargs.get("freshness")
            )
            result.trace_id = trace_id
            return result
        except Exception as e:
            logger.error(f"❌ [InternetSearch] Bing 오류: {e}")
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="bing", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

    async def _search_with_duckduckgo(
        self, query: str, top_k: int, trace_id: str
    ) -> SearchToolResult:
        """DuckDuckGo로 검색 (폴백)"""
        start_time = datetime.utcnow()
        
        if not HAS_DDG:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="duckduckgo", trace_id=trace_id),
                errors=["duckduckgo-search 패키지가 설치되지 않았습니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
        
        try:
            max_retries = 3
            
            def do_search():
                for attempt in range(max_retries):
                    try:
                        with DDGS() as ddgs:
                            results = list(ddgs.text(query, region="kr-kr", max_results=top_k))
                        return results
                    except (RatelimitException, DuckDuckGoSearchException) as e:
                        if "Ratelimit" in str(e) or isinstance(e, RatelimitException):
                            if attempt < max_retries - 1:
                                wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                                logger.warning(f"⏳ [DuckDuckGo] Rate limit, {wait_time:.1f}초 후 재시도")
                                time.sleep(wait_time)
                            else:
                                raise
                        else:
                            raise
                return []
            
            raw_results = await asyncio.to_thread(do_search)
            
            chunks = []
            if raw_results:
                for idx, res in enumerate(raw_results):
                    content = f"제목: {res.get('title', '')}\n내용: {res.get('body', '')}\n출처: {res.get('href', '')}"
                    
                    chunk = SearchChunk(
                        chunk_id=f"ddg_{trace_id}_{idx}",
                        content=content,
                        score=0.9 - (idx * 0.05),
                        file_id=None,
                        match_type="internet",
                        container_id="duckduckgo",
                        metadata={
                            "source": "duckduckgo",
                            "url": res.get('href'),
                            "title": res.get('title'),
                            "snippet": res.get('body')
                        }
                    )
                    chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=0,
                search_params={"query": query, "top_k": top_k},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="duckduckgo",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            logger.error(f"❌ [DuckDuckGo] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="duckduckgo", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

    def _run(
        self,
        query: str,
        top_k: int = 0,
        provider: Optional[str] = None,
        **kwargs
    ) -> SearchToolResult:
        """인터넷 검색 실행 (동기)"""
        if not settings.web_search_enabled:
            trace_id = str(uuid.uuid4())
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": "" if not settings.web_search_log_queries else query},
                metrics=ToolMetrics(latency_ms=0, provider="disabled", trace_id=trace_id),
                errors=["WEB_SEARCH가 비활성화되어 있습니다 (web_search_enabled=false)."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version,
            )

        if not isinstance(top_k, int) or top_k <= 0:
            top_k = int(settings.web_search_max_results or 6)

        selected_provider = provider or self._get_preferred_provider()
        
        if selected_provider == "tavily":
            tavily_tool, _ = _get_tavily_tool()
            if tavily_tool:
                return tavily_tool._run(query=query, top_k=top_k, **kwargs)
        elif selected_provider == "bing":
            bing_tool = _get_bing_tool()
            if bing_tool:
                return bing_tool._run(query=query, top_k=top_k, **kwargs)
        elif selected_provider == "duckduckgo":
            return self._run_duckduckgo(query, top_k)
        
        trace_id = str(uuid.uuid4())
        return SearchToolResult(
            success=False,
            data=[],
            total_found=0,
            filtered_count=0,
            search_params={"query": query},
            metrics=ToolMetrics(latency_ms=0, provider="none", trace_id=trace_id),
            errors=["사용 가능한 검색 제공자가 없습니다."],
            trace_id=trace_id,
            tool_name=self.name,
            tool_version=self.version
        )
    
    def _run_duckduckgo(self, query: str, top_k: int) -> SearchToolResult:
        """DuckDuckGo 동기 검색"""
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        if not HAS_DDG:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="duckduckgo", trace_id=trace_id),
                errors=["duckduckgo-search 패키지가 설치되지 않았습니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
        
        try:
            max_retries = 3
            raw_results = []
            
            for attempt in range(max_retries):
                try:
                    with DDGS() as ddgs:
                        raw_results = list(ddgs.text(query, region="kr-kr", max_results=top_k))
                    break
                except (RatelimitException, DuckDuckGoSearchException) as e:
                    if "Ratelimit" in str(e) or isinstance(e, RatelimitException):
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                            time.sleep(wait_time)
                        else:
                            raise
                    else:
                        raise
            
            chunks = []
            for idx, res in enumerate(raw_results):
                content = f"제목: {res.get('title', '')}\n내용: {res.get('body', '')}\n출처: {res.get('href', '')}"
                
                chunk = SearchChunk(
                    chunk_id=f"ddg_{trace_id}_{idx}",
                    content=content,
                    score=0.9 - (idx * 0.05),
                    file_id=None,
                    match_type="internet",
                    container_id="duckduckgo",
                    metadata={
                        "source": "duckduckgo",
                        "url": res.get('href'),
                        "title": res.get('title'),
                        "snippet": res.get('body')
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=0,
                search_params={"query": query, "top_k": top_k},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="duckduckgo",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="duckduckgo", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )


# 전역 인스턴스
internet_search_tool = InternetSearchTool()

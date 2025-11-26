"""
Internet Search Tool - 인터넷 검색 도구
DuckDuckGo 등을 사용하여 외부 웹 검색 수행
"""
import asyncio
import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

# langchain_community가 설치되어 있다고 가정
try:
    from langchain_community.tools import DuckDuckGoSearchResults
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

from app.tools.contracts import (
    SearchToolResult, SearchChunk, ToolMetrics
)

class InternetSearchTool(BaseTool):
    """
    인터넷 검색 도구
    
    책임:
    - 외부 검색 엔진(DuckDuckGo 등)을 통한 웹 검색
    - 검색 결과를 SearchChunk 형태로 변환
    
    책임 없음:
    - 내부 문서 검색
    - 중복 제거
    """
    name: str = "internet_search"
    description: str = "인터넷 검색을 수행하여 최신 정보나 외부 지식을 찾습니다."
    version: str = "1.0.0"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    async def _arun(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> SearchToolResult:
        """
        인터넷 검색 실행 (비동기)
        
        Args:
            query: 검색 질의
            top_k: 반환할 최대 결과 수
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        if not HAS_DDG:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="internet", trace_id=trace_id),
                errors=["langchain-community 또는 duckduckgo-search 패키지가 필요합니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        try:
            # DuckDuckGo 검색 실행
            wrapper = DuckDuckGoSearchAPIWrapper(max_results=top_k, region="kr-kr")
            search = DuckDuckGoSearchResults(api_wrapper=wrapper)
            
            # 동기 함수이므로 스레드 풀에서 실행
            results_str = await asyncio.to_thread(search.run, query)
            
            # 결과 파싱 (DuckDuckGoSearchResults는 문자열로 반환됨, 보통 snippet, title, link 포함)
            # 포맷: [snippet: ..., title: ..., link: ...], ...
            # 정규식이나 파싱이 필요할 수 있음. 
            # langchain의 DuckDuckGoSearchResults는 기본적으로 포맷팅된 문자열을 반환함.
            # 여기서는 간단히 문자열을 청크로 변환하거나, 가능하다면 raw results를 가져오는 것이 좋음.
            
            # 직접 wrapper를 사용하여 raw results 가져오기 시도
            raw_results = await asyncio.to_thread(wrapper.results, query, max_results=top_k)
            
            chunks = []
            for idx, res in enumerate(raw_results):
                content = f"제목: {res.get('title', '')}\n내용: {res.get('snippet', '')}\n출처: {res.get('link', '')}"
                
                chunk = SearchChunk(
                    chunk_id=f"web_{trace_id}_{idx}",
                    content=content,
                    score=0.9 - (idx * 0.05),  # 순위 기반 가상 점수
                    file_id=None,
                    match_type="internet",
                    container_id="internet",
                    metadata={
                        "source": "internet",
                        "url": res.get('link'),
                        "title": res.get('title'),
                        "snippet": res.get('snippet')
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
            logger.error(f"❌ [InternetSearch] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internet", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

    def _run(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> SearchToolResult:
        """
        인터넷 검색 실행 (동기)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        if not HAS_DDG:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="internet", trace_id=trace_id),
                errors=["langchain-community 또는 duckduckgo-search 패키지가 필요합니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        try:
            # DuckDuckGo 검색 실행
            wrapper = DuckDuckGoSearchAPIWrapper(max_results=top_k, region="kr-kr")
            
            # 직접 wrapper를 사용하여 raw results 가져오기
            raw_results = wrapper.results(query, max_results=top_k)
            
            chunks = []
            for idx, res in enumerate(raw_results):
                content = f"제목: {res.get('title', '')}\n내용: {res.get('snippet', '')}\n출처: {res.get('link', '')}"
                
                chunk = SearchChunk(
                    chunk_id=f"web_{trace_id}_{idx}",
                    content=content,
                    score=0.9 - (idx * 0.05),  # 순위 기반 가상 점수
                    file_id=None,
                    match_type="internet",
                    container_id="internet",
                    metadata={
                        "source": "internet",
                        "url": res.get('link'),
                        "title": res.get('title'),
                        "snippet": res.get('snippet')
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
            logger.error(f"❌ [InternetSearch] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internet", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

# 전역 인스턴스
internet_search_tool = InternetSearchTool()

"""
Bing Search Tool - Azure Bing Search API 웹 검색 도구
Microsoft Bing Search API v7을 사용하여 웹/뉴스 검색 수행
"""
import asyncio
import uuid
import aiohttp
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.tools.contracts import (
    SearchToolResult, SearchChunk, ToolMetrics
)
from app.core.config import settings


class BingSearchTool(BaseTool):
    """
    Bing Search 도구 (Azure)
    
    특징:
    - Microsoft Azure Bing Search API v7
    - 웹, 뉴스, 이미지 검색 지원
    - 엔터프라이즈 안정성
    - 한국어 검색 우수
    
    책임:
    - Bing Search API를 통한 웹/뉴스 검색
    - 검색 결과를 SearchChunk 형태로 변환
    """
    name: str = "bing_search"
    description: str = "Microsoft Bing을 사용한 웹 검색. 뉴스, 최신 정보, 기업 정보 검색에 적합합니다."
    version: str = "1.0.0"
    
    # Bing Search API 엔드포인트
    WEB_SEARCH_ENDPOINT: str = "https://api.bing.microsoft.com/v7.0/search"
    NEWS_SEARCH_ENDPOINT: str = "https://api.bing.microsoft.com/v7.0/news/search"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        search_type: str = "web",  # web | news | both
        market: str = "ko-KR",
        freshness: Optional[str] = None,  # Day | Week | Month
        **kwargs
    ) -> SearchToolResult:
        """
        Bing 검색 실행 (비동기)
        
        Args:
            query: 검색 질의
            top_k: 반환할 최대 결과 수
            search_type: 검색 유형 (web, news, both)
            market: 검색 시장/언어 (ko-KR, en-US 등)
            freshness: 결과 신선도 필터 (Day, Week, Month)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        # API 키 확인
        api_key = settings.bing_search_api_key
        if not api_key:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="bing", trace_id=trace_id),
                errors=["BING_SEARCH_API_KEY가 설정되지 않았습니다. .env 파일에 BING_SEARCH_API_KEY를 추가하세요."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        try:
            logger.info(
                f"🔍 [BingSearch] 검색 시작: query=({self._format_query_for_log(query)}) (type={search_type}, market={market})"
            )
            
            chunks = []
            
            async with aiohttp.ClientSession() as session:
                # 웹 검색
                if search_type in ["web", "both"]:
                    web_results = await self._search_web(
                        session, api_key, query, top_k, market, freshness
                    )
                    chunks.extend(web_results)
                
                # 뉴스 검색
                if search_type in ["news", "both"]:
                    news_count = top_k if search_type == "news" else min(3, top_k)
                    news_results = await self._search_news(
                        session, api_key, query, news_count, market, freshness
                    )
                    # 뉴스 결과에 태그 추가
                    for chunk in news_results:
                        chunk.metadata["result_type"] = "news"
                    chunks.extend(news_results)
            
            # trace_id로 chunk_id 업데이트
            for idx, chunk in enumerate(chunks):
                chunk.chunk_id = f"bing_{trace_id}_{idx}"
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ [BingSearch] 검색 완료: {len(chunks)}개 결과, {latency_ms:.0f}ms")
            
            return SearchToolResult(
                success=True,
                data=chunks[:top_k],  # top_k 제한
                total_found=len(chunks),
                filtered_count=max(0, len(chunks) - top_k),
                search_params={
                    "query": query,
                    "top_k": top_k,
                    "search_type": search_type,
                    "market": market
                },
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="bing",
                    items_returned=min(len(chunks), top_k),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            logger.error(f"❌ [BingSearch] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="bing", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

    async def _search_web(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        query: str,
        count: int,
        market: str,
        freshness: Optional[str]
    ) -> List[SearchChunk]:
        """웹 검색 수행"""
        headers = {
            "Ocp-Apim-Subscription-Key": api_key
        }
        
        params = {
            "q": query,
            "count": str(count),
            "mkt": market,
            "responseFilter": "Webpages",
            "textDecorations": "false",
            "textFormat": "Raw"
        }
        
        if freshness:
            params["freshness"] = freshness
        
        async with session.get(
            self.WEB_SEARCH_ENDPOINT,
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=settings.web_search_timeout_seconds)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"❌ [BingSearch] Web API 오류: {response.status} - {error_text}")
                return []
            
            data = await response.json()
            
        chunks = []
        web_pages = data.get("webPages", {}).get("value", [])
        
        for idx, page in enumerate(web_pages):
            title = page.get("name", "")
            snippet = page.get("snippet", "")
            url = page.get("url", "")
            date_published = page.get("dateLastCrawled", "")
            
            content = f"제목: {title}\n내용: {snippet}\n출처: {url}"
            if date_published:
                content += f"\n날짜: {date_published[:10]}"
            
            chunk = SearchChunk(
                chunk_id=f"bing_web_{idx}",
                content=content,
                score=0.9 - (idx * 0.05),
                file_id=None,
                match_type="internet",
                container_id="bing",
                metadata={
                    "source": "bing",
                    "result_type": "web",
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "date_crawled": date_published
                }
            )
            chunks.append(chunk)
        
        return chunks

    async def _search_news(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        query: str,
        count: int,
        market: str,
        freshness: Optional[str]
    ) -> List[SearchChunk]:
        """뉴스 검색 수행"""
        headers = {
            "Ocp-Apim-Subscription-Key": api_key
        }
        
        params = {
            "q": query,
            "count": str(count),
            "mkt": market,
            "textDecorations": "false",
            "textFormat": "Raw"
        }
        
        if freshness:
            params["freshness"] = freshness
        
        async with session.get(
            self.NEWS_SEARCH_ENDPOINT,
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=settings.web_search_timeout_seconds)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"❌ [BingSearch] News API 오류: {response.status} - {error_text}")
                return []
            
            data = await response.json()
            
        chunks = []
        news_items = data.get("value", [])
        
        for idx, news in enumerate(news_items):
            title = news.get("name", "")
            description = news.get("description", "")
            url = news.get("url", "")
            date_published = news.get("datePublished", "")
            provider = news.get("provider", [{}])[0].get("name", "") if news.get("provider") else ""
            
            content = f"[뉴스] 제목: {title}\n내용: {description}\n출처: {url}"
            if provider:
                content += f"\n제공: {provider}"
            if date_published:
                content += f"\n발행일: {date_published[:10]}"
            
            chunk = SearchChunk(
                chunk_id=f"bing_news_{idx}",
                content=content,
                score=0.95 - (idx * 0.05),  # 뉴스는 조금 더 높은 점수
                file_id=None,
                match_type="internet",
                container_id="bing",
                metadata={
                    "source": "bing",
                    "result_type": "news",
                    "url": url,
                    "title": title,
                    "snippet": description,
                    "provider": provider,
                    "date_published": date_published
                }
            )
            chunks.append(chunk)
        
        return chunks

    def _run(
        self,
        query: str,
        top_k: int = 5,
        search_type: str = "web",
        market: str = "ko-KR",
        freshness: Optional[str] = None,
        **kwargs
    ) -> SearchToolResult:
        """
        Bing 검색 실행 (동기)
        """
        import requests
        
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        api_key = settings.bing_search_api_key
        if not api_key:
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=0, provider="bing", trace_id=trace_id),
                errors=["BING_SEARCH_API_KEY가 설정되지 않았습니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        try:
            logger.info(f"🔍 [BingSearch] 검색 시작: query=({self._format_query_for_log(query)})")
            
            headers = {"Ocp-Apim-Subscription-Key": api_key}
            params = {
                "q": query,
                "count": str(top_k),
                "mkt": market,
                "responseFilter": "Webpages",
                "textDecorations": "false",
                "textFormat": "Raw"
            }
            
            if freshness:
                params["freshness"] = freshness
            
            response = requests.get(
                self.WEB_SEARCH_ENDPOINT,
                headers=headers,
                params=params,
                timeout=settings.web_search_timeout_seconds
            )
            
            if response.status_code != 200:
                raise Exception(f"Bing API 오류: {response.status_code} - {response.text}")
            
            data = response.json()
            
            chunks = []
            web_pages = data.get("webPages", {}).get("value", [])
            
            for idx, page in enumerate(web_pages):
                title = page.get("name", "")
                snippet = page.get("snippet", "")
                url = page.get("url", "")
                
                content = f"제목: {title}\n내용: {snippet}\n출처: {url}"
                
                chunk = SearchChunk(
                    chunk_id=f"bing_{trace_id}_{idx}",
                    content=content,
                    score=0.9 - (idx * 0.05),
                    file_id=None,
                    match_type="internet",
                    container_id="bing",
                    metadata={
                        "source": "bing",
                        "result_type": "web",
                        "url": url,
                        "title": title,
                        "snippet": snippet
                    }
                )
                chunks.append(chunk)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ [BingSearch] 검색 완료: {len(chunks)}개 결과")
            
            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=0,
                search_params={"query": query, "top_k": top_k},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="bing",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            logger.error(f"❌ [BingSearch] 실패: {e}")
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"query": query},
                metrics=ToolMetrics(latency_ms=latency_ms, provider="bing", trace_id=trace_id),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )


# 전역 인스턴스
bing_search_tool = BingSearchTool()

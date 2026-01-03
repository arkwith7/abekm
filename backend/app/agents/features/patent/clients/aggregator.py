"""
Patent Source Aggregator - 다중 데이터 소스 통합 검색기

여러 특허 데이터베이스(KIPRIS, Google Patents, USPTO 등)를 
통합하여 검색하는 어그리게이터.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from ..core.interfaces import BasePatentClient
from ..core.models import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    AggregatedSearchResult,
    PatentJurisdiction,
)
from .kipris_client import KiprisPatentClient

from app.core.config import settings


class PatentSourceAggregator:
    """
    다중 특허 데이터 소스 통합 검색기
    
    여러 특허 DB 클라이언트를 관리하고, 통합 검색을 제공합니다.
    새로운 데이터 소스 추가 시 _register_clients()에 등록만 하면 됩니다.
    
    Features:
        - 다중 소스 병렬 검색
        - 관할권 기반 소스 필터링
        - 결과 통합 및 중복 제거
        - 소스별 실패 처리
    
    Usage:
        aggregator = PatentSourceAggregator()
        result = await aggregator.search(query, jurisdictions=['KR', 'US'])
    """
    
    def __init__(self, auto_register: bool = True):
        """
        Args:
            auto_register: 사용 가능한 클라이언트 자동 등록 여부
        """
        self._clients: Dict[str, BasePatentClient] = {}
        
        if auto_register:
            self._register_clients()
    
    def _register_clients(self):
        """
        사용 가능한 클라이언트 등록
        
        환경 변수/설정에 따라 활성화된 데이터 소스만 등록합니다.
        새로운 데이터 소스 추가 시 이 메서드에 등록 로직을 추가합니다.
        """
        # KIPRIS (한국)
        if getattr(settings, 'kipris_api_key', None):
            self._clients['KIPRIS'] = KiprisPatentClient()
            logger.info("✅ [PatentAggregator] KIPRIS 클라이언트 등록")
        
        # Google Patents (글로벌) - SerpAPI 사용
        if getattr(settings, 'serpapi_api_key', None):
            try:
                from .google_patents_client import GooglePatentsClient
                self._clients['GOOGLE'] = GooglePatentsClient()
                logger.info("✅ [PatentAggregator] Google Patents 클라이언트 등록")
            except ImportError as e:
                logger.warning(f"⚠️ [PatentAggregator] Google Patents 클라이언트 로드 실패: {e}")
        
        # USPTO (미국) - 향후 구현
        # if getattr(settings, 'USPTO_API_KEY', None):
        #     self._clients['USPTO'] = UsptoClient()
        
        # EPO Espacenet (유럽) - 향후 구현
        # if getattr(settings, 'EPO_API_KEY', None):
        #     self._clients['EPO'] = EspacenetClient()
        
        # J-PlatPat (일본) - 향후 구현
        # if getattr(settings, 'JPO_API_KEY', None):
        #     self._clients['JPO'] = JplatpatClient()
        
        # CNIPA (중국) - 향후 구현
        # if getattr(settings, 'CNIPA_API_KEY', None):
        #     self._clients['CNIPA'] = CnipaClient()
        
        logger.info(
            f"📋 [PatentAggregator] 총 {len(self._clients)}개 클라이언트 등록: "
            f"{list(self._clients.keys())}"
        )
    
    def register_client(self, name: str, client: BasePatentClient):
        """
        클라이언트 수동 등록
        
        Args:
            name: 클라이언트 이름
            client: 클라이언트 인스턴스
        """
        self._clients[name] = client
        logger.info(f"✅ [PatentAggregator] {name} 클라이언트 등록")
    
    def get_client(self, name: str) -> Optional[BasePatentClient]:
        """
        특정 클라이언트 조회
        
        Args:
            name: 클라이언트 이름
            
        Returns:
            Optional[BasePatentClient]: 클라이언트 인스턴스
        """
        return self._clients.get(name)
    
    def list_available_sources(self) -> List[str]:
        """사용 가능한 데이터 소스 목록"""
        return list(self._clients.keys())
    
    def list_available_jurisdictions(self) -> List[str]:
        """사용 가능한 관할권 목록"""
        jurisdictions: Set[str] = set()
        for client in self._clients.values():
            jurisdictions.update(client.supported_jurisdictions)
        return sorted(jurisdictions)
    
    # =========================================================================
    # Search
    # =========================================================================
    
    async def search(
        self,
        query: PatentSearchQuery,
        sources: Optional[List[str]] = None,
        jurisdictions: Optional[List[str]] = None,
    ) -> AggregatedSearchResult:
        """
        다중 소스 통합 검색
        
        Args:
            query: 검색 쿼리
            sources: 검색할 소스 목록 (None이면 전체)
            jurisdictions: 검색할 관할권 목록 (None이면 전체)
            
        Returns:
            AggregatedSearchResult: 통합 검색 결과
        """
        start_time = datetime.utcnow()
        
        # 대상 클라이언트 필터링
        target_clients = self._filter_clients(sources, jurisdictions)
        
        if not target_clients:
            logger.warning("⚠️ [PatentAggregator] 사용 가능한 클라이언트 없음")
            return AggregatedSearchResult(
                patents=[],
                total_count=0,
                unique_count=0,
                source_results={},
                search_time_ms=0,
                sources_queried=[],
                sources_failed=[],
            )
        
        # 병렬 검색 실행
        logger.info(
            f"🔍 [PatentAggregator] 검색 시작: sources={[c.source_name for c in target_clients]}"
        )
        
        tasks = [client.search(query) for client in target_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 처리
        source_results: Dict[str, SearchResult] = {}
        sources_queried: List[str] = []
        sources_failed: List[str] = []
        
        for client, result in zip(target_clients, results):
            source_name = client.source_name
            
            if isinstance(result, Exception):
                logger.error(f"❌ [PatentAggregator] {source_name} 검색 실패: {result}")
                sources_failed.append(source_name)
            else:
                source_results[source_name] = result
                sources_queried.append(source_name)
        
        # 결과 통합 및 중복 제거
        all_patents = self._merge_results(source_results)
        unique_patents = self._deduplicate_patents(all_patents)
        
        total_count = sum(r.total_count for r in source_results.values())
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(
            f"✅ [PatentAggregator] 검색 완료: "
            f"total={len(all_patents)}, unique={len(unique_patents)}, "
            f"time={elapsed_ms:.0f}ms"
        )
        
        return AggregatedSearchResult(
            patents=unique_patents,
            total_count=total_count,
            unique_count=len(unique_patents),
            source_results=source_results,
            search_time_ms=elapsed_ms,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
        )
    
    async def search_prior_art(
        self,
        claims: List[str],
        title: str = "",
        abstract: str = "",
        jurisdictions: Optional[List[str]] = None,
    ) -> AggregatedSearchResult:
        """
        선행기술 조사용 국제 검색
        
        선행기술 조사는 국제 DB 검색이 필수입니다.
        기본적으로 KR, US, EP, WO, JP, CN 관할권을 검색합니다.
        
        Args:
            claims: 청구항 목록
            title: 발명의 명칭
            abstract: 초록
            jurisdictions: 검색 관할권 (기본: 전체)
            
        Returns:
            AggregatedSearchResult: 선행기술 검색 결과
        """
        # 기본 관할권: 주요 국제 DB
        if jurisdictions is None:
            jurisdictions = ['KR', 'US', 'EP', 'WO', 'JP', 'CN']
        
        # 청구항에서 키워드 추출하여 쿼리 생성
        # 실제로는 더 정교한 키워드 추출 로직 필요
        query_text = f"{title} {abstract} {' '.join(claims[:3])}"[:500]
        
        query = PatentSearchQuery(
            query=query_text,
            jurisdictions=[PatentJurisdiction(j) for j in jurisdictions if j != "ALL"],
            max_results=100,  # 선행기술은 더 많은 결과 필요
        )
        
        return await self.search(query, jurisdictions=jurisdictions)
    
    # =========================================================================
    # Detail & Citations
    # =========================================================================
    
    async def get_detail(
        self,
        patent_number: str,
        source: Optional[str] = None,
    ) -> Optional[PatentData]:
        """
        특허 상세 정보 조회
        
        Args:
            patent_number: 특허번호
            source: 데이터 소스 (None이면 자동 감지)
            
        Returns:
            Optional[PatentData]: 특허 상세 정보
        """
        # 소스 지정된 경우
        if source and source in self._clients:
            return await self._clients[source].get_detail(patent_number)
        
        # 관할권에서 소스 추론
        from ..core.utils import extract_jurisdiction
        jurisdiction = extract_jurisdiction(patent_number)
        
        if jurisdiction:
            for client in self._clients.values():
                if jurisdiction.value in client.supported_jurisdictions:
                    return await client.get_detail(patent_number)
        
        # 모든 클라이언트에서 시도
        for client in self._clients.values():
            result = await client.get_detail(patent_number)
            if result:
                return result
        
        return None
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """전체 클라이언트 상태 확인"""
        results = {}
        
        for name, client in self._clients.items():
            try:
                results[name] = await client.health_check()
            except Exception as e:
                results[name] = {
                    "available": False,
                    "error": str(e),
                }
        
        return {
            "aggregator": "healthy",
            "total_clients": len(self._clients),
            "available_clients": sum(
                1 for r in results.values()
                if r.get("available", False)
            ),
            "clients": results,
        }
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    async def close(self):
        """모든 클라이언트 리소스 정리"""
        for client in self._clients.values():
            if hasattr(client, 'close'):
                await client.close()
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _filter_clients(
        self,
        sources: Optional[List[str]],
        jurisdictions: Optional[List[str]],
    ) -> List[BasePatentClient]:
        """소스/관할권 기준으로 클라이언트 필터링"""
        filtered = []
        
        for name, client in self._clients.items():
            # 소스 필터
            if sources and name not in sources:
                continue
            
            # 관할권 필터
            if jurisdictions:
                # 클라이언트가 요청된 관할권 중 하나라도 지원하는지 확인
                if not any(
                    j in client.supported_jurisdictions or j == "ALL"
                    for j in jurisdictions
                ):
                    continue
            
            filtered.append(client)
        
        return filtered
    
    def _merge_results(
        self,
        source_results: Dict[str, SearchResult],
    ) -> List[PatentData]:
        """소스별 결과 병합"""
        all_patents = []
        
        for result in source_results.values():
            all_patents.extend(result.patents)
        
        return all_patents
    
    def _deduplicate_patents(
        self,
        patents: List[PatentData],
    ) -> List[PatentData]:
        """중복 특허 제거 (특허번호 기준)"""
        seen: Set[str] = set()
        unique = []
        
        for patent in patents:
            # 정규화된 특허번호로 중복 체크
            from ..core.utils import normalize_patent_number
            normalized = normalize_patent_number(patent.patent_number)
            
            if normalized not in seen:
                seen.add(normalized)
                unique.append(patent)
        
        return unique


# 전역 싱글톤 인스턴스 (lazy initialization)
_aggregator_instance: Optional[PatentSourceAggregator] = None


def get_patent_aggregator() -> PatentSourceAggregator:
    """전역 어그리게이터 인스턴스 반환"""
    global _aggregator_instance
    
    if _aggregator_instance is None:
        _aggregator_instance = PatentSourceAggregator()
    
    return _aggregator_instance

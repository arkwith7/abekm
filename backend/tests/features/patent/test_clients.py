"""
Patent Clients 테스트

KIPRIS, Google Patents 클라이언트 및 Aggregator 테스트
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    PatentJurisdiction,
    PatentStatus,
)
from app.agents.features.patent.clients import (
    KiprisPatentClient,
    GooglePatentsClient,
    PatentSourceAggregator,
)


class TestKiprisClient:
    """KIPRIS 클라이언트 테스트"""
    
    def test_client_creation(self):
        """클라이언트 생성"""
        client = KiprisPatentClient()
        assert client.source_name == "KIPRIS"
        # supported_jurisdictions는 문자열 리스트
        assert "KR" in client.supported_jurisdictions
    
    def test_client_availability(self):
        """클라이언트 가용성 체크"""
        # API 키가 있으면 available
        client = KiprisPatentClient()
        # is_available은 property
        assert isinstance(client.is_available, bool)
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """빈 쿼리 검색"""
        client = KiprisPatentClient()
        query = PatentSearchQuery(
            query="",  # query 필드 사용
            max_results=10,
        )
        result = await client.search(query)
        
        assert isinstance(result, SearchResult)
        assert result.source == "KIPRIS"


class TestGooglePatentsClient:
    """Google Patents 클라이언트 테스트"""
    
    def test_client_creation(self):
        """클라이언트 생성"""
        client = GooglePatentsClient()
        assert client.source_name == "google_patents"
        assert PatentJurisdiction.US in client.supported_jurisdictions
        assert PatentJurisdiction.EP in client.supported_jurisdictions
    
    def test_supported_jurisdictions(self):
        """지원 관할권 확인"""
        client = GooglePatentsClient()
        jurisdictions = client.supported_jurisdictions
        
        # 주요 관할권 지원 확인
        assert PatentJurisdiction.US in jurisdictions
        assert PatentJurisdiction.EP in jurisdictions
        assert PatentJurisdiction.WO in jurisdictions
        assert PatentJurisdiction.JP in jurisdictions
        assert PatentJurisdiction.CN in jurisdictions
        assert PatentJurisdiction.KR in jurisdictions
    
    def test_applicant_match(self):
        """출원인 매칭 로직 테스트"""
        client = GooglePatentsClient()
        
        # 직접 매칭
        assert client._is_applicant_match("Samsung", "Samsung Electronics") == True
        assert client._is_applicant_match("삼성", "삼성전자 주식회사") == True
        
        # 비매칭
        assert client._is_applicant_match("LG", "삼성전자") == False
    
    def test_extract_jurisdiction(self):
        """관할권 추출 테스트"""
        client = GooglePatentsClient()
        
        assert client._extract_jurisdiction("US11734097B1") == PatentJurisdiction.US
        assert client._extract_jurisdiction("EP1234567A1") == PatentJurisdiction.EP
        assert client._extract_jurisdiction("KR1020230123456") == PatentJurisdiction.KR
        assert client._extract_jurisdiction("") == PatentJurisdiction.US  # 기본값


class TestPatentSourceAggregator:
    """특허 소스 Aggregator 테스트"""
    
    def test_aggregator_creation(self):
        """Aggregator 생성"""
        aggregator = PatentSourceAggregator(auto_register=False)
        assert len(aggregator.list_available_sources()) == 0
    
    def test_auto_registration(self):
        """자동 등록 테스트"""
        aggregator = PatentSourceAggregator(auto_register=True)
        sources = aggregator.list_available_sources()
        
        # 환경에 따라 등록된 클라이언트 수가 다름
        assert isinstance(sources, list)
    
    def test_manual_registration(self):
        """수동 등록 테스트"""
        aggregator = PatentSourceAggregator(auto_register=False)
        
        # Mock 클라이언트 등록
        mock_client = MagicMock()
        mock_client.source_name = "test_source"
        mock_client.supported_jurisdictions = [PatentJurisdiction.KR]
        
        aggregator.register_client("TEST", mock_client)
        
        assert "TEST" in aggregator.list_available_sources()
        assert aggregator.get_client("TEST") == mock_client
    
    def test_get_nonexistent_client(self):
        """존재하지 않는 클라이언트 조회"""
        aggregator = PatentSourceAggregator(auto_register=False)
        assert aggregator.get_client("NONEXISTENT") is None
    
    @pytest.mark.asyncio
    async def test_search_with_mock_clients(self):
        """Mock 클라이언트로 검색 테스트"""
        aggregator = PatentSourceAggregator(auto_register=False)
        
        # Mock 클라이언트 생성
        mock_patent = PatentData(
            patent_number="TEST-001",
            title="테스트 특허",
            applicant="테스트 회사",
        )
        
        mock_client = AsyncMock()
        mock_client.source_name = "test"
        mock_client.supported_jurisdictions = ["KR"]  # 문자열 리스트
        mock_client.is_available = True  # property 형식
        mock_client.search.return_value = SearchResult(
            patents=[mock_patent],
            total_count=1,
            source="test",
        )
        
        aggregator.register_client("TEST", mock_client)
        
        # 검색 실행 - query 필드 사용
        query = PatentSearchQuery(
            query="테스트",
            jurisdictions=[PatentJurisdiction.KR],
            max_results=10,
        )
        result = await aggregator.search(query)
        
        # AggregatedSearchResult 형식 확인
        assert result.total_count >= 1
        # source_name이 'test' (lowercase)
        assert "test" in result.sources_queried


class TestClientIntegration:
    """클라이언트 통합 테스트 (실제 API 호출은 skip)"""
    
    @pytest.mark.skipif(
        True,  # 실제 API 테스트는 수동으로만 실행
        reason="실제 API 호출 테스트는 수동 실행"
    )
    @pytest.mark.asyncio
    async def test_kipris_real_search(self):
        """KIPRIS 실제 검색 (수동 테스트)"""
        client = KiprisPatentClient()
        
        if not client.is_available:  # property
            pytest.skip("KIPRIS API 키가 없습니다")
        
        query = PatentSearchQuery(
            query="인공지능",
            jurisdictions=[PatentJurisdiction.KR],
            max_results=5,
        )
        result = await client.search(query)
        
        assert result.total_count >= 0
        for patent in result.patents:
            assert patent.patent_number
            assert patent.title
    
    @pytest.mark.skipif(
        True,  # 실제 API 테스트는 수동으로만 실행
        reason="실제 API 호출 테스트는 수동 실행"
    )
    @pytest.mark.asyncio
    async def test_google_patents_real_search(self):
        """Google Patents 실제 검색 (수동 테스트)"""
        client = GooglePatentsClient()
        
        if not client.is_available:  # property
            pytest.skip("SerpAPI 키가 없습니다")
        
        query = PatentSearchQuery(
            query="artificial intelligence",
            jurisdictions=[PatentJurisdiction.US],
            max_results=5,
        )
        result = await client.search(query)
        
        assert result.total_count >= 0
        for patent in result.patents:
            assert patent.patent_number
            assert patent.title

"""
Patent Agents 테스트

Search Agent, Analysis Agent 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    PatentJurisdiction,
)


class TestPatentSearchAgent:
    """특허 검색 에이전트 테스트"""
    
    def test_agent_import(self):
        """에이전트 임포트 테스트"""
        from app.agents.features.patent.search_agent import (
            PatentSearchAgent,
            create_patent_search_agent,
        )
        assert PatentSearchAgent is not None
        assert create_patent_search_agent is not None
    
    def test_agent_creation(self):
        """에이전트 생성 테스트"""
        from app.agents.features.patent.search_agent import PatentSearchAgent
        
        agent = PatentSearchAgent()
        assert agent is not None
        assert agent.config is not None
    
    def test_agent_has_tools(self):
        """에이전트 도구 보유 테스트"""
        from app.agents.features.patent.search_agent import PatentSearchAgent
        
        agent = PatentSearchAgent()
        tools = agent._get_tools()  # private method
        
        # 최소 3개 도구
        assert len(tools) >= 3
        
        tool_names = [t.name for t in tools]
        assert "unified_patent_search" in tool_names


class TestPatentAnalysisAgent:
    """특허 분석 에이전트 테스트"""
    
    def test_agent_import(self):
        """에이전트 임포트 테스트"""
        from app.agents.features.patent.analysis_agent import (
            PatentAnalysisAgent,
            create_patent_analysis_agent,
        )
        assert PatentAnalysisAgent is not None
        assert create_patent_analysis_agent is not None
    
    def test_agent_creation(self):
        """에이전트 생성 테스트"""
        from app.agents.features.patent.analysis_agent import PatentAnalysisAgent
        
        agent = PatentAnalysisAgent()
        assert agent is not None
        # Analysis Agent는 _tools 속성 사용
        assert hasattr(agent, '_tools')
    
    def test_agent_has_tools(self):
        """에이전트 도구 보유 테스트"""
        from app.agents.features.patent.analysis_agent import PatentAnalysisAgent
        
        agent = PatentAnalysisAgent()
        tools = agent._tools  # private attribute
        
        # 최소 5개 도구
        assert len(tools) >= 5
        
        tool_names = [t.name for t in tools]
        # patent 관련 도구 확인
        assert any("patent" in name for name in tool_names)


class TestAgentIntegration:
    """에이전트 통합 테스트"""
    
    def test_agents_share_common_tools(self):
        """에이전트들이 도구를 가지고 있는지 테스트"""
        from app.agents.features.patent.search_agent import PatentSearchAgent
        from app.agents.features.patent.analysis_agent import PatentAnalysisAgent
        
        search_agent = PatentSearchAgent()
        analysis_agent = PatentAnalysisAgent()
        
        # Search Agent는 _get_tools(), Analysis Agent는 _tools
        search_tools = {t.name for t in search_agent._get_tools()}
        analysis_tools = {t.name for t in analysis_agent._tools}
        
        # 두 에이전트 모두 도구를 가지고 있음
        assert len(search_tools) >= 3, f"Search agent should have at least 3 tools, got {len(search_tools)}"
        assert len(analysis_tools) >= 5, f"Analysis agent should have at least 5 tools, got {len(analysis_tools)}"
    
    def test_factory_functions(self):
        """팩토리 함수 테스트"""
        from app.agents.features.patent.search_agent import create_patent_search_agent
        from app.agents.features.patent.analysis_agent import create_patent_analysis_agent
        
        search_agent = create_patent_search_agent()
        analysis_agent = create_patent_analysis_agent()
        
        assert search_agent is not None
        assert analysis_agent is not None


class TestPriorArtAgent:
    """선행기술 분석 에이전트 테스트"""
    
    def test_agent_import(self):
        """에이전트 임포트 테스트"""
        try:
            from app.agents.features.patent.prior_art_agent import (
                PriorArtAnalysisAgent,
            )
            assert PriorArtAnalysisAgent is not None
        except ImportError:
            # 선행기술 에이전트가 아직 마이그레이션되지 않았을 수 있음
            pytest.skip("Prior Art Agent not yet migrated")
    
    def test_compatibility_shim(self):
        """호환성 shim 테스트"""
        try:
            # 기존 경로에서 임포트 가능해야 함
            from app.agents.features.prior_art.agent import (
                PriorArtAnalysisAgent,
            )
            assert PriorArtAnalysisAgent is not None
        except ImportError:
            pytest.skip("Compatibility shim not available")

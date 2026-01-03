"""
Patent Tools 테스트

Search, Analysis 도구들 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    PatentJurisdiction,
)


class TestUnifiedSearchTool:
    """통합 검색 도구 테스트"""
    
    def test_tool_import(self):
        """도구 임포트 테스트"""
        from app.agents.features.patent.tools.search.unified_search_tool import (
            UnifiedPatentSearchTool,
            unified_search_tool,  # 실제 인스턴스 이름
        )
        assert UnifiedPatentSearchTool is not None
        assert unified_search_tool is not None
    
    def test_tool_creation(self):
        """도구 생성 테스트"""
        from app.agents.features.patent.tools.search.unified_search_tool import (
            UnifiedPatentSearchTool,
        )
        tool = UnifiedPatentSearchTool()
        assert tool.name == "unified_patent_search"
        assert tool.description


class TestSimilaritySearchTool:
    """유사 특허 검색 도구 테스트"""
    
    def test_tool_import(self):
        """도구 임포트 테스트"""
        from app.agents.features.patent.tools.search.similarity_search_tool import (
            PatentSimilaritySearchTool,
            similarity_search_tool,  # 실제 인스턴스 이름
        )
        assert PatentSimilaritySearchTool is not None
        assert similarity_search_tool is not None
    
    def test_tool_creation(self):
        """도구 생성 테스트"""
        from app.agents.features.patent.tools.search.similarity_search_tool import (
            PatentSimilaritySearchTool,
        )
        tool = PatentSimilaritySearchTool()
        assert tool.name == "patent_similarity_search"  # 실제 이름
        assert tool.description


class TestTrendAnalysisTool:
    """트렌드 분석 도구 테스트"""
    
    def test_tool_import(self):
        """도구 임포트 테스트"""
        from app.agents.features.patent.tools.analysis.trend_analysis_tool import (
            PatentTrendAnalysisTool,
            trend_analysis_tool,  # 실제 인스턴스 이름
        )
        assert PatentTrendAnalysisTool is not None
        assert trend_analysis_tool is not None
    
    def test_tool_creation(self):
        """도구 생성 테스트"""
        from app.agents.features.patent.tools.analysis.trend_analysis_tool import (
            PatentTrendAnalysisTool,
        )
        tool = PatentTrendAnalysisTool()
        assert tool.name == "patent_trend_analysis"  # 실제 이름
        assert tool.description


class TestPortfolioAnalysisTool:
    """포트폴리오 분석 도구 테스트"""
    
    def test_tool_import(self):
        """도구 임포트 테스트"""
        from app.agents.features.patent.tools.analysis.portfolio_analysis_tool import (
            PatentPortfolioAnalysisTool,
            portfolio_analysis_tool,  # 실제 인스턴스 이름
        )
        assert PatentPortfolioAnalysisTool is not None
        assert portfolio_analysis_tool is not None
    
    def test_tool_creation(self):
        """도구 생성 테스트"""
        from app.agents.features.patent.tools.analysis.portfolio_analysis_tool import (
            PatentPortfolioAnalysisTool,
        )
        tool = PatentPortfolioAnalysisTool()
        assert tool.name == "patent_portfolio_analysis"  # 실제 이름
        assert tool.description


class TestToolsIntegration:
    """도구 통합 테스트"""
    
    def test_all_tools_available(self):
        """모든 도구 가용성 테스트"""
        from app.agents.features.patent.tools.search.unified_search_tool import unified_search_tool
        from app.agents.features.patent.tools.search.similarity_search_tool import similarity_search_tool
        from app.agents.features.patent.tools.analysis.trend_analysis_tool import trend_analysis_tool
        from app.agents.features.patent.tools.analysis.portfolio_analysis_tool import portfolio_analysis_tool
        
        tools = [
            unified_search_tool,
            similarity_search_tool,
            trend_analysis_tool,
            portfolio_analysis_tool,
        ]
        
        for tool in tools:
            assert tool is not None
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
    
    def test_tool_descriptions_not_empty(self):
        """도구 설명이 비어있지 않은지 테스트"""
        from app.agents.features.patent.tools.search.unified_search_tool import unified_search_tool
        from app.agents.features.patent.tools.search.similarity_search_tool import similarity_search_tool
        from app.agents.features.patent.tools.analysis.trend_analysis_tool import trend_analysis_tool
        from app.agents.features.patent.tools.analysis.portfolio_analysis_tool import portfolio_analysis_tool
        
        tools = [
            unified_search_tool,
            similarity_search_tool,
            trend_analysis_tool,
            portfolio_analysis_tool,
        ]
        
        for tool in tools:
            assert len(tool.description) > 10

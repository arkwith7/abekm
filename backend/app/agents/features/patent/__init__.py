"""
Patent Feature-Pack: 특허 관련 에이전트 통합 모듈

레이어드 구조:
- core/: 공통 모델, 인터페이스, 유틸리티
- clients/: 데이터 소스 클라이언트 (KIPRIS, Google Patents, USPTO 등)
- tools/: 공유 도구 (검색, 분석, 공통)
- search_agent/: 특허 검색 에이전트
- analysis_agent/: 특허 분석 에이전트
- prior_art_agent/: 선행기술조사 에이전트
"""
from __future__ import annotations

# Core
from .core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    AggregatedSearchResult,
    PatentJurisdiction,
    PatentStatus,
    BasePatentClient,
)

# Clients
from .clients import (
    KiprisPatentClient,
    PatentSourceAggregator,
    get_patent_aggregator,
)

# Tools (primary exports)
from .tools import (
    UnifiedPatentSearchTool,
    unified_search_tool,
    PatentSimilaritySearchTool,
    similarity_search_tool,
    PatentTrendAnalysisTool,
    trend_analysis_tool,
    PatentPortfolioAnalysisTool,
    portfolio_analysis_tool,
)


# =============================================================================
# Lazy Agent Accessors (avoid circular imports)
# =============================================================================

def get_search_agent():
    """Get PatentSearchAgent instance"""
    from .search_agent import get_patent_search_agent
    return get_patent_search_agent()

def get_analysis_agent():
    """Get PatentAnalysisAgent instance"""
    from .analysis_agent import patent_analysis_agent
    return patent_analysis_agent

def get_prior_art_worker_specs():
    """Get Prior Art worker specs for AgentCatalog"""
    from .prior_art_agent import get_worker_specs
    return get_worker_specs()


__all__ = [
    # Core Models
    "PatentData",
    "PatentSearchQuery",
    "SearchResult",
    "AggregatedSearchResult",
    "PatentJurisdiction",
    "PatentStatus",
    "BasePatentClient",
    # Clients
    "KiprisPatentClient",
    "PatentSourceAggregator",
    "get_patent_aggregator",
    # Tools
    "UnifiedPatentSearchTool",
    "unified_search_tool",
    "PatentSimilaritySearchTool",
    "similarity_search_tool",
    "PatentTrendAnalysisTool",
    "trend_analysis_tool",
    "PatentPortfolioAnalysisTool",
    "portfolio_analysis_tool",
    # Agent accessors
    "get_search_agent",
    "get_analysis_agent",
    "get_prior_art_worker_specs",
]

"""
Patent Tools - 특허 공유 도구

검색, 분석, 공통 도구를 제공하는 모듈.
각 에이전트에서 필요한 도구를 import하여 사용.
"""
from __future__ import annotations

# Search Tools
from app.agents.features.patent.tools.search import (
    UnifiedPatentSearchTool,
    unified_search_tool,
    unified_patent_search,
    PatentSimilaritySearchTool,
    similarity_search_tool,
)

# Analysis Tools
from app.agents.features.patent.tools.analysis import (
    PatentTrendAnalysisTool,
    trend_analysis_tool,
    PatentPortfolioAnalysisTool,
    portfolio_analysis_tool,
)

# Common Tools
from app.agents.features.patent.tools.common import (
    PatentDetailTool,
    patent_detail_tool,
    LegalStatusTool,
    legal_status_tool,
)

__all__ = [
    # Search
    "UnifiedPatentSearchTool",
    "unified_search_tool",
    "unified_patent_search",
    "PatentSimilaritySearchTool",
    "similarity_search_tool",
    # Analysis
    "PatentTrendAnalysisTool",
    "trend_analysis_tool",
    "PatentPortfolioAnalysisTool",
    "portfolio_analysis_tool",
    # Common
    "PatentDetailTool",
    "patent_detail_tool",
    "LegalStatusTool",
    "legal_status_tool",
]

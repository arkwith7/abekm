"""Agents package - 에이전트 계층.

Import-time side effects를 피하기 위해 이 패키지는 lazy export를 사용한다.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "PresentationAgentTool",
    "presentation_agent_tool",
    "PatentAnalysisAgentTool",
    "patent_analysis_agent_tool",
    "agent_catalog",
    "AgentCatalog",
    "CatalogItem",
]


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name in {"PresentationAgentTool", "presentation_agent_tool"}:
        from app.agents.features.presentation import PresentationAgentTool, presentation_agent_tool

        return PresentationAgentTool if name == "PresentationAgentTool" else presentation_agent_tool

    if name in {"PatentAnalysisAgentTool", "patent_analysis_agent_tool"}:
        from app.agents.features.patent.analysis_agent import PatentAnalysisAgentTool, patent_analysis_agent_tool

        return (
            PatentAnalysisAgentTool
            if name == "PatentAnalysisAgentTool"
            else patent_analysis_agent_tool
        )

    if name in {"agent_catalog", "AgentCatalog", "CatalogItem"}:
        from app.agents.catalog import AgentCatalog, CatalogItem, agent_catalog

        if name == "AgentCatalog":
            return AgentCatalog
        if name == "CatalogItem":
            return CatalogItem
        return agent_catalog

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


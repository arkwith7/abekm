"""New agent registry for the modular agent architecture."""
from __future__ import annotations

from typing import Dict, Optional

try:  # pragma: no cover - optional dependency for LangChain compatibility
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:  # pragma: no cover
    from langchain_core.tools import BaseTool  # type: ignore

from app.agents.summary import SummaryAgentTool
from app.agents.presentation import PresentationAgentTool
from app.agents.patent import PatentAnalysisAgentTool


class AgentRegistry:
    """Registry mapping agent types to tool instances."""

    def __init__(self) -> None:
        self._agents: Dict[str, BaseTool] = {
            "summarizer": SummaryAgentTool(),
            "presentation": PresentationAgentTool(),
            "patent_analysis": PatentAnalysisAgentTool(),
        }

    def get_agent_tool(self, agent_type: str) -> Optional[BaseTool]:
        """Return the registered tool for the given agent type."""

        return self._agents.get(agent_type)

    def list_agent_types(self) -> Dict[str, str]:
        """Return a mapping of agent type to tool description."""

        return {agent_type: tool.description for agent_type, tool in self._agents.items()}


agent_registry = AgentRegistry()

__all__ = ["AgentRegistry", "agent_registry"]

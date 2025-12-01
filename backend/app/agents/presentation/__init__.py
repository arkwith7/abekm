"""Presentation agent package exports."""

from .presentation_agent import (
    PresentationAgentTool,
    presentation_agent_tool,
    PresentationReActAgent,
    QuickPPTReActAgent,
    presentation_react_agent,
    quick_ppt_react_agent,
)

__all__ = [
    # Legacy (Pipeline-based)
    "PresentationAgentTool", 
    "presentation_agent_tool",
    # New (ReAct-based)
    "PresentationReActAgent",
    "QuickPPTReActAgent",
    "presentation_react_agent",
    "quick_ppt_react_agent",
]

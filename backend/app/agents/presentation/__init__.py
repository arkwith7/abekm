"""Presentation agent package exports."""

# Unified agent (recommended)
from .unified_presentation_agent import (
    UnifiedPresentationAgent,
    unified_presentation_agent,
    PresentationAgentTool,
    presentation_agent_tool,
)

# Legacy aliases for backward compatibility
# These now point to the unified agent
PresentationReActAgent = UnifiedPresentationAgent
QuickPPTReActAgent = UnifiedPresentationAgent
presentation_react_agent = unified_presentation_agent
quick_ppt_react_agent = unified_presentation_agent

__all__ = [
    # Unified Agent (Recommended)
    "UnifiedPresentationAgent",
    "unified_presentation_agent",
    "PresentationAgentTool", 
    "presentation_agent_tool",
    
    # Legacy aliases (for backward compatibility)
    "PresentationReActAgent",
    "QuickPPTReActAgent",
    "presentation_react_agent",
    "quick_ppt_react_agent",
]

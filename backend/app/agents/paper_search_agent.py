"""Compatibility shim for the legacy import path.

The Search RAG agent has been moved to `app.agents.features.search_rag` as part of
Step 2 (feature-pack migration). Keep this module to avoid breaking imports.
"""

from __future__ import annotations

from app.agents.features.search_rag.agent import PaperSearchAgent, paper_search_agent

__all__ = ["PaperSearchAgent", "paper_search_agent"]

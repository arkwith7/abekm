"""Core agent orchestration building blocks.

This package holds supervisor/registry/state primitives that are shared across
multiple agent features.

Design goal:
- Keep public, stable imports in app.agents.*
- Allow internal re-org under app.agents.core / app.agents.features without
  breaking external callers.
"""

from .workers import WorkerSpec, get_default_workers

__all__ = [
    "WorkerSpec",
    "get_default_workers",
]

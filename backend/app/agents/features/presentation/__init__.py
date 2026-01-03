"""Presentation feature-pack.

This package provides a feature-pack worker spec for the Supervisor via AgentCatalog.
"""

from __future__ import annotations

from .worker import get_worker_specs

__all__ = ["get_worker_specs"]

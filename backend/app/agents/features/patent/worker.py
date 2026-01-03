"""Patent Feature-Pack Worker Registration.

Exposes PriorArtAgent for AgentCatalog discovery.
"""

from __future__ import annotations

from typing import Mapping

from app.agents.core.workers import WorkerSpec


def get_worker_specs() -> Mapping[str, WorkerSpec]:
    """Export patent-related workers for AgentCatalog discovery.
    
    Currently exports:
    - PriorArtAgent: KIPRIS 기반 선행기술 검색/정리(리포트 초안 생성)
    """
    from .prior_art_agent.worker import get_worker_specs as get_prior_art_specs
    
    return get_prior_art_specs()

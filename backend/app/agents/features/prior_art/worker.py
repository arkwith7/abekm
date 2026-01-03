from __future__ import annotations

from typing import Mapping

from app.agents.core.workers import WorkerSpec


async def prior_art_worker_node(state):
    # Delegate to the existing prior-art worker node, but keep the node's
    # `__module__` under `app.agents.features.prior_art.*` for catalog/testing.
    from app.agents.features.patent.prior_art_agent.graph import (
        prior_art_worker_node as _prior_art_worker_node,
    )

    return await _prior_art_worker_node(state)


def get_worker_specs() -> Mapping[str, WorkerSpec]:
    return {
        "PriorArtAgent": WorkerSpec(
            name="PriorArtAgent",
            description="KIPRIS 기반 선행기술 검색/정리(리포트 초안 생성)",
            node=prior_art_worker_node,
        )
    }

from __future__ import annotations

from typing import Mapping

from app.agents.core.workers import WorkerSpec

from .graph import prior_art_worker_node


def get_worker_specs() -> Mapping[str, WorkerSpec]:
    return {
        "PriorArtAgent": WorkerSpec(
            name="PriorArtAgent",
            description="KIPRIS 기반 선행기술 검색/정리(리포트 초안 생성)",
            node=prior_art_worker_node,
        )
    }

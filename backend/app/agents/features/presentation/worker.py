from __future__ import annotations

from typing import Mapping

from app.agents.core.workers import WorkerSpec

from .graph import presentation_worker_node


def get_worker_specs() -> Mapping[str, WorkerSpec]:
    return {
        "PresentationAgent": WorkerSpec(
            name="PresentationAgent",
            description="검색 결과 기반 PPT 생성",
            node=presentation_worker_node,
        )
    }

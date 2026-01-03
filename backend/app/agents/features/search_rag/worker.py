from __future__ import annotations

from typing import Mapping

from app.agents.catalog import WorkerSpec
from app.agents.features.search_rag.graph import search_rag_worker_node


def get_worker_specs() -> Mapping[str, WorkerSpec]:
    """Feature-pack exported workers for AgentCatalog discovery."""

    return {
        "SearchAgent": WorkerSpec(
            name="SearchAgent",
            description="논문/문서 검색 및 QA 수행",
            node=search_rag_worker_node,
        )
    }

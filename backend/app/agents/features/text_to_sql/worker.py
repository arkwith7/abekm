from __future__ import annotations

from typing import Mapping

from app.agents.catalog import WorkerSpec
from app.agents.features.text_to_sql.graph import text_to_sql_worker_node


def get_worker_specs() -> Mapping[str, WorkerSpec]:
    """Feature-pack exported workers for AgentCatalog discovery."""

    return {
        "TextToSQLAgent": WorkerSpec(
            name="TextToSQLAgent",
            description="자연어 질의를 안전한 SQL로 변환하고 조회 결과를 제공",
            node=text_to_sql_worker_node,
        )
    }

import pytest
from sqlalchemy import text


@pytest.mark.integration
async def test_integration_smoke_db_and_catalog() -> None:
    """Basic integration smoke: DB session works and AgentCatalog can load workers."""

    from app.agents import agent_catalog
    from app.agents.core.db import get_db_session_context

    workers = agent_catalog.get_workers()
    assert "SearchAgent" in workers
    assert "PresentationAgent" in workers
    assert "PriorArtAgent" in workers

    assert workers["SearchAgent"].node.__module__.startswith("app.agents.features.search_rag")
    assert workers["PresentationAgent"].node.__module__.startswith("app.agents.features.presentation")
    assert workers["PriorArtAgent"].node.__module__.startswith("app.agents.features.prior_art")

    async with get_db_session_context() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

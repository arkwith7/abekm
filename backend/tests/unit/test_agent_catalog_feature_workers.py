import sys

import pytest


def test_agent_catalog_prefers_feature_pack_workers() -> None:
    """AgentCatalog should discover feature-pack workers and allow them to override defaults."""

    # Avoid order-dependent flakiness if other tests already imported the feature pack.
    if (
        "app.agents.features.search_rag.worker" in sys.modules
        or "app.agents.features.presentation.worker" in sys.modules
        or "app.agents.features.patent.worker" in sys.modules
    ):
        pytest.skip("feature worker already imported; cannot assert discovery behavior")

    from app.agents import agent_catalog

    workers = agent_catalog.get_workers()
    assert "SearchAgent" in workers
    assert "PresentationAgent" in workers
    assert "PriorArtAgent" in workers

    # Our feature-pack implementation provides the SearchAgent worker node.
    assert workers["SearchAgent"].node.__module__.startswith("app.agents.features.search_rag")

    # Our feature-pack implementation provides the PresentationAgent worker node.
    assert workers["PresentationAgent"].node.__module__.startswith("app.agents.features.presentation")

    # Our feature-pack implementation provides the PriorArtAgent worker node.
    assert workers["PriorArtAgent"].node.__module__.startswith("app.agents.features.patent.prior_art_agent")

import sys

import pytest


def test_app_agents_package_is_lazy_on_import() -> None:
    """Ensure app.agents import doesn't eagerly load heavyweight agent modules."""

    # If another test already imported these, we can't meaningfully test laziness.
    if "app.agents.paper_search_agent" in sys.modules:
        pytest.skip("paper_search_agent already imported; cannot assert package laziness")

    import app.agents as agents

    assert "app.agents.paper_search_agent" not in sys.modules

    # Accessing the attribute should trigger the deferred import.
    _ = agents.paper_search_agent
    assert "app.agents.paper_search_agent" in sys.modules

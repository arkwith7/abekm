# Prior Art Feature Pack

Provides the `PriorArtAgent` worker via `AgentCatalog` feature discovery.

- Entry: `prior_art_worker_node` in `graph.py`
- Orchestration: `app.tools.prior_art.orchestrator.prior_art_orchestrator`

Notes:
- Imports are kept lazy to preserve import-safety for tests and misconfigured environments.
- Network calls to KIPRIS happen only when the node is executed.

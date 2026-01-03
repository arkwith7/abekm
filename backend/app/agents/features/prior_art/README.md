# Prior Art Feature Pack

Provides the `PriorArtAgent` worker via `AgentCatalog` feature discovery.

## Structure

```
prior_art/
├── graph.py              # LangGraph worker node
├── worker.py             # Worker spec provider
├── prompt.md             # System prompt
└── tools/                # Self-contained tools (2025-01-03)
    ├── orchestrator.py           # Main workflow orchestrator
    ├── patent_analysis_tool.py   # Input analysis
    ├── search_tool.py            # KIPRIS search
    ├── screening_tool.py         # Patent screening
    └── report_tool.py            # Report generation
```

## Migration Notes (2025-01-03)

**Tools consolidated into feature-pack:**
- Moved from `app/tools/prior_art/` → `app/agents/features/prior_art/tools/`
- All 5 tools (orchestrator, analysis, search, screening, report) are now self-contained
- Original `app/tools/prior_art/` removed (no external dependencies)

**Import Updates:**
- `graph.py`: Updated to `app.agents.features.prior_art.tools.orchestrator`
- `app/api/v1/agent.py`: Updated legacy import path

## Notes

- Entry: `prior_art_worker_node` in `graph.py`
- Orchestration: `app.agents.features.prior_art.tools.orchestrator.prior_art_orchestrator`
- Imports are kept lazy to preserve import-safety for tests and misconfigured environments
- Network calls to KIPRIS happen only when the node is executed

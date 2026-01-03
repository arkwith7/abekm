# Presentation Feature Pack

This feature-pack provides the `PresentationAgent` worker for the Supervisor via `AgentCatalog`.

## Structure (Consolidated 2026-01-03)

```
presentation/
├── graph.py              # LangGraph worker node
├── worker.py             # Worker spec provider
├── prompt.md             # System prompt
├── tools/                # Self-contained tools (13 files, ~5,900 lines)
│   ├── __init__.py
│   ├── outline_generation_tool.py
│   ├── quick_pptx_builder_tool.py
│   ├── template_analyzer_tool.py
│   ├── slide_type_matcher_tool.py
│   ├── content_mapping_tool.py
│   ├── templated_pptx_builder_tool.py
│   ├── visualization_tool.py
│   ├── ppt_quality_validator_tool.py
│   ├── template_ppt_comparator_tool.py
│   ├── ai_direct_mapping_tool.py
│   ├── quality_guard_tool.py
│   └── simple_ppt_builder_tool.py
├── services/             # PPT generation services (22 files, ~11,600 lines)
│   ├── __init__.py
│   ├── quick_ppt_generator_service.py
│   ├── templated_ppt_generator_service.py
│   ├── simple_ppt_builder.py
│   ├── ai_ppt_builder.py
│   ├── ppt_template_manager.py
│   ├── user_template_manager.py
│   ├── product_template_manager.py
│   ├── dynamic_slide_manager.py
│   ├── dynamic_template_manager.py
│   ├── ppt_template_extractor.py
│   ├── template_content_generator_service.py
│   ├── template_content_cleaner.py
│   ├── template_auto_mapping_service.py
│   ├── template_migration_service.py
│   ├── enhanced_object_processor.py
│   ├── file_manager.py
│   ├── thumbnail_generator.py
│   ├── pdf_preview_generator.py
│   ├── template_debugger.py
│   ├── ppt_wizard_store.py
│   └── ppt_models.py (if exists)
└── prompts/              # Agent prompts (5 files)
    ├── README.md
    ├── presentation.prompt
    ├── ai_direct_mapping_system.prompt
    ├── react_agent_system.prompt
    └── templated_react_agent_system.prompt
```

## Migration Notes (2026-01-03)

**Complete consolidation:**
- Moved from `app/tools/presentation/` → `app/agents/features/presentation/tools/`
- Moved from `app/services/presentation/` → `app/agents/features/presentation/services/`
- Moved from `backend/prompts/presentation/` → `app/agents/features/presentation/prompts/`

**Updated imports in:**
- All 13 tool files (tools → tools, tools → services)
- All 22 service files (internal cross-references)
- Main agent files: `unified_presentation_agent.py`, `ppt_generation_graph.py`

**Key characteristics:**
- Self-contained feature-pack with tools, services, and prompts
- Complex HITL (Human-in-the-Loop) workflow support
- Template-based and AI-driven slide generation
- Integration with Search RAG for content extraction
- Frontend coordination for interactive PPT creation

## Notes

- Entry: `presentation_worker_node` in `graph.py`
- Main agent: `app.agents.presentation.presentation_agent_tool`
- Uses: LangGraph for workflow orchestration
- Dependencies: Search RAG results, template files, PPT libraries

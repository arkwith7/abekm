# Deep Research Feature Pack

Provides autonomous deep research capabilities with agentic RAG workflow.

## Overview

The Deep Research Agent implements a **Plan → Retrieve → Write → Critique** loop to generate comprehensive, well-cited research reports.

## Architecture

```
deep_research/
├── __init__.py           # Feature-pack exports
├── agent.py              # DeepResearchAgent implementation (580 lines)
└── README.md             # This file
```

## Workflow

1. **Plan Phase**
   - Breaks down user query into sub-questions
   - Identifies key research areas
   - Max 5 sub-questions generated

2. **Retrieve Phase** (Hybrid Search)
   - **Internal Search**: Uses Search RAG Agent for document retrieval
   - **Web Search**: Internet search for external sources
   - Deduplication and source management
   - Citation numbering [1], [2], etc.

3. **Write Phase**
   - Synthesizes evidence into coherent report
   - Korean language output
   - Inline citations for every claim
   - Structured markdown format

4. **Critique Phase**
   - Validates report completeness
   - Identifies missing topics
   - Generates follow-up questions
   - Decides if iteration needed (max 3 iterations)

## Features

- ✅ Autonomous research planning
- ✅ Multi-source evidence gathering (internal + web)
- ✅ Citation tracking and formatting
- ✅ Quality assurance through critique loop
- ✅ Iterative refinement (up to 3 rounds)
- ✅ Comprehensive source references

## Usage

```python
from app.agents.features.deep_research import deep_research_agent

result = await deep_research_agent.execute(
    input_data={"query": "연구 질문"},
    context=context,
    mode=AgentMode.GRAPH
)
```

## API Integration

Invoked from streaming API when `tool='deep-research'`:
- Endpoint: `POST /api/v1/agent/stream`
- Parameter: `{"tool": "deep-research", "query": "..."}`

## Dependencies

- **Search RAG Agent**: For internal document search
- **AI Service**: LLM for planning, writing, critique
- **Internet Search Tools**: For web research

## Configuration

- `MAX_ITERATIONS = 3`: Maximum critique-refine cycles
- `MAX_FOLLOWUPS = 3`: Follow-up questions per critique
- `MAX_CHUNKS_PER_QUERY = 30`: Search result limit

## Output Format

```markdown
# [Research Title]

## 개요
...

## 주요 발견사항
- [1] 첫 번째 발견
- [2] 두 번째 발견

## 상세 분석
...

## 결론
...

## 참고자료
- [1] Source Title - URL/Location
- [2] Source Title - URL/Location
```

## Future Enhancements

- [ ] Graph integration for Supervisor routing
- [ ] Worker node for LangGraph architecture
- [ ] Streaming support for real-time updates
- [ ] Multi-language support
- [ ] Custom iteration limits
- [ ] Source quality scoring
- [ ] Fact-checking integration

## Notes

- Currently used via direct API call (not Supervisor-routed)
- Fully implemented and production-ready
- Moved to feature-pack structure: 2026-01-03

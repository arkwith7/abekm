# Search RAG Feature Pack

기존 `PaperSearchAgent`를 feature-pack 아키텍처로 마이그레이션하고 자체 완결적 구조로 통합

## 📁 구조

```
search_rag/
├── agent.py              # PaperSearchAgent 구현 (이전: app.agents.paper_search_agent)
├── graph.py              # LangGraph 워커 노드 래퍼
├── worker.py             # WorkerSpec 정의 (Supervisor 연동)
├── prompt.md             # Search RAG 프롬프트
├── tools/                # 🆕 통합 도구 모음
│   ├── retrieval/        # 검색 도구 (vector, keyword, fulltext, internet, multimodal)
│   ├── processing/       # 후처리 (deduplicate, rerank)
│   └── context/          # 컨텍스트 구성 (context_builder)
└── prompts/              # 🆕 프롬프트 리소스
    ├── search-failure.prompt
    └── summarizer.prompt
```

## 🎯 통합 완료 (2026-01-03)

### 이동된 도구들

**Retrieval Tools** (from `app.tools.retrieval`):
- `vector_search_tool.py` - 벡터 유사도 검색
- `keyword_search_tool.py` - 키워드 매칭 검색
- `fulltext_search_tool.py` - PostgreSQL tsvector 전문검색
- `internet_search_tool.py` - 통합 인터넷 검색
- `multimodal_search_tool.py` - 이미지 임베딩 검색

**Processing Tools** (from `app.tools.processing`):
- `deduplicate_tool.py` - 중복 제거
- `rerank_tool.py` - 재랭킹

**Context Tools** (from `app.tools.context`):
- `context_builder_tool.py` - 컨텍스트 구성

**Prompts** (from `prompts/`):
- `search-failure.prompt` - 검색 실패 응답
- `summarizer.prompt` - 문서 요약

## 🔄 호환성

- 기존 import 경로 `app.agents.paper_search_agent` 는 shim으로 유지됩니다.
- 원본 `app.tools/*` 경로는 향후 deprecated 처리 예정

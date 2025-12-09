# Deprecated Services

이 폴더에는 더 이상 활발하게 사용하지 않는 서비스들이 보관됩니다.

## 폴더 구조

```
deprecated/
├── chat/                          # 기존 채팅 서비스
│   ├── ai_agent_service.py        # -> agents/ 로 대체됨
│   ├── query_classification_service.py
│   ├── rag_response_service.py
│   └── unified_chat_service.py
│
├── multi_agent/                   # 기존 멀티 에이전트 시스템
│   ├── supervisor_agent.py        # -> agents/supervisor_agent.py 로 대체됨
│   ├── rag_agent.py
│   └── web_search_agent.py
│
├── legacy/                        # 레거시 서비스
│   ├── integrated_rag_pipeline_service_deprecated.py
│   └── vector_storage_service_integrated.py
│
├── presentation_archived/         # 기존 프레젠테이션 서비스
│   ├── enhanced_ppt_generator_service.py
│   ├── pptx_template_analyzer.py
│   └── template_metadata_extractor.py
│
└── integrated_content_service_part2.py
```

## Deprecated 사유

### chat/
- 새로운 Agent 기반 아키텍처(`/app/agents/`)로 전면 개편됨
- `api/v1/chat.py` → `api/v1/agent.py`로 엔드포인트 통합

### multi_agent/
- LangGraph 기반 새로운 `agents/supervisor_agent.py`로 대체
- 도구 기반 아키텍처(`/app/tools/`)로 리팩토링

### legacy/
- 초기 개발 시 사용했던 서비스들
- 현재 document/, search/ 서비스로 대체

### presentation_archived/
- 템플릿 기반 PPT 생성 시스템 개편
- `services/presentation/` 신규 서비스들로 대체

## 주의사항

⚠️ **이 폴더의 코드는 참조용으로만 유지됩니다.**
- 새로운 기능 개발 시 사용하지 마세요
- 필요한 로직이 있다면 활성 서비스로 마이그레이션하세요
- 6개월 후 삭제 예정 (2025-06-09)

## Deprecated Date
2025-12-09

# 🎯 Agent 도구 기반 아키텍처 구현 완료 보고서

**작성일**: 2025-11-12  
**목적**: LLM 기반 의도 분류 + 도구 라우팅 아키텍처 구축

---

## 📋 **1. 구현 개요**

### **핵심 철학**
> **"질의 의도를 파악하고 → 적절한 도구를 찾아 → 도구가 결과를 생성 → 도구를 찾을 수 없거나 결과가 없으면 명확히 안내"**

### **구현 범위**
- ✅ LLM 기반 통합 질의 분석 (재작성 + 의도 분류 + 도구 선택)
- ✅ 도구 디렉토리 체계 확립 (`/app/tools/`)
- ✅ 문서 요약 도구 (DB 문서 + 첨부 파일 통합)
- ✅ 도구 미지원 및 결과 부재 처리
- ✅ .env 기반 LLM 설정 (Azure OpenAI / Bedrock)

---

## 📂 **2. 디렉토리 구조**

```
backend/app/
├── services/              # 비즈니스 로직
│   └── chat/
│       ├── ai_agent_service.py          # 도구 라우팅
│       └── conversation_context_service.py  # 질의 분석
│
└── tools/                 # 🎯 Agent 도구 (독립적 유지보수)
    ├── contracts.py       # 도구 표준 인터페이스
    ├── retrieval/         # 검색 도구
    │   ├── vector_search_tool.py
    │   ├── keyword_search_tool.py
    │   └── fulltext_search_tool.py
    ├── processing/        # 처리 도구
    │   ├── deduplicate_tool.py
    │   └── rerank_tool.py
    ├── context/          # 컨텍스트 도구
    │   └── context_builder_tool.py
    └── document/         # 📚 문서 도구 (신규)
        ├── document_loader_tool.py      # DB 문서 로드
        └── document_summarizer_tool.py  # 통합 요약 도구 ⭐
```

---

## 🔧 **3. 핵심 컴포넌트**

### **3.1 통합 질의 분석 (`conversation_context_service.py`)**

**메서드**: `analyze_query_with_intent()`

**입력**:
- 사용자 질의문
- 대화 히스토리
- 선택된 문서/컨테이너 ID

**출력 (JSON)**:
```json
{
  "rewritten_query": "선택한 논문 '머신러닝 기초'의 주요 내용을 요약해주세요",
  "intent": "summarization",
  "confidence": 0.95,
  "required_tools": ["document_summarizer"],
  "parameters": {
    "document_ids": [5],
    "summarization_type": "comprehensive"
  },
  "reasoning": "사용자가 특정 문서 요약을 요청했으므로 document_summarizer 사용 필요"
}
```

**LLM 설정 (.env)**:
```bash
# 질의문 재작성 및 의도 분류 LLM
QUERY_REWRITE_PROVIDER=azure_openai
QUERY_REWRITE_AZURE_DEPLOYMENT=gpt-4o
QUERY_REWRITE_MAX_TOKENS=500
QUERY_REWRITE_TEMPERATURE=0.3
```

---

### **3.2 Document Summarizer Tool** ⭐

**파일**: `/app/tools/document/document_summarizer_tool.py`

**두 가지 입력 경로 지원**:

#### **Input 1: DB 저장 문서 (Vector Store)**
```python
# 사용자가 문서 검색 → 선택 → "요약해줘"
result = await document_summarizer_tool._arun(
    document_ids=[5, 12, 23],  # 선택된 문서 ID
    db_session=db,
    summarization_type="comprehensive"
)
```

**처리 흐름**:
1. `DocumentLoaderTool`로 `tb_document_chunks`에서 청크 조회
2. 페이지 순서대로 정렬
3. LLM으로 요약 생성

#### **Input 2: 첨부 파일 (Upload)**
```python
# 플로팅 채팅창에서 파일 첨부 → "요약해줘"
result = await document_summarizer_tool._arun(
    attachment_paths=["/uploads/temp/paper.pdf"],
    attachment_metadata=[{
        "file_name": "research_paper.pdf",
        "mime_type": "application/pdf"
    }],
    summarization_type="brief"
)
```

**처리 흐름**:
1. Azure Document Intelligence로 텍스트 추출
2. SearchChunk 형식으로 변환
3. LLM으로 요약 생성

#### **통합 결과**:
```python
{
    "success": True,
    "data": {
        "summary": "이 논문은 머신러닝의 기초 개념을...",
        "source_info": {
            "db_documents": 2,      # DB에서 2개
            "uploaded_files": 1,     # 첨부 1개
            "total_chunks": 47,
            "extraction_errors": []
        },
        "chunks": [...]
    },
    "metrics": {
        "latency_ms": 3245.5,
        "items_returned": 47
    }
}
```

---

### **3.3 도구 라우팅 로직 (`ai_agent_service.py`)**

**흐름**:
```python
# 1. 질의 분석
analysis = await conversation_context_service.analyze_query_with_intent(
    original_query=query,
    conversation_history=history,
    document_ids=[doc.id for doc in selected_documents],
    container_ids=container_ids
)

# 2. 도구 선택
intent = analysis['intent']
required_tools = analysis['required_tools']

# 3. 도구 라우팅
if intent == 'unsupported' or not required_tools:
    return "죄송합니다. 해당 요청을 처리할 수 있는 도구가 아직 준비되지 않았습니다."

if 'document_summarizer' in required_tools:
    result = await document_summarizer_tool._arun(
        document_ids=document_ids,
        attachment_paths=attachment_paths,
        db_session=db
    )
    
    if not result.success or not result.data['summary']:
        return "죄송합니다. 문서 내용을 추출할 수 없습니다."
    
    return result.data['summary']
```

---

## 🎯 **4. 핵심 원칙**

### **원칙 1: 도구가 책임을 진다**
- ❌ **나쁜 예**: 서비스 코드에 DB 쿼리, 텍스트 추출 로직 분산
- ✅ **좋은 예**: 도구가 모든 처리를 담당, 서비스는 라우팅만

### **원칙 2: 도구를 찾을 수 없으면 솔직하게 답변**
```python
if intent == 'unsupported':
    return {
        "message": "죄송합니다. 해당 요청을 처리할 수 있는 도구가 아직 준비되지 않았습니다.",
        "suggestion": "현재 지원: 문서 요약, 검색, 비교 분석"
    }
```

### **원칙 3: 도구 결과가 없으면 명확한 피드백**
```python
if not result.data:
    return f"""죄송합니다. 선택하신 문서의 내용을 찾을 수 없습니다.

이 문서가 아직 처리 중이거나, 시스템 오류가 발생했을 수 있습니다.
다른 문서를 선택하시거나, 잠시 후 다시 시도해 주세요."""
```

### **원칙 4: 답변이 부정확할 때 → 도구를 개선**
| 문제 | 해결 위치 | 방법 |
|------|----------|------|
| 검색 결과 부정확 | `vector_search_tool.py` | 임계값 조정, 임베딩 모델 변경 |
| 요약이 부족함 | `document_summarizer_tool.py` | max_chunks 증가, 프롬프트 개선 |
| 리랭킹 품질 문제 | `rerank_tool.py` | LLM 모델 변경, 프롬프트 개선 |
| 텍스트 추출 실패 | `document_summarizer_tool.py` | Azure DI 설정 확인, 폴백 로직 추가 |

---

## 🔄 **5. 확장 계획**

### **5.1 향후 추가 도구**
```
tools/
├── generation/              # 생성 도구
│   ├── ppt_generator_tool.py      # PPT 생성
│   └── report_generator_tool.py   # 보고서 생성
├── analysis/                # 분석 도구
│   ├── comparison_tool.py         # 문서 비교
│   └── trend_analysis_tool.py     # 트렌드 분석
└── validation/              # 검증 도구
    ├── fact_checker_tool.py       # 사실 확인
    └── citation_validator_tool.py # 인용 검증
```

### **5.2 도구 추가 프로세스**
1. `/app/tools/{category}/{tool_name}_tool.py` 생성
2. `BaseTool` 상속, `_arun()` 구현
3. `ToolResult` 반환 (contracts.py 준수)
4. `__init__.py`에 등록
5. `conversation_context_service.py`의 프롬프트에 도구 추가
6. `ai_agent_service.py`에 라우팅 로직 추가

---

## 📊 **6. 성능 및 모니터링**

### **로그 패턴**
```
🎯 질의 분석 결과: intent=summarization, confidence=0.95, tools=['document_summarizer']
✍️ 재작성 질의: '첨부 논문 요약' → '첨부한 연구 논문의 주요 내용을 요약해주세요'
📚 [Summarizer] DB 문서 로드: 2개
✅ [Summarizer] DB 문서 로드 완료: 35개 청크
📎 [Summarizer] 첨부 파일 처리: 1개
✅ [Summarizer] 파일 추출 완료: research_paper.pdf
📝 [Summarizer] 요약 생성 시작: 42개 청크, type=comprehensive
✅ [Summarizer] 요약 완료: DB=2, Upload=1, latency=3245.5ms
```

### **메트릭 수집**
- 도구별 실행 시간 (`ToolMetrics.latency_ms`)
- 성공/실패 비율 (`ToolResult.success`)
- 오류 패턴 (`ToolResult.errors`)
- 도구 사용 빈도 (`tool_name` 집계)

---

## ✅ **7. 완료 체크리스트**

- [x] .env에 질의 재작성 LLM 설정 추가
- [x] `config.py`에 `get_query_rewrite_config()` 구현
- [x] `conversation_context_service`의 LLM 호출 수정 (Bedrock → 설정 기반)
- [x] `analyze_query_with_intent()` 통합 질의 분석 함수 구현
- [x] `query_classification_service`에 summarization/comparison 패턴 추가
- [x] `DocumentLoaderTool` 생성 (DB 문서 로드)
- [x] `DocumentSummarizerTool` 생성 (DB + 첨부 파일 통합) ⭐
- [x] `ai_agent_service`에 도구 라우팅 로직 통합
- [x] 도구 미지원 메시지 처리
- [x] 도구 결과 부재 시 명확한 오류 메시지
- [ ] Agent 엔드포인트에 reasoning_step 이벤트 통합 (다음 단계)

---

## 🚀 **8. 다음 단계**

### **즉시 수행**
1. **테스트 시나리오 실행**:
   - DB 문서 선택 + "요약해줘"
   - 파일 첨부 + "주요 내용 정리해줘"
   - 지원하지 않는 요청 ("PPT 만들어줘")

2. **Agent 엔드포인트 통합** (`agent.py`):
   - `event_generator()`가 `analyze_query_with_intent()` 호출
   - reasoning_step 이벤트로 의도 분류 결과 스트리밍

### **향후 개선**
- PPT 생성 도구 구현
- 문서 비교 도구 구현
- 도구 실행 추적 (OpenTelemetry)
- 도구 성능 대시보드

---

## 📝 **9. 주요 파일 요약**

| 파일 | 역할 | 핵심 기능 |
|------|------|----------|
| `conversation_context_service.py` | 질의 분석 | `analyze_query_with_intent()` - LLM 기반 의도 분류 |
| `ai_agent_service.py` | 도구 라우팅 | 의도별 도구 선택 및 실행 |
| `document_loader_tool.py` | DB 문서 로드 | `tb_document_chunks`에서 청크 조회 |
| `document_summarizer_tool.py` | 통합 요약 | DB 문서 + 첨부 파일 모두 처리 ⭐ |
| `query_classification_service.py` | 패턴 기반 분류 | summarization/comparison 패턴 추가 |

---

**작성자**: AI Assistant  
**검토**: 사용자 확인 필요  
**상태**: ✅ 구현 완료, 테스트 대기

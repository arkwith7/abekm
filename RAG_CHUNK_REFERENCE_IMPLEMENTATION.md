# RAG 채팅 참조 문서 및 청크 정보 저장/복원 구현 완료

## 📋 요구사항 분석

### 1. 참조한 문서 저장 및 복원
- ✅ **이미 구현됨**: `referenced_documents` 배열로 문서 ID 저장 및 복원

### 2. 답변 생성 시 참고한 청크 정보 저장 및 복원
- ✅ **신규 구현됨**: `search_results.detailed_chunks`에 청크 상세 정보 저장

---

## 🔍 현재 상태 분석 (구현 전)

### ✅ 작동 중인 기능
1. **문서 ID 저장**
   - `tb_chat_history.referenced_documents` (ARRAY): `[6, 7]` 형태로 저장
   - 예: 7개 청크 사용 → 1개 문서 ID 저장 (중복 제거)

2. **문서 메타데이터 복원**
   ```json
   {
     "fileId": "6",
     "fileName": "토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf",
     "fileType": "pdf",
     "containerName": "USER_77107791_0627BBC2"
   }
   ```

### ❌ 누락된 기능
1. **청크 상세 정보 미저장**
   - 어떤 페이지의 어떤 내용을 참조했는지 알 수 없음
   - 유사도 점수, 검색 방식 등 메타데이터 손실

2. **프론트엔드 표시 불가**
   - "7개 청크 참조" 정보 표시 불가
   - "페이지 3, 유사도 0.53" 같은 상세 정보 표시 불가

---

## ✨ 구현 내용

### 1. 청크 상세 정보 저장 (`generate_stream` 함수)

**위치**: `backend/app/api/v1/chat.py` Line ~1884-1910

```python
# 🆕 청크 상세 정보 구조화 (문서명, 페이지, 내용 포함)
detailed_chunks = []
if references:
    for idx, ref in enumerate(references):
        chunk_info = {
            'index': idx + 1,                           # 청크 순서
            'file_id': ref.get('file_bss_info_sno'),   # 문서 ID
            'file_name': ref.get('file_name', ''),      # 문서명
            'chunk_index': ref.get('chunk_index', 0),   # 문서 내 청크 번호
            'page_number': ref.get('page_number'),      # 페이지 번호
            'content_preview': ref.get('content', '')[:200],  # 내용 미리보기 (200자)
            'similarity_score': ref.get('similarity_score', 0.0),  # 유사도
            'search_type': ref.get('search_type', 'unknown'),      # 검색 방식
            'section_title': ref.get('section_title', ''),         # 섹션 제목
        }
        detailed_chunks.append(chunk_info)

# search_results에 청크 상세 정보 추가
enhanced_search_results = {
    **(context_info if context_info else {}),
    'detailed_chunks': detailed_chunks,      # 🆕 청크 상세 정보
    'chunks_count': len(detailed_chunks),    # 청크 개수
    'documents_count': len(union_doc_ids)    # 문서 개수
}
```

**저장 대상**: `tb_chat_history.search_results` (JSONB 컬럼)

### 2. 청크 정보 복원 (`get_chat_session` 함수)

**위치**: `backend/app/api/v1/chat.py` Line ~665-675

```python
# 검색 결과/컨텍스트 포함 (JSONB)
if row.search_results:
    try:
        search_data = json.loads(row.search_results)
        assistant_msg['context_info'] = search_data
        
        # 🆕 청크 상세 정보 추출 및 포함
        if isinstance(search_data, dict) and 'detailed_chunks' in search_data:
            assistant_msg['detailed_chunks'] = search_data['detailed_chunks']
            logger.debug(f"📋 메시지 {i}에 {len(search_data['detailed_chunks'])}개 청크 정보 복원")
    except Exception as e:
        logger.warning(f"search_results JSON 파싱 실패: {e}")
```

---

## 📊 데이터 구조

### 저장 형식 (`tb_chat_history.search_results`)

```json
{
  "rag_used": true,
  "context_used": true,
  "chunks_count": 7,
  "documents_count": 1,
  "detailed_chunks": [
    {
      "index": 1,
      "file_id": 6,
      "file_name": "토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf",
      "chunk_index": 0,
      "page_number": 1,
      "content_preview": "DOI: https://doi.org/10.36491/APJSB.46.1.3\n중소기업연구 제46권 제1호 (2024년 3월)...",
      "similarity_score": 0.5326,
      "search_type": "hybrid",
      "section_title": ""
    },
    {
      "index": 2,
      "file_id": 6,
      "file_name": "토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf",
      "chunk_index": 3,
      "page_number": 4,
      "content_preview": "1990년대 자동차 산업의 기술 특허는 주로 엔진 효율화와...",
      "similarity_score": 0.4891,
      "search_type": "hybrid",
      "section_title": "III. 연구 결과"
    }
    // ... 5개 더
  ]
}
```

### 프론트엔드 수신 형식

```json
{
  "success": true,
  "session_id": "chat_1762498157156_p0oikzbsl",
  "messages": [
    {
      "id": "user_0",
      "role": "user",
      "content": "자동차 산업분야 기술로드맵을 위해 특허 분석을 어떤 기법을 사용하여 할수 있는지 알려 주세요",
      "timestamp": "2025-11-07T16:24:06Z"
    },
    {
      "id": "assistant_0",
      "role": "assistant",
      "content": "자동차 산업 기술 분석을 위해 특허 데이터 기반의 토픽 모델링 기법을 활용할 수 있습니다...",
      "timestamp": "2025-11-07T16:24:18Z",
      "referenced_documents": [6],
      "context_info": {
        "rag_used": true,
        "chunks_count": 7,
        "documents_count": 1
      },
      "detailed_chunks": [
        {
          "index": 1,
          "file_name": "토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf",
          "page_number": 1,
          "content_preview": "DOI: https://doi.org/10.36491/APJSB.46.1.3...",
          "similarity_score": 0.5326
        }
        // ... 6개 더
      ]
    }
  ],
  "referenced_documents": [
    {
      "fileId": "6",
      "fileName": "토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf",
      "fileType": "pdf",
      "containerName": "USER_77107791_0627BBC2"
    }
  ]
}
```

---

## 🎯 프론트엔드 통합 가이드

### 1. 참조 문서 목록 표시

```typescript
// ChatMessage 컴포넌트에서
interface DetailedChunk {
  index: number;
  file_name: string;
  page_number: number;
  content_preview: string;
  similarity_score: number;
  search_type: string;
}

const message = {
  role: 'assistant',
  content: '...',
  detailed_chunks: DetailedChunk[],
  context_info: {
    chunks_count: 7,
    documents_count: 1
  }
};

// UI 표시
<div className="reference-summary">
  <span>📚 {message.context_info.documents_count}개 문서의 {message.context_info.chunks_count}개 청크 참조</span>
  <button onClick={() => setShowDetails(true)}>상세 보기</button>
</div>
```

### 2. 청크 상세 정보 모달/확장 패널

```typescript
{showDetails && (
  <div className="chunks-detail">
    <h4>참조한 내용</h4>
    {message.detailed_chunks?.map((chunk, idx) => (
      <div key={idx} className="chunk-card">
        <div className="chunk-header">
          <span className="chunk-number">#{chunk.index}</span>
          <span className="file-name">{chunk.file_name}</span>
          <span className="page">p.{chunk.page_number}</span>
        </div>
        <div className="chunk-preview">
          {chunk.content_preview}...
        </div>
        <div className="chunk-meta">
          <span className="similarity">유사도: {(chunk.similarity_score * 100).toFixed(1)}%</span>
          <span className="search-type">{chunk.search_type}</span>
        </div>
      </div>
    ))}
  </div>
)}
```

### 3. 세션 복원 시 자동 표시

```typescript
// ChatPage.tsx에서 세션 로드 시
useEffect(() => {
  const loadSession = async (sessionId: string) => {
    const response = await fetch(`/api/v1/chat/sessions/${sessionId}`);
    const data = await response.json();
    
    // messages에 detailed_chunks가 자동 포함됨
    setMessages(data.messages);
    setReferencedDocuments(data.referenced_documents);
  };
  
  loadSession(sessionId);
}, [sessionId]);
```

---

## 🧪 테스트 방법

### 1. 새 대화 생성 및 저장 확인

```bash
# 1. RAG 기반 질문 입력
curl -X POST http://localhost:3000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "자동차 산업 기술 동향을 알려주세요",
    "session_id": "test_session_001",
    "use_rag": true
  }'

# 2. PostgreSQL에서 저장 확인
docker exec -it abkms-postgres psql -U wkms -d wkms -c "
  SELECT 
    session_id,
    jsonb_pretty(search_results) 
  FROM tb_chat_history 
  WHERE session_id = 'test_session_001' 
  ORDER BY created_date DESC 
  LIMIT 1;
"

# 기대 결과: detailed_chunks 배열 확인
```

### 2. 세션 복원 및 청크 정보 확인

```bash
# GET 요청
curl http://localhost:3000/api/v1/chat/sessions/test_session_001

# 응답에서 확인할 항목:
# - messages[*].detailed_chunks (청크 상세 정보)
# - messages[*].context_info.chunks_count (청크 개수)
# - referenced_documents (문서 메타데이터)
```

### 3. 로그 확인

```bash
# 백엔드 로그에서 확인
docker logs -f abkms-backend --tail 100 | grep -E "청크|chunk"

# 기대 출력:
# ✅ 청크 상세 정보 저장: 7개 청크, 1개 문서
# ✅ PostgreSQL 세션 및 메시지 저장 완료: test_session_001 (청크 7개)
# 📋 메시지 0에 7개 청크 정보 복원
```

---

## 📈 개선 효과

### Before (구현 전)
```
사용자: "특허 분석 방법 알려줘"
AI: "토픽 모델링을 활용할 수 있습니다..."

[복원 시]
- 답변 내용만 표시
- 어떤 문서를 참조했는지만 알 수 있음 (파일명)
- 몇 개의 청크를 사용했는지 알 수 없음
```

### After (구현 후)
```
사용자: "특허 분석 방법 알려줘"
AI: "토픽 모델링을 활용할 수 있습니다..."

[복원 시]
📚 1개 문서의 7개 청크 참조 [상세 보기]

[상세 보기 클릭 시]
#1. 토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf (p.1)
   "DOI: https://doi.org/10.36491/APJSB.46.1.3..."
   유사도: 53.3% | hybrid 검색

#2. 토픽 모델링을 활용한 국내 자동차 특허기반 기술개발 동향 분석.pdf (p.4)
   "1990년대 자동차 산업의 기술 특허는 주로..."
   유사도: 48.9% | hybrid 검색

... (5개 더)
```

---

## 🔧 추가 개선 가능 사항

### 1. 청크 하이라이팅
- content_preview를 사용자 질문 키워드로 하이라이트
- 프론트엔드에서 구현 가능

### 2. 청크 재검색
- "이 청크의 전후 문맥 보기" 기능
- `file_id + chunk_index`로 인접 청크 조회

### 3. 청크별 피드백
- "이 청크가 도움이 되었나요?" 버튼
- 피드백 데이터로 리랭킹 모델 개선

### 4. 레거시 데이터 처리
- 기존 대화는 `detailed_chunks` 없음
- 프론트엔드에서 graceful degradation 처리 필요
  ```typescript
  const hasDetailedChunks = message.detailed_chunks && message.detailed_chunks.length > 0;
  ```

---

## ✅ 체크리스트

- [x] 청크 상세 정보 저장 구현 (`generate_stream`)
- [x] 청크 정보 복원 구현 (`get_chat_session`)
- [x] 데이터 구조 설계 (JSONB에 저장)
- [x] 로깅 추가 (저장/복원 시 청크 개수)
- [x] 에러 핸들링 (JSON 파싱 실패 대응)
- [ ] 프론트엔드 UI 구현 (권장 사항)
- [ ] 레거시 데이터 호환성 테스트
- [ ] 대용량 청크 처리 (페이징/가상스크롤)

---

## 📝 마이그레이션 노트

**기존 데이터 영향**: 없음
- 새로 저장되는 메시지부터 `detailed_chunks` 포함
- 기존 메시지는 `detailed_chunks` 필드 없음 (호환 가능)
- 프론트엔드에서 옵셔널 체이닝으로 안전하게 처리

**롤백 방안**: 
- 코드만 이전 버전으로 롤백 가능
- 데이터베이스 스키마 변경 없음 (JSONB 유연성)

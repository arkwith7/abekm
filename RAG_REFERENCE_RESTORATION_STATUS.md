# RAG 채팅 참조 정보 보존/복원 현황 분석

## 📋 사용자 요구사항

첨부 화면 기준으로 다음 두 가지 정보가 **대화 복원 시에도 보존**되어야 함:

### 1. "참고자료 6개▶" 표시
- RAG 기반 답변 생성 시 실제로 사용된 청크/문서 정보
- 답변 옆에 접기/펼치기 가능한 참고자료 패널

### 2. "RAG 모드 활성화 - 선택된 문서 기반 답변" 표시
```
선택된 문서 (1개)  [전체 문서로 확대]
📄 (논문 2) Roadmapping integrates business and technology, Pieter Groenveld, Research Technology Management, November - December 2007.pdf
👁️  ×
```

---

## 🔍 현재 상태 분석

### ✅ **백엔드: 완벽하게 구현됨**

#### 1. 참고자료 (References) 저장 ✅
```python
# chat.py Line ~1884-1920
detailed_chunks = []
if references:
    for idx, ref in enumerate(references):
        chunk_info = {
            'index': idx + 1,
            'file_id': ref.get('file_bss_info_sno'),
            'file_name': ref.get('file_name', ''),
            'chunk_index': ref.get('chunk_index', 0),
            'page_number': ref.get('page_number'),
            'content_preview': ref.get('content', '')[:200],
            'similarity_score': ref.get('similarity_score', 0.0),
            'search_type': ref.get('search_type', 'unknown'),
            'section_title': ref.get('section_title', ''),
        }
        detailed_chunks.append(chunk_info)

enhanced_search_results = {
    **(context_info if context_info else {}),
    'detailed_chunks': detailed_chunks,  # 🆕 청크 상세 정보
    'chunks_count': len(detailed_chunks),
    'documents_count': len(union_doc_ids)
}
```

**저장 위치**: `tb_chat_history.search_results` (JSONB)

#### 2. 선택된 문서 저장 ✅
```python
# chat.py Line ~1914
await save_chat_session(
    db=db,
    session_id=session_id,
    user_emp_no=user_emp_no,
    message=message,
    response=final_to_store,
    referenced_documents=union_doc_ids,
    search_results=enhanced_search_results,
    conversation_context=selected_docs_context  # 🆕 선택 문서 보존
)
```

**저장 위치**: `tb_chat_history.conversation_context` (JSONB)

#### 3. 복원 API ✅
```python
# chat.py Line ~665-685
if row.search_results:
    search_data = json.loads(row.search_results)
    assistant_msg['context_info'] = search_data
    
    # 🆕 청크 상세 정보 추출 및 포함
    if isinstance(search_data, dict) and 'detailed_chunks' in search_data:
        assistant_msg['detailed_chunks'] = search_data['detailed_chunks']

# Line ~687-693
if i == 0 and row.conversation_context:
    ctx = json.loads(row.conversation_context)
    if isinstance(ctx, dict) and 'selected_documents' in ctx:
        selected_documents = ctx.get('selected_documents', [])
```

**반환 데이터**:
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "...",
      "context_info": {
        "chunks_count": 6,
        "documents_count": 2
      },
      "detailed_chunks": [
        {
          "index": 1,
          "file_name": "Roadmapping integrates business.pdf",
          "page_number": 3,
          "similarity_score": 0.82
        }
        // ... 5개 더
      ]
    }
  ],
  "selected_documents": [
    {
      "id": "123",
      "fileName": "Roadmapping integrates business.pdf",
      "fileType": "pdf"
    }
  ]
}
```

---

### ❌ **프론트엔드: 구현 누락**

#### 1. 참고자료 패널 표시 ❌

**현재 상태**:
```tsx
// MessageBubble.tsx Line ~18-19
const hasReferences = message.references && message.references.length > 0;
```
- `message.references` 필드를 체크하지만, **백엔드는 `detailed_chunks`로 전달**
- 결과: `hasReferences`가 항상 `false`

**필요한 수정**:
```tsx
const hasReferences = (
  (message.references && message.references.length > 0) ||
  (message.detailed_chunks && message.detailed_chunks.length > 0) ||
  (message.context_info?.chunks_count && message.context_info.chunks_count > 0)
);
```

#### 2. 참고자료 개수 표시 ❌

**현재 코드**:
```tsx
// MessageBubble.tsx에 "참고자료 6개▶" 표시 로직 없음
```

**필요한 추가**:
```tsx
{!isUser && hasReferences && (
  <button
    onClick={() => setShowReferences(!showReferences)}
    className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
  >
    📚 참고자료 {message.context_info?.chunks_count || message.detailed_chunks?.length || 0}개
    {showReferences ? '▼' : '▶'}
  </button>
)}
```

#### 3. ReferencePanel 컴포넌트 연동 ❌

**현재 상태**:
```tsx
// MessageBubble.tsx Line ~11
import ReferencePanel from './ReferencePanel';

// 하지만 실제 사용 코드 없음
```

**필요한 추가**:
```tsx
{showReferences && hasReferences && (
  <ReferencePanel
    references={message.detailed_chunks || message.references || []}
    contextInfo={message.context_info}
    onOpenDocument={onOpenDocument}
  />
)}
```

#### 4. 선택된 문서 복원 UI ❌

**현재 상태**:
```tsx
// ChatPage.tsx Line ~240-270
useEffect(() => {
  const handleRestoreSelectedDocuments = (event: CustomEvent) => {
    const { documents } = event.detail;
    const restoredDocs: GlobalDocument[] = documents.map(...);
    setSelectedDocuments(restoredDocs);
  };
  
  window.addEventListener('restoreSelectedDocuments', handleRestoreSelectedDocuments);
}, []);
```

**문제점**:
- 이벤트 리스너는 있지만, **이벤트를 발생시키는 코드가 없음**
- 세션 로드 시 `selected_documents`를 받아도 UI에 반영 안 됨

**필요한 수정**:
```tsx
// 세션 로드 함수에서
const loadSession = async (sessionId: string) => {
  const response = await fetch(`/api/v1/chat/sessions/${sessionId}`);
  const data = await response.json();
  
  setMessages(data.messages);
  
  // 🆕 선택된 문서 복원
  if (data.selected_documents && data.selected_documents.length > 0) {
    const restoredDocs = data.selected_documents.map(doc => ({
      fileId: doc.id || doc.fileId,
      fileName: doc.fileName,
      fileType: doc.fileType || 'pdf',
      // ... 나머지 필드
      isSelected: true
    }));
    setSelectedDocuments(restoredDocs);
    
    // RAG 패널도 자동 열기
    setRagOpen(true);
  }
};
```

#### 5. "RAG 모드 활성화" 패널 복원 시 표시 ❌

**현재 상태**:
```tsx
// ChatPage.tsx Line ~604-610
{workContext.ragMode && (
  <div className="px-4 py-2 bg-green-50">
    <span>RAG 모드 활성화 - {selectedDocuments.length > 0 ? '선택된 문서 기반 답변' : '전체 문서 검색 모드'}</span>
  </div>
)}
```

**문제점**:
- `selectedDocuments`가 복원되어도 패널이 접혀있으면 사용자가 인지 불가
- 복원 시 자동으로 펼쳐져야 함

**필요한 수정**:
```tsx
// 세션 복원 시
if (data.selected_documents && data.selected_documents.length > 0) {
  setSelectedDocuments(restoredDocs);
  setRagOpen(true);  // 🆕 자동 펼치기
  setDocumentsAddedToChat(true);  // 중복 안내 방지
}
```

---

## 📊 데이터 흐름 비교

### 새 대화 생성 시 (정상 작동)
```
1. 검색 페이지에서 문서 선택
2. ChatPage.tsx: selectedDocuments 상태 설정
3. RAG 패널 자동 표시 (ragOpen=true)
4. 채팅 전송 시 selected_documents 포함
5. 백엔드: conversation_context에 저장
6. 응답 생성 시 references 사용
7. 백엔드: detailed_chunks로 저장
8. 프론트: "참고자료 6개▶" 표시 (현재 누락)
```

### 대화 복원 시 (현재 문제)
```
1. 채팅 히스토리에서 세션 클릭
2. GET /api/v1/chat/sessions/{session_id}
3. 백엔드: selected_documents, detailed_chunks 반환 ✅
4. 프론트: 데이터 수신 ✅
5. ❌ selectedDocuments 상태 미설정
6. ❌ RAG 패널 표시 안 됨
7. ❌ "참고자료 6개▶" 표시 안 됨
```

---

## 🔧 필요한 수정 사항 요약

### Priority 1: 참고자료 표시 (즉시 수정 필요)

#### 1.1 MessageBubble.tsx
```tsx
// Line ~18-19 수정
const hasReferences = (
  (message.references && message.references.length > 0) ||
  (message.detailed_chunks && message.detailed_chunks.length > 0) ||
  (message.context_info?.chunks_count && message.context_info.chunks_count > 0)
);

// 참고자료 버튼 추가 (AI 메시지 내용 아래)
{!isUser && hasReferences && (
  <div className="mt-2 pt-2 border-t border-gray-100">
    <button
      onClick={() => setShowReferences(!showReferences)}
      className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
    >
      📚 참고자료 {message.context_info?.chunks_count || message.detailed_chunks?.length || 0}개
      {showReferences ? '▼' : '▶'}
    </button>
  </div>
)}

// ReferencePanel 표시
{showReferences && hasReferences && (
  <div className="mt-2">
    <ReferencePanel
      references={message.detailed_chunks || message.references || []}
      contextInfo={message.context_info}
      onOpenDocument={onOpenDocument}
    />
  </div>
)}
```

#### 1.2 ReferencePanel.tsx 확인
- `detailed_chunks` 데이터 구조 호환 확인
- 없으면 신규 구현 필요

### Priority 2: 선택된 문서 복원 (중요)

#### 2.1 ChatPage.tsx - loadSession 수정
```tsx
const loadSession = async (sessionId: string) => {
  const response = await fetch(`/api/v1/chat/sessions/${sessionId}`);
  const data = await response.json();
  
  if (data.success) {
    setMessages(data.messages);
    
    // 🆕 선택된 문서 복원
    if (data.selected_documents && data.selected_documents.length > 0) {
      console.log('📄 복원: 선택된 문서', data.selected_documents.length, '개');
      
      const restoredDocs: GlobalDocument[] = data.selected_documents.map(doc => ({
        fileId: doc.id || doc.fileId,
        fileName: doc.fileName,
        fileType: doc.fileType || 'pdf',
        fileSize: 0,
        uploadDate: doc.uploadDate || new Date().toISOString(),
        containerName: doc.containerName || '',
        containerId: doc.containerId || '',
        content: '',
        keywords: [],
        isSelected: true
      }));
      
      setSelectedDocuments(restoredDocs);
      setRagOpen(true);  // 패널 자동 펼치기
      setDocumentsAddedToChat(true);  // 중복 안내 방지
      
      console.log('✅ RAG 패널 복원 완료');
    }
  }
};
```

#### 2.2 타입 정의 확인
```tsx
// chat.types.ts
interface ChatMessage {
  // ... 기존 필드
  detailed_chunks?: Array<{
    index: number;
    file_id: number;
    file_name: string;
    chunk_index: number;
    page_number?: number;
    content_preview: string;
    similarity_score: number;
    search_type: string;
    section_title: string;
  }>;
  context_info?: {
    chunks_count?: number;
    documents_count?: number;
    rag_used?: boolean;
    // ... 기타
  };
}
```

---

## ✅ 검증 체크리스트

### 신규 대화
- [ ] 문서 선택 후 채팅 시작
- [ ] RAG 패널에 선택된 문서 표시 ✅
- [ ] 답변에 "참고자료 6개▶" 버튼 표시 (수정 필요)
- [ ] 버튼 클릭 시 청크 상세 정보 표시 (수정 필요)

### 대화 복원
- [ ] 채팅 히스토리에서 이전 대화 선택
- [ ] RAG 패널에 원래 선택했던 문서 복원 (수정 필요)
- [ ] 각 답변에 "참고자료 6개▶" 버튼 표시 (수정 필요)
- [ ] 버튼 클릭 시 저장된 청크 정보 표시 (수정 필요)

---

## 🚀 구현 순서 제안

1. **MessageBubble.tsx 수정** (30분)
   - `hasReferences` 로직 수정
   - "참고자료 N개▶" 버튼 추가
   - ReferencePanel 연동

2. **ReferencePanel.tsx 확인/수정** (30분)
   - `detailed_chunks` 데이터 구조 호환성 확인
   - 필요시 컴포넌트 수정

3. **ChatPage.tsx 수정** (20분)
   - `loadSession` 함수에 문서 복원 로직 추가
   - `setRagOpen(true)` 자동 펼치기

4. **테스트** (20분)
   - 신규 대화 → 참고자료 표시 확인
   - 대화 복원 → RAG 패널 + 참고자료 확인

**총 소요 시간**: 약 1.5-2시간

---

## 📝 참고: ReferencePanel 예상 인터페이스

```tsx
interface ReferencePanelProps {
  references: Array<{
    index: number;
    file_name: string;
    page_number?: number;
    content_preview: string;
    similarity_score: number;
    search_type: string;
  }>;
  contextInfo?: {
    chunks_count?: number;
    documents_count?: number;
  };
  onOpenDocument?: (doc: any) => void;
}

const ReferencePanel: React.FC<ReferencePanelProps> = ({
  references,
  contextInfo,
  onOpenDocument
}) => {
  return (
    <div className="bg-gray-50 rounded-lg p-3 space-y-2">
      <div className="text-sm font-medium text-gray-700">
        📚 참고자료 ({contextInfo?.chunks_count || references.length}개 청크, {contextInfo?.documents_count || 0}개 문서)
      </div>
      
      {references.map((ref, idx) => (
        <div key={idx} className="bg-white p-2 rounded border border-gray-200">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-gray-600">#{ref.index}</span>
            <span className="text-xs text-gray-500">{ref.search_type}</span>
          </div>
          <div className="text-sm font-medium text-gray-800 truncate">
            {ref.file_name} {ref.page_number && `(p.${ref.page_number})`}
          </div>
          <div className="text-xs text-gray-600 mt-1 line-clamp-2">
            {ref.content_preview}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            유사도: {(ref.similarity_score * 100).toFixed(1)}%
          </div>
        </div>
      ))}
    </div>
  );
};
```

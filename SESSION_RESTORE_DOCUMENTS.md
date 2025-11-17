# 대화 복원 시 선택 문서 및 참고자료 복원 기능 구현

## 📋 요구사항

대화 복원 시 다음 정보를 함께 복원:
1. **최초 대화 때 사용한 선택된 문서 목록** (Selected Documents)
2. **대화 중 참고한 자료 목록** (Referenced Documents)

## 🔍 기술적 검토 결과

### ✅ 복원 가능 여부

**결론: 둘 다 복원 가능합니다!**

#### 1. 선택된 문서 목록 (Selected Documents)
- **저장 위치**: Redis `RedisChatMessage.search_context['selected_documents']`
- **저장 시점**: 사용자가 첫 메시지 전송 시
- **복원 방법**: 세션의 첫 번째 사용자 메시지의 `search_context`에서 추출

#### 2. 참고자료 목록 (Referenced Documents)
- **저장 위치**: 
  - Redis: `RedisChatMessage.referenced_documents` (메시지별)
  - PostgreSQL: `tb_chat_history.referenced_documents` (영구 저장)
- **저장 시점**: AI 응답 생성 후 자동 저장
- **복원 방법**: 
  - 각 메시지의 `referenced_documents` 필드에서 수집
  - DB에서 문서 상세 정보 조회

## 🛠️ 구현된 기능

### 1. 백엔드 수정 (backend/app/api/v1/chat.py)

#### 1.1 사용자 메시지 저장 시 선택 문서 포함
```python
# 선택된 문서 정보를 컨텍스트로 준비
selected_docs_context = None
if selected_documents and len(selected_documents) > 0:
    selected_docs_context = {
        'selected_documents': [
            {
                'id': doc.id,
                'fileName': doc.fileName,
                'fileType': doc.fileType,
            }
            for doc in selected_documents
        ]
    }

# 사용자 메시지 저장 (선택된 문서 포함)
await chat_manager.add_message(
    session_id=session_id,
    content=message,
    message_type=MessageType.USER,
    user_emp_no=user_emp_no,
    user_name=user_name,
    search_context=selected_docs_context  # ✅ 선택 문서 저장
)
```

#### 1.2 세션 로드 시 선택 문서 및 참고자료 반환
```python
@router.get("/chat/sessions/{session_id}")
async def get_chat_session(...):
    """
    세션의 대화 내역 조회
    - 메시지 목록
    - 참고자료 목록 (referenced_documents)
    - 선택된 문서 목록 (첫 메시지의 컨텍스트에서 추출)
    """
    # 전체 참고자료 ID 수집
    all_referenced_doc_ids = set()
    
    # 선택된 문서 목록 추출
    selected_documents = []
    
    for idx, m in enumerate(messages):
        # 참고자료 수집
        if hasattr(m, 'referenced_documents') and m.referenced_documents:
            all_referenced_doc_ids.update(m.referenced_documents)
        
        # 첫 번째 사용자 메시지에서 선택된 문서 추출
        if idx == 0 and role == 'user' and hasattr(m, 'search_context'):
            if 'selected_documents' in m.search_context:
                selected_documents = m.search_context.get('selected_documents', [])
    
    # 참고자료 상세 정보 조회 (DB)
    referenced_docs_detail = []
    if all_referenced_doc_ids:
        query = select(TbFileBssInfo).where(
            TbFileBssInfo.file_bss_info_sno.in_(list(all_referenced_doc_ids))
        )
        result = await db.execute(query)
        docs = result.scalars().all()
        
        for doc in docs:
            referenced_docs_detail.append({
                'fileId': str(doc.file_bss_info_sno),
                'fileName': doc.file_logic_name,
                'fileType': doc.file_extsn,
                'containerName': doc.container_path or '',
                'uploadDate': doc.created_date.isoformat()
            })
    
    return {
        'success': True,
        'session_id': session_id,
        'messages': frontend_msgs,
        'referenced_documents': referenced_docs_detail,  # ✅ 참고자료
        'selected_documents': selected_documents  # ✅ 선택 문서
    }
```

### 2. 프론트엔드 수정

#### 2.1 useChat.ts - 세션 로드 시 이벤트 발송
```typescript
if (data.selected_documents && data.selected_documents.length > 0) {
    console.log('📄 선택된 문서 복원:', data.selected_documents.length, '개');
    
    // 글로벌 상태 복원을 위한 이벤트 발송
    window.dispatchEvent(new CustomEvent('restoreSelectedDocuments', {
        detail: { documents: data.selected_documents }
    }));
}

if (data.referenced_documents && data.referenced_documents.length > 0) {
    console.log('📚 참고자료 복원:', data.referenced_documents.length, '개');
    
    window.dispatchEvent(new CustomEvent('restoreReferencedDocuments', {
        detail: { documents: data.referenced_documents }
    }));
}
```

#### 2.2 ChatPage.tsx - 이벤트 수신 및 상태 복원
```typescript
useEffect(() => {
    const handleRestoreSelectedDocuments = (event: CustomEvent) => {
        const { documents } = event.detail;
        console.log('📄 세션 복원: 선택된 문서 복원', documents.length, '개');
        
        // GlobalDocument 형식으로 변환
        const restoredDocs: GlobalDocument[] = documents.map((doc: any) => ({
            fileId: doc.id || doc.fileId,
            fileName: doc.fileName || doc.file_name || '알 수 없음',
            fileType: doc.fileType || doc.file_type || '',
            // ... 기타 필드
            isSelected: true
        }));
        
        setSelectedDocuments(restoredDocs);  // ✅ 글로벌 상태 복원
        setDocumentsAddedToChat(true);  // 복원 시 안내 메시지 생략
    };

    const handleRestoreReferencedDocuments = (event: CustomEvent) => {
        const { documents } = event.detail;
        console.log('📚 세션 복원: 참고자료', documents.length, '개');
        // 참고자료는 각 메시지의 context_info에 포함되므로 별도 처리 불필요
    };

    window.addEventListener('restoreSelectedDocuments', handleRestoreSelectedDocuments);
    window.addEventListener('restoreReferencedDocuments', handleRestoreReferencedDocuments);

    return () => {
        window.removeEventListener('restoreSelectedDocuments', handleRestoreSelectedDocuments);
        window.removeEventListener('restoreReferencedDocuments', handleRestoreReferencedDocuments);
    };
}, [setSelectedDocuments]);
```

## 📊 데이터 흐름

### 저장 흐름
```
1. 사용자가 문서 선택 후 첫 메시지 전송
   ↓
2. 선택 문서 → search_context에 저장 (Redis)
   ↓
3. RAG 검색 후 AI 응답 생성
   ↓
4. 참고자료 ID → referenced_documents에 저장 (Redis & PostgreSQL)
```

### 복원 흐름
```
1. 세션 ID로 대화 로드 요청
   ↓
2. Redis에서 메시지 조회
   ↓
3. 첫 메시지 search_context → 선택 문서 추출
   ↓
4. 모든 메시지 referenced_documents → 참고자료 ID 수집
   ↓
5. DB에서 참고자료 상세 정보 조회
   ↓
6. 프론트엔드에 반환
   ↓
7. 프론트엔드에서 글로벌 상태 복원
```

## 🎯 복원되는 정보

### 1. 선택된 문서 (Selected Documents)
- **위치**: 우측 사이드바 "선택된 문서" 패널
- **내용**:
  - 파일 ID
  - 파일명
  - 파일 타입
  - 컨테이너명
  - 업로드 날짜

### 2. 참고자료 (Referenced Documents)
- **위치**: 각 AI 응답 메시지 하단
- **내용**:
  - 파일 ID
  - 파일명
  - 파일 타입
  - 컨테이너 경로
  - 관련도 점수 (있는 경우)

### 3. 메시지별 컨텍스트 정보
- **위치**: 각 메시지의 `context_info`
- **내용**:
  - 검색 모드
  - 사용된 청크 수
  - 토큰 수
  - 재랭킹 적용 여부
  - 참고자료 목록

## 🧪 테스트 시나리오

### 시나리오 1: 문서 선택 후 새 대화
1. 검색 페이지에서 문서 2개 선택
2. "AI 채팅으로 이동" 클릭
3. 첫 메시지 전송
4. **검증**: Redis에 `search_context.selected_documents` 저장 확인

### 시나리오 2: 대화 진행 및 참고자료 확인
1. AI 응답 수신
2. **검증**: AI 응답 하단에 참고자료 표시
3. **검증**: Redis/DB에 `referenced_documents` 저장 확인

### 시나리오 3: 세션 복원
1. 대시보드에서 이전 대화 클릭
2. **검증**: 
   - ✅ 대화 내역 표시
   - ✅ 우측 사이드바에 선택된 문서 2개 표시
   - ✅ 각 AI 응답에 참고자료 표시
3. 브라우저 콘솔 로그 확인:
```
📦 세션 데이터 수신: {
  sessionId: "chat_xxx",
  success: true,
  messageCount: 10,
  referencedDocumentsCount: 5,
  selectedDocumentsCount: 2
}
📄 선택된 문서 복원: 2 개
📚 참고자료 복원: 5 개
```

### 시나리오 4: 복원 후 대화 계속
1. 세션 복원 완료
2. 새 메시지 전송
3. **검증**: 선택된 문서가 유지된 상태로 RAG 검색 수행

## 📝 로그 확인 방법

### 백엔드 로그
```bash
# 선택 문서 저장 확인
grep "선택된 문서 정보를 컨텍스트로 준비" logs/app.log

# 참고자료 저장 확인
grep "참고자료 저장:" logs/app.log

# 세션 로드 시 복원 확인
grep "선택된 문서 복원\|참고자료 복원" logs/app.log
```

### 프론트엔드 콘솔
```javascript
// 세션 로드 시
📦 세션 데이터 수신: {...}
📄 선택된 문서 복원: N 개
📚 참고자료 복원: M 개

// 상태 복원 시
📄 세션 복원: 선택된 문서 복원 N 개
```

## 🎉 기대 효과

### 1. 사용자 경험 향상
- ✅ 이전 대화 맥락 완전 복원
- ✅ 어떤 문서를 기반으로 대화했는지 명확히 확인
- ✅ 참고자료 즉시 접근 가능

### 2. 대화 연속성 보장
- ✅ 중단된 대화를 정확히 이어갈 수 있음
- ✅ 같은 문서 기반으로 계속 대화 가능
- ✅ 컨텍스트 유지로 더 정확한 AI 응답

### 3. 감사 추적 (Audit Trail)
- ✅ 어떤 문서를 사용했는지 기록
- ✅ AI가 어떤 자료를 참고했는지 추적
- ✅ 답변의 신뢰성 검증 가능

## ⚠️ 주의사항

### 1. 선택 문서 저장 조건
- 첫 메시지 전송 시에만 `search_context`에 저장됨
- 대화 중간에 문서를 추가 선택한 경우는 별도 처리 필요

### 2. 참고자료 중복 제거
- 같은 문서를 여러 응답에서 참고할 수 있음
- 백엔드에서 `set()`으로 중복 제거 처리됨

### 3. 삭제된 문서 처리
- 참고자료로 사용된 문서가 삭제된 경우
- DB 조회 시 해당 문서는 목록에서 제외됨
- 프론트엔드에서 "문서를 찾을 수 없음" 표시 권장

## 🔄 향후 개선 방향

### 1. 대화 중 문서 추가 선택 지원
현재는 첫 메시지에만 저장되므로, 대화 중간에 추가된 문서도 추적

### 2. 참고자료 시각화 개선
- 참고자료 패널 추가
- 전체 대화에서 참고한 문서 한눈에 보기
- 문서별 참고 횟수 표시

### 3. 문서별 기여도 분석
- 각 문서가 답변에 얼마나 기여했는지 분석
- 가장 유용한 문서 하이라이트

---
**작성일**: 2025-11-07
**버전**: v1.0
**상태**: ✅ 구현 완료

# 채팅 세션 로드 실패 원인 분석

## 🔴 문제 상황

**증상**:
- 대시보드 "최근 AI 대화"에서 세션 클릭 시
- 채팅창으로 이동하지만 **대화 내용이 전혀 표시되지 않음**
- 세션 정보: `chat_1762322972575_stm4lp5mk`
  - 제목: "What is a Roadmapping integrates business and tech..."
  - 메시지 수: 6개
  - 문서 수: 0개

## 🔍 원인 분석

### 1. 데이터베이스 조사 결과

#### ✅ `tb_chat_sessions` - 세션 메타데이터 존재
```sql
SELECT session_id, session_name, message_count, created_date 
FROM tb_chat_sessions 
WHERE session_id = 'chat_1762322972575_stm4lp5mk';

-- 결과:
session_id: chat_1762322972575_stm4lp5mk
session_name: What is a Roadmapping integrates business and tech...
message_count: 6          ← 6개 메시지가 있다고 표시
created_date: 2025-11-05 07:20:05
```

#### ❌ `tb_chat_history` - 실제 메시지 없음
```sql
SELECT chat_id, user_message, assistant_response 
FROM tb_chat_history 
WHERE session_id = 'chat_1762322972575_stm4lp5mk';

-- 결과: (0개 행)  ← 메시지가 전혀 없음!
```

#### ❌ Redis - 메시지 없음
```bash
redis-cli KEYS "chat:*1762322972575*"
# 결과: (empty array)  ← TTL 만료로 삭제됨
```

### 2. 코드 분석 결과

#### 문제의 함수: `save_chat_session()`
**위치**: `/home/admin/wkms-aws/backend/app/api/v1/chat.py:339`

```python
async def save_chat_session(
    db: AsyncSession, 
    session_id: str, 
    user_emp_no: str, 
    message: str,
    response: str
) -> bool:
    """채팅 세션을 tb_chat_sessions 테이블에 저장/업데이트"""
    
    # ✅ 세션 메타데이터 저장 - 정상
    if existing_session:
        # message_count 증가
        UPDATE tb_chat_sessions 
        SET message_count = message_count + 1
    else:
        # 새 세션 생성
        INSERT INTO tb_chat_sessions (...)
    
    # ❌ 실제 메시지 저장 누락!
    # 다음 코드가 없음:
    # INSERT INTO tb_chat_history (
    #     session_id, user_message, assistant_response, ...
    # )
```

### 3. 데이터 흐름 비교

#### 현재 상태 (문제 있음)
```
사용자 메시지 전송
    ↓
Redis에 메시지 저장 (임시)
    ↓
AI 응답 생성
    ↓
Redis에 응답 저장 (임시)
    ↓
save_chat_session() 호출
    ├─ tb_chat_sessions.message_count += 1  ✅ 실행됨
    └─ tb_chat_history에 메시지 저장     ❌ 누락!
    ↓
시간 경과 (2일)
    ↓
Redis TTL 만료 (메시지 삭제)
    ↓
세션 로드 시도
    ├─ tb_chat_sessions 조회  ✅ 세션 정보 있음
    ├─ tb_chat_history 조회   ❌ 메시지 0개
    └─ Redis 조회             ❌ 메시지 없음 (TTL 만료)
    ↓
결과: 빈 채팅창
```

#### 올바른 동작 (수정 필요)
```
사용자 메시지 전송
    ↓
Redis에 메시지 저장 (임시)
    ↓
AI 응답 생성
    ↓
Redis에 응답 저장 (임시)
    ↓
save_chat_session() 호출
    ├─ tb_chat_sessions.message_count += 1  ✅
    └─ tb_chat_history에 메시지 저장      ✅ 추가 필요!
    ↓
PostgreSQL에 영구 저장
    ↓
시간 경과 (Redis TTL 만료되어도 무방)
    ↓
세션 로드 시도
    ├─ tb_chat_sessions 조회  ✅ 세션 정보 있음
    ├─ tb_chat_history 조회   ✅ 6개 메시지 있음
    └─ Redis 조회             (필요 없음)
    ↓
결과: 대화 내용 정상 표시
```

## 🔧 해결 방법

### 1. `save_chat_session()` 함수 수정

`tb_chat_history` 테이블에 메시지를 저장하는 로직 추가:

```python
async def save_chat_session(
    db: AsyncSession, 
    session_id: str, 
    user_emp_no: str, 
    message: str,
    response: str,
    referenced_documents: Optional[List[int]] = None,
    search_results: Optional[dict] = None,
    conversation_context: Optional[dict] = None
) -> bool:
    """채팅 세션을 tb_chat_sessions와 tb_chat_history에 저장/업데이트"""
    try:
        # 1. 세션 메타데이터 저장 (기존 로직)
        # ... 기존 코드 유지 ...
        
        # 2. 🆕 메시지 저장 (추가 필요!)
        insert_message_query = text("""
            INSERT INTO tb_chat_history (
                session_id,
                user_emp_no,
                user_message,
                assistant_response,
                referenced_documents,
                search_results,
                conversation_context,
                created_date
            ) VALUES (
                :session_id,
                :user_emp_no,
                :user_message,
                :assistant_response,
                :referenced_documents,
                :search_results,
                :conversation_context,
                NOW()
            )
        """)
        
        await db.execute(insert_message_query, {
            "session_id": session_id,
            "user_emp_no": user_emp_no,
            "user_message": message,
            "assistant_response": response,
            "referenced_documents": referenced_documents,
            "search_results": json.dumps(search_results) if search_results else None,
            "conversation_context": json.dumps(conversation_context) if conversation_context else None
        })
        
        await db.commit()
        logger.info(f"✅ 채팅 세션 및 메시지 저장 완료: {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 채팅 세션 저장 실패: {e}")
        await db.rollback()
        return False
```

### 2. `get_chat_session()` 함수 수정

Redis가 아닌 PostgreSQL에서 메시지를 우선 조회:

```python
@router.get("/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: str, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """세션의 대화 내역 조회 - PostgreSQL 우선"""
    try:
        # 1. 세션 존재 확인
        session_query = text("""
            SELECT * FROM tb_chat_sessions 
            WHERE session_id = :session_id AND user_emp_no = :user_emp_no
        """)
        session_result = await db.execute(session_query, {
            "session_id": session_id,
            "user_emp_no": str(current_user.emp_no)
        })
        session = session_result.fetchone()
        
        if not session:
            return {'success': False, 'session_id': session_id, 'messages': []}
        
        # 2. PostgreSQL에서 메시지 조회 (우선)
        messages_query = text("""
            SELECT 
                chat_id,
                user_message,
                assistant_response,
                referenced_documents,
                search_results,
                conversation_context,
                created_date
            FROM tb_chat_history
            WHERE session_id = :session_id
            ORDER BY created_date
        """)
        messages_result = await db.execute(messages_query, {
            "session_id": session_id
        })
        db_messages = messages_result.fetchall()
        
        # 3. 메시지 포맷 변환
        frontend_msgs = []
        all_referenced_doc_ids = set()
        selected_documents = []
        
        for i, row in enumerate(db_messages):
            # 사용자 메시지
            frontend_msgs.append({
                'id': f"user_{i}",
                'role': 'user',
                'content': row.user_message,
                'timestamp': row.created_date.isoformat()
            })
            
            # AI 응답
            assistant_msg = {
                'id': f"assistant_{i}",
                'role': 'assistant',
                'content': row.assistant_response,
                'timestamp': row.created_date.isoformat()
            }
            
            # 참고자료 포함
            if row.referenced_documents:
                assistant_msg['referenced_documents'] = row.referenced_documents
                all_referenced_doc_ids.update(row.referenced_documents)
            
            # 검색 결과/컨텍스트 포함
            if row.search_results:
                assistant_msg['context_info'] = json.loads(row.search_results)
            
            frontend_msgs.append(assistant_msg)
        
        # 4. 참고자료 상세 정보 조회
        referenced_docs_detail = []
        if all_referenced_doc_ids:
            # ... 기존 로직 유지 ...
        
        return {
            'success': True,
            'session_id': session_id,
            'messages': frontend_msgs,
            'referenced_documents': referenced_docs_detail,
            'selected_documents': selected_documents
        }
        
    except Exception as e:
        logger.error(f"세션 조회 실패: {e}")
        return {'success': False, 'session_id': session_id, 'messages': []}
```

## 📋 체크리스트

### 즉시 수정 필요
- [ ] `save_chat_session()` 함수에 `tb_chat_history` INSERT 로직 추가
- [ ] `get_chat_session()` 함수에서 PostgreSQL 우선 조회
- [ ] 호출하는 모든 위치에서 `referenced_documents` 등 파라미터 전달

### 테스트 시나리오
1. **새 대화 생성 및 저장 테스트**
   ```sql
   -- 메시지 전송 후 확인
   SELECT * FROM tb_chat_sessions WHERE session_id = '새_세션_ID';
   SELECT * FROM tb_chat_history WHERE session_id = '새_세션_ID';
   ```

2. **세션 로드 테스트**
   - 대시보드에서 세션 클릭
   - 메시지 정상 표시 확인

3. **TTL 만료 후 테스트**
   - Redis 메시지 삭제 후
   - PostgreSQL에서 정상 로드되는지 확인

## 🎯 영향 범위

### 영향받는 사용자
- ✅ **기존 세션**: 이미 메시지가 누락된 상태 (복구 불가)
- ✅ **새 세션**: 수정 후 정상 저장됨

### 데이터 손실
- ⚠️ 11월 5일 생성된 `chat_1762322972575_stm4lp5mk` 세션의 6개 메시지
- ⚠️ 기타 오래된 세션의 메시지들
- 📝 Redis TTL 만료 전 데이터는 복구 가능 (현재는 만료됨)

---
**분석일**: 2025-11-07
**심각도**: 🔴 Critical (데이터 손실 발생)
**상태**: ⚠️ 수정 필요
**우선순위**: Highest (즉시 수정)

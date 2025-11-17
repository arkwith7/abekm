# 채팅 세션 저장 수정 완료

## ✅ 수정 완료 사항

### 1. `save_chat_session()` 함수 수정 (Line 339)
**변경 내용**:
- 함수 시그니처에 추가 파라미터 추가:
  - `referenced_documents: Optional[List[int]]`
  - `search_results: Optional[dict]`
  - `conversation_context: Optional[dict]`
- `tb_chat_history` 테이블에 실제 메시지 저장 로직 추가
- JSONB 필드 직렬화 처리

**추가된 코드**:
```python
# 2. 🆕 실제 메시지 내용을 tb_chat_history에 저장
INSERT INTO tb_chat_history (
    session_id,
    user_emp_no,
    user_message,
    assistant_response,
    referenced_documents,
    search_results,
    conversation_context,
    created_date
)
```

### 2. `save_chat_session()` 호출 부분 수정 (Line 1706)
**변경 내용**:
- 참고자료와 검색 결과를 함께 전달:
```python
await save_chat_session(
    db=db,
    session_id=session_id,
    user_emp_no=user_emp_no,
    message=message,
    response=final_to_store,
    referenced_documents=referenced_doc_ids if referenced_doc_ids else None,
    search_results=context_info if context_info else None,
    conversation_context=None
)
```

### 3. `get_chat_session()` 함수 전면 수정 (Line 539)
**변경 내용**:
- PostgreSQL 우선 조회로 변경
- Redis는 폴백으로만 사용
- DB에서 메시지 조회 및 변환 로직 추가

**주요 로직**:
1. `tb_chat_sessions`에서 세션 존재 확인
2. `tb_chat_history`에서 메시지 조회 (PostgreSQL 우선)
3. 메시지가 없으면 Redis 폴백
4. 참고자료 상세 정보 조회
5. 프론트엔드 형식으로 변환하여 반환

## 🎯 기대 효과

### Before (수정 전)
```
사용자 메시지 → Redis 저장
                 ↓
AI 응답 생성 → Redis 저장
                 ↓
save_chat_session() → tb_chat_sessions.message_count++
                       ❌ tb_chat_history 저장 안 함
                 ↓
Redis TTL 만료 (2일)
                 ↓
세션 로드 → Redis 조회 → 메시지 없음
            → 빈 화면 표시
```

### After (수정 후)
```
사용자 메시지 → Redis 저장
                 ↓
AI 응답 생성 → Redis 저장
                 ↓
save_chat_session() → tb_chat_sessions.message_count++
                       ✅ tb_chat_history에 메시지 저장
                       ✅ referenced_documents 저장
                       ✅ search_results 저장
                 ↓
Redis TTL 만료 (무관)
                 ↓
세션 로드 → PostgreSQL 조회 → 메시지 있음
            → 대화 내용 정상 표시
```

## 📋 테스트 시나리오

### 1. 새 대화 생성 및 저장 확인
```sql
-- 1. 새 대화 시작 (프론트엔드에서)
-- 2. PostgreSQL 확인
SELECT * FROM tb_chat_sessions WHERE session_id = '새_세션_ID';
SELECT * FROM tb_chat_history WHERE session_id = '새_세션_ID';

-- 기대 결과:
-- tb_chat_sessions: 1개 행 (세션 메타데이터)
-- tb_chat_history: N개 행 (실제 메시지들)
```

### 2. 세션 로드 테스트
```bash
# 1. 대시보드에서 세션 클릭
# 2. 채팅창에 메시지 표시되는지 확인
# 3. 백엔드 로그 확인
grep "PostgreSQL에서.*개 메시지 조회" logs/app.log
```

### 3. 참고자료 복원 테스트
```bash
# 1. 문서 선택 후 대화 생성
# 2. 세션 재로드
# 3. 참고자료가 메시지와 함께 표시되는지 확인
```

## ⚠️ 주의사항

### 기존 세션 데이터
- **이미 손실된 데이터는 복구 불가**
- 수정 이전에 생성된 세션들:
  - `tb_chat_sessions`에는 메타데이터만 존재
  - `tb_chat_history`는 비어있음
  - Redis도 TTL 만료로 메시지 없음

### 영향받는 세션
```sql
-- 메시지 없는 세션 확인
SELECT s.session_id, s.session_name, s.message_count, 
       (SELECT COUNT(*) FROM tb_chat_history h WHERE h.session_id = s.session_id) as actual_messages
FROM tb_chat_sessions s
WHERE s.message_count > 0
HAVING actual_messages = 0;
```

## 🚀 다음 단계

### 즉시 테스트
1. 서버 재시작 (hot reload 확인)
2. 새 대화 생성
3. DB 확인
4. 세션 로드 테스트

### 모니터링
```bash
# 저장 성공 로그
tail -f logs/app.log | grep "PostgreSQL 세션 및 메시지 저장 완료"

# 조회 성공 로그
tail -f logs/app.log | grep "PostgreSQL에서.*개 메시지 조회"

# 오류 로그
tail -f logs/app.log | grep "PostgreSQL 세션 저장 실패"
```

### 데이터 정합성 확인
```sql
-- 세션 카운트와 실제 메시지 수 비교
SELECT 
    s.session_id,
    s.session_name,
    s.message_count as declared_count,
    COUNT(h.chat_id) as actual_count,
    CASE 
        WHEN s.message_count = COUNT(h.chat_id) THEN '✅ 일치'
        ELSE '❌ 불일치'
    END as status
FROM tb_chat_sessions s
LEFT JOIN tb_chat_history h ON s.session_id = h.session_id
GROUP BY s.session_id, s.session_name, s.message_count
ORDER BY s.created_date DESC
LIMIT 10;
```

---
**수정일**: 2025-11-07
**심각도**: 🔴 Critical → ✅ 해결
**상태**: ✅ 수정 완료
**파일**: `/home/admin/wkms-aws/backend/app/api/v1/chat.py`

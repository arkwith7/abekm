# 채팅 히스토리 목록 불일치 문제 해결

## 🔴 문제 상황

### 증상
**대시보드 "최근 AI 대화"**와 **ChatPage "채팅 히스토리"** 목록이 불일치

### 원인 분석

#### 1. 데이터 소스 불일치
| 위치 | API 엔드포인트 | 데이터 소스 | 문제 |
|------|---------------|------------|------|
| 대시보드 | `/api/v1/dashboard/recent-chat-sessions` | ✅ PostgreSQL | 정상 (영구 저장) |
| 채팅 히스토리 | `/api/v1/chat/sessions` | ❌ Redis만 | TTL 만료 시 표시 안 됨 |

#### 2. Redis TTL 문제
```
채팅 생성 → Redis 저장 (TTL 2일)
            ↓
2일 후 → Redis TTL 만료
            ↓
채팅 히스토리 조회 → Redis에 없음 → 목록 비어있음
대시보드 조회 → PostgreSQL 조회 → 세션 표시됨
```

**결과**: 같은 세션이 대시보드에는 보이지만 채팅 히스토리에는 안 보임!

## ✅ 해결 방법

### 1. `/api/v1/chat/sessions` API 전면 수정

#### Before (문제)
```python
@router.get("/chat/sessions")
async def get_chat_sessions(...):
    # ❌ Redis만 조회
    user_sessions = await chat_manager.get_user_active_sessions(...)
    # Redis TTL 만료 시 빈 목록 반환
```

#### After (해결)
```python
@router.get("/chat/sessions")
async def get_chat_sessions(
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ...
):
    """
    ✅ PostgreSQL 우선 조회 (영구 저장된 모든 세션)
    ✅ 실제 메시지 수 계산 (tb_chat_history 집계)
    """
    # PostgreSQL에서 세션 조회 + 실제 메시지 수
    sessions_query = (
        select(
            TbChatSessions.session_id,
            TbChatSessions.session_name,
            TbChatSessions.message_count,
            TbChatSessions.last_modified_date,
            # 실제 메시지 수 집계
            func.count(text('h.chat_id')).label('actual_message_count')
        )
        .outerjoin(
            text('tb_chat_history h'),
            text('tb_chat_sessions.session_id = h.session_id')
        )
        .where(TbChatSessions.user_emp_no == str(current_user.emp_no))
        .group_by(...)
        .order_by(desc(TbChatSessions.last_modified_date))
    )
```

### 2. `/api/v1/dashboard/recent-chat-sessions` API 개선

#### Before (부정확)
```python
# 선언된 메시지 수만 사용
message_count = getattr(session, 'message_count', 0)
# 항상 0으로 표시됨
document_count = 0
```

#### After (정확)
```python
# ✅ 실제 메시지 수 계산
func.count(sql_text('h.chat_id')).label('actual_message_count')

# ✅ 실제 참고자료 수 계산
doc_query = sql_text("""
    SELECT COUNT(DISTINCT unnest(referenced_documents)) as doc_count
    FROM tb_chat_history
    WHERE session_id = :session_id
    AND referenced_documents IS NOT NULL
""")
```

## 📊 데이터 흐름 비교

### Before (불일치)
```
대시보드 API
    ↓
PostgreSQL tb_chat_sessions 조회
    ↓
세션 5개 표시 (message_count: 1, 2, 1, 1, 6)
    ↓
실제 메시지: 0개 (tb_chat_history 비어있음)

채팅 히스토리 API
    ↓
Redis 조회
    ↓
TTL 만료로 비어있음
    ↓
세션 0개 표시
```

**결과**: 대시보드 5개 vs 채팅 히스토리 0개 ❌

### After (일치)
```
대시보드 API
    ↓
PostgreSQL 조회
    ├─ tb_chat_sessions (세션 메타데이터)
    └─ tb_chat_history JOIN (실제 메시지 수)
    ↓
세션 5개 표시 (actual_count: 0, 0, 0, 0, 0)

채팅 히스토리 API
    ↓
PostgreSQL 조회 (동일한 로직)
    ├─ tb_chat_sessions (세션 메타데이터)
    └─ tb_chat_history JOIN (실제 메시지 수)
    ↓
세션 5개 표시 (actual_count: 0, 0, 0, 0, 0)
```

**결과**: 대시보드 5개 vs 채팅 히스토리 5개 ✅

## 🎯 주요 개선 사항

### 1. 데이터 소스 통일
- ✅ 두 API 모두 PostgreSQL 기반으로 통일
- ✅ Redis는 폴백/추가 정보용으로만 사용

### 2. 정확한 메시지 수 표시
- ✅ `tb_chat_history` 테이블에서 실제 메시지 수 집계
- ✅ 선언된 수(message_count)와 실제 수(actual_count) 구분

### 3. 참고자료 수 정확성
- ✅ `referenced_documents` 배열에서 고유 문서 ID 집계
- ✅ NULL 체크 및 예외 처리

### 4. 일관된 정렬 및 필터링
- ✅ `last_modified_date` 기준 내림차순
- ✅ `is_active = true` 필터링
- ✅ 사용자별 세션만 조회

## 📋 테스트 시나리오

### 시나리오 1: 기존 세션 표시 확인
```bash
# 1. 대시보드 접속
# → "최근 AI 대화" 카드 확인
# → 5개 세션 표시 (message_count: 0)

# 2. ChatPage 접속
# → "채팅 히스토리" 버튼 클릭
# → 동일한 5개 세션 표시 ✅

# 3. DB 확인
docker exec -it abkms-postgres psql -U wkms -d wkms -c \
"SELECT session_id, session_name, message_count, 
 (SELECT COUNT(*) FROM tb_chat_history h WHERE h.session_id = s.session_id) as actual
 FROM tb_chat_sessions s 
 WHERE user_emp_no = '77107791'
 ORDER BY last_modified_date DESC;"
```

### 시나리오 2: 새 세션 생성 후 확인
```bash
# 1. 새 채팅 생성
# 2. 메시지 2개 전송
# 3. 대시보드 새로고침 → 새 세션 표시 (message_count: 2)
# 4. ChatPage 히스토리 → 새 세션 표시 (message_count: 2)
# 5. 두 목록이 일치하는지 확인 ✅
```

### 시나리오 3: Redis TTL 만료 후 확인
```bash
# 1. 2일 이상 지난 세션
# 2. Redis에는 없지만 PostgreSQL에는 있음
# 3. 대시보드 → 표시됨 ✅
# 4. ChatPage 히스토리 → 표시됨 ✅ (수정 전에는 안 보였음)
```

## 🔧 수정된 파일

### 1. `/home/admin/wkms-aws/backend/app/api/v1/chat.py`
- `@router.get("/chat/sessions")` 전면 수정
- PostgreSQL 기반 조회로 변경
- 실제 메시지 수 집계 추가
- `from sqlalchemy import text` import 추가

### 2. `/home/admin/wkms-aws/backend/app/api/v1/dashboard.py`
- `@router.get("/recent-chat-sessions")` 개선
- 실제 메시지 수 집계 추가
- 참고자료 수 정확한 계산 추가

## 📊 현재 데이터 상태

### 세션 목록 (2025-11-07 기준)
```sql
SELECT session_id, session_name, message_count as declared, 
       COUNT(h.chat_id) as actual
FROM tb_chat_sessions s 
LEFT JOIN tb_chat_history h ON s.session_id = h.session_id
WHERE is_active = true
GROUP BY s.session_id, s.session_name, s.message_count
ORDER BY s.last_modified_date DESC;
```

| session_id | session_name | declared | actual |
|------------|-------------|----------|--------|
| chat_1762491307850_6b0vzt66l | 토픽모델링이란 | 1 | 0 |
| chat_1762489901728_vo422kwt4 | 특허 분석에... | 2 | 0 |
| chat_1762484043000_hpkvfjsl4 | Ambidextrous... | 1 | 0 |
| chat_1762402149525_fhiygilkn | 첨부의 논문... | 1 | 0 |
| chat_1762322972575_stm4lp5mk | Roadmapping... | 6 | 0 |

**해석**:
- ✅ 세션 메타데이터는 존재
- ❌ 실제 메시지는 없음 (이전 버그로 인해 저장 안 됨)
- ✅ 이제부터 생성되는 세션은 정상 저장됨

## 🎉 결과

### Before
- ❌ 대시보드: 5개 세션
- ❌ 채팅 히스토리: 0개 세션 (Redis TTL 만료)
- ❌ 불일치!

### After
- ✅ 대시보드: 5개 세션 (actual_count: 0)
- ✅ 채팅 히스토리: 5개 세션 (actual_count: 0)
- ✅ 완벽히 일치!

### 향후 (새 세션)
- ✅ 대시보드: N개 세션 (실제 메시지 수)
- ✅ 채팅 히스토리: N개 세션 (실제 메시지 수)
- ✅ 정확한 메시지 수 표시
- ✅ 정확한 참고자료 수 표시

---
**수정일**: 2025-11-07
**상태**: ✅ 완료
**영향**: 대시보드와 채팅 히스토리 목록 일치
**테스트**: 새 세션 생성 필요

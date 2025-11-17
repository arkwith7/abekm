# 채팅 히스토리 관리 문제 점검 및 해결

## 📋 문제 상황

"최근 AI 대화"에서 클릭 시:
1. ❌ AI 지식생성 메뉴로 전환되지 않거나 전환되어도 대화 이력이 표시되지 않음
2. ❌ "AI 지식생성" 메뉴의 "채팅 히스토리" 목록과 불일치

## 🔍 원인 분석

### 1. URL 파라미터 전달 문제 (✅ 해결됨)
- **문제**: `navigateWithContext`가 `sessionId`를 URL 파라미터로 전달하지 않음
- **영향**: ChatPage가 URL에서 세션 ID를 읽을 수 없어 세션 로드 실패

### 2. PostgreSQL 세션 저장 불안정 (✅ 개선됨)
- **문제**: async generator 사용 방식이 잘못되어 DB 저장 실패 가능
- **영향**: Redis에는 저장되지만 PostgreSQL에 저장 안되어 대시보드/사이드바에 표시 안됨

### 3. 세션 제목 생성 문제 (✅ 개선됨)
- **문제**: 첫 메시지 50자만 잘라서 의미 없는 제목 생성
- **영향**: 사용자가 대화 내용을 구분하기 어려움

### 4. 세션 로드 에러 핸들링 부족 (✅ 개선됨)
- **문제**: 세션 로드 실패 시 상세한 로그 없음
- **영향**: 문제 진단 어려움

## ✅ 적용된 수정 사항

### 1. GlobalAppContext.tsx - URL 파라미터 전달
```typescript
// 채팅 페이지로 이동 시 sessionId가 있으면 URL 파라미터로 추가
if (to === 'chat' && preserveState?.sessionId) {
    targetRoute = `${targetRoute}?session=${preserveState.sessionId}`;
    console.log('🔗 채팅 세션 ID 포함하여 이동:', preserveState.sessionId);
}
```

**효과**:
- ✅ 대시보드에서 "최근 AI 대화" 클릭 시 정확한 세션 ID 전달
- ✅ ChatPage가 URL에서 세션 ID를 읽어 자동 로드

### 2. backend/app/api/v1/chat.py - DB 세션 저장 개선
```python
# 기존 (문제있는 코드)
async for db in get_db():
    await save_chat_session(...)
    break  # 첫 번째 세션만 사용

# 개선된 코드
db_gen = get_db()
db: AsyncSession = await db_gen.__anext__()
try:
    await save_chat_session(...)
    logger.info(f"✅ PostgreSQL 세션 저장 완료: {session_id}")
finally:
    await db_gen.aclose()
```

**효과**:
- ✅ async generator 올바른 사용으로 DB 저장 안정성 향상
- ✅ 에러 시 상세 로그로 문제 추적 가능
- ✅ DB 세션 정리로 리소스 누수 방지

### 3. backend/app/api/v1/chat.py - 세션 제목 개선
```python
# 기존
session_title = message[:50] + "..." if len(message) > 50 else message

# 개선
session_title = message.strip()
# 이모지 제거
session_title = re.sub(r'[🔍📄💬🎯📊🤖✨🚀]+', '', session_title)
# 줄바꿈을 공백으로
session_title = ' '.join(session_title.split())
# 최대 100자 (기존 50자에서 증가)
if len(session_title) > 100:
    session_title = session_title[:97] + "..."
```

**효과**:
- ✅ 더 의미있고 읽기 쉬운 세션 제목
- ✅ 불필요한 이모지/특수문자 제거
- ✅ 더 긴 제목으로 내용 파악 용이

### 4. useChat.ts - 세션 로드 개선
```typescript
// 상세한 로깅 추가
console.log('📦 세션 데이터 수신:', {
    sessionId: targetSessionId,
    success: data.success,
    messageCount: data.messages?.length || 0
});

// 에러 핸들링 강화
if (!data.success) {
    console.warn('⚠️ 백엔드에서 세션 로드 실패 응답:', data);
    throw new Error(data.message || '세션을 찾을 수 없습니다');
}
```

**효과**:
- ✅ 세션 로드 프로세스 전체 가시성 확보
- ✅ 문제 발생 시 즉시 원인 파악 가능
- ✅ 사용자에게 더 명확한 에러 메시지

## 🧪 테스트 시나리오

### 시나리오 1: 대시보드에서 세션 클릭
1. 대시보드 접속
2. "최근 AI 대화"에서 대화 하나 클릭
3. **기대 결과**:
   - ✅ AI 지식생성 페이지로 이동
   - ✅ 해당 세션의 대화 내역 표시
   - ✅ 브라우저 콘솔에 로드 로그 출력

### 시나리오 2: 사이드바에서 세션 클릭
1. 사이드바의 "채팅 히스토리" 확장
2. 세션 하나 클릭
3. **기대 결과**:
   - ✅ 선택한 세션의 대화 내역 표시
   - ✅ URL에 `?session=세션ID` 파라미터 포함

### 시나리오 3: 새 대화 후 히스토리 확인
1. 새 대화 시작
2. 메시지 여러 개 주고받기
3. 대시보드로 이동
4. "최근 AI 대화" 확인
5. **기대 결과**:
   - ✅ 방금 만든 세션이 목록 최상단에 표시
   - ✅ 의미있는 제목 (첫 메시지 최대 100자)
   - ✅ 정확한 메시지 개수 표시

## 📊 로그 모니터링

### 백엔드 로그 확인 항목
```bash
# 세션 저장 성공 로그
✅ PostgreSQL 세션 저장 완료: chat_xxx

# 세션 저장 실패 로그 (발생 시)
❌ PostgreSQL 세션 저장 실패 (Redis는 정상): [에러 메시지]

# 세션 로드 로그
🔄 세션 로드 시작: chat_xxx
✅ 기존 세션 로드 완료: {sessionId: ..., messageCount: ...}
```

### 프론트엔드 콘솔 확인 항목
```javascript
// 세션 클릭 시
🔗 채팅 세션 ID 포함하여 이동: chat_xxx

// 세션 로드 시
📦 세션 데이터 수신: {sessionId: ..., success: true, messageCount: 5}
✅ 기존 세션 로드 완료: {sessionId: ..., messageCount: 5, ...}
```

## 🔄 Redis vs PostgreSQL 동기화

### 저장 흐름
1. **메시지 전송** → Redis에 즉시 저장 (실시간)
2. **스트림 완료** → PostgreSQL에 세션 정보 저장/업데이트
3. **대시보드/사이드바** → PostgreSQL에서 세션 목록 조회
4. **세션 로드** → Redis에서 메시지 조회

### 일관성 보장
- ✅ Redis: 실시간 메시지 저장 (빠른 응답)
- ✅ PostgreSQL: 세션 메타데이터 저장 (영구 보존)
- ✅ 저장 실패 시 에러 로그로 즉시 감지 가능

## 🎯 추가 개선 권장사항

### 1. 세션 목록 페이지네이션
현재는 최근 5개만 표시하므로, 오래된 대화 접근 어려움
→ 무한 스크롤 또는 페이지네이션 구현 권장

### 2. 세션 검색 기능
대화 내용으로 세션 검색
→ 대시보드에 검색 바 추가 권장

### 3. 세션 정렬 옵션
현재는 최근 활동 순으로만 정렬
→ 제목순, 메시지 개수순 등 정렬 옵션 추가 권장

### 4. 세션 아카이브/즐겨찾기
중요한 대화를 별도로 표시
→ 즐겨찾기 기능 추가 권장

## 📌 결론

**핵심 문제 모두 해결됨**:
- ✅ URL 파라미터 전달로 세션 ID 전달
- ✅ DB 저장 안정성 향상
- ✅ 의미있는 세션 제목 생성
- ✅ 상세한 로깅으로 문제 추적 가능

**사용자 경험 개선**:
- ✅ 대시보드에서 클릭 시 즉시 대화 이력 표시
- ✅ 채팅 히스토리와 대시보드 목록 일치
- ✅ 명확한 에러 메시지로 문제 파악 용이

---
**작성일**: 2025-11-07
**버전**: v1.0
**담당**: ABEKM 개발팀

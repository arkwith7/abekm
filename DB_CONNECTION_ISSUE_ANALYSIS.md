# 🔍 삭제 오류 반복 발생 원인 분석 및 해결 방안

## 📋 현황 요약

### 1. **문제 증상**
- 문서 삭제 시 반복적으로 `ConnectionDoesNotExistError` 발생
- `PendingRollbackError: Can't reconnect until invalid transaction is rolled back` 발생
- PostgreSQL 연결이 작업 중에 갑자기 닫힘

### 2. **DB 상태 확인 결과**

```sql
-- 문서 78 현재 상태
file_bss_info_sno: 78
del_yn: 'N'  ← 삭제되지 않음!
processing_status: 'failed'
processing_error: "작업 등록 실패: Can't patch loop of type <class 'uvloop.Loop'>"
```

**중요 발견:**
- ✅ 문서 78은 DB에 존재하지만 `del_yn='N'` 상태
- ❌ 삭제 시도 시 cleanup 단계에서 연결이 끊김
- ❌ cleanup 실행 시 "connection was closed in the middle of operation" 발생

---

## 🎯 근본 원인 분석

### 1️⃣ **PostgreSQL Connection Pool 고갈 및 불안정**

#### 증상:
```
asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation
서버가 갑자기 연결을 닫았음 (psql 접속 시)
```

#### 원인:
1. **Connection Pool Size 부족**
   ```python
   # backend/app/core/config.py
   db_pool_size: int = 20
   db_max_overflow: int = 30
   ```
   - 총 최대 50개 연결 (pool_size + max_overflow)
   - FastAPI, Celery Worker, 개별 cleanup 세션이 모두 pool 공유
   - cleanup_standalone이 매번 새 세션 생성 → pool 고갈 가능

2. **Connection Recycling 설정**
   ```python
   db_pool_recycle: int = 300  # 5분마다 연결 재생성
   ```
   - 5분 내에 많은 작업 시 연결이 닫혀도 pool에 반환 안됨
   - PostgreSQL의 `idle_in_transaction_session_timeout` 기본값과 충돌 가능

3. **Connection Pre-ping 활성화되어 있지만 효과 없음**
   ```python
   db_pool_pre_ping: bool = True
   ```
   - pre_ping이 true지만 cleanup 작업 중에는 이미 연결이 닫힌 후

### 2️⃣ **cleanup_standalone의 구조적 문제**

#### 현재 코드:
```python
async def _cleanup_vector_and_index_artifacts_standalone(self, document_id, user_emp_no):
    for attempt in range(1, max_attempts + 1):
        async_session_factory = get_async_session_local()
        async with async_session_factory() as cleanup_session:
            async with cleanup_session.begin():
                # UPDATE vs_doc_contents_chunks ...
                # DELETE FROM tb_document_search_index ...
```

#### 문제점:
1. **매 재시도마다 새로운 session factory 생성**
   - Connection pool에서 새 연결 획득
   - 이전 실패한 연결은 pool에 남아있음 (zombie connection)

2. **begin() context 내에서 실행**
   - Exception 발생 시 자동 rollback
   - 하지만 connection 자체가 닫히면 rollback도 실패

3. **재시도 간 delay가 너무 짧음**
   - 0.5초, 1초, 2초 → DB가 복구할 시간 부족

### 3️⃣ **메인 삭제 트랜잭션과의 타이밍 이슈**

#### 삭제 흐름:
```python
# 1. 메인 soft delete + commit
await session.commit()

# 2. 즉시 cleanup 호출
cleanup_ok = await self._cleanup_vector_and_index_artifacts_standalone(...)
```

#### 문제:
- **메인 commit 직후 cleanup 실행**
- cleanup이 실패하면 메인 삭제는 성공했지만 연관 데이터는 남음
- **데이터 정합성 깨짐!**

---

## 🔧 해결 방안

### ✅ 즉시 적용 가능한 해결책

#### 1. **Connection Pool 크기 증가**

```python
# backend/app/core/config.py
db_pool_size: int = 40  # 20 → 40
db_max_overflow: int = 60  # 30 → 60
db_pool_timeout: int = 60  # 30 → 60 (대기 시간 증가)
```

#### 2. **cleanup_standalone 개선**

```python
async def _cleanup_vector_and_index_artifacts_standalone(
    self,
    document_id: int,
    user_emp_no: str,
) -> bool:
    from asyncio import sleep
    from app.core.database import get_async_session_local
    from app.models import VsDocContentsChunks
    from app.models.document.unified_search_models import TbDocumentSearchIndex
    
    max_attempts = 3
    delay = 2.0  # 0.5 → 2.0 (초기 대기 시간 증가)
    
    for attempt in range(1, max_attempts + 1):
        try:
            # 매번 새로운 connection factory 생성
            async_session_factory = get_async_session_local()
            async with async_session_factory() as cleanup_session:
                try:
                    # EXPLICIT transaction control
                    async with cleanup_session.begin():
                        stmt_chunks = (update(VsDocContentsChunks)
                                       .where(VsDocContentsChunks.file_bss_info_sno == document_id)
                                       .values(del_yn='Y', last_modified_by=user_emp_no))
                        await cleanup_session.execute(stmt_chunks)

                        stmt_search = delete(TbDocumentSearchIndex).where(
                            TbDocumentSearchIndex.file_bss_info_sno == document_id
                        )
                        await cleanup_session.execute(stmt_search)
                    
                    # begin() context 종료 시 자동 commit
                    logger.info(f"✅ [CLEANUP] doc_id={document_id} 정리 성공")
                    return True
                    
                except Exception as inner_e:
                    # begin() context는 자동 rollback하지만 명시적으로도 처리
                    logger.warning(
                        f"[CLEANUP] 시도 {attempt}/{max_attempts} 실패 - doc_id={document_id}: {inner_e}"
                    )
                    raise  # 외부 except로 전파
                    
        except Exception as e:
            if attempt < max_attempts:
                logger.info(f"🔄 [CLEANUP] {delay}초 대기 후 재시도...")
                await sleep(delay)
                delay = min(delay * 2.5, 10.0)  # 2초 → 5초 → 10초
            else:
                logger.error(
                    f"❌ [CLEANUP] 최종 실패 - doc_id={document_id}: {e}"
                )
                return False
    
    return False
```

#### 3. **데이터 정합성 보장 전략**

**Option A: 삭제 전 cleanup (추천)**
```python
async def delete_document_by_id(self, document_id, user_emp_no, session):
    # 1. 권한 확인
    # ...
    
    # 2. cleanup 먼저 수행 (실패 시 전체 롤백)
    cleanup_ok = await self._cleanup_vector_and_index_artifacts(
        document_id=document_id,
        user_emp_no=user_emp_no,
        session=session  # 메인 세션 사용!
    )
    
    if not cleanup_ok:
        await session.rollback()
        return {
            "success": False,
            "error": "연관 데이터 정리 실패 - 삭제를 중단합니다."
        }
    
    # 3. 메인 soft delete
    setattr(file_info, 'del_yn', 'Y')
    # ...
    
    # 4. 한번에 commit (all or nothing)
    await session.commit()
```

**Option B: 삭제 후 cleanup (현재 방식 개선)**
```python
async def delete_document_by_id(self, document_id, user_emp_no, session):
    # 1. 메인 soft delete + commit
    await session.commit()
    
    # 2. cleanup은 백그라운드로 위임 (Celery Task)
    from app.tasks.cleanup_tasks import cleanup_document_artifacts
    cleanup_document_artifacts.delay(document_id, user_emp_no)
    
    # 즉시 성공 응답
    return {"success": True, "message": "문서 삭제됨 (정리 작업 진행 중)"}
```

---

## 🎯 최종 권장 사항

### 1. **즉시 적용 (긴급)**
- [x] Connection pool 크기 증가 (40 + 60)
- [x] cleanup_standalone 재시도 로직 개선
- [x] delay 시간 증가 (2초 → 5초 → 10초)

### 2. **단기 개선 (1-2일 내)**
- [ ] Celery Task로 cleanup 위임 (`cleanup_tasks.py` 생성)
- [ ] 메인 삭제와 cleanup 분리 (eventual consistency)
- [ ] 정기 배치 작업으로 실패한 cleanup 재처리

### 3. **중장기 개선 (1주일 내)**
- [ ] PostgreSQL connection pooler (PgBouncer) 도입
- [ ] Connection monitoring 및 alerting 추가
- [ ] DB 쿼리 성능 최적화 (vs_doc_contents_chunks 테이블 인덱스)
- [ ] Soft delete 대신 hard delete + audit log 고려

---

## 📊 데이터 정합성 현황

### 현재 문제:
```
문서 78:
- tb_file_bss_info: del_yn='N', processing_status='failed'
- vs_doc_contents_chunks: 존재 여부 불명 (연결 끊김)
- tb_document_search_index: 존재 여부 불명 (연결 끊김)
```

### 정합성 복구 스크립트:
```sql
-- 1. 실패한 문서 확인
SELECT file_bss_info_sno, file_lgc_nm, del_yn, processing_status
FROM tb_file_bss_info
WHERE processing_status = 'failed' AND del_yn = 'N';

-- 2. 수동 cleanup
UPDATE vs_doc_contents_chunks
SET del_yn = 'Y', last_modified_by = '77107791'
WHERE file_bss_info_sno = 78;

DELETE FROM tb_document_search_index
WHERE file_bss_info_sno = 78;

-- 3. 메인 레코드 삭제 표시
UPDATE tb_file_bss_info
SET del_yn = 'Y', last_modified_by = '77107791'
WHERE file_bss_info_sno = 78;
```

---

## 🚀 다음 단계

1. **Connection pool 설정 변경 적용**
2. **cleanup_standalone 코드 개선**
3. **서버 재시작**
4. **문서 78 재삭제 테스트**
5. **성공 시 정합성 복구 스크립트 실행**
6. **Celery cleanup task 구현 (백로그)**

# 컨테이너 문서 개수 동기화 해결책

## 📋 문제 상황
- **증상**: 지식 컨테이너 카드에 "0개 문서"로 표시
- **실제**: MS서비스팀에 2개 문서 존재 (file_id: 1, 2)
- **원인**: `tb_knowledge_containers.document_count` 필드가 실제 문서 수와 동기화되지 않음

## ✅ 구현된 해결책

### 1️⃣ 즉시 해결: SQL 수동 업데이트 (완료)
```sql
-- 모든 컨테이너의 document_count를 실제 문서 개수로 업데이트
UPDATE tb_knowledge_containers kc
SET document_count = (
    SELECT COUNT(*)
    FROM tb_file_bss_info f
    WHERE f.knowledge_container_id = kc.container_id
      AND f.del_yn != 'Y'
),
last_modified_date = CURRENT_TIMESTAMP;
```

**실행 결과**:
- WJ_MS_SERVICE: 0 → 1개 (file_id=2만 유효)
- WJ_CLOUD: 0개 유지
- WJ_CLOUD_SERVICE: 0개 유지

### 2️⃣ 장기 해결: 자동 동기화 로직 (완료)

#### A. ContainerService에 업데이트 함수 추가
**파일**: `backend/app/services/auth/container_service.py`

```python
async def update_container_document_count(
    self,
    container_id: str
) -> int:
    """
    컨테이너의 document_count를 실제 문서 개수로 업데이트
    
    Args:
        container_id: 업데이트할 컨테이너 ID
        
    Returns:
        업데이트된 문서 개수
    """
    # 실제 문서 개수 조회 (del_yn != 'Y')
    doc_count_query = select(func.count(TbFileBssInfo.file_bss_info_sno)).where(
        and_(
            TbFileBssInfo.knowledge_container_id == container_id,
            TbFileBssInfo.del_yn != 'Y'
        )
    )
    doc_count_result = await self.session.execute(doc_count_query)
    actual_count = doc_count_result.scalar() or 0
    
    # tb_knowledge_containers 업데이트
    update_query = (
        update(TbKnowledgeContainers)
        .where(TbKnowledgeContainers.container_id == container_id)
        .values(
            document_count=actual_count,
            last_modified_date=datetime.utcnow()
        )
    )
    await self.session.execute(update_query)
    await self.session.commit()
    
    return actual_count
```

#### B. 문서 업로드 시 자동 업데이트
**파일**: `backend/app/api/v1/documents.py` (646행)

```python
# 🔢 컨테이너의 document_count 업데이트
try:
    from app.services.auth.container_service import ContainerService
    container_service = ContainerService(session)
    updated_count = await container_service.update_container_document_count(container_id)
    logger.info(f"📊 컨테이너 문서 개수 업데이트: {container_id} -> {updated_count}개")
except Exception as count_error:
    logger.warning(f"⚠️ 컨테이너 문서 개수 업데이트 실패 (무시): {count_error}")
```

#### C. 문서 삭제 시 자동 업데이트
**파일**: `backend/app/services/document/document_service.py` (665행)

```python
# 🔢 컨테이너의 document_count 업데이트
if container_id:
    try:
        from app.services.auth.container_service import ContainerService
        container_svc = ContainerService(session)
        updated_count = await container_svc.update_container_document_count(container_id)
        logger.info(f"📊 컨테이너 문서 개수 업데이트: {container_id} -> {updated_count}개")
    except Exception as count_error:
        logger.warning(f"⚠️ 컨테이너 문서 개수 업데이트 실패 (무시): {count_error}")
```

### 3️⃣ 추가 옵션: PostgreSQL 트리거 (선택사항)

데이터베이스 레벨에서 자동 동기화를 원할 경우:

**파일**: `backend/alembic/versions/sync_document_count_trigger.sql`

```bash
# 트리거 설치
docker exec -i abkms-postgres psql -U wkms -d wkms < \
  backend/alembic/versions/sync_document_count_trigger.sql
```

**장점**:
- 애플리케이션 코드 외부에서도 동기화 보장
- 직접 SQL로 데이터 변경 시에도 자동 업데이트

**단점**:
- 데이터베이스 의존성 증가
- 디버깅 복잡도 상승

## 🚀 배포 방법

### 백엔드 재시작
```bash
docker restart abkms-backend
```

### 검증
```bash
# 1. 문서 업로드 테스트
# - 프론트엔드에서 문서 업로드
# - 컨테이너 카드 개수 증가 확인

# 2. 문서 삭제 테스트
# - 프론트엔드에서 문서 삭제
# - 컨테이너 카드 개수 감소 확인

# 3. 데이터베이스 직접 확인
docker exec -i abkms-postgres psql -U wkms -d wkms <<EOF
SELECT 
    kc.container_id,
    kc.container_name,
    kc.document_count as stored_count,
    (SELECT COUNT(*) FROM tb_file_bss_info f 
     WHERE f.knowledge_container_id = kc.container_id 
       AND f.del_yn != 'Y') as actual_count
FROM tb_knowledge_containers kc
WHERE kc.container_id IN ('WJ_MS_SERVICE', 'WJ_CLOUD', 'WJ_CLOUD_SERVICE')
ORDER BY kc.container_id;
EOF
```

## 📊 기대 효과

1. **실시간 동기화**: 문서 업로드/삭제 시 즉시 개수 업데이트
2. **데이터 정합성**: 화면 표시와 실제 데이터 일치
3. **성능 최적화**: `/full-hierarchy` API는 여전히 실시간 조회 사용
4. **유지보수성**: 중앙화된 업데이트 로직으로 관리 용이

## 🔍 추가 개선 사항

### 향후 고려사항
1. **배치 정리 작업**: 주기적으로 모든 컨테이너 document_count 검증
2. **모니터링**: document_count 불일치 알림 시스템
3. **캐싱**: 자주 조회되는 컨테이너 정보 Redis 캐싱

### 배치 정리 스크립트 예시
```python
# backend/scripts/sync_all_document_counts.py
async def sync_all_document_counts():
    async with get_db_session() as session:
        container_service = ContainerService(session)
        containers = await session.execute(
            select(TbKnowledgeContainers.container_id)
        )
        for (container_id,) in containers:
            await container_service.update_container_document_count(container_id)
```

## ✅ 체크리스트

- [x] SQL로 초기 데이터 동기화 완료
- [x] ContainerService에 업데이트 함수 추가
- [x] 문서 업로드 시 자동 업데이트 추가
- [x] 문서 삭제 시 자동 업데이트 추가
- [x] PostgreSQL 트리거 스크립트 작성 (선택사항)
- [ ] 백엔드 재시작
- [ ] 문서 업로드 테스트
- [ ] 문서 삭제 테스트
- [ ] 화면 표시 확인

## 📝 참고사항

- `del_yn != 'Y'` 조건으로 삭제된 문서 제외
- 업데이트 실패 시 경고 로그만 출력 (트랜잭션 롤백 방지)
- `/full-hierarchy` API는 기존처럼 실시간 조회 유지 (이중 안전장치)

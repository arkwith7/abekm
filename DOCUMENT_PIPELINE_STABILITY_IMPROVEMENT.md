# 문서 파이프라인 안정성 개선 완료 보고서

**작업 일자**: 2025-10-14  
**작업자**: AI Assistant  
**목적**: 문서 업로드/다운로드/삭제 기능의 안정성 및 데이터 정합성 개선

---

## 📋 목차

1. [개요](#개요)
2. [완료된 작업](#완료된-작업)
3. [세부 변경사항](#세부-변경사항)
4. [테스트 가이드](#테스트-가이드)
5. [운영 가이드](#운영-가이드)
6. [설정 변경사항](#설정-변경사항)

---

## 개요

### 배경

- 문서 삭제 시 500 오류 발생 (ConnectionDoesNotExistError)
- Azure SDK 로그 과다 출력
- 업로드 실패 시 DB와 스토리지 간 데이터 불일치
- 다운로드 302 리다이렉트 프론트엔드 호환성 문제

### 목표

✅ 데이터 정합성 보장 (DB ↔ Azure Blob Storage)  
✅ 예외 처리 강화 (트랜잭션 롤백, 리소스 정리)  
✅ 운영 안정성 향상 (DB 연결, 재시도 로직)  
✅ 사용자 경험 개선 (명확한 오류 메시지, 다운로드 옵션)

---

## 완료된 작업

### ✅ Task 1: 업로드 실패 시 트랜잭션 롤백 강화

**파일**: `backend/app/api/v1/documents.py`

**개선사항**:
- S3/Azure Blob 업로드 실패 시 즉시 중단 및 로컬 파일 정리
- DB 저장 실패 시 명시적 트랜잭션 롤백
- 예외 발생 시 원격 스토리지 + 로컬 파일 모두 정리
- 로컬 경로가 DB에 저장되는 문제 해결

**영향**:
- 🟢 업로드 실패 시 DB와 스토리지 간 불일치 방지
- 🟢 Orphan 파일 생성 최소화

---

### ✅ Task 2: 멀티모달 파이프라인 예외 처리 개선

**파일**: `backend/app/services/document/document_service.py`

**개선사항**:
- RAG 파이프라인 실패를 치명적 오류로 처리
- 파이프라인 실패 시 DB 트랜잭션 롤백
- 불완전한 문서가 DB에 저장되는 문제 해결

**영향**:
- 🟢 RAG 처리 실패 시 문서 메타데이터만 남지 않음
- 🟢 검색 인덱스 정합성 보장

---

### ✅ Task 3: 다운로드 302 리다이렉트 대체 구현

**파일**: `backend/app/api/v1/documents.py`

**개선사항**:
- Azure Blob 다운로드 방식을 설정으로 제어
  - **redirect 모드**: 302 SAS URL 리다이렉트 (기존, 빠름)
  - **proxy 모드**: 서버 프록시 다운로드 (프론트 호환)
- BackgroundTasks로 임시 파일 자동 정리

**설정 방법**:
```python
# backend/app/core/config.py
azure_blob_download_mode: str = "redirect"  # 또는 "proxy"
```

**영향**:
- 🟢 프론트엔드 호환성 문제 해결
- 🟢 다운로드 방식 선택 가능

---

### ✅ Task 4: DB 연결 안정성 강화

**파일**: `backend/app/services/document/document_service.py`

**개선사항**:
- 청크 정리 재시도 대기 시간 증가: **2초 → 5초 → 10초**
- DB 연결 복구 시간 확보
- 재시도 로그 추가

**영향**:
- 🟢 DB 연결 불안정 시 복구 가능성 향상
- 🟢 청크 정리 성공률 개선

---

### ✅ Task 5: 권한 검증 로직 통일

**파일**: 
- `backend/app/services/auth/permission_service.py`
- `backend/app/api/v1/documents.py`
- `backend/app/services/document/document_service.py`

**개선사항**:
- `check_download_permission()` 메서드 추가
- `check_delete_permission()` 메서드 추가
- 다운로드 엔드포인트에 권한 체크 추가
- 삭제 권한 체크를 permission_service로 통일
- 일관된 403 오류 반환

**권한 레벨**:
- **업로드**: ADMIN, MANAGER, EDITOR, CONTRIBUTOR, MEMBER_DEPT
- **다운로드**: ADMIN, MANAGER, EDITOR, CONTRIBUTOR, VIEWER, MEMBER_DEPT
- **삭제**: 소유자/생성자 또는 ADMIN, MANAGER, EDITOR

**영향**:
- 🟢 권한 로직 중복 제거
- 🟢 일관된 권한 정책 적용

---

### ✅ Task 6: Orphan 파일 정리 메커니즘

**파일**: `backend/app/management/commands/cleanup_orphan_files.py`

**개선사항**:
- DB에 없으나 Azure Blob에 남은 파일 검색
- 생성 후 최소 경과 시간 체크 (기본 24시간)
- Dry-run 모드 지원
- 최대 파일 개수 제한

**사용법**:
```bash
# Dry run (삭제하지 않고 로그만)
python -m app.management.commands.cleanup_orphan_files --purpose raw --dry-run

# 실제 삭제 (24시간 경과 파일)

python -m app.management.commands.cleanup_orphan_files --purpose raw --no-dry-run

# 48시간 경과 파일만 삭제

python -m app.management.commands.cleanup_orphan_files --purpose raw --no-dry-run --min-age 48

# Intermediate 파일 정리

python -m app.management.commands.cleanup_orphan_files --purpose intermediate --no-dry-run
```

**영향**:
- 🟢 스토리지 비용 절감
- 🟢 장기 운영 안정성 확보

---

## 세부 변경사항

### 1. 업로드 에러 처리 흐름

**이전**:
```
업로드 시도 → Azure 실패 → 로컬 경로 DB 저장 ❌
```

**현재**:
```
업로드 시도 → Azure 실패 → 로컬 파일 삭제 → HTTPException(500) ✅
업로드 성공 → DB 저장 실패 → DB 롤백 → Azure 삭제 → 로컬 삭제 ✅
```

### 2. 멀티모달 파이프라인 에러 처리 흐름

**이전**:
```
파이프라인 실패 → 로그만 남김 → 문서는 DB에 저장 ❌
```

**현재**:
```
파이프라인 실패 → DB 롤백 → 오류 반환 ✅
```

### 3. 다운로드 방식

**redirect 모드** (기본):
```
클라이언트 요청 → 백엔드 SAS URL 생성 → 302 리다이렉트 → Azure Blob 직접 다운로드
```

**proxy 모드**:
```
클라이언트 요청 → 백엔드 임시 다운로드 → FileResponse 응답 → 임시 파일 삭제
```

### 4. 삭제 권한 체크

**이전**:
```python
# document_service 내부에서 소유자만 체크
if user_emp_no not in {owner_emp_no, creator_emp_no}:
    return {"error": "권한 없음"}
```

**현재**:
```python
# permission_service에서 통합 체크
can_delete, msg = await permission_service.check_delete_permission(
    user_emp_no, container_id, owner_emp_no, created_by
)
# 소유자/생성자 OR ADMIN/MANAGER/EDITOR 권한 확인
```

---

## 테스트 가이드

### 1. 업로드 테스트

#### 성공 시나리오

```bash
# 정상 업로드
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf" \
  -F "container_id=CONT001" \
  -F "use_multimodal=true"

# 기대 결과: 200 OK, document_id 반환
```

#### 실패 시나리오

```bash
# Azure 연결 실패 시뮬레이션 (네트워크 끊기)
# 기대 결과: 500 오류, DB에 데이터 없음, 로컬 임시 파일 삭제됨
```

### 2. 다운로드 테스트

#### redirect 모드 (기본)

```bash
# 설정: azure_blob_download_mode = "redirect"
curl -L http://localhost:8000/api/v1/documents/{doc_id}/download \
  -H "Authorization: Bearer $TOKEN" \
  -o downloaded.pdf

# 기대 결과: 302 리다이렉트 → Azure Blob에서 직접 다운로드
```

#### proxy 모드

```bash
# 설정: azure_blob_download_mode = "proxy"
curl http://localhost:8000/api/v1/documents/{doc_id}/download \
  -H "Authorization: Bearer $TOKEN" \
  -o downloaded.pdf

# 기대 결과: 200 OK, 백엔드 프록시로 다운로드
```

### 3. 삭제 테스트

#### 권한 있는 사용자

```bash
# 소유자 또는 ADMIN/MANAGER/EDITOR
curl -X DELETE http://localhost:8000/api/v1/documents/{doc_id} \
  -H "Authorization: Bearer $TOKEN"

# 기대 결과: 200 OK, DB 소프트 삭제, Azure Blob 삭제, 청크/인덱스 정리
```

#### 권한 없는 사용자

```bash
# VIEWER 또는 타인 문서
curl -X DELETE http://localhost:8000/api/v1/documents/{doc_id} \
  -H "Authorization: Bearer $TOKEN"

# 기대 결과: 403 Forbidden
```

### 4. Orphan 파일 정리 테스트

```bash
# 1. Dry run으로 확인
python -m app.management.commands.cleanup_orphan_files --purpose raw --dry-run

# 2. 실제 삭제 (최대 10개만)
python -m app.management.commands.cleanup_orphan_files --purpose raw --no-dry-run --max-files 10
```

---

## 운영 가이드

### 1. 모니터링 포인트

#### 업로드 실패율

```python
# 로그 패턴
"❌ [UPLOAD-DEBUG] Azure Blob 업로드 실패"
"🔄 [UPLOAD-DEBUG] DB 트랜잭션 롤백 완료"
```

#### 삭제 청크 정리 실패율

```python
# 로그 패턴
"문서 연관 데이터 정리 실패 - 문서 ID: {id}, 시도: {attempt}/3"
"🔄 [CLEANUP-DEBUG] {delay}초 대기 후 재시도..."
```

#### Orphan 파일 증가 추세

```bash
# 주간 체크 스크립트
python -m app.management.commands.cleanup_orphan_files --purpose raw --dry-run > orphan_check.log
```

### 2. 권장 Cron 작업

```cron
# Orphan 파일 정리 (매일 새벽 2시)
0 2 * * * cd /path/to/backend && python -m app.management.commands.cleanup_orphan_files --purpose raw --no-dry-run --min-age 48 >> /var/log/orphan_cleanup.log 2>&1

# Intermediate 파일 정리 (매주 일요일 새벽 3시)
0 3 * * 0 cd /path/to/backend && python -m app.management.commands.cleanup_orphan_files --purpose intermediate --no-dry-run --min-age 72 >> /var/log/orphan_cleanup.log 2>&1
```

### 3. 알림 설정

#### 업로드 실패 알림

- 임계값: 시간당 10건 이상
- 조치: Azure Blob 연결 상태 확인

#### 청크 정리 실패 알림

- 임계값: 일일 100건 이상
- 조치: DB 연결 안정성 점검

#### Orphan 파일 임계값 알림

- 임계값: 1000개 이상
- 조치: 수동 정리 또는 max_files 증가

---

## 설정 변경사항

### 1. config.py 추가 설정

```python
# backend/app/core/config.py

class Settings(BaseSettings):
    # ... 기존 설정 ...
    
    # Azure Blob 다운로드 방식
    azure_blob_download_mode: str = "redirect"  # "redirect" | "proxy"
    
    # DB 연결 설정 (기존 값 변경)
    db_pool_recycle: int = 300  # 변경: 3600 → 300 (5분)
```

### 2. 환경변수

```bash
# .env 파일
AZURE_BLOB_DOWNLOAD_MODE=redirect  # 또는 proxy
DB_POOL_RECYCLE=300
```

---

## 주요 코드 변경 요약

### 변경된 파일 목록

1. `backend/app/api/v1/documents.py` (업로드/다운로드 엔드포인트)
2. `backend/app/services/document/document_service.py` (문서 서비스)
3. `backend/app/services/auth/permission_service.py` (권한 서비스)
4. `backend/app/core/config.py` (설정)
5. `backend/app/management/commands/cleanup_orphan_files.py` (새 파일)

### 추가된 기능

- `permission_service.check_download_permission()`
- `permission_service.check_delete_permission()`
- `cleanup_orphan_files.py` 관리 명령

### 개선된 로직

- 업로드 실패 시 롤백 및 정리
- 멀티모달 파이프라인 예외 처리
- 다운로드 proxy 모드
- DB 연결 재시도 타이밍

---

## 롤백 가이드

문제 발생 시 이전 버전으로 롤백하려면:

```bash
# Git 롤백
git checkout <이전_커밋_해시>

# 또는 개별 파일 롤백
git checkout <이전_커밋> backend/app/api/v1/documents.py
git checkout <이전_커밋> backend/app/services/document/document_service.py
```

---

## 향후 개선 사항

### 단기 (1-2주)

- [ ] 업로드/다운로드/삭제 통합 테스트 작성
- [ ] 프론트엔드 다운로드 302 vs proxy 성능 비교
- [ ] Orphan 정리 실행 로그 모니터링

### 중기 (1-2개월)

- [ ] 업로드 진행률 실시간 전송 (WebSocket/SSE)
- [ ] 대용량 파일 청킹 업로드 지원
- [ ] 삭제 시 물리 삭제 vs 소프트 삭제 정책 선택

### 장기 (3개월+)

- [ ] 파일 버전 관리 시스템
- [ ] 휴지통 기능 (30일 보관 후 영구 삭제)
- [ ] S3/Azure Blob 멀티 리전 복제

---

## 문의 및 지원

이슈 발생 시:
1. 로그 확인: `backend/logs/app.log`
2. 에러 패턴 검색: `grep "❌" logs/app.log`
3. GitHub Issue 등록 또는 팀 슬랙 채널에 문의

---

**작성일**: 2025-10-14  
**문서 버전**: 1.0  
**검토자**: -  
**승인자**: -

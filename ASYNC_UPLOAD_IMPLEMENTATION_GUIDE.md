# 비동기 업로드 + 백그라운드 처리 기능 실행 가이드

## 📋 개요

문서 업로드 시 비동기 백그라운드 처리를 통해 사용자 경험을 개선합니다.

### 개선 효과
- ❌ **이전**: 98초 동안 브라우저 멈춤
- ✅ **개선**: 2-3초 이내 즉시 응답 + 백그라운드 처리

---

## 🚀 실행 방법

### 1. 패키지 설치

```bash
cd backend
pip install -r requirements.txt
```

새로 추가된 패키지:
- `celery==5.3.4`: 비동기 작업 큐
- `flower==2.0.1`: Celery 모니터링 (선택사항)

### 2. Redis 서버 실행

Celery는 Redis를 메시지 브로커로 사용합니다.

#### Docker로 실행 (권장)
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

#### 직접 설치
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# macOS
brew install redis
brew services start redis
```

#### 연결 확인
```bash
redis-cli ping
# 응답: PONG
```

### 3. 환경 변수 설정

`.env` 파일에 Redis 설정 추가:

```bash
# Redis 설정
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# 또는 전체 URL
REDIS_URL=redis://localhost:6379/0
```

### 4. DB 마이그레이션 실행

```bash
cd backend

# 마이그레이션 적용
alembic upgrade head

# 마이그레이션 확인
alembic current
```

마이그레이션 내용:
- `tb_file_bss_info` 테이블에 4개 컬럼 추가
  - `processing_status`: 처리 상태
  - `processing_error`: 오류 메시지
  - `processing_started_at`: 시작 시간
  - `processing_completed_at`: 완료 시간
- 인덱스 추가: `idx_file_bss_info_processing_status`

### 5. 서비스 실행

#### 방법 1: 자동 시작 스크립트 사용 (권장 ⭐)

**Redis 서버 먼저 시작:**
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

**백엔드 서버 시작 (Redis + Celery + FastAPI 자동 실행):**
```bash
cd /home/wjadmin/Dev/InsightBridge
./shell-script/dev-start-backend.sh
```

**특징:**
- ✅ 가상환경 자동 활성화
- ✅ Redis 연결 자동 확인
- ✅ Celery Worker 백그라운드 자동 시작
- ✅ FastAPI 서버 자동 시작
- ✅ Ctrl+C로 모든 서비스 한 번에 정리
- ✅ PID 파일 관리로 프로세스 추적
- ✅ 로그 파일 자동 생성 (`logs/celery.log`)

**콘솔 출력 예시:**
```
===================================================================
   WKMS 백엔드 개발 서버 시작 (비동기 업로드 지원)
===================================================================

✅ Redis 서버 연결됨 (PONG)
✅ Celery Worker 시작됨 (PID: 12345)
   로그: logs/celery.log
✅ FastAPI 서버 시작됨 (PID: 12346)

-------------------------------------------------------------------
   📍 API 서버:     http://localhost:8000
   📚 API 문서:     http://localhost:8000/docs
   ✅ 비동기 업로드: 활성화
-------------------------------------------------------------------
```

#### 방법 2: 수동 실행 (개별 제어 필요 시)

**3개의 터미널 필요:**

**터미널 1: Celery Worker**
```bash
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

로그 예시:
```
[2025-10-14 10:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-10-14 10:00:00,100: INFO/MainProcess] Ready to accept tasks!
```

**터미널 2: FastAPI 서버**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**터미널 3: Flower 모니터링 (선택사항)**
```bash
cd backend
celery -A app.core.celery_app flower --port=5555
```

Flower 웹 UI: http://localhost:5555

---

## 🧪 테스트

### 1. 문서 업로드 (비동기 처리)

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf" \
  -F "container_id=container_1" \
  -F "use_multimodal=true"
```

**응답 (2-3초 이내):**
```json
{
  "success": true,
  "message": "문서 업로드가 완료되었습니다.",
  "document_id": 123,
  "file_info": {
    "original_name": "test.pdf",
    "file_size": 12345678,
    "file_type": ".pdf"
  },
  "processing_stats": {
    "upload_time": 2.5,
    "status": "processing",
    "message": "백그라운드에서 문서를 분석하고 있습니다."
  },
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 2. 처리 상태 조회

```bash
curl -X GET "http://localhost:8000/api/v1/documents/123/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**응답 (처리 중):**
```json
{
  "success": true,
  "document_id": 123,
  "file_name": "test.pdf",
  "status": "processing",
  "progress": 45,
  "error": null,
  "started_at": "2025-10-14T10:00:00",
  "completed_at": null,
  "message": "텍스트와 이미지를 추출하고 있습니다..."
}
```

**응답 (완료):**
```json
{
  "success": true,
  "document_id": 123,
  "file_name": "test.pdf",
  "status": "completed",
  "progress": 100,
  "error": null,
  "started_at": "2025-10-14T10:00:00",
  "completed_at": "2025-10-14T10:01:38",
  "message": "문서 처리가 완료되었습니다."
}
```

### 3. 폴링 방식 프론트엔드 예제

```javascript
async function uploadAndMonitor(file, containerId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('container_id', containerId);
  formData.append('use_multimodal', 'true');
  
  // 1. 업로드 (즉시 응답)
  const uploadResponse = await fetch('/api/v1/documents/upload', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  
  const uploadResult = await uploadResponse.json();
  const documentId = uploadResult.document_id;
  
  console.log(`✅ 업로드 완료: ${documentId}`);
  
  // 2. 상태 폴링 (3초마다)
  const checkInterval = setInterval(async () => {
    const statusResponse = await fetch(
      `/api/v1/documents/${documentId}/status`,
      {
        headers: { 'Authorization': `Bearer ${token}` }
      }
    );
    
    const status = await statusResponse.json();
    
    console.log(`진행률: ${status.progress}% - ${status.message}`);
    
    // 진행률 UI 업데이트
    updateProgressBar(status.progress, status.message);
    
    if (status.status === 'completed') {
      clearInterval(checkInterval);
      console.log('✅ 처리 완료!');
      onComplete(documentId);
    } else if (status.status === 'failed') {
      clearInterval(checkInterval);
      console.error(`❌ 처리 실패: ${status.error}`);
      onError(status.error);
    }
  }, 3000);
}
```

---

## �� 트러블슈팅

### Redis 연결 실패

**증상:**
```
[ERROR] Failed to connect to redis://localhost:6379
```

**해결:**
```bash
# Redis 상태 확인
docker ps | grep redis

# Redis 재시작
docker restart redis

# 연결 테스트
redis-cli ping
```

### Celery Worker 작업 실행 안됨

**증상:**
```
[WARNING] No active tasks
```

**해결:**
```bash
# Worker 재시작
# Ctrl+C로 중단 후
celery -A app.core.celery_app worker --loglevel=info

# 작업 큐 확인
redis-cli
> LLEN celery
```

### DB 마이그레이션 충돌

**증상:**
```
alembic.util.exc.CommandError: Target database is not up to date.
```

**해결:**
```bash
# 현재 버전 확인
alembic current

# 특정 버전으로 다운그레이드 후 재실행
alembic downgrade b38f1337b6ae
alembic upgrade head
```

### 작업 타임아웃

**증상:**
```
Task exceeded time limit
```

**해결:**
`backend/app/core/celery_app.py` 수정:
```python
celery_app.conf.update(
    task_time_limit=7200,  # 2시간으로 증가
    task_soft_time_limit=6600,
)
```

---

## 📊 모니터링

### 1. Flower 대시보드

http://localhost:5555

- 실시간 작업 상태
- 성공/실패 통계
- Worker 성능 메트릭

### 2. Redis 큐 확인

```bash
redis-cli

# 대기 중인 작업 수
LLEN celery

# 작업 목록 보기
LRANGE celery 0 -1
```

### 3. 로그 확인

```bash
# Celery Worker 로그
tail -f logs/celery.log

# FastAPI 로그
tail -f logs/app.log
```

---

## 🎯 성능 최적화 (선택사항)

### 1. Worker 프로세스 수 증가

```bash
celery -A app.core.celery_app worker --loglevel=info --concurrency=4
```

### 2. 임베딩 배치 처리

현재 48개 청크를 순차 처리하는 대신 배치로 처리하면:
- 순차: 48 × 0.43초 = 20.76초
- 배치: 3 batch × 2초 = 6초

### 3. WebSocket 실시간 진행률

폴링 대신 WebSocket으로 실시간 업데이트 (향후 개선 예정)

---

## 📝 운영 가이드

### 프로덕션 배포

1. **Redis 고가용성 구성**
   - Redis Sentinel 또는 Redis Cluster 사용
   
2. **Celery Worker 자동 재시작**
   ```bash
   # systemd 서비스 등록
   sudo systemctl enable celery-worker
   sudo systemctl start celery-worker
   ```

3. **모니터링 알림 설정**
   - Flower 알림 설정
   - 실패 작업 자동 알림

### 백업 및 복구

```bash
# DB 백업 (마이그레이션 전)
pg_dump -U wkms -d wkms > backup_$(date +%Y%m%d).sql

# 롤백 (필요시)
alembic downgrade -1
```

---

## ✅ 체크리스트

배포 전 확인:

- [ ] Redis 서버 실행 중
- [ ] Celery Worker 실행 중
- [ ] DB 마이그레이션 완료
- [ ] 환경 변수 설정 완료
- [ ] 테스트 업로드 성공
- [ ] 상태 조회 API 동작 확인
- [ ] 에러 핸들링 테스트 완료
- [ ] Flower 모니터링 접속 확인

---

**작성일**: 2025-10-14  
**버전**: 1.0  
**작성자**: AI Assistant

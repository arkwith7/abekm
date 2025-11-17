# 개발 스크립트 가이드

## dev-start-backend.sh

비동기 업로드 기능을 포함한 백엔드 개발 서버 시작 스크립트입니다.

### 🚀 빠른 시작

**1. Redis 서버 시작:**
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

**2. 백엔드 서버 시작:**
```bash
cd /home/wjadmin/Dev/InsightBridge
./shell-script/dev-start-backend.sh
```

### ✨ 자동 실행 항목

- ✅ 가상환경 자동 활성화
- ✅ Redis 연결 확인
- ✅ Celery Worker 백그라운드 시작
- ✅ FastAPI 서버 시작
- ✅ Ctrl+C로 모든 서비스 정리

### 📂 생성되는 파일

- **로그:** `logs/celery.log` - Celery Worker 로그
- **PID:** `tmp/pids/celery.pid` - Celery Worker PID
- **PID:** `tmp/pids/fastapi.pid` - FastAPI 서버 PID

### 🌐 접속 주소

- **API 서버:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Flower (선택):** http://localhost:5555
  ```bash
  cd backend
  celery -A app.core.celery_app flower
  ```

### �� 서버 종료

**방법 1: 자동 정리 (권장)**
```
Ctrl+C를 누르면 모든 서비스가 자동으로 종료됩니다.
```

**방법 2: 수동 종료**
```bash
# Celery Worker 종료
kill $(cat tmp/pids/celery.pid)

# FastAPI 서버 종료
kill $(cat tmp/pids/fastapi.pid)

# PID 파일 삭제
rm -f tmp/pids/*.pid
```

### ⚠️ Redis 없이 실행

Redis가 실행되지 않은 경우:
- 스크립트가 Redis 연결 실패를 감지합니다.
- 계속 진행 여부를 묻습니다.
- Redis 없이 실행 시 **비동기 업로드가 비활성화**됩니다.

### 🔍 로그 확인

**Celery Worker 로그:**
```bash
tail -f logs/celery.log
```

**FastAPI 로그:**
스크립트 실행 시 실시간으로 표시됩니다.

### 🐛 문제 해결

**1. Redis 연결 실패**
```bash
# Redis 상태 확인
redis-cli ping

# Docker Redis 재시작
docker restart redis
```

**2. Celery Worker 시작 실패**
```bash
# 수동으로 Celery 시작 시도
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

**3. 포트 이미 사용 중**
```bash
# 8000 포트 사용 프로세스 찾기
lsof -i :8000

# 프로세스 종료
kill <PID>
```

**4. 이전 PID 파일 남아있음**
```bash
# 모든 PID 파일 정리
rm -f tmp/pids/*.pid
```

### 📖 관련 문서

- [비동기 업로드 실행 가이드](../ASYNC_UPLOAD_IMPLEMENTATION_GUIDE.md)
- [비동기 업로드 구현 요약](../ASYNC_UPLOAD_SUMMARY.md)

---

## 기타 스크립트

### dev.sh
기존 백엔드 서버 시작 스크립트 (비동기 기능 없음)

### deploy.sh
프로덕션 배포 스크립트

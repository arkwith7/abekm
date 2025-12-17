# 개발 스크립트 가이드

## dev-start-backend.sh

비동기 업로드 기능을 포함한 백엔드 개발 서버 시작 스크립트입니다.

### 🚀 빠른 시작

**1. 백엔드/Celery 서버 시작 (Docker Compose):**
```bash
cd /home/admin/Dev/abekm
./shell-script/dev-start-backend.sh
```

### ✨ 자동 실행 항목

- ✅ Docker Compose로 `backend`, `celery-worker` 컨테이너 실행
- ✅ 컨테이너 내부 `uvicorn --reload`로 코드 변경 자동 반영
- ✅ 의존 서비스(예: Redis/DB)는 Compose 설정에 따라 자동 기동
- ✅ Ctrl+C로 `backend/celery-worker` 컨테이너 중지

### 📂 생성되는 파일

- 별도 PID/로그 파일을 생성하지 않습니다.
- 로그는 Compose로 확인합니다: `docker compose logs -f backend celery-worker`

### 🌐 접속 주소

- **API 서버:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### 🌸 Flower (선택)

프로세스 모니터링이 필요하면 로컬에서 Flower를 따로 띄울 수 있습니다.

```bash
docker compose exec backend bash -lc "celery -A app.core.celery_app flower --port=5555"
```

### 🛑 서버 종료

**방법 1: 자동 정리 (권장)**
```
Ctrl+C를 누르면 backend/celery-worker 컨테이너가 중지됩니다.
```

**방법 2: 수동 종료**
```bash
docker compose stop backend celery-worker
```

### 🔍 로그 확인

**backend / celery-worker 로그:**
```bash
docker compose logs -f --tail=100 backend celery-worker
```

### 🐛 문제 해결

**1. Redis 연결 실패**
```bash
docker compose ps
docker compose logs --tail=200 redis
```

**2. Celery Worker 시작 실패**
```bash
docker compose logs --tail=300 celery-worker
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
# Compose 컨테이너 재기동
docker compose up -d --build backend celery-worker
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

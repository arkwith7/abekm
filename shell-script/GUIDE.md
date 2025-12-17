# Shell Script Guide

이 디렉토리는 **필수 워크플로우만 남기고 단순화**되어 있습니다.

## 남아있는 스크립트 (4개)

- `dev-start-backend.sh`: 개발용 백엔드 + Celery Worker 실행/로그 팔로우
- `dev-start-frontend.sh`: 개발용 프론트엔드 실행/로그 팔로우
- `deploy.sh`: 운영용 배포(Compose prod) `up/down/restart/rebuild/logs/ps`
- `docker-compose-utils.sh`: Docker Compose 명령 탐지 유틸(현재 일부 스크립트만 사용)

## 공통 전제

- Docker가 설치되어 있고 실행 중이어야 합니다.
- `docker compose`(권장) 또는 `docker-compose`(구버전) 중 하나가 필요합니다.
- 개발/운영 모두 설정은 `backend/.env`를 기준으로 동작합니다.

---

## 개발(로컬) 사용법

### 1) 백엔드 + Celery Worker 시작

```bash
./shell-script/dev-start-backend.sh
```

- API: `http://localhost:8000`
- 문서: `http://localhost:8000/docs`
- 스크립트가 `docker compose logs -f`로 로그를 계속 출력합니다.
- 종료: `Ctrl+C` → **backend / celery-worker만 stop** (DB/Redis는 유지)

로그만 다시 보고 싶으면:

```bash
docker compose -f docker-compose.yml logs -f --tail=100 backend celery-worker
```

### 2) 프론트엔드 시작

```bash
./shell-script/dev-start-frontend.sh
```

- 접속: `http://localhost:3000`
- 종료: `Ctrl+C` → **frontend만 stop**

로그만 다시 보고 싶으면:

```bash
docker compose -f docker-compose.yml logs -f --tail=100 frontend
```

### 3) 전체 종료(원하면)

개발에서 전체 스택을 내리고 싶으면 스크립트 대신 Compose를 직접 사용합니다.

```bash
docker compose -f docker-compose.yml down
```

---

## 운영(서버) 배포 사용법

운영 배포는 `docker-compose.prod.yml`을 대상으로 합니다. (스크립트 내부에서 해당 파일을 사용)

### up

```bash
./shell-script/deploy.sh up
```

### down

```bash
./shell-script/deploy.sh down
```

### restart

```bash
./shell-script/deploy.sh restart
```

### rebuild (이미지 재빌드 포함)

```bash
./shell-script/deploy.sh rebuild
```

### logs (기본 nginx, 특정 서비스 지정 가능)

```bash
./shell-script/deploy.sh logs
./shell-script/deploy.sh logs backend
./shell-script/deploy.sh logs celery-worker
```

### ps

```bash
./shell-script/deploy.sh ps
```

---

## 참고

- 이 디렉토리의 스크립트들은 **설정을 코드/Compose에 하드코딩하지 않고**, `backend/.env`를 “단일 진실 소스(SSOT)”로 두는 방향에 맞춰져 있습니다.
- 비밀키/토큰(AWS/Azure/Upstage 등)은 문서에 적지 말고 `backend/.env`에서 관리하세요.
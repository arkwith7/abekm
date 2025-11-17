# Docker 문제 해결 가이드

## 일반적인 Docker 문제들

### 1. 포트 충돌 문제

**증상:**
```
Error response from daemon: driver failed programming external connectivity on endpoint: bind for 0.0.0.0:3000 failed: port is already allocated
```

**해결책:**
```bash
# 포트 사용 중인 프로세스 확인
sudo netstat -tlnp | grep :3000
sudo lsof -i :3000

# 프로세스 종료
sudo kill -9 <PID>

# 또는 다른 포트 사용
FRONTEND_PORT=3001 docker-compose up -d
```

### 2. 권한 문제

**증상:**
```
Permission denied while trying to connect to the Docker daemon socket
```

**해결책:**
```bash
# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 재로그인 또는 새 세션 시작
newgrp docker

# Docker 서비스 재시작
sudo systemctl restart docker
```

### 3. 디스크 공간 부족

**증상:**
```
no space left on device
```

**해결책:**
```bash
# 디스크 사용량 확인
df -h
docker system df

# 불필요한 이미지, 컨테이너, 볼륨 정리
docker system prune -a
docker volume prune

# 빌드 캐시 정리
docker builder prune -a
```

### 4. 메모리 부족

**증상:**
- 컨테이너가 자주 재시작됨
- Out of Memory 오류

**해결책:**
```bash
# 메모리 사용량 확인
free -h
docker stats

# 컨테이너별 메모리 제한 설정
version: '3.8'
services:
  backend:
    mem_limit: 2g
    memswap_limit: 2g
  frontend:
    mem_limit: 1g
    memswap_limit: 1g
```

### 5. 네트워크 연결 문제

**증상:**
- 컨테이너 간 통신 실패
- 외부 네트워크 접근 불가

**해결책:**
```bash
# 네트워크 상태 확인
docker network ls
docker network inspect bridge

# 컨테이너 간 통신 테스트
docker-compose exec backend ping frontend
docker-compose exec backend nslookup frontend

# 네트워크 재생성
docker-compose down
docker network prune
docker-compose up -d
```

## 서비스별 문제 해결

### Backend (FastAPI) 문제

#### 1. 애플리케이션이 시작되지 않음

**진단:**
```bash
# 백엔드 로그 확인
docker-compose logs backend

# 컨테이너 상태 확인
docker-compose ps backend

# 컨테이너 내부 접속
docker-compose exec backend bash
```

**일반적인 원인과 해결:**
- **Python 패키지 설치 실패**: `requirements.txt` 확인
- **환경 변수 누락**: `.env` 파일 설정 확인
- **데이터베이스 연결 실패**: 데이터베이스 컨테이너 상태 확인

#### 2. 데이터베이스 연결 오류

**증상:**
```
sqlalchemy.exc.OperationalError: connection failed
```

**해결책:**
```bash
# PostgreSQL 컨테이너 상태 확인
docker-compose ps postgres
docker-compose logs postgres

# 데이터베이스 연결 테스트
docker-compose exec postgres psql -U wkms -d wkms -c "SELECT 1;"

# 환경 변수 확인
docker-compose exec backend env | grep -i db
```

#### 3. AI 서비스 연결 오류

**증상:**
```
Failed to connect to AI service
```

**해결책:**
```bash
# API 키 확인
docker-compose exec backend env | grep -i api_key

# 네트워크 연결 테스트
docker-compose exec backend curl -I https://api.openai.com
docker-compose exec backend curl -I https://bedrock.amazonaws.com

# 로그 확인
docker-compose logs backend | grep -i "ai\|llm\|bedrock\|openai"
```

### Frontend (React) 문제

#### 1. 빌드 실패

**증상:**
```
npm ERR! code ELIFECYCLE
```

**해결책:**
```bash
# Node.js 버전 확인
docker-compose exec frontend node --version

# 패키지 재설치
docker-compose exec frontend rm -rf node_modules package-lock.json
docker-compose exec frontend npm install

# 빌드 다시 시도
docker-compose restart frontend
```

#### 2. API 연결 실패

**증상:**
- 프론트엔드는 로드되지만 데이터가 표시되지 않음
- Network 탭에서 API 호출 실패 확인

**해결책:**
```bash
# 백엔드 상태 확인
curl http://localhost:8000/docs

# 환경 변수 확인
docker-compose exec frontend env | grep REACT_APP

# CORS 설정 확인 (백엔드)
docker-compose logs backend | grep -i cors
```

### Database (PostgreSQL) 문제

#### 1. 데이터베이스 시작 실패

**증상:**
```
database system was not properly shut down
```

**해결책:**
```bash
# 볼륨 상태 확인
docker volume ls | grep postgres

# 데이터베이스 복구 시도
docker-compose stop postgres
docker-compose start postgres

# 심각한 경우 데이터 재생성 (주의: 데이터 손실)
docker-compose down -v
docker-compose up -d postgres
```

#### 2. 성능 문제

**증상:**
- 쿼리 응답이 매우 느림
- 높은 CPU/메모리 사용률

**해결책:**
```sql
-- 느린 쿼리 확인
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- 인덱스 상태 확인
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch 
FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;
```

### Redis 문제

#### 1. Redis 연결 실패

**증상:**
```
ConnectionError: Error connecting to Redis
```

**해결책:**
```bash
# Redis 컨테이너 상태 확인
docker-compose ps redis
docker-compose logs redis

# Redis 연결 테스트
docker-compose exec redis redis-cli ping

# 메모리 사용량 확인
docker-compose exec redis redis-cli info memory
```

## 성능 최적화

### 1. Docker 이미지 최적화

```dockerfile
# 멀티스테이지 빌드 사용
FROM node:18-alpine AS frontend-build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --only=production
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
# 필요한 패키지만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*
```

### 2. 컨테이너 리소스 제한

```yaml
version: '3.8'
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 3. 볼륨 최적화

```yaml
volumes:
  # tmpfs 사용으로 성능 향상 (임시 데이터용)
  - type: tmpfs
    target: /tmp
    tmpfs:
      size: 100M
```

## 모니터링 및 로깅

### 1. 헬스체크 설정

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 2. 로그 관리

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 3. 메트릭 수집

```bash
# cAdvisor를 이용한 컨테이너 모니터링
docker run -d \
  --name=cadvisor \
  --port=8080:8080 \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  google/cadvisor:latest
```

## 백업 및 복구

### 1. 데이터베이스 백업

```bash
# 정기 백업 스크립트
#!/bin/bash
BACKUP_DIR="/backup"
DATE=$(date +%Y%m%d_%H%M%S)

# 데이터베이스 덤프
docker-compose exec -T postgres pg_dump -U wkms wkms > "${BACKUP_DIR}/db_backup_${DATE}.sql"

# 볼륨 백업
docker run --rm -v wkms_postgres_data:/data -v ${BACKUP_DIR}:/backup alpine \
  tar czf /backup/volume_backup_${DATE}.tar.gz -C /data .

# 오래된 백업 정리 (30일 이상)
find ${BACKUP_DIR} -name "*.sql" -mtime +30 -delete
find ${BACKUP_DIR} -name "*.tar.gz" -mtime +30 -delete
```

### 2. 복구

```bash
# 데이터베이스 복구
docker-compose exec -T postgres psql -U wkms wkms < backup_file.sql

# 볼륨 복구
docker-compose down
docker volume rm wkms_postgres_data
docker volume create wkms_postgres_data
docker run --rm -v wkms_postgres_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/volume_backup.tar.gz -C /data
docker-compose up -d
```

## 보안 체크리스트

### 1. 컨테이너 보안

- [ ] 루트 사용자로 실행하지 않음
- [ ] 최소한의 권한만 부여
- [ ] 불필요한 포트 노출 방지
- [ ] 시크릿을 환경변수가 아닌 Docker Secrets 사용

### 2. 네트워크 보안

- [ ] 내부 네트워크 사용
- [ ] 불필요한 외부 통신 차단
- [ ] HTTPS 사용 (프로덕션)

### 3. 이미지 보안

- [ ] 공식 베이스 이미지 사용
- [ ] 최신 보안 패치 적용
- [ ] 이미지 스캔 실행

```bash
# 이미지 취약점 스캔
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image your-image:tag
```

## 자주 묻는 질문 (FAQ)

### Q: Docker Compose가 너무 느려요
A: 다음 최적화를 시도해보세요:
- BuildKit 활성화: `DOCKER_BUILDKIT=1 docker-compose build`
- 병렬 빌드: `docker-compose build --parallel`
- 불필요한 파일 제외: `.dockerignore` 파일 작성

### Q: 컨테이너가 자주 재시작해요
A: 리소스 부족이 주원인입니다:
- 메모리 사용량 확인: `docker stats`
- 로그 확인: `docker-compose logs <service>`
- 리소스 제한 설정 검토

### Q: 개발 중 코드 변경이 반영되지 않아요
A: 볼륨 마운트 설정을 확인하세요:
```yaml
volumes:
  - ./backend:/app  # 로컬 디렉토리를 컨테이너에 마운트
```

더 자세한 정보는 [Docker 공식 문서](https://docs.docker.com/)를 참고하세요.

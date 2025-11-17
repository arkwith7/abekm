# Docker 배포 가이드

## 개요

이 문서는 AI 지식생성 플랫폼의 Docker 기반 배포 방법을 설명합니다.

## 🚀 빠른 시작

### 1. 기본 실행 (권장)

```bash
# 전체 서비스 자동 실행
docker-compose up --build -d

# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

### 2. 환경별 실행

```bash
# 개발 환경
docker-compose --env-file environments/.env.development up -d

# 스테이징 환경
docker-compose --env-file environments/.env.staging up -d

# 프로덕션 환경
docker-compose --env-file environments/.env.production up -d
```

## 📁 파일 구조

```
deployment/docker/
├── README.md                    # 이 파일
├── docker-compose.yml           # 메인 Docker Compose 설정
├── docker-compose.override.yml  # 개발용 오버라이드
├── docker-compose.prod.yml      # 프로덕션용 설정
├── environments/                # 환경별 설정 파일들
│   ├── .env.development        # 개발 환경 변수
│   ├── .env.staging           # 스테이징 환경 변수
│   └── .env.production        # 프로덕션 환경 변수
├── DOCKER_DEPLOYMENT_GUIDE.md  # 상세 배포 가이드
└── troubleshooting.md          # Docker 관련 문제 해결
```

## 🔧 환경 설정

### 환경 변수 파일 설정

#### 개발 환경 (`.env.development`)

```bash
# API 설정
REACT_APP_API_URL=http://localhost:8000
REACT_APP_ENV=development

# 데이터베이스 설정
DATABASE_URL=postgresql+asyncpg://wkms:wkms123@postgres:5432/wkms
DB_HOST=postgres
DB_USER=wkms
DB_PASSWORD=wkms123
DB_NAME=wkms
DB_PORT=5432

# Redis 설정
REDIS_URL=redis://redis:6379

# AI 서비스 설정
DEFAULT_LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
```

#### 스테이징 환경 (`.env.staging`)

```bash
# API 설정
REACT_APP_API_URL=http://your-staging-server:8000
REACT_APP_ENV=staging

# 데이터베이스 설정
DATABASE_URL=postgresql+asyncpg://wkms:secure_password@postgres:5432/wkms
DB_HOST=postgres
DB_USER=wkms
DB_PASSWORD=secure_password
DB_NAME=wkms
DB_PORT=5432

# Redis 설정
REDIS_URL=redis://redis:6379

# AI 서비스 설정
DEFAULT_LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=your-staging-api-key
AZURE_OPENAI_ENDPOINT=https://your-staging-openai.openai.azure.com/
```

#### 프로덕션 환경 (`.env.production`)

```bash
# API 설정
REACT_APP_API_URL=https://api.your-domain.com
REACT_APP_ENV=production

# 데이터베이스 설정 (외부 데이터베이스 사용 권장)
DATABASE_URL=postgresql+asyncpg://username:password@your-db-host:5432/database
DB_HOST=your-db-host
DB_USER=username
DB_PASSWORD=strong_password
DB_NAME=database
DB_PORT=5432

# Redis 설정 (외부 Redis 사용 권장)
REDIS_URL=redis://your-redis-host:6379

# AI 서비스 설정
DEFAULT_LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=your-production-api-key
AZURE_OPENAI_ENDPOINT=https://your-production-openai.openai.azure.com/
```

## 🐳 Docker Compose 파일들

### 메인 docker-compose.yml

기본적인 서비스 정의 및 개발 환경 설정이 포함되어 있습니다.

### docker-compose.override.yml (개발용)

개발 환경에서 자동으로 적용되는 오버라이드 설정:
- 볼륨 마운트로 실시간 코드 변경 반영
- 디버깅 포트 노출
- 개발용 환경 변수

### docker-compose.prod.yml (프로덕션용)

```bash
# 프로덕션 환경으로 실행
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🔄 일반적인 작업 흐름

### 1. 새로운 서버에서 첫 배포

```bash
# 1. 저장소 클론
git clone <repository-url>
cd InsightBridge

# 2. 환경에 맞는 설정 파일 준비
cp deployment/docker/environments/.env.production .env

# 3. 설정 파일 수정 (데이터베이스, API 키 등)
nano .env

# 4. 서비스 시작
docker-compose --env-file .env up -d --build

# 5. 서비스 확인
docker-compose ps
curl http://localhost:8000/docs
curl http://localhost:3000
```

### 2. 애플리케이션 업데이트

```bash
# 1. 최신 코드 가져오기
git pull

# 2. 이미지 재빌드 및 재시작
docker-compose up -d --build

# 3. 불필요한 이미지 정리
docker system prune -f
```

### 3. 백업 및 복원

```bash
# 데이터베이스 백업
docker-compose exec postgres pg_dump -U wkms wkms > backup_$(date +%Y%m%d_%H%M%S).sql

# 데이터베이스 복원
docker-compose exec -T postgres psql -U wkms wkms < backup_file.sql

# 볼륨 백업
docker run --rm -v wkms_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data_backup.tar.gz -C /data .
```

## 📊 모니터링

### 1. 로그 모니터링

```bash
# 전체 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
docker-compose logs -f redis

# 최근 100줄만 확인
docker-compose logs --tail=100 backend
```

### 2. 리소스 사용량 확인

```bash
# 컨테이너 리소스 사용량
docker stats

# 볼륨 사용량
docker system df

# 네트워크 상태
docker network ls
docker network inspect wkms_default
```

### 3. 헬스체크

```bash
# 백엔드 API 상태 확인
curl http://localhost:8000/health

# 프론트엔드 상태 확인
curl http://localhost:3000

# 데이터베이스 연결 확인
docker-compose exec backend python -c "
import asyncio
from app.database.connection import get_database
async def test():
    db = get_database()
    result = await db.fetch_one('SELECT 1 as test')
    print(f'DB OK: {result}')
asyncio.run(test())
"
```

## 🔧 고급 설정

### 1. Nginx 프록시 설정

```nginx
# nginx.conf 예시
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 2. SSL/TLS 설정

```yaml
# Let's Encrypt 인증서 자동 발급
version: '3.8'
services:
  nginx-proxy:
    image: jwilder/nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/tmp/docker.sock:ro
      - certs:/etc/nginx/certs:ro
      - vhost.d:/etc/nginx/vhost.d
      - html:/usr/share/nginx/html
    
  letsencrypt:
    image: jrcs/letsencrypt-nginx-proxy-companion
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - certs:/etc/nginx/certs:rw
      - vhost.d:/etc/nginx/vhost.d
      - html:/usr/share/nginx/html
```

### 3. 개발 환경 최적화

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  backend:
    volumes:
      - ./backend:/app
    environment:
      - PYTHONPATH=/app
      - RELOAD=true
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    
  frontend:
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - CHOKIDAR_USEPOLLING=true
    command: npm start
```

## 🚨 문제 해결

자세한 내용: [troubleshooting.md](./troubleshooting.md)

### 일반적인 문제들

- 포트 충돌 문제
- 권한 문제
- 메모리 부족
- 디스크 공간 부족
- 네트워크 연결 문제

### 유용한 디버깅 명령어

```bash
# 컨테이너 내부 접속
docker-compose exec backend bash
docker-compose exec frontend sh
docker-compose exec postgres psql -U wkms

# 컨테이너 재시작
docker-compose restart backend
docker-compose restart frontend

# 볼륨 초기화 (주의: 데이터 삭제됨)
docker-compose down -v
docker-compose up -d --build
```

## 📝 체크리스트

### 배포 전 점검사항

- [ ] 환경 변수 파일 설정 확인
- [ ] API 키 및 시크릿 설정
- [ ] 데이터베이스 연결 정보 확인
- [ ] 방화벽/보안그룹 설정
- [ ] 도메인 DNS 설정 (해당시)
- [ ] SSL 인증서 준비 (해당시)

### 배포 후 확인사항

- [ ] 모든 서비스 정상 시작 확인
- [ ] 프론트엔드 접속 확인
- [ ] 백엔드 API 응답 확인
- [ ] 데이터베이스 연결 확인
- [ ] AI 서비스 연동 확인
- [ ] 로그 정상 출력 확인

## 📚 추가 자료

- [Docker 공식 문서](https://docs.docker.com/)
- [Docker Compose 문서](https://docs.docker.com/compose/)
- [프로덕션 배포 모범 사례](https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/)
- [상세 배포 가이드](./DOCKER_DEPLOYMENT_GUIDE.md)
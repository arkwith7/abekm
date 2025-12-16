# Docker 컨테이너 배포 체크리스트

## ✅ 완료된 설정

### 1. 환경 변수 파일 구조
- ✅ 프로젝트 루트 `.env` 심볼릭 링크 제거
- ✅ `backend/.env` - 백엔드 전용 환경변수
- ✅ `frontend/.env` - 프론트엔드 전용 환경변수
- ✅ docker-compose.yml에 `env_file` 설정 추가
- ✅ docker-compose.prod.yml에 `env_file` 설정 추가

### 2. 하드코딩 경로 제거
- ✅ 모든 Python 파일에서 절대 경로 제거
- ✅ `Path(__file__).parent` 기반 동적 경로 사용
- ✅ 환경 변수를 통한 경로 오버라이드 가능

### 3. Docker Compose 구성
- ✅ Postgres (pgvector 지원)
- ✅ Redis
- ✅ Backend (FastAPI)
- ✅ Frontend (React)
- ✅ Nginx (포트 80)
- ✅ Office Generator Service

## 🔍 배포 전 점검 사항

### 1. 환경 변수 파일 확인
```bash
# Backend .env 확인
cat backend/.env | grep -E "^(DATABASE_URL|REDIS_URL|AWS_|AZURE_)"

# Frontend .env 확인
cat frontend/.env | grep -E "^REACT_APP_"
```

### 2. Docker 이미지 빌드 테스트
```bash
# 개발 환경
docker-compose build

# 프로덕션 환경
docker-compose -f docker-compose.prod.yml build
```

### 3. 컨테이너 시작 테스트
```bash
# 개발 환경
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```

### 4. 네트워크 연결 테스트
```bash
# Nginx 웹 접속 (포트 80)
curl http://localhost/

# Backend API 헬스체크
curl http://localhost/api/health

# Frontend 접속
curl http://localhost/ -I
```

### 5. 데이터베이스 초기화 확인
```bash
# Postgres 접속
docker exec -it abkms-postgres psql -U wkms -d wkms

# 테이블 확인
\dt

# 초기 데이터 확인
SELECT * FROM tb_user LIMIT 5;
```

## 📝 주요 설정 파일

### docker-compose.yml (개발용)
- Backend: `env_file: ./backend/.env`
- Frontend: `env_file: ./frontend/.env`
- Nginx: 포트 80:80

### docker-compose.prod.yml (프로덕션)
- Backend: `env_file: ./backend/.env`
- Frontend: `env_file: ./frontend/.env`
- Storage: S3 (STORAGE_BACKEND=s3)
- 로깅: JSON 형식, 10MB 제한

### nginx/nginx.conf
- Frontend: `proxy_pass http://frontend:3000`
- Backend: `proxy_pass http://backend:8000`
- Gzip 압축 활성화
- 보안 헤더 설정

## ⚠️ 주의 사항

1. **환경변수 우선순위**
   - docker-compose `environment` > `env_file` > 컨테이너 내부 기본값
   - 동일한 변수는 `environment`에서 명시적으로 오버라이드

2. **볼륨 마운트**
   - 개발: 소스 코드 마운트 (핫 리로드)
   - 프로덕션: Named 볼륨만 사용

3. **네트워크**
   - 모든 서비스가 `abkms-network` 브리지 네트워크 사용
   - 서비스 간 통신은 컨테이너 이름으로 가능 (예: `http://backend:8000`)

4. **데이터 지속성**
   - `abkms_postgres_data`: PostgreSQL 데이터
   - `abkms_redis_data`: Redis 데이터
   - `abkms_backend_uploads`: 업로드 파일

## 🚀 배포 명령어

### 개발 환경 시작
```bash
docker-compose up -d
```

### 프로덕션 환경 시작
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 중지 및 정리
```bash
# 중지
docker-compose down

# 볼륨까지 삭제 (주의!)
docker-compose down -v
```

### 재시작
```bash
# 특정 서비스만 재시작
docker-compose restart backend

# 전체 재시작
docker-compose restart
```

## 🐛 트러블슈팅

### 1. 환경 변수가 로드되지 않는 경우
```bash
# env_file 경로 확인
docker-compose config

# 컨테이너 내부 환경변수 확인
docker exec abkms-backend env | grep DATABASE_URL
```

### 2. Nginx 502 Bad Gateway
```bash
# Backend 상태 확인
docker-compose logs backend

# 네트워크 연결 확인
docker exec abkms-nginx ping backend
```

### 3. 데이터베이스 연결 실패
```bash
# Postgres 로그 확인
docker-compose logs postgres

# 연결 테스트
docker exec abkms-postgres pg_isready -U wkms
```


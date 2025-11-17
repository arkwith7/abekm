# WKMS Docker 컨테이너 기반 배포 가이드

## 📋 개요

이 가이드는 WKMS 애플리케이션을 Docker 컨테이너 기반으로 AWS/Azure에 배포하는 방법을 설명합니다.

## 🏗️ 아키텍처

```
[Nginx] → [React Frontend] → [FastAPI Backend] → [PostgreSQL + Redis]
   ↑            ↑                    ↑              ↑
 Port 80    Port 3000           Port 8000      Port 5432,6379
```

## 🚀 로컬 개발 환경 실행

### 방법 1: Docker Compose (권장)

```bash
# 개발 환경 시작
./dev-start-docker.sh

# 또는 직접 실행
docker compose up -d
```

### 방법 2: 기존 방식 (개별 실행)

```bash
# 데이터베이스만 Docker로 실행
./dev-start-db.sh

# 백엔드 로컬 실행
./dev-start-backend.sh

# 프론트엔드 로컬 실행
./dev-start-frontend.sh
```

## 🌐 프로덕션 배포

### 1. 환경 설정

```bash
# 환경 변수 파일 복사 및 수정
cp .env.production.example .env.production
vi .env.production
```

### 2. 프로덕션 배포 실행

```bash
./deploy-production.sh
```

## ☁️ 클라우드 플랫폼 배포

### AWS ECS 배포

1. **ECR 레지스트리 생성**
2. **이미지 빌드 및 푸시**
3. **ECS 클러스터 및 서비스 구성**
4. **RDS/ElastiCache 연결**

### Azure Container Instances 배포

1. **Azure Container Registry 생성**
2. **이미지 빌드 및 푸시**
3. **Container Group 구성**
4. **Azure Database for PostgreSQL 연결**

### Docker Swarm 배포

```bash
# 스웜 모드 초기화
docker swarm init

# 스택 배포
docker stack deploy -c docker-compose.prod.yml wkms
```

## 🔧 설정 가이드

### 환경 변수 설정

- `.env.production`: 프로덕션 환경용
- `.env.docker.local`: 로컬 Docker 환경용
- `.env.docker.staging`: 스테이징 환경용

### SSL/TLS 설정

```bash
# Let's Encrypt 인증서 (예시)
mkdir -p nginx/ssl
# 인증서 파일 복사
# nginx/ssl/cert.pem
# nginx/ssl/key.pem
```

## 📊 모니터링 및 로그

### 컨테이너 상태 확인

```bash
docker compose ps
docker compose logs -f [service_name]
```

### 헬스체크

- Nginx: http://localhost/health
- Backend: http://localhost/api/health
- Frontend: http://localhost

## 🔒 보안 고려사항

1. **환경 변수**: 민감한 정보는 Docker Secrets 사용
2. **네트워크**: 내부 통신용 별도 네트워크 구성
3. **방화벽**: 필요한 포트만 외부 노출
4. **인증서**: HTTPS 적용 권장

## 🚨 트러블슈팅

### 일반적인 문제

1. **포트 충돌**: 기존 서비스와 포트 충돌 시 docker-compose.yml 수정
2. **메모리 부족**: Docker Desktop 메모리 할당량 증가
3. **권한 문제**: Docker 그룹에 사용자 추가

### 로그 확인

```bash
# 전체 로그
docker compose logs

# 특정 서비스 로그
docker compose logs backend
docker compose logs frontend
```

## 📝 참고 자료

- [Docker Compose 문서](https://docs.docker.com/compose/)
- [AWS ECS 가이드](https://docs.aws.amazon.com/ecs/)
- [Azure Container Instances](https://docs.microsoft.com/azure/container-instances/)
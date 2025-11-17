# 환경 변수 관리 전략 가이드

## 📁 파일 구조 및 역할

### 1. `.env.example` - 템플릿 파일
- 모든 가능한 환경 변수의 예시
- 민감하지 않은 기본값 포함
- 버전 관리에 포함

### 2. `.env.local` - 로컬 개발 환경
- 개발자 개인 설정
- localhost 기반 연결 정보
- 개발용 AWS/Azure 계정 정보

### 3. `.env.docker` - Docker 개발 환경  
- Docker Compose 개발용
- 컨테이너 간 서비스 이름 사용
- 개발용 설정

### 4. `.env.production` - 프로덕션 환경
- 실제 배포 환경용
- 보안 강화 설정
- 실제 도메인/서비스 정보

## 🔄 사용 방식

### 로컬 개발 (기존 방식)
```bash
# backend/.env 사용
./dev-start-backend.sh
```

### Docker 개발 환경
```bash
# .env.docker 사용
docker compose --env-file .env.docker up
```

### 프로덕션 배포
```bash
# .env.production 사용  
docker compose -f docker-compose.prod.yml --env-file .env.production up
```
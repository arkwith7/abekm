# AI 지식생성 플랫폼 - 배포 가이드

## 📋 개요

이 디렉토리는 AI 지식생성 플랫폼의 다양한 배포 환경에 대한 설정과 가이드를 포함합니다.

## 📁 디렉토리 구조

```
deployment/
├── README.md              # 이 파일 - 배포 개요
├── docker/               # Docker 기반 배포
│   ├── README.md         # Docker 배포 상세 가이드
│   ├── docker-compose.yml         # 메인 Docker Compose 설정
│   ├── docker-compose.prod.yml    # 프로덕션용 설정
│   ├── environments/              # 환경별 설정 파일
│   │   ├── .env.development      # 개발 환경
│   │   ├── .env.staging         # 스테이징 환경
│   │   └── .env.production      # 프로덕션 환경
│   ├── DOCKER_DEPLOYMENT_GUIDE.md # 기존 상세 가이드
│   └── troubleshooting.md        # Docker 관련 문제 해결
├── cloud/                # 클라우드 배포 설정
│   ├── aws-setup.md      # AWS 클라우드 설정
│   ├── azure-setup.md    # Azure 클라우드 설정
│   └── architecture.md   # 클라우드 아키텍처
└── local/                # 로컬 개발 환경
    ├── development-setup.md    # 로컬 개발 환경 설정
    └── environment-config.md   # 환경 변수 설정
```

## 🚀 배포 옵션 선택 가이드

### 1. 🐳 Docker 기반 배포 (권장)
**적합한 경우:**
- 빠른 프로토타이핑 및 개발
- 중소규모 운영 환경
- 단일 서버 배포
- 개발팀 내부 테스트

**장점:**
- 설정이 간단함
- 빠른 배포 가능
- 환경 일관성 보장
- 로컬 개발과 동일한 환경

**시작하기:** [docker/README.md](./docker/README.md)

### 2. ☸️ 쿠버네티스 배포
**적합한 경우:**
- 대규모 프로덕션 환경
- 자동 확장이 필요한 경우
- 높은 가용성 요구
- 마이크로서비스 아키텍처

**장점:**
- 자동 확장 및 복구
- 로드 밸런싱
- 서비스 디스커버리
- 롤링 업데이트

**시작하기:** [../k8s/README.md](../k8s/README.md)

### 3. ☁️ 클라우드 네이티브 배포
**적합한 경우:**
- 클라우드 서비스 완전 활용
- 관리형 서비스 선호
- 글로벌 서비스 제공
- 엔터프라이즈급 운영

**장점:**
- 관리 오버헤드 최소화
- 클라우드 서비스 통합
- 자동 백업 및 복구
- 글로벌 CDN 활용

**시작하기:** [cloud/](./cloud/)

## ⚡ 빠른 배포 가이드

### Docker로 즉시 시작 (5분)
```bash
# 저장소 클론
git clone <repository-url>
cd InsightBridge

# 환경 설정 (선택사항)
cp deployment/docker/environments/.env.development .env

# 서비스 시작
docker-compose up -d

# 접속 확인
open http://localhost:3000
```

### 쿠버네티스 배포 (15분)
```bash
# 이미지 빌드 및 푸시 (registry 설정 필요)
docker build -t your-registry/wkms-backend:latest ./backend
docker build -t your-registry/wkms-frontend:latest ./frontend
docker push your-registry/wkms-backend:latest
docker push your-registry/wkms-frontend:latest

# 쿠버네티스 배포
kubectl apply -f k8s/00-namespace-config.yaml
kubectl apply -f k8s/04-database.yaml
kubectl apply -f k8s/01-backend.yaml
kubectl apply -f k8s/02-frontend.yaml
kubectl apply -f k8s/03-ingress.yaml

# 상태 확인
kubectl get pods -n wkms
```

## 🔧 환경별 설정 가이드

### 개발 환경
- **목적**: 로컬 개발 및 테스트
- **특징**: 자동 리로딩, 디버깅 포트 오픈, 개발용 데이터
- **배포**: Docker Compose 사용
- **설정**: `.env.development`

### 스테이징 환경  
- **목적**: 프로덕션 배포 전 최종 검증
- **특징**: 프로덕션과 유사한 환경, 테스트 데이터
- **배포**: Docker Compose 또는 쿠버네티스
- **설정**: `.env.staging`

### 프로덕션 환경
- **목적**: 실제 서비스 운영
- **특징**: 고가용성, 자동 확장, 보안 강화
- **배포**: 쿠버네티스 (권장) 또는 관리형 서비스
- **설정**: `.env.production`

## 📊 리소스 요구사항

### 최소 요구사항 (개발/테스트)
- **CPU**: 2 cores
- **메모리**: 4GB RAM
- **스토리지**: 20GB
- **네트워크**: 인터넷 연결

### 권장 요구사항 (프로덕션)
- **CPU**: 4+ cores
- **메모리**: 8GB+ RAM
- **스토리지**: 100GB+ SSD
- **네트워크**: 고속 인터넷, 로드 밸런서

### 대규모 환경 (엔터프라이즈)
- **CPU**: 8+ cores (멀티 노드)
- **메모리**: 16GB+ RAM
- **스토리지**: 500GB+ SSD (분산 스토리지)
- **네트워크**: 전용선, CDN

## 🔐 보안 고려사항

### 개발 환경
- 기본 패스워드 변경
- 개발용 API 키 사용
- HTTP 허용 (로컬만)

### 프로덕션 환경  
- 강력한 패스워드 정책
- 프로덕션 API 키 관리
- HTTPS 필수
- 방화벽 설정
- 정기 보안 업데이트

## 🚨 문제 해결

### 공통 문제들

#### 1. 포트 충돌
```bash
# 사용 중인 포트 확인
netstat -tlnp | grep :3000
netstat -tlnp | grep :8000

# 다른 포트로 변경
FRONTEND_PORT=3001 BACKEND_PORT=8001 docker-compose up -d
```

#### 2. 메모리 부족
```bash
# Docker 메모리 사용량 확인
docker stats

# 불필요한 컨테이너 정리
docker system prune -a
```

#### 3. 네트워크 연결 문제
```bash
# Docker 네트워크 확인
docker network ls
docker network inspect <network-name>

# 컨테이너 간 통신 테스트
docker-compose exec backend ping frontend
```

### 각 배포 유형별 상세 문제 해결
- **Docker**: [docker/troubleshooting.md](./docker/troubleshooting.md)
- **쿠버네티스**: [../k8s/troubleshooting/](../k8s/troubleshooting/)
- **클라우드**: [cloud/troubleshooting.md](./cloud/troubleshooting.md)

## 📈 모니터링 및 로깅

### 기본 모니터링
```bash
# 서비스 상태 확인
docker-compose ps                    # Docker 환경
kubectl get pods -n wkms            # 쿠버네티스 환경

# 로그 확인
docker-compose logs -f              # Docker 환경  
kubectl logs -f deployment/wkms-backend -n wkms  # 쿠버네티스 환경

# 리소스 사용량
docker stats                        # Docker 환경
kubectl top nodes && kubectl top pods -n wkms    # 쿠버네티스 환경
```

### 고급 모니터링
- **Prometheus + Grafana**: 메트릭 수집 및 시각화
- **ELK Stack**: 중앙화된 로그 관리
- **Jaeger**: 분산 추적
- **AlertManager**: 알림 시스템

## 🔄 CI/CD 통합

### GitHub Actions 예시
```yaml
name: Deploy to Production
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Deploy to Docker
      run: |
        docker-compose -f docker-compose.prod.yml up -d --build
```

### Jenkins 파이프라인
```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh 'docker-compose build'
            }
        }
        stage('Deploy') {
            steps {
                sh 'docker-compose up -d'
            }
        }
    }
}
```

## 📚 추가 자료

- [Docker 공식 문서](https://docs.docker.com/)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)
- [AWS 배포 가이드](https://aws.amazon.com/getting-started/)
- [Azure 배포 가이드](https://docs.microsoft.com/azure/)
- [Google Cloud 배포 가이드](https://cloud.google.com/docs/)

## 📞 지원

배포 관련 문제가 발생하면:
1. 해당 배포 유형의 README.md 및 troubleshooting.md 참고
2. 로그 확인 및 오류 메시지 수집
3. 커뮤니티 또는 기술 지원팀에 문의

---

**성공적인 배포를 위해 환경에 맞는 가이드를 선택하여 따라해보세요! 🚀**

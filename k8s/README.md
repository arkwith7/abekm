# AI 지식생성 플랫폼 - 쿠버네티스 배포 가이드

## 📋 개요

이 디렉토리는 AI 지식생성 플랫폼의 쿠버네티스 배포와 관련된 모든 설정 및 가이드를 포함합니다.

## 📁 디렉토리 구조

```
k8s/
├── README.md                           # 이 파일 - 쿠버네티스 배포 개요
├── *.yaml                             # 쿠버네티스 매니페스트 파일들
├── deployment-guides/                  # 클라우드별 배포 가이드
│   ├── eks-deployment.md              # AWS EKS 배포 가이드
│   ├── aks-deployment.md              # Azure AKS 배포 가이드
│   ├── gke-deployment.md              # Google GKE 배포 가이드
│   └── local-k8s.md                  # 로컬 쿠버네티스 배포
├── configs/                           # 환경별 설정 및 모니터링
│   ├── environment/                   # 환경별 설정
│   │   ├── dev/                      # 개발 환경 설정
│   │   ├── staging/                  # 스테이징 환경 설정
│   │   └── production/               # 프로덕션 환경 설정
│   └── monitoring/                   # 모니터링 설정 (Prometheus, Grafana)
└── troubleshooting/                   # 문제 해결 가이드
    ├── common-issues.md              # 일반적인 문제 해결
    └── performance-tuning.md         # 성능 튜닝 가이드
```

## 🚀 빠른 시작

### 1. 매니페스트 파일들

| 파일                         | 설명                        |
| -------------------------- | ------------------------- |
| `00-namespace-config.yaml` | 네임스페이스 및 기본 설정            |
| `01-backend.yaml`          | FastAPI 백엔드 배포            |
| `02-frontend.yaml`         | React 프론트엔드 배포            |
| `03-ingress.yaml`          | 인그레스 및 외부 접근 설정           |
| `04-database.yaml`         | PostgreSQL + Redis 데이터베이스 |
| `05-eks-specific.yaml`     | AWS EKS 특화 설정             |
| `06-aks-specific.yaml`     | Azure AKS 특화 설정           |

### 2. 배포 순서

```bash
# 1. 네임스페이스 및 설정
kubectl apply -f 00-namespace-config.yaml

# 2. 데이터베이스 먼저 배포
kubectl apply -f 04-database.yaml

# 3. 백엔드 애플리케이션
kubectl apply -f 01-backend.yaml

# 4. 프론트엔드 애플리케이션
kubectl apply -f 02-frontend.yaml

# 5. 외부 접근 설정
kubectl apply -f 03-ingress.yaml

# 6. 클라우드별 특화 설정 (선택)
kubectl apply -f 05-eks-specific.yaml  # AWS EKS 사용시
kubectl apply -f 06-aks-specific.yaml  # Azure AKS 사용시
```

## ☁️ 클라우드별 배포 가이드

### AWS EKS

자세한 내용: [deployment-guides/eks-deployment.md](./deployment-guides/eks-deployment.md)
- EKS 클러스터 생성
- ECR 이미지 관리  
- AWS Load Balancer Controller
- CloudWatch 통합

### Azure AKS  

자세한 내용: [deployment-guides/aks-deployment.md](./deployment-guides/aks-deployment.md)
- AKS 클러스터 생성
- ACR 이미지 관리
- Application Gateway Ingress
- Azure Monitor 통합

### Google GKE

자세한 내용: [deployment-guides/gke-deployment.md](./deployment-guides/gke-deployment.md)
- GKE 클러스터 생성
- Container Registry 관리
- Google Cloud Load Balancer
- Operations Suite 통합

### 로컬 쿠버네티스

자세한 내용: [deployment-guides/local-k8s.md](./deployment-guides/local-k8s.md)
- minikube, kind, Docker Desktop
- 로컬 개발 환경 설정

## 🔧 환경 설정

### 개발 환경

```bash
# 개발용 설정 적용
kubectl apply -f configs/environment/dev/
```

### 스테이징 환경

```bash
# 스테이징용 설정 적용
kubectl apply -f configs/environment/staging/
```

### 프로덕션 환경

```bash
# 프로덕션용 설정 적용
kubectl apply -f configs/environment/production/
```

## 📊 모니터링

### Prometheus & Grafana 설정

```bash
# 모니터링 스택 배포
kubectl apply -f configs/monitoring/
```

자세한 내용: [configs/monitoring/README.md](./configs/monitoring/README.md)

## 🔍 문제 해결

### 일반적인 문제들

자세한 내용: [troubleshooting/common-issues.md](./troubleshooting/common-issues.md)

- Pod 시작 실패
- 이미지 풀링 문제
- 서비스 간 통신 문제
- 스토리지 문제

### 성능 튜닝

자세한 내용: [troubleshooting/performance-tuning.md](./troubleshooting/performance-tuning.md)

- 리소스 할당 최적화
- 자동 확장 설정
- 네트워크 성능 튜닝

## 📝 유용한 명령어들

### 기본 모니터링

```bash
# 전체 리소스 상태 확인
kubectl get all -n wkms

# Pod 로그 확인
kubectl logs -f deployment/wkms-backend -n wkms
kubectl logs -f deployment/wkms-frontend -n wkms

# 리소스 사용량 확인
kubectl top nodes
kubectl top pods -n wkms
```

### 디버깅

```bash
# Pod 세부 정보 확인
kubectl describe pod <pod-name> -n wkms

# 서비스 엔드포인트 확인
kubectl get endpoints -n wkms

# 이벤트 확인
kubectl get events -n wkms --sort-by='.lastTimestamp'
```

## 🔄 업데이트 및 롤백

### 애플리케이션 업데이트

```bash
# 이미지 업데이트
kubectl set image deployment/wkms-backend backend=your-registry/wkms-backend:v2.0.0 -n wkms

# 롤아웃 상태 확인
kubectl rollout status deployment/wkms-backend -n wkms

# 롤백
kubectl rollout undo deployment/wkms-backend -n wkms
```

### 설정 업데이트

```bash
# ConfigMap 업데이트
kubectl apply -f 00-namespace-config.yaml

# Pod 재시작으로 설정 반영
kubectl rollout restart deployment/wkms-backend -n wkms
kubectl rollout restart deployment/wkms-frontend -n wkms
```

## 🧹 정리

### 전체 애플리케이션 삭제

```bash
kubectl delete namespace wkms
```

### 개별 리소스 삭제

```bash
kubectl delete -f 03-ingress.yaml
kubectl delete -f 02-frontend.yaml
kubectl delete -f 01-backend.yaml
kubectl delete -f 04-database.yaml
kubectl delete -f 00-namespace-config.yaml
```

## 📚 추가 자료

- [Kubernetes 공식 문서](https://kubernetes.io/docs/)
- [Helm 차트 사용법](https://helm.sh/docs/)
- [Kustomize를 이용한 설정 관리](https://kustomize.io/)
# AKS/EKS 배포 가이드

## 🎯 AKS/EKS 배포 준비 완료

### ✅ 수정 완료 사항

1. **보안 컨텍스트 추가**: 모든 컨테이너에 비특권 실행 설정
2. **Ingress 현대화**: deprecated 어노테이션 제거, ingressClassName 사용
3. **스토리지 클래스 설정**: 클라우드별 최적화된 스토리지 클래스 준비
4. **LoadBalancer 서비스**: 클라우드 네이티브 로드밸런서 지원 추가
5. **환경별 ConfigMap**: EKS/AKS 특화 설정 분리

## 🚀 EKS 배포 (Amazon Web Services)

### 사전 준비사항

```bash
# AWS CLI 및 eksctl 설치 확인
aws --version
eksctl version

# kubectl 설치 확인  
kubectl version --client

# EKS 클러스터 생성 (예시)
eksctl create cluster --name wkms-cluster --region us-west-2 --nodegroup-name standard-workers --node-type t3.medium --nodes 3
```

### 1단계: 네임스페이스 및 기본 설정

```bash
# 기본 매니페스트 적용
kubectl apply -f k8s/00-namespace-config.yaml

# EKS 특화 설정 적용 (선택)
kubectl apply -f k8s/05-eks-specific.yaml
```

### 2단계: 스토리지 및 데이터베이스

```bash
# PostgreSQL용 스토리지 클래스 설정 (gp3 권장)
kubectl patch storageclass gp2 -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'

# 데이터베이스 배포
kubectl apply -f k8s/04-database.yaml
```

### 3단계: 애플리케이션 배포

```bash
# 컨테이너 이미지 ECR에 푸시
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-west-2.amazonaws.com

# 이미지 태그 변경 (매니페스트에서)
# image: wkms-backend:latest → image: 123456789012.dkr.ecr.us-west-2.amazonaws.com/wkms-backend:latest

# 백엔드 및 프론트엔드 배포
kubectl apply -f k8s/01-backend.yaml
kubectl apply -f k8s/02-frontend.yaml
```

### 4단계: 외부 접근 설정

```bash
# Nginx Ingress Controller 설치 (선택)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/aws/deploy.yaml

# 또는 AWS Load Balancer Controller 사용
kubectl apply -f k8s/03-ingress.yaml  # 기본 Nginx Ingress
# kubectl apply -f k8s/05-eks-specific.yaml  # ALB Ingress (주석 해제 후)
```

### EKS 특화 최적화

```bash
# IRSA (IAM Roles for Service Accounts) 설정
eksctl create iamserviceaccount \
  --cluster=wkms-cluster \
  --namespace=wkms \
  --name=wkms-backend-sa \
  --attach-policy-arn=arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
  --approve

# AWS Load Balancer Controller 설치
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=wkms-cluster
```

## 🌐 AKS 배포 (Microsoft Azure)

### 사전 준비사항

```bash
# Azure CLI 설치 확인
az --version

# kubectl 설치 확인
kubectl version --client

# AKS 클러스터 생성 (예시)
az group create --name wkms-rg --location eastus
az aks create --resource-group wkms-rg --name wkms-cluster --node-count 3 --enable-addons monitoring --generate-ssh-keys
az aks get-credentials --resource-group wkms-rg --name wkms-cluster
```

### 1단계: 네임스페이스 및 기본 설정

```bash
# 기본 매니페스트 적용
kubectl apply -f k8s/00-namespace-config.yaml

# AKS 특화 설정 적용 (선택)
kubectl apply -f k8s/06-aks-specific.yaml
```

### 2단계: 스토리지 및 데이터베이스

```bash
# Azure 스토리지 클래스 확인
kubectl get storageclass

# 데이터베이스 배포 
kubectl apply -f k8s/04-database.yaml
```

### 3단계: 애플리케이션 배포

```bash
# ACR에 이미지 푸시
az acr login --name myregistry

# 이미지 태그 변경 (매니페스트에서)
# image: wkms-backend:latest → image: myregistry.azurecr.io/wkms-backend:latest

# 백엔드 및 프론트엔드 배포
kubectl apply -f k8s/01-backend.yaml
kubectl apply -f k8s/02-frontend.yaml
```

### 4단계: 외부 접근 설정

```bash
# Nginx Ingress Controller 설치
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace

# 또는 Application Gateway Ingress Controller 사용
kubectl apply -f k8s/03-ingress.yaml  # 기본 Nginx Ingress
# kubectl apply -f k8s/06-aks-specific.yaml  # AGIC (주석 해제 후)
```

### AKS 특화 최적화

```bash
# Workload Identity 설정 (권장)
az aks update --resource-group wkms-rg --name wkms-cluster --enable-workload-identity --enable-oidc-issuer

# Azure Key Vault CSI Secret Store Driver 설치
helm repo add csi-secrets-store-provider-azure https://azure.github.io/secrets-store-csi-driver-provider-azure/charts
helm install csi csi-secrets-store-provider-azure/csi-secrets-store-provider-azure --namespace kube-system
```

## 🔍 배포 검증

### 상태 확인

```bash
# Pod 상태 확인
kubectl get pods -n wkms

# 서비스 확인
kubectl get svc -n wkms

# Ingress 확인
kubectl get ingress -n wkms

# 로그 확인
kubectl logs -f deployment/wkms-backend -n wkms
kubectl logs -f deployment/wkms-frontend -n wkms
```

### 연결 테스트

```bash
# 포트 포워딩으로 로컬 테스트
kubectl port-forward svc/wkms-frontend 8080:80 -n wkms
kubectl port-forward svc/wkms-backend 8001:8000 -n wkms

# 브라우저에서 접근
# http://localhost:8080 (프론트엔드)
# http://localhost:8001 (백엔드 API)
```

## ⚙️ 환경별 설정 선택

### 기본 설정 사용 (Simple)

```bash
kubectl apply -f k8s/00-namespace-config.yaml
kubectl apply -f k8s/04-database.yaml
kubectl apply -f k8s/01-backend.yaml
kubectl apply -f k8s/02-frontend.yaml
kubectl apply -f k8s/03-ingress.yaml
```

### EKS 최적화 설정

```bash
kubectl apply -f k8s/00-namespace-config.yaml
kubectl apply -f k8s/05-eks-specific.yaml  # EKS ConfigMap으로 대체
kubectl apply -f k8s/04-database.yaml
kubectl apply -f k8s/01-backend.yaml
kubectl apply -f k8s/02-frontend.yaml
# ALB 사용시 05-eks-specific.yaml의 Ingress 부분 주석 해제 후 적용
```

### AKS 최적화 설정

```bash
kubectl apply -f k8s/00-namespace-config.yaml
kubectl apply -f k8s/06-aks-specific.yaml  # AKS ConfigMap으로 대체
kubectl apply -f k8s/04-database.yaml
kubectl apply -f k8s/01-backend.yaml
kubectl apply -f k8s/02-frontend.yaml
# AGIC 사용시 06-aks-specific.yaml의 Ingress 부분 주석 해제 후 적용
```

## 🛡️ 보안 고려사항

1. **시크릿 관리**: 하드코딩된 시크릿을 클라우드 시크릿 관리자로 교체
2. **네트워크 정책**: 필요시 NetworkPolicy 추가
3. **RBAC**: 서비스 계정별 최소 권한 부여
4. **이미지 보안**: 취약점 스캔 및 최신 이미지 사용
5. **SSL/TLS**: 인증서 자동 갱신 설정

## 📊 모니터링 및 로깅

1. **Prometheus + Grafana**: 메트릭 수집 및 시각화
2. **Fluentd/Fluent Bit**: 로그 수집 및 중앙화
3. **Jaeger**: 분산 추적 (선택사항)
4. **Azure Monitor/CloudWatch**: 클라우드 네이티브 모니터링

이제 AKS와 EKS 모두에서 안전하고 효율적으로 배포할 수 있는 상태입니다!
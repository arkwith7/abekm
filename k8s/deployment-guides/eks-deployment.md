# AWS EKS 배포 가이드

## 개요

이 문서는 AI 지식생성 플랫폼을 AWS EKS(Elastic Kubernetes Service)에 배포하는 방법을 설명합니다.

## 사전 준비사항

### 1. AWS CLI 및 도구 설치
```bash
# AWS CLI 설치 및 설정
aws configure

# eksctl 설치
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# kubectl 설치
kubectl version --client
```

### 2. ECR 리포지토리 생성
```bash
# ECR 리포지토리 생성
aws ecr create-repository --repository-name wkms-backend --region ap-northeast-2
aws ecr create-repository --repository-name wkms-frontend --region ap-northeast-2
```

## EKS 클러스터 생성

### 1. 클러스터 생성
```bash
# EKS 클러스터 생성
eksctl create cluster --name wkms-cluster --region ap-northeast-2 --version 1.27 --nodegroup-name wkms-nodes --node-type t3.medium --nodes 2 --nodes-min 1 --nodes-max 4

# kubectl 컨텍스트 설정
aws eks update-kubeconfig --region ap-northeast-2 --name wkms-cluster
```

### 2. AWS Load Balancer Controller 설치
```bash
# OIDC 프로바이더 생성
eksctl utils associate-iam-oidc-provider --cluster wkms-cluster --region ap-northeast-2 --approve

# AWS Load Balancer Controller 설치
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller/crds?ref=master"
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=wkms-cluster
```

## 이미지 빌드 및 푸시

### 1. ECR 로그인
```bash
aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com
```

### 2. 이미지 빌드 및 푸시
```bash
# 백엔드 이미지
docker build -t 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/wkms-backend:latest ./backend
docker push 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/wkms-backend:latest

# 프론트엔드 이미지
docker build -t 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/wkms-frontend:latest ./frontend
docker push 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/wkms-frontend:latest
```

## 애플리케이션 배포

### 1. 네임스페이스 및 설정
```bash
kubectl apply -f ../00-namespace-config.yaml
```

### 2. 데이터베이스 배포
```bash
kubectl apply -f ../04-database.yaml
```

### 3. 애플리케이션 배포
```bash
# 백엔드 배포
kubectl apply -f ../01-backend.yaml

# 프론트엔드 배포
kubectl apply -f ../02-frontend.yaml

# 인그레스 배포
kubectl apply -f ../03-ingress.yaml
```

### 4. EKS 특화 설정
```bash
kubectl apply -f ../05-eks-specific.yaml
```

## 모니터링 및 로깅

### 1. CloudWatch Container Insights 설정
```bash
# Fluent Bit 설치
kubectl apply -f https://raw.githubusercontent.com/aws/amazon-cloudwatch-agent/master/k8s-deploy-files/fluentbit/fluent-bit.yaml
```

### 2. 메트릭 서버 설치
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

## 자동 확장 설정

### 1. Cluster Autoscaler 설치
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
kubectl patch deployment cluster-autoscaler -n kube-system -p '{"spec":{"template":{"metadata":{"annotations":{"cluster-autoscaler.kubernetes.io/safe-to-evict": "false"}}}}}'
kubectl patch deployment cluster-autoscaler -n kube-system --type='merge' -p='{"spec":{"template":{"spec":{"containers":[{"name":"cluster-autoscaler","command":["./cluster-autoscaler","--v=4","--stderrthreshold=info","--cloud-provider=aws","--skip-nodes-with-local-storage=false","--expander=least-waste","--node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/wkms-cluster"]}]}}}}'
```

### 2. HPA 설정
```bash
kubectl get hpa -n wkms
```

## 보안 설정

### 1. RBAC 설정
```bash
# 서비스 어카운트 및 역할 생성
kubectl apply -f ../configs/security/rbac.yaml
```

### 2. Network Policies 적용
```bash
kubectl apply -f ../configs/security/network-policies.yaml
```

## 도메인 및 SSL 설정

### 1. Route 53 설정
```bash
# 도메인 레코드 생성
aws route53 change-resource-record-sets --hosted-zone-id Z123456789 --change-batch file://dns-changes.json
```

### 2. cert-manager 설치
```bash
kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.12.0/cert-manager.yaml
```

## 문제 해결

### 일반적인 문제들

1. **Pod가 시작되지 않는 경우**
   ```bash
   kubectl describe pod <pod-name> -n wkms
   kubectl logs <pod-name> -n wkms
   ```

2. **LoadBalancer 서비스가 External IP를 받지 못하는 경우**
   - AWS Load Balancer Controller가 올바르게 설치되었는지 확인
   - 보안 그룹 설정 확인

3. **이미지 풀링 실패**
   - ECR 권한 확인
   - 이미지 태그 확인

### 유용한 명령어들

```bash
# 클러스터 상태 확인
kubectl get nodes
kubectl get pods -A

# EKS 클러스터 정보
eksctl get cluster

# 로그 확인
kubectl logs -f deployment/wkms-backend -n wkms
kubectl logs -f deployment/wkms-frontend -n wkms
```

## 정리 및 삭제

### 클러스터 삭제
```bash
# 애플리케이션 삭제
kubectl delete -f ../

# 클러스터 삭제
eksctl delete cluster --name wkms-cluster --region ap-northeast-2
```

## 참고 자료

- [AWS EKS 공식 문서](https://docs.aws.amazon.com/eks/)
- [eksctl 문서](https://eksctl.io/)
- [AWS Load Balancer Controller 설치 가이드](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)

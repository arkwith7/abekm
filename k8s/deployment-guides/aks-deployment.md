# Azure AKS 배포 가이드

## 개요

이 문서는 AI 지식생성 플랫폼을 Azure AKS(Azure Kubernetes Service)에 배포하는 방법을 설명합니다.

## 사전 준비사항

### 1. Azure CLI 및 도구 설치
```bash
# Azure CLI 설치
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Azure CLI 로그인
az login

# kubectl 설치
az aks install-cli
```

### 2. Azure Container Registry (ACR) 생성
```bash
# 리소스 그룹 생성
az group create --name wkms-rg --location koreacentral

# ACR 생성
az acr create --resource-group wkms-rg --name wkmsacr --sku Basic
```

## AKS 클러스터 생성

### 1. 클러스터 생성
```bash
# AKS 클러스터 생성
az aks create \
  --resource-group wkms-rg \
  --name wkms-aks-cluster \
  --node-count 2 \
  --node-vm-size Standard_DS2_v2 \
  --enable-addons monitoring \
  --generate-ssh-keys \
  --attach-acr wkmsacr

# kubectl 컨텍스트 설정
az aks get-credentials --resource-group wkms-rg --name wkms-aks-cluster
```

### 2. Application Gateway Ingress Controller 설정
```bash
# Application Gateway 애드온 활성화
az aks enable-addons -n wkms-aks-cluster -g wkms-rg --addons ingress-appgw --appgw-name wkms-appgw --appgw-subnet-cidr "10.2.0.0/16"
```

## 이미지 빌드 및 푸시

### 1. ACR 로그인
```bash
az acr login --name wkmsacr
```

### 2. 이미지 빌드 및 푸시
```bash
# 백엔드 이미지
docker build -t wkmsacr.azurecr.io/wkms-backend:latest ./backend
docker push wkmsacr.azurecr.io/wkms-backend:latest

# 프론트엔드 이미지
docker build -t wkmsacr.azurecr.io/wkms-frontend:latest ./frontend
docker push wkmsacr.azurecr.io/wkms-frontend:latest
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

### 4. AKS 특화 설정
```bash
kubectl apply -f ../06-aks-specific.yaml
```

## Azure 서비스 통합

### 1. Azure Files 스토리지 클래스
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: azure-file
provisioner: kubernetes.io/azure-file
parameters:
  storageAccount: wkmsstorageaccount
  location: koreacentral
```

### 2. Azure Key Vault 통합
```bash
# Key Vault 생성
az keyvault create --name wkms-keyvault --resource-group wkms-rg --location koreacentral

# CSI 드라이버 설치
kubectl apply -f https://raw.githubusercontent.com/Azure/secrets-store-csi-driver-provider-azure/master/deployment/provider-azure-installer.yaml
```

## 모니터링 및 로깅

### 1. Azure Monitor Container Insights
```bash
# Container Insights 활성화 (클러스터 생성 시 이미 활성화됨)
az aks enable-addons -a monitoring -n wkms-aks-cluster -g wkms-rg
```

### 2. Log Analytics 작업 영역
```bash
# Log Analytics 작업 영역 생성
az monitor log-analytics workspace create --resource-group wkms-rg --workspace-name wkms-logs --location koreacentral
```

## 자동 확장 설정

### 1. Cluster Autoscaler 설정
```bash
# 클러스터 자동 확장 활성화
az aks update \
  --resource-group wkms-rg \
  --name wkms-aks-cluster \
  --enable-cluster-autoscaler \
  --min-count 1 \
  --max-count 5
```

### 2. HPA 및 VPA 설정
```bash
# Vertical Pod Autoscaler 설치
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/download/vertical-pod-autoscaler-0.13.0/vpa-release-0.13.0.yaml
```

## 보안 설정

### 1. Azure Active Directory 통합
```bash
# AAD 통합 활성화
az aks update-credentials \
  --resource-group wkms-rg \
  --name wkms-aks-cluster \
  --reset-aad \
  --aad-server-app-id <server-app-id> \
  --aad-server-app-secret <server-app-secret> \
  --aad-client-app-id <client-app-id>
```

### 2. Azure Policy 적용
```bash
# Azure Policy 애드온 활성화
az aks enable-addons --addons azure-policy --name wkms-aks-cluster --resource-group wkms-rg
```

## 네트워킹 설정

### 1. Azure CNI 네트워크 설정
```bash
# 가상 네트워크 생성
az network vnet create \
  --resource-group wkms-rg \
  --name wkms-vnet \
  --address-prefixes 10.0.0.0/8 \
  --subnet-name wkms-subnet \
  --subnet-prefix 10.240.0.0/16
```

### 2. Private Cluster 설정
```bash
# Private AKS 클러스터 생성
az aks create \
  --resource-group wkms-rg \
  --name wkms-private-cluster \
  --enable-private-cluster \
  --private-dns-zone system
```

## SSL 인증서 설정

### 1. cert-manager 설치
```bash
# cert-manager 설치
kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.12.0/cert-manager.yaml
```

### 2. Let's Encrypt 설정
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: azure/application-gateway
```

## 문제 해결

### 일반적인 문제들

1. **ACR 이미지 풀링 실패**
   ```bash
   # ACR과 AKS 통합 확인
   az aks check-acr --name wkms-aks-cluster --resource-group wkms-rg --acr wkmsacr.azurecr.io
   ```

2. **Application Gateway 연결 문제**
   ```bash
   # Application Gateway 상태 확인
   az network application-gateway show --name wkms-appgw --resource-group wkms-rg
   ```

3. **Pod 네트워킹 문제**
   ```bash
   # CNI 로그 확인
   kubectl logs -n kube-system -l app=azure-cni-networkmonitor
   ```

### 유용한 명령어들

```bash
# 클러스터 상태 확인
kubectl get nodes
kubectl get pods -A

# AKS 클러스터 정보
az aks show --resource-group wkms-rg --name wkms-aks-cluster

# 노드 풀 확인
az aks nodepool list --cluster-name wkms-aks-cluster --resource-group wkms-rg

# 로그 확인
kubectl logs -f deployment/wkms-backend -n wkms
kubectl logs -f deployment/wkms-frontend -n wkms
```

## 정리 및 삭제

### 리소스 삭제
```bash
# 애플리케이션 삭제
kubectl delete -f ../

# AKS 클러스터 삭제
az aks delete --resource-group wkms-rg --name wkms-aks-cluster

# 리소스 그룹 삭제 (모든 리소스 삭제)
az group delete --name wkms-rg
```

## 참고 자료

- [Azure AKS 공식 문서](https://docs.microsoft.com/azure/aks/)
- [Azure Container Registry 문서](https://docs.microsoft.com/azure/container-registry/)
- [Application Gateway Ingress Controller](https://azure.github.io/application-gateway-kubernetes-ingress/)

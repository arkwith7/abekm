# Google GKE 배포 가이드

## 개요

이 문서는 AI 지식생성 플랫폼을 Google GKE(Google Kubernetes Engine)에 배포하는 방법을 설명합니다.

## 사전 준비사항

### 1. Google Cloud SDK 설치
```bash
# Google Cloud SDK 설치
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# gcloud 초기화
gcloud init

# kubectl 설치
gcloud components install kubectl
```

### 2. 프로젝트 및 API 활성화
```bash
# 프로젝트 설정
gcloud config set project PROJECT_ID

# 필요한 API 활성화
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable cloudsql.googleapis.com
```

## GKE 클러스터 생성

### 1. 표준 GKE 클러스터 생성
```bash
# 기본 클러스터 생성
gcloud container clusters create wkms-gke-cluster \
    --zone=asia-northeast3-a \
    --machine-type=e2-standard-2 \
    --num-nodes=2 \
    --enable-cloud-logging \
    --enable-cloud-monitoring \
    --enable-autorepair \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=5
```

### 2. GKE Autopilot 클러스터 (권장)
```bash
# Autopilot 클러스터 생성
gcloud container clusters create-auto wkms-autopilot-cluster \
    --region=asia-northeast3 \
    --release-channel=regular
```

### 3. kubectl 컨텍스트 설정
```bash
# 클러스터 자격 증명 가져오기
gcloud container clusters get-credentials wkms-gke-cluster --zone=asia-northeast3-a

# 또는 Autopilot의 경우
gcloud container clusters get-credentials wkms-autopilot-cluster --region=asia-northeast3
```

## Container Registry 설정

### 1. Artifact Registry 생성 (권장)
```bash
# Artifact Registry 생성
gcloud artifacts repositories create wkms-repo \
    --repository-format=docker \
    --location=asia-northeast3 \
    --description="WKMS Docker repository"

# Docker 인증 설정
gcloud auth configure-docker asia-northeast3-docker.pkg.dev
```

### 2. 이미지 빌드 및 푸시
```bash
# 백엔드 이미지
docker build -t asia-northeast3-docker.pkg.dev/PROJECT_ID/wkms-repo/wkms-backend:latest ./backend
docker push asia-northeast3-docker.pkg.dev/PROJECT_ID/wkms-repo/wkms-backend:latest

# 프론트엔드 이미지
docker build -t asia-northeast3-docker.pkg.dev/PROJECT_ID/wkms-repo/wkms-frontend:latest ./frontend
docker push asia-northeast3-docker.pkg.dev/PROJECT_ID/wkms-repo/wkms-frontend:latest
```

## 애플리케이션 배포

### 1. 네임스페이스 및 설정
```bash
kubectl apply -f ../00-namespace-config.yaml
```

### 2. Cloud SQL 연결 설정
```bash
# Cloud SQL Proxy 설치
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/cloudsql-proxy/main/examples/k8s/proxy_workload_identity.yaml
```

### 3. 애플리케이션 배포
```bash
# 데이터베이스 배포
kubectl apply -f ../04-database.yaml

# 백엔드 배포
kubectl apply -f ../01-backend.yaml

# 프론트엔드 배포
kubectl apply -f ../02-frontend.yaml

# 인그레스 배포
kubectl apply -f ../03-ingress.yaml
```

### 4. GKE 특화 설정
```bash
kubectl apply -f ../07-gke-specific.yaml
```

## Google Cloud 서비스 통합

### 1. Cloud SQL 데이터베이스 생성
```bash
# PostgreSQL 인스턴스 생성
gcloud sql instances create wkms-postgres \
    --database-version=POSTGRES_13 \
    --tier=db-f1-micro \
    --region=asia-northeast3

# 데이터베이스 생성
gcloud sql databases create wkms_db --instance=wkms-postgres

# 사용자 생성
gcloud sql users create wkms_user --instance=wkms-postgres --password=your_password
```

### 2. Cloud Storage 설정
```bash
# 스토리지 버킷 생성
gsutil mb -l asia-northeast3 gs://wkms-storage-bucket

# 버킷 권한 설정
gsutil iam ch serviceAccount:YOUR_SERVICE_ACCOUNT:objectAdmin gs://wkms-storage-bucket
```

### 3. Secret Manager 통합
```bash
# Secret Manager API 활성화
gcloud services enable secretmanager.googleapis.com

# 시크릿 생성
echo "your-database-password" | gcloud secrets create db-password --data-file=-
echo "your-jwt-secret" | gcloud secrets create jwt-secret --data-file=-
```

## 네트워킹 설정

### 1. Ingress Controller 설정
```bash
# Google Cloud Load Balancer Ingress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: gce
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
spec:
  controller: k8s.io/ingress-gce
EOF
```

### 2. 방화벽 규칙 설정
```bash
# 방화벽 규칙 생성
gcloud compute firewall-rules create wkms-allow-http \
    --allow tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTP traffic"

gcloud compute firewall-rules create wkms-allow-https \
    --allow tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTPS traffic"
```

### 3. 정적 IP 주소 예약
```bash
# 정적 IP 주소 예약
gcloud compute addresses create wkms-static-ip --global

# IP 주소 확인
gcloud compute addresses describe wkms-static-ip --global
```

## SSL 인증서 설정

### 1. Google-managed SSL 인증서
```bash
kubectl apply -f - <<EOF
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: wkms-ssl-cert
  namespace: wkms
spec:
  domains:
    - yourdomain.com
    - www.yourdomain.com
EOF
```

### 2. cert-manager를 통한 Let's Encrypt
```bash
# cert-manager 설치
kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.12.0/cert-manager.yaml

# ClusterIssuer 생성
kubectl apply -f - <<EOF
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
          class: gce
EOF
```

## 모니터링 및 로깅

### 1. Google Cloud Operations Suite
```bash
# Operations Suite는 GKE에 기본으로 활성화됨
# 추가 설정이 필요한 경우:
gcloud container clusters update wkms-gke-cluster \
    --zone=asia-northeast3-a \
    --enable-cloud-logging \
    --enable-cloud-monitoring
```

### 2. Prometheus 및 Grafana 설치
```bash
# Helm으로 kube-prometheus-stack 설치
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace
```

## 자동 확장 설정

### 1. Horizontal Pod Autoscaler
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: wkms-backend-hpa
  namespace: wkms
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: wkms-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 2. Vertical Pod Autoscaler
```bash
# VPA 설치
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/download/vertical-pod-autoscaler-0.13.0/vpa-release-0.13.0.yaml
```

### 3. Cluster Autoscaler (표준 클러스터)
```bash
# 클러스터 자동 확장 활성화
gcloud container clusters update wkms-gke-cluster \
    --zone=asia-northeast3-a \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=5
```

## 보안 설정

### 1. Workload Identity 설정
```bash
# Workload Identity 활성화
gcloud container clusters update wkms-gke-cluster \
    --zone=asia-northeast3-a \
    --workload-pool=PROJECT_ID.svc.id.goog

# Kubernetes 서비스 계정 생성
kubectl create serviceaccount wkms-ksa --namespace wkms

# Google 서비스 계정과 연결
gcloud iam service-accounts add-iam-policy-binding \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:PROJECT_ID.svc.id.goog[wkms/wkms-ksa]" \
    wkms-gsa@PROJECT_ID.iam.gserviceaccount.com
```

### 2. Binary Authorization 설정
```bash
# Binary Authorization API 활성화
gcloud services enable binaryauthorization.googleapis.com

# 정책 생성
gcloud container binauthz policy import policy.yaml
```

### 3. Pod Security Standards
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: wkms
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

## 백업 및 복구

### 1. 백업 설정
```bash
# Backup for GKE API 활성화
gcloud services enable gkebackup.googleapis.com

# 백업 계획 생성
gcloud alpha container backup-restore backup-plans create wkms-backup-plan \
    --project=PROJECT_ID \
    --location=asia-northeast3 \
    --cluster=projects/PROJECT_ID/locations/asia-northeast3-a/clusters/wkms-gke-cluster
```

### 2. 정기 백업 스케줄
```bash
# 백업 스케줄 생성
gcloud alpha container backup-restore backups create \
    --project=PROJECT_ID \
    --location=asia-northeast3 \
    --backup-plan=wkms-backup-plan \
    --backup-id=wkms-backup-$(date +%Y%m%d)
```

## 문제 해결

### 일반적인 문제들

1. **이미지 풀링 실패**
   ```bash
   # 서비스 계정 키 확인
   kubectl get secrets
   kubectl describe secret default-token-xxxxx
   ```

2. **Cloud SQL 연결 문제**
   ```bash
   # Cloud SQL Proxy 로그 확인
   kubectl logs -l app=cloudsql-proxy -n wkms
   
   # 네트워크 연결 테스트
   kubectl run test-pod --image=busybox --rm -it -- nslookup cloudsql-service
   ```

3. **Load Balancer 문제**
   ```bash
   # 인그레스 상태 확인
   kubectl describe ingress wkms-ingress -n wkms
   
   # 로드 밸런서 확인
   gcloud compute forwarding-rules list
   ```

### 유용한 명령어들

```bash
# 클러스터 상태 확인
kubectl get nodes
kubectl get pods -A

# GKE 클러스터 정보
gcloud container clusters describe wkms-gke-cluster --zone=asia-northeast3-a

# 노드 풀 확인
gcloud container node-pools list --cluster=wkms-gke-cluster --zone=asia-northeast3-a

# 로그 확인
kubectl logs -f deployment/wkms-backend -n wkms
kubectl logs -f deployment/wkms-frontend -n wkms

# Cloud Logging에서 로그 확인
gcloud logging read "resource.type=k8s_container AND resource.labels.cluster_name=wkms-gke-cluster"
```

## 비용 최적화

### 1. Preemptible Nodes 사용
```bash
# Preemptible 노드 풀 생성
gcloud container node-pools create preemptible-pool \
    --cluster=wkms-gke-cluster \
    --zone=asia-northeast3-a \
    --preemptible \
    --num-nodes=2 \
    --machine-type=e2-standard-2
```

### 2. GKE Autopilot 권장
- 자동 리소스 최적화
- 사용한 만큼만 과금
- 운영 오버헤드 최소화

### 3. 리소스 모니터링
```bash
# 리소스 사용량 확인
kubectl top nodes
kubectl top pods -A

# 비용 분석
gcloud billing projects describe PROJECT_ID
```

## 정리 및 삭제

### 리소스 삭제
```bash
# 애플리케이션 삭제
kubectl delete -f ../

# 클러스터 삭제
gcloud container clusters delete wkms-gke-cluster --zone=asia-northeast3-a

# Cloud SQL 인스턴스 삭제
gcloud sql instances delete wkms-postgres

# 스토리지 버킷 삭제
gsutil rm -r gs://wkms-storage-bucket

# 정적 IP 주소 삭제
gcloud compute addresses delete wkms-static-ip --global
```

## 참고 자료

- [Google Kubernetes Engine 문서](https://cloud.google.com/kubernetes-engine/docs)
- [GKE Autopilot 가이드](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres)
- [Workload Identity 설정](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)

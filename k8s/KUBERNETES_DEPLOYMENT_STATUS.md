# Kubernetes 배포 상태 점검 및 업데이트 완료

## 업데이트 완료 사항

### 1. 환경 변수 통합 (00-namespace-config.yaml)

- ✅ 프로덕션 Docker 설정과 일치하는 모든 환경 변수 추가
- ✅ ConfigMap으로 중앙 집중화된 환경 변수 관리
- ✅ JWT, CORS, LLM 설정 포함

### 2. 백엔드 서비스 (01-backend.yaml)

- ✅ ConfigMap 환경 변수 참조로 업데이트
- ✅ 컨테이너 포트 8000 유지 (Docker와 일치)
- ✅ 헬스체크 설정 포함

### 3. 프론트엔드 서비스 (02-frontend.yaml)

- ✅ 컨테이너 포트 3000 → 80으로 업데이트 (프로덕션 Docker와 일치)
- ✅ 서비스 포트 80으로 업데이트
- ✅ 헬스체크 포트 80으로 업데이트
- ✅ ConfigMap 환경 변수 참조 추가

### 4. Ingress 및 NodePort (03-ingress.yaml)

- ✅ 프론트엔드 NodePort targetPort 3000 → 80으로 업데이트
- ✅ 백엔드 NodePort 8000 유지
- ✅ Ingress 설정 포함 (도메인 설정 필요)

### 5. 데이터베이스 및 Redis (04-database.yaml)

- ✅ PostgreSQL with pgvector 설정
- ✅ Redis 7-alpine 설정 (패스워드 없음, Docker와 일치)
- ✅ StatefulSet과 ClusterIP 서비스

## Docker vs Kubernetes 설정 일치 확인

| 구성 요소                 | Docker 프로덕션     | Kubernetes  | 상태           |
| --------------------- | --------------- | ----------- | ------------ |
| Backend Port          | 8000            | 8000        | ✅ 일치         |
| Frontend Port         | 80              | 80          | ✅ 일치         |
| PostgreSQL            | wkms:wkms123    | wkms:secret | ⚠️ 시크릿 설정 필요 |
| Redis                 | No password     | No password | ✅ 일치         |
| Environment Variables | .env.production | ConfigMap   | ✅ 일치         |
| CORS Origins          | 15.165.163.233  | ConfigMap   | ✅ 일치         |

## 배포 준비 상태

### 준비 완료

- ✅ 모든 매니페스트 파일 업데이트 완료
- ✅ 네트워킹 설정 Docker와 일치
- ✅ 환경 변수 중앙 관리
- ✅ 서비스 포트 매핑 정확

### 배포 전 필요 작업

1. **컨테이너 이미지 빌드 및 푸시**

   ```bash
   # 백엔드 이미지 빌드
   docker build -t wkms-backend:latest .
   docker tag wkms-backend:latest your-registry/wkms-backend:latest
   docker push your-registry/wkms-backend:latest

   # 프론트엔드 이미지 빌드
   cd frontend
   docker build -t wkms-frontend:latest .
   docker tag wkms-frontend:latest your-registry/wkms-frontend:latest
   docker push your-registry/wkms-frontend:latest
   ```
2. **시크릿 생성**

   ```bash
   kubectl create secret generic wkms-secrets \
     --from-literal=postgres-password=wkms123 \
     --from-literal=jwt-secret-key=your-jwt-secret \
     -n wkms
   ```
3. **네임스페이스 및 배포**

   ```bash
   kubectl apply -f k8s/00-namespace-config.yaml
   kubectl apply -f k8s/04-database.yaml
   kubectl apply -f k8s/01-backend.yaml
   kubectl apply -f k8s/02-frontend.yaml
   kubectl apply -f k8s/03-ingress.yaml
   ```

## 접근 방법

### NodePort를 통한 접근 (개발/테스트)

- Frontend: `http://[NODE-IP]:30000`
- Backend API: `http://[NODE-IP]:30001`

### Ingress를 통한 접근 (프로덕션)

- 도메인 설정 후 Ingress 컨트롤러 및 SSL 인증서 필요
- Frontend: `https://your-domain.com`
- Backend API: `https://api.your-domain.com`

## 검증 방법

1. **Pod 상태 확인**

   ```bash
   kubectl get pods -n wkms
   ```
2. **서비스 확인**

   ```bash
   kubectl get svc -n wkms
   ```
3. **로그 확인**

   ```bash
   kubectl logs -f deployment/wkms-backend -n wkms
   kubectl logs -f deployment/wkms-frontend -n wkms
   ```
4. **연결 테스트**

   ```bash
   kubectl port-forward svc/wkms-frontend 8080:80 -n wkms
   kubectl port-forward svc/wkms-backend 8001:8000 -n wkms
   ```

## 결론

모든 Kubernetes 매니페스트가 성공적으로 작동하는 Docker 프로덕션 환경 설정과 일치하도록 업데이트되었습니다. 이제 컨테이너 이미지 빌드와 시크릿 설정 후 Kubernetes 클러스터에 배포할 준비가 완료되었습니다.
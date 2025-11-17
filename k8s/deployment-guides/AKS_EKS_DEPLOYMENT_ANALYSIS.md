# AKS/EKS 배포를 위한 Kubernetes 매니페스트 수정 사항

## 🚨 현재 매니페스트의 AKS/EKS 배포 문제점

### 1. 스토리지 클래스 문제

- **문제**: StatefulSet에서 스토리지 클래스가 지정되지 않음
- **영향**: EKS(gp2, gp3), AKS(managed-csi) 기본값과 충돌 가능
- **해결**: 명시적 storageClassName 지정 필요

### 2. Ingress 컨트롤러 호환성

- **문제**: `kubernetes.io/ingress.class: "nginx"` 구식 어노테이션 사용
- **영향**: 최신 Ingress 컨트롤러에서 경고/오류 발생
- **해결**: `spec.ingressClassName` 필드 사용 권장

### 3. 리소스 제한 및 네임스페이스 할당량

- **문제**: CPU/메모리 리소스가 EKS/AKS 노드 크기와 맞지 않을 수 있음
- **영향**: Pod 스케줄링 실패 가능
- **해결**: 클러스터 환경에 맞는 리소스 조정

### 4. 보안 컨텍스트 및 PSP/PSA

- **문제**: 보안 컨텍스트 미설정
- **영향**: EKS/AKS의 기본 보안 정책에 위반될 수 있음
- **해결**: SecurityContext 추가 필요

### 5. 로드밸런서 타입 설정

- **문제**: NodePort로만 설정됨
- **영향**: 클라우드 로드밸런서 활용 불가
- **해결**: LoadBalancer 타입 옵션 추가

## 📋 수정 필요 사항

### 우선순위 HIGH

1. **스토리지 클래스 명시**
2. **Ingress 클래스 현대화**
3. **보안 컨텍스트 추가**
4. **리소스 제한 조정**

### 우선순위 MEDIUM

1. **LoadBalancer 서비스 추가**
2. **PodDisruptionBudget 설정**
3. **HorizontalPodAutoscaler 준비**

### 우선순위 LOW

1. **NetworkPolicy 설정**
2. **ServiceMonitor 설정** (모니터링용)

## 🛠 즉시 수정 권장 사항

### 1. 환경별 ConfigMap 분리

- 현재: 단일 ConfigMap으로 모든 환경 설정
- 권장: 환경별(dev/staging/prod) ConfigMap 분할

### 2. Secret 관리 개선

- 현재: 하드코딩된 Base64 값
- 권장: 외부 시크릿 관리자 연동 (AWS Secrets Manager, Azure Key Vault)

### 3. 이미지 태그 관리

- 현재: latest 태그 사용
- 권장: 명시적 버전 태그 사용

## 🌐 클라우드별 특이사항

### EKS (Amazon Web Services)

- **스토리지**: gp3 (권장), gp2 (기본)
- **Ingress**: AWS Load Balancer Controller 권장
- **보안**: IRSA (IAM Roles for Service Accounts) 활용
- **네트워킹**: VPC CNI 특성 고려

### AKS (Microsoft Azure)

- **스토리지**: managed-csi (기본)
- **Ingress**: Application Gateway Ingress Controller 옵션
- **보안**: AAD Pod Identity 또는 Workload Identity
- **네트워킹**: Azure CNI vs Kubenet 선택

## ✅ 현재 매니페스트의 장점

1. **표준 Kubernetes 리소스 사용**
2. **네임스페이스 격리 구현**
3. **ConfigMap/Secret 분리**
4. **헬스체크 설정 포함**
5. **리소스 제한 설정**

## 🚀 다음 작업 계획

1. 스토리지 클래스 및 Ingress 수정
2. 환경별 매니페스트 분리
3. 보안 컨텍스트 추가
4. 클라우드별 최적화 가이드 작성
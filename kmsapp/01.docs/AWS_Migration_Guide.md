# WKMS AWS 마이그레이션 가이드

## 1. 마이그레이션 개요

### 1.1 목표

- 현재 Azure 기반 WKMS 시스템을 AWS 환경으로 마이그레이션
- AWS VM과 오픈소스 도구 활용을 통한 비용 효율성 확보
- 프론트엔드 현대화 및 백엔드 아키텍처 개선

### 1.2 마이그레이션 전략

1. **Lift and Shift**: 기본 기능 이전 (단기)
2. **Re-architecting**: AWS 네이티브 서비스 활용 (중기)
3. **Modernization**: 완전한 클라우드 네이티브 구조 (장기)

---

## 2. Azure vs AWS 서비스 매핑

### 2.1 컴퓨팅 서비스

| Azure 서비스       | AWS 서비스    | 마이그레이션 방안      | 비고                      |
| --------------- | ---------- | -------------- | ----------------------- |
| Azure Functions | AWS Lambda | 함수별 개별 이전      | 런타임 및 트리거 호환성 확인 필요     |
| App Service     | EC2 + ALB  | Docker 컨테이너 배포 | Streamlit 앱 EC2 인스턴스 배포 |
| -               | ECS/EKS    | 컨테이너 오케스트레이션   | 확장성 고려 시 권장             |

### 2.2 데이터베이스 서비스

| Azure 서비스   | AWS 서비스      | 마이그레이션 방안   | 비고            |
| ----------- | ------------ | ----------- | ------------- |
| Azure MySQL | RDS MySQL    | 데이터 덤프 및 복원 | 스키마 호환성 완전    |
| Azure MySQL | Aurora MySQL | 성능 개선 옵션    | 서버리스 옵션 고려    |
| CosmosDB    | DynamoDB     | 데이터 변환 필요   | NoSQL 스키마 재설계 |
| CosmosDB    | DocumentDB   | 더 유사한 구조    | MongoDB 호환성   |

### 2.3 AI/ML 서비스

| Azure 서비스             | AWS 서비스        | 마이그레이션 방안  | 비고                  |
| --------------------- | -------------- | ---------- | ------------------- |
| Azure OpenAI          | Amazon Bedrock | API 호환성 확인 | Claude, Titan 모델 활용 |
| Azure OpenAI          | SageMaker      | 오픈소스 모델 배포 | Llama, Mistral 등    |
| Document Intelligence | Textract       | API 변경 필요  | OCR 기능 유사           |
| AI Search             | OpenSearch     | 인덱스 재구성    | OpenSearch 기반       |

### 2.4 스토리지 서비스

| Azure 서비스     | AWS 서비스 | 마이그레이션 방안           | 비고         |
| ------------- | ------- | ------------------- | ---------- |
| Blob Storage  | S3      | AWS CLI 또는 DataSync | 완전 호환      |
| Queue Storage | SQS     | 메시지 큐 재구성           | FIFO 옵션 고려 |

### 2.5 모니터링 및 로깅

| Azure 서비스            | AWS 서비스         | 마이그레이션 방안 | 비고       |
| -------------------- | --------------- | --------- | -------- |
| Application Insights | CloudWatch      | 로그 수집 재구성 | 대시보드 재작성 |
| Log Analytics        | CloudWatch Logs | 로그 포맷 통일  | 검색 기능 유사 |

---

## 3. 오픈소스 도구 활용 방안

### 3.1 AI/ML 오픈소스 스택

#### 3.1.1 LLM 모델 대안

```yaml
# HuggingFace 모델 활용
models:
  embedding:
    - sentence-transformers/all-MiniLM-L6-v2
    - intfloat/multilingual-e5-large
  generation:
    - microsoft/DialoGPT-large
    - beomi/KoAlpaca-Polyglot-12.8B
  korean_specific:
    - nlpai-lab/kullm-polyglot-12.8b-v2
    - kakaobrain/kogpt
```

#### 3.1.2 문서 처리 도구

```python
# 오픈소스 문서 처리 스택
document_processing:
  - pdf_processing: PyPDF2, pdfplumber, fitz
  - ocr: Tesseract, EasyOCR
  - preprocessing: spaCy, NLTK
  - chunking: LangChain, LlamaIndex
```

#### 3.1.3 벡터 데이터베이스

```yaml
vector_databases:
  options:
    - Weaviate: 오픈소스, 멀티모달 지원
    - Chroma: 경량, 임베딩 특화
    - Qdrant: 고성능, 필터링 강화
    - FAISS: Facebook 개발, 고속 검색
  recommended: Weaviate (확장성과 기능의 균형)
```

### 3.2 검색 엔진 대안

#### 3.2.1 OpenSearch 스택

```yaml
search_stack:
  engine: OpenSearch 2.x
  ui: OpenSearch Dashboards
  data_processing: Logstash
  korean_analyzer: nori
  features:
    - 하이브리드 검색 (키워드 + 벡터)
    - 실시간 인덱싱
    - 고급 필터링
```

### 3.3 모니터링 스택

#### 3.3.1 Observability 도구

```yaml
monitoring:
  metrics: Prometheus + Grafana
  logging: OpenSearch Stack (OpenSearch, Logstash, Dashboards)
  tracing: Jaeger
  alerting: AlertManager
```

---

## 4. 아키텍처 설계

### 4.1 프론트엔드 아키텍처

#### 4.1.1 현대적 웹 프론트엔드 옵션

**Option 1: React + TypeScript SPA**
```typescript
// 기술 스택
frontend_stack:
  framework: React 18 + TypeScript
  ui_library: Material-UI 또는 Ant Design
  state_management: Redux Toolkit + RTK Query
  routing: React Router v6
  styling: Styled Components 또는 Emotion
  build_tool: Vite
  testing: Jest + React Testing Library
```

**Option 2: Next.js 풀스택**
```typescript
// Next.js 13+ App Router
next_stack:
  framework: Next.js 13+ (App Router)
  styling: Tailwind CSS
  ui_components: Radix UI + Shadcn/ui
  state: Zustand 또는 React Query
  authentication: NextAuth.js
  api: API Routes (내장)
```

**Option 3: Vue.js 현대화**
```typescript
// Vue 3 Composition API
vue_stack:
  framework: Vue 3 + TypeScript
  ui_library: Vuetify 또는 Quasar
  state_management: Pinia
  routing: Vue Router 4
  build_tool: Vite
```

#### 4.1.2 채팅 UI 컴포넌트

```typescript
// 채팅 인터페이스 설계
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: DocumentSource[];
  attachments?: FileAttachment[];
}

interface DocumentSource {
  filename: string;
  path: string;
  relevance_score: number;
  snippet: string;
  view_url?: string;
  download_url?: string;
}
```

### 4.2 백엔드 아키텍처

#### 4.2.1 마이크로서비스 분할

```yaml
microservices:
  auth_service:
    tech: FastAPI + JWT
    db: Redis (세션)
    
  document_service:
    tech: FastAPI + Celery
    db: PostgreSQL + S3
    queue: Redis
    
  search_service:
    tech: FastAPI
    engine: OpenSearch
    vector_db: Weaviate
    
  chat_service:
    tech: FastAPI + WebSocket
    llm: SageMaker 또는 HuggingFace
    memory: Redis
    
  sap_integration:
    tech: FastAPI
    connector: SAP RFC SDK
```

#### 4.2.2 API Gateway 패턴

```yaml
api_gateway:
  tool: AWS API Gateway 또는 Kong
  features:
    - 라우팅 및 로드밸런싱
    - 인증/인가 (JWT 검증)
    - 요청/응답 변환
    - 트래픽 제한
    - 로깅 및 모니터링
```

### 4.3 인프라 아키텍처

#### 4.3.1 AWS EC2 기반 배포

```yaml
infrastructure:
  compute:
    web_tier:
      - EC2 instances (t3.medium+)
      - Application Load Balancer
      - Auto Scaling Group
      
    app_tier:
      - EC2 instances (c5.large+)
      - Internal Load Balancer
      - Container runtime (Docker)
      
    data_tier:
      - RDS Multi-AZ
      - ElastiCache Redis Cluster
      - S3 buckets
      
  networking:
    - VPC with public/private subnets
    - NAT Gateway
    - CloudFront CDN
    
  security:
    - WAF (Web Application Firewall)
    - Security Groups
    - IAM roles and policies
```

#### 4.3.2 컨테이너 기반 배포 (ECS)

```yaml
container_deployment:
  orchestration: AWS ECS with Fargate
  services:
    - Frontend: React app (Nginx)
    - API Gateway: Kong or AWS API Gateway
    - Microservices: FastAPI containers
    - Background Jobs: Celery workers
    
  scaling:
    - Application Auto Scaling
    - Target Tracking policies
    - CloudWatch metrics
```

---

## 5. 마이그레이션 단계별 계획

### 5.1 Phase 1: 인프라 준비 (2-3주)

#### 5.1.1 AWS 환경 구성

```bash
# Terraform으로 인프라 구성
terraform/
├── vpc.tf              # VPC, 서브넷, 보안그룹
├── ec2.tf              # EC2 인스턴스, ALB
├── rds.tf              # MySQL RDS
├── s3.tf               # S3 버킷들
├── elasticache.tf      # Redis 클러스터
└── iam.tf              # IAM 역할 및 정책
```

#### 5.1.2 오픈소스 도구 설치

```bash
# EC2 인스턴스 설정 스크립트
#!/bin/bash
# Docker 설치
sudo apt update
sudo apt install -y docker.io docker-compose

# OpenSearch 설치
docker run -d --name opensearch \
  -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" \
  opensearchproject/opensearch:2.11.0

# Weaviate 설치
docker run -d --name weaviate \
  -p 8080:8080 \
  semitechnologies/weaviate:1.22.1
```

### 5.2 Phase 2: 데이터 마이그레이션 (1-2주)

#### 5.2.1 MySQL 데이터 이전

```bash
# Azure MySQL에서 덤프
mysqldump -h azure-mysql-host.mysql.database.azure.com \
  -u username -p wkms_db > wkms_backup.sql

# AWS RDS로 복원
mysql -h wkms-db.cluster-xxx.ap-northeast-2.rds.amazonaws.com \
  -u username -p wkms_db < wkms_backup.sql
```

#### 5.2.2 Blob Storage에서 S3로 이전

```bash
# AzCopy와 AWS CLI 사용
az storage blob download-batch \
  --source container-name \
  --destination ./temp-storage

aws s3 sync ./temp-storage s3://wkms-documents/
```

#### 5.2.3 CosmosDB에서 DynamoDB/DocumentDB로 이전

```python
# 데이터 변환 스크립트
import boto3
from azure.cosmos import CosmosClient

def migrate_cosmos_to_dynamodb():
    # CosmosDB에서 데이터 읽기
    cosmos_client = CosmosClient(cosmos_uri, cosmos_key)
    container = cosmos_client.get_database_client('wkms').get_container_client('documents')
    
    # DynamoDB에 데이터 쓰기
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('wkms-documents')
    
    for item in container.read_all_items():
        # 데이터 구조 변환
        dynamo_item = transform_cosmos_to_dynamo(item)
        table.put_item(Item=dynamo_item)
```

### 5.3 Phase 3: 애플리케이션 이전 (3-4주)

#### 5.3.1 백엔드 API 변환

```python
# Azure Functions를 FastAPI로 변환
# functions/chat_api.py -> fastapi_app/routers/chat.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

class ChatRequest(BaseModel):
    query: str
    session_id: str
    user_id: str

@router.post("/")
async def chat_endpoint(request: ChatRequest):
    try:
        # 기존 Azure Functions 로직 이전
        chatbot = WJChatbot()
        response = await chatbot.process_chat(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 5.3.2 프론트엔드 현대화

```typescript
// React 채팅 컴포넌트
import React, { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: DocumentSource[];
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');

  const chatMutation = useMutation({
    mutationFn: async (query: string) => {
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, session_id: 'user-session' })
      });
      return response.json();
    },
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: data.answer,
        sources: data.sources
      }]);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // 사용자 메시지 추가
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: input
    }]);

    chatMutation.mutate(input);
    setInput('');
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map(message => (
          <MessageComponent key={message.id} message={message} />
        ))}
      </div>
      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문을 입력하세요..."
        />
        <button type="submit">전송</button>
      </form>
    </div>
  );
};
```

### 5.4 Phase 4: 통합 테스트 및 최적화 (2-3주)

#### 5.4.1 성능 테스트

```yaml
# K6 부하 테스트 시나리오
performance_tests:
  scenarios:
    chat_api:
      executor: ramping-vus
      startVUs: 10
      stages:
        - duration: 2m, target: 50
        - duration: 5m, target: 100
        - duration: 2m, target: 0
      
    search_api:
      executor: constant-vus
      vus: 30
      duration: 5m
      
    document_upload:
      executor: per-vu-iterations
      vus: 5
      iterations: 20
```

#### 5.4.2 모니터링 설정

```yaml
# Prometheus 설정
prometheus_config:
  scrape_configs:
    - job_name: 'fastapi-apps'
      static_configs:
        - targets: ['app1:8000', 'app2:8000']
      metrics_path: '/metrics'
      
    - job_name: 'opensearch'
      static_configs:
        - targets: ['opensearch:9200']
        
# Grafana 대시보드
dashboards:
  - API 응답시간 및 처리량
  - 에러율 및 가용성
  - 인프라 리소스 사용률
  - 비즈니스 메트릭 (검색 횟수, 채팅 세션 등)
```

---

## 6. 비용 분석

### 6.1 현재 Azure 비용 (월 예상)

| 서비스             | 사양                 | 월 비용 (USD)     |
| --------------- | ------------------ | -------------- |
| Azure Functions | Premium Plan       | $200-400       |
| Azure MySQL     | Standard B2s       | $100-150       |
| CosmosDB        | 1000 RU/s          | $60-80         |
| Blob Storage    | 1TB + transactions | $50-70         |
| AI Search       | Standard S1        | $200-250       |
| OpenAI          | GPT-4 + Embeddings | $300-500       |
| **총계**          |                    | **$910-1,450** |

### 6.2 AWS 마이그레이션 후 비용 (월 예상)

#### 6.2.1 Option 1: AWS 관리형 서비스

| 서비스         | 사양              | 월 비용 (USD)   |
| ----------- | --------------- | ------------ |
| ECS Fargate | 2 vCPU, 4GB     | $100-150     |
| RDS MySQL   | db.t3.medium    | $80-120      |
| DynamoDB    | On-demand       | $40-60       |
| S3          | 1TB + requests  | $25-35       |
| OpenSearch  | t3.small.search | $80-100      |
| Bedrock     | Claude + Titan  | $200-300     |
| **총계**      |                 | **$525-765** |

#### 6.2.2 Option 2: EC2 + 오픈소스

| 서비스           | 사양             | 월 비용 (USD)   |
| ------------- | -------------- | ------------ |
| EC2 instances | 3x t3.large    | $150-200     |
| RDS MySQL     | db.t3.medium   | $80-120      |
| ElastiCache   | cache.t3.micro | $15-20       |
| S3            | 1TB + requests | $25-35       |
| 오픈소스 스택       | Self-hosted    | $0           |
| **총계**        |                | **$270-375** |

### 6.3 비용 절감 효과

- **Option 1**: 약 42-47% 절감 ($385-685 절약)
- **Option 2**: 약 65-74% 절감 ($640-1,075 절약)

---

## 7. 리스크 및 고려사항

### 7.1 기술적 리스크

| 리스크          | 영향도 | 확률 | 완화 방안             |
| ------------ | --- | -- | ----------------- |
| API 호환성 문제   | 높음  | 중간 | 단계적 마이그레이션, 병렬 운영 |
| 성능 저하        | 중간  | 낮음 | 충분한 테스트, 모니터링 강화  |
| 데이터 손실       | 높음  | 낮음 | 백업 전략, 롤백 계획      |
| 오픈소스 도구 러닝커브 | 중간  | 높음 | 팀 교육, 문서화         |

### 7.2 운영 리스크

| 리스크    | 영향도 | 확률 | 완화 방안          |
| ------ | --- | -- | -------------- |
| 서비스 중단 | 높음  | 중간 | Blue-Green 배포  |
| 보안 취약점 | 높음  | 낮음 | 보안 감사, 정기 업데이트 |
| 인력 부족  | 중간  | 중간 | 외부 컨설팅, 점진적 이전 |

### 7.3 비즈니스 리스크

| 리스크     | 영향도 | 확률 | 완화 방안          |
| ------- | --- | -- | -------------- |
| 프로젝트 지연 | 중간  | 중간 | 버퍼 기간 확보       |
| 예산 초과   | 중간  | 낮음 | 단계별 예산 통제      |
| 사용자 불편  | 낮음  | 중간 | 사용자 교육, 점진적 전환 |

---

## 8. 성공 기준 및 KPI

### 8.1 기술적 KPI

- **응답 시간**: 평균 2초 이하 유지
- **가용성**: 99.9% 이상
- **에러율**: 0.1% 이하
- **동시 사용자**: 100명 이상 지원

### 8.2 비즈니스 KPI

- **비용 절감**: 최소 40% 이상
- **배포 시간**: 기존 대비 50% 단축
- **사용자 만족도**: 4.0/5.0 이상
- **시스템 안정성**: 월 장애 시간 4시간 이하

### 8.3 운영 KPI

- **모니터링 커버리지**: 95% 이상
- **자동화율**: 80% 이상
- **문서화 완성도**: 90% 이상
- **팀 역량**: AWS/오픈소스 숙련도 향상

---

## 9. 타임라인

### 9.1 전체 일정 (12-16주)

```mermaid
gantt
    title WKMS AWS 마이그레이션 일정
    dateFormat  YYYY-MM-DD
    section Phase 1: 인프라 준비
    AWS 환경 구성      :2024-01-01, 2024-01-21
    오픈소스 도구 설치  :2024-01-14, 2024-01-28
    
    section Phase 2: 데이터 마이그레이션
    데이터베이스 이전   :2024-01-22, 2024-02-04
    파일 스토리지 이전  :2024-01-29, 2024-02-11
    
    section Phase 3: 애플리케이션 이전
    백엔드 API 변환     :2024-02-05, 2024-03-03
    프론트엔드 개발     :2024-02-12, 2024-03-17
    
    section Phase 4: 테스트 및 최적화
    통합 테스트        :2024-03-04, 2024-03-24
    성능 최적화        :2024-03-18, 2024-04-07
    운영 준비          :2024-03-25, 2024-04-14
```

### 9.2 주요 마일스톤

- **Week 3**: AWS 인프라 완료
- **Week 6**: 데이터 마이그레이션 완료
- **Week 10**: 백엔드 API 완료
- **Week 13**: 프론트엔드 완료
- **Week 16**: 운영 전환 완료

---

## 10. 결론

### 10.1 권장 사항

1. **단계적 접근**: 리스크 최소화를 위한 점진적 마이그레이션
2. **오픈소스 우선**: 벤더 종속성 탈피 및 비용 절감
3. **모던 프론트엔드**: 사용자 경험 개선을 위한 React 도입
4. **마이크로서비스**: 확장성과 유지보수성 향상

### 10.2 기대 효과

- **비용**: 40-74% 절감
- **성능**: 응답시간 개선
- **확장성**: 수평적 확장 용이
- **유지보수**: 모듈화된 구조

### 10.3 다음 단계

1. 이해관계자 승인 및 예산 확보
2. AWS 계정 및 초기 인프라 설정
3. 팀 교육 및 역할 분담
4. 상세 구현 계획 수립

---

## 11. Azure/AWS VM 기반 중소규모 WKMS 구현 방안

### 11.1 시스템 규모 및 전제조건

#### 11.1.1 사용자 규모

- **동시 사용자**: 10~20명
- **전체 사용자**: 150명
- **예상 일일 쿼리**: 500~1,000건
- **문서 저장량**: 10GB~50GB

#### 11.1.2 성능 요구사항

- **응답 시간**: 평균 3초 이하
- **가용성**: 99.5% 이상
- **동시 처리**: 20개 요청
- **확장성**: 향후 300명까지 확장 가능

### 11.2 최적화된 아키텍처 설계

#### 11.2.1 단순화된 아키텍처 개요

```yaml
optimized_architecture:
  approach: "단순한 VM + 컨테이너 + 관리형 AI 서비스"
  target_users: "동시 10-20명, 전체 150명"
  
  benefits:
    - 운영 복잡도 최소화
    - 비용 효율적 구성 (월 $300-500)
    - 쉬운 유지보수 및 확장
    - 검증된 기술 스택 활용
  
  core_layers:
    frontend: React.js SPA
    proxy: Nginx (API Gateway + Load Balancer)
    backend: 통합 FastAPI 서비스
    database: MySQL + Redis
    search: OpenSearch (벡터 + 키워드 검색)
    ai_services: Azure OpenAI / AWS Bedrock (API 호출)
    storage: S3 / Blob Storage
    monitoring: 기본 로깅 + 헬스체크
```

#### 11.2.2 Docker Compose 기반 서비스 정의

```yaml
# docker-compose.yml - 중소규모 WKMS 스택
version: '3.8'

services:
  # Frontend
  frontend:
    build: ./frontend
    restart: unless-stopped
    networks:
      - wkms-network

  # Nginx Proxy (API Gateway + Load Balancer)
  nginx:
    image: nginx:1.24-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - ./frontend/dist:/usr/share/nginx/html
    depends_on:
      - backend-api
    restart: unless-stopped
    networks:
      - wkms-network

  # 통합 Backend API Service
  backend-api:
    build: ./backend
    environment:
      - DATABASE_URL=mysql+pymysql://wkms:${DB_PASSWORD}@mysql:3306/wkms
      - REDIS_URL=redis://redis:6379/0
      - OPENSEARCH_URL=http://opensearch:9200
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
    volumes:
      - ./uploads:/app/uploads
    depends_on:
      - mysql
      - redis
      - opensearch
    restart: unless-stopped
    deploy:
      replicas: 2
    networks:
      - wkms-network

  # MySQL Database
  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
      - MYSQL_DATABASE=wkms
      - MYSQL_USER=wkms
      - MYSQL_PASSWORD=${DB_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./mysql/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "3306:3306"
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    restart: unless-stopped
    networks:
      - wkms-network

  # Redis Cache
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped
    networks:
      - wkms-network

  # OpenSearch (검색 + 벡터 스토어)
  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
      - plugins.security.disabled=true
      - cluster.name=wkms-search
    volumes:
      - opensearch_data:/usr/share/opensearch/data
    ports:
      - "9200:9200"
    restart: unless-stopped
    networks:
      - wkms-network

  # OpenSearch Dashboards (Optional)
  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:2.11.0
    environment:
      - OPENSEARCH_HOSTS=http://opensearch:9200
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    ports:
      - "5601:5601"
    depends_on:
      - opensearch
    restart: unless-stopped
    networks:
      - wkms-network

volumes:
  mysql_data:
  redis_data:
  opensearch_data:

networks:
  wkms-network:
    driver: bridge
```

### 11.3 클라우드별 VM 구성 방안 (중소규모)

#### 11.3.1 Azure VM 기반 구성

```yaml
azure_vm_config:
  resource_group: wkms-rg
  location: Korea Central
  target_users: "동시 10-20명, 전체 150명"
  
  vms:
    app_server:
      vm_size: Standard_D2s_v3  # 2 vCPU, 8GB RAM
      count: 1
      os: Ubuntu 20.04 LTS
      services: [nginx, backend-api, mysql, redis, opensearch]
      description: "모든 서비스를 단일 VM에 컨테이너로 배포"
      
    backup_server: # Optional for HA
      vm_size: Standard_B2s  # 2 vCPU, 4GB RAM
      count: 1
      os: Ubuntu 20.04 LTS
      services: [mysql-replica, backup-agent]
      description: "데이터 백업 및 간단한 HA"
      
  networking:
    vnet: wkms-vnet (10.0.0.0/24)
    subnets:
      main: 10.0.0.0/26  # 64 IP addresses
    load_balancer: Azure Load Balancer (Basic)
    
  storage:
    os_disk: Premium SSD 128GB
    data_disk: Premium SSD 256GB
    backup: Azure Backup (주간)
    
  ai_services:
    provider: Azure OpenAI Service
    models: [gpt-4, gpt-35-turbo, text-embedding-ada-002]
    region: Korea Central
    
  estimated_monthly_cost: $150-250
```

#### 11.3.2 AWS EC2 기반 구성

```yaml
aws_ec2_config:
  region: ap-northeast-2  # Seoul
  vpc: 10.1.0.0/24
  target_users: "동시 10-20명, 전체 150명"
  
  instances:
    app_server:
      instance_type: t3.medium  # 2 vCPU, 4GB RAM
      count: 1
      ami: Ubuntu 20.04 LTS
      services: [nginx, backend-api, mysql, redis, opensearch]
      description: "모든 서비스를 단일 EC2에 컨테이너로 배포"
      
    backup_server: # Optional for HA
      instance_type: t3.small  # 2 vCPU, 2GB RAM
      count: 1
      ami: Ubuntu 20.04 LTS
      services: [mysql-replica, backup-scripts]
      description: "데이터 백업 및 간단한 HA"
      
  networking:
    subnets:
      public: 10.1.0.0/27   # 32 IP addresses
      private: 10.1.0.32/27 # 32 IP addresses
    load_balancer: Application Load Balancer (기본)
    
  storage:
    root_volume: gp3 SSD 30GB
    data_volume: gp3 SSD 100GB
    backup: EBS Snapshots (일일)
    
  ai_services:
    provider: AWS Bedrock / SageMaker
    models: [anthropic.claude-3-sonnet, amazon.titan-embed-text-v1]
    region: ap-northeast-2 (Seoul)
    
  estimated_monthly_cost: $80-150
```

### 11.4 마이크로서비스 상세 구현

#### 11.4.1 Chat Service (FastAPI)

```python
# services/chat/main.py
from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
import redis
import asyncpg
from transformers import pipeline
import logging

app = FastAPI(title="WKMS Chat Service")

# 글로벌 설정
redis_client = redis.from_url("redis://redis:6379")
chatbot = pipeline("text-generation", model="beomi/KoAlpaca-Polyglot-12.8B")

class ChatRequest(BaseModel):
    query: str
    session_id: str
    user_id: str

class ChatResponse(BaseModel):
    answer: str
    sources: list
    session_id: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. 채팅 히스토리 조회
        history = await get_chat_history(request.session_id)
        
        # 2. 문서 검색 (search-service 호출)
        relevant_docs = await search_documents(request.query)
        
        # 3. RAG 기반 답변 생성
        context = build_context(relevant_docs, history)
        answer = generate_answer(request.query, context)
        
        # 4. 채팅 히스토리 저장
        await save_chat_history(request.session_id, request.query, answer)
        
        return ChatResponse(
            answer=answer,
            sources=relevant_docs,
            session_id=request.session_id
        )
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_chat_history(session_id: str):
    """Redis에서 채팅 히스토리 조회"""
    history = redis_client.lrange(f"chat:{session_id}", 0, -1)
    return [json.loads(msg) for msg in history]

async def search_documents(query: str):
    """검색 서비스 호출"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://search-service:8000/search",
            json={"query": query, "top_k": 5}
        )
        return response.json()

def generate_answer(query: str, context: str):
    """HuggingFace 모델로 답변 생성"""
    prompt = f"질문: {query}\n컨텍스트: {context}\n답변:"
    response = chatbot(prompt, max_length=512, num_return_sequences=1)
    return response[0]['generated_text'].split('답변:')[-1].strip()

# Dockerfile for Chat Service
dockerfile_chat = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
```

#### 11.4.2 Search Service (OpenSearch + Weaviate)

```python
# services/search/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opensearchpy import OpenSearch
import weaviate
import numpy as np
from sentence_transformers import SentenceTransformer

app = FastAPI(title="WKMS Search Service")

# 클라이언트 초기화
opensearch_client = OpenSearch([{"host": "opensearch", "port": 9200}])
weaviate_client = weaviate.Client("http://weaviate:8080")
embedding_model = SentenceTransformer('intfloat/multilingual-e5-large')

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    search_type: str = "hybrid"  # keyword, vector, hybrid

class SearchResponse(BaseModel):
    documents: list
    total_hits: int
    search_time: float

@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    start_time = time.time()
    
    if request.search_type == "hybrid":
        results = await hybrid_search(request.query, request.top_k)
    elif request.search_type == "vector":
        results = await vector_search(request.query, request.top_k)
    else:
        results = await keyword_search(request.query, request.top_k)
    
    search_time = time.time() - start_time
    
    return SearchResponse(
        documents=results,
        total_hits=len(results),
        search_time=search_time
    )

async def hybrid_search(query: str, top_k: int):
    """하이브리드 검색 (키워드 + 벡터)"""
    # 1. 키워드 검색
    keyword_results = await keyword_search(query, top_k)
    
    # 2. 벡터 검색
    vector_results = await vector_search(query, top_k)
    
    # 3. 결과 융합 (RRF - Reciprocal Rank Fusion)
    combined_results = combine_search_results(keyword_results, vector_results)
    
    return combined_results[:top_k]

async def vector_search(query: str, top_k: int):
    """Weaviate를 이용한 벡터 검색"""
    query_vector = embedding_model.encode([query])[0].tolist()
    
    result = weaviate_client.query.get("Document", [
        "file_name", "main_text", "file_path", "category"
    ]).with_near_vector({
        "vector": query_vector
    }).with_limit(top_k).do()
    
    return result['data']['Get']['Document']

async def keyword_search(query: str, top_k: int):
    """OpenSearch를 이용한 키워드 검색"""
    search_body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "main_text", "keywords"],
                "type": "best_fields",
                "fuzziness": "AUTO"
            }
        },
        "highlight": {
            "fields": {
                "main_text": {"fragment_size": 200}
            }
        },
        "size": top_k
    }
    
    response = opensearch_client.search(index="wkms-documents", body=search_body)
    return [hit['_source'] for hit in response['hits']['hits']]
```

#### 11.4.3 AI Service (HuggingFace Models)

```python
# services/ai/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    AutoModel, pipeline
)
import cv2
import easyocr
from PIL import Image
import io

app = FastAPI(title="WKMS AI Service")

# 모델 로딩
device = "cuda" if torch.cuda.is_available() else "cpu"

# 한국어 특화 생성 모델
generation_tokenizer = AutoTokenizer.from_pretrained("beomi/KoAlpaca-Polyglot-12.8B")
generation_model = AutoModelForCausalLM.from_pretrained(
    "beomi/KoAlpaca-Polyglot-12.8B",
    torch_dtype=torch.float16,
    device_map="auto"
)

# 임베딩 모델
embedding_tokenizer = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
embedding_model = AutoModel.from_pretrained("intfloat/multilingual-e5-large")

# OCR 모델
ocr_reader = easyocr.Reader(['ko', 'en'])

class GenerationRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7

class EmbeddingRequest(BaseModel):
    texts: list[str]

class OCRRequest(BaseModel):
    image_data: str  # base64 encoded

@app.post("/generate")
async def generate_text(request: GenerationRequest):
    """텍스트 생성 API"""
    try:
        inputs = generation_tokenizer(request.prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = generation_model.generate(
                inputs.input_ids,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                do_sample=True,
                pad_token_id=generation_tokenizer.eos_token_id
            )
        
        generated_text = generation_tokenizer.decode(outputs[0], skip_special_tokens=True)
        result_text = generated_text[len(request.prompt):].strip()
        
        return {"generated_text": result_text}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """텍스트 임베딩 생성 API"""
    try:
        inputs = embedding_tokenizer(
            request.texts,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512
        )
        
        with torch.no_grad():
            outputs = embedding_model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1)
            embeddings = embeddings.cpu().numpy().tolist()
        
        return {"embeddings": embeddings}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ocr")
async def extract_text_from_image(request: OCRRequest):
    """이미지에서 텍스트 추출 API"""
    try:
        # Base64 디코딩
        image_data = base64.b64decode(request.image_data)
        image = Image.open(io.BytesIO(image_data))
        image_np = np.array(image)
        
        # OCR 수행
        results = ocr_reader.readtext(image_np)
        
        extracted_text = ""
        for (bbox, text, confidence) in results:
            if confidence > 0.5:  # 신뢰도 임계값
                extracted_text += text + " "
        
        return {
            "extracted_text": extracted_text.strip(),
            "details": [
                {"text": text, "confidence": conf, "bbox": bbox}
                for (bbox, text, conf) in results
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 11.5 배포 및 운영 스크립트

#### 11.5.1 자동화 배포 스크립트

```bash
#!/bin/bash
# deploy.sh - 멀티클라우드 자동 배포 스크립트

set -e

CLOUD_PROVIDER=${1:-aws}  # aws, azure
ENVIRONMENT=${2:-dev}     # dev, staging, prod

echo "🚀 WKMS 배포 시작 - Provider: $CLOUD_PROVIDER, Environment: $ENVIRONMENT"

# 1. 환경별 설정 로드
source ./config/${ENVIRONMENT}.env

# 2. 클라우드별 VM 생성
case $CLOUD_PROVIDER in
  "aws")
    echo "📡 AWS EC2 인스턴스 생성 중..."
    terraform -chdir=./terraform/aws init
    terraform -chdir=./terraform/aws plan -var-file="../${ENVIRONMENT}.tfvars"
    terraform -chdir=./terraform/aws apply -auto-approve
    ;;
  "azure")
    echo "📡 Azure VM 생성 중..."
    terraform -chdir=./terraform/azure init
    terraform -chdir=./terraform/azure plan -var-file="../${ENVIRONMENT}.tfvars"
    terraform -chdir=./terraform/azure apply -auto-approve
    ;;
  *)
    echo "❌ 지원하지 않는 클라우드 제공업체: $CLOUD_PROVIDER"
    exit 1
    ;;
esac

# 3. 인벤토리 파일 생성
echo "📋 Ansible 인벤토리 생성 중..."
python scripts/generate_inventory.py --provider $CLOUD_PROVIDER --env $ENVIRONMENT

# 4. 서버 기본 설정
echo "⚙️ 서버 기본 설정 중..."
ansible-playbook -i inventory/${CLOUD_PROVIDER}_${ENVIRONMENT}.yml playbooks/setup-servers.yml

# 5. Docker 설치 및 설정
echo "🐳 Docker 환경 설정 중..."
ansible-playbook -i inventory/${CLOUD_PROVIDER}_${ENVIRONMENT}.yml playbooks/install-docker.yml

# 6. 애플리케이션 배포
echo "📦 애플리케이션 배포 중..."
ansible-playbook -i inventory/${CLOUD_PROVIDER}_${ENVIRONMENT}.yml playbooks/deploy-apps.yml

# 7. 모니터링 설정
echo "📊 모니터링 설정 중..."
ansible-playbook -i inventory/${CLOUD_PROVIDER}_${ENVIRONMENT}.yml playbooks/setup-monitoring.yml

# 8. 헬스 체크
echo "🏥 헬스 체크 수행 중..."
./scripts/health-check.sh $CLOUD_PROVIDER $ENVIRONMENT

echo "✅ 배포 완료!"
echo "🌐 Frontend: http://$(terraform -chdir=./terraform/$CLOUD_PROVIDER output -raw frontend_ip):3000"
echo "📊 Grafana: http://$(terraform -chdir=./terraform/$CLOUD_PROVIDER output -raw monitoring_ip):3001"
echo "🔍 OpenSearch Dashboard: http://$(terraform -chdir=./terraform/$CLOUD_PROVIDER output -raw search_ip):5601"
```

#### 11.5.2 Ansible 플레이북 예시

```yaml
# playbooks/deploy-apps.yml
---
- name: Deploy WKMS Applications
  hosts: all
  become: yes
  
  vars:
    docker_compose_version: "2.20.2"
    app_dir: "/opt/wkms"
    
  tasks:
    - name: Create application directory
      file:
        path: "{{ app_dir }}"
        state: directory
        mode: '0755'
    
    - name: Copy application files
      synchronize:
        src: ../
        dest: "{{ app_dir }}/"
        delete: yes
        rsync_opts:
          - "--exclude=.git"
          - "--exclude=terraform"
          - "--exclude=*.pyc"
    
    - name: Copy environment-specific config
      template:
        src: "{{ item.src }}"
        dest: "{{ app_dir }}/{{ item.dest }}"
      loop:
        - { src: "docker-compose.{{ ansible_hostname }}.yml.j2", dest: "docker-compose.yml" }
        - { src: "env.{{ environment }}.j2", dest: ".env" }
    
    - name: Pull Docker images
      command: docker-compose pull
      args:
        chdir: "{{ app_dir }}"
    
    - name: Build custom images
      command: docker-compose build
      args:
        chdir: "{{ app_dir }}"
    
    - name: Start services
      command: docker-compose up -d
      args:
        chdir: "{{ app_dir }}"
    
    - name: Wait for services to be healthy
      uri:
        url: "http://localhost:8000/health"
        method: GET
      register: health_check
      until: health_check.status == 200
      retries: 30
      delay: 10
```

### 11.6 비용 분석 및 비교

#### 11.6.1 Azure vs AWS VM 기반 비용 비교

| 항목                    | Azure VM     | AWS EC2      | 비고                 |
| --------------------- | ------------ | ------------ | ------------------ |
| **웹 계층** (2x 4vCPU)   | $240         | $220         | 프론트엔드, API Gateway |
| **앱 계층** (3x 8vCPU)   | $480         | $450         | 마이크로서비스들           |
| **AI 계층** (1x GPU)    | $600         | $550         | AI 모델 서빙           |
| **데이터 계층** (2x 4vCPU) | $280         | $250         | DB, 캐시, 검색         |
| **스토리지** (2TB SSD)    | $160         | $140         | 데이터 저장             |
| **네트워크**              | $80          | $70          | 로드밸런서, 트래픽         |
| **백업**                | $60          | $50          | 스냅샷, 백업            |
| **모니터링**              | $40          | $30          | 로그, 메트릭            |
| **총계**                | **$1,940/월** | **$1,760/월** |                    |
| **연간 비용**             | **$23,280**  | **$21,120**  |                    |

#### 11.6.2 기존 방안들과의 비교

| 구분         | 현재 Azure | AWS 관리형 | AWS+오픈소스 | AWS VM |
| ---------- | -------- | ------- | -------- | ------ |
| **월 비용**   | $1,489   | $706    | $383     | $1,760 |
| **벤더 종속성** | 높음       | 중간      | 낮음       | 낮음     |
| **커스터마이징** | 낮음       | 중간      | 높음       | 최고     |
| **운영 복잡도** | 낮음       | 낮음      | 중간       | 높음     |
| **성능**     | 좋음       | 좋음      | 매우 좋음    | 최고     |
| **확장성**    | 자동       | 자동      | 수동       | 수동     |
| **재해복구**   | 관리형      | 관리형     | 수동       | 수동     |

#### 11.6.3 장단점 분석

**장점:**
- ✅ **완전한 벤더 독립성**: 다른 클라우드로 이전 용이
- ✅ **최대 성능**: 전용 리소스로 최적화 가능
- ✅ **비용 예측성**: 고정 비용, 예상치 못한 요금 없음
- ✅ **데이터 주권**: 완전한 데이터 통제권
- ✅ **커스터마이징**: 모든 레벨에서 자유로운 설정
- ✅ **멀티리전**: 재해복구 및 지역 확장 용이

**단점:**
- ❌ **높은 운영 복잡도**: 전문 인력 필요
- ❌ **초기 설정 비용**: 구축 시간과 노력 많이 소요
- ❌ **수동 스케일링**: 자동 확장 기능 직접 구현 필요
- ❌ **보안 책임**: 모든 보안 설정을 직접 관리
- ❌ **24/7 운영**: 상시 모니터링 및 유지보수 필요

### 11.7 권장 시나리오

#### 11.7.1 적합한 상황

```yaml
recommended_for:
  - 대규모 엔터프라이즈 (1000+ 사용자)
  - 높은 보안 요구사항
  - 데이터 주권이 중요한 경우
  - 장기적 비용 절감 목표
  - 전문 DevOps 팀 보유
  - 멀티클라우드 전략 필요
  - 특수한 커스터마이징 요구사항
```

#### 11.7.2 도입 로드맵

```yaml
phase_1: # 3개월
  - 단일 클라우드(AWS)에서 PoC 구축
  - 핵심 서비스 컨테이너화
  - 기본 모니터링 설정
  
phase_2: # 6개월
  - 프로덕션 환경 구축
  - CI/CD 파이프라인 완성
  - 보안 강화 및 백업 설정
  
phase_3: # 12개월
  - Azure 이중화 환경 구축
  - 고급 모니터링 및 알림
  - 자동 복구 시스템 구축
```

이제 완전한 세 가지 옵션을 제공할 수 있습니다:
1. **Azure 현재 상태 유지**
2. **AWS 관리형 서비스 마이그레이션** (52% 절감)
3. **AWS + 오픈소스 하이브리드** (74% 절감)
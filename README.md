# InsightBridge - AI 지식생성 플랫폼

## 프로젝트 개요

InsightBridge는 문서를 기반으로 지식을 자동 생성하고 관리하는 AI 플랫폼입니다. 대용량 문서를 처리하여 구조화된 지식으로 변환하고, 자연어 검색과 Q&A 기능을 제공합니다.

### 주요 기능

- 📄 **문서 처리**: PDF, PPT, Word 등 다양한 형식의 문서 자동 처리
- 🧠 **AI 지식 생성**: 문서 내용을 기반으로 구조화된 지식 자동 생성
- 🔍 **자연어 검색**: 한국어 특화 검색 엔진을 통한 정확한 정보 검색
- 💬 **AI Q&A**: RAG(Retrieval-Augmented Generation) 기반 질의응답 시스템
- 📊 **지식 관리**: 지식 컨테이너를 통한 체계적인 지식 분류 및 관리
- 👥 **권한 관리**: 역할 기반 접근 제어 및 사용자 관리

## 기술 스택

### Backend

- **Framework**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL 13+ with pgvector
- **Cache**: Redis 6+
- **AI/ML**: OpenAI API, Azure OpenAI, AWS Bedrock
- **Search**: pgvector, Elasticsearch (선택적)

### Frontend

- **Framework**: React 18+ with TypeScript
- **UI Components**: Ant Design, Material-UI
- **State Management**: Redux Toolkit
- **Build Tool**: Vite

### Infrastructure

- **Container**: Docker, Docker Compose
- **Orchestration**: Kubernetes (EKS, AKS, GKE)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus, Grafana

## 시작하기

### 개발 환경 설정

#### 1. 저장소 클론

```bash
git clone https://github.com/your-org/InsightBridge.git
cd InsightBridge
```

#### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 환경 변수 설정
```

#### 3. Docker Compose로 실행

```bash
docker-compose up -d
```

애플리케이션이 실행되면:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API 문서: http://localhost:8000/docs

### 상세 설정 가이드

배포 및 환경 설정에 대한 자세한 내용은 다음 가이드를 참조하세요:

- 🚀 **배포 가이드**: [deployment/README.md](./deployment/README.md)
- ☸️ **Kubernetes 배포**: [k8s/README.md](./k8s/README.md)
- 🔧 **환경 설정**: [ENV_MANAGEMENT_GUIDE.md](./ENV_MANAGEMENT_GUIDE.md)

## 프로젝트 구조

```
InsightBridge/
├── backend/                    # FastAPI 백엔드 애플리케이션
│   ├── app/                   # 애플리케이션 코드
│   ├── requirements.txt       # Python 의존성
│   └── Dockerfile            # 백엔드 Docker 이미지
├── frontend/                  # React 프론트엔드 애플리케이션
│   ├── src/                  # 소스 코드
│   ├── package.json          # Node.js 의존성
│   └── Dockerfile           # 프론트엔드 Docker 이미지
├── deployment/               # 배포 관련 파일들
│   ├── docker/              # Docker 배포 설정
│   └── cloud/               # 클라우드 배포 설정
├── k8s/                     # Kubernetes 매니페스트
│   ├── deployment-guides/   # 클라우드별 배포 가이드
│   └── manifests/          # K8s YAML 파일들
├── postgres/               # 데이터베이스 스키마 및 설정
├── docs/                   # 프로젝트 문서
└── docker-compose.yml      # 로컬 개발 환경 설정
```

## API 문서

자세한 API 사용법은 다음에서 확인할 수 있습니다:
- **Swagger UI**: http://localhost:8000/docs (서버 실행 후)
- **ReDoc**: http://localhost:8000/redoc

## 개발 가이드

### Backend 개발

- [Backend API 구조 가이드](./backend/API_STRUCTURE_GUIDE.md)
- [초기 데이터 설정](./backend/INIT_DATA_GUIDE.md)
- [비밀번호 관리 가이드](./backend/PASSWORD_MANAGEMENT_GUIDE.md)

### Frontend 개발

- [Frontend-Backend 연결 가이드](./FRONTEND_BACKEND_CONNECTION_GUIDE.md)
- [UI/UX 표준](./ui_ux_standards.md)

### 데이터베이스

- [한국어 검색 설정](./postgres/KOR_SEARCH_SETUP.md)
- [마이그레이션 계획](./MIGRATION_PLAN.md)

### PPT 처리

- [PPT 파이프라인 분석](./PPT_PIPELINE_ANALYSIS_COMPLETE.md)
- [PPT 개선 로드맵](./PPT_ENHANCEMENT_ROADMAP.md)
- [PPT 테스트 가이드](./PPT_TESTING_GUIDE.md)

## 배포 옵션

### 1. Docker Compose (개발/테스트)

```bash
docker-compose up -d
```

### 2. Kubernetes (운영)

클라우드별 배포 가이드:
- [AWS EKS 배포](./k8s/deployment-guides/eks-deployment.md)
- [Azure AKS 배포](./k8s/deployment-guides/aks-deployment.md)
- [Google GKE 배포](./k8s/deployment-guides/gke-deployment.md)

## 모니터링

- **로그**: 애플리케이션 로그는 `logs/` 디렉토리에 저장
- **메트릭**: Prometheus 메트릭을 통한 성능 모니터링
- **헬스체크**: `/health` 엔드포인트를 통한 서비스 상태 확인

## 기여하기

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 라이선스

이 프로젝트는 [MIT License](LICENSE) 하에 배포됩니다.

## 문의

- **이슈**: [GitHub Issues](https://github.com/your-org/InsightBridge/issues)
- **문서**: [프로젝트 Wiki](https://github.com/your-org/InsightBridge/wiki)
- **이메일**: support@insightbridge.com

---

📚 **추가 문서**
- [시스템 설계 개요](./01.docs/01.system_overview_design.md)
- [검색 및 Q&A 서비스](./01.docs/03.search_and_qa_service.md)
- [지식 컨테이너 관리](./01.docs/04.knowledge_container_management.md)
- [AI 지식 생성](./01.docs/05.ai_knowledge_generation.md)

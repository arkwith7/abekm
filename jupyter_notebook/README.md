# 🧪 WKMS 테스트 및 분석 시스템

이 디렉토리는 WKMS(지식 관리 시스템)의 다양한 기능을 테스트하고 분석하기 위한 주피터 노트북과 도구들을 포함합니다.

## 📁 디렉토리 구조

```
jupyter_notebook/
├── tests/                          # 테스트 관련 코드
│   ├── rag_chat/                   # RAG 채팅 시스템 테스트
│   │   ├── automated_rag_tester.py # 자동화된 RAG 테스트 실행기
│   │   └── multiturn_improvement/  # 멀티턴 대화 개선 관련
│   ├── document_processing/        # 문서 전처리 테스트 (예정)
│   │   ├── text_extraction/        # 텍스트 추출 테스트
│   │   ├── chunking_strategy/      # 청킹 전략 테스트
│   │   └── embedding_generation/   # 임베딩 생성 테스트
│   └── hybrid_search/              # 하이브리드 검색 테스트 (예정)
│       ├── semantic_search/        # 의미적 검색 테스트
│       ├── keyword_search/         # 키워드 검색 테스트
│       └── fusion_algorithms/      # 검색 결과 융합 알고리즘
├── data/                           # 테스트 데이터
│   ├── ground_truth/              # 그라운드 트루스 데이터
│   │   ├── ground_truth_criteria.csv
│   │   ├── documents_analysis.csv
│   │   └── documents_analysis_detail.json
│   ├── test_results/              # 테스트 결과 저장
│   │   ├── rag_chat/             # RAG 채팅 테스트 결과
│   │   ├── document_processing/   # 문서 처리 테스트 결과
│   │   └── hybrid_search/        # 하이브리드 검색 테스트 결과
│   └── sample_documents/          # 테스트용 샘플 문서들
├── utils/                         # 공통 유틸리티
│   ├── analyze_uploads_documents.py # 업로드 문서 분석 도구
│   ├── test_data_generator.py      # 테스트 데이터 생성 도구
│   └── common_test_utils.py        # 공통 테스트 유틸리티
├── ai_agent_chat_test.ipynb       # RAG 채팅 시스템 테스트 노트북
├── textract_rag_pipeline_test.ipynb # Textract RAG 파이프라인 테스트
├── aws_bedrock_chat.ipynb          # AWS Bedrock 채팅 테스트
├── opensource_pipeline_test.ipynb  # 오픈소스 파이프라인 테스트
└── README.md                       # 이 파일
```

## 🎯 주요 기능

### 1. RAG 채팅 시스템 테스트
- **자동화된 테스트**: 130개 테스트 케이스 자동 실행
- **멀티턴 대화 개선**: 주제 전환 감지 및 컨텍스트 필터링
- **성능 분석**: 통계적 유의성 검정 포함

### 2. 문서 처리 테스트 (개발 예정)
- **텍스트 추출**: 다양한 문서 형식에서 텍스트 추출 품질 테스트
- **청킹 전략**: 최적의 문서 분할 방법 실험
- **임베딩 생성**: 벡터 임베딩 품질 및 성능 평가

### 3. 하이브리드 검색 테스트 (개발 예정)
- **의미적 검색**: 벡터 유사도 기반 검색 성능
- **키워드 검색**: BM25 등 전통적 검색 성능
- **융합 알고리즘**: 다양한 검색 결과 결합 방법 실험

## 🚀 빠른 시작

### 환경 설정
```bash
cd /home/admin/wkms-aws
source .venv/bin/activate
pip install -r jupyter_notebook/requirements.txt
```

### RAG 채팅 테스트 실행
```bash
cd jupyter_notebook/tests/rag_chat
python automated_rag_tester.py
```

### 문서 분석 및 그라운드 트루스 생성
```bash
cd jupyter_notebook/utils
python analyze_uploads_documents.py
```

### 3. 환경 변수 확인
`/home/admin/wkms-aws/backend/.env` 파일에서 다음 설정들이 올바른지 확인:

```properties
# AWS Bedrock 설정
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# 모델 설정
DEFAULT_LLM_PROVIDER=bedrock
DEFAULT_EMBEDDING_PROVIDER=bedrock
BEDROCK_LLM_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# 데이터베이스 설정
DATABASE_URL=postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms
```

## 🚀 노트북 실행 방법

### 방법 1: Jupyter Lab 실행
```bash
cd /home/admin/wkms-aws
jupyter lab jupyter_notebook/aws_bedrock_chat.ipynb
```

### 방법 2: Jupyter Notebook 실행
```bash
cd /home/admin/wkms-aws
jupyter notebook jupyter_notebook/aws_bedrock_chat.ipynb
```

### 방법 3: VS Code에서 실행
1. VS Code에서 `aws_bedrock_chat.ipynb` 파일 열기
2. Python 인터프리터를 `.venv` 가상환경으로 선택
3. 셀 단위로 실행

## 📖 노트북 사용법

### 1. 순차적 실행 (권장)
- 첫 번째 셀부터 순서대로 실행
- 각 단계별로 테스트 결과 확인
- 오류 발생 시 해당 셀에서 중단하여 문제 해결

### 2. 개별 테스트
- 특정 기능만 테스트하고 싶은 경우
- 해당 셀과 필요한 의존성 셀만 실행

### 3. 사용자 정의 질문 테스트
- 마지막 셀의 `user_question` 변수 수정
- 다양한 질문으로 RAG 성능 테스트

## 🔧 문제해결

### 자주 발생하는 오류들

#### 1. AWS 자격증명 오류
```
AWS 자격증명을 확인할 수 없습니다.
```
**해결방법:**
- `.env` 파일의 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 확인
- AWS CLI 설정 확인: `aws configure list`
- IAM 권한에 Bedrock 액세스 권한 추가

#### 2. 데이터베이스 연결 오류
```
could not connect to server
```
**해결방법:**
- PostgreSQL 컨테이너 상태 확인: `docker ps`
- 데이터베이스 재시작: `docker compose restart postgres`
- 연결 정보 확인: `DATABASE_URL` 설정

#### 3. 모듈 import 오류
```
ModuleNotFoundError: No module named 'app'
```
**해결방법:**
- 노트북 실행 경로 확인 (WKMS 루트에서 실행)
- 가상환경 활성화 확인
- 백엔드 의존성 재설치

#### 4. Bedrock 모델 접근 오류
```
Model access denied
```
**해결방법:**
- AWS 콘솔에서 Bedrock 모델 액세스 요청
- 리전 설정 확인 (ap-northeast-2)
- IAM 정책에 Bedrock 권한 추가

## 📊 성능 최적화 팁

### 1. 검색 성능 향상
- `RAG_SIMILARITY_THRESHOLD` 값 조정 (0.3 ~ 0.7)
- `RAG_MAX_CHUNKS` 값 조정 (10 ~ 50)

### 2. 답변 품질 향상
- `TEMPERATURE` 값 조정 (0.1 ~ 0.9)
- `MAX_TOKENS` 값 조정 (1024 ~ 4096)

### 3. 한국어 처리 최적화
- `KOREAN_NLP_PROVIDER=hybrid` 사용
- 사용자 사전 추가 (`dictionaries/company_dict.txt`)

## 📈 테스트 결과 해석

### 성공적인 테스트 지표
- ✅ Bedrock 연결 성공
- ✅ 임베딩 차원: 1024
- ✅ 검색 결과: 3개 이상
- ✅ 처리 시간: 5초 이내
- ✅ 답변 길이: 100자 이상

### 주의사항
- AWS Bedrock 사용량에 따른 과금 발생 가능
- 대량 테스트 시 API 제한율 고려
- 민감한 정보 테스트 시 주의

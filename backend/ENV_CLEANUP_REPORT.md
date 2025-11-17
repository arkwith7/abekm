# backend/.env 불필요한 환경 변수 분석 보고서

**분석 날짜**: 2025-10-27  
**분석 대상**: `/home/wjadmin/Dev/InsightBridge/backend/.env`  
**분석 방법**: `app/core/config.py`의 Settings 클래스 기준

---

## 📊 전체 요약

- **총 환경 변수**: 113개
- **config.py에 선언됨**: 75개 ✅
- **config.py에 미선언**: 38개 ❌
- **삭제 가능 비율**: 33.6%

---

## 🚨 삭제 가능한 환경 변수 (38개)

### 1. JWT 관련 (3개) - **중복 변수**

config.py에서 `secret_key`, `algorithm`, `access_token_expire_minutes`로 이미 선언되어 있어 중복입니다.

```bash
# ❌ 삭제 가능 (중복)
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480
```

**대체 변수** (config.py):
```python
secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
algorithm: str = "HS256"
access_token_expire_minutes: int = 30
```

**권장 조치**: ❌ **backend/.env에서 삭제** (`.env.development`, `.env.production`에는 유지)

---

### 2. AWS Textract 관련 (19개) - **미사용 기능**

현재 Azure Document Intelligence를 사용 중이며, AWS Textract는 전혀 사용하지 않습니다.

```bash
# ❌ 삭제 가능 (미사용)
TEXTRACT_MODE=layout
TEXTRACT_FEATURE_TYPES=TABLES,FORMS,LAYOUT
TEXTRACT_MAX_CONCURRENCY=3
TEXTRACT_ENABLE_ASYNC=true
TEXTRACT_MAX_PAGES=50
TEXTRACT_CONFIDENCE_THRESHOLD=80.0
TEXTRACT_USE_ASYNC_THRESHOLD_SIZE=5242880
TEXTRACT_USE_ASYNC_PAGE_COUNT=10
TEXTRACT_JOB_POLL_INTERVAL=4
TEXTRACT_JOB_TIMEOUT=600
TEXTRACT_S3_BUCKET=ABEKM-file-bucket-20250910
TEXTRACT_RESULT_PREFIX=textract/results
TEXTRACT_RATE_LIMIT_PER_MIN=60
TEXTRACT_MAX_RETRIES=3
TEXTRACT_FALLBACK_ON_FAILURE=true
TEXTRACT_LOG_RAW_RESPONSE=false
TEXTRACT_ENABLE_PII_MASKING=true
TEXTRACT_ENABLE_QUERIES=false
TEXTRACT_QUERIES=총금액,서명자,문서제목
```

**권장 조치**: ❌ **모두 삭제** (AWS Textract 사용하지 않음)

---

### 3. RAG 검색 관련 (5개) - **일부 중복**

`hybrid_search_weights`로 통합되었으므로 일부 변수는 불필요합니다.

```bash
# ✅ 사용 중
RAG_SIMILARITY_THRESHOLD=0.3  # 사용됨
RAG_MAX_CHUNKS=30              # 사용됨
RAG_USE_RERANKING=true         # 사용됨

# ❌ 삭제 가능 (중복)
RAG_KEYWORD_BOOST=0.5          # hybrid_search_weights로 대체
RAG_SEMANTIC_BOOST=0.5         # hybrid_search_weights로 대체
```

**대체 변수** (config.py):
```python
hybrid_search_weights: dict = {
    "semantic": 0.7,
    "keyword": 0.3
}
```

**권장 조치**: ❌ **RAG_KEYWORD_BOOST, RAG_SEMANTIC_BOOST만 삭제**

---

### 4. 데이터베이스 관련 (3개) - **Docker 전용**

`backend/.env`에서는 `DATABASE_URL`만 사용하며, `POSTGRES_*` 변수는 Docker Compose에서만 필요합니다.

```bash
# ❌ backend/.env에서는 불필요 (DATABASE_URL로 충분)
POSTGRES_USER=wkms
POSTGRES_PASSWORD=wkms123
POSTGRES_DB=wkms

# ✅ 사용 중
DATABASE_URL=postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms
```

**권장 조치**: 
- ❌ **backend/.env에서 삭제** (DATABASE_URL만 유지)
- ✅ **`.env.development`, `.env.production`에는 유지** (Docker Compose가 사용)

---

### 5. 한국어 NLP 관련 (5개) - **제거된 기능**

2025-10-16에 kiwipiepy가 제거되었으므로 관련 설정은 불필요합니다.

```bash
# ❌ 삭제 가능 (kiwipiepy 제거됨)
KOREAN_NLP_PROVIDER=hybrid
KIWI_MODEL_TYPE=sbg
KIWI_TYPOS_CORRECTION=basic_with_continual_and_lengthening
USER_DICTIONARY_PATH=dictionaries/company_dict.txt
KOREAN_STOPWORDS_PATH=dictionaries/korean_stopwords.txt
```

**권장 조치**: ❌ **모두 삭제**

---

### 6. AWS S3 관련 (3개) - **일부 사용**

```bash
# ✅ 사용 중
AWS_S3_BUCKET=ABEKM-file-bucket-20250910  # 실제 사용됨

# ⚠️ 부분 사용 (getattr로 참조)
S3_PRESIGN_EXPIRY_SECONDS=3600  # files.py에서 getattr로 사용
USE_AWS_TEXTRACT=true           # 미사용 (Azure DI 사용 중)
```

**권장 조치**: 
- ✅ **AWS_S3_BUCKET 유지** (현재 사용 중)
- ⚠️ **S3_PRESIGN_EXPIRY_SECONDS 유지** (config.py에 선언됨)
- ❌ **USE_AWS_TEXTRACT 삭제** (미사용)

---

## 📋 삭제 권장 환경 변수 전체 목록 (33개)

```bash
# JWT 중복 (3개)
JWT_SECRET_KEY
JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRE_MINUTES

# Textract 미사용 (20개)
USE_AWS_TEXTRACT
TEXTRACT_MODE
TEXTRACT_FEATURE_TYPES
TEXTRACT_MAX_CONCURRENCY
TEXTRACT_ENABLE_ASYNC
TEXTRACT_MAX_PAGES
TEXTRACT_CONFIDENCE_THRESHOLD
TEXTRACT_USE_ASYNC_THRESHOLD_SIZE
TEXTRACT_USE_ASYNC_PAGE_COUNT
TEXTRACT_JOB_POLL_INTERVAL
TEXTRACT_JOB_TIMEOUT
TEXTRACT_S3_BUCKET
TEXTRACT_RESULT_PREFIX
TEXTRACT_RATE_LIMIT_PER_MIN
TEXTRACT_MAX_RETRIES
TEXTRACT_FALLBACK_ON_FAILURE
TEXTRACT_LOG_RAW_RESPONSE
TEXTRACT_ENABLE_PII_MASKING
TEXTRACT_ENABLE_QUERIES
TEXTRACT_QUERIES

# RAG 중복 (2개)
RAG_KEYWORD_BOOST
RAG_SEMANTIC_BOOST

# 데이터베이스 (backend/.env에서만, 3개)
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB

# 한국어 NLP (kiwipiepy 제거됨, 5개)
KOREAN_NLP_PROVIDER
KIWI_MODEL_TYPE
KIWI_TYPOS_CORRECTION
USER_DICTIONARY_PATH
KOREAN_STOPWORDS_PATH
```

---

## ✅ 유지해야 하는 중요 환경 변수

```bash
# 데이터베이스
DATABASE_URL=postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://localhost:6379/0

# AWS
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=ABEKM-file-bucket-20250910

# Azure Blob Storage
AZURE_BLOB_ACCOUNT_NAME=blobstoragephs1
AZURE_BLOB_ACCOUNT_KEY=...
AZURE_BLOB_CONTAINER_RAW=wkms-raw
AZURE_BLOB_CONTAINER_INTERMEDIATE=wkms-intermediate
AZURE_BLOB_CONTAINER_DERIVED=wkms-derived

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_LLM_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Azure Document Intelligence
USE_AZURE_DOCUMENT_INTELLIGENCE_PDF=true
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=...
AZURE_DOCUMENT_INTELLIGENCE_API_KEY=...

# 기타
STORAGE_BACKEND=azure_blob
CORS_ORIGINS=["http://localhost:3000","http://15.165.163.233:3000"]
```

---

## 💡 조치 가이드

### 1단계: 백업

```bash
cp backend/.env backend/.env.backup.$(date +%Y%m%d)
```

### 2단계: 불필요한 변수 제거

다음 스크립트를 실행하여 자동 정리:

```bash
cd backend
grep -v -E '^(JWT_SECRET_KEY|JWT_ALGORITHM|JWT_ACCESS_TOKEN_EXPIRE_MINUTES|USE_AWS_TEXTRACT|TEXTRACT_|RAG_KEYWORD_BOOST|RAG_SEMANTIC_BOOST|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB|KOREAN_NLP_PROVIDER|KIWI_|USER_DICTIONARY_PATH|KOREAN_STOPWORDS_PATH)=' .env > .env.cleaned
mv .env.cleaned .env
```

### 3단계: 동기화 확인

```bash
# 다른 환경 파일과 동기화 확인
./shell-script/sync-check-env.sh
```

### 4단계: 테스트

```bash
# 백엔드 서버 시작 테스트
cd backend
python -m uvicorn app.main:app --reload
```

---

## 📊 정리 후 예상 결과

- **정리 전**: 113개 환경 변수
- **정리 후**: 80개 환경 변수 (예상)
- **감소량**: 33개 (29.2%)
- **파일 크기**: 약 30% 감소

---

## ⚠️ 주의 사항

1. **Docker 환경 파일 분리**: 
   - `backend/.env`: 로컬 개발용 (최소한의 변수만)
   - `.env.development`: Docker Compose 개발 환경용
   - `.env.production`: Docker Compose 프로덕션 환경용

2. **POSTGRES_* 변수**: 
   - `backend/.env`에서는 삭제 가능
   - `.env.development`, `.env.production`에서는 **반드시 유지**

3. **향후 Textract 사용 계획**: 
   - 현재 Azure DI 사용 중
   - AWS Textract 사용 계획이 없다면 삭제 권장

---

**작성자**: GitHub Copilot  
**분석 도구**: Python regex + grep_search  
**검증 방법**: config.py Settings 클래스 필드 매칭

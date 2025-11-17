# AWS Bedrock LLM & Embedding 설정 가이드

## 📋 개요
이 문서는 WKMS에서 AWS Bedrock의 Claude 3.5 Sonnet v2와 Titan/Cohere Embedding 모델을 사용하기 위한 구체적인 설정 방법을 안내합니다.

## 🔧 사전 준비사항

### 1. AWS 계정 및 권한 설정

#### AWS IAM 사용자 생성
```bash
# AWS CLI 설치 (Ubuntu/Debian)
sudo apt update
sudo apt install awscli

# AWS CLI 버전 확인
aws --version
```

#### IAM 정책 설정
다음 권한이 필요한 IAM 정책을 생성하세요:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel"
            ],
            "Resource": [
                "arn:aws:bedrock:ap-northeast-2::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "arn:aws:bedrock:ap-northeast-2::foundation-model/amazon.titan-embed-text-v2:0",
                "arn:aws:bedrock:ap-northeast-2::foundation-model/cohere.embed-multilingual-v3"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "opensearch:ESHttpPost",
                "opensearch:ESHttpPut",
                "opensearch:ESHttpGet",
                "opensearch:ESHttpDelete"
            ],
            "Resource": "arn:aws:es:ap-northeast-2:*:domain/wkms-search/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::wkms-documents/*"
        }
    ]
}
```

### 2. Bedrock 모델 액세스 요청

#### AWS Console에서 모델 액세스 활성화
1. AWS Console → Amazon Bedrock → Model access
2. 다음 모델들의 액세스 요청:
   - **Claude 3.5 Sonnet v2** (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
   - **Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`)
   - **Cohere Embed Multilingual v3** (`cohere.embed-multilingual-v3`)

#### CLI를 통한 모델 목록 확인
```bash
# 사용 가능한 모델 목록 확인
aws bedrock list-foundation-models --region ap-northeast-2

# 특정 모델 상세 정보 확인
aws bedrock get-foundation-model \
    --model-identifier anthropic.claude-3-5-sonnet-20241022-v2:0 \
    --region ap-northeast-2
```

## 🔑 환경 변수 설정

### backend/.env 파일 구성
```bash
# AWS 기본 설정
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key

# Bedrock 모델 설정
BEDROCK_TEXT_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_TEXT_MODEL_NAME=Claude 3.5 Sonnet v2

BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_EMBEDDING_MODEL_NAME=Titan Text Embeddings V2

BEDROCK_ALT_EMBEDDING_MODEL_ID=cohere.embed-multilingual-v3
BEDROCK_ALT_EMBEDDING_MODEL_NAME=Marengo Embed 2.7

# Bedrock 파라미터
BEDROCK_MAX_TOKENS=4096
BEDROCK_TEMPERATURE=0.7
BEDROCK_TOP_P=0.9
BEDROCK_TOP_K=250

# 벡터 검색 설정
VECTOR_DIMENSION=1536
SIMILARITY_THRESHOLD=0.7

# OpenSearch 설정 (선택사항)
OPENSEARCH_ENDPOINT=https://your-domain.ap-northeast-2.es.amazonaws.com
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=wkms-documents
```

## 🚀 실행 가이드

### 1. 개발 환경 설정
```bash
# 프로젝트 디렉토리로 이동
cd /home/admin/wkms-aws

# 환경 변수 파일 복사 및 수정
cp backend/.env.example backend/.env
# backend/.env 파일을 편집하여 AWS 인증 정보 입력

# 개발 환경 실행
./setup.sh
```

### 2. 수동 실행 (단계별)
```bash
# Docker 네트워크 생성
docker network create wkms-network

# 서비스 빌드 및 실행
docker-compose up --build -d

# 로그 확인
docker-compose logs -f backend
```

### 3. 모델 연결 테스트
```bash
# 컨테이너 내부에서 Python 테스트
docker-compose exec backend python -c "
import asyncio
from app.services.bedrock_service import bedrock_service

async def test():
    status = await bedrock_service.check_model_access()
    print(f'모델 상태: {status}')
    
    if status['claude_3_5_sonnet']:
        response = await bedrock_service.generate_text_claude('안녕하세요!')
        print(f'Claude 응답: {response}')

asyncio.run(test())
"
```

## 📱 프론트엔드 사용법

### 1. 기본 채팅
- 브라우저에서 `http://localhost:3000` 접속
- 로그인 후 Bedrock Chat 인터페이스 사용
- 메시지 입력 시 자동으로 Claude 3.5 Sonnet v2 사용

### 2. 문서 업로드 및 검색
```typescript
// 문서 업로드
const uploadResult = await bedrockService.uploadDocument(file, 'titan');

// 벡터 검색
const searchResults = await bedrockService.searchDocuments('질문', 10, 'titan');
```

### 3. 직접 임베딩 생성
```typescript
// Titan 임베딩
const titanEmbeddings = await bedrockService.generateEmbeddings({
    texts: ['텍스트1', '텍스트2'],
    model: 'titan'
});

// Cohere 임베딩
const cohereEmbeddings = await bedrockService.generateEmbeddings({
    texts: ['텍스트1', '텍스트2'],
    model: 'cohere'
});
```

## 🛠️ API 엔드포인트

### Bedrock 관련 API
```
GET  /api/bedrock/models/status         # 모델 상태 확인
POST /api/bedrock/chat                  # Claude 채팅
POST /api/bedrock/embeddings            # 임베딩 생성
POST /api/bedrock/documents/upload      # 문서 업로드
GET  /api/bedrock/documents/search      # 문서 검색
```

### 사용 예시
```bash
# 모델 상태 확인
curl -X GET "http://localhost:8000/api/bedrock/models/status" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Claude와 채팅
curl -X POST "http://localhost:8000/api/bedrock/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "안녕하세요, WKMS에 대해 설명해주세요",
    "include_context": true
  }'

# 임베딩 생성
curl -X POST "http://localhost:8000/api/bedrock/embeddings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "texts": ["이것은 테스트 텍스트입니다"],
    "model": "titan"
  }'
```

## 🔍 문제 해결

### 1. 모델 액세스 오류
```
Error: Access denied to model
```
**해결방법:**
- AWS Console에서 Bedrock 모델 액세스 승인 확인
- IAM 권한 재확인
- 리전 설정 확인 (ap-northeast-2)

### 2. 인증 오류
```
Error: Unable to locate credentials
```
**해결방법:**
```bash
# AWS 인증 정보 확인
aws configure list

# 환경 변수 확인
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY

# 컨테이너 내 환경 변수 확인
docker-compose exec backend env | grep AWS
```

### 3. 네트워크 오류
```
Error: Unable to connect to Bedrock
```
**해결방법:**
- 보안 그룹에서 Bedrock 엔드포인트 허용
- VPC 엔드포인트 설정 확인
- 네트워크 연결 상태 확인

### 4. 임베딩 차원 불일치
```
Error: Vector dimension mismatch
```
**해결방법:**
- `VECTOR_DIMENSION` 설정 확인 (Titan: 1536, Cohere: 1024)
- OpenSearch 인덱스 매핑 재생성

## 📊 모니터링 및 로깅

### 로그 확인
```bash
# 전체 로그
docker-compose logs -f

# 백엔드만
docker-compose logs -f backend

# 특정 시간 이후 로그
docker-compose logs --since="2024-01-01T00:00:00" backend
```

### 성능 모니터링
```python
# app/services/bedrock_service.py에 추가된 로깅
logger.info(f"Claude 응답 시간: {response_time}ms")
logger.info(f"임베딩 생성 완료: {len(embeddings)}개")
```

## 🎯 최적화 팁

### 1. 비용 최적화
- 필요시에만 컨텍스트 검색 활성화
- 임베딩 캐싱 구현
- 토큰 사용량 모니터링

### 2. 성능 최적화
- 배치 임베딩 처리
- 연결 풀링 설정
- 비동기 처리 활용

### 3. 보안 강화
- IAM 최소 권한 원칙
- API 키 로테이션
- 로그에서 민감정보 제거

이제 `./setup.sh`를 실행하여 전체 시스템을 구동할 수 있습니다!

# GPT-5-Nano API 호환성 완전 가이드

## 📋 개요

GPT-5-Nano 모델은 Azure OpenAI의 최신 모델로, 기존 GPT-4 시리즈와 다른 API 파라미터를 사용합니다.

## 🚨 주요 차이점

### 1. Temperature 파라미터 미지원

**일반 모델 (GPT-4, GPT-4o, GPT-4o-mini):**
```python
AzureChatOpenAI(
    temperature=0.3,  # ✅ 지원
    ...
)
```

**GPT-5-Nano:**
```python
AzureChatOpenAI(
    # temperature 파라미터 없음 ❌
    ...
)
```

**오류 메시지:**
```
Unsupported parameter: 'temperature' is not supported with this model.
```

---

### 2. max_tokens → max_completion_tokens

**일반 모델 (GPT-4, GPT-4o, GPT-4o-mini):**
```python
AzureChatOpenAI(
    max_tokens=500,  # ✅ 지원
    ...
)
```

**GPT-5-Nano:**
```python
AzureChatOpenAI(
    max_completion_tokens=500,  # ✅ 지원
    # max_tokens=500,  # ❌ 미지원
    ...
)
```

**오류 메시지:**
```
Unsupported parameter: 'max_tokens' is not supported with this model. 
Use 'max_completion_tokens' instead.
```

---

## 🔧 해결 방법

### 코드 패턴 (리랭킹 예시)

```python
from langchain_openai import AzureChatOpenAI
from app.core.config import settings
import os

# 모델 이름 확인
deployment_lower = rerank_deployment.lower()

# GPT-5/Nano 계열 모델 확인
if 'gpt-5' in deployment_lower or 'nano' in deployment_lower or 'o1' in deployment_lower or 'o3' in deployment_lower:
    logger.info(f"🔧 리랭킹 모델: {rerank_deployment} (temperature/max_tokens 미지원)")
    
    # max_completion_tokens 사용 (temperature 없음)
    rerank_llm = AzureChatOpenAI(
        azure_endpoint=rerank_endpoint,
        api_key=rerank_api_key,
        api_version=os.getenv("RAG_RERANKING_API_VERSION", settings.azure_openai_api_version),
        deployment_name=rerank_deployment,
        max_completion_tokens=500,  # ✅ gpt-5/nano는 이것 사용
    )
else:
    logger.info(f"🔧 리랭킹 모델: {rerank_deployment} (temperature 지원)")
    
    # 일반 파라미터 사용
    rerank_llm = AzureChatOpenAI(
        azure_endpoint=rerank_endpoint,
        api_key=rerank_api_key,
        api_version=os.getenv("RAG_RERANKING_API_VERSION", settings.azure_openai_api_version),
        deployment_name=rerank_deployment,
        temperature=0.3,           # ✅ 일반 모델은 이것 사용
        max_tokens=500,            # ✅ 일반 모델은 이것 사용
    )
```

---

## 📊 모델별 파라미터 호환성 표

| 모델 | temperature | max_tokens | max_completion_tokens |
|------|-------------|------------|----------------------|
| **GPT-4** | ✅ | ✅ | ✅ |
| **GPT-4o** | ✅ | ✅ | ✅ |
| **GPT-4o-mini** | ✅ | ✅ | ✅ |
| **GPT-5-Nano** | ❌ | ❌ | ✅ |
| **O1 시리즈** | ❌ | ❌ | ✅ |
| **O3 시리즈** | ❌ | ❌ | ✅ |

---

## 🎯 적용 사례

### 1. RAG 리랭킹 (현재 프로젝트)

**파일**: `backend/app/services/chat/rag_search_service.py`  
**라인**: 1210-1230

**시나리오:**
- 리랭킹 전용 설정 있음 → `gpt-4o-mini` 사용 (temperature 지원)
- 리랭킹 전용 설정 없음 → `gpt-5-nano` 사용 (temperature 미지원)

**수정 전 문제:**
```python
# 모든 모델에 동일하게 적용
rerank_llm = AzureChatOpenAI(
    max_tokens=500,  # ❌ gpt-5-nano에서 오류
)
```

**수정 후:**
```python
# 모델별 분기 처리
if 'gpt-5' in deployment_lower or 'nano' in deployment_lower:
    rerank_llm = AzureChatOpenAI(
        max_completion_tokens=500,  # ✅ gpt-5-nano 지원
    )
else:
    rerank_llm = AzureChatOpenAI(
        temperature=0.3,
        max_tokens=500,  # ✅ 일반 모델 지원
    )
```

---

### 2. AI Service (답변 생성)

**파일**: `backend/app/services/core/ai_service.py`  
**라인**: 150-170

**시나리오:**
- RAG 답변 생성에 `gpt-5-nano` 사용

**수정 완료:**
```python
# gpt-5-nano는 model_kwargs로 max_completion_tokens 전달
if 'gpt-5' in model_lower or 'nano' in model_lower:
    llm = AzureChatOpenAI(
        model_kwargs={"max_completion_tokens": max_tokens},  # ✅
    )
```

---

## 🔍 디버깅 팁

### 1. 로그 확인

**리랭킹 모델 확인:**
```log
🔧 리랭킹 모델: gpt-5-nano (temperature/max_tokens 미지원)
🔧 리랭킹 모델: gpt-4o-mini (temperature 지원)
```

**오류 패턴:**
```log
HTTP Request: POST https://...openai.azure.com/.../chat/completions "HTTP/1.1 400 Bad Request"

Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' ...", ...}}
```

### 2. 모델 이름 감지

```python
deployment_lower = deployment_name.lower()

# GPT-5/Nano 계열 확인
is_gpt5_nano = (
    'gpt-5' in deployment_lower or 
    'nano' in deployment_lower or 
    'o1' in deployment_lower or 
    'o3' in deployment_lower
)
```

### 3. API 버전 확인

```bash
# 최신 API 버전 권장
AZURE_OPENAI_API_VERSION=2024-12-01-preview
RAG_RERANKING_API_VERSION=2024-12-01-preview
```

---

## 📝 체크리스트

### 코드 수정 시 확인사항

- [ ] 모델 이름 감지 로직 추가
- [ ] GPT-5/Nano 분기 처리
- [ ] max_completion_tokens 사용 (GPT-5/Nano)
- [ ] max_tokens 사용 (일반 모델)
- [ ] temperature 제외 (GPT-5/Nano)
- [ ] temperature 포함 (일반 모델)
- [ ] 로그 메시지 명확히 작성
- [ ] Exception 처리 추가

### 배포 전 테스트

- [ ] GPT-5-Nano 모델 테스트
- [ ] GPT-4o-mini 모델 테스트
- [ ] Fallback 로직 테스트
- [ ] 400 Bad Request 오류 없음
- [ ] 리랭킹 정상 작동
- [ ] 답변 생성 정상 작동

---

## 🚀 배포 가이드

### 1. 코드 수정 확인

```bash
# 수정된 파일 확인
git diff backend/app/services/chat/rag_search_service.py
git diff backend/app/services/core/ai_service.py
```

### 2. 백엔드 재시작

```bash
# 현재 프로세스 종료
ps aux | grep uvicorn
kill <PID>

# 가상환경 활성화
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate

# 백엔드 실행
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

### 3. 검증

```bash
# RAG 질의 테스트
# 로그에서 확인:
# - "🔧 리랭킹 모델: gpt-5-nano (temperature/max_tokens 미지원)"
# - "✅ 리랭킹 완료: X개 선택" (기본 순서 아님)
# - 400 Bad Request 오류 없음
```

---

## 📖 관련 문서

- **Azure OpenAI API 레퍼런스**: https://learn.microsoft.com/azure/ai-services/openai/reference
- **LangChain AzureChatOpenAI**: https://python.langchain.com/docs/integrations/chat/azure_chat_openai
- **GPT-5-Nano 문서**: (최신 모델 문서 참조)

---

## ✅ 수정 이력

| 날짜 | 수정 내용 | 파일 | 담당자 |
|------|----------|------|--------|
| 2025-11-06 | temperature 미지원 처리 | ai_service.py | GitHub Copilot |
| 2025-11-06 | max_tokens → max_completion_tokens | rag_search_service.py | GitHub Copilot |
| 2025-11-06 | Fallback 로직 추가 | rag_search_service.py | GitHub Copilot |

---

**작성일**: 2025-11-06  
**작성자**: GitHub Copilot  
**상태**: ✅ 완료 (백엔드 재시작 필요)

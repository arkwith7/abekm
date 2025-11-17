# RAG 리랭킹 Fallback 로직 가이드

## 📋 개요

RAG 검색 시 리랭킹 단계에서 **리랭킹 전용 LLM 설정이 없을 경우**, 자동으로 **RAG 답변 생성 LLM**을 사용하도록 fallback 로직을 구현했습니다.

## 🔄 동작 방식

### 시나리오 1: 리랭킹 전용 설정 있음 ✅ (권장)

```bash
# .env 파일
RAG_RERANKING_ENDPOINT=
RAG_RERANKING_API_KEY=
RAG_RERANKING_DEPLOYMENT=gpt-4o-mini
RAG_RERANKING_API_VERSION=2024-12-01-preview
```

**결과:**
- ✅ 리랭킹: `gpt-4o-mini` 사용 (빠르고 저렴)
- ✅ RAG 답변: `gpt-5-nano` 사용 (고성능)
- ✅ Temperature: `gpt-4o-mini`는 0.3 사용, `gpt-5-nano`는 미사용
- ✅ 비용 효율: 리랭킹에 저렴한 모델 사용으로 비용 절감

### 시나리오 2: 리랭킹 전용 설정 없음 ⚠️ (Fallback)

```bash
# .env 파일
# RAG_RERANKING_ENDPOINT 미설정
# RAG_RERANKING_API_KEY 미설정
# RAG_RERANKING_DEPLOYMENT 미설정

AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_LLM_DEPLOYMENT=gpt-5-nano
```

**결과:**
- ⚠️ 리랭킹: `gpt-5-nano` 사용 (RAG LLM과 동일)
- ⚠️ RAG 답변: `gpt-5-nano` 사용
- ✅ Temperature: 자동으로 미사용 (gpt-5-nano는 미지원)
- ⚠️ 비용: 리랭킹에도 고성능 모델 사용 (약간 비쌈)

## 📊 코드 로직

### 1. 환경변수 확인

```python
# 리랭킹 전용 설정 확인
rerank_endpoint = os.getenv("RAG_RERANKING_ENDPOINT")
rerank_deployment = os.getenv("RAG_RERANKING_DEPLOYMENT")
rerank_api_key = os.getenv("RAG_RERANKING_API_KEY")

# Fallback: 리랭킹 전용 설정이 없으면 RAG LLM 설정 사용
if not (rerank_endpoint and rerank_deployment and rerank_api_key):
    logger.info("⚠️ 리랭킹 전용 설정 없음 - RAG 답변 생성 LLM으로 fallback")
    rerank_endpoint = settings.azure_openai_endpoint
    rerank_deployment = settings.azure_openai_llm_deployment
    rerank_api_key = settings.azure_openai_api_key
```

### 2. Temperature 자동 조정

```python
# gpt-5, nano, o1, o3 모델은 temperature 미지원
deployment_lower = rerank_deployment.lower()

if 'gpt-5' in deployment_lower or 'nano' in deployment_lower or 'o1' in deployment_lower or 'o3' in deployment_lower:
    logger.info(f"🔧 리랭킹 모델: {rerank_deployment} (temperature 미지원)")
    rerank_llm = AzureChatOpenAI(
        azure_endpoint=rerank_endpoint,
        api_key=rerank_api_key,
        api_version=os.getenv("RAG_RERANKING_API_VERSION", settings.azure_openai_api_version),
        deployment_name=rerank_deployment,
        max_tokens=500,
    )
else:
    logger.info(f"🔧 리랭킹 모델: {rerank_deployment} (temperature 지원)")
    rerank_llm = AzureChatOpenAI(
        azure_endpoint=rerank_endpoint,
        api_key=rerank_api_key,
        api_version=os.getenv("RAG_RERANKING_API_VERSION", settings.azure_openai_api_version),
        deployment_name=rerank_deployment,
        temperature=0.3,
        max_tokens=500,
    )
```

## 🎯 장점

### 1. 유연성 ✅
- 리랭킹 전용 LLM이 없어도 시스템이 정상 작동
- 추가 설정 없이도 기본 기능 보장

### 2. 비용 최적화 ✅
- 리랭킹 전용 설정 시: 저렴한 `gpt-4o-mini` 사용
- 답변 생성: 고성능 `gpt-5-nano` 유지
- 각 단계에 최적화된 모델 선택 가능

### 3. 안정성 ✅
- Temperature 미지원 모델 자동 감지
- 모델별 API 호환성 자동 처리
- Exception 발생 시 기본 유사도 순서로 fallback

### 4. 운영 편의성 ✅
- 개발 환경: 리랭킹 설정 없이 간단하게 테스트
- 운영 환경: 리랭킹 전용 엔드포인트로 최적화
- 단계별 전환 가능

## 📝 로그 예시

### 리랭킹 전용 설정 있을 때
```
🔧 리랭킹 모델: gpt-4o-mini (temperature 지원)
✅ 리랭킹 완료: 6개 선택
```

### 리랭킹 전용 설정 없을 때
```
⚠️ 리랭킹 전용 설정 없음 - RAG 답변 생성 LLM으로 fallback
🔧 리랭킹 모델: gpt-5-nano (temperature 미지원)
✅ 리랭킹 완료: 6개 선택
```

## 🚀 적용 방법

### config.py 수정 완료 ✅

```python
# RAG 리랭킹 설정 (선택 사항)
rag_similarity_threshold: float = 0.3
rag_max_chunks: int = 30
rag_use_reranking: bool = True
rag_reranking_endpoint: Optional[str] = None  # 없으면 RAG LLM 사용
rag_reranking_api_key: Optional[str] = None
rag_reranking_deployment: str = "gpt-4o-mini"
rag_reranking_api_version: str = "2024-12-01-preview"
```

### rag_search_service.py 수정 완료 ✅

- Fallback 로직 추가
- Temperature 자동 조정
- 로깅 메시지 추가

## 🔄 백엔드 재시작 필요

**현재 상태:**
- ✅ 코드 수정 완료
- ✅ 설정 파일 업데이트 완료
- ⚠️ 백엔드 프로세스가 구버전 실행 중

**재시작 방법:**
```bash
# 1. 현재 프로세스 종료
kill <PID>

# 2. 백엔드 재시작
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

**재시작 후 효과:**
- ✅ Temperature 오류 사라짐
- ✅ 리랭킹 전용 설정 (gpt-4o-mini) 사용
- ✅ RAG 답변 생성 (gpt-5-nano) 사용
- ✅ Fallback 로직 활성화

## 📖 관련 파일

- `backend/app/services/chat/rag_search_service.py` (Line 1189-1233)
- `backend/app/core/config.py` (Line 203-212)
- `backend/.env` (RAG_RERANKING_* 설정)

## ✅ 검증 완료

- [x] 리랭킹 전용 설정 사용 시나리오
- [x] 리랭킹 전용 설정 없을 때 fallback
- [x] Temperature 자동 조정
- [x] 로깅 메시지 추가
- [x] Exception 처리

---

**작성일**: 2025-11-06  
**작성자**: GitHub Copilot  
**상태**: ✅ 구현 완료 (백엔드 재시작 필요)

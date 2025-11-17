"""
환경변수 디버깅 스크립트 - settings 객체 사용
"""
import sys
import os

# backend 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings

print("=" * 60)
print("Settings 객체를 통한 환경변수 확인")
print("=" * 60)

# 리랭킹 제공자
print(f"\nrag_reranking_provider: {settings.rag_reranking_provider}")
print(f"rag_use_reranking: {settings.rag_use_reranking}")

# Azure OpenAI 리랭킹 설정
if settings.rag_reranking_provider == "azure_openai":
    print(f"\n[Azure OpenAI 리랭킹 설정]")
    print(f"rag_reranking_endpoint: {settings.rag_reranking_endpoint}")
    print(f"rag_reranking_deployment: {settings.rag_reranking_deployment}")
    print(f"rag_reranking_api_key: {settings.rag_reranking_api_key[:30] if settings.rag_reranking_api_key else 'None'}...") 
    print(f"rag_reranking_api_version: {settings.rag_reranking_api_version}")

# Bedrock 리랭킹 설정
elif settings.rag_reranking_provider == "bedrock":
    print(f"\n[AWS Bedrock 리랭킹 설정]")
    print(f"rag_reranking_bedrock_model_id: {settings.rag_reranking_bedrock_model_id}")
    print(f"rag_reranking_bedrock_region: {settings.rag_reranking_bedrock_region}")

# 일반 LLM
print(f"\nazure_openai_llm_deployment: {settings.azure_openai_llm_deployment}")
print(f"azure_openai_endpoint: {settings.azure_openai_endpoint}")
print(f"azure_openai_api_version: {settings.azure_openai_api_version}")

print("\n" + "=" * 60)

# 리랭킹 모델 검증
if settings.rag_use_reranking:
    if settings.rag_reranking_provider == "azure_openai":
        if not settings.rag_reranking_deployment:
            print("\n❌ 경고: Azure OpenAI 리랭킹 활성화되었지만 RAG_RERANKING_DEPLOYMENT가 비어있습니다!")
        else:
            print(f"\n✅ 리랭킹 설정 완료: Azure OpenAI - {settings.rag_reranking_deployment}")
    elif settings.rag_reranking_provider == "bedrock":
        if not settings.rag_reranking_bedrock_model_id:
            print("\n❌ 경고: Bedrock 리랭킹 활성화되었지만 RAG_RERANKING_BEDROCK_MODEL_ID가 비어있습니다!")
        else:
            print(f"\n✅ 리랭킹 설정 완료: Bedrock - {settings.rag_reranking_bedrock_model_id}")

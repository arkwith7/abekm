#!/usr/bin/env python
"""Azure OpenAI 배포 확인 스크립트"""

import os
import httpx
from dotenv import load_dotenv

# backend/.env 로드
load_dotenv("/home/admin/wkms-aws/backend/.env")

endpoint = os.getenv("RAG_RERANKING_ENDPOINT", "").rstrip("/")
api_key = os.getenv("RAG_RERANKING_API_KEY", "")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

print(f"🔍 엔드포인트: {endpoint}")
print(f"🔍 API 버전: {api_version}")
print()

# 배포 목록 확인 (Azure OpenAI REST API)
url = f"{endpoint}/openai/deployments?api-version={api_version}"

try:
    response = httpx.get(
        url,
        headers={"api-key": api_key},
        timeout=30.0
    )
    
    print(f"📡 응답 코드: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        deployments = data.get("data", [])
        
        print(f"\n✅ 배포된 모델 목록 ({len(deployments)}개):\n")
        for idx, dep in enumerate(deployments, 1):
            dep_id = dep.get("id", "N/A")
            model = dep.get("model", "N/A")
            status = dep.get("status", "N/A")
            print(f"{idx}. ID: {dep_id}")
            print(f"   모델: {model}")
            print(f"   상태: {status}")
            print()
            
        # gpt-4o-mini 검색
        gpt4o_mini_found = [d for d in deployments if "4o-mini" in d.get("id", "").lower() or "4o-mini" in d.get("model", "").lower()]
        
        if gpt4o_mini_found:
            print(f"🎯 gpt-4o-mini 관련 배포 발견:")
            for dep in gpt4o_mini_found:
                print(f"   - {dep.get('id')}")
        else:
            print("❌ gpt-4o-mini 관련 배포를 찾을 수 없습니다.")
            print("\n💡 Azure Portal에서 배포를 생성해야 합니다:")
            print("   1. Azure Portal → Azure OpenAI")
            print("   2. Model deployments → Create new deployment")
            print("   3. Model: gpt-4o-mini")
            print("   4. Deployment name: gpt-4o-mini (또는 기억하기 쉬운 이름)")
    else:
        print(f"❌ API 호출 실패: {response.text}")
        
except Exception as e:
    print(f"❌ 에러 발생: {e}")

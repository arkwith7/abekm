#!/usr/bin/env python3
"""Azure Blob Storage 파일 존재 여부 확인 스크립트"""
import sys
import os
from pathlib import Path

# 백엔드 모듈 경로 추가
sys.path.insert(0, '/home/wjadmin/Dev/InsightBridge/backend')

# .env 파일 로드
from dotenv import load_dotenv
env_path = Path('/home/wjadmin/Dev/InsightBridge/backend/.env')
load_dotenv(dotenv_path=env_path)

from app.services.core.azure_blob_service import get_azure_blob_service

def check_blob_exists(blob_path: str, purpose: str = 'raw'):
    """Azure Blob Storage에 파일이 존재하는지 확인"""
    try:
        azure_blob = get_azure_blob_service()
        
        # 컨테이너와 blob 경로 분리
        container_name = azure_blob._get_container(purpose)
        
        print(f"🔍 Azure Blob 확인:")
        print(f"  - Container: {container_name}")
        print(f"  - Blob Path: {blob_path}")
        
        # Blob 존재 여부 확인
        blob_client = azure_blob.client.get_blob_client(container=container_name, blob=blob_path)
        
        if blob_client.exists():
            properties = blob_client.get_blob_properties()
            print(f"\n✅ 파일 존재!")
            print(f"  - 크기: {properties.size:,} bytes")
            print(f"  - 타입: {properties.content_settings.content_type}")
            print(f"  - 생성일: {properties.creation_time}")
            print(f"  - 수정일: {properties.last_modified}")
            return True
        else:
            print(f"\n❌ 파일이 존재하지 않습니다!")
            return False
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        return False

def list_blobs_in_container(purpose: str = 'raw', prefix: str = ""):
    """컨테이너 내 블롭 목록 조회"""
    try:
        azure_blob = get_azure_blob_service()
        container_name = azure_blob._get_container(purpose)
        
        print(f"\n📂 컨테이너 '{container_name}' 블롭 목록:")
        if prefix:
            print(f"  - Prefix: {prefix}")
        
        container_client = azure_blob.client.get_container_client(container_name)
        blobs = list(container_client.list_blobs(name_starts_with=prefix))
        
        if not blobs:
            print(f"  ⚠️ 블롭이 없습니다.")
            return
        
        print(f"\n  총 {len(blobs)}개 파일:")
        for i, blob in enumerate(blobs[:20], 1):  # 최대 20개만 표시
            print(f"  {i}. {blob.name} ({blob.size:,} bytes)")
        
        if len(blobs) > 20:
            print(f"  ... 외 {len(blobs) - 20}개 더")
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

if __name__ == "__main__":
    # 문서 ID 13의 경로
    # DB: raw/WJ_MS_SERVICE/2025/10/b31a9394_ProductSpec_SmartInsulinPump_KO_v0.1.docx
    # 다운로드 코드에서 분리: purpose=raw, blob_path=WJ_MS_SERVICE/2025/10/...
    
    blob_path = "WJ_MS_SERVICE/2025/10/b31a9394_ProductSpec_SmartInsulinPump_KO_v0.1.docx"
    
    print("=" * 80)
    print("🔎 Azure Blob Storage 파일 확인")
    print("=" * 80)
    
    # 1. 특정 파일 확인
    exists = check_blob_exists(blob_path, purpose='raw')
    
    # 2. WJ_MS_SERVICE 전체 디렉토리 목록 확인
    print("\n" + "=" * 80)
    list_blobs_in_container(purpose='raw', prefix='WJ_MS_SERVICE/')
    
    # 3. 전체 raw 컨테이너 목록 확인
    print("\n" + "=" * 80)
    print("📂 전체 raw 컨테이너 블롭 목록 (모든 파일):")
    list_blobs_in_container(purpose='raw', prefix="")
    
    print("\n" + "=" * 80)
    if exists:
        print("✅ 파일이 Azure Blob Storage에 존재합니다!")
    else:
        print("❌ 파일이 Azure Blob Storage에 없습니다. 업로드를 다시 해야 합니다.")
    print("=" * 80)

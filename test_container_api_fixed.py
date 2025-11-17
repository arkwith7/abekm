#!/usr/bin/env python3
"""
컨테이너 API 테스트 (라우터 prefix 수정 후)
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_container_apis():
    """컨테이너 API 전체 테스트"""
    
    # 1. 로그인
    print("=" * 60)
    print("1️⃣ 로그인 테스트")
    print("=" * 60)
    
    login_data = {
        "emp_no": "ADMIN001",
        "password": "admin123!"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            token = result.get("access_token")
            print(f"✅ 로그인 성공! Token: {token[:50]}...")
            
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            # 2. 컨테이너 목록 조회
            print("\n" + "=" * 60)
            print("2️⃣ 컨테이너 목록 조회 (/api/v1/containers/)")
            print("=" * 60)
            
            response = requests.get(f"{BASE_URL}/api/v1/containers/", headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 성공!")
                print(f"Total Containers: {result.get('total_count', 0)}")
                print(f"Containers: {len(result.get('containers', []))}")
                
                if result.get('containers'):
                    print("\n첫 번째 컨테이너:")
                    print(json.dumps(result['containers'][0], indent=2, ensure_ascii=False))
            else:
                print(f"❌ 실패!")
                print(f"Error: {response.text}")
            
            # 3. 컨테이너 계층 구조 조회
            print("\n" + "=" * 60)
            print("3️⃣ 컨테이너 계층 구조 조회 (/api/v1/containers/hierarchy)")
            print("=" * 60)
            
            response = requests.get(f"{BASE_URL}/api/v1/containers/hierarchy", headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 성공!")
                print(f"Tree structure:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"❌ 실패!")
                print(f"Error: {response.text}")
                
        else:
            print(f"❌ 로그인 실패!")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ 예외 발생: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_container_apis()

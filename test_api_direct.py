"""
API 직접 호출 테스트
"""
import requests
import json

# 로그인하여 토큰 획득
login_url = "http://localhost:8000/api/v1/auth/login"
login_data = {
    "emp_no": "77107791",  # 홍길동 사용자의 사번
    "password": "staff2025"
}

print("=" * 100)
print("1. 로그인 시도...")
print("=" * 100)

try:
    response = requests.post(login_url, json=login_data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    if response.status_code == 200:
        token = response.json().get('access_token')
        print(f"\n토큰 획득 성공: {token[:50]}...")
        
        # 권한 신청 목록 조회
        print("\n" + "=" * 100)
        print("2. 내 권한 신청 목록 조회...")
        print("=" * 100)
        
        requests_url = "http://localhost:8000/api/v1/permission-requests/my-requests"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(requests_url, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n응답 데이터:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            print(f"\n총 {data.get('total', 0)}건의 권한 신청")
            requests_list = data.get('requests', [])
            print(f"실제 반환된 항목 수: {len(requests_list)}")
            
            for idx, req in enumerate(requests_list, 1):
                print(f"\n[{idx}] 신청 ID: {req.get('id')}")
                print(f"    컨테이너: {req.get('container_name')}")
                print(f"    권한 레벨: {req.get('requested_permission_level')}")
                print(f"    상태: {req.get('status')}")
                print(f"    신청일: {req.get('created_at')}")
        else:
            print(f"Error: {response.text}")
    else:
        print("로그인 실패")
        
except Exception as e:
    print(f"오류 발생: {e}")
    import traceback
    traceback.print_exc()

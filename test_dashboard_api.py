#!/usr/bin/env python3
"""
대시보드 API 엔드포인트 테스트
실제 JWT 토큰으로 API 호출 테스트
"""
import requests
import json

# API 설정
BASE_URL = "http://localhost:8001"
LOGIN_URL = f"{BASE_URL}/api/v1/auth/login"
DASHBOARD_URL = f"{BASE_URL}/api/v1/dashboard/summary"

# 테스트 사용자
TEST_USER = {
    "emp_no": "77107791",
    "password": "admin"  # 실제 비밀번호로 변경 필요
}

def test_dashboard_api():
    """대시보드 API 테스트"""
    print("=" * 60)
    print("🧪 대시보드 API 엔드포인트 테스트")
    print("=" * 60)
    
    # 1. 로그인하여 토큰 획득
    print("\n[1] 로그인 시도...")
    try:
        login_response = requests.post(LOGIN_URL, json=TEST_USER)
        if login_response.status_code == 200:
            login_data = login_response.json()
            token = login_data.get("access_token")
            print(f"   ✅ 로그인 성공!")
            print(f"   🔑 토큰: {token[:30]}...")
        else:
            print(f"   ❌ 로그인 실패: {login_response.status_code}")
            print(f"   📄 응답: {login_response.text}")
            return
    except Exception as e:
        print(f"   ❌ 로그인 요청 실패: {e}")
        return
    
    # 2. 대시보드 API 호출
    print("\n[2] 대시보드 summary API 호출...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        dashboard_response = requests.get(DASHBOARD_URL, headers=headers)
        
        if dashboard_response.status_code == 200:
            data = dashboard_response.json()
            print(f"   ✅ API 호출 성공!")
            print(f"\n   📊 대시보드 데이터:")
            print(f"   ├─ 내 문서: {data.get('my_documents_count', 0)}개")
            print(f"   ├─ AI 대화: {data.get('chat_sessions_count', 0)}개")
            print(f"   ├─ 권한 요청: {data.get('pending_requests_count', 0)}개")
            print(f"   └─ 컨테이너: {data.get('total_containers', 0)}개")
            
            # 세션 카운트가 1인지 확인
            chat_count = data.get('chat_sessions_count', 0)
            if chat_count > 0:
                print(f"\n   ✅ AI 대화 카운트 정상: {chat_count}개")
            else:
                print(f"\n   ⚠️ AI 대화 카운트가 0입니다. 타입 변환 이슈가 있을 수 있습니다.")
            
            # 전체 응답 출력 (디버깅용)
            print(f"\n   📋 전체 응답:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
        else:
            print(f"   ❌ API 호출 실패: {dashboard_response.status_code}")
            print(f"   📄 응답: {dashboard_response.text}")
            
    except Exception as e:
        print(f"   ❌ API 요청 실패: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    test_dashboard_api()

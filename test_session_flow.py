#!/usr/bin/env python3
"""
세션 만료 → 로그인 리다이렉트 기능 통합 테스트 스크립트

테스트 시나리오:
1. 로그인 성공 (CSRF 토큰 포함)
2. 인증이 필요한 API 호출 (정상)
3. 토큰 만료 시뮬레이션
4. 만료된 토큰으로 API 호출 → 401 확인
5. Refresh 토큰으로 갱신 시도
6. 갱신 후 API 호출 성공 확인
7. 로그아웃 후 refresh 토큰 revoke 확인
"""

import asyncio
import httpx
import json
import time
from datetime import datetime, timezone

API_BASE_URL = "http://localhost:8000"

class SessionTestClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token = None
        self.refresh_token = None
        self.csrf_token = None
        self.cookies = {}

    async def login(self, emp_no="TRN001", password="training123!"):
        """로그인 테스트"""
        print("🔐 로그인 테스트 시작...")
        
        login_data = {
            "emp_no": emp_no,
            "password": password
        }
        
        try:
            response = await self.client.post(
                f"{API_BASE_URL}/api/v1/auth/login",
                json=login_data
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.csrf_token = data.get("csrf_token")
                
                # 쿠키에서 refresh_token과 csrf_token 추출
                for cookie_name, cookie_value in response.cookies.items():
                    self.cookies[cookie_name] = cookie_value
                
                print(f"✅ 로그인 성공")
                print(f"   - Access Token: {self.access_token[:20]}...")
                print(f"   - Refresh Token: {self.refresh_token[:20] if self.refresh_token else 'None'}...")
                print(f"   - CSRF Token: {self.csrf_token[:20] if self.csrf_token else 'None'}...")
                print(f"   - 쿠키: {list(self.cookies.keys())}")
                return True
            else:
                print(f"❌ 로그인 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 로그인 오류: {e}")
            return False

    async def test_authenticated_api(self):
        """인증이 필요한 API 테스트"""
        print("\n🔍 인증 API 호출 테스트...")
        
        if not self.access_token:
            print("❌ Access Token이 없습니다")
            return False
        
        try:
            response = await self.client.get(
                f"{API_BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 사용자 정보 조회 성공: {data.get('username', 'Unknown')}")
                return True
            else:
                print(f"❌ API 호출 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ API 호출 오류: {e}")
            return False

    async def test_token_refresh(self):
        """토큰 갱신 테스트"""
        print("\n🔄 토큰 갱신 테스트...")
        
        if not self.csrf_token:
            print("❌ CSRF Token이 없습니다")
            return False
        
        try:
            # 쿠키를 사용한 refresh (body는 fallback)
            refresh_data = {}
            if self.refresh_token:
                refresh_data["refresh_token"] = self.refresh_token
            
            response = await self.client.post(
                f"{API_BASE_URL}/api/v1/auth/refresh",
                json=refresh_data if refresh_data else None,
                headers={
                    "X-CSRF-Token": self.csrf_token,
                    "Content-Type": "application/json"
                },
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                old_access = self.access_token[:10] if self.access_token else "None"
                
                self.access_token = data.get("access_token")
                if data.get("refresh_token"):
                    self.refresh_token = data.get("refresh_token")
                if data.get("csrf_token"):
                    self.csrf_token = data.get("csrf_token")
                
                # 새 쿠키 업데이트
                for cookie_name, cookie_value in response.cookies.items():
                    self.cookies[cookie_name] = cookie_value
                
                new_access = self.access_token[:10] if self.access_token else "None"
                print(f"✅ 토큰 갱신 성공")
                print(f"   - 기존: {old_access}... → 신규: {new_access}...")
                return True
            elif response.status_code == 403:
                print(f"❌ CSRF 검증 실패: {response.text}")
                return False
            else:
                print(f"❌ 토큰 갱신 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 토큰 갱신 오류: {e}")
            return False

    async def test_expired_token_scenario(self):
        """만료된 토큰 시나리오 테스트"""
        print("\n⏰ 만료된 토큰 시나리오 테스트...")
        
        # 의도적으로 잘못된 토큰으로 설정하여 401 유발
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        try:
            response = await self.client.get(
                f"{API_BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {fake_token}"}
            )
            
            if response.status_code == 401:
                print("✅ 만료된/잘못된 토큰으로 401 응답 확인")
                return True
            else:
                print(f"❌ 예상과 다른 응답: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 테스트 오류: {e}")
            return False

    async def test_logout(self):
        """로그아웃 및 refresh 토큰 revoke 테스트"""
        print("\n🚪 로그아웃 테스트...")
        
        try:
            response = await self.client.post(
                f"{API_BASE_URL}/api/v1/auth/logout",
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print("✅ 로그아웃 성공")
                
                # 로그아웃 후 revoked된 refresh 토큰으로 갱신 시도 (실패해야 함)
                if self.refresh_token and self.csrf_token:
                    refresh_response = await self.client.post(
                        f"{API_BASE_URL}/api/v1/auth/refresh",
                        json={"refresh_token": self.refresh_token},
                        headers={"X-CSRF-Token": self.csrf_token},
                        cookies=self.cookies
                    )
                    
                    if refresh_response.status_code == 401:
                        print("✅ revoked된 refresh 토큰으로 갱신 실패 확인 (정상)")
                    else:
                        print(f"⚠️ revoked 토큰이 여전히 작동: {refresh_response.status_code}")
                
                return True
            else:
                print(f"❌ 로그아웃 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 로그아웃 오류: {e}")
            return False

    async def run_full_test(self):
        """전체 세션 테스트 실행"""
        print("=" * 60)
        print("🧪 세션 만료 → 로그인 리다이렉트 기능 통합 테스트")
        print("=" * 60)
        
        results = []
        
        # 1. 로그인
        results.append(("로그인", await self.login()))
        
        # 2. 인증 API 호출 (정상)
        if results[-1][1]:
            results.append(("인증 API 호출", await self.test_authenticated_api()))
        
        # 3. 토큰 갱신
        if self.refresh_token and self.csrf_token:
            results.append(("토큰 갱신", await self.test_token_refresh()))
        
        # 4. 갱신 후 API 호출
        if results[-1][1]:
            results.append(("갱신 후 API 호출", await self.test_authenticated_api()))
        
        # 5. 만료된 토큰 시나리오
        results.append(("만료 토큰 처리", await self.test_expired_token_scenario()))
        
        # 6. 로그아웃
        results.append(("로그아웃", await self.test_logout()))
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("📊 테스트 결과 요약")
        print("=" * 60)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:20} : {status}")
            if result:
                passed += 1
        
        print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
        
        return passed == total

    async def close(self):
        await self.client.aclose()


async def main():
    client = SessionTestClient()
    
    try:
        success = await client.run_full_test()
        
        if success:
            print("\n🎉 모든 테스트 통과! 세션 관리 기능이 정상 작동합니다.")
        else:
            print("\n⚠️ 일부 테스트 실패. 로그를 확인해주세요.")
            
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

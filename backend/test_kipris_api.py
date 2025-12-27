#!/usr/bin/env python3
"""
KIPRIS API 검색 테스트 스크립트
다양한 검색 조건으로 API를 테스트하여 올바른 검색 방법을 찾습니다.
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

KIPRIS_API_KEY = os.getenv('KIPRIS_API_KEY', '')
BASE_URL = "http://plus.kipris.or.kr/kipo-api"

async def test_search(test_name: str, params: dict):
    """검색 테스트 실행"""
    url = f"{BASE_URL}/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
    
    print(f"\n{'='*60}")
    print(f"🔍 테스트: {test_name}")
    print(f"   URL: {url}")
    print(f"   파라미터: {params}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            text = response.text
            
            print(f"   상태 코드: {response.status_code}")
            
            # 결과 수 파싱
            if "<totalCount>" in text:
                import re
                match = re.search(r'<totalCount>(\d+)</totalCount>', text)
                if match:
                    total = int(match.group(1))
                    print(f"   ✅ 총 결과 수: {total}건")
            
            if "<item>" in text:
                # 첫 번째 item의 제목만 출력
                import re
                match = re.search(r'<inventionTitle>([^<]+)</inventionTitle>', text)
                if match:
                    print(f"   📄 첫 번째 결과: {match.group(1)[:50]}...")
            else:
                print(f"   ⚠️ 검색 결과 없음")
                # 오류 메시지 확인
                if "<resultMsg>" in text:
                    match = re.search(r'<resultMsg>([^<]+)</resultMsg>', text)
                    if match:
                        print(f"   ❌ 메시지: {match.group(1)}")
                
                # 응답 일부 출력 (디버깅용)
                print(f"   📝 응답 일부: {text[:500]}...")
            
            return text
        except Exception as e:
            print(f"   ❌ 오류: {e}")
            return None


async def main():
    print("=" * 60)
    print("KIPRIS API 검색 테스트")
    print("=" * 60)
    
    if not KIPRIS_API_KEY:
        print("❌ KIPRIS_API_KEY가 설정되지 않았습니다!")
        print("   .env 파일에 KIPRIS_API_KEY를 설정하세요.")
        return
    
    print(f"✅ API 키 설정됨: {KIPRIS_API_KEY[:10]}...")
    
    # 테스트 1: 가장 단순한 검색 (키워드만)
    await test_search(
        "단순 키워드 검색 - '인공지능'",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": "인공지능",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 2: 영어 키워드
    await test_search(
        "영어 키워드 검색 - 'artificial intelligence'",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": "artificial intelligence",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 3: 출원인 검색 (PA: 접두사 없이)
    await test_search(
        "출원인 검색 - 'applicant' 파라미터 사용",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "applicant": "삼성전자",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 4: IPC 코드 검색 (ipc 파라미터)
    await test_search(
        "IPC 코드 검색 - 'ipc' 파라미터 사용",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "ipc": "G06N",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 5: 키워드 + 출원인 조합 (별도 파라미터)
    await test_search(
        "키워드 + 출원인 조합 - 별도 파라미터",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": "인공지능",
            "applicant": "삼성전자",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 6: 키워드 + IPC 조합
    await test_search(
        "키워드 + IPC 조합",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": "인공지능",
            "ipc": "G06N",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 7: 현재 코드 방식 (word에 모든 조건 넣기)
    await test_search(
        "현재 코드 방식 - word에 IPC:/PA: 포함",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": "(IPC:G06N) AND (인공지능) AND (PA:삼성전자)",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 8: 간단한 AND 검색
    await test_search(
        "간단한 AND 검색 - '인공지능 AND 삼성전자'",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": "인공지능 AND 삼성전자",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 9: 쌍따옴표 사용
    await test_search(
        "쌍따옴표 사용 - '\"인공지능\" AND \"삼성전자\"'",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "word": '"인공지능" AND "삼성전자"',
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    # 테스트 10: title 파라미터 사용
    await test_search(
        "title 파라미터 사용",
        {
            "ServiceKey": KIPRIS_API_KEY,
            "title": "인공지능",
            "patent": "true",
            "utility": "true",
            "numOfRows": "10",
            "pageNo": "1",
        }
    )
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
    
    # 수정된 KIPRISClient 테스트
    print("\n\n" + "=" * 60)
    print("🔧 수정된 KIPRISClient 클래스 테스트")
    print("=" * 60)
    
    try:
        from app.services.patent.kipris_client import KIPRISClient
        
        client = KIPRISClient()
        
        # 테스트 1: 키워드만 검색
        print("\n📝 KIPRISClient 테스트 1: keywords=['인공지능']")
        results = await client.search_patents(keywords=["인공지능"], max_results=5)
        print(f"   결과 수: {len(results)}건")
        if results:
            print(f"   첫 번째: {results[0].get('inventionTitle', 'N/A')[:40]}...")
        
        # 테스트 2: 출원인만 검색
        print("\n📝 KIPRISClient 테스트 2: applicants=['삼성전자']")
        results = await client.search_patents(applicants=["삼성전자"], max_results=5)
        print(f"   결과 수: {len(results)}건")
        if results:
            print(f"   첫 번째: {results[0].get('inventionTitle', 'N/A')[:40]}...")
        
        # 테스트 3: 키워드 + 출원인 조합
        print("\n📝 KIPRISClient 테스트 3: keywords=['인공지능'], applicants=['삼성전자']")
        results = await client.search_patents(
            keywords=["인공지능"],
            applicants=["삼성전자"],
            max_results=5
        )
        print(f"   결과 수: {len(results)}건")
        if results:
            print(f"   첫 번째: {results[0].get('inventionTitle', 'N/A')[:40]}...")
        
        # 테스트 4: IPC 코드 + 키워드
        print("\n📝 KIPRISClient 테스트 4: ipc_codes=['G06N'], keywords=['학습']")
        results = await client.search_patents(
            ipc_codes=["G06N"],
            keywords=["학습"],
            max_results=5
        )
        print(f"   결과 수: {len(results)}건")
        if results:
            print(f"   첫 번째: {results[0].get('inventionTitle', 'N/A')[:40]}...")
        
        print("\n✅ KIPRISClient 테스트 완료!")
        
    except Exception as e:
        print(f"   ❌ 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


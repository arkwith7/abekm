#!/usr/bin/env python3
"""
AI Agent 기반 RAG API 테스트 스크립트

Phase 3: Agent 활성화 및 검증
- Health Check
- Agent Chat 테스트
- A/B 비교 테스트
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any


BASE_URL = "http://localhost:8000"
TIMEOUT = 60.0  # 60초 타임아웃


def print_section(title: str):
    """섹션 제목 출력"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_result(success: bool, message: str, data: Any = None):
    """결과 출력"""
    status = "✅ 성공" if success else "❌ 실패"
    print(f"{status}: {message}")
    if data:
        print(f"  데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")


async def test_health_check() -> bool:
    """Agent Health Check 테스트"""
    print_section("1️⃣ Agent Health Check")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/v1/agent/health")
            
            if response.status_code == 200:
                data = response.json()
                print_result(True, "Agent 시스템 정상", data)
                
                # 주요 정보 출력
                print("\n📊 시스템 상태:")
                print(f"  - Agent 아키텍처: {data.get('use_agent_architecture')}")
                print(f"  - Observability: {data.get('observability_enabled')}")
                print(f"  - 등록된 도구: {len(data.get('tools', []))}개")
                
                if data.get('tools'):
                    print(f"\n🔧 등록된 도구 목록:")
                    for tool in data['tools']:
                        print(f"  - {tool}")
                
                return True
            else:
                print_result(False, f"HTTP {response.status_code}", response.text)
                return False
                
    except Exception as e:
        print_result(False, f"Health check 실패: {str(e)}")
        return False


async def test_agent_chat(query: str, container_id: int = 1, user_id: int = 1) -> Dict[str, Any]:
    """Agent Chat 엔드포인트 테스트"""
    print_section(f"2️⃣ Agent Chat 테스트: '{query}'")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "query": query,
                "container_id": container_id,
                "user_id": user_id,
                "conversation_id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
            
            print(f"📤 요청: {json.dumps(payload, ensure_ascii=False)}\n")
            
            response = await client.post(
                f"{BASE_URL}/api/v1/agent/chat",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                print_result(True, "Agent 실행 완료")
                
                # 주요 정보 출력
                print("\n📝 응답 요약:")
                print(f"  - 검색된 청크: {data.get('chunks_found', 0)}개")
                print(f"  - 실행 시간: {data.get('execution_time_ms', 0)}ms")
                print(f"  - 실행 단계: {len(data.get('steps', []))}개")
                
                if data.get('steps'):
                    print(f"\n🔄 실행된 단계:")
                    for i, step in enumerate(data['steps'], 1):
                        print(f"  {i}. {step.get('tool_name')} - {step.get('status')} ({step.get('duration_ms')}ms)")
                        if step.get('error'):
                            print(f"     ⚠️ 오류: {step.get('error')}")
                
                # 메트릭 정보
                if data.get('metrics'):
                    print(f"\n📊 메트릭:")
                    metrics = data['metrics']
                    print(f"  - 총 실행 시간: {metrics.get('total_duration_ms')}ms")
                    print(f"  - 성공 단계: {metrics.get('successful_steps')}/{metrics.get('total_steps')}")
                    print(f"  - 검색된 아이템: {metrics.get('total_items_retrieved')}")
                
                # 응답 미리보기
                if data.get('answer'):
                    answer = data['answer']
                    preview = answer[:200] + "..." if len(answer) > 200 else answer
                    print(f"\n💬 답변 미리보기:\n{preview}")
                
                return data
            else:
                print_result(False, f"HTTP {response.status_code}", response.text)
                return {}
                
    except Exception as e:
        print_result(False, f"Agent chat 실패: {str(e)}")
        return {}


async def test_agent_compare(query: str, container_id: int = 1, user_id: int = 1) -> Dict[str, Any]:
    """A/B 비교 테스트"""
    print_section(f"3️⃣ A/B 비교 테스트: '{query}'")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT * 2) as client:  # 비교는 2배 시간
            payload = {
                "query": query,
                "container_id": container_id,
                "user_id": user_id,
                "conversation_id": f"compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
            
            print(f"📤 요청: {json.dumps(payload, ensure_ascii=False)}\n")
            
            response = await client.post(
                f"{BASE_URL}/api/v1/agent/compare",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                print_result(True, "A/B 비교 완료")
                
                # 비교 결과 출력
                old_arch = data.get('old_architecture', {})
                new_arch = data.get('new_architecture', {})
                comparison = data.get('comparison', {})
                
                print("\n📊 성능 비교:")
                print(f"\n  [기존 아키텍처]")
                print(f"  - 실행 시간: {old_arch.get('execution_time_ms', 0)}ms")
                print(f"  - 검색된 청크: {old_arch.get('chunks_found', 0)}개")
                
                print(f"\n  [Agent 아키텍처]")
                print(f"  - 실행 시간: {new_arch.get('execution_time_ms', 0)}ms")
                print(f"  - 검색된 청크: {new_arch.get('chunks_found', 0)}개")
                print(f"  - 실행 단계: {len(new_arch.get('steps', []))}개")
                
                if comparison:
                    print(f"\n  [비교 결과]")
                    print(f"  - 속도 차이: {comparison.get('speed_difference', 0)}ms")
                    print(f"  - 청크 차이: {comparison.get('chunks_difference', 0)}개")
                    print(f"  - 더 빠른 방식: {comparison.get('faster', 'N/A')}")
                
                return data
            else:
                print_result(False, f"HTTP {response.status_code}", response.text)
                return {}
                
    except Exception as e:
        print_result(False, f"A/B 비교 실패: {str(e)}")
        return {}


async def main():
    """메인 테스트 함수"""
    print_section("🤖 AI Agent 기반 RAG 테스트 시작")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"서버 URL: {BASE_URL}")
    
    # 1. Health Check
    health_ok = await test_health_check()
    if not health_ok:
        print("\n❌ Health check 실패. 서버가 실행 중인지 확인하세요.")
        print("   실행 방법: cd backend && uvicorn app.main:app --reload")
        return
    
    await asyncio.sleep(2)  # 잠시 대기
    
    # 2. Agent Chat 테스트
    test_queries = [
        "양손잡이 리더십이란 무엇인가요?",
        "혁신과 효율성을 동시에 달성하는 방법",
        "조직의 디지털 전환 전략"
    ]
    
    for query in test_queries:
        result = await test_agent_chat(query)
        if result:
            await asyncio.sleep(2)  # 잠시 대기
    
    # 3. A/B 비교 테스트
    compare_query = test_queries[0]  # 첫 번째 쿼리로 비교
    await test_agent_compare(compare_query)
    
    # 최종 요약
    print_section("✅ 테스트 완료")
    print(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📋 다음 단계:")
    print("  1. 로그 파일 확인: backend/logs/")
    print("  2. Agent 실행 로그에서 '🤖 [AgentChat]' 검색")
    print("  3. 각 tool의 실행 로그 확인")
    print("  4. Frontend 통합 진행")


if __name__ == "__main__":
    asyncio.run(main())

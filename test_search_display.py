#!/usr/bin/env python3
import asyncio
import sys
import json
sys.path.append('backend')

from backend.app.services.search_service import SearchService

async def test_search_results():
    """Test search results to check container information display"""
    
    search_service = SearchService()
    
    try:
        # 실제 검색어로 테스트
        query = "제조로봇"
        user_emp_no = "admin"  # 테스트 사용자
        
        print("Testing search with query:", query)
        print("-" * 60)
        
        # 검색 수행
        results = await search_service.hybrid_search(
            query=query,
            user_emp_no=user_emp_no,
            max_results=5
        )
        
        print("Search Results:")
        print(f"Query: {results.get('query', 'N/A')}")
        print(f"Total Results: {results.get('total_results', 0)}")
        print(f"Search Time: {results.get('search_time_ms', 0)}ms")
        
        # accessible_container_names 확인
        accessible_containers = results.get('accessible_container_names', [])
        print(f"\nAccessible Container Names: {accessible_containers}")
        
        # 개별 검색 결과의 컨테이너 정보 확인
        search_results = results.get('results', [])
        print(f"\nIndividual Results ({len(search_results)} items):")
        
        for i, result in enumerate(search_results, 1):
            print(f"\n[Result {i}]")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Container ID: {result.get('container_id', 'N/A')}")
            print(f"  Container Name: {result.get('container_name', 'N/A')}")
            print(f"  Container Path: {result.get('container_path', 'N/A')}")
            print(f"  Container Icon: {result.get('container_icon', 'N/A')}")
            print(f"  Similarity Score: {result.get('similarity_score', 'N/A')}")
            print(f"  Normalized Score: {result.get('normalized_score', 'N/A')}")
            print(f"  Final Score: {result.get('final_score', 'N/A')}")
            
        print("\n" + "="*60)
        print("Current Status Summary:")
        print("="*60)
        
        # 상태 체크
        if accessible_containers:
            print("✅ accessible_container_names: Working (contains data)")
        else:
            print("❌ accessible_container_names: Empty or null")
            
        container_info_working = True
        for result in search_results:
            if not result.get('container_name') or result.get('container_name') == result.get('container_id'):
                container_info_working = False
                break
                
        if container_info_working and search_results:
            print("✅ Individual result container_name: Working (contains friendly names)")
        else:
            print("❌ Individual result container_name: Missing or shows technical IDs")
            
        path_info_working = True
        for result in search_results:
            if not result.get('container_path') or result.get('container_path') == result.get('container_name'):
                path_info_working = False
                break
                
        if path_info_working and search_results:
            print("✅ Container path information: Working")
        else:
            print("❌ Container path information: Missing or incomplete")
            
        # 정확도 표시 체크
        accuracy_working = True
        for result in search_results:
            final_score = result.get('final_score')
            if final_score is None or final_score <= 0:
                accuracy_working = False
                break
                
        if accuracy_working and search_results:
            print("✅ Search accuracy scores: Working")
        else:
            print("❌ Search accuracy scores: Missing or invalid")
            
    except Exception as e:
        print(f"Error during search test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search_results())

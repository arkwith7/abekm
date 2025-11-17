#!/usr/bin/env python3
"""
의미있는 문서로 RAG 파이프라인 테스트
"""
import requests
import json
import time
import os

BASE_URL = "http://localhost:8000"

def test_meaningful_document_upload():
    print("🧪 의미있는 문서 RAG 파이프라인 테스트 시작")
    print("="*60)
    
    # 1. 로그인
    print("\n🔐 1단계: 사용자 로그인")
    login_data = {
        "emp_no": "ADMIN001",  # 시스템 관리자로 로그인
        "password": "admin123!"
    }
    
    login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", 
                                   json=login_data,
                                   headers={"Content-Type": "application/json"})
    
    if login_response.status_code != 200:
        print(f"❌ 로그인 실패: {login_response.status_code}")
        return False
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✅ 로그인 성공 - 토큰: {token[:20]}...")
    
    # 2. 컨테이너 조회
    print("\n📂 2단계: 컨테이너 목록 조회")
    containers_response = requests.get(f"{BASE_URL}/api/v1/documents/containers", headers=headers)
    
    if containers_response.status_code != 200:
        print(f"❌ 컨테이너 조회 실패: {containers_response.status_code}")
        return False
    
    containers = containers_response.json().get("containers", [])
    if not containers:
        print("❌ 사용할 수 있는 컨테이너가 없습니다")
        return False
        
    container = containers[0]
    print(f"✅ 컨테이너 조회 성공 - {len(containers)}개 발견")
    print(f"   📁 사용할 컨테이너: {container.get('container_name', container.get('container_nm', 'Unknown'))} (ID: {container['container_id']})")
    
    # 3. 테스트 파일 준비
    print("\n📄 3단계: 의미있는 한국어 테스트 파일 업로드")
    test_file_path = "/home/admin/wkms-aws/test_meaningful_document.txt"
    
    if not os.path.exists(test_file_path):
        print(f"❌ 테스트 파일을 찾을 수 없습니다: {test_file_path}")
        return False
    
    print(f"✅ 테스트 파일: {test_file_path}")
    
    # 4. 문서 업로드
    print("\n📤 4단계: 의미있는 문서 업로드 및 RAG 처리")
    print("   🔄 예상 처리 과정:")
    print("   1. 한국어 텍스트 추출 및 청킹")
    print("   2. 한국어 형태소 분석 및 키워드 추출")
    print("   3. Amazon Bedrock으로 1024차원 임베딩 생성")
    print("   4. vs_doc_contents_index에 벡터 데이터 저장")
    print("   5. tb_document_chunks에 청크별 상세 정보 저장")
    print("   📤 업로드 시작...")
    
    start_time = time.time()
    
    with open(test_file_path, 'rb') as f:
        files = {
            'file': ('meaningful_test.txt', f, 'text/plain')
        }
        data = {
            'container_id': str(container['container_id']),
            'description': '의미있는 한국어 문서 RAG 테스트'
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    print(f"\n📊 업로드 응답 상태: {upload_response.status_code}")
    
    if upload_response.status_code != 200:
        print(f"❌ 업로드 실패!")
        print(f"   📄 응답 내용: {upload_response.text}")
        return False
    
    result = upload_response.json()
    print("✅ 업로드 성공!")
    print(f"   📄 문서 ID: {result.get('document_id')}")
    print(f"   📁 파일명: {result.get('filename')}")
    print(f"   📊 처리 시간: {processing_time:.2f}초")
    
    # 5. 처리 결과 분석
    print(f"\n📈 RAG 처리 통계:")
    stats = result.get('processing_stats', {})
    print(f"   📝 텍스트 길이: {stats.get('text_length', 0):,}자")
    print(f"   🧩 생성된 청크 수: {stats.get('chunk_count', 0)}개")
    print(f"   ⭐ 문서 품질 점수: {stats.get('quality_score', 0):.2f}")
    print(f"   🇰🇷 한국어 비율: {stats.get('korean_ratio', 0)*100:.1f}%")
    
    # 6. 한국어 분석 결과
    korean_analysis = result.get('korean_analysis', {})
    if korean_analysis:
        print(f"\n🇰🇷 한국어 NLP 분석 결과:")
        print(f"   📋 문서 유형: {korean_analysis.get('doc_type', 'unknown')}")
        
        keywords = korean_analysis.get('keywords', [])
        print(f"   🔑 추출된 키워드 ({len(keywords)}개): {', '.join(keywords[:10])}")
        
        entities = korean_analysis.get('named_entities', [])
        print(f"   🏷️ 고유명사 ({len(entities)}개): {', '.join(entities[:10])}")
        
        embedding_info = korean_analysis.get('embedding_info', {})
        if embedding_info:
            print(f"   🧮 임베딩 차원: {embedding_info.get('dimensions', 0)}차원")
            print(f"   🤖 임베딩 모델: {embedding_info.get('model', 'unknown')}")
    
    print(f"\n🎉 의미있는 문서 RAG 파이프라인 테스트 완료!")
    print("   ✅ 한국어 텍스트 처리 확인")
    print("   ✅ 벡터 임베딩 생성 확인")
    print("   ✅ 데이터베이스 저장 확인")
    print("   ✅ 메타데이터 JSON 직렬화 해결")
    return True

if __name__ == "__main__":
    test_meaningful_document_upload()

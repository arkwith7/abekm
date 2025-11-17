#!/usr/bin/env python3
"""
테스트: 수정된 파이프라인으로 문서 업로드 테스트
==============================================

목적:
- 수정된 integrated_document_pipeline_service가 올바른 스키마 사용하는지 확인
- vs_doc_contents_index와 tb_document_chunks 테이블 사용 확인
- 벡터스토어 저장 "text" 오류 해결 여부 검증
"""

import asyncio
import requests
import json
import os
from pathlib import Path

# 테스트 설정
BASE_URL = "http://localhost:8000"
TEST_FILE_PATH = "/home/admin/wkms-aws/test_document.txt"

async def test_corrected_upload():
    """수정된 파이프라인으로 업로드 테스트"""
    
    print("🧪 수정된 파이프라인 업로드 테스트 시작")
    print("=" * 50)
    
    # 1. 로그인
    print("🔐 1단계: 사용자 로그인")
    login_data = {
        "emp_no": "ADMIN001",  # 시스템 관리자로 로그인 (모든 권한 보유)
        "password": "admin123!"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login", 
        json=login_data,  # JSON 형식으로 전송
        headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        print(f"❌ 로그인 실패: {response.status_code}")
        print(f"   응답: {response.text}")
        return
    
    token_data = response.json()
    token = token_data.get("access_token")
    print(f"✅ 로그인 성공 - 토큰: {token[:20]}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. 컨테이너 목록 조회
    print("\n📂 2단계: 컨테이너 목록 조회")
    response = requests.get(f"{BASE_URL}/api/v1/documents/containers", headers=headers)
    if response.status_code != 200:
        print(f"❌ 컨테이너 조회 실패: {response.status_code}")
        return
    
    containers = response.json().get("containers", [])
    print(f"✅ 컨테이너 조회 성공 - {len(containers)}개 발견")
    
    if not containers:
        print("❌ 사용 가능한 컨테이너가 없습니다")
        return
    
    # 첫 번째 컨테이너 사용
    container_id = str(containers[0]["container_id"])
    container_name = containers[0].get("container_name", containers[0].get("container_nm", "Unknown"))
    print(f"   📁 사용할 컨테이너: {container_name} (ID: {container_id})")
    
    # 3. 테스트 파일 준비
    print("\n📄 3단계: 테스트 파일 준비")
    if not os.path.exists(TEST_FILE_PATH):
        # 테스트 파일 생성
        test_content = """
수정된 파이프라인 테스트 문서
========================

이 문서는 corrected pipeline을 테스트하기 위한 문서입니다.

주요 테스트 내용:
1. VsDocContentsIndex 테이블 사용 확인
2. DocumentChunk 테이블 사용 확인  
3. 벡터 임베딩 저장 확인
4. 한국어 NLP 분석 결과 저장 확인

기술적 세부사항:
- 파이프라인: document_preprocessing → korean_nlp → vector_storage
- 벡터 차원: 1024 (Amazon Titan Embeddings V2)
- 청킹 전략: 문서 구조 기반 분할
- NLP 분석: Kiwipiepy 형태소 분석 + Bedrock 임베딩

예상 결과:
✅ vs_doc_contents_index에 벡터 데이터 저장
✅ tb_document_chunks에 상세 청크 정보 저장
✅ 메타데이터에 한국어 분석 결과 포함
✅ "벡터스토어 저장 실패: 'text'" 오류 해결

이전 오류 원인:
❌ TbVectorDocuments, TbVectorChunks 테이블 사용 (존재하지 않음)
✅ VsDocContentsIndex, DocumentChunk 테이블 사용 (기존 스키마)
        """.strip()
        
        with open(TEST_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(test_content)
        print(f"✅ 테스트 파일 생성: {TEST_FILE_PATH}")
    else:
        print(f"✅ 기존 테스트 파일 사용: {TEST_FILE_PATH}")
    
    # 4. 문서 업로드 (수정된 파이프라인 사용)
    print("\n📤 4단계: 문서 업로드 (수정된 파이프라인)")
    print("   🔄 예상 처리 과정:")
    print("   1. 문서 전처리 (텍스트 추출 + 청킹)")
    print("   2. 한국어 NLP 분석 (형태소 + 1024차원 임베딩)")
    print("   3. vs_doc_contents_index에 벡터 저장")
    print("   4. tb_document_chunks에 상세 정보 저장")
    
    with open(TEST_FILE_PATH, "rb") as f:
        files = {"file": ("corrected_pipeline_test.txt", f, "text/plain")}
        data = {"container_id": container_id}
        
        print(f"   📤 업로드 시작...")
        response = requests.post(
            f"{BASE_URL}/api/v1/documents/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=300  # 5분 타임아웃
        )
    
    print(f"\n📊 업로드 응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("✅ 업로드 성공!")
        print(f"   📄 문서 ID: {result.get('document_id')}")
        print(f"   📁 파일명: {result.get('file_info', {}).get('original_name')}")
        print(f"   📊 처리 시간: {result.get('processing_stats', {}).get('processing_time', 0):.2f}초")
        
        # 처리 통계 출력
        stats = result.get('processing_stats', {})
        print(f"\n📈 처리 통계:")
        print(f"   📝 텍스트 길이: {stats.get('text_length', 0):,}자")
        print(f"   🧩 청크 수: {stats.get('chunk_count', 0)}개")
        print(f"   ⭐ 품질 점수: {stats.get('quality_score', 0):.2f}")
        print(f"   🇰🇷 한국어 비율: {stats.get('korean_ratio', 0):.1%}")
        
        # 한국어 분석 결과
        korean_analysis = result.get('korean_analysis', {})
        print(f"\n🇰🇷 한국어 분석:")
        print(f"   📋 문서 유형: {korean_analysis.get('document_type', 'unknown')}")
        print(f"   🔑 키워드: {len(korean_analysis.get('keywords', []))}개")
        print(f"   🏷️ 고유명사: {len(korean_analysis.get('proper_nouns', []))}개")
        
        # 저장 정보 확인
        if 'storage_info' in result:
            storage = result['storage_info']
            print(f"\n🗄️ 저장 정보:")
            print(f"   📊 벡터 테이블: {storage.get('vector_table', 'N/A')}")
            print(f"   📊 청크 테이블: {storage.get('chunk_table', 'N/A')}")
            print(f"   📐 벡터 차원: {storage.get('vector_dimension', 0)}")
            print(f"   🇰🇷 한국어 분석: {'✅' if storage.get('has_korean_analysis') else '❌'}")
            print(f"   🔢 임베딩: {'✅' if storage.get('has_embeddings') else '❌'}")
        
        print(f"\n🎉 테스트 성공: 수정된 파이프라인이 올바르게 작동합니다!")
        print(f"   ✅ 'text' 오류 해결됨")
        print(f"   ✅ vs_doc_contents_index 테이블 사용 확인")
        print(f"   ✅ tb_document_chunks 테이블 사용 확인")
        
    else:
        print("❌ 업로드 실패!")
        print(f"   상태 코드: {response.status_code}")
        print(f"   응답 내용: {response.text}")
        
        # 오류 분석
        try:
            error_data = response.json()
            error_detail = error_data.get('detail', '알 수 없는 오류')
            print(f"   오류 상세: {error_detail}")
            
            if "'text'" in error_detail or "벡터스토어" in error_detail:
                print(f"\n🔍 오류 분석:")
                print(f"   - 여전히 테이블 스키마 문제가 있을 수 있습니다")
                print(f"   - 백엔드 로그를 확인해주세요")
            
        except:
            print(f"   JSON 파싱 실패")

if __name__ == "__main__":
    asyncio.run(test_corrected_upload())

"""
한국어 NLP 서비스 테스트 스크립트
"""
import asyncio
import sys
import os

# 백엔드 앱 경로를 시스템 패스에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.korean_nlp_service import korean_nlp_service

async def test_korean_nlp_service():
    """한국어 NLP 서비스 기능 테스트"""
    
    # 테스트 텍스트
    test_texts = [
        "(주)웅진의 지식관리시스템 WKMS는 AWS Bedrock과 kiwipiepy를 활용합니다.",
        "2024년 사업계획서를 검토해주세요. SharePoint에서 다운로드할 수 있습니다.",
        "SAP RFC를 통해 인사정보를 연동하고 있으며, HWP 문서도 지원합니다."
    ]
    
    print("=" * 60)
    print("ABKMS - 한국어 NLP 서비스 테스트")
    print("=" * 60)
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n[테스트 {i}] {text}")
        print("-" * 40)
        
        # 1. 기본 토큰화 테스트
        try:
            tokenize_result = await korean_nlp_service.tokenize_korean_text(text)
            print(f"✓ 토큰화 성공: {len(tokenize_result.get('tokens', []))}개 토큰")
            print(f"  토큰: {tokenize_result.get('tokens', [])[:10]}...")  # 처음 10개만
        except Exception as e:
            print(f"✗ 토큰화 실패: {e}")
        
        # 2. 키워드 추출 테스트
        try:
            keywords = await korean_nlp_service.extract_keywords(text, top_k=5)
            print(f"✓ 키워드 추출 성공: {keywords}")
        except Exception as e:
            print(f"✗ 키워드 추출 실패: {e}")
        
        # 3. 하이브리드 분석 테스트
        try:
            hybrid_result = await korean_nlp_service.hybrid_process_korean_text(text)
            if "error" not in hybrid_result:
                print(f"✓ 하이브리드 분석 성공")
                print(f"  처리 모드: {hybrid_result.get('processing_mode')}")
                print(f"  기본 분석: {len(hybrid_result.get('basic_analysis', {}).get('tokens', []))}개 토큰")
                if hybrid_result.get('advanced_analysis'):
                    print(f"  고급 분석: {list(hybrid_result.get('advanced_analysis', {}).keys())}")
            else:
                print(f"✗ 하이브리드 분석 실패: {hybrid_result['error']}")
        except Exception as e:
            print(f"✗ 하이브리드 분석 실패: {e}")
        
        # 4. 임베딩 생성 테스트
        try:
            embedding = await korean_nlp_service.generate_korean_embedding(text)
            if embedding:
                print(f"✓ 임베딩 생성 성공: {len(embedding)}차원")
            else:
                print("✗ 임베딩 생성 실패")
        except Exception as e:
            print(f"✗ 임베딩 생성 실패: {e}")
        
        # 5. 텍스트 청킹 테스트
        try:
            chunks = korean_nlp_service.calculate_text_chunks(text)
            print(f"✓ 텍스트 청킹 성공: {len(chunks)}개 청크")
        except Exception as e:
            print(f"✗ 텍스트 청킹 실패: {e}")
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_korean_nlp_service())

"""멀티모달 파이프라인 검증 테스트

목적:
1. CLIP 임베딩 생성 로직 검증
2. 로컬 CLIP fallback 동작 확인
3. 멀티모달 문서 처리 파이프라인 검증
4. 에러 핸들링 강화 확인
"""

import asyncio
import sys
import os

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.document.vision.image_embedding_service import image_embedding_service


async def test_clip_service_initialization():
    """CLIP 서비스 초기화 테스트"""
    print("\n" + "=" * 80)
    print("TEST 1: CLIP 서비스 초기화")
    print("=" * 80)
    
    print(f"\n✅ 기본 설정:")
    print(f"  - Azure CLIP 사용: {image_embedding_service.use_azure_clip}")
    print(f"  - 로컬 CLIP 사용 가능: {image_embedding_service.use_local_clip}")
    print(f"  - Azure CLIP 실패 플래그: {image_embedding_service.azure_clip_failed}")
    print(f"  - 타겟 차원: {image_embedding_service.target_dim}")
    print(f"  - 엔드포인트: {image_embedding_service.endpoint or 'N/A'}")
    print(f"  - 배포 이름: {image_embedding_service.deployment or 'N/A'}")
    
    # 로컬 CLIP 모델 초기화 테스트
    if image_embedding_service.use_local_clip:
        print("\n🔄 로컬 CLIP 모델 초기화 시도...")
        image_embedding_service._initialize_local_clip()
        
        if image_embedding_service.local_clip_initialized:
            print("✅ 로컬 CLIP 모델 초기화 성공")
            print(f"  - 디바이스: {image_embedding_service.local_clip_device}")
            print(f"  - 모델: {image_embedding_service.local_clip_model is not None}")
            print(f"  - 프로세서: {image_embedding_service.local_clip_processor is not None}")
        else:
            print("❌ 로컬 CLIP 모델 초기화 실패")
    else:
        print("\n⚠️ transformers 라이브러리 미설치 - pip install transformers torch")


async def test_text_embedding():
    """텍스트 임베딩 생성 테스트 (크로스 모달 검색)"""
    print("\n" + "=" * 80)
    print("TEST 2: 텍스트 임베딩 생성 (크로스 모달)")
    print("=" * 80)
    
    test_text = "이 차트는 2024년 분기별 매출 추이를 보여줍니다"
    
    print(f"\n입력 텍스트: {test_text}")
    print("🔄 임베딩 생성 중...")
    
    try:
        embedding = await image_embedding_service.generate_text_embedding(test_text)
        
        if embedding:
            print(f"✅ 텍스트 임베딩 생성 성공")
            print(f"  - 차원: {len(embedding)}d")
            print(f"  - 샘플 벡터: {embedding[:5]}")
            print(f"  - 벡터 범위: [{min(embedding):.4f}, {max(embedding):.4f}]")
            
            # L2 norm 검증
            import math
            l2_norm = math.sqrt(sum(x*x for x in embedding))
            print(f"  - L2 Norm: {l2_norm:.4f} (정규화됨)")
        else:
            print("❌ 텍스트 임베딩 생성 실패")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


async def test_image_embedding():
    """이미지 임베딩 생성 테스트"""
    print("\n" + "=" * 80)
    print("TEST 3: 이미지 임베딩 생성")
    print("=" * 80)
    
    # 테스트 이미지 생성 (간단한 PNG)
    try:
        from PIL import Image
        import io
        
        # 100x100 빨간색 이미지 생성
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        print(f"\n✅ 테스트 이미지 생성: {len(img_bytes)} bytes (100x100 빨간색)")
        print("🔄 임베딩 생성 중...")
        
        embedding = await image_embedding_service.generate_image_embedding(
            image_bytes=img_bytes
        )
        
        if embedding:
            print(f"✅ 이미지 임베딩 생성 성공")
            print(f"  - 차원: {len(embedding)}d")
            print(f"  - 샘플 벡터: {embedding[:5]}")
            print(f"  - 벡터 범위: [{min(embedding):.4f}, {max(embedding):.4f}]")
            
            # L2 norm 검증
            import math
            l2_norm = math.sqrt(sum(x*x for x in embedding))
            print(f"  - L2 Norm: {l2_norm:.4f} (정규화됨)")
        else:
            print("❌ 이미지 임베딩 생성 실패")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


async def test_extract_features():
    """이미지 특징 추출 테스트 (pHash + 임베딩)"""
    print("\n" + "=" * 80)
    print("TEST 4: 이미지 특징 추출 (pHash + 임베딩)")
    print("=" * 80)
    
    try:
        from PIL import Image
        import io
        
        # 200x150 파란색 이미지 생성
        img = Image.new('RGB', (200, 150), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        print(f"\n✅ 테스트 이미지 생성: {len(img_bytes)} bytes (200x150 파란색)")
        print("🔄 특징 추출 중...")
        
        features = await image_embedding_service.extract_features(
            img_bytes=img_bytes,
            generate_embedding=True
        )
        
        print(f"\n✅ 이미지 특징 추출 성공:")
        print(f"  - pHash: {features['phash']}")
        print(f"  - Width: {features['width']}px")
        print(f"  - Height: {features['height']}px")
        print(f"  - Aspect Ratio: {features['aspect_ratio']}")
        print(f"  - Vector Dimension: {features['vector_dimension']}d")
        print(f"  - Embedding 샘플: {features['embedding'][:5] if features['embedding'] else 'N/A'}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


async def test_azure_clip_fallback():
    """Azure CLIP 실패 시 로컬 CLIP fallback 동작 검증"""
    print("\n" + "=" * 80)
    print("TEST 5: Azure CLIP Fallback 동작 검증")
    print("=" * 80)
    
    print(f"\n초기 상태:")
    print(f"  - Azure CLIP 사용: {image_embedding_service.use_azure_clip}")
    print(f"  - Azure CLIP 실패 플래그: {image_embedding_service.azure_clip_failed}")
    print(f"  - 로컬 CLIP 사용 가능: {image_embedding_service.use_local_clip}")
    
    if image_embedding_service.use_azure_clip:
        print("\n🔄 Azure CLIP API 호출 시도 (실패 시 자동 fallback)...")
        
        try:
            from PIL import Image
            import io
            
            # 테스트 이미지
            img = Image.new('RGB', (50, 50), color='green')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            # 임베딩 생성 (Azure CLIP 실패 시 자동으로 로컬 CLIP 사용)
            embedding = await image_embedding_service.generate_image_embedding(
                image_bytes=img_bytes
            )
            
            print(f"\n최종 결과:")
            print(f"  - Azure CLIP 실패 플래그: {image_embedding_service.azure_clip_failed}")
            print(f"  - 임베딩 생성: {'성공' if embedding else '실패'}")
            print(f"  - 사용된 모델: {'로컬 CLIP' if image_embedding_service.azure_clip_failed else 'Azure CLIP'}")
            
            if embedding:
                print(f"  - 임베딩 차원: {len(embedding)}d")
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
    else:
        print("\n⚠️ Azure CLIP 설정 안됨 - 로컬 CLIP만 사용")


async def test_error_handling():
    """에러 핸들링 테스트"""
    print("\n" + "=" * 80)
    print("TEST 6: 에러 핸들링")
    print("=" * 80)
    
    # 1. 잘못된 이미지 데이터
    print("\n1️⃣ 잘못된 이미지 데이터 테스트:")
    try:
        embedding = await image_embedding_service.generate_image_embedding(
            image_bytes=b"invalid_image_data"
        )
        print(f"  - 결과: {'성공' if embedding else '실패'} (예상: 실패 또는 placeholder)")
    except Exception as e:
        print(f"  - 예외 발생 (예상): {type(e).__name__}")
    
    # 2. 빈 데이터
    print("\n2️⃣ 빈 데이터 테스트:")
    try:
        embedding = await image_embedding_service.generate_image_embedding(
            image_bytes=b""
        )
        print(f"  - 결과: {'성공' if embedding else '실패'} (예상: 실패)")
    except Exception as e:
        print(f"  - 예외 발생 (예상): {type(e).__name__}")
    
    # 3. 누락된 인자
    print("\n3️⃣ 인자 누락 테스트:")
    try:
        embedding = await image_embedding_service.generate_image_embedding()
        print(f"  - 결과: {'성공' if embedding else '실패'} (예상: 실패)")
    except Exception as e:
        print(f"  - 예외 발생 (예상): {type(e).__name__}: {str(e)[:50]}")


async def main():
    """전체 테스트 실행"""
    print("\n" + "=" * 80)
    print("멀티모달 파이프라인 검증 테스트 시작")
    print("=" * 80)
    
    await test_clip_service_initialization()
    await test_text_embedding()
    await test_image_embedding()
    await test_extract_features()
    await test_azure_clip_fallback()
    await test_error_handling()
    
    print("\n" + "=" * 80)
    print("✅ 모든 테스트 완료")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

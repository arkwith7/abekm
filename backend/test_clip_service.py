"""Azure CLIP 임베딩 서비스 테스트

테스트 항목:
1. 이미지 임베딩 생성 (512d)
2. 텍스트 임베딩 생성 (512d)
3. 크로스 모달 유사도 계산
4. Perceptual Hash 생성
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.document.vision.image_embedding_service import image_embedding_service
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cosine_similarity(vec1, vec2):
    """코사인 유사도 계산"""
    import math
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    return dot_product / (norm1 * norm2) if norm1 and norm2 else 0.0


async def test_clip_service():
    """CLIP 서비스 테스트"""
    
    print("\n" + "="*80)
    print("Azure CLIP 임베딩 서비스 테스트")
    print("="*80 + "\n")
    
    # 설정 확인
    print("📋 설정 확인:")
    print(f"  - Endpoint: {settings.azure_openai_multimodal_embedding_endpoint}")
    print(f"  - Deployment: {settings.azure_openai_multimodal_embedding_deployment}")
    print(f"  - API Key: {'✓ 설정됨' if settings.azure_openai_multimodal_embedding_api_key else '✗ 미설정'}")
    print(f"  - Target Dimension: {image_embedding_service.target_dim}")
    print(f"  - Azure CLIP 사용: {'✓' if image_embedding_service.use_azure_clip else '✗'}\n")
    
    if not image_embedding_service.use_azure_clip:
        print("❌ Azure CLIP이 설정되지 않았습니다.")
        print("   .env 파일에서 다음 환경 변수를 확인하세요:")
        print("   - AZURE_OPENAI_MULTIMODAL_EMBEDDING_ENDPOINT")
        print("   - AZURE_OPENAI_MULTIMODAL_EMBEDDING_API_KEY")
        return
    
    # 테스트 1: 텍스트 임베딩
    print("="*80)
    print("테스트 1: 텍스트 임베딩 생성")
    print("="*80)
    
    test_texts = [
        "파란색 자동차가 도로를 달리고 있다",
        "빨간색 스포츠카",
        "고양이가 소파에 앉아있다"
    ]
    
    text_embeddings = []
    for text in test_texts:
        print(f"\n📝 텍스트: \"{text}\"")
        embedding = await image_embedding_service.generate_text_embedding(text)
        if embedding:
            print(f"   ✅ 임베딩 생성 성공: dimension={len(embedding)}")
            print(f"   벡터 샘플: {embedding[:5]}...")
            text_embeddings.append((text, embedding))
        else:
            print(f"   ❌ 임베딩 생성 실패")
    
    # 텍스트 간 유사도 계산
    if len(text_embeddings) >= 2:
        print(f"\n📊 텍스트 간 유사도:")
        for i in range(len(text_embeddings)):
            for j in range(i + 1, len(text_embeddings)):
                text1, emb1 = text_embeddings[i]
                text2, emb2 = text_embeddings[j]
                similarity = cosine_similarity(emb1, emb2)
                print(f"   \"{text1}\" ↔ \"{text2}\"")
                print(f"   → 유사도: {similarity:.4f}\n")
    
    # 테스트 2: 이미지 임베딩 (테스트 이미지가 있는 경우)
    print("\n" + "="*80)
    print("테스트 2: 이미지 임베딩 생성")
    print("="*80)
    
    # 간단한 테스트 이미지 생성
    try:
        from PIL import Image
        import io
        
        # 100x100 파란색 이미지 생성
        img = Image.new('RGB', (100, 100), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        print(f"\n🖼️ 테스트 이미지: 100x100 파란색")
        embedding = await image_embedding_service.generate_image_embedding(
            image_bytes=img_bytes.getvalue()
        )
        
        if embedding:
            print(f"   ✅ 임베딩 생성 성공: dimension={len(embedding)}")
            print(f"   벡터 샘플: {embedding[:5]}...")
            
            # 텍스트 "파란색"과 유사도 비교
            if text_embeddings:
                text_blue = next((emb for txt, emb in text_embeddings if "파란색" in txt), None)
                if text_blue:
                    similarity = cosine_similarity(embedding, text_blue)
                    print(f"\n   📊 크로스 모달 유사도:")
                    print(f"   파란색 이미지 ↔ \"파란색 자동차\" 텍스트")
                    print(f"   → 유사도: {similarity:.4f}")
        else:
            print(f"   ❌ 임베딩 생성 실패")
    
    except Exception as e:
        print(f"   ❌ 이미지 테스트 실패: {str(e)}")
    
    # 테스트 3: extract_features 전체 기능
    print("\n" + "="*80)
    print("테스트 3: extract_features 전체 기능")
    print("="*80)
    
    try:
        # 빨간색 이미지 생성
        img = Image.new('RGB', (200, 150), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        print(f"\n🖼️ 테스트 이미지: 200x150 빨간색")
        features = await image_embedding_service.extract_features(
            img_bytes.getvalue(),
            generate_embedding=True
        )
        
        print(f"\n   추출된 특징:")
        print(f"   - pHash: {features['phash']}")
        print(f"   - Width: {features['width']}")
        print(f"   - Height: {features['height']}")
        print(f"   - Aspect Ratio: {features['aspect_ratio']}")
        print(f"   - Vector Dimension: {features['vector_dimension']}")
        print(f"   - Embedding: {'✓ 생성됨' if features['embedding'] else '✗ 미생성'}")
        
    except Exception as e:
        print(f"   ❌ extract_features 실패: {str(e)}")
    
    print("\n" + "="*80)
    print("✅ 테스트 완료")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_clip_service())

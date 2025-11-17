"""Azure CLIP 모델 직접 테스트

Hugging Face의 CLIP 모델을 로컬에서 테스트하여
Azure 배포와 동일한 기능 구현
"""
import asyncio
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class LocalCLIPService:
    """로컬 CLIP 모델 서비스 (Fallback)"""
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = "cpu"
        self._initialized = False
    
    def _initialize(self):
        """CLIP 모델 초기화"""
        if self._initialized:
            return
        
        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch
            
            print("🔄 Hugging Face CLIP 모델 로딩 중...")
            
            # ViT-B/32 모델 (Azure와 동일)
            model_name = "openai/clip-vit-base-patch32"
            self.processor = CLIPProcessor.from_pretrained(model_name)
            self.model = CLIPModel.from_pretrained(model_name)
            
            # GPU 사용 가능하면 사용
            if torch.cuda.is_available():
                self.device = "cuda"
                self.model = self.model.to(self.device)
            
            self._initialized = True
            print(f"✅ CLIP 모델 로딩 완료 (device: {self.device})")
            
        except ImportError:
            print("❌ transformers 라이브러리 설치 필요: pip install transformers torch pillow")
            raise
        except Exception as e:
            print(f"❌ CLIP 모델 초기화 실패: {e}")
            raise
    
    def generate_text_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        self._initialize()
        
        import torch
        
        with torch.no_grad():
            inputs = self.processor(text=[text], return_tensors="pt", padding=True)
            
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            text_features = self.model.get_text_features(**inputs)
            
            # L2 정규화
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            # CPU로 이동 및 리스트 변환
            embedding = text_features.cpu().numpy()[0].tolist()
            
            print(f"✅ 텍스트 임베딩 생성: {len(embedding)}d")
            return embedding
    
    def generate_image_embedding(self, image_bytes: bytes) -> List[float]:
        """이미지 임베딩 생성"""
        self._initialize()
        
        from PIL import Image
        import io
        import torch
        
        # 이미지 로드
        image = Image.open(io.BytesIO(image_bytes))
        
        with torch.no_grad():
            inputs = self.processor(images=image, return_tensors="pt")
            
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            image_features = self.model.get_image_features(**inputs)
            
            # L2 정규화
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            # CPU로 이동 및 리스트 변환
            embedding = image_features.cpu().numpy()[0].tolist()
            
            print(f"✅ 이미지 임베딩 생성: {len(embedding)}d")
            return embedding
    
    def compute_similarity(self, text: str, image_bytes: bytes) -> float:
        """텍스트-이미지 유사도 계산"""
        text_emb = self.generate_text_embedding(text)
        image_emb = self.generate_image_embedding(image_bytes)
        
        # 코사인 유사도 (이미 정규화되어 있으므로 내적)
        import numpy as np
        similarity = np.dot(text_emb, image_emb)
        
        return float(similarity)

async def test_local_clip():
    """로컬 CLIP 모델 테스트"""
    print("="*80)
    print("로컬 CLIP 모델 테스트")
    print("="*80)
    
    try:
        clip_service = LocalCLIPService()
        
        # 테스트 1: 텍스트 임베딩
        print("\n[테스트 1] 텍스트 임베딩")
        print("-"*60)
        texts = [
            "파란색 자동차",
            "빨간색 스포츠카",
            "고양이가 소파에 앉아있다"
        ]
        
        text_embeddings = []
        for text in texts:
            emb = clip_service.generate_text_embedding(text)
            text_embeddings.append(emb)
            print(f"'{text}': {len(emb)}d")
        
        # 유사도 계산
        import numpy as np
        print("\n텍스트 간 유사도:")
        for i in range(len(texts)):
            for j in range(i+1, len(texts)):
                sim = np.dot(text_embeddings[i], text_embeddings[j])
                print(f"  '{texts[i]}' <-> '{texts[j]}': {sim:.4f}")
        
        # 테스트 2: 이미지 임베딩
        print("\n[테스트 2] 이미지 임베딩")
        print("-"*60)
        
        from PIL import Image
        import io
        
        # 파란색 이미지 생성
        img = Image.new('RGB', (224, 224), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        image_emb = clip_service.generate_image_embedding(img_bytes)
        print(f"이미지 임베딩: {len(image_emb)}d")
        
        # 테스트 3: 크로스 모달 유사도
        print("\n[테스트 3] 크로스 모달 유사도 (텍스트 <-> 이미지)")
        print("-"*60)
        
        for text in texts:
            similarity = clip_service.compute_similarity(text, img_bytes)
            print(f"'{text}' <-> 파란색 이미지: {similarity:.4f}")
        
        print("\n✅ 로컬 CLIP 모델 테스트 성공!")
        print("\n💡 이 로컬 CLIP 서비스를 Azure CLIP 대신 사용할 수 있습니다.")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ 필요한 라이브러리 설치:")
        print("   pip install transformers torch pillow")
        return False
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_local_clip())

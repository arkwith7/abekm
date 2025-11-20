"""CLIP 기반 이미지 임베딩 서비스

로컬 CLIP 또는 Azure CLIP 모델을 사용한 멀티모달 임베딩 생성:
1) 이미지 임베딩 생성 (512d)
2) 텍스트 임베딩 생성 (512d) - 크로스 모달 검색
3) Perceptual Hash (pHash) 생성
4) 이미지 메타데이터 추출

특징:
- 이미지와 텍스트가 같은 벡터 공간에 매핑
- 시각적 유사도 검색 가능
- 텍스트 쿼리로 이미지 검색 가능 (크로스 모달)

Fallback 전략:
1. Azure CLIP API (우선)
2. 로컬 Hugging Face CLIP 모델 (자동 fallback)
3. Placeholder 임베딩 (최후)
"""

from __future__ import annotations
import io
import base64
from typing import List, Dict, Any, Optional
from PIL import Image
import imagehash
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import numpy as np  # noqa
except Exception:  # pragma: no cover
    np = None  # type: ignore

# 로컬 CLIP 모델 (Hugging Face)
try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    CLIPProcessor = None
    CLIPModel = None
    torch = None


class ImageEmbeddingService:
    """멀티모달 이미지 임베딩 서비스 (Provider 기반 동적 선택)
    
    ⚠️ 중요: 이 서비스는 멀티모달(이미지+텍스트) 임베딩 전용입니다.
    일반 텍스트 임베딩은 EmbeddingService를 사용하세요!
    
    용도:
    - 이미지 임베딩 생성 (512d)
    - 크로스모달 검색용 텍스트 임베딩 (이미지와 같은 벡터 공간)
    - 이미지-텍스트 유사도 비교
    
    지원 Provider:
    - bedrock: AWS Bedrock TwelveLabs Marengo (512d) - 멀티모달 전용
    - azure_openai: Azure CLIP (512d) - 멀티모달 전용
    - local: Hugging Face CLIP (fallback)
    
    일반 텍스트 임베딩 (문서 청킹, RAG 쿼리):
    - EmbeddingService 사용 → amazon.titan-embed-text-v2:0 (1024d)
    """
    
    def __init__(self, target_dim: int = 512):
        self.target_dim = target_dim
        
        # Provider 설정 읽기
        self.provider = getattr(settings, 'default_embedding_provider', 'bedrock').lower()
        
        # AWS Bedrock 설정
        self.use_bedrock = False
        self.bedrock_model_id = None
        self.bedrock_client = None
        if self.provider == 'bedrock':
            self.bedrock_model_id = getattr(settings, 'bedrock_multimodal_embedding_model_id', None)
            self.use_bedrock = bool(self.bedrock_model_id)
            if self.use_bedrock:
                try:
                    import boto3
                    self.bedrock_client = boto3.client(
                        'bedrock-runtime',
                        region_name=settings.aws_region,
                        aws_access_key_id=settings.aws_access_key_id,
                        aws_secret_access_key=settings.aws_secret_access_key
                    )
                    logger.info(f"✅ AWS Bedrock 멀티모달 임베딩 초기화: {self.bedrock_model_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Bedrock 초기화 실패: {e}")
                    self.use_bedrock = False
        
        # Azure CLIP 설정
        self.endpoint = settings.azure_openai_multimodal_embedding_endpoint
        self.api_key = settings.azure_openai_multimodal_embedding_api_key
        self.deployment = settings.azure_openai_multimodal_embedding_deployment
        self.use_azure_clip = False
        if self.provider == 'azure_openai':
            self.use_azure_clip = bool(self.endpoint and self.api_key)
            if self.use_azure_clip:
                logger.info(f"✅ Azure CLIP 서비스 초기화: {self.deployment}")
        
        # 로컬 CLIP 모델 초기화 (lazy loading, fallback)
        self.local_clip_model = None
        self.local_clip_processor = None
        self.local_clip_device = "cpu"
        self.local_clip_initialized = False
        self.use_local_clip = TRANSFORMERS_AVAILABLE
        
        # Azure CLIP 실패 시 자동으로 로컬 CLIP 사용
        self.azure_clip_failed = False
        
        # 현재 활성 provider 로깅
        if self.use_bedrock:
            logger.info(f"🎯 멀티모달 Provider: AWS Bedrock ({self.bedrock_model_id})")
        elif self.use_azure_clip:
            logger.info(f"🎯 멀티모달 Provider: Azure OpenAI ({self.deployment})")
        elif self.use_local_clip:
            logger.info("🎯 멀티모달 Provider: 로컬 CLIP (Hugging Face)")
        else:
            # 모든 Provider가 없는 경우에만 경고
            logger.warning("⚠️ 멀티모달 임베딩 Provider 없음")
            logger.warning("⚠️ transformers 미설치 - pip install transformers torch")
            logger.warning("⚠️ 또는 .env에서 AWS Bedrock/Azure OpenAI 설정 필요")
    
    def _initialize_local_clip(self):
        """로컬 CLIP 모델 초기화 (Lazy Loading)"""
        if self.local_clip_initialized or not self.use_local_clip:
            return
        
        try:
            logger.info("🔄 로컬 CLIP 모델 로딩 중 (openai/clip-vit-base-patch32)...")
            
            model_name = "openai/clip-vit-base-patch32"
            self.local_clip_processor = CLIPProcessor.from_pretrained(model_name)
            self.local_clip_model = CLIPModel.from_pretrained(model_name)
            
            # GPU 사용 가능 시 사용
            if torch and torch.cuda.is_available():
                self.local_clip_device = "cuda"
                self.local_clip_model = self.local_clip_model.to(self.local_clip_device)
                logger.info("✅ 로컬 CLIP 모델 로딩 완료 (GPU)")
            else:
                logger.info("✅ 로컬 CLIP 모델 로딩 완료 (CPU)")
            
            self.local_clip_initialized = True
            
        except Exception as e:
            logger.error(f"❌ 로컬 CLIP 모델 초기화 실패: {e}")
            self.use_local_clip = False
    
    def _generate_local_image_embedding(self, image_bytes: bytes) -> Optional[List[float]]:
        """로컬 CLIP으로 이미지 임베딩 생성"""
        try:
            self._initialize_local_clip()
            
            if not self.local_clip_initialized:
                return None
            
            # 이미지 로드
            image = Image.open(io.BytesIO(image_bytes))
            
            with torch.no_grad():
                inputs = self.local_clip_processor(images=image, return_tensors="pt")
                
                if self.local_clip_device == "cuda":
                    inputs = {k: v.to(self.local_clip_device) for k, v in inputs.items()}
                
                image_features = self.local_clip_model.get_image_features(**inputs)
                
                # L2 정규화
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
                # CPU로 이동 및 리스트 변환
                embedding = image_features.cpu().numpy()[0].tolist()
                
                logger.info(f"✅ 로컬 CLIP 이미지 임베딩 생성: {len(embedding)}d")
                return embedding
                
        except Exception as e:
            logger.error(f"❌ 로컬 CLIP 이미지 임베딩 실패: {e}")
            return None
    
    def _generate_bedrock_image_embedding(self, image_bytes: bytes, caption: Optional[str] = None) -> Optional[List[float]]:
        """AWS Bedrock으로 멀티모달 이미지 임베딩 생성 (TwelveLabs Marengo)
        
        Args:
            image_bytes: 이미지 바이너리 데이터
            caption: 이미지 캡션 텍스트 (선택) - 제공 시 text_image 모드로 멀티모달 임베딩 생성
        
        Returns:
            512차원 임베딩 벡터
        """
        try:
            if not self.use_bedrock or not self.bedrock_client:
                return None
            
            import json
            
            # 이미지를 base64로 인코딩
            img_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Bedrock API 호출 (TwelveLabs Marengo 형식)
            if caption and caption.strip():
                # 🎯 멀티모달: 이미지 + 텍스트 동시 임베딩 (text_image)
                request_body = json.dumps({
                    "inputType": "text_image",
                    "text_image": {
                        "inputText": caption.strip(),
                        "mediaSource": {
                            "base64String": img_base64
                        }
                    }
                })
                logger.info(f"[BEDROCK] 멀티모달 임베딩 요청 (text_image) - caption: {caption[:50]}...")
            else:
                # 이미지만 임베딩 (image)
                request_body = json.dumps({
                    "inputType": "image",
                    "image": {
                        "mediaSource": {
                            "base64String": img_base64
                        }
                    }
                })
                logger.info(f"[BEDROCK] 이미지 임베딩 요청 (image only)")
            
            response = self.bedrock_client.invoke_model(
                modelId=self.bedrock_model_id,
                body=request_body,
                contentType="application/json",
                accept="application/json"
            )
            
            # 응답 파싱 (Marengo 3.0 응답 형식: {"data": {"embedding": [...]}})
            response_body = json.loads(response['body'].read())
            
            # data.embedding 경로로 접근
            embedding = None
            if 'data' in response_body:
                data = response_body['data']
                if isinstance(data, dict):
                    embedding = data.get('embedding')
                elif isinstance(data, list) and len(data) > 0:
                    embedding = data[0].get('embedding')
            elif 'embedding' in response_body:
                # 호환성: 직접 embedding 필드
                embedding = response_body['embedding']
            
            if embedding and isinstance(embedding, list):
                mode_str = "text_image (멀티모달)" if caption else "image"
                logger.info(f"✅ Bedrock {mode_str} 임베딩: {len(embedding)}d ({self.bedrock_model_id})")
                return embedding
            else:
                logger.warning(f"⚠️ Bedrock 응답 파싱 실패: {response_body}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Bedrock 멀티모달 이미지 임베딩 실패: {e}")
            return None
    
    def _generate_bedrock_text_embedding(self, text: str) -> Optional[List[float]]:
        """AWS Bedrock으로 멀티모달 텍스트 임베딩 생성 (TwelveLabs Marengo)
        
        ⚠️ 주의: 이 메서드는 크로스모달 검색용 텍스트 임베딩 전용입니다.
        일반 텍스트 임베딩(문서 청킹, RAG 쿼리)은 EmbeddingService를 사용하세요!
        """
        try:
            if not self.use_bedrock or not self.bedrock_client:
                return None
            
            import json
            
            # Bedrock API 호출 (TwelveLabs Marengo 형식)
            request_body = json.dumps({
                "inputType": "text",
                "text": {
                    "inputText": text
                }
            })
            
            response = self.bedrock_client.invoke_model(
                modelId=self.bedrock_model_id,
                body=request_body,
                contentType="application/json",
                accept="application/json"
            )
            
            # 응답 파싱 (Marengo 3.0 응답 형식: {"data": {"embedding": [...]}})
            response_body = json.loads(response['body'].read())
            
            # data.embedding 경로로 접근
            embedding = None
            if 'data' in response_body:
                data = response_body['data']
                if isinstance(data, dict):
                    embedding = data.get('embedding')
                elif isinstance(data, list) and len(data) > 0:
                    embedding = data[0].get('embedding')
            elif 'embedding' in response_body:
                # 호환성: 직접 embedding 필드
                embedding = response_body['embedding']
            
            if embedding and isinstance(embedding, list):
                logger.info(f"✅ Bedrock 멀티모달 텍스트 임베딩: {len(embedding)}d ({self.bedrock_model_id}) - 크로스모달 검색용")
                return embedding
            else:
                logger.warning(f"⚠️ Bedrock 응답 파싱 실패: {response_body}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Bedrock 멀티모달 텍스트 임베딩 실패: {e}")
            return None
    
    def _generate_local_text_embedding(self, text: str) -> Optional[List[float]]:
        """로컬 CLIP으로 텍스트 임베딩 생성"""
        try:
            self._initialize_local_clip()
            
            if not self.local_clip_initialized:
                return None
            
            with torch.no_grad():
                inputs = self.local_clip_processor(text=[text], return_tensors="pt", padding=True)
                
                if self.local_clip_device == "cuda":
                    inputs = {k: v.to(self.local_clip_device) for k, v in inputs.items()}
                
                text_features = self.local_clip_model.get_text_features(**inputs)
                
                # L2 정규화
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                
                # CPU로 이동 및 리스트 변환
                embedding = text_features.cpu().numpy()[0].tolist()
                
                logger.info(f"✅ 로컬 CLIP 텍스트 임베딩 생성: {len(embedding)}d")
                return embedding
                
        except Exception as e:
            logger.error(f"❌ 로컬 CLIP 텍스트 임베딩 실패: {e}")
            return None

    def compute_phash(self, img: Image.Image) -> str:
        """Perceptual Hash 생성"""
        return str(imagehash.phash(img))

    async def generate_image_embedding(
        self, 
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        caption: Optional[str] = None
    ) -> Optional[List[float]]:
        """멀티모달 이미지 임베딩 생성 (Provider 기반 동적 선택)
        
        우선순위:
        1. AWS Bedrock TwelveLabs Marengo (provider=bedrock) → 512d
        2. Azure CLIP (provider=azure_openai) → 512d
        3. 로컬 CLIP (fallback) → 512d
        
        Args:
            image_path: 이미지 파일 경로
            image_bytes: 이미지 바이트 데이터
            caption: 이미지 캡션 텍스트 (선택) - "Figure 1. Diagram...", "Table 2. Results..."
            
        Returns:
            512차원 멀티모달 임베딩 벡터 또는 None
        """
        # 이미지 데이터 준비
        if image_path:
            with open(image_path, "rb") as f:
                img_data = f.read()
        elif image_bytes:
            img_data = image_bytes
        else:
            raise ValueError("image_path 또는 image_bytes 중 하나 필요")
        
        # 1단계: AWS Bedrock 시도 (provider=bedrock) - 캡션 포함 가능
        if self.use_bedrock:
            embedding = self._generate_bedrock_image_embedding(img_data, caption=caption)
            if embedding:
                return embedding
            logger.warning("⚠️ Bedrock 실패, 다음 방법 시도...")
        
        # 2단계: Azure CLIP 시도 (provider=azure_openai, 실패 전력 없을 때만)
        if self.use_azure_clip and not self.azure_clip_failed:
            try:
                # Base64 인코딩
                img_base64 = base64.b64encode(img_data).decode("utf-8")
                
                # Azure CLIP API 호출 (image + text 필드 모두 필요)
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.endpoint,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Authorization": f"Bearer {self.api_key}"
                        },
                        json={
                            "input_data": {
                                "columns": ["image", "text"],  # 모델이 요구하는 스키마
                                "data": [[img_base64, ""]]     # text는 빈 문자열 (이미지만 임베딩)
                            }
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()
                    result = response.json()
                
                # 응답 파싱: [{"image_features": [...], "text_features": [...]}] 형식
                embedding = None
                if isinstance(result, list) and len(result) > 0:
                    first_item = result[0]
                    if isinstance(first_item, dict):
                        # image_features 추출 (이미지 임베딩)
                        embedding = first_item.get("image_features")
                    elif isinstance(first_item, list):
                        # 리스트 형식인 경우
                        embedding = first_item
                elif isinstance(result, dict):
                    # dict 응답인 경우
                    embedding = (result.get("image_features") or
                               result.get("output", [[]])[0] or 
                               result.get("embedding") or
                               result.get("data", [[]])[0])
                
                if embedding and isinstance(embedding, list) and len(embedding) > 0:
                    logger.info(f"✅ Azure CLIP 이미지 임베딩: {len(embedding)}d")
                    return embedding
                else:
                    logger.warning(f"⚠️ Azure CLIP 응답 파싱 실패: {type(result)}, Fallback 시도...")
                    self.azure_clip_failed = True
                    
            except httpx.HTTPStatusError as e:
                logger.warning(f"⚠️ Azure CLIP API 오류 (HTTP {e.response.status_code}), Fallback 시도...")
                self.azure_clip_failed = True  # 이후 요청은 바로 로컬 CLIP 사용
            except Exception as e:
                logger.warning(f"⚠️ Azure CLIP 실패: {str(e)[:100]}, Fallback 시도...")
                self.azure_clip_failed = True
        
        # 3단계: 로컬 CLIP Fallback
        if self.use_local_clip:
            embedding = self._generate_local_image_embedding(img_data)
            if embedding:
                return embedding
        
        # 3단계: Placeholder (최후의 수단)
        logger.warning("⚠️ CLIP 사용 불가 - placeholder 임베딩 반환")
        return await self._generate_placeholder_embedding(image_path, image_bytes)

    async def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """멀티모달 텍스트 임베딩 생성 (크로스모달 검색 전용)
        
        ⚠️ 중요: 이 메서드는 크로스모달 검색용 텍스트 임베딩 전용입니다!
        - 용도: 텍스트 쿼리로 이미지 검색 (이미지와 같은 512d 벡터 공간)
        - 일반 텍스트 임베딩(문서 청킹, RAG 쿼리)은 EmbeddingService 사용!
        
        우선순위:
        1. AWS Bedrock TwelveLabs Marengo (provider=bedrock) → 512d
        2. Azure CLIP (provider=azure_openai) → 512d
        3. 로컬 CLIP (fallback) → 512d
        
        일반 텍스트 임베딩 (RAG 시스템):
        - EmbeddingService.get_embedding() 사용
        - amazon.titan-embed-text-v2:0 → 1024d
        
        Args:
            text: 크로스모달 검색용 텍스트 쿼리
            
        Returns:
            512차원 멀티모달 임베딩 벡터 또는 None
        """
        # 1단계: AWS Bedrock 시도 (provider=bedrock)
        if self.use_bedrock:
            embedding = self._generate_bedrock_text_embedding(text)
            if embedding:
                return embedding
            logger.warning("⚠️ Bedrock 텍스트 임베딩 실패, Fallback 시도...")
        
        # 2단계: Azure CLIP 시도 (provider=azure_openai, 실패 전력 없을 때만)
        if self.use_azure_clip and not self.azure_clip_failed:
            try:
                # Azure CLIP API 호출 (image + text 필드 모두 필요)
                # 텍스트만 임베딩할 때는 image를 빈 문자열로 전송
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.endpoint,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Authorization": f"Bearer {self.api_key}"
                        },
                        json={
                            "input_data": {
                                "columns": ["image", "text"],  # 모델이 요구하는 스키마
                                "data": [["", text]]           # image는 빈 문자열 (텍스트만 임베딩)
                            }
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()
                    result = response.json()
                
                # 응답 파싱: [{"image_features": [...], "text_features": [...]}] 형식
                embedding = None
                if isinstance(result, list) and len(result) > 0:
                    first_item = result[0]
                    if isinstance(first_item, dict):
                        # text_features 추출 (텍스트 임베딩)
                        embedding = first_item.get("text_features")
                    elif isinstance(first_item, list):
                        embedding = first_item
                elif isinstance(result, dict):
                    embedding = (result.get("text_features") or
                               result.get("output", [[]])[0] or 
                               result.get("embedding") or
                               result.get("data", [[]])[0])
                
                if embedding and isinstance(embedding, list) and len(embedding) > 0:
                    logger.info(f"✅ Azure CLIP 텍스트 임베딩: {len(embedding)}d")
                    return embedding
                else:
                    embedding = None
                
                if embedding:
                    logger.info(f"✅ Azure CLIP 텍스트 임베딩: {len(embedding)}d")
                    return embedding
                    
            except httpx.HTTPStatusError as e:
                logger.warning(f"⚠️ Azure CLIP API 오류 (HTTP {e.response.status_code}), Fallback 시도...")
                self.azure_clip_failed = True
            except Exception as e:
                logger.warning(f"⚠️ Azure CLIP 실패: {str(e)[:100]}, Fallback 시도...")
                self.azure_clip_failed = True
        
        # 3단계: 로컬 CLIP Fallback
        if self.use_local_clip:
            embedding = self._generate_local_text_embedding(text)
            if embedding:
                return embedding
        
        # 4단계: None 반환 (텍스트는 placeholder 없음)
        logger.warning("⚠️ CLIP 텍스트 임베딩 생성 불가")
        return None

    async def _generate_placeholder_embedding(
        self,
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None
    ) -> List[float]:
        """Placeholder 임베딩 생성 (Azure CLIP 미설정 시)"""
        if image_path:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
        elif image_bytes:
            img_bytes = image_bytes
        else:
            return [0.0] * self.target_dim
        
        with Image.open(io.BytesIO(img_bytes)) as img:
            h = self.compute_phash(img)
            ints = [int(h[i:i+2], 16) for i in range(0, len(h), 2)]
            vec = (ints * (self.target_dim // len(ints) + 1))[: self.target_dim]
            max_v = max(vec) or 1
            return [v / max_v for v in vec]

    async def extract_features(
        self, 
        img_bytes: bytes,
        generate_embedding: bool = True
    ) -> Dict[str, Any]:
        """이미지 특징 추출
        
        Args:
            img_bytes: 이미지 바이트 데이터
            generate_embedding: 임베딩 생성 여부
            
        Returns:
            {
                "phash": str,
                "embedding": List[float],
                "width": int,
                "height": int,
                "aspect_ratio": float,
                "vector_dimension": int
            }
        """
        with Image.open(io.BytesIO(img_bytes)) as im:
            im = im.convert('RGB')
            phash = self.compute_phash(im)
            
            # 임베딩 생성
            embedding = None
            if generate_embedding:
                embedding = await self.generate_image_embedding(image_bytes=img_bytes)
            
            return {
                "phash": phash,
                "embedding": embedding,
                "width": im.width,
                "height": im.height,
                "aspect_ratio": round(im.width / im.height, 4) if im.height else None,
                "vector_dimension": len(embedding) if embedding else None
            }


# 전역 인스턴스
image_embedding_service = ImageEmbeddingService()

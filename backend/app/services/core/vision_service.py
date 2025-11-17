"""
Vision Service - GPT-4o Vision API 통합
이미지 분석 및 설명 생성
"""
from typing import List, Dict, Optional
from openai import AzureOpenAI
from app.core.config import settings
from loguru import logger
import base64
from io import BytesIO
from PIL import Image


class VisionService:
    """GPT-4o Vision을 사용한 이미지 분석 서비스"""
    
    def __init__(self):
        """Azure OpenAI 클라이언트 초기화"""
        # 환경 변수 검증
        if not settings.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT가 설정되지 않았습니다")
        if not settings.azure_openai_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY가 설정되지 않았습니다")
            
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version or "2024-02-15-preview",
            azure_endpoint=settings.azure_openai_endpoint
        )
        # Vision 모델 - .env의 AZURE_OPENAI_MULTIMODAL_DEPLOYMENT 사용
        self.vision_model = settings.azure_openai_multimodal_deployment
        logger.info(f"✅ Vision 서비스 초기화 완료: {self.vision_model}")
    
    async def analyze_image_from_url(
        self, 
        image_url: str, 
        prompt: str = "이미지를 상세히 설명해주세요.",
        max_tokens: int = 500
    ) -> str:
        """
        URL로부터 이미지 분석
        
        Args:
            image_url: 이미지 URL (Blob Storage SAS URL)
            prompt: 분석 프롬프트
            max_tokens: 최대 토큰 수
        
        Returns:
            이미지 설명 텍스트
        """
        try:
            logger.info(f"🔍 Vision 분석 시작: {image_url[:100]}...")
            
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 이미지를 정확하고 상세하게 분석하는 AI 어시스턴트입니다. 한국어로 답변하세요."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"  # high/low/auto
                                }
                            }
                        ]
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            description = response.choices[0].message.content
            if not description:
                logger.warning("⚠️ Vision API returned empty content")
                return "이미지 분석 결과를 가져올 수 없습니다."
            
            logger.info(f"✅ Vision 분석 완료: {description[:100]}...")
            
            return description
            
        except Exception as e:
            logger.error(f"❌ Vision 분석 실패: {e}")
            return f"이미지 분석 중 오류가 발생했습니다: {str(e)}"
    
    async def analyze_image_from_base64(
        self,
        base64_image: str,
        prompt: str = "이미지를 상세히 설명해주세요.",
        max_tokens: int = 500
    ) -> str:
        """
        Base64 인코딩된 이미지 분석
        
        Args:
            base64_image: Base64 인코딩된 이미지 데이터
            prompt: 분석 프롬프트
            max_tokens: 최대 토큰 수
        
        Returns:
            이미지 설명 텍스트
        """
        try:
            logger.info("🔍 Vision 분석 시작 (Base64)")
            
            # data:image/jpeg;base64, 접두사 처리
            if base64_image.startswith('data:image'):
                base64_image = base64_image.split(',')[1]
            
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 이미지를 정확하고 상세하게 분석하는 AI 어시스턴트입니다. 한국어로 답변하세요."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            description = response.choices[0].message.content
            if not description:
                logger.warning("⚠️ Vision API returned empty content")
                return "이미지 분석 결과를 가져올 수 없습니다."
            
            logger.info(f"✅ Vision 분석 완료: {description[:100]}...")
            
            return description
            
        except Exception as e:
            logger.error(f"❌ Vision 분석 실패: {e}")
            return f"이미지 분석 중 오류가 발생했습니다: {str(e)}"
    
    async def analyze_multiple_images(
        self,
        image_urls: List[str],
        prompt: str = "각 이미지를 설명해주세요.",
        max_tokens: int = 1000
    ) -> List[str]:
        """
        여러 이미지 분석
        
        Args:
            image_urls: 이미지 URL 리스트
            prompt: 분석 프롬프트
            max_tokens: 최대 토큰 수
        
        Returns:
            이미지 설명 리스트
        """
        descriptions = []
        
        for i, url in enumerate(image_urls):
            logger.info(f"🔍 이미지 {i+1}/{len(image_urls)} 분석 중...")
            description = await self.analyze_image_from_url(
                image_url=url,
                prompt=f"{prompt} (이미지 {i+1})",
                max_tokens=max_tokens // len(image_urls)
            )
            descriptions.append(description)
        
        return descriptions
    
    async def extract_text_from_image(
        self,
        image_url: str,
        max_tokens: int = 1000
    ) -> str:
        """
        이미지에서 텍스트 추출 (OCR)
        
        Args:
            image_url: 이미지 URL
            max_tokens: 최대 토큰 수
        
        Returns:
            추출된 텍스트
        """
        prompt = """
        이미지에 포함된 모든 텍스트를 정확하게 추출해주세요.
        - 표, 차트의 레이블도 포함
        - 원본 형식 유지
        - 텍스트만 반환 (설명 제외)
        """
        
        return await self.analyze_image_from_url(
            image_url=image_url,
            prompt=prompt,
            max_tokens=max_tokens
        )
    
    async def describe_chart_or_diagram(
        self,
        image_url: str,
        max_tokens: int = 800
    ) -> str:
        """
        차트/다이어그램 설명
        
        Args:
            image_url: 이미지 URL
            max_tokens: 최대 토큰 수
        
        Returns:
            차트 설명
        """
        prompt = """
        이미지의 차트 또는 다이어그램을 분석하고 다음 정보를 제공해주세요:
        1. 차트 유형 (막대, 선, 원형 등)
        2. 주요 데이터 포인트
        3. 트렌드 및 인사이트
        4. 축 레이블 및 범례
        """
        
        return await self.analyze_image_from_url(
            image_url=image_url,
            prompt=prompt,
            max_tokens=max_tokens
        )
    
    async def compare_images(
        self,
        image_urls: List[str],
        comparison_prompt: str = "이미지들을 비교하고 차이점과 공통점을 설명해주세요.",
        max_tokens: int = 1000
    ) -> str:
        """
        여러 이미지 비교 분석
        
        Args:
            image_urls: 이미지 URL 리스트
            comparison_prompt: 비교 프롬프트
            max_tokens: 최대 토큰 수
        
        Returns:
            비교 분석 결과
        """
        try:
            logger.info(f"🔍 {len(image_urls)}개 이미지 비교 분석 시작")
            
            # 여러 이미지를 한 번에 분석
            from typing import Any
            content: List[Dict[str, Any]] = [{"type": "text", "text": comparison_prompt}]
            
            for i, url in enumerate(image_urls):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                        "detail": "high"
                    }
                })
            
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 이미지를 비교 분석하는 전문가입니다. 한국어로 답변하세요."
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            comparison = response.choices[0].message.content
            if not comparison:
                logger.warning("⚠️ Vision API returned empty content")
                return "비교 분석 결과를 가져올 수 없습니다."
            
            logger.info(f"✅ 비교 분석 완료: {comparison[:100]}...")
            
            return comparison
            
        except Exception as e:
            logger.error(f"❌ 비교 분석 실패: {e}")
            return f"이미지 비교 중 오류가 발생했습니다: {str(e)}"


# 싱글톤 인스턴스
vision_service = VisionService()

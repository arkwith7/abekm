"""
Image Analysis Tool
이미지를 VLM(Vision Language Model)로 분석하여 텍스트 설명을 생성하는 도구
"""
from typing import Any, List, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from app.services.core.ai_service import ai_service  # 올바른 경로
from app.core.config import settings
from loguru import logger


class ImageAnalysisInput(BaseModel):
    """이미지 분석 도구 입력"""
    images: List[str] = Field(description="분석할 이미지들 (base64 인코딩 또는 URL)")
    query: str = Field(description="사용자 질문 (이미지 분석 컨텍스트)")
    detail_level: str = Field(default="detailed", description="분석 상세도: simple, detailed, comprehensive")


class ImageAnalysisTool(BaseTool):
    """
    이미지 분석 도구
    - VLM을 사용하여 이미지 내용을 텍스트로 변환
    - 사용자 질문과 관련된 정보 추출
    - OCR 텍스트 인식 포함
    """
    
    name: str = "image_analysis"
    description: str = """
    이미지를 분석하여 텍스트 설명을 생성합니다.
    사용 시점:
    - 이미지가 첨부된 경우
    - 이미지 내용에 대한 질문인 경우
    - OCR이 필요한 경우 (문서 이미지, 차트, 다이어그램)
    
    입력: images (List[str]), query (str)
    출력: 이미지 설명 텍스트
    """
    args_schema: type[BaseModel] = ImageAnalysisInput
    
    class Config:
        arbitrary_types_allowed = True

    def _run(self, *args, **kwargs) -> str:
        """동기 실행 (미지원)"""
        raise NotImplementedError("이미지 분석은 비동기로만 실행 가능합니다.")

    async def _arun(
        self,
        images: List[str],
        query: str,
        detail_level: str = "detailed",
        **kwargs
    ) -> str:
        """
        이미지 분석 실행
        
        Args:
            images: 분석할 이미지 목록 (base64 또는 URL)
            query: 사용자 질문
            detail_level: 분석 상세도
            
        Returns:
            str: 이미지 분석 결과 (텍스트 설명)
        """
        if not images:
            logger.warning("📷 [ImageAnalysis] 이미지가 없음")
            return ""
        
        try:
            logger.info(f"📷 [ImageAnalysis] 시작: {len(images)}개 이미지, detail={detail_level}")
            
            # 프롬프트 구성 (상세도에 따라)
            if detail_level == "simple":
                prompt = f"사용자 질문: {query}\n\n이미지의 주요 내용을 간단히 설명해주세요."
            elif detail_level == "comprehensive":
                prompt = f"""사용자 질문: {query}

이미지를 매우 상세히 분석하여 다음을 포함해주세요:
1. 이미지의 전체적인 내용과 구조
2. 텍스트 내용 (OCR - 모든 가독 가능한 텍스트)
3. 차트/그래프가 있다면 데이터 해석
4. 사용자 질문과 관련된 구체적인 정보
5. 주요 객체, 색상, 레이아웃"""
            else:  # detailed (기본)
                prompt = f"""사용자 질문: {query}

이미지의 내용을 상세히 분석하고 다음을 포함해주세요:
1. 이미지의 주요 내용
2. 텍스트 내용 (OCR - 읽을 수 있는 모든 텍스트)
3. 사용자 질문과 관련된 정보
4. 주요 시각적 요소"""
            
            content = [{"type": "text", "text": prompt}]
            
            # 이미지 추가
            for img_base64 in images:
                # 헤더 처리
                if "base64," in img_base64:
                    url = img_base64
                elif img_base64.startswith('http'):
                    url = img_base64
                else:
                    url = f"data:image/jpeg;base64,{img_base64}"
                
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url}
                })
            
            messages = [{"role": "user", "content": content}]
            
            # VLM 호출 (전역 싱글톤 사용)
            max_tokens = 2000 if detail_level == "comprehensive" else 1000
            response = await ai_service.chat_completion(
                messages,
                max_tokens=max_tokens,
                temperature=0.0
            )
            
            description = response.get("response", "").strip()
            
            if not description:
                logger.warning("📷 [ImageAnalysis] 빈 응답")
                return "이미지 분석 결과가 없습니다."
            
            logger.info(f"✅ [ImageAnalysis] 완료: {len(description)}자")
            return description
            
        except Exception as e:
            error_msg = f"이미지 분석 실패: {str(e)}"
            logger.error(f"❌ [ImageAnalysis] {error_msg}", exc_info=True)
            return error_msg


# 싱글톤 인스턴스
_image_analysis_tool_instance: Optional[ImageAnalysisTool] = None


def get_image_analysis_tool() -> ImageAnalysisTool:
    """이미지 분석 도구 싱글톤 인스턴스 반환"""
    global _image_analysis_tool_instance
    if _image_analysis_tool_instance is None:
        _image_analysis_tool_instance = ImageAnalysisTool()
    return _image_analysis_tool_instance

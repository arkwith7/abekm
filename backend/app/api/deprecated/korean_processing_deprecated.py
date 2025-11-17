"""
한국어 처리 전용 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from app.services.korean_nlp_service import korean_nlp_service

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Korean NLP"])

# Request/Response 모델
class KoreanTextRequest(BaseModel):
    text: str
    analysis_type: str = "hybrid"  # "basic", "advanced", "hybrid"

class TokenizeRequest(BaseModel):
    text: str

class KeywordExtractionRequest(BaseModel):
    text: str
    top_k: int = 10

class EmbeddingRequest(BaseModel):
    text: str

class TokenizeResponse(BaseModel):
    tokens: List[str]
    pos_tags: List[tuple]
    token_count: int
    original_text: str

class KeywordResponse(BaseModel):
    keywords: List[str]
    text: str

class EmbeddingResponse(BaseModel):
    embedding: Optional[List[float]]
    dimension: Optional[int]
    text: str

class HybridAnalysisResponse(BaseModel):
    text: str
    basic_analysis: Dict[str, Any]
    advanced_analysis: Dict[str, Any]
    processing_mode: str
    timestamp: float

@router.post("/tokenize", response_model=TokenizeResponse)
async def tokenize_korean_text(request: TokenizeRequest):
    """한국어 텍스트 토큰화"""
    try:
        result = await korean_nlp_service.tokenize_korean_text(request.text)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return TokenizeResponse(**result)
        
    except Exception as e:
        logger.error(f"Tokenization API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/keywords", response_model=KeywordResponse)
async def extract_keywords(request: KeywordExtractionRequest):
    """한국어 키워드 추출"""
    try:
        keywords = await korean_nlp_service.extract_keywords(request.text, request.top_k)
        
        return KeywordResponse(
            keywords=keywords,
            text=request.text
        )
        
    except Exception as e:
        logger.error(f"Keyword extraction API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embedding", response_model=EmbeddingResponse)
async def generate_embedding(request: EmbeddingRequest):
    """한국어 텍스트 임베딩 생성"""
    try:
        embedding = await korean_nlp_service.generate_korean_embedding(request.text)
        
        return EmbeddingResponse(
            embedding=embedding,
            dimension=len(embedding) if embedding else None,
            text=request.text
        )
        
    except Exception as e:
        logger.error(f"Embedding API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=HybridAnalysisResponse)
async def analyze_korean_text(request: KoreanTextRequest):
    """하이브리드 한국어 텍스트 분석"""
    try:
        if request.analysis_type == "basic":
            # 기본 kiwipiepy 분석만
            result = await korean_nlp_service.tokenize_korean_text(request.text)
            keywords = await korean_nlp_service.extract_keywords(request.text)
            
            return HybridAnalysisResponse(
                text=request.text,
                basic_analysis={
                    "tokens": result.get("tokens", []),
                    "pos_tags": result.get("pos_tags", []),
                    "token_count": result.get("token_count", 0),
                    "keywords": keywords
                },
                advanced_analysis={},
                processing_mode="basic",
                timestamp=0
            )
            
        elif request.analysis_type == "advanced":
            # Bedrock 분석만
            bedrock_result = await korean_nlp_service.analyze_with_bedrock(request.text)
            
            return HybridAnalysisResponse(
                text=request.text,
                basic_analysis={},
                advanced_analysis=bedrock_result,
                processing_mode="advanced",
                timestamp=0
            )
            
        else:  # hybrid
            # 전체 하이브리드 분석
            result = await korean_nlp_service.hybrid_process_korean_text(request.text)
            
            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            
            return HybridAnalysisResponse(**result)
        
    except Exception as e:
        logger.error(f"Analysis API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chunks")
async def chunk_korean_text(request: TokenizeRequest):
    """한국어 텍스트 청킹"""
    try:
        chunks = korean_nlp_service.calculate_text_chunks(request.text)
        
        return {
            "chunks": chunks,
            "chunk_count": len(chunks),
            "original_text": request.text
        }
        
    except Exception as e:
        logger.error(f"Chunking API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def korean_nlp_health():
    """한국어 NLP 서비스 상태 확인"""
    try:
        # 간단한 테스트 실행
        test_result = await korean_nlp_service.tokenize_korean_text("(주)웅진 테스트")
        
        service_status = "healthy"
        if "error" in test_result:
            service_status = "limited"
        
        return {
            "status": service_status,
            "service": "korean_nlp",
            "components": {
                "kiwipiepy": "ok" if korean_nlp_service.kiwi else "not_available",
                "tokenizer": "ok" if korean_nlp_service.tokenizer else "not_available",
                "bedrock": "ok" if korean_nlp_service.bedrock_client else "not_configured",
                "embedding": "ok" if korean_nlp_service.embedding_model else "loading_or_not_available"
            },
            "test_result": test_result
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

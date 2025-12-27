"""
통합 검색 API
- 기본 벡터 검색 (레거시 호환)
- 하이브리드 검색 (벡터 + 키워드 + 전문검색)
- 벡터 전용 검색
- 키워드 전용 검색  
- 멀티모달 검색 (텍스트 + 이미지)
- 검색 제안 및 분석
- 문서 재인덱싱

모든 검색 기능을 단일 API로 통합하여 제공
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
import logging
import json

from app.core.database import get_db
from app.schemas.chat import SearchRequest, SearchResponse
from app.services.search.search_service import search_service
from app.services.search import multimodal_search_service
from app.core.dependencies import get_current_user
from app.models import User
from app.utils.provider_filters import get_provider_summary
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["🔍 Search"])

# 하이브리드 검색용 모델
class HybridSearchRequest(BaseModel):
    """하이브리드 검색 요청 모델"""
    query: str = Field(..., min_length=2, max_length=500, description="검색 쿼리")
    container_ids: Optional[List[str]] = Field(None, description="검색 대상 컨테이너 ID 목록")
    search_type: str = Field("hybrid", description="검색 타입 (hybrid, vector_only, keyword_only)")
    max_results: int = Field(10, ge=1, le=50, description="최대 결과 수")
    filters: Optional[Dict[str, Any]] = Field(None, description="추가 필터")

class HybridSearchResult(BaseModel):
    """하이브리드 검색 결과 모델"""
    file_id: str
    title: str
    content_preview: str
    similarity_score: float
    match_type: str  # "vector", "keyword", "fulltext"
    container_id: str
    container_name: Optional[str] = None  # 사용자 친화적인 컨테이너 이름
    container_path: Optional[str] = None  # 전체 경로 (아이콘 포함)
    container_icon: Optional[str] = None  # 폴더 아이콘
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    # 멀티모달 검색 필드
    has_images: Optional[bool] = None
    image_count: Optional[int] = None
    clip_score: Optional[float] = None
    modality: Optional[str] = None  # "text", "image", "table"
    image_url: Optional[str] = None
    image_blob_key: Optional[str] = None
    chunk_id: Optional[int] = None
    thumbnail_blob_key: Optional[str] = None
    thumbnail_chunk_id: Optional[int] = None

class HybridSearchResponse(BaseModel):
    """하이브리드 검색 응답 모델"""
    results: List[HybridSearchResult]
    total_count: int
    search_type: str
    accessible_containers: List[str]
    query_processed: Dict[str, Any]
    execution_time: str
    message: Optional[str] = None

# 통합검색용 모델
class UnifiedSearchResult(BaseModel):
    """통합검색 결과 모델 (파일 단위)"""
    file_id: str
    title: str
    content_preview: str
    similarity_score: Optional[float] = None  # 청크 레벨 유사도
    max_similarity_score: Optional[float] = None  # 파일 레벨 최대 유사도
    match_type: str
    container_id: str
    container_name: Optional[str] = None  # 사용자 친화적인 컨테이너 이름
    container_path: Optional[str] = None  # 전체 경로
    container_icon: Optional[str] = None  # 폴더 아이콘
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    chunk_count: Optional[int] = None
    top_chunks: Optional[List[Dict[str, Any]]] = None

class UnifiedSearchResponse(BaseModel):
    """통합검색 응답 모델"""
    results: List[UnifiedSearchResult]
    total_count: int
    search_type: str
    accessible_containers: List[str]
    query_processed: Dict[str, Any]
    execution_time: str
    message: Optional[str] = None

# RAG 컨텍스트용 모델
class ContextSearchResult(BaseModel):
    """RAG 컨텍스트 검색 결과 모델 (청크 단위)"""
    chunk_id: str
    file_id: str
    content: str
    similarity_score: float
    match_type: str
    container_id: str
    chunk_info: Dict[str, Any]
    reference_info: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class ContextSearchResponse(BaseModel):
    """RAG 컨텍스트 검색 응답 모델"""
    results: List[ContextSearchResult]
    total_count: int
    search_type: str
    context_info: Dict[str, Any]
    accessible_containers: List[str]
    query_processed: Dict[str, Any]
    execution_time: str
    message: Optional[str] = None


class ClipSearchRequest(BaseModel):
    """CLIP 검색 요청 모델."""
    query_type: Literal["text", "image_base64", "image_bytes", "vector"] = "text"
    text_query: Optional[str] = None
    image_base64: Optional[str] = None
    clip_vector: Optional[List[float]] = None
    top_k: int = 5
    similarity_threshold: float = 0.30
    accessible_container_ids: Optional[List[str]] = None


class ClipSearchResult(BaseModel):
    """CLIP 기반 멀티모달 검색 결과."""
    chunk_id: Optional[int]
    embedding_id: Optional[int]
    file_id: Optional[int]
    chunk_index: Optional[int]
    content: Optional[str]
    token_count: Optional[int]
    similarity_score: Optional[float]
    distance: Optional[float]
    modality: Optional[str]
    file_name: Optional[str]
    file_path: Optional[str]
    container_id: Optional[str]
    clip_score: Optional[float] = None
    has_images: Optional[bool] = None
    image_count: Optional[int] = None


class ClipSearchResponse(BaseModel):
    """CLIP 검색 응답 모델."""
    results: List[ClipSearchResult]
    success: bool
    top_k: int
    similarity_threshold: float
    query_type: str
    query_embedding: Optional[List[float]] = None
    message: Optional[str] = None

@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    기본 문서 검색 엔드포인트 (하이브리드 검색 사용)
    벡터 + 키워드 + 전문검색을 통해 관련 문서를 찾습니다.
    """
    try:
        logger.info(f"문서 검색 요청: {current_user.emp_no}, 쿼리: {request.query}")
        
        # 하이브리드 검색 수행
        search_result = await search_service.hybrid_search(
            query=request.query,
            user_emp_no=current_user.emp_no,
            container_ids=None,  # 모든 접근 가능한 컨테이너 검색
            max_results=getattr(request, 'limit', 10),
            search_type="hybrid",
            filters=None
        )
        
        # 레거시 형식으로 변환
        legacy_results = []
        for result in search_result.get("results", []):
            # search_service 응답에서 올바른 필드 추출
            legacy_results.append({
                "id": result.get("file_id", ""),
                "content": result.get("content_preview", ""),
                "metadata": {
                    "title": result.get("title", ""),
                    "file_id": result.get("file_id", ""),
                    "container_id": result.get("container_id", ""),
                    "keywords": result.get("metadata", {}).get("keywords", []),
                    "document_type": result.get("metadata", {}).get("document_type", ""),
                    "file_path": result.get("file_path", "")
                },
                "similarity_score": result.get("similarity_score", 0.0)
            })
        
        return SearchResponse(
            results=legacy_results,
            total_count=search_result.get("total_count", 0),
            query=request.query,
            search_metadata={
                "search_type": "hybrid",
                "execution_time": search_result.get("execution_time"),
                "accessible_containers": len(search_result.get("accessible_containers", [])),
                "message": search_result.get("message")
            }
        )
        
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/search/unified", response_model=UnifiedSearchResponse)
async def unified_search(
    request: HybridSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    통합검색 - 파일 단위로 그룹화된 검색 결과
    프론트엔드 검색 화면 표시용 (동일 파일의 청크들을 하나로 통합)
    """
    try:
        logger.info(f"통합검색 요청: {current_user.emp_no}, 쿼리: {request.query}")
        
        # 통합검색 수행
        search_result = await search_service.unified_search(
            query=request.query,
            user_emp_no=current_user.emp_no,
            container_ids=request.container_ids,
            max_results=request.max_results,
            search_type=request.search_type,
            filters=request.filters
        )
        
        return search_result
        
    except Exception as e:
        logger.error(f"통합검색 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통합검색 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/search/context", response_model=ContextSearchResponse)
async def context_search(
    request: HybridSearchRequest,
    include_references: bool = Query(True, description="참조 정보 포함 여부"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    RAG 컨텍스트용 청크 단위 정밀 검색
    챗봇 응답 생성을 위한 상세한 청크 정보 제공
    """
    try:
        logger.info(f"컨텍스트 검색 요청: {current_user.emp_no}, 쿼리: {request.query}")
        
        # 컨텍스트 검색 수행
        search_result = await search_service.context_search(
            query=request.query,
            user_emp_no=current_user.emp_no,
            container_ids=request.container_ids,
            max_results=request.max_results,
            search_type=request.search_type,
            filters=request.filters,
            include_references=include_references
        )
        
        return search_result
        
    except Exception as e:
        logger.error(f"컨텍스트 검색 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컨텍스트 검색 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/search/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    하이브리드 검색 수행
    - 벡터 유사도 검색
    - 키워드 매칭 검색  
    - PostgreSQL 전문검색
    
    ⚠️ 현재 프로바이더(.env)로 처리된 문서만 검색됩니다.
    """
    try:
        # 🌩️ 프로바이더 설정 로깅 (디버깅용)
        provider_info = get_provider_summary()
        logger.info(
            f"하이브리드 검색 요청: {current_user.emp_no}, 쿼리: {request.query}, "
            f"프로바이더: {provider_info['embedding_provider']}, "
            f"임베딩 차원: {provider_info['embedding_dimension']}d"
        )
        
        # 검색 수행
        search_result = await search_service.hybrid_search(
            query=request.query,
            user_emp_no=current_user.emp_no,
            container_ids=request.container_ids,
            max_results=request.max_results,
            search_type=request.search_type,
            filters=request.filters
        )
        
        # 🔍 응답 검증 로그 (첫 번째 결과만)
        if search_result.get("results") and len(search_result["results"]) > 0:
            first_result = search_result["results"][0]
            logger.info(f"🔍 [API Response] 첫 번째 결과 검증:")
            logger.info(f"  - file_id: {first_result.get('file_id')}")
            logger.info(f"  - title: {first_result.get('title')}")
            logger.info(f"  - container_id: {first_result.get('container_id')}")
            logger.info(f"  - container_name: {first_result.get('container_name')}")
            logger.info(f"  - container_path: {first_result.get('container_path')}")
            logger.info(f"  - modality: {first_result.get('modality')}")
            logger.info(f"  - image_blob_key: {first_result.get('image_blob_key')}")
            logger.info(f"  - thumbnail_blob_key: {first_result.get('thumbnail_blob_key')}")
            logger.info(f"  - content_preview: {first_result.get('content_preview')[:50] if first_result.get('content_preview') else 'None'}...")
        
        return search_result
        
    except Exception as e:
        logger.error(f"하이브리드 검색 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"하이브리드 검색 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/search/vector")
async def vector_search(
    query: str = Query(..., description="검색 쿼리"),
    limit: int = Query(10, ge=1, le=50, description="결과 개수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    벡터 검색 전용
    
    ⚠️ 현재 프로바이더(.env)로 처리된 문서만 검색됩니다.
    """
    try:
        # 🌩️ 프로바이더 설정 로깅
        provider_info = get_provider_summary()
        logger.info(
            f"벡터 검색 요청: {current_user.emp_no}, 쿼리: {query}, "
            f"프로바이더: {provider_info['embedding_provider']}, "
            f"임베딩 차원: {provider_info['embedding_dimension']}d"
        )
        
        results = await search_service.vector_search_only(
            query=query,
            user_emp_no=current_user.emp_no,
            limit=limit
        )
        return results
    except Exception as e:
        logger.error(f"벡터 검색 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/keyword")
async def keyword_search(
    query: str = Query(..., description="검색 키워드"),
    limit: int = Query(10, ge=1, le=50, description="결과 개수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """키워드 검색 전용"""
    try:
        results = await search_service.keyword_search_only(
            query=query,
            user_emp_no=current_user.emp_no,
            limit=limit
        )
        return results
    except Exception as e:
        logger.error(f"키워드 검색 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/suggestions")
async def get_search_suggestions(
    query: str = Query(..., description="검색어"),
    limit: int = Query(5, description="제안 개수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """검색 제안 기능"""
    try:
        suggestions = await search_service.get_search_suggestions(
            partial_query=query,
            user_emp_no=current_user.emp_no,
            limit=limit
        )
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"검색 제안 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/analytics")
async def get_search_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """검색 분석 정보"""
    try:
        analytics = await search_service.get_search_analytics(
            user_emp_no=current_user.emp_no
        )
        return analytics
    except Exception as e:
        logger.error(f"검색 분석 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/reindex/{file_id}")
async def reindex_document(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """문서 재인덱싱"""
    try:
        result = await search_service.reindex_document(
            file_id=file_id,
            user_emp_no=current_user.emp_no
        )
        return result
    except Exception as e:
        logger.error(f"문서 재인덱싱 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 멀티모달 검색 엔드포인트 (CLIP 기반 이미지 검색)
# ============================================================================

class MultimodalSearchRequest(BaseModel):
    """멀티모달 검색 요청 (텍스트 + 이미지 선택 가능)"""
    query: str = Field(..., min_length=1, max_length=1000, description="검색 쿼리 (텍스트)")
    top_k: int = Field(10, ge=1, le=50, description="반환할 최대 결과 수")
    container_ids: Optional[List[str]] = Field(None, description="필터링할 컨테이너 ID 목록")
    file_ids: Optional[List[int]] = Field(None, description="필터링할 파일 ID 목록") 
    similarity_threshold: float = Field(0.3, ge=0.0, le=1.0, description="최소 유사도 임계값")
    prefer_images: bool = Field(False, description="이미지가 있는 문서 우선")
    search_type: str = Field("hybrid", description="검색 유형: hybrid, vector_only, keyword_only, clip")

class MultimodalSearchResult(BaseModel):
    """멀티모달 검색 결과 항목"""
    chunk_id: int
    embedding_id: Optional[int] = None
    file_id: int
    chunk_index: int
    content: str
    token_count: Optional[int] = None
    modality: str
    file_name: str
    file_path: Optional[str] = None  # 파일 경로 추가
    container_id: Optional[str] = None
    container_path: Optional[str] = None  # 컨테이너 경로 추가
    similarity_score: float
    distance: Optional[float] = None
    has_images: bool = False
    image_count: int = 0
    clip_score: Optional[float] = None  # CLIP 유사도 점수
    metadata: Optional[Dict[str, Any]] = None  # 추가 메타데이터

class MultimodalSearchResponse(BaseModel):
    """멀티모달 검색 응답"""
    success: bool
    query: str
    has_image_query: bool = False
    results: List[MultimodalSearchResult]
    total_found: int
    search_metadata: dict


@router.post("/multimodal", response_model=MultimodalSearchResponse)
async def multimodal_search(
    request: MultimodalSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    멀티모달 통합 검색 (텍스트 + 이미지 메타데이터)
    
    🎯 기능:
    - 텍스트 하이브리드 검색 (벡터 + 키워드 + FTS)
    - 이미지 메타데이터 필터링
    - 멀티모달 결과 통합
    
    🔐 권한: 로그인 사용자
    ✨ 특징: 이미지 포함 문서 우선 검색
    """
    try:
        logger.info(f"[MULTIMODAL_API] 검색 시작 - 사용자: {current_user.emp_no}, 쿼리: {request.query[:50]}...")
        
        # 통합 검색 서비스 사용
        filters = {
            'prefer_images': request.prefer_images,
            'file_ids': request.file_ids
        }
        
        search_results = await search_service.multimodal_search(
            query=request.query,
            user_emp_no=str(current_user.emp_no),
            image_query=None,  # 향후 이미지 업로드 지원
            container_ids=request.container_ids,
            max_results=request.top_k,
            filters=filters
        )
        
        # 결과 변환
        formatted_results = []
        for result in search_results.get('results', []):
            formatted_results.append(MultimodalSearchResult(
                chunk_id=result.get('chunk_id', 0),
                embedding_id=result.get('embedding_id'),
                file_id=result.get('file_id', 0),
                chunk_index=result.get('chunk_index', 0),
                content=result.get('content', ''),
                token_count=result.get('token_count'),
                modality=result.get('modality', 'text'),
                file_name=result.get('file_name', ''),
                file_path=result.get('file_path'),  # 파일 경로 추가
                container_id=result.get('container_id'),
                container_path=result.get('container_path'),  # 컨테이너 경로 추가
                similarity_score=result.get('similarity_score', 0.0),
                distance=result.get('distance'),
                has_images=result.get('has_images', False),
                image_count=result.get('image_count', 0),
                clip_score=result.get('clip_score'),
                metadata=result.get('metadata')  # 메타데이터 추가
            ))
        
        # 응답 구성
        response = MultimodalSearchResponse(
            success=search_results.get('success', True),
            query=request.query,
            has_image_query=False,
            results=formatted_results,
            total_found=search_results.get('total_results', len(formatted_results)),
            search_metadata={
                **search_results.get('search_metadata', {}),
                "top_k": request.top_k,
                "similarity_threshold": request.similarity_threshold,
                "container_filter": request.container_ids is not None,
                "file_filter": request.file_ids is not None,
                "prefer_images": request.prefer_images,
                "search_type": request.search_type,
                "user_emp_no": str(current_user.emp_no),
                "multimodal_enabled": True
            }
        )
        
        logger.info(f"[MULTIMODAL_API] 검색 완료 - 결과: {len(formatted_results)}개")
        return response
        
    except Exception as e:
        logger.error(f"[MULTIMODAL_API] 검색 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"멀티모달 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/search/clip", response_model=ClipSearchResponse)
async def clip_search(
    request: ClipSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """CLIP 기반 이미지/텍스트 검색 엔드포인트."""
    try:
        logger.info(
            "[CLIP_API] 검색 시작 - 사용자: %s, 타입: %s, top_k: %s",
            current_user.emp_no,
            request.query_type,
            request.top_k,
        )

        user_emp_no = str(current_user.emp_no)
        container_ids = request.accessible_container_ids

        if request.query_type == "text":
            if not request.text_query:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="text_query 값이 필요합니다."
                )
            service_result = await multimodal_search_service.search_by_text_prompt(
                user_emp_no=user_emp_no,
                text=request.text_query,
                container_ids=container_ids,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold,
            )
        elif request.query_type == "image_base64":
            if not request.image_base64:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="image_base64 값이 필요합니다."
                )
            service_result = await multimodal_search_service.search_by_image(
                user_emp_no=user_emp_no,
                image_base64=request.image_base64,
                container_ids=container_ids,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold,
            )
        elif request.query_type == "vector":
            if not request.clip_vector:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="clip_vector 값이 필요합니다."
                )
            service_result = await multimodal_search_service.search_by_clip_vector(
                user_emp_no=user_emp_no,
                clip_vector=request.clip_vector,
                container_ids=container_ids,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 query_type 입니다: {request.query_type}"
            )

        raw_results = service_result.get("results", []) if service_result else []

        clip_results = [
            ClipSearchResult(
                chunk_id=result.get("chunk_id"),
                embedding_id=result.get("embedding_id"),
                file_id=result.get("file_id"),
                chunk_index=result.get("chunk_index"),
                content=result.get("content"),
                token_count=result.get("token_count"),
                similarity_score=result.get("similarity_score"),
                distance=result.get("distance"),
                modality=result.get("modality"),
                file_name=result.get("file_name"),
                file_path=result.get("file_path"),
                container_id=result.get("container_id"),
                clip_score=result.get("clip_score"),
                has_images=result.get("has_images"),
                image_count=result.get("image_count"),
            )
            for result in raw_results
        ]

        response = ClipSearchResponse(
            results=clip_results,
            success=service_result.get("success", True) if service_result else False,
            top_k=service_result.get("top_k", request.top_k) if service_result else request.top_k,
            similarity_threshold=service_result.get("similarity_threshold", request.similarity_threshold) if service_result else request.similarity_threshold,
            query_type=request.query_type,
            query_embedding=service_result.get("query_embedding") if service_result else None,
            message=service_result.get("message") if service_result else None,
        )

        logger.info(
            "[CLIP_API] 검색 완료 - 결과: %d개, success: %s",
            len(response.results),
            response.success,
        )
        return response

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - 예외 상황 방어
        logger.error("[CLIP_API] 검색 실패: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CLIP 검색 중 오류가 발생했습니다: {str(exc)}",
        )


# 🗑️ 레거시 documents 엔드포인트들 - v1/documents.py로 통합됨
# @router.post("/documents", response_model=DocumentResponse)
# async def create_document(
#     document: DocumentCreate,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     새 문서 생성 엔드포인트 (DEPRECATED: v1/documents.py 사용)
#     """
#     try:
#         document_service = DocumentService(db)
#         result = await document_service.create_document(document)
#         return result
#         
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"문서 생성 중 오류가 발생했습니다: {str(e)}"
#         )

# @router.post("/documents/upload")
# async def upload_document(
#     file: UploadFile = File(...),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     파일 업로드 엔드포인트 (DEPRECATED: v1/documents.py 사용)
#     """
#     try:
#         document_service = DocumentService(db)
#         result = await document_service.upload_and_process_file(file)
#         return {"message": "파일이 성공적으로 업로드되었습니다.", "document_id": result.id}
#         
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"파일 업로드 중 오류가 발생했습니다: {str(e)}"
#         )

# @router.get("/documents", response_model=List[DocumentResponse])
# async def list_documents(
#     skip: int = 0,
#     limit: int = 100,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     문서 목록 조회 엔드포인트 (DEPRECATED: v1/documents.py 사용)
#     """
#     try:
#         document_service = DocumentService(db)
#         documents = await document_service.list_documents(skip=skip, limit=limit)
#         return documents
#         
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"문서 목록 조회 중 오류가 발생했습니다: {str(e)}"
#         )

# @router.get("/documents/{document_id}", response_model=DocumentResponse)
# async def get_document(
#     document_id: str,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     특정 문서 조회 엔드포인트 (DEPRECATED: v1/documents.py 사용)
#     """
#     try:
#         document_service = DocumentService(db)
#         document = await document_service.get_document(document_id)
#         
#         if not document:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="문서를 찾을 수 없습니다."
#             )
#         
#         return document
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"문서 조회 중 오류가 발생했습니다: {str(e)}"
#         )

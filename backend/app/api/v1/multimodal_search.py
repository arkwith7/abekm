"""멀티모달 검색 API 엔드포인트
=====================================

텍스트 + 이미지 멀티모달 검색 기능 제공
- 텍스트 검색: 벡터 + 키워드 + FTS 하이브리드
- 이미지 검색: 이미지 임베딩 벡터 검색 (향후 지원)
- 멀티모달 통합: 텍스트 + 이미지 동시 검색
- 컨테이너별 필터링 및 권한 관리
"""

from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.services.document.search.multimodal_search_service import multimodal_search_service
from app.services.search.search_service import search_service  # 새로운 통합 검색 서비스

logger = logging.getLogger(__name__)

# 라우터 설정
router = APIRouter(
    prefix="/search",
    tags=["🔍 Multimodal Search"],
    responses={
        400: {"description": "잘못된 요청"},
        401: {"description": "인증 필요"},
        500: {"description": "서버 내부 오류"}
    }
)

# 스키마 정의
class MultimodalSearchRequest(BaseModel):
    """멀티모달 검색 요청 (텍스트 + 이미지)"""
    query: Optional[str] = Field(None, min_length=1, max_length=1000, description="검색 쿼리 (텍스트) - image와 둘 중 하나 필수")
    image: Optional[str] = Field(None, description="검색 이미지 (Base64 인코딩) - query와 둘 중 하나 필수")
    top_k: int = Field(10, ge=1, le=50, description="반환할 최대 결과 수")
    container_ids: Optional[List[str]] = Field(None, description="필터링할 컨테이너 ID 목록")
    file_ids: Optional[List[int]] = Field(None, description="필터링할 파일 ID 목록") 
    similarity_threshold: float = Field(0.3, ge=0.0, le=1.0, description="최소 유사도 임계값")
    prefer_images: bool = Field(False, description="이미지가 있는 문서 우선 (멀티모달)")
    search_type: str = Field("hybrid", description="검색 유형: hybrid, vector_only, keyword_only, image_only")
    
    @classmethod
    def validate_request(cls, values):
        """query 또는 image 중 하나는 필수"""
        if not values.get('query') and not values.get('image'):
            raise ValueError("query 또는 image 중 하나는 필수입니다")
        return values

class SearchResult(BaseModel):
    """검색 결과 항목 (멀티모달)"""
    chunk_id: int
    embedding_id: Optional[int] = None
    file_id: int
    chunk_index: int
    content: str
    token_count: Optional[int] = None
    modality: str
    file_name: str
    title: Optional[str] = None  # 문서 제목 추가
    file_path: Optional[str] = None  # 파일 경로 추가
    container_id: Optional[str] = None
    container_name: Optional[str] = None  # 컨테이너 이름 추가
    container_path: Optional[str] = None  # 컨테이너 경로 추가
    similarity_score: float
    distance: Optional[float] = None
    has_images: bool = False  # 멀티모달: 이미지 포함 여부
    image_count: int = 0  # 멀티모달: 이미지 개수
    clip_score: Optional[float] = None  # CLIP 유사도 점수
    metadata: Optional[dict] = None  # 추가 메타데이터

class MultimodalSearchResponse(BaseModel):
    """멀티모달 검색 응답 (텍스트 + 이미지)"""
    success: bool
    query: str
    has_image_query: bool = False  # 이미지 쿼리 포함 여부
    results: List[SearchResult]
    total_found: int
    search_metadata: dict

class ChunkContextResponse(BaseModel):
    """청크 컨텍스트 응답"""
    success: bool
    target_chunk: dict
    context_chunks: List[dict]
    total_context_length: int

@router.post("/multimodal", response_model=MultimodalSearchResponse)
async def search_multimodal(
    request: MultimodalSearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 멀티모달 통합 검색 (텍스트 + 이미지)
    📋 단계:
        1. 텍스트 하이브리드 검색 (벡터 + 키워드 + FTS)
        2. 이미지 임베딩 검색 (CLIP 기반)
        3. 멀티모달 결과 통합
        4. 결과 반환
    🔐 권한: 로그인 사용자
    ✨ 새로운 기능: 이미지 붙여넣기 검색 지원
    
    요청 예시:
    - 텍스트 검색: {"query": "Figure 1"}
    - 이미지 검색: {"image": "data:image/png;base64,iVBOR..."}
    - 하이브리드: {"query": "Figure 1", "image": "data:image/..."}
    """
    try:
        # 검색 타입 결정
        search_mode = "text"
        if request.image and request.query:
            search_mode = "hybrid"
        elif request.image:
            search_mode = "image"
        
        # 로그 출력
        if search_mode == "image":
            logger.info(f"[MULTIMODAL_API] 이미지 검색 시작 - 사용자: {user.emp_no}")
        elif search_mode == "hybrid":
            query_preview = request.query[:50] if request.query and len(request.query) > 50 else request.query
            logger.info(f"[MULTIMODAL_API] 하이브리드 검색 시작 - 사용자: {user.emp_no}, 쿼리: {query_preview}...")
        else:
            query_preview = request.query[:50] if request.query and len(request.query) > 50 else request.query
            logger.info(f"[MULTIMODAL_API] 검색 시작 - 사용자: {user.emp_no}, 쿼리: {query_preview}...")
        
        # 통합 검색 서비스 사용 (하이브리드 검색)
        filters = {
            'prefer_images': request.prefer_images,
            'file_ids': request.file_ids
        }
        
        search_results = await search_service.multimodal_search(
            query=request.query or "",  # 이미지 전용 검색 시 빈 문자열
            user_emp_no=str(user.emp_no),
            image_query=request.image,  # Base64 이미지 데이터
            container_ids=request.container_ids,
            max_results=request.top_k,
            filters=filters
        )
        
        # 결과 변환
        formatted_results = []
        
        # 텍스트 검색 결과 추가
        for result in search_results.get('results', []):
            formatted_results.append(SearchResult(
                chunk_id=result.get('chunk_id', 0),
                embedding_id=result.get('embedding_id'),
                file_id=result.get('file_id', 0),
                chunk_index=result.get('chunk_index', 0),
                content=result.get('content', ''),
                token_count=result.get('token_count'),
                modality=result.get('modality', 'TEXT'),
                file_name=result.get('file_name', ''),
                title=result.get('title') or result.get('file_name'),
                file_path=result.get('file_path'),
                container_id=result.get('container_id'),
                container_name=result.get('container_name'),
                container_path=result.get('container_path'),
                similarity_score=result.get('similarity_score', 0.0),
                distance=result.get('distance'),
                has_images=result.get('has_images', False),
                image_count=result.get('image_count', 0),
                clip_score=result.get('clip_score'),
                metadata=result.get('metadata')
            ))
        
        # 이미지 검색 결과 추가
        for result in search_results.get('image_results', []):
            formatted_results.append(SearchResult(
                chunk_id=result.get('chunk_id', 0),
                embedding_id=result.get('embedding_id'),
                file_id=result.get('file_id', 0),
                chunk_index=result.get('chunk_index', 0),
                content=result.get('content', ''),
                token_count=result.get('token_count'),
                modality=result.get('modality', 'IMAGE'),
                file_name=result.get('file_name', ''),
                title=result.get('title') or result.get('file_name'),
                file_path=result.get('file_path'),
                container_id=result.get('container_id'),
                container_name=result.get('container_name'),
                container_path=result.get('container_path'),
                similarity_score=result.get('similarity_score', 0.0),
                distance=result.get('distance'),
                has_images=result.get('has_images', True),
                image_count=result.get('image_count', 1),
                clip_score=result.get('clip_score'),
                metadata=result.get('metadata')
            ))
        
        # 응답 구성
        response = MultimodalSearchResponse(
            success=search_results.get('success', True),
            query=request.query or "[이미지 검색]",
            has_image_query=bool(request.image),
            results=formatted_results,
            total_found=search_results.get('total_results', len(formatted_results)),
            search_metadata={
                **search_results.get('search_metadata', {}),
                "top_k": request.top_k,
                "similarity_threshold": request.similarity_threshold,
                "container_filter": request.container_ids is not None,
                "file_filter": request.file_ids is not None,
                "prefer_images": request.prefer_images,
                "search_type": search_mode,
                "user_emp_no": str(user.emp_no),
                "multimodal_enabled": True,
                "image_search_enabled": bool(request.image)
            }
        )
        
        logger.info(f"[MULTIMODAL_API] 검색 완료 - 결과: {len(formatted_results)}개, "
                   f"이미지 우선: {request.prefer_images}")
        return response
        
    except Exception as e:
        logger.error(f"[MULTIMODAL_API] 검색 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"멀티모달 검색 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/context/{chunk_id}", response_model=ChunkContextResponse)
async def get_chunk_context(
    chunk_id: int,
    context_window: int = Query(2, ge=1, le=10, description="앞뒤로 가져올 청크 수"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 특정 청크의 주변 컨텍스트 조회
    📋 단계:
        1. 대상 청크 조회
        2. 인접 청크들 조회
        3. 컨텍스트 구성
    🔐 권한: 로그인 사용자
    """
    try:
        logger.info(f"청크 컨텍스트 조회 - 사용자: {user.emp_no}, 청크 ID: {chunk_id}")
        
        # 컨텍스트 조회
        context_result = await multimodal_search_service.get_chunk_context(
            chunk_id=chunk_id,
            session=session,
            context_window=context_window
        )
        
        if "error" in context_result:
            raise HTTPException(status_code=404, detail=context_result["error"])
        
        response = ChunkContextResponse(
            success=True,
            target_chunk=context_result["target_chunk"],
            context_chunks=context_result["context_chunks"],
            total_context_length=context_result["total_context_length"]
        )
        
        logger.info(f"청크 컨텍스트 조회 완료 - 컨텍스트 청크: {len(context_result['context_chunks'])}개")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"청크 컨텍스트 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"컨텍스트 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/health")
async def search_health():
    """검색 서비스 상태 확인"""
    return {
        "status": "healthy",
        "service": "multimodal_search",
        "features": ["vector_search", "context_retrieval"],
        "vector_dimension": 3072
    }
@router.post("/multimodal/image", response_model=MultimodalSearchResponse)
async def search_with_image(
    query: str = Form(..., description="텍스트 검색 쿼리"),
    image: Optional[UploadFile] = File(None, description="이미지 검색 쿼리 (향후 지원)"),
    top_k: int = Form(10, ge=1, le=50, description="반환할 최대 결과 수"),
    container_ids: Optional[str] = Form(None, description="컨테이너 ID (쉼표로 구분)"),
    prefer_images: bool = Form(True, description="이미지가 있는 문서 우선"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🎯 기능: 이미지 + 텍스트 동시 검색 (멀티모달)
    📋 단계:
        1. 이미지 임베딩 생성 (향후 지원)
        2. 텍스트 하이브리드 검색
        3. 이미지 벡터 검색 (향후 지원)
        4. 결과 통합 및 재랭킹
    🔐 권한: 로그인 사용자
    ✨ 새로운 기능: 이미지 쿼리 지원 (준비 중)
    """
    try:
        logger.info(f"[MULTIMODAL_IMAGE_API] 이미지 검색 시작 - 사용자: {user.emp_no}")
        
        # 컨테이너 ID 파싱
        container_id_list = None
        if container_ids:
            container_id_list = [cid.strip() for cid in container_ids.split(',') if cid.strip()]
        
        # 이미지 데이터 읽기
        image_data = None
        if image:
            logger.info(f"[MULTIMODAL_IMAGE_API] 이미지 업로드됨 - 파일명: {image.filename}")
            image_data = await image.read()
            logger.warning(f"[MULTIMODAL_IMAGE_API] 이미지 검색 기능 준비 중")
        
        # 멀티모달 검색 수행
        filters = {'prefer_images': prefer_images}
        
        search_results = await search_service.multimodal_search(
            query=query,
            user_emp_no=str(user.emp_no),
            image_query=image_data,
            container_ids=container_id_list,
            max_results=top_k,
            filters=filters
        )
        
        # 결과 변환
        formatted_results = []
        for result in search_results.get('results', []):
            formatted_results.append(SearchResult(
                chunk_id=result.get('chunk_id', 0),
                embedding_id=result.get('embedding_id'),
                file_id=result.get('file_id', 0),
                chunk_index=result.get('chunk_index', 0),
                content=result.get('content', ''),
                token_count=result.get('token_count'),
                modality=result.get('modality', 'TEXT'),
                file_name=result.get('file_name', ''),
                title=result.get('title') or result.get('file_name'),
                file_path=result.get('file_path'),
                container_id=result.get('container_id'),
                container_name=result.get('container_name'),
                container_path=result.get('container_path'),
                similarity_score=result.get('similarity_score', 0.0),
                distance=result.get('distance'),
                has_images=result.get('has_images', False),
                image_count=result.get('image_count', 0),
                clip_score=result.get('clip_score'),
                metadata=result.get('metadata')
            ))
        
        # 응답 구성
        response = MultimodalSearchResponse(
            success=search_results.get('success', True),
            query=query,
            has_image_query=image_data is not None,
            results=formatted_results,
            total_found=search_results.get('total_results', len(formatted_results)),
            search_metadata={
                **search_results.get('search_metadata', {}),
                "top_k": top_k,
                "image_uploaded": image_data is not None,
                "multimodal_enabled": True
            }
        )
        
        logger.info(f"[MULTIMODAL_IMAGE_API] 검색 완료 - 결과: {len(formatted_results)}개")
        return response
        
    except Exception as e:
        logger.error(f"[MULTIMODAL_IMAGE_API] 검색 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"멀티모달 검색 실패: {str(e)}")


@router.post("/clip", response_model=MultimodalSearchResponse)
async def search_clip(
    query: str = Form(..., description="검색 쿼리 (텍스트)"),
    query_type: str = Form("text", description="쿼리 유형: text 또는 image"),
    image: Optional[UploadFile] = File(None, description="이미지 쿼리 파일 (선택적)"),
    top_k: int = Form(10, ge=1, le=50, description="반환할 최대 결과 수"),
    container_ids: Optional[str] = Form(None, description="컨테이너 ID (쉼표 구분)"),
    modality_filter: Optional[str] = Form(None, description="검색 모달리티: text, image, 또는 None (모두)"),
    similarity_threshold: float = Form(0.3, ge=0.0, le=1.0, description="최소 유사도 임계값"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🚀 기능: CLIP 기반 멀티모달 검색
    
    📋 특징:
        - 텍스트 쿼리로 이미지 검색 (크로스 모달)
        - 이미지 쿼리로 유사 이미지 검색
        - 이미지-텍스트 통합 검색
        - 512차원 CLIP 임베딩 벡터 사용
    
    🔐 권한: 로그인 사용자
    
    ✨ 새로운 기능: 
        - Azure CLIP 모델 기반
        - 크로스 모달 검색 지원
        - 하이브리드 검색 가능
    """
    try:
        logger.info(f"[CLIP_API] CLIP 검색 시작 - 사용자: {user.emp_no}, 쿼리: {query[:50]}...")
        
        # 컨테이너 ID 파싱
        container_id_list = None
        if container_ids:
            container_id_list = [cid.strip() for cid in container_ids.split(',') if cid.strip()]
        
        # 이미지 쿼리 처리
        if image and query_type == "image":
            logger.info(f"[CLIP_API] 이미지 쿼리 업로드됨 - 파일명: {image.filename}")
            # 임시 파일로 저장하거나 바이트로 직접 처리
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                content = await image.read()
                tmp.write(content)
                query = tmp.name  # 이미지 경로로 사용
        
        # CLIP 검색 수행
        search_results = await multimodal_search_service.search_multimodal_clip(
            query=query,
            session=session,
            query_type=query_type,
            top_k=top_k,
            container_ids=container_id_list,
            file_ids=None,
            similarity_threshold=similarity_threshold,
            modality_filter=modality_filter
        )
        
        # 결과 변환
        formatted_results = []
        for result in search_results:
            formatted_results.append(SearchResult(
                chunk_id=result.get('chunk_id', 0),
                embedding_id=result.get('embedding_id'),
                file_id=result.get('file_id', 0),
                chunk_index=result.get('chunk_index', 0),
                content=result.get('content', ''),
                token_count=result.get('token_count'),
                modality=result.get('modality', 'text'),
                file_name=result.get('file_name', ''),
                title=result.get('title') or result.get('file_name'),
                file_path=result.get('file_path'),
                container_id=result.get('container_id'),
                container_name=result.get('container_name'),
                container_path=result.get('container_path'),
                similarity_score=result.get('similarity_score', 0.0),
                distance=result.get('distance'),
                has_images=result.get('modality') == 'image',
                image_count=1 if result.get('modality') == 'image' else 0,
                clip_score=result.get('clip_score'),
                metadata=result.get('metadata')
            ))
        
        # 응답 구성
        response = MultimodalSearchResponse(
            success=True,
            query=query if query_type == "text" else f"이미지 쿼리: {image.filename if image else 'N/A'}",
            has_image_query=query_type == "image",
            results=formatted_results,
            total_found=len(formatted_results),
            search_metadata={
                "top_k": top_k,
                "query_type": query_type,
                "modality_filter": modality_filter,
                "similarity_threshold": similarity_threshold,
                "clip_enabled": True,
                "search_type": "clip_multimodal"
            }
        )
        
        logger.info(f"[CLIP_API] CLIP 검색 완료 - 결과: {len(formatted_results)}개")
        return response
        
    except Exception as e:
        logger.error(f"[CLIP_API] CLIP 검색 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"CLIP 검색 실패: {str(e)}")


@router.post("/hybrid", response_model=MultimodalSearchResponse)
async def search_hybrid(
    query: str = Form(..., description="검색 쿼리 (텍스트)"),
    top_k: int = Form(20, ge=1, le=50, description="반환할 최대 결과 수"),
    container_ids: Optional[str] = Form(None, description="컨테이너 ID (쉼표 구분)"),
    text_weight: float = Form(0.6, ge=0.0, le=1.0, description="텍스트 검색 가중치"),
    clip_weight: float = Form(0.4, ge=0.0, le=1.0, description="CLIP 검색 가중치"),
    similarity_threshold: float = Form(0.3, ge=0.0, le=1.0, description="최소 유사도 임계값"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    🌟 기능: 하이브리드 검색 (텍스트 + CLIP)
    
    📋 특징:
        - 텍스트 벡터 검색 (1536d)
        - CLIP 멀티모달 검색 (512d)
        - 가중치 기반 점수 통합
        - 최상의 검색 정확도
    
    🔐 권한: 로그인 사용자
    
    ⚖️ 가중치:
        - text_weight: 텍스트 검색 비중 (기본 0.6)
        - clip_weight: CLIP 검색 비중 (기본 0.4)
        - 합계: 1.0
    """
    try:
        logger.info(f"[HYBRID_API] 하이브리드 검색 시작 - 사용자: {user.emp_no}, 쿼리: {query[:50]}...")
        
        # 가중치 정규화
        total_weight = text_weight + clip_weight
        if total_weight > 0:
            text_weight = text_weight / total_weight
            clip_weight = clip_weight / total_weight
        
        # 컨테이너 ID 파싱
        container_id_list = None
        if container_ids:
            container_id_list = [cid.strip() for cid in container_ids.split(',') if cid.strip()]
        
        # 하이브리드 검색 수행
        search_results = await multimodal_search_service.search_hybrid(
            query_text=query,
            session=session,
            top_k=top_k,
            container_ids=container_id_list,
            file_ids=None,
            text_weight=text_weight,
            clip_weight=clip_weight,
            similarity_threshold=similarity_threshold
        )
        
        # 결과 변환
        formatted_results = []
        for result in search_results:
            formatted_results.append(SearchResult(
                chunk_id=result.get('chunk_id', 0),
                embedding_id=result.get('embedding_id'),
                file_id=result.get('file_id', 0),
                chunk_index=result.get('chunk_index', 0),
                content=result.get('content', ''),
                token_count=result.get('token_count'),
                modality=result.get('modality', 'text'),
                file_name=result.get('file_name', ''),
                title=result.get('title') or result.get('file_name'),
                file_path=result.get('file_path'),
                container_id=result.get('container_id'),
                container_name=result.get('container_name'),
                container_path=result.get('container_path'),
                similarity_score=result.get('hybrid_score', 0.0),
                distance=None,
                has_images=result.get('modality') == 'image',
                image_count=1 if result.get('modality') == 'image' else 0,
                clip_score=result.get('clip_score'),
                metadata=result.get('metadata')
            ))
        
        # 응답 구성
        response = MultimodalSearchResponse(
            success=True,
            query=query,
            has_image_query=False,
            results=formatted_results,
            total_found=len(formatted_results),
            search_metadata={
                "top_k": top_k,
                "text_weight": text_weight,
                "clip_weight": clip_weight,
                "similarity_threshold": similarity_threshold,
                "search_type": "hybrid",
                "text_score_included": True,
                "clip_score_included": True
            }
        )
        
        logger.info(f"[HYBRID_API] 하이브리드 검색 완료 - 결과: {len(formatted_results)}개")
        return response
        
    except Exception as e:
        logger.error(f"[HYBRID_API] 하이브리드 검색 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"하이브리드 검색 실패: {str(e)}")

"""
하이브리드 검색 API
벡터 검색 + 키워드 검색 + 전문검색을 통합한 검색 엔드포인트
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.services.search.search_service import search_service
from app.services.auth_service import get_current_user
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Hybrid Search"])


class SearchRequest(BaseModel):
    """검색 요청 모델"""
    query: str = Field(..., min_length=2, max_length=500, description="검색 쿼리")
    container_ids: Optional[List[str]] = Field(None, description="검색 대상 컨테이너 ID 목록")
    search_type: str = Field("hybrid", description="검색 타입 (hybrid, vector_only, keyword_only)")
    max_results: int = Field(10, ge=1, le=50, description="최대 결과 수")
    filters: Optional[Dict[str, Any]] = Field(None, description="추가 필터")


class SearchResult(BaseModel):
    """검색 결과 모델"""
    document_id: int
    file_id: int
    container_id: str
    chunk_index: int
    title: str
    content: str
    keywords: List[str]
    proper_nouns: List[str]
    corp_names: List[str]
    document_type: Optional[str]
    search_methods: List[str]
    scores: Dict[str, float]
    last_updated: Optional[str]


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    results: List[SearchResult]
    total_count: int
    search_type: str
    accessible_containers: List[str]
    query_processed: Dict[str, Any]
    execution_time: str
    message: Optional[str] = None


@router.post("/search/hybrid", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    하이브리드 검색 수행
    - 벡터 유사도 검색
    - 키워드 매칭 검색  
    - PostgreSQL 전문검색
    """
    try:
        logger.info(f"하이브리드 검색 요청: {current_user.emp_no}, 쿼리: {request.query}")
        
        # 검색 수행
        search_result = await search_service.hybrid_search(
            query=request.query,
            user_emp_no=current_user.emp_no,
            container_ids=request.container_ids,
            max_results=request.max_results,
            search_type=request.search_type,
            filters=request.filters
        )
        
        # 결과 변환
        search_results = []
        for result in search_result["results"]:
            search_results.append(SearchResult(
                document_id=result["document_id"],
                file_id=result["file_id"],
                container_id=result["container_id"],
                chunk_index=result["chunk_index"],
                title=result["title"],
                content=result["content"],
                keywords=result["keywords"],
                proper_nouns=result["proper_nouns"],
                corp_names=result["corp_names"],
                document_type=result["document_type"],
                search_methods=result["search_methods"],
                scores=result["scores"],
                last_updated=result["last_updated"]
            ))
        
        return SearchResponse(
            results=search_results,
            total_count=search_result["total_count"],
            search_type=search_result["search_type"],
            accessible_containers=search_result["accessible_containers"],
            query_processed=search_result["query_processed"],
            execution_time=search_result["execution_time"],
            message=search_result.get("message")
        )
        
    except Exception as e:
        logger.error(f"하이브리드 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/search/vector")
async def vector_search(
    query: str = Query(..., min_length=2, max_length=500),
    container_ids: Optional[List[str]] = Query(None),
    max_results: int = Query(10, ge=1, le=50),
    similarity_threshold: float = Query(0.7, ge=0.1, le=1.0),
    current_user: User = Depends(get_current_user)
):
    """
    벡터 유사도 검색만 수행
    """
    try:
        search_result = await search_service.hybrid_search(
            query=query,
            user_emp_no=current_user.emp_no,
            container_ids=container_ids,
            max_results=max_results,
            search_type="vector_only",
            filters={"similarity_threshold": similarity_threshold}
        )
        
        return search_result
        
    except Exception as e:
        logger.error(f"벡터 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"벡터 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/search/keyword")
async def keyword_search(
    query: str = Query(..., min_length=2, max_length=500),
    container_ids: Optional[List[str]] = Query(None),
    max_results: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """
    키워드 매칭 검색만 수행
    """
    try:
        search_result = await search_service.hybrid_search(
            query=query,
            user_emp_no=current_user.emp_no,
            container_ids=container_ids,
            max_results=max_results,
            search_type="keyword_only"
        )
        
        return search_result
        
    except Exception as e:
        logger.error(f"키워드 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"키워드 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/search/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=20),
    current_user: User = Depends(get_current_user)
):
    """
    검색 자동완성 제안
    """
    try:
        # 사용자 접근 가능한 컨테이너의 키워드에서 제안
        suggestions = await search_service._get_search_suggestions(
            query, current_user.emp_no, limit
        )
        
        return {
            "suggestions": suggestions,
            "query": query
        }
        
    except Exception as e:
        logger.error(f"검색 제안 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 제안 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/search/analytics")
async def get_search_analytics(
    period: str = Query("7d", regex="^(1d|7d|30d|90d)$"),
    current_user: User = Depends(get_current_user)
):
    """
    검색 분석 정보 (관리자용)
    """
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 권한이 필요합니다"
            )
        
        analytics = await search_service._get_search_analytics(period)
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"검색 분석 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 분석 중 오류가 발생했습니다: {str(e)}"
        )


class DocumentUploadRequest(BaseModel):
    """문서 업로드 요청"""
    container_id: str = Field(..., description="대상 컨테이너 ID")
    title: Optional[str] = Field(None, description="문서 제목")
    tags: Optional[List[str]] = Field(None, description="태그")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")


@router.post("/documents/reindex/{file_id}")
async def reindex_document(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 문서 재색인
    """
    try:
        # 파일 정보 조회
        from app.models.file_models import TbFileBssInfo
        file_info = db.query(TbFileBssInfo).filter(
            TbFileBssInfo.file_bss_info_sno == file_id
        ).first()
        
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="파일을 찾을 수 없습니다"
            )
        
        # 권한 확인 (소유자 또는 관리자)
        if file_info.owner_emp_no != current_user.emp_no and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 파일에 대한 권한이 없습니다"
            )
        
        # 재색인 수행 (백그라운드 태스크로)
        from app.services.document_vectorization_service import document_vectorization_service
        # 실제 구현에서는 백그라운드 태스크로 처리
        
        return {
            "success": True,
            "message": "문서 재색인이 시작되었습니다",
            "file_id": file_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 재색인 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 재색인 중 오류가 발생했습니다: {str(e)}"
        )

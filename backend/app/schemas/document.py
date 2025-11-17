"""
문서 관련 Pydantic 스키마
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답 스키마 (멀티모달 지원)"""
    success: bool
    message: str
    document_id: int
    file_info: Dict[str, Any]
    processing_stats: Dict[str, Any]
    korean_analysis: Dict[str, Any]
    container_assignment: Dict[str, Any]
    
    # 멀티모달 메타데이터 (CLIP 임베딩 정보)
    multimodal_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="멀티모달 처리 결과 메타데이터 (이미지 개수, CLIP 임베딩 상태 등)"
    )

class SearchRequest(BaseModel):
    """검색 요청 스키마"""
    query: str = Field(..., min_length=1, max_length=500, description="검색 쿼리")
    container_ids: Optional[List[int]] = Field(None, description="검색할 컨테이너 ID 목록")
    limit: int = Field(10, ge=1, le=50, description="검색 결과 수 제한")
    similarity_threshold: float = Field(0.5, ge=0.0, le=1.0, description="유사도 임계값")

class SearchResult(BaseModel):
    """검색 결과 항목 스키마"""
    chunk_id: int
    document_id: int
    content: str
    chunk_index: int
    document_title: str
    file_name: str
    document_type: str
    similarity_score: float
    relevance_score: float
    final_score: float
    chunk_keywords: List[str]
    document_keywords: List[str]
    container_name: Optional[str]
    score_breakdown: Dict[str, float]

class SearchResponse(BaseModel):
    """검색 응답 스키마"""
    success: bool
    query: str
    results: List[SearchResult]
    total_found: int
    search_metadata: Dict[str, Any]
    query_analysis: Dict[str, Any]

class DocumentInfo(BaseModel):
    """문서 정보 스키마"""
    id: int
    title: str
    file_name: str
    file_size: int
    file_extension: str = ""
    document_type: str = ""
    quality_score: float = 0.0
    korean_ratio: float = 0.0
    keywords: List[str] = []
    container_path: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    uploaded_by: str = ""
    # 비동기 처리 상태 필드 추가
    processing_status: Optional[str] = "completed"  # pending, processing, completed, failed
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

class DocumentListResponse(BaseModel):
    """문서 목록 응답 스키마"""
    success: bool
    documents: List[DocumentInfo]
    total: int  # 전체 문서 수
    current_page_count: Optional[int] = None  # 현재 페이지 문서 수
    skip: int
    limit: int
    has_next: Optional[bool] = None  # 다음 페이지 존재 여부
    has_previous: Optional[bool] = None  # 이전 페이지 존재 여부
    metadata: Optional[dict] = None  # 추가 메타데이터

class DocumentResponse(BaseModel):
    """단일 문서 응답 스키마"""
    id: int
    title: str
    content: str = ""
    file_path: str
    container_path: str = ""
    file_size: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    uploaded_by: str = ""


# --- 추가: 전처리/청킹 분리용 경량 스키마 ---

class PreprocessResponse(BaseModel):
    success: bool
    extracted_text: Optional[str] = None
    cleaned_text: Optional[str] = None
    extraction_metadata: Dict[str, Any] = {}
    total_chars: int = 0
    total_tokens: int = 0

class ChunkRequest(BaseModel):
    text: str = Field(..., description="청킹할 원본 텍스트")
    container_id: Optional[str] = Field(None, description="선택: 컨테이너 ID (메타데이터용)")
    file_name: Optional[str] = Field(None, description="선택: 파일명 또는 식별자 (메타데이터용)")

class ChunkResponse(BaseModel):
    success: bool
    total_chunks: int
    total_tokens: int
    chunks: List[str]
    metadata: Optional[List[Dict[str, Any]]] = None

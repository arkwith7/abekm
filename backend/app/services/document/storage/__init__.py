"""
Document Storage Services
=========================

문서 저장 관련 서비스들

구조:
- search_index_store: 통합검색 인덱스 저장
- vector_storage_service: 벡터 저장 서비스 (통합)
- file_storage_service: 파일 저장 서비스  
- vector_embedding_service: 벡터 임베딩 서비스
"""

from .search_index_store import search_index_store_service

# 벡터 저장 서비스들
try:
    from .vector_storage_service import VectorStorageService
    from .file_storage_service import FileStorageService
    from .vector_embedding_service import VectorEmbeddingService
except ImportError as e:
    # 임포트 실패 시 로깅하고 기본 서비스만 export
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"일부 저장 서비스 임포트 실패: {e}")
    VectorStorageService = None
    FileStorageService = None
    VectorEmbeddingService = None

__all__ = [
    "search_index_store_service",
    "VectorStorageService",
    "FileStorageService",
    "VectorEmbeddingService"
]

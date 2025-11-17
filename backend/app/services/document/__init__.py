"""
Document Services Package
========================

문서 처리 관련 서비스들의 통합 패키지

구조:
- extraction/: 텍스트 추출 서비스
- processing/: 전처리 및 NLP 서비스  
- storage/: 저장 관련 서비스
- pipeline/: 통합 파이프라인 서비스
"""

# 핵심 서비스들만 안전하게 import
try:
    from .storage import search_index_store_service
except ImportError:
    search_index_store_service = None

try: 
    from .extraction import text_extractor_service, office_converter_service
except ImportError:
    text_extractor_service = None
    office_converter_service = None

try:
    from .processing import document_preprocessing_service  
except ImportError:
    document_preprocessing_service = None

# 기존 서비스들
from .document_service import document_service

__all__ = [
    # Storage services (핵심)
    "search_index_store_service",
    
    # Extraction services
    "text_extractor_service",
    "office_converter_service",
    
    # Processing services  
    "document_preprocessing_service",
    
    # Document services
    "document_service"
]

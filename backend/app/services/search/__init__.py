"""
🔍 검색 서비스 모듈
==================

검색 관련 서비스들을 포함하는 모듈입니다.

통합 질의 처리 파이프라인:
- query_pipeline.process_user_query(): 일반 검색 + RAG 검색 공통 사용
- query_config.UNIFIED_STOPWORDS: 통합 불용어 리스트
- query_models.ProcessedQuery: 처리된 질의 모델
"""

from .search_service import search_service
from .multimodal_search_service import multimodal_search_service
from .query_pipeline import process_user_query
from .query_config import UNIFIED_STOPWORDS, INTENT_SEARCH_STRATEGIES, RAG_SEARCH_STRATEGIES
from .query_models import ProcessedQuery, IntentType

__all__ = [
    "search_service",
    "multimodal_search_service",
    "process_user_query",
    "UNIFIED_STOPWORDS",
    "INTENT_SEARCH_STRATEGIES",
    "RAG_SEARCH_STRATEGIES",
    "ProcessedQuery",
    "IntentType"
]

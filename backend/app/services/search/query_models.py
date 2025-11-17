"""
질의 처리 데이터 모델
검색 파이프라인의 모든 데이터 구조
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class IntentType(str, Enum):
    """의도 타입"""
    KEYWORD_SEARCH = "keyword_search"
    DOCUMENT_SEARCH = "document_search"
    QA_QUESTION = "qa_question"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"
    PRESENTATION = "presentation"
    UNKNOWN = "unknown"


@dataclass
class ProcessedQuery:
    """
    처리된 질의 (통합 모델)
    일반 검색과 RAG 검색 모두 사용
    """
    # 원본
    original_text: str
    
    # 정규화
    normalized_text: str
    language: str  # "ko", "en", "mixed"
    
    # 의도 분류
    intent: str  # IntentType 값
    intent_confidence: float
    
    # 키워드
    keywords: List[str]
    filtered_keywords: List[str]  # 불용어 제거 후
    
    # 검색 쿼리
    fulltext_query: str  # tsquery용
    keyword_query: str   # ILIKE용
    vector_embedding: Optional[List[float]] = None
    spell_corrections: Dict[str, str] = field(default_factory=dict)
    
    # 검색 전략
    weights: Dict[str, float] = field(default_factory=dict)
    similarity_threshold: float = 0.4
    max_results: int = 15
    
    # 메타 정보
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "language": self.language,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "keywords": self.keywords,
            "filtered_keywords": self.filtered_keywords,
            "fulltext_query": self.fulltext_query,
            "weights": self.weights,
            "similarity_threshold": self.similarity_threshold,
            "processing_time_ms": self.processing_time_ms,
            "spell_corrections": self.spell_corrections
        }

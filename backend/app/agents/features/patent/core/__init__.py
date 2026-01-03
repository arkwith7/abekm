"""
Patent Core - 특허 공통 인프라

공통 모델, 인터페이스, 유틸리티 제공
"""

from .models import (
    # Enums
    PatentJurisdiction,
    PatentStatus,
    PatentDocumentType,
    # Core Models
    PatentData,
    PatentCitation,
    LegalStatus,
    # Search Models
    PatentSearchQuery,
    SearchResult,
    AggregatedSearchResult,
    # Analysis Models
    TechnologyTopic,
    CompetitorMetrics,
    PriorArtCandidate,
    PriorArtSearchResult,
)

from .interfaces import (
    BasePatentClient,
    PatentAnalyzer,
    PriorArtSearcher,
)

from .utils import (
    # IPC 유틸리티
    parse_ipc_code,
    get_ipc_section_name,
    extract_main_ipc,
    group_by_ipc_section,
    # 날짜 유틸리티
    parse_patent_date,
    format_date,
    get_date_range_years,
    # 특허번호 유틸리티
    normalize_patent_number,
    extract_jurisdiction,
    parse_korean_patent_number,
    # 텍스트 유틸리티
    clean_text,
    extract_keywords,
    truncate_text,
)

__all__ = [
    # Enums
    "PatentJurisdiction",
    "PatentStatus",
    "PatentDocumentType",
    # Core Models
    "PatentData",
    "PatentCitation",
    "LegalStatus",
    # Search Models
    "PatentSearchQuery",
    "SearchResult",
    "AggregatedSearchResult",
    # Analysis Models
    "TechnologyTopic",
    "CompetitorMetrics",
    "PriorArtCandidate",
    "PriorArtSearchResult",
    # Interfaces
    "BasePatentClient",
    "PatentAnalyzer",
    "PriorArtSearcher",
    # Utilities
    "parse_ipc_code",
    "get_ipc_section_name",
    "extract_main_ipc",
    "group_by_ipc_section",
    "parse_patent_date",
    "format_date",
    "get_date_range_years",
    "normalize_patent_number",
    "extract_jurisdiction",
    "parse_korean_patent_number",
    "clean_text",
    "extract_keywords",
    "truncate_text",
]

"""
Patent Clients - 특허 데이터 소스 클라이언트

다양한 특허 데이터베이스에 접근하기 위한 클라이언트 모듈.
BasePatentClient 인터페이스를 구현하여 통합 사용 가능.
"""

from .base_client import BasePatentClient
from .kipris_client import KiprisPatentClient, create_kipris_client
from .google_patents_client import GooglePatentsClient, get_google_patents_client
from .aggregator import PatentSourceAggregator, get_patent_aggregator

__all__ = [
    # Base
    "BasePatentClient",
    # KIPRIS
    "KiprisPatentClient",
    "create_kipris_client",
    # Google Patents
    "GooglePatentsClient",
    "get_google_patents_client",
    # Aggregator
    "PatentSourceAggregator",
    "get_patent_aggregator",
]

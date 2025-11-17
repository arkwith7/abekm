"""
Document Extraction Services
===========================

텍스트 추출 관련 서비스들

구조:
- text_extractor_service: 다양한 파일 포맷의 텍스트 추출
- office_converter_service: 오피스 문서 변환 및 처리
"""

from .text_extractor_service import TextExtractorService
from .office_converter_service import OfficeConverterService

# 서비스 인스턴스 생성
text_extractor_service = TextExtractorService()
office_converter_service = OfficeConverterService()

__all__ = [
    "TextExtractorService",
    "OfficeConverterService", 
    "text_extractor_service",
    "office_converter_service"
]

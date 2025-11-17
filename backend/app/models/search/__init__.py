"""
WKMS 검색 및 분석 모델 패키지
"""
from .analytics_models import (
    TbKnowledgeAccessLog,
    TbKnowledgeSharingLog,
    TbSearchAnalytics
)

__all__ = [
    # 분석 및 로그 모델
    "TbKnowledgeAccessLog",
    "TbKnowledgeSharingLog", 
    "TbSearchAnalytics",
]

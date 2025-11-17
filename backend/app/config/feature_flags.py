"""Feature Flags Configuration

간단한 환경변수 기반 Feature Flag Helper.
필요시 LaunchDarkly 등 외부 서비스로 대체 가능.
"""
from __future__ import annotations
import os
from functools import lru_cache

class FeatureFlags:
    AZURE_PIPELINE_ENABLED: bool
    AZURE_BLOB_ENABLED: bool
    AZURE_DOCINT_ENABLED: bool
    AZURE_OPENAI_EMBEDDING_ENABLED: bool
    KOR_SEARCH_ENABLED: bool
    MULTIMODAL_PIPELINE_ENABLED: bool

    def __init__(self) -> None:
        self.AZURE_PIPELINE_ENABLED = os.getenv('AZURE_PIPELINE_ENABLED', '0') == '1'
        self.AZURE_BLOB_ENABLED = os.getenv('AZURE_BLOB_ENABLED', '0') == '1'
        self.AZURE_DOCINT_ENABLED = os.getenv('AZURE_DOCINT_ENABLED', '0') == '1'
        self.AZURE_OPENAI_EMBEDDING_ENABLED = os.getenv('AZURE_OPENAI_EMBEDDING_ENABLED', '0') == '1'
        self.KOR_SEARCH_ENABLED = os.getenv('KOR_SEARCH_ENABLED', '0') == '1'
        self.MULTIMODAL_PIPELINE_ENABLED = os.getenv('MULTIMODAL_PIPELINE_ENABLED', '0') == '1'

@lru_cache(maxsize=1)
def get_feature_flags() -> FeatureFlags:
    return FeatureFlags()

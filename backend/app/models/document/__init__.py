"""
WKMS 문서 관리 모델 패키지
"""
from .file_models import TbFileBssInfo, TbFileDtlInfo
from .vector_models import VsDocContentsChunks
from .unified_search_models import TbDocumentSearchIndex  # 통합검색 모델 활성화

__all__ = [
    # 파일 관리 모델
    "TbFileBssInfo",
    "TbFileDtlInfo",
    # 벡터 청킹 모델
    "VsDocContentsChunks",
    # 통합검색 모델 (vs_doc_contents_index 대체)
    "TbDocumentSearchIndex",  # 활성화
]

"""Search Service V2 (초안 시그니처)

목표: 파일 레벨 / 청크 레벨 / 멀티모달 컨텍스트 검색 분리.
구현은 단계적으로 진행하며 현재는 뼈대만 포함.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SearchServiceV2:
    async def file_level_search(
        self,
        query: str,
        user_emp_no: str,
        limit: int = 10,
        container_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """파일 메타 중심 검색 (kor_search + 요약 기반)
        TODO: kor_search 활성화시 전용 함수 사용
        """
        logger.info(f"[SearchV2] file_level_search query='{query}' user={user_emp_no}")
        return {
            "results": [],
            "total": 0,
            "query": query,
            "mode": "file_level"
        }

    async def chunk_level_search(
        self,
        query: str,
        user_emp_no: str,
        limit: int = 20,
        modality: str = 'text',
        container_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """청크 단위 상세 검색 (텍스트/표/이미지 선택)
        TODO: doc_chunk + doc_embedding 조인
        """
        logger.info(f"[SearchV2] chunk_level_search query='{query}' modality={modality}")
        return {
            "results": [],
            "total": 0,
            "query": query,
            "modality": modality,
            "mode": "chunk_level"
        }

    async def multimodal_context(
        self,
        query: str,
        user_emp_no: str,
        k_text: int = 8,
        k_table: int = 3,
        k_image: int = 2,
        container_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """RAG 멀티모달 컨텍스트 묶음 검색.
        1) 텍스트 top-k
        2) 표 top-k
        3) 이미지(캡션) top-k
        TODO: 재랭킹 / 중복 제거
        """
        logger.info(f"[SearchV2] multimodal_context query='{query}' user={user_emp_no}")
        return {
            "text": [],
            "tables": [],
            "images": [],
            "query": query,
            "mode": "multimodal_context"
        }

search_service_v2 = SearchServiceV2()

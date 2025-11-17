"""멀티모달 검색 서비스 (Phase 2)

CLIP 기반 이미지/텍스트 검색을 SearchService와 연계하여 제공한다.
- 이미지 → 이미지 임베딩 생성 후 doc_embedding.clip_vector 유사도 검색
- 텍스트 → CLIP 텍스트 임베딩 생성 후 이미지/비주얼 청크 검색
- 사전 계산된 CLIP 벡터 입력을 통한 직접 검색
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.search.search_service import search_service

try:
    from app.services.document.vision.image_embedding_service import image_embedding_service
except ImportError:  # pragma: no cover - 선택 구성 요소 미설치 대비
    image_embedding_service = None

logger = logging.getLogger(__name__)


class MultimodalSearchService:
    """멀티모달 검색을 위한 헬퍼 서비스."""

    def __init__(self, default_top_k: int = 10, default_threshold: float = 0.25):
        self.default_top_k = default_top_k
        self.default_threshold = default_threshold

        if not image_embedding_service:
            logger.warning("⚠️ image_embedding_service가 초기화되지 않았습니다. CLIP 검색이 비활성화됩니다.")

    async def search_by_image(
        self,
        *,
        user_emp_no: str,
        image_bytes: Optional[bytes] = None,
        image_base64: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """이미지 데이터를 활용해 CLIP 이미지 검색을 수행한다."""
        if not image_embedding_service:
            return {
                "results": [],
                "query_embedding": None,
                "message": "CLIP 임베딩 서비스가 활성화되어 있지 않습니다.",
                "success": False,
            }

        if not image_bytes and image_base64:
            try:
                image_bytes = base64.b64decode(image_base64)
            except Exception as exc:  # pragma: no cover - 잘못된 입력 방어
                logger.error(f"잘못된 base64 이미지 입력: {exc}")
                return {
                    "results": [],
                    "query_embedding": None,
                    "message": "base64 이미지 디코딩에 실패했습니다.",
                    "success": False,
                }

        if not image_bytes:
            return {
                "results": [],
                "query_embedding": None,
                "message": "이미지 데이터가 필요합니다.",
                "success": False,
            }

        # 1) 이미지 임베딩 생성
        embedding = await image_embedding_service.generate_image_embedding(image_bytes=image_bytes)
        if not embedding:
            return {
                "results": [],
                "query_embedding": None,
                "message": "이미지 임베딩 생성에 실패했습니다.",
                "success": False,
            }

        # 2) 검색 실행
        results = await search_service.search_by_image_embedding(
            image_embedding=list(map(float, embedding)),
            user_emp_no=user_emp_no,
            container_ids=container_ids,
            max_results=top_k or self.default_top_k,
            similarity_threshold=similarity_threshold if similarity_threshold is not None else self.default_threshold,
        )

        return {
            "results": results,
            "query_embedding": embedding,
            "success": True,
            "similarity_threshold": similarity_threshold if similarity_threshold is not None else self.default_threshold,
            "top_k": top_k or self.default_top_k,
        }

    async def search_by_clip_vector(
        self,
        *,
        user_emp_no: str,
        clip_vector: List[float],
        container_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """사전 계산된 CLIP 벡터로 직접 검색."""
        results = await search_service.search_by_image_embedding(
            image_embedding=list(map(float, clip_vector)),
            user_emp_no=user_emp_no,
            container_ids=container_ids,
            max_results=top_k or self.default_top_k,
            similarity_threshold=similarity_threshold if similarity_threshold is not None else self.default_threshold,
        )

        return {
            "results": results,
            "query_embedding": clip_vector,
            "success": True,
            "similarity_threshold": similarity_threshold if similarity_threshold is not None else self.default_threshold,
            "top_k": top_k or self.default_top_k,
        }

    async def search_by_text_prompt(
        self,
        *,
        user_emp_no: str,
        text: str,
        container_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """텍스트 쿼리를 CLIP 텍스트 임베딩으로 변환해 이미지/비주얼 청크를 검색."""
        if not image_embedding_service:
            return {
                "results": [],
                "query_embedding": None,
                "message": "CLIP 임베딩 서비스가 활성화되어 있지 않습니다.",
                "success": False,
            }

        clip_embedding = await image_embedding_service.generate_text_embedding(text)
        if not clip_embedding:
            return {
                "results": [],
                "query_embedding": None,
                "message": "텍스트 CLIP 임베딩 생성에 실패했습니다.",
                "success": False,
            }

        return await self.search_by_clip_vector(
            user_emp_no=user_emp_no,
            clip_vector=list(map(float, clip_embedding)),
            container_ids=container_ids,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )


multimodal_search_service = MultimodalSearchService(
    default_top_k=getattr(settings, "clip_top_k", 10),
    default_threshold=getattr(settings, "clip_similarity_threshold", 0.25),
)

"""
일반 문서 처리 파이프라인

MultimodalDocumentService를 기반으로 한 표준 파이프라인
"""
from typing import Dict, Any
import logging

from app.services.document.pipelines.base_pipeline import DocumentPipeline
from app.services.document.multimodal_document_service import MultimodalDocumentService
from app.services.document.vision.image_embedding_service import ImageEmbeddingService
from app.core.database import get_async_session_local
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeneralPipeline(DocumentPipeline):
    """일반 문서 처리 파이프라인"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.image_embedding_service = ImageEmbeddingService()
        self.multimodal_service = MultimodalDocumentService(
            image_embedding_service=self.image_embedding_service
        )
        self._session_factory = get_async_session_local()

    async def process(self) -> Dict[str, Any]:
        """MultimodalDocumentService 중심으로 멀티모달 파이프라인 실행"""
        logger.info(f"🚀 [{self.__class__.__name__}] 파이프라인 시작: {self.file_name}")

        provider = self._get_option("provider", settings.get_current_llm_provider())
        model_profile = self._get_option("model_profile", "default")

        async with self._session_factory() as session:
            try:
                result = await self.multimodal_service.process_document_multimodal(
                    file_path=self.file_path,
                    file_bss_info_sno=self.document_id,
                    container_id=self.container_id,
                    user_emp_no=self.user_emp_no,
                    session=session,
                    provider=provider,
                    model_profile=model_profile,
                    processing_options=self.processing_options,
                    document_type=self.processing_options.get("document_type"),
                )
            except Exception as exc:
                logger.error(
                    f"❌ [{self.__class__.__name__}] 파이프라인 실행 중 예외: {exc}",
                    exc_info=True,
                )
                return {"success": False, "error": str(exc), "statistics": {}}

        if not result.get("success"):
            error_msg = result.get("error", "알 수 없는 오류")
            logger.error(f"❌ [{self.__class__.__name__}] 파이프라인 실패: {error_msg}")
            return {"success": False, "error": error_msg, "statistics": {}}

        stats = result.get("stats", {}) or {}
        aggregated = {
            "total_objects_extracted": result.get("objects_count", 0),
            "total_chunks": result.get("chunks_count", 0),
            "total_embeddings": result.get("embeddings_count", 0),
            "clip_embeddings": result.get("clip_embeddings_count", 0),
            "elapsed_seconds": stats.get("elapsed_seconds"),
            "avg_chunk_tokens": stats.get("avg_chunk_tokens"),
            "vector_dimension": stats.get("vector_dimension"),
            "tables": stats.get("tables"),
            "images": stats.get("images"),
            "figures": stats.get("figures"),
            "text_chunks": stats.get("text_chunks"),
            "image_chunks": stats.get("image_chunks"),
            "table_chunks": stats.get("table_chunks"),
            "pipeline_type": self.__class__.__name__,
        }

        if result.get("section_chunking"):
            aggregated["section_chunking"] = result["section_chunking"]

        logger.info(f"✅ [{self.__class__.__name__}] 파이프라인 완료")
        logger.info(f"   📊 통계: {aggregated}")

        return {"success": True, "statistics": aggregated}

    # Template Method 패턴과의 호환성을 위해 추상 메서드를 스텁으로 유지한다.
    async def extract(self) -> Dict[str, Any]:  # pragma: no cover - 직접 호출되지 않음
        return {"success": False, "error": "Not implemented"}

    async def chunk(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        return {"success": False, "error": "Not implemented"}

    async def embed(self, chunking_result: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        return {"success": False, "error": "Not implemented"}

    async def index(self, embedding_result: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        return {"success": False, "error": "Not implemented"}

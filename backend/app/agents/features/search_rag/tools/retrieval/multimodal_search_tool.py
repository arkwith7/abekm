"""
Multimodal Search Tool
이미지 쿼리로 이미지 임베딩 기반 검색 수행
"""
from typing import Any, Dict, List, Optional
import base64
import uuid
from datetime import datetime
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger

from app.tools.contracts import SearchChunk, SearchToolResult, ToolMetrics
from app.services.document.vision.image_embedding_service import ImageEmbeddingService


class MultimodalSearchInput(BaseModel):
    """멀티모달 검색 도구 입력"""
    image_data: str = Field(description="검색할 이미지 데이터 (base64 인코딩)")
    query: str = Field(default="", description="텍스트 쿼리 (선택사항)")
    top_k: int = Field(default=10, description="반환할 결과 수")
    container_ids: List[str] = Field(default_factory=list, description="검색 대상 컨테이너 ID")


class MultimodalSearchTool(BaseTool):
    """
    멀티모달 검색 도구 - 이미지 임베딩 기반 검색
    
    사용 시점:
    - 사용자가 이미지를 첨부한 경우
    - 이미지와 유사한 문서/이미지를 찾아야 하는 경우
    - "이 이미지와 비슷한 문서" 질문
    
    동작:
    1. 이미지 → CLIP 임베딩 생성
    2. 벡터 유사도 검색 (이미지 청크)
    3. 관련 문서 반환
    """
    
    name: str = "multimodal_search"
    description: str = """
    이미지를 입력받아 유사한 이미지/문서를 검색합니다.
    CLIP 임베딩을 사용하여 멀티모달 벡터 검색을 수행합니다.
    
    입력: image_data (base64), query (optional), top_k, container_ids
    출력: 이미지 유사도 기반 검색 결과
    """
    args_schema: type[BaseModel] = MultimodalSearchInput
    version: str = "1.0.0"
    
    db_session: Optional[AsyncSession] = Field(default=None, exclude=True)
    
    class Config:
        arbitrary_types_allowed = True

    def _run(self, *args, **kwargs) -> str:
        """동기 실행 (미지원)"""
        raise NotImplementedError("멀티모달 검색은 비동기로만 실행 가능합니다.")

    async def _arun(
        self,
        image_data: str,
        query: str = "",
        top_k: int = 10,
        container_ids: Optional[List[str]] = None,
        db_session: Optional[AsyncSession] = None,
        **kwargs
    ) -> SearchToolResult:
        """
        멀티모달 검색 실행
        
        Args:
            image_data: Base64 인코딩된 이미지 데이터
            query: 텍스트 쿼리 (선택)
            top_k: 반환할 결과 수
            container_ids: 검색 대상 컨테이너
            db_session: DB 세션
            
        Returns:
            ToolResult: 검색 결과 (SearchChunk 리스트)
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        normalized_containers = [str(cid) for cid in (container_ids or [])]
        db = db_session or self.db_session

        if not db:
            logger.error("❌ [MultimodalSearch] DB 세션 누락")
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={},
                metrics=ToolMetrics(latency_ms=0, provider="internal", trace_id=trace_id),
                errors=["DB 세션이 제공되지 않았습니다."],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

        if not image_data:
            logger.warning("📷 [MultimodalSearch] 이미지 데이터 없음")
            return SearchToolResult(
                success=True,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={"reason": "no_image"},
                metrics=ToolMetrics(latency_ms=0, provider="internal", trace_id=trace_id),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

        try:
            logger.info(
                f"📷 [MultimodalSearch] 시작: top_k={top_k}, containers={len(normalized_containers)}"
            )

            if image_data.startswith('data:image'):
                image_data = image_data.split(',', 1)[1]
            image_bytes = base64.b64decode(image_data)

            embedding_service = ImageEmbeddingService()
            clip_embedding = await embedding_service.generate_image_embedding(image_bytes=image_bytes)

            if not clip_embedding:
                logger.warning("📷 [MultimodalSearch] CLIP 임베딩 생성 실패")
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                return SearchToolResult(
                    success=True,
                    data=[],
                    total_found=0,
                    filtered_count=0,
                    search_params={"reason": "embedding_failed"},
                    metrics=ToolMetrics(latency_ms=latency_ms, provider="bedrock", trace_id=trace_id),
                    errors=[],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )

            clip_dim = 512
            if len(clip_embedding) < clip_dim:
                clip_embedding = clip_embedding + [0.0] * (clip_dim - len(clip_embedding))
            elif len(clip_embedding) > clip_dim:
                clip_embedding = clip_embedding[:clip_dim]

            vector_literal = "[" + ",".join(map(str, clip_embedding)) + "]"

            from app.core.config import settings
            provider = settings.get_current_embedding_provider()

            if provider == 'bedrock':
                vector_column = "de.aws_marengo_vector_512"
                vector_not_null = f"{vector_column} IS NOT NULL"
            else:
                vector_column = "COALESCE(de.azure_clip_vector, de.clip_vector)"
                vector_not_null = "(de.azure_clip_vector IS NOT NULL OR de.clip_vector IS NOT NULL)"

            sql_parts = [
                f"""
                SELECT 
                    dc.chunk_id,
                    dc.file_bss_info_sno as file_id,
                    dc.chunk_index,
                    dc.content_text,
                    dc.modality,
                    dc.blob_key,
                    fbi.file_lgc_nm as file_name,
                    fbi.knowledge_container_id as container_id,
                    1 - ({vector_column} <=> CAST(:vector_literal AS vector)) as similarity
                FROM doc_chunk dc
                JOIN doc_embedding de ON dc.chunk_id = de.chunk_id
                LEFT JOIN tb_file_bss_info fbi ON dc.file_bss_info_sno = fbi.file_bss_info_sno
                WHERE {vector_not_null}
                  AND COALESCE(de.modality, dc.modality) = 'image'
                  AND fbi.del_yn = 'N'
                """
            ]

            params: Dict[str, Any] = {
                "vector_literal": vector_literal,
                "top_k": top_k
            }

            if normalized_containers:
                sql_parts.append("AND fbi.knowledge_container_id = ANY(:container_ids)")
                params["container_ids"] = normalized_containers

            sql_parts.append("ORDER BY similarity DESC LIMIT :top_k")
            query_sql = text(" ".join(sql_parts))

            result = await db.execute(query_sql, params)
            rows = result.fetchall()

            if not rows:
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info("📷 [MultimodalSearch] 결과 없음")
                return SearchToolResult(
                    success=True,
                    data=[],
                    total_found=0,
                    filtered_count=0,
                    search_params={
                        "top_k": top_k,
                        "container_ids": normalized_containers,
                        "has_text_query": bool(query)
                    },
                    metrics=ToolMetrics(latency_ms=latency_ms, provider="internal", trace_id=trace_id),
                    errors=[],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )

            chunks = []
            for row in rows:
                chunk = SearchChunk(
                    chunk_id=str(row.chunk_id),
                    file_id=str(row.file_id),
                    content=row.content_text or "[이미지 캡션이 비어 있습니다]",
                    score=float(row.similarity),
                    match_type="multimodal",
                    metadata={
                        'file_name': row.file_name,
                        'container_id': row.container_id,
                        'blob_key': row.blob_key,
                        'chunk_index': row.chunk_index,
                        'modality': row.modality,
                        'search_type': 'multimodal'
                    }
                )
                chunks.append(chunk)

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✅ [MultimodalSearch] 완료: {len(chunks)}개 발견")

            return SearchToolResult(
                success=True,
                data=chunks,
                total_found=len(chunks),
                filtered_count=len(chunks),
                search_params={
                    "top_k": top_k,
                    "container_ids": normalized_containers,
                    "has_text_query": bool(query)
                },
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    items_returned=len(chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )

        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = f"멀티모달 검색 실패: {str(e)}"
            logger.error(f"❌ [MultimodalSearch] {error_msg}", exc_info=True)
            if db:
                try:
                    await db.rollback()
                except Exception as rollback_error:
                    logger.error(f"⚠️ [MultimodalSearch] 롤백 실패: {rollback_error}")
            return SearchToolResult(
                success=False,
                data=[],
                total_found=0,
                filtered_count=0,
                search_params={
                    "top_k": top_k,
                    "container_ids": normalized_containers
                },
                metrics=ToolMetrics(latency_ms=latency_ms, provider="internal", trace_id=trace_id),
                errors=[error_msg],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )


# 싱글톤 인스턴스
_multimodal_search_tool_instance: Optional[MultimodalSearchTool] = None


def get_multimodal_search_tool() -> MultimodalSearchTool:
    """멀티모달 검색 도구 싱글톤 인스턴스 반환"""
    global _multimodal_search_tool_instance
    if _multimodal_search_tool_instance is None:
        _multimodal_search_tool_instance = MultimodalSearchTool()
    return _multimodal_search_tool_instance


# 전역 인스턴스
multimodal_search_tool = get_multimodal_search_tool()

"""
Document Summarizer Tool - 문서 요약 통합 도구
두 가지 입력 경로를 모두 지원:
1. DB 저장 문서 (Vector Store) - 청크 조회 후 요약
2. 첨부 파일 (Upload) - 텍스트 추출 후 요약
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import os

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.tools.contracts import ToolResult, ToolMetrics, SearchChunk
from app.tools.document.document_loader_tool import document_loader_tool
from app.tools.retrieval.vector_search_tool import vector_search_tool
from app.tools.retrieval.keyword_search_tool import keyword_search_tool
from app.tools.processing.deduplicate_tool import deduplicate_tool
from app.tools.processing.rerank_tool import rerank_tool
from app.tools.context.context_builder_tool import context_builder_tool


class DocumentSummarizerTool(BaseTool):
    """
    문서 요약 통합 도구
    
    책임:
    - 두 가지 입력 경로 처리:
      1) DB 문서: file_id/document_id → 청크 로드 → 요약
      2) 첨부 파일: file_path → 텍스트 추출 → 요약
    - 통일된 요약 결과 반환
    
    사용 케이스:
    - "선택한 논문 요약해줘" (DB 문서)
    - "첨부 파일 요약해줘" (업로드 파일)
    - "이 문서들의 주요 내용 정리해줘"
    
    의존성:
    - DocumentLoaderTool: DB 문서 로드
    - Azure Document Intelligence: 새 파일 텍스트 추출
    - LLM Service: 요약 생성
    """
    name: str = "document_summarizer"
    description: str = """문서를 요약합니다. 
DB에 저장된 문서와 새로 첨부된 파일 모두 처리 가능합니다."""
    version: str = "2.0.0"
    
    async def _arun(
        self,
        # Input 1: DB 문서
        document_ids: Optional[List[int]] = None,
        # Input 2: 첨부 파일
        attachment_paths: Optional[List[str]] = None,
        attachment_metadata: Optional[List[Dict[str, Any]]] = None,
        # 공통 파라미터
        db_session: Optional[AsyncSession] = None,
        max_chunks: int = 50,
        summarization_type: str = "comprehensive",  # comprehensive | brief | bullet_points
        user_emp_no: Optional[str] = None,
        request_type: Optional[str] = None,
        query_text: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        search_document_ids: Optional[List[int]] = None,
        context_max_tokens: int = 4000,
        **kwargs
    ) -> ToolResult:
        """
        문서 요약 실행
        
        Args:
            document_ids: DB 문서 ID 리스트 (Input 1)
            attachment_paths: 첨부 파일 경로 리스트 (Input 2)
            attachment_metadata: 첨부 파일 메타데이터
            db_session: DB 세션 (Input 1 필수)
            max_chunks: 최대 청크 수
            summarization_type: 요약 유형
            user_emp_no: 사용자 사번
            request_type: 요청 유형 힌트 (chat_prompt | selected_documents | uploaded_files)
            query_text: 채팅 입력 기반 요약 시 사용할 텍스트
            container_ids: 검색 범위를 제한할 컨테이너 ID 목록
            search_document_ids: 검색 시 우선 고려할 문서 ID 목록
            context_max_tokens: 컨텍스트 빌더 토큰 상한
        
        Returns:
            ToolResult: 통합 요약 결과
        """
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())

        try:
            normalized_query_text = query_text.strip() if isinstance(query_text, str) else None
            query_text = normalized_query_text if normalized_query_text else None

            # 입력 검증
            if not document_ids and not attachment_paths and not query_text:
                return ToolResult(
                    success=False,
                    data={"summary": "", "source_count": 0},
                    metrics=ToolMetrics(latency_ms=0, provider="internal", trace_id=trace_id),
                    errors=["문서 ID, 첨부 파일, 또는 요약 대상 텍스트가 제공되지 않음"],
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            resolved_request_type = self._resolve_request_type(
                explicit=request_type,
                document_ids=document_ids,
                attachment_paths=attachment_paths,
                query_text=query_text
            )

            logger.info(
                f"🧭 [Summarizer] 요청 유형={resolved_request_type}, "
                f"documents={len(document_ids or [])}, attachments={len(attachment_paths or [])}, "
                f"query_present={bool(query_text)}"
            )

            all_chunks = []
            source_info = {
                "db_documents": 0,
                "uploaded_files": 0,
                "total_chunks": 0,
                "extraction_errors": [],
                "request_type": resolved_request_type
            }
            
            # ===== Input 1: DB 문서 처리 =====
            if resolved_request_type in {"selected_documents", "auto"} and document_ids and db_session:
                logger.info(f"📚 [Summarizer] DB 문서 로드: {len(document_ids)}개")
                
                try:
                    # DocumentLoaderTool 사용
                    loader_result = await document_loader_tool._arun(
                        document_ids=document_ids,
                        db_session=db_session,
                        max_chunks=max_chunks,
                        user_emp_no=user_emp_no
                    )
                    
                    if loader_result.success and loader_result.data:
                        all_chunks.extend(loader_result.data)
                        source_info["db_documents"] = len(set(c.file_id for c in loader_result.data))
                        logger.info(f"✅ [Summarizer] DB 문서 로드 완료: {len(loader_result.data)}개 청크")
                    else:
                        error_msg = f"DB 문서 로드 실패: {loader_result.errors}"
                        logger.warning(f"⚠️ [Summarizer] {error_msg}")
                        source_info["extraction_errors"].append(error_msg)
                        
                except Exception as e:
                    error_msg = f"DB 문서 처리 중 오류: {str(e)}"
                    logger.error(f"❌ [Summarizer] {error_msg}")
                    source_info["extraction_errors"].append(error_msg)
            
            # ===== Input 2: 첨부 파일 처리 =====
            if attachment_paths and resolved_request_type in {"uploaded_files", "auto", "selected_documents"}:
                logger.info(f"📎 [Summarizer] 첨부 파일 처리: {len(attachment_paths)}개")
                
                for idx, file_path in enumerate(attachment_paths):
                    try:
                        metadata = attachment_metadata[idx] if attachment_metadata and idx < len(attachment_metadata) else {}
                        
                        # 파일 존재 확인
                        if not os.path.exists(file_path):
                            error_msg = f"파일 없음: {file_path}"
                            logger.warning(f"⚠️ [Summarizer] {error_msg}")
                            source_info["extraction_errors"].append(error_msg)
                            continue
                        
                        # 텍스트 추출
                        extracted_text = await self._extract_text_from_file(
                            file_path=file_path,
                            mime_type=metadata.get("mime_type", "application/pdf")
                        )
                        
                        if extracted_text:
                            # SearchChunk 형식으로 변환
                            from app.tools.contracts import SearchChunk
                            
                            chunk = SearchChunk(
                                chunk_id=f"upload_{idx}_{uuid.uuid4().hex[:8]}",
                                file_id=f"upload_{idx}",
                                content=extracted_text,
                                score=1.0,
                                match_type="file_upload",
                                metadata={
                                    "file_name": metadata.get("file_name", os.path.basename(file_path)),
                                    "file_type": metadata.get("mime_type", "unknown"),
                                    "source": "upload",
                                    "extraction_method": "azure_di"
                                }
                            )
                            all_chunks.append(chunk)
                            source_info["uploaded_files"] += 1
                            logger.info(f"✅ [Summarizer] 파일 추출 완료: {metadata.get('file_name', file_path)}")
                        else:
                            error_msg = f"텍스트 추출 실패: {file_path}"
                            logger.warning(f"⚠️ [Summarizer] {error_msg}")
                            source_info["extraction_errors"].append(error_msg)
                            
                    except Exception as e:
                        error_msg = f"파일 처리 중 오류 ({file_path}): {str(e)}"
                        logger.error(f"❌ [Summarizer] {error_msg}")
                        source_info["extraction_errors"].append(error_msg)
            
            # ===== Input 3: 채팅 질의 기반 요약 =====
            if resolved_request_type in {"chat_prompt", "auto"} and query_text:
                retrieval_chunks, retrieval_info = await self._build_chunks_from_query(
                    query_text=query_text,
                    db_session=db_session,
                    max_candidates=max_chunks * 2,
                    container_ids=container_ids,
                    document_filter=search_document_ids,
                    user_emp_no=user_emp_no,
                    context_max_tokens=context_max_tokens
                )

                if retrieval_chunks:
                    all_chunks.extend(retrieval_chunks)
                    source_info.setdefault("retrieval_pipeline", retrieval_info)
                    logger.info(
                        f"✅ [Summarizer] 질의 기반 청크 확보: {len(retrieval_chunks)}개 (context_included={retrieval_info.get('context', {}).get('included', 0)})"
                    )
                else:
                    source_info["extraction_errors"].append("질의 기반 청크 확보 실패")
                    logger.warning("⚠️ [Summarizer] 질의 기반 청크를 확보하지 못했습니다")

            # ===== 청크 수집 완료 확인 =====
            if not all_chunks:
                error_messages = source_info["extraction_errors"] or ["문서 내용을 추출할 수 없음"]
                return ToolResult(
                    success=False,
                    data={
                        "summary": "",
                        "source_info": source_info
                    },
                    metrics=ToolMetrics(
                        latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                        provider="internal",
                        trace_id=trace_id
                    ),
                    errors=error_messages,
                    trace_id=trace_id,
                    tool_name=self.name,
                    tool_version=self.version
                )
            
            source_info["total_chunks"] = len(all_chunks)
            
            # ===== 요약 생성 =====
            logger.info(f"📝 [Summarizer] 요약 생성 시작: {len(all_chunks)}개 청크, type={summarization_type}")
            
            summary = await self._generate_summary(
                chunks=all_chunks,
                summarization_type=summarization_type
            )
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"✅ [Summarizer] 요약 완료: DB={source_info['db_documents']}, "
                f"Upload={source_info['uploaded_files']}, "
                f"latency={latency_ms:.1f}ms"
            )
            
            return ToolResult(
                success=True,
                data={
                    "summary": summary,
                    "source_info": source_info,
                    "chunks": [
                        {
                            "file_name": c.metadata.get("file_name", "Unknown"),
                            "source": c.metadata.get("source", "db"),
                            "content_preview": c.content[:200]
                        }
                        for c in all_chunks[:10]  # 최대 10개만 미리보기
                    ]
                },
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    items_returned=len(all_chunks),
                    trace_id=trace_id
                ),
                errors=source_info["extraction_errors"],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = f"문서 요약 실패: {str(e)}"
            logger.error(f"❌ [Summarizer] {error_msg}")
            
            return ToolResult(
                success=False,
                data={"summary": "", "source_info": {}},
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    provider="internal",
                    trace_id=trace_id
                ),
                errors=[error_msg],
                trace_id=trace_id,
                tool_name=self.name,
                tool_version=self.version
            )
    
    async def _extract_text_from_file(
        self,
        file_path: str,
        mime_type: str
    ) -> Optional[str]:
        """
        첨부 파일에서 텍스트 추출
        
        Azure Document Intelligence 사용
        """
        try:
            from app.services.document.azure_document_intelligence_service import azure_di_service  # type: ignore[import-error]
            
            logger.info(f"🔍 [Summarizer] 텍스트 추출 시작: {os.path.basename(file_path)}")
            
            # Azure DI로 문서 분석
            result = await azure_di_service.analyze_document(
                file_path=file_path,
                analysis_type="layout"  # 텍스트만 추출
            )
            
            if not result or "error" in result:
                logger.error(f"❌ [Summarizer] Azure DI 분석 실패: {result.get('error') if result else 'No result'}")
                return None
            
            # 페이지별 텍스트 결합
            pages = result.get("pages", [])
            if not pages:
                logger.warning(f"⚠️ [Summarizer] 페이지 없음: {file_path}")
                return None
            
            all_text = []
            for page in pages:
                page_text = page.get("text", "")
                if page_text:
                    all_text.append(f"[Page {page.get('page_number', '?')}]\n{page_text}")
            
            extracted = "\n\n".join(all_text)
            logger.info(f"✅ [Summarizer] 텍스트 추출 완료: {len(extracted)}자")
            
            return extracted
            
        except Exception as e:
            logger.error(f"❌ [Summarizer] 텍스트 추출 오류: {e}")
            return None
    
    async def _generate_summary(
        self,
        chunks: List,
        summarization_type: str
    ) -> str:
        """
        청크를 기반으로 요약 생성
        
        LLM을 사용하여 요약 (현재는 단순 결합, 향후 LLM 통합)
        """
        try:
            from app.services.ai_service import ai_service  # type: ignore[import-error]
            
            # 청크를 컨텍스트로 변환
            context_parts = []
            for chunk in chunks:
                file_name = chunk.metadata.get("file_name", "Unknown")
                page_num = chunk.metadata.get("page_number", "?")
                context_parts.append(f"[{file_name} - p.{page_num}]\n{chunk.content}")
            
            context_text = "\n\n---\n\n".join(context_parts)
            
            # 요약 타입별 프롬프트
            prompts = {
                "comprehensive": "위 문서의 전체 내용을 체계적으로 요약해주세요. 주요 섹션별로 구분하여 작성해주세요.",
                "brief": "위 문서의 핵심 내용을 3-5문장으로 간략히 요약해주세요.",
                "bullet_points": "위 문서의 주요 내용을 글머리 기호(•)를 사용하여 5-7개 항목으로 정리해주세요."
            }
            
            prompt = f"""다음 문서의 내용을 요약해주세요.

{context_text}

{prompts.get(summarization_type, prompts['comprehensive'])}"""
            
            summary = await ai_service.generate_completion(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.3
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ [Summarizer] 요약 생성 실패: {e}")
            # 폴백: 단순 텍스트 결합
            return "\n\n".join([c.content[:500] for c in chunks[:5]])
    
    def _run(self, *args, **kwargs):
        """동기 실행은 지원하지 않음"""
        raise NotImplementedError("DocumentSummarizerTool은 비동기 실행만 지원합니다. _arun()을 사용하세요.")

    def _resolve_request_type(
        self,
        explicit: Optional[str],
        document_ids: Optional[List[int]],
        attachment_paths: Optional[List[str]],
        query_text: Optional[str]
    ) -> str:
        if explicit:
            return explicit
        if attachment_paths:
            return "uploaded_files"
        if document_ids:
            return "selected_documents"
        if query_text:
            return "chat_prompt"
        return "unknown"

    async def _build_chunks_from_query(
        self,
        query_text: str,
        db_session: Optional[AsyncSession],
        max_candidates: int,
        container_ids: Optional[List[str]],
        document_filter: Optional[List[int]],
        user_emp_no: Optional[str],
        context_max_tokens: int
    ) -> tuple[List[SearchChunk], Dict[str, Any]]:
        if not db_session:
            logger.warning("⚠️ [Summarizer] DB 세션 없이 질의 기반 요약을 수행할 수 없습니다")
            return [], {"error": "db_session_required"}

        normalized_filter = [str(doc_id) for doc_id in document_filter] if document_filter else None

        retrieval_info: Dict[str, Any] = {
            "vector": {},
            "keyword": {},
            "dedupe": {},
            "rerank": {},
            "context": {}
        }

        combined_chunks: List[SearchChunk] = []

        # Vector Search
        vector_result = await vector_search_tool._arun(
            query=query_text,
            db_session=db_session,
            top_k=max_candidates,
            container_ids=container_ids,
            document_ids=normalized_filter,
            user_emp_no=user_emp_no
        )
        if vector_result.success:
            combined_chunks.extend(vector_result.data)
        else:
            retrieval_info["vector"]["errors"] = vector_result.errors
        retrieval_info["vector"].update({
            "count": len(vector_result.data),
            "latency_ms": vector_result.metrics.latency_ms
        })

        # Keyword Search (fallback/augmentation)
        keyword_result = await keyword_search_tool._arun(
            query=query_text,
            db_session=db_session,
            top_k=max_candidates,
            container_ids=container_ids,
            document_ids=normalized_filter,
            user_emp_no=user_emp_no
        )
        if keyword_result.success:
            combined_chunks.extend(keyword_result.data)
        else:
            retrieval_info["keyword"]["errors"] = keyword_result.errors
        retrieval_info["keyword"].update({
            "count": len(keyword_result.data),
            "latency_ms": keyword_result.metrics.latency_ms
        })

        if not combined_chunks:
            return [], retrieval_info

        # Deduplicate
        dedupe_result = await deduplicate_tool._arun(chunks=combined_chunks)
        deduped_chunks = dedupe_result.data if dedupe_result.success else combined_chunks
        retrieval_info["dedupe"].update({
            "input": len(combined_chunks),
            "output": len(deduped_chunks),
            "latency_ms": dedupe_result.metrics.latency_ms,
            "errors": dedupe_result.errors if not dedupe_result.success else []
        })

        # Rerank
        rerank_result = await rerank_tool._arun(
            chunks=deduped_chunks,
            query=query_text,
            top_k=min(max_candidates, max(len(deduped_chunks), 1))
        )
        reranked_chunks = rerank_result.data if rerank_result.success else deduped_chunks
        retrieval_info["rerank"].update({
            "input": len(deduped_chunks),
            "output": len(reranked_chunks),
            "latency_ms": rerank_result.metrics.latency_ms,
            "errors": rerank_result.errors if not rerank_result.success else []
        })

        # Context Builder (token pack)
        context_result = await context_builder_tool._arun(
            chunks=reranked_chunks,
            max_tokens=context_max_tokens,
            include_metadata=True,
            priority_by="hybrid"
        )
        used_chunks = context_result.used_chunks if context_result.success and context_result.used_chunks else reranked_chunks[:max_candidates]
        retrieval_info["context"].update({
            "included": len(used_chunks),
            "tokens": context_result.total_tokens if context_result.success else None,
            "latency_ms": context_result.metrics.latency_ms,
            "errors": context_result.errors if not context_result.success else []
        })

        return used_chunks, retrieval_info


# 전역 인스턴스
document_summarizer_tool = DocumentSummarizerTool()

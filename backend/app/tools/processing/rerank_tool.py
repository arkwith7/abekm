"""
Reranking Tool - 검색 결과 재순위화
Cross-encoder 모델 기반 정확도 개선
"""
import os
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from app.tools.contracts import SearchChunk, ToolResult, ToolMetrics
from langchain_core.tools import BaseTool


class RerankTool(BaseTool):
    """
    재순위화 도구
    
    기능:
    - 검색 결과를 cross-encoder 모델로 재점수화
    - 쿼리와 문서의 실제 관련도를 정밀하게 평가
    - 초기 검색(벡터/키워드)보다 정확한 순위
    
    입력: 검색 청크 리스트, 쿼리
    출력: 재순위화된 청크 리스트
    """
    
    name: str = "rerank_tool"
    description: str = "Cross-encoder로 검색 결과 재순위화"
    
    def _run(self, *args, **kwargs):
        """동기 실행 (지원하지 않음)"""
        raise NotImplementedError("Use async _arun instead")
    
    async def _arun(
        self,
        chunks: List[SearchChunk],
        query: str,
        top_k: Optional[int] = None,
        model_name: str = "bge-reranker-base"
    ) -> ToolResult:
        """
        재순위화 실행
        
        Args:
            chunks: 입력 청크 리스트
            query: 쿼리
            top_k: 반환할 상위 K개 (None이면 전체)
            model_name: 재순위화 모델 이름
        """
        start_time = datetime.utcnow()
        trace_id = f"rerank_{uuid.uuid4().hex[:8]}"
        
        try:
            if not chunks:
                logger.warning(f"[{trace_id}] 입력 청크 없음")
                return ToolResult(
                    success=True,
                    data=[],
                    metrics=ToolMetrics(
                        latency_ms=0,
                        cost_estimate=0.0,
                        items_returned=0,
                        trace_id=trace_id
                    ),
                    errors=[],
                    trace_id=trace_id,
                    tool_name="rerank_tool",
                    tool_version="1.0.0"
                )
            
            logger.info(f"[{trace_id}] 재순위화 시작: {len(chunks)}개 청크")
            
            # Cross-encoder 점수 계산
            reranked_chunks = await self._compute_cross_encoder_scores(
                chunks=chunks,
                query=query,
                model_name=model_name
            )
            
            # Top-K 선택
            if top_k:
                reranked_chunks = reranked_chunks[:top_k]
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"[{trace_id}] 재순위화 완료: {len(reranked_chunks)}개 반환, {latency_ms:.1f}ms")
            
            return ToolResult(
                success=True,
                data=reranked_chunks,
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    cost_estimate=0.0,
                    items_returned=len(reranked_chunks),
                    trace_id=trace_id
                ),
                errors=[],
                trace_id=trace_id,
                tool_name="rerank_tool",
                tool_version="1.0.0"
            )
            
        except Exception as e:
            logger.error(f"[{trace_id}] 재순위화 실패: {e}", exc_info=True)
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 실패 시 원본 반환
            return ToolResult(
                success=False,
                data=chunks,  # fallback
                metrics=ToolMetrics(
                    latency_ms=latency_ms,
                    cost_estimate=0.0,
                    items_returned=len(chunks) if chunks else 0,
                    trace_id=trace_id
                ),
                errors=[str(e)],
                trace_id=trace_id,
                tool_name="rerank_tool",
                tool_version="1.0.0"
            )
    
    async def _compute_cross_encoder_scores(
        self,
        chunks: List[SearchChunk],
        query: str,
        model_name: str
    ) -> List[SearchChunk]:
        """
        LLM 기반 리랭킹 - Provider별 동적 처리
        
        RAG_RERANKING_PROVIDER 설정에 따라:
        - azure_openai: Azure OpenAI 모델 사용
        - bedrock: AWS Bedrock 모델 사용
        """
        from app.core.config import settings
        from langchain.schema import HumanMessage
        
        try:
            provider = settings.rag_reranking_provider
            logger.info(f"🔧 리랭킹 제공자: {provider}")
            
            # Provider별 LLM 클라이언트 생성
            if provider == "azure_openai":
                from langchain_openai import AzureChatOpenAI
                
                rerank_endpoint = settings.rag_reranking_endpoint or settings.azure_openai_endpoint
                rerank_deployment = settings.rag_reranking_deployment
                rerank_api_key = settings.rag_reranking_api_key or settings.azure_openai_api_key
                rerank_api_version = settings.rag_reranking_api_version or settings.azure_openai_api_version
                
                if not rerank_deployment:
                    raise ValueError("RAG_RERANKING_DEPLOYMENT 환경변수가 설정되지 않았습니다.")
                
                logger.info(f"🔧 리랭킹 모델: {rerank_deployment}")
                logger.info(f"🔧 리랭킹 엔드포인트: {rerank_endpoint}")
                logger.info(f"🔧 리랭킹 API 버전: {rerank_api_version}")
                
                # 모델별 파라미터 설정
                deployment_lower = rerank_deployment.lower()
                is_reasoning_model = (
                    "gpt-5" in deployment_lower
                    or "nano" in deployment_lower
                    or "o1" in deployment_lower
                    or "o3" in deployment_lower
                )
                
                if is_reasoning_model:
                    model_kwargs: Dict[str, Any] = {
                        "max_completion_tokens": settings.rag_reranking_max_completion_tokens,
                    }
                    if settings.rag_reranking_reasoning_effort:
                        model_kwargs["reasoning_effort"] = settings.rag_reranking_reasoning_effort
                    rerank_llm = AzureChatOpenAI(
                        azure_endpoint=rerank_endpoint,
                        api_key=rerank_api_key,
                        api_version=rerank_api_version,
                        azure_deployment=rerank_deployment,
                        model_kwargs=model_kwargs,
                    )
                else:
                    rerank_llm = AzureChatOpenAI(
                        azure_endpoint=rerank_endpoint,
                        api_key=rerank_api_key,
                        api_version=rerank_api_version,
                        azure_deployment=rerank_deployment,
                        temperature=settings.rag_reranking_temperature,
                        max_tokens=settings.rag_reranking_max_tokens,
                    )
                    
            elif provider == "bedrock":
                from langchain_aws import ChatBedrock
                
                rerank_model_id = settings.rag_reranking_bedrock_model_id or settings.bedrock_llm_model_id
                rerank_region = settings.rag_reranking_bedrock_region or settings.aws_region
                
                if not rerank_model_id:
                    raise ValueError("RAG_RERANKING_BEDROCK_MODEL_ID 환경변수가 설정되지 않았습니다.")
                
                logger.info(f"🔧 리랭킹 모델: {rerank_model_id}")
                logger.info(f"🔧 리랭킹 리전: {rerank_region}")
                
                rerank_llm = ChatBedrock(
                    model=rerank_model_id,
                    region_name=rerank_region,
                    model_kwargs={
                        "temperature": settings.rag_reranking_temperature,
                        "max_tokens": settings.rag_reranking_max_tokens,
                    }
                )
                
            else:
                raise ValueError(f"지원하지 않는 리랭킹 제공자: {provider}")
            
            # 리랭킹 프롬프트 생성
            chunks_text = "\n\n".join([
                f"문서 {i+1}:\n{chunk.content[:300]}"
                for i, chunk in enumerate(chunks)
            ])
            
            rerank_prompt = f"""다음 문서들을 질문과의 관련도가 높은 순서대로 재정렬하세요.

질문: "{query}"

문서들:
{chunks_text}

지시사항:
1. 질문과 가장 관련성이 높은 문서부터 낮은 순서로 번호를 나열하세요.
2. 답변 형식: 숫자만 쉼표로 구분 (예: 3,1,5,2,4,6,7)
3. 모든 문서 번호를 포함해야 합니다.

관련도가 높은 순서:"""
            
            # 리랭킹 실행
            response = await rerank_llm.ainvoke([HumanMessage(content=rerank_prompt)])
            rerank_response = response.content if hasattr(response, 'content') else str(response)
            
            # 디버깅: 원본 응답 로그
            logger.debug(f"🔍 LLM 리랭킹 원본 응답 (처음 200자): {str(rerank_response)[:200]}")
            
            # 응답 파싱 (더 견고한 로직)
            import re
            
            # 응답에서 숫자 추출 (다양한 형식 지원)
            # 예: "3,1,5,2,4" or "3, 1, 5" or "순서: 3 1 5" or "[3,1,5]"
            rerank_response_str = str(rerank_response)
            
            # 1. 쉼표/공백으로 구분된 숫자 찾기
            numbers = re.findall(r'\d+', rerank_response_str)
            
            logger.debug(f"🔍 추출된 숫자: {numbers}")
            
            reranked_order = []
            for num_str in numbers:
                num = int(num_str) - 1  # 0-based index
                if 0 <= num < len(chunks) and num not in reranked_order:
                    reranked_order.append(num)
            
            logger.debug(f"🔍 유효한 인덱스: {reranked_order}")
            
            # 재정렬 실패 시 원본 순서 유지
            if len(reranked_order) == 0:
                logger.warning(f"⚠️ 리랭킹 응답 파싱 실패, 원본 순서 유지")
                return chunks
            
            # 새로운 순서로 재정렬
            sorted_chunks = [chunks[i] for i in reranked_order if i < len(chunks)]
            
            # 리랭킹되지 않은 나머지 추가
            remaining = [c for i, c in enumerate(chunks) if i not in reranked_order]
            sorted_chunks.extend(remaining)
            
            logger.info(f"✅ LLM 리랭킹 완료: {len(reranked_order)}개 재정렬")
            return sorted_chunks
            
        except Exception as e:
            logger.warning(f"⚠️ 리랭킹 실패, 원본 점수 사용: {e}")
            # 폴백: 기존 점수 기준 정렬
            sorted_chunks = sorted(
                chunks,
                key=lambda c: c.score,
                reverse=True
        )
        
        return sorted_chunks


# 전역 인스턴스
rerank_tool = RerankTool()

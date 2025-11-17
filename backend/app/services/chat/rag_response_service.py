"""
🤖 RAG 응답 생성 서비스 
======================

RAG 기반 질의응답 처리:
- 검색 결과를 바탕으로 컨텍스트 구성
- Claude 3.5 Sonnet을 활용한 답변 생성
- 답변 품질 검증 및 최적화
- 실시간 채팅 및 PPT 생성 지원
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Generator
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

# Services
from backend.app.services.chat.rag_search_service import rag_search_service, RAGSearchParams
from backend.app.services.core.bedrock_service import bedrock_service

logger = logging.getLogger(__name__)

class ResponseMode(Enum):
    """응답 생성 모드"""
    CHAT = "chat"           # 일반 채팅
    DETAILED = "detailed"   # 상세 설명
    SUMMARY = "summary"     # 요약
    PPT = "ppt"            # PPT 생성용

@dataclass
class RAGRequest:
    """RAG 요청 매개변수"""
    query: str
    container_ids: Optional[List[str]] = None
    response_mode: ResponseMode = ResponseMode.CHAT
    max_context_chunks: int = 8
    include_sources: bool = True
    stream_response: bool = False
    user_context: Optional[Dict[str, Any]] = None

@dataclass
class RAGResponse:
    """RAG 응답 결과"""
    answer: str
    sources: List[Dict[str, Any]]
    context_used: str
    confidence_score: float
    processing_stats: Dict[str, Any]
    search_results: Optional[Dict[str, Any]] = None

class RAGResponseService:
    """RAG 응답 생성 서비스"""
    
    def __init__(self):
        self.search_service = rag_search_service
        self.bedrock_service = bedrock_service
        
        # 응답 모드별 설정
        self.mode_configs = {
            ResponseMode.CHAT: {
                "max_tokens": 2000,
                "temperature": 0.7,
                "system_prompt": "친근하고 정확한 AI 어시스턴트로서 답변해주세요."
            },
            ResponseMode.DETAILED: {
                "max_tokens": 4000,
                "temperature": 0.3,
                "system_prompt": "전문적이고 상세한 설명을 제공하는 AI 어시스턴트입니다."
            },
            ResponseMode.SUMMARY: {
                "max_tokens": 1000,
                "temperature": 0.2,
                "system_prompt": "핵심 내용을 간결하게 요약하는 AI 어시스턴트입니다."
            },
            ResponseMode.PPT: {
                "max_tokens": 3000,
                "temperature": 0.4,
                "system_prompt": "PowerPoint 프레젠테이션 자료 작성 전문 AI 어시스턴트입니다."
            }
        }
    
    async def generate_rag_response(
        self,
        session: AsyncSession,
        request: RAGRequest
    ) -> RAGResponse:
        """
        RAG 기반 응답 생성
        
        Args:
            session: 데이터베이스 세션
            request: RAG 요청 매개변수
            
        Returns:
            RAG 응답 결과
        """
        start_time = time.time()
        
        try:
            logger.info(f"🤖 RAG 응답 생성 시작: '{request.query[:50]}...' "
                       f"(모드: {request.response_mode.value})")
            
            # 1단계: 컨텍스트 검색 (필요 시 하이브리드 후보 재사용)
            search_params = RAGSearchParams(
                query=request.query,
                container_ids=request.container_ids,
                max_chunks=request.max_context_chunks,
                use_reranking=True,
                context_window=4000
            )

            # 하이브리드 검색 후보 문서가 전달된 경우 바로 필터링에 사용하여 재검색 비용 축소
            try:
                if request.user_context:
                    candidate_ids = None
                    for key in ("hybrid_candidates", "candidate_file_ids", "document_ids"):
                        if key in request.user_context and isinstance(request.user_context[key], list):
                            candidate_ids = request.user_context[key]
                            break
                    if candidate_ids:
                        from backend.app.services.chat.rag_search_service import RAGSearchService
                        # 정규화는 서비스 내부에서 재확인되지만, 여기서도 간단 보정
                        def _norm_ids(ids):
                            out = []
                            for x in ids:
                                sx = str(x)
                                import re
                                m = re.search(r"(?i)(?:doc[_-]|file[_-])?(\d+)", sx)
                                if m:
                                    out.append(int(m.group(1)))
                                else:
                                    try:
                                        out.append(int(sx))
                                    except Exception:
                                        pass
                            return out
                        normed = _norm_ids(candidate_ids)
                        if normed:
                            search_params.document_ids = normed
                            logger.info(f"♻️ 하이브리드 후보 문서 재사용: {len(normed)}개 문서로 필터링")
            except Exception:
                pass
            
            search_result = await self.search_service.search_for_rag_context(
                session=session,
                search_params=search_params
            )
            
            if not search_result.chunks:
                logger.warning("검색 결과가 없어 UX 친화적 폴백 응답 생성")
                # 연관 문서 추천 시도 (컨테이너 범위 내)
                try:
                    recommendations = await self.search_service.recommend_related_documents(
                        query=request.query,
                        limit=5,
                        threshold=0.25,
                        db_session=session
                    )
                except Exception:
                    recommendations = []
                return await self._generate_fallback_response(request, recommendations)
            
            # 2단계: 응답 생성
            if request.stream_response:
                # 스트리밍 응답 (실시간 채팅용)
                answer = await self._generate_streaming_response(request, search_result)
            else:
                # 일반 응답
                answer = await self._generate_standard_response(request, search_result)
            
            # 3단계: 소스 정보 구성
            sources = self._build_sources_info(search_result.chunks, request.include_sources)
            
            # 4단계: 신뢰도 점수 계산
            confidence_score = self._calculate_confidence_score(search_result, answer)
            
            # 5단계: 처리 통계
            processing_stats = {
                "total_time": time.time() - start_time,
                "search_time": search_result.search_stats.get("search_time", 0),
                "generation_time": time.time() - start_time - search_result.search_stats.get("search_time", 0),
                "chunks_used": len(search_result.chunks),
                "context_tokens": search_result.total_tokens,
                "response_mode": request.response_mode.value,
                "reranking_applied": search_result.reranking_applied
            }
            
            logger.info(f"✅ RAG 응답 생성 완료: {processing_stats['total_time']:.2f}초, "
                       f"신뢰도 {confidence_score:.2f}")
            
            return RAGResponse(
                answer=answer,
                sources=sources,
                context_used=search_result.context_text,
                confidence_score=confidence_score,
                processing_stats=processing_stats,
                search_results=search_result.search_stats
            )
            
        except Exception as e:
            logger.error(f"RAG 응답 생성 실패: {str(e)}")
            return await self._generate_error_response(request, str(e))
    
    async def _generate_standard_response(
        self,
        request: RAGRequest,
        search_result
    ) -> str:
        """표준 응답 생성"""
        config = self.mode_configs[request.response_mode]
        
        # 응답 모드별 프롬프트 구성
        if request.response_mode == ResponseMode.PPT:
            prompt = self._build_ppt_prompt(request, search_result)
        else:
            prompt = self._build_standard_prompt(request, search_result, config)
        
        # Claude로 응답 생성
        response = await self.bedrock_service.generate_text_claude(
            prompt=prompt,
            max_tokens=config["max_tokens"],
            temperature=config["temperature"]
        )
        
        return response
    
    async def _generate_streaming_response(
        self,
        request: RAGRequest,
        search_result
    ) -> str:
        """스트리밍 응답 생성 (실시간 채팅용)"""
        # TODO: 스트리밍 구현
        # 현재는 표준 응답으로 대체
        return await self._generate_standard_response(request, search_result)
    
    def _build_standard_prompt(
        self,
        request: RAGRequest,
        search_result,
        config: Dict[str, Any]
    ) -> str:
        """표준 프롬프트 구성"""
        prompt = f"""다음 컨텍스트를 바탕으로 질문에 답변해주세요.

질문: {request.query}

컨텍스트:
{search_result.context_text}

답변 지침:
- 제공된 컨텍스트를 우선적으로 활용하세요
- 정확하고 구체적인 정보를 제공하세요
- 컨텍스트에 없는 내용은 추측하지 마세요
- 한국어로 자연스럽게 답변하세요
"""
        
        if request.response_mode == ResponseMode.DETAILED:
            prompt += "- 상세하고 전문적인 설명을 제공하세요\n"
        elif request.response_mode == ResponseMode.SUMMARY:
            prompt += "- 핵심 내용만 간결하게 요약하세요\n"
        
        if request.user_context:
            prompt += f"\n사용자 컨텍스트: {json.dumps(request.user_context, ensure_ascii=False)}\n"
        
        return prompt
    
    def _build_ppt_prompt(
        self,
        request: RAGRequest,
        search_result
    ) -> str:
        """PPT 생성용 프롬프트 구성"""
        return f"""다음 내용을 바탕으로 PowerPoint 프레젠테이션을 위한 구조화된 내용을 작성해주세요.

주제: {request.query}

참고 자료:
{search_result.context_text}

요구사항:
1. 프레젠테이션 제목과 부제목 제안
2. 슬라이드별 구성 (제목, 주요 내용, 세부 설명)
3. 각 슬라이드당 3-5개의 핵심 포인트
4. 시각적 요소 제안 (차트, 이미지, 다이어그램)
5. 발표자 노트 포함

출력 형식:
```json
{{
    "presentation_title": "프레젠테이션 제목",
    "subtitle": "부제목",
    "slides": [
        {{
            "slide_number": 1,
            "title": "슬라이드 제목",
            "content_points": ["포인트1", "포인트2", "포인트3"],
            "detailed_explanation": "상세 설명",
            "visual_suggestions": "시각적 요소 제안",
            "speaker_notes": "발표자 노트"
        }}
    ]
}}
```

컨텍스트에 기반하여 실용적이고 전문적인 프레젠테이션을 구성해주세요.
"""
    
    def _build_sources_info(
        self,
        chunks: List[Dict[str, Any]],
        include_details: bool
    ) -> List[Dict[str, Any]]:
        """소스 정보 구성"""
        sources = []
        
        for i, chunk in enumerate(chunks):
            source_info = {
                "index": i + 1,
                "file_name": chunk.get("file_name", "Unknown"),
                "similarity_score": chunk.get("similarity_score", 0),
                "chunk_type": chunk.get("chunk_type", "content")
            }
            
            if include_details:
                source_info.update({
                    "content_preview": chunk.get("content", "")[:200] + "...",
                    "metadata": chunk.get("metadata", {}),
                    "search_type": chunk.get("search_type", "unknown")
                })
            
            sources.append(source_info)
        
        return sources
    
    def _calculate_confidence_score(
        self,
        search_result,
        answer: str
    ) -> float:
        """신뢰도 점수 계산"""
        try:
            # 기본 점수 (검색 결과 품질)
            base_score = 0.5
            
            # 검색 결과 품질 평가
            if search_result.chunks:
                avg_similarity = sum(chunk.get("similarity_score", 0) for chunk in search_result.chunks) / len(search_result.chunks)
                base_score += avg_similarity * 0.3
            
            # 답변 길이 평가 (너무 짧거나 길면 감점)
            answer_length = len(answer)
            if 100 <= answer_length <= 2000:
                base_score += 0.1
            elif answer_length < 50:
                base_score -= 0.2
            
            # 컨텍스트 활용도 평가
            if search_result.total_tokens > 0:
                base_score += 0.1
            
            # 리랭킹 적용 여부
            if search_result.reranking_applied:
                base_score += 0.05
            
            return min(1.0, max(0.0, base_score))
            
        except Exception as e:
            logger.error(f"신뢰도 점수 계산 실패: {str(e)}")
            return 0.5
    
    async def _generate_fallback_response(self, request: RAGRequest, recommendations: Optional[List[Dict[str, Any]]] = None) -> RAGResponse:
        """검색 결과가 없을 때 대체 응답 (추천 문서/질문 유도/PPT 초안 제안 포함)"""
        rec_lines: List[str] = []
        if recommendations:
            for r in recommendations[:5]:
                name = r.get("file_name") or r.get("title") or str(r.get("file_id"))
                rec_lines.append(f"- {name} (유사도 {r.get('max_similarity', 0):.2f})")
        rec_text = "\n".join(rec_lines)

        guidance = (
            "다음을 선택하시면 더 정확히 도와드릴 수 있어요:\n"
            "- 대상(고객/제품/부서)\n- 분량(슬라이드 수/페이지)\n- 톤앤매너(전문/친근/간결)\n"
        )

        ppt_skeleton = (
            "간단한 PPT 초안을 시작할 수도 있어요:\n"
            "1) 표지: 제목/부제목/작성자\n"
            "2) 개요: 목적/배경/범위\n"
            "3) 본문: 핵심 메시지 3~5개 (각 3 bullet)\n"
            "4) 결론: 요약/다음 단계\n"
        )

        fallback_answer = (
            f"죄송합니다. '{request.query}'에 대한 직접적인 참고자료를 찾지 못했습니다.\n\n"
            + ("추천 문서:\n" + rec_text + "\n\n" if rec_text else "")
            + guidance
            + ppt_skeleton
        )
        
        return RAGResponse(
            answer=fallback_answer,
            sources=[],
            context_used="",
            confidence_score=0.1,
            processing_stats={
                "total_time": 0.1,
                "search_time": 0.05,
                "generation_time": 0.05,
                "chunks_used": 0,
                "context_tokens": 0,
                "response_mode": request.response_mode.value,
                "is_fallback": True
            }
        )
    
    async def _generate_error_response(self, request: RAGRequest, error_msg: str) -> RAGResponse:
        """오류 발생시 응답"""
        error_answer = "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        
        return RAGResponse(
            answer=error_answer,
            sources=[],
            context_used="",
            confidence_score=0.0,
            processing_stats={
                "total_time": 0.0,
                "error": error_msg,
                "response_mode": request.response_mode.value
            }
        )

# 전역 인스턴스
rag_response_service = RAGResponseService()

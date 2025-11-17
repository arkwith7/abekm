"""
Paper Search Agent - 논문/문서 검색 전문 에이전트
동적 도구 선택과 전략 기반 검색 수행
"""
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.contracts import (
    AgentIntent, AgentConstraints, AgentResult, AgentStep,
    SearchChunk, ToolResult
)
from app.tools.retrieval.vector_search_tool import vector_search_tool
from app.tools.retrieval.keyword_search_tool import keyword_search_tool
from app.tools.retrieval.fulltext_search_tool import fulltext_search_tool
from app.tools.processing.deduplicate_tool import deduplicate_tool
from app.tools.processing.rerank_tool import rerank_tool
from app.tools.context.context_builder_tool import context_builder_tool
from app.services.core.korean_nlp_service import korean_nlp_service
from app.services.core.ai_service import ai_service


class PaperSearchAgent:
    """
    논문/문서 검색 에이전트
    
    역할:
    1. 질의 분석 (의도 분류, 키워드 추출, 언어 감지)
    2. 검색 전략 선택 (의도와 제약에 따라 도구 조합 결정)
    3. 도구 순차 실행 (각 도구는 독립적)
    4. 컨텍스트 구성 및 답변 생성
    
    도구 목록:
    - vector_search: 의미 기반 검색
    - keyword_search: 키워드 매칭
    - fulltext_search: 전문검색 (tsvector)
    - deduplicate: 중복 제거
    - context_builder: 컨텍스트 토큰 패킹
    """
    
    name: str = "paper_search_agent"
    description: str = "논문/문서 검색 및 QA 전문 에이전트"
    version: str = "1.0.0"
    
    def __init__(self):
        # 도구 등록 (느슨한 결합) - 전역 인스턴스 사용
        self.tools = {
            "vector_search": vector_search_tool,
            "keyword_search": keyword_search_tool,
            "rerank": rerank_tool,
            "fulltext_search": fulltext_search_tool,
            "deduplicate": deduplicate_tool,
            "context_builder": context_builder_tool,
            # TODO: PPT 생성 도구 추가 예정
            # "ppt_generator": ppt_generator_tool,
            # - 검색 결과를 받아 슬라이드 구조 생성
            # - general.prompt의 PPT 모드 규칙을 tool 내부로 캡슐화
            # - Agent는 PPT 요청 감지 시 이 도구를 전략에 포함
        }
        
        self.nlp_service = korean_nlp_service
        self.ai_service = ai_service
        self._steps: List[AgentStep] = []
        self._start_time: Optional[datetime] = None
    
    async def execute(
        self,
        query: str,
        db_session: AsyncSession,
        constraints: Optional[AgentConstraints] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        에이전트 실행
        
        Args:
            query: 사용자 질의
            db_session: DB 세션
            constraints: 제약 조건
            context: 추가 컨텍스트 (user_emp_no 등)
        """
        self._start_time = datetime.utcnow()
        self._steps = []
        
        if constraints is None:
            constraints = AgentConstraints()
        
        try:
            logger.info(f"🤖 [PaperSearchAgent] 실행 시작: '{query[:50]}...'")
            
            # Step 1: 질의 분석
            intent = self.classify_intent(query)
            keywords = await self._extract_keywords(query)
            
            logger.info(f"   - 의도: {intent}, 키워드: {keywords}")
            
            # Step 2: 전략 선택
            strategy = self.select_strategy(intent, constraints)
            logger.info(f"   - 전략: {strategy}")
            
            # Step 3: 도구 실행
            all_chunks: List[SearchChunk] = []
            search_results_by_type = {}  # 검색 타입별 결과 추적
            
            for tool_name in strategy:
                tool = self.tools.get(tool_name)
                if not tool:
                    logger.warning(f"⚠ 도구 없음: {tool_name}")
                    continue
                
                try:
                    tool_result = await self._execute_tool(
                        tool_name=tool_name,
                        query=query,
                        db_session=db_session,
                        keywords=keywords,
                        constraints=constraints,
                        chunks=all_chunks,  # 이전 도구 결과
                        context=context
                    )
                    
                    # 결과 병합/교체
                    if tool_name in ["vector_search", "keyword_search", "fulltext_search"]:
                        # 🆕 검색 도구 → 병합 및 타입별 추적
                        if tool_result.success and hasattr(tool_result, 'data'):
                            new_chunks = tool_result.data
                            all_chunks.extend(new_chunks)
                            search_results_by_type[tool_name] = len(new_chunks)
                            logger.info(f"   ✅ {tool_name}: {len(new_chunks)}개 청크 추가 (총 {len(all_chunks)}개)")
                    elif tool_name in ["deduplicate", "rerank"]:
                        # 후처리 도구 → 교체
                        if tool_result.success and hasattr(tool_result, 'data'):
                            before_count = len(all_chunks)
                            all_chunks = tool_result.data
                            logger.info(f"   ✅ {tool_name}: {before_count}개 → {len(all_chunks)}개")
                    
                except Exception as e:
                    logger.error(f"❌ 도구 실행 실패: {tool_name} - {e}")
                    continue
            
            # 🆕 하이브리드 검색 결과 로깅
            if search_results_by_type:
                logger.info(f"   📊 하이브리드 검색 완료: {search_results_by_type}")
            
            # Step 4: 컨텍스트 구성
            context_result = await self._execute_tool(
                tool_name="context_builder",
                query=query,
                db_session=db_session,
                keywords=keywords,
                constraints=constraints,
                chunks=all_chunks,
                context=None
            )
            
            if not context_result.success:
                raise Exception("컨텍스트 구성 실패")
            
            # ContextResult는 ToolResult의 서브클래스이므로 속성에 직접 접근
            context_text = context_result.data if isinstance(context_result.data, str) else ""
            used_chunks = getattr(context_result, 'used_chunks', all_chunks[:5])
            
            # Step 5: 답변 생성
            answer = await self.generate_answer(query, context_text, intent)
            
            # Step 6: 결과 반환
            latency_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
            
            logger.info(f"✅ [PaperSearchAgent] 완료: {latency_ms:.1f}ms, {len(used_chunks)}개 참조")
            
            return AgentResult(
                answer=answer,
                references=used_chunks,
                steps=self._steps,
                metrics={
                    "total_latency_ms": latency_ms,
                    "tools_used": len(self._steps),
                    "chunks_found": len(all_chunks),
                    "chunks_used": len(used_chunks),
                    "total_tokens": getattr(context_result, 'total_tokens', 0)
                },
                intent=intent,
                strategy_used=strategy,
                success=True,
                errors=[]
            )
            
        except Exception as e:
            logger.error(f"❌ [PaperSearchAgent] 실패: {e}", exc_info=True)
            latency_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000 if self._start_time else 0
            
            return AgentResult(
                answer=f"죄송합니다. 검색 중 오류가 발생했습니다: {str(e)}",
                references=[],
                steps=self._steps,
                metrics={"total_latency_ms": latency_ms},
                intent=AgentIntent.FACTUAL_QA,
                strategy_used=[],
                success=False,
                errors=[str(e)]
            )
    
    def classify_intent(self, query: str) -> AgentIntent:
        """의도 분류 (간단한 룰 기반)"""
        q = query.lower()
        
        # 키워드 검색
        if any(kw in q for kw in ["검색", "찾아", "찾기", "있나", "있는지"]):
            return AgentIntent.KEYWORD_SEARCH
        
        # 비교
        if any(kw in q for kw in ["비교", "차이", "다른점", "vs"]):
            return AgentIntent.COMPARISON
        
        # 요약
        if any(kw in q for kw in ["요약", "정리", "개요"]):
            return AgentIntent.SUMMARIZATION
        
        # 기본: 사실 확인 질문
        return AgentIntent.FACTUAL_QA
    
    def select_strategy(
        self,
        intent: AgentIntent,
        constraints: AgentConstraints
    ) -> List[str]:
        """
        전략 선택 - 핵심 에이전트 로직
        의도와 제약에 따라 도구 조합 동적 결정
        
        🆕 모든 전략에 하이브리드 검색 적용 (벡터 + 키워드 동시 실행)
        """
        if intent == AgentIntent.FACTUAL_QA:
            # 🆕 사실 확인 → 하이브리드 검색 (벡터 + 키워드) + 중복제거 + 리랭킹
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.KEYWORD_SEARCH:
            # 키워드 중심 → 키워드 + 전문검색 + 중복제거 + 리랭킹
            return ["keyword_search", "fulltext_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.EXPLORATORY:
            # 탐색 → 하이브리드 (벡터 + 키워드 + 전문검색) + 리랭킹
            return ["vector_search", "keyword_search", "fulltext_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.COMPARISON:
            # 비교 → 하이브리드 (벡터 + 키워드) + 풍부한 컨텍스트 + 리랭킹
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.SUMMARIZATION:
            # 요약 → 하이브리드 검색으로 광범위한 자료 수집
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
        
        else:
            # 기본 전략: 하이브리드 검색 + 리랭킹
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
    
    async def _execute_tool(
        self,
        tool_name: str,
        query: str,
        db_session: AsyncSession,
        keywords: List[str],
        constraints: AgentConstraints,
        chunks: List[SearchChunk],
        context: Optional[Dict[str, Any]]
    ) -> ToolResult:
        """도구 실행 헬퍼"""
        tool = self.tools[tool_name]
        
        if tool_name == "vector_search":
            tool_input = {
                "query": query,
                "db_session": db_session,
                "top_k": constraints.max_chunks,
                "similarity_threshold": constraints.similarity_threshold,
                "container_ids": constraints.container_ids,
                "document_ids": constraints.document_ids,
                "user_emp_no": context.get("user_emp_no") if context else None
            }
            reasoning = "의미 기반 유사 문서 검색"
        
        elif tool_name == "keyword_search":
            tool_input = {
                "query": query,
                "db_session": db_session,
                "keywords": keywords,
                "top_k": constraints.max_chunks,
                "container_ids": constraints.container_ids,
                "document_ids": constraints.document_ids,
                "user_emp_no": context.get("user_emp_no") if context else None
            }
            reasoning = "키워드 직접 매칭"
        
        elif tool_name == "fulltext_search":
            tool_input = {
                "query": query,
                "db_session": db_session,
                "tsquery_str": " | ".join(keywords) if keywords else None,
                "top_k": constraints.max_chunks,
                "container_ids": constraints.container_ids,
                "document_ids": constraints.document_ids,
                "user_emp_no": context.get("user_emp_no") if context else None
            }
            reasoning = "PostgreSQL 전문검색"
        
        elif tool_name == "deduplicate":
            tool_input = {
                "chunks": chunks,
                "similarity_threshold": 0.95
            }
            reasoning = "중복 청크 제거"
        
        elif tool_name == "rerank":
            tool_input = {
                "chunks": chunks,
                "query": query,
                "top_k": constraints.max_chunks
            }
            reasoning = "LLM 기반 관련도 재평가"
        
        elif tool_name == "context_builder":
            tool_input = {
                "chunks": chunks,
                "max_tokens": constraints.max_tokens,
                "include_metadata": True,
                "format_style": "citation"
            }
            reasoning = "토큰 제한 내에서 컨텍스트 구성"
        
        else:
            tool_input = {}
            reasoning = f"{tool_name} 실행"
        
        result = await tool._arun(**tool_input)
        
        self._log_step(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result,
            reasoning=reasoning
        )
        
        return result
    
    async def _extract_keywords(self, query: str) -> List[str]:
        """키워드 추출"""
        try:
            analysis = await self.nlp_service.analyze_text_for_search(query)
            return analysis.get("keywords", [])
        except Exception as e:
            logger.warning(f"형태소 분석 실패, 공백 분리 사용: {e}")
            return [w.strip() for w in query.split() if len(w.strip()) >= 2]
    
    async def generate_answer(
        self,
        query: str,
        context: str,
        intent: AgentIntent
    ) -> str:
        """
        답변 생성 (general.prompt 기반)
        
        Note: PPT 생성 관련 로직은 향후 별도 tool로 분리 예정
        - 현재: general.prompt의 모든 규칙 적용 (일반 답변 + PPT 모드 포함)
        - 향후: ppt_generator_tool 분리 후 Agent가 도구로 호출하는 구조로 변경
        """
        from pathlib import Path
        
        # 컨텍스트 없을 때 처리
        if not context or context.strip() == "":
            return "죄송합니다. 질문과 관련된 문서를 찾을 수 없습니다. 다른 키워드로 검색해 주세요."
        
        # 🆕 general.prompt 로드 (일반 채팅과 동일한 품질 보장)
        system_prompt = None
        try:
            prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
            if prompt_path.exists():
                system_prompt = prompt_path.read_text(encoding='utf-8').strip()
                logger.info("✅ Agent: general.prompt 로드 성공")
            else:
                logger.warning("⚠️ general.prompt 파일 없음, 기본 프롬프트 사용")
                system_prompt = "논문/문서 검색 전문가. 제공된 문서를 바탕으로 간결하게 답변."
        except Exception as e:
            logger.error(f"❌ general.prompt 로드 실패: {e}, 기본 프롬프트 사용")
            system_prompt = "논문/문서 검색 전문가. 제공된 문서를 바탕으로 간결하게 답변."
        
        # 참조 문서 개수 계산 (general.prompt의 참조문서 개수 확인 원칙 준수)
        doc_count = len([c for c in context.split('---') if c.strip()])
        
        # User 메시지 구성 (참조문서 개수 명시)
        user_message = f"""질문: {query}

참조 문서:
{context}

참조문서 개수: {doc_count}개

위 문서를 바탕으로 질문에 답변하세요. 출처는 (파일명) 형식으로 표기하세요."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # max_tokens 증가 (general.prompt의 상세 답변 지원을 위해)
        response = await self.ai_service.chat_completion(
            messages,
            max_tokens=2000,  # 800 → 2000 (일반 채팅과 동일하게 상세 답변 가능)
            temperature=0.3  # 낮은 temperature로 일관성 향상
        )
        return response.get("response", "답변 생성 실패")
    
    def _log_step(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: ToolResult,
        reasoning: str
    ):
        """실행 단계 로깅"""
        step = AgentStep(
            step_number=len(self._steps) + 1,
            tool_name=tool_name,
            tool_input={k: str(v)[:100] for k, v in tool_input.items()},  # 긴 값 자르기
            tool_output=tool_output,
            reasoning=reasoning
        )
        self._steps.append(step)


# 전역 인스턴스
paper_search_agent = PaperSearchAgent()

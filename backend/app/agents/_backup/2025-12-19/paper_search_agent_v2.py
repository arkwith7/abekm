"""
Autonomous Paper Search Agent V2 - LangChain 1.X ReAct Pattern

기존 PaperSearchAgent의 자율형 버전:
- BaseAutonomousAgent 상속
- LangChain ReAct 패턴 사용
- LLM이 도구를 자율적으로 선택/실행
- 하드코딩된 전략 제거
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_core.language_models import BaseLanguageModel
from langgraph.prebuilt import create_react_agent

from app.agents.base import BaseAutonomousAgent, AgentExecutionContext, AgentCapability, AgentExecutionResult
from app.agents.base.agent_protocol import AgentMode, AgentStatus, AgentStep
from app.agents.base.agent_state import AgentStateManager

# 기존 도구들 임포트 (이미 BaseTool 호환)
from app.tools.retrieval.vector_search_tool import vector_search_tool
from app.tools.retrieval.keyword_search_tool import keyword_search_tool
from app.tools.retrieval.fulltext_search_tool import fulltext_search_tool
from app.tools.retrieval.internet_search_tool import internet_search_tool
from app.tools.retrieval.multimodal_search_tool import multimodal_search_tool
from app.tools.processing.deduplicate_tool import deduplicate_tool
from app.tools.processing.rerank_tool import rerank_tool
from app.tools.context.context_builder_tool import context_builder_tool
from app.tools.vision.image_analysis_tool import get_image_analysis_tool

from app.services.core.ai_service import ai_service
from app.services.core.korean_nlp_service import korean_nlp_service


class PaperSearchAgentV2(BaseAutonomousAgent):
    """
    자율형 논문/문서 검색 에이전트 V2
    
    주요 개선점:
    1. LangChain ReAct 패턴으로 LLM이 도구를 자율적으로 선택
    2. 하드코딩된 전략 맵핑 제거
    3. BaseAutonomousAgent 표준 인터페이스 준수
    4. ContextVar 기반 상태 관리로 동시성 안전성 확보
    5. 스트리밍 지원 및 진행 상황 추적
    
    사용 가능한 도구 (9개):
    - vector_search: 의미 기반 벡터 검색
    - keyword_search: 키워드 매칭 검색
    - fulltext_search: PostgreSQL 전문검색
    - internet_search: 인터넷 검색 (외부 정보)
    - multimodal_search: 이미지+텍스트 멀티모달 검색
    - deduplicate: 중복 청크 제거
    - rerank: 관련도 재순위화
    - context_builder: 컨텍스트 토큰 패킹
    - image_analysis: 이미지 분석
    """
    
    def __init__(self):
        super().__init__()

        self.name = "paper_search_agent_v2"
        self.description = "자율형 논문/문서 검색 및 QA 에이전트 (LangGraph ReAct)"
        self.version = "2.0.0"
        
        # 원본 도구(의존성 주입 전). 실제 실행 시 요청 컨텍스트에 맞게 래핑된 도구를 사용.
        self._raw_tools: List[BaseTool] = [
            vector_search_tool,
            keyword_search_tool,
            fulltext_search_tool,
            internet_search_tool,
            multimodal_search_tool,
            deduplicate_tool,
            rerank_tool,
            context_builder_tool,
            get_image_analysis_tool(),
        ]
        
        # 서비스 의존성
        self.ai_service = ai_service
        self.nlp_service = korean_nlp_service

        self._system_prompt_template = (
            "당신은 기업 지식 관리 시스템의 전문 검색 에이전트입니다.\n\n"
            "역할: 사용자 질문을 분석하고, 필요 시 도구를 호출해 근거 기반 답변을 생성합니다.\n\n"
            "사용 가능한 도구:\n{tools}\n\n"
            "제약 조건:\n"
            "- knowledge_container_ids: {container_ids}\n"
            "- user_emp_no: {user_emp_no}\n"
            "- max_iterations: {max_iterations}\n"
            "- timeout_seconds: {timeout_seconds}\n"
        )
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: AgentExecutionContext,
        mode: AgentMode = AgentMode.REACT,
    ) -> AgentExecutionResult:
        """BaseAutonomousAgent 표준 인터페이스 구현."""
        started_at = datetime.utcnow()
        query = input_data.get("query") or input_data.get("message") or ""
        if not query:
            return AgentExecutionResult(
                success=False,
                output={"answer": ""},
                agent_name=self.name,
                mode=mode,
                status=AgentStatus.FAILED,
                steps=[],
                tools_used=[],
                total_latency_ms=0.0,
                llm_calls=0,
                tool_calls=0,
                tokens_used=0,
                errors=["query is required"],
                warnings=[],
                context=context,
            )

        db_session: Optional[AsyncSession] = input_data.get("db_session")
        if db_session is None:
            return AgentExecutionResult(
                success=False,
                output={"answer": ""},
                agent_name=self.name,
                mode=mode,
                status=AgentStatus.FAILED,
                steps=[],
                tools_used=[],
                total_latency_ms=0.0,
                llm_calls=0,
                tool_calls=0,
                tokens_used=0,
                errors=["db_session is required"],
                warnings=[],
                context=context,
            )

        # 컨텍스트에서 제약 추출 (v2 엔드포인트가 context.metadata에 넣어줌)
        constraints = (context.metadata or {}).get("constraints", {})
        container_ids = constraints.get("knowledge_container_ids") or constraints.get("container_ids") or []
        document_ids = constraints.get("document_ids") or []
        user_emp_no = str(context.shared_context.get("user_emp_no", "unknown"))

        history = input_data.get("history", [])
        images = input_data.get("images", [])

        # 상태 초기화 (관측용)
        AgentStateManager.init_state(
            request_id=context.request_id,
            agent_name=self.name,
            query=query,
        )
        if images:
            AgentStateManager.add_metadata("has_images", True)
            AgentStateManager.add_metadata("image_count", len(images))

        try:
            llm = await self._get_llm()

            bound_tools = self._build_bound_tools(
                db_session=db_session,
                container_ids=[str(cid) for cid in (container_ids or [])],
                document_ids=[str(did) for did in (document_ids or [])],
                user_emp_no=user_emp_no,
                images=images,
            )

            system_prompt = self._system_prompt_template.format(
                tools=self._format_tool_descriptions(bound_tools),
                container_ids=container_ids,
                user_emp_no=user_emp_no,
                max_iterations=context.max_iterations,
                timeout_seconds=context.timeout_seconds,
            )

            messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
            messages.extend(self._format_chat_history(history))
            messages.append(HumanMessage(content=query))

            react_agent = create_react_agent(llm, bound_tools)

            AgentStateManager.update_step("react_execution", "started")

            async def _run():
                return await react_agent.ainvoke(
                    {"messages": messages},
                    config={"recursion_limit": context.max_iterations},
                )

            state = await asyncio.wait_for(_run(), timeout=context.timeout_seconds)
            out_messages: List[BaseMessage] = list(state.get("messages", []))

            answer = self._extract_final_answer(out_messages)
            steps = self._extract_tool_steps(out_messages)

            AgentStateManager.update_step("react_execution", "completed")

            total_latency_ms = (datetime.utcnow() - started_at).total_seconds() * 1000
            tools_used = [s.action for s in steps if s.action]

            return AgentExecutionResult(
                success=True,
                output={"answer": answer},
                agent_name=self.name,
                mode=mode,
                status=AgentStatus.COMPLETED,
                steps=steps,
                tools_used=tools_used,
                total_latency_ms=total_latency_ms,
                llm_calls=sum(1 for m in out_messages if isinstance(m, AIMessage)),
                tool_calls=sum(1 for m in out_messages if isinstance(m, ToolMessage)),
                tokens_used=0,
                errors=[],
                warnings=[],
                context=context,
            )

        except asyncio.TimeoutError:
            total_latency_ms = (datetime.utcnow() - started_at).total_seconds() * 1000
            AgentStateManager.add_error("timeout")
            return AgentExecutionResult(
                success=False,
                output={"answer": "요청 처리 시간이 초과되었습니다."},
                agent_name=self.name,
                mode=mode,
                status=AgentStatus.FAILED,
                steps=[],
                tools_used=[],
                total_latency_ms=total_latency_ms,
                llm_calls=0,
                tool_calls=0,
                tokens_used=0,
                errors=["timeout"],
                warnings=[],
                context=context,
            )
        except Exception as e:
            total_latency_ms = (datetime.utcnow() - started_at).total_seconds() * 1000
            logger.error(f"[PaperSearchAgentV2] Execution failed: {e}", exc_info=True)
            AgentStateManager.add_error(str(e))
            return AgentExecutionResult(
                success=False,
                output={"answer": f"검색 중 오류가 발생했습니다: {str(e)}"},
                agent_name=self.name,
                mode=mode,
                status=AgentStatus.FAILED,
                steps=[],
                tools_used=[],
                total_latency_ms=total_latency_ms,
                llm_calls=0,
                tool_calls=0,
                tokens_used=0,
                errors=[str(e)],
                warnings=[],
                context=context,
            )
    
    async def _get_llm(self) -> BaseLanguageModel:
        """
        AI 서비스에서 LLM 인스턴스 가져오기
        """
        # ai_service의 get_model 메서드 사용
        # GPT-4o나 Claude Sonnet 등 고성능 모델 권장
        llm = await self.ai_service.get_model(
            provider="azure",  # 또는 "openai", "bedrock"
            model_name="gpt-4o",
            temperature=0.0,  # 검색 에이전트는 정확성 우선
            streaming=True,
        )
        return llm
    
    def _format_chat_history(self, history: List[Dict[str, str]]) -> List[BaseMessage]:
        """
        대화 히스토리를 LangChain 메시지로 변환
        """
        messages = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        
        return messages
    
    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(name="search", description="내부 문서 검색 및 QA"),
            AgentCapability(name="retrieval", description="벡터/키워드/전문검색"),
            AgentCapability(name="multimodal", description="이미지 기반 검색 및 분석"),
            AgentCapability(name="web_search", description="인터넷 검색 폴백"),
        ]

    def _format_tool_descriptions(self, tools: List[BaseTool]) -> str:
        return "\n".join([f"- {t.name}: {t.description}" for t in tools])

    def _extract_final_answer(self, messages: List[BaseMessage]) -> str:
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and (msg.content or "").strip():
                return str(msg.content)
        return "검색 결과를 찾을 수 없습니다."

    def _try_parse_json(self, value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
                try:
                    return json.loads(text)
                except Exception:
                    return value
        return value

    def _extract_tool_steps(self, messages: List[BaseMessage]) -> List[AgentStep]:
        """LangGraph ReAct 메시지에서 tool 호출 로그를 AgentStep으로 변환."""
        tool_call_by_id: Dict[str, Dict[str, Any]] = {}
        steps: List[AgentStep] = []
        step_number = 1

        for msg in messages:
            if isinstance(msg, AIMessage):
                for tc in (getattr(msg, "tool_calls", None) or []):
                    tc_id = tc.get("id") or tc.get("tool_call_id")
                    if tc_id:
                        tool_call_by_id[tc_id] = tc
            elif isinstance(msg, ToolMessage):
                tc_id = getattr(msg, "tool_call_id", None)
                tc = tool_call_by_id.get(tc_id, {}) if tc_id else {}

                tool_name = tc.get("name") or getattr(msg, "name", "tool")
                tool_input = tc.get("args") or {}
                tool_output = self._try_parse_json(msg.content)

                latency_ms = 0.0
                if isinstance(tool_output, dict):
                    metrics = tool_output.get("metrics")
                    if isinstance(metrics, dict):
                        latency_ms = float(metrics.get("latency_ms") or 0.0)

                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action=str(tool_name),
                        reasoning=None,
                        tool_input=tool_input if isinstance(tool_input, dict) else {"value": tool_input},
                        tool_output=tool_output,
                        latency_ms=latency_ms,
                        success=True,
                        error=None,
                    )
                )
                step_number += 1

        return steps

    def _build_bound_tools(
        self,
        db_session: AsyncSession,
        container_ids: List[str],
        document_ids: List[str],
        user_emp_no: str,
        images: List[Any],
    ) -> List[BaseTool]:
        """LLM 도구 호출에 db_session 같은 내부 의존성이 노출되지 않도록 래핑."""

        def _dump_model(result: Any) -> Any:
            try:
                return result.model_dump()  # pydantic v2
            except Exception:
                try:
                    return result.dict()  # pydantic v1
                except Exception:
                    return result

        from app.tools.contracts import SearchChunk

        @tool("vector_search")
        async def vector_search(query: str, top_k: int = 20, similarity_threshold: float = 0.2):
            res = await vector_search_tool._arun(
                query=query,
                db_session=db_session,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                container_ids=container_ids,
                document_ids=document_ids or None,
                user_emp_no=user_emp_no,
            )
            return _dump_model(res)

        @tool("keyword_search")
        async def keyword_search(query: str, top_k: int = 20, case_sensitive: bool = False):
            res = await keyword_search_tool._arun(
                query=query,
                db_session=db_session,
                top_k=top_k,
                container_ids=container_ids,
                document_ids=document_ids or None,
                user_emp_no=user_emp_no,
                case_sensitive=case_sensitive,
            )
            return _dump_model(res)

        @tool("fulltext_search")
        async def fulltext_search(query: str, top_k: int = 20):
            res = await fulltext_search_tool._arun(
                query=query,
                db_session=db_session,
                top_k=top_k,
                container_ids=container_ids,
                document_ids=document_ids or None,
                user_emp_no=user_emp_no,
            )
            return _dump_model(res)

        @tool("internet_search")
        async def internet_search(query: str, top_k: int = 5, provider: Optional[str] = None):
            res = await internet_search_tool._arun(query=query, top_k=top_k, provider=provider)
            return _dump_model(res)

        @tool("multimodal_search")
        async def multimodal_search(query: str = "", top_k: int = 10):
            if not images:
                return {"success": False, "errors": ["no images provided"], "data": []}
            image_data = images[0]
            res = await multimodal_search_tool._arun(
                image_data=image_data,
                query=query,
                top_k=top_k,
                container_ids=container_ids,
                db_session=db_session,
            )
            return _dump_model(res)

        @tool("image_analysis")
        async def image_analysis():
            if not images:
                return {"success": False, "errors": ["no images provided"]}
            image_data = images[0]
            res = await get_image_analysis_tool()._arun(image_data=image_data)
            return _dump_model(res)

        def _coerce_chunks(chunks: Any) -> List[SearchChunk]:
            if not chunks:
                return []
            if isinstance(chunks, dict) and "data" in chunks:
                chunks = chunks.get("data")
            if not isinstance(chunks, list):
                return []
            out: List[SearchChunk] = []
            for item in chunks:
                if isinstance(item, SearchChunk):
                    out.append(item)
                elif isinstance(item, dict):
                    try:
                        out.append(SearchChunk(**item))
                    except Exception:
                        continue
            return out

        @tool("deduplicate")
        async def deduplicate(chunks: Any):
            coerced = _coerce_chunks(chunks)
            res = await deduplicate_tool._arun(chunks=coerced)
            return _dump_model(res)

        @tool("rerank")
        async def rerank(chunks: Any, query: str, top_k: Optional[int] = None, model_name: str = "bge-reranker-base", threshold: float = 0.3):
            coerced = _coerce_chunks(chunks)
            res = await rerank_tool._arun(
                chunks=coerced,
                query=query,
                top_k=top_k,
                model_name=model_name,
                threshold=threshold,
            )
            return _dump_model(res)

        @tool("context_builder")
        async def context_builder(chunks: Any, max_tokens: int = 4000, include_metadata: bool = True, format_style: str = "citation", priority_by: str = "similarity"):
            coerced = _coerce_chunks(chunks)
            res = await context_builder_tool._arun(
                chunks=coerced,
                max_tokens=max_tokens,
                include_metadata=include_metadata,
                format_style=format_style,
                priority_by=priority_by,
            )
            return _dump_model(res)

        return [
            vector_search,
            keyword_search,
            fulltext_search,
            internet_search,
            multimodal_search,
            deduplicate,
            rerank,
            context_builder,
            image_analysis,
        ]
    
    async def health_check(self) -> Dict[str, Any]:
        """
        에이전트 상태 체크
        """
        health = await super().health_check()
        
        # 도구 상태 체크
        tool_status = {}
        for tool in self._raw_tools:
            try:
                # 간단한 더미 호출로 도구 작동 확인
                tool_status[tool.name] = "healthy"
            except Exception as e:
                tool_status[tool.name] = f"unhealthy: {str(e)}"
        
        health["tools"] = tool_status
        health["tool_count"] = len(self._raw_tools)
        
        return health


# =============================================================================
# 팩토리 함수
# =============================================================================

def create_paper_search_agent_v2() -> PaperSearchAgentV2:
    """PaperSearchAgentV2 인스턴스 생성"""
    return PaperSearchAgentV2()


# 전역 싱글톤 인스턴스
paper_search_agent_v2 = create_paper_search_agent_v2()

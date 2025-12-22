"""
Patent Analysis Agent V2 - Autonomous ReAct Pattern

기존 patent_analysis_agent.py의 자율형 버전:
- BaseAutonomousAgent 상속
- LangChain ReAct 패턴으로 LLM이 도구를 자율 선택
- analysis_type 파라미터 제거 (LLM이 자율 판단)
- 특허 검색/분석/비교 도구를 조합하여 복잡한 분석 수행
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List
from datetime import datetime
from loguru import logger

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseLanguageModel
from langgraph.prebuilt import create_react_agent

from app.agents.base import BaseAutonomousAgent, AgentExecutionContext, AgentCapability, AgentExecutionResult
from app.agents.base.agent_protocol import AgentMode, AgentStatus, AgentStep
from app.agents.base.agent_state import AgentStateManager

# 특허 도구 임포트
from app.tools.retrieval.patent_search_tool import PatentSearchTool
from app.tools.retrieval.patent_functional_tools import (
    PatentDiscoveryTool,
    PatentDetailTool,
    PatentLegalTool
)
from app.tools.retrieval.patent_analysis_tool import PatentAnalysisTool

from app.services.core.ai_service import ai_service


class PatentAnalysisAgentV2(BaseAutonomousAgent):
    """
    자율형 특허 분석 에이전트 V2
    
    주요 개선점:
    1. analysis_type 파라미터 제거 - LLM이 분석 유형 자동 결정
    2. LangChain ReAct 패턴으로 도구 자율 선택
    3. 복잡한 다단계 분석을 LLM이 계획하고 실행
    4. 경쟁사 비교, 트렌드 분석 등을 단일 질의로 처리
    
    사용 가능한 도구:
    - patent_search: 기본 특허 검색
    - patent_discovery: 특허 검색 + 필터링
    - patent_detail: 특허 상세 정보 조회
    - patent_legal: 법적 상태 조회
    - patent_analysis: 특허 포트폴리오 분석
    
    예시 질의:
    - "삼성전자 AI 반도체 특허를 검색해줘"
    - "삼성전자와 LG전자의 OLED 특허를 비교 분석해줘"
    - "최근 5년간 AI 특허 출원 트렌드를 분석해줘"
    """
    
    def __init__(self):
        super().__init__()

        self.name = "patent_analysis_v2"
        self.description = "자율형 특허 검색 및 분석 에이전트 (LangGraph ReAct)"
        self.version = "2.0.0"
        
        # 특허 도구 등록
        self._tools: List[BaseTool] = [
            PatentSearchTool(),
            PatentDiscoveryTool(),
            PatentDetailTool(),
            PatentLegalTool(),
            PatentAnalysisTool(),
        ]
        
        self.ai_service = ai_service

        self._system_prompt_template = (
            "당신은 특허 분석 전문 에이전트입니다.\n\n"
            "사용 가능한 도구:\n{tools}\n\n"
            "제약 조건:\n- max_iterations: {max_iterations}\n- timeout_seconds: {timeout_seconds}\n"
        )
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: AgentExecutionContext,
        mode: AgentMode = AgentMode.REACT,
    ) -> AgentExecutionResult:
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

        AgentStateManager.init_state(
            request_id=context.request_id,
            agent_name=self.name,
            query=query,
        )

        try:
            llm = await self._get_llm()

            system_prompt = self._system_prompt_template.format(
                tools=self._format_tool_descriptions(self._tools),
                max_iterations=context.max_iterations,
                timeout_seconds=context.timeout_seconds,
            )

            messages: List[BaseMessage] = [SystemMessage(content=system_prompt), HumanMessage(content=query)]
            react_agent = create_react_agent(llm, self._tools)

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
            logger.error(f"[PatentAnalysisV2] Execution failed: {e}", exc_info=True)
            AgentStateManager.add_error(str(e))
            return AgentExecutionResult(
                success=False,
                output={"answer": f"특허 분석 중 오류가 발생했습니다: {str(e)}"},
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
        """LLM 인스턴스 가져오기"""
        llm = await self.ai_service.get_model(
            provider="azure",
            model_name="gpt-4o",
            temperature=0.0,  # 특허 분석은 정확성 우선
            streaming=True,
        )
        return llm
    
    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(name="patent", description="특허 검색"),
            AgentCapability(name="analysis", description="특허 분석/비교"),
            AgentCapability(name="trend", description="트렌드 분석"),
        ]

    def _format_tool_descriptions(self, tools: List[BaseTool]) -> str:
        return "\n".join([f"- {t.name}: {t.description}" for t in tools])

    def _extract_final_answer(self, messages: List[BaseMessage]) -> str:
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and (msg.content or "").strip():
                return str(msg.content)
        return "특허 분석 결과를 찾을 수 없습니다."

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
    
    async def health_check(self) -> Dict[str, Any]:
        """에이전트 상태 체크"""
        health = await super().health_check()
        
        tool_status = {}
        for tool in self._tools:
            tool_status[tool.name] = "healthy"
        
        health["tools"] = tool_status
        health["tool_count"] = len(self._tools)
        
        return health


# =============================================================================
# 팩토리 함수
# =============================================================================

def create_patent_analysis_agent_v2() -> PatentAnalysisAgentV2:
    """PatentAnalysisAgentV2 인스턴스 생성"""
    return PatentAnalysisAgentV2()


# 전역 싱글톤
patent_analysis_agent_v2 = create_patent_analysis_agent_v2()

# 하위 호환성 Alias (기존 코드가 PatentAnalysisAgentTool을 기대하는 경우)
PatentAnalysisAgentTool = PatentAnalysisAgentV2
patent_analysis_agent_tool = patent_analysis_agent_v2

"""
Unified Presentation Agent

Quick PPT와 Template PPT를 모두 처리하는 통합 에이전트.
ReAct와 Plan-Execute 패턴을 모두 지원합니다.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from loguru import logger

try:
    from langchain_core.tools import BaseTool
    from langchain_core.messages import HumanMessage, AIMessage
except ImportError:
    from langchain_core.tools import BaseTool
    from langchain_core.messages import HumanMessage, AIMessage

from app.agents.presentation.base_agent import BaseAgent
from app.services.core.ai_service import ai_service
from app.utils.prompt_loader import load_presentation_prompt
from app.agents.presentation.ppt_generation_graph import (
    run_ppt_generation_graph,
    run_template_wizard_until_mapped,
    resume_template_wizard_build,
)

# Tools import
from app.tools.presentation.outline_generation_tool import outline_generation_tool
from app.tools.presentation.quick_pptx_builder_tool import quick_pptx_builder_tool  # Restored 2025-12-09
from app.tools.presentation.template_analyzer_tool import template_analyzer_tool
from app.tools.presentation.slide_type_matcher_tool import slide_type_matcher_tool
from app.tools.presentation.content_mapping_tool import content_mapping_tool
from app.tools.presentation.templated_pptx_builder_tool import templated_pptx_builder_tool
from app.tools.presentation.visualization_tool import visualization_tool
from app.tools.presentation.ppt_quality_validator_tool import ppt_quality_validator_tool
from app.tools.presentation.template_ppt_comparator_tool import template_ppt_comparator_tool

# AI-First Tools (신규)
from app.tools.presentation.ai_direct_mapping_tool import AIDirectMappingTool
from app.services.presentation.simple_ppt_builder import SimplePPTBuilder
from app.services.presentation.ai_ppt_builder import AIPPTBuilder, build_ppt_from_ai_mappings

# 🆕 v3.7: 동적 슬라이드 관리
from app.services.presentation.dynamic_slide_manager import DynamicSlideManager


class PresentationMode(str, Enum):
    """프레젠테이션 생성 모드"""
    QUICK = "quick"  # Quick PPT (템플릿 미적용)
    TEMPLATE = "template"  # Template PPT (템플릿 기반)


class ExecutionPattern(str, Enum):
    """실행 패턴"""
    REACT = "react"  # ReAct (Reasoning + Acting)
    PLAN_EXECUTE = "plan_execute"  # Plan-and-Execute
    TOOL_CALLING = "tool_calling"  # Tool-calling based agent loop (Phase 3)


LLM_TIMEOUT_SECONDS = 120


# ---------------------------------------------------------------------------
# Phase 0: 요청별 상태 격리 (완전 무상태화)
#
# UnifiedPresentationAgent는 singleton으로 사용되므로, 인스턴스 필드에 요청별 상태를
# 저장하면 동시 실행 시 교차 오염이 발생할 수 있습니다.
#
# 해결: ContextVar 기반으로 요청(=async task) 단위 실행 컨텍스트를 격리합니다.
# 기존 코드 변경을 최소화하기 위해, BaseAgent가 쓰는 내부 필드명들을 property로
# 오버라이드하여 컨텍스트로 라우팅합니다.
# ---------------------------------------------------------------------------


@dataclass
class _UnifiedPPTRequestContext:
    execution_id: Optional[str] = None
    start_time: Optional[datetime] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    user_id: Optional[int] = None

    # Legacy caches used for auto-injection during ReAct/tool-calling loops.
    latest_deck_spec: Any = None
    latest_mappings: Any = None
    latest_template_structure: Any = None
    latest_template_metadata: Any = None
    latest_slide_matches: Any = None


_UNIFIED_PPT_CTX: ContextVar[Optional[_UnifiedPPTRequestContext]] = ContextVar(
    "unified_ppt_request_ctx", default=None
)


class UnifiedPresentationAgent(BaseAgent):
    """
    통합 프레젠테이션 에이전트.
    
    Quick PPT와 Template PPT를 mode 파라미터로 분기하고,
    ReAct와 Plan-Execute 패턴을 pattern 파라미터로 선택합니다.
    
    Attributes:
        name: 에이전트 이름
        description: 에이전트 설명
        version: 버전
    """
    
    name: str = "unified_presentation_agent"
    description: str = "Unified agent for Quick and Template PPT generation"
    version: str = "2.0.0"
    
    def __init__(self) -> None:
        """초기화 및 모든 도구 등록"""
        super().__init__()
        
        # 모든 도구 등록
        self.tools = {
            # 공통 도구
            "outline_generation_tool": outline_generation_tool,
            "quick_pptx_builder_tool": quick_pptx_builder_tool,  # Restored 2025-12-09 for Quick PPT
            "ppt_quality_validator_tool": ppt_quality_validator_tool,
            "template_ppt_comparator_tool": template_ppt_comparator_tool,
            "visualization_tool": visualization_tool,
            
            # Template PPT 전용 도구
            "template_analyzer_tool": template_analyzer_tool,
            "slide_type_matcher_tool": slide_type_matcher_tool,
            "content_mapping_tool": content_mapping_tool,
            "templated_pptx_builder_tool": templated_pptx_builder_tool,
        }
        
        self.max_iterations = 10
        
        logger.info(
            f"🎨 {self.name} v{self.version} 초기화 완료: {len(self.tools)}개 도구 등록"
        )

    def _get_request_ctx(self) -> _UnifiedPPTRequestContext:
        """Get current request context.

        If there is no active ContextVar (e.g., during startup), we keep a
        per-instance fallback context that is *not* shared across async tasks.
        The run() method always installs a ContextVar context for real requests.
        """
        ctx = _UNIFIED_PPT_CTX.get()
        if ctx is not None:
            return ctx
        fallback = self.__dict__.get("_unified_ppt_fallback_ctx")
        if fallback is None:
            fallback = _UnifiedPPTRequestContext()
            self.__dict__["_unified_ppt_fallback_ctx"] = fallback
        return fallback

    # --- Context-backed properties (override BaseAgent mutable fields) ---
    @property
    def _execution_id(self) -> Optional[str]:  # type: ignore[override]
        return self._get_request_ctx().execution_id

    @_execution_id.setter
    def _execution_id(self, value: Optional[str]) -> None:  # type: ignore[override]
        self._get_request_ctx().execution_id = value

    @property
    def _start_time(self) -> Optional[datetime]:  # type: ignore[override]
        return self._get_request_ctx().start_time

    @_start_time.setter
    def _start_time(self, value: Optional[datetime]) -> None:  # type: ignore[override]
        self._get_request_ctx().start_time = value

    @property
    def _steps(self) -> List[Dict[str, Any]]:  # type: ignore[override]
        return self._get_request_ctx().steps

    @_steps.setter
    def _steps(self, value: List[Dict[str, Any]]) -> None:  # type: ignore[override]
        self._get_request_ctx().steps = value

    @property
    def _tools_used(self) -> List[str]:  # type: ignore[override]
        return self._get_request_ctx().tools_used

    @_tools_used.setter
    def _tools_used(self, value: List[str]) -> None:  # type: ignore[override]
        self._get_request_ctx().tools_used = value

    @property
    def _user_id(self) -> Optional[int]:
        return self._get_request_ctx().user_id

    @_user_id.setter
    def _user_id(self, value: Optional[int]) -> None:
        self._get_request_ctx().user_id = value

    @property
    def _latest_deck_spec(self) -> Any:
        return self._get_request_ctx().latest_deck_spec

    @_latest_deck_spec.setter
    def _latest_deck_spec(self, value: Any) -> None:
        self._get_request_ctx().latest_deck_spec = value

    @property
    def _latest_mappings(self) -> Any:
        return self._get_request_ctx().latest_mappings

    @_latest_mappings.setter
    def _latest_mappings(self, value: Any) -> None:
        self._get_request_ctx().latest_mappings = value

    @property
    def _latest_template_structure(self) -> Any:
        return self._get_request_ctx().latest_template_structure

    @_latest_template_structure.setter
    def _latest_template_structure(self, value: Any) -> None:
        self._get_request_ctx().latest_template_structure = value

    @property
    def _latest_template_metadata(self) -> Any:
        return self._get_request_ctx().latest_template_metadata

    @_latest_template_metadata.setter
    def _latest_template_metadata(self, value: Any) -> None:
        self._get_request_ctx().latest_template_metadata = value

    @property
    def _latest_slide_matches(self) -> Any:
        return self._get_request_ctx().latest_slide_matches

    @_latest_slide_matches.setter
    def _latest_slide_matches(self, value: Any) -> None:
        self._get_request_ctx().latest_slide_matches = value
    
    def _load_system_prompt(
        self, 
        mode: PresentationMode, 
        pattern: ExecutionPattern
    ) -> str:
        """
        모드와 패턴에 따른 시스템 프롬프트 로드.
        
        Args:
            mode: 생성 모드 (quick/template)
            pattern: 실행 패턴 (react/plan_execute)
            
        Returns:
            시스템 프롬프트 문자열
        """
        # 프롬프트 파일명 결정
        if mode == PresentationMode.QUICK:
            prompt_name = "react_agent_system"  # Quick은 ReAct만 지원
        else:  # TEMPLATE
            if pattern == ExecutionPattern.REACT:
                prompt_name = "templated_react_agent_system"
            else:
                prompt_name = "templated_plan_execute_agent_system"
        
        try:
            return load_presentation_prompt(prompt_name)
        except FileNotFoundError:
            logger.warning(f"{prompt_name}.prompt 파일을 찾을 수 없습니다. 기본 프롬프트 사용")
            return self._get_default_system_prompt(mode, pattern)
    
    def _get_default_system_prompt(
        self, 
        mode: PresentationMode,
        pattern: ExecutionPattern
    ) -> str:
        """기본 시스템 프롬프트 생성"""
        if mode == PresentationMode.QUICK:
            return """당신은 전문 프레젠테이션 생성 AI 에이전트입니다.
사용자의 요청을 분석하고, 도구를 실행하여 PPT를 생성합니다.

## 응답 형식
각 단계에서 다음 형식으로 응답하세요:

**Thought**: 현재 상황 분석
**Action**: 도구_이름
**Action Input**:
```json
{"파라미터": "값"}
```

도구 실행 결과(Observation)를 받은 후, 다음 단계로 진행하세요.
마지막에 파일 생성이 완료되면:
**Final Answer**: 결과 요약

## 필수 워크플로우 (Quick PPT) - 반드시 2개 도구 모두 실행!
1. outline_generation_tool 실행 → deck_spec 획득 (1단계)
2. templated_pptx_builder_tool 실행 → PPTX 파일 생성 (2단계 - 반드시 실행!)
3. 파일 생성 완료 후 Final Answer 출력

⚠️ 중요: outline_generation_tool 실행 후 반드시 templated_pptx_builder_tool을 호출해야 합니다!
⚠️ templated_pptx_builder_tool 호출 없이 Final Answer를 출력하면 안됩니다!"""
        
        else:  # TEMPLATE
            if pattern == ExecutionPattern.REACT:
                return """당신은 전문 템플릿 기반 프레젠테이션 생성 AI 에이전트입니다.

## 응답 형식
각 단계에서 다음 형식으로 응답하세요:

**Thought**: 현재 상황 분석
**Action**: 도구_이름
**Action Input**:
```json
{"파라미터": "값"}
```

도구 실행 결과(Observation)를 받은 후, 다음 단계로 진행하세요.
마지막에 파일 생성이 완료되면:
**Final Answer**: 결과 요약

## 필수 워크플로우 (Template PPT - ReAct) - 5단계 순서대로 실행!
1. outline_generation_tool 실행 → deck_spec 획득 (콘텐츠 슬라이드 생성)
2. template_analyzer_tool 실행 → template_structure & template_metadata 획득 (템플릿 분석)
3. slide_type_matcher_tool 실행 → slide_matches 획득 (슬라이드 유형 매칭: title→title, content→content)
4. content_mapping_tool 실행 → mappings 생성 (텍스트박스 콘텐츠 매핑)
5. templated_pptx_builder_tool 실행 → PPTX 파일 생성 (반드시 실행!)
6. 파일 생성 완료 후 Final Answer 출력

## 사용 가능한 도구
- outline_generation_tool: 컨텍스트에서 아웃라인 생성
- template_analyzer_tool: 템플릿 구조 분석 (슬라이드 역할 정보 포함)
- slide_type_matcher_tool: AI 아웃라인 슬라이드를 템플릿 슬라이드에 유형별로 매칭 (title→title, toc→toc, content→content, thanks→thanks)
- content_mapping_tool: 아웃라인 콘텐츠를 템플릿 텍스트박스에 매핑
- templated_pptx_builder_tool: 최종 PPTX 파일 생성

## 슬라이드 유형 매칭 중요성
- AI가 4개 슬라이드를 생성하고 템플릿이 10개 슬라이드라면, slide_type_matcher_tool이:
  - 제목 슬라이드 → 템플릿의 title 역할 슬라이드
  - 목차 슬라이드 → 템플릿의 toc 역할 슬라이드
  - 내용 슬라이드 → 템플릿의 content 역할 슬라이드
  - 감사 슬라이드 → 템플릿의 thanks 역할 슬라이드
  를 지능적으로 매칭합니다.

⚠️ 중요: 각 도구를 순서대로 호출하고, templated_pptx_builder_tool 호출 없이 Final Answer를 출력하지 마세요!"""
            else:  # PLAN_EXECUTE
                return """당신은 전문 템플릿 기반 프레젠테이션 생성 AI 에이전트입니다.

## 필수 워크플로우 (Template PPT - Plan-Execute)
[Planning Phase]
1. 전체 실행 계획 수립
   - Step 1: Generate outline
   - Step 2: Analyze template
   - Step 3: Map content
   - Step 4: Build PPTX

[Execution Phase]
2. 각 단계를 순차 실행하며 결과 수집

⚠️ templated_pptx_builder_tool 호출 없이 Final Answer를 출력하지 마세요!"""
    
    def _get_available_tools(self, mode: PresentationMode) -> List[str]:
        """
        모드에 따른 사용 가능 도구 목록 반환.
        
        Args:
            mode: 생성 모드
            
        Returns:
            도구 이름 리스트
        """
        if mode == PresentationMode.QUICK:
            return [
                "outline_generation_tool",
                "templated_pptx_builder_tool",
                "visualization_tool",
                "ppt_quality_validator_tool",
            ]
        else:  # TEMPLATE
            return [
                "outline_generation_tool",
                "template_analyzer_tool",
                "slide_type_matcher_tool",
                "content_mapping_tool",
                "templated_pptx_builder_tool",
                "ppt_quality_validator_tool",
            ]
    
    async def run(
        self,
        *,
        mode: str = "quick",
        pattern: str = "react",
        topic: str,
        context_text: str,
        template_id: Optional[str] = None,
        max_slides: int = 8,
        user_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        통합 에이전트 실행.
        
        Args:
            mode: 생성 모드 ("quick" | "template")
            pattern: 실행 패턴 ("react" | "plan_execute")
            topic: 발표 주제
            context_text: 컨텍스트 텍스트
            template_id: 템플릿 ID (template 모드에서만 사용)
            max_slides: 최대 슬라이드 수
            user_id: 사용자 ID (user-specific 템플릿 접근용)
            **kwargs: 추가 파라미터
            
        Returns:
            실행 결과 딕셔너리
        """
        # Phase 0: install request-scoped context (prevents cross-request state pollution)
        ctx_token = _UNIFIED_PPT_CTX.set(_UnifiedPPTRequestContext())
        try:
            # Enum 변환
            try:
                mode_enum = PresentationMode(mode)
                pattern_enum = ExecutionPattern(pattern)
            except ValueError as e:
                return {
                    "success": False,
                    "error": f"Invalid mode or pattern: {e}",
                }

            # Template 모드인데 template_id가 없으면 에러
            if mode_enum == PresentationMode.TEMPLATE and not template_id:
                return {
                    "success": False,
                    "error": "template_id is required for template mode",
                }

            # 실행 초기화 (Phase 3: allow caller-provided run_id)
            execution_id = kwargs.pop("run_id", None) or kwargs.pop("execution_id", None)
            self._init_execution(execution_id)

            # NOTE: Phase 0 statelessness: keep user_id in request context (not instance state)
            self._user_id = user_id

            logger.info(
                f"🚀 [{self.name}] 시작: mode={mode}, pattern={pattern}, "
                f"topic='{topic[:50]}', max_slides={max_slides}, user_id={user_id}"
            )

            # LangGraph 기반 고정 워크플로우(권장)를 기본 경로로 사용합니다.
            # 필요 시 `use_langgraph=False`로 레거시 루프(ReAct/Plan-Execute)로 되돌릴 수 있습니다.
            use_langgraph = bool(kwargs.pop("use_langgraph", True))
            validate = bool(kwargs.pop("validate", False))

            # Phase 3: tool_calling 패턴은 레거시 에이전트 루프를 사용합니다.
            if pattern_enum == ExecutionPattern.TOOL_CALLING:
                use_langgraph = False

            if use_langgraph:
                graph_result = await run_ppt_generation_graph(
                    mode=mode_enum.value,
                    topic=topic,
                    context_text=context_text,
                    max_slides=max_slides,
                    template_id=template_id,
                    user_id=user_id,
                    request_id=self._execution_id,
                    run_id=self._execution_id,
                    validate=validate,
                )

                # Graph에서 수집한 관측값을 BaseAgent 메타데이터에 반영
                self._steps = list(graph_result.get("steps") or [])
                self._tools_used = list(graph_result.get("tools_used") or [])
                result = graph_result
            else:
                # 패턴에 따라 레거시 루프 실행
                if pattern_enum == ExecutionPattern.TOOL_CALLING:
                    result = await self._run_tool_calling_agent(
                        mode=mode_enum,
                        topic=topic,
                        context_text=context_text,
                        template_id=template_id,
                        max_slides=max_slides,
                        **kwargs,
                    )
                elif pattern_enum == ExecutionPattern.REACT:
                    result = await self._run_react(
                        mode=mode_enum,
                        topic=topic,
                        context_text=context_text,
                        template_id=template_id,
                        max_slides=max_slides,
                        **kwargs,
                    )
                else:  # PLAN_EXECUTE
                    result = await self._run_plan_execute(
                        mode=mode_enum,
                        topic=topic,
                        context_text=context_text,
                        template_id=template_id,
                        max_slides=max_slides,
                        **kwargs,
                    )

            # 실행 종료
            return self._finalize_execution(result)
        finally:
            _UNIFIED_PPT_CTX.reset(ctx_token)

    async def _run_tool_calling_agent(
        self,
        mode: PresentationMode,
        topic: str,
        context_text: str,
        template_id: Optional[str],
        max_slides: int,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Phase 3: tool-calling based agent loop.

        This replaces fragile string parsing (Thought/Action/Action Input) with
        structured tool calls when the underlying chat model supports it.
        """

        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

        self._log_step("START", f"Tool-calling Agent 시작 (mode={mode.value})")

        # 상태 저장용 변수 (레거시 ReAct와 동일한 보조 캐시)
        self._latest_deck_spec = None
        self._latest_mappings = None
        self._latest_template_structure = None
        self._latest_template_metadata = None
        self._latest_slide_matches = None

        system_prompt = self._load_system_prompt(mode, ExecutionPattern.REACT)

        available_tool_names = self._get_available_tools(mode)
        available_tools = {name: self.tools[name] for name in available_tool_names}

        # Prefer default provider; allow override.
        provider = kwargs.pop("provider", None)
        llm = ai_service.get_chat_model(provider=provider, temperature=0.0, max_tokens=4000)
        if llm is None:
            return {"success": False, "error": "LLM is not available"}

        # Bind tools if supported; otherwise fail fast (caller can use legacy react).
        if not hasattr(llm, "bind_tools"):
            return {
                "success": False,
                "error": "Selected LLM does not support tool calling (missing bind_tools)",
            }

        llm = llm.bind_tools(list(available_tools.values()))

        user_prompt = (
            f"주제: {topic}\n"
            f"최대 슬라이드: {max_slides}\n"
            f"{'템플릿 ID: ' + template_id if template_id else ''}\n\n"
            f"컨텍스트:\n{(context_text or '')[:3000]}\n\n"
            f"위 정보를 바탕으로 {'템플릿 기반' if mode == PresentationMode.TEMPLATE else ''} PPT를 생성해주세요.\n"
        )

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

        for iteration in range(self.max_iterations):
            try:
                response = await asyncio.wait_for(
                    llm.ainvoke(
                        messages,
                        config={
                            "run_id": self._execution_id,
                            "tags": ["ppt", "tool_calling", f"mode:{mode.value}"],
                            "metadata": {
                                "mode": mode.value,
                                "template_id": template_id,
                                "max_slides": max_slides,
                            },
                        },
                    ),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

                tool_calls = getattr(response, "tool_calls", None) or []
                if tool_calls:
                    # Append the assistant message so the tool call context is preserved.
                    messages.append(response)

                    for call in tool_calls:
                        tool_name = (call.get("name") if isinstance(call, dict) else None) or ""
                        tool_args = (call.get("args") if isinstance(call, dict) else None) or {}
                        tool_call_id = (call.get("id") if isinstance(call, dict) else None) or ""

                        if not isinstance(tool_args, dict):
                            tool_args = {}

                        # Auto-inject required params (keeps parity with legacy flow)
                        if tool_name == "outline_generation_tool":
                            tool_args.setdefault("topic", topic)
                            tool_args.setdefault("context_text", context_text)
                            tool_args.setdefault("max_slides", max_slides)

                        if mode == PresentationMode.TEMPLATE:
                            if tool_name == "template_analyzer_tool" and template_id:
                                tool_args["template_id"] = template_id
                                if self._user_id:
                                    tool_args.setdefault("user_id", self._user_id)
                            if tool_name == "templated_pptx_builder_tool" and template_id:
                                tool_args["template_id"] = template_id
                                if self._user_id:
                                    tool_args.setdefault("user_id", self._user_id)

                        if tool_name in ["quick_pptx_builder_tool", "templated_pptx_builder_tool", "content_mapping_tool"]:
                            if self._latest_deck_spec:
                                if tool_name == "content_mapping_tool":
                                    tool_args.setdefault("outline", self._latest_deck_spec)
                                else:
                                    tool_args.setdefault("deck_spec", self._latest_deck_spec)

                        if tool_name == "templated_pptx_builder_tool":
                            if self._latest_mappings:
                                tool_args.setdefault("mappings", self._latest_mappings)
                            if self._latest_slide_matches:
                                tool_args.setdefault("slide_matches", self._latest_slide_matches)

                        if tool_name == "content_mapping_tool":
                            if self._latest_template_structure:
                                tool_args.setdefault("template_structure", self._latest_template_structure)
                            if self._latest_slide_matches:
                                tool_args.setdefault("slide_matches", self._latest_slide_matches)

                        if tool_name == "slide_type_matcher_tool":
                            if self._latest_deck_spec:
                                tool_args.setdefault("outline", self._latest_deck_spec)
                            if self._latest_template_metadata:
                                tool_args.setdefault("template_metadata", self._latest_template_metadata)

                        self._log_step("ACTION", tool_name, {"input": tool_args})
                        observation = await self._execute_tool(tool_name, tool_args)

                        # Cache important artifacts
                        if isinstance(observation, dict):
                            if "deck_spec" in observation:
                                self._latest_deck_spec = observation["deck_spec"]
                            elif "deck" in observation:
                                self._latest_deck_spec = observation["deck"]
                            if "mappings" in observation:
                                self._latest_mappings = observation["mappings"]
                            if "template_structure" in observation:
                                self._latest_template_structure = observation["template_structure"]
                            if tool_name == "template_analyzer_tool":
                                if observation.get("template_metadata"):
                                    self._latest_template_metadata = observation.get("template_metadata")
                                elif observation.get("template_structure", {}).get("slides"):
                                    self._latest_template_metadata = {"slides": observation["template_structure"]["slides"]}
                            if "slide_matches" in observation:
                                self._latest_slide_matches = observation["slide_matches"]

                        self._tools_used.append(tool_name)
                        self._log_step(
                            "OBSERVATION",
                            json.dumps(observation, ensure_ascii=False)[:500],
                            metadata=observation if isinstance(observation, dict) else {"raw": str(observation)},
                        )

                        # Send tool result back
                        messages.append(
                            ToolMessage(
                                content=json.dumps(observation, ensure_ascii=False),
                                tool_call_id=tool_call_id or f"{tool_name}:{iteration}",
                            )
                        )

                        # Early exit if builder succeeded
                        if tool_name in ("templated_pptx_builder_tool", "quick_pptx_builder_tool"):
                            if isinstance(observation, dict) and observation.get("success"):
                                file_path = observation.get("file_path")
                                file_name = observation.get("file_name") or observation.get("filename")
                                slide_count = observation.get("slide_count", 0)
                                return {
                                    "success": True,
                                    "file_path": file_path,
                                    "file_name": file_name,
                                    "slide_count": slide_count,
                                    "final_answer": f"파일 생성이 완료되었습니다: {file_name}",
                                    "iterations": iteration + 1,
                                }

                    continue

                # No tool calls: treat as final.
                final_text = getattr(response, "content", None) or str(response)
                self._log_step("FINAL_ANSWER", final_text)
                file_path, file_name, slide_count = self._extract_file_info_from_steps()
                if not file_path:
                    return {
                        "success": False,
                        "error": "Tool-calling completed without generating a PPT file (no builder tool call)",
                        "file_path": None,
                        "file_name": None,
                        "slide_count": 0,
                        "final_answer": final_text,
                        "iterations": iteration + 1,
                    }
                return {
                    "success": True if file_path else False,
                    "file_path": file_path,
                    "file_name": file_name,
                    "slide_count": slide_count,
                    "final_answer": final_text,
                    "iterations": iteration + 1,
                }

            except asyncio.TimeoutError:
                logger.error(f"❌ [{self.name}] LLM 타임아웃 (tool_calling)")
                return {"success": False, "error": "LLM timeout"}
            except Exception as e:
                logger.error(f"❌ [{self.name}] tool_calling 실행 실패: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Maximum iterations exceeded"}
    
    async def _run_react(
        self,
        mode: PresentationMode,
        topic: str,
        context_text: str,
        template_id: Optional[str],
        max_slides: int,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        ReAct 패턴 실행.
        
        Thought → Action → Observation 루프를 반복하며 PPT를 생성합니다.
        """
        self._log_step("START", f"ReAct 패턴 시작 (mode={mode.value})")
        
        # 상태 저장용 변수
        self._latest_deck_spec = None
        self._latest_mappings = None
        self._latest_template_structure = None
        self._latest_template_metadata = None  # 전체 템플릿 메타데이터 (slides 포함)
        self._latest_slide_matches = None  # slide_type_matcher_tool 결과
        
        # 시스템 프롬프트 로드
        system_prompt = self._load_system_prompt(mode, ExecutionPattern.REACT)
        
        # 사용 가능 도구 필터링
        available_tool_names = self._get_available_tools(mode)
        available_tools = {
            name: self.tools[name] 
            for name in available_tool_names
        }
        
        # 도구 설명 생성
        tools_description = self._format_tools_description(available_tools)
        
        # 초기 프롬프트
        user_prompt = f"""
주제: {topic}
최대 슬라이드: {max_slides}
{"템플릿 ID: " + template_id if template_id else ""}

컨텍스트:
{context_text[:3000]}

위 정보를 바탕으로 {'템플릿 기반' if mode == PresentationMode.TEMPLATE else ''} PPT를 생성해주세요.
"""
        
        conversation = [
            {"role": "system", "content": system_prompt + "\n\n" + tools_description},
            {"role": "user", "content": user_prompt},
        ]
        
        # ReAct 루프
        for iteration in range(self.max_iterations):
            logger.info(f"🔄 [{self.name}] Iteration {iteration + 1}/{self.max_iterations}")
            
            try:
                # LLM 호출
                response_data = await asyncio.wait_for(
                    ai_service.chat_completion(
                        messages=conversation,
                        provider="bedrock",
                        temperature=0.0,
                        max_tokens=4000,
                        run_config={
                            "run_id": self._execution_id,
                            "tags": ["ppt", "legacy_react", f"mode:{mode.value}"],
                            "metadata": {
                                "mode": mode.value,
                                "template_id": template_id,
                                "max_slides": max_slides,
                            },
                        },
                    ),
                    timeout=LLM_TIMEOUT_SECONDS,
                )
                response = response_data["response"]
                
                # 응답 파싱
                parsed = self._parse_agent_response(response)
                
                # Thought 로깅
                if parsed["thought"]:
                    self._log_step("THOUGHT", parsed["thought"])
                
                # Final Answer 확인
                if parsed["final_answer"]:
                    # 필수 도구 사용 여부 확인
                    required_tool = "templated_pptx_builder_tool"  # Both modes use same builder now
                    if required_tool not in self._tools_used:
                        logger.warning(f"⚠️ [{self.name}] 필수 도구 {required_tool} 미사용 감지. 재시도/자동 실행 시도")
                        await self._handle_missing_required_tool(
                            conversation=conversation,
                            response=response,
                            required_tool=required_tool,
                            mode=mode,
                            topic=topic,
                            max_slides=max_slides,
                            template_id=template_id,
                        )
                        continue

                    self._log_step("FINAL_ANSWER", parsed["final_answer"])
                    
                    # 파일 정보 추출
                    file_path, file_name, slide_count = self._extract_file_info_from_steps()
                    
                    return {
                        "success": True if file_path else False,
                        "file_path": file_path,
                        "file_name": file_name,
                        "slide_count": slide_count,
                        "final_answer": parsed["final_answer"],
                        "iterations": iteration + 1,
                    }
                
                # Action 실행
                if parsed["action"] and parsed["action_input"] is not None:
                    action_name = parsed["action"]
                    action_input = parsed["action_input"]
                    
                    # Template 모드에서 자동 파라미터 주입
                    if mode == PresentationMode.TEMPLATE:
                        if action_name == "template_analyzer_tool" and template_id:
                            action_input["template_id"] = template_id
                            # user_id 자동 주입
                            if self._user_id:
                                action_input["user_id"] = self._user_id
                        elif action_name == "templated_pptx_builder_tool" and template_id:
                            action_input["template_id"] = template_id
                            # user_id 자동 주입
                            if self._user_id:
                                action_input["user_id"] = self._user_id
                    
                    # outline_generation_tool에 필수 파라미터 자동 주입
                    if action_name == "outline_generation_tool":
                        if "topic" not in action_input or not action_input.get("topic"):
                            action_input["topic"] = topic
                        if "context_text" not in action_input or not action_input.get("context_text"):
                            action_input["context_text"] = context_text
                        if "max_slides" not in action_input:
                            action_input["max_slides"] = max_slides

                    # deck_spec 자동 주입 (Quick/Template 공통)
                    # quick_pptx_builder_tool 추가됨 (2025-12-09 복원)
                    if action_name in ["quick_pptx_builder_tool", "templated_pptx_builder_tool", "content_mapping_tool"]:
                        # deck_spec이 없거나 비어있고, 메모리에 저장된 deck_spec이 있는 경우
                        if self._latest_deck_spec:
                            if action_name == "content_mapping_tool":
                                if "outline" not in action_input or not action_input.get("outline"):
                                    action_input["outline"] = self._latest_deck_spec
                                    logger.info(f"💉 [{self.name}] deck_spec(outline) 자동 주입 완료")
                            else:
                                if "deck_spec" not in action_input or not action_input.get("deck_spec"):
                                    action_input["deck_spec"] = self._latest_deck_spec
                                    logger.info(f"💉 [{self.name}] deck_spec 자동 주입 완료")

                    # mappings 자동 주입 (Template 전용)
                    if action_name == "templated_pptx_builder_tool":
                        if ("mappings" not in action_input or not action_input.get("mappings")) and self._latest_mappings:
                            action_input["mappings"] = self._latest_mappings
                            logger.info(f"💉 [{self.name}] mappings 자동 주입 완료")
                        # slide_matches 자동 주입 (선택적)
                        if ("slide_matches" not in action_input or not action_input.get("slide_matches")) and self._latest_slide_matches:
                            action_input["slide_matches"] = self._latest_slide_matches
                            logger.info(f"💉 [{self.name}] slide_matches 자동 주입 완료")
                            
                    # template_structure 자동 주입 (Template 전용)
                    if action_name == "content_mapping_tool":
                        if ("template_structure" not in action_input or not action_input.get("template_structure")) and self._latest_template_structure:
                            action_input["template_structure"] = self._latest_template_structure
                            logger.info(f"💉 [{self.name}] template_structure 자동 주입 완료")
                        # slide_matches 자동 주입
                        if ("slide_matches" not in action_input or not action_input.get("slide_matches")) and self._latest_slide_matches:
                            action_input["slide_matches"] = self._latest_slide_matches
                            logger.info(f"💉 [{self.name}] slide_matches 자동 주입 완료 (content_mapping)")
                    
                    # slide_type_matcher_tool 자동 주입 (Template 전용)
                    if action_name == "slide_type_matcher_tool":
                        if ("outline" not in action_input or not action_input.get("outline")) and self._latest_deck_spec:
                            action_input["outline"] = self._latest_deck_spec
                            logger.info(f"💉 [{self.name}] outline 자동 주입 완료 (slide_type_matcher)")
                        if ("template_metadata" not in action_input or not action_input.get("template_metadata")) and self._latest_template_metadata:
                            action_input["template_metadata"] = self._latest_template_metadata
                            logger.info(f"💉 [{self.name}] template_metadata 자동 주입 완료")
                    
                    self._log_step("ACTION", f"{action_name}", {"input": action_input})
                    
                    # 도구 실행
                    observation = await self._execute_tool(action_name, action_input)
                    
                    # 🚨 도구 실행 실패 감지 및 복구
                    if isinstance(observation, dict) and observation.get("success") == False:
                        error_msg = observation.get("error", "알 수 없는 오류")
                        logger.error(f"❌ [{self.name}] 도구 실행 실패: {action_name} - {error_msg}")
                        
                        # 에러 정보를 대화에 추가하고 LLM이 대처하도록 유도
                        conversation.append({"role": "assistant", "content": response})
                        conversation.append({
                            "role": "user",
                            "content": f"⚠️ 도구 실행 실패: {action_name}\n에러: {error_msg}\n\n다른 방법을 시도하거나, 필요한 파라미터를 다시 확인해주세요."
                        })
                        continue
                    
                    # 결과 캡처 (outline_generation_tool의 deck도 캡처)
                    if isinstance(observation, dict):
                        if "deck_spec" in observation:
                            self._latest_deck_spec = observation["deck_spec"]
                        elif "deck" in observation:  # 레거시 호환
                            self._latest_deck_spec = observation["deck"]
                        if "mappings" in observation:
                            self._latest_mappings = observation["mappings"]
                        if "template_structure" in observation:
                            self._latest_template_structure = observation["template_structure"]
                        # template_analyzer_tool에서 전체 메타데이터 캡처
                        if action_name == "template_analyzer_tool":
                            # template_metadata 캡처 (slide_type_matcher용)
                            if observation.get("template_metadata"):
                                self._latest_template_metadata = observation.get("template_metadata")
                                logger.info(f"💉 [{self.name}] template_metadata 캡처 완료")
                            elif observation.get("template_structure", {}).get("slides"):
                                # template_structure 안에 slides가 있으면 그것을 사용
                                self._latest_template_metadata = {"slides": observation["template_structure"]["slides"]}
                                logger.info(f"💉 [{self.name}] template_structure.slides에서 template_metadata 캡처")
                        # slide_type_matcher_tool 결과 캡처
                        if "slide_matches" in observation:
                            self._latest_slide_matches = observation["slide_matches"]
                    
                    self._log_step("OBSERVATION", json.dumps(observation, ensure_ascii=False)[:500], metadata=observation)
                    self._tools_used.append(action_name)

                    # 🚀 [최적화] 파일 생성 도구가 성공했다면 즉시 종료 (LLM 요약 생략)
                    if action_name == "templated_pptx_builder_tool":
                        if isinstance(observation, dict) and observation.get("success"):
                            logger.info(f"🚀 [{self.name}] 파일 생성 성공 감지 - 즉시 종료")
                            file_path = observation.get("file_path")
                            file_name = observation.get("file_name") or observation.get("filename")
                            slide_count = observation.get("slide_count", 0)
                            
                            return {
                                "success": True,
                                "file_path": file_path,
                                "file_name": file_name,
                                "slide_count": slide_count,
                                "final_answer": f"파일 생성이 완료되었습니다: {file_name}",
                                "iterations": iteration + 1,
                            }
                    
                    # Conversation에 추가
                    conversation.append({"role": "assistant", "content": response})
                    
                    # 다음 단계 안내 메시지 추가
                    next_step_hint = ""
                    if action_name == "outline_generation_tool" and mode == PresentationMode.QUICK:
                        next_step_hint = "\n\n⚠️ 다음 단계: deck_spec을 사용하여 templated_pptx_builder_tool을 호출하세요."
                    elif action_name == "outline_generation_tool" and mode == PresentationMode.TEMPLATE:
                        next_step_hint = "\n\n⚠️ 다음 단계: template_analyzer_tool을 호출하여 템플릿 구조를 분석하세요."
                    elif action_name == "template_analyzer_tool":
                        next_step_hint = "\n\n⚠️ 다음 단계: slide_type_matcher_tool을 호출하여 AI 슬라이드와 템플릿 슬라이드를 유형별로 매칭하세요."
                    elif action_name == "slide_type_matcher_tool":
                        next_step_hint = "\n\n⚠️ 다음 단계: content_mapping_tool을 호출하여 아웃라인 콘텐츠를 템플릿 텍스트박스에 매핑하세요."
                    elif action_name == "content_mapping_tool":
                        next_step_hint = "\n\n⚠️ 다음 단계: templated_pptx_builder_tool을 호출하여 최종 PPTX 파일을 생성하세요."
                    
                    conversation.append({
                        "role": "user", 
                        "content": f"**Observation**: {json.dumps(observation, ensure_ascii=False)}{next_step_hint}"
                    })

                    # Quick 모드에서 outline 생성 직후 Builder를 자동 실행하여 중간 정지 방지
                    if (
                        mode == PresentationMode.QUICK
                        and action_name == "outline_generation_tool"
                        and "templated_pptx_builder_tool" not in self._tools_used
                    ):
                        auto_executed, auto_tool, auto_result = await self._maybe_autorun_required_tool(
                            required_tool="templated_pptx_builder_tool",
                            conversation=conversation,
                            template_id=template_id,
                            mode=mode,
                        )

                        if auto_executed and auto_tool == "templated_pptx_builder_tool":
                            if isinstance(auto_result, dict) and auto_result.get("success"):
                                file_path = auto_result.get("file_path")
                                file_name = auto_result.get("file_name") or auto_result.get("filename")
                                slide_count = auto_result.get("slide_count", 0)

                                return {
                                    "success": True,
                                    "file_path": file_path,
                                    "file_name": file_name,
                                    "slide_count": slide_count,
                                    "final_answer": f"파일 생성이 완료되었습니다: {file_name}",
                                    "iterations": iteration + 1,
                                }
                            else:
                                # 자동 실행 도중 오류가 난 경우, LLM이 후속 조치를 안내하도록 다음 루프로 진행
                                continue
                else:
                    # Action 없음 - 구체적인 안내 제공
                    logger.warning(f"❌ [{self.name}] Action 파싱 실패. 응답 미리보기: {response[:200]}")
                    conversation.append({"role": "assistant", "content": response})
                    
                    # 현재 단계에 따른 구체적인 안내
                    if mode == PresentationMode.QUICK:
                        if "outline_generation_tool" not in self._tools_used:
                            hint = "**Action**: outline_generation_tool\n**Action Input**:\n```json\n{}\n```"
                        else:
                            hint = "**Action**: templated_pptx_builder_tool\n**Action Input**:\n```json\n{\"deck_spec\": {}}\n```"
                    else:  # TEMPLATE
                        if "outline_generation_tool" not in self._tools_used:
                            hint = "**Action**: outline_generation_tool\n**Action Input**:\n```json\n{}\n```"
                        elif "template_analyzer_tool" not in self._tools_used:
                            hint = f"**Action**: template_analyzer_tool\n**Action Input**:\n```json\n{{\"template_id\": \"{template_id}\"}}\n```"
                        elif "content_mapping_tool" not in self._tools_used:
                            hint = "**Action**: content_mapping_tool\n**Action Input**:\n```json\n{\"outline\": {}, \"template_structure\": {}}\n```"
                        else:
                            hint = "**Action**: templated_pptx_builder_tool\n**Action Input**:\n```json\n{\"deck_spec\": {}, \"template_id\": \"\", \"mappings\": []}\n```"
                    
                    conversation.append({
                        "role": "user",
                        "content": f"⚠️ Action 형식이 올바르지 않습니다. 다음 형식으로 응답해주세요:\n\n{hint}"
                    })
            
            except asyncio.TimeoutError:
                logger.error(f"❌ [{self.name}] LLM 타임아웃")
                return {
                    "success": False,
                    "error": "LLM timeout",
                }
            except Exception as e:
                logger.error(f"❌ [{self.name}] 실행 실패: {e}")
                return {
                    "success": False,
                    "error": str(e),
                }
        
        # 최대 반복 초과
        logger.warning(f"⚠️ [{self.name}] 최대 반복 횟수 초과")
        return {
            "success": False,
            "error": "Maximum iterations exceeded",
        }
    
    async def _run_plan_execute(
        self,
        mode: PresentationMode,
        topic: str,
        context_text: str,
        template_id: Optional[str],
        max_slides: int,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Plan-and-Execute 패턴 실행.
        
        1. Planning: 전체 실행 계획 수립
        2. Execution: 단계별 도구 실행
        3. Replan: 필요시 재계획 (Optional)
        """
        self._log_step("START", f"Plan-Execute 패턴 시작 (mode={mode.value})")
        
        # 시스템 프롬프트 로드
        system_prompt = self._load_system_prompt(mode, ExecutionPattern.PLAN_EXECUTE)
        
        # 사용 가능 도구
        available_tool_names = self._get_available_tools(mode)
        available_tools = {
            name: self.tools[name] 
            for name in available_tool_names
        }
        
        tools_description = self._format_tools_description(available_tools)
        
        # === Phase 1: Planning ===
        planning_prompt = f"""
다음 정보를 바탕으로 PPT 생성 계획을 수립해주세요:

주제: {topic}
최대 슬라이드: {max_slides}
{"템플릿 ID: " + template_id if template_id else ""}
모드: {mode.value}

컨텍스트:
{context_text[:2000]}

실행 가능한 도구:
{tools_description}

**계획을 JSON 형식으로 작성해주세요:**
```json
{{
  "steps": [
    {{"step": 1, "tool": "outline_generation_tool", "description": "아웃라인 생성"}},
    {{"step": 2, "tool": "...", "description": "..."}}
  ]
}}
```
"""
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": planning_prompt}
            ]

            run_config = {
                "run_id": self._execution_id,
                "tags": ["ppt", "legacy_plan_execute", f"mode:{mode.value}", "phase:planning"],
                "metadata": {
                    "mode": mode.value,
                    "template_id": template_id,
                    "max_slides": max_slides,
                },
            }
            plan_response_data = await asyncio.wait_for(
                ai_service.chat_completion(
                    messages=messages,
                    provider="bedrock",
                    temperature=0.0,
                    max_tokens=2000,
                    run_config=run_config,
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            plan_response = plan_response_data["response"]
            
            # 계획 파싱
            plan = self._parse_plan(plan_response)
            self._log_step("PLAN", json.dumps(plan, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 계획 수립 실패: {e}")
            return {
                "success": False,
                "error": f"Planning failed: {e}",
            }
        
        # === Phase 2: Execution ===
        execution_results = {}
        
        for step_info in plan.get("steps", []):
            step_num = step_info.get("step")
            tool_name = step_info.get("tool")
            description = step_info.get("description", "")
            
            logger.info(f"📍 [{self.name}] Step {step_num}: {tool_name} - {description}")
            
            # 도구 입력 준비
            tool_input = self._prepare_tool_input(
                tool_name=tool_name,
                mode=mode,
                topic=topic,
                context_text=context_text,
                template_id=template_id,
                max_slides=max_slides,
                execution_results=execution_results,
            )
            
            # 도구 실행
            self._log_step("ACTION", f"Step {step_num}: {tool_name}", {"input": tool_input})
            
            result = await self._execute_tool(tool_name, tool_input)
            
            self._log_step("OBSERVATION", json.dumps(result, ensure_ascii=False)[:500], metadata=result)
            self._tools_used.append(tool_name)
            
            # 결과 저장
            execution_results[tool_name] = result
            
            # 실패 시 중단
            if isinstance(result, dict) and not result.get("success", True):
                logger.error(f"❌ [{self.name}] Step {step_num} 실패: {result.get('error')}")
                return {
                    "success": False,
                    "error": f"Step {step_num} failed: {result.get('error')}",
                    "plan": plan,
                    "execution_results": execution_results,
                }
        
        # === Phase 3: Result ===
        # 최종 파일 정보 추출
        file_path, file_name, slide_count = self._extract_file_info_from_steps()
        
        self._log_step("FINAL_ANSWER", f"파일 생성 완료: {file_name}")
        
        return {
            "success": True if file_path else False,
            "file_path": file_path,
            "file_name": file_name,
            "slide_count": slide_count,
            "plan": plan,
            "execution_results": execution_results,
        }
    
    def _format_tools_description(self, tools: Dict[str, BaseTool]) -> str:
        """도구 설명 포맷팅"""
        descriptions = []
        for name, tool in tools.items():
            desc = f"- **{name}**: {tool.description}"
            descriptions.append(desc)
        return "\n".join(descriptions)
    
    def _parse_plan(self, plan_response: str) -> Dict[str, Any]:
        """계획 응답에서 JSON 추출"""
        try:
            # JSON 코드 블록 추출
            if "```json" in plan_response:
                json_str = plan_response.split("```json")[1].split("```")[0]
            elif "```" in plan_response:
                json_str = plan_response.split("```")[1].split("```")[0]
            else:
                json_str = plan_response
            
            return json.loads(json_str.strip())
        except Exception as e:
            logger.warning(f"계획 파싱 실패: {e}. 기본 계획 사용")
            # 기본 계획 반환
            return {
                "steps": [
                    {"step": 1, "tool": "outline_generation_tool", "description": "아웃라인 생성"},
                    {"step": 2, "tool": "templated_pptx_builder_tool", "description": "PPTX 생성"},
                ]
            }
    
    def _prepare_tool_input(
        self,
        tool_name: str,
        mode: PresentationMode,
        topic: str,
        context_text: str,
        template_id: Optional[str],
        max_slides: int,
        execution_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """도구 입력 자동 준비"""
        
        if tool_name == "outline_generation_tool":
            return {
                "context_text": context_text,
                "topic": topic,
                "max_slides": max_slides,
                "presentation_type": "general",
            }
        
        elif tool_name == "templated_pptx_builder_tool" and mode == PresentationMode.QUICK:
            outline_result = execution_results.get("outline_generation_tool", {})
            deck_spec = outline_result.get("deck_spec", {})
            return {
                "deck_spec": deck_spec,
            }
        
        elif tool_name == "template_analyzer_tool":
            result = {
                "template_id": template_id,
            }
            # user_id 주입
            if self._user_id:
                result["user_id"] = self._user_id
            return result
        
        elif tool_name == "content_mapping_tool":
            outline_result = execution_results.get("outline_generation_tool", {})
            template_result = execution_results.get("template_analyzer_tool", {})
            return {
                "outline": outline_result.get("deck_spec", {}),
                "template_structure": template_result.get("template_structure", {}),
            }
        
        elif tool_name == "templated_pptx_builder_tool":
            outline_result = execution_results.get("outline_generation_tool", {})
            mapping_result = execution_results.get("content_mapping_tool", {})
            result = {
                "deck_spec": outline_result.get("deck_spec", {}),
                "template_id": template_id,
                "mappings": mapping_result.get("mappings", []),
            }
            # user_id 주입
            if self._user_id:
                result["user_id"] = self._user_id
            return result
        
        elif tool_name == "ppt_quality_validator_tool":
            # 이전 단계에서 생성된 파일 경로 추출
            file_path, _, _ = self._extract_file_info_from_steps()
            return {
                "file_path": file_path,
            }
        
        else:
            return {}

    async def _handle_missing_required_tool(
        self,
        *,
        conversation: List[Dict[str, str]],
        response: str,
        required_tool: str,
        mode: PresentationMode,
        topic: str,
        max_slides: int,
        template_id: Optional[str],
    ) -> None:
        """필수 도구 미사용 시 자동 실행 또는 구체적 가이드를 제공."""

        # LLM의 응답을 대화 히스토리에 반영
        conversation.append({"role": "assistant", "content": response})

        # 자동 실행 가능한 경우 시도
        auto_executed, _, _ = await self._maybe_autorun_required_tool(
            required_tool=required_tool,
            conversation=conversation,
            template_id=template_id,
            mode=mode,
        )
        if auto_executed:
            return

        # 자동 실행이 불가능하면 구체적 가이드를 제공
        if "outline_generation_tool" not in self._tools_used:
            guide = f"""⚠️ 오류: 아직 도구를 실행하지 않았습니다.

먼저 outline_generation_tool을 실행하세요:

**Thought**: 아웃라인 생성
**Action**: outline_generation_tool
**Action Input**:
```json
{{"context_text": "...", "topic": "{topic}", "max_slides": {max_slides}}}
```"""
        else:
            if required_tool == "templated_pptx_builder_tool" and mode == PresentationMode.QUICK:
                action_template = """**Thought**: PPT 파일 생성
**Action**: templated_pptx_builder_tool
**Action Input**:
```json
{{"deck_spec": {{}}}}
```"""
            else:
                action_template = f"""**Thought**: 템플릿 기반 PPT 파일 생성
**Action**: templated_pptx_builder_tool
**Action Input**:
```json
{{"deck_spec": {{}}, "mappings": [], "template_id": "{template_id or ''}"}}
```"""

            guide = f"""⚠️ 오류: {required_tool}을 아직 실행하지 않았습니다.

이전 단계의 결과를 사용하여 아래 형식으로 호출하세요.
deck_spec이 너무 길다면 빈 객체로 보내도 됩니다 (시스템이 자동으로 주입합니다):

{action_template}"""

        conversation.append({"role": "user", "content": guide})

    async def _maybe_autorun_required_tool(
        self,
        *,
        required_tool: str,
        conversation: List[Dict[str, str]],
        template_id: Optional[str],
        mode: PresentationMode = PresentationMode.QUICK,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """필수 도구(또는 선행 도구) 자동 실행을 시도하고 성공 여부를 반환."""

        tool_to_run = None
        action_input = None

        if mode == PresentationMode.QUICK:
            if required_tool == "templated_pptx_builder_tool" and self._latest_deck_spec:
                tool_to_run = "templated_pptx_builder_tool"
                action_input = {"deck_spec": self._latest_deck_spec}

        elif mode == PresentationMode.TEMPLATE:
            # Template Mode: 의존성 체인 확인 및 순차적 자동 실행
            
            # 1. Template Analyzer (아직 실행 안 됨)
            if "template_analyzer_tool" not in self._tools_used and template_id:
                tool_to_run = "template_analyzer_tool"
                action_input = {"template_id": template_id}
                # user_id 주입
                if self._user_id:
                    action_input["user_id"] = self._user_id
            
            # 2. Content Mapping (아직 실행 안 됨, 선행 조건 만족)
            elif "content_mapping_tool" not in self._tools_used:
                if self._latest_deck_spec and self._latest_template_structure:
                    tool_to_run = "content_mapping_tool"
                    action_input = {
                        "outline": self._latest_deck_spec,
                        "template_structure": self._latest_template_structure
                    }
            
            # 3. Final Builder (아직 실행 안 됨, 선행 조건 만족)
            elif required_tool == "templated_pptx_builder_tool":
                if self._latest_deck_spec and self._latest_mappings and template_id:
                    tool_to_run = "templated_pptx_builder_tool"
                    action_input = {
                        "deck_spec": self._latest_deck_spec,
                        "mappings": self._latest_mappings,
                        "template_id": template_id
                    }
                    # user_id 주입
                    if self._user_id:
                        action_input["user_id"] = self._user_id

        if not tool_to_run or not action_input:
            logger.info(
                "⚙️ [%s] 자동 실행 불가 - 필요한 데이터가 없거나 이미 실행됨 (mode=%s, required=%s)",
                self.name,
                mode,
                required_tool,
            )
            return False, None, None

        logger.info("🤖 [%s] 도구 %s 자동 실행", self.name, tool_to_run)

        self._log_step(
            "ACTION",
            f"{tool_to_run} (auto)",
            {"input": action_input, "auto": True},
        )

        observation = await self._execute_tool(tool_to_run, action_input)

        if isinstance(observation, dict):
            if "deck_spec" in observation:
                self._latest_deck_spec = observation["deck_spec"]
            if "mappings" in observation:
                self._latest_mappings = observation["mappings"]
            if "template_structure" in observation:
                self._latest_template_structure = observation["template_structure"]

        self._log_step(
            "OBSERVATION",
            json.dumps(observation, ensure_ascii=False)[:500],
            metadata=observation,
        )
        self._tools_used.append(tool_to_run)

        # 🚀 [최적화] 자동 실행된 도구가 파일 생성 도구라면 즉시 종료 여부 확인
        if tool_to_run in ["quick_pptx_builder_tool", "templated_pptx_builder_tool"]:
            if isinstance(observation, dict) and observation.get("success"):
                logger.info(f"🚀 [{self.name}] 자동 실행으로 파일 생성 성공 - 즉시 종료 플래그 설정")
                # 여기서 True를 반환하면 호출자(_handle_missing_required_tool)가 리턴함.
                # 하지만 호출자는 void를 리턴하므로, 상위 루프(run_react)에서 이를 감지할 방법이 필요함.
                # _handle_missing_required_tool은 void 반환이므로, 여기서 직접 종료할 수 없음.
                # 대신, conversation에 "Final Answer"를 유도하는 메시지를 넣는 기존 로직 유지하되,
                # 다음 루프에서 LLM이 바로 Final Answer를 내놓도록 유도.
                # 더 강력하게는, 여기서 예외를 던져서 상위에서 잡거나, 상태를 변경해야 함.
                # 하지만 구조상 복잡하므로, 일단 LLM에게 강력한 힌트를 주는 것으로 유지.
                pass

        observation_preview = json.dumps(observation, ensure_ascii=False)
        if len(observation_preview) > 1500:
            observation_preview = observation_preview[:1500] + "..."

        # 다음 단계 안내 메시지
        next_instruction = "이제 다음 단계를 진행하세요."
        if tool_to_run == "templated_pptx_builder_tool" or tool_to_run == "quick_pptx_builder_tool":
            next_instruction = "이제 결과를 요약하고 Final Answer를 출력하세요. 파일 경로와 파일명을 명시하세요."

        conversation.append(
            {
                "role": "user",
                "content": (
                    f"✅ 시스템이 자동으로 {tool_to_run}을 실행했습니다.\n"
                    f"**Observation**: {observation_preview}\n"
                    f"{next_instruction}"
                ),
            }
        )

        return True, tool_to_run, observation

    # =========================================================================
    # UI 편집 경로 지원 메서드 (Agent 아키텍처 통합)
    # =========================================================================
    
    async def generate_content_for_template(
        self,
        template_id: str,
        user_query: str,
        context: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        use_rag: bool = True,
        use_ai_first: bool = True,  # 🆕 AI-First 모드 (기본값: True)
    ) -> Dict[str, Any]:
        try:
            _UNIFIED_PPT_CTX.get()
            has_ctx = True
        except LookupError:
            has_ctx = False

        if has_ctx:
            return await self._generate_content_for_template_impl(
                template_id=template_id,
                user_query=user_query,
                context=context,
                user_id=user_id,
                session_id=session_id,
                container_ids=container_ids,
                use_rag=use_rag,
                use_ai_first=use_ai_first,
            )

        ctx_token = _UNIFIED_PPT_CTX.set(_UnifiedPPTRequestContext())
        try:
            return await self._generate_content_for_template_impl(
                template_id=template_id,
                user_query=user_query,
                context=context,
                user_id=user_id,
                session_id=session_id,
                container_ids=container_ids,
                use_rag=use_rag,
                use_ai_first=use_ai_first,
            )
        finally:
            _UNIFIED_PPT_CTX.reset(ctx_token)

    async def _generate_content_for_template_impl(
        self,
        template_id: str,
        user_query: str,
        context: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        use_rag: bool = True,
        use_ai_first: bool = True,  # 🆕 AI-First 모드 (기본값: True)
    ) -> Dict[str, Any]:
        """
        UI 편집용 콘텐츠 생성 (Agent 통제 하에 실행).
        
        use_ai_first=True (기본): AI-First 파이프라인
        - 단일 AI 호출로 모든 element_id ↔ content 매핑 생성
        - 간단하고 정확한 결과
        
        use_ai_first=False: 기존 4-Tool 파이프라인
        - template_analyzer → outline_generation → slide_type_matcher → content_mapping
        
        Args:
            template_id: 템플릿 ID
            user_query: 사용자 입력 주제/질의
            context: 기본 컨텍스트
            user_id: 사용자 ID
            session_id: 채팅 세션 ID (RAG용)
            container_ids: RAG 검색 범위
            use_rag: RAG 검색 활성화 여부
            use_ai_first: AI-First 모드 사용 여부 (기본값: True)
            
        Returns:
            UI 편집 가능한 슬라이드 콘텐츠 구조
        """
        logger.info(
            f"🎨 [{self.name}] 콘텐츠 생성 시작: template={template_id}, "
            f"query='{user_query[:50]}', use_rag={use_rag}, use_ai_first={use_ai_first}"
        )
        
        self._init_execution()
        self._user_id = int(user_id) if user_id else None
        
        try:
            # 🆕 AI-First 모드: 단일 AI 호출로 모든 매핑 생성
            if use_ai_first:
                result = await self._generate_content_ai_first(
                    template_id=template_id,
                    user_query=user_query,
                    context=context,
                    user_id=user_id,
                    session_id=session_id,
                    container_ids=container_ids,
                    use_rag=use_rag,
                )
                return self._finalize_execution(result)
            
            # 기존 4-Tool 파이프라인
            # Phase 2: if session_id is provided, run via LangGraph + checkpointer so we can resume.
            if session_id:
                # Step 0: RAG 컨텍스트 수집 (use_rag=True인 경우)
                enriched_context = context
                if use_rag:
                    try:
                        rag_context = await self._perform_rag_search(
                            query=user_query,
                            container_ids=container_ids,
                            session_id=session_id,
                        )
                        if rag_context:
                            enriched_context = f"{context}\n\n## RAG 검색 결과\n{rag_context}"
                            logger.info(f"  📚 RAG 컨텍스트 수집: {len(rag_context)}자 추가")
                    except Exception as e:
                        logger.warning(f"RAG 검색 실패 (계속 진행): {e}")

                thread_id = f"pptwiz:{session_id}:{template_id}:{self._user_id or 'anon'}"
                graph_result = await run_template_wizard_until_mapped(
                    thread_id=thread_id,
                    template_id=template_id,
                    topic=user_query,
                    context_text=enriched_context or "",
                    user_id=self._user_id,
                    request_id=session_id,
                )

                if not graph_result.get("success", False):
                    raise ValueError(graph_result.get("error") or "콘텐츠 생성 실패")

                deck_spec = graph_result.get("deck_spec") or {}
                slide_matches = graph_result.get("slide_matches") or []
                mappings = graph_result.get("mappings") or []
                ai_slides = (deck_spec or {}).get("slides", [])

                original_metadata = await self._load_template_metadata_direct(template_id, user_id)
                original_slides_info = (original_metadata or {}).get("slides", []) if original_metadata else []
                ui_slides = self._convert_to_ui_format(
                    slides_info=original_slides_info,
                    ai_slides=ai_slides,
                    slide_matches=slide_matches,
                    mappings=mappings,
                )

                logger.info(f"✅ [{self.name}] 콘텐츠 생성 완료(LangGraph): {len(ui_slides)} 슬라이드")
                result = {
                    "success": True,
                    "slides": ui_slides,
                    "template_id": template_id,
                    "deck_spec": deck_spec,
                    "slide_matches": slide_matches,
                    "mappings": mappings,
                    "thread_id": thread_id,
                }
                return self._finalize_execution(result)

            # Step 1: 템플릿 분석
            logger.info(f"📋 Step 1: 템플릿 분석 - {template_id}")
            template_result = await self.tools["template_analyzer_tool"]._arun(
                template_id=template_id,
                user_id=self._user_id,
            )
            
            if not template_result.get("success", False):
                raise ValueError(f"템플릿 분석 실패: {template_result.get('error', 'Unknown error')}")
            
            template_structure = template_result.get("template_structure", {})
            template_metadata = template_result.get("template_metadata", {})
            slides_info = template_metadata.get("slides", [])
            
            logger.info(f"  ✅ 템플릿 분석 완료: {len(slides_info)} 슬라이드")
            
            # Step 2: RAG 컨텍스트 수집 (use_rag=True인 경우)
            enriched_context = context
            if use_rag:
                try:
                    rag_context = await self._perform_rag_search(
                        query=user_query,
                        container_ids=container_ids,
                        session_id=session_id,
                    )
                    if rag_context:
                        enriched_context = f"{context}\n\n## RAG 검색 결과\n{rag_context}"
                        logger.info(f"  📚 RAG 컨텍스트 수집: {len(rag_context)}자 추가")
                except Exception as e:
                    logger.warning(f"RAG 검색 실패 (계속 진행): {e}")
            
            # Step 3: 아웃라인 생성 (템플릿 구조 기반)
            logger.info(f"📝 Step 2: 콘텐츠 아웃라인 생성")
            outline_result = await self.tools["outline_generation_tool"]._arun(
                topic=user_query,
                context_text=enriched_context,
                max_slides=len(slides_info),
                template_structure=template_structure,
            )
            
            if not outline_result.get("success", False):
                raise ValueError(f"아웃라인 생성 실패: {outline_result.get('error', 'Unknown error')}")
            
            deck_spec = outline_result.get("deck_spec", {})
            ai_slides = deck_spec.get("slides", [])
            logger.info(f"  ✅ 아웃라인 생성 완료: {len(ai_slides)} 슬라이드")
            
            # Step 4: 슬라이드 유형 매칭
            logger.info(f"🔗 Step 3: 슬라이드 유형 매칭")
            match_result = await self.tools["slide_type_matcher_tool"]._arun(
                deck_spec=deck_spec,
                template_metadata=template_metadata,  # template_metadata 사용
            )
            
            slide_matches = match_result.get("slide_matches", [])
            logger.info(f"  ✅ 슬라이드 매칭 완료: {len(slide_matches)} 매칭")
            
            # Step 5: 콘텐츠 매핑
            logger.info(f"📌 Step 4: 콘텐츠-템플릿 매핑")
            mapping_result = await self.tools["content_mapping_tool"]._arun(
                deck_spec=deck_spec,
                template_structure=template_structure,  # template_structure 사용 (text_boxes 포함)
                slide_matches=slide_matches,
            )
            
            mappings = mapping_result.get("mappings", [])
            logger.info(f"  ✅ 콘텐츠 매핑 완료: {len(mappings)} 매핑")
            
            # Step 6: UI 편집 가능한 형식으로 변환
            # slides_info는 원본 메타데이터의 slides를 사용 (shapes 정보 포함)
            original_metadata = await self._load_template_metadata_direct(template_id, user_id)
            original_slides_info = original_metadata.get("slides", []) if original_metadata else slides_info
            
            ui_slides = self._convert_to_ui_format(
                slides_info=original_slides_info,  # 원본 메타데이터 사용
                ai_slides=ai_slides,
                slide_matches=slide_matches,
                mappings=mappings,
            )
            
            logger.info(f"✅ [{self.name}] 콘텐츠 생성 완료: {len(ui_slides)} 슬라이드")

            result = {
                "success": True,
                "slides": ui_slides,
                "template_id": template_id,
                "deck_spec": deck_spec,  # 원본 보존 (PPT 빌드용)
                "slide_matches": slide_matches,
                "mappings": mappings,
            }
            return self._finalize_execution(result)
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 콘텐츠 생성 실패: {e}", exc_info=True)
            result = {
                "success": False,
                "error": str(e),
                "slides": [],
            }
            return self._finalize_execution(result)
    
    async def build_ppt_from_ui_data(
        self,
        template_id: str,
        slides_data: List[Dict[str, Any]],
        output_filename: str = "presentation",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        deck_spec: Optional[Dict[str, Any]] = None,
        slide_matches: Optional[List[Dict[str, Any]]] = None,
        mappings: Optional[List[Dict[str, Any]]] = None,
        use_ai_builder: bool = True,  # 🆕 SimplePPTBuilder 사용 (기본값 True로 변경)
        slide_replacements: Optional[List[Dict[str, Any]]] = None,  # 🆕 v3.4
        content_plan: Optional[Dict[str, Any]] = None,              # 🆕 v3.7
        dynamic_slides: Optional[Dict[str, Any]] = None,            # 🆕 v3.7
    ) -> Dict[str, Any]:
        try:
            _UNIFIED_PPT_CTX.get()
            has_ctx = True
        except LookupError:
            has_ctx = False

        if has_ctx:
            return await self._build_ppt_from_ui_data_impl(
                template_id=template_id,
                slides_data=slides_data,
                output_filename=output_filename,
                user_id=user_id,
                session_id=session_id,
                deck_spec=deck_spec,
                slide_matches=slide_matches,
                mappings=mappings,
                use_ai_builder=use_ai_builder,
                slide_replacements=slide_replacements,
                content_plan=content_plan,
                dynamic_slides=dynamic_slides,
            )

        ctx_token = _UNIFIED_PPT_CTX.set(_UnifiedPPTRequestContext())
        try:
            return await self._build_ppt_from_ui_data_impl(
                template_id=template_id,
                slides_data=slides_data,
                output_filename=output_filename,
                user_id=user_id,
                session_id=session_id,
                deck_spec=deck_spec,
                slide_matches=slide_matches,
                mappings=mappings,
                use_ai_builder=use_ai_builder,
                slide_replacements=slide_replacements,
                content_plan=content_plan,
                dynamic_slides=dynamic_slides,
            )
        finally:
            _UNIFIED_PPT_CTX.reset(ctx_token)

    async def _build_ppt_from_ui_data_impl(
        self,
        template_id: str,
        slides_data: List[Dict[str, Any]],
        output_filename: str = "presentation",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        deck_spec: Optional[Dict[str, Any]] = None,
        slide_matches: Optional[List[Dict[str, Any]]] = None,
        mappings: Optional[List[Dict[str, Any]]] = None,
        use_ai_builder: bool = True,  # 🆕 SimplePPTBuilder 사용 (기본값 True로 변경)
        slide_replacements: Optional[List[Dict[str, Any]]] = None,  # 🆕 v3.4
        content_plan: Optional[Dict[str, Any]] = None,              # 🆕 v3.7
        dynamic_slides: Optional[Dict[str, Any]] = None,            # 🆕 v3.7
    ) -> Dict[str, Any]:
        """
        UI 편집 데이터로 PPT 생성 (Agent 통제 하에 실행).
        
        Args:
            use_ai_builder: True면 새 AIPPTBuilder 사용 (절충형 아키텍처)
                Agent가 templated_pptx_builder_tool을 사용하여 PPT 생성.
        
        Args:
            template_id: 템플릿 ID
            slides_data: UI에서 편집된 슬라이드 데이터
            output_filename: 출력 파일명
            user_id: 사용자 ID
            deck_spec: 원본 deck_spec (generate_content_for_template에서 반환)
            slide_matches: 슬라이드 매칭 정보
            mappings: 콘텐츠 매핑 정보
            slide_replacements: 슬라이드 대체 정보 (🆕 v3.4)
            content_plan: 콘텐츠 계획 (🆕 v3.7) - 필요 섹션, TOC 항목 등
            dynamic_slides: 동적 슬라이드 설정 (🆕 v3.7) - mode, add_slides, remove_slides
            
        Returns:
            PPT 파일 경로 및 정보
        """
        # 🆕 파일명에서 요청 표현 제거 (명사형으로 축약)
        output_filename = self._refine_output_filename(output_filename)
        
        logger.info(
            f"🏗️ [{self.name}] PPT 빌드 시작: template={template_id}, "
            f"slides={len(slides_data)}, filename={output_filename}"
        )
        
        self._init_execution()
        self._user_id = int(user_id) if user_id else None
        
        try:
            # UI 편집 데이터를 deck_spec 형식으로 변환
            if deck_spec:
                # 기존 deck_spec에 UI 편집 내용 반영
                updated_deck_spec = self._apply_ui_edits_to_deck_spec(
                    deck_spec=deck_spec,
                    slides_data=slides_data,
                )
            else:
                # deck_spec이 없으면 slides_data에서 생성
                updated_deck_spec = self._create_deck_spec_from_ui_data(
                    slides_data=slides_data,
                    topic=output_filename,
                )
            
            # 🆕 slides_data에서 text_box_mappings 생성 (핵심 수정)
            if not mappings:
                mappings = self._generate_mappings_from_slides_data(slides_data)
                logger.info(f"📋 slides_data에서 {len(mappings)}개 매핑 생성")
            
            # 🆕 매핑에 originalName 추가 (메타데이터 참조)
            mappings = await self._enrich_mappings_with_original_names(
                mappings=mappings,
                template_id=template_id,
                user_id=str(self._user_id) if self._user_id else None,
            )
            
            # 🆕 AI-First 매핑 형식 변환 (snake_case -> camelCase)
            normalized_mappings = self._normalize_mappings_format(mappings)
            
            # 🆕 절충형 AIPPTBuilder 사용 옵션
            # Phase 2: if we have a wizard session checkpoint, try resuming the LangGraph build.
            # Only do this when advanced build options aren't used (to avoid dropping features).
            if session_id and not slide_replacements and not content_plan and not dynamic_slides:
                thread_id = f"pptwiz:{session_id}:{template_id}:{self._user_id or 'anon'}"
                resume_result = await resume_template_wizard_build(
                    thread_id=thread_id,
                    state_updates={
                        "topic": output_filename,
                        "template_id": template_id,
                        "user_id": self._user_id,
                        "deck_spec": updated_deck_spec,
                        "slide_matches": slide_matches or [],
                        "mappings": normalized_mappings,
                        "validate": False,
                    },
                )
                if resume_result.get("success"):
                    build_result = resume_result
                else:
                    logger.warning(f"🧩 LangGraph resume build failed (fallback): {resume_result.get('error')}")
                    build_result = None
            else:
                build_result = None

            if build_result is None and use_ai_builder:
                build_result = await self._build_with_ai_ppt_builder(
                    template_id=template_id,
                    mappings=normalized_mappings,
                    output_filename=output_filename,
                    user_id=self._user_id,
                    slide_replacements=slide_replacements,  # 🆕 v3.4
                    content_plan=content_plan,              # 🆕 v3.7
                    dynamic_slides=dynamic_slides,          # 🆕 v3.7
                )
            elif build_result is None:
                # 기존 templated_pptx_builder_tool 실행
                build_result = await self.tools["templated_pptx_builder_tool"]._arun(
                    deck_spec=updated_deck_spec,
                    template_id=template_id,
                    mappings=normalized_mappings,
                    slide_matches=slide_matches,
                    file_basename=output_filename,
                    user_id=self._user_id,
                )
            
            if not build_result.get("success", False):
                raise ValueError(f"PPT 빌드 실패: {build_result.get('error', 'Unknown error')}")
            
            file_path = build_result.get("file_path")
            file_name = build_result.get("file_name") or build_result.get("filename")
            slide_count = build_result.get("slide_count", len(slides_data))
            
            logger.info(f"✅ [{self.name}] PPT 빌드 완료: {file_name}")
            
            # 🆕 자동 품질 검증 (Template PPT만)
            quality_report = await self._validate_template_ppt_quality(
                generated_path=file_path,
                template_id=template_id,
                user_id=self._user_id,
            )

            result = {
                "success": True,
                "file_path": file_path,
                "file_name": file_name,
                "slide_count": slide_count,
                "quality_report": quality_report,  # 품질 검증 결과 추가
            }
            return self._finalize_execution(result)
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] PPT 빌드 실패: {e}", exc_info=True)
            result = {
                "success": False,
                "error": str(e),
            }
            return self._finalize_execution(result)
    
    # =========================================================================
    # Helper Methods for UI 편집 경로
    # =========================================================================
    
    async def _build_with_ai_ppt_builder(
        self,
        template_id: str,
        mappings: List[Dict[str, Any]],
        output_filename: str,
        user_id: Optional[int] = None,
        slide_replacements: Optional[List[Dict[str, Any]]] = None,  # 🆕 v3.4
        content_plan: Optional[Dict[str, Any]] = None,              # 🆕 v3.7
        dynamic_slides: Optional[Dict[str, Any]] = None,            # 🆕 v3.7
    ) -> Dict[str, Any]:
        """
        🆕 절충형 AIPPTBuilder를 사용하여 PPT 빌드.
        
        기존 EnhancedObjectProcessor 대신 간단한 AIPPTBuilder 사용.
        original_name 기반 shape 매칭으로 스타일 100% 보존.
        
        🆕 v3.7: 동적 슬라이드 관리 지원
        - content_plan: 콘텐츠 계획 (필요 섹션, TOC 항목 등)
        - dynamic_slides: 동적 슬라이드 설정 (mode, add_slides, remove_slides)
        
        Args:
            template_id: 템플릿 ID
            mappings: AI 매핑 (slideIndex, elementId, originalName, generatedText 포함)
            output_filename: 출력 파일명
            user_id: 사용자 ID
            slide_replacements: 슬라이드 대체 정보 (🆕 v3.4)
            content_plan: 콘텐츠 계획 (🆕 v3.7)
            dynamic_slides: 동적 슬라이드 설정 (🆕 v3.7)
            
        Returns:
            빌드 결과 딕셔너리
        """
        logger.info(f"🔨 [{self.name}] AIPPTBuilder로 PPT 빌드: template={template_id}, mappings={len(mappings)}개")
        if slide_replacements:
            logger.info(f"  🔄 슬라이드 대체: {len(slide_replacements)}개")
        if dynamic_slides:
            ds_mode = dynamic_slides.get('mode') if isinstance(dynamic_slides, dict) else dynamic_slides
            logger.info(f"  📐 동적 슬라이드: mode={ds_mode}")
        
        try:
            # 1. 템플릿 경로 가져오기
            template_path = await self._get_template_path(template_id, str(user_id) if user_id else None)
            
            if not template_path:
                return {
                    "success": False,
                    "error": f"템플릿을 찾을 수 없습니다: {template_id}",
                    "file_path": None,
                    "file_name": None,
                }
            
            logger.info(f"  📄 템플릿 경로: {template_path}")
            
            # 2. 프레젠테이션 제목 추출 (첫 번째 슬라이드의 main_title)
            presentation_title = None
            for m in mappings:
                if m.get('elementRole') == 'main_title' and m.get('generatedText'):
                    presentation_title = m.get('generatedText')
                    break
            
            if not presentation_title:
                presentation_title = output_filename
            
            # 🆕 v3.8: dynamic_slides가 문자열인 경우 JSON 파싱
            if dynamic_slides and isinstance(dynamic_slides, str):
                try:
                    import json
                    dynamic_slides = json.loads(dynamic_slides)
                    logger.info(f"  📐 dynamic_slides 문자열 파싱 완료: {type(dynamic_slides)}")
                except json.JSONDecodeError as e:
                    logger.warning(f"  ⚠️ dynamic_slides JSON 파싱 실패: {e}")
                    dynamic_slides = None
            
            # 🆕 v3.8: content_plan이 문자열인 경우 JSON 파싱
            if content_plan and isinstance(content_plan, str):
                try:
                    import json
                    content_plan = json.loads(content_plan)
                    logger.info(f"  📐 content_plan 문자열 파싱 완료")
                except json.JSONDecodeError as e:
                    logger.warning(f"  ⚠️ content_plan JSON 파싱 실패: {e}")
                    content_plan = None
            
            # 🆕 v3.7: 동적 슬라이드 처리 (build 전)
            adjusted_mappings = mappings
            dynamic_slide_ops = None
            
            if dynamic_slides and isinstance(dynamic_slides, dict) and dynamic_slides.get('mode') and dynamic_slides.get('mode') != 'fixed':
                logger.info(f"  📐 동적 슬라이드 관리 시작: mode={dynamic_slides.get('mode')}")
                
                try:
                    dynamic_manager = DynamicSlideManager(template_path)
                    
                    if dynamic_slides.get('mode') == 'expand':
                        add_ops = dynamic_slides.get('add_slides', [])
                        if add_ops:
                            # 슬라이드 추가 연산 준비
                            dynamic_slide_ops = {
                                'mode': 'expand',
                                'add_slides': add_ops  # 🔧 v3.8: 'operations' → 'add_slides'
                            }
                            # 매핑 인덱스 조정 (나중에 빌더에서 처리)
                            logger.info(f"    추가 대상: {len(add_ops)}개 슬라이드")
                    
                    elif dynamic_slides.get('mode') == 'reduce':
                        remove_ops = dynamic_slides.get('remove_slides', [])
                        if remove_ops:
                            dynamic_slide_ops = {
                                'mode': 'reduce',
                                'remove_slides': remove_ops  # 🔧 v3.8: 'operations' → 'remove_slides'
                            }
                            logger.info(f"    삭제 대상: {len(remove_ops)}개 슬라이드")
                    
                    # TOC 조정이 필요한 경우
                    if content_plan and content_plan.get('toc_items'):
                        toc_items = content_plan.get('toc_items', [])
                        logger.info(f"    TOC 항목 수: {len(toc_items)}개")
                        # TOC 조정은 SimplePPTBuilder 또는 별도 로직에서 처리
                        
                except Exception as dm_error:
                    logger.warning(f"  ⚠️ 동적 슬라이드 관리 실패, 기본 모드로 진행: {dm_error}")
                    dynamic_slide_ops = None
            
            # 3. AIPPTBuilder로 PPT 생성 (🆕 v3.4: slide_replacements 전달, v3.7: dynamic_slide_ops)
            result = build_ppt_from_ai_mappings(
                template_path=template_path,
                mappings=adjusted_mappings,
                output_filename=output_filename,
                presentation_title=presentation_title,
                slide_replacements=slide_replacements,
                dynamic_slide_ops=dynamic_slide_ops,  # 🆕 v3.7
            )
            
            # slide_count 추가 (통계에서)
            if result.get("success"):
                stats = result.get("stats", {})
                result["slide_count"] = stats.get("applied", 0) + stats.get("skipped", 0)
                
                # 🆕 v3.7: 동적 슬라이드 처리 결과 추가
                if dynamic_slide_ops:
                    result["dynamic_slides_applied"] = True
                    result["dynamic_slides_mode"] = dynamic_slide_ops.get('mode')
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] AIPPTBuilder 빌드 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
                "file_name": None,
            }
    
    async def _validate_template_ppt_quality(
        self,
        generated_path: str,
        template_id: str,
        user_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        생성된 Template PPT의 품질 검증.
        
        Args:
            generated_path: 생성된 PPT 파일 경로
            template_id: 템플릿 ID
            user_id: 사용자 ID
            
        Returns:
            품질 검증 리포트 또는 None (검증 실패 시)
        """
        try:
            from app.services.presentation.ppt_template_manager import template_manager
            from app.services.presentation.user_template_manager import user_template_manager
            
            logger.info(f"🔍 [{self.name}] 품질 검증 시작: {template_id}")
            
            # 템플릿 파일 경로 찾기
            template_path = None
            metadata_path = None
            
            # 시스템 템플릿 확인 (get_template_details 사용)
            template_info = template_manager.get_template_details(template_id)
            if template_info:
                template_path = template_info.get("path")
                metadata_path = template_info.get("metadata_path")
            
            # 사용자 템플릿 확인 (get_template_details 사용)
            if not template_path and user_id:
                user_template_info = user_template_manager.get_template_details(str(user_id), template_id)
                if user_template_info:
                    template_path = user_template_info.get("path")
                    # 🆕 v3.4: metadata_path가 없으면 직접 구성
                    if not metadata_path and template_path:
                        import os
                        from pathlib import Path
                        template_dir = Path(template_path).parent
                        metadata_dir = template_dir / "metadata"
                        template_stem = Path(template_path).stem.replace(' ', '_')
                        possible_metadata = metadata_dir / f"{template_stem}_metadata.json"
                        if possible_metadata.exists():
                            metadata_path = str(possible_metadata)
                            logger.debug(f"  메타데이터 경로 구성: {metadata_path}")
            
            if not template_path:
                logger.warning(f"⚠️ 템플릿 파일을 찾을 수 없어 품질 검증 생략: {template_id}")
                return None
            
            # template_ppt_comparator_tool 실행
            comparison_result = await self.tools["template_ppt_comparator_tool"]._arun(
                generated_pptx_path=generated_path,
                template_pptx_path=template_path,
                template_metadata_path=metadata_path,
            )
            
            if not comparison_result.get("success"):
                logger.warning(f"⚠️ 품질 검증 실패: {comparison_result.get('error')}")
                return None
            
            report = comparison_result.get("report", {})
            passed = comparison_result.get("passed", False)
            quality_score = comparison_result.get("quality_score", 0.0)
            
            logger.info(
                f"{'✅' if passed else '❌'} [{self.name}] 품질 검증 완료: "
                f"점수={quality_score:.1f}/100, 결과={'PASS' if passed else 'FAIL'}"
            )
            
            # 실패 시 경고 로그
            if not passed:
                critical_issues = report.get("critical_issues", [])
                warnings = report.get("warnings", [])
                
                logger.warning(
                    f"⚠️ [{self.name}] 품질 문제 발견:\n"
                    f"  치명적 문제: {len(critical_issues)}개\n"
                    f"  경고: {len(warnings)}개"
                )
                
                for issue in critical_issues[:3]:  # 최대 3개만 로그
                    logger.warning(f"  ❌ {issue}")
            
            return {
                "passed": passed,
                "quality_score": quality_score,
                "critical_issues_count": len(report.get("critical_issues", [])),
                "warnings_count": len(report.get("warnings", [])),
                "summary": comparison_result.get("summary", ""),
                "recommendations": report.get("recommendations", [])[:5],  # 최대 5개
            }
            
        except Exception as e:
            logger.warning(f"⚠️ [{self.name}] 품질 검증 중 오류 (무시하고 계속): {e}")
            return None
    
    # =========================================================================
    # AI-First 파이프라인 (신규)
    # =========================================================================
    
    async def _generate_content_ai_first(
        self,
        template_id: str,
        user_query: str,
        context: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        use_rag: bool = True,
    ) -> Dict[str, Any]:
        """
        AI-First 파이프라인: 단일 AI 호출로 모든 매핑 생성.
        
        기존 4-Tool 파이프라인의 복잡성을 제거하고,
        AI가 직접 element_id ↔ content 매핑을 생성.
        """
        logger.info(f"🚀 [{self.name}] AI-First 파이프라인 시작")
        
        try:
            # Step 1: 템플릿 메타데이터 로드
            template_metadata = await self._load_template_metadata_direct(template_id, user_id)
            if not template_metadata:
                raise ValueError(f"템플릿 메타데이터를 찾을 수 없습니다: {template_id}")
            
            slides_info = template_metadata.get("slides", [])
            logger.info(f"  📋 템플릿 로드 완료: {len(slides_info)} 슬라이드")
            
            # Step 2: RAG 컨텍스트 수집 (use_rag=True인 경우)
            enriched_context = context
            if use_rag:
                try:
                    rag_context = await self._perform_rag_search(
                        query=user_query,
                        container_ids=container_ids,
                        session_id=session_id,
                    )
                    if rag_context:
                        enriched_context = f"{context}\n\n## RAG 검색 결과\n{rag_context}"
                        logger.info(f"  📚 RAG 컨텍스트 수집: {len(rag_context)}자 추가")
                except Exception as e:
                    logger.warning(f"RAG 검색 실패 (계속 진행): {e}")
            
            # Step 3: AI Direct Mapping Tool 실행
            logger.info(f"  🤖 AI Direct Mapping 실행 중...")
            ai_mapping_tool = AIDirectMappingTool()
            mapping_result = await ai_mapping_tool._arun(
                user_query=user_query,
                template_metadata=template_metadata,
                additional_context=enriched_context,
            )
            
            if not mapping_result.get("success", False):
                raise ValueError(f"AI Mapping 실패: {mapping_result.get('error', 'Unknown error')}")
            
            mappings = mapping_result.get("mappings", [])
            slide_replacements = mapping_result.get("slide_replacements", [])  # 🆕 v3.4
            content_plan = mapping_result.get("content_plan", {})              # 🆕 v3.8: 동적 슬라이드
            dynamic_slides = mapping_result.get("dynamic_slides", {"mode": "fixed"})  # 🆕 v3.8: 동적 슬라이드
            
            logger.info(f"  ✅ AI Mapping 완료: {len(mappings)} 매핑")
            if slide_replacements:
                logger.info(f"  🔄 슬라이드 대체 요청: {len(slide_replacements)}개")
            if dynamic_slides and dynamic_slides.get("mode") != "fixed":
                logger.info(f"  📐 동적 슬라이드: mode={dynamic_slides.get('mode')}")
            
            # =================================================================
            # 🆕 v3.6: Quality Guard & 부분 재생성 (Agentic AI)
            # 
            # 품질 이슈가 있는 요소만 타겟팅하여 부분 재생성합니다.
            # 기존 정상 콘텐츠는 보존됩니다.
            # =================================================================
            from app.tools.presentation.quality_guard_tool import QualityGuard
            quality_guard = QualityGuard()
            
            # 품질 검증
            completeness_result = quality_guard.check_completeness(mappings)
            stagnation_result = quality_guard.check_data_stagnation(mappings, user_query)
            
            is_complete = completeness_result["is_complete"]
            is_clean = stagnation_result["is_clean"]
            
            if is_complete and is_clean:
                logger.info(f"  ✨ [QualityGuard] 모든 품질 검증 통과")
            else:
                # 품질 이슈가 있는 경우: 부분 재생성 시도
                log_messages = []
                if not is_complete:
                    missing_items = completeness_result["missing_items"]
                    log_messages.append(f"누락 {len(missing_items)}건")
                if not is_clean:
                    stagnant_count = len(stagnation_result.get("stagnant_items", []))
                    mismatch_count = len(stagnation_result.get("domain_mismatch_items", []))
                    if stagnant_count > 0:
                        log_messages.append(f"데이터 정체 {stagnant_count}건")
                    if mismatch_count > 0:
                        log_messages.append(f"도메인 불일치 {mismatch_count}건")
                
                logger.warning(f"  🚨 [QualityGuard] 품질 이슈 감지 ({', '.join(log_messages)}) -> 부분 재생성 시도")
                
                # 문제가 있는 elementId 목록 추출
                stagnant_element_ids = quality_guard.get_stagnant_element_ids(stagnation_result)
                
                if stagnant_element_ids:
                    # 품질 이슈 정보 수집 (프롬프트 힌트용)
                    quality_issues = stagnation_result.get("stagnant_items", []) + stagnation_result.get("domain_mismatch_items", [])
                    
                    # 부분 재생성 실행
                    regen_result = await ai_mapping_tool.regenerate_elements(
                        user_query=user_query,
                        template_metadata=template_metadata,
                        target_element_ids=stagnant_element_ids,
                        existing_mappings=mappings,
                        additional_context=enriched_context,
                        quality_issues=quality_issues
                    )
                    
                    if regen_result.get("success") and regen_result.get("regenerated_mappings"):
                        regenerated = regen_result["regenerated_mappings"]
                        logger.info(f"  🔄 [QualityGuard] 부분 재생성 완료: {len(regenerated)}개 매핑 갱신")
                        
                        # elementId 기준으로 기존 매핑 갱신 (덮어쓰기)
                        mappings = self._merge_mappings(mappings, regenerated)
                    else:
                        logger.warning(f"  ⚠️ [QualityGuard] 부분 재생성 실패 또는 결과 없음")
            
            # =================================================================
            
            # Step 4: 매핑을 UI 형식으로 변환
            ui_slides = self._convert_ai_mappings_to_ui_format(
                slides_info=slides_info,
                mappings=mappings,
            )
            
            # deck_spec 생성 (기존 UI와 호환성 유지)
            deck_spec = self._create_deck_spec_from_mappings(
                topic=user_query,
                slides_info=slides_info,
                mappings=mappings,
            )
            
            # slide_matches 생성 (1:1 매핑)
            slide_matches = [
                {"ai_slide_idx": i, "template_index": i + 1}
                for i in range(len(slides_info))
            ]
            
            # 🆕 프레젠테이션 제목 추출 (첫 번째 슬라이드의 main_title)
            presentation_title = self._extract_presentation_title(mappings, user_query)
            
            logger.info(f"✅ [{self.name}] AI-First 콘텐츠 생성 완료: {len(ui_slides)} 슬라이드")
            logger.info(f"  📌 프레젠테이션 제목: '{presentation_title}'")
            
            return {
                "success": True,
                "slides": ui_slides,
                "template_id": template_id,
                "deck_spec": deck_spec,
                "slide_matches": slide_matches,
                "mappings": mappings,
                "slide_replacements": slide_replacements,  # 🆕 v3.4
                "content_plan": content_plan,              # 🆕 v3.8: 동적 슬라이드
                "dynamic_slides": dynamic_slides,          # 🆕 v3.8: 동적 슬라이드
                "pipeline": "ai_first",  # 파이프라인 구분자
                "presentation_title": presentation_title,  # 🆕 파일명용 제목
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] AI-First 파이프라인 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "slides": [],
            }
    
    def _convert_ai_mappings_to_ui_format(
        self,
        slides_info: List[Dict[str, Any]],
        mappings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        AI 매핑을 UI 편집 가능한 형식으로 변환.
        
        기존 UI와 호환되는 형식으로 변환:
        {
            "index": 1,  # 1-based
            "role": "content",
            "elements": [
                {"id": "textbox-0-0", "text": "AI 생성 내용", "role": "body", "original_text": "원본"}
            ],
            "note": ""
        }
        """
        # elementId를 키로 하는 매핑 딕셔너리 (AI Tool은 camelCase 사용)
        mapping_dict = {}
        for m in mappings:
            # camelCase (elementId) 또는 snake_case (element_id) 모두 지원
            elem_id = m.get("elementId") or m.get("element_id", "")
            if elem_id:
                mapping_dict[elem_id] = m
        
        logger.debug(f"📋 매핑 딕셔너리 키: {list(mapping_dict.keys())[:10]}...")
        
        ui_slides = []
        for slide_idx, slide in enumerate(slides_info, start=1):
            shapes = slide.get("shapes", [])
            editable_elements = slide.get("editable_elements", [])
            elements_meta = slide.get("elements", [])  # 기존 메타데이터의 elements
            
            # elements 메타데이터에서 ID 매핑
            elements_by_id = {e.get("id"): e for e in elements_meta}
            shapes_by_name = {s.get("name"): s for s in shapes}
            
            ui_elements = []
            
            # 🔧 elements_meta를 우선 사용 (textbox-X-X 형식의 표준화된 ID)
            for elem in elements_meta:
                elem_id = elem.get("id", "")
                if not elem_id:
                    continue
                
                # AI 매핑에서 찾기 (textbox-0-0 형식)
                mapping = mapping_dict.get(elem_id)
                
                # 원본 텍스트
                original_text = elem.get("content", "")
                
                # AI 콘텐츠 (매핑이 없으면 원본 유지)
                # 🔧 FIX: generatedText가 AI 매핑의 실제 키
                new_content = original_text
                if mapping:
                    new_content = mapping.get("generatedText") or mapping.get("newContent") or mapping.get("new_content", original_text)
                
                # element_role
                elem_role = elem.get("element_role", "body")
                
                ui_elements.append({
                    "id": elem_id,
                    "text": new_content,
                    "role": elem_role,
                    "original_text": original_text,
                })
            
            # elements_meta가 비어있으면 shapes에서 생성 (fallback)
            if not ui_elements and shapes:
                for shape in shapes:
                    shape_name = shape.get("name", "")
                    if not shape_name:
                        continue
                    
                    # AI 매핑에서 찾기
                    mapping = mapping_dict.get(shape_name)
                    
                    # 원본 텍스트 추출
                    text_info = shape.get("text", {})
                    if isinstance(text_info, dict):
                        original_text = text_info.get("raw", "")
                    else:
                        original_text = str(text_info) if text_info else ""
                    
                    # AI 콘텐츠
                    # 🔧 FIX: generatedText가 AI 매핑의 실제 키
                    new_content = original_text
                    if mapping:
                        new_content = mapping.get("generatedText") or mapping.get("newContent") or mapping.get("new_content", original_text)
                    
                    ui_elements.append({
                        "id": shape_name,
                        "text": new_content,
                        "role": shape.get("element_role", "body"),
                        "original_text": original_text,
                    })
            
            ui_slides.append({
                "index": slide_idx,
                "role": slide.get("slide_type", slide.get("role", "content")),
                "elements": ui_elements,
                "note": "",  # AI-First는 speaker notes 미생성
            })
        
        return ui_slides
    
    def _create_deck_spec_from_mappings(
        self,
        topic: str,
        slides_info: List[Dict[str, Any]],
        mappings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """AI 매핑에서 deck_spec 생성 (기존 PPT 빌더와 호환성 유지)"""
        slides = []
        
        # 슬라이드별 매핑 그룹화 (camelCase/snake_case 모두 지원)
        mapping_by_slide = {}
        for m in mappings:
            # slideIndex (camelCase) 또는 slide_index (snake_case)
            slide_idx = m.get("slideIndex", m.get("slide_index", 0))
            # slideIndex는 0-based, slide_index는 1-based일 수 있음
            if "slideIndex" in m:
                slide_idx = slide_idx + 1  # 0-based → 1-based
            
            if slide_idx not in mapping_by_slide:
                mapping_by_slide[slide_idx] = []
            mapping_by_slide[slide_idx].append(m)
        
        for slide_idx, slide in enumerate(slides_info, start=1):
            slide_mappings = mapping_by_slide.get(slide_idx, [])
            
            # 제목 찾기 (첫 번째 매핑 또는 슬라이드 타입에서 추론)
            title = ""
            content_items = []
            
            for m in slide_mappings:
                # generatedText (camelCase) 또는 newContent (legacy) 또는 new_content (snake_case)
                new_content = m.get("generatedText") or m.get("newContent") or m.get("new_content", "")
                if not title and new_content:
                    title = new_content
                else:
                    content_items.append({"text": new_content})
            
            slides.append({
                "slide_index": slide_idx,
                "slide_type": slide.get("slide_type", "content"),
                "title": title,
                "content": content_items,
            })
        
        return {
            "topic": topic,
            "total_slides": len(slides_info),
            "slides": slides,
        }
    
    def _normalize_mappings_format(
        self,
        mappings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        AI-First 매핑 형식을 기존 빌더 형식으로 변환.
        
        AI-First 형식 (snake_case):
        {
            "slide_index": 1,
            "element_id": "s1_shape_0",
            "original_text": "...",
            "new_content": "..."
        }
        
        기존 빌더 형식 (camelCase):
        {
            "slideIndex": 0,
            "elementId": "textbox-0-0",
            "newContent": "..."
        }
        """
        normalized = []
        
        for m in mappings:
            # snake_case 키가 있는 경우 (AI-First 형식)
            if "slide_index" in m:
                normalized.append({
                    "slideIndex": m.get("slide_index", 1) - 1,  # 1-based → 0-based
                    "elementId": m.get("element_id", ""),
                    "newContent": m.get("new_content", ""),
                    "originalName": m.get("original_name", ""),
                    "objectType": m.get("object_type", "textbox"),
                    "isEnabled": m.get("is_enabled", True),
                    "metadata": m.get("metadata", {}),
                })
            # camelCase 키가 있는 경우 (기존 형식 - 그대로 전달)
            elif "slideIndex" in m:
                normalized.append(m)
            # 그 외 (혼합 형식 등)
            else:
                logger.warning(f"⚠️ 알 수 없는 매핑 형식: {m}")
                normalized.append(m)
        
        logger.info(f"📋 매핑 형식 정규화: {len(mappings)} → {len(normalized)} 매핑")
        return normalized
    
    async def _get_template_path(
        self,
        template_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """템플릿 파일 경로 반환"""
        try:
            from app.services.presentation.ppt_template_manager import template_manager
            from app.services.presentation.user_template_manager import user_template_manager
            
            # 시스템 템플릿
            path = template_manager.get_template_path(template_id)
            if path:
                return path
            
            # 사용자 템플릿
            if user_id:
                path = user_template_manager.get_template_path(user_id, template_id)
                if path:
                    return path
            
            # owner 찾기
            owner_id = user_template_manager.find_template_owner(template_id)
            if owner_id:
                return user_template_manager.get_template_path(owner_id, template_id)
            
            return None
        except Exception as e:
            logger.warning(f"템플릿 경로 조회 실패: {e}")
            return None
    
    async def _load_template_metadata_direct(
        self,
        template_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """템플릿 메타데이터 직접 로드 (shapes 정보 포함)"""
        try:
            from app.services.presentation.ppt_template_manager import template_manager
            from app.services.presentation.user_template_manager import user_template_manager
            
            # 시스템 템플릿에서 먼저 찾기
            metadata = template_manager.get_template_metadata(template_id)
            
            if not metadata:
                # 사용자 템플릿에서 찾기
                if user_id:
                    metadata = user_template_manager.get_template_metadata(user_id, template_id)
                
                if not metadata:
                    owner_id = user_template_manager.find_template_owner(template_id)
                    if owner_id:
                        metadata = user_template_manager.get_template_metadata(owner_id, template_id)
            
            return metadata
        except Exception as e:
            logger.warning(f"템플릿 메타데이터 직접 로드 실패: {e}")
            return None
    
    async def _perform_rag_search(
        self,
        query: str,
        container_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """RAG 검색을 통한 관련 문서 컨텍스트 수집"""
        try:
            from app.services.chat.rag_search_service import rag_search_service, RAGSearchParams
            from app.core.database import get_async_session_local
            
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                search_params = RAGSearchParams(
                    query=query,
                    container_ids=container_ids,
                    limit=10,
                    max_chunks=5,
                    similarity_threshold=0.3,
                )
                
                results = await rag_search_service.search_for_rag_context(
                    session=session,
                    search_params=search_params,
                    session_id=session_id,
                )
                
                if not results or not results.chunks:
                    return ""
                
                chunks = results.chunks[:5]  # 상위 5개만
                context_parts = []
                for chunk in chunks:
                    text = chunk.get("text", "")
                    if text:
                        context_parts.append(text)
                
                return "\n\n---\n\n".join(context_parts)
                
        except Exception as e:
            logger.warning(f"RAG 검색 실패: {e}")
            return ""
    
    def _convert_to_ui_format(
        self,
        slides_info: List[Dict[str, Any]],
        ai_slides: List[Dict[str, Any]],
        slide_matches: List[Dict[str, Any]],
        mappings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """AI 생성 콘텐츠를 UI 편집 가능한 형식으로 변환
        
        v3.0 개선:
        - 모든 편집 가능 요소에 AI 콘텐츠 매핑
        - numbered_card, icon_text, label 등 다양한 역할 지원
        - 원본 텍스트 길이/구조에 맞춰 AI 콘텐츠 분배
        
        메타데이터 구조:
        - slides_info[i]["index"]: 1-based 슬라이드 인덱스
        - slides_info[i]["editable_elements"]: shape 이름 리스트 (문자열)
        - slides_info[i]["shapes"]: 실제 shape 정보 배열
        - slides_info[i]["elements"]: 추출된 요소 배열 (element_role 포함)
        """
        ui_slides = []
        
        # slide_matches를 template_index -> ai_index 매핑으로 변환
        template_to_ai = {}
        for match in slide_matches:
            ai_idx = match.get("ai_slide_index", match.get("outline_index", 0))
            template_idx = match.get("template_slide_index", match.get("template_index", 0))
            
            # template_index가 1-based면 0-based로 변환
            if template_idx >= 1:
                template_to_ai[template_idx - 1] = ai_idx
            else:
                template_to_ai[template_idx] = ai_idx
        
        logger.debug(f"🔗 Template→AI 매핑: {template_to_ai}")
        
        # 템플릿 슬라이드 순서대로 처리
        for list_idx, slide_info in enumerate(slides_info):
            slide_role = slide_info.get("role", "content")
            meta_index = slide_info.get("index", list_idx + 1)  # 메타데이터의 index (1-based)
            
            # editable_elements는 shape 이름 리스트 (표준화된 ID: textbox-X-X, shape-X-X)
            editable_element_names = slide_info.get("editable_elements", [])
            shapes = slide_info.get("shapes", [])
            elements_meta = slide_info.get("elements", [])  # v3.0 요소 메타데이터
            
            # shape 이름으로 shape 정보 매핑 (원본 PPT 이름)
            shapes_by_name = {s.get("name"): s for s in shapes}
            # elements 메타데이터에서 element_role 매핑 (표준화된 ID)
            elements_by_id = {e.get("id"): e for e in elements_meta}
            
            # 🔧 수정: elements_meta를 우선 사용 (shape-X-X 형태의 표준화된 ID 포함)
            # editable_elements에 있는 ID가 elements_meta에 있으면 그 정보 사용
            # 없으면 shapes_by_name에서 찾기 시도
            
            # 해당 템플릿 슬라이드에 매칭된 AI 슬라이드 찾기
            matched_ai_idx = template_to_ai.get(list_idx)
            
            # AI 콘텐츠 가져오기
            ai_content = {}
            if matched_ai_idx is not None and matched_ai_idx < len(ai_slides):
                ai_content = ai_slides[matched_ai_idx]
            
            logger.debug(f"📄 Slide {meta_index}: role={slide_role}, matched_ai={matched_ai_idx}, "
                        f"editable={len(editable_element_names)}, elements_meta={len(elements_meta)}, "
                        f"ai_content_keys={list(ai_content.keys())}")
            
            # AI 콘텐츠 분배 준비
            ai_title = ai_content.get("title", "")
            ai_key_message = ai_content.get("key_message", "")
            ai_bullets = ai_content.get("bullets", [])
            ai_speaker_notes = ai_content.get("speaker_notes", "")
            
            # 불릿 인덱스 관리 (여러 요소에 분배)
            bullet_idx = 0
            
            # UI 요소 생성
            elements = []
            title_applied = False
            key_message_applied = False
            
            for elem_name in editable_element_names:
                if not isinstance(elem_name, str):
                    continue
                
                # 🔧 수정: element_meta를 우선 사용 (shape-X-X 형태의 표준화된 ID에 대응)
                element_meta = elements_by_id.get(elem_name, {})
                shape_info = shapes_by_name.get(elem_name, {})
                
                # elements_meta에 정보가 있으면 우선 사용, 없으면 shapes에서 찾기
                if not element_meta and not shape_info:
                    logger.warning(f"⚠️ Element '{elem_name}' not found in elements_meta or shapes")
                    continue
                
                # 텍스트 정보 추출: element_meta의 content 우선 사용
                original_text = ""
                if element_meta:
                    original_text = element_meta.get("content", "")
                
                # element_meta에 content가 없으면 shape_info에서 찾기
                if not original_text and shape_info:
                    text_info = shape_info.get("text", {})
                    if isinstance(text_info, dict):
                        original_text = text_info.get("raw", "")
                    else:
                        original_text = str(text_info) if text_info else ""
                
                # element_role 결정 (element_meta 우선, 없으면 shape_info)
                elem_role = element_meta.get("element_role", "") or shape_info.get("element_role", "")
                
                if not elem_role:
                    # 위치 기반 추론
                    top_px = shape_info.get("top_px", 0) or element_meta.get("top_px", 0) or 0
                    
                    if top_px < 200 and not title_applied:
                        elem_role = "slide_title"
                    elif top_px < 300:
                        elem_role = "key_message"
                    else:
                        elem_role = "body_content"
                
                # AI 콘텐츠에서 해당 역할의 텍스트 찾기
                new_text = original_text  # 기본값: 원본 유지
                
                # === 역할별 AI 콘텐츠 매핑 ===
                
                # 1. 제목 역할
                if elem_role in ["slide_title", "title", "main_title"] and not title_applied:
                    if ai_title:
                        new_text = ai_title
                        title_applied = True
                
                # 2. 키 메시지 / 부제목 역할
                elif elem_role in ["key_message", "subtitle", "caption"]:
                    if ai_key_message and not key_message_applied:
                        new_text = ai_key_message
                        key_message_applied = True
                    elif ai_bullets and bullet_idx < len(ai_bullets):
                        # 키 메시지가 없으면 불릿 사용
                        new_text = ai_bullets[bullet_idx]
                        bullet_idx += 1
                
                # 3. 번호 카드 역할 (01, 02, 03 형태)
                elif elem_role in ["numbered_card", "card"]:
                    if ai_bullets and bullet_idx < len(ai_bullets):
                        # 원본 텍스트의 번호 형식 유지
                        original_lines = original_text.split('\n')
                        if original_lines and original_lines[0].strip().isdigit():
                            # 번호 유지, 내용만 교체
                            number_part = original_lines[0].strip()
                            new_text = f"{number_part}\n{ai_bullets[bullet_idx]}"
                        else:
                            new_text = ai_bullets[bullet_idx]
                        bullet_idx += 1
                
                # 4. 아이콘+텍스트 역할
                elif elem_role in ["icon_text", "icon_box"]:
                    if ai_bullets and bullet_idx < len(ai_bullets):
                        # 원본의 아이콘 이모지 유지
                        import re
                        emoji_match = re.match(r'^([\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]+)', original_text)
                        if emoji_match:
                            icon = emoji_match.group(1)
                            new_text = f"{icon}\n{ai_bullets[bullet_idx]}"
                        else:
                            new_text = ai_bullets[bullet_idx]
                        bullet_idx += 1
                
                # 5. 불릿/목록 항목 역할
                elif elem_role in ["bullet_item", "list_item", "toc_item"]:
                    if ai_bullets and bullet_idx < len(ai_bullets):
                        new_text = f"• {ai_bullets[bullet_idx]}"
                        bullet_idx += 1
                
                # 6. 본문 콘텐츠 역할
                elif elem_role in ["body_content", "content", "content_item"]:
                    if ai_bullets and bullet_idx < len(ai_bullets):
                        # 남은 불릿 모두 합치기
                        remaining_bullets = ai_bullets[bullet_idx:]
                        if remaining_bullets:
                            new_text = "\n".join(f"• {b}" for b in remaining_bullets)
                            bullet_idx = len(ai_bullets)  # 모두 사용됨
                    elif ai_key_message and not key_message_applied:
                        new_text = ai_key_message
                        key_message_applied = True
                
                # 7. 라벨 역할 (짧은 텍스트)
                elif elem_role == "label":
                    # 라벨은 보통 짧은 텍스트, AI 콘텐츠에서 적절한 것 선택
                    if ai_bullets and bullet_idx < len(ai_bullets):
                        # 짧게 자르기
                        bullet_text = ai_bullets[bullet_idx]
                        new_text = bullet_text[:30] if len(bullet_text) > 30 else bullet_text
                        bullet_idx += 1
                
                # 8. 감사 슬라이드 역할
                elif elem_role in ["thanks_message", "contact_info"]:
                    # 감사 슬라이드는 원본 유지 (기본 템플릿 텍스트)
                    pass
                
                # 9. 기타 역할 (남은 불릿으로 채우기)
                else:
                    if ai_bullets and bullet_idx < len(ai_bullets):
                        new_text = ai_bullets[bullet_idx]
                        bullet_idx += 1
                
                elements.append({
                    "id": elem_name,
                    "text": new_text,
                    "role": elem_role,
                    "original_text": original_text,
                })
            
            ui_slides.append({
                "index": meta_index,  # 메타데이터의 1-based index 유지
                "role": slide_role,
                "elements": elements,
                "note": ai_speaker_notes,
            })
        
        return ui_slides
    
    def _extract_presentation_title(
        self,
        mappings: List[Dict[str, Any]],
        user_query: str,
    ) -> str:
        """
        AI 매핑에서 프레젠테이션 제목 추출.
        
        우선순위:
        1. 첫 번째 슬라이드(slideIndex=0)의 main_title 역할 요소
        2. 첫 번째 슬라이드의 title 역할 요소
        3. 사용자 쿼리에서 요청 표현 제거한 버전
        """
        if not mappings:
            return self._refine_output_filename(user_query)
        
        # 슬라이드 0(표지)의 매핑만 필터
        cover_mappings = [
            m for m in mappings 
            if m.get("slideIndex", m.get("slide_index", -1)) == 0
        ]
        
        # 1. main_title 역할 찾기
        for m in cover_mappings:
            role = m.get("elementRole", m.get("element_role", ""))
            if role == "main_title":
                generated_text = m.get("generatedText", m.get("generated_text", ""))
                if generated_text and len(generated_text.strip()) >= 3:
                    title = generated_text.strip()
                    # 너무 긴 제목은 자르기 (파일명 제한)
                    if len(title) > 50:
                        title = title[:47] + "..."
                    logger.info(f"📌 프레젠테이션 제목 추출 (main_title): '{title}'")
                    return title
        
        # 2. title 역할 찾기
        for m in cover_mappings:
            role = m.get("elementRole", m.get("element_role", ""))
            if role == "title":
                generated_text = m.get("generatedText", m.get("generated_text", ""))
                if generated_text and len(generated_text.strip()) >= 3:
                    title = generated_text.strip()
                    if len(title) > 50:
                        title = title[:47] + "..."
                    logger.info(f"📌 프레젠테이션 제목 추출 (title): '{title}'")
                    return title
        
        # 3. 첫 번째 슬라이드의 아무 요소라도 (길이 5자 이상)
        for m in cover_mappings:
            generated_text = m.get("generatedText", m.get("generated_text", ""))
            if generated_text and len(generated_text.strip()) >= 5:
                title = generated_text.strip()
                if len(title) > 50:
                    title = title[:47] + "..."
                logger.info(f"📌 프레젠테이션 제목 추출 (fallback): '{title}'")
                return title
        
        # 4. 최종 폴백: 사용자 쿼리 정제
        refined = self._refine_output_filename(user_query)
        logger.info(f"📌 프레젠테이션 제목 (사용자 쿼리): '{refined}'")
        return refined
    
    def _refine_output_filename(self, filename: str) -> str:
        """파일명에서 요청 표현을 제거하고 명사형으로 축약.
        
        예시:
        - '자동차 산업의 특허분석 방법론에 대해 PPT 작성해 주세요' → '자동차 산업의 특허분석 방법론'
        - 'AI 기술 트렌드 발표 자료 만들어줘' → 'AI 기술 트렌드'
        """
        if not filename or filename == "presentation":
            return filename
        
        original = filename
        
        # 1. 후위 요청 표현 패턴 (끝에서부터 제거)
        suffix_patterns = [
            r'\s*(에 대해|에 대한|에 관한|에 관해|을 위한|를 위한)\s*(PPT|ppt|프레젠테이션|발표\s*자료|슬라이드).*$',
            r'\s*(PPT|ppt|프레젠테이션|발표\s*자료|슬라이드)\s*(작성|생성|만들|제작).*$',
            r'\s*(작성|생성|만들어|제작)\s*(해|좀)?\s*(주세요|줘|줘요|주십시오|부탁).*$',
            r'\s*(해|좀)?\s*(주세요|줘|줘요|주십시오|부탁).*$',
            r'\s+PPT\s*$',
            r'\s+ppt\s*$',
        ]
        
        for pattern in suffix_patterns:
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE).strip()
        
        # 2. 전위 요청 표현 패턴 (앞에서부터 제거)
        prefix_patterns = [
            r'^(다음|아래|위)\s*(내용|주제)(에 대해|으로|로)?\s*',
        ]
        
        for pattern in prefix_patterns:
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE).strip()
        
        # 3. 조사 정리 (끝에 '의', '에', '를' 등이 남으면 제거)
        filename = re.sub(r'[의에를을가이]$', '', filename).strip()
        
        # 결과가 너무 짧으면 원본 반환
        if len(filename) < 3:
            filename = original
        
        if filename != original:
            logger.info(f"📝 파일명 정제: '{original[:50]}' → '{filename[:50]}'")
        
        return filename
    
    def _apply_ui_edits_to_deck_spec(
        self,
        deck_spec: Dict[str, Any],
        slides_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """UI 편집 내용을 deck_spec에 반영"""
        updated_spec = deck_spec.copy()
        updated_slides = updated_spec.get("slides", [])
        
        # UI 슬라이드 데이터를 index로 매핑
        ui_by_index = {s.get("index"): s for s in slides_data}
        
        for i, slide in enumerate(updated_slides):
            slide_index = i + 1  # 1-based
            ui_slide = ui_by_index.get(slide_index)
            
            if ui_slide:
                elements = ui_slide.get("elements", [])
                for elem in elements:
                    role = elem.get("role", "")
                    text = elem.get("text", "")
                    
                    if role in ["slide_title", "title"]:
                        slide["title"] = text
                    elif role in ["key_message", "subtitle"]:
                        slide["key_message"] = text
                    elif role in ["body_content", "content"]:
                        # 불릿 형식에서 리스트로 변환
                        if text:
                            lines = [
                                line.lstrip("•-").strip()
                                for line in text.split("\n")
                                if line.strip()
                            ]
                            slide["bullets"] = lines
        
        updated_spec["slides"] = updated_slides
        return updated_spec
    
    def _create_deck_spec_from_ui_data(
        self,
        slides_data: List[Dict[str, Any]],
        topic: str,
    ) -> Dict[str, Any]:
        """UI 데이터에서 deck_spec 생성"""
        slides = []
        
        for slide_data in slides_data:
            slide = {
                "title": "",
                "key_message": "",
                "bullets": [],
                "layout": "content",
            }
            
            for elem in slide_data.get("elements", []):
                role = elem.get("role", "")
                text = elem.get("text", "")
                
                if role in ["slide_title", "title"]:
                    slide["title"] = text
                elif role in ["key_message", "subtitle"]:
                    slide["key_message"] = text
                elif role in ["body_content", "content"]:
                    if text:
                        lines = [
                            line.lstrip("•-").strip()
                            for line in text.split("\n")
                            if line.strip()
                        ]
                        slide["bullets"] = lines
            
            slides.append(slide)
        
        return {
            "topic": topic,
            "slides": slides,
            "max_slides": len(slides),
        }
    
    async def _enrich_mappings_with_original_names(
        self,
        mappings: List[Dict[str, Any]],
        template_id: str,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        매핑에 originalName 추가 (메타데이터 참조).
        
        UI 편집 데이터에는 originalName이 없으므로,
        메타데이터에서 elementId → originalName 매핑을 조회하여 추가.
        
        Args:
            mappings: elementId 기반 매핑 리스트
            template_id: 템플릿 ID
            user_id: 사용자 ID
            
        Returns:
            originalName이 추가된 매핑 리스트
        """
        # 이미 모든 매핑에 originalName이 있으면 그대로 반환
        if all(m.get("originalName") for m in mappings):
            return mappings
        
        # 메타데이터 로드
        try:
            metadata = await self._load_template_metadata_direct(template_id, user_id)
            if not metadata:
                logger.warning(f"⚠️ 메타데이터 로드 실패: {template_id}, originalName 추가 스킵")
                return mappings
            
            # elementId → (originalName, originalText) 매핑 생성
            element_info = {}
            for slide in metadata.get("slides", []):
                for elem in slide.get("elements", []):
                    elem_id = elem.get("id", "")
                    original_name = elem.get("original_name", "")
                    original_text = elem.get("content", "")
                    if elem_id:
                        element_info[elem_id] = {
                            "name": original_name,
                            "text": original_text
                        }
            
            logger.info(f"📋 메타데이터에서 {len(element_info)}개 요소 정보 로드")
            
            # 매핑에 originalName, originalText 추가
            enriched = []
            for m in mappings:
                elem_id = m.get("elementId", "")
                if elem_id in element_info:
                    info = element_info[elem_id]
                    if not m.get("originalName"):
                        m["originalName"] = info["name"]
                    if not m.get("originalText"):
                        m["originalText"] = info["text"]
                enriched.append(m)
            
            enriched_count = sum(1 for m in enriched if m.get("originalName"))
            logger.info(f"✅ 요소 정보(Name/Text) 추가 완료: {enriched_count}/{len(enriched)} 매핑")
            
            return enriched
            
        except Exception as e:
            logger.warning(f"⚠️ originalName 추가 실패: {e}")
            return mappings
    
    def _generate_mappings_from_slides_data(
        self,
        slides_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """UI 편집 데이터(slides_data)에서 text_box_mappings 생성
        
        slides_data 구조:
        [
            {
                "index": 1,  # 1-based
                "role": "title",
                "elements": [
                    {"id": "textbox-0-0", "text": "제목", "role": "slide_title"},
                    {"id": "textbox-0-1", "text": "부제목", "role": "key_message"},
                    {"id": "shape-0-2", "text": "도형 내 텍스트", "role": "body"},
                    ...
                ]
            },
            ...
        ]
        
        Returns:
            text_box_mappings 형식:
            [
                {
                    "slideIndex": 0,  # 0-based
                    "elementId": "textbox-0-0",
                    "objectType": "textbox",
                    "action": "replace_content",
                    "newContent": "새 내용",
                    "isEnabled": True
                },
                {
                    "slideIndex": 0,
                    "elementId": "shape-0-2",
                    "objectType": "shape",  # shape-X-X 요소는 shape 타입
                    "action": "replace_content",
                    "newContent": "새 내용",
                    "isEnabled": True
                },
                ...
            ]
        """
        mappings = []
        
        for slide_data in slides_data:
            slide_index = slide_data.get("index", 1)
            # UI index는 1-based, 내부 처리는 0-based
            zero_based_idx = slide_index - 1 if slide_index >= 1 else slide_index
            
            for elem in slide_data.get("elements", []):
                elem_id = elem.get("id", "")
                text = elem.get("text", "")
                
                if not elem_id or not text:
                    continue
                
                # element ID에서 objectType 추론
                # 형식: textbox-X-X, shape-X-X, table-X-X, image-X-X 등
                object_type = "textbox"  # 기본값
                if elem_id.startswith("shape-"):
                    object_type = "shape"
                elif elem_id.startswith("table-"):
                    object_type = "table"
                elif elem_id.startswith("image-"):
                    object_type = "image"
                elif elem_id.startswith("chart-"):
                    object_type = "chart"
                elif elem_id.startswith("textbox-"):
                    object_type = "textbox"
                
                mappings.append({
                    "slideIndex": zero_based_idx,
                    "elementId": elem_id,
                    "objectType": object_type,
                    "action": "replace_content",
                    "newContent": text,
                    "isEnabled": True,
                })
        
        logger.debug(f"📋 생성된 매핑: {len(mappings)}개 (textbox: {sum(1 for m in mappings if m['objectType']=='textbox')}, shape: {sum(1 for m in mappings if m['objectType']=='shape')}, 기타: {sum(1 for m in mappings if m['objectType'] not in ['textbox', 'shape'])})")
        return mappings
    
    def _merge_mappings(
        self,
        original_mappings: List[Dict[str, Any]],
        regenerated_mappings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        🆕 v3.6: elementId 기준으로 기존 매핑에 재생성된 매핑을 병합
        
        기존 매핑에서 재생성된 elementId의 항목을 새 값으로 교체합니다.
        이렇게 하면 정상 콘텐츠는 보존되고 문제 요소만 갱신됩니다.
        
        Args:
            original_mappings: 기존 매핑 리스트
            regenerated_mappings: 재생성된 매핑 리스트 (문제 요소만)
            
        Returns:
            병합된 매핑 리스트
        """
        if not regenerated_mappings:
            return original_mappings
        
        # 재생성된 매핑을 elementId로 인덱싱
        regen_by_id = {m.get('elementId'): m for m in regenerated_mappings}
        
        # 기존 매핑에서 재생성된 항목 교체
        merged = []
        replaced_count = 0
        
        for orig in original_mappings:
            elem_id = orig.get('elementId')
            if elem_id in regen_by_id:
                # 재생성된 매핑으로 교체
                merged.append(regen_by_id[elem_id])
                replaced_count += 1
            else:
                # 기존 매핑 유지
                merged.append(orig)
        
        logger.info(f"  📋 [MergeMappings] {replaced_count}개 매핑 갱신, 총 {len(merged)}개")
        
        return merged


# -----------------------------------------------------------------------------
# Stateless facade
# -----------------------------------------------------------------------------


class UnifiedPresentationAgentFacade:
    """Facade that creates a fresh agent instance per request.

    This avoids cross-request state pollution caused by shared instance fields
    (steps/tools_used/_latest_* etc.) when running concurrent requests.
    """

    name: str = "unified_presentation_agent"
    description: str = "Unified agent for Quick and Template PPT generation"
    version: str = UnifiedPresentationAgent.version

    async def run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return await UnifiedPresentationAgent().run(*args, **kwargs)

    async def generate_content_for_template(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return await UnifiedPresentationAgent().generate_content_for_template(*args, **kwargs)

    async def build_ppt_from_ui_data(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return await UnifiedPresentationAgent().build_ppt_from_ui_data(*args, **kwargs)


# Public singleton symbol (now stateless)
unified_presentation_agent = UnifiedPresentationAgentFacade()


# --- Tool Wrapper for LangChain Compatibility ---

from pydantic import BaseModel, Field

class PresentationAgentInput(BaseModel):
    """Input schema for :class:`PresentationAgentTool`."""

    topic: Optional[str] = Field(default=None, description="프레젠테이션 제목/주제")
    context_text: str = Field(..., description="PPT 생성에 사용할 컨텍스트 텍스트")
    documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="선택된 문서 목록 (메타데이터 참조용)",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="추가 옵션 (template_style, include_charts, max_slides 등)",
    )
    template_style: str = Field(
        default="business",
        description="템플릿 스타일 (business | modern | minimal | playful)",
    )
    presentation_type: str = Field(
        default="general",
        description="프레젠테이션 유형 (general | product_introduction)",
    )
    quick_mode: bool = Field(
        default=False,
        description="빠른 생성 모드 (레거시 호환용)",
    )


class PresentationAgentTool(BaseTool):
    """LangChain tool wrapper for the Unified Presentation Agent."""

    name: str = "presentation_agent_tool"
    description: str = (
        "Generates professional presentations from document summaries or context text. "
        "Uses the Unified Presentation Agent (Quick/Template modes)."
    )
    args_schema: Type[BaseModel] = PresentationAgentInput

    async def _arun(
        self,
        context_text: str,
        topic: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        template_style: str = "business",
        presentation_type: str = "general",
        quick_mode: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        docs = documents or []
        options = options or {}

        # Topic Inference
        inferred_topic = topic
        if not inferred_topic:
            # Simple inference logic (can be improved)
            if docs:
                first_doc = docs[0]
                filename = first_doc.get("fileName") or first_doc.get("file_name") or first_doc.get("name")
                if filename:
                    import re
                    inferred_topic = re.sub(r"\.(docx?|pdf|txt|pptx?)$", "", filename, flags=re.IGNORECASE)
            
            if not inferred_topic and context_text:
                lines = [ln.strip() for ln in context_text.split("\n") if ln.strip()]
                if lines:
                    import re
                    first_line = lines[0]
                    cleaned = re.sub(r"^[#>*\s]*", "", first_line).strip()
                    if cleaned and len(cleaned) <= 100:
                        inferred_topic = cleaned
            
            if not inferred_topic:
                inferred_topic = "프레젠테이션"

        # Mode Selection
        mode = options.get("mode")
        if not mode:
            mode = "quick" if quick_mode else "quick" # Default to quick for now unless template specified
            if options.get("template_id"):
                mode = "template"

        logger.info(
            "🎨 [PresentationAgentTool] Unified Agent 호출: mode=%s, topic='%s'",
            mode,
            inferred_topic[:50]
        )

        # Pattern selection
        # Default to tool_calling (Phase 3), with runtime fallback to legacy react
        # for models/providers that do not support tool calling.
        pattern = options.get("pattern") or "tool_calling"

        result = await unified_presentation_agent.run(
            mode=mode,
            pattern=pattern,
            topic=inferred_topic,
            context_text=context_text,
            template_id=options.get("template_id"),
            max_slides=int(options.get("max_slides", 8)),
            **kwargs,
        )

        # Fallback: tool calling not supported
        if pattern == "tool_calling" and not result.get("success") and isinstance(result.get("error"), str):
            err = result.get("error") or ""
            if "does not support tool calling" in err or "bind_tools" in err:
                logger.warning(
                    "⚠️ [PresentationAgentTool] tool_calling not available; falling back to react: %s",
                    err,
                )
                result = await unified_presentation_agent.run(
                    mode=mode,
                    pattern="react",
                    topic=inferred_topic,
                    context_text=context_text,
                    template_id=options.get("template_id"),
                    max_slides=int(options.get("max_slides", 8)),
                    **kwargs,
                )

        return result

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return asyncio.run(self._arun(*args, **kwargs))


presentation_agent_tool = PresentationAgentTool()


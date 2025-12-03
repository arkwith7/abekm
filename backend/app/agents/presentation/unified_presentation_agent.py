"""
Unified Presentation Agent

Quick PPT와 Template PPT를 모두 처리하는 통합 에이전트.
ReAct와 Plan-Execute 패턴을 모두 지원합니다.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from loguru import logger

try:
    from langchain_core.tools import BaseTool
    from langchain_core.messages import HumanMessage, AIMessage
except ImportError:
    from langchain.tools import BaseTool
    from langchain.schema import HumanMessage, AIMessage

from app.agents.presentation.base_agent import BaseAgent
from app.services.core.ai_service import ai_service
from app.utils.prompt_loader import load_presentation_prompt

# Tools import
from app.tools.presentation.outline_generation_tool import outline_generation_tool
from app.tools.presentation.quick_pptx_builder_tool import quick_pptx_builder_tool
from app.tools.presentation.template_analyzer_tool import template_analyzer_tool
from app.tools.presentation.content_mapping_tool import content_mapping_tool
from app.tools.presentation.templated_pptx_builder_tool import templated_pptx_builder_tool
from app.tools.presentation.visualization_tool import visualization_tool
from app.tools.presentation.ppt_quality_validator_tool import ppt_quality_validator_tool


class PresentationMode(str, Enum):
    """프레젠테이션 생성 모드"""
    QUICK = "quick"  # Quick PPT (템플릿 미적용)
    TEMPLATE = "template"  # Template PPT (템플릿 기반)


class ExecutionPattern(str, Enum):
    """실행 패턴"""
    REACT = "react"  # ReAct (Reasoning + Acting)
    PLAN_EXECUTE = "plan_execute"  # Plan-and-Execute


LLM_TIMEOUT_SECONDS = 120


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
            "ppt_quality_validator_tool": ppt_quality_validator_tool,
            "visualization_tool": visualization_tool,
            
            # Quick PPT 전용 도구
            "quick_pptx_builder_tool": quick_pptx_builder_tool,
            
            # Template PPT 전용 도구
            "template_analyzer_tool": template_analyzer_tool,
            "content_mapping_tool": content_mapping_tool,
            "templated_pptx_builder_tool": templated_pptx_builder_tool,
        }
        
        self.max_iterations = 10
        
        logger.info(
            f"🎨 {self.name} v{self.version} 초기화 완료: {len(self.tools)}개 도구 등록"
        )
    
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
2. quick_pptx_builder_tool 실행 → PPTX 파일 생성 (2단계 - 반드시 실행!)
3. 파일 생성 완료 후 Final Answer 출력

⚠️ 중요: outline_generation_tool 실행 후 반드시 quick_pptx_builder_tool을 호출해야 합니다!
⚠️ quick_pptx_builder_tool 호출 없이 Final Answer를 출력하면 안됩니다!"""
        
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

## 필수 워크플로우 (Template PPT - ReAct) - 4단계 순서대로 실행!
1. outline_generation_tool 실행 → deck_spec 획득 (1단계)
2. template_analyzer_tool 실행 → template_structure 획득 (2단계)
3. content_mapping_tool 실행 → mappings 생성 (3단계)
4. templated_pptx_builder_tool 실행 → PPTX 파일 생성 (4단계 - 반드시 실행!)
5. 파일 생성 완료 후 Final Answer 출력

## 사용 가능한 도구
- outline_generation_tool: 컨텍스트에서 아웃라인 생성
- template_analyzer_tool: 템플릿 구조 분석
- content_mapping_tool: 아웃라인과 템플릿 매핑
- templated_pptx_builder_tool: 최종 PPTX 파일 생성

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
                "quick_pptx_builder_tool",
                "visualization_tool",
                "ppt_quality_validator_tool",
            ]
        else:  # TEMPLATE
            return [
                "outline_generation_tool",
                "template_analyzer_tool",
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
            **kwargs: 추가 파라미터
            
        Returns:
            실행 결과 딕셔너리
        """
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
        
        # 실행 초기화
        self._init_execution()
        
        logger.info(
            f"🚀 [{self.name}] 시작: mode={mode}, pattern={pattern}, "
            f"topic='{topic[:50]}', max_slides={max_slides}"
        )
        
        # 패턴에 따라 분기
        if pattern_enum == ExecutionPattern.REACT:
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
                    required_tool = "quick_pptx_builder_tool" if mode == PresentationMode.QUICK else "templated_pptx_builder_tool"
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
                        elif action_name == "templated_pptx_builder_tool" and template_id:
                            action_input["template_id"] = template_id
                    
                    # outline_generation_tool에 필수 파라미터 자동 주입
                    if action_name == "outline_generation_tool":
                        if "topic" not in action_input or not action_input.get("topic"):
                            action_input["topic"] = topic
                        if "context_text" not in action_input or not action_input.get("context_text"):
                            action_input["context_text"] = context_text
                        if "max_slides" not in action_input:
                            action_input["max_slides"] = max_slides

                    # deck_spec 자동 주입 (Quick/Template 공통)
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
                            
                    # template_structure 자동 주입 (Template 전용)
                    if action_name == "content_mapping_tool":
                        if ("template_structure" not in action_input or not action_input.get("template_structure")) and self._latest_template_structure:
                            action_input["template_structure"] = self._latest_template_structure
                            logger.info(f"💉 [{self.name}] template_structure 자동 주입 완료")
                    
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
                    
                    self._log_step("OBSERVATION", json.dumps(observation, ensure_ascii=False)[:500], metadata=observation)
                    self._tools_used.append(action_name)

                    # 🚀 [최적화] 파일 생성 도구가 성공했다면 즉시 종료 (LLM 요약 생략)
                    if action_name in ["quick_pptx_builder_tool", "templated_pptx_builder_tool"]:
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
                        next_step_hint = "\n\n⚠️ 다음 단계: deck_spec을 사용하여 quick_pptx_builder_tool을 호출하세요."
                    elif action_name == "outline_generation_tool" and mode == PresentationMode.TEMPLATE:
                        next_step_hint = "\n\n⚠️ 다음 단계: template_analyzer_tool을 호출하여 템플릿 구조를 분석하세요."
                    elif action_name == "template_analyzer_tool":
                        next_step_hint = "\n\n⚠️ 다음 단계: content_mapping_tool을 호출하여 아웃라인과 템플릿을 매핑하세요."
                    elif action_name == "content_mapping_tool":
                        next_step_hint = "\n\n⚠️ 다음 단계: templated_pptx_builder_tool을 호출하여 최종 PPTX 파일을 생성하세요."
                    
                    conversation.append({
                        "role": "user", 
                        "content": f"**Observation**: {json.dumps(observation, ensure_ascii=False)}{next_step_hint}"
                    })

                    # Quick 모드에서 outline 생성 직후 Quick Builder를 자동 실행하여 중간 정지 방지
                    if (
                        mode == PresentationMode.QUICK
                        and action_name == "outline_generation_tool"
                        and "quick_pptx_builder_tool" not in self._tools_used
                    ):
                        auto_executed, auto_tool, auto_result = await self._maybe_autorun_required_tool(
                            required_tool="quick_pptx_builder_tool",
                            conversation=conversation,
                            template_id=template_id,
                            mode=mode,
                        )

                        if auto_executed and auto_tool == "quick_pptx_builder_tool":
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
                            hint = "**Action**: quick_pptx_builder_tool\n**Action Input**:\n```json\n{\"deck_spec\": {}}\n```"
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
            plan_response_data = await asyncio.wait_for(
                ai_service.chat_completion(
                    messages=messages,
                    provider="bedrock",
                    temperature=0.0,
                    max_tokens=2000,
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
                    {"step": 2, "tool": "quick_pptx_builder_tool", "description": "PPTX 생성"},
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
        
        elif tool_name == "quick_pptx_builder_tool":
            outline_result = execution_results.get("outline_generation_tool", {})
            deck_spec = outline_result.get("deck_spec", {})
            return {
                "deck_spec": deck_spec,
            }
        
        elif tool_name == "template_analyzer_tool":
            return {
                "template_id": template_id,
            }
        
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
            return {
                "deck_spec": outline_result.get("deck_spec", {}),
                "template_id": template_id,
                "mappings": mapping_result.get("mappings", []),
            }
        
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
            if required_tool == "quick_pptx_builder_tool":
                action_template = """**Thought**: PPT 파일 생성
**Action**: quick_pptx_builder_tool
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
            if required_tool == "quick_pptx_builder_tool" and self._latest_deck_spec:
                tool_to_run = "quick_pptx_builder_tool"
                action_input = {"deck_spec": self._latest_deck_spec}

        elif mode == PresentationMode.TEMPLATE:
            # Template Mode: 의존성 체인 확인 및 순차적 자동 실행
            
            # 1. Template Analyzer (아직 실행 안 됨)
            if "template_analyzer_tool" not in self._tools_used and template_id:
                tool_to_run = "template_analyzer_tool"
                action_input = {"template_id": template_id}
            
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


# Singleton instance
unified_presentation_agent = UnifiedPresentationAgent()


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

        result = await unified_presentation_agent.run(
            mode=mode,
            pattern="react", # Default pattern
            topic=inferred_topic,
            context_text=context_text,
            template_id=options.get("template_id"),
            max_slides=int(options.get("max_slides", 8)),
            **kwargs
        )

        return result

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return asyncio.run(self._arun(*args, **kwargs))


presentation_agent_tool = PresentationAgentTool()


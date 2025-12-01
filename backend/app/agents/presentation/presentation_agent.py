"""ReAct 기반 프레젠테이션 에이전트와 LangChain 호환 툴."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency for LangChain compatibility
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:  # pragma: no cover
    from langchain.tools import BaseTool  # type: ignore

from app.services.core.ai_service import ai_service
from app.tools.presentation.outline_generation_tool import outline_generation_tool
from app.tools.presentation.quick_pptx_builder_tool import quick_pptx_builder_tool
from app.tools.presentation.visualization_tool import visualization_tool
from app.tools.presentation.ppt_quality_validator_tool import ppt_quality_validator_tool
from app.utils.prompt_loader import load_presentation_prompt


LLM_TIMEOUT_SECONDS = 120


def _load_react_system_prompt() -> str:
    """ReAct Agent 시스템 프롬프트 로드."""
    try:
        return load_presentation_prompt("react_agent_system")
    except FileNotFoundError:
        logger.warning("react_agent_system.prompt 파일을 찾을 수 없습니다. 기본 프롬프트 사용")
        return (
            "당신은 전문 프레젠테이션 생성 AI 에이전트입니다.\n"
            "사용자의 요청을 분석하고, 도구를 실행하여 PPT를 생성합니다.\n\n"
            "## 필수 워크플로우\n"
            "1. outline_generation_tool 실행 → deck_spec 획득\n"
            "2. quick_pptx_builder_tool 실행 → PPTX 파일 생성 (필수!)\n"
            "3. Final Answer로 결과 반환\n\n"
            "⚠️ quick_pptx_builder_tool 호출 없이 Final Answer를 출력하지 마세요!"
        )


class PresentationReActAgent:
    """ReAct 패턴 기반 PPT 생성 에이전트."""

    name: str = "presentation_react_agent"
    description: str = "ReAct 패턴 기반 PPT 생성 에이전트"
    version: str = "1.0.0"

    def __init__(self) -> None:
        self.tools: Dict[str, BaseTool] = {
            "outline_generation_tool": outline_generation_tool,
            "visualization_tool": visualization_tool,
            "quick_pptx_builder_tool": quick_pptx_builder_tool,
            "ppt_quality_validator_tool": ppt_quality_validator_tool,
        }
        self.max_iterations = 10
        self._execution_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._steps: List[Dict[str, Any]] = []
        self._tools_used: List[str] = []

    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답에서 Thought/Action/Final Answer를 파싱."""

        result = {
            "thought": "",
            "action": None,
            "action_input": None,
            "final_answer": None,
        }

        thought_match = response.split("**Thought**:")
        if len(thought_match) > 1:
            thought_part = (
                thought_match[1]
                .split("**Action")[0]
                .split("**Final")[0]
                .strip()
            )
            result["thought"] = thought_part[:500]

        if "**Action**:" in response:
            action_part = response.split("**Action**:")[1]
            action_name = action_part.split("**")[0].split("\n")[0].strip()
            result["action"] = action_name

            if "**Action Input**:" in response:
                input_part = response.split("**Action Input**:")[1]
                json_block = (
                    input_part.split("**Thought")[0]
                    .split("**Final")[0]
                    .strip()
                )

                if "```json" in json_block:
                    json_block = json_block.split("```json")[1].split("```")[0]
                elif "```" in json_block:
                    json_block = json_block.split("```")[1].split("```")[0]

                try:
                    result["action_input"] = json.loads(json_block)
                except json.JSONDecodeError:
                    logger.warning("Action Input JSON 파싱 실패: %s", json_block[:200])
                    result["action_input"] = {"raw": json_block}

            return result

        if "**Final Answer**:" in response:
            final_part = response.split("**Final Answer**:")[-1].strip()
            result["final_answer"] = final_part

        return result

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """도구 실행 및 예외 처리."""

        if tool_name not in self.tools:
            return {"success": False, "error": f"알 수 없는 도구: {tool_name}"}

        tool = self.tools[tool_name]

        try:
            logger.info("🔧 [ReActAgent] 도구 실행: %s", tool_name)
            logger.debug("  입력: %s", json.dumps(tool_input, ensure_ascii=False)[:200])

            if hasattr(tool, "_arun"):
                result = await tool._arun(**tool_input)
            else:  # pragma: no cover - sync fallback
                result = tool._run(**tool_input)

            logger.info("✅ [ReActAgent] 도구 완료: %s", tool_name)
            return result

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ [ReActAgent] 도구 실행 실패: %s - %s", tool_name, exc)
            return {"success": False, "error": str(exc)}

    def _log_step(
        self,
        step_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._steps.append(step)
        logger.info("📝 [%s] %s", step_type, content[:100])

    async def run(
        self,
        user_request: str,
        context_text: str,
        topic: Optional[str] = None,
        max_slides: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """ReAct 루프 실행."""

        self._execution_id = str(uuid.uuid4())
        self._start_time = datetime.utcnow()
        self._steps = []
        self._tools_used = []

        logger.info("🚀 [ReActAgent] 시작: execution_id=%s", self._execution_id)

        safe_context = context_text or ""
        initial_message = (
            f"사용자 요청: {user_request}\n\n"
            f"주제: {topic or '자동 추론 필요'}\n"
            f"최대 슬라이드 수: {max_slides}\n\n"
            "콘텐츠:\n```\n"
            f"{safe_context[:8000]}\n"
            "```"
        )

        messages = [
            {"role": "system", "content": _load_react_system_prompt()},
            {"role": "user", "content": initial_message},
        ]

        self._log_step("START", f"ReAct Agent 시작: {user_request[:50]}")

        iteration = 0
        final_result: Optional[Dict[str, Any]] = None
        deck_spec: Optional[Dict[str, Any]] = None
        regenerated_outline_text: Optional[str] = None

        while iteration < self.max_iterations:
            iteration += 1
            logger.info("🔄 [ReActAgent] Iteration %s/%s", iteration, self.max_iterations)

            try:
                response_text = ""

                async def collect_stream() -> None:
                    nonlocal response_text
                    async for chunk in ai_service.chat_stream(
                        messages=messages,
                        provider="bedrock",
                        temperature=0.0,
                    ):
                        if isinstance(chunk, str):
                            response_text += chunk
                        elif getattr(chunk, "content", None):
                            response_text += str(chunk.content)

                try:
                    await asyncio.wait_for(collect_stream(), timeout=LLM_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    logger.warning(
                        "⏰ [ReActAgent] LLM 응답 타임아웃 (%s초)",
                        LLM_TIMEOUT_SECONDS,
                    )
                    if not response_text:
                        continue

                parsed = self._parse_agent_response(response_text)

                if parsed["thought"]:
                    self._log_step("THOUGHT", parsed["thought"])

                if parsed["final_answer"]:
                    self._log_step("FINAL_ANSWER", parsed["final_answer"])

                    # 🔍 [Safety Check] deck_spec은 있는데 PPT 생성 도구가 실행되지 않은 경우 강제 실행
                    if deck_spec and "quick_pptx_builder_tool" not in self._tools_used:
                        logger.warning("🔧 [ReActAgent] Final Answer 감지되었으나 PPT 생성 도구가 실행되지 않음. 강제 실행합니다.")
                        try:
                            fallback_result = await self._execute_tool(
                                "quick_pptx_builder_tool",
                                {"deck_spec": deck_spec},
                            )
                            if fallback_result.get("success"):
                                self._tools_used.append("quick_pptx_builder_tool")
                                # 메타데이터가 있는 스텝 추가 (나중에 file_name 추출용)
                                self._log_step("OBSERVATION", "Fallback PPT Generation Success", metadata=fallback_result)
                        except Exception as exc:
                            logger.error("❌ [ReActAgent] 강제 PPT 생성 실패: %s", exc)

                    file_path = None
                    file_name = None
                    slide_count = 0

                    # 1. 도구 실행 결과에서 파일 정보 우선 검색 (신뢰도 높음)
                    for step in reversed(self._steps):
                        metadata = step.get("metadata", {})
                        if isinstance(metadata, dict) and metadata.get("file_name"):
                            file_name = metadata.get("file_name")
                            file_path = metadata.get("file_path", file_name)
                            slide_count = metadata.get("slide_count", 0)
                            break

                    # 2. 도구 결과가 없으면 Final Answer 텍스트 파싱 (신뢰도 낮음)
                    if not file_path:
                        file_path_match = re.search(
                            r"\[file_path=([^\]]+)\]",
                            parsed["final_answer"],
                        )
                        if file_path_match:
                            file_path = file_path_match.group(1).strip()
                            file_name = (
                                file_path.split("/")[-1]
                                if "/" in file_path
                                else file_path
                            )

                    execution_time = (datetime.utcnow() - self._start_time).total_seconds()

                    final_result = {
                        "success": True,
                        "file_path": file_path,
                        "file_name": file_name,
                        "slide_count": slide_count,
                        "final_answer": parsed["final_answer"],
                        "execution_id": self._execution_id,
                        "steps": self._steps,
                        "iterations": iteration,
                        "execution_time": execution_time,
                        "tools_used": self._tools_used,
                        "outline_text": regenerated_outline_text,
                    }
                    break

                if parsed["action"] and parsed["action_input"]:
                    action_name = parsed["action"].strip()
                    action_input = parsed["action_input"]

                    self._log_step(
                        "ACTION",
                        f"{action_name}: {json.dumps(action_input, ensure_ascii=False)[:200]}",
                    )

                    observation = await self._execute_tool(action_name, action_input)

                    if (
                        action_name == "outline_generation_tool"
                        and isinstance(observation, dict)
                        and observation.get("success")
                    ):
                        deck_spec = observation.get("deck")
                        if observation.get("outline_text"):
                            regenerated_outline_text = observation.get("outline_text")

                    if action_name not in self._tools_used:
                        self._tools_used.append(action_name)

                    obs_summary = json.dumps(observation, ensure_ascii=False)[:500]
                    self._log_step("OBSERVATION", obs_summary, metadata=observation)

                    messages.append({"role": "assistant", "content": response_text})
                    messages.append(
                        {
                            "role": "user",
                            "content": "**Observation**: "
                            + json.dumps(observation, ensure_ascii=False)
                            + "\n\n다음 단계를 진행하세요.",
                        }
                    )
                else:
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append(
                        {
                            "role": "user",
                            "content": "응답 형식이 올바르지 않습니다. **Thought**, **Action**, **Action Input** 형식으로 다시 응답해주세요.",
                        }
                    )

            except Exception as exc:  # pragma: no cover - defensive
                logger.error("❌ [ReActAgent] 오류: %s", exc, exc_info=True)
                self._log_step("ERROR", str(exc))
                messages.append(
                    {
                        "role": "user",
                        "content": f"오류가 발생했습니다: {exc}\n다른 방법을 시도하거나 Final Answer로 종료해주세요.",
                    }
                )

        if final_result is None:
            execution_time = (datetime.utcnow() - self._start_time).total_seconds()
            file_path = None
            file_name = None
            slide_count = 0

            for step in reversed(self._steps):
                metadata = step.get("metadata", {})
                if isinstance(metadata, dict) and metadata.get("file_name"):
                    file_name = metadata.get("file_name")
                    file_path = metadata.get("file_path", file_name)
                    slide_count = metadata.get("slide_count", 0)
                    break

            if not file_name and deck_spec:
                logger.info("🔧 [ReActAgent] 폴백: deck_spec으로 직접 PPT 생성")
                try:
                    fallback_result = await self._execute_tool(
                        "quick_pptx_builder_tool",
                        {"deck_spec": deck_spec},
                    )
                    if fallback_result.get("success"):
                        file_name = fallback_result.get("file_name")
                        file_path = fallback_result.get("file_path", file_name)
                        slide_count = fallback_result.get("slide_count", 0)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error("❌ [ReActAgent] 폴백 PPT 생성 실패: %s", exc)

            if file_name:
                final_result = {
                    "success": True,
                    "file_path": file_path,
                    "file_name": file_name,
                    "slide_count": slide_count,
                    "final_answer": f"PPT 파일이 생성되었습니다: {file_name}",
                    "execution_id": self._execution_id,
                    "steps": self._steps,
                    "iterations": iteration,
                    "execution_time": execution_time,
                    "tools_used": self._tools_used,
                    "outline_text": regenerated_outline_text,
                }
            else:
                final_result = {
                    "success": False,
                    "error": f"최대 반복 횟수({self.max_iterations}) 초과",
                    "execution_id": self._execution_id,
                    "steps": self._steps,
                    "iterations": iteration,
                    "execution_time": execution_time,
                    "tools_used": self._tools_used,
                }

        logger.info(
            "✅ [ReActAgent] 완료: %s, %.2f초",
            final_result.get("success"),
            final_result.get("execution_time", 0),
        )
        return final_result


class QuickPPTReActAgent(PresentationReActAgent):
    """빠른 PPT 생성을 위한 경량 ReAct 에이전트."""

    name: str = "quick_ppt_react_agent"
    description: str = "Quick PPT 생성 전용 ReAct 에이전트"

    def __init__(self) -> None:
        super().__init__()
        self.max_iterations = 7


presentation_react_agent = PresentationReActAgent()
quick_ppt_react_agent = QuickPPTReActAgent()


class PresentationAgent:
    """레거시 orchestrator API를 유지하는 ReAct 래퍼."""

    name: str = "presentation_agent"
    description: str = "ReAct 기반 PPT 생성 orchestrator"
    version: str = "3.0.0"

    def __init__(self) -> None:
        self._react_agent = QuickPPTReActAgent()

    async def execute(
        self,
        mode: str,
        topic: str,
        context_text: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        max_slides = int(options.get("max_slides", 10))
        user_request = options.get("user_request") or topic or "프레젠테이션 생성"

        logger.info(
            "🎯 [PresentationAgent] ReAct 실행: mode=%s, topic='%s'",
            mode,
            topic[:50] if topic else "N/A",
        )

        result = await self._react_agent.run(
            user_request=user_request,
            context_text=context_text,
            topic=topic,
            max_slides=max_slides,
        )

        formatted = {
            "success": result.get("success", False),
            "mode": mode,
            "strategy": "react",
            "topic": topic,
            "file_path": result.get("file_path"),
            "file_name": result.get("file_name"),
            "slide_count": result.get("slide_count"),
            "execution_id": result.get("execution_id"),
            "execution_time": result.get("execution_time"),
            "steps": result.get("steps", []),
            "tools_used": result.get("tools_used", []),
            "final_answer": result.get("final_answer"),
            "outline_text": result.get("outline_text"),
        }

        if not formatted["success"]:
            formatted["error"] = result.get("error", "Presentation generation failed")

        return formatted


presentation_agent = PresentationAgent()


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
    """LangChain tool wrapper for the ReAct presentation agent."""

    name: str = "presentation_agent_tool"
    description: str = (
        "Generates professional presentations from document summaries or context text. "
        "Now backed by the ReAct agent pipeline for tool-based reasoning."
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

        document_filename = None
        if docs:
            first_doc = docs[0]
            document_filename = (
                first_doc.get("fileName")
                or first_doc.get("file_name")
                or first_doc.get("name")
            )

        inferred_topic = topic or self._infer_topic_from_context(
            context_text,
            document_filename,
        )

        mode = options.get("mode")
        if not mode:
            mode = "quick" if quick_mode else "react"
        if options.get("style_reference_path"):
            mode = "style_transfer"

        enriched_options = {
            **options,
            "template_style": template_style,
            "presentation_type": presentation_type,
        }

        logger.info(
            "🎨 [PresentationAgentTool] 호출: mode=%s, topic='%s'",
            mode,
            inferred_topic[:50] if inferred_topic else "N/A",
        )

        result = await presentation_agent.execute(
            mode=mode,
            topic=inferred_topic,
            context_text=context_text,
            options=enriched_options,
        )

        return result

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - sync fallback
        return asyncio.run(self._arun(*args, **kwargs))

    def _infer_topic_from_context(
        self,
        context_text: str,
        document_filename: Optional[str] = None,
    ) -> str:
        if document_filename:
            clean_name = re.sub(
                r"\.(docx?|pdf|txt|pptx?)$",
                "",
                document_filename,
                flags=re.IGNORECASE,
            )
            return clean_name

        if context_text:
            lines = [ln.strip() for ln in context_text.split("\n") if ln.strip()]
            if lines:
                first_line = lines[0]
                cleaned = re.sub(r"^[#>*\s]*", "", first_line).strip()
                if cleaned and len(cleaned) <= 100:
                    return cleaned

        return "프레젠테이션"


presentation_agent_tool = PresentationAgentTool()

__all__ = [
    "PresentationReActAgent",
    "QuickPPTReActAgent",
    "presentation_react_agent",
    "quick_ppt_react_agent",
    "PresentationAgent",
    "presentation_agent",
    "PresentationAgentTool",
    "presentation_agent_tool",
]

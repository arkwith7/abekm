"""
Base Agent for Presentation Generation

공통 에이전트 로직을 제공하는 베이스 클래스.
모든 프레젠테이션 에이전트는 이 클래스를 상속받아야 합니다.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool


class BaseAgent(ABC):
    """프레젠테이션 에이전트 베이스 클래스"""
    
    name: str = "base_agent"
    description: str = "Base presentation agent"
    version: str = "1.0.0"
    
    def __init__(self) -> None:
        self.tools: Dict[str, BaseTool] = {}
        self.max_iterations: int = 10
        self._execution_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._steps: List[Dict[str, Any]] = []
        self._tools_used: List[str] = []
    
    @abstractmethod
    def _load_system_prompt(self) -> str:
        """시스템 프롬프트 로드 (서브클래스에서 구현)"""
        pass
    
    @abstractmethod
    async def run(self, **kwargs: Any) -> Dict[str, Any]:
        """에이전트 실행 (서브클래스에서 구현)"""
        pass
    
    # ===== 공통 메서드 =====
    
    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """
        LLM 응답에서 Thought/Action/Final Answer를 파싱.
        
        Args:
            response: LLM 응답 텍스트
            
        Returns:
            파싱된 결과 딕셔너리:
            - thought: 사고 과정
            - action: 실행할 도구 이름
            - action_input: 도구 입력 파라미터
            - final_answer: 최종 답변
        """
        import re
        
        result = {
            "thought": "",
            "action": None,
            "action_input": None,
            "final_answer": None,
        }
        
        # 디버그용 로깅
        logger.debug(f"🔍 파싱할 응답 (처음 300자): {response[:300]}")

        # Thought 추출 (여러 패턴 지원)
        thought_patterns = [
            r"\*\*Thought\*\*:\s*(.+?)(?=\*\*Action|\*\*Final|$)",
            r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)",
        ]
        for pattern in thought_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                result["thought"] = match.group(1).strip()[:500]
                break

        # Action 추출 (여러 패턴 지원) - 도구 이름에 _tool 포함된 것도 매칭
        action_patterns = [
            r"\*\*Action\*\*:\s*([\w_]+)",
            r"Action:\s*([\w_]+)",
        ]
        for pattern in action_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                result["action"] = match.group(1).strip()
                logger.debug(f"🔍 Action 감지: {result['action']}")
                break

        # Action Input 추출 - JSON 블록 찾기 (개선된 로직)
        if result["action"]:
            # 여러 JSON 추출 패턴 시도
            input_patterns = [
                r"\*\*Action Input\*\*:\s*```json\s*(\{[\s\S]*?\})\s*```",
                r"\*\*Action Input\*\*:\s*```\s*(\{[\s\S]*?\})\s*```",
                r"Action Input:\s*```json\s*(\{[\s\S]*?\})\s*```",
                r"Action Input:\s*```\s*(\{[\s\S]*?\})\s*```",
                r"\*\*Action Input\*\*:\s*(\{[^}]+\})",
                r"Action Input:\s*(\{[^}]+\})",
            ]
            
            for pattern in input_patterns:
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if match:
                    json_str = match.group(1).strip()
                    try:
                        # 먼저 원본 그대로 시도
                        result["action_input"] = json.loads(json_str)
                        logger.debug(f"🔍 Action Input 파싱 성공: {list(result['action_input'].keys())}")
                        break
                    except json.JSONDecodeError:
                        # 줄바꿈과 불필요한 공백 정리 후 재시도
                        json_str_cleaned = re.sub(r'\s+', ' ', json_str)
                        try:
                            result["action_input"] = json.loads(json_str_cleaned)
                            logger.debug(f"🔍 Action Input 파싱 성공 (정리 후): {list(result['action_input'].keys())}")
                            break
                        except json.JSONDecodeError as e:
                            logger.warning(f"Action Input JSON 파싱 실패: {e}, 원본: {json_str[:200]}")
                            continue
            
            # JSON 파싱 실패 시에도 Action이 있으면 빈 dict 설정
            # (단, 도구에서 필수 파라미터를 자동 주입하므로 괜찮음)
            if result["action_input"] is None:
                logger.warning(f"⚠️ Action '{result['action']}'에 대한 Input을 찾지 못함. 빈 dict 사용 (자동 주입 예정)")
                result["action_input"] = {}

        # Final Answer 추출 - Action이 없을 때만 Final Answer로 처리
        if result["action"] is None:
            final_patterns = [
                r"\*\*Final Answer\*\*:\s*(.+)",
                r"Final Answer:\s*(.+)",
            ]
            for pattern in final_patterns:
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if match:
                    result["final_answer"] = match.group(1).strip()
                    logger.debug(f"🔍 Final Answer 감지: {result['final_answer'][:100]}")
                    break

        return result
    
    async def _execute_tool(
        self, 
        tool_name: str, 
        tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        도구 실행 및 예외 처리.
        
        Args:
            tool_name: 도구 이름
            tool_input: 도구 입력 파라미터
            
        Returns:
            도구 실행 결과
        """
        if tool_name not in self.tools:
            return {"success": False, "error": f"알 수 없는 도구: {tool_name}"}

        tool = self.tools[tool_name]

        try:
            logger.info("🔧 [%s] 도구 실행: %s", self.name, tool_name)
            logger.debug("  입력: %s", json.dumps(tool_input, ensure_ascii=False)[:200])

            # 비동기/동기 실행
            if hasattr(tool, "_arun"):
                result = await tool._arun(**tool_input)
            else:
                result = tool._run(**tool_input)

            logger.info("✅ [%s] 도구 완료: %s", self.name, tool_name)
            return result

        except Exception as exc:
            logger.error("❌ [%s] 도구 실행 실패: %s - %s", self.name, tool_name, exc)
            return {"success": False, "error": str(exc)}
    
    def _log_step(
        self,
        step_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        실행 단계 로깅.
        
        Args:
            step_type: 단계 타입 (START, THOUGHT, ACTION, OBSERVATION, FINAL_ANSWER, ERROR)
            content: 단계 내용
            metadata: 추가 메타데이터
        """
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._steps.append(step)
        logger.info("📝 [%s] %s: %s", self.name, step_type, content[:100])
    
    def _init_execution(self, execution_id: Optional[str] = None) -> None:
        """실행 초기화"""
        self._execution_id = execution_id or str(uuid.uuid4())
        self._start_time = datetime.utcnow()
        self._steps = []
        self._tools_used = []
        
        logger.info("🚀 [%s] 시작: execution_id=%s", self.name, self._execution_id)
    
    def _finalize_execution(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        실행 종료 및 메타데이터 추가.
        
        Args:
            result: 실행 결과
            
        Returns:
            메타데이터가 추가된 결과
        """
        execution_time = (datetime.utcnow() - self._start_time).total_seconds()
        
        # NOTE: Phase 3 observability (01.docs/13.2): surface run_id/trace_id.
        # We alias both to execution_id for now so callers have stable correlation IDs
        # even when external tracing (e.g., LangSmith) is not configured.
        result.update({
            "execution_id": self._execution_id,
            "run_id": self._execution_id,
            "trace_id": self._execution_id,
            "execution_time": execution_time,
            "steps": self._steps,
            "tools_used": self._tools_used,
        })
        
        logger.info(
            "✅ [%s] 완료: success=%s, time=%.2fs, iterations=%s",
            self.name,
            result.get("success"),
            execution_time,
            len(self._steps)
        )
        
        return result
    
    def _extract_file_info_from_steps(self) -> tuple[Optional[str], Optional[str], int]:
        """
        실행 단계에서 파일 정보 추출.
        
        Returns:
            (file_path, file_name, slide_count)
        """
        file_path = None
        file_name = None
        slide_count = 0

        # 역순으로 도구 실행 결과 검색
        for step in reversed(self._steps):
            metadata = step.get("metadata", {})
            if isinstance(metadata, dict) and metadata.get("file_name"):
                file_name = metadata.get("file_name")
                file_path = metadata.get("file_path", file_name)
                slide_count = metadata.get("slide_count", 0)
                break

        return file_path, file_name, slide_count

"""
Agent State Management using ContextVar

요청별 격리된 상태 관리 (동시성 안전)
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class AgentExecutionState:
    """에이전트 실행 상태"""
    
    request_id: str
    agent_name: str
    start_time: datetime
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    
    # 실행 컨텍스트
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    
    # 메타데이터
    tools_used: List[str] = field(default_factory=list)
    llm_calls: int = 0
    tool_calls: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ContextVar를 사용한 스레드 안전 상태 관리
_agent_state: ContextVar[Optional[AgentExecutionState]] = ContextVar(
    "agent_execution_state",
    default=None
)


class AgentStateManager:
    """
    에이전트 상태 관리자
    
    ContextVar를 사용하여 비동기 태스크별로 격리된 상태를 관리합니다.
    """
    
    @staticmethod
    def init_state(
        request_id: str,
        agent_name: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentExecutionState:
        """
        새로운 실행 상태 초기화
        
        Args:
            request_id: 요청 ID
            agent_name: 에이전트 이름
            user_id: 사용자 ID
            session_id: 세션 ID
            **kwargs: 추가 입력 데이터
        
        Returns:
            초기화된 상태
        """
        state = AgentExecutionState(
            request_id=request_id,
            agent_name=agent_name,
            start_time=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            inputs=kwargs,
        )
        _agent_state.set(state)
        logger.debug(f"🔧 [StateManager] State initialized: {request_id} / {agent_name}")
        return state
    
    @staticmethod
    def get_state() -> Optional[AgentExecutionState]:
        """
        현재 실행 상태 가져오기
        
        Returns:
            현재 상태 (없으면 None)
        """
        return _agent_state.get()
    
    @staticmethod
    def update_state(**kwargs: Any) -> None:
        """
        실행 상태 업데이트
        
        Args:
            **kwargs: 업데이트할 필드
        """
        state = _agent_state.get()
        if state:
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
                else:
                    logger.warning(f"⚠️ [StateManager] Unknown field: {key}")
    
    @staticmethod
    def add_tool_usage(tool_name: str) -> None:
        """
        사용한 도구 기록
        
        Args:
            tool_name: 도구 이름
        """
        state = _agent_state.get()
        if state:
            state.tools_used.append(tool_name)
            state.tool_calls += 1
    
    @staticmethod
    def increment_llm_calls() -> None:
        """LLM 호출 횟수 증가"""
        state = _agent_state.get()
        if state:
            state.llm_calls += 1
    
    @staticmethod
    def add_error(error: str) -> None:
        """
        에러 기록
        
        Args:
            error: 에러 메시지
        """
        state = _agent_state.get()
        if state:
            state.errors.append(error)
            logger.error(f"❌ [StateManager] Error recorded: {error}")
    
    @staticmethod
    def add_warning(warning: str) -> None:
        """
        경고 기록
        
        Args:
            warning: 경고 메시지
        """
        state = _agent_state.get()
        if state:
            state.warnings.append(warning)
            logger.warning(f"⚠️ [StateManager] Warning recorded: {warning}")
    
    @staticmethod
    def add_intermediate_result(key: str, value: Any) -> None:
        """
        중간 결과 저장
        
        Args:
            key: 결과 키
            value: 결과 값
        """
        state = _agent_state.get()
        if state:
            state.intermediate_results[key] = value
    
    @staticmethod
    def get_intermediate_result(key: str) -> Optional[Any]:
        """
        중간 결과 가져오기
        
        Args:
            key: 결과 키
        
        Returns:
            저장된 값 (없으면 None)
        """
        state = _agent_state.get()
        if state:
            return state.intermediate_results.get(key)
        return None
    
    @staticmethod
    def clear_state() -> None:
        """상태 정리"""
        state = _agent_state.get()
        if state:
            logger.debug(f"🧹 [StateManager] State cleared: {state.request_id}")
        _agent_state.set(None)
    
    @staticmethod
    def get_summary() -> Dict[str, Any]:
        """
        상태 요약
        
        Returns:
            상태 요약 딕셔너리
        """
        state = _agent_state.get()
        if not state:
            return {"error": "No active state"}
        
        elapsed_seconds = (datetime.utcnow() - state.start_time).total_seconds()
        
        return {
            "request_id": state.request_id,
            "agent_name": state.agent_name,
            "elapsed_seconds": elapsed_seconds,
            "tools_used": state.tools_used,
            "llm_calls": state.llm_calls,
            "tool_calls": state.tool_calls,
            "errors": state.errors,
            "warnings": state.warnings,
            "has_intermediate_results": len(state.intermediate_results) > 0,
        }

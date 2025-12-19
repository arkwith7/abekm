"""
Unified Agent Protocol for LangChain 1.X

모든 에이전트가 준수해야 하는 표준 인터페이스
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Type
from enum import Enum

from pydantic import BaseModel, Field
from loguru import logger

try:
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    from langchain_core.tools import BaseTool
    from langchain_core.language_models import BaseLanguageModel
except ImportError:
    from langchain.schema import BaseMessage, HumanMessage, AIMessage
    from langchain_core.tools import BaseTool
    from langchain.llms import BaseLanguageModel


# =============================================================================
# Enums
# =============================================================================

class AgentMode(str, Enum):
    """에이전트 실행 모드"""
    REACT = "react"  # ReAct (Reasoning + Acting)
    PLAN_EXECUTE = "plan_execute"  # Plan-and-Execute
    TOOL_CALLING = "tool_calling"  # Native tool-calling
    GRAPH = "graph"  # LangGraph 기반


class AgentStatus(str, Enum):
    """에이전트 실행 상태"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Context & Configuration
# =============================================================================

class AgentExecutionContext(BaseModel):
    """에이전트 실행 컨텍스트"""
    
    request_id: str = Field(default_factory=lambda: f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(object())}")
    session_id: Optional[str] = Field(None, description="세션 ID (멀티턴 대화)")
    user_id: Optional[int] = Field(None, description="사용자 ID")
    
    # 부모-자식 관계 (에이전트 체인)
    parent_agent: Optional[str] = Field(None, description="부모 에이전트 이름")
    execution_depth: int = Field(0, ge=0, le=5, description="실행 깊이 (무한 루프 방지)")
    
    # 실행 제약
    timeout_seconds: int = Field(120, ge=10, le=600, description="최대 실행 시간 (초)")
    max_iterations: int = Field(10, ge=1, le=50, description="최대 반복 횟수")
    max_tokens: int = Field(4000, ge=100, le=16000, description="최대 컨텍스트 토큰")
    
    # 공유 데이터
    shared_context: Dict[str, Any] = Field(default_factory=dict, description="에이전트 간 공유 데이터")
    
    # 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    
    class Config:
        arbitrary_types_allowed = True


class AgentCapability(BaseModel):
    """에이전트 역량 정의"""
    
    name: str = Field(..., description="역량 이름")
    description: str = Field(..., description="역량 설명")
    input_schema: Optional[Type[BaseModel]] = Field(None, description="입력 스키마")
    output_schema: Optional[Type[BaseModel]] = Field(None, description="출력 스키마")
    supported_modes: List[AgentMode] = Field(
        default_factory=lambda: [AgentMode.REACT],
        description="지원하는 실행 모드"
    )
    estimated_latency_ms: Optional[int] = Field(None, description="예상 처리 시간 (ms)")
    requires_internet: bool = Field(False, description="인터넷 연결 필요 여부")
    requires_database: bool = Field(False, description="데이터베이스 연결 필요 여부")
    
    class Config:
        arbitrary_types_allowed = True


# =============================================================================
# Execution Result
# =============================================================================

class AgentStep(BaseModel):
    """에이전트 실행 단계"""
    
    step_number: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = Field(..., description="수행한 액션 (도구 이름 또는 'reasoning')")
    reasoning: Optional[str] = Field(None, description="사고 과정")
    tool_input: Optional[Dict[str, Any]] = Field(None, description="도구 입력")
    tool_output: Optional[Any] = Field(None, description="도구 출력")
    latency_ms: float = Field(..., description="실행 시간 (밀리초)")
    success: bool = Field(True, description="성공 여부")
    error: Optional[str] = Field(None, description="에러 메시지")


class AgentExecutionResult(BaseModel):
    """에이전트 실행 결과"""
    
    success: bool = Field(..., description="실행 성공 여부")
    output: Any = Field(..., description="최종 출력")
    
    # 실행 정보
    agent_name: str
    mode: AgentMode
    status: AgentStatus
    
    # 실행 추적
    steps: List[AgentStep] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    
    # 메트릭
    total_latency_ms: float
    llm_calls: int = Field(0, description="LLM 호출 횟수")
    tool_calls: int = Field(0, description="도구 호출 횟수")
    tokens_used: int = Field(0, description="사용한 토큰 수")
    
    # 에러 처리
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # 메타데이터
    context: AgentExecutionContext
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# Base Agent Protocol
# =============================================================================

class BaseAutonomousAgent(ABC):
    """
    LangChain 1.X 기반 자율 에이전트 베이스 클래스
    
    모든 에이전트는 이 클래스를 상속받아 구현합니다.
    """
    
    # 에이전트 메타데이터
    name: str = "base_agent"
    description: str = "Base autonomous agent"
    version: str = "1.0.0"
    
    def __init__(self) -> None:
        self.tools: Dict[str, BaseTool] = {}
        self.llm: Optional[BaseLanguageModel] = None
        self._capabilities: List[AgentCapability] = []
    
    # ===== 필수 구현 메서드 =====
    
    @abstractmethod
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: AgentExecutionContext,
        mode: AgentMode = AgentMode.REACT,
    ) -> AgentExecutionResult:
        """
        에이전트 실행 (비동기)
        
        Args:
            input_data: 입력 데이터
            context: 실행 컨텍스트
            mode: 실행 모드
        
        Returns:
            실행 결과
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[AgentCapability]:
        """에이전트가 제공하는 역량 목록"""
        pass
    
    # ===== 공통 메서드 =====
    
    async def health_check(self) -> Dict[str, Any]:
        """
        에이전트 상태 확인
        
        Returns:
            상태 정보 딕셔너리
        """
        try:
            # LLM 연결 확인
            llm_status = "available" if self.llm else "not_configured"
            
            # 도구 상태 확인
            tools_status = {}
            for tool_name, tool in self.tools.items():
                try:
                    # 간단한 도구 체크 (실제 실행은 하지 않음)
                    tools_status[tool_name] = "available"
                except Exception as e:
                    tools_status[tool_name] = f"error: {str(e)}"
            
            return {
                "healthy": True,
                "agent_name": self.name,
                "version": self.version,
                "llm_status": llm_status,
                "tools": tools_status,
                "capabilities": len(self._capabilities),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] Health check failed: {e}")
            return {
                "healthy": False,
                "agent_name": self.name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def register_tool(self, tool: BaseTool) -> None:
        """도구 등록"""
        self.tools[tool.name] = tool
        logger.info(f"✅ [{self.name}] Tool registered: {tool.name}")
    
    def set_llm(self, llm: BaseLanguageModel) -> None:
        """LLM 설정"""
        self.llm = llm
        logger.info(f"✅ [{self.name}] LLM configured")
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        도구 실행 (공통 로직)
        
        Args:
            tool_name: 도구 이름
            tool_input: 도구 입력
        
        Returns:
            도구 실행 결과
        """
        if tool_name not in self.tools:
            error_msg = f"Unknown tool: {tool_name}"
            logger.error(f"❌ [{self.name}] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
            }
        
        tool = self.tools[tool_name]
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"🔧 [{self.name}] Executing tool: {tool_name}")
            
            # 비동기/동기 실행
            if hasattr(tool, "_arun"):
                result = await tool._arun(**tool_input)
            else:
                result = tool._run(**tool_input)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✅ [{self.name}] Tool completed: {tool_name} ({latency_ms:.1f}ms)")
            
            # 결과 정규화
            if isinstance(result, dict):
                result["latency_ms"] = latency_ms
                if "success" not in result:
                    result["success"] = True
                return result
            else:
                return {
                    "success": True,
                    "result": result,
                    "latency_ms": latency_ms,
                }
                
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(f"❌ [{self.name}] {tool_name}: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "latency_ms": latency_ms,
            }
    
    def _log_step(
        self,
        action: str,
        reasoning: Optional[str] = None,
        tool_input: Optional[Dict] = None,
        tool_output: Optional[Any] = None,
        latency_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> AgentStep:
        """실행 단계 로깅"""
        step = AgentStep(
            step_number=len(getattr(self, "_steps", [])) + 1,
            action=action,
            reasoning=reasoning,
            tool_input=tool_input,
            tool_output=tool_output,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        
        if not hasattr(self, "_steps"):
            self._steps = []
        self._steps.append(step)
        
        return step

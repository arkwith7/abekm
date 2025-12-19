"""
Base Agent Infrastructure for LangChain 1.X

통일된 에이전트 베이스 클래스 및 프로토콜
"""

from .agent_protocol import (
    BaseAutonomousAgent,
    AgentExecutionContext,
    AgentCapability,
    AgentExecutionResult,
)
from .agent_state import (
    AgentStateManager,
    AgentExecutionState,
)

__all__ = [
    "BaseAutonomousAgent",
    "AgentExecutionContext",
    "AgentCapability",
    "AgentExecutionResult",
    "AgentStateManager",
    "AgentExecutionState",
]

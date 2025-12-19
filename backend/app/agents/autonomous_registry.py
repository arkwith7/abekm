"""
Dynamic Agent Registry V2 for Autonomous Agents

BaseAutonomousAgent를 상속한 자율형 에이전트들의 중앙 관리
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
from loguru import logger

from app.agents.base import BaseAutonomousAgent


@dataclass
class AgentMetadata:
    """에이전트 메타데이터"""
    name: str
    display_name: str
    description: str
    version: str
    agent_class: Type[BaseAutonomousAgent]
    instance: Optional[BaseAutonomousAgent] = None
    capabilities: List[str] = field(default_factory=list)
    priority: int = 50  # 낮을수록 우선순위 높음
    enabled: bool = True


class AutonomousAgentRegistry:
    """
    자율형 에이전트 레지스트리
    
    SupervisorAgent가 동적으로 에이전트를 검색하고 실행할 수 있도록
    모든 BaseAutonomousAgent 구현체를 중앙에서 관리
    """
    
    _instance: Optional[AutonomousAgentRegistry] = None
    _agents: Dict[str, AgentMetadata] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
        return cls._instance
    
    @classmethod
    def register(
        cls,
        name: str,
        agent_class: Type[BaseAutonomousAgent],
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        priority: int = 50,
        enabled: bool = True
    ) -> None:
        """
        에이전트 등록
        
        Args:
            name: 고유 이름 (예: "paper_search_v2")
            agent_class: BaseAutonomousAgent 하위 클래스
            display_name: 표시 이름
            description: 설명
            capabilities: 능력 목록 ["search", "qa", "patent", "presentation"]
            priority: 우선순위 (낮을수록 먼저 선택됨)
            enabled: 활성화 여부
        """
        if cls._instance is None:
            cls._instance = cls()
        
        metadata = AgentMetadata(
            name=name,
            display_name=display_name or name,
            description=description or "",
            version="1.0.0",
            agent_class=agent_class,
            instance=None,  # Lazy initialization
            capabilities=capabilities or [],
            priority=priority,
            enabled=enabled
        )
        
        cls._instance._agents[name] = metadata
        logger.info(f"✅ [AgentRegistry] Registered: {name} -> {display_name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseAutonomousAgent]:
        """
        에이전트 인스턴스 가져오기
        
        싱글톤 패턴으로 한 번만 초기화
        """
        if cls._instance is None:
            cls._instance = cls()
        
        metadata = cls._instance._agents.get(name)
        if not metadata:
            logger.warning(f"⚠️ [AgentRegistry] Not found: {name}")
            return None
        
        if not metadata.enabled:
            logger.warning(f"⚠️ [AgentRegistry] Disabled: {name}")
            return None
        
        # Lazy initialization
        if metadata.instance is None:
            try:
                metadata.instance = metadata.agent_class()
                logger.info(f"🔧 [AgentRegistry] Instantiated: {name}")
            except Exception as e:
                logger.error(f"❌ [AgentRegistry] Failed to instantiate {name}: {e}")
                return None
        
        return metadata.instance
    
    @classmethod
    def get_metadata(cls, name: str) -> Optional[AgentMetadata]:
        """에이전트 메타데이터 조회"""
        if cls._instance is None:
            return None
        return cls._instance._agents.get(name)
    
    @classmethod
    def list_all(cls) -> List[AgentMetadata]:
        """모든 에이전트 목록 (활성/비활성 포함)"""
        if cls._instance is None:
            return []
        return list(cls._instance._agents.values())
    
    @classmethod
    def list_enabled(cls) -> List[AgentMetadata]:
        """활성화된 에이전트 목록만"""
        if cls._instance is None:
            return []
        return [m for m in cls._instance._agents.values() if m.enabled]
    
    @classmethod
    def find_by_capability(cls, capability: str) -> List[AgentMetadata]:
        """
        특정 능력을 가진 에이전트 검색
        
        Args:
            capability: 능력 키워드 (예: "search", "patent", "presentation")
        
        Returns:
            우선순위순으로 정렬된 에이전트 목록
        """
        if cls._instance is None:
            return []
        
        matching = [
            m for m in cls._instance._agents.values()
            if m.enabled and capability in m.capabilities
        ]
        
        # 우선순위 정렬
        matching.sort(key=lambda x: x.priority)
        
        return matching
    
    @classmethod
    def clear(cls) -> None:
        """레지스트리 초기화 (테스트용)"""
        if cls._instance:
            cls._instance._agents.clear()
            logger.info("🧹 [AgentRegistry] Cleared")


# =============================================================================
# Auto Registration
# =============================================================================

def auto_register_autonomous_agents():
    """
    애플리케이션 시작 시 모든 자율형 에이전트 자동 등록
    
    app/main.py의 startup 이벤트에서 호출
    """
    logger.info("🚀 [AgentRegistry] Auto-registering autonomous agents...")

    # NOTE: V2 agents were consolidated/archived under app/agents/_backup.
    # Keep this registry focused on currently active (non-archived) agents.
    
    # 3. DeepResearchAgent (신규)
    # 4. SummaryAgentV2 (향후 개선)
    # 5. ImageGenerationAgent (신규)
    
    total = len(AutonomousAgentRegistry.list_all())
    enabled = len(AutonomousAgentRegistry.list_enabled())
    logger.info(f"✅ [AgentRegistry] Total: {total}, Enabled: {enabled}")


# 전역 싱글톤
autonomous_agent_registry = AutonomousAgentRegistry()

"""
Supervisor Agent V2 - Dynamic Agent Registry Integration

개선 사항:
- AutonomousAgentRegistry와 통합
- 등록된 모든 자율형 에이전트 자동 검색
- 능력 기반 에이전트 매칭
- LangGraph 동적 노드 생성
"""
from __future__ import annotations

from typing import TypedDict, Annotated, Sequence, Dict, Any, Optional, Literal
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from loguru import logger

from app.core.config import settings
from app.agents.autonomous_registry import AutonomousAgentRegistry, auto_register_autonomous_agents
from app.agents.base import AgentExecutionContext
from app.services.core.ai_service import ai_service
from app.core.database import get_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from contextlib import asynccontextmanager


# =============================================================================
# Database Helper
# =============================================================================

@asynccontextmanager
async def get_db_session_context():
    """DB 세션 컨텍스트 매니저"""
    engine = get_async_engine()
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


# =============================================================================
# State Definition
# =============================================================================

class SupervisorState(TypedDict):
    """슈퍼바이저 에이전트 상태"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str  # 다음 실행할 에이전트 이름
    shared_context: Dict[str, Any]  # 에이전트 간 공유 컨텍스트


# =============================================================================
# Supervisor LLM
# =============================================================================

# NOTE: LLM은 런타임에 초기화 (import-time 실패/지연 방지)
llm = None


# =============================================================================
# Dynamic Agent Options
# =============================================================================

def get_available_agents() -> list[str]:
    """
    등록된 모든 활성 에이전트 이름 가져오기
    
    Returns:
        ["paper_search_v2", "patent_v2", ..., "FINISH"]
    """
    agents = AutonomousAgentRegistry.list_enabled()
    agent_names = [agent.name for agent in agents]
    agent_names.append("FINISH")
    return agent_names


def get_agent_descriptions() -> str:
    """
    에이전트 설명 목록 (프롬프트 삽입용)
    
    Returns:
        "- paper_search_v2: 자율형 논문/문서 검색 및 QA 에이전트
         - patent_v2: 자율형 특허 검색/분석 에이전트
         ..."
    """
    agents = AutonomousAgentRegistry.list_enabled()
    descriptions = []
    for agent in agents:
        capabilities_str = ", ".join(agent.capabilities)
        descriptions.append(
            f"- {agent.name}: {agent.description} (능력: {capabilities_str})"
        )
    return "\n".join(descriptions)


# =============================================================================
# Supervisor Prompt & Chain
# =============================================================================

system_prompt = """당신은 여러 전문 에이전트를 관리하는 슈퍼바이저입니다.

**사용 가능한 에이전트**:
{agent_descriptions}

**당신의 역할**:
1. 사용자 요청을 분석하여 가장 적합한 에이전트 선택
2. 에이전트 실행 결과를 관찰
3. 추가 에이전트 호출이 필요한지 판단
4. 모든 작업이 완료되면 FINISH

**라우팅 가이드라인**:
- "검색", "찾아줘", "알려줘" → paper_search_v2
- "특허", "patent" → patent_v2 (구현 시)
- "PPT", "프레젠테이션", "발표자료" → presentation (향후 통합)
- "요약해줘" → summary (향후 통합)
- 복잡한 리서치 → deep_research (향후 구현)

**다음 중 하나를 선택하세요**: {options}
"""

# 동적으로 옵션 생성
options = get_available_agents()
agent_descriptions = get_agent_descriptions()


class RouteDecision(BaseModel):
    """라우팅 결정"""
    next: str  # 동적이므로 Literal 사용 불가


prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
    ("system", "대화 맥락을 고려하여 다음에 실행할 에이전트를 선택하세요. 완료되었다면 FINISH를 선택하세요."),
]).partial(
    options=", ".join(options),
    agent_descriptions=agent_descriptions
)

def _get_supervisor_chain():
    global llm
    if llm is None:
        llm = ai_service.get_chat_model(temperature=0)
    return prompt | llm.with_structured_output(RouteDecision)


# =============================================================================
# Supervisor Node
# =============================================================================

async def supervisor_node(state: SupervisorState) -> Dict[str, str]:
    """
    슈퍼바이저 노드: 다음 실행할 에이전트 결정
    """
    try:
        supervisor_chain = _get_supervisor_chain()
        decision = await supervisor_chain.ainvoke(state)
        next_agent = decision.next
        
        logger.info(f"🧠 [SupervisorV2] Decision: {next_agent}")
        
        return {"next": next_agent}
    
    except Exception as e:
        logger.error(f"❌ [SupervisorV2] Decision failed: {e}")
        return {"next": "FINISH"}


# =============================================================================
# Dynamic Agent Nodes
# =============================================================================

def create_agent_node(agent_name: str):
    """
    동적 에이전트 노드 팩토리
    
    Args:
        agent_name: 에이전트 이름 (예: "paper_search_v2")
    
    Returns:
        async 노드 함수
    """
    async def agent_node(state: SupervisorState) -> Dict[str, Any]:
        """동적 생성된 에이전트 노드"""
        messages = state["messages"]
        shared_context = state.get("shared_context", {})
        
        # 사용자 메시지 추출
        last_message = messages[-1]
        if isinstance(last_message, HumanMessage):
            query = last_message.content
        else:
            query = last_message.content  # AIMessage일 수도 있음
        
        logger.info(f"🤖 [SupervisorV2] Routing to {agent_name}: {query[:50]}...")
        
        # 레지스트리에서 에이전트 가져오기
        agent = AutonomousAgentRegistry.get(agent_name)
        if not agent:
            error_msg = f"❌ Agent not found: {agent_name}"
            logger.error(error_msg)
            return {
                "messages": [AIMessage(content=error_msg, name=agent_name)],
                "shared_context": shared_context
            }
        
        # 에이전트 실행
        try:
            async with get_db_session_context() as db_session:
                # 실행 컨텍스트 생성
                context = AgentExecutionContext(
                    request_id=shared_context.get("request_id", "unknown"),
                    max_iterations=settings.agent_max_iterations,
                    timeout=settings.agent_timeout_seconds,
                    constraints={},
                    shared_context=shared_context
                )
                
                # 에이전트 실행
                result = await agent.execute(
                    input_data={
                        "query": query,
                        "db_session": db_session,
                        "history": [],  # TODO: messages에서 히스토리 추출
                    },
                    context=context,
                )
                
                # 결과 저장
                output = result.output or {}
                response_content = output.get("answer") if isinstance(output, dict) else str(output)
                shared_context[f"{agent_name}_result"] = result
                
                logger.info(f"✅ [SupervisorV2] {agent_name} completed: {len(response_content)} chars")
                
                return {
                    "messages": [AIMessage(content=response_content, name=agent_name)],
                    "shared_context": shared_context
                }
        
        except Exception as e:
            error_msg = f"❌ {agent_name} execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "messages": [AIMessage(content=error_msg, name=agent_name)],
                "shared_context": shared_context
            }
    
    return agent_node


# =============================================================================
# Graph Construction
# =============================================================================

def build_supervisor_graph() -> StateGraph:
    """
    동적 슈퍼바이저 그래프 생성
    
    등록된 모든 에이전트를 자동으로 노드로 추가
    """
    # 에이전트 자동 등록 (앱 시작 시 한 번만 실행)
    auto_register_autonomous_agents()
    
    # 그래프 초기화
    workflow = StateGraph(SupervisorState)
    
    # 슈퍼바이저 노드 추가
    workflow.add_node("supervisor", supervisor_node)
    
    # 동적 에이전트 노드 추가
    enabled_agents = AutonomousAgentRegistry.list_enabled()
    for agent_meta in enabled_agents:
        node_name = agent_meta.name
        node_func = create_agent_node(node_name)
        workflow.add_node(node_name, node_func)
        
        # 에이전트 → 슈퍼바이저 엣지
        workflow.add_edge(node_name, "supervisor")
        
        logger.info(f"🔗 [SupervisorV2] Added node: {node_name}")
    
    # 조건부 엣지: 슈퍼바이저 → 에이전트 or END
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: END if x["next"] == "FINISH" else x["next"],
    )
    
    # 시작점
    workflow.set_entry_point("supervisor")
    
    logger.info(f"✅ [SupervisorV2] Graph built with {len(enabled_agents)} agents")
    
    return workflow


# =============================================================================
# Compiled Graph
# =============================================================================

# 그래프 컴파일
supervisor_agent_v2 = build_supervisor_graph().compile()

logger.info("✅ [SupervisorV2] Initialized successfully")

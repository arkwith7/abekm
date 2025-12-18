from typing import TypedDict, Annotated, List, Dict, Any, Optional, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from app.core.config import settings
from app.agents import paper_search_agent
from app.agents import presentation_agent_tool
from app.core.database import get_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from contextlib import asynccontextmanager
import json
import operator
from loguru import logger
from pydantic import BaseModel

# DB Session Helper
@asynccontextmanager
async def get_db_session_context():
    engine = get_async_engine()
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session

# State 정의
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    shared_context: Dict[str, Any]

# Supervisor LLM - Use Azure OpenAI
try:
    from app.services.core.ai_service import ai_service
    llm = ai_service.get_chat_model(temperature=0)
    logger.info("✅ SupervisorAgent initialized with ai_service")
except Exception as e:
    logger.warning(f"⚠️ Failed to initialize ai_service, falling back to direct OpenAI: {e}")
    api_key = settings.openai_api_key or settings.azure_openai_api_key
    if not api_key:
        logger.error("❌ No OpenAI/Azure API key found. SupervisorAgent will not work.")
        llm = None
    else:
        llm = ChatOpenAI(
            model=settings.openai_llm_model or "gpt-4o",
            api_key=api_key,
            temperature=0
        )

# Supervisor Prompt
system_prompt = (
    "You are a supervisor tasked with managing a conversation between the"
    " following workers: {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
    " If the user asks to create a presentation based on search results,"
    " first call 'SearchAgent', then call 'PresentationAgent'."
    " If the user just asks for a presentation without search context,"
    " you can call 'PresentationAgent' directly."
)

options = ["SearchAgent", "PresentationAgent", "FINISH"]


class RouteDecision(BaseModel):
    next: Literal["SearchAgent", "PresentationAgent", "FINISH"]

# Function definition for routing
function_def = {
    "name": "route",
    "description": "Select the next role.",
    "parameters": {
        "title": "routeSchema",
        "type": "object",
        "properties": {
            "next": {
                "title": "Next",
                "anyOf": [
                    {"enum": options},
                ],
            }
        },
        "required": ["next"],
    },
}

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Given the conversation above, who should act next?"
            " Or should we FINISH? Select one of: {options}",
        ),
    ]
).partial(options=str(options), members=", ".join(options))

supervisor_chain = (
    prompt
    | llm.with_structured_output(RouteDecision)
)

# Nodes
async def supervisor_node(state: AgentState):
    decision = await supervisor_chain.ainvoke(state)
    return {"next": decision.next}

async def search_node(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1].content
    
    logger.info(f"Supervisor routing to SearchAgent: {last_message[:50]}...")
    
    async with get_db_session_context() as db_session:
        # 검색 실행
        # constraints 등은 기본값 사용
        # history 변환 필요 (BaseMessage -> Dict)
        history_dicts = []
        for msg in messages[:-1]: # 마지막 메시지는 query이므로 제외
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            history_dicts.append({"role": role, "content": msg.content})

        result = await paper_search_agent.execute(
            query=last_message,
            db_session=db_session,
            history=history_dicts
        )
    
    response_content = result.answer
    
    # 검색 결과를 shared_context에 저장
    # AgentResult 객체 자체를 저장하여 메타데이터 보존
    return {
        "messages": [AIMessage(content=response_content, name="SearchAgent")],
        "shared_context": {
            "search_result": response_content,
            "search_agent_result": result  # AgentResult 객체 저장
        }
    }

async def presentation_node(state: AgentState):
    messages = state["messages"]
    # messages에는 User -> SearchAgent(AI) -> ... 순으로 쌓여있음.
    # PresentationAgent에게 전달할 때는 "검색 결과를 바탕으로 PPT 만들어줘"라는 의도가 전달되어야 함.
    
    shared_context = state.get("shared_context", {})
    search_result = shared_context.get("search_result", "")
    
    logger.info(f"Supervisor routing to PresentationAgent. Context len: {len(search_result)}")
    
    # PresentationAgent Tool 실행 (New Tool-based Architecture)
    context_text = search_result if search_result else "Create a presentation based on the conversation."
    
    # 원래 사용자 요청에서 주제 추출 시도
    original_query = messages[0].content if messages else ""
    
    try:
        tool_result = await presentation_agent_tool._arun(
            context_text=context_text,
            topic=None,  # 자동 추론
            documents=[],
            options={},
            template_style="business",
            presentation_type="general",
            quick_mode=False
        )
        
        if tool_result.get("success"):
            file_name = tool_result.get("file_name", "presentation.pptx")
            file_path = tool_result.get("file_path", "")
            final_response = f"✅ PPT 생성 완료!\n\n📄 파일명: {file_name}\n💾 경로: {file_path}"
        else:
            error_msg = tool_result.get("error", "알 수 없는 오류")
            final_response = f"❌ PPT 생성 실패: {error_msg}"
    
    except Exception as e:
        logger.error(f"PresentationAgent Tool 실행 실패: {e}")
        final_response = f"❌ Presentation generation failed: {str(e)}"
    
    return {
        "messages": [AIMessage(content=final_response, name="PresentationAgent")]
    }

# Graph 구성
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("SearchAgent", search_node)
workflow.add_node("PresentationAgent", presentation_node)

for member in options[:-1]:
    workflow.add_edge(member, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    lambda x: END if x["next"] == "FINISH" else x["next"],
)

workflow.set_entry_point("supervisor")

supervisor_agent = workflow.compile()

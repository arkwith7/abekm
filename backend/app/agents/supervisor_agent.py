from typing import TypedDict, Annotated, Dict, Any, Optional, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from app.core.config import settings
import json
import operator
from loguru import logger
from pydantic import BaseModel

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
    " If the user asks for prior-art search (e.g., KIPRIS, 선행기술조사), call 'PriorArtAgent'."
)

# Dynamic worker loading via AgentCatalog (Phase 1 unification)
from app.agents.catalog import agent_catalog

workers = agent_catalog.get_workers()
worker_names = list(workers.keys())
options = [*worker_names, "FINISH"]


class RouteDecision(BaseModel):
    # options는 런타임에 구성되므로 Literal 대신 런타임 검증
    next: str

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

if llm is None:
    supervisor_chain = None
else:
    supervisor_chain = prompt | llm.with_structured_output(RouteDecision)

# Nodes
async def supervisor_node(state: AgentState):
    if supervisor_chain is None:
        # Avoid worker execution when supervisor cannot route.
        # This keeps unit tests and misconfigured deployments from crashing at import-time.
        msg = (
            "❌ Supervisor LLM is not configured. "
            "Set OpenAI/Azure credentials (e.g., OPENAI_API_KEY or AZURE_OPENAI_API_KEY)."
        )
        return {
            "next": "FINISH",
            "messages": [AIMessage(content=msg, name="Supervisor")],
            "shared_context": state.get("shared_context", {}),
        }

    decision = await supervisor_chain.ainvoke(state)

    chosen = decision.next
    if chosen not in options:
        logger.warning(f"⚠️ Supervisor returned unknown next='{chosen}', defaulting to FINISH")
        chosen = "FINISH"

    # shared_context는 유지
    return {"next": chosen, "shared_context": state.get("shared_context", {})}

# Graph 구성
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
for worker_name, spec in workers.items():
    workflow.add_node(worker_name, spec.node)

for member in options[:-1]:
    workflow.add_edge(member, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    lambda x: END if x["next"] == "FINISH" else x["next"],
)

workflow.set_entry_point("supervisor")

supervisor_agent = workflow.compile()

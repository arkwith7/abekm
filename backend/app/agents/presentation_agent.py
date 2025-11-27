from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from app.agents.tools.presentation_tools import get_presentation_tools
from app.core.config import settings
import json
from loguru import logger

# State 정의
class PresentationState(TypedDict):
    messages: Annotated[List[BaseMessage], "The conversation history"]
    topic: Optional[str]
    context: Optional[str]
    outline: Optional[Dict[str, Any]]
    ppt_file_url: Optional[str]
    final_response: Optional[str]

# LLM 설정
# settings.openai_api_key가 설정되어 있다고 가정
# 만약 설정되어 있지 않다면 에러가 발생할 수 있으므로 체크 필요
api_key = settings.openai_api_key
if not api_key:
    logger.warning("OPENAI_API_KEY is not set. PresentationAgent might fail.")

llm = ChatOpenAI(
    model=settings.openai_llm_model or "gpt-4o",
    api_key=api_key,
    temperature=0
)

# Tools
tools = get_presentation_tools()

# Nodes
async def analyze_request(state: PresentationState):
    """사용자 요청을 분석하여 주제와 컨텍스트를 추출"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    
    logger.info(f"Analyzing presentation request: {last_message[:50]}...")

    # 구조화된 출력을 위한 프롬프트
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a presentation expert. Extract the presentation topic and any context from the user's request.
        If the user provides a specific topic, use it. If the user refers to previous context, summarize it as context.
        Return JSON with 'topic' and 'context' keys."""),
        ("user", "{input}")
    ])
    
    # JSON 모드 사용 (모델이 지원하는 경우)
    try:
        chain = prompt | llm.bind(response_format={"type": "json_object"})
        response = await chain.ainvoke({"input": last_message})
        content = response.content
    except Exception as e:
        logger.warning(f"LLM call failed or JSON mode not supported: {e}. Fallback to text parsing.")
        # Fallback: 일반 텍스트로 요청
        chain = prompt | llm
        response = await chain.ainvoke({"input": last_message})
        content = response.content

    try:
        # 마크다운 코드 블록 제거
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        data = json.loads(content)
        topic = data.get("topic", last_message)
        context = data.get("context", "")
        logger.info(f"Extracted topic: {topic}")
        return {"topic": topic, "context": context}
    except Exception as e:
        logger.warning(f"Failed to parse analysis result: {e}")
        return {"topic": last_message, "context": ""}

async def generate_outline_node(state: PresentationState):
    """아웃라인 생성"""
    topic = state["topic"]
    context = state["context"]
    
    logger.info("Generating outline...")
    tool = next(t for t in tools if t.name == "generate_outline")
    
    # Tool 실행
    try:
        outline = await tool.ainvoke({"topic": topic, "context": context})
        return {"outline": outline}
    except Exception as e:
        logger.error(f"Outline generation error: {e}")
        return {"outline": {"error": str(e)}}

async def create_slides_node(state: PresentationState):
    """슬라이드 생성"""
    outline = state["outline"]
    
    if isinstance(outline, dict) and "error" in outline:
        return {"final_response": f"Failed to generate outline: {outline['error']}"}

    logger.info("Creating slides...")
    tool = next(t for t in tools if t.name == "create_slides")
    
    try:
        file_url = await tool.ainvoke({"outline": outline})
        return {
            "ppt_file_url": file_url, 
            "final_response": f"Presentation created successfully! You can download it here: {file_url}"
        }
    except Exception as e:
        logger.error(f"Slide creation error: {e}")
        return {"final_response": f"Failed to create slides: {str(e)}"}

# Graph 구성
workflow = StateGraph(PresentationState)

workflow.add_node("analyze", analyze_request)
workflow.add_node("generate_outline", generate_outline_node)
workflow.add_node("create_slides", create_slides_node)

workflow.set_entry_point("analyze")
workflow.add_edge("analyze", "generate_outline")
workflow.add_edge("generate_outline", "create_slides")
workflow.add_edge("create_slides", END)

presentation_agent = workflow.compile()

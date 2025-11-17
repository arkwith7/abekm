"""
Content Structurer - 마크다운을 구조화된 슬라이드 아웃라인으로 변환

This module uses LLM to convert markdown text into a structured presentation outline
with proper layout types, visual elements, and slide organization.
"""
from typing import Optional
import logging

try:
    from langchain_openai import AzureChatOpenAI
except ImportError:
    from langchain_community.chat_models import AzureChatOpenAI

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from app.models.presentation import StructuredOutline, StructuredSlide, VisualElements
from app.core.config import settings
from app.utils.prompt_loader import load_presentation_prompt

logger = logging.getLogger(__name__)


# ========== Main Function ==========

async def structure_markdown_to_outline(
    markdown: str,
    *,
    max_slides: int = 15,
    audience: str = "general",
    style: str = "business",
    llm: Optional[AzureChatOpenAI] = None
) -> StructuredOutline:
    """
    Convert markdown text to structured presentation outline using LLM.
    
    Args:
        markdown: Input markdown text
        max_slides: Maximum number of slides (default: 15)
        audience: Target audience (general|technical|executive)
        style: Presentation style (business|modern|playful)
        llm: LangChain LLM instance (optional, will create if not provided)
    
    Returns:
        StructuredOutline object
    
    Raises:
        ValueError: If markdown is empty or LLM fails
    """
    if not markdown or not markdown.strip():
        raise ValueError("Markdown content cannot be empty")
    
    # Truncate if too long
    if len(markdown) > 50000:
        logger.warning(f"Markdown too long ({len(markdown)} chars), truncating to 50000")
        markdown = markdown[:50000] + "\n\n[... content truncated ...]"
    
    # Create LLM if not provided
    if llm is None:
        llm = AzureChatOpenAI(
        deployment_name=settings.azure_openai_llm_deployment,
            openai_api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            temperature=0.7,
            max_tokens=4000
        )
    
    # Create structured output LLM
    parser = PydanticOutputParser(pydantic_object=StructuredOutline)
    structured_llm = llm.with_structured_output(StructuredOutline)
    
    # Load prompts from files
    system_prompt = load_presentation_prompt("content_structurer_system")
    user_prompt_template = load_presentation_prompt("content_structurer_user")
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt_template)
    ])
    
    # Execute LLM
    try:
        logger.info(f"Structuring markdown ({len(markdown)} chars) to outline...")
        
        messages = prompt.format_messages(
            markdown=markdown,
            max_slides=max_slides,
            audience=audience,
            style=style
        )
        
        result = await structured_llm.ainvoke(messages)
        
        # Validate result
        if not isinstance(result, StructuredOutline):
            logger.error(f"LLM returned unexpected type: {type(result)}")
            raise ValueError("LLM failed to return valid StructuredOutline")
        
        logger.info(
            f"✅ Successfully structured outline: '{result.title}' with {len(result.slides)} slides"
        )
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Content structuring failed: {e}", exc_info=True)
        raise ValueError(f"Failed to structure markdown: {str(e)}") from e


# ========== Helper Functions ==========

def validate_outline(outline: StructuredOutline) -> bool:
    """
    Validate structured outline for common issues.
    
    Returns:
        True if valid, raises ValueError otherwise
    """
    if not outline.slides:
        raise ValueError("Outline must have at least one slide")
    
    if len(outline.slides) > 30:
        raise ValueError(f"Too many slides: {len(outline.slides)} (max 30)")
    
    # Check for title slide
    if outline.slides[0].layout != "title":
        logger.warning("First slide should be 'title' layout")
    
    # Check bullet point limits
    for i, slide in enumerate(outline.slides):
        if slide.visual_elements and slide.visual_elements.bullets:
            if len(slide.visual_elements.bullets) > 8:
                logger.warning(
                    f"Slide {i+1} has {len(slide.visual_elements.bullets)} bullets (recommended max: 8)"
                )
    
    return True

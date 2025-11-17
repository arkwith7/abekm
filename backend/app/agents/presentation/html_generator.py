"""
HTML Generator - Converts structured presentation outline to interactive HTML deck

This module leverages LLM to transform StructuredOutline data into a fully interactive
HTML presentation that follows the WKMS design system (Tailwind CSS + Lucide icons).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

try:
    from langchain_openai import AzureChatOpenAI
except ImportError:  # pragma: no cover
    from langchain_community.chat_models import AzureChatOpenAI

from langchain_core.prompts import ChatPromptTemplate

from app.models.presentation import StructuredOutline
from app.core.config import settings
from app.utils.prompt_loader import load_presentation_prompt

logger = logging.getLogger(__name__)

# Base template used as reference/example for LLM output
BASE_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "presentation_base.html"


def _load_base_template() -> str:
    if not BASE_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Base template not found: {BASE_TEMPLATE_PATH}")
    return BASE_TEMPLATE_PATH.read_text(encoding="utf-8")


async def generate_presentation_html(
    outline: StructuredOutline,
    *,
    llm: Optional[AzureChatOpenAI] = None,
    temperature: float = 0.5,
    max_tokens: int = 6000
) -> str:
    """Generate interactive HTML presentation from StructuredOutline.

    Args:
        outline: StructuredOutline data
        llm: Optional pre-configured LLM instance
        temperature: Sampling temperature for HTML generation
        max_tokens: Maximum tokens for LLM response

    Returns:
        HTML string (complete document)
    """
    if not outline or not outline.slides:
        raise ValueError("Structured outline must contain at least one slide")

    base_template = _load_base_template()

    # Initialize LLM if not provided
    if llm is None:
        llm = AzureChatOpenAI(
            deployment_name=settings.azure_openai_llm_deployment,
            openai_api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # Load prompts from files
    system_prompt = load_presentation_prompt("html_generator_system")
    user_prompt_template = load_presentation_prompt("html_generator_user")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt_template),
    ])

    outline_json = json.dumps(outline.model_dump(), ensure_ascii=False, indent=2)
    messages = prompt.format_messages(
        outline_json=outline_json,
        base_template=base_template,
    )

    try:
        logger.info("Generating HTML presentation for '%s'", outline.title)
        response = await llm.ainvoke(messages)
        html_content = response.content if hasattr(response, "content") else str(response)
        html_content = html_content.strip()

        if not html_content.lower().startswith("<!doctype html>") and not html_content.lower().startswith("<!DOCTYPE html>"):
            logger.warning("Generated HTML missing DOCTYPE, prepending declaration")
            html_content = "<!DOCTYPE html>\n" + html_content

        return html_content
    except Exception as exc:  # pragma: no cover - network/LLM errors
        logger.error("HTML generation failed: %s", exc, exc_info=True)
        raise


def save_html_dump(html_content: str, output_path: Path) -> None:
    """Save HTML content to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    logger.info("HTML saved: %s", output_path)

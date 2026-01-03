from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings
from app.utils.prompt_loader import load_prompt


class SqlGeneration(BaseModel):
    sql: str = Field(..., description="Read-only SELECT SQL")


def _build_prompt(schema_context: str) -> ChatPromptTemplate:
    system = load_prompt("text_to_sql", "sql_generator_system")
    user = load_prompt("text_to_sql", "sql_generator_user")
    return ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", user),
        ]
    ).partial(schema_context=schema_context)


def _get_llm():
    """Lazy LLM accessor; returns None if not configured."""

    try:
        from app.services.core.ai_service import ai_service

        return ai_service.get_chat_model(temperature=0)
    except Exception:
        # Fallback to direct OpenAI if configured
        try:
            from langchain_openai import ChatOpenAI

            api_key = settings.openai_api_key or settings.azure_openai_api_key
            if not api_key:
                return None
            return ChatOpenAI(
                model=settings.openai_llm_model or "gpt-4o",
                api_key=api_key,
                temperature=0,
            )
        except Exception:
            return None


async def generate_sql(*, question: str, schema_context: str) -> Optional[SqlGeneration]:
    llm = _get_llm()
    if llm is None:
        return None

    prompt = _build_prompt(schema_context)
    chain = prompt | llm.with_structured_output(SqlGeneration)
    return await chain.ainvoke({"question": question})

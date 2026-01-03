from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Sequence

from langchain_core.messages import AIMessage, BaseMessage
from loguru import logger

from app.agents.core.db import get_db_session_context

from .services.schema_introspector import introspect_public_schema_tables
from .services.sql_guard import SqlGuardConfig, SqlGuardError, validate_read_only_sql
from .storage.sqlite_store import TextToSqlStore, TextToSqlStoreConfig
from .tools import (
    ExecuteSQLTool,
    GenerateSQLTool,
    GetTableSchemaTool,
    SearchSchemaTool,
    SearchSimilarQueriesTool,
    ValidateSQLTool,
)


def _default_store() -> TextToSqlStore:
    # Keep store outside repo root; aligns with other local caches.
    path = Path("/tmp") / "abekm" / "text_to_sql" / "text_to_sql_store.sqlite3"
    return TextToSqlStore(TextToSqlStoreConfig(path=path))


def _format_result_as_markdown(columns, rows, *, max_preview_rows: int = 20) -> str:
    if not rows:
        return "(결과 없음)"

    try:
        import pandas as pd

        df = pd.DataFrame(rows)
        if max_preview_rows and len(df) > max_preview_rows:
            df = df.head(max_preview_rows)
        return df.to_markdown(index=False)
    except Exception:
        # Minimal fallback
        preview = rows[:max_preview_rows]
        lines = []
        lines.append(" | ".join(columns))
        lines.append(" | ".join(["---"] * len(columns)))
        for r in preview:
            lines.append(" | ".join(str(r.get(c, "")) for c in columns))
        return "\n".join(lines)


def _extract_keyword(question: str) -> str:
    """Extract relevant keyword from user question for schema search."""
    keywords = ["문서", "사용자", "컨테이너", "파일", "청크", "chunk", "document", "user", "container", "file"]
    question_lower = str(question).lower()

    for keyword in keywords:
        if keyword.lower() in question_lower:
            return keyword

    return ""


def _extract_table_names_from_search(search_result: str) -> list[str]:
    """Extract table names from search schema tool result."""
    table_names = []
    lines = search_result.split("\n")

    for line in lines:
        if line.strip().startswith("- ") and "." in line:
            # Format: "- schema.table"
            parts = line.strip()[2:].split(".")
            if len(parts) == 2:
                table_names.append(parts[1])

    return table_names


def _extract_sql_from_result(result: str) -> str:
    """Extract SQL query from tool result containing ```sql blocks."""
    if "```sql" in result:
        start = result.find("```sql") + 6
        end = result.find("```", start)
        if end > start:
            return result[start:end].strip()

    return result.strip()


async def _bootstrap_schema_cache(
    store: TextToSqlStore,
    session,
    connection_id: str,
) -> None:
    """Bootstrap schema cache if empty (best-effort)."""
    try:
        schema_rows = await store.search_tables(connection_id=connection_id, keyword="", limit=1)
    except Exception:
        schema_rows = []

    if not schema_rows:
        try:
            tables = await introspect_public_schema_tables(session)
            for t in tables:
                await store.upsert_table_schema(
                    connection_id=connection_id,
                    schema_name=t["schema_name"],
                    table_name=t["table_name"],
                    columns=t["columns"],
                    table_comment=t.get("table_comment"),
                )
            logger.info(f"✅ Bootstrapped schema cache with {len(tables)} tables")
        except Exception as e:
            logger.warning(f"⚠️ Schema bootstrap failed: {e}")


async def text_to_sql_worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Supervisor worker entrypoint for Text-to-SQL with ReAct pattern.
    
    ReAct Pattern Flow:
    1. Reasoning: Analyze user question
    2. Action 1: Search schema for relevant tables
    3. Observation: Review found tables
    4. Action 2: Get detailed schema for selected tables
    5. Observation: Review schema details
    6. Action 3: Search for similar past queries (cache)
    7. Observation: Check if cached SQL exists
    8. Action 4: Generate SQL (if not cached)
    9. Observation: Review generated SQL
    10. Action 5: Validate SQL safety
    11. Observation: Ensure SQL is safe
    12. Action 6: Execute SQL
    13. Observation: Review results
    14. Final Answer: Format and return results
    """

    messages: Sequence[BaseMessage] = state["messages"]
    question = messages[-1].content

    logger.info(f"🧠 [TextToSQLAgent ReAct] Question: {str(question)[:80]}...")

    connection_id = "app_db"
    store = _default_store()

    # === ReAct Phase 1: Reasoning - Analyze question ===
    logger.info("💭 Reasoning: Extracting keywords from question...")
    keyword = _extract_keyword(question)
    logger.info(f"💭 Extracted keyword: '{keyword}'")

    async with get_db_session_context() as session:
        # Ensure schema is available in local store (bootstrap)
        await _bootstrap_schema_cache(store, session, connection_id)

        # === ReAct Phase 2: Action - Search Schema ===
        logger.info(f"🔍 Action 1: Searching schema with keyword '{keyword}'...")
        search_tool = SearchSchemaTool(store=store)
        schema_search_result = await search_tool._arun(
            keyword=keyword,
            connection_id=connection_id,
            limit=8,
        )
        logger.info(f"📊 Observation 1: {schema_search_result}")

        # Extract table names from search result
        table_names = _extract_table_names_from_search(schema_search_result)

        # === ReAct Phase 3: Action - Get Detailed Schema ===
        logger.info(f"📋 Action 2: Getting detailed schema for {len(table_names)} tables...")
        schema_context_parts = []
        get_schema_tool = GetTableSchemaTool(store=store)

        for table_name in table_names[:5]:  # Limit to 5 tables
            schema_result = await get_schema_tool._arun(
                table_name=table_name,
                schema_name="public",
                connection_id=connection_id,
            )
            if "✅" in schema_result:
                # Extract schema info for context
                schema_data = await store.get_table_schema(
                    connection_id=connection_id,
                    schema_name="public",
                    table_name=table_name,
                )
                if schema_data:
                    cols = schema_data.get("columns", [])
                    col_str = ", ".join([f"{col['name']}:{col['type']}" for col in cols[:30]])
                    schema_context_parts.append(f"- public.{table_name}({col_str})")

        schema_context = "\n".join(schema_context_parts) if schema_context_parts else "- public.<table>(<columns...>)"
        logger.info(f"📊 Observation 2: Schema context built with {len(schema_context_parts)} tables")

        # === ReAct Phase 4: Action - Search Similar Queries ===
        logger.info("🔎 Action 3: Searching for similar past queries...")
        similar_tool = SearchSimilarQueriesTool(store=store)
        similar_result = await similar_tool._arun(
            question=question,
            connection_id=connection_id,
        )
        logger.info(f"📊 Observation 3: {similar_result}")

        sql_text = None
        if "✅" in similar_result and "```sql" in similar_result:
            # Extract cached SQL
            sql_text = _extract_sql_from_result(similar_result)
            logger.info("♻️ Using cached SQL")

        # === ReAct Phase 5: Action - Generate SQL (if not cached) ===
        if not sql_text:
            logger.info("🤖 Action 4: Generating SQL with LLM...")
            generate_tool = GenerateSQLTool()
            generation_result = await generate_tool._arun(
                question=question,
                schema_context=schema_context,
            )
            logger.info(f"📊 Observation 4: {generation_result}")

            if "❌" in generation_result:
                # LLM not configured
                response = generation_result
                return {
                    "messages": [AIMessage(content=response, name="TextToSQLAgent")],
                    "shared_context": dict(state.get("shared_context", {})),
                }

            sql_text = _extract_sql_from_result(generation_result)

        # === ReAct Phase 6: Action - Validate SQL ===
        logger.info("🔐 Action 5: Validating SQL safety...")
        validate_tool = ValidateSQLTool()
        validation_result = await validate_tool._arun(
            sql_query=sql_text,
            max_rows=100,
        )
        logger.info(f"📊 Observation 5: {validation_result}")

        if "❌" in validation_result:
            # Validation failed
            response = validation_result
            return {
                "messages": [AIMessage(content=response, name="TextToSQLAgent")],
                "shared_context": dict(state.get("shared_context", {})),
            }

        validated_sql = _extract_sql_from_result(validation_result)

        # === ReAct Phase 7: Action - Execute SQL ===
        logger.info("⚡ Action 6: Executing SQL...")
        execute_tool = ExecuteSQLTool(session=session)
        execution_result = await execute_tool._arun(sql_query=validated_sql)
        logger.info(f"📊 Observation 6: Execution completed")

        if "❌" in execution_result:
            # Execution failed
            response = f"{execution_result}\n\n```sql\n{validated_sql}\n```"
            return {
                "messages": [AIMessage(content=response, name="TextToSQLAgent")],
                "shared_context": dict(state.get("shared_context", {})),
            }

        # Cache successful query
        await store.cache_question_sql(
            connection_id=connection_id,
            question=question,
            sql_query=validated_sql,
        )

    # === Final Answer: Format results ===
    answer = f"✅ SQL 실행 결과\n\n```sql\n{validated_sql}\n```\n\n{execution_result}"

    shared_context = dict(state.get("shared_context", {}))
    shared_context.update(
        {
            "text_to_sql": {
                "connection_id": connection_id,
                "sql": validated_sql,
                "question": question,
            }
        }
    )

    logger.info("✅ [TextToSQLAgent ReAct] Completed successfully")

    return {
        "messages": [AIMessage(content=answer, name="TextToSQLAgent")],
        "shared_context": shared_context,
    }

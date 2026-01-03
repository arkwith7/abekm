from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy import text


async def execute_sql(session, *, sql: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Execute SQL via an AsyncSession and return (columns, rows-as-dicts)."""

    result = await session.execute(text(sql))

    # Use mappings() for dict-like rows when possible.
    try:
        mappings = result.mappings().all()
        rows = [dict(r) for r in mappings]
        columns = list(rows[0].keys()) if rows else []
        return columns, rows
    except Exception:
        raw = result.all()
        columns = list(result.keys()) if getattr(result, "keys", None) else []
        rows = [dict(zip(columns, r)) for r in raw] if columns else []
        return columns, rows

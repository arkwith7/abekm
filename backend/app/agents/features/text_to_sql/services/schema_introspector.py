from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import text


async def introspect_public_schema_tables(session) -> List[Dict[str, Any]]:
    """Best-effort introspection for Postgres (app DB).

    Returns list of tables with columns:
    [{schema_name, table_name, columns:[{name,type,nullable,comment}]}]
    """

    # Tables
    tables_rows = await session.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type='BASE TABLE'
            ORDER BY table_name
            """
        )
    )
    tables = [(r[0], r[1]) for r in tables_rows.all()]

    # Columns
    cols_rows = await session.execute(
        text(
            """
            SELECT table_schema, table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )
    )

    columns_by_table: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for schema_name, table_name, column_name, data_type, is_nullable in cols_rows.all():
        columns_by_table.setdefault((schema_name, table_name), []).append(
            {
                "name": column_name,
                "type": data_type,
                "nullable": (is_nullable == "YES"),
                "comment": None,
            }
        )

    out: List[Dict[str, Any]] = []
    for schema_name, table_name in tables:
        out.append(
            {
                "schema_name": schema_name,
                "table_name": table_name,
                "columns": columns_by_table.get((schema_name, table_name), []),
                "table_comment": None,
            }
        )

    return out

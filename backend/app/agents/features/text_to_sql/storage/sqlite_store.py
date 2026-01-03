from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite


@dataclass(frozen=True)
class TextToSqlStoreConfig:
    path: Path


class TextToSqlStore:
    """SQLite store for schema metadata + query cache.

    This is intentionally lightweight and safe to initialize lazily.
    """

    def __init__(self, config: TextToSqlStoreConfig):
        self._path = config.path

    async def init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path.as_posix()) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id TEXT NOT NULL,
                    schema_name TEXT,
                    table_name TEXT NOT NULL,
                    columns_json TEXT NOT NULL,
                    table_comment TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS query_sql_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id TEXT NOT NULL,
                    question_hash TEXT NOT NULL,
                    question TEXT NOT NULL,
                    sql_query TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS connection_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    db_type TEXT,
                    connection_info_json TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    async def upsert_table_schema(
        self,
        *,
        connection_id: str,
        schema_name: str,
        table_name: str,
        columns: List[Dict[str, Any]],
        table_comment: Optional[str] = None,
    ) -> None:
        await self.init()
        async with aiosqlite.connect(self._path.as_posix()) as db:
            await db.execute(
                "DELETE FROM schema_metadata WHERE connection_id=? AND schema_name=? AND table_name=?",
                (connection_id, schema_name, table_name),
            )
            await db.execute(
                """
                INSERT INTO schema_metadata (connection_id, schema_name, table_name, columns_json, table_comment)
                VALUES (?, ?, ?, ?, ?)
                """,
                (connection_id, schema_name, table_name, json.dumps(columns, ensure_ascii=False), table_comment),
            )
            await db.commit()

    async def search_tables(self, *, connection_id: str, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        await self.init()
        kw = f"%{keyword}%"
        async with aiosqlite.connect(self._path.as_posix()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT schema_name, table_name, table_comment
                FROM schema_metadata
                WHERE connection_id=? AND (
                    table_name LIKE ? OR table_comment LIKE ? OR columns_json LIKE ?
                )
                ORDER BY table_name
                LIMIT ?
                """,
                (connection_id, kw, kw, kw, limit),
            )
            rows = await cur.fetchall()
            await cur.close()
            return [dict(r) for r in rows]

    async def get_table_schema(
        self, *, connection_id: str, schema_name: str, table_name: str
    ) -> Optional[Dict[str, Any]]:
        await self.init()
        async with aiosqlite.connect(self._path.as_posix()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT schema_name, table_name, columns_json, table_comment
                FROM schema_metadata
                WHERE connection_id=? AND schema_name=? AND table_name=?
                """,
                (connection_id, schema_name, table_name),
            )
            row = await cur.fetchone()
            await cur.close()
            if not row:
                return None
            d = dict(row)
            d["columns"] = json.loads(d.pop("columns_json"))
            return d

    async def cache_question_sql(self, *, connection_id: str, question: str, sql_query: str) -> None:
        await self.init()
        question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        async with aiosqlite.connect(self._path.as_posix()) as db:
            await db.execute(
                """
                INSERT INTO query_sql_cache (connection_id, question_hash, question, sql_query)
                VALUES (?, ?, ?, ?)
                """,
                (connection_id, question_hash, question, sql_query),
            )
            await db.commit()

    async def get_cached_sql(self, *, connection_id: str, question: str) -> Optional[str]:
        await self.init()
        question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        async with aiosqlite.connect(self._path.as_posix()) as db:
            cur = await db.execute(
                """
                SELECT sql_query
                FROM query_sql_cache
                WHERE connection_id=? AND question_hash=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (connection_id, question_hash),
            )
            row = await cur.fetchone()
            await cur.close()
            return row[0] if row else None

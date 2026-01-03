"""SearchSchemaTool - Find relevant tables and columns by keyword."""

from __future__ import annotations

from typing import Any, Dict, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..storage.sqlite_store import TextToSqlStore


class SearchSchemaToolInput(BaseModel):
    keyword: str = Field(..., description="검색 키워드 (테이블명, 컬럼명 또는 비즈니스 용어)")
    connection_id: str = Field(default="app_db", description="데이터베이스 연결 ID")
    limit: int = Field(default=10, description="최대 결과 개수")


class SearchSchemaTool(BaseTool):
    """한국어 키워드로 관련 테이블과 컬럼을 검색합니다.
    
    비즈니스 용어를 DB 객체(테이블/컬럼)로 매핑하는 데 사용됩니다.
    예: '사용자' → users 테이블, '문서' → documents 테이블
    """

    name: str = "search_schema"
    description: str = (
        "데이터베이스 스키마에서 키워드와 관련된 테이블과 컬럼을 검색합니다. "
        "비즈니스 용어를 실제 테이블명으로 매핑할 때 사용하세요."
    )
    args_schema: type[BaseModel] = SearchSchemaToolInput

    store: Optional[TextToSqlStore] = Field(default=None, exclude=True)

    def __init__(self, store: TextToSqlStore, **kwargs):
        super().__init__(store=store, **kwargs)

    async def _arun(
        self,
        keyword: str,
        connection_id: str = "app_db",
        limit: int = 10,
    ) -> str:
        """비동기 실행 (권장)."""
        try:
            results = await self.store.search_tables(
                connection_id=connection_id,
                keyword=keyword,
                limit=limit,
            )

            if not results:
                return f"키워드 '{keyword}'와 관련된 테이블을 찾을 수 없습니다."

            lines = [f"✅ 검색된 테이블 ({len(results)}개):"]
            for r in results:
                schema_name = r.get("schema_name", "public")
                table_name = r["table_name"]
                lines.append(f"- {schema_name}.{table_name}")

            return "\n".join(lines)

        except Exception as e:
            return f"❌ 스키마 검색 실패: {e}"

    def _run(
        self,
        keyword: str,
        connection_id: str = "app_db",
        limit: int = 10,
    ) -> str:
        """동기 실행 (비권장, 호환성용)."""
        import asyncio

        return asyncio.run(self._arun(keyword, connection_id, limit))

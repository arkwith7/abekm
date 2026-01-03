"""GetTableSchemaTool - Retrieve detailed schema for specific tables."""

from __future__ import annotations

from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..storage.sqlite_store import TextToSqlStore


class GetTableSchemaToolInput(BaseModel):
    table_name: str = Field(..., description="조회할 테이블명")
    schema_name: str = Field(default="public", description="스키마명")
    connection_id: str = Field(default="app_db", description="데이터베이스 연결 ID")


class GetTableSchemaTool(BaseTool):
    """특정 테이블의 상세 스키마 정보를 조회합니다.
    
    컬럼 목록, 데이터 타입, 제약조건 등을 확인하여
    정확한 SQL을 작성할 수 있도록 돕습니다.
    """

    name: str = "get_table_schema"
    description: str = (
        "특정 테이블의 상세 스키마(컬럼명, 타입, 제약조건)를 조회합니다. "
        "SQL 작성 전에 정확한 컬럼명과 타입을 확인할 때 사용하세요."
    )
    args_schema: type[BaseModel] = GetTableSchemaToolInput

    store: Optional[TextToSqlStore] = Field(default=None, exclude=True)

    def __init__(self, store: TextToSqlStore, **kwargs):
        super().__init__(store=store, **kwargs)

    async def _arun(
        self,
        table_name: str,
        schema_name: str = "public",
        connection_id: str = "app_db",
    ) -> str:
        """비동기 실행 (권장)."""
        try:
            schema = await self.store.get_table_schema(
                connection_id=connection_id,
                schema_name=schema_name,
                table_name=table_name,
            )

            if not schema:
                return f"❌ 테이블 '{schema_name}.{table_name}'의 스키마를 찾을 수 없습니다."

            columns = schema.get("columns", [])
            if not columns:
                return f"⚠️ 테이블 '{schema_name}.{table_name}'에 컬럼 정보가 없습니다."

            lines = [f"✅ {schema_name}.{table_name} 스키마:"]
            for col in columns[:30]:  # 최대 30개 컬럼
                col_name = col["name"]
                col_type = col["type"]
                nullable = "NULL" if col.get("nullable") else "NOT NULL"
                lines.append(f"  - {col_name}: {col_type} {nullable}")

            if len(columns) > 30:
                lines.append(f"  ... (총 {len(columns)}개 컬럼)")

            comment = schema.get("table_comment")
            if comment:
                lines.append(f"\n📝 설명: {comment}")

            return "\n".join(lines)

        except Exception as e:
            return f"❌ 스키마 조회 실패: {e}"

    def _run(
        self,
        table_name: str,
        schema_name: str = "public",
        connection_id: str = "app_db",
    ) -> str:
        """동기 실행 (비권장, 호환성용)."""
        import asyncio

        return asyncio.run(self._arun(table_name, schema_name, connection_id))

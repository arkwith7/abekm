"""ExecuteSQLTool - Execute validated SQL queries."""

from __future__ import annotations

from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.sql_executor import execute_sql


class ExecuteSQLToolInput(BaseModel):
    sql_query: str = Field(..., description="실행할 SQL 쿼리 (검증 완료된 것)")


class ExecuteSQLTool(BaseTool):
    """검증된 SQL 쿼리를 데이터베이스에서 실행합니다.
    
    제약사항:
    - 30초 타임아웃
    - 100행 결과 제한 (LIMIT)
    - SELECT 전용
    
    성공 시 결과를 표 형태로 반환합니다.
    """

    name: str = "execute_sql"
    description: str = (
        "검증된 SQL 쿼리를 실행하고 결과를 반환합니다. "
        "반드시 validate_sql 도구로 검증한 후 사용하세요."
    )
    args_schema: type[BaseModel] = ExecuteSQLToolInput

    session: Optional[AsyncSession] = Field(default=None, exclude=True)

    def __init__(self, session: AsyncSession, **kwargs):
        super().__init__(session=session, **kwargs)

    async def _arun(self, sql_query: str) -> str:
        """비동기 실행 (권장)."""
        try:
            columns, rows = await execute_sql(self.session, sql=sql_query)

            if not rows:
                return "✅ 실행 완료 (결과 없음)"

            # Format as simple table
            lines = [f"✅ 실행 완료 ({len(rows)}개 행):\n"]
            lines.append(" | ".join(columns))
            lines.append(" | ".join(["---"] * len(columns)))

            max_preview = 10
            for row in rows[:max_preview]:
                lines.append(" | ".join(str(row.get(c, "")) for c in columns))

            if len(rows) > max_preview:
                lines.append(f"... (총 {len(rows)}개 행, 처음 {max_preview}개만 표시)")

            return "\n".join(lines)

        except Exception as e:
            return f"❌ SQL 실행 실패: {type(e).__name__}: {str(e)}"

    def _run(self, sql_query: str) -> str:
        """동기 실행 (비권장, 호환성용)."""
        import asyncio

        return asyncio.run(self._arun(sql_query))

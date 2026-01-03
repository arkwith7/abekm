"""ValidateSQLTool - Validate SQL safety and syntax."""

from __future__ import annotations

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..services.sql_guard import SqlGuardConfig, SqlGuardError, validate_read_only_sql


class ValidateSQLToolInput(BaseModel):
    sql_query: str = Field(..., description="검증할 SQL 쿼리")
    max_rows: int = Field(default=100, description="최대 결과 행 수 (LIMIT 강제)")


class ValidateSQLTool(BaseTool):
    """SQL 쿼리의 안전성과 유효성을 검증합니다.
    
    검증 항목:
    - SELECT 전용 (DML/DDL 차단)
    - 금지 키워드 확인 (DROP, DELETE 등)
    - LIMIT 절 강제 추가
    - 구문 유효성 (기본)
    """

    name: str = "validate_sql"
    description: str = (
        "SQL 쿼리의 안전성을 검증합니다. "
        "SELECT 전용인지, 금지된 키워드가 없는지, LIMIT이 포함되었는지 확인합니다. "
        "SQL 실행 전에 반드시 사용하세요."
    )
    args_schema: type[BaseModel] = ValidateSQLToolInput

    async def _arun(
        self,
        sql_query: str,
        max_rows: int = 100,
    ) -> str:
        """비동기 실행 (권장)."""
        try:
            config = SqlGuardConfig(max_rows=max_rows)
            validated_sql = validate_read_only_sql(sql_query, config=config)

            return f"✅ SQL 검증 성공\n\n```sql\n{validated_sql}\n```"

        except SqlGuardError as e:
            return f"❌ SQL 검증 실패: {e}"
        except Exception as e:
            return f"❌ SQL 검증 오류: {e}"

    def _run(
        self,
        sql_query: str,
        max_rows: int = 100,
    ) -> str:
        """동기 실행 (비권장, 호환성용)."""
        import asyncio

        return asyncio.run(self._arun(sql_query, max_rows))

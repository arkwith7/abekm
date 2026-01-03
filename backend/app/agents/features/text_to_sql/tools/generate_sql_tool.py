"""GenerateSQLTool - Generate SQL from natural language using LLM."""

from __future__ import annotations

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..services.sql_generator import generate_sql


class GenerateSQLToolInput(BaseModel):
    question: str = Field(..., description="자연어 질문")
    schema_context: str = Field(..., description="관련 테이블 스키마 정보")


class GenerateSQLTool(BaseTool):
    """자연어 질문을 SQL 쿼리로 변환합니다 (LLM 기반).
    
    입력:
    - question: 사용자의 자연어 질문
    - schema_context: 관련 테이블/컬럼 정보
    
    출력:
    - SELECT 쿼리 (검증 전)
    
    사용 전 필수:
    1. search_schema로 관련 테이블 찾기
    2. get_table_schema로 상세 스키마 확인
    3. schema_context에 정보 포함
    """

    name: str = "generate_sql"
    description: str = (
        "자연어 질문을 SQL 쿼리로 변환합니다. "
        "스키마 정보를 함께 제공하면 더 정확한 SQL을 생성합니다."
    )
    args_schema: type[BaseModel] = GenerateSQLToolInput

    async def _arun(
        self,
        question: str,
        schema_context: str,
    ) -> str:
        """비동기 실행 (권장)."""
        try:
            result = await generate_sql(
                question=question,
                schema_context=schema_context,
            )

            if result is None:
                return (
                    "❌ SQL 생성 실패: LLM이 설정되지 않았습니다.\n"
                    "OpenAI 또는 Azure OpenAI 자격증명을 확인하세요."
                )

            sql = result.sql
            return f"✅ SQL 생성 완료:\n\n```sql\n{sql}\n```"

        except Exception as e:
            return f"❌ SQL 생성 오류: {e}"

    def _run(
        self,
        question: str,
        schema_context: str,
    ) -> str:
        """동기 실행 (비권장, 호환성용)."""
        import asyncio

        return asyncio.run(self._arun(question, schema_context))

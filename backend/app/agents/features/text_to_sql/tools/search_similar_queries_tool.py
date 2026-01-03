"""SearchSimilarQueriesTool - Find similar past queries for few-shot learning."""

from __future__ import annotations

from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..storage.sqlite_store import TextToSqlStore


class SearchSimilarQueriesToolInput(BaseModel):
    question: str = Field(..., description="현재 사용자 질문")
    connection_id: str = Field(default="app_db", description="데이터베이스 연결 ID")


class SearchSimilarQueriesTool(BaseTool):
    """유사한 과거 질문과 SQL을 검색하여 Few-shot 예제로 활용합니다.
    
    캐시된 질문-SQL 쌍을 검색하여:
    - 비슷한 패턴 파악
    - SQL 작성 힌트 얻기
    - 성공적인 쿼리 재사용
    """

    name: str = "search_similar_queries"
    description: str = (
        "과거에 성공적으로 실행된 유사한 질문과 SQL을 검색합니다. "
        "SQL 작성 전에 참고 예제를 찾을 때 사용하세요."
    )
    args_schema: type[BaseModel] = SearchSimilarQueriesToolInput

    store: Optional[TextToSqlStore] = Field(default=None, exclude=True)

    def __init__(self, store: TextToSqlStore, **kwargs):
        super().__init__(store=store, **kwargs)

    async def _arun(
        self,
        question: str,
        connection_id: str = "app_db",
    ) -> str:
        """비동기 실행 (권장)."""
        try:
            # 현재 구현은 정확 일치 캐시만 지원
            # Phase 3에서 임베딩 기반 유사도 검색으로 확장 예정
            cached_sql = await self.store.get_cached_sql(
                connection_id=connection_id,
                question=question,
            )

            if cached_sql:
                return f"✅ 캐시된 SQL 발견:\n\n```sql\n{cached_sql}\n```"

            return "⚠️ 유사한 질문을 찾을 수 없습니다. 새로운 SQL을 생성하세요."

        except Exception as e:
            return f"❌ 유사 질문 검색 실패: {e}"

    def _run(
        self,
        question: str,
        connection_id: str = "app_db",
    ) -> str:
        """동기 실행 (비권장, 호환성용)."""
        import asyncio

        return asyncio.run(self._arun(question, connection_id))

"""Prior Art Search Tool - 선행기술 검색 도구

책임:
- 검색 전략(질의) 수립
- KIPRIS 등 외부 DB 검색 실행
- 검색 결과 중복 제거 및 정렬
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.clients.kipris import KiprisClient


class PriorArtSearchTool(BaseTool):
    name: str = "prior_art_search"
    description: str = "키워드를 기반으로 검색 전략을 수립하고 선행기술을 검색합니다."
    version: str = "1.0.0"

    def generate_queries(
        self,
        *,
        keywords: List[str],
        base_query: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """
        검색 질의(전략) 생성
        
        Returns:
            List[Tuple[label, query_string]]
        """
        def _is_bad_kw(k: str) -> bool:
            kk = (k or "").strip()
            if not kk:
                return True
            if len(kk) < 2:
                return True
            if kk.isdigit():
                return True

            # Very common/low-signal Korean tokens in patent boilerplate or generic phrasing
            stop = {
                "공개", "특허", "공보", "번호", "일자", "대한민국", "특허청", "출원", "출원인",
                "국제", "분류", "요약", "명세서", "청구", "청구항", "대표", "도", "cpc",
                "방법", "장치", "시스템", "단계", "제공", "수행", "식별", "기초", "수신",
                "입력", "데이터", "변경", "정보", "관련", "위한", "통해", "상기", "본", "일",
                "실시", "개시", "단말", "서비스", "사업자",
            }
            if kk in stop:
                return True
            return False

        # De-dup while preserving order, and drop low-signal tokens.
        cleaned: List[str] = []
        seen = set()
        for kw in (keywords or []):
            k = (kw or "").strip()
            if _is_bad_kw(k):
                continue
            if k not in seen:
                cleaned.append(k)
                seen.add(k)

        # If everything gets filtered (rare), fall back to raw keywords.
        if not cleaned:
            cleaned = [k for k in (keywords or []) if (k or "").strip()]

        # Strategy:
        # - broad: slightly wider net but still mostly technical
        # - balanced: shorter, high-signal tokens to avoid collapsing with IPC/applicant filters
        broad_query = " ".join(cleaned[:10]).strip() or (base_query or "")
        balanced_query = " ".join(cleaned[:8]).strip() or (base_query or "")

        # MVP 호환: 항상 broad/balanced 2개를 계획해서
        # 라우터 SSE(stage=prior_art_search) 진행률 이벤트가 일정하게 유지되도록 한다.
        if not broad_query and base_query:
            broad_query = base_query
        if not balanced_query:
            balanced_query = broad_query

        queries: List[Tuple[str, str]] = []
        if broad_query:
            queries.append(("broad", broad_query))
        if balanced_query:
            queries.append(("balanced", balanced_query))

        # 최후 폴백
        if not queries and base_query:
            queries.append(("fallback", base_query))

        return queries

    async def execute_search(
        self,
        *,
        query: str,
        applicant: Optional[str] = None,
        ipc_code: Optional[str] = None,
        date_from: Optional[str] = None,
        max_results: int = 20,
    ) -> Tuple[List[Any], int]:
        """
        단일 질의 검색 실행 (KIPRIS)
        """
        kipris = KiprisClient()
        try:
            patents, total = await kipris.search_patents(
                query=query,
                applicant=applicant,
                ipc_code=ipc_code,
                date_from=date_from,
                max_results=max_results,
            )
            return (patents or [], int(total or 0))
        except Exception as e:
            logger.error(f"❌ [PriorArtSearchTool] 검색 실패 (query={query}): {e}")
            return ([], 0)
        finally:
            try:
                await kipris.close()
            except Exception:
                pass

    # NOTE: 결과 스크리닝(중복 제거/관련도 컷오프/정렬)은 PriorArtScreeningTool로 분리됨.

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("Use generate_queries, execute_search, deduplicate_and_sort methods.")

    def _run(self, *args, **kwargs):
        raise NotImplementedError("PriorArtSearchTool supports async only.")


prior_art_search_tool = PriorArtSearchTool()

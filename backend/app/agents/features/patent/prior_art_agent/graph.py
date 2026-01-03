from __future__ import annotations

from typing import Any, Dict, Sequence

from langchain_core.messages import AIMessage, BaseMessage
from loguru import logger


async def prior_art_worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Supervisor worker entrypoint for Prior Art (KIPRIS).

    This node is import-safe: heavy dependencies and network clients are imported
    only at runtime inside the function.

    Expected behavior (MVP):
    - Analyze input → plan queries → execute searches → screen → build markdown report.
    - Store structured artifacts in shared_context.
    """

    # Lazy imports to avoid import-time side effects.
    from app.agents.features.patent.prior_art_agent.tools.orchestrator import prior_art_orchestrator

    messages: Sequence[BaseMessage] = state["messages"]
    user_text = messages[-1].content

    shared_context = dict(state.get("shared_context", {}))
    attached_document_context = shared_context.get("attached_document_context")

    logger.info(f"Supervisor routing to PriorArtAgent: {str(user_text)[:50]}...")

    try:
        analysis_result = await prior_art_orchestrator.analyze_input(
            attached_document_context=attached_document_context,
            rewritten_query=user_text,
            fallback_keywords=None,
        )

        planned = prior_art_orchestrator.plan_search(analysis_result=analysis_result, base_query=user_text)

        all_patents = []
        search_runs = []
        broad_query = ""
        balanced_query = ""

        for idx, (label, query) in enumerate(planned, start=1):
            if idx == 1:
                broad_query = query
            elif idx == 2:
                balanced_query = query

            step = await prior_art_orchestrator.execute_search_step(
                label=label,
                query=query,
                applicant=None,
                ipc_code=None,
                date_from=None,
                max_results=20,
            )
            search_runs.append({k: step.get(k) for k in ("label", "query", "total_found", "returned")})
            all_patents.extend(step.get("patents") or [])

        unique_patents, stats = prior_art_orchestrator.screen_results(
            all_results=all_patents,
            target_keywords=analysis_result.get("keywords"),
            min_relevance_score=None,
            max_candidates=50,
        )

        search_metadata = {
            "search_runs": search_runs,
            "broad_query": broad_query,
            "balanced_query": balanced_query,
            "screening_stats": stats,
        }

        report = prior_art_orchestrator.create_report_content(
            session_id=shared_context.get("session_id"),
            user_message=user_text,
            document_ids=shared_context.get("document_ids"),
            analysis_result=analysis_result,
            search_metadata=search_metadata,
            unique_patents=unique_patents,
        )

        report_md = report.get("report_md", "")
        report_filename = report.get("report_filename", "prior-art-report.md")

        shared_context.update(
            {
                "prior_art": {
                    "analysis_result": analysis_result,
                    "search_metadata": search_metadata,
                    "unique_patents": unique_patents,
                    "report_md": report_md,
                    "report_filename": report_filename,
                }
            }
        )

        final_response = (
            "✅ 선행기술조사(초안) 생성 완료\n\n"
            f"- 후보 수: {len(unique_patents)}\n"
            f"- 리포트 파일명: {report_filename}\n"
            "\n"
            "필요하면 후보 상위 10개를 기반으로 비교표/요약도 생성할 수 있습니다."
        )

        return {
            "messages": [AIMessage(content=final_response, name="PriorArtAgent")],
            "shared_context": shared_context,
        }

    except Exception as e:
        logger.error(f"PriorArtAgent execution failed: {e}")
        shared_context.update({"prior_art_error": str(e)})
        return {
            "messages": [AIMessage(content=f"❌ Prior art search failed: {str(e)}", name="PriorArtAgent")],
            "shared_context": shared_context,
        }

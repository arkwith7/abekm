"""Prior-art tool benchmark / quality check.

Runs the prior-art tool chain against a local PDF and prints per-step metrics.
Intended to be executed inside the backend container:
  docker compose exec -T backend python3 backend/tests/prior_art_tool_benchmark.py

This script is read-only: it does NOT save generated reports to storage.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path


# Ensure repo root is importable when executed inside the container.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent  # /app when running from /app/tests
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _truncate(s: str, n: int = 240) -> str:
    s = s or ""
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def _normalize_ipc_prefix(value: Any) -> Optional[str]:
    import re

    v = (str(value or "").strip() if value is not None else "")
    if not v:
        return None
    m = re.match(r"^([A-H]\d{2}[A-Z])", v)
    return m.group(1) if m else None


def _normalize_applicant(value: Any) -> Optional[str]:
    import re

    v = (str(value or "").strip() if value is not None else "")
    if not v:
        return None
    v = re.split(r"\s{2,}|\t|\n|\(|\[", v)[0].strip()
    if len(v) < 2 or len(v) > 40:
        return None
    return v


async def main() -> None:
    # Path resolution order:
    # 1) CLI arg (most explicit)
    # 2) PDF_PATH env var
    # 3) Reasonable default for the backend container
    default_pdf = "/app/tests/1020240027504.pdf"
    pdf_path = (
        (sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else None)
        or (os.environ.get("PDF_PATH") or "").strip()
        or default_pdf
    )

    from app.services.document.extraction.text_extractor_service import text_extractor_service
    from app.tools.prior_art.orchestrator import prior_art_orchestrator

    print("=== Prior-art Tool Benchmark ===")
    print(f"pdf_path={pdf_path}")

    metrics: Dict[str, Any] = {"pdf_path": pdf_path}

    # 0) Extraction
    t0 = _now_ms()
    extraction = await text_extractor_service.extract_text(pdf_path, ".pdf")
    t1 = _now_ms()
    meta0 = extraction.get("metadata") or {}
    metrics["extraction"] = {
        "latency_ms": round(t1 - t0, 1),
        "success": bool(extraction.get("success")),
        "error": extraction.get("error"),
        "text_length": int(extraction.get("text_length") or 0),
        "extraction_method": meta0.get("extraction_method"),
        "extraction_note": meta0.get("extraction_note"),
        "provider": meta0.get("provider") or meta0.get("document_processing_provider"),
        "fallback_provider": meta0.get("fallback_provider"),
    }

    extracted_text = (extraction.get("text") or "").strip()
    print("\n[0] Extraction")
    print(json.dumps(metrics["extraction"], ensure_ascii=False, indent=2))
    print("text_excerpt=", _truncate(extracted_text, 260))

    # 1) Analysis
    t2 = _now_ms()
    analysis = await prior_art_orchestrator.analyze_input(
        attached_document_context=extracted_text,
        rewritten_query=None,
        fallback_keywords=None,
    )
    t3 = _now_ms()
    keywords: List[str] = list(analysis.get("keywords") or [])

    metrics["analysis"] = {
        "latency_ms": round(t3 - t2, 1),
        "original_length": analysis.get("original_length"),
        "summary_excerpt": _truncate(str(analysis.get("summary_excerpt") or ""), 220),
        "keywords_top": keywords[:20],
        "keywords_count": len(keywords),
        "ipc_candidates": analysis.get("ipc_candidates") or [],
        "ipc_code": analysis.get("ipc_code"),
        "applicant_candidates": analysis.get("applicant_candidates") or [],
        "applicant": analysis.get("applicant"),
    }

    print("\n[1] Analysis (PatentAnalysisTool)")
    print(json.dumps(metrics["analysis"], ensure_ascii=False, indent=2))

    # 2) Query planning
    t4 = _now_ms()
    planned: List[Tuple[str, str]] = list(prior_art_orchestrator.plan_search(analysis_result=analysis, base_query=None))
    t5 = _now_ms()
    metrics["plan_search"] = {
        "latency_ms": round(t5 - t4, 1),
        "planned_queries": [{"label": lbl, "query": q} for (lbl, q) in planned],
    }

    print("\n[2] Query planning (PriorArtSearchTool.generate_queries)")
    print(json.dumps(metrics["plan_search"], ensure_ascii=False, indent=2))

    # Normalize filters similar to API behavior
    applicant = _normalize_applicant(analysis.get("applicant"))
    ipc_prefix = _normalize_ipc_prefix(analysis.get("ipc_code"))

    # 3) Search execution
    search_runs: List[Dict[str, Any]] = []
    all_candidates: List[Any] = []

    print("\n[3] Search execution (KIPRIS)")
    for label, q in planned:
        run_ipc = ipc_prefix if label == "balanced" else None
        t6 = _now_ms()
        run = await prior_art_orchestrator.execute_search_step(
            label=label,
            query=q,
            applicant=applicant,
            ipc_code=run_ipc,
            date_from=None,
            max_results=20,
        )
        t7 = _now_ms()

        patents = run.get("patents") or []
        all_candidates.extend(patents)

        search_runs.append(
            {
                "label": label,
                "query": q,
                "applicant": applicant,
                "ipc_filter": run_ipc,
                "latency_ms": round(t7 - t6, 1),
                "total_found": int(run.get("total_found") or 0),
                "returned": int(run.get("returned") or 0),
                "sample_titles": [getattr(p, "title", None) for p in patents[:3]],
            }
        )

        print(json.dumps(search_runs[-1], ensure_ascii=False, indent=2))

    metrics["search"] = search_runs

    # Extra search variants: measure how IPC filter affects recall.
    # (In practice, overly strict IPC+word can easily collapse to 0.)
    broad_query = next((q for (lbl, q) in planned if lbl == "broad"), planned[0][1] if planned else "")
    balanced_query = next((q for (lbl, q) in planned if lbl == "balanced"), broad_query)
    short_query = " ".join([k for k in keywords if len(k) >= 3][:8])

    variants: List[Tuple[str, str, Optional[str], Optional[str]]] = [
        ("balanced_no_ipc", balanced_query, applicant, None),
        ("broad_with_ipc_prefix", broad_query, applicant, ipc_prefix),
        ("short_with_ipc_prefix", short_query, applicant, ipc_prefix),
    ]

    print("\n[3b] Search variants (diagnostics)")
    metrics["search_variants"] = []
    for name, qv, av, iv in variants:
        if not qv:
            continue
        t6 = _now_ms()
        run = await prior_art_orchestrator.execute_search_step(
            label=name,
            query=qv,
            applicant=av,
            ipc_code=iv,
            date_from=None,
            max_results=5,
        )
        t7 = _now_ms()
        patents = run.get("patents") or []
        row = {
            "label": name,
            "query": qv,
            "applicant": av,
            "ipc_filter": iv,
            "latency_ms": round(t7 - t6, 1),
            "total_found": int(run.get("total_found") or 0),
            "returned": int(run.get("returned") or 0),
            "sample_titles": [getattr(p, "title", None) for p in patents[:3]],
        }
        metrics["search_variants"].append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2))

    # 4) Screening
    t8 = _now_ms()
    screened, screening_stats = prior_art_orchestrator.screen_results(
        all_candidates,
        target_keywords=keywords,
        min_relevance_score=None,
        max_candidates=None,
    )
    t9 = _now_ms()

    def _patent_compact(p: Any) -> Dict[str, Any]:
        return {
            "application_number": getattr(p, "application_number", None),
            "title": getattr(p, "title", None),
            "applicant": getattr(p, "applicant", None),
            "ipc_code": getattr(p, "ipc_code", None),
            "open_date": getattr(p, "open_date", None),
        }

    metrics["screening"] = {
        "latency_ms": round(t9 - t8, 1),
        "stats": screening_stats,
        "out_count": len(screened),
        "top5": [_patent_compact(p) for p in screened[:5]],
    }

    print("\n[4] Screening (PriorArtScreeningTool)")
    print(json.dumps(metrics["screening"], ensure_ascii=False, indent=2))

    # 5) Report build (no save)
    t10 = _now_ms()
    report_out = prior_art_orchestrator.create_report_content(
        session_id="bench_1020240027504",
        user_message="(benchmark) 1020240027504.pdf 기반 선행기술조사",
        document_ids=None,
        analysis_result=analysis,
        search_metadata={
            "search_runs": search_runs,
            "broad_query": broad_query,
            "balanced_query": balanced_query,
        },
        unique_patents=screened,
    )
    t11 = _now_ms()

    report_md = str(report_out.get("report_md") or "")
    metrics["report"] = {
        "latency_ms": round(t11 - t10, 1),
        "report_filename": report_out.get("report_filename"),
        "report_length": len(report_md),
        "report_head": "\n".join(report_md.splitlines()[:30]),
    }

    print("\n[5] Report build (PriorArtReportTool.build_report)")
    print(json.dumps({k: v for k, v in metrics["report"].items() if k != "report_head"}, ensure_ascii=False, indent=2))
    print("\n--- report_head (first 30 lines) ---")
    print(metrics["report"]["report_head"])

    print("\n=== Summary JSON ===")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

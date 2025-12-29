"""Evaluate predicted prior-art retrieval results against ground truth.

Inputs:
  1) Ground truth dataset (JSONL): each line contains `target_patent` and `ground_truth_prior_arts`.
  2) Predictions (JSONL): each line must contain an application number and a list of predicted prior-arts.

Predictions JSONL accepted formats (per line):
  - {"application_number": "1020200027504", "predicted_prior_arts": ["US... A1", "JP..." ...]}
  - {"target_patent": {"application_number": "..."}, "predicted_prior_arts": [...]}

See: app/evaluation/PRIOR_ART_EVALUATION.md

Usage:
  PYTHONPATH=. /home/arkwith/Dev/abekm/.venv/bin/python app/scripts/evaluate_prior_art_retrieval.py \
    --dataset data/02kipris_semiconductor_ai_dataset.jsonl \
    --predictions data/predictions.jsonl \
    --k 20 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.evaluation.prior_art_ground_truth_dataset import (
    EvaluationSummary,
    evaluate_dataset_predictions,
    iter_jsonl,
    load_ground_truth_dataset,
    normalize_application_number,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate prior-art retrieval vs ground truth")
    p.add_argument("--dataset", required=True, help="Path to ground-truth JSONL dataset")
    p.add_argument("--predictions", required=True, help="Path to predictions JSONL")
    p.add_argument("--limit", type=int, default=None, help="Only read the first N targets from dataset (fast sanity check)")
    p.add_argument("--k", type=int, default=None, help="Use only top-K predictions per target")
    p.add_argument("--include-npl", action="store_true", help="Include NPL citations in scoring")
    p.add_argument("--json", action="store_true", help="Print summary as JSON")
    return p.parse_args()


def _extract_application_number(obj: Dict[str, Any]) -> Optional[str]:
    if isinstance(obj.get("application_number"), str):
        return obj["application_number"]
    tp = obj.get("target_patent")
    if isinstance(tp, dict) and isinstance(tp.get("application_number"), str):
        return tp["application_number"]
    if isinstance(obj.get("target_application_number"), str):
        return obj["target_application_number"]
    return None


def _extract_predictions_list(obj: Dict[str, Any]) -> List[str]:
    candidates = (
        obj.get("predicted_prior_arts"),
        obj.get("predicted"),
        obj.get("prior_arts"),
        obj.get("predictions"),
    )
    for v in candidates:
        if isinstance(v, list):
            out: List[str] = []
            for item in v:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    # Common keys from retrieval outputs
                    for k in ("publication_number", "doc_number", "citation", "id"):
                        if isinstance(item.get(k), str):
                            out.append(item[k])
                            break
            return out
    return []


def load_predictions(path: str | Path) -> Dict[str, List[str]]:
    p = Path(path)
    preds: Dict[str, List[str]] = {}
    for obj in iter_jsonl(p):
        app_no_raw = _extract_application_number(obj)
        if not app_no_raw:
            continue
        app_no = normalize_application_number(app_no_raw)
        preds[app_no] = _extract_predictions_list(obj)
    return preds


def _print_human(summary: EvaluationSummary, *, k: Optional[int]) -> None:
    print("=" * 70)
    print("Prior Art Retrieval Evaluation")
    print("=" * 70)
    print(f"Targets: {summary.total_targets}")
    print(f"Targets with predictions: {summary.targets_with_predictions}")
    print(f"Top-K: {k if k is not None else 'ALL'}")
    print("\nMicro (pooled):")
    print(f"  TP/FP/FN: {summary.micro.tp}/{summary.micro.fp}/{summary.micro.fn}")
    print(f"  Precision: {summary.micro.precision:.4f}")
    print(f"  Recall:    {summary.micro.recall:.4f}")
    print(f"  F1:        {summary.micro.f1:.4f}")
    print("\nMacro (avg per-target):")
    print(f"  Precision: {summary.macro_precision:.4f}")
    print(f"  Recall:    {summary.macro_recall:.4f}")
    print(f"  F1:        {summary.macro_f1:.4f}")


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    predictions_path = Path(args.predictions)

    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return 2
    if not predictions_path.exists():
        print(f"❌ Predictions not found: {predictions_path}")
        return 2

    rows = load_ground_truth_dataset(dataset_path, limit=args.limit)
    predictions = load_predictions(predictions_path)
    summary = evaluate_dataset_predictions(
        rows=rows,
        predictions_by_application_number=predictions,
        k=args.k,
        include_npl=args.include_npl,
    )

    if args.json:
        print(json.dumps(summary.model_dump(), indent=2, ensure_ascii=False))
        return 0

    _print_human(summary, k=args.k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

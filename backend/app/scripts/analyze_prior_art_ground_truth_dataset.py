"""Analyze KIPRIS prior-art ground-truth JSONL dataset.

Usage:
  PYTHONPATH=./ python app/scripts/analyze_prior_art_ground_truth_dataset.py \
    --path data/02kipris_semiconductor_ai_dataset.jsonl

Prints basic stats (targets, citations, country breakdown, NPL counts).

See: app/evaluation/PRIOR_ART_EVALUATION.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from app.evaluation.prior_art_ground_truth_dataset import (
        compute_dataset_stats,
        load_ground_truth_dataset,
    )
except Exception as e:  # pragma: no cover
    print(f"❌ Failed importing application modules: {e}")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze prior-art ground truth dataset (JSONL)")
    p.add_argument("--path", required=True, help="Path to JSONL dataset")
    p.add_argument("--limit", type=int, default=None, help="Only read the first N targets (fast sanity check)")
    p.add_argument("--json", action="store_true", help="Print stats as JSON")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.path)
    if not dataset_path.exists():
        print(f"❌ File not found: {dataset_path}")
        return 2

    rows = load_ground_truth_dataset(dataset_path, limit=args.limit)
    stats = compute_dataset_stats(rows)

    if args.json:
        print(json.dumps(stats.model_dump(), indent=2, ensure_ascii=False))
        return 0

    print("=" * 70)
    print("Prior Art Ground Truth Dataset Stats")
    print("=" * 70)
    print(f"Targets: {stats.total_targets}")
    print(f"Citations (total): {stats.total_citations}")
    print(f"Avg citations/target: {stats.avg_citations_per_target:.2f}")
    print(f"Unique patent citations: {stats.unique_patent_citations}")
    print(f"NPL citations: {stats.npl_citations}")
    print(f"Unknown/unparsed citations: {stats.unknown_citations}")
    print("\nPatent citation country breakdown:")
    for cc, n in stats.patent_citation_country_counts.items():
        print(f"  - {cc}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

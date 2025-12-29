from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field


_PATENT_CITATION_RE = re.compile(
    r"^\s*(?P<country>[A-Z]{2}|WO|EP)\s*(?P<number>[0-9A-Z][0-9A-Z\-\/\.]+?)\s*(?P<kind>[A-Z][0-9A-Z]{0,3})?\s*$"
)


class TargetPatent(BaseModel):
    application_number: str
    title: str
    abstract: str = ""
    ipc: str = ""
    applicant: str = ""
    date: Optional[str] = None
    biblio: Dict[str, Any] = Field(default_factory=dict)


class DatasetMeta(BaseModel):
    source: str = "KIPRIS"
    query_type: Optional[str] = None
    mode: Optional[str] = None
    search_policy: Optional[str] = None


class GroundTruthRow(BaseModel):
    target_patent: TargetPatent
    ground_truth_prior_arts: List[str] = Field(default_factory=list)
    meta: DatasetMeta = Field(default_factory=DatasetMeta)


@dataclass(frozen=True)
class NormalizedCitation:
    raw: str
    citation_type: str  # "patent" | "npl" | "unknown"
    country: Optional[str]
    number: Optional[str]
    kind: Optional[str]
    normalized_id: Optional[str]


def _clean_doc_number(value: str) -> str:
    # Keep alphanumerics only; normalize common separators.
    return re.sub(r"[^0-9A-Z]", "", value.upper())


def normalize_citation(citation: str) -> NormalizedCitation:
    """Normalize a prior-art citation string.

    The dataset mixes patent literature (US/EP/JP/CN/KR/WO...) and
    non-patent literature (paper titles, author lists, etc.).

    Returns:
        NormalizedCitation with a stable `normalized_id` for patent citations.
        For NPL, `normalized_id` is None (you may choose to hash externally).
    """
    raw = (citation or "").strip()
    if not raw:
        return NormalizedCitation(raw=citation, citation_type="unknown", country=None, number=None, kind=None, normalized_id=None)

    m = _PATENT_CITATION_RE.match(raw)
    if not m:
        # Heuristic: if it contains 'et al.' or looks like a sentence, treat as NPL.
        if any(tok in raw.lower() for tok in ["et al", "conference", "journal", "doi", "pp."]):
            return NormalizedCitation(raw=raw, citation_type="npl", country=None, number=None, kind=None, normalized_id=None)
        return NormalizedCitation(raw=raw, citation_type="unknown", country=None, number=None, kind=None, normalized_id=None)

    country = (m.group("country") or "").upper()
    number = _clean_doc_number(m.group("number") or "")
    kind = (m.group("kind") or "").upper() or None

    # Canonical ID: COUNTRY + NUMBER + KIND (if present)
    normalized_id = f"{country}{number}{kind or ''}" if country and number else None
    return NormalizedCitation(raw=raw, citation_type="patent", country=country, number=number, kind=kind, normalized_id=normalized_id)


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Stream JSONL file safely (skips blank lines)."""
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {line_no} in {path}: {e}") from e


def load_ground_truth_dataset(path: str | Path) -> List[GroundTruthRow]:
    p = Path(path)
    rows: List[GroundTruthRow] = []
    for obj in iter_jsonl(p):
        rows.append(GroundTruthRow.model_validate(obj))
    return rows


class DatasetStats(BaseModel):
    total_targets: int
    total_citations: int
    avg_citations_per_target: float
    unique_patent_citations: int
    patent_citation_country_counts: Dict[str, int]
    npl_citations: int
    unknown_citations: int


def compute_dataset_stats(rows: Sequence[GroundTruthRow]) -> DatasetStats:
    patent_country_counts: Dict[str, int] = {}
    patent_ids: set[str] = set()
    npl_count = 0
    unknown_count = 0
    total_citations = 0

    for row in rows:
        total_citations += len(row.ground_truth_prior_arts)
        for c in row.ground_truth_prior_arts:
            nc = normalize_citation(c)
            if nc.citation_type == "patent" and nc.normalized_id:
                patent_ids.add(nc.normalized_id)
                patent_country_counts[nc.country or "??"] = patent_country_counts.get(nc.country or "??", 0) + 1
            elif nc.citation_type == "npl":
                npl_count += 1
            else:
                unknown_count += 1

    total_targets = len(rows)
    avg = (total_citations / total_targets) if total_targets else 0.0
    return DatasetStats(
        total_targets=total_targets,
        total_citations=total_citations,
        avg_citations_per_target=avg,
        unique_patent_citations=len(patent_ids),
        patent_citation_country_counts=dict(sorted(patent_country_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        npl_citations=npl_count,
        unknown_citations=unknown_count,
    )


class RetrievalMetrics(BaseModel):
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


def evaluate_retrieval(
    *,
    predicted: Iterable[str],
    ground_truth: Iterable[str],
    include_npl: bool = False,
) -> RetrievalMetrics:
    """Evaluate predicted prior-art list against ground truth.

    Important: This evaluator is normalization-based.
    - Patent citations are normalized to stable IDs.
    - NPL is ignored by default (include_npl=False) because many retrieval stacks
      only target patent literature.
    """

    gt_patent: set[str] = set()
    gt_npl_raw: set[str] = set()
    for c in ground_truth:
        nc = normalize_citation(c)
        if nc.citation_type == "patent" and nc.normalized_id:
            gt_patent.add(nc.normalized_id)
        elif include_npl and nc.citation_type == "npl":
            gt_npl_raw.add(nc.raw)

    pred_patent: set[str] = set()
    pred_npl_raw: set[str] = set()
    for c in predicted:
        nc = normalize_citation(c)
        if nc.citation_type == "patent" and nc.normalized_id:
            pred_patent.add(nc.normalized_id)
        elif include_npl and nc.citation_type == "npl":
            pred_npl_raw.add(nc.raw)

    gt_all = set(gt_patent)
    pred_all = set(pred_patent)
    if include_npl:
        # For NPL we keep raw matching (no canonical id).
        gt_all |= {f"NPL:{x}" for x in gt_npl_raw}
        pred_all |= {f"NPL:{x}" for x in pred_npl_raw}

    tp = len(gt_all & pred_all)
    fp = len(pred_all - gt_all)
    fn = len(gt_all - pred_all)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return RetrievalMetrics(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)

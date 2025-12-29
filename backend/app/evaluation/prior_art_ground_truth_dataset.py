from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

from pydantic import BaseModel, Field


_PATENT_CITATION_RE = re.compile(
    r"^\s*(?P<country>[A-Z]{2}|WO|EP)\s*(?P<number>[0-9A-Z][0-9A-Z\-\/\.]+?)\s*(?P<kind>[A-Z][0-9A-Z]{0,3})?\s*$"
)


def normalize_application_number(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "").strip()).upper()


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
    return re.sub(r"[^0-9A-Z]", "", value.upper())


def normalize_citation(citation: str) -> NormalizedCitation:
    """Normalize a prior-art citation string into a stable key when possible."""

    raw = (citation or "").strip()
    if not raw:
        return NormalizedCitation(
            raw=citation,
            citation_type="unknown",
            country=None,
            number=None,
            kind=None,
            normalized_id=None,
        )

    m = _PATENT_CITATION_RE.match(raw)
    if not m:
        if any(tok in raw.lower() for tok in ["et al", "conference", "journal", "doi", "pp."]):
            return NormalizedCitation(raw=raw, citation_type="npl", country=None, number=None, kind=None, normalized_id=None)
        return NormalizedCitation(raw=raw, citation_type="unknown", country=None, number=None, kind=None, normalized_id=None)

    country = (m.group("country") or "").upper()
    number = _clean_doc_number(m.group("number") or "")
    kind = (m.group("kind") or "").upper() or None
    normalized_id = f"{country}{number}{kind or ''}" if country and number else None
    return NormalizedCitation(raw=raw, citation_type="patent", country=country, number=number, kind=kind, normalized_id=normalized_id)


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {line_no} in {path}: {e}") from e


def load_ground_truth_dataset(path: str | Path, *, limit: Optional[int] = None) -> List[GroundTruthRow]:
    p = Path(path)
    rows: List[GroundTruthRow] = []
    for obj in iter_jsonl(p):
        rows.append(GroundTruthRow.model_validate(obj))
        if limit is not None and len(rows) >= limit:
            break
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
                cc = nc.country or "??"
                patent_country_counts[cc] = patent_country_counts.get(cc, 0) + 1
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
        gt_all |= {f"NPL:{x}" for x in gt_npl_raw}
        pred_all |= {f"NPL:{x}" for x in pred_npl_raw}

    tp = len(gt_all & pred_all)
    fp = len(pred_all - gt_all)
    fn = len(gt_all - pred_all)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return RetrievalMetrics(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)


class EvaluationSummary(BaseModel):
    total_targets: int
    targets_with_predictions: int
    micro: RetrievalMetrics
    macro_precision: float
    macro_recall: float
    macro_f1: float


def evaluate_dataset_predictions(
    *,
    rows: Sequence[GroundTruthRow],
    predictions_by_application_number: Dict[str, List[str]],
    k: Optional[int] = None,
    include_npl: bool = False,
) -> EvaluationSummary:
    tp_sum = fp_sum = fn_sum = 0
    precisions: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []

    targets_with_predictions = 0
    for row in rows:
        app_no = normalize_application_number(row.target_patent.application_number)
        pred = predictions_by_application_number.get(app_no, [])
        if pred:
            targets_with_predictions += 1
        pred_k = pred[:k] if (k is not None) else pred

        m = evaluate_retrieval(predicted=pred_k, ground_truth=row.ground_truth_prior_arts, include_npl=include_npl)
        tp_sum += m.tp
        fp_sum += m.fp
        fn_sum += m.fn
        precisions.append(m.precision)
        recalls.append(m.recall)
        f1s.append(m.f1)

    micro = evaluate_retrieval(
        predicted=[],
        ground_truth=[],
        include_npl=include_npl,
    )
    micro = RetrievalMetrics(
        tp=tp_sum,
        fp=fp_sum,
        fn=fn_sum,
        precision=(tp_sum / (tp_sum + fp_sum)) if (tp_sum + fp_sum) else 0.0,
        recall=(tp_sum / (tp_sum + fn_sum)) if (tp_sum + fn_sum) else 0.0,
        f1=(2 * (tp_sum / (tp_sum + fp_sum)) * (tp_sum / (tp_sum + fn_sum)) / ((tp_sum / (tp_sum + fp_sum)) + (tp_sum / (tp_sum + fn_sum))))
        if (tp_sum + fp_sum) and (tp_sum + fn_sum) and ((tp_sum / (tp_sum + fp_sum)) + (tp_sum / (tp_sum + fn_sum)))
        else 0.0,
    )

    total = len(rows)
    macro_precision = sum(precisions) / total if total else 0.0
    macro_recall = sum(recalls) / total if total else 0.0
    macro_f1 = sum(f1s) / total if total else 0.0
    return EvaluationSummary(
        total_targets=total,
        targets_with_predictions=targets_with_predictions,
        micro=micro,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
    )

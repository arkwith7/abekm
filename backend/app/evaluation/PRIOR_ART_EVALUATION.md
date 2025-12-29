# Prior Art Ground Truth Dataset — What We Evaluate

This repo contains a KIPRIS-derived dataset:

- Ground truth = **examiner-cited prior art** strings for each target KR patent.
- Each dataset row is a pair:
  - `target_patent` (application number + title/abstract/etc.)
  - `ground_truth_prior_arts` (list of citations; mixed patent literature + NPL)

## Evaluation Goal

We evaluate **prior-art retrieval quality**:

- Input: a system (or baseline script) that outputs, for each `target_patent.application_number`, a ranked list of predicted prior-art citations.
- Output: metrics comparing predicted vs ground-truth citations.

In other words, the evaluation answers:

> “Given a target patent, how many of the examiner-cited prior arts does the system retrieve?”

This is primarily a **recall-oriented** task (but precision is also measured).

## What Is Scored

### Patent citations (default)

By default, scoring is **patent-literature only**:

- Ground-truth and predicted citations are normalized.
- A match is counted when the normalized IDs are equal.

Current normalization for patent citations:

- Parses forms like `US20140072209 A1`, `US 2014/0072209 A1`, `JP2000123456 A`.
- Canonical ID = `COUNTRY + DOC_NUMBER + KIND` (kind is included if present).
  - Example: `US 2014/0072209 A1` → `US20140072209A1`

### NPL citations (optional)

The dataset contains NPL (papers, standards, etc.).

- Default behavior: **NPL is ignored** in scoring.
- If you want to include it, run the evaluator with `--include-npl`.
  - Current behavior for NPL: raw-string match only (no DOI/title canonicalization yet).

## Metrics

The evaluator reports:

- **Micro (pooled) Precision / Recall / F1**: counts TP/FP/FN over all targets.
- **Macro Precision / Recall / F1**: averages per-target metrics.

It also supports `--k` (Top-K): use only the first K predictions per target.

## Inputs / Outputs

### Ground truth dataset (JSONL)

File example:

- `backend/data/02kipris_semiconductor_ai_dataset.jsonl`

Each line includes:

- `target_patent.application_number`
- `ground_truth_prior_arts` (list of strings)

### Predictions (JSONL)

The evaluator expects a JSONL where each line has:

- an application number
- a list of predicted prior-art strings

Accepted shapes:

```json
{"application_number": "1020200027504", "predicted_prior_arts": ["US... A1", "JP... A"]}
```

or

```json
{"target_patent": {"application_number": "1020200027504"}, "predicted_prior_arts": ["US... A1"]}
```

## Limitations (current)

- No patent-family collapsing (same invention across jurisdictions may be counted separately).
- Kind-code equivalences are not expanded (e.g., A1 vs A). Matching is strict on normalized ID.
- NPL normalization is minimal.

If you want, we can extend normalization to:

- family-based dedup (INPADOC / simple heuristics)
- kind-code mapping per jurisdiction
- DOI/title hashing for NPL

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class SqlGuardConfig:
    """Guards for safe, read-only SQL."""

    max_rows: int = 100
    allowed_schemas: Optional[Sequence[str]] = ("public",)
    allowlist_tables: Optional[Sequence[str]] = None  # e.g., ("public.documents", "public.chunks")


class SqlGuardError(ValueError):
    pass


_FORBIDDEN_PATTERNS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bVACUUM\b",
    r"\bCOPY\b",
    r"\bCALL\b",
    r"\bDO\b",
    r";\s*\S+",  # multiple statements
]


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", (sql or "").strip())


def validate_read_only_sql(sql: str, *, config: SqlGuardConfig) -> str:
    """Validate & normalize SQL.

    - Enforces SELECT-only
    - Blocks common mutating keywords
    - Enforces a LIMIT if missing

    Returns normalized SQL (possibly with LIMIT appended).
    """

    normalized = _normalize_sql(sql)
    if not normalized:
        raise SqlGuardError("Empty SQL")

    # Must start with SELECT (simple rule by design)
    if not re.match(r"(?is)^\s*select\b", normalized):
        raise SqlGuardError("Only SELECT queries are allowed")

    for pat in _FORBIDDEN_PATTERNS:
        if re.search(pat, normalized, flags=re.IGNORECASE):
            raise SqlGuardError("Potentially unsafe SQL detected")

    # Optional allowlist enforcement (best-effort, heuristic)
    if config.allowlist_tables:
        lower = normalized.lower()
        allowed = {t.lower() for t in config.allowlist_tables}

        # Extract table tokens after FROM/JOIN (very simple heuristic)
        table_candidates = re.findall(r"(?is)\b(from|join)\s+([a-zA-Z0-9_\.\"]+)", lower)
        tables = []
        for _, tok in table_candidates:
            tok = tok.strip().strip('"')
            tables.append(tok)

        # If any table appears and is not in allowlist -> block
        for t in tables:
            # Normalize schema.table
            if "." not in t and config.allowed_schemas:
                t_norm = f"{config.allowed_schemas[0]}.{t}"
            else:
                t_norm = t
            if t_norm not in allowed:
                raise SqlGuardError(f"Table not allowlisted: {t}")

    # Enforce LIMIT
    if not re.search(r"(?is)\blimit\s+\d+\b", normalized):
        normalized = f"{normalized} LIMIT {int(config.max_rows)}"

    return normalized

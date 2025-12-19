"""Stream/character-oriented chunker.

Use when documents have weak or no explicit section structure (news/blog posts/boards/ads).
Chunk boundaries prioritize line breaks and sentence-like punctuation, then hard-split by
character/token limits as a fallback.

Output shape matches advanced_chunk_text():
  {content_text, token_count, char_count, source_object_ids, page_numbers}
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


_PUNCT_SPLIT_RE = re.compile(r"(?<=[\.!\?\u3002\uff01\uff1f])\s+")


def _tokenize(text: str) -> List[str]:
    # Keep consistent with advanced_chunker fallback behavior.
    return (text or "").split()


def stream_chunk_text(
    objects: Iterable[Tuple[str, Optional[int], int]],
    *,
    min_tokens: int = 80,
    target_tokens: int = 280,
    max_tokens: int = 420,
    overlap_tokens: int = 40,
    max_chars: int = 4000,
    join_separator: str = "\n",
) -> List[Dict[str, Any]]:
    """Chunk unstructured text with line/sentence hints, then length fallback."""
    try:
        segments: List[Tuple[str, Optional[int], int]] = []
        for text, page_no, obj_id in objects:
            if not text or not text.strip():
                continue
            normalized = text.replace("\r", "")

            # 1) Prefer line boundaries first
            for line in normalized.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # 2) If a line is very long, try sentence-ish boundaries
                if len(line) > max_chars:
                    parts = [p.strip() for p in _PUNCT_SPLIT_RE.split(line) if p.strip()]
                    if parts:
                        for part in parts:
                            segments.append((part, page_no, obj_id))
                        continue

                segments.append((line, page_no, obj_id))

        if not segments:
            return []

        chunks: List[Dict[str, Any]] = []
        buffer_tokens: List[str] = []
        buffer_texts: List[str] = []
        buffer_object_ids: Set[int] = set()
        buffer_pages: Set[int] = set()

        def flush(final: bool = False):
            if not buffer_texts:
                return
            content_text = join_separator.join(buffer_texts).strip()
            if not content_text:
                return

            if not final and len(buffer_tokens) < min_tokens:
                return

            chunks.append(
                {
                    "content_text": content_text,
                    "token_count": len(buffer_tokens),
                    "char_count": len(content_text),
                    "source_object_ids": list(buffer_object_ids),
                    "page_numbers": sorted(list(buffer_pages)),
                }
            )

        def reset_buffers():
            nonlocal buffer_tokens, buffer_texts, buffer_object_ids, buffer_pages
            buffer_tokens = []
            buffer_texts = []
            buffer_object_ids = set()
            buffer_pages = set()

        for seg_text, page_no, obj_id in segments:
            seg_tokens = _tokenize(seg_text)

            # Hard-split extremely long segments
            if len(seg_tokens) > max_tokens or len(seg_text) > max_chars * 2:
                flush(final=True)
                reset_buffers()

                # Prefer token slicing when possible, else char slicing
                if len(seg_tokens) > max_tokens:
                    start = 0
                    while start < len(seg_tokens):
                        end = min(start + max_tokens, len(seg_tokens))
                        slice_tokens = seg_tokens[start:end]
                        slice_text = " ".join(slice_tokens)
                        chunks.append(
                            {
                                "content_text": slice_text,
                                "token_count": len(slice_tokens),
                                "char_count": len(slice_text),
                                "source_object_ids": [obj_id],
                                "page_numbers": [page_no] if page_no is not None else [],
                            }
                        )
                        start = end - overlap_tokens if (end < len(seg_tokens) and overlap_tokens > 0) else end
                else:
                    start = 0
                    while start < len(seg_text):
                        end = min(start + max_chars, len(seg_text))
                        slice_text = seg_text[start:end].strip()
                        if slice_text:
                            chunks.append(
                                {
                                    "content_text": slice_text,
                                    "token_count": len(_tokenize(slice_text)),
                                    "char_count": len(slice_text),
                                    "source_object_ids": [obj_id],
                                    "page_numbers": [page_no] if page_no is not None else [],
                                }
                            )
                        start = end
                continue

            prospective_tokens = len(buffer_tokens) + len(seg_tokens)
            prospective_chars = sum(len(t) for t in buffer_texts) + len(seg_text)

            if prospective_tokens > max_tokens or prospective_chars > max_chars:
                flush(final=True)

                # overlap carry (token-based approximation)
                if overlap_tokens > 0 and buffer_tokens:
                    last_tokens = buffer_tokens[-overlap_tokens:]
                    buffer_tokens = list(last_tokens)
                    buffer_texts = [" ".join(last_tokens)] if last_tokens else []
                    buffer_object_ids = set()
                    buffer_pages = set()
                else:
                    reset_buffers()

            buffer_tokens.extend(seg_tokens)
            buffer_texts.append(seg_text)
            buffer_object_ids.add(obj_id)
            if page_no is not None:
                buffer_pages.add(page_no)

            if len(buffer_tokens) >= target_tokens or prospective_chars >= max_chars:
                flush(final=True)
                if overlap_tokens > 0:
                    last_tokens = buffer_tokens[-overlap_tokens:]
                    buffer_tokens = list(last_tokens)
                    buffer_texts = [" ".join(last_tokens)] if last_tokens else []
                    buffer_object_ids = set()
                    buffer_pages = set()
                else:
                    reset_buffers()

        flush(final=True)
        return chunks
    except Exception as e:  # pragma: no cover
        logger.error(f"[STREAM-CHUNKER] 청킹 실패: {e}")
        return []


__all__ = ["stream_chunk_text"]

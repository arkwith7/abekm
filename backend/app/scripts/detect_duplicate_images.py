"""Duplicate Image Detection Utility (pHash-based)

Usage:
  PYTHONPATH=./ python app/scripts/detect_duplicate_images.py --threshold 6 --limit 500 --recent-only

Features:
  * Loads IMAGE objects with non-null phash from database
  * Computes pairwise Hamming distances (optimized by grouping by phash prefix)
  * Reports likely duplicates (distance <= threshold)
  * Optionally restricts to recent N objects (by object_id desc)

Exit Codes:
  0 success (some or none duplicates)
  2 db/config issues
"""
from __future__ import annotations
import argparse
import sys
from typing import List, Tuple, Dict

from sqlalchemy import select

try:
    from app.core.database import async_session
    from app.models.document.multimodal_models import DocExtractedObject
except Exception as e:  # pragma: no cover
    print(f"❌ Import failed: {e}")
    sys.exit(2)


def hamming_hex(a: str, b: str) -> int:
    """Compute Hamming distance between two hexadecimal pHash strings."""
    try:
        if not a or not b:
            return 999
        # Normalize length by padding shorter
        if len(a) != len(b):
            m = max(len(a), len(b))
            a = a.ljust(m, '0')
            b = b.ljust(m, '0')
        x = int(a, 16) ^ int(b, 16)
        # Count bits
        return bin(x).count('1')
    except Exception:
        return 999


async def load_images(limit: int | None, recent_only: bool) -> List[DocExtractedObject]:
    async with async_session() as session:
        stmt = select(DocExtractedObject).where(
            DocExtractedObject.object_type == 'IMAGE',
            DocExtractedObject.phash.isnot(None)
        )
        if recent_only:
            stmt = stmt.order_by(DocExtractedObject.object_id.desc())
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return list(rows)


def find_duplicates(objs: List[DocExtractedObject], threshold: int) -> List[Dict[str, object]]:
    # Group by first 4 hex chars to reduce comparisons
    buckets: Dict[str, List[DocExtractedObject]] = {}
    for o in objs:
        key = (o.phash or '????')[:4]
        buckets.setdefault(key, []).append(o)

    duplicates: List[Dict[str, object]] = []
    for key, group in buckets.items():
        n = len(group)
        if n < 2:
            continue
        for i in range(n):
            for j in range(i+1, n):
                h = hamming_hex(group[i].phash, group[j].phash)
                if h <= threshold:
                    duplicates.append({
                        'object_id_a': group[i].object_id,
                        'object_id_b': group[j].object_id,
                        'file_a': group[i].file_bss_info_sno,
                        'file_b': group[j].file_bss_info_sno,
                        'page_a': group[i].page_no,
                        'page_b': group[j].page_no,
                        'phash_a': group[i].phash,
                        'phash_b': group[j].phash,
                        'distance': h
                    })
    # Sort by distance then object ids
    duplicates.sort(key=lambda d: (d['distance'], d['object_id_a'], d['object_id_b']))
    return duplicates


async def main():
    parser = argparse.ArgumentParser(description="Detect duplicate images using pHash")
    parser.add_argument('--threshold', type=int, default=5, help='Maximum Hamming distance to consider duplicate')
    parser.add_argument('--limit', type=int, default=1000, help='Limit number of images to load')
    parser.add_argument('--recent-only', action='store_true', help='Fetch most recent images first (object_id desc)')
    parser.add_argument('--top', type=int, default=50, help='Show top N duplicate pairs')
    args = parser.parse_args()

    images = await load_images(args.limit, args.recent_only)
    if not images:
        print("⚠ No images with non-null phash found.")
        return 0
    print(f"Loaded {len(images)} images with pHash. Computing duplicates (threshold={args.threshold})...")
    dups = find_duplicates(images, args.threshold)
    if not dups:
        print("✅ No duplicates found under threshold.")
        return 0
    print(f"Found {len(dups)} candidate duplicate pairs. Showing top {args.top}:")
    for row in dups[:args.top]:
        print(f"  dist={row['distance']:02d} A#{row['object_id_a']}({row['file_a']}/{row['page_a']}) B#{row['object_id_b']}({row['file_b']}/{row['page_b']}) phashA={row['phash_a']} phashB={row['phash_b']}")
    return 0


if __name__ == '__main__':  # pragma: no cover
    import asyncio
    asyncio.run(main())

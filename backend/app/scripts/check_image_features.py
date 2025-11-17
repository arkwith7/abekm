#!/usr/bin/env python
"""Check Image Feature Extraction Results

Usage:
  PYTHONPATH=./ python app/scripts/check_image_features.py --file-id 2

Outputs each IMAGE object for the given file with:
  object_id, page_no, seq, phash, width, height
And a short aggregate summary (counts, missing phash, avg dimensions).
"""
from __future__ import annotations
import argparse
import asyncio
from statistics import mean

from sqlalchemy import select

try:
    from app.core.database import get_async_session_local
    from app.models.document.multimodal_models import DocExtractedObject
except Exception as e:  # pragma: no cover
    print(f"❌ Import failure: {e}")
    raise SystemExit(2)


async def run(file_id: int, limit: int | None):
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        stmt = select(DocExtractedObject).where(
            DocExtractedObject.file_bss_info_sno == file_id,
            DocExtractedObject.object_type == 'IMAGE'
        ).order_by(DocExtractedObject.object_id.asc())
        if limit:
            stmt = stmt.limit(limit)
        res = await session.execute(stmt)
        rows = res.scalars().all()
        if not rows:
            print(f"⚠ No IMAGE objects found for file {file_id}.")
            return 0

        print(f"📄 IMAGE objects for file {file_id} (showing {len(rows)}):")
        missing = 0
        widths, heights = [], []
        for r in rows:
            w = getattr(r, 'image_width', None)
            h = getattr(r, 'image_height', None)
            ph = getattr(r, 'phash', None)
            if ph is None:
                missing += 1
            if w:
                widths.append(w)
            if h:
                heights.append(h)
            print(f"  id={r.object_id} page={r.page_no} seq={r.sequence_in_page} phash={ph} size={w}x{h}")

        print("\nSummary:")
        print(f"  total_images={len(rows)}")
        print(f"  missing_phash={missing}")
        if widths and heights:
            print(f"  avg_width={mean(widths):.1f} avg_height={mean(heights):.1f}")
        return 0


def main():
    ap = argparse.ArgumentParser(description="Inspect image feature extraction results for a file")
    ap.add_argument('--file-id', type=int, required=True)
    ap.add_argument('--limit', type=int, help='Optional limit of images to display')
    args = ap.parse_args()
    asyncio.run(run(args.file_id, args.limit))


if __name__ == '__main__':  # pragma: no cover
    main()

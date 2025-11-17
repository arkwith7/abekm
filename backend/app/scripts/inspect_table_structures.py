"""Inspect extracted TABLE objects structure_json for a given file.

Usage:
  PYTHONPATH=./ python app/scripts/inspect_table_structures.py --file-id 123 --limit 10

Reports:
  - Count of TABLE objects
  - For each sample: page_no, sequence_in_page, rows/cols, header row (if detected)
Detection:
  - Treat first row of 'content' or 'cells' as header when has_header flag present.
"""
from __future__ import annotations
import argparse
import sys
from sqlalchemy import select

try:
    from app.core.database import async_session
    from app.models.document.multimodal_models import DocExtractedObject
except Exception as e:  # pragma: no cover
    print(f"❌ Import failed: {e}")
    sys.exit(2)


async def load_tables(file_id: int, limit: int):
    async with async_session() as session:
        stmt = select(DocExtractedObject).where(
            DocExtractedObject.file_bss_info_sno == file_id,
            DocExtractedObject.object_type == 'TABLE'
        ).order_by(DocExtractedObject.object_id.asc())
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return rows[:limit]


async def main():
    parser = argparse.ArgumentParser(description="Inspect table structures for a file")
    parser.add_argument('--file-id', type=int, required=True)
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()

    tables = await load_tables(args.file_id, args.limit)
    print(f"Loaded {len(tables)} table objects (showing up to {args.limit}).")
    for t in tables:
        sj = t.structure_json or {}
        rows = sj.get('rows_count') or sj.get('rows') or '??'
        cols = sj.get('cols_count') or sj.get('cols') or '??'
        content = sj.get('content') or []
        cells = sj.get('cells') or []
        header = content[0] if content else ''
        print(f"TABLE object_id={t.object_id} page={t.page_no} seq={t.sequence_in_page} rows={rows} cols={cols} header='{header[:80]}'")
        if cells:
            print(f"  first row cells: {cells[0]}")

if __name__ == '__main__':  # pragma: no cover
    import asyncio
    asyncio.run(main())

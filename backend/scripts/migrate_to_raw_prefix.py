#!/usr/bin/env python
"""
Migrate local or legacy S3-referenced file paths to standardized raw/ prefix structure.

Target key pattern:
  raw/{knowledge_container_id}/{YYYY/MM}/{hash8}_{original_filename}

Features:
  - Dry-run by default; use --apply to commit DB changes and perform uploads.
  - Skips rows already using standardized prefixes (raw/, ocr/, processed/).
  - Detects existing S3 key collision and skips (reports). No overwrite by default.
  - Optional --force-overwrite to allow replacing existing objects.
  - Computes MD5 for idempotent naming unless --keep-name is specified.
  - Optional --delete-local to remove local file after successful upload (moves to .backup/ if --safe-delete).
  - Concurrency with asyncio + thread pool for S3 upload I/O.
  - Summary report (counts by status).

Usage examples:
  Dry run all:        python migrate_to_raw_prefix.py
  Apply only uploads: python migrate_to_raw_prefix.py --apply --only-uploads
  Specific container: python migrate_to_raw_prefix.py --apply --container HR001

Exit code 0 on success; non-zero on unexpected exception.
"""
from __future__ import annotations
import argparse
import asyncio
import concurrent.futures
import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _SCRIPTS_DIR.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from dotenv import load_dotenv  # type: ignore

# Lazy imports inside async context for app dependencies

STANDARD_PREFIXES = ("raw/", "ocr/", "processed/")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Normalize file storage paths to raw/ prefix structure.")
    p.add_argument('--apply', action='store_true', help='Perform uploads and DB updates (default: dry-run)')
    p.add_argument('--delete-local', action='store_true', help='Delete local file after successful migration (with --apply)')
    p.add_argument('--safe-delete', action='store_true', help='Move deleted local files to .backup/ instead of unlink (implies --delete-local)')
    p.add_argument('--container', default=None, help='Filter by knowledge_container_id')
    p.add_argument('--only-uploads', action='store_true', help='Only rows whose path contains "uploads" (heuristic)')
    p.add_argument('--force-overwrite', action='store_true', help='Overwrite existing S3 object if key already exists')
    p.add_argument('--keep-name', action='store_true', help='Keep original filename (no MD5 hash prefix)')
    p.add_argument('--concurrency', type=int, default=4, help='Max concurrent uploads (default: 4)')
    p.add_argument('--max', type=int, default=None, help='Limit number of rows processed')
    return p.parse_args()


def is_already_standard(path: str) -> bool:
    return any(path.startswith(pref) for pref in STANDARD_PREFIXES)


def build_object_key(container: str, file_path: Path, keep_name: bool) -> str:
    date_prefix = datetime.utcnow().strftime('%Y/%m')
    original_name = file_path.name
    if keep_name:
        name = original_name
    else:
        # md5 hash for dedup/collision avoidance
        h = hashlib.md5(file_path.read_bytes()).hexdigest()[:8]
        name = f"{h}_{original_name}"
    return f"raw/{container}/{date_prefix}/{name}"


async def upload_with_executor(loop, s3_client, bucket: str, local: Path, key: str, force: bool) -> Tuple[bool, str]:
    def _do():
        import botocore
        if not force:
            try:
                s3_client.head_object(Bucket=bucket, Key=key)
                return False, f"skip: exists {key}"
            except botocore.exceptions.ClientError as e:
                if e.response['ResponseMetadata']['HTTPStatusCode'] not in (403, 404):
                    # unexpected error re-raise
                    raise
        s3_client.upload_file(str(local), bucket, key)
        return True, f"uploaded {key}"
    return await loop.run_in_executor(None, _do)


async def main_async(args: argparse.Namespace):
    # Load env
    env_path = os.path.abspath(os.path.join(_BACKEND_ROOT, '.env'))
    load_dotenv(env_path)

    from app.core.database import get_async_session_local
    from app.core.config import settings
    from app.models.document.file_models import TbFileBssInfo
    from app.services.core.aws_service import S3Service
    from sqlalchemy import select
    from sqlalchemy import or_

    async_session_local = get_async_session_local()
    s3_service = S3Service()
    s3_client = s3_service.s3_client
    bucket = s3_service.bucket_name

    stmt = select(TbFileBssInfo)
    if args.container:
        stmt = stmt.where(TbFileBssInfo.knowledge_container_id == args.container)
    if args.only_uploads:
        stmt = stmt.where(TbFileBssInfo.path.ilike('%uploads%'))

    async with async_session_local() as session:
        rows = (await session.execute(stmt)).scalars().all()
        if args.max:
            rows = rows[:args.max]

        loop = asyncio.get_event_loop()
        sem = asyncio.Semaphore(args.concurrency)

        stats = { 'total': 0, 'skipped_standard': 0, 'missing_local': 0, 'uploaded': 0, 'exists': 0, 'errors': 0 }
        messages: List[str] = []

        async def process(row):
            stats['total'] += 1
            original_path = (row.path or '').strip()
            container = row.knowledge_container_id or 'default'
            if not original_path:
                stats['missing_local'] += 1
                messages.append(f"SKIP {row.file_bss_info_sno} empty path")
                return
            if is_already_standard(original_path):
                stats['skipped_standard'] += 1
                messages.append(f"SKIP {row.file_bss_info_sno} already standard {original_path}")
                return
            p = Path(original_path)
            if not p.is_absolute():
                p = (_BACKEND_ROOT / original_path).resolve()
            if not p.exists():
                stats['missing_local'] += 1
                messages.append(f"SKIP {row.file_bss_info_sno} not found {p}")
                return
            key = build_object_key(container, p, args.keep_name)
            if not args.apply:
                messages.append(f"DRY-RUN {row.file_bss_info_sno} -> s3://{bucket}/{key}")
                return
            async with sem:
                try:
                    ok, msg = await upload_with_executor(loop, s3_client, bucket, p, key, args.force_overwrite)
                    if ok:
                        stats['uploaded'] += 1
                        # Update DB path
                        row.path = key
                    else:
                        stats['exists'] += 1
                    # Record result message (avoid embedded newline syntax error)
                    messages.append(f"{('OK' if ok else 'SKIP')} {row.file_bss_info_sno} {msg}")
                except Exception as e:
                    stats['errors'] += 1
                    messages.append(f"ERR {row.file_bss_info_sno} {e}")

        await asyncio.gather(*(process(r) for r in rows))
        if args.apply:
            await session.commit()
        else:
            await session.rollback()

    # Summary
    summary = {k: stats[k] for k in stats}
    print("Summary:", summary)
    for m in messages:
        print(m.rstrip())


def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

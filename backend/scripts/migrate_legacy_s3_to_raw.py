#!/usr/bin/env python
"""
Reorganize legacy S3 object keys (e.g., WJ_MS_SERVICE/, uploads/) into standardized raw/ prefix structure
and update DB records accordingly.

Process:
 1. Query DB rows whose path starts with any legacy prefix.
 2. For each row, HEAD the legacy key in S3; if exists, build new key:
      raw/{container}/{YYYY/MM}/{hash8}_{original_filename}
 3. CopyObject (no overwrite by default). If --force-overwrite, skip head on target.
 4. Update DB path to new key (on apply). Optionally delete legacy object after successful copy.
 5. Generate summary counts.

Features:
  - Dry-run default (no copy, no DB change)
  - --apply to perform copy + DB update
  - --delete-legacy to remove old key after copy (implies --apply)
  - --force-overwrite to overwrite if target exists
  - --keep-name to retain original filename (no hash prefix)
  - --prefixes to specify comma-separated legacy prefixes (default: WJ_MS_SERVICE,uploads)
  - --container-map optional JSON file mapping file_bss_info_sno -> container override
  - Concurrency control (--concurrency)
  - Limit rows (--max)

Exit codes: 0 success, non-zero fatal error.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import hashlib
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _SCRIPTS_DIR.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from dotenv import load_dotenv  # type: ignore

DEFAULT_PREFIXES = ["WJ_MS_SERVICE/", "uploads/"]
STANDARD_PREFIXES = ("raw/", "ocr/", "processed/")


def parse_args():
    p = argparse.ArgumentParser(description="Reorganize legacy S3 objects into raw/ structure.")
    p.add_argument('--apply', action='store_true', help='Execute copy + DB update (default: dry-run)')
    p.add_argument('--delete-legacy', action='store_true', help='Delete legacy object after successful copy (implies --apply)')
    p.add_argument('--force-overwrite', action='store_true', help='Overwrite if target already exists')
    p.add_argument('--keep-name', action='store_true', help='Keep original filename (no hash prefix)')
    p.add_argument('--prefixes', default=','.join(DEFAULT_PREFIXES), help='Comma-separated legacy prefixes')
    p.add_argument('--concurrency', type=int, default=5, help='Concurrent operations (default:5)')
    p.add_argument('--max', type=int, default=None, help='Process at most N rows')
    p.add_argument('--container-map', default=None, help='Optional JSON file mapping file_bss_info_sno -> container override')
    return p.parse_args()


def load_container_map(path: str | None) -> Dict[str, str]:
    if not path:
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # keys as string for uniform matching
    return {str(k): v for k, v in data.items()}


def build_new_key(container: str, filename: str, keep_name: bool, content_bytes: bytes | None = None) -> str:
    date_prefix = datetime.utcnow().strftime('%Y/%m')
    if keep_name:
        name = filename
    else:
        if content_bytes is None:
            # fallback to name hash only
            digest = hashlib.md5(filename.encode()).hexdigest()[:8]
        else:
            digest = hashlib.md5(content_bytes).hexdigest()[:8]
        name = f"{digest}_{filename}"
    return f"raw/{container}/{date_prefix}/{name}"


async def main_async(args):
    # Load env
    env_path = os.path.abspath(os.path.join(_BACKEND_ROOT, '.env'))
    load_dotenv(env_path)

    from sqlalchemy import select, or_
    from app.core.database import get_async_session_local
    from app.core.config import settings
    from app.models.document.file_models import TbFileBssInfo
    from app.services.core.aws_service import S3Service

    async_session_local = get_async_session_local()
    s3_service = S3Service()
    s3 = s3_service.s3_client
    bucket = s3_service.bucket_name

    legacy_prefixes = [p.strip() for p in args.prefixes.split(',') if p.strip()]

    # Build query: rows whose path starts with any legacy prefix
    conditions = []
    for pref in legacy_prefixes:
        conditions.append(TbFileBssInfo.path.ilike(f"{pref}%"))
    stmt = select(TbFileBssInfo).where(or_(*conditions))

    container_override = load_container_map(args.container_map)

    async with async_session_local() as session:
        rows = (await session.execute(stmt)).scalars().all()
        if args.max:
            rows = rows[:args.max]

        sem = asyncio.Semaphore(args.concurrency)
        loop = asyncio.get_event_loop()

        stats = { 'total': 0, 'copied': 0, 'skipped_exists': 0, 'skipped_standard': 0, 'missing_legacy': 0, 'errors': 0 }
        messages: List[str] = []

        async def process(row):
            stats['total'] += 1
            legacy_key = (row.path or '').strip()
            if not legacy_key:
                stats['missing_legacy'] += 1
                messages.append(f"SKIP {row.file_bss_info_sno} empty path")
                return
            if legacy_key.startswith(STANDARD_PREFIXES):
                stats['skipped_standard'] += 1
                messages.append(f"SKIP {row.file_bss_info_sno} already standard {legacy_key}")
                return
            # HEAD legacy
            try:
                head = s3.head_object(Bucket=bucket, Key=legacy_key)
            except Exception:
                stats['missing_legacy'] += 1
                messages.append(f"SKIP {row.file_bss_info_sno} not found {legacy_key}")
                return
            container = container_override.get(str(row.file_bss_info_sno), row.knowledge_container_id or 'default')
            filename = legacy_key.split('/')[-1]
            content_bytes = None
            if not args.keep_name and head.get('ContentLength', 0) <= 5_000_000:  # up to 5MB for hashing
                try:
                    obj = s3.get_object(Bucket=bucket, Key=legacy_key)
                    content_bytes = obj['Body'].read()
                except Exception:
                    pass
            new_key = build_new_key(container, filename, args.keep_name, content_bytes)

            # Collision check
            if not args.force_overwrite:
                try:
                    s3.head_object(Bucket=bucket, Key=new_key)
                    stats['skipped_exists'] += 1
                    messages.append(f"SKIP {row.file_bss_info_sno} target exists {new_key}")
                    return
                except Exception:
                    pass

            if not args.apply:
                messages.append(f"DRY-RUN {row.file_bss_info_sno} {legacy_key} -> {new_key}")
                return

            async with sem:
                def _copy_delete():
                    s3.copy_object(Bucket=bucket, CopySource={'Bucket': bucket, 'Key': legacy_key}, Key=new_key)
                    if args.delete_legacy:
                        s3.delete_object(Bucket=bucket, Key=legacy_key)
                try:
                    await loop.run_in_executor(None, _copy_delete)
                    row.path = new_key
                    stats['copied'] += 1
                    messages.append(f"OK {row.file_bss_info_sno} {legacy_key} -> {new_key}")
                except Exception as e:
                    stats['errors'] += 1
                    messages.append(f"ERR {row.file_bss_info_sno} {legacy_key} {e}")

        await asyncio.gather(*(process(r) for r in rows))
        if args.apply:
            await session.commit()
        else:
            await session.rollback()

    summary = {k: stats[k] for k in stats}
    print("Summary:", summary)
    for m in messages:
        print(m)


def main():
    args = parse_args()
    if args.delete_legacy:
        args.apply = True
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

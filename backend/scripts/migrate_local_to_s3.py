#!/usr/bin/env python
"""
Migrate locally-stored file records to S3 and update DB paths.

Behavior:
- Scans tb_file_bss_info where path looks like local file path (not containing '/') or containing 'uploads'.
- If local file exists, upload to S3 with key {knowledge_container_id}/{basename}.
- On success, update tb_file_bss_info.path to S3 object key.
- Optional --delete-local to remove local file after successful upload.
- Dry-run by default unless --apply is provided.
"""
import argparse
import asyncio
import os
from pathlib import Path
from typing import Optional, cast
import sys

# Ensure `app` package is importable when running from repo root
_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _SCRIPTS_DIR.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from dotenv import load_dotenv

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def is_local_path(p: str) -> bool:
    if not p:
        return False
    # heuristic: local paths usually contain directory separators and/or 'uploads'
    # S3 keys also have '/', but we treat keys not starting with '/' and existing in filesystem as local
    return True  # decide by existence below


async def migrate_one(session: AsyncSession, s3, row, settings, delete_local: bool, dry_run: bool) -> tuple[bool, str]:
    # Guard typing for SQLAlchemy-instrumented attribute
    original_path = cast(str, getattr(row, 'path', '') or '')
    container = row.knowledge_container_id or "default"
    # Resolve absolute path relative to backend root
    backend_root = Path(__file__).parent.parent
    abs_path = Path(original_path)
    if not abs_path.is_absolute():
        abs_path = (backend_root / original_path).resolve()

    if not abs_path.exists():
        return False, f"skip: local file not found: {abs_path}"

    basename = abs_path.name
    object_key = f"{container}/{basename}"

    if dry_run:
        return True, f"DRY-RUN would upload {abs_path} -> s3://{getattr(settings,'aws_s3_bucket','')}/{object_key} and update DB path"

    # Upload
    await s3.upload_file(file_path=str(abs_path), object_key=object_key)

    # Update DB path to object key
    setattr(row, 'path', object_key)
    await session.flush()

    # Optionally delete local
    if delete_local:
        try:
            os.remove(abs_path)
        except Exception:
            pass

    return True, f"migrated {basename} -> {object_key}"


async def main_async(args):
    # Load env for AWS creds
    scripts_dir = _SCRIPTS_DIR
    backend_root = _BACKEND_ROOT
    env_path = os.path.abspath(os.path.join(backend_root, '.env'))
    load_dotenv(env_path)

    # Import app modules AFTER dotenv so settings/env are populated
    from app.core.database import get_async_session_local
    from app.core.config import settings
    from app.models.document.file_models import TbFileBssInfo
    from app.services.core.aws_service import S3Service

    async_session_local = get_async_session_local()
    s3 = S3Service()

    async with async_session_local() as session:
        # Build query: candidates with local-looking paths
        stmt = select(TbFileBssInfo)
        if args.container:
            stmt = stmt.where(TbFileBssInfo.knowledge_container_id == args.container)
        if args.only_uploads:
            from sqlalchemy import or_
            stmt = stmt.where(TbFileBssInfo.path.ilike('%uploads%'))
        # selection is broad; we rely on local file existence check to decide migration

        result = await session.execute(stmt)
        rows = result.scalars().all()

        total = 0
        migrated = 0
        for row in rows:
            total += 1
            ok, msg = await migrate_one(session, s3, row, settings, args.delete_local, not args.apply)
            print(("OK" if ok else "SKIP"), row.file_bss_info_sno, msg)
        if args.apply:
            await session.commit()
        else:
            await session.rollback()

        print({
            'total_considered': total,
            'mode': 'apply' if args.apply else 'dry-run',
        })


def parse_args():
    p = argparse.ArgumentParser(description="Migrate locally referenced files in DB to S3.")
    p.add_argument('--apply', action='store_true', help='Actually perform uploads and DB updates (default: dry-run)')
    p.add_argument('--delete-local', action='store_true', help='Delete local file after successful upload (with --apply)')
    p.add_argument('--container', default=None, help='Filter by knowledge_container_id')
    p.add_argument('--only-uploads', action='store_true', help='Only consider rows whose path contains "uploads"')
    return p.parse_args()


def main():
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == '__main__':
    main()

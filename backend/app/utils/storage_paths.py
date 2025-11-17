import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import settings

SAFE_REPLACE = {':': '_', '\\': '_', '/': '_', '\n': '_'}

def _sanitize_filename(filename: str) -> str:
    # 최소한의 치환만 (경로 분리자/제어문자 제거)
    name = filename.strip().replace('\r', '')
    for k, v in SAFE_REPLACE.items():
        name = name.replace(k, v)
    if len(name) == 0:
        return 'file'
    return name

def build_raw_object_key(container_id: str, original_filename: str, local_path_for_hash: str) -> str:
    """raw/{container}/{YYYY}/{MM}/{hash8}_{sanitizedOriginal}
    - hash: 파일 내용 md5 8자리 (충돌 최소화)
    - 날짜: UTC 기준 (시간대 일관성)
    """
    try:
        h = hashlib.md5()
        with open(local_path_for_hash, 'rb') as f:
            # 대용량 안전: 스트리밍
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                if not chunk:
                    break
                h.update(chunk)
        digest8 = h.hexdigest()[:8]
    except Exception:
        # 실패 시 파일명 기반 해시 폴백
        digest8 = hashlib.md5(original_filename.encode('utf-8')).hexdigest()[:8]

    now = datetime.utcnow()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    safe_name = _sanitize_filename(original_filename)
    container_norm = container_id.strip('/').replace('..', '_') or 'default'
    return f"raw/{container_norm}/{year}/{month}/{digest8}_{safe_name}"


def looks_like_raw_scheme(key: str) -> bool:
    return key.startswith('raw/') and key.count('/') >= 4


def classify_key_scheme(key: str) -> str:
    if looks_like_raw_scheme(key):
        return 'raw'
    # 과거: <container>/<filename>
    parts = key.split('/')
    if len(parts) == 2:
        return 'legacy_flat'
    return 'other'

def build_intermediate_extraction_summary_key(container_id: str, file_id: int) -> str:
    container_norm = container_id.strip('/').replace('..', '_') or 'default'
    return f"intermediate/{container_norm}/{file_id}/extraction_summary.json"


def build_intermediate_page_key(container_id: str, file_id: int, page_no: int) -> str:
    container_norm = container_id.strip('/').replace('..', '_') or 'default'
    return f"intermediate/{container_norm}/{file_id}/pages/page_{page_no:04d}.json"


def build_derived_chunk_key(container_id: str, file_id: int, chunk_index: int) -> str:
    container_norm = container_id.strip('/').replace('..', '_') or 'default'
    return f"derived/{container_norm}/{file_id}/chunks/chunk_{chunk_index:05d}.json"


def build_derived_chunks_manifest_key(container_id: str, file_id: int) -> str:
    container_norm = container_id.strip('/').replace('..', '_') or 'default'
    return f"derived/{container_norm}/{file_id}/chunks/chunks_manifest.json"


__all__ = [
    'build_raw_object_key',
    'looks_like_raw_scheme',
    'classify_key_scheme',
    'build_intermediate_extraction_summary_key',
    'build_intermediate_page_key',
    'build_derived_chunk_key',
    'build_derived_chunks_manifest_key'
]

"""Inspect objects_manifest.json for a given file ID.

Usage:
  PYTHONPATH=./ python app/scripts/inspect_objects_manifest.py --file-id 123 --summary

Outputs:
  - Counts by object_type
  - Sample entries (first N)
  - Missing feature diagnostics for IMAGE objects (phash/size)
  - Integrity check versus extraction_metadata.json if present
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from typing import Any, Dict, List

try:
    from app.core.config import settings
    from app.services.core.azure_blob_service import get_azure_blob_service
except Exception as e:  # pragma: no cover
    print(f"❌ Import failed: {e}")
    sys.exit(2)


def load_json(azure, key: str, purpose: str) -> Any:
    try:
        txt = azure.download_text(key, purpose=purpose)
        return json.loads(txt)
    except Exception as e:  # pragma: no cover
        return None


def inspect(file_id: int, sample: int, show_summary: bool) -> int:
    if settings.storage_backend != 'azure_blob':
        print(f"⚠ STORAGE_BACKEND={settings.storage_backend} (expected azure_blob). Aborting.")
        return 2
    azure = get_azure_blob_service()

    prefix = f"multimodal/{file_id}/"
    inter = settings.azure_blob_container_intermediate
    manifest_key = prefix + 'objects_manifest.json'
    meta_key = prefix + 'extraction_metadata.json'

    manifest = load_json(azure, manifest_key, purpose='intermediate')
    if manifest is None:
        print(f"❌ objects_manifest.json not found for file {file_id}")
        return 3

    if not isinstance(manifest, list):
        print("❌ Manifest is not a list")
        return 4

    print(f"📄 objects_manifest.json entries={len(manifest)}")
    types = Counter([m.get('object_type') for m in manifest])
    print("Counts by type:")
    for t, c in types.items():
        print(f"  {t}: {c}")

    images = [m for m in manifest if m.get('object_type') == 'IMAGE']
    missing_phash = [m for m in images if not m.get('phash')]
    print(f"IMAGE objects: {len(images)} (missing phash={len(missing_phash)})")

    if images:
        sample_imgs = images[:min(sample, len(images))]
        print(f"Sample IMAGE entries (up to {sample}):")
        for im in sample_imgs:
            print(f"  idx={im.get('object_index')} page={im.get('page_no')} seq={im.get('sequence_in_page')} phash={im.get('phash')} size={im.get('width')}x{im.get('height')} has_binary={im.get('has_binary')} binary_key={im.get('binary_image_key')}")

    if show_summary:
        meta = load_json(azure, meta_key, purpose='intermediate') or {}
        em = meta.get('extraction_metadata') or {}
        expected = em.get('extracted_objects_count') or meta.get('extracted_objects_count')
        if expected is not None and expected != len(manifest):
            print(f"⚠ Object count mismatch: manifest={len(manifest)} meta={expected}")
        else:
            print("✅ Object count matches extraction metadata (if available)")

    # Basic integrity rules
    problems = []
    for m in images:
        if m.get('has_binary') and (not m.get('width') or not m.get('height')):
            problems.append(f"IMAGE idx={m.get('object_index')} has binary but missing dimensions")
    if problems:
        print("⚠ Detected potential issues:")
        for p in problems[:20]:
            print("  -", p)
    else:
        print("✅ No structural problems detected in IMAGE entries")

    print("\nInspection complete.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Inspect objects_manifest.json for a file")
    parser.add_argument('--file-id', type=int, required=True)
    parser.add_argument('--sample', type=int, default=5, help='Sample entries to show')
    parser.add_argument('--summary', action='store_true', help='Validate counts against extraction metadata')
    args = parser.parse_args()
    sys.exit(inspect(args.file_id, args.sample, args.summary))


if __name__ == '__main__':  # pragma: no cover
    main()

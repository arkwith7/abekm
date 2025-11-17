"""Blob Inspection Utility for Multimodal Pipeline Outputs

Usage:
  PYTHONPATH=./ /path/to/venv/bin/python app/scripts/blob_inspect_multimodal.py --file-id 1

Notes:
  - Run from backend directory or set PYTHONPATH to backend root.
  - STORAGE_BACKEND must be azure_blob.
"""
from __future__ import annotations
import argparse
import json
import sys
from typing import Optional

try:
    from app.core.config import settings
    from app.services.core.azure_blob_service import get_azure_blob_service
except Exception as e:  # pragma: no cover
    print(f"❌ Failed importing application modules: {e}")
    sys.exit(1)


def inspect(file_id: int, show_text_lines: int = 20) -> int:
    if settings.storage_backend != 'azure_blob':
        print(f"⚠ STORAGE_BACKEND={settings.storage_backend} (expected azure_blob). Aborting.")
        return 2

    try:
        azure = get_azure_blob_service()
    except Exception as e:
        print(f"❌ Azure init failed: {e}")
        return 3

    prefix = f"multimodal/{file_id}/"
    inter = settings.azure_blob_container_intermediate
    derived = settings.azure_blob_container_derived
    print(f"🔎 Inspecting file_bss_info_sno={file_id} (prefix={prefix})")

    inter_client = azure.client.get_container_client(inter)
    derived_client = azure.client.get_container_client(derived)

    # Intermediate container
    print(f"\n📦 Intermediate Container: {inter}")
    inter_blobs = [b for b in inter_client.list_blobs() if b.name.startswith(prefix)]
    if not inter_blobs:
        print("  (no blobs)")
    else:
        for b in inter_blobs:
            print(f"  - {b.name} ({b.size} bytes)")

        # Full text
        full_key = prefix + "extraction_full_text.txt"
        try:
            txt = azure.download_text(full_key, purpose='intermediate')
            lines = txt.splitlines()
            print(f"\n📝 Full Text: chars={len(txt)}, lines={len(lines)}")
            for i, line in enumerate(lines[:show_text_lines]):
                print(f"    {i+1:02d}: {line[:200]}")
            if len(lines) > show_text_lines:
                print(f"    ... ({len(lines)-show_text_lines} more lines)")
        except Exception as e:
            print(f"  ❌ full text not found: {e}")

        # Extraction metadata
        meta_key = prefix + 'extraction_metadata.json'
        try:
            meta_raw = azure.download_text(meta_key, purpose='intermediate')
            meta = json.loads(meta_raw)
            print("\n📋 extraction_metadata.json:")
            print("  extraction_session_id:", meta.get('extraction_session_id'))
            print("  objects_count:", meta.get('extracted_objects_count'))
            print("  pages_detected:", meta.get('pages_detected'))
            em = meta.get('extraction_metadata', {})
            if 'pages' in em:
                print("  page_entries:", len(em['pages']))
                if em['pages']:
                    snippet = (em['pages'][0].get('text', '') or '')[:180].replace('\n', ' ')
                    print("  first_page_snippet:", snippet)
        except Exception as e:
            print("  ❌ extraction metadata missing:", e)

    # Derived container
    print(f"\n📦 Derived Container: {derived}")
    der_blobs = [b for b in derived_client.list_blobs() if b.name.startswith(prefix)]
    if not der_blobs:
        print("  (no blobs)")
    else:
        for b in der_blobs:
            print(f"  - {b.name} ({b.size} bytes)")

        def _load_json(key: str):
            try:
                raw = azure.download_text(prefix + key, purpose='derived')
                return json.loads(raw or 'null')
            except Exception as e:  # pragma: no cover
                print(f"  ❌ {key} missing: {e}")
                return None

        chunk_meta = _load_json('chunking_metadata.json')
        if chunk_meta:
            print("\n🔗 chunking_metadata.json:")
            for f in ['chunk_session_id', 'strategy_name', 'chunk_count', 'params', 'timestamp']:
                if f in chunk_meta:
                    print(f"  {f}: {chunk_meta.get(f)}")

        manifest = _load_json('chunks_manifest.json')
        if manifest is not None:
            if isinstance(manifest, list):
                print(f"\n📄 chunks_manifest.json: entries={len(manifest)}")
                if manifest:
                    first = manifest[0]
                    if isinstance(first, dict):
                        print("  first keys:", list(first.keys()))
            else:
                print("  (manifest not a list)")

        emb_meta = _load_json('embedding_metadata.json')
        if emb_meta:
            print("\n🧬 embedding_metadata.json:")
            for f in ['model_name', 'vector_dimension', 'embeddings_generated', 'total_chunks', 'timestamp']:
                if f in emb_meta:
                    print(f"  {f}: {emb_meta.get(f)}")

    print("\n✅ Inspection complete.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Inspect Azure Blob outputs for a multimodal file ID")
    parser.add_argument('--file-id', type=int, required=True, help='file_bss_info_sno value')
    parser.add_argument('--lines', type=int, default=20, help='Preview lines of full text')
    args = parser.parse_args()
    sys.exit(inspect(args.file_id, args.lines))


if __name__ == '__main__':  # pragma: no cover
    main()

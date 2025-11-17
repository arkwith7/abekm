#!/usr/bin/env python
"""Re-embed Documents Script

기능:
  - 지정한 임베딩 모델명 기준으로 과거 문서를 재임베딩
  - 날짜 필터 / 특정 doc_ids / limit 옵션 지원 (초안)

사용 예시:
  python reembed_documents.py --model text-embedding-3-small --since 2024-01-01 --limit 500

미구현(TODO):
  - 실제 embedding provider 주입
  - session 기반 dual-write (기존 vs_doc_contents_chunks + doc_embedding)
  - 작업 진행률 출력 / 병렬 처리 최적화
"""
from __future__ import annotations
import asyncio
import argparse
import logging
from datetime import datetime
from typing import List, Optional

# from app.db.session import async_session
# from app.models.document.multimodal_models import DocChunk, DocEmbedding

logger = logging.getLogger("reembed")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

async def fetch_target_chunks(model: str, since: Optional[str], limit: Optional[int], doc_ids: Optional[List[str]]):
    """TODO: DB 조회 (기존 model != 주어진 model OR missing embedding)"""
    logger.info("Fetching target chunks (stub) ...")
    return []

async def embed_chunks(chunks, model: str):
    """TODO: 실제 임베딩 호출 및 doc_embedding upsert"""
    logger.info(f"Embedding {len(chunks)} chunks with model={model} (stub)")

async def main_async(args):
    target_chunks = await fetch_target_chunks(args.model, args.since, args.limit, args.doc_ids)
    if not target_chunks:
        logger.warning("No target chunks found (stub). Exiting.")
        return
    await embed_chunks(target_chunks, args.model)

def parse_args():
    parser = argparse.ArgumentParser(description="Re-embed existing document chunks")
    parser.add_argument('--model', required=True, help='Embedding model name')
    parser.add_argument('--since', help='ISO date (YYYY-MM-DD) after which documents updated')
    parser.add_argument('--limit', type=int, help='Max number of chunks to process')
    parser.add_argument('--doc-ids', nargs='*', help='Specific document IDs')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    asyncio.run(main_async(args))

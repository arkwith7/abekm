#!/usr/bin/env python
"""Reindex kor_search Script

기능:
  - kor_search 확장 기반 TSVECTOR (형태소/음절) 재생성
  - 파일 메타데이터 테이블(tb_document_search_index)이나 별도 컬럼 대상

주의:
  - 트랜잭션 단위로 batch 처리 권장
  - 대규모 데이터 시 VACUUM / REINDEX 고려

미구현(TODO):
  - 실제 kor_search 함수 호출 SQL
  - 진행률 / 병렬 처리
"""
from __future__ import annotations
import asyncio
import argparse
import logging

logger = logging.getLogger("reindex_kor_search")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

async def rebuild_vectors(limit: int | None):
    logger.info(f"Rebuilding kor_search tsvectors (limit={limit}) (stub)")
    # TODO: SELECT id, content FROM tb_document_search_index WHERE ...
    #       UPDATE tb_document_search_index SET kor_tsv = kor_build_vector(content)

async def main_async(args):
    await rebuild_vectors(args.limit)

def parse_args():
    parser = argparse.ArgumentParser(description="Reindex kor_search tsvectors")
    parser.add_argument('--limit', type=int, help='Limit number of rows (for testing)')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    asyncio.run(main_async(args))

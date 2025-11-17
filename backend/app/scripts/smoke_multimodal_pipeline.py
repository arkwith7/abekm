#!/usr/bin/env python
"""멀티모달 파이프라인 스모크 테스트

수행 내용:
 1. 지정한 DOCX / PPTX / PDF (존재하는 것만) 순차 처리
 2. 처리 후 IMAGE 객체의 phash / width / height 누락 여부 집계
 3. objects_manifest / chunking / embedding 기본 개수 확인
 4. 요약 리포트 출력

사용 예:
  python smoke_multimodal_pipeline.py \
    --file-ids 1 2 3 \
    --docx /path/to/file.docx \
    --pptx /path/to/file.pptx \
    --pdf  /path/to/file.pdf

(파일 경로를 생략하면 기본 업로드 디렉토리 내 존재 여부만 확인)
"""
from __future__ import annotations
import asyncio
import argparse
import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# 내부 경로 추가
BACKEND_ROOT = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_async_session_local
from app.core.config import settings
from app.models.document.multimodal_models import DocExtractedObject, DocChunk, DocEmbedding, DocExtractionSession, DocChunkSession
from app.services.document.multimodal_document_service import MultimodalDocumentService

try:
    from app.services.core.azure_blob_service import get_azure_blob_service
except ImportError:
    get_azure_blob_service = None

SERVICE = MultimodalDocumentService()

async def process_if_exists(session: AsyncSession, file_path: str, file_id: int, container_id: str = "SMOKE", user: str = "smoke") -> Optional[Dict[str, Any]]:
    if not file_path or not os.path.exists(file_path):
        print(f"[SKIP] 파일 없음: {file_path}")
        return None
    print(f"▶ 처리 시작: {os.path.basename(file_path)} (file_id={file_id})")
    result = await SERVICE.process_document_multimodal(
        file_path=file_path,
        file_bss_info_sno=file_id,
        container_id=container_id,
        user_emp_no=user,
        session=session
    )
    if not result.get("success"):
        print(f"  ✖ 실패: {result.get('error')}")
    else:
        print(f"  ✔ 성공: objects={result.get('objects_count')} chunks={result.get('chunks_count')} embeddings={result.get('embeddings_count')}")
    return result

async def summarize_images(session: AsyncSession, file_ids: List[int]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for fid in file_ids:
        stmt = select(
            func.count(),
            func.count(DocExtractedObject.phash),
            func.sum(func.case((DocExtractedObject.phash == None, 1), else_=0)),  # noqa: E711
            func.count(DocExtractedObject.image_width),
        ).where(
            DocExtractedObject.file_bss_info_sno == fid,
            DocExtractedObject.object_type == 'IMAGE'
        )
        res = await session.execute(stmt)
        total, phash_populated, phash_null, width_populated = res.first()
        data[fid] = {
            "image_total": int(total or 0),
            "phash_filled": int(phash_populated or 0),
            "phash_missing": int(phash_null or 0),
            "width_recorded": int(width_populated or 0)
        }
    return data

async def collect_basic_stats(session: AsyncSession, file_ids: List[int]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    for fid in file_ids:
        # chunks
        c_stmt = select(func.count()).select_from(DocChunk).where(DocChunk.file_bss_info_sno == fid)
        e_stmt = select(func.count()).select_from(DocEmbedding).where(DocEmbedding.file_bss_info_sno == fid)
        img_stmt = select(func.count()).select_from(DocExtractedObject).where(
            DocExtractedObject.file_bss_info_sno == fid,
            DocExtractedObject.object_type == 'IMAGE'
        )
        (chunks,), (embeddings,), (images,) = await asyncio.gather(
            session.execute(c_stmt), session.execute(e_stmt), session.execute(img_stmt)
        )
        stats[fid] = {
            "chunks": chunks.scalar() if hasattr(chunks, 'scalar') else chunks,
            "embeddings": embeddings.scalar() if hasattr(embeddings, 'scalar') else embeddings,
            "images": images.scalar() if hasattr(images, 'scalar') else images
        }
    return stats

async def main_async(args):
    async_session_local = get_async_session_local()
    async with async_session_local() as session:  # type: AsyncSession
        processed_file_ids: List[int] = []

        # 파일 경로 구성 (존재하면 처리)
        targets: List[tuple[str, int]] = []
        if args.docx and os.path.exists(args.docx):
            targets.append((args.docx, args.file_ids[0] if args.file_ids else 1001))
        if args.pptx and os.path.exists(args.pptx):
            targets.append((args.pptx, (args.file_ids[1] if len(args.file_ids) > 1 else (1002 if args.file_ids else 1002))))
        if args.pdf and os.path.exists(args.pdf):
            targets.append((args.pdf, (args.file_ids[2] if len(args.file_ids) > 2 else (1003 if args.file_ids else 1003))))

        for path, fid in targets:
            res = await process_if_exists(session, path, fid)
            if res and res.get("success"):
                processed_file_ids.append(fid)

        if not processed_file_ids:
            print("처리된 파일이 없습니다. (입력 경로 확인)\n")
            return

        # 이미지 특징 요약
        img_summary = await summarize_images(session, processed_file_ids)
        # 기본 통계
        basic_stats = await collect_basic_stats(session, processed_file_ids)

        print("\n====== 스모크 결과 요약 ======")
        for fid in processed_file_ids:
            is_img = img_summary.get(fid, {})
            st = basic_stats.get(fid, {})
            print(f"FileID {fid} -> chunks={st.get('chunks')} embeddings={st.get('embeddings')} images={st.get('images')} ")
            if is_img.get("image_total"):
                print(f"  IMAGE total={is_img['image_total']} phash_filled={is_img['phash_filled']} missing={is_img['phash_missing']}")

        # Optional: Azure Blob manifest 존재 여부 확인 (간단)
        if settings.storage_backend == 'azure_blob' and get_azure_blob_service:
            azure = get_azure_blob_service()
            print("\n(참고) Blob 업로드 여부는 개별 키 조회로 확장 가능")

        if args.json_output:
            out = {"images": img_summary, "stats": basic_stats, "processed_file_ids": processed_file_ids}
            with open(args.json_output, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"JSON 결과 저장: {args.json_output}")


def parse_args():
    p = argparse.ArgumentParser(description="멀티모달 파이프라인 스모크 테스트")
    p.add_argument("--docx", help="DOCX 파일 경로")
    p.add_argument("--pptx", help="PPTX 파일 경로")
    p.add_argument("--pdf", help="PDF 파일 경로")
    p.add_argument("--file-ids", nargs='*', type=int, default=[], help="파일 ID 리스트 (docx,pptx,pdf 순서 매핑)")
    p.add_argument("--json-output", help="JSON 요약 결과 저장 경로")
    return p.parse_args()

if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))

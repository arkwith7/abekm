"""이미지 바이너리 / pHash / 임베딩 백필 스크립트 (초기 버전)

사용 목적:
1) 과거 세션 중 IMAGE 객체가 있으나 binary PNG / manifest has_binary=false 인 경우 보강
2) pHash 및 placeholder vision embedding 생성 (향후 실제 비전 모델 교체 가능)

주의:
- 현재 멀티모달 모델 구조상 image embedding 저장 테이블 분리 미구현 → 후속 작업 필요
- 일단 manifest 보강 + (선택) 별도 JSON 아티팩트 저장
"""
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import async_session
from app.models.document.multimodal_models import DocExtractionSession, DocExtractedObject
from app.services.core.azure_blob_service import get_azure_blob_service
from app.services.document.vision.image_embedding_service import image_embedding_service

logger = logging.getLogger("backfill.image")


async def backfill_images(limit: int = 50, file_id: int | None = None):
    azure = get_azure_blob_service()
    updated = 0
    async with async_session() as session:  # type: AsyncSession
        # 후보 IMAGE 객체 쿼리 (간단히 최근순)
        stmt = select(DocExtractedObject).order_by(DocExtractedObject.object_id.desc())
        if file_id is not None:
            stmt = stmt.where(DocExtractedObject.file_bss_info_sno == file_id)
        stmt = stmt.where(DocExtractedObject.object_type == 'IMAGE').limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        logger.info(f"후보 IMAGE 객체 {len(rows)}개")

        for obj in rows:
            try:
                # 기존 PNG 존재 여부 확인 (경로 패턴 재구성)
                # NOTE: object index를 재현하기 어렵기 때문에 manifest 정합성 재구성은 후속 개선
                if not obj.page_no or not obj.bbox:
                    continue
                # 현재는 재크롭 구현 보류 (pipeline 재실행 권장)
                # Placeholder: 향후 page raster + crop 추가 가능
                logger.debug(f"이미지 백필 준비 object_id={obj.object_id} (페이지={obj.page_no})")
                # Skip if future: binary exists check
                # phash / embedding 생성은 PNG 필요 → 현재 파이프라인 생성 후 실행하는 것이 맞음
            except Exception as e:
                logger.warning(f"이미지 백필 오류 object_id={getattr(obj, 'object_id', None)}: {e}")
                continue
    logger.info(f"백필 완료 updated={updated}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--file-id', type=int, default=None)
    args = parser.parse_args()
    asyncio.run(backfill_images(limit=args.limit, file_id=args.file_id))


if __name__ == "__main__":
    main()

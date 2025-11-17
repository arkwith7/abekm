"""
Azure CLIP 벡터를 AWS Cohere Embed v4 멀티모달 벡터로 마이그레이션

사용법:
    python scripts/migrate_multimodal_to_aws.py --batch-size 5 --dry-run
    python scripts/migrate_multimodal_to_aws.py --batch-size 5  # 실제 실행
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session_local
from app.models.document.multimodal_models import DocEmbedding
from app.core.config import settings
import logging
import argparse
from typing import Dict
from datetime import datetime
import boto3
import json
import base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_multimodal_embeddings(
    session: AsyncSession,
    batch_size: int = 5,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    이미지 청크의 Azure CLIP → AWS Cohere Embed v4 마이그레이션
    """
    stats = {
        "total": 0,
        "migrated": 0,
        "skipped": 0,
        "failed": 0
    }
    
    # Azure CLIP 있지만 AWS 멀티모달 없는 이미지 청크 조회
    query = select(DocEmbedding).where(
        DocEmbedding.azure_clip_vector.isnot(None),
        DocEmbedding.aws_multimodal_vector_1024.is_(None),
        DocEmbedding.modality == 'image'
    ).limit(100)  # 안전장치
    
    result = await session.execute(query)
    embeddings = result.scalars().all()
    stats["total"] = len(embeddings)
    
    logger.info(f"🔍 마이그레이션 대상: {stats['total']}개 이미지 청크")
    
    if dry_run:
        logger.info("⚠️ DRY-RUN 모드: 실제 변경 없음")
        return stats
    
    # Bedrock 클라이언트 초기화
    bedrock = boto3.client(
        'bedrock-runtime',
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key
    )
    
    # 배치 처리
    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i:i+batch_size]
        logger.info(f"📦 배치 {i//batch_size + 1}/{(len(embeddings)-1)//batch_size + 1} 처리 중...")
        
        for emb in batch:
            try:
                # 청크 텍스트 조회 (이미지 설명)
                chunk_result = await session.execute(
                    text("SELECT content_text FROM doc_chunk WHERE chunk_id = :chunk_id"),
                    {"chunk_id": emb.chunk_id}
                )
                row = chunk_result.fetchone()
                content_text = row[0] if row else None
                
                if not content_text:
                    logger.warning(f"⚠️ 청크 {emb.chunk_id} 텍스트 없음 - 스킵")
                    stats["skipped"] += 1
                    continue
                
                # AWS Cohere Embed v4 멀티모달 임베딩 생성
                logger.info(f"🔄 청크 {emb.chunk_id} AWS Cohere v4 멀티모달 임베딩 생성 중...")
                
                # Cohere Embed v4 호출 (텍스트만 - 이미지는 별도 처리 필요)
                request_body = json.dumps({
                    "texts": [content_text],
                    "input_type": "search_document",
                    "embedding_types": ["float"]
                })
                
                response = bedrock.invoke_model(
                    modelId=settings.bedrock_multimodal_embedding_model_id,
                    body=request_body,
                    contentType="application/json",
                    accept="application/json"
                )
                
                response_body = json.loads(response['body'].read())
                aws_vector = response_body['embeddings']['float'][0]
                
                if len(aws_vector) != 1024:
                    logger.error(f"❌ 잘못된 차원: {len(aws_vector)} (예상: 1024)")
                    stats["failed"] += 1
                    continue
                
                # AWS 멀티모달 벡터 업데이트
                emb.aws_multimodal_vector_1024 = aws_vector
                
                stats["migrated"] += 1
                logger.info(f"✅ 청크 {emb.chunk_id} 마이그레이션 완료 ({stats['migrated']}/{stats['total']})")
                
            except Exception as e:
                logger.error(f"❌ 청크 {emb.chunk_id} 실패: {e}")
                stats["failed"] += 1
        
        # 배치 커밋
        await session.commit()
        logger.info(f"💾 배치 커밋 완료")
        
        # API 레이트 리밋 방지
        await asyncio.sleep(1)
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Azure CLIP → AWS Cohere v4 멀티모달 마이그레이션")
    parser.add_argument("--batch-size", type=int, default=5, help="배치 크기 (기본: 5)")
    parser.add_argument("--dry-run", action="store_true", help="테스트 실행 (변경 없음)")
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("🚀 AWS 멀티모달 임베딩 마이그레이션 시작 (Cohere Embed v4)")
    logger.info(f"📊 설정: batch_size={args.batch_size}, dry_run={args.dry_run}")
    logger.info(f"🔧 멀티모달 모델: {settings.bedrock_multimodal_embedding_model_id}")
    logger.info("="*80)
    
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        start_time = datetime.now()
        
        stats = await migrate_multimodal_embeddings(session, args.batch_size, args.dry_run)
        logger.info(f"✅ 마이그레이션 완료: {stats}")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n⏱️ 총 소요 시간: {elapsed:.1f}초")
    
    logger.info("="*80)
    logger.info("🎉 AWS 멀티모달 마이그레이션 완료!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())

"""
기존 Azure 임베딩을 AWS Bedrock으로 재생성하는 마이그레이션 스크립트

사용법:
    python scripts/migrate_embeddings_to_aws.py --batch-size 10 --dry-run
    python scripts/migrate_embeddings_to_aws.py --batch-size 10  # 실제 실행
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session_local
from app.models.document.multimodal_models import DocEmbedding
from app.models.document.vector_models import VsDocContentsChunks
from app.services.core.embedding_service import embedding_service
from app.core.config import settings
import logging
import argparse
from typing import List, Dict, Any
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_doc_embeddings(
    session: AsyncSession,
    batch_size: int = 10,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    doc_embedding 테이블의 Azure 임베딩을 AWS로 마이그레이션
    
    Args:
        session: 데이터베이스 세션
        batch_size: 배치 크기
        dry_run: 테스트 실행 여부
    
    Returns:
        마이그레이션 통계
    """
    stats = {
        "total": 0,
        "migrated": 0,
        "skipped": 0,
        "failed": 0
    }
    
    # Azure 임베딩만 조회 (AWS 임베딩이 없는 것들)
    query = select(DocEmbedding).where(
        DocEmbedding.provider == 'azure',
        DocEmbedding.azure_vector_1536.isnot(None),
        DocEmbedding.aws_vector_1024.is_(None)
    ).limit(1000)  # 안전장치
    
    result = await session.execute(query)
    embeddings = result.scalars().all()
    stats["total"] = len(embeddings)
    
    logger.info(f"🔍 마이그레이션 대상: {stats['total']}개")
    
    if dry_run:
        logger.info("⚠️ DRY-RUN 모드: 실제 변경 없음")
        return stats
    
    # 배치 처리
    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i:i+batch_size]
        logger.info(f"📦 배치 {i//batch_size + 1}/{(len(embeddings)-1)//batch_size + 1} 처리 중...")
        
        for emb in batch:
            try:
                # 청크 텍스트 조회 (doc_chunk 테이블에서)
                try:
                    from app.models.document.multimodal_models import DocChunk
                except ImportError:
                    # 폴백: SQL로 직접 조회
                    chunk_result = await session.execute(
                        text("SELECT content_text FROM doc_chunk WHERE chunk_id = :chunk_id"),
                        {"chunk_id": emb.chunk_id}
                    )
                    row = chunk_result.fetchone()
                    content_text = row[0] if row else None
                else:
                    chunk_result = await session.execute(
                        select(DocChunk).where(DocChunk.chunk_id == emb.chunk_id)
                    )
                    chunk = chunk_result.scalar_one_or_none()
                    content_text = chunk.content_text if chunk else None
                
                if not content_text:
                    logger.warning(f"⚠️ 청크 {emb.chunk_id} 텍스트 없음 - 스킵")
                    stats["skipped"] += 1
                    continue
                
                # AWS Bedrock 임베딩 생성 (강제로 Bedrock 사용)
                logger.info(f"🔄 청크 {emb.chunk_id} AWS 임베딩 생성 중...")
                # 임시로 provider를 bedrock으로 변경하여 AWS 임베딩 보장
                original_provider = embedding_service.default_provider
                embedding_service.default_provider = 'bedrock'
                aws_vector = await embedding_service.get_embedding(content_text)
                embedding_service.default_provider = original_provider
                
                if len(aws_vector) != 1024:
                    logger.error(f"❌ 잘못된 차원: {len(aws_vector)} (예상: 1024)")
                    stats["failed"] += 1
                    continue
                
                # AWS 벡터 업데이트
                emb.aws_vector_1024 = aws_vector
                emb.provider = 'aws'  # 또는 'hybrid'로 설정
                
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


async def migrate_vs_chunks(
    session: AsyncSession,
    batch_size: int = 10,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    vs_doc_contents_chunks 테이블의 Azure 임베딩을 AWS로 마이그레이션
    """
    stats = {
        "total": 0,
        "migrated": 0,
        "skipped": 0,
        "failed": 0
    }
    
    # Azure 임베딩만 조회
    query = select(VsDocContentsChunks).where(
        VsDocContentsChunks.embedding_provider == 'azure',
        VsDocContentsChunks.azure_embedding_1536.isnot(None),
        VsDocContentsChunks.aws_embedding_1024.is_(None)
    ).limit(1000)
    
    result = await session.execute(query)
    chunks = result.scalars().all()
    stats["total"] = len(chunks)
    
    logger.info(f"🔍 vs_chunks 마이그레이션 대상: {stats['total']}개")
    
    if dry_run:
        return stats
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        logger.info(f"📦 배치 {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1} 처리 중...")
        
        for chunk in batch:
            try:
                if not chunk.chunk_text:
                    stats["skipped"] += 1
                    continue
                
                # AWS 임베딩 생성 (강제로 Bedrock 사용)
                original_provider = embedding_service.default_provider
                embedding_service.default_provider = 'bedrock'
                aws_vector = await embedding_service.get_embedding(chunk.chunk_text)
                embedding_service.default_provider = original_provider
                
                if len(aws_vector) != 1024:
                    logger.error(f"❌ 잘못된 차원: {len(aws_vector)}")
                    stats["failed"] += 1
                    continue
                
                # 업데이트
                chunk.aws_embedding_1024 = aws_vector
                chunk.embedding_provider = 'aws'
                
                stats["migrated"] += 1
                logger.info(f"✅ vs_chunk {chunk.chunk_sno} 완료 ({stats['migrated']}/{stats['total']})")
                
            except Exception as e:
                logger.error(f"❌ 실패: {e}")
                stats["failed"] += 1
        
        await session.commit()
        await asyncio.sleep(1)
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Azure → AWS 임베딩 마이그레이션")
    parser.add_argument("--batch-size", type=int, default=10, help="배치 크기 (기본: 10)")
    parser.add_argument("--dry-run", action="store_true", help="테스트 실행 (변경 없음)")
    parser.add_argument("--table", choices=["doc_embedding", "vs_chunks", "all"], 
                        default="all", help="마이그레이션 대상 테이블")
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("🚀 AWS 임베딩 마이그레이션 시작")
    logger.info(f"📊 설정: batch_size={args.batch_size}, dry_run={args.dry_run}, table={args.table}")
    logger.info(f"🔧 임베딩 프로바이더: {settings.default_embedding_provider}")
    logger.info(f"📐 벡터 차원: {settings.vector_dimension}")
    logger.info("="*80)
    
    # 임베딩 프로바이더 확인
    if settings.default_embedding_provider != 'bedrock':
        logger.error("❌ DEFAULT_EMBEDDING_PROVIDER를 'bedrock'으로 설정해주세요!")
        return
    
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        start_time = datetime.now()
        
        # doc_embedding 마이그레이션
        if args.table in ["doc_embedding", "all"]:
            logger.info("\n📄 doc_embedding 테이블 마이그레이션 시작...")
            doc_stats = await migrate_doc_embeddings(session, args.batch_size, args.dry_run)
            logger.info(f"✅ doc_embedding 완료: {doc_stats}")
        
        # vs_doc_contents_chunks 마이그레이션
        if args.table in ["vs_chunks", "all"]:
            logger.info("\n📄 vs_doc_contents_chunks 테이블 마이그레이션 시작...")
            vs_stats = await migrate_vs_chunks(session, args.batch_size, args.dry_run)
            logger.info(f"✅ vs_chunks 완료: {vs_stats}")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n⏱️ 총 소요 시간: {elapsed:.1f}초")
    
    logger.info("="*80)
    logger.info("🎉 마이그레이션 완료!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())

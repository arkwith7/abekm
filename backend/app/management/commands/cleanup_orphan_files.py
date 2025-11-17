"""
Orphan 파일 정리 명령어

DB에는 없으나 Azure Blob Storage에 남아있는 파일을 정리합니다.
실행 방법: python -m app.management.commands.cleanup_orphan_files [--dry-run] [--purpose raw|intermediate|derived]
"""
import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import Set, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session_local
from app.models import TbFileBssInfo
from app.services.core.azure_blob_service import get_azure_blob_service
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_db_file_paths(session: AsyncSession, purpose: str = 'raw') -> Set[str]:
    """
    DB에 저장된 파일 경로 목록 조회
    
    Args:
        session: DB 세션
        purpose: Azure Blob purpose (raw/intermediate/derived)
    
    Returns:
        DB에 존재하는 파일 경로 집합
    """
    logger.info(f"📊 DB 파일 경로 조회 시작 (purpose={purpose})...")
    
    # 삭제되지 않은 파일만 조회
    query = select(TbFileBssInfo.path).where(TbFileBssInfo.del_yn != 'Y')
    result = await session.execute(query)
    all_paths = result.scalars().all()
    
    # purpose prefix와 일치하는 경로만 필터링
    purpose_prefix = f"{purpose}/"
    db_file_paths = set()
    
    for path in all_paths:
        if not path:
            continue
        # 절대 경로는 제외 (로컬 파일)
        if path.startswith('/'):
            continue
        # purpose prefix로 시작하는 경로
        if path.startswith(purpose_prefix):
            # prefix 제거 후 blob_path만 저장
            blob_path = path[len(purpose_prefix):]
            db_file_paths.add(blob_path)
        # prefix 없는 레거시 경로 (기본 raw로 간주)
        elif purpose == 'raw' and '/' in path and not path.startswith(('intermediate/', 'derived/')):
            db_file_paths.add(path)
    
    logger.info(f"✅ DB에서 {len(db_file_paths)}개 파일 경로 발견 (purpose={purpose})")
    return db_file_paths


def get_blob_file_paths(purpose: str = 'raw') -> Set[str]:
    """
    Azure Blob Storage의 파일 목록 조회
    
    Args:
        purpose: Azure Blob purpose (raw/intermediate/derived)
    
    Returns:
        Blob Storage에 존재하는 파일 경로 집합
    """
    logger.info(f"☁️ Azure Blob 파일 목록 조회 시작 (purpose={purpose})...")
    
    azure_blob = get_azure_blob_service()
    blob_paths = azure_blob.list_blobs(purpose=purpose)
    
    logger.info(f"✅ Azure Blob에서 {len(blob_paths)}개 파일 발견 (purpose={purpose})")
    return set(blob_paths)


async def find_orphan_files(
    session: AsyncSession,
    purpose: str = 'raw',
    min_age_hours: int = 24
) -> List[str]:
    """
    Orphan 파일 찾기 (Blob에는 있지만 DB에 없는 파일)
    
    Args:
        session: DB 세션
        purpose: Azure Blob purpose
        min_age_hours: 최소 파일 생성 후 경과 시간 (시간)
    
    Returns:
        Orphan 파일 경로 리스트
    """
    logger.info(f"🔍 Orphan 파일 검색 시작 (purpose={purpose}, min_age={min_age_hours}h)...")
    
    db_paths = await get_db_file_paths(session, purpose)
    blob_paths = get_blob_file_paths(purpose)
    
    # Blob에는 있지만 DB에 없는 파일
    orphan_candidates = blob_paths - db_paths
    
    if not orphan_candidates:
        logger.info("✅ Orphan 파일 없음")
        return []
    
    logger.info(f"🔎 {len(orphan_candidates)}개 Orphan 후보 발견, 생성 시간 확인 중...")
    
    # 파일 생성 시간 확인 (최소 경과 시간 체크)
    azure_blob = get_azure_blob_service()
    min_creation_time = datetime.now() - timedelta(hours=min_age_hours)
    orphan_files = []
    
    for blob_path in orphan_candidates:
        try:
            # Blob 메타데이터 조회
            blob_client = azure_blob._get_blob_client(blob_path, purpose)
            properties = blob_client.get_blob_properties()
            
            # 생성 시간이 min_age_hours 이상 경과한 파일만 orphan으로 판정
            if properties.creation_time and properties.creation_time < min_creation_time:
                orphan_files.append(blob_path)
                logger.info(
                    f"  🗑️ Orphan: {blob_path} "
                    f"(생성: {properties.creation_time.strftime('%Y-%m-%d %H:%M:%S')})"
                )
        except Exception as e:
            logger.warning(f"  ⚠️ 메타데이터 조회 실패: {blob_path}, {e}")
            # 메타데이터 조회 실패 시 안전하게 제외
            continue
    
    logger.info(f"✅ {len(orphan_files)}개 Orphan 파일 확인 완료")
    return orphan_files


async def cleanup_orphan_files_async(
    purpose: str = 'raw',
    min_age_hours: int = 24,
    dry_run: bool = True,
    max_files: int = 100
):
    """
    Orphan 파일 정리 실행
    
    Args:
        purpose: Azure Blob purpose
        min_age_hours: 최소 파일 생성 후 경과 시간
        dry_run: True이면 삭제하지 않고 로그만 출력
        max_files: 한 번에 정리할 최대 파일 개수
    """
    logger.info("=" * 80)
    logger.info("🧹 Orphan 파일 정리 시작")
    logger.info(f"  - Purpose: {purpose}")
    logger.info(f"  - Min Age: {min_age_hours}h")
    logger.info(f"  - Dry Run: {dry_run}")
    logger.info(f"  - Max Files: {max_files}")
    logger.info("=" * 80)
    
    # DB 세션 생성
    async_session_factory = get_async_session_local()
    async with async_session_factory() as session:
        # Orphan 파일 찾기
        orphan_files = await find_orphan_files(session, purpose, min_age_hours)
        
        if not orphan_files:
            logger.info("✅ 정리할 Orphan 파일이 없습니다.")
            return
        
        # 최대 개수 제한
        if len(orphan_files) > max_files:
            logger.warning(
                f"⚠️ Orphan 파일이 {len(orphan_files)}개로 max_files({max_files})를 초과합니다. "
                f"처음 {max_files}개만 처리합니다."
            )
            orphan_files = orphan_files[:max_files]
        
        if dry_run:
            logger.info(f"🔍 [DRY RUN] {len(orphan_files)}개 파일을 삭제할 예정입니다:")
            for blob_path in orphan_files:
                logger.info(f"  - {purpose}/{blob_path}")
            logger.info("🔍 [DRY RUN] 실제 삭제하려면 --no-dry-run 옵션을 사용하세요.")
        else:
            logger.info(f"🗑️ {len(orphan_files)}개 Orphan 파일 삭제 시작...")
            azure_blob = get_azure_blob_service()
            deleted_count = 0
            failed_count = 0
            
            for blob_path in orphan_files:
                try:
                    if azure_blob.delete_blob(blob_path, purpose=purpose):
                        deleted_count += 1
                        logger.info(f"  ✅ 삭제 완료: {purpose}/{blob_path}")
                    else:
                        failed_count += 1
                        logger.warning(f"  ⚠️ 삭제 실패: {purpose}/{blob_path}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ❌ 삭제 예외: {purpose}/{blob_path}, {e}")
            
            logger.info("=" * 80)
            logger.info(f"🎉 Orphan 파일 정리 완료")
            logger.info(f"  - 삭제 성공: {deleted_count}개")
            logger.info(f"  - 삭제 실패: {failed_count}개")
            logger.info("=" * 80)


def main():
    """명령줄 인터페이스"""
    parser = argparse.ArgumentParser(
        description='Azure Blob Storage Orphan 파일 정리',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # Dry run (삭제하지 않고 로그만 출력)
  python -m app.management.commands.cleanup_orphan_files --purpose raw --dry-run
  
  # 실제 삭제 실행
  python -m app.management.commands.cleanup_orphan_files --purpose raw --no-dry-run --min-age 48
  
  # Intermediate 파일 정리
  python -m app.management.commands.cleanup_orphan_files --purpose intermediate --no-dry-run
        """
    )
    
    parser.add_argument(
        '--purpose',
        type=str,
        choices=['raw', 'intermediate', 'derived'],
        default='raw',
        help='Azure Blob purpose (default: raw)'
    )
    
    parser.add_argument(
        '--min-age',
        type=int,
        default=24,
        help='최소 파일 생성 후 경과 시간(시간) (default: 24)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='삭제하지 않고 로그만 출력 (default: True)'
    )
    
    parser.add_argument(
        '--no-dry-run',
        action='store_false',
        dest='dry_run',
        help='실제로 파일 삭제'
    )
    
    parser.add_argument(
        '--max-files',
        type=int,
        default=100,
        help='한 번에 정리할 최대 파일 개수 (default: 100)'
    )
    
    args = parser.parse_args()
    
    # 실행
    asyncio.run(cleanup_orphan_files_async(
        purpose=args.purpose,
        min_age_hours=args.min_age,
        dry_run=args.dry_run,
        max_files=args.max_files
    ))


if __name__ == '__main__':
    main()

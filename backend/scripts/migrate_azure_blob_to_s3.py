"""
Azure Blob Storage → AWS S3 파일 마이그레이션 스크립트

목적:
- Azure Blob Storage의 모든 컨테이너(raw, intermediate, derived)를 S3로 복사
- 데이터베이스 파일 경로는 그대로 유지 (동일한 prefix 구조)
- 멀티모달 객체 이미지 포함 전체 마이그레이션

사용법:
    python scripts/migrate_azure_blob_to_s3.py --dry-run  # 테스트 실행
    python scripts/migrate_azure_blob_to_s3.py            # 실제 마이그레이션
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple
import logging

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
import boto3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    logger.error("❌ azure-storage-blob 미설치. pip install azure-storage-blob 필요")
    sys.exit(1)


class AzureToS3Migrator:
    """Azure Blob → S3 마이그레이션"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        
        # Azure Blob 클라이언트
        self.azure_conn_str = settings.azure_blob_connection_string or os.getenv("AZURE_BLOB_CONNECTION_STRING")
        if not self.azure_conn_str:
            account_name = settings.azure_blob_account_name
            account_key = settings.azure_blob_account_key
            if not account_name or not account_key:
                raise RuntimeError("Azure Blob 인증 정보 없음 (connection string or account name/key)")
            self.azure_conn_str = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
        
        self.azure_client = BlobServiceClient.from_connection_string(self.azure_conn_str)
        
        # S3 클라이언트
        self.s3_client = boto3.client(
            's3',
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        self.s3_bucket = settings.aws_s3_bucket
        
        # 컨테이너 매핑 (Azure container → S3 prefix)
        self.container_map = {
            settings.azure_blob_container_raw: "",  # S3는 버킷 루트에 바로 저장
            settings.azure_blob_container_intermediate: "",
            settings.azure_blob_container_derived: ""
        }
        
        logger.info(f"📦 Azure 계정: {settings.azure_blob_account_name}")
        logger.info(f"📦 S3 버킷: {self.s3_bucket}")
        logger.info(f"🌍 S3 리전: {settings.aws_region}")
        if dry_run:
            logger.info("⚠️ DRY-RUN 모드 활성화")
    
    def list_azure_blobs(self, container_name: str) -> List[Tuple[str, int]]:
        """Azure 컨테이너의 모든 Blob 목록 조회"""
        try:
            container_client = self.azure_client.get_container_client(container_name)
            blobs = []
            
            for blob in container_client.list_blobs():
                blobs.append((blob.name, blob.size))
            
            logger.info(f"✅ Azure 컨테이너 '{container_name}': {len(blobs)}개 파일")
            return blobs
            
        except Exception as e:
            logger.error(f"❌ Azure 컨테이너 '{container_name}' 조회 실패: {e}")
            return []
    
    def copy_blob_to_s3(self, azure_container: str, blob_name: str, blob_size: int) -> bool:
        """단일 Blob을 S3로 복사"""
        try:
            # Azure에서 다운로드
            blob_client = self.azure_client.get_blob_client(
                container=azure_container,
                blob=blob_name
            )
            
            if self.dry_run:
                logger.info(f"[DRY-RUN] {azure_container}/{blob_name} → s3://{self.s3_bucket}/{blob_name} ({blob_size:,} bytes)")
                return True
            
            # 스트리밍으로 다운로드 (메모리 효율)
            blob_data = blob_client.download_blob()
            file_bytes = blob_data.readall()
            
            # S3에 업로드 (동일한 키 사용)
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=blob_name,
                Body=file_bytes
            )
            
            logger.info(f"✅ {blob_name} ({blob_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"❌ {blob_name} 복사 실패: {e}")
            return False
    
    async def migrate_container(self, container_name: str) -> Dict[str, int]:
        """컨테이너 전체 마이그레이션"""
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "total_bytes": 0
        }
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📦 컨테이너 마이그레이션 시작: {container_name}")
        logger.info(f"{'='*80}")
        
        # Azure Blob 목록 조회
        blobs = self.list_azure_blobs(container_name)
        stats["total"] = len(blobs)
        
        if not blobs:
            logger.warning(f"⚠️ 컨테이너 '{container_name}'에 파일 없음")
            return stats
        
        # 배치 처리
        batch_size = 10
        for i in range(0, len(blobs), batch_size):
            batch = blobs[i:i+batch_size]
            
            for blob_name, blob_size in batch:
                stats["total_bytes"] += blob_size
                
                if self.copy_blob_to_s3(container_name, blob_name, blob_size):
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            
            # API 레이트 리밋 방지
            if not self.dry_run:
                await asyncio.sleep(0.5)
        
        logger.info(f"\n✅ 컨테이너 '{container_name}' 완료: {stats['success']}/{stats['total']} 성공")
        return stats
    
    async def migrate_all(self) -> Dict[str, Dict[str, int]]:
        """모든 컨테이너 마이그레이션"""
        logger.info("\n" + "="*80)
        logger.info("🚀 Azure Blob → S3 마이그레이션 시작")
        logger.info("="*80)
        
        results = {}
        
        for container_name in self.container_map.keys():
            stats = await self.migrate_container(container_name)
            results[container_name] = stats
        
        # 전체 통계
        total_files = sum(s["total"] for s in results.values())
        total_success = sum(s["success"] for s in results.values())
        total_failed = sum(s["failed"] for s in results.values())
        total_bytes = sum(s["total_bytes"] for s in results.values())
        
        logger.info("\n" + "="*80)
        logger.info("🎉 마이그레이션 완료")
        logger.info("="*80)
        logger.info(f"📊 전체 파일: {total_files}개")
        logger.info(f"✅ 성공: {total_success}개")
        logger.info(f"❌ 실패: {total_failed}개")
        logger.info(f"💾 전송량: {total_bytes / (1024**2):.2f} MB")
        logger.info("="*80)
        
        return results


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Azure Blob → S3 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="테스트 실행 (실제 복사 없음)")
    
    args = parser.parse_args()
    
    migrator = AzureToS3Migrator(dry_run=args.dry_run)
    results = await migrator.migrate_all()
    
    # 실패한 파일 있으면 종료 코드 1
    total_failed = sum(s["failed"] for s in results.values())
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())

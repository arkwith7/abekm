"""
System Data Seeder

시스템 기본 데이터(공통 코드, 카테고리 등)에 대한 시드 데이터를 로드합니다.
CSV 파일: common_codes.csv, categories.csv
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.models.core.system_models import TbCmnsCdGrpItem, TbKnowledgeCategories
from app.core.database import get_async_session_local
from data.seeds.base_seeder import BaseSeeder
import logging

logger = logging.getLogger(__name__)


class SystemSeeder(BaseSeeder):
    """시스템 데이터 시더"""
    
    async def seed_common_codes(self, clear_existing: bool = False) -> bool:
        """공통 코드를 시드합니다."""
        return await self.run_seed(
            csv_filename="common_codes.csv",
            model=TbCmnsCdGrpItem,
            key_fields=["grp_cd", "item_cd"],
            required_fields=["grp_cd", "item_cd", "item_nm"],
            clear_existing=clear_existing
        )
    
    async def seed_categories(self, clear_existing: bool = False) -> bool:
        """지식 카테고리를 시드합니다."""
        return await self.run_seed(
            csv_filename="categories.csv",
            model=TbKnowledgeCategories,
            key_fields=["category_id"],
            required_fields=["category_id", "category_name"],
            clear_existing=clear_existing
        )
    
    async def seed_all(self, clear_existing: bool = False) -> bool:
        """모든 시스템 데이터를 시드합니다."""
        try:
            logger.info("🌱 시스템 데이터 시드 시작...")
            
            # 1. 공통 코드 시드
            if not await self.seed_common_codes(clear_existing):
                return False
            
            # 2. 카테고리 시드
            if not await self.seed_categories(clear_existing):
                return False
            
            logger.info("🎉 모든 시스템 데이터 시드 완료!")
            return True
            
        except Exception as e:
            logger.error(f"❌ 시스템 데이터 시드 실패: {e}")
            return False


async def main():
    """단독 실행용 메인 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async_session = get_async_session_local()
    
    async with async_session() as session:
        try:
            seeder = SystemSeeder(session)
            success = await seeder.seed_all(clear_existing=True)
            
            if success:
                logger.info("🎉 시스템 시드 데이터 로딩 완료!")
            else:
                logger.error("❌ 시스템 시드 데이터 로딩 실패!")
                
        except Exception as e:
            logger.error(f"❌ 시드 실행 중 오류 발생: {e}")
            await session.rollback()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
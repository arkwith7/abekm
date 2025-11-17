"""
User Data Seeder

사용자 테이블(tb_user)에 대한 시드 데이터를 로드합니다.
CSV 파일: users.csv
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.models.auth.user_models import User
from app.core.database import get_async_session_local
from .base_seeder import BaseSeeder
import logging

logger = logging.getLogger(__name__)


class UserSeeder(BaseSeeder):
    """사용자 데이터 시더"""
    
    async def seed_users(self, clear_existing: bool = False) -> bool:
        """사용자 데이터를 시드합니다."""
        return await self.run_seed(
            csv_filename="users.csv",
            model=User,
            key_fields=["emp_no"],
            required_fields=["emp_no", "username", "email"],
            clear_existing=clear_existing
        )


async def main():
    """단독 실행용 메인 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async_session = get_async_session_local()
    
    async with async_session() as session:
        try:
            seeder = UserSeeder(session)
            success = await seeder.seed_users(clear_existing=True)
            
            if success:
                logger.info("🎉 사용자 시드 데이터 로딩 완료!")
            else:
                logger.error("❌ 사용자 시드 데이터 로딩 실패!")
                
        except Exception as e:
            logger.error(f"❌ 시드 실행 중 오류 발생: {e}")
            await session.rollback()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
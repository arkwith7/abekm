"""
Permission Seeder

사용자 권한 관련 테이블들에 대한 시드 데이터를 로드합니다.
CSV 파일: user_permissions.csv, user_roles.csv
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.models.auth.permission_models import TbUserPermissions, TbUserRoles
from app.core.database import get_async_session_local
from .base_seeder import BaseSeeder
import logging

logger = logging.getLogger(__name__)


class PermissionSeeder(BaseSeeder):
    """권한 데이터 시더"""
    
    async def seed_user_roles(self, clear_existing: bool = False) -> bool:
        """사용자 역할을 시드합니다."""
        return await self.run_seed(
            csv_filename="user_roles.csv",
            model=TbUserRoles,
            key_fields=["user_emp_no", "role_name", "scope_type", "scope_value"],
            required_fields=["user_emp_no", "role_name", "role_level"],
            clear_existing=clear_existing
        )
    
    async def seed_user_permissions(self, clear_existing: bool = False) -> bool:
        """사용자 권한을 시드합니다."""
        return await self.run_seed(
            csv_filename="user_permissions.csv",
            model=TbUserPermissions,
            key_fields=["user_emp_no", "container_id"],
            required_fields=["user_emp_no", "container_id", "role_id", "permission_type"],
            clear_existing=clear_existing
        )
    
    async def seed_all(self, clear_existing: bool = False) -> bool:
        """모든 권한 데이터를 시드합니다."""
        try:
            logger.info("🔐 권한 데이터 시드 시작...")
            
            # 1. 사용자 역할 시드 (먼저 실행)
            if not await self.seed_user_roles(clear_existing):
                return False
            
            # 2. 사용자 권한 시드
            if not await self.seed_user_permissions(clear_existing):
                return False
            
            logger.info("🎉 모든 권한 데이터 시드 완료!")
            return True
            
        except Exception as e:
            logger.error(f"❌ 권한 데이터 시드 실패: {e}")
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
            seeder = PermissionSeeder(session)
            success = await seeder.seed_all(clear_existing=True)
            
            if success:
                logger.info("🎉 권한 시드 데이터 로딩 완료!")
            else:
                logger.error("❌ 권한 시드 데이터 로딩 실패!")
                
        except Exception as e:
            logger.error(f"❌ 시드 실행 중 오류 발생: {e}")
            await session.rollback()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
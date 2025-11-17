"""
Knowledge Container Seeder

지식 컨테이너 테이블(tb_knowledge_containers)에 대한 시드 데이터를 로드합니다.
CSV 파일: knowledge_containers.csv
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.models.auth.permission_models import TbKnowledgeContainers
from app.core.database import get_async_session_local
from .base_seeder import BaseSeeder
import logging

logger = logging.getLogger(__name__)


class ContainerSeeder(BaseSeeder):
    """지식 컨테이너 데이터 시더"""
    
    async def seed_containers(self, clear_existing: bool = False) -> bool:
        """지식 컨테이너를 시드합니다."""
        return await self.run_seed(
            csv_filename="knowledge_containers.csv",
            model=TbKnowledgeContainers,
            key_fields=["container_id"],
            required_fields=["container_id", "container_name", "container_type"],
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
            seeder = ContainerSeeder(session)
            success = await seeder.seed_containers(clear_existing=True)
            
            if success:
                logger.info("🎉 지식 컨테이너 시드 데이터 로딩 완료!")
            else:
                logger.error("❌ 지식 컨테이너 시드 데이터 로딩 실패!")
                
        except Exception as e:
            logger.error(f"❌ 시드 실행 중 오류 발생: {e}")
            await session.rollback()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
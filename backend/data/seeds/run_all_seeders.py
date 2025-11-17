"""
All Seeders Runner

모든 시드 데이터를 순서대로 로드하는 통합 실행기입니다.
외래키 제약 조건을 고려하여 적절한 순서로 데이터를 로드합니다.
"""
import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_async_session_local
from data.seeds.system_seeder import SystemSeeder
from data.seeds.hr_seeder import HRSeeder
from data.seeds.user_seeder import UserSeeder
from data.seeds.container_seeder import ContainerSeeder
from data.seeds.permission_seeder import PermissionSeeder
import logging

logger = logging.getLogger(__name__)


class AllSeeders:
    """모든 시더를 실행하는 통합 클래스"""
    
    def __init__(self, session):
        self.session = session
        self.system_seeder = SystemSeeder(session)
        self.hr_seeder = HRSeeder(session)
        self.user_seeder = UserSeeder(session)
        self.container_seeder = ContainerSeeder(session)
        self.permission_seeder = PermissionSeeder(session)
    
    async def run_all(self, clear_existing: bool = False) -> bool:
        """모든 시드 데이터를 순서대로 실행합니다."""
        try:
            logger.info("🚀 WKMS 마스터 데이터 초기화 시작...")
            logger.info("=" * 60)
            
            # 1. 시스템 기본 데이터 (공통코드, 카테고리)
            logger.info("📋 1단계: 시스템 기본 데이터 로딩...")
            if not await self.system_seeder.seed_all(clear_existing):
                logger.error("❌ 시스템 데이터 로딩 실패!")
                return False
            
            # 2. HR 정보 (부서/조직 정보)
            logger.info("🏢 2단계: SAP HR 조직 정보 로딩...")
            if not await self.hr_seeder.seed_hr_info(clear_existing):
                logger.error("❌ HR 데이터 로딩 실패!")
                return False
            
            # 3. 사용자 정보 (HR 정보 참조)
            logger.info("👥 3단계: 사용자 정보 로딩...")
            if not await self.user_seeder.seed_users(clear_existing):
                logger.error("❌ 사용자 데이터 로딩 실패!")
                return False
            
            # 4. 지식 컨테이너 (조직 구조 기반)
            logger.info("📁 4단계: 지식 컨테이너 구조 생성...")
            if not await self.container_seeder.seed_containers(clear_existing):
                logger.error("❌ 지식 컨테이너 데이터 로딩 실패!")
                return False
            
            # 5. 권한 데이터 (사용자, 컨테이너 참조)
            logger.info("🔐 5단계: 사용자 권한 및 역할 설정...")
            if not await self.permission_seeder.seed_all(clear_existing):
                logger.error("❌ 권한 데이터 로딩 실패!")
                return False
            
            logger.info("=" * 60)
            logger.info("🎉 WKMS 마스터 데이터 초기화 완료!")
            logger.info("=" * 60)
            
            # 최종 통계 출력
            await self._print_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 시드 데이터 로딩 중 오류 발생: {e}")
            await self.session.rollback()
            return False
    
    async def _print_summary(self):
        """데이터 로딩 결과 요약을 출력합니다."""
        try:
            logger.info("📊 데이터 로딩 결과 요약:")
            
            # 각 테이블의 레코드 수 확인
            tables = [
                ("tb_cmns_cd_grp_item", "공통 코드"),
                ("tb_knowledge_categories", "지식 카테고리"), 
                ("tb_sap_hr_info", "SAP HR 정보"),
                ("tb_user", "사용자"),
                ("tb_knowledge_containers", "지식 컨테이너"),
                ("tb_user_roles", "사용자 역할"),
                ("tb_user_permissions", "사용자 권한")
            ]
            
            for table_name, description in tables:
                try:
                    count = await self.system_seeder.get_record_count(table_name)
                    logger.info(f"   ✅ {description}: {count}개")
                except:
                    logger.info(f"   ⚠️  {description}: 확인 불가")
                    
        except Exception as e:
            logger.warning(f"⚠️  요약 정보 출력 실패: {e}")


async def main():
    """메인 실행 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('wkms_seed.log', encoding='utf-8')
        ]
    )
    
    logger.info("🌱 WKMS 시드 데이터 로더 시작")
    
    async_session = get_async_session_local()
    
    async with async_session() as session:
        try:
            all_seeders = AllSeeders(session)
            
            # 기존 데이터 초기화 여부 확인 (비대화식 자동 모드)
            import os
            if os.getenv('WKMS_AUTO_SEED', '').lower() == 'true':
                clear_existing = True
                logger.info("🔄 자동 모드: 기존 데이터를 삭제하고 새로 로드합니다.")
            else:
                clear_existing = input("기존 데이터를 삭제하고 다시 로드하시겠습니까? (y/N): ").lower() == 'y'
            
            success = await all_seeders.run_all(clear_existing=clear_existing)
            
            if success:
                logger.info("✅ 모든 시드 데이터 로딩이 성공적으로 완료되었습니다!")
                logger.info("")
                logger.info("🔑 기본 로그인 정보:")
                logger.info("   관리자: ADMIN001 / admin123!")
                logger.info("   일반사용자: 77107791 / staff2025")
                logger.info("")
                logger.info("💡 참고: 로그인 시 사번(emp_no)과 비밀번호를 입력하세요")
                logger.info("")
                return 0
            else:
                logger.error("❌ 시드 데이터 로딩 중 오류가 발생했습니다!")
                return 1
                
        except KeyboardInterrupt:
            logger.info("⚠️  사용자에 의해 중단되었습니다.")
            return 1
        except Exception as e:
            logger.error(f"❌ 실행 중 오류 발생: {e}")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
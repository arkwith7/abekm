"""Woongjin Knowledge Container Structure Setup

웅진 조직 구조에 맞는 지식 컨테이너 계층 구조 생성
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_async_session_local
from app.core.security import AuthUtils
from sqlalchemy import text
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 비동기 세션 팩토리
async_session_local = get_async_session_local()


async def create_woongjin_structure():
    """웅진 조직 구조에 맞는 지식 컨테이너 생성"""
    async with async_session_local() as session:
        try:
            # 웅진 조직 구조 정의
            containers_data = [
                # ROOT - COMPANY 레벨
                {
                    "container_id": "WJ_ROOT",
                    "container_name": "🏢 웅진",
                    "container_description": "웅진 그룹 최상위 지식 컨테이너",
                    "container_type": "COMPANY",
                    "container_owner": "ADMIN001",
                    "access_level": "PUBLIC",
                    "parent_container_id": None,
                    "hierarchy_level": 1,
                    "hierarchy_path": "/WJ_ROOT",
                    "sap_org_code": "WJ000",
                    "display_order": 1
                },
                
                # DIVISION 레벨 (본부/사업부)
                {
                    "container_id": "WJ_CEO",
                    "container_name": "📁 CEO직속",
                    "container_description": "CEO 직속 조직",
                    "container_type": "DIVISION",
                    "container_owner": "ADMIN001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_ROOT",
                    "hierarchy_level": 2,
                    "hierarchy_path": "/WJ_ROOT/WJ_CEO",
                    "sap_org_code": "WJ100",
                    "display_order": 1
                },
                {
                    "container_id": "WJ_CLOUD",
                    "container_name": "📁 클라우드사업본부",
                    "container_description": "클라우드 사업 관련 지식 관리",
                    "container_type": "DIVISION",
                    "container_owner": "ADMIN001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_ROOT",
                    "hierarchy_level": 2,
                    "hierarchy_path": "/WJ_ROOT/WJ_CLOUD",
                    "sap_org_code": "WJ200",
                    "display_order": 2
                },
                {
                    "container_id": "WJ_CTI",
                    "container_name": "📁 CTI사업본부",
                    "container_description": "CTI 사업 관련 지식 관리",
                    "container_type": "DIVISION",
                    "container_owner": "ADMIN001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_ROOT",
                    "hierarchy_level": 2,
                    "hierarchy_path": "/WJ_ROOT/WJ_CTI",
                    "sap_org_code": "WJ300",
                    "display_order": 3
                },
                
                # DEPARTMENT 레벨 (팀/부서)
                {
                    "container_id": "WJ_HR",
                    "container_name": "📁 인사전략팀",
                    "container_description": "인사 전략 및 관리",
                    "container_type": "DEPARTMENT",
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CEO",
                    "hierarchy_level": 3,
                    "hierarchy_path": "/WJ_ROOT/WJ_CEO/WJ_HR",
                    "sap_org_code": "WJ110",
                    "display_order": 1
                },
                {
                    "container_id": "WJ_PLANNING",
                    "container_name": "📁 기획팀",
                    "container_description": "전략 기획 및 경영 기획",
                    "container_type": "DEPARTMENT",
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CEO",
                    "hierarchy_level": 3,
                    "hierarchy_path": "/WJ_ROOT/WJ_CEO/WJ_PLANNING",
                    "sap_org_code": "WJ120",
                    "display_order": 2
                },
                {
                    "container_id": "WJ_CLOUD_SERVICE",
                    "container_name": "📁 클라우드서비스팀",
                    "container_description": "클라우드 서비스 개발 및 운영",
                    "container_type": "DEPARTMENT",
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CLOUD",
                    "hierarchy_level": 3,
                    "hierarchy_path": "/WJ_ROOT/WJ_CLOUD/WJ_CLOUD_SERVICE",
                    "sap_org_code": "WJ210",
                    "display_order": 1
                },
                {
                    "container_id": "WJ_MS_SERVICE",
                    "container_name": "📁 MS서비스팀",
                    "container_description": "Microsoft 솔루션 서비스",
                    "container_type": "DEPARTMENT",
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CLOUD",
                    "hierarchy_level": 3,
                    "hierarchy_path": "/WJ_ROOT/WJ_CLOUD/WJ_MS_SERVICE",
                    "sap_org_code": "WJ220",
                    "display_order": 2
                },
                {
                    "container_id": "WJ_INFRA_CONSULT",
                    "container_name": "📁 인프라컨설팅팀",
                    "container_description": "인프라 컨설팅 서비스",
                    "container_type": "DEPARTMENT",
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CTI",
                    "hierarchy_level": 3,
                    "hierarchy_path": "/WJ_ROOT/WJ_CTI/WJ_INFRA_CONSULT",
                    "sap_org_code": "WJ310",
                    "display_order": 1
                },
                {
                    "container_id": "WJ_BIZ_OPS1",
                    "container_name": "📁 Biz운영1팀",
                    "container_description": "비즈니스 운영 1팀",
                    "container_type": "DEPARTMENT",
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CTI",
                    "hierarchy_level": 3,
                    "hierarchy_path": "/WJ_ROOT/WJ_CTI/WJ_BIZ_OPS1",
                    "sap_org_code": "WJ320",
                    "display_order": 2
                },
                
                # TEAM 레벨 (세부 팀)
                {
                    "container_id": "WJ_RECRUIT",
                    "container_name": "📁 채용팀",
                    "container_description": "인재 채용 및 관리",
                    "container_type": "TEAM",
                    "container_owner": "EMP002",
                    "access_level": "TEAM_ONLY",
                    "parent_container_id": "WJ_HR",
                    "hierarchy_level": 4,
                    "hierarchy_path": "/WJ_ROOT/WJ_CEO/WJ_HR/WJ_RECRUIT",
                    "sap_org_code": "WJ111",
                    "display_order": 1
                },
                {
                    "container_id": "WJ_TRAINING",
                    "container_name": "📁 교육팀",
                    "container_description": "직원 교육 및 개발",
                    "container_type": "TEAM",
                    "container_owner": "EMP002",
                    "access_level": "TEAM_ONLY",
                    "parent_container_id": "WJ_HR",
                    "hierarchy_level": 4,
                    "hierarchy_path": "/WJ_ROOT/WJ_CEO/WJ_HR/WJ_TRAINING",
                    "sap_org_code": "WJ112",
                    "display_order": 2
                }
            ]
            
            for container_data in containers_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_knowledge_containers WHERE container_id = :container_id"),
                    {"container_id": container_data["container_id"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_knowledge_containers (
                                container_id, container_name, container_description, container_type,
                                container_owner, access_level, parent_container_id, hierarchy_level,
                                hierarchy_path, sap_org_code, display_order, is_active,
                                created_by, created_date
                            ) VALUES (
                                :container_id, :container_name, :container_description, :container_type,
                                :container_owner, :access_level, :parent_container_id, :hierarchy_level,
                                :hierarchy_path, :sap_org_code, :display_order, true,
                                'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        container_data
                    )
                    level_indent = "  " * (container_data["hierarchy_level"] - 1)
                    logger.info(f"{level_indent}✅ {container_data['container_name']} ({container_data['container_type']})")
            
            await session.commit()
            logger.info("🎉 웅진 조직 구조 지식 컨테이너 생성 완료!")
            
        except Exception as e:
            logger.error(f"❌ Error creating Woongjin structure: {e}")
            await session.rollback()
            raise


async def create_sample_categories():
    """웅진에 맞는 지식 카테고리 생성"""
    async with async_session_local() as session:
        try:
            categories_data = [
                {
                    "category_id": "CAT_HR",
                    "category_name": "인사관리",
                    "category_description": "인사 관련 정책 및 절차",
                    "parent_category_id": None,
                    "category_level": 1,
                    "display_order": 1
                },
                {
                    "category_id": "CAT_RECRUIT",
                    "category_name": "채용",
                    "category_description": "채용 프로세스 및 가이드",
                    "parent_category_id": "CAT_HR",
                    "category_level": 2,
                    "display_order": 1
                },
                {
                    "category_id": "CAT_TRAINING",
                    "category_name": "교육",
                    "category_description": "직원 교육 및 개발",
                    "parent_category_id": "CAT_HR",
                    "category_level": 2,
                    "display_order": 2
                },
                {
                    "category_id": "CAT_TECH",
                    "category_name": "기술문서",
                    "category_description": "기술 관련 문서 및 매뉴얼",
                    "parent_category_id": None,
                    "category_level": 1,
                    "display_order": 2
                },
                {
                    "category_id": "CAT_CLOUD",
                    "category_name": "클라우드",
                    "category_description": "클라우드 기술 및 서비스",
                    "parent_category_id": "CAT_TECH",
                    "category_level": 2,
                    "display_order": 1
                },
                {
                    "category_id": "CAT_BUSINESS",
                    "category_name": "업무매뉴얼",
                    "category_description": "업무 프로세스 및 매뉴얼",
                    "parent_category_id": None,
                    "category_level": 1,
                    "display_order": 3
                }
            ]
            
            for cat_data in categories_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_knowledge_categories WHERE category_id = :category_id"),
                    {"category_id": cat_data["category_id"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_knowledge_categories (
                                category_id, category_name, category_description, parent_category_id,
                                category_level, display_order, is_active, created_by, created_date
                            ) VALUES (
                                :category_id, :category_name, :category_description, :parent_category_id,
                                :category_level, :display_order, true, 'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        cat_data
                    )
                    indent = "  " * (cat_data["category_level"] - 1)
                    logger.info(f"{indent}📚 {cat_data['category_name']}")
            
            await session.commit()
            logger.info("✅ 지식 카테고리 생성 완료!")
            
        except Exception as e:
            logger.error(f"❌ Error creating categories: {e}")
            await session.rollback()
            raise


async def assign_container_permissions():
    """웅진 조직 구조에 맞는 권한 할당"""
    async with async_session_local() as session:
        try:
            permissions_data = [
                # 시스템 관리자 - 모든 컨테이너 ADMIN 권한
                {"user_emp_no": "ADMIN001", "container_id": "WJ_ROOT", "role_id": "ADMIN"},
                {"user_emp_no": "ADMIN001", "container_id": "WJ_CEO", "role_id": "ADMIN"},
                {"user_emp_no": "ADMIN001", "container_id": "WJ_CLOUD", "role_id": "ADMIN"},
                {"user_emp_no": "ADMIN001", "container_id": "WJ_CTI", "role_id": "ADMIN"},
                
                # 매니저 - 부서별 MANAGER 권한
                {"user_emp_no": "EMP001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "EMP001", "container_id": "WJ_HR", "role_id": "MANAGER"},
                {"user_emp_no": "EMP001", "container_id": "WJ_CLOUD_SERVICE", "role_id": "MANAGER"},
                
                # 에디터 - 팀별 EDITOR 권한
                {"user_emp_no": "EMP002", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "EMP002", "container_id": "WJ_HR", "role_id": "EDITOR"},
                {"user_emp_no": "EMP002", "container_id": "WJ_RECRUIT", "role_id": "EDITOR"},
                {"user_emp_no": "EMP002", "container_id": "WJ_TRAINING", "role_id": "EDITOR"},
                
                # 뷰어 - 제한적 VIEWER 권한
                {"user_emp_no": "EMP003", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "EMP003", "container_id": "WJ_CLOUD", "role_id": "VIEWER"}
            ]
            
            for perm_data in permissions_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM tb_user_permissions 
                        WHERE user_emp_no = :user_emp_no 
                        AND container_id = :container_id
                    """),
                    {
                        "user_emp_no": perm_data["user_emp_no"],
                        "container_id": perm_data["container_id"]
                    }
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_user_permissions (
                                user_emp_no, container_id, role_id, granted_by,
                                granted_date, is_active
                            ) VALUES (
                                :user_emp_no, :container_id, :role_id, 'SYSTEM',
                                CURRENT_TIMESTAMP, true
                            )
                        """),
                        perm_data
                    )
                    logger.info(f"🔐 {perm_data['user_emp_no']} -> {perm_data['container_id']} ({perm_data['role_id']})")
            
            await session.commit()
            logger.info("✅ 컨테이너 권한 할당 완료!")
            
        except Exception as e:
            logger.error(f"❌ Error assigning container permissions: {e}")
            await session.rollback()
            raise


async def verify_woongjin_structure():
    """웅진 조직 구조 검증"""
    async with async_session_local() as session:
        try:
            logger.info(f"\n🏢 웅진 지식 컨테이너 구조 검증:")
            
            # 계층별 컨테이너 확인
            result = await session.execute(
                text("""
                    SELECT 
                        container_id,
                        container_name,
                        container_type,
                        hierarchy_level,
                        parent_container_id
                    FROM tb_knowledge_containers 
                    ORDER BY hierarchy_level, display_order, container_name
                """)
            )
            containers = result.fetchall()
            
            # 계층 구조 출력
            def print_hierarchy(containers, parent_id=None, level=0):
                for container in containers:
                    if container.parent_container_id == parent_id:
                        indent = "│   " * level + ("├── " if level > 0 else "")
                        logger.info(f"{indent}{container.container_name} ({container.container_type})")
                        print_hierarchy(containers, container.container_id, level + 1)
            
            print_hierarchy(containers)
            
            # 통계 출력
            result = await session.execute(
                text("""
                    SELECT 
                        container_type,
                        COUNT(*) as count
                    FROM tb_knowledge_containers 
                    GROUP BY container_type
                    ORDER BY count DESC
                """)
            )
            stats = result.fetchall()
            
            logger.info(f"\n📊 컨테이너 통계:")
            for stat in stats:
                logger.info(f"   {stat.container_type}: {stat.count}개")
            
            # 권한 할당 현황
            result = await session.execute(
                text("""
                    SELECT COUNT(*) as perm_count 
                    FROM tb_user_permissions 
                    WHERE is_active = true
                """)
            )
            perm_count = result.scalar()
            logger.info(f"\n🔐 활성 권한 할당: {perm_count}개")
                
        except Exception as e:
            logger.error(f"❌ Error during verification: {e}")
            raise


async def main():
    """웅진 지식 컨테이너 구조 설정 메인 함수"""
    logger.info("🚀 웅진 지식 컨테이너 구조 설정을 시작합니다...")
    
    try:
        # 1. 웅진 조직 구조 생성
        await create_woongjin_structure()
        
        # 2. 지식 카테고리 생성
        await create_sample_categories()
        
        # 3. 컨테이너 권한 할당
        await assign_container_permissions()
        
        # 4. 구조 검증
        await verify_woongjin_structure()
        
        logger.info("🎉 웅진 지식 컨테이너 구조 설정이 완료되었습니다!")
        logger.info("\n🌟 생성된 구조:")
        logger.info("   🏢 웅진 (최상위)")
        logger.info("   ├── 📁 CEO직속")
        logger.info("   │   ├── 📁 인사전략팀")
        logger.info("   │   │   ├── 📁 채용팀")
        logger.info("   │   │   └── 📁 교육팀")
        logger.info("   │   └── 📁 기획팀")
        logger.info("   ├── 📁 클라우드사업본부")
        logger.info("   │   ├── 📁 클라우드서비스팀")
        logger.info("   │   └── 📁 MS서비스팀")
        logger.info("   └── 📁 CTI사업본부")
        logger.info("       ├── 📁 인프라컨설팅팀")
        logger.info("       └── 📁 Biz운영1팀")
        
    except Exception as e:
        logger.error(f"❌ Error during Woongjin structure setup: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

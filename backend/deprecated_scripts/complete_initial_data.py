"""Complete initial data setup for WKMS

완전한 초기 데이터 설정 - 권한 관리 시스템 포함
- SAP HR 정보
- 사용자 정보 (tb_user)
- 지식 컨테이너
- 사용자 권한 할당
- 기본 카테고리
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


async def create_sap_hr_info():
    """SAP HR 정보 생성"""
    async with async_session_local() as session:
        try:
            sap_users_data = [
                {
                    "emp_no": "ADMIN001",
                    "emp_name": "시스템 관리자",
                    "dept_code": "IT001",
                    "dept_name": "정보시스템팀",
                    "position_code": "MGR001",
                    "position_name": "팀장",
                    "job_title": "시스템 관리자",
                    "email": "admin@wkms.com",
                    "phone_number": "02-1234-5678",
                    "hire_date": "2020-01-01",
                    "employment_status": "ACTIVE"
                },
                {
                    "emp_no": "EMP001",
                    "emp_name": "김매니저",
                    "dept_code": "BIZ001",
                    "dept_name": "사업기획팀",
                    "position_code": "MGR002",
                    "position_name": "과장",
                    "job_title": "기획 매니저",
                    "email": "manager1@wkms.com",
                    "phone_number": "02-1234-5679",
                    "hire_date": "2021-03-15",
                    "employment_status": "ACTIVE"
                },
                {
                    "emp_no": "EMP002",
                    "emp_name": "이에디터",
                    "dept_code": "CON001",
                    "dept_name": "콘텐츠팀",
                    "position_code": "SEN001",
                    "position_name": "선임",
                    "job_title": "콘텐츠 에디터",
                    "email": "editor1@wkms.com",
                    "phone_number": "02-1234-5680",
                    "hire_date": "2022-06-01",
                    "employment_status": "ACTIVE"
                },
                {
                    "emp_no": "EMP003",
                    "emp_name": "박뷰어",
                    "dept_code": "SAL001",
                    "dept_name": "영업팀",
                    "position_code": "JUN001",
                    "position_name": "사원",
                    "job_title": "영업 사원",
                    "email": "viewer1@wkms.com",
                    "phone_number": "02-1234-5681",
                    "hire_date": "2023-09-01",
                    "employment_status": "ACTIVE"
                }
            ]
            
            for sap_data in sap_users_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_sap_hr_info WHERE emp_no = :emp_no"),
                    {"emp_no": sap_data["emp_no"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_sap_hr_info (
                                emp_no, emp_name, dept_code, dept_name, position_code, position_name,
                                job_title, email, phone_number, hire_date, employment_status,
                                created_by, created_date
                            ) VALUES (
                                :emp_no, :emp_name, :dept_code, :dept_name, :position_code, :position_name,
                                :job_title, :email, :phone_number, :hire_date, :employment_status,
                                'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        sap_data
                    )
                    logger.info(f"Created SAP HR info: {sap_data['emp_no']} - {sap_data['emp_name']}")
            
            await session.commit()
            logger.info("✅ SAP HR information created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating SAP HR info: {e}")
            await session.rollback()
            raise


async def create_users():
    """사용자 정보 생성 (tb_user)"""
    async with async_session_local() as session:
        try:
            users_data = [
                {
                    "emp_no": "ADMIN001",
                    "username": "admin",
                    "email": "admin@wkms.com",
                    "password": "admin123!",
                    "is_admin": True
                },
                {
                    "emp_no": "EMP001",
                    "username": "manager1",
                    "email": "manager1@wkms.com",
                    "password": "manager123!",
                    "is_admin": False
                },
                {
                    "emp_no": "EMP002",
                    "username": "editor1",
                    "email": "editor1@wkms.com",
                    "password": "editor123!",
                    "is_admin": False
                },
                {
                    "emp_no": "EMP003",
                    "username": "viewer1",
                    "email": "viewer1@wkms.com",
                    "password": "viewer123!",
                    "is_admin": False
                }
            ]
            
            for user_data in users_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_user WHERE username = :username"),
                    {"username": user_data["username"]}
                )
                count = result.scalar()
                
                if count == 0:
                    password_hash = AuthUtils.get_password_hash(user_data["password"])
                    
                    await session.execute(
                        text("""
                            INSERT INTO tb_user (emp_no, username, email, password_hash, is_active, is_admin)
                            VALUES (:emp_no, :username, :email, :password_hash, :is_active, :is_admin)
                        """),
                        {
                            "emp_no": user_data["emp_no"],
                            "username": user_data["username"],
                            "email": user_data["email"],
                            "password_hash": password_hash,
                            "is_active": True,
                            "is_admin": user_data["is_admin"]
                        }
                    )
                    logger.info(f"Created user: {user_data['username']}")
            
            await session.commit()
            logger.info("✅ Users created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating users: {e}")
            await session.rollback()
            raise


async def create_knowledge_categories():
    """지식 카테고리 생성"""
    async with async_session_local() as session:
        try:
            categories_data = [
                {
                    "category_id": "CAT001",
                    "category_name": "기술문서",
                    "category_description": "기술 관련 문서 및 자료",
                    "parent_category_id": None
                },
                {
                    "category_id": "CAT002", 
                    "category_name": "업무매뉴얼",
                    "category_description": "업무 프로세스 및 매뉴얼",
                    "parent_category_id": None
                },
                {
                    "category_id": "CAT003",
                    "category_name": "교육자료",
                    "category_description": "교육 및 학습 자료",
                    "parent_category_id": None
                },
                {
                    "category_id": "CAT004",
                    "category_name": "API문서",
                    "category_description": "API 개발 문서",
                    "parent_category_id": "CAT001"
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
                                created_by, created_date
                            ) VALUES (
                                :category_id, :category_name, :category_description, :parent_category_id,
                                'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        cat_data
                    )
                    logger.info(f"Created category: {cat_data['category_id']} - {cat_data['category_name']}")
            
            await session.commit()
            logger.info("✅ Knowledge categories created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating categories: {e}")
            await session.rollback()
            raise


async def create_knowledge_containers():
    """지식 컨테이너 생성"""
    async with async_session_local() as session:
        try:
            containers_data = [
                {
                    "container_id": "CONT001",
                    "container_name": "전사 공통문서",
                    "container_description": "전사적으로 공유하는 공통 문서",
                    "container_type": "PUBLIC",
                    "container_owner": "ADMIN001",
                    "access_level": "PUBLIC",
                    "is_active": True
                },
                {
                    "container_id": "CONT002",
                    "container_name": "IT팀 기술문서",
                    "container_description": "IT팀 전용 기술 문서",
                    "container_type": "DEPARTMENT",
                    "container_owner": "ADMIN001",
                    "access_level": "RESTRICTED",
                    "is_active": True
                },
                {
                    "container_id": "CONT003",
                    "container_name": "사업기획 자료",
                    "container_description": "사업기획팀 업무 자료",
                    "container_type": "DEPARTMENT", 
                    "container_owner": "EMP001",
                    "access_level": "RESTRICTED",
                    "is_active": True
                },
                {
                    "container_id": "CONT004",
                    "container_name": "개인 작업공간",
                    "container_description": "개인 문서 작업 공간",
                    "container_type": "PERSONAL",
                    "container_owner": "EMP002",
                    "access_level": "PRIVATE",
                    "is_active": True
                }
            ]
            
            for cont_data in containers_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_knowledge_containers WHERE container_id = :container_id"),
                    {"container_id": cont_data["container_id"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_knowledge_containers (
                                container_id, container_name, container_description, container_type,
                                container_owner, access_level, is_active, created_by, created_date
                            ) VALUES (
                                :container_id, :container_name, :container_description, :container_type,
                                :container_owner, :access_level, :is_active, 'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        cont_data
                    )
                    logger.info(f"Created container: {cont_data['container_id']} - {cont_data['container_name']}")
            
            await session.commit()
            logger.info("✅ Knowledge containers created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating containers: {e}")
            await session.rollback()
            raise


async def create_user_roles():
    """사용자 역할 생성"""
    async with async_session_local() as session:
        try:
            roles_data = [
                {
                    "role_id": "ADMIN",
                    "role_name": "관리자",
                    "role_description": "시스템 전체 관리 권한",
                    "role_level": 1
                },
                {
                    "role_id": "MANAGER",
                    "role_name": "매니저",
                    "role_description": "팀/부서 관리 권한",
                    "role_level": 2
                },
                {
                    "role_id": "EDITOR",
                    "role_name": "편집자",
                    "role_description": "문서 편집 권한",
                    "role_level": 3
                },
                {
                    "role_id": "VIEWER",
                    "role_name": "조회자",
                    "role_description": "문서 조회 권한",
                    "role_level": 4
                }
            ]
            
            for role_data in roles_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_user_roles WHERE role_id = :role_id"),
                    {"role_id": role_data["role_id"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_user_roles (
                                role_id, role_name, role_description, role_level,
                                created_by, created_date
                            ) VALUES (
                                :role_id, :role_name, :role_description, :role_level,
                                'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        role_data
                    )
                    logger.info(f"Created role: {role_data['role_id']} - {role_data['role_name']}")
            
            await session.commit()
            logger.info("✅ User roles created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating roles: {e}")
            await session.rollback()
            raise


async def assign_user_permissions():
    """사용자 권한 할당"""
    async with async_session_local() as session:
        try:
            permissions_data = [
                # 관리자 - 모든 컨테이너에 ADMIN 권한
                {"user_emp_no": "ADMIN001", "container_id": "CONT001", "role_id": "ADMIN"},
                {"user_emp_no": "ADMIN001", "container_id": "CONT002", "role_id": "ADMIN"},
                {"user_emp_no": "ADMIN001", "container_id": "CONT003", "role_id": "ADMIN"},
                {"user_emp_no": "ADMIN001", "container_id": "CONT004", "role_id": "ADMIN"},
                
                # 매니저 - 전사공통, 사업기획에 MANAGER 권한
                {"user_emp_no": "EMP001", "container_id": "CONT001", "role_id": "MANAGER"},
                {"user_emp_no": "EMP001", "container_id": "CONT003", "role_id": "MANAGER"},
                
                # 에디터 - 전사공통, 개인작업공간에 EDITOR 권한
                {"user_emp_no": "EMP002", "container_id": "CONT001", "role_id": "EDITOR"},
                {"user_emp_no": "EMP002", "container_id": "CONT004", "role_id": "EDITOR"},
                
                # 뷰어 - 전사공통에만 VIEWER 권한
                {"user_emp_no": "EMP003", "container_id": "CONT001", "role_id": "VIEWER"}
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
                    logger.info(f"Assigned permission: {perm_data['user_emp_no']} -> {perm_data['container_id']} ({perm_data['role_id']})")
            
            await session.commit()
            logger.info("✅ User permissions assigned successfully")
            
        except Exception as e:
            logger.error(f"❌ Error assigning permissions: {e}")
            await session.rollback()
            raise


async def verify_complete_setup():
    """완전한 설정 검증"""
    async with async_session_local() as session:
        try:
            logger.info(f"\n📊 Complete Setup Verification:")
            
            # SAP HR 정보 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_sap_hr_info"))
            sap_count = result.scalar()
            logger.info(f"   SAP HR Info: {sap_count}명")
            
            # 사용자 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_user"))
            user_count = result.scalar()
            logger.info(f"   Users: {user_count}명")
            
            # 카테고리 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_knowledge_categories"))
            cat_count = result.scalar()
            logger.info(f"   Categories: {cat_count}개")
            
            # 컨테이너 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_knowledge_containers"))
            cont_count = result.scalar()
            logger.info(f"   Containers: {cont_count}개")
            
            # 역할 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_user_roles"))
            role_count = result.scalar()
            logger.info(f"   Roles: {role_count}개")
            
            # 권한 할당 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_user_permissions"))
            perm_count = result.scalar()
            logger.info(f"   Permission assignments: {perm_count}개")
            
            # 권한 매트릭스 출력
            logger.info(f"\n🔐 Permission Matrix:")
            result = await session.execute(
                text("""
                    SELECT 
                        h.emp_name,
                        c.container_name,
                        r.role_name
                    FROM tb_user_permissions p
                    JOIN tb_sap_hr_info h ON p.user_emp_no = h.emp_no
                    JOIN tb_knowledge_containers c ON p.container_id = c.container_id
                    JOIN tb_user_roles r ON p.role_id = r.role_id
                    WHERE p.is_active = true
                    ORDER BY h.emp_name, c.container_name
                """)
            )
            permissions = result.fetchall()
            
            for perm in permissions:
                logger.info(f"   {perm.emp_name} -> {perm.container_name} ({perm.role_name})")
                
        except Exception as e:
            logger.error(f"❌ Error during verification: {e}")
            raise


async def main():
    """완전한 초기 데이터 설정 메인 함수"""
    logger.info("🚀 Starting complete initial data setup for WKMS...")
    
    try:
        # 1. SAP HR 정보 생성
        await create_sap_hr_info()
        
        # 2. 사용자 정보 생성
        await create_users()
        
        # 3. 지식 카테고리 생성
        await create_knowledge_categories()
        
        # 4. 지식 컨테이너 생성
        await create_knowledge_containers()
        
        # 5. 사용자 역할 생성
        await create_user_roles()
        
        # 6. 사용자 권한 할당
        await assign_user_permissions()
        
        # 7. 설정 검증
        await verify_complete_setup()
        
        logger.info("🎉 Complete initial data setup finished successfully!")
        logger.info("\n📋 Login Information:")
        logger.info("   Admin: admin / admin123! (전체 시스템 관리)")
        logger.info("   Manager: manager1 / manager123! (팀 관리)")
        logger.info("   Editor: editor1 / editor123! (문서 편집)")
        logger.info("   Viewer: viewer1 / viewer123! (문서 조회)")
        
        logger.info("\n🏗️ System Components Ready:")
        logger.info("   ✅ User Authentication")
        logger.info("   ✅ Permission Management")
        logger.info("   ✅ Knowledge Containers")
        logger.info("   ✅ Role-based Access Control")
        logger.info("   ✅ Category System")
        
    except Exception as e:
        logger.error(f"❌ Error during complete initial data setup: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

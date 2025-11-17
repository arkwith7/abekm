"""Complete WKMS Initial Data Setup

웅진 WKMS 시스템의 완전한 초기 데이터 설정
- 웅진 조직 구조 기반 지식 컨테이너
- SAP HR 정보
- 사용자 계정 및 권한 관리
- 지식 카테고리 체계
- 역할 기반 접근 제어 (RBAC)
- 권한 할당 및 워크플로우
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
    """웅진 조직 구조 기반 SAP HR 정보 생성"""
    async with async_session_local() as session:
        try:
            sap_users_data = [
                # 시스템 관리자
                {
                    "emp_no": "ADMIN001",
                    "emp_nm": "시스템관리자",
                    "dept_cd": "IT100",
                    "dept_nm": "IT운영팀",
                    "postn_cd": "ADM001",
                    "postn_nm": "시스템관리자",
                    "email": "admin@woongjin.co.kr",
                    "telno": "02-1234-5678",
                    "entrps_de": "20200101",
                    "emp_stats_cd": "ACTIVE"
                },
                # CEO직속 - 인사전략팀
                {
                    "emp_no": "HR001",
                    "emp_nm": "김인사",
                    "dept_cd": "HR100",
                    "dept_nm": "인사전략팀",
                    "postn_cd": "MGR002",
                    "postn_nm": "팀장",
                    "email": "hr.manager@woongjin.co.kr",
                    "telno": "02-1234-5679",
                    "entrps_de": "20190315",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "REC001",
                    "emp_nm": "이채용",
                    "dept_cd": "HR110",
                    "dept_nm": "채용팀",
                    "postn_cd": "SEN001",
                    "postn_nm": "선임",
                    "email": "recruit@woongjin.co.kr",
                    "telno": "02-1234-5680",
                    "entrps_de": "20210601",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "TRN001",
                    "emp_nm": "박교육",
                    "dept_cd": "HR120",
                    "dept_nm": "교육팀",
                    "postn_cd": "SEN002",
                    "postn_nm": "선임",
                    "email": "training@woongjin.co.kr",
                    "telno": "02-1234-5681",
                    "entrps_de": "20200901",
                    "emp_stats_cd": "ACTIVE"
                },
                # CEO직속 - 기획팀
                {
                    "emp_no": "PLN001",
                    "emp_nm": "최기획",
                    "dept_cd": "PLN100",
                    "dept_nm": "기획팀",
                    "postn_cd": "MGR003",
                    "postn_nm": "팀장",
                    "email": "planning@woongjin.co.kr",
                    "telno": "02-1234-5682",
                    "entrps_de": "20180115",
                    "emp_stats_cd": "ACTIVE"
                },
                # 클라우드사업본부
                {
                    "emp_no": "CLD001",
                    "emp_nm": "김클라우드",
                    "dept_cd": "CLD100",
                    "dept_nm": "클라우드서비스팀",
                    "postn_cd": "MGR004",
                    "postn_nm": "팀장",
                    "email": "cloud@woongjin.co.kr",
                    "telno": "02-1234-5683",
                    "entrps_de": "20190701",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "MSS001",
                    "emp_nm": "정MS",
                    "dept_cd": "MSS100",
                    "dept_nm": "MS서비스팀",
                    "postn_cd": "MGR005",
                    "postn_nm": "팀장",
                    "email": "ms.service@woongjin.co.kr",
                    "telno": "02-1234-5684",
                    "entrps_de": "20200215",
                    "emp_stats_cd": "ACTIVE"
                },
                # CTI사업본부
                {
                    "emp_no": "INF001",
                    "emp_nm": "한인프라",
                    "dept_cd": "INF100",
                    "dept_nm": "인프라컨설팅팀",
                    "postn_cd": "MGR006",
                    "postn_nm": "팀장",
                    "email": "infra@woongjin.co.kr",
                    "telno": "02-1234-5685",
                    "entrps_de": "20181101",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "BIZ001",
                    "emp_nm": "오비즈",
                    "dept_cd": "BIZ100",
                    "dept_nm": "Biz운영1팀",
                    "postn_cd": "MGR007",
                    "postn_nm": "팀장",
                    "email": "biz.ops@woongjin.co.kr",
                    "telno": "02-1234-5686",
                    "entrps_de": "20190401",
                    "emp_stats_cd": "ACTIVE"
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
                    query = text("""
                        INSERT INTO tb_sap_hr_info (
                            emp_no, emp_nm, dept_cd, dept_nm, postn_cd, postn_nm,
                            email, telno, entrps_de, emp_stats_cd,
                            created_by, created_date
                        ) VALUES (
                            :emp_no, :emp_nm, :dept_cd, :dept_nm, :postn_cd, :postn_nm,
                            :email, :telno, :entrps_de, :emp_stats_cd,
                            'SYSTEM', CURRENT_TIMESTAMP
                        )
                    """)
                    
                    await session.execute(query, sap_data)
                    logger.info(f"Created SAP HR: {sap_data['emp_no']} - {sap_data['emp_nm']} ({sap_data['dept_nm']})")
            
            await session.commit()
            logger.info("✅ SAP HR 정보 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ Error creating SAP HR info: {e}")
            await session.rollback()
            raise


async def create_users():
    """사용자 계정 생성"""
    async with async_session_local() as session:
        try:
            users_data = [
                {
                    "emp_no": "ADMIN001",
                    "username": "admin",
                    "email": "admin@woongjin.co.kr",
                    "password": "admin123!",
                    "is_admin": True
                },
                {
                    "emp_no": "HR001",
                    "username": "hr.manager",
                    "email": "hr.manager@woongjin.co.kr",
                    "password": "hr123!",
                    "is_admin": False
                },
                {
                    "emp_no": "REC001",
                    "username": "recruit",
                    "email": "recruit@woongjin.co.kr",
                    "password": "recruit123!",
                    "is_admin": False
                },
                {
                    "emp_no": "TRN001",
                    "username": "training",
                    "email": "training@woongjin.co.kr",
                    "password": "training123!",
                    "is_admin": False
                },
                {
                    "emp_no": "PLN001",
                    "username": "planning",
                    "email": "planning@woongjin.co.kr",
                    "password": "planning123!",
                    "is_admin": False
                },
                {
                    "emp_no": "CLD001",
                    "username": "cloud",
                    "email": "cloud@woongjin.co.kr",
                    "password": "cloud123!",
                    "is_admin": False
                },
                {
                    "emp_no": "MSS001",
                    "username": "ms.service",
                    "email": "ms.service@woongjin.co.kr",
                    "password": "ms123!",
                    "is_admin": False
                },
                {
                    "emp_no": "INF001",
                    "username": "infra",
                    "email": "infra@woongjin.co.kr",
                    "password": "infra123!",
                    "is_admin": False
                },
                {
                    "emp_no": "BIZ001",
                    "username": "biz.ops",
                    "email": "biz.ops@woongjin.co.kr",
                    "password": "biz123!",
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
                    logger.info(f"Created user: {user_data['username']} ({user_data['emp_no']})")
            
            await session.commit()
            logger.info("✅ 사용자 계정 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ Error creating users: {e}")
            await session.rollback()
            raise


async def create_woongjin_containers():
    """웅진 조직 구조 기반 지식 컨테이너 생성"""
    async with async_session_local() as session:
        try:
            containers_data = [
                # 1. 웅진 최상위 컨테이너 (COMPANY 레벨)
                {
                    "container_id": "WJ_ROOT",
                    "container_name": "🏢 웅진",
                    "description": "웅진 그룹 최상위 지식 컨테이너",
                    "container_type": "COMPANY",
                    "container_owner": "ADMIN001",
                    "access_level": "PUBLIC",
                    "parent_container_id": None,
                    "org_level": 1,
                    "org_path": "/WJ_ROOT",
                    "sap_org_code": "WJ000",
                    "default_permission": "READ",
                    "inherit_parent_permissions": False,
                    "permission_inheritance_type": "NONE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 2. CEO직속 (DIVISION 레벨)
                {
                    "container_id": "WJ_CEO",
                    "container_name": "📁 CEO직속",
                    "description": "CEO 직속 조직",
                    "container_type": "DIVISION",
                    "container_owner": "ADMIN001",
                    "access_level": "DIVISION_ONLY",
                    "parent_container_id": "WJ_ROOT",
                    "org_level": 2,
                    "org_path": "/WJ_ROOT/WJ_CEO",
                    "sap_org_code": "CEO000",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "CASCADING",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 3. 클라우드사업본부 (DIVISION 레벨)
                {
                    "container_id": "WJ_CLOUD",
                    "container_name": "📁 클라우드사업본부",
                    "description": "클라우드 사업 관련 지식 관리",
                    "container_type": "DIVISION",
                    "container_owner": "CLD001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_ROOT",
                    "org_level": 2,
                    "org_path": "/WJ_ROOT/WJ_CLOUD",
                    "sap_org_code": "WJ200",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "CASCADING",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": True,
                    "approval_workflow_enabled": True
                },
                # 4. CTI사업본부 (DIVISION 레벨)
                {
                    "container_id": "WJ_CTI",
                    "container_name": "📁 CTI사업본부",
                    "description": "CTI 사업 관련 지식 관리",
                    "container_type": "DIVISION",
                    "container_owner": "INF001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_ROOT",
                    "org_level": 2,
                    "org_path": "/WJ_ROOT/WJ_CTI",
                    "sap_org_code": "WJ300",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "CASCADING",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": True,
                    "approval_workflow_enabled": True
                },
                
                # DEPARTMENT 레벨 (팀/부서)
                # 5. 인사전략팀 (CEO직속)
                {
                    "container_id": "WJ_HR",
                    "container_name": "📁 인사전략팀",
                    "description": "인사 전략 및 관리",
                    "container_type": "DEPARTMENT",
                    "container_owner": "HR001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CEO",
                    "org_level": 3,
                    "org_path": "/WJ_ROOT/WJ_CEO/WJ_HR",
                    "sap_org_code": "HR100",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 6. 기획팀 (CEO직속)
                {
                    "container_id": "WJ_PLANNING",
                    "container_name": "📁 기획팀",
                    "description": "전략 기획 및 경영 기획",
                    "container_type": "DEPARTMENT",
                    "container_owner": "PLN001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CEO",
                    "org_level": 3,
                    "org_path": "/WJ_ROOT/WJ_CEO/WJ_PLANNING",
                    "sap_org_code": "PLN100",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 7. 클라우드서비스팀 (클라우드사업본부)
                {
                    "container_id": "WJ_CLOUD_SERVICE",
                    "container_name": "📁 클라우드서비스팀",
                    "description": "클라우드 서비스 개발 및 운영",
                    "container_type": "DEPARTMENT",
                    "container_owner": "CLD001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CLOUD",
                    "org_level": 3,
                    "org_path": "/WJ_ROOT/WJ_CLOUD/WJ_CLOUD_SERVICE",
                    "sap_org_code": "CLD100",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                                # 8. MS서비스팀 (클라우드사업본부)
                {
                    "container_id": "WJ_MS_SERVICE",
                    "container_name": "📁 MS서비스팀",
                    "description": "Microsoft 솔루션 서비스",
                    "container_type": "DEPARTMENT",
                    "container_owner": "MSS001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CLOUD",
                    "org_level": 3,
                    "org_path": "/WJ_ROOT/WJ_CLOUD/WJ_MS_SERVICE",
                    "sap_org_code": "MSS100",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 9. 인프라컨설팅팀 (CTI사업본부)
                {
                    "container_id": "WJ_INFRA_CONSULT",
                    "container_name": "📁 인프라컨설팅팀",
                    "description": "인프라 컨설팅 서비스",
                    "container_type": "DEPARTMENT",
                    "container_owner": "INF001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CTI",
                    "org_level": 3,
                    "org_path": "/WJ_ROOT/WJ_CTI/WJ_INFRA_CONSULT",
                    "sap_org_code": "INF100",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 10. Biz운영1팀 (CTI사업본부)
                {
                    "container_id": "WJ_BIZ_OPS1",
                    "container_name": "📁 Biz운영1팀",
                    "description": "비즈니스 운영 1팀",
                    "container_type": "DEPARTMENT",
                    "container_owner": "BIZ001",
                    "access_level": "RESTRICTED",
                    "parent_container_id": "WJ_CTI",
                    "org_level": 3,
                    "org_path": "/WJ_ROOT/WJ_CTI/WJ_BIZ_OPS1",
                    "sap_org_code": "BIZ100",
                    "default_permission": "READ",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                
                # TEAM 레벨 (하위 팀)
                # 11. 채용팀 (인사전략팀 하위)
                {
                    "container_id": "WJ_RECRUIT",
                    "container_name": "📁 채용팀",
                    "description": "직원 채용 및 선발",
                    "container_type": "TEAM",
                    "container_owner": "REC001",
                    "access_level": "TEAM_ONLY",
                    "parent_container_id": "WJ_HR",
                    "org_level": 4,
                    "org_path": "/WJ_ROOT/WJ_CEO/WJ_HR/WJ_RECRUIT",
                    "sap_org_code": "HR110",
                    "default_permission": "WRITE",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
                },
                # 12. 교육팀 (인사전략팀 하위)
                {
                    "container_id": "WJ_TRAINING",
                    "container_name": "📁 교육팀",
                    "description": "직원 교육 및 개발",
                    "container_type": "TEAM",
                    "container_owner": "TRN001",
                    "access_level": "TEAM_ONLY",
                    "parent_container_id": "WJ_HR",
                    "org_level": 4,
                    "org_path": "/WJ_ROOT/WJ_CEO/WJ_HR/WJ_TRAINING",
                    "sap_org_code": "HR120",
                    "default_permission": "WRITE",
                    "inherit_parent_permissions": True,
                    "permission_inheritance_type": "SELECTIVE",
                    "auto_assign_by_org": True,
                    "require_approval_for_access": False,
                    "approval_workflow_enabled": False
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
                                container_id, container_name, description, container_type,
                                container_owner, access_level, parent_container_id, org_level,
                                org_path, sap_org_code, default_permission, inherit_parent_permissions,
                                permission_inheritance_type, auto_assign_by_org, require_approval_for_access,
                                approval_workflow_enabled, is_active, document_count, total_knowledge_size,
                                user_count, permission_request_count, created_by, created_date
                            ) VALUES (
                                :container_id, :container_name, :description, :container_type,
                                :container_owner, :access_level, :parent_container_id, :org_level,
                                :org_path, :sap_org_code, :default_permission, :inherit_parent_permissions,
                                :permission_inheritance_type, :auto_assign_by_org, :require_approval_for_access,
                                :approval_workflow_enabled, true, 0, 0,
                                0, 0, 'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        container_data
                    )
                    level_indent = "  " * (container_data["org_level"] - 1)
                    logger.info(f"{level_indent}Created: {container_data['container_name']}")
            
            await session.commit()
            logger.info("✅ 웅진 지식 컨테이너 구조 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ Error creating containers: {e}")
            await session.rollback()
            raise


async def create_knowledge_categories():
    """지식 카테고리 체계 생성"""
    async with async_session_local() as session:
        try:
            categories_data = [
                # 1단계 카테고리
                {
                    "category_code": "HR",
                    "category_name": "인사관리",
                    "description": "인사 관련 정책 및 절차",
                    "parent_category_id": None,
                    "category_level": 1,
                    "knowledge_type": "POLICY",
                    "content_format": "DOCUMENT",
                    "update_frequency": "QUARTERLY"
                },
                {
                    "category_code": "TECH",
                    "category_name": "기술문서",
                    "description": "기술 관련 문서 및 매뉴얼",
                    "parent_category_id": None,
                    "category_level": 1,
                    "knowledge_type": "TECHNICAL",
                    "content_format": "DOCUMENT",
                    "update_frequency": "MONTHLY"
                },
                {
                    "category_code": "BUSINESS",
                    "category_name": "업무매뉴얼",
                    "description": "업무 프로세스 및 매뉴얼",
                    "parent_category_id": None,
                    "category_level": 1,
                    "knowledge_type": "PROCESS",
                    "content_format": "MANUAL",
                    "update_frequency": "BIANNUAL"
                },
                {
                    "category_code": "PLANNING",
                    "category_name": "기획자료",
                    "description": "전략 기획 및 사업 계획",
                    "parent_category_id": None,
                    "category_level": 1,
                    "knowledge_type": "STRATEGIC",
                    "content_format": "PRESENTATION",
                    "update_frequency": "ANNUAL"
                }
            ]
            
            # 1단계 카테고리 생성
            created_categories = {}
            for cat_data in categories_data:
                # 이미 존재하는지 확인
                result = await session.execute(
                    text("SELECT category_id FROM tb_knowledge_categories WHERE category_code = :category_code"),
                    {"category_code": cat_data["category_code"]}
                )
                existing = result.fetchone()
                
                if not existing:
                    result = await session.execute(
                        text("""
                            INSERT INTO tb_knowledge_categories (
                                category_name, category_code, parent_category_id, description,
                                category_level, knowledge_type, content_format, update_frequency,
                                is_active, created_date
                            ) VALUES (
                                :category_name, :category_code, :parent_category_id, :description,
                                :category_level, :knowledge_type, :content_format, :update_frequency,
                                true, CURRENT_TIMESTAMP
                            ) RETURNING category_id
                        """),
                        cat_data
                    )
                    category_id = result.scalar()
                    created_categories[cat_data["category_code"]] = category_id
                    logger.info(f"Created category: {cat_data['category_name']} (ID: {category_id})")
                else:
                    created_categories[cat_data["category_code"]] = existing[0]
            
            await session.commit()
            logger.info("✅ 지식 카테고리 체계 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ Error creating categories: {e}")
            await session.rollback()
            raise


async def create_user_roles():
    """사용자 역할 정의 생성"""
    async with async_session_local() as session:
        try:
            roles_data = [
                {
                    "role_id": "ADMIN",
                    "role_name": "시스템 관리자",
                    "role_description": "시스템 전체 관리 권한",
                    "role_level": 1,
                    "permissions": ["CREATE", "READ", "UPDATE", "DELETE", "MANAGE"]
                },
                {
                    "role_id": "MANAGER",
                    "role_name": "부서 관리자",
                    "role_description": "부서/팀 관리 권한",
                    "role_level": 2,
                    "permissions": ["CREATE", "READ", "UPDATE", "DELETE"]
                },
                {
                    "role_id": "EDITOR",
                    "role_name": "편집자",
                    "role_description": "문서 편집 권한",
                    "role_level": 3,
                    "permissions": ["CREATE", "READ", "UPDATE"]
                },
                {
                    "role_id": "VIEWER",
                    "role_name": "조회자",
                    "role_description": "문서 조회 권한",
                    "role_level": 4,
                    "permissions": ["READ"]
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
                        {
                            "role_id": role_data["role_id"],
                            "role_name": role_data["role_name"],
                            "role_description": role_data["role_description"],
                            "role_level": role_data["role_level"]
                        }
                    )
                    logger.info(f"Created role: {role_data['role_name']} ({role_data['role_id']})")
            
            await session.commit()
            logger.info("✅ 사용자 역할 정의 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ Error creating roles: {e}")
            await session.rollback()
            raise


async def assign_user_permissions():
    """웅진 조직 구조에 맞는 사용자 권한 할당"""
    async with async_session_local() as session:
        try:
            permissions_data = [
                # 시스템 관리자 - 전체 시스템 ADMIN 권한
                {"user_emp_no": "ADMIN001", "container_id": "WJ_ROOT", "role_id": "ADMIN"},
                
                # 본부/사업부 관리자 권한
                {"user_emp_no": "HR001", "container_id": "WJ_CEO", "role_id": "MANAGER"},
                {"user_emp_no": "HR001", "container_id": "WJ_HR", "role_id": "MANAGER"},
                {"user_emp_no": "PLN001", "container_id": "WJ_PLANNING", "role_id": "MANAGER"},
                {"user_emp_no": "CLD001", "container_id": "WJ_CLOUD", "role_id": "MANAGER"},
                {"user_emp_no": "CLD001", "container_id": "WJ_CLOUD_SERVICE", "role_id": "MANAGER"},
                {"user_emp_no": "MSS001", "container_id": "WJ_MS_SERVICE", "role_id": "MANAGER"},
                {"user_emp_no": "INF001", "container_id": "WJ_CTI", "role_id": "MANAGER"},
                {"user_emp_no": "INF001", "container_id": "WJ_INFRA_CONSULT", "role_id": "MANAGER"},
                {"user_emp_no": "BIZ001", "container_id": "WJ_BIZ_OPS1", "role_id": "MANAGER"},
                
                # 팀 단위 EDITOR 권한
                {"user_emp_no": "REC001", "container_id": "WJ_RECRUIT", "role_id": "EDITOR"},
                {"user_emp_no": "TRN001", "container_id": "WJ_TRAINING", "role_id": "EDITOR"},
                
                # 전사 공통 영역 VIEWER 권한
                {"user_emp_no": "HR001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "REC001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "TRN001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "PLN001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "CLD001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "MSS001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "INF001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "BIZ001", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                
                # 부서간 협업을 위한 크로스 권한
                {"user_emp_no": "REC001", "container_id": "WJ_HR", "role_id": "VIEWER"},
                {"user_emp_no": "TRN001", "container_id": "WJ_HR", "role_id": "VIEWER"},
                {"user_emp_no": "CLD001", "container_id": "WJ_INFRA_CONSULT", "role_id": "VIEWER"},
                {"user_emp_no": "INF001", "container_id": "WJ_CLOUD_SERVICE", "role_id": "VIEWER"}
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
                    # 역할에 따른 권한 타입 및 접근 범위 설정
                    permission_type = "FULL_ACCESS" if perm_data["role_id"] == "ADMIN" else "READ_WRITE" if perm_data["role_id"] in ["MANAGER", "EDITOR"] else "READ_ONLY"
                    access_scope = "UNLIMITED" if perm_data["role_id"] == "ADMIN" else "CONTAINER" 
                    permission_source = "ROLE_BASED"
                    granted_by = "ADMIN001"  # 시스템 관리자가 권한 부여
                    
                    await session.execute(
                        text("""
                            INSERT INTO tb_user_permissions (
                                user_emp_no, container_id, role_id, permission_type, 
                                access_scope, permission_source, granted_by,
                                granted_date, is_active, access_count
                            ) VALUES (
                                :user_emp_no, :container_id, :role_id, :permission_type,
                                :access_scope, :permission_source, :granted_by,
                                CURRENT_TIMESTAMP, true, 0
                            )
                        """),
                        {
                            **perm_data,
                            "permission_type": permission_type,
                            "access_scope": access_scope,
                            "permission_source": permission_source,
                            "granted_by": granted_by
                        }
                    )
                    logger.info(f"Assigned: {perm_data['user_emp_no']} -> {perm_data['container_id']} ({perm_data['role_id']}, {permission_type})")
            
            await session.commit()
            logger.info("✅ 사용자 권한 할당 완료")
            
        except Exception as e:
            logger.error(f"❌ Error assigning permissions: {e}")
            await session.rollback()
            raise


# 샘플 문서 생성 함수 제거됨 - 존재하지 않는 더미 파일 생성 방지


async def verify_complete_setup():
    """완전한 설정 검증 및 현황 출력"""
    async with async_session_local() as session:
        try:
            logger.info(f"\n🏢 웅진 WKMS 시스템 설정 검증:")
            
            # SAP HR 정보 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_sap_hr_info"))
            sap_count = result.scalar()
            logger.info(f"   👥 SAP HR 정보: {sap_count}명")
            
            # 사용자 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_user"))
            user_count = result.scalar()
            logger.info(f"   🔐 사용자 계정: {user_count}개")
            
            # 컨테이너 확인
            result = await session.execute(
                text("""
                    SELECT container_type, COUNT(*) as count 
                    FROM tb_knowledge_containers 
                    GROUP BY container_type 
                    ORDER BY count DESC
                """)
            )
            container_stats = result.fetchall()
            logger.info(f"   📁 지식 컨테이너:")
            for stat in container_stats:
                logger.info(f"      {stat.container_type}: {stat.count}개")
            
            # 카테고리 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_knowledge_categories"))
            cat_count = result.scalar()
            logger.info(f"   📚 지식 카테고리: {cat_count}개")
            
            # 역할 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_user_roles"))
            role_count = result.scalar()
            logger.info(f"   🎭 사용자 역할: {role_count}개")
            
            # 권한 할당 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_user_permissions WHERE is_active = true"))
            perm_count = result.scalar()
            logger.info(f"   🔒 권한 할당: {perm_count}개")
            
            # 샘플 문서 확인
            result = await session.execute(text("SELECT COUNT(*) FROM tb_file_bss_info"))
            doc_count = result.scalar()
            logger.info(f"   📄 샘플 문서: {doc_count}개")
            
            # 웅진 조직 구조 출력
            logger.info(f"\n🌲 웅진 조직 구조:")
            result = await session.execute(
                text("""
                    SELECT 
                        container_id, container_name, container_type, 
                        org_level, parent_container_id
                    FROM tb_knowledge_containers 
                    ORDER BY org_level, container_name
                """)
            )
            containers = result.fetchall()
            
            def print_hierarchy(containers, parent_id=None, level=0):
                for container in containers:
                    if container.parent_container_id == parent_id:
                        indent = "│   " * level + ("├── " if level > 0 else "")
                        logger.info(f"   {indent}{container.container_name}")
                        print_hierarchy(containers, container.container_id, level + 1)
            
            print_hierarchy(containers)
            
            # 권한 매트릭스 출력
            logger.info(f"\n🔐 주요 권한 할당 현황:")
            result = await session.execute(
                text("""
                    SELECT 
                        h.emp_nm,
                        h.dept_nm,
                        c.container_name,
                        r.role_name
                    FROM tb_user_permissions p
                    JOIN tb_sap_hr_info h ON p.user_emp_no = h.emp_no
                    JOIN tb_knowledge_containers c ON p.container_id = c.container_id
                    JOIN tb_user_roles r ON p.role_id = r.role_id
                    WHERE p.is_active = true
                      AND c.org_level <= 3
                    ORDER BY h.emp_nm, c.org_level
                """)
            )
            permissions = result.fetchall()
            
            current_user = None
            for perm in permissions:
                if current_user != perm.emp_nm:
                    current_user = perm.emp_nm
                    logger.info(f"   👤 {perm.emp_nm} ({perm.dept_nm})")
                logger.info(f"      └── {perm.container_name}: {perm.role_name}")
                
        except Exception as e:
            logger.error(f"❌ Error during verification: {e}")
            raise


async def main():
    """웅진 WKMS 완전한 초기 데이터 설정 메인 함수"""
    logger.info("🚀 웅진 WKMS 완전한 초기 데이터 설정을 시작합니다...")
    
    try:
        # 1. SAP HR 정보 생성 (조직도 기반)
        logger.info("\n1️⃣ SAP HR 정보 생성 중...")
        await create_sap_hr_info()
        
        # 2. 사용자 계정 생성
        logger.info("\n2️⃣ 사용자 계정 생성 중...")
        await create_users()
        
        # 3. 웅진 조직 구조 기반 지식 컨테이너 생성
        logger.info("\n3️⃣ 웅진 지식 컨테이너 구조 생성 중...")
        await create_woongjin_containers()
        
        # 4. 지식 카테고리 체계 생성
        logger.info("\n4️⃣ 지식 카테고리 체계 생성 중...")
        await create_knowledge_categories()
        
        # 5. 사용자 역할 정의 생성
        logger.info("\n5️⃣ 사용자 역할 정의 생성 중...")
        await create_user_roles()
        
        # 6. 조직 구조에 맞는 권한 할당
        logger.info("\n6️⃣ 사용자 권한 할당 중...")
        await assign_user_permissions()
        
        # 7. 샘플 문서 생성 제거됨 - 존재하지 않는 더미 파일 생성 방지
        logger.info("\n7️⃣ 샘플 문서 생성 건너뜀 (더미 데이터 제거됨)")
        
        # 8. 설정 검증 및 현황 출력
        logger.info("\n8️⃣ 시스템 설정 검증 중...")
        await verify_complete_setup()
        
        logger.info("\n🎉 웅진 WKMS 완전한 초기 데이터 설정이 완료되었습니다!")
        
        logger.info("\n🔑 로그인 정보:")
        logger.info("   🔐 시스템 관리자: admin / admin123!")
        logger.info("   👥 인사팀장: hr.manager / hr123!")
        logger.info("   📋 채용담당: recruit / recruit123!")
        logger.info("   🎓 교육담당: training / training123!")
        logger.info("   📊 기획팀장: planning / planning123!")
        logger.info("   ☁️  클라우드팀장: cloud / cloud123!")
        logger.info("   🖥️  MS서비스팀장: ms.service / ms123!")
        logger.info("   🏗️  인프라팀장: infra / infra123!")
        logger.info("   💼 Biz운영팀장: biz.ops / biz123!")
        
        logger.info("\n🌟 시스템 준비 완료:")
        logger.info("   ✅ 웅진 조직 구조 기반 지식 컨테이너")
        logger.info("   ✅ 계층적 권한 관리 시스템")
        logger.info("   ✅ 역할 기반 접근 제어 (RBAC)")
        logger.info("   ✅ SAP 연동 준비")
        logger.info("   ✅ 지식 카테고리 체계")
        logger.info("   ✅ 샘플 문서 및 메타데이터")
        
        logger.info("\n🔗 다음 단계:")
        logger.info("   1. API 서버 실행 및 테스트")
        logger.info("   2. 프론트엔드 연동")
        logger.info("   3. 파일 업로드 및 벡터 검색 테스트")
        logger.info("   4. SAP 연동 설정")
        
    except Exception as e:
        logger.error(f"❌ Error during complete WKMS setup: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

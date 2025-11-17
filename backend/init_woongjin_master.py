"""Woongjin WKMS Master Initial Data Setup

웅진 WKMS 통합 초기 데이터 설정 스크립트
- 기존 데이터 초기화 및 재설정 기능 포함
- SAP HR 조직구조 기반 완전한 데이터 생성
- 역할 기반 권한 관리 (RBAC) 시스템 구축
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_async_session_local
from app.core.security import AuthUtils
from sqlalchemy import text
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wkms_init.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 비동기 세션 팩토리
async_session_local = get_async_session_local()


async def reset_all_data(confirm: bool = False):
    """모든 기존 데이터 초기화 (기존 데이터가 있을 경우)"""
    if not confirm:
        logger.warning("⚠️  데이터 초기화는 confirm=True로 명시적으로 실행해야 합니다.")
        return False
        
    async with async_session_local() as session:
        try:
            logger.info("🗑️  기존 데이터 초기화 시작...")
            
            # 순서대로 삭제 (외래키 제약 고려)
            tables_to_clear = [
                "tb_user_permissions",
                "tb_user_permission_view",
                "tb_permission_requests",
                "tb_permission_management_info",
                "tb_permission_audit_log",
                "tb_user_roles",
                "tb_knowledge_containers",
                "vs_doc_contents_index",
                "vs_doc_contents_chunks",
                "vs_chat_history_index",
                "tb_chat_feedback",
                "tb_chat_history",
                "tb_chat_sessions",
                "tb_knowledge_access_log",
                "tb_knowledge_sharing_log",
                "tb_search_analytics",
                "tb_file_bss_info",
                "tb_file_dtl_info",
                "tb_knowledge_categories",
                "tb_container_categories",
                "tb_system_settings",
                "tb_user",
                "tb_sap_hr_info",
                "tb_cmns_cd_grp_item"
            ]
            
            for table in tables_to_clear:
                try:
                    # 테이블 존재 확인
                    result = await session.execute(
                        text(f"""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = '{table}'
                            )
                        """)
                    )
                    table_exists = result.scalar()
                    
                    if table_exists:
                        # 데이터 개수 확인
                        result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        
                        if (count or 0) > 0:
                            await session.execute(text(f"DELETE FROM {table}"))
                            logger.info(f"   🧹 {table}: {count}개 레코드 삭제")
                        else:
                            logger.info(f"   ✅ {table}: 이미 비어있음")
                    else:
                        logger.info(f"   ⚠️  {table}: 테이블이 존재하지 않음")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️  {table} 삭제 중 오류 (무시됨): {e}")
            
            await session.commit()
            logger.info("✅ 데이터 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 데이터 초기화 중 오류: {e}")
            await session.rollback()
            return False


async def create_sap_hr_info():
    """SAP HR 정보 생성 - 웅진 조직구조 기반"""
    async with async_session_local() as session:
        try:
            logger.info("👥 SAP HR 정보 생성 중...")
            
            sap_users_data = [
                # 최고 경영진
                {
                    "emp_no": "ADMIN001",
                    "emp_nm": "김관리자",
                    "dept_cd": "CEO000",
                    "dept_nm": "CEO직속",
                    "postn_cd": "CEO001",
                    "postn_nm": "시스템관리자",
                    "email": "admin@woongjin.co.kr",
                    "telno": "02-1234-5678",
                    "entrps_de": "20200101",
                    "emp_stats_cd": "ACTIVE"
                },
                # CEO직속 팀
                {
                    "emp_no": "HR001",
                    "emp_nm": "이인사",
                    "dept_cd": "HR100",
                    "dept_nm": "인사전략팀",
                    "postn_cd": "MGR001",
                    "postn_nm": "팀장",
                    "email": "hr.manager@woongjin.co.kr",
                    "telno": "02-1234-5679",
                    "entrps_de": "20180301",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "REC001",
                    "emp_nm": "박채용",
                    "dept_cd": "HR110",
                    "dept_nm": "채용팀",
                    "postn_cd": "MGR002",
                    "postn_nm": "과장",
                    "email": "recruit@woongjin.co.kr",
                    "telno": "02-1234-5680",
                    "entrps_de": "20190615",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "TRN001",
                    "emp_nm": "최교육",
                    "dept_cd": "HR120",
                    "dept_nm": "교육팀",
                    "postn_cd": "MGR003",
                    "postn_nm": "과장",
                    "email": "training@woongjin.co.kr",
                    "telno": "02-1234-5681",
                    "entrps_de": "20190801",
                    "emp_stats_cd": "ACTIVE"
                },
                {
                    "emp_no": "PLN001",
                    "emp_nm": "정기획",
                    "dept_cd": "PLN100",
                    "dept_nm": "기획팀",
                    "postn_cd": "MGR004",
                    "postn_nm": "팀장",
                    "email": "planning@woongjin.co.kr",
                    "telno": "02-1234-5682",
                    "entrps_de": "20170901",
                    "emp_stats_cd": "ACTIVE"
                },
                # 클라우드사업본부
                {
                    "emp_no": "CLD001",
                    "emp_nm": "김클라우드",
                    "dept_cd": "CLD100",
                    "dept_nm": "클라우드서비스팀",
                    "postn_cd": "MGR005",
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
                    "postn_cd": "MGR006",
                    "postn_nm": "팀장",
                    "email": "ms.service@woongjin.co.kr",
                    "telno": "02-1234-5684",
                    "entrps_de": "20200215",
                    "emp_stats_cd": "ACTIVE"
                },
                # MS서비스팀 일반 팀원 (일반사용자)
                {
                    "emp_no": "77107791",
                    "emp_nm": "홍길동",
                    "dept_cd": "MSS100",
                    "dept_nm": "MS서비스팀",
                    "postn_cd": "MGR006",
                    "postn_nm": "팀원",
                    "email": "ms.staff@woongjin.co.kr",
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
                    "postn_cd": "MGR007",
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
                    "postn_cd": "MGR008",
                    "postn_nm": "팀장",
                    "email": "biz.ops@woongjin.co.kr",
                    "telno": "02-1234-5686",
                    "entrps_de": "20190401",
                    "emp_stats_cd": "ACTIVE"
                }
            ]
            
            for sap_data in sap_users_data:
                # 중복 확인 후 삽입
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_sap_hr_info WHERE emp_no = :emp_no"),
                    {"emp_no": sap_data["emp_no"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_sap_hr_info (
                                emp_no, emp_nm, dept_cd, dept_nm, postn_cd, postn_nm,
                                email, telno, entrps_de, emp_stats_cd, del_yn,
                                created_by, created_date
                            ) VALUES (
                                :emp_no, :emp_nm, :dept_cd, :dept_nm, :postn_cd, :postn_nm,
                                :email, :telno, :entrps_de, :emp_stats_cd, 'N',
                                'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        sap_data
                    )
                    logger.info(f"   ✅ {sap_data['emp_nm']} ({sap_data['dept_nm']})")
            
            await session.commit()
            logger.info("✅ SAP HR 정보 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ SAP HR 정보 생성 오류: {e}")
            await session.rollback()
            raise


async def create_users():
    """사용자 계정 생성"""
    async with async_session_local() as session:
        try:
            logger.info("🔐 사용자 계정 생성 중...")
            
            users_data = [
                {"emp_no": "ADMIN001", "username": "admin", "email": "admin@woongjin.co.kr", "password": "admin123!", "is_admin": True},
                {"emp_no": "HR001", "username": "hr.manager", "email": "hr.manager@woongjin.co.kr", "password": "hr123!", "is_admin": False},
                {"emp_no": "REC001", "username": "recruit", "email": "recruit@woongjin.co.kr", "password": "recruit123!", "is_admin": False},
                {"emp_no": "TRN001", "username": "training", "email": "training@woongjin.co.kr", "password": "training123!", "is_admin": False},
                {"emp_no": "PLN001", "username": "planning", "email": "planning@woongjin.co.kr", "password": "planning123!", "is_admin": False},
                {"emp_no": "CLD001", "username": "cloud", "email": "cloud@woongjin.co.kr", "password": "cloud123!", "is_admin": False},
                {"emp_no": "MSS001", "username": "ms.service", "email": "ms.service@woongjin.co.kr", "password": "ms123!", "is_admin": False},
                {"emp_no": "77107791", "username": "ms.staff", "email": "ms.staff@woongjin.co.kr", "password": "ms123!", "is_admin": False},
                {"emp_no": "INF001", "username": "infra", "email": "infra@woongjin.co.kr", "password": "infra123!", "is_admin": False},
                {"emp_no": "BIZ001", "username": "biz.ops", "email": "biz.ops@woongjin.co.kr", "password": "biz123!", "is_admin": False}
            ]
            
            for user_data in users_data:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_user WHERE username = :username"),
                    {"username": user_data["username"]}
                )
                count = result.scalar()
                
                if count == 0:
                    password_hash = AuthUtils.get_password_hash(user_data["password"])
                    
                    await session.execute(
                        text("""
                            INSERT INTO tb_user (
                                emp_no, username, email, password_hash, is_active, is_admin,
                                failed_login_attempts, created_date, last_modified_date
                            )
                            VALUES (
                                :emp_no, :username, :email, :password_hash, :is_active, :is_admin,
                                0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                            )
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
                    role = "시스템관리자" if user_data["is_admin"] else "일반사용자"
                    logger.info(f"   ✅ {user_data['username']} ({role})")
            
            await session.commit()
            logger.info("✅ 사용자 계정 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ 사용자 계정 생성 오류: {e}")
            await session.rollback()
            raise


async def create_woongjin_containers():
    """웅진 조직구조 기반 지식 컨테이너 생성"""
    async with async_session_local() as session:
        try:
            logger.info("📁 웅진 지식 컨테이너 구조 생성 중...")
            
            containers_data = [
                # 1. 웅진 최상위 컨테이너 (COMPANY 레벨)
                {
                    "container_id": "WJ_ROOT",
                    "container_name": "웅진",
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
                    "container_name": "CEO직속",
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
                # 3-4. 사업본부들
                {
                    "container_id": "WJ_CLOUD",
                    "container_name": "클라우드사업본부",
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
                {
                    "container_id": "WJ_CTI",
                    "container_name": "CTI사업본부",
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
                # 5-6. CEO직속 팀들 (DEPARTMENT 레벨)
                {
                    "container_id": "WJ_HR",
                    "container_name": "인사전략팀",
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
                {
                    "container_id": "WJ_PLANNING",
                    "container_name": "기획팀",
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
                # 7-8. 클라우드사업본부 팀들
                {
                    "container_id": "WJ_CLOUD_SERVICE",
                    "container_name": "클라우드서비스팀",
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
                {
                    "container_id": "WJ_MS_SERVICE",
                    "container_name": "MS서비스팀",
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
                # 9-10. CTI사업본부 팀들
                {
                    "container_id": "WJ_INFRA_CONSULT",
                    "container_name": "인프라컨설팅팀",
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
                {
                    "container_id": "WJ_BIZ_OPS1",
                    "container_name": "Biz운영1팀",
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
                # 11-12. 하위 팀들 (TEAM 레벨)
                {
                    "container_id": "WJ_RECRUIT",
                    "container_name": "채용팀",
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
                {
                    "container_id": "WJ_TRAINING",
                    "container_name": "교육팀",
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
                    logger.info(f"   {level_indent}✅ {container_data['container_name']}")
            
            await session.commit()
            logger.info("✅ 웅진 지식 컨테이너 구조 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ 지식 컨테이너 생성 오류: {e}")
            await session.rollback()
            raise


async def create_knowledge_categories():
    """지식 카테고리 체계 생성"""
    async with async_session_local() as session:
        try:
            logger.info("📚 지식 카테고리 체계 생성 중...")
            
            categories_data = [
                {
                    "category_id": "HR",
                    "category_name": "인사관리",
                    "category_description": "인사 관련 정책 및 절차",
                    "parent_category_id": None,
                    "category_level": 1,
                    "sort_order": 1
                },
                {
                    "category_id": "TECH",
                    "category_name": "기술문서",
                    "category_description": "기술 관련 문서 및 매뉴얼",
                    "parent_category_id": None,
                    "category_level": 1,
                    "sort_order": 2
                },
                {
                    "category_id": "BUSINESS",
                    "category_name": "업무매뉴얼",
                    "category_description": "업무 프로세스 및 매뉴얼",
                    "parent_category_id": None,
                    "category_level": 1,
                    "sort_order": 3
                },
                {
                    "category_id": "PLANNING",
                    "category_name": "기획자료",
                    "category_description": "전략 기획 및 사업 계획",
                    "parent_category_id": None,
                    "category_level": 1,
                    "sort_order": 4
                }
            ]
            
            for cat_data in categories_data:
                result = await session.execute(
                    text("SELECT category_id FROM tb_knowledge_categories WHERE category_id = :category_id"),
                    {"category_id": cat_data["category_id"]}
                )
                existing = result.fetchone()
                
                if not existing:
                    result = await session.execute(
                        text("""
                            INSERT INTO tb_knowledge_categories (
                                category_id, category_name, parent_category_id, category_description,
                                category_level, sort_order, is_active, document_count, created_date
                            ) VALUES (
                                :category_id, :category_name, :parent_category_id, :category_description,
                                :category_level, :sort_order, true, 0, CURRENT_TIMESTAMP
                            )
                        """),
                        cat_data
                    )
                    logger.info(f"   ✅ {cat_data['category_name']} (ID: {cat_data['category_id']})")
            
            await session.commit()
            logger.info("✅ 지식 카테고리 체계 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ 지식 카테고리 생성 오류: {e}")
            await session.rollback()
            raise


async def create_user_roles():
    """사용자 역할 정의 생성"""
    async with async_session_local() as session:
        try:
            logger.info("🎭 사용자 역할 정의 생성 중...")
            
            roles_data = [
                {
                    "user_emp_no": "ADMIN001", 
                    "role_name": "시스템관리자", 
                    "role_level": 1, 
                    "scope_type": "GLOBAL", 
                    "scope_value": "ALL",
                    "role_description": "시스템 전체 관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                {
                    "user_emp_no": "HR001", 
                    "role_name": "인사팀관리자", 
                    "role_level": 2, 
                    "scope_type": "DEPARTMENT", 
                    "scope_value": "HR",
                    "role_description": "인사팀 관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                {
                    "user_emp_no": "PLN001", 
                    "role_name": "기획팀관리자", 
                    "role_level": 2, 
                    "scope_type": "DEPARTMENT", 
                    "scope_value": "PLANNING",
                    "role_description": "기획팀 관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                # 추가된 지식관리자 역할들
                {
                    "user_emp_no": "REC001", 
                    "role_name": "채용팀관리자", 
                    "role_level": 3, 
                    "scope_type": "TEAM", 
                    "scope_value": "RECRUIT",
                    "role_description": "채용팀 지식관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                {
                    "user_emp_no": "TRN001", 
                    "role_name": "교육팀관리자", 
                    "role_level": 3, 
                    "scope_type": "TEAM", 
                    "scope_value": "TRAINING",
                    "role_description": "교육팀 지식관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                {
                    "user_emp_no": "CLD001", 
                    "role_name": "클라우드팀관리자", 
                    "role_level": 2, 
                    "scope_type": "DEPARTMENT", 
                    "scope_value": "CLOUD",
                    "role_description": "클라우드사업본부 지식관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                {
                    "user_emp_no": "MSS001", 
                    "role_name": "MS서비스팀관리자", 
                    "role_level": 3, 
                    "scope_type": "DEPARTMENT", 
                    "scope_value": "MS_SERVICE",
                    "role_description": "MS서비스팀 지식관리 권한",
                    "is_active": True,
                    "approval_required": False
                },
                # 일반 사용자 (MS서비스팀 구성원) - 조회 중심 권한 정의
                {
                    "user_emp_no": "77107791",
                    "role_name": "MS서비스팀구성원",
                    "role_level": 5,
                    "scope_type": "DEPARTMENT",
                    "scope_value": "MS_SERVICE",
                    "role_description": "MS서비스팀 일반 사용자 (조회 권한 중심)",
                    "is_active": True,
                    "approval_required": False
                }
            ]
            
            for role_data in roles_data:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tb_user_roles WHERE user_emp_no = :user_emp_no AND role_name = :role_name"),
                    {"user_emp_no": role_data["user_emp_no"], "role_name": role_data["role_name"]}
                )
                count = result.scalar()
                
                if count == 0:
                    await session.execute(
                        text("""
                            INSERT INTO tb_user_roles (
                                user_emp_no, role_name, role_level, scope_type, scope_value,
                                role_description, is_active, approval_required, 
                                created_by, created_date
                            ) VALUES (
                                :user_emp_no, :role_name, :role_level, :scope_type, :scope_value,
                                :role_description, :is_active, :approval_required,
                                'SYSTEM', CURRENT_TIMESTAMP
                            )
                        """),
                        role_data
                    )
                    logger.info(f"   ✅ {role_data['role_name']} (사원: {role_data['user_emp_no']})")
            
            await session.commit()
            logger.info("✅ 사용자 역할 정의 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ 사용자 역할 생성 오류: {e}")
            await session.rollback()
            raise


async def assign_user_permissions():
    """웅진 조직구조에 맞는 사용자 권한 할당
    
    권한 할당 원칙:
    1. 같은 팀 구성원들은 동일한 컨테이너 트리를 볼 수 있어야 함
    2. 팀장은 MANAGER, 팀원은 EDITOR 권한으로 역할 구분
    3. 상위 조직 컨테이너에 대한 VIEWER 권한으로 계층 구조 표시
    4. 교차 부서 협업을 위한 선택적 크로스 권한 부여
    """
    async with async_session_local() as session:
        try:
            logger.info("🔒 사용자 권한 할당 중...")
            
            permissions_data = [
                # 시스템 관리자 - 전체 시스템 ADMIN 권한
                {"user_emp_no": "ADMIN001", "container_id": "WJ_ROOT", "role_id": "ADMIN"},
                
                # 본부/사업부 관리자 권한 (지식관리자)
                {"user_emp_no": "HR001", "container_id": "WJ_CEO", "role_id": "MANAGER"},
                {"user_emp_no": "HR001", "container_id": "WJ_HR", "role_id": "MANAGER"},
                {"user_emp_no": "PLN001", "container_id": "WJ_PLANNING", "role_id": "MANAGER"},
                {"user_emp_no": "CLD001", "container_id": "WJ_CLOUD", "role_id": "MANAGER"},
                {"user_emp_no": "CLD001", "container_id": "WJ_CLOUD_SERVICE", "role_id": "MANAGER"},
                {"user_emp_no": "MSS001", "container_id": "WJ_MS_SERVICE", "role_id": "MANAGER"},
                {"user_emp_no": "INF001", "container_id": "WJ_CTI", "role_id": "MANAGER"},
                {"user_emp_no": "INF001", "container_id": "WJ_INFRA_CONSULT", "role_id": "MANAGER"},
                {"user_emp_no": "BIZ001", "container_id": "WJ_BIZ_OPS1", "role_id": "MANAGER"},
                
                # 팀 단위 지식관리자 권한 (EDITOR에서 MANAGER로 업그레이드)
                {"user_emp_no": "REC001", "container_id": "WJ_RECRUIT", "role_id": "MANAGER"},
                {"user_emp_no": "TRN001", "container_id": "WJ_TRAINING", "role_id": "MANAGER"},
                
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
                {"user_emp_no": "INF001", "container_id": "WJ_CLOUD_SERVICE", "role_id": "VIEWER"},
                
                # MS서비스팀 팀장(MSS001) 계층별 권한 부여 - 같은 팀원과 동일한 트리 구조
                {"user_emp_no": "MSS001", "container_id": "WJ_CLOUD", "role_id": "VIEWER"},
                {"user_emp_no": "MSS001", "container_id": "WJ_CLOUD_SERVICE", "role_id": "VIEWER"},
                
                # MS서비스팀 일반사원(77107791) 계층별 권한 부여 (최종 소속: MS서비스팀)
                {"user_emp_no": "77107791", "container_id": "WJ_ROOT", "role_id": "VIEWER"},
                {"user_emp_no": "77107791", "container_id": "WJ_CLOUD", "role_id": "VIEWER"},
                {"user_emp_no": "77107791", "container_id": "WJ_CLOUD_SERVICE", "role_id": "VIEWER"},
                {"user_emp_no": "77107791", "container_id": "WJ_MS_SERVICE", "role_id": "EDITOR"}  # 소속 부서는 편집 권한
            ]
            
            for perm_data in permissions_data:
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
                    permission_type = "FULL_ACCESS" if perm_data["role_id"] == "ADMIN" else "read_write" if perm_data["role_id"] in ["MANAGER", "EDITOR"] else "read_ONLY"
                    access_scope = "UNLIMITED" if perm_data["role_id"] == "ADMIN" else "CONTAINER"
                    
                    await session.execute(
                        text("""
                            INSERT INTO tb_user_permissions (
                                user_emp_no, container_id, role_id, permission_type, 
                                access_scope, permission_source, granted_by,
                                granted_date, is_active, access_count
                            ) VALUES (
                                :user_emp_no, :container_id, :role_id, :permission_type,
                                :access_scope, 'ROLE_BASED', 'ADMIN001',
                                CURRENT_TIMESTAMP, true, 0
                            )
                        """),
                        {
                            **perm_data,
                            "permission_type": permission_type,
                            "access_scope": access_scope
                        }
                    )
                    logger.info(f"   ✅ {perm_data['user_emp_no']} → {perm_data['container_id']} ({perm_data['role_id']})")
            
            await session.commit()
            logger.info("✅ 사용자 권한 할당 완료")
            
            # 같은 팀 구성원들의 권한 일관성 검증
            await validate_team_permissions(session)
            
        except Exception as e:
            logger.error(f"❌ 사용자 권한 할당 오류: {e}")
            await session.rollback()
            raise


async def validate_team_permissions(session):
    """같은 팀 구성원들의 권한 일관성 검증"""
    try:
        logger.info("🔍 팀별 권한 일관성 검증 중...")
        
        # 중요한 팀들의 구성원 정의
        critical_teams = {
            'MS서비스팀': ['MSS001', '77107791']  # 팀장과 팀원이 동일한 트리를 봐야 함
        }
        
        for team_name, members in critical_teams.items():
            logger.info(f"   🏢 {team_name} 검증 중...")
            
            # 각 구성원의 컨테이너 접근 권한 조회
            member_containers = {}
            for member in members:
                result = await session.execute(
                    text("""
                        SELECT container_id FROM tb_user_permissions 
                        WHERE user_emp_no = :emp_no AND is_active = true
                        ORDER BY container_id
                    """),
                    {"emp_no": member}
                )
                containers = [row.container_id for row in result.fetchall()]
                member_containers[member] = set(containers)
            
            # 권한 일관성 확인
            if len(set(str(containers) for containers in member_containers.values())) == 1:
                logger.info(f"   ✅ {team_name} 구성원들의 컨테이너 접근 권한이 일치합니다.")
            else:
                logger.warning(f"   ⚠️  {team_name} 구성원들의 컨테이너 접근 권한이 다릅니다:")
                for member, containers in member_containers.items():
                    logger.warning(f"      {member}: {sorted(containers)}")
                    
    except Exception as e:
        logger.error(f"❌ 팀 권한 검증 오류: {e}")


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
            
            return True
                
        except Exception as e:
            logger.error(f"❌ 검증 중 오류: {e}")
            return False


async def main(reset_data: bool = False):
    """웅진 WKMS 마스터 초기 데이터 설정 메인 함수"""
    logger.info("🚀 웅진 WKMS 마스터 초기 데이터 설정을 시작합니다...")
    
    try:
        # 1. 기존 데이터 초기화 (선택사항)
        if reset_data:
            logger.info("\n0️⃣ 기존 데이터 초기화 중...")
            reset_success = await reset_all_data(confirm=True)
            if not reset_success:
                logger.error("❌ 데이터 초기화 실패. 작업을 중단합니다.")
                return
        
        # 2. SAP HR 정보 생성
        logger.info("\n1️⃣ SAP HR 정보 생성 중...")
        await create_sap_hr_info()
        
        # 3. 사용자 계정 생성
        logger.info("\n2️⃣ 사용자 계정 생성 중...")
        await create_users()
        
        # 4. 웅진 조직 구조 기반 지식 컨테이너 생성
        logger.info("\n3️⃣ 웅진 지식 컨테이너 구조 생성 중...")
        await create_woongjin_containers()
        
        # 5. 지식 카테고리 체계 생성
        logger.info("\n4️⃣ 지식 카테고리 체계 생성 중...")
        await create_knowledge_categories()
        
        # 6. 사용자 역할 정의 생성
        logger.info("\n5️⃣ 사용자 역할 정의 생성 중...")
        await create_user_roles()
        
        # 7. 조직 구조에 맞는 권한 할당
        logger.info("\n6️⃣ 사용자 권한 할당 중...")
        await assign_user_permissions()
        
        # 8. 샘플 문서 생성 제거됨 - 존재하지 않는 더미 파일 생성 방지
        logger.info("\n7️⃣ 샘플 문서 생성 건너뜀 (더미 데이터 제거됨)")
        
        # 9. 설정 검증 및 현황 출력
        logger.info("\n8️⃣ 시스템 설정 검증 중...")
        verify_success = await verify_complete_setup()
        
        if verify_success:
            logger.info("\n🎉 웅진 WKMS 마스터 초기 데이터 설정이 완료되었습니다!")
            
            logger.info("\n🔑 로그인 정보:")
            logger.info("   🔐 시스템 관리자: admin / admin123!")
            logger.info("   👥 인사팀장(지식관리자): hr.manager / hr123!")
            logger.info("   📋 채용담당(지식관리자): recruit / recruit123!")
            logger.info("   🎓 교육담당(지식관리자): training / training123!")
            logger.info("   📊 기획팀장(지식관리자): planning / planning123!")
            logger.info("   ☁️  클라우드팀장(지식관리자): cloud / cloud123!")
            logger.info("   🖥️  MS서비스팀장(지식관리자): ms.service / ms123!")
            logger.info("   🏗️  인프라팀장: infra / infra123!")
            logger.info("   💼 Biz운영팀장: biz.ops / biz123!")
            
            logger.info("\n🌟 시스템 준비 완료:")
            logger.info("   ✅ 웅진 조직 구조 기반 지식 컨테이너")
            logger.info("   ✅ 계층적 권한 관리 시스템 (RBAC)")
            logger.info("   ✅ 지식관리자 역할 정의 및 권한 할당")
            logger.info("   ✅ SAP HR 연동 준비")
            logger.info("   ✅ 지식 카테고리 체계")
            logger.info("   ✅ 샘플 문서 및 메타데이터")
            
            logger.info("\n🔗 다음 단계:")
            logger.info("   1. FastAPI 서버 실행: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
            logger.info("   2. API 문서 확인: http://localhost:8000/docs")
            logger.info("   3. 프론트엔드 연동 테스트")
            logger.info("   4. 파일 업로드 및 벡터 검색 테스트")
        else:
            logger.error("❌ 설정 검증 실패")
        
    except Exception as e:
        logger.error(f"❌ 웅진 WKMS 설정 중 오류: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='웅진 WKMS 마스터 초기 데이터 설정')
    parser.add_argument('--reset', action='store_true', 
                       help='기존 데이터를 초기화하고 새로 설정 (주의: 모든 데이터가 삭제됩니다)')
    
    args = parser.parse_args()
    
    if args.reset:
        confirm = input("⚠️  모든 기존 데이터가 삭제됩니다. 계속하시겠습니까? (yes/no): ")
        if confirm.lower() != 'yes':
            print("작업이 취소되었습니다.")
            sys.exit(0)
    
    asyncio.run(main(reset_data=args.reset))

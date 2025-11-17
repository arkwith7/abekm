"""
초기 데이터 적재 준비 상태 검증 스크립트

CSV 파일과 모델 스키마가 일치하는지, 필수 데이터가 존재하는지 검증합니다.
"""
import sys
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple
import logging

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.models.auth.user_models import User, TbSapHrInfo
from app.models.core.system_models import (
    TbCmnsCdGrpItem,
    TbKnowledgeCategories,
    TbContainerCategories,
    TbSystemSettings
)
from app.models.auth.permission_models import (
    TbKnowledgeContainers,
    TbUserRoles,
    TbUserPermissions
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SeedDataValidator:
    """초기 데이터 검증 클래스"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "csv"
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate_all(self) -> bool:
        """모든 검증을 수행합니다."""
        logger.info("=" * 70)
        logger.info("🔍 WKMS 초기 데이터 검증 시작")
        logger.info("=" * 70)
        
        # 1. CSV 파일 존재 확인
        logger.info("\n📁 1단계: CSV 파일 존재 여부 확인")
        csv_exists = self._check_csv_files_exist()
        
        # 2. CSV 파일 구조 검증
        logger.info("\n📋 2단계: CSV 파일 구조 검증")
        structure_valid = self._validate_csv_structures()
        
        # 3. 데이터 정합성 검증
        logger.info("\n🔗 3단계: 데이터 정합성 검증")
        integrity_valid = self._validate_data_integrity()
        
        # 4. 필수 데이터 존재 확인
        logger.info("\n✅ 4단계: 필수 데이터 존재 확인")
        required_data_valid = self._validate_required_data()
        
        # 5. Seeder 코드 검증
        logger.info("\n💻 5단계: Seeder 코드 검증")
        seeder_valid = self._validate_seeder_code()
        
        # 결과 요약
        self._print_summary()
        
        return (csv_exists and structure_valid and 
                integrity_valid and required_data_valid and seeder_valid)
    
    def _check_csv_files_exist(self) -> bool:
        """CSV 파일 존재 여부 확인"""
        required_files = {
            "common_codes.csv": "공통 코드",
            "categories.csv": "지식 카테고리",
            "sap_hr_info.csv": "SAP HR 정보",
            "users.csv": "사용자",
            "knowledge_containers.csv": "지식 컨테이너",
            "user_roles.csv": "사용자 역할",
            "user_permissions.csv": "사용자 권한"
        }
        
        all_exist = True
        for filename, description in required_files.items():
            filepath = self.data_dir / filename
            if filepath.exists():
                logger.info(f"   ✅ {description}: {filename}")
            else:
                logger.error(f"   ❌ {description}: {filename} 없음!")
                self.errors.append(f"필수 파일 누락: {filename}")
                all_exist = False
        
        return all_exist
    
    def _validate_csv_structures(self) -> bool:
        """CSV 파일 구조가 모델과 일치하는지 검증"""
        validations = [
            ("common_codes.csv", TbCmnsCdGrpItem, {
                'grp_cd', 'item_cd', 'item_nm', 'item_desc', 
                'sort_ord', 'use_yn', 'created_by', 'created_date'
            }),
            ("categories.csv", TbKnowledgeCategories, {
                'category_id', 'category_name', 'category_description',
                'parent_category_id', 'category_level', 'category_path',
                'sort_order', 'is_active', 'created_by', 'created_date'
            }),
            ("sap_hr_info.csv", TbSapHrInfo, {
                'emp_no', 'emp_nm', 'dept_cd', 'dept_nm',
                'postn_cd', 'postn_nm', 'email', 'telno',
                'entrps_de', 'emp_stats_cd', 'del_yn'
            }),
            ("users.csv", User, {
                'emp_no', 'username', 'email', 'password_hash',
                'is_active', 'is_admin', 'failed_login_attempts', 'created_date'
            }),
            ("knowledge_containers.csv", TbKnowledgeContainers, {
                'container_id', 'container_name', 'container_description',
                'owner_emp_no', 'dept_cd', 'is_active'
            }),
            ("user_roles.csv", TbUserRoles, {
                'emp_no', 'role_name', 'container_id',
                'is_active', 'created_by', 'created_date'
            }),
            ("user_permissions.csv", TbUserPermissions, {
                'emp_no', 'container_id', 'permission_type',
                'is_granted', 'created_by', 'created_date'
            })
        ]
        
        all_valid = True
        for csv_file, model_class, expected_columns in validations:
            filepath = self.data_dir / csv_file
            if not filepath.exists():
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    csv_columns = set(reader.fieldnames or [])
                
                # 필수 컬럼 확인
                missing = expected_columns - csv_columns
                extra = csv_columns - expected_columns
                
                if missing:
                    logger.error(f"   ❌ {csv_file}: 누락된 컬럼 {missing}")
                    self.errors.append(f"{csv_file}: 누락된 컬럼 {missing}")
                    all_valid = False
                elif extra:
                    logger.warning(f"   ⚠️  {csv_file}: 추가 컬럼 {extra} (무시됨)")
                    self.warnings.append(f"{csv_file}: 추가 컬럼 {extra}")
                else:
                    logger.info(f"   ✅ {csv_file}: 스키마 일치")
                    
            except Exception as e:
                logger.error(f"   ❌ {csv_file}: 읽기 오류 - {e}")
                self.errors.append(f"{csv_file}: {e}")
                all_valid = False
        
        return all_valid
    
    def _validate_data_integrity(self) -> bool:
        """데이터 정합성 검증 (외래키 관계 등)"""
        all_valid = True
        
        # 1. users.csv의 emp_no가 sap_hr_info.csv에 존재하는지 확인
        try:
            sap_emp_nos = self._read_column("sap_hr_info.csv", "emp_no")
            user_emp_nos = self._read_column("users.csv", "emp_no")
            
            missing_hr = user_emp_nos - sap_emp_nos
            if missing_hr:
                logger.error(f"   ❌ users.csv: SAP HR 정보 없는 사번 {missing_hr}")
                self.errors.append(f"users.csv: SAP HR 누락 {missing_hr}")
                all_valid = False
            else:
                logger.info(f"   ✅ 사용자-HR 정보 연결: {len(user_emp_nos)}개 일치")
        
        except Exception as e:
            logger.error(f"   ❌ 사용자-HR 정합성 검증 실패: {e}")
            all_valid = False
        
        # 2. knowledge_containers.csv의 owner_emp_no가 users.csv에 존재하는지
        try:
            container_owners = self._read_column("knowledge_containers.csv", "owner_emp_no")
            missing_owners = container_owners - user_emp_nos
            
            if missing_owners:
                logger.error(f"   ❌ knowledge_containers.csv: 없는 소유자 {missing_owners}")
                self.errors.append(f"컨테이너: 없는 소유자 {missing_owners}")
                all_valid = False
            else:
                logger.info(f"   ✅ 컨테이너 소유자: {len(container_owners)}개 일치")
        
        except Exception as e:
            logger.error(f"   ❌ 컨테이너 정합성 검증 실패: {e}")
            all_valid = False
        
        # 3. user_roles.csv와 user_permissions.csv의 emp_no 확인
        try:
            role_emp_nos = self._read_column("user_roles.csv", "emp_no")
            perm_emp_nos = self._read_column("user_permissions.csv", "emp_no")
            
            missing_role_users = role_emp_nos - user_emp_nos
            missing_perm_users = perm_emp_nos - user_emp_nos
            
            if missing_role_users:
                logger.error(f"   ❌ user_roles.csv: 없는 사용자 {missing_role_users}")
                self.errors.append(f"역할: 없는 사용자 {missing_role_users}")
                all_valid = False
            
            if missing_perm_users:
                logger.error(f"   ❌ user_permissions.csv: 없는 사용자 {missing_perm_users}")
                self.errors.append(f"권한: 없는 사용자 {missing_perm_users}")
                all_valid = False
            
            if not missing_role_users and not missing_perm_users:
                logger.info(f"   ✅ 역할/권한 사용자: 모두 일치")
        
        except Exception as e:
            logger.error(f"   ❌ 역할/권한 정합성 검증 실패: {e}")
            all_valid = False
        
        return all_valid
    
    def _validate_required_data(self) -> bool:
        """필수 데이터 존재 확인"""
        all_valid = True
        
        # 1. 관리자 계정 존재 확인
        try:
            with open(self.data_dir / "users.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                admin_count = sum(1 for row in reader if row.get('is_admin', '').lower() == 'true')
            
            if admin_count == 0:
                logger.error("   ❌ 관리자 계정이 없습니다!")
                self.errors.append("관리자 계정 누락")
                all_valid = False
            else:
                logger.info(f"   ✅ 관리자 계정: {admin_count}개")
        
        except Exception as e:
            logger.error(f"   ❌ 관리자 확인 실패: {e}")
            all_valid = False
        
        # 2. 최소 1개 이상의 컨테이너 존재
        try:
            container_count = len(self._read_column("knowledge_containers.csv", "container_id"))
            if container_count == 0:
                logger.warning("   ⚠️  지식 컨테이너가 없습니다.")
                self.warnings.append("컨테이너 없음")
            else:
                logger.info(f"   ✅ 지식 컨테이너: {container_count}개")
        
        except Exception as e:
            logger.error(f"   ❌ 컨테이너 확인 실패: {e}")
            all_valid = False
        
        return all_valid
    
    def _validate_seeder_code(self) -> bool:
        """Seeder 코드 파일 존재 및 기본 구조 검증"""
        seeder_dir = Path(__file__).parent
        required_seeders = [
            "system_seeder.py",
            "hr_seeder.py",
            "user_seeder.py",
            "container_seeder.py",
            "permission_seeder.py",
            "run_all_seeders.py"
        ]
        
        all_exist = True
        for seeder_file in required_seeders:
            filepath = seeder_dir / seeder_file
            if filepath.exists():
                logger.info(f"   ✅ {seeder_file}")
            else:
                logger.error(f"   ❌ {seeder_file} 없음!")
                self.errors.append(f"Seeder 파일 누락: {seeder_file}")
                all_exist = False
        
        return all_exist
    
    def _read_column(self, csv_file: str, column_name: str) -> Set[str]:
        """CSV 파일에서 특정 컬럼의 모든 값을 읽어옵니다."""
        filepath = self.data_dir / csv_file
        values = set()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                value = row.get(column_name, '').strip()
                if value:
                    values.add(value)
        
        return values
    
    def _print_summary(self):
        """검증 결과 요약 출력"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 검증 결과 요약")
        logger.info("=" * 70)
        
        if not self.errors and not self.warnings:
            logger.info("🎉 모든 검증 통과! 초기 데이터 적재 준비 완료")
            logger.info("\n다음 명령어로 초기 데이터를 적재할 수 있습니다:")
            logger.info("cd /home/wjadmin/Dev/InsightBridge/backend")
            logger.info("source ../.venv/bin/activate")
            logger.info("WKMS_AUTO_SEED=true python data/seeds/run_all_seeders.py")
        else:
            if self.errors:
                logger.error(f"\n❌ 오류 {len(self.errors)}개:")
                for error in self.errors:
                    logger.error(f"   • {error}")
            
            if self.warnings:
                logger.warning(f"\n⚠️  경고 {len(self.warnings)}개:")
                for warning in self.warnings:
                    logger.warning(f"   • {warning}")
        
        logger.info("=" * 70)


def main():
    """메인 실행 함수"""
    validator = SeedDataValidator()
    success = validator.validate_all()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

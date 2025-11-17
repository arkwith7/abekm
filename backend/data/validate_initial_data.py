#!/usr/bin/env python3
"""
초기 데이터 검증 및 수정 스크립트

목적:
1. CSV 파일과 모델 스키마 일치성 검증
2. 컨테이너 트리 구조 정합성 검증
3. ADMIN001 권한 완전성 검증 및 수정
4. 모든 검증 통과 후 데이터 적재
"""
import sys
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class InitialDataValidator:
    """초기 데이터 검증기"""
    
    def __init__(self):
        self.csv_dir = Path(__file__).parent / "csv"
        self.errors = []
        self.warnings = []
        self.containers = []
        self.permissions = []
        self.users = []
        self.sap_hr = []
        self.user_roles = []
        
        # SAP 조직 코드 → 컨테이너 ID 매핑
        self.org_to_container_map = {
            'CEO000': 'WJ_CEO',
            'HR100': 'WJ_HR',
            'HR110': 'WJ_RECRUIT',
            'HR120': 'WJ_TRAINING',
            'PLN100': 'WJ_PLANNING',
            'CLD100': 'WJ_CLOUD_SERVICE',
            'MSS100': 'WJ_MS_SERVICE',
            'INF100': 'WJ_INFRA_CONSULT',
            'BIZ100': 'WJ_BIZ_OPS1',
            'WJ200': 'WJ_CLOUD',  # 사업본부
            'WJ300': 'WJ_CTI',    # 사업본부
        }
        
    def load_csv(self, filename: str) -> List[Dict]:
        """CSV 파일 로드"""
        csv_path = self.csv_dir / filename
        if not csv_path.exists():
            self.errors.append(f"❌ CSV 파일 없음: {filename}")
            return []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    
    def validate_containers_tree(self) -> bool:
        """컨테이너 트리 구조 검증"""
        print("\n🌲 컨테이너 트리 구조 검증 중...")
        
        self.containers = self.load_csv("knowledge_containers.csv")
        if not self.containers:
            return False
        
        # 1. 필수 컨테이너 확인
        container_ids = {c['container_id'] for c in self.containers}
        required_containers = {
            'WJ_ROOT', 'WJ_CEO', 'WJ_CLOUD', 'WJ_CTI',
            'WJ_HR', 'WJ_PLANNING', 'WJ_CLOUD_SERVICE', 'WJ_MS_SERVICE',
            'WJ_INFRA_CONSULT', 'WJ_BIZ_OPS1', 'WJ_RECRUIT', 'WJ_TRAINING'
        }
        
        missing = required_containers - container_ids
        if missing:
            self.errors.append(f"❌ 필수 컨테이너 누락: {missing}")
            return False
        
        print(f"   ✅ 필수 컨테이너 12개 모두 존재")
        
        # 2. 트리 구조 검증 (parent_container_id 참조 무결성)
        parent_refs = {c['parent_container_id'] for c in self.containers if c['parent_container_id']}
        invalid_parents = parent_refs - container_ids
        
        if invalid_parents:
            self.errors.append(f"❌ 잘못된 parent_container_id: {invalid_parents}")
            return False
        
        print(f"   ✅ 부모 컨테이너 참조 무결성 통과")
        
        # 3. 계층 구조 검증 (org_level)
        hierarchy_map = {}
        for c in self.containers:
            level = int(c['org_level'])
            path = c['org_path']
            hierarchy_map[c['container_id']] = {'level': level, 'path': path}
            
            # 경로 깊이와 레벨 일치 검증
            expected_level = path.count('/') 
            if expected_level != level:
                self.errors.append(
                    f"❌ {c['container_id']}: org_level({level})과 org_path 깊이({expected_level}) 불일치"
                )
        
        if self.errors:
            return False
        
        print(f"   ✅ 계층 구조(org_level, org_path) 일치성 통과")
        
        # 4. 트리 시각화
        self._print_tree_structure()
        
        return True
    
    def _print_tree_structure(self):
        """트리 구조 시각화"""
        print("\n📊 컨테이너 트리 구조:")
        
        # 레벨별로 그룹화
        by_level = {}
        for c in self.containers:
            level = int(c['org_level'])
            if level not in by_level:
                by_level[level] = []
            by_level[level].append(c)
        
        # 재귀적으로 출력
        def print_node(container_id, indent=0):
            container = next((c for c in self.containers if c['container_id'] == container_id), None)
            if not container:
                return
            
            prefix = "   " * indent + ("└── " if indent > 0 else "")
            print(f"{prefix}{container['container_name']} ({container_id}) [{container['container_type']}]")
            
            # 자식 찾기
            children = [c for c in self.containers if c['parent_container_id'] == container_id]
            for child in sorted(children, key=lambda x: x['org_level']):
                print_node(child['container_id'], indent + 1)
        
        print_node('WJ_ROOT')
    
    def validate_admin_permissions(self) -> bool:
        """ADMIN001 권한 완전성 검증"""
        print("\n🔐 ADMIN001 권한 검증 중...")
        
        self.permissions = self.load_csv("user_permissions.csv")
        if not self.permissions:
            return False
        
        # ADMIN001의 권한 확인
        admin_perms = [p for p in self.permissions if p['user_emp_no'] == 'ADMIN001']
        admin_containers = {p['container_id'] for p in admin_perms}
        
        print(f"   📋 현재 ADMIN001 권한이 있는 컨테이너: {len(admin_containers)}개")
        print(f"      {admin_containers}")
        
        # 모든 컨테이너 ID
        all_containers = {c['container_id'] for c in self.containers}
        
        # 누락된 컨테이너
        missing_containers = all_containers - admin_containers
        
        if missing_containers:
            self.warnings.append(
                f"⚠️  ADMIN001에게 권한이 없는 컨테이너: {missing_containers}"
            )
            print(f"   ⚠️  권한 누락 컨테이너: {len(missing_containers)}개")
            print(f"      {missing_containers}")
            return False
        
        # 권한 타입 검증 (ADMIN이어야 함)
        for perm in admin_perms:
            if perm['permission_type'] != 'ADMIN':
                self.warnings.append(
                    f"⚠️  {perm['container_id']}: ADMIN001의 권한이 ADMIN이 아님 ({perm['permission_type']})"
                )
        
        if not self.warnings:
            print(f"   ✅ ADMIN001이 모든 컨테이너({len(all_containers)}개)에 ADMIN 권한 보유")
            return True
        else:
            return False
    
    def fix_admin_permissions(self):
        """ADMIN001 권한 수정 (누락된 컨테이너 추가)"""
        print("\n🔧 ADMIN001 권한 수정 중...")
        
        all_containers = {c['container_id'] for c in self.containers}
        admin_perms = [p for p in self.permissions if p['user_emp_no'] == 'ADMIN001']
        admin_containers = {p['container_id'] for p in admin_perms}
        
        missing_containers = all_containers - admin_containers
        
        if not missing_containers:
            print("   ✅ 수정 불필요 (이미 완전함)")
            return
        
        print(f"   📝 {len(missing_containers)}개 컨테이너에 ADMIN 권한 추가 중...")
        
        # 새 권한 레코드 생성
        new_permissions = []
        for container_id in sorted(missing_containers):
            container = next(c for c in self.containers if c['container_id'] == container_id)
            
            new_perm = {
                'user_emp_no': 'ADMIN001',
                'container_id': container_id,
                'role_id': f'ADMIN_{container["container_type"]}',
                'permission_type': 'ADMIN',
                'permission_level': 'ADMIN',
                'access_scope': container['container_type'],
                'source_container_id': '',
                'sap_role': 'SYSTEM_ADMIN',
                'granted_by': 'SYSTEM',
                'granted_date': '2025-09-30 13:00:00',
                'expires_date': '',
                'is_active': 'true',
                'last_accessed_date': '',
                'access_count': '0'
            }
            new_permissions.append(new_perm)
            print(f"      + {container_id} ({container['container_name']})")
        
        # 기존 권한에 추가
        all_permissions = self.permissions + new_permissions
        
        # CSV 파일에 저장
        output_path = self.csv_dir / "user_permissions.csv"
        backup_path = self.csv_dir / "user_permissions.csv.backup"
        
        # 백업 생성
        if output_path.exists():
            import shutil
            shutil.copy(output_path, backup_path)
            print(f"   💾 백업 생성: {backup_path.name}")
        
        # 저장
        fieldnames = list(all_permissions[0].keys())
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_permissions)
        
        print(f"   ✅ user_permissions.csv 업데이트 완료 ({len(all_permissions)}개 레코드)")
    
    def validate_user_data(self) -> bool:
        """사용자 데이터 검증"""
        print("\n👥 사용자 데이터 검증 중...")
        
        self.users = self.load_csv("users.csv")
        if not self.users:
            return False
        
        # 필수 사용자 확인
        user_emp_nos = {u['emp_no'] for u in self.users}
        required_users = {
            'ADMIN001', 'HR001', 'REC001', 'TRN001', 'PLN001',
            'CLD001', 'MSS001', '77107791', 'INF001', 'BIZ001'
        }
        
        missing_users = required_users - user_emp_nos
        if missing_users:
            self.errors.append(f"❌ 필수 사용자 누락: {missing_users}")
            return False
        
        print(f"   ✅ 필수 사용자 {len(required_users)}명 모두 존재")
        
        # ADMIN001 관리자 권한 확인
        admin_user = next((u for u in self.users if u['emp_no'] == 'ADMIN001'), None)
        if admin_user['is_admin'] != 'true':
            self.errors.append("❌ ADMIN001의 is_admin이 true가 아님")
            return False
        
        print(f"   ✅ ADMIN001 관리자 권한 확인")
        
        return True
    
    def validate_org_permissions(self) -> bool:
        """조직 기반 권한 검증"""
        print("\n🏢 사용자 조직-권한 매핑 검증 중...")
        
        # SAP HR 정보 로드
        self.sap_hr = self.load_csv("sap_hr_info.csv")
        self.user_roles = self.load_csv("user_roles.csv")
        
        if not self.sap_hr or not self.user_roles:
            return False
        
        print(f"   📋 SAP HR 정보: {len(self.sap_hr)}명")
        print(f"   📋 사용자 역할: {len(self.user_roles)}개")
        
        # 사용자별 조직-권한 매핑 검증
        validation_results = []
        
        for user in self.users:
            emp_no = user['emp_no']
            
            # ADMIN은 별도 검증 (이미 완료)
            if emp_no == 'ADMIN001':
                continue
            
            # SAP HR 정보에서 부서 코드 찾기
            hr_info = next((h for h in self.sap_hr if h['emp_no'] == emp_no), None)
            if not hr_info:
                self.warnings.append(f"⚠️  {emp_no}: SAP HR 정보 없음")
                continue
            
            dept_cd = hr_info['dept_cd']
            dept_nm = hr_info['dept_nm']
            postn_nm = hr_info['postn_nm']
            
            # 조직 코드 → 컨테이너 ID 변환
            expected_container = self.org_to_container_map.get(dept_cd)
            if not expected_container:
                self.warnings.append(f"⚠️  {emp_no} ({dept_nm}): 조직 코드 '{dept_cd}' 매핑 정보 없음")
                continue
            
            # user_permissions에서 해당 사용자의 권한 확인
            user_perms = [p for p in self.permissions if p['user_emp_no'] == emp_no]
            user_containers = {p['container_id'] for p in user_perms}
            
            # 소속 컨테이너에 권한이 있는지 확인
            has_own_container_perm = expected_container in user_containers
            
            # 권한 레벨 확인
            own_perm = next((p for p in user_perms if p['container_id'] == expected_container), None)
            
            # 역할 정보 확인
            user_role = next((r for r in self.user_roles if r['user_emp_no'] == emp_no), None)
            
            # 검증 결과 저장
            result = {
                'emp_no': emp_no,
                'name': user.get('username', 'N/A'),
                'dept_cd': dept_cd,
                'dept_nm': dept_nm,
                'postn_nm': postn_nm,
                'expected_container': expected_container,
                'has_permission': has_own_container_perm,
                'permission_type': own_perm['permission_type'] if own_perm else 'NONE',
                'role_level': user_role['role_level'] if user_role else 'N/A',
                'role_name': user_role['role_name'] if user_role else 'N/A'
            }
            validation_results.append(result)
            
            # 오류/경고 체크
            if not has_own_container_perm:
                self.errors.append(
                    f"❌ {emp_no} ({dept_nm}): 소속 컨테이너 '{expected_container}'에 권한 없음"
                )
            elif own_perm:
                # 직책에 따른 적절한 권한 레벨 체크
                perm_type = own_perm['permission_type']
                
                # 팀장급은 MANAGER, 팀원은 EDITOR 이상
                if '팀장' in postn_nm or '본부장' in postn_nm:
                    if perm_type not in ['MANAGER', 'ADMIN']:
                        self.warnings.append(
                            f"⚠️  {emp_no} ({dept_nm} {postn_nm}): 권한 '{perm_type}'이 직책에 부적합 (MANAGER 권장)"
                        )
                elif perm_type == 'VIEWER':
                    self.warnings.append(
                        f"⚠️  {emp_no} ({dept_nm} {postn_nm}): 권한 '{perm_type}'이 너무 제한적 (EDITOR 권장)"
                    )
        
        # 검증 결과 출력
        print("\n   📊 사용자별 조직-권한 매핑 결과:")
        print("   " + "-" * 100)
        print(f"   {'사번':<12} {'이름':<15} {'부서':<20} {'직책':<10} {'컨테이너':<20} {'권한':<10} {'상태':<10}")
        print("   " + "-" * 100)
        
        for r in validation_results:
            status = "✅" if r['has_permission'] else "❌"
            print(
                f"   {r['emp_no']:<12} {r['name']:<15} {r['dept_nm']:<20} {r['postn_nm']:<10} "
                f"{r['expected_container']:<20} {r['permission_type']:<10} {status:<10}"
            )
        
        print("   " + "-" * 100)
        
        return len([r for r in validation_results if not r['has_permission']]) == 0
    
    def validate_all(self) -> bool:
        """전체 검증 실행"""
        print("=" * 60)
        print("🔍 WKMS 초기 데이터 검증 시작")
        print("=" * 60)
        
        # 1. 사용자 데이터 검증
        if not self.validate_user_data():
            self._print_results()
            return False
        
        # 2. 컨테이너 트리 구조 검증
        if not self.validate_containers_tree():
            self._print_results()
            return False
        
        # 3. ADMIN001 권한 검증
        admin_ok = self.validate_admin_permissions()
        
        # 4. 권한 수정이 필요한 경우
        if not admin_ok:
            print("\n⚠️  ADMIN001 권한이 불완전합니다. 수정하시겠습니까?")
            response = input("수정하시겠습니까? (y/N): ").lower()
            
            if response == 'y':
                self.fix_admin_permissions()
                # 재검증 (CSV 파일 다시 로드)
                print("\n🔄 수정된 데이터로 재검증 중...")
                self.permissions = self.load_csv("user_permissions.csv")
                self.warnings = []  # 경고 초기화
                if not self.validate_admin_permissions():
                    self.errors.append("❌ 권한 수정 후에도 검증 실패")
                    self._print_results()
                    return False
                else:
                    print("   ✅ 재검증 통과!")
            else:
                print("   ⚠️  권한 수정을 건너뜁니다.")
                self.warnings.append("ADMIN001 권한 불완전 (사용자가 수정 거부)")
        
        # 5. 조직 기반 권한 검증 (NEW!)
        if not self.validate_org_permissions():
            self._print_results()
            return False
        
        self._print_results()
        
        return len(self.errors) == 0
    
    def _print_results(self):
        """검증 결과 출력"""
        print("\n" + "=" * 60)
        print("📊 검증 결과")
        print("=" * 60)
        
        if self.errors:
            print(f"\n❌ 오류 {len(self.errors)}개:")
            for error in self.errors:
                print(f"   {error}")
        
        if self.warnings:
            print(f"\n⚠️  경고 {len(self.warnings)}개:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ 모든 검증 통과!")
            print("\n🚀 초기 데이터 적재 준비 완료")
        elif not self.errors:
            print("\n✅ 필수 검증 통과 (경고 있음)")
            print("⚠️  경고를 확인하세요")
        else:
            print("\n❌ 검증 실패")
            print("⚠️  오류를 수정 후 다시 실행하세요")


def main():
    """메인 함수"""
    validator = InitialDataValidator()
    success = validator.validate_all()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 초기 데이터 검증 완료!")
        print("=" * 60)
        print("\n다음 단계:")
        print("1. cd /home/wjadmin/Dev/InsightBridge/backend")
        print("2. source ../.venv/bin/activate")
        print("3. WKMS_AUTO_SEED=true python data/seeds/run_all_seeders.py")
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ 검증 실패 - 데이터 적재 불가")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

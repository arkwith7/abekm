#!/usr/bin/env python3
"""
Woongjin Knowledge Management System - Simple Database Initialization
실제 테이블 구조에 맞춘 데이터 로딩 스크립트
"""

import os
import sys
import asyncio
import csv
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import uuid

# 절대 경로 설정
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# CSV 파일 경로
CSV_DIR = BACKEND_DIR / "data" / "csv"

class SimpleDBInitializer:
    """간단한 데이터베이스 초기화"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        
    async def init_engine(self):
        """비동기 엔진 초기화"""
        try:
            self.engine = get_async_engine()
            self.session_factory = sessionmaker(
                self.engine, 
                class_=AsyncSession, 
                expire_on_commit=False
            )
            print("✅ 데이터베이스 연결 완료")
        except Exception as e:
            print(f"❌ 데이터베이스 연결 실패: {e}")
            raise
    
    async def load_csv_data(self, filename: str) -> List[Dict[str, Any]]:
        """CSV 파일 데이터 로드"""
        csv_path = CSV_DIR / filename
        if not csv_path.exists():
            print(f"⚠️  CSV 파일을 찾을 수 없습니다: {csv_path}")
            return []
        
        data = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 빈 값 처리
                    processed_row = {}
                    for key, value in row.items():
                        if value == '' or value == 'NULL':
                            processed_row[key] = None
                        else:
                            processed_row[key] = value
                    data.append(processed_row)
            print(f"📄 {filename}: {len(data)}개 레코드 로드")
            return data
        except Exception as e:
            print(f"❌ CSV 파일 로드 실패 ({filename}): {e}")
            return []
    
    async def execute_sql(self, query: str, params: Dict[str, Any] = None):
        """SQL 직접 실행"""
        async with self.session_factory() as session:
            try:
                if params:
                    await session.execute(text(query), params)
                else:
                    await session.execute(text(query))
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                print(f"❌ SQL 실행 실패: {e}")
                return False
    
    async def seed_common_codes(self):
        """공통 코드 데이터 시드"""
        print("\n🔧 공통 코드 데이터 로딩...")
        
        data = await self.load_csv_data('common_codes.csv')
        if not data:
            return False
        
        for row in data:
            query = """
            INSERT INTO tb_cmns_cd_grp_item (grp_cd, item_cd, item_nm, item_desc, sort_ord, use_yn, created_by, created_date)
            VALUES (:grp_cd, :item_cd, :item_nm, :item_desc, :sort_ord, :use_yn, :created_by, :created_date)
            ON CONFLICT (grp_cd, item_cd) DO UPDATE SET
                item_nm = EXCLUDED.item_nm,
                item_desc = EXCLUDED.item_desc,
                updated_date = CURRENT_TIMESTAMP
            """
            
            # 날짜 파싱
            created_date = None
            if row.get('created_date'):
                try:
                    created_date = datetime.strptime(row['created_date'], '%Y-%m-%d %H:%M:%S')
                except:
                    created_date = datetime.now()
            
            params = {
                'grp_cd': row['grp_cd'],
                'item_cd': row['item_cd'],
                'item_nm': row['item_nm'],
                'item_desc': row.get('item_desc'),
                'sort_ord': int(row.get('sort_ord', 0)),
                'use_yn': row.get('use_yn', 'Y').upper(),
                'created_by': 'SYSTEM',
                'created_date': created_date or datetime.now()
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 공통 코드 데이터 로딩 완료")
        return True
    
    async def seed_sap_hr_info(self):
        """SAP HR 정보 시드"""
        print("\n🏢 SAP HR 데이터 로딩...")
        
        data = await self.load_csv_data('sap_hr_info.csv')
        if not data:
            return False
        
        for row in data:
            query = """
            INSERT INTO tb_sap_hr_info (emp_no, emp_nm, dept_cd, dept_nm, postn_cd, postn_nm, 
                                      email, telno, entrps_de, emp_stats_cd, del_yn, created_by, created_date)
            VALUES (:emp_no, :emp_nm, :dept_cd, :dept_nm, :postn_cd, :postn_nm,
                    :email, :telno, :entrps_de, :emp_stats_cd, :del_yn, :created_by, :created_date)
            ON CONFLICT (emp_no) DO UPDATE SET
                emp_nm = EXCLUDED.emp_nm,
                dept_cd = EXCLUDED.dept_cd,
                dept_nm = EXCLUDED.dept_nm,
                postn_cd = EXCLUDED.postn_cd,
                postn_nm = EXCLUDED.postn_nm,
                email = EXCLUDED.email,
                telno = EXCLUDED.telno,
                entrps_de = EXCLUDED.entrps_de,
                emp_stats_cd = EXCLUDED.emp_stats_cd,
                last_modified_date = CURRENT_TIMESTAMP
            """
            
            # 날짜 파싱
            created_date = None
            if row.get('created_date'):
                try:
                    created_date = datetime.strptime(row['created_date'], '%Y-%m-%d %H:%M:%S')
                except:
                    created_date = datetime.now()
            
            params = {
                'emp_no': row['emp_no'],
                'emp_nm': row['emp_nm'],
                'dept_cd': row['dept_cd'],
                'dept_nm': row['dept_nm'],
                'postn_cd': row.get('postn_cd'),
                'postn_nm': row.get('postn_nm'),
                'email': row.get('email'),
                'telno': row.get('telno'),
                'entrps_de': row.get('entrps_de'),  # 입사일 YYYYMMDD 형식
                'emp_stats_cd': row.get('emp_stats_cd', 'ACTIVE'),
                'del_yn': 'N',
                'created_by': 'SYSTEM',
                'created_date': created_date or datetime.now()
            }
            
            await self.execute_sql(query, params)
        
        print("✅ SAP HR 데이터 로딩 완료")
        return True
    
    async def seed_users(self):
        """사용자 데이터 시드"""
        print("\n👥 사용자 데이터 로딩...")
        
        # 비밀번호 해시화를 위한 import 추가
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        except ImportError:
            print("⚠️  passlib이 설치되지 않았습니다. 기존 해시값 사용")
            pwd_context = None
        
        data = await self.load_csv_data('users.csv')
        if not data:
            return False
        
        for row in data:
            # emp_no UNIQUE, email UNIQUE -> emp_no 기준 upsert
            query = """
            INSERT INTO tb_user (emp_no, username, email, password_hash, is_active, 
                               is_admin, failed_login_attempts, created_date, last_modified_date)
            VALUES (:emp_no, :username, :email, :password_hash, :is_active,
                    :is_admin, :failed_login_attempts, :created_date, :last_modified_date)
            ON CONFLICT (emp_no) DO UPDATE SET
                username = EXCLUDED.username,
                email = EXCLUDED.email,
                password_hash = EXCLUDED.password_hash,
                is_active = EXCLUDED.is_active,
                is_admin = EXCLUDED.is_admin,
                last_modified_date = CURRENT_TIMESTAMP
            """
            
            # 평문 비밀번호를 해시화
            hashed_password = row.get('password_hash')  # 기본값으로 기존 해시 사용
            if row.get('password_plain') and pwd_context:
                hashed_password = pwd_context.hash(row['password_plain'])
                print(f"🔑 {row['username']} 비밀번호 해시화 완료 (평문: {row['password_plain']})")
            
            # 날짜 파싱
            created_date = None
            if row.get('created_date'):
                try:
                    created_date = datetime.strptime(row['created_date'], '%Y-%m-%d %H:%M:%S')
                except:
                    created_date = datetime.now()
            
            last_modified_date = None
            if row.get('last_modified_date'):
                try:
                    last_modified_date = datetime.strptime(row['last_modified_date'], '%Y-%m-%d %H:%M:%S')
                except:
                    last_modified_date = datetime.now()
            
            params = {
                'emp_no': row.get('emp_no'),
                'username': row['username'],
                'email': row['email'],
                'password_hash': hashed_password,
                'is_active': row.get('is_active', 'true').lower() == 'true',
                'is_admin': row.get('is_admin', 'false').lower() == 'true',
                'failed_login_attempts': int(row.get('failed_login_attempts', 0)),
                'created_date': created_date or datetime.now(),
                'last_modified_date': last_modified_date or datetime.now()
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 사용자 데이터 로딩 완료")
        return True
    
    async def seed_user_roles(self):
        """사용자 역할 데이터 시드 (tb_user_roles)"""
        print("\n🔑 사용자 역할 데이터 로딩...")
        data = await self.load_csv_data('user_roles.csv')
        if not data:
            return False

        # 존재 여부 확인용 helper
        async def role_exists(session: AsyncSession, user_emp_no: str, role_name: str, scope_type: str, scope_value: str):
            q = text("""
                SELECT 1 FROM tb_user_roles
                WHERE user_emp_no=:user_emp_no AND role_name=:role_name
                  AND scope_type=:scope_type AND COALESCE(scope_value,'') = COALESCE(:scope_value,'')
                LIMIT 1
            """)
            res = await session.execute(q, {
                'user_emp_no': user_emp_no,
                'role_name': role_name,
                'scope_type': scope_type,
                'scope_value': scope_value
            })
            return res.first() is not None

        async with self.session_factory() as session:
            for row in data:
                # 날짜 파싱
                def parse_dt(v):
                    if not v:
                        return None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                        try:
                            return datetime.strptime(v, fmt)
                        except:
                            continue
                    return None

                if await role_exists(session, row['user_emp_no'], row['role_name'], row['scope_type'], row.get('scope_value','')):
                    continue  # 이미 존재

                query = """
                INSERT INTO tb_user_roles (
                    user_emp_no, role_name, role_level, scope_type, scope_value,
                    role_description, permissions, valid_from, valid_until,
                    is_active, assigned_by, assigned_date, approval_required,
                    approved_by, approved_date, created_by, created_date
                ) VALUES (
                    :user_emp_no, :role_name, :role_level, :scope_type, :scope_value,
                    :role_description, cast(:permissions as jsonb), :valid_from, :valid_until,
                    :is_active, :assigned_by, :assigned_date, :approval_required,
                    :approved_by, :approved_date, :created_by, :created_date
                )
                """

                # permissions JSON 파싱
                import json
                permissions_json = None
                if row.get('permissions'):
                    try:
                        permissions_json = json.loads(row['permissions'])
                    except json.JSONDecodeError:
                        # 따옴표 이스케이프 문제 보정
                        try:
                            permissions_json = json.loads(row['permissions'].replace('""', '"'))
                        except:
                            permissions_json = {}

                import json as _json
                approved_by = row.get('approved_by') or row['user_emp_no']
                if approved_by == 'SYSTEM':
                    approved_by = row['user_emp_no']
                assigned_by = approved_by

                params = {
                    'user_emp_no': row['user_emp_no'],
                    'role_name': row['role_name'],
                    'role_level': int(row.get('role_level', 0) or 0),
                    'scope_type': row.get('scope_type','global'),
                    'scope_value': row.get('scope_value'),
                    'role_description': row.get('role_description'),
                    'permissions': _json.dumps(permissions_json, ensure_ascii=False) if permissions_json is not None else None,
                    'valid_from': parse_dt(row.get('valid_from')),
                    'valid_until': parse_dt(row.get('valid_until')),
                    'is_active': str(row.get('is_active','true')).lower() == 'true',
                    'assigned_by': assigned_by,
                    'assigned_date': parse_dt(row.get('approved_date')) or datetime.utcnow(),
                    'approval_required': False,
                    'approved_by': approved_by,
                    'approved_date': parse_dt(row.get('approved_date')) or datetime.utcnow(),
                    'created_by': row.get('created_by','SYSTEM'),
                    'created_date': parse_dt(row.get('created_date')) or datetime.utcnow(),
                }

                try:
                    await session.execute(text(query), params)
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    print(f"❌ 역할 INSERT 실패: {row.get('user_emp_no')} / {row.get('role_name')} - {e}")

        print("✅ 사용자 역할 데이터 로딩 완료")
        return True

    async def seed_user_permissions(self):
        """사용자 권한 데이터 시드 (tb_user_permissions)"""
        print("\n🛡️  사용자 권한 데이터 로딩...")
        data = await self.load_csv_data('user_permissions.csv')
        if not data:
            return False

        async with self.session_factory() as session:
            for row in data:
                def parse_dt(v):
                    if not v:
                        return None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                        try:
                            return datetime.strptime(v, fmt)
                        except:
                            continue
                    return None

                # 중복 체크 (user_emp_no, container_id, permission_type, role_id)
                exists_q = text("""
                    SELECT 1 FROM tb_user_permissions
                     WHERE user_emp_no=:user_emp_no AND container_id=:container_id
                       AND permission_type=:permission_type AND role_id=:role_id
                    LIMIT 1
                """)
                res = await session.execute(exists_q, {
                    'user_emp_no': row['user_emp_no'],
                    'container_id': row['container_id'],
                    'permission_type': row['permission_type'],
                    'role_id': row['role_id']
                })
                if res.first():
                    continue

                query = """
                INSERT INTO tb_user_permissions (
                    user_emp_no, container_id, role_id, permission_type, access_scope,
                    permission_source, source_container_id, sap_role, is_active,
                    granted_by, granted_date, expires_date, access_count
                ) VALUES (
                    :user_emp_no, :container_id, :role_id, :permission_type, :access_scope,
                    :permission_source, :source_container_id, :sap_role, :is_active,
                    :granted_by, :granted_date, :expires_date, :access_count
                )
                """

                params = {
                    'user_emp_no': row['user_emp_no'],
                    'container_id': row['container_id'],
                    'role_id': row['role_id'],
                    'permission_type': row['permission_type'],
                    'access_scope': row.get('access_scope','GLOBAL'),
                    # permission_level 컬럼이 테이블에 없으므로 permission_source 를 고정값 DIRECT 로 저장
                    'permission_source': 'DIRECT',
                    'source_container_id': row.get('source_container_id'),
                    'sap_role': row.get('sap_role'),
                    'is_active': str(row.get('is_active','true')).lower() == 'true',
                    'granted_by': row.get('granted_by'),
                    'granted_date': parse_dt(row.get('granted_date')) or datetime.utcnow(),
                    'expires_date': parse_dt(row.get('expires_date')),
                    'access_count': int(row.get('access_count',0) or 0)
                }

                try:
                    await session.execute(text(query), params)
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    print(f"❌ 권한 INSERT 실패: {row.get('user_emp_no')} / {row.get('container_id')} - {e}")

        print("✅ 사용자 권한 데이터 로딩 완료")
        return True

    async def seed_categories(self):
        """카테고리 데이터 시드 (tb_knowledge_categories)"""
        print("\n📂 카테고리 데이터 로딩...")
        data = await self.load_csv_data('categories.csv')
        if not data:
            return False

        # 먼저 모든 행을 dict 로 보관
        raw = {r['category_id']: r for r in data}
        level_cache = {}
        path_cache = {}

        def compute_level(cat_id):
            if cat_id in level_cache:
                return level_cache[cat_id]
            parent = raw[cat_id].get('parent_id')
            if not parent:
                level_cache[cat_id] = 1
            else:
                level_cache[cat_id] = compute_level(parent) + 1
            return level_cache[cat_id]

        def compute_path(cat_id):
            if cat_id in path_cache:
                return path_cache[cat_id]
            parent = raw[cat_id].get('parent_id')
            if not parent:
                path_cache[cat_id] = f"/{cat_id}"
            else:
                path_cache[cat_id] = compute_path(parent) + f"/{cat_id}"
            return path_cache[cat_id]

        # 존재 체크 helper
        async def cat_exists(session: AsyncSession, cid: str):
            q = text("SELECT 1 FROM tb_knowledge_categories WHERE category_id=:cid LIMIT 1")
            res = await session.execute(q, {'cid': cid})
            return res.first() is not None

        async with self.session_factory() as session:
            for row in data:
                cid = row['category_id']
                if await cat_exists(session, cid):
                    continue
                query = """
                INSERT INTO tb_knowledge_categories (
                    category_id, category_name, category_description, parent_category_id,
                    category_level, category_path, sort_order, is_active, document_count,
                    created_by, created_date
                ) VALUES (
                    :category_id, :category_name, :category_description, :parent_category_id,
                    :category_level, :category_path, :sort_order, :is_active, :document_count,
                    :created_by, :created_date
                )
                """
                params = {
                    'category_id': cid,
                    'category_name': row['category_name'],
                    'category_description': row.get('description'),
                    'parent_category_id': row.get('parent_id') or None,
                    'category_level': compute_level(cid),
                    'category_path': compute_path(cid),
                    'sort_order': int(row.get('sort_order',0) or 0),
                    'is_active': str(row.get('is_active','true')).lower() == 'true',
                    'document_count': 0,
                    'created_by': 'SYSTEM',
                    'created_date': datetime.utcnow()
                }
                try:
                    await session.execute(text(query), params)
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    print(f"❌ 카테고리 INSERT 실패: {cid} - {e}")

        print("✅ 카테고리 데이터 로딩 완료")
        return True

    async def seed_knowledge_containers(self):
        """지식 컨테이너 데이터 시드"""
        print("\n📚 지식 컨테이너 데이터 로딩...")
        
        data = await self.load_csv_data('knowledge_containers.csv')
        if not data:
            return False
        
        for row in data:
            query = """
            INSERT INTO tb_knowledge_containers (
                container_id, container_name, parent_container_id, container_type, 
                org_level, description, access_level, default_permission,
                inherit_parent_permissions, permission_inheritance_type,
                auto_assign_by_org, require_approval_for_access, approval_workflow_enabled,
                is_active, document_count, total_knowledge_size, user_count, 
                permission_request_count, created_by, created_date
            )
            VALUES (
                :container_id, :container_name, :parent_container_id, :container_type,
                :org_level, :description, :access_level, :default_permission,
                :inherit_parent_permissions, :permission_inheritance_type,
                :auto_assign_by_org, :require_approval_for_access, :approval_workflow_enabled,
                :is_active, :document_count, :total_knowledge_size, :user_count,
                :permission_request_count, :created_by, :created_date
            )
            ON CONFLICT (container_id) DO UPDATE SET
                container_name = EXCLUDED.container_name,
                container_type = EXCLUDED.container_type,
                description = EXCLUDED.description,
                parent_container_id = EXCLUDED.parent_container_id,
                access_level = EXCLUDED.access_level,
                last_modified_date = CURRENT_TIMESTAMP
            """
            
            # 날짜 파싱
            created_date = None
            if row.get('created_date'):
                try:
                    created_date = datetime.strptime(row['created_date'], '%Y-%m-%d %H:%M:%S')
                except:
                    created_date = datetime.now()
            
            params = {
                'container_id': row['container_id'],
                'container_name': row['container_name'],
                'parent_container_id': row.get('parent_container_id') if row.get('parent_container_id') else None,
                'container_type': row['container_type'],
                'org_level': int(row.get('org_level', 1)),
                'description': row.get('description'),
                'access_level': row.get('access_level', 'PUBLIC'),
                'default_permission': row.get('default_permission', 'VIEWER'),
                'inherit_parent_permissions': row.get('inherit_parent_permissions', 'false').lower() == 'true',
                'permission_inheritance_type': row.get('permission_inheritance_type', 'NONE'),
                'auto_assign_by_org': row.get('auto_assign_by_org', 'true').lower() == 'true',
                'require_approval_for_access': row.get('require_approval_for_access', 'false').lower() == 'true',
                'approval_workflow_enabled': row.get('approval_workflow_enabled', 'false').lower() == 'true',
                'is_active': row.get('is_active', 'true').lower() == 'true',
                'document_count': int(row.get('document_count', 0)),
                'total_knowledge_size': int(row.get('total_knowledge_size', 0)),
                'user_count': int(row.get('user_count', 0)),
                'permission_request_count': int(row.get('permission_request_count', 0)),
                'created_by': row.get('created_by', 'SYSTEM'),
                'created_date': created_date or datetime.now()
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 지식 컨테이너 데이터 로딩 완료")
        return True
    
    async def initialize_all(self):
        """전체 초기화 실행"""
        print("🚀 WKMS 데이터베이스 초기화 시작\n")
        
        try:
            await self.init_engine()
            
            # 의존성 순서에 따라 실행
            success = True
            success &= await self.seed_common_codes()
            success &= await self.seed_sap_hr_info()
            success &= await self.seed_users()
            success &= await self.seed_knowledge_containers()
            success &= await self.seed_user_roles()
            success &= await self.seed_user_permissions()
            success &= await self.seed_categories()
            
            if success:
                print("\n🎉 모든 초기 데이터 로딩이 완료되었습니다!")
                print("\n📋 로그인 테스트 계정:")
                print("   • 관리자: admin / admin123!")
                print("   • 인사담당: hr.manager / hr2025!")
                print("   • 일반사용자: ms.staff / staff2025")
                print("\n📝 비밀번호 관리 가이드: backend/PASSWORD_MANAGEMENT_GUIDE.md")
            else:
                print("\n⚠️  일부 데이터 로딩에 실패했습니다.")
            
        except Exception as e:
            print(f"\n❌ 초기화 중 오류 발생: {e}")
            raise
        finally:
            if self.engine:
                await self.engine.dispose()
                print("✅ 데이터베이스 연결 해제 완료")

async def main():
    """메인 실행 함수"""
    initializer = SimpleDBInitializer()
    await initializer.initialize_all()

if __name__ == "__main__":
    asyncio.run(main())
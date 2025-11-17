#!/usr/bin/env python3
"""
Woongjin Knowledge Management System - Complete Database Initialization
모든 테이블의 초기 데이터를 CSV 파일로부터 로드합니다.
"""

import os
import sys
import asyncio
import asyncpg
import csv
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import uuid

# 절대 경로 설정
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_async_engine
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# CSV 파일 경로
CSV_DIR = BACKEND_DIR / "data" / "csv"

class DatabaseInitializer:
    """데이터베이스 초기화 관리자"""
    
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
            print("✅ 데이터베이스 엔진 초기화 완료")
        except Exception as e:
            print(f"❌ 데이터베이스 엔진 초기화 실패: {e}")
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
                        elif key.endswith('_at') and value:  # 날짜 필드
                            try:
                                processed_row[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            except:
                                processed_row[key] = datetime.now()
                        elif key == 'id' and value:  # UUID 필드
                            processed_row[key] = uuid.UUID(value)
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
            
            # CSV 파일의 실제 컬럼명 매핑
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
            
            hire_date = None
            if row.get('entrps_de'):  # entrps_de -> hire_date
                try:
                    hire_date = datetime.strptime(row['entrps_de'], '%Y%m%d').date()
                except:
                    pass
            
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
            query = """
            INSERT INTO tb_user (emp_no, username, email, password_hash, is_active, 
                               is_admin, failed_login_attempts, created_date, last_modified_date)
            VALUES (:emp_no, :username, :email, :password_hash, :is_active,
                    :is_admin, :failed_login_attempts, :created_date, :last_modified_date)
            ON CONFLICT (username) DO UPDATE SET
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
            
            # UUID 생성 (container_id 사용)
            container_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, row['container_id'])
            parent_uuid = None
            if row.get('parent_container_id'):
                parent_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, row['parent_container_id'])
            created_by_uuid = None
            if row.get('created_by'):
                created_by_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, row['created_by'])
            
            params = {
                'id': container_uuid,
                'container_name': row['container_name'],
                'container_type': row['container_type'],
                'description': row.get('description'),
                'parent_container_id': parent_uuid,
                'access_level': row.get('access_level', 'PUBLIC'),
                'created_by': created_by_uuid,
                'created_at': created_date or datetime.now(),
                'updated_at': datetime.now(),
                'is_active': row.get('is_active', 'true').lower() == 'true'
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 지식 컨테이너 데이터 로딩 완료")
        return True
    
    async def seed_user_roles(self):
        """사용자 역할 데이터 시드"""
        print("\n🔑 사용자 역할 데이터 로딩...")
        
        data = await self.load_csv_data('user_roles.csv')
        if not data:
            return False
        
        for row in data:
            query = """
            INSERT INTO tb_user_roles (id, user_id, role_name, granted_by, granted_at, expires_at, is_active)
            VALUES (:id, :user_id, :role_name, :granted_by, :granted_at, :expires_at, :is_active)
            ON CONFLICT (id) DO UPDATE SET
                role_name = EXCLUDED.role_name,
                granted_by = EXCLUDED.granted_by,
                granted_at = EXCLUDED.granted_at,
                expires_at = EXCLUDED.expires_at,
                is_active = EXCLUDED.is_active
            """
            
            params = {
                'id': uuid.UUID(row['id']),
                'user_id': uuid.UUID(row['user_id']),
                'role_name': row['role_name'],
                'granted_by': uuid.UUID(row['granted_by']) if row.get('granted_by') else None,
                'granted_at': row.get('granted_at') or datetime.now(),
                'expires_at': row.get('expires_at'),
                'is_active': row.get('is_active', 'true').lower() == 'true'
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 사용자 역할 데이터 로딩 완료")
        return True
    
    async def seed_user_permissions(self):
        """사용자 권한 데이터 시드"""
        print("\n🛡️  사용자 권한 데이터 로딩...")
        
        data = await self.load_csv_data('user_permissions.csv')
        if not data:
            return False
        
        for row in data:
            query = """
            INSERT INTO tb_user_permissions (id, user_id, container_id, permission_type, 
                                           granted_by, granted_at, expires_at, is_active)
            VALUES (:id, :user_id, :container_id, :permission_type, :granted_by, 
                    :granted_at, :expires_at, :is_active)
            ON CONFLICT (id) DO UPDATE SET
                permission_type = EXCLUDED.permission_type,
                granted_by = EXCLUDED.granted_by,
                granted_at = EXCLUDED.granted_at,
                expires_at = EXCLUDED.expires_at,
                is_active = EXCLUDED.is_active
            """
            
            params = {
                'id': uuid.UUID(row['id']),
                'user_id': uuid.UUID(row['user_id']),
                'container_id': uuid.UUID(row['container_id']) if row.get('container_id') else None,
                'permission_type': row['permission_type'],
                'granted_by': uuid.UUID(row['granted_by']) if row.get('granted_by') else None,
                'granted_at': row.get('granted_at') or datetime.now(),
                'expires_at': row.get('expires_at'),
                'is_active': row.get('is_active', 'true').lower() == 'true'
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 사용자 권한 데이터 로딩 완료")
        return True
    
    async def seed_categories(self):
        """카테고리 데이터 시드"""
        print("\n📂 카테고리 데이터 로딩...")
        
        data = await self.load_csv_data('categories.csv')
        if not data:
            return False
        
        for row in data:
            query = """
            INSERT INTO tb_categories (id, name, description, parent_id, container_id, 
                                     sort_order, is_active, created_at, updated_at)
            VALUES (:id, :name, :description, :parent_id, :container_id,
                    :sort_order, :is_active, :created_at, :updated_at)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                parent_id = EXCLUDED.parent_id,
                container_id = EXCLUDED.container_id,
                sort_order = EXCLUDED.sort_order,
                is_active = EXCLUDED.is_active,
                updated_at = CURRENT_TIMESTAMP
            """
            
            params = {
                'id': uuid.UUID(row['id']),
                'name': row['name'],
                'description': row.get('description'),
                'parent_id': uuid.UUID(row['parent_id']) if row.get('parent_id') else None,
                'container_id': uuid.UUID(row['container_id']) if row.get('container_id') else None,
                'sort_order': int(row.get('sort_order', 0)),
                'is_active': row.get('is_active', 'true').lower() == 'true',
                'created_at': row.get('created_at') or datetime.now(),
                'updated_at': row.get('updated_at') or datetime.now()
            }
            
            await self.execute_sql(query, params)
        
        print("✅ 카테고리 데이터 로딩 완료")
        return True
    
    async def initialize_all(self):
        """전체 초기화 실행"""
        print("🚀 Woongjin Knowledge Management System 데이터베이스 초기화 시작\n")
        
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
                print("   • 관리자: admin / password123")
                print("   • 일반사용자: ms.staff / password123")
                print("   • 영업담당: sales.manager / password123")
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
    initializer = DatabaseInitializer()
    await initializer.initialize_all()

if __name__ == "__main__":
    asyncio.run(main())
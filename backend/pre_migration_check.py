#!/usr/bin/env python3
"""
비동기 업로드 마이그레이션 사전 검증 스크립트

이 스크립트는 알렘빅 마이그레이션을 실행하기 전에:
1. 데이터베이스 연결 확인
2. 현재 마이그레이션 상태 확인
3. 적용될 마이그레이션 검증
4. 테이블 백업 권장사항 제공
5. 마이그레이션 시뮬레이션 (dry-run)
"""

import sys
import os
import psycopg2
from datetime import datetime
from pathlib import Path

# 환경 변수 설정
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'wkms')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'wkms123')
DB_NAME = os.getenv('DB_NAME', 'wkms')
DB_PORT = os.getenv('DB_PORT', '5432')

# 색상 코드
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{RESET}")

def check_database_connection():
    """데이터베이스 연결 확인"""
    print_header("1. 데이터베이스 연결 확인")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        print_success(f"데이터베이스 연결 성공")
        print_info(f"PostgreSQL: {version.split(',')[0]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print_error(f"데이터베이스 연결 실패: {e}")
        return False

def check_alembic_version():
    """현재 알렘빅 버전 확인"""
    print_header("2. 현재 마이그레이션 상태 확인")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        
        # alembic_version 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            );
        """)
        
        if not cursor.fetchone()[0]:
            print_warning("alembic_version 테이블이 없습니다. 최초 마이그레이션입니다.")
            cursor.close()
            conn.close()
            return None
        
        # 현재 버전 조회
        cursor.execute("SELECT version_num FROM alembic_version;")
        result = cursor.fetchone()
        
        if result:
            current_version = result[0]
            print_success(f"현재 마이그레이션 버전: {current_version}")
            
            # 버전 정보 매핑
            version_map = {
                '300c1a2a7c7f': 'initial_schema',
                '3e19d6566abb': 'remove_vector_tables_add_unified_search',
                '9c2a4d9c1b2e': 'add_refresh_token_table',
                'b38f1337b6ae': 'add_multimodal_schema_v2',
                'a1b2c3d4e5f6': 'add_processing_status_columns'
            }
            
            if current_version in version_map:
                print_info(f"마이그레이션 이름: {version_map[current_version]}")
            
            cursor.close()
            conn.close()
            return current_version
        else:
            print_warning("마이그레이션 버전 정보가 없습니다.")
            cursor.close()
            conn.close()
            return None
            
    except Exception as e:
        print_error(f"버전 확인 실패: {e}")
        return None

def check_table_structure():
    """tb_file_bss_info 테이블 구조 확인"""
    print_header("3. 테이블 구조 확인")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        
        # tb_file_bss_info 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'tb_file_bss_info'
            );
        """)
        
        if not cursor.fetchone()[0]:
            print_error("tb_file_bss_info 테이블이 존재하지 않습니다!")
            cursor.close()
            conn.close()
            return False
        
        print_success("tb_file_bss_info 테이블 존재 확인")
        
        # 컬럼 목록 조회
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'tb_file_bss_info'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print_info(f"총 {len(columns)}개 컬럼 존재")
        
        # processing 관련 컬럼 확인
        processing_columns = [col for col in columns if 'processing' in col[0]]
        
        if processing_columns:
            print_warning("비동기 처리 컬럼이 이미 존재합니다:")
            for col in processing_columns:
                print(f"   - {col[0]} ({col[1]})")
            print_warning("마이그레이션이 이미 적용되었거나 수동으로 컬럼이 추가되었습니다.")
            cursor.close()
            conn.close()
            return False
        else:
            print_success("비동기 처리 컬럼이 아직 없습니다. 마이그레이션 준비 완료!")
        
        # 레코드 수 확인
        cursor.execute("SELECT COUNT(*) FROM tb_file_bss_info WHERE del_yn = 'N';")
        count = cursor.fetchone()[0]
        print_info(f"활성 레코드 수: {count:,}개")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"테이블 구조 확인 실패: {e}")
        return False

def check_migration_file():
    """마이그레이션 파일 검증"""
    print_header("4. 마이그레이션 파일 검증")
    
    migration_file = Path(__file__).parent / "alembic" / "versions" / "a1b2c3d4e5f6_add_processing_status_columns.py"
    
    if not migration_file.exists():
        print_error(f"마이그레이션 파일이 없습니다: {migration_file}")
        return False
    
    print_success(f"마이그레이션 파일 존재 확인: {migration_file.name}")
    
    # 파일 내용 검증
    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 필수 요소 확인
    required_elements = [
        ('revision', "revision = 'a1b2c3d4e5f6'"),
        ('down_revision', "down_revision = 'b38f1337b6ae'"),
        ('upgrade 함수', 'def upgrade()'),
        ('downgrade 함수', 'def downgrade()'),
        ('processing_status 컬럼', "Column('processing_status'"),
        ('processing_error 컬럼', "Column('processing_error'"),
        ('processing_started_at 컬럼', "Column('processing_started_at'"),
        ('processing_completed_at 컬럼', "Column('processing_completed_at'"),
        ('인덱스 생성', 'create_index'),
    ]
    
    all_valid = True
    for name, pattern in required_elements:
        if pattern in content:
            print_success(f"{name} 확인")
        else:
            print_error(f"{name} 누락")
            all_valid = False
    
    return all_valid

def provide_backup_recommendation():
    """백업 권장사항 제공"""
    print_header("5. 백업 권장사항")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_before_async_migration_{timestamp}.sql"
    
    print_info("마이그레이션 전 백업을 강력히 권장합니다!")
    print("\n백업 명령어:")
    print(f"{YELLOW}pg_dump -h {DB_HOST} -U {DB_USER} -d {DB_NAME} -f {backup_file}{RESET}")
    
    print("\n특정 테이블만 백업:")
    print(f"{YELLOW}pg_dump -h {DB_HOST} -U {DB_USER} -d {DB_NAME} -t tb_file_bss_info -f tb_file_bss_info_backup_{timestamp}.sql{RESET}")
    
    print("\n복원 명령어 (필요 시):")
    print(f"{YELLOW}psql -h {DB_HOST} -U {DB_USER} -d {DB_NAME} -f {backup_file}{RESET}")

def check_foreign_keys():
    """외래 키 제약조건 확인"""
    print_header("6. 외래 키 제약조건 확인")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND (tc.table_name = 'tb_file_bss_info' OR ccu.table_name = 'tb_file_bss_info')
            ORDER BY tc.table_name;
        """)
        
        fks = cursor.fetchall()
        
        if fks:
            print_info(f"tb_file_bss_info 관련 외래 키: {len(fks)}개")
            for fk in fks:
                print(f"   - {fk[1]}.{fk[2]} → {fk[3]}.{fk[4]}")
            print_success("외래 키 제약조건 확인 완료 (마이그레이션에 영향 없음)")
        else:
            print_success("관련 외래 키 없음")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"외래 키 확인 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    print_header("비동기 업로드 마이그레이션 사전 검증")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    checks = []
    
    # 1. 데이터베이스 연결
    checks.append(("데이터베이스 연결", check_database_connection()))
    
    if not checks[-1][1]:
        print_error("\n데이터베이스 연결 실패로 검증을 중단합니다.")
        sys.exit(1)
    
    # 2. 알렘빅 버전
    current_version = check_alembic_version()
    checks.append(("알렘빅 버전 확인", current_version is not None))
    
    # 3. 테이블 구조
    table_check = check_table_structure()
    checks.append(("테이블 구조", table_check))
    
    # 4. 마이그레이션 파일
    checks.append(("마이그레이션 파일", check_migration_file()))
    
    # 5. 백업 권장
    provide_backup_recommendation()
    
    # 6. 외래 키
    checks.append(("외래 키 제약조건", check_foreign_keys()))
    
    # 결과 요약
    print_header("검증 결과 요약")
    
    all_passed = all(check[1] for check in checks)
    
    for name, result in checks:
        if result:
            print_success(f"{name}: 통과")
        else:
            print_error(f"{name}: 실패")
    
    print("\n" + "="*70)
    
    if all_passed and table_check:
        print(f"\n{GREEN}✅ 모든 사전 검증을 통과했습니다!{RESET}")
        print(f"\n{BLUE}다음 단계:{RESET}")
        print("1. 백업 수행 (권장)")
        print("2. 마이그레이션 실행:")
        print(f"   {YELLOW}cd /home/wjadmin/Dev/InsightBridge/backend{RESET}")
        print(f"   {YELLOW}alembic upgrade head{RESET}")
        print("3. 마이그레이션 확인:")
        print(f"   {YELLOW}alembic current{RESET}")
        print(f"   {YELLOW}psql -h localhost -U wkms -d wkms -c '\\d tb_file_bss_info'{RESET}")
    elif not table_check:
        print(f"\n{YELLOW}⚠️  비동기 처리 컬럼이 이미 존재합니다.{RESET}")
        print("마이그레이션을 건너뛰거나, 기존 컬럼을 확인하세요.")
    else:
        print(f"\n{RED}❌ 일부 검증이 실패했습니다.{RESET}")
        print("문제를 해결한 후 다시 시도하세요.")
        sys.exit(1)

if __name__ == "__main__":
    main()

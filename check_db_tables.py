"""
데이터베이스 테이블 목록 확인
"""
import os
from sqlalchemy import create_engine, text

def check_tables():
    # 환경변수에서 데이터베이스 정보 가져오기
    db_user = os.getenv('DB_USER', 'wkms')
    db_password = os.getenv('DB_PASSWORD', 'wkms123')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'wkms')
    
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        print("=" * 80)
        print("데이터베이스 테이블 목록")
        print("=" * 80 + "\n")
        
        # 모든 테이블 조회
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        
        tables = result.fetchall()
        
        print(f"총 {len(tables)}개의 테이블이 존재합니다:\n")
        for table in tables:
            print(f"  - {table[0]}")
            
        print("\n" + "=" * 80)
        
        # permission 관련 테이블 확인
        print("\n'permission' 단어가 포함된 테이블:")
        permission_tables = [t[0] for t in tables if 'permission' in t[0].lower()]
        if permission_tables:
            for table in permission_tables:
                print(f"  - {table}")
        else:
            print("  없음")
            
        print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    check_tables()

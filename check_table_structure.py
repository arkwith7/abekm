"""
테이블 구조 확인
"""
import os
from sqlalchemy import create_engine, text

def check_table_structure():
    db_user = os.getenv('DB_USER', 'wkms')
    db_password = os.getenv('DB_PASSWORD', 'wkms123')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'wkms')
    
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        tables = ['tb_permission_requests', 'tb_knowledge_containers', 'tb_user']
        
        for table_name in tables:
            print("=" * 80)
            print(f"테이블: {table_name}")
            print("=" * 80)
            
            result = conn.execute(text(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            print(f"\n컬럼 목록 ({len(columns)}개):\n")
            for col in columns:
                nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                print(f"  {col[0]:<30} {col[1]:<20} {nullable}")
            print()

if __name__ == "__main__":
    check_table_structure()

"""
실제 권한 신청 데이터 조회
"""
import os
from sqlalchemy import create_engine, text

def check_requests():
    db_user = os.getenv('DB_USER', 'wkms')
    db_password = os.getenv('DB_PASSWORD', 'wkms123')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'wkms')
    
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        print("=" * 100)
        print("권한 신청 데이터 조회")
        print("=" * 100 + "\n")
        
        # 권한 신청 목록
        result = conn.execute(text("""
            SELECT 
                pr.request_id,
                pr.requester_emp_no,
                pr.container_id,
                kc.container_name,
                pr.requested_permission,
                pr.justification,
                pr.request_status,
                pr.created_date,
                pr.approval_date,
                pr.approver_emp_no,
                pr.rejection_reason
            FROM tb_permission_requests pr
            LEFT JOIN tb_knowledge_containers kc ON pr.container_id = kc.container_id
            ORDER BY pr.created_date DESC
            LIMIT 10
        """))
        
        rows = result.fetchall()
        
        print(f"총 {len(rows)}건의 권한 신청:\n")
        
        for row in rows:
            print(f"신청 ID: {row[0]}")
            print(f"  신청자 사번: {row[1]}")
            print(f"  컨테이너 ID: {row[2]}")
            print(f"  컨테이너명: {row[3]}")
            print(f"  요청 권한: {row[4]}")
            print(f"  신청 사유: {row[5]}")
            print(f"  상태: {row[6]}")
            print(f"  신청일: {row[7]}")
            if row[8]:
                print(f"  승인일: {row[8]}")
                print(f"  승인자: {row[9]}")
            if row[10]:
                print(f"  거부 사유: {row[10]}")
            print()
        
        # 통계
        print("=" * 100)
        print("상태별 통계")
        print("=" * 100 + "\n")
        
        stats = conn.execute(text("""
            SELECT request_status, COUNT(*) as count
            FROM tb_permission_requests
            GROUP BY request_status
        """))
        
        for stat in stats.fetchall():
            print(f"{stat[0]}: {stat[1]}건")

if __name__ == "__main__":
    check_requests()

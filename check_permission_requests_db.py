"""
권한 신청 데이터베이스 상태 확인 스크립트
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_permission_requests():
    # 환경변수에서 데이터베이스 정보 가져오기
    db_user = os.getenv('DB_USER', 'wkms')
    db_password = os.getenv('DB_PASSWORD', 'wkms123')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'wkms')
    
    # psycopg2용 동기 데이터베이스 URL
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    print(f"데이터베이스 연결: {db_host}:{db_port}/{db_name}")
    
    # 데이터베이스 연결
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        print("\n" + "="*80)
        print("권한 신청 데이터베이스 상태 확인")
        print("="*80 + "\n")
        
        # 1. 전체 권한 신청 목록 조회
        query = text("""
            SELECT 
                pr.id,
                pr.container_id,
                kc.container_name,
                pr.user_id,
                u.username,
                u.full_name,
                d.dept_name,
                pr.requested_permission_level,
                pr.request_reason,
                pr.status,
                pr.created_at,
                pr.processed_at,
                pr.processed_by,
                pr.rejection_reason,
                pm.username as processor_name
            FROM tb_permission_requests pr
            LEFT JOIN tb_knowledge_containers kc ON pr.container_id = kc.id
            LEFT JOIN tb_user u ON pr.user_id = u.id
            LEFT JOIN tb_sap_hr_info d ON u.dept_id = d.id
            LEFT JOIN tb_user pm ON pr.processed_by = pm.id
            ORDER BY pr.created_at DESC
            LIMIT 20
        """)
        
        result = db.execute(query)
        rows = result.fetchall()
        
        print(f"📊 전체 권한 신청 목록 (최근 20건):")
        print("-" * 80)
        
        if rows:
            for row in rows:
                print(f"\n신청 ID: {row.id}")
                print(f"  컨테이너: {row.container_name} (ID: {row.container_id})")
                print(f"  신청자: {row.full_name} ({row.username}) - {row.dept_name}")
                print(f"  요청 권한: {row.requested_permission_level}")
                print(f"  신청 사유: {row.request_reason}")
                print(f"  상태: {row.status}")
                print(f"  신청일: {row.created_at}")
                if row.processed_at:
                    print(f"  처리일: {row.processed_at}")
                    print(f"  처리자: {row.processor_name}")
                if row.rejection_reason:
                    print(f"  거부 사유: {row.rejection_reason}")
        else:
            print("권한 신청 데이터가 없습니다.")
        
        # 2. 홍길동 사용자 조회
        print("\n" + "="*80)
        print("👤 홍길동 사용자 정보")
        print("="*80)
        
        user_query = text("""
            SELECT 
                u.id,
                u.username,
                u.full_name,
                u.email,
                d.dept_name
            FROM tb_user u
            LEFT JOIN tb_sap_hr_info d ON u.dept_id = d.id
            WHERE u.full_name LIKE '%홍길동%' OR u.username LIKE '%hong%'
        """)
        
        user_result = db.execute(user_query)
        user_rows = user_result.fetchall()
        
        if user_rows:
            for user in user_rows:
                print(f"\nID: {user.id}")
                print(f"사용자명: {user.username}")
                print(f"이름: {user.full_name}")
                print(f"이메일: {user.email}")
                print(f"부서: {user.dept_name}")
                
                # 해당 사용자의 권한 신청 내역
                user_requests_query = text("""
                    SELECT 
                        pr.id,
                        kc.container_name,
                        pr.requested_permission_level,
                        pr.status,
                        pr.created_at
                    FROM tb_permission_requests pr
                    LEFT JOIN tb_knowledge_containers kc ON pr.container_id = kc.id
                    WHERE pr.user_id = :user_id
                    ORDER BY pr.created_at DESC
                """)
                
                user_requests = db.execute(user_requests_query, {"user_id": user.id})
                user_request_rows = user_requests.fetchall()
                
                print(f"\n  📝 권한 신청 내역 ({len(user_request_rows)}건):")
                if user_request_rows:
                    for req in user_request_rows:
                        print(f"    - ID {req.id}: {req.container_name} / {req.requested_permission_level} / {req.status} ({req.created_at})")
                else:
                    print("    권한 신청 내역이 없습니다.")
        else:
            print("홍길동 사용자를 찾을 수 없습니다.")
        
        # 3. 인프라컨설팅팀 컨테이너 조회
        print("\n" + "="*80)
        print("📦 인프라컨설팅팀 관련 컨테이너")
        print("="*80)
        
        container_query = text("""
            SELECT 
                kc.id,
                kc.container_id,
                kc.container_name,
                kc.description,
                d.dept_name as owner_dept
            FROM tb_knowledge_containers kc
            LEFT JOIN tb_sap_hr_info d ON kc.owner_dept_id = d.id
            WHERE kc.container_name LIKE '%인프라%' OR d.dept_name LIKE '%인프라%'
        """)
        
        container_result = db.execute(container_query)
        container_rows = container_result.fetchall()
        
        if container_rows:
            for container in container_rows:
                print(f"\nID: {container.id}")
                print(f"컨테이너 ID: {container.container_id}")
                print(f"컨테이너명: {container.container_name}")
                print(f"설명: {container.description}")
                print(f"소유 부서: {container.owner_dept}")
                
                # 해당 컨테이너에 대한 권한 신청
                container_requests_query = text("""
                    SELECT 
                        pr.id,
                        u.full_name,
                        pr.requested_permission_level,
                        pr.status,
                        pr.created_at
                    FROM tb_permission_requests pr
                    LEFT JOIN tb_user u ON pr.user_id = u.id
                    WHERE pr.container_id = :container_id
                    ORDER BY pr.created_at DESC
                """)
                
                container_requests = db.execute(container_requests_query, {"container_id": container.id})
                container_request_rows = container_requests.fetchall()
                
                print(f"\n  📝 권한 신청 내역 ({len(container_request_rows)}건):")
                if container_request_rows:
                    for req in container_request_rows:
                        print(f"    - ID {req.id}: {req.full_name} / {req.requested_permission_level} / {req.status} ({req.created_at})")
                else:
                    print("    권한 신청 내역이 없습니다.")
        else:
            print("인프라컨설팅팀 관련 컨테이너를 찾을 수 없습니다.")
        
        # 4. 상태별 통계
        print("\n" + "="*80)
        print("📊 권한 신청 상태별 통계")
        print("="*80 + "\n")
        
        stats_query = text("""
            SELECT 
                status,
                COUNT(*) as count
            FROM tb_permission_requests
            GROUP BY status
        """)
        
        stats_result = db.execute(stats_query)
        stats_rows = stats_result.fetchall()
        
        for stat in stats_rows:
            print(f"{stat.status}: {stat.count}건")
        
        print("\n" + "="*80 + "\n")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_permission_requests()

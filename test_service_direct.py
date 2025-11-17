"""
백엔드 서비스 직접 테스트
"""
import asyncio
import sys
import os

# backend 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.auth.permission_request_service import PermissionRequestService

async def test_get_my_requests():
    # 데이터베이스 연결
    db_user = os.getenv('DB_USER', 'wkms')
    db_password = os.getenv('DB_PASSWORD', 'wkms123')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'wkms')
    
    database_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            print("=" * 100)
            print("권한 신청 서비스 테스트")
            print("=" * 100 + "\n")
            
            service = PermissionRequestService(session)
            
            # 홍길동 사용자 (77107791)의 권한 신청 조회
            result = await service.get_my_requests(
                requester_emp_no="77107791",
                status=None,
                limit=50
            )
            
            print(f"\n✅ 조회 성공!")
            print(f"Total: {result.get('total', 0)}")
            print(f"Requests count: {len(result.get('requests', []))}")
            
            requests = result.get('requests', [])
            for idx, req in enumerate(requests, 1):
                print(f"\n[{idx}] Request ID: {req.request_id}")
                print(f"    Container ID: {req.container_id}")
                print(f"    Status: {req.request_status}")
                print(f"    Requested Permission: {req.requested_permission}")
                print(f"    Created: {req.created_date}")
                
                # Relationship 확인
                print(f"    Requester: {req.requester}")
                print(f"    Container: {req.knowledge_container}")
                print(f"    Approver: {req.approver}")
                
        except Exception as e:
            print(f"\n❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_get_my_requests())

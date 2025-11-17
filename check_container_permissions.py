"""
사용자 컨테이너 권한 확인 스크립트
"""
import asyncio
import sys
from sqlalchemy import select, and_

sys.path.append('/home/admin/wkms-aws/backend')

from app.core.database import get_async_session_local
from app.models import TbKnowledgeContainers, TbUserPermissions

async def check_container_permissions():
    """사용자 컨테이너 권한 확인"""
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        print("=" * 80)
        print("사용자 컨테이너 권한 확인")
        print("=" * 80)
        
        # USER_로 시작하는 모든 컨테이너 조회
        container_query = select(TbKnowledgeContainers).where(
            and_(
                TbKnowledgeContainers.container_id.like('USER_%'),
                TbKnowledgeContainers.is_active == True
            )
        ).order_by(TbKnowledgeContainers.container_id)
        
        result = await db.execute(container_query)
        containers = result.scalars().all()
        
        for container in containers:
            print(f"\n📁 {container.container_name} ({container.container_id})")
            print(f"   소유자: {container.container_owner}")
            print(f"   타입: {container.container_type}")
            
            # 권한 조회
            perm_query = select(TbUserPermissions).where(
                and_(
                    TbUserPermissions.container_id == container.container_id,
                    TbUserPermissions.is_active == True
                )
            ).order_by(TbUserPermissions.role_id)
            
            result = await db.execute(perm_query)
            permissions = result.scalars().all()
            
            print(f"   권한 목록:")
            for perm in permissions:
                print(f"     🔑 {perm.role_id:10s} - {perm.user_emp_no:15s} (출처: {perm.permission_source})")
            
            # 시스템관리자 권한 확인
            has_admin = any(p.user_emp_no == 'ADMIN001' for p in permissions)
            has_owner = any(p.role_id == 'OWNER' for p in permissions)
            
            status = "✅" if (has_admin and has_owner) else "❌"
            print(f"   {status} 시스템관리자: {'있음' if has_admin else '없음'}, 소유자: {'있음' if has_owner else '없음'}")

if __name__ == "__main__":
    asyncio.run(check_container_permissions())

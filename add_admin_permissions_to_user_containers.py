"""
기존 사용자 컨테이너에 시스템관리자 권한 추가 스크립트
"""
import asyncio
import sys
from sqlalchemy import select, and_
from datetime import datetime, timezone

sys.path.append('/home/admin/wkms-aws/backend')

from app.core.database import get_async_session_local
from app.models import TbKnowledgeContainers, TbUserPermissions

async def add_admin_permissions():
    """모든 사용자 컨테이너에 시스템관리자 권한 추가"""
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        print("=" * 80)
        print("기존 사용자 컨테이너에 시스템관리자 권한 추가")
        print("=" * 80)
        
        # 모든 PERSONAL 타입 컨테이너 조회
        container_query = select(TbKnowledgeContainers).where(
            and_(
                TbKnowledgeContainers.container_type == 'PERSONAL',
                TbKnowledgeContainers.is_active == True
            )
        ).order_by(TbKnowledgeContainers.container_id)
        
        result = await db.execute(container_query)
        containers = result.scalars().all()
        
        print(f"\n📁 총 {len(containers)}개의 사용자 컨테이너 발견")
        
        added_count = 0
        skipped_count = 0
        
        for container in containers:
            print(f"\n처리 중: {container.container_name} ({container.container_id})")
            
            # 이미 시스템관리자 권한이 있는지 확인
            existing_query = select(TbUserPermissions).where(
                and_(
                    TbUserPermissions.container_id == container.container_id,
                    TbUserPermissions.user_emp_no == 'ADMIN001',
                    TbUserPermissions.is_active == True
                )
            )
            result = await db.execute(existing_query)
            existing_perm = result.scalar_one_or_none()
            
            if existing_perm:
                print(f"  ⏭️  이미 권한 존재: {existing_perm.role_id}")
                skipped_count += 1
                continue
            
            # 시스템관리자 권한 추가
            admin_permission = TbUserPermissions(
                user_emp_no='ADMIN001',
                container_id=container.container_id,
                role_id='ADMIN',
                permission_type='DIRECT',
                access_scope='FULL',
                permission_source='SYSTEM_DEFAULT',
                granted_by='SYSTEM',
                granted_date=datetime.now(timezone.utc),
                is_active=True,
                access_count=0
            )
            db.add(admin_permission)
            print(f"  ✅ ADMIN 권한 추가 완료")
            added_count += 1
        
        await db.commit()
        
        print("\n" + "=" * 80)
        print("권한 추가 완료")
        print("=" * 80)
        print(f"✅ 추가된 권한: {added_count}개")
        print(f"⏭️  건너뛴 권한: {skipped_count}개")
        print(f"📊 총 처리: {len(containers)}개 컨테이너")

if __name__ == "__main__":
    asyncio.run(add_admin_permissions())

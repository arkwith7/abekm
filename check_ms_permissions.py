"""
MS서비스팀 관련 권한 확인 및 수정 스크립트
"""
import asyncio
import sys
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append('/home/admin/wkms-aws/backend')

from app.core.database import get_async_session_local
from app.models import TbKnowledgeContainers, TbUserPermissions, TbSapHrInfo

async def check_and_fix_ms_permissions():
    """MS서비스팀 권한 확인 및 수정"""
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        print("=" * 80)
        print("1. 정MS (MSS001) 사용자 정보 확인")
        print("=" * 80)
        
        # 사용자 정보 확인
        user_query = select(TbSapHrInfo).where(TbSapHrInfo.emp_no == 'MSS001')
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()
        
        if user:
            print(f"✅ 사용자: {user.emp_nm} ({user.emp_no})")
            print(f"   부서: {user.dept_nm} ({user.dept_cd})")
            print(f"   직급: {user.postn_nm}")
        else:
            print("❌ MSS001 사용자를 찾을 수 없습니다.")
            return
        
        print("\n" + "=" * 80)
        print("2. MS서비스팀 관련 컨테이너 확인")
        print("=" * 80)
        
        # MS서비스팀 컨테이너 확인
        container_query = select(TbKnowledgeContainers).where(
            or_(
                TbKnowledgeContainers.container_id == 'WJ_MS_SERVICE',
                TbKnowledgeContainers.container_name.like('%MS서비스%'),
                TbKnowledgeContainers.container_name.like('%myMS%')
            )
        ).order_by(TbKnowledgeContainers.org_level)
        
        result = await db.execute(container_query)
        containers = result.scalars().all()
        
        container_map = {}
        for container in containers:
            print(f"\n📁 컨테이너: {container.container_name} ({container.container_id})")
            print(f"   타입: {container.container_type}")
            print(f"   레벨: {container.org_level}")
            print(f"   부모: {container.parent_container_id}")
            print(f"   경로: {container.org_path}")
            print(f"   소유자: {container.container_owner}")
            container_map[container.container_id] = container
        
        print("\n" + "=" * 80)
        print("3. 정MS (MSS001)의 현재 권한 확인")
        print("=" * 80)
        
        # 현재 권한 확인
        perm_query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_emp_no == 'MSS001',
                TbUserPermissions.is_active == True
            )
        )
        result = await db.execute(perm_query)
        current_perms = result.scalars().all()
        
        for perm in current_perms:
            print(f"\n🔑 권한: {perm.role_id}")
            print(f"   컨테이너: {perm.container_id}")
            print(f"   부여자: {perm.granted_by}")
            print(f"   생성일: {perm.granted_date}")
        
        print("\n" + "=" * 80)
        print("4. 권한 수정 계획")
        print("=" * 80)
        
        # WJ_MS_SERVICE 컨테이너 찾기
        ms_service_container = container_map.get('WJ_MS_SERVICE')
        
        if not ms_service_container:
            print("❌ WJ_MS_SERVICE 컨테이너를 찾을 수 없습니다.")
            return
        
        # myMS서비스 컨테이너 찾기 (USER_로 시작하는 컨테이너)
        my_ms_containers = [c for c in containers if c.parent_container_id == 'WJ_MS_SERVICE' and c.container_id.startswith('USER_')]
        
        print(f"\n📋 수정 계획:")
        print(f"1. WJ_MS_SERVICE (MS서비스팀) - MSS001에게 OWNER 권한 부여")
        
        for my_ms in my_ms_containers:
            print(f"2. {my_ms.container_id} ({my_ms.container_name}) - MSS001에게 VIEWER 권한 부여")
        
        print("\n계속하시겠습니까? (y/n): ", end='')
        response = input().strip().lower()
        
        if response != 'y':
            print("취소되었습니다.")
            return
        
        print("\n" + "=" * 80)
        print("5. 권한 수정 실행")
        print("=" * 80)
        
        # WJ_MS_SERVICE에 대한 기존 권한 확인
        existing_perm_query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_emp_no == 'MSS001',
                TbUserPermissions.container_id == 'WJ_MS_SERVICE',
                TbUserPermissions.is_active == True
            )
        )
        result = await db.execute(existing_perm_query)
        existing_perm = result.scalar_one_or_none()
        
        if existing_perm:
            if existing_perm.role_id != 'OWNER':
                # VIEWER를 OWNER로 업데이트
                await db.execute(
                    update(TbUserPermissions)
                    .where(TbUserPermissions.permission_id == existing_perm.permission_id)
                    .values(role_id='OWNER')
                )
                print(f"✅ WJ_MS_SERVICE: {existing_perm.role_id} → OWNER 권한으로 업데이트")
            else:
                print(f"✅ WJ_MS_SERVICE: 이미 OWNER 권한 보유")
        else:
            # 새로운 OWNER 권한 추가
            from datetime import datetime, timezone
            new_perm = TbUserPermissions(
                container_id='WJ_MS_SERVICE',
                user_emp_no='MSS001',
                role_id='OWNER',
                permission_type='DIRECT',
                access_scope='FULL',
                permission_source='ADMIN_ASSIGNED',
                granted_by='SYSTEM',
                is_active=True,
                access_count=0,
                granted_date=datetime.now(timezone.utc)
            )
            db.add(new_perm)
            print(f"✅ WJ_MS_SERVICE: OWNER 권한 새로 추가")
        
        # myMS서비스 하위 컨테이너에 VIEWER 권한 추가
        for my_ms in my_ms_containers:
            existing_child_perm_query = select(TbUserPermissions).where(
                and_(
                    TbUserPermissions.user_emp_no == 'MSS001',
                    TbUserPermissions.container_id == my_ms.container_id,
                    TbUserPermissions.is_active == True
                )
            )
            result = await db.execute(existing_child_perm_query)
            existing_child_perm = result.scalar_one_or_none()
            
            if not existing_child_perm:
                from datetime import datetime, timezone
                new_child_perm = TbUserPermissions(
                    container_id=my_ms.container_id,
                    user_emp_no='MSS001',
                    role_id='VIEWER',
                    permission_type='DIRECT',
                    access_scope='FULL',
                    permission_source='ADMIN_ASSIGNED',
                    granted_by='SYSTEM',
                    is_active=True,
                    access_count=0,
                    granted_date=datetime.now(timezone.utc)
                )
                db.add(new_child_perm)
                print(f"✅ {my_ms.container_id} ({my_ms.container_name}): VIEWER 권한 추가")
            else:
                print(f"✅ {my_ms.container_id} ({my_ms.container_name}): 이미 {existing_child_perm.role_id} 권한 보유")
        
        await db.commit()
        print("\n✅ 권한 수정 완료!")
        
        print("\n" + "=" * 80)
        print("6. 수정 후 권한 확인")
        print("=" * 80)
        
        # 수정 후 권한 재확인
        perm_query = select(TbUserPermissions).where(
            and_(
                TbUserPermissions.user_emp_no == 'MSS001',
                TbUserPermissions.is_active == True
            )
        ).order_by(TbUserPermissions.container_id)
        result = await db.execute(perm_query)
        updated_perms = result.scalars().all()
        
        for perm in updated_perms:
            container = container_map.get(perm.container_id)
            container_name = container.container_name if container else '알 수 없음'
            print(f"\n🔑 {perm.role_id:10s} - {perm.container_id:30s} ({container_name})")

if __name__ == "__main__":
    asyncio.run(check_and_fix_ms_permissions())

#!/usr/bin/env python3
"""
권한 조회 디버깅 스크립트
"""
import asyncio
import sys
import os
sys.path.insert(0, '/home/admin/wkms-aws/backend')

from sqlalchemy.ext.asyncio import create_async_session, AsyncSession
from sqlalchemy import select, and_
from app.models.permission_models import TbUserPermissions, TbKnowledgeContainers
from app.core.database import get_async_engine
from app.services.permission_service import PermissionService

async def test_permission_query():
    """권한 쿼리 직접 테스트"""
    print("=== 권한 조회 디버깅 시작 ===")
    
    # 데이터베이스 연결
    engine = get_async_engine()
    async with AsyncSession(engine) as session:
        print("데이터베이스 연결 성공")
        
        # 직접 SQL 쿼리로 먼저 확인
        print("\n1. 직접 권한 데이터 확인:")
        query1 = select(TbUserPermissions).where(TbUserPermissions.user_emp_no == 'ADMIN001')
        result1 = await session.execute(query1)
        permissions = result1.scalars().all()
        print(f"발견된 권한 수: {len(permissions)}")
        for perm in permissions:
            print(f"  - container_id: {perm.container_id}, permission_type: {perm.permission_type}, is_active: {perm.is_active}")
        
        # 컨테이너 데이터 확인
        print("\n2. 컨테이너 데이터 확인:")
        query2 = select(TbKnowledgeContainers).where(TbKnowledgeContainers.container_id == 'WJ_ROOT')
        result2 = await session.execute(query2)
        containers = result2.scalars().all()
        print(f"발견된 컨테이너 수: {len(containers)}")
        for container in containers:
            print(f"  - container_id: {container.container_id}, container_name: {container.container_name}, is_active: {container.is_active}")
        
        # JOIN 쿼리 테스트
        print("\n3. JOIN 쿼리 테스트:")
        join_query = select(TbUserPermissions, TbKnowledgeContainers).join(
            TbKnowledgeContainers,
            TbUserPermissions.container_id == TbKnowledgeContainers.container_id
        ).where(
            and_(
                TbUserPermissions.user_emp_no == 'ADMIN001',
                TbUserPermissions.is_active == True,
                TbKnowledgeContainers.is_active == True
            )
        )
        join_result = await session.execute(join_query)
        join_data = join_result.all()
        print(f"JOIN 결과 수: {len(join_data)}")
        for permission, container in join_data:
            print(f"  - permission: {permission.user_emp_no}, container: {container.container_name}")
        
        # PermissionService 테스트
        print("\n4. PermissionService 테스트:")
        permission_service = PermissionService(session)
        accessible_containers = await permission_service.get_accessible_containers('ADMIN001')
        print(f"accessible_containers 결과: {accessible_containers}")

if __name__ == "__main__":
    asyncio.run(test_permission_query())

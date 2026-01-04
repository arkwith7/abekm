"""
IPC 데이터 검증 스크립트
IPC 코드 및 권한 데이터의 무결성과 분포 확인

실행 방법:
    cd /home/arkwith/Dev/abekm/backend
    python scripts/verify_ipc_data.py

작성일: 2026-01-04
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select, func

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.models.patent.ipc_models import TbIpcCode, TbIpcPermissions
from app.models import User


async def verify_ipc_data():
    """IPC 데이터 검증"""
    async for session in get_db():
        try:
            print("=" * 60)
            print("IPC 데이터 검증 리포트")
            print("=" * 60)
            print()
            
            # 1. IPC 코드 수 확인
            print("📊 IPC 코드 마스터 데이터")
            print("-" * 60)
            ipc_count_result = await session.execute(
                select(func.count()).select_from(TbIpcCode)
            )
            ipc_count = ipc_count_result.scalar()
            print(f"  전체 IPC 코드: {ipc_count}개")
            
            if ipc_count == 0:
                print("  ❌ IPC 코드가 없습니다. load_ipc_codes.py를 실행하세요.")
                return
            
            # 2. 섹션별 IPC 코드 분포
            print("\n  섹션별 분포:")
            sections_result = await session.execute(
                select(
                    TbIpcCode.section,
                    func.count().label('count')
                ).group_by(TbIpcCode.section)
                .order_by(TbIpcCode.section)
            )
            
            for section, count in sections_result:
                section_name_map = {
                    'H': '전기 (반도체 제조 장비)',
                    'G': '물리학 (검사/측정)',
                    'B': '처리 조작 (핸들링/CMP)',
                    'C': '화학 (증착/코팅)'
                }
                section_name = section_name_map.get(section, section)
                print(f"    {section} ({section_name}): {count}개")
            
            # 3. 레벨별 IPC 코드 분포
            print("\n  레벨별 분포:")
            sections_only = await session.execute(
                select(func.count()).select_from(TbIpcCode)
                .where(TbIpcCode.level == 'SECTION')
            )
            classes = await session.execute(
                select(func.count()).select_from(TbIpcCode)
                .where(TbIpcCode.level == 'CLASS')
            )
            subclasses = await session.execute(
                select(func.count()).select_from(TbIpcCode)
                .where(TbIpcCode.level == 'SUBCLASS')
            )
            groups = await session.execute(
                select(func.count()).select_from(TbIpcCode)
                .where(TbIpcCode.level.in_(['GROUP', 'SUBGROUP']))
            )
            print(f"    섹션 (Section): {sections_only.scalar()}개")
            print(f"    클래스 (Class): {classes.scalar()}개")
            print(f"    서브클래스 (Subclass): {subclasses.scalar()}개")
            print(f"    그룹/서브그룹 (Group): {groups.scalar()}개")
            
            # 4. IPC 권한 수 확인
            print("\n" + "=" * 60)
            print("👥 IPC 권한 데이터")
            print("-" * 60)
            perm_count_result = await session.execute(
                select(func.count()).select_from(TbIpcPermissions)
            )
            perm_count = perm_count_result.scalar()
            print(f"  전체 권한: {perm_count}개")
            
            if perm_count == 0:
                print("  ❌ IPC 권한이 없습니다. load_ipc_permissions.py를 실행하세요.")
                return
            
            # 5. 역할별 권한 분포
            print("\n  역할별 분포:")
            roles_result = await session.execute(
                select(
                    TbIpcPermissions.role_id,
                    func.count().label('count')
                ).group_by(TbIpcPermissions.role_id)
                .order_by(TbIpcPermissions.role_id)
            )
            
            for role, count in roles_result:
                role_name_map = {
                    'ADMIN': '관리자 (전체 권한)',
                    'EDITOR': '편집자 (수정 가능)',
                    'VIEWER': '조회자 (읽기 전용)'
                }
                role_name = role_name_map.get(role, role)
                print(f"    {role} ({role_name}): {count}개")
            
            # 6. 사용자별 권한 분포
            print("\n  사용자별 권한:")
            users_result = await session.execute(
                select(
                    TbIpcPermissions.user_emp_no,
                    func.count().label('count')
                ).group_by(TbIpcPermissions.user_emp_no)
                .order_by(TbIpcPermissions.user_emp_no)
            )
            
            for emp_no, count in users_result:
                # 사용자 정보는 건너뛰고 사번만 표시
                print(f"    {emp_no}: {count}개 권한")
            
            # 7. IPC 코드별 권한 할당 현황
            print("\n  IPC 코드별 권한 할당:")
            ipc_perms_result = await session.execute(
                select(
                    TbIpcPermissions.ipc_code,
                    func.count().label('count')
                ).group_by(TbIpcPermissions.ipc_code)
                .order_by(func.count().desc())
            )
            
            for ipc_code, count in ipc_perms_result:
                # IPC 코드 이름 조회
                ipc_name_result = await session.execute(
                    select(TbIpcCode.description_ko).where(TbIpcCode.code == ipc_code)
                )
                ipc_name = ipc_name_result.scalar()
                print(f"    {ipc_code} ({ipc_name}): {count}명")
            
            # 8. 비활성 권한 확인
            print("\n" + "=" * 60)
            print("⚠️  데이터 품질 검사")
            print("-" * 60)
            inactive_perms = await session.execute(
                select(func.count()).select_from(TbIpcPermissions)
                .where(TbIpcPermissions.is_active == False)
            )
            inactive_count = inactive_perms.scalar()
            if inactive_count > 0:
                print(f"  ⚠️  비활성 권한: {inactive_count}개")
            else:
                print(f"  ✅ 모든 권한 활성화 상태")
            
            # 9. 고아 권한 확인 (IPC 코드 미존재)
            orphan_perms = await session.execute(
                select(TbIpcPermissions.ipc_code)
                .outerjoin(TbIpcCode, TbIpcPermissions.ipc_code == TbIpcCode.code)
                .where(TbIpcCode.code.is_(None))
            )
            orphan_list = orphan_perms.scalars().all()
            if orphan_list:
                print(f"  ⚠️  고아 권한 (IPC 코드 미존재): {len(orphan_list)}개")
                for ipc_code in orphan_list:
                    print(f"      - {ipc_code}")
            else:
                print(f"  ✅ 모든 권한이 유효한 IPC 코드 참조")
            
            # 10. 중복 권한 확인
            duplicate_perms = await session.execute(
                select(
                    TbIpcPermissions.user_emp_no,
                    TbIpcPermissions.ipc_code,
                    func.count().label('count')
                ).group_by(
                    TbIpcPermissions.user_emp_no,
                    TbIpcPermissions.ipc_code
                ).having(func.count() > 1)
            )
            duplicate_list = duplicate_perms.all()
            if duplicate_list:
                print(f"  ⚠️  중복 권한: {len(duplicate_list)}개")
                for emp_no, ipc_code, count in duplicate_list:
                    print(f"      - {emp_no} + {ipc_code}: {count}개")
            else:
                print(f"  ✅ 중복 권한 없음")
            
            print("\n" + "=" * 60)
            print("✅ 검증 완료!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break  # 첫 번째 세션만 사용


if __name__ == "__main__":
    asyncio.run(verify_ipc_data())

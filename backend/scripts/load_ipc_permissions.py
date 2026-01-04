"""
IPC 권한 초기 데이터 적재 스크립트
조직별 IPC 코드 권한 할당

실행 방법:
    cd /home/arkwith/Dev/abekm/backend
    python scripts/load_ipc_permissions.py

작성일: 2026-01-04
"""
import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.models.patent.ipc_models import TbIpcPermissions


async def load_ipc_permissions():
    """CSV 파일에서 IPC 권한 초기 데이터 로드"""
    csv_path = Path(__file__).parent.parent / "data" / "ipc_permissions_initial.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV 파일이 존재하지 않습니다: {csv_path}")
        return
    
    print(f"📂 CSV 파일 경로: {csv_path}")
    
    async for session in get_db():
        try:
            # 기존 데이터 확인
            existing_count = await session.execute(
                select(TbIpcPermissions).limit(1)
            )
            if existing_count.scalar():
                print("⚠️  기존 IPC 권한 데이터가 존재합니다.")
                response = input("삭제하고 다시 로드하시겠습니까? (y/N): ")
                if response.lower() != 'y':
                    print("취소되었습니다.")
                    return
                
                # 기존 데이터 삭제
                await session.execute(text("DELETE FROM tb_ipc_permissions"))
                await session.commit()
                print("✅ 기존 데이터 삭제 완료")
            
            # CSV 파일 읽기 및 적재
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                user_summary = {}
                
                for row in reader:
                    permission = TbIpcPermissions(
                        user_emp_no=row['user_emp_no'],
                        ipc_code=row['ipc_code'],
                        role_id=row['role_id'],
                        access_scope='FULL',
                        include_children=True,
                        is_active=True,
                        created_by=row['created_by']
                    )
                    session.add(permission)
                    count += 1
                    
                    # 사용자별 요약
                    emp_no = row['user_emp_no']
                    if emp_no not in user_summary:
                        user_summary[emp_no] = []
                    user_summary[emp_no].append(f"{row['ipc_code']} ({row['role_id']})")
                    
                    print(f"  {count}. {row['user_emp_no']} → {row['ipc_code']} ({row['role_id']})")
                
                await session.commit()
                print(f"\n✅ {count}개 IPC 권한 할당 완료!")
                
                print("\n👥 사용자별 권한 요약:")
                for emp_no, permissions in user_summary.items():
                    print(f"   {emp_no}: {', '.join(permissions)}")
                
                print("\n📊 역할별 분포:")
                print("   ADMIN: 전체 섹션 (H, G, B, C)")
                print("   EDITOR: 주요 기술 분야 (H01L, H05H, G01N, G01B, B24B, C23C)")
                print("   VIEWER: 세부 공정 (H01L21/00, G01N21/95)")
                
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
            await session.rollback()
            raise
        finally:
            break  # 첫 번째 세션만 사용


if __name__ == "__main__":
    print("=" * 60)
    print("IPC 권한 초기 데이터 적재 스크립트")
    print("반도체 장비 업종 조직별 권한 할당 (12개 권한)")
    print("=" * 60)
    print()
    
    asyncio.run(load_ipc_permissions())

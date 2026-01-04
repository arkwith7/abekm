"""
IPC 코드 마스터 데이터 적재 스크립트
반도체 장비 업종 특화 IPC 코드 23개 적재

실행 방법:
    cd /home/arkwith/Dev/abekm/backend
    python scripts/load_ipc_codes.py

작성일: 2026-01-04
"""
import asyncio
import csv
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.models.patent.ipc_models import TbIpcCode


async def load_ipc_codes():
    """CSV 파일에서 IPC 코드 마스터 데이터 로드"""
    csv_path = Path(__file__).parent.parent / "data" / "ipc_codes_semiconductor.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV 파일이 존재하지 않습니다: {csv_path}")
        return
    
    print(f"📂 CSV 파일 경로: {csv_path}")
    
    async for session in get_db():
        try:
            # 기존 데이터 확인
            existing_count = await session.execute(
                select(TbIpcCode).limit(1)
            )
            if existing_count.scalar():
                print("⚠️  기존 IPC 코드 데이터가 존재합니다.")
                response = input("삭제하고 다시 로드하시겠습니까? (y/N): ")
                if response.lower() != 'y':
                    print("취소되었습니다.")
                    return
                
                # 기존 데이터 삭제
                await session.execute(text("DELETE FROM tb_ipc_code"))
                await session.commit()
                print("✅ 기존 데이터 삭제 완료")
            
            # CSV 파일 읽기 및 적재
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                
                for row in reader:
                    # IPC 계층 레벨 결정
                    code = row['ipc_code']
                    if len(code) == 1:
                        level = 'SECTION'
                        parent_code = None
                    elif '/' in code:
                        if code.count('/') == 1 and code.endswith('/00'):
                            level = 'GROUP'
                        else:
                            level = 'SUBGROUP'
                        # 상위 코드는 '/' 이전 부분
                        parent_code = code.split('/')[0]
                    elif len(code) == 4:
                        level = 'SUBCLASS'
                        parent_code = code[:3]
                    elif len(code) == 3:
                        level = 'CLASS'
                        parent_code = code[0]
                    else:
                        level = 'UNKNOWN'
                        parent_code = None
                    
                    ipc_code = TbIpcCode(
                        code=code,
                        level=level,
                        parent_code=parent_code,
                        description_ko=row['korean_name'],
                        description_en=row['english_name'],
                        section=row['ipc_section'] if row['ipc_section'] else None,
                        class_code=f"{row['ipc_section']}{row['ipc_class']}" if row['ipc_class'] else None,
                        subclass_code=f"{row['ipc_section']}{row['ipc_class']}{row['ipc_subclass']}" if row['ipc_subclass'] else None,
                        is_active='Y' if row['is_active'].lower() == 'true' else 'N'
                    )
                    session.add(ipc_code)
                    count += 1
                    print(f"  {count}. {code} [{level}]: {row['korean_name']}")
                
                await session.commit()
                print(f"\n✅ {count}개 IPC 코드 적재 완료!")
                print("\n📊 섹션별 분포:")
                print("   H (전기): 11개 - 반도체 제조 장비")
                print("   G (물리학): 3개 - 검사/측정 장비")
                print("   B (처리 조작): 3개 - 핸들링/CMP")
                print("   C (화학): 3개 - 증착/코팅")
                
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
            await session.rollback()
            raise
        finally:
            break  # 첫 번째 세션만 사용


if __name__ == "__main__":
    print("=" * 60)
    print("IPC 코드 마스터 데이터 적재 스크립트")
    print("반도체 장비 업종 특화 (23개 코드)")
    print("=" * 60)
    print()
    
    asyncio.run(load_ipc_codes())

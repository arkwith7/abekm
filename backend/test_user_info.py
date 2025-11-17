import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_async_session_local
from sqlalchemy import text

async def test_user_data():
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        try:
            # 사용자 정보 조회
            result = await session.execute(
                text("SELECT emp_no, username, email, is_active, is_admin FROM tb_user LIMIT 3")
            )
            users = result.fetchall()
            print("사용자 목록:")
            for user in users:
                print(f"  - {user.username} ({user.emp_no}): {user.email}")
            
            # 특정 사용자 정보 조회 (MS 서비스팀)
            result = await session.execute(
                text("""
                    SELECT u.emp_no, u.username, u.email, u.is_active, u.is_admin,
                           h.emp_nm, h.dept_nm, h.postn_nm, h.telno, h.entrps_de
                    FROM tb_user u
                    LEFT JOIN tb_sap_hr_info h ON u.emp_no = h.emp_no
                    WHERE u.username = 'ms.staff'
                """)
            )
            user_detail = result.fetchone()
            if user_detail:
                print(f"\n사용자 상세 정보 (ms.staff):")
                print(f"  사원번호: {user_detail.emp_no}")
                print(f"  이름: {user_detail.emp_nm}")
                print(f"  부서: {user_detail.dept_nm}")
                print(f"  직급: {user_detail.postn_nm}")
                print(f"  이메일: {user_detail.email}")
                print(f"  전화번호: {user_detail.telno}")
            else:
                print("ms.staff 사용자를 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"오류: {e}")

if __name__ == "__main__":
    asyncio.run(test_user_data())
